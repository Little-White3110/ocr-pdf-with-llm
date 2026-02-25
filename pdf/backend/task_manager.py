import asyncio
import uuid
import os
import shutil
from typing import Dict, Optional, Set
from datetime import datetime
from models import Task, TaskStatus, TaskProgress, TaskOptions, OutlineMode
from ocr_service import ocr_processor
from llm_service import llm_service
from config import settings

class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.queue: asyncio.Queue = asyncio.Queue()
        self.processing = False
        self.cancelled_tasks: Set[str] = set()
        self._ensure_directories()
    
    def _ensure_directories(self):
        os.makedirs(settings.upload_dir, exist_ok=True)
        os.makedirs(settings.output_dir, exist_ok=True)
    
    def create_task(self, original_filename: str, options: TaskOptions) -> Task:
        task_id = str(uuid.uuid4())
        filename = f"{task_id}_{original_filename}"
        
        task = Task(
            id=task_id,
            filename=filename,
            original_filename=original_filename,
            status=TaskStatus.PENDING,
            progress=TaskProgress(
                stage="pending",
                progress=0,
                message="等待上传"
            ),
            options=options
        )
        
        self.tasks[task_id] = task
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> list[Task]:
        return list(self.tasks.values())
    
    def update_task_progress(self, task_id: str, stage: str, progress: int, message: str):
        if task_id in self.tasks:
            self.tasks[task_id].progress = TaskProgress(
                stage=stage,
                progress=progress,
                message=message
            )
    
    def update_task_status(self, task_id: str, status: TaskStatus, error: Optional[str] = None):
        if task_id in self.tasks:
            self.tasks[task_id].status = status
            if error:
                self.tasks[task_id].error = error
    
    def set_queue_position(self, task_id: str, position: Optional[int]):
        if task_id in self.tasks:
            self.tasks[task_id].queue_position = position
    
    def is_cancelled(self, task_id: str) -> bool:
        return task_id in self.cancelled_tasks
    
    async def add_to_queue(self, task_id: str):
        await self.queue.put(task_id)
        position = self.queue.qsize()
        self.set_queue_position(task_id, position)
        self.update_task_status(task_id, TaskStatus.QUEUED)
        self.update_task_progress(task_id, "queued", 0, f"队列位置: {position}")
        
        if not self.processing:
            asyncio.create_task(self._process_queue())
    
    async def _process_queue(self):
        self.processing = True
        
        while not self.queue.empty():
            task_id = await self.queue.get()
            task = self.get_task(task_id)
            
            if task and not self.is_cancelled(task_id):
                self.set_queue_position(task_id, None)
                await self._process_task(task)
            elif self.is_cancelled(task_id):
                self.cancelled_tasks.discard(task_id)
        
        self.processing = False
    
    async def _process_task(self, task: Task):
        try:
            if self.is_cancelled(task.id):
                return
            
            self.update_task_status(task.id, TaskStatus.PROCESSING)
            self.update_task_progress(task.id, "processing", 5, "开始处理...")
            
            input_path = os.path.join(settings.upload_dir, task.filename)
            output_filename = f"OCR-{task.original_filename}"
            output_path = os.path.join(settings.output_dir, f"{task.id}_{output_filename}")
            
            def progress_callback(progress: int, message: str):
                if not self.is_cancelled(task.id):
                    self.update_task_progress(task.id, "ocr_processing", progress, message)
            
            if self.is_cancelled(task.id):
                return
            
            self.update_task_status(task.id, TaskStatus.OCR_PROCESSING)
            self.update_task_progress(task.id, "ocr_processing", 10, "正在进行 OCR 处理...")
            
            await ocr_processor.process_pdf(
                input_path, 
                output_path, 
                progress_callback,
                is_cancelled=lambda: self.is_cancelled(task.id)
            )
            
            if self.is_cancelled(task.id):
                return
            
            if task.options.generate_outline:
                self.update_task_status(task.id, TaskStatus.OUTLINE_GENERATING)
                self.update_task_progress(task.id, "outline_generating", 70, "正在生成大纲...")
                
                if self.is_cancelled(task.id):
                    return
                
                outline = None
                
                if task.options.outline_mode == OutlineMode.TOC_PAGE:
                    if task.options.toc_page_start and task.options.toc_page_end:
                        toc_text = ocr_processor.extract_text_from_pages(
                            output_path,
                            task.options.toc_page_start,
                            task.options.toc_page_end
                        )
                        outline = await llm_service.generate_outline_from_toc(
                            toc_text,
                            task.options.page_offset
                        )
                else:
                    content = ocr_processor.extract_all_text(output_path)
                    outline = await llm_service.generate_outline_from_content(content)
                
                if self.is_cancelled(task.id):
                    return
                
                if outline and task.options.embed_outline:
                    self.update_task_progress(task.id, "outline_generating", 85, "正在嵌入大纲...")
                    temp_output = output_path + ".temp"
                    llm_service.embed_outline_to_pdf(output_path, temp_output, outline)
                    shutil.move(temp_output, output_path)
            
            if self.is_cancelled(task.id):
                return
            
            self.update_task_progress(task.id, "completed", 100, "处理完成")
            self.update_task_status(task.id, TaskStatus.COMPLETED)
            self.tasks[task.id].output_filename = output_filename
            
        except Exception as e:
            if not self.is_cancelled(task.id):
                self.update_task_status(task.id, TaskStatus.FAILED, str(e))
                self.update_task_progress(task.id, "failed", 0, f"处理失败: {str(e)}")
    
    def delete_task(self, task_id: str) -> bool:
        if task_id in self.tasks:
            task = self.tasks[task_id]
            
            if task.status in [TaskStatus.PROCESSING, TaskStatus.OCR_PROCESSING, TaskStatus.OUTLINE_GENERATING]:
                self.cancelled_tasks.add(task_id)
                self.update_task_status(task_id, TaskStatus.FAILED, "任务已取消")
                print(f"Task {task_id} cancelled")
            
            input_path = os.path.join(settings.upload_dir, task.filename)
            if os.path.exists(input_path):
                os.remove(input_path)
            
            if task.output_filename:
                output_path = os.path.join(settings.output_dir, f"{task_id}_{task.output_filename}")
                if os.path.exists(output_path):
                    os.remove(output_path)
                
                text_path = output_path.replace('.pdf', '.txt')
                if os.path.exists(text_path):
                    os.remove(text_path)
            
            del self.tasks[task_id]
            return True
        return False

task_manager = TaskManager()
