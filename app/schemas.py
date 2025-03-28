from datetime import datetime
from pydantic import BaseModel, computed_field, field_serializer, model_serializer, ConfigDict
from typing import Optional, Literal, Dict, Any, List
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    VIP = "vip"
    NORMAL = "normal"

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobAction(str, Enum):
    PAUSE = "pause"
    RESUME = "resume"
    CANCEL = "cancel"
    RETRY = "retry"

class JobTaskType(str, Enum):
    PROCESS_UPLOAD = "process_upload"
    CONVERT_TO_MARKDOWN = "convert_to_markdown"
    PROCESS_WITH_LLM = "process_with_llm"
    PROCESS_AI_REVIEW = "process_ai_review"
    EXTRACT_STRUCTURED_DATA = "extract_structured_data"

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    role: UserRole
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# 文章类型相关模型
class ArticleTypeBase(BaseModel):
    name: str
    is_public: bool
    config: Dict[str, Any] | None = None

class ArticleTypeCreate(ArticleTypeBase):
    pass

class ArticleType(ArticleTypeBase):
    id: int
    owner_id: int | None

    model_config = ConfigDict(from_attributes=True)

class ArticleTypeUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

# 附件相关模型
class AttachmentSchema(BaseModel):
    path: str
    is_active: bool
    filename: str
    created_at: str

# 文章相关模型
class ArticleBase(BaseModel):
    name: str
    attachments: list[AttachmentSchema]
    article_type_id: int

class ArticleCreate(ArticleBase):
    name: str
    attachments: List[Dict[str, Any]] = []
    article_type_id: int
    project_id: int

class Article(ArticleBase):
    id: int
    created_at: datetime
    json_result: Dict = {}
    project_id: int | None = None
    
    model_config = ConfigDict(from_attributes=True)

    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat() if dt else None

class ArticleUpdate(BaseModel):
    name: Optional[str] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    article_type_id: Optional[int] = None
    active_ai_review_report_id: Optional[int] = None

class AttachmentUpdate(BaseModel):
    is_active: bool

# AI批阅报告相关模型
class AIReviewReportBase(BaseModel):
    source_data: str | None = None
    processed_attachment_text: str | None = None

class AIReviewReportCreate(AIReviewReportBase):
    article_id: int
    source_data: str = ""
    structured_data: Optional[Dict[str, Any]] = None
    status: str = "pending"

class AIReviewReport(AIReviewReportBase):
    id: int
    article_id: int
    created_at: datetime
    job_id: int | None
    status: str = "pending"
    structured_data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat() if dt else None


class AIReviewReportUpdate(BaseModel):
    source_data: Optional[str] = None
    status: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None

# 项目相关模型
class ProjectBase(BaseModel):
    name: str
    config: Dict[str, Any] | None = None
    auto_approve: bool = True

class ProjectCreate(BaseModel):
    name: Optional[str] = None
    auto_approve: bool = True
    article_type_id: int
    config: Optional[Dict[str, Any]] = None

class Project(ProjectBase):
    id: int
    owner_id: int
    article_type_id: int

    model_config = ConfigDict(from_attributes=True)

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    auto_approve: Optional[bool] = None

# JobTask相关模型
class JobTaskBase(BaseModel):
    task_type: JobTaskType
    status: JobStatus
    progress: Optional[int] = None
    logs: Optional[str] = None
    article_id: Optional[int] = None
    params: Optional[Dict[str, Any]] = None

class JobTaskCreate(BaseModel):
    task_type: JobTaskType
    article_id: Optional[int] = None
    params: Optional[Dict[str, Any]] = None

class JobTask(JobTaskBase):
    id: int
    job_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat() if dt else None

class JobTaskUpdate(BaseModel):
    status: Optional[JobStatus] = None
    progress: Optional[int] = None
    logs: Optional[str] = None
    params: Optional[Dict[str, Any]] = None

# Job相关模型
class JobBase(BaseModel):
    name: Optional[str] = None
    status: JobStatus
    progress: Optional[int] = None
    logs: Optional[str] = None
    parallelism: Optional[int] = 1

class JobCreate(BaseModel):
    project_id: Optional[int] = None
    name: Optional[str] = None
    parallelism: Optional[int] = 1
    tasks: List[JobTaskCreate]

class Job(JobBase):
    id: int
    uuid: str
    project_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    tasks: List[JobTask] = []

    model_config = ConfigDict(from_attributes=True)

    @model_serializer
    def serialize_model(self) -> dict:
        return {
            "id": self.id,
            "uuid": self.uuid,
            "project_id": self.project_id,
            "name": self.name,
            "status": self.status,
            "progress": self.progress,
            "logs": self.logs,
            "parallelism": self.parallelism,
            "tasks": [task for task in self.tasks],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class JobUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[JobStatus] = None
    progress: Optional[int] = None
    logs: Optional[str] = None
    parallelism: Optional[int] = None

class JobActionRequest(BaseModel):
    action: JobAction
    task_id: Optional[int] = None  # 可选，指定要操作的特定任务ID

class UserStats(BaseModel):
    article_count: int
    project_count: int
    article_type_count: int
    total_jobs: int
    active_jobs: int
