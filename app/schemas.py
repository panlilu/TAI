from pydantic import BaseModel
from typing import Optional
from .models import UserRole

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    role: UserRole
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# 文章类型相关模型
class ArticleTypeBase(BaseModel):
    name: str
    is_public: bool
    prompt: str
    fields: list[str]

class ArticleTypeCreate(ArticleTypeBase):
    pass

class ArticleType(ArticleTypeBase):
    id: int
    owner_id: int

    class Config:
        from_attributes = True

class ArticleTypeUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    fields: Optional[list[str]] = None

# 文章相关模型
class ArticleBase(BaseModel):
    name: str
    attachments: list[str]
    article_type_id: int

class ArticleCreate(ArticleBase):
    pass

class Article(ArticleBase):
    id: int
    created_at: str

    class Config:
        from_attributes = True

class ArticleUpdate(BaseModel):
    name: Optional[str] = None
    attachments: Optional[list[str]] = None

# AI批阅报告相关模型
class AIReviewReportBase(BaseModel):
    source_data: str
    structured_data: dict

class AIReviewReportCreate(AIReviewReportBase):
    article_id: int

class AIReviewReport(AIReviewReportBase):
    id: int
    article_id: int
    created_at: str
    is_active: bool

    class Config:
        from_attributes = True

class AIReviewReportUpdate(BaseModel):
    source_data: Optional[str] = None
    structured_data: Optional[dict] = None
    is_active: Optional[bool] = None

# 项目相关模型
class ProjectBase(BaseModel):
    name: str
    prompt: str
    fields: list[str]
    auto_approve: bool = True

class ProjectCreate(ProjectBase):
    article_type_id: int

class Project(ProjectBase):
    id: int
    owner_id: int
    article_type_id: int

    class Config:
        from_attributes = True

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    prompt: Optional[str] = None
    fields: Optional[list[str]] = None
    auto_approve: Optional[bool] = None
