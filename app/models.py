from sqlalchemy import Column, Integer, String, ForeignKey, Float, DateTime, Enum as SQLAlchemyEnum, Boolean, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB, JSON
import uuid
from .database import Base
from .schemas import UserRole, JobStatus, JobTaskType

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(SQLAlchemyEnum(UserRole), default=UserRole.NORMAL)
    is_active = Column(Boolean, default=True)
    
    article_types = relationship("ArticleType", back_populates="owner")
    projects = relationship("Project", back_populates="owner")

class ArticleType(Base):
    __tablename__ = "article_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # 文章类型名称
    is_public = Column(Boolean, default=False)  # 是否为公共类型
    config = Column(JSON, nullable=False, server_default='{}')  # 配置信息，包含prompt等
    owner_id = Column(Integer, ForeignKey("users.id"))  # 创建者ID
    
    owner = relationship("User", back_populates="article_types")
    articles = relationship("Article", back_populates="article_type")

class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # 文章名称
    attachments = Column(JSON)  # 附件列表
    article_type_id = Column(Integer, ForeignKey("article_types.id"))  # 文章类型ID
    json_result = Column(JSON, nullable=False, server_default='{}')  # AI审阅结果
    project_id = Column(Integer, ForeignKey("projects.id"))  # 项目ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 创建时间
    active_ai_review_report_id = Column(Integer, nullable=True)  # 当前激活的AI审阅报告ID
    
    article_type = relationship("ArticleType", back_populates="articles")
    project = relationship("Project", back_populates="articles")
    ai_reviews = relationship("AIReviewReport", back_populates="article", cascade="all, delete-orphan")

class AIReviewReport(Base):
    __tablename__ = "ai_review_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"))  # 关联的文章ID
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)  # 关联的任务ID
    source_data = Column(String)  # 源数据
    processed_attachment_text = Column(Text)  # 处理后的附件文本内容
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # 创建时间
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # 更新时间
    status = Column(String, default="pending")  # pending, processing, completed, failed
    structured_data = Column(JSON, nullable=True)  # 结构化的数据
    
    article = relationship("Article", back_populates="ai_reviews")
    job = relationship("Job")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # 项目名称
    config = Column(JSON, nullable=False, server_default='{}')  # 配置信息，包含prompt等
    auto_approve = Column(Boolean, default=True)  # 是否自动审批
    owner_id = Column(Integer, ForeignKey("users.id"))  # 创建者ID
    article_type_id = Column(Integer, ForeignKey("article_types.id"))  # 基于的文章类型ID
    
    owner = relationship("User", back_populates="projects")
    article_type = relationship("ArticleType")
    articles = relationship("Article", back_populates="project", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")

class JobTask(Base):
    __tablename__ = "job_tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    task_type = Column(SQLAlchemyEnum(JobTaskType), nullable=False)
    status = Column(SQLAlchemyEnum(JobStatus), nullable=False)
    progress = Column(Integer, nullable=True)
    logs = Column(Text, nullable=True)
    article_id = Column(Integer, ForeignKey("articles.id"), nullable=True)
    params = Column(JSON, nullable=True)  # 存储任务参数
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    job = relationship("Job", back_populates="tasks")
    article = relationship("Article")

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=True)  # 任务名称
    status = Column(SQLAlchemyEnum(JobStatus), nullable=False)
    progress = Column(Integer, nullable=True)
    logs = Column(Text, nullable=True)
    parallelism = Column(Integer, default=1)  # 并行度设置
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    project = relationship("Project", back_populates="jobs")
    tasks = relationship("JobTask", back_populates="job", cascade="all, delete-orphan")
