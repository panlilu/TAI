from datetime import datetime
from pydantic import BaseModel, computed_field, field_serializer, model_serializer
from typing import Optional, Literal, Dict, Any
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

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    role: UserRole
    is_active: bool

    model_config = {
        "from_attributes": True
    }

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

    model_config = {
        "from_attributes": True
    }

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
    pass

class Article(ArticleBase):
    id: int
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat() if dt else None

class ArticleUpdate(BaseModel):
    name: Optional[str] = None
    attachments: Optional[list[AttachmentSchema]] = None

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
    is_active: bool
    job_id: int | None
    status: str = "pending"
    structured_data: Optional[Dict[str, Any]] = None

    model_config = {
        "from_attributes": True
    }

    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat() if dt else None


class AIReviewReportUpdate(BaseModel):
    source_data: Optional[str] = None
    is_active: Optional[bool] = None
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

class Project(ProjectBase):
    id: int
    owner_id: int
    article_type_id: int

    model_config = {
        "from_attributes": True
    }

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    auto_approve: Optional[bool] = None

# Job相关模型
class JobBase(BaseModel):
    task: str
    status: JobStatus
    progress: Optional[int] = None
    logs: Optional[str] = None

class JobCreate(BaseModel):
    project_id: Optional[int] = None
    task: JobTaskType
    article_id: Optional[int] = None

class Job(JobBase):
    id: int
    project_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

    @model_serializer
    def serialize_model(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "task": self.task,
            "status": self.status,
            "progress": self.progress,
            "logs": self.logs,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

class JobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    progress: Optional[int] = None
    logs: Optional[str] = None

class JobActionRequest(BaseModel):
    action: JobAction
