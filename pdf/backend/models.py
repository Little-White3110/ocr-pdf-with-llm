from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    QUEUED = "queued"
    PROCESSING = "processing"
    OCR_PROCESSING = "ocr_processing"
    OUTLINE_GENERATING = "outline_generating"
    COMPLETED = "completed"
    FAILED = "failed"

class OutlineMode(str, Enum):
    AUTO = "auto"
    TOC_PAGE = "toc_page"

class TaskOptions(BaseModel):
    generate_outline: bool = False
    outline_mode: OutlineMode = OutlineMode.AUTO
    toc_page_start: Optional[int] = None
    toc_page_end: Optional[int] = None
    page_offset: int = 0
    embed_outline: bool = True

class TaskCreate(BaseModel):
    filename: str
    options: TaskOptions

class TaskProgress(BaseModel):
    stage: str
    progress: int
    message: str

class Task(BaseModel):
    id: str
    filename: str
    original_filename: str
    status: TaskStatus
    progress: TaskProgress
    options: TaskOptions
    error: Optional[str] = None
    output_filename: Optional[str] = None
    queue_position: Optional[int] = None

class LLMConfig(BaseModel):
    api_key: str
    base_url: str = "https://api.deepseek.com/v1"
    model: str = "deepseek-chat"

class LLMTestResult(BaseModel):
    success: bool
    message: str
