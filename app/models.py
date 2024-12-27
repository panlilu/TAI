from sqlalchemy import Boolean, Column, Integer, String, Enum, ForeignKey, JSON, DateTime, Text
from sqlalchemy.orm import relationship
from .database import Base
import enum
from datetime import datetime

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    VIP = "vip"
    NORMAL = "normal"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(Enum(UserRole), default=UserRole.NORMAL)
    is_active = Column(Boolean, default=True)
    
    article_types = relationship("ArticleType", back_populates="owner")
    projects = relationship("Project", back_populates="owner")

class ArticleType(Base):
    __tablename__ = "article_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # 文章类型名称
    is_public = Column(Boolean, default=False)  # 是否为公共类型
    prompt = Column(String, default="")  # 审核用的prompt
    schema_prompt = Column(String, default="")  # 用于生成格式化数据的prompt
    fields = Column(JSON)  # 自定义结构化数据字段
    owner_id = Column(Integer, ForeignKey("users.id"))  # 创建者ID
    
    owner = relationship("User", back_populates="article_types")
    articles = relationship("Article", back_populates="article_type")

class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # 文章名称
    attachments = Column(JSON)  # 附件列表
    article_type_id = Column(Integer, ForeignKey("article_types.id"))  # 文章类型ID
    project_id = Column(Integer, ForeignKey("projects.id"))  # 项目ID
    created_at = Column(DateTime, default=datetime.utcnow)  # 创建时间
    
    article_type = relationship("ArticleType", back_populates="articles")
    project = relationship("Project", back_populates="articles")
    ai_reviews = relationship("AIReviewReport", back_populates="article")

class AIReviewReport(Base):
    __tablename__ = "ai_review_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"))  # 关联的文章ID
    source_data = Column(String)  # 源数据
    structured_data = Column(JSON)  # 结构化数据
    processed_attachment_text = Column(Text)  # 处理后的附件文本内容
    created_at = Column(DateTime, default=datetime.utcnow)  # 创建时间
    is_active = Column(Boolean, default=False)  # 是否为当前激活的批阅报告
    
    article = relationship("Article", back_populates="ai_reviews")

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)  # 项目名称
    prompt = Column(String, default="")  # 审核用的prompt
    schema_prompt = Column(String, default="")  # 用于生成格式化数据的prompt
    fields = Column(JSON)  # 自定义结构化数据字段
    auto_approve = Column(Boolean, default=True)  # 是否自动审批
    owner_id = Column(Integer, ForeignKey("users.id"))  # 创建者ID
    article_type_id = Column(Integer, ForeignKey("article_types.id"))  # 基于的文章类型ID
    
    owner = relationship("User", back_populates="projects")
    article_type = relationship("ArticleType")
    articles = relationship("Article", back_populates="project")

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    task = Column(String, nullable=False)
    status = Column(String, nullable=False)
    progress = Column(Integer, nullable=True)
    logs = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    project = relationship("Project")
