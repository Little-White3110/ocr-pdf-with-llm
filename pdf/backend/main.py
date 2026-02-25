import os
import zipfile
import tempfile
import time
import asyncio
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from models import Task, TaskOptions, LLMConfig, LLMTestResult, OutlineMode
from task_manager import task_manager
from config import settings, save_llm_config, load_llm_config
from llm_service import llm_service

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.output_dir, exist_ok=True)

CLEANUP_INTERVAL = 30 * 60
FILE_MAX_AGE = 30 * 60

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_cleanup())

async def periodic_cleanup():
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        cleanup_old_files()

def cleanup_old_files():
    now = time.time()
    cleaned = 0
    
    for directory in [settings.upload_dir, settings.output_dir]:
        if not os.path.exists(directory):
            continue
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath):
                file_age = now - os.path.getmtime(filepath)
                if file_age > FILE_MAX_AGE:
                    try:
                        os.remove(filepath)
                        cleaned += 1
                        print(f"Cleaned up old file: {filepath}")
                    except Exception as e:
                        print(f"Failed to clean up {filepath}: {e}")
    
    if cleaned > 0:
        print(f"Periodic cleanup: removed {cleaned} files")
    
    return cleaned

class TaskOptionsRequest(BaseModel):
    generate_outline: bool = False
    outline_mode: str = "auto"
    toc_page_start: Optional[int] = None
    toc_page_end: Optional[int] = None
    page_offset: int = 0
    embed_outline: bool = True

@app.get("/")
async def root():
    return {"message": "PDF OCR Web API", "version": "1.0.0"}

@app.get("/api/tasks")
async def get_tasks():
    return task_manager.get_all_tasks()

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    generate_outline: bool = False,
    outline_mode: str = "auto",
    toc_page_start: Optional[int] = None,
    toc_page_end: Optional[int] = None,
    page_offset: int = 0,
    embed_outline: bool = True
):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持 PDF 文件")
    
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    
    if file_size > settings.max_file_size:
        raise HTTPException(status_code=400, detail="文件大小超过 500MB 限制")
    
    options = TaskOptions(
        generate_outline=generate_outline,
        outline_mode=OutlineMode(outline_mode),
        toc_page_start=toc_page_start,
        toc_page_end=toc_page_end,
        page_offset=page_offset,
        embed_outline=embed_outline
    )
    
    task = task_manager.create_task(file.filename, options)
    
    file_path = os.path.join(settings.upload_dir, task.filename)
    
    task_manager.update_task_status(task.id, "uploading")
    task_manager.update_task_progress(task.id, "uploading", 0, "正在上传...")
    
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        task_manager.update_task_progress(task.id, "uploading", 100, "上传完成")
        
        background_tasks.add_task(task_manager.add_to_queue, task.id)
        
        return task
    except Exception as e:
        task_manager.update_task_status(task.id, "failed", str(e))
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

@app.get("/api/download/{task_id}")
async def download_file(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    output_path = os.path.join(settings.output_dir, f"{task_id}_{task.output_filename}")
    
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(
        path=output_path,
        filename=task.output_filename,
        media_type="application/pdf"
    )

@app.post("/api/download/batch")
async def download_batch(task_ids: List[str]):
    tasks = []
    for task_id in task_ids:
        task = task_manager.get_task(task_id)
        if task and task.status == "completed":
            tasks.append(task)
    
    if not tasks:
        raise HTTPException(status_code=400, detail="没有可下载的文件")
    
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        with zipfile.ZipFile(tmp.name, 'w', zipfile.ZIP_DEFLATED) as zf:
            for task in tasks:
                file_path = os.path.join(settings.output_dir, f"{task.id}_{task.output_filename}")
                if os.path.exists(file_path):
                    zf.write(file_path, task.output_filename)
        
        return FileResponse(
            path=tmp.name,
            filename="OCR_PDFs.zip",
            media_type="application/zip"
        )

@app.get("/api/download/text/{task_id}")
async def download_text_file(task_id: str):
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    output_path = os.path.join(settings.output_dir, f"{task_id}_{task.output_filename}")
    text_path = output_path.replace('.pdf', '.txt')
    
    if not os.path.exists(text_path):
        raise HTTPException(status_code=404, detail="文本文件不存在")
    
    text_filename = task.output_filename.replace('.pdf', '.txt')
    
    return FileResponse(
        path=text_path,
        filename=text_filename,
        media_type="text/plain"
    )

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    if task_manager.delete_task(task_id):
        return {"message": "任务已删除"}
    raise HTTPException(status_code=404, detail="任务不存在")

@app.get("/api/llm/config")
async def get_llm_config():
    config = load_llm_config()
    return {
        "api_key": "***" if config.get("api_key") else "",
        "base_url": config.get("base_url", settings.llm_base_url),
        "model": config.get("model", settings.llm_model),
        "has_api_key": bool(config.get("api_key"))
    }

@app.post("/api/llm/config")
async def set_llm_config(config: LLMConfig):
    save_llm_config(config.api_key, config.base_url, config.model)
    llm_service.config = load_llm_config()
    return {"message": "配置已保存"}

@app.post("/api/llm/test")
async def test_llm_connection(config: LLMConfig):
    success, message = await llm_service.test_connection(
        config.api_key,
        config.base_url,
        config.model
    )
    return LLMTestResult(success=success, message=message)

@app.post("/api/cleanup")
async def manual_cleanup():
    cleaned = cleanup_old_files()
    return {"message": f"清理完成，删除了 {cleaned} 个文件"}

@app.post("/api/cleanup/all")
async def cleanup_all():
    cleaned = 0
    for directory in [settings.upload_dir, settings.output_dir]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath):
                    try:
                        os.remove(filepath)
                        cleaned += 1
                    except Exception as e:
                        print(f"Failed to clean up {filepath}: {e}")
    task_manager.tasks.clear()
    return {"message": f"清理完成，删除了 {cleaned} 个文件"}

@app.get("/api/storage")
async def get_storage_info():
    upload_size = 0
    output_size = 0
    upload_files = 0
    output_files = 0
    
    for directory, size_var, count_var in [
        (settings.upload_dir, 'upload_size', 'upload_files'),
        (settings.output_dir, 'output_size', 'output_files')
    ]:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath):
                    if directory == settings.upload_dir:
                        upload_size += os.path.getsize(filepath)
                        upload_files += 1
                    else:
                        output_size += os.path.getsize(filepath)
                        output_files += 1
    
    return {
        "upload_dir": {
            "size_mb": round(upload_size / (1024 * 1024), 2),
            "files": upload_files
        },
        "output_dir": {
            "size_mb": round(output_size / (1024 * 1024), 2),
            "files": output_files
        },
        "total_size_mb": round((upload_size + output_size) / (1024 * 1024), 2),
        "total_files": upload_files + output_files
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
