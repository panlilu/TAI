from datetime import timedelta
import os
from typing import List, Optional, Dict, Any
from fastapi import Depends, FastAPI, HTTPException, status, UploadFile, File, APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from datetime import datetime
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from redis import Redis
from rq import Queue
import asyncio
import json
import base64
import mimetypes
from pathlib import Path
import csv
import io
import copy
import logging

from . import models, schemas, auth, tasks
from .database import engine, get_db
from .schemas import UserRole

# 设置日志记录器
logger = logging.getLogger(__name__)

redis_conn = Redis()
task_queue = Queue(connection=redis_conn)

models.Base.metadata.create_all(bind=engine)

# 创建主应用
app = FastAPI()

# 创建API子应用
api_app = FastAPI(
    title="TAI API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# 将API子应用挂载到/api路径
app.mount("/api", api_app)

# 配置静态文件服务
app.mount("/static", StaticFiles(directory="frontend/tai_frontend/build/static"), name="static")

# 处理前端路由请求
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    return FileResponse("frontend/tai_frontend/build/index.html")

# 添加CORS中间件到API子应用
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@api_app.post("/token", response_model=schemas.Token, tags=["User Management"])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@api_app.post("/users/register", response_model=schemas.User, tags=["User Management"])
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # 检查是否是第一个用户，如果是则设置为管理员
    is_first_user = db.query(models.User).first() is None
    
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        hashed_password=hashed_password,
        role=UserRole.ADMIN if is_first_user else UserRole.NORMAL
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@api_app.get("/users/me", response_model=schemas.User, tags=["User Management"])
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

@api_app.get("/users", response_model=List[schemas.User], tags=["User Management"])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.check_admin_user),
    db: Session = Depends(get_db)
):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

@api_app.get("/users/{user_id}", response_model=schemas.User, tags=["User Management"])
async def get_user(
    user_id: int,
    current_user: models.User = Depends(auth.check_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@api_app.put("/users/{user_id}", response_model=schemas.User, tags=["User Management"])
async def update_user(
    user_id: int,
    user_update: dict,
    current_user: models.User = Depends(auth.check_admin_user),
    db: Session = Depends(get_db)
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    if "user_role" in user_update:
        db_user.role = user_update["user_role"]
    
    db.commit()
    db.refresh(db_user)
    return db_user

@api_app.delete("/users/{user_id}", response_model=schemas.User, tags=["User Management"])
async def delete_user(
    user_id: int,
    current_user: models.User = Depends(auth.check_admin_user),
    db: Session = Depends(get_db)
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    if db_user.role == UserRole.ADMIN:
        # 检查是否还有其他管理员
        admin_count = db.query(models.User).filter(models.User.role == UserRole.ADMIN).count()
        if admin_count <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete the last admin user"
            )
    
    db.delete(db_user)
    db.commit()
    return db_user

# 文章类型管理API
@api_app.post("/article-types", response_model=schemas.ArticleType, tags=["Article Type Management"])
async def create_article_type(
    article_type: schemas.ArticleTypeCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_article_type = models.ArticleType(
        name=article_type.name,
        is_public=article_type.is_public,
        config=article_type.config or {},  # 使用提供的config或空对象
        owner_id=current_user.id
    )
    db.add(db_article_type)
    db.commit()
    db.refresh(db_article_type)
    return db_article_type

@api_app.get("/article-types", response_model=List[schemas.ArticleType], tags=["Article Type Management"])
async def get_article_types(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 获取公共类型和用户自定义类型
    article_types = db.query(models.ArticleType).filter(
        (models.ArticleType.is_public == True) |
        (models.ArticleType.owner_id == current_user.id)
    ).offset(skip).limit(limit).all()
    return article_types

@api_app.get("/article-types/{article_type_id}", response_model=schemas.ArticleType, tags=["Article Type Management"])
async def get_article_type(
    article_type_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 获取单个文章类型
    db_article_type = db.query(models.ArticleType).filter(models.ArticleType.id == article_type_id).first()
    if db_article_type is None:
        raise HTTPException(status_code=404, detail="Article type not found")
    
    # 检查访问权限：公共类型或者属于当前用户
    if not db_article_type.is_public and db_article_type.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this article type")
    
    return db_article_type

@api_app.put("/article-types/{article_type_id}", response_model=schemas.ArticleType, tags=["Article Type Management"])
async def update_article_type(
    article_type_id: int,
    article_type: schemas.ArticleTypeUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_article_type = db.query(models.ArticleType).filter(models.ArticleType.id == article_type_id).first()
    if db_article_type is None:
        raise HTTPException(status_code=404, detail="Article type not found")
    if db_article_type.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this article type")
    
    if article_type.name is not None:
        db_article_type.name = article_type.name
    if article_type.config is not None:
        # 直接更新整个config对象
        db_article_type.config = article_type.config
    
    db.commit()
    db.refresh(db_article_type)
    return db_article_type

@api_app.delete("/article-types/{article_type_id}", tags=["Article Type Management"])
async def delete_article_type(
    article_type_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_article_type = db.query(models.ArticleType).filter(models.ArticleType.id == article_type_id).first()
    if db_article_type is None:
        raise HTTPException(status_code=404, detail="Article type not found")
    if db_article_type.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this article type")
    
    db.delete(db_article_type)
    db.commit()
    return {"message": "Article type deleted successfully"}

# 文章管理API
@api_app.post("/articles", response_model=schemas.Article, tags=["Article Management"])
async def create_article(
    article: schemas.ArticleCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_article = models.Article(
        name=article.name,
        attachments=article.attachments,
        article_type_id=article.article_type_id,
        project_id=article.project_id
    )
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article

@api_app.get("/articles", response_model=List[schemas.Article], tags=["Article Management"])
async def get_articles(
    skip: int = 0,
    limit: int = 100,
    project_id: Optional[int] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    if project_id:
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if project.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this project")
        articles = db.query(models.Article).filter(
            models.Article.project_id == project_id
        ).offset(skip).limit(limit).all()
    else:
        articles = db.query(models.Article).offset(skip).limit(limit).all()
    return articles

@api_app.get("/articles/{article_id}", response_model=schemas.Article, tags=["Article Management"])
async def get_article(
    article_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@api_app.put("/articles/{article_id}", response_model=schemas.Article, tags=["Article Management"])
async def update_article(
    article_id: int,
    article: schemas.ArticleUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if db_article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    
    if article.name is not None:
        db_article.name = article.name
    if article.attachments is not None:
        db_article.attachments = jsonable_encoder(article.attachments)
    db.commit()
    db.refresh(db_article)
    return db_article

@api_app.delete("/articles/{article_id}", tags=["Article Management"])
async def delete_article(
    article_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if db_article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    
    db.delete(db_article)
    db.commit()
    return {"message": "Article deleted successfully"}

@api_app.post("/articles/{article_id}/review", response_model=schemas.Job, tags=["AI Review Management"])
async def create_article_review(
    article_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查文章是否存在
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # 检查项目是否属于当前用户
    project = db.query(models.Project).filter(models.Project.id == article.project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this article")
    
    # 创建一个新的Job
    db_job = models.Job(
        name=f"AI Review for {article.name}",
        project_id=article.project_id,
        status=schemas.JobStatus.PENDING,
        progress=0,
        logs="",
        parallelism=1
    )
    db.add(db_job)
    db.commit()
    
    # 创建任务
    convert_task = models.JobTask(
        job_id=db_job.id,
        task_type=schemas.JobTaskType.CONVERT_TO_MARKDOWN,
        status=schemas.JobStatus.PENDING,
        article_id=article_id
    )
    db.add(convert_task)
    
    llm_task = models.JobTask(
        job_id=db_job.id,
        task_type=schemas.JobTaskType.PROCESS_WITH_LLM,
        status=schemas.JobStatus.PENDING,
        article_id=article_id
    )
    db.add(llm_task)
    
    db.commit()
    
    # 启动任务
    task_queue.enqueue(
        tasks.schedule_job_tasks,
        args=(db_job.id,)
    )
    
    return db_job

@api_app.post("/articles/{article_id}/extract-structured-data", response_model=schemas.Job, tags=["AI Review Management"])
async def extract_article_structured_data(
    article_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查文章是否存在
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # 检查项目是否属于当前用户
    project = db.query(models.Project).filter(models.Project.id == article.project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this article")
    
    # 检查文章是否有AI审阅报告
    ai_review = None
    if article.active_ai_review_report_id:
        ai_review = db.query(models.AIReviewReport).filter(
            models.AIReviewReport.id == article.active_ai_review_report_id
        ).first()
    
    if not ai_review:
        ai_review = db.query(models.AIReviewReport).filter(
            models.AIReviewReport.article_id == article_id
        ).order_by(models.AIReviewReport.created_at.desc()).first()
    
    if not ai_review or not ai_review.source_data:
        raise HTTPException(status_code=400, detail="Article doesn't have an AI review report")
    
    # 创建一个新的Job
    db_job = models.Job(
        name=f"Extract Structured Data for {article.name}",
        project_id=article.project_id,
        status=schemas.JobStatus.PENDING,
        progress=0,
        logs="",
        parallelism=1
    )
    db.add(db_job)
    db.commit()
    
    # 创建任务
    extract_task = models.JobTask(
        job_id=db_job.id,
        task_type=schemas.JobTaskType.EXTRACT_STRUCTURED_DATA,
        status=schemas.JobStatus.PENDING,
        article_id=article_id
    )
    db.add(extract_task)
    db.commit()
    
    # 启动任务
    task_queue.enqueue(
        tasks.schedule_job_tasks,
        args=(db_job.id,)
    )
    
    return db_job

@api_app.delete("/articles", tags=["Article Management"])
async def delete_all_articles(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 删除所有文章
    db.query(models.Article).delete()
    db.commit()
    return {"message": "All articles deleted successfully"}

@api_app.get("/articles/{article_id}/content", response_model=None, tags=["Article Management"])
async def get_article_content(
    article_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if db_article is None:
        raise HTTPException(status_code=404, detail="Article not found")
        
    attachments = db_article.attachments
    if not attachments:
        return {"content": "", "filename": "", "path": "", "content_type": "text/plain"}
        
    active_attachment = next((att for att in attachments if att.get('is_active')), attachments[0] if attachments else None)
    
    if not active_attachment:
        return {"content": "", "filename": "", "path": "", "content_type": "text/plain"}
        
    file_path = active_attachment['path']
    filename = active_attachment['filename']
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        # 文件不存在时返回空内容而不是404错误
        return {"content": "", "filename": filename, "path": file_path, "content_type": "text/plain"}

    # 检测文件类型
    mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    
    # 如果是文本文件，直接读取内容
    is_text = mime_type.startswith('text/') or filename.endswith(('.md', '.txt'))
    
    try:
        if is_text:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return {
                    "content": content,
                    "filename": filename,
                    "path": file_path,
                    "content_type": mime_type,
                }
        else:
            # 对于二进制文件，使用 FileResponse
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type=mime_type
            )
    except Exception as e:
        # 读取文件失败时返回空内容和错误消息
        return {
            "content": "",
            "filename": filename,
            "path": file_path,
            "content_type": mime_type,
            "error": str(e)
        }

# AI批阅报告管理API
@api_app.post("/ai-reviews", response_model=schemas.AIReviewReport, tags=["AI Review Management"])
async def create_ai_review(
    ai_review: schemas.AIReviewReportCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_ai_review = models.AIReviewReport(
        article_id=ai_review.article_id,
        source_data=ai_review.source_data,
        structured_data=ai_review.structured_data,
        status=ai_review.status
    )
    db.add(db_ai_review)
    db.commit()
    db.refresh(db_ai_review)
    return db_ai_review

@api_app.get("/ai-reviews", response_model=List[schemas.AIReviewReport], tags=["AI Review Management"])
async def get_ai_reviews(
    article_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查文章是否存在且属于当前用户
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    project = db.query(models.Project).filter(models.Project.id == article.project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this article")
    
    ai_reviews = db.query(models.AIReviewReport).filter(models.AIReviewReport.article_id == article_id).offset(skip).limit(limit).all()
    return ai_reviews

@api_app.get("/structured-data", tags=["AI Review Management"])
async def get_structured_data(
    article_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查文章是否存在且属于当前用户
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    project = db.query(models.Project).filter(models.Project.id == article.project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this article")
    
    # 获取文章当前活跃的AI审阅报告
    if article.active_ai_review_report_id:
        ai_review = db.query(models.AIReviewReport).filter(
            models.AIReviewReport.id == article.active_ai_review_report_id
        ).first()
    else:
        # 如果没有活跃报告，获取最新的报告
        ai_review = db.query(models.AIReviewReport).filter(
            models.AIReviewReport.article_id == article_id
        ).order_by(models.AIReviewReport.created_at.desc()).first()
    
    if not ai_review or not ai_review.structured_data:
        raise HTTPException(status_code=404, detail="Structured data not found")
    
    return ai_review.structured_data

@api_app.put("/ai-reviews/{ai_review_id}", response_model=schemas.AIReviewReport, tags=["AI Review Management"])
async def update_ai_review(
    ai_review_id: int,
    ai_review: schemas.AIReviewReportUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_ai_review = db.query(models.AIReviewReport).filter(models.AIReviewReport.id == ai_review_id).first()
    if db_ai_review is None:
        raise HTTPException(status_code=404, detail="AI review not found")
    
    if ai_review.source_data is not None:
        db_ai_review.source_data = ai_review.source_data
    if ai_review.structured_data is not None:
        db_ai_review.structured_data = ai_review.structured_data
    if ai_review.status is not None:
        db_ai_review.status = ai_review.status
    
    # 获取关联的文章
    article = db.query(models.Article).filter(models.Article.id == db_ai_review.article_id).first()
    if article:
        # 更新文章的active_ai_review_report_id为当前ai_review_id
        article.active_ai_review_report_id = ai_review_id
    
    db.commit()
    db.refresh(db_ai_review)
    return db_ai_review

# 项目相关API
@api_app.post("/projects", response_model=schemas.Project, tags=["Project Management"])
async def create_project(
    project: schemas.ProjectCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 获取article_type信息
    article_type = db.query(models.ArticleType).filter(models.ArticleType.id == project.article_type_id).first()
    if not article_type:
        raise HTTPException(status_code=404, detail="Article type not found")
    
    # 检查权限：article_type必须是public或者属于当前用户
    if not article_type.is_public and article_type.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="Not authorized to use this article type"
        )

    # 如果没有提供name，则使用article_type.name + 当前日期
    if not project.name:
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")
        project_name = f"{article_type.name}_{current_date}"
    else:
        project_name = project.name
    
    # 创建project，从article_type完整深拷贝config
    project_config = json.loads(json.dumps(article_type.config or {}))
    
    # 如果项目配置中没有tasks字段，添加默认的任务配置
    if "tasks" not in project_config:
        project_config["tasks"] = {}
    
    # 确保extract_structured_data配置被完整保留，即使值为空
    if "tasks" in project_config and "extract_structured_data" in project_config["tasks"]:
        extract_config = project_config["tasks"]["extract_structured_data"]
        if "extraction_prompt" not in extract_config:
            extract_config["extraction_prompt"] = ""
    
    # 如果提供了新的配置，合并它
    if getattr(project, 'config', None):
        # 合并tasks配置
        if "tasks" in project.config:
            for task_type, task_config in project.config["tasks"].items():
                if task_type not in project_config["tasks"]:
                    project_config["tasks"][task_type] = {}
                # 使用深拷贝确保所有字段都被保留
                project_config["tasks"][task_type].update(copy.deepcopy(task_config))
        
        # 合并其他配置
        for key, value in project.config.items():
            if key != "tasks":
                project_config[key] = copy.deepcopy(value)
    
    db_project = models.Project(
        name=project_name,
        config=project_config,  # 使用完整深拷贝的配置
        auto_approve=project.auto_approve,
        owner_id=current_user.id,
        article_type_id=project.article_type_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@api_app.get("/projects", response_model=List[schemas.Project], tags=["Project Management"])
async def get_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    projects = db.query(models.Project).filter(
        models.Project.owner_id == current_user.id
    ).offset(skip).limit(limit).all()
    return projects

@api_app.get("/projects/{project_id}", response_model=schemas.Project, tags=["Project Management"])
async def get_project(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    return project

@api_app.put("/projects/{project_id}", response_model=schemas.Project, tags=["Project Management"])
async def update_project(
    project_id: int,
    project: schemas.ProjectUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if db_project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this project")
    
    if project.name is not None:
        db_project.name = project.name
    if project.config is not None:
        db_project.config = project.config
    if project.auto_approve is not None:
        db_project.auto_approve = project.auto_approve
    
    db.commit()
    db.refresh(db_project)
    return db_project

@api_app.delete("/projects/{project_id}", tags=["Project Management"])
async def delete_project(
    project_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if db_project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")
    
    # 删除项目，级联删除所有关联的文章、任务和AI审阅报告
    # 通过在models.py中设置cascade="all, delete-orphan"实现
    db.delete(db_project)
    db.commit()
    return {"message": "Project deleted successfully"}

@api_app.get("/projects/{project_id}/export-csv", tags=["Project Management"])
async def export_project_to_csv(
    project_id: int,
    include_report: bool = True,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查项目是否存在且属于当前用户
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this project")
    
    # 获取项目下所有文章
    articles = db.query(models.Article).filter(models.Article.project_id == project_id).all()
    
    # 准备CSV内容
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 遍历文章，获取活动的AI审阅报告
    rows = []
    headers = ["article_name"]
    
    if include_report:
        headers.append("report")
    
    # 先扫描一遍，确定所有可能的structured_data字段，构建完整的表头
    structured_fields = set()
    for article in articles:
        if article.active_ai_review_report_id is not None:
            # 获取文章的活动AI审阅报告
            ai_review = db.query(models.AIReviewReport).filter(
                models.AIReviewReport.id == article.active_ai_review_report_id
            ).first()
            
            if ai_review and ai_review.structured_data:
                # 将一级字段名称添加到表头集合中
                for field in ai_review.structured_data.keys():
                    structured_fields.add(field)
    
    # 扩展表头，包含所有structured_data的一级字段
    headers.extend(sorted(structured_fields))
    
    # 写入表头
    writer.writerow(headers)
    
    # 写入数据行
    for article in articles:
        row = [article.name]
        structured_data = {}
        
        if article.active_ai_review_report_id is not None:
            # 获取文章的活动AI审阅报告
            ai_review = db.query(models.AIReviewReport).filter(
                models.AIReviewReport.id == article.active_ai_review_report_id
            ).first()
            
            if ai_review:
                if include_report:
                    row.append(ai_review.source_data)
                if ai_review.structured_data:
                    structured_data = ai_review.structured_data
        else:
            if include_report:
                row.append("")
        
        # 添加structured_data的各字段值
        for field in headers[2:] if include_report else headers[1:]:
            row.append(structured_data.get(field, ""))
        
        writer.writerow(row)
    
    # 准备响应
    output.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"project_{project_id}_{timestamp}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# Job相关API
@api_app.post("/jobs", response_model=schemas.Job, tags=["Job Management"])
async def create_job(
    job: schemas.JobCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查project是否存在且属于当前用户
    if job.project_id:
        project = db.query(models.Project).filter(
            models.Project.id == job.project_id,
            models.Project.owner_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or not authorized")
    else:
        raise HTTPException(status_code=400, detail="Project ID is required")
    
    # 创建job记录
    db_job = models.Job(
        project_id=job.project_id,
        name=job.name,
        status=schemas.JobStatus.PENDING,
        progress=0,
        logs="",
        parallelism=job.parallelism or 1
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    # 创建任务记录
    for task_create in job.tasks:
        # 如果提供了article_id，检查文章是否存在
        if task_create.article_id:
            article = db.query(models.Article).filter(models.Article.id == task_create.article_id).first()
            if not article:
                raise HTTPException(status_code=404, detail=f"Article {task_create.article_id} not found")
            
            # 检查文章是否属于该项目
            if article.project_id != job.project_id:
                raise HTTPException(status_code=400, detail=f"Article {task_create.article_id} does not belong to project {job.project_id}")
        
        # 创建任务
        db_task = models.JobTask(
            job_id=db_job.id,
            task_type=task_create.task_type,
            status=schemas.JobStatus.PENDING,
            progress=0,
            logs="",
            article_id=task_create.article_id,
            params=task_create.params
        )
        db.add(db_task)
    
    db.commit()
    
    # 调度任务
    task_queue.enqueue(
        tasks.schedule_job_tasks,
        args=(db_job.id,)
    )
    
    # 刷新job以获取关联的tasks
    db.refresh(db_job)
    return db_job

# 上传文件任务
@api_app.post("/jobs_upload", response_model=schemas.Job, tags=["Job Management"])
async def create_upload_job(
    project_id: int,
    file: UploadFile = File(...),
    parallelism: int = 1,
    name: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查项目是否属于当前用户
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or not authorized")
    
    # 创建job记录
    db_job = models.Job(
        project_id=project_id,
        name=name or f"Upload {file.filename}",
        status=schemas.JobStatus.PENDING,
        progress=0,
        logs="",
        parallelism=parallelism
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    # 创建按用户ID和任务ID组织的目录结构，使用uuid替代id
    upload_dir = f"data/uploads/{current_user.id}/{db_job.uuid}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # 保存上传文件
    file_path = f"{upload_dir}/{file.filename}"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # 创建任务记录
    db_task = models.JobTask(
        job_id=db_job.id,
        task_type=schemas.JobTaskType.PROCESS_UPLOAD,
        status=schemas.JobStatus.PENDING,
        progress=0,
        logs="",
        params={
            "file_path": file_path,
            "project_id": project_id
        }
    )
    db.add(db_task)
    db.commit()
    
    # 调度任务
    task_queue.enqueue(
        tasks.schedule_job_tasks,
        args=(db_job.id,)
    )
    
    # 刷新job以获取关联的tasks
    db.refresh(db_job)
    return db_job

@api_app.get("/jobs", response_model=List[schemas.Job], tags=["Job Management"])
async def get_jobs(
    skip: int = 0,
    limit: int = 100,
    project_id: Optional[int] = None,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 构建基本查询，包含项目所有权验证
    query = db.query(models.Job).join(
        models.Project,
        models.Job.project_id == models.Project.id
    ).filter(
        models.Project.owner_id == current_user.id
    ).order_by(models.Job.id.desc())
    
    # 如果提供了project_id，添加项目过滤条件
    if project_id is not None:
        # 检查项目是否存在且属于当前用户
        project = db.query(models.Project).filter(
            models.Project.id == project_id,
            models.Project.owner_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found or not authorized")
        query = query.filter(models.Job.project_id == project_id)
    
    # 执行查询
    jobs = query.offset(skip).limit(limit).all()
    return jobs

@api_app.get("/jobs/{job_id}", response_model=schemas.Job, tags=["Job Management"])
async def get_job(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # 检查项目是否属于当前用户
    project = db.query(models.Project).filter(
        models.Project.id == job.project_id,
        models.Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")
    
    return job

@api_app.post("/jobs/{job_id}/action", response_model=schemas.Job, tags=["Job Management"])
async def job_action(
    job_id: int,
    action: schemas.JobActionRequest,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # 检查项目是否属于当前用户
    project = db.query(models.Project).filter(
        models.Project.id == job.project_id,
        models.Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to perform action on this job")
    
    # 如果指定了task_id，则操作特定任务
    if hasattr(action, 'task_id') and action.task_id:
        return await task_action(job_id, action.task_id, action, current_user, db)
    
    # 处理不同的操作
    if action.action == schemas.JobAction.PAUSE:
        # 先试着找一个正在处理的任务
        task_to_pause = db.query(models.JobTask).filter(
            models.JobTask.job_id == job_id,
            models.JobTask.status == schemas.JobStatus.PROCESSING
        ).first()
        
        # 如果没有正在处理的任务，查找待处理的任务
        if not task_to_pause:
            task_to_pause = db.query(models.JobTask).filter(
                models.JobTask.job_id == job_id,
                models.JobTask.status == schemas.JobStatus.PENDING
            ).first()
        
        # 如果找到了任务，则暂停
        if task_to_pause:
            task_to_pause.status = schemas.JobStatus.PAUSED
            job.status = schemas.JobStatus.PAUSED
        else:
            # 没有找到任何任务，但不抛出错误
            # 把所有任务都标记为暂停
            db.query(models.JobTask).filter(
                models.JobTask.job_id == job_id
            ).update({"status": schemas.JobStatus.PAUSED})
            job.status = schemas.JobStatus.PAUSED
    
    elif action.action == schemas.JobAction.RESUME:
        # 恢复所有暂停的任务
        tasks_to_resume = db.query(models.JobTask).filter(
            models.JobTask.job_id == job_id,
            models.JobTask.status == schemas.JobStatus.PAUSED
        ).all()
        
        if not tasks_to_resume:
            # 检查是否有其他类型的任务
            other_tasks = db.query(models.JobTask).filter(
                models.JobTask.job_id == job_id
            ).all()
            
            if not other_tasks:
                raise HTTPException(status_code=400, detail="No tasks found")
                
            # 有其他任务，但没有暂停的，所以设置为pending
            for task in other_tasks:
                if task.status != schemas.JobStatus.COMPLETED and task.status != schemas.JobStatus.FAILED:
                    task.status = schemas.JobStatus.PENDING
                    
            job.status = schemas.JobStatus.PENDING
        else:
            for task in tasks_to_resume:
                task.status = schemas.JobStatus.PENDING
            
            job.status = schemas.JobStatus.PENDING
        
        # 调度任务
        task_queue.enqueue(
            tasks.schedule_job_tasks,
            args=(job_id,)
        )
    
    elif action.action == schemas.JobAction.CANCEL:
        # 取消所有未完成的任务
        tasks_to_cancel = db.query(models.JobTask).filter(
            models.JobTask.job_id == job_id,
            models.JobTask.status.in_([
                schemas.JobStatus.PENDING,
                schemas.JobStatus.PROCESSING,
                schemas.JobStatus.PAUSED
            ])
        ).all()
        
        if not tasks_to_cancel:
            raise HTTPException(status_code=400, detail="No active tasks to cancel")
        
        for task in tasks_to_cancel:
            task.status = schemas.JobStatus.CANCELLED
        
        job.status = schemas.JobStatus.CANCELLED
    
    elif action.action == schemas.JobAction.RETRY:
        # 重试所有失败或取消的任务
        tasks_to_retry = db.query(models.JobTask).filter(
            models.JobTask.job_id == job_id,
            models.JobTask.status.in_([
                schemas.JobStatus.FAILED,
                schemas.JobStatus.CANCELLED
            ])
        ).all()
        
        if not tasks_to_retry:
            raise HTTPException(status_code=400, detail="No failed or cancelled tasks to retry")
        
        for task in tasks_to_retry:
            task.status = schemas.JobStatus.PENDING
            task.progress = 0
            task.logs = ""
        
        job.status = schemas.JobStatus.PENDING
        job.progress = 0
        
        # 调度任务
        task_queue.enqueue(
            tasks.schedule_job_tasks,
            args=(job_id,)
        )
    
    db.commit()
    db.refresh(job)
    return job

@api_app.post("/jobs/{job_id}/tasks/{task_id}/action", response_model=schemas.Job, tags=["Job Management"])
async def task_action(
    job_id: int,
    task_id: int,
    action: schemas.JobActionRequest,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # 检查项目是否属于当前用户
    project = db.query(models.Project).filter(
        models.Project.id == job.project_id,
        models.Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to perform action on this job")
    
    # 获取任务
    task = db.query(models.JobTask).filter(
        models.JobTask.id == task_id,
        models.JobTask.job_id == job_id
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 处理不同的操作
    if action.action == schemas.JobAction.PAUSE:
        if task.status != schemas.JobStatus.PROCESSING:
            raise HTTPException(status_code=400, detail="Can only pause processing tasks")
        task.status = schemas.JobStatus.PAUSED
    
    elif action.action == schemas.JobAction.RESUME:
        if task.status != schemas.JobStatus.PAUSED:
            raise HTTPException(status_code=400, detail="Can only resume paused tasks")
        task.status = schemas.JobStatus.PENDING
        
        # 调度任务
        task_queue.enqueue(
            tasks.execute_task,
            args=(task_id,)
        )
    
    elif action.action == schemas.JobAction.CANCEL:
        if task.status in [schemas.JobStatus.COMPLETED, schemas.JobStatus.FAILED, schemas.JobStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="Cannot cancel completed, failed or cancelled tasks")
        task.status = schemas.JobStatus.CANCELLED
    
    elif action.action == schemas.JobAction.RETRY:
        if task.status not in [schemas.JobStatus.COMPLETED, schemas.JobStatus.FAILED, schemas.JobStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="Can only retry completed, failed or cancelled tasks")
        
        task.status = schemas.JobStatus.PENDING
        task.progress = 0
        task.logs = ""
        
        # 调度任务
        task_queue.enqueue(
            tasks.execute_task,
            args=(task_id,)
        )
    
    db.commit()
    
    # 更新Job状态
    tasks.update_job_status(db, job_id)
    
    db.refresh(job)
    return job

@api_app.get("/jobs/{job_id}/tasks", response_model=List[schemas.JobTask], tags=["Job Management"])
async def get_job_tasks(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查Job是否存在且属于当前用户
    job = db.query(models.Job).join(
        models.Project,
        models.Job.project_id == models.Project.id
    ).filter(
        models.Job.id == job_id,
        models.Project.owner_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or not authorized")
    
    # 获取所有任务
    tasks = db.query(models.JobTask).filter(
        models.JobTask.job_id == job_id
    ).all()
    
    return tasks

@api_app.get("/jobs/{job_id}/tasks/{task_id}", response_model=schemas.JobTask, tags=["Job Management"])
async def get_job_task(
    job_id: int,
    task_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查Job是否存在且属于当前用户
    job = db.query(models.Job).join(
        models.Project,
        models.Job.project_id == models.Project.id
    ).filter(
        models.Job.id == job_id,
        models.Project.owner_id == current_user.id
    ).first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or not authorized")
    
    # 获取任务
    task = db.query(models.JobTask).filter(
        models.JobTask.id == task_id,
        models.JobTask.job_id == job_id
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task

@api_app.post("/jobs/cancel-all", tags=["Job Management"])
async def cancel_all_jobs(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 获取用户所有项目中的进行中任务
    active_jobs = db.query(models.Job).join(
        models.Project,
        models.Job.project_id == models.Project.id
    ).filter(
        models.Project.owner_id == current_user.id,
        models.Job.status.in_([
            schemas.JobStatus.PENDING,
            schemas.JobStatus.PROCESSING,
            schemas.JobStatus.PAUSED
        ])
    ).all()
    
    # 更新所有任务状态为已取消
    for job in active_jobs:
        job.status = schemas.JobStatus.CANCELLED
    
    db.commit()
    
    return {
        "message": f"Successfully cancelled {len(active_jobs)} jobs",
        "cancelled_jobs": len(active_jobs)
    }

@api_app.put("/jobs/{job_id}", response_model=schemas.Job, tags=["Job Management"])
async def update_job(
    job_id: int,
    job_update: schemas.JobUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # 检查项目是否属于当前用户
    project = db.query(models.Project).filter(
        models.Project.id == job.project_id,
        models.Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to access this job")
    
    # 更新任务属性
    if job_update.name is not None:
        job.name = job_update.name

    db.commit()
    db.refresh(job)
    return job

@api_app.get("/events")
async def job_events(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    async def event_generator():
        heartbeat_interval = 30  # 30秒发送一次心跳
        last_heartbeat = 0
        last_job_updates = {}  # 存储上次更新的作业状态
        last_task_updates = {}  # 存储上次更新的任务状态和日志

        while True:
            current_time = datetime.utcnow().timestamp()

            # 检查是否需要发送心跳
            if current_time - last_heartbeat >= heartbeat_interval:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                last_heartbeat = current_time

            # 刷新数据库会话以避免过期数据
            db.expire_all()
            
            # 查询最近10秒内更新的任务
            recent_jobs = db.query(models.Job).join(
                models.Project
            ).filter(
                models.Project.owner_id == current_user.id,
                models.Job.updated_at >= datetime.utcnow() - timedelta(seconds=10)
            ).all()

            if recent_jobs:
                for job in recent_jobs:
                    # 获取任务的第一个子任务类型（如果有）
                    first_task = db.query(models.JobTask).filter(
                        models.JobTask.job_id == job.id
                    ).first()
                    
                    job_data = {
                        "type": "job_update",
                        "id": job.id,
                        "name": job.name,
                        "status": job.status,
                        "progress": job.progress,
                        "task_type": first_task.task_type if first_task else None
                    }
                    
                    # 检查作业状态是否有变化，有则发送更新
                    if job.id not in last_job_updates or job.status != last_job_updates[job.id]['status'] or job.progress != last_job_updates[job.id]['progress']:
                        yield f"data: {json.dumps(job_data)}\n\n"
                        # 更新缓存的状态
                        last_job_updates[job.id] = {
                            'status': job.status,
                            'progress': job.progress
                        }
                    
                    # 查询该作业下的任务
                    job_tasks = db.query(models.JobTask).filter(
                        models.JobTask.job_id == job.id,
                        models.JobTask.updated_at >= datetime.utcnow() - timedelta(seconds=10)
                    ).all()
                    
                    
                    for task in job_tasks:
                        task_key = f"{job.id}_{task.id}"
                        
                        # 检查任务的状态和日志是否有变化
                        task_changed = (
                            task_key not in last_task_updates or
                            task.status != last_task_updates[task_key]['status'] or
                            task.progress != last_task_updates[task_key]['progress'] or
                            task.logs != last_task_updates[task_key]['logs']
                        )
                        
                        if task_changed:
                            # 如果任务日志有更新，发送新的日志内容
                            task_data = {
                                "type": "task_update",
                                "job_id": job.id,
                                "task_id": task.id,
                                "task_type": task.task_type,
                                "status": task.status,
                                "progress": task.progress,
                                "logs": task.logs
                            }
                            
                            yield f"data: {json.dumps(task_data)}\n\n"
                            
                            # 更新缓存的任务状态和日志
                            last_task_updates[task_key] = {
                                'status': task.status,
                                'progress': task.progress,
                                'logs': task.logs
                            }
            
            await asyncio.sleep(2)  # Poll every 2 seconds
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@api_app.get("/events_ai_review/{ai_review_id}")
async def ai_review_events(
    ai_review_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查 AI 审阅报告是否存在并且属于当前用户的项目
    ai_review = db.query(models.AIReviewReport).filter(models.AIReviewReport.id == ai_review_id).first()
    if not ai_review:
        raise HTTPException(status_code=404, detail="AI review report not found")
    
    article = db.query(models.Article).filter(models.Article.id == ai_review.article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    project = db.query(models.Project).filter(models.Project.id == article.project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this AI review report")

    async def event_generator():
        try:
            while True:
                # 刷新数据库会话以避免过期数据
                db.expire_all()
                
                # 重新查询数据库以获取最新数据
                db_review = db.query(models.AIReviewReport).filter(models.AIReviewReport.id == ai_review_id).first()
                
                if not db_review:
                    # 如果审阅报告被删除
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI review report not found'})}\n\n"
                    break
                
                # 发送当前审阅状态
                yield f"data: {json.dumps({'type': 'status', 'status': db_review.status})}\n\n"
                
                # 如果已完成，发送完成通知
                if db_review.status == "completed":
                    yield f"data: {json.dumps({'type': 'content', 'content': db_review.source_data or '', 'is_final': True})}\n\n"
                    break
                # 如果是ready状态，表示文档已转换为Markdown等待LLM处理
                elif db_review.status == "ready" and db_review.processed_attachment_text:
                    # 发送状态但不终止连接，因为之后可能会收到LLM处理的结果
                    yield f"data: {json.dumps({'type': 'content', 'content': '文档已准备好，等待AI处理...', 'is_final': False})}\n\n"
                # 如果是processing状态，表示LLM正在处理，发送当前的部分内容
                elif db_review.status == "processing":
                    if db_review.source_data:
                        yield f"data: {json.dumps({'type': 'content', 'content': db_review.source_data, 'is_final': False})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'content', 'content': 'AI正在处理文档内容...', 'is_final': False})}\n\n"
                
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            logger.info(f"Client disconnected from AI review events stream for review ID {ai_review_id}")
            raise
        except Exception as e:
            logger.error(f"Error in AI review events stream: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@api_app.get("/events_structured_data/{report_id}")
async def structured_data_events(
    report_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 检查 AI 审阅报告是否存在并且属于当前用户的项目
    ai_review = db.query(models.AIReviewReport).filter(models.AIReviewReport.id == report_id).first()
    if not ai_review:
        raise HTTPException(status_code=404, detail="AI review report not found")
    
    article = db.query(models.Article).filter(models.Article.id == ai_review.article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    
    project = db.query(models.Project).filter(models.Project.id == article.project_id).first()
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this AI review report")

    async def event_generator():
        try:
            while True:
                # 刷新数据库会话以避免过期数据
                db.expire_all()
                
                # 重新查询数据库以获取最新数据
                db_review = db.query(models.AIReviewReport).filter(models.AIReviewReport.id == report_id).first()
                
                if not db_review:
                    # 如果审阅报告被删除
                    yield f"data: {json.dumps({'type': 'error', 'message': 'AI review report not found'})}\n\n"
                    break
                
                # 发送当前审阅状态
                yield f"data: {json.dumps({'type': 'status', 'status': db_review.status})}\n\n"
                
                # 如果结构化数据已生成，发送数据
                if db_review.structured_data:
                    yield f"data: {json.dumps({'type': 'content', 'content': json.dumps(db_review.structured_data), 'is_final': True})}\n\n"
                    break
                
                # 如果处理完成但没有结构化数据
                if db_review.status == "completed" and not db_review.structured_data:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'No structured data available', 'is_final': True})}\n\n"
                    break
                
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            logger.info(f"Client disconnected from structured data events stream for review ID {report_id}")
            raise
        except Exception as e:
            logger.error(f"Error in structured data events stream: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            raise

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# 添加模型配置相关的API端点
@api_app.get("/models", tags=["Model Configuration"])
async def get_models(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """获取所有可用的模型配置"""
    model_config = tasks.get_model_config()
    return model_config.get("models", {})

@api_app.get("/models/{model_id}", tags=["Model Configuration"])
async def get_model_details(
    model_id: str,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """获取特定模型的详细信息"""
    model_config = tasks.get_model_config()
    model_details = model_config.get("models", {}).get(model_id)
    if not model_details:
        raise HTTPException(status_code=404, detail="Model not found")
    return model_details

@api_app.get("/tasks/{task_type}/models", tags=["Model Configuration"])
async def get_task_models(
    task_type: str,
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """获取特定任务类型可用的模型列表（包括详细信息）
    
    支持的任务类型:
    - process_with_llm: LLM处理任务
    - extract_structured_data: 结构化数据提取任务
    - ai_review: AI审阅任务
    - 其他自定义任务类型
    
    对于convert_to_markdown/image_description模型，请使用 /tasks/convert_to_markdown/image_description_models 端点
    """
    # 图片描述模型使用单独的API
    if task_type == "convert_to_markdown" and "image_description" in task_type:
        raise HTTPException(status_code=400, detail="For image description models, use /tasks/convert_to_markdown/image_description_models endpoint")
    
    # 从tasks模块获取可用模型列表
    available_models = tasks.get_available_models_for_task(task_type)
    
    # 获取模型详细信息
    result = []
    for model_id in available_models:
        model_detail = tasks.get_model_details(model_id)
        if model_detail:
            result.append(model_detail)
    
    return result

@api_app.get("/model-config", tags=["Model Configuration"])
async def get_model_config(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """获取完整的模型配置"""
    return tasks.get_model_config()

@api_app.get("/user/stats", response_model=schemas.UserStats, tags=["User Management"])
async def get_user_stats(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    # 获取用户的文章数量
    article_count = db.query(models.Article).join(
        models.Project
    ).filter(
        models.Project.owner_id == current_user.id
    ).count()
    
    # 获取用户的项目数量
    project_count = db.query(models.Project).filter(
        models.Project.owner_id == current_user.id
    ).count()
    
    # 获取用户的文章类型数量
    article_type_count = db.query(models.ArticleType).filter(
        (models.ArticleType.is_public == True) | 
        (models.ArticleType.owner_id == current_user.id)
    ).count()
    
    # 获取用户的任务总数
    total_jobs = db.query(models.Job).join(
        models.Project
    ).filter(
        models.Project.owner_id == current_user.id
    ).count()
    
    # 获取用户的进行中任务数量
    active_jobs = db.query(models.Job).join(
        models.Project
    ).filter(
        models.Project.owner_id == current_user.id,
        models.Job.status.in_([schemas.JobStatus.PENDING, schemas.JobStatus.PROCESSING])
    ).count()
    
    return {
        "article_count": article_count,
        "project_count": project_count,
        "article_type_count": article_type_count,
        "total_jobs": total_jobs,
        "active_jobs": active_jobs
    }

@api_app.get("/tasks/convert_to_markdown/image_description_models", tags=["Model Configuration"])
async def get_image_description_models(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """获取图片描述任务可用的模型列表"""
    available_models = tasks.MODEL_CONFIG.get("tasks", {}).get("convert_to_markdown", {}).get("available_image_description_models", [])
    result = []
    for model_id in available_models:
        model_detail = tasks.get_model_details(model_id)
        if model_detail:
            result.append(model_detail)
    return result

