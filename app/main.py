from datetime import timedelta
import os
from typing import List, Optional
from fastapi import Depends, FastAPI, HTTPException, status, UploadFile, File, APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
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

from . import models, schemas, auth, tasks
from .database import engine, get_db
from .models import UserRole

redis_conn = Redis()
task_queue = Queue(connection=redis_conn)

models.Base.metadata.create_all(bind=engine)

# 创建主应用
app = FastAPI()

# 创建API子应用
api_app = FastAPI(
    title="User Management API",
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
    user_role: UserRole,
    current_user: models.User = Depends(auth.check_admin_user),
    db: Session = Depends(get_db)
):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_user.role = user_role
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
        prompt=article_type.prompt,
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
    
    db_article_type.name = article_type.name
    db_article_type.prompt = article_type.prompt
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
        attachments=jsonable_encoder(article.attachments),
        article_type_id=article.article_type_id
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
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    
    # 检查文章是否属于项目
    if not article.project_id:
        raise HTTPException(status_code=400, detail="Article must belong to a project")
    
    # 创建job记录
    db_job = models.Job(
        project_id=article.project_id,
        task="process_ai_review",
        status=schemas.JobStatus.PENDING,
        progress=0,
        logs=""
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    # 将任务加入队列
    task_queue.enqueue(
        tasks.process_ai_review,
        args=(article_id, db_job.id)
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
    active_attachment = next((att for att in attachments if att.get('is_active')), attachments[0] if attachments else None)
    
    if not active_attachment:
        raise HTTPException(status_code=404, detail="No attachment found")
        
    file_path = active_attachment['path']
    filename = active_attachment['filename']
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

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
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

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
        structured_data=ai_review.structured_data
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
    ai_reviews = db.query(models.AIReviewReport).filter(
        models.AIReviewReport.article_id == article_id
    ).offset(skip).limit(limit).all()
    return ai_reviews

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
    
    db_ai_review.source_data = ai_review.source_data
    db_ai_review.structured_data = ai_review.structured_data
    db_ai_review.is_active = ai_review.is_active
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
    
    # 创建project，从article_type复制prompt
    db_project = models.Project(
        name=project_name,
        prompt=article_type.prompt,
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
    if project.prompt is not None:
        db_project.prompt = project.prompt
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
    
    db.delete(db_project)
    db.commit()
    return {"message": "Project deleted successfully"}

# Job相关API
@api_app.post("/jobs", response_model=schemas.Job, tags=["Job Management"])
async def create_job(
    project_id: int,
    file: UploadFile = File(...),
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
        task="process_upload",
        status=schemas.JobStatus.PENDING,
        progress=0,
        logs=""
    )
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    # 创建按用户ID和任务ID组织的目录结构
    upload_dir = f"data/uploads/{current_user.id}/{db_job.id}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # 保存上传文件
    file_path = f"{upload_dir}/{file.filename}"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    
    # 将任务添加到队列中
    task_queue.enqueue(
        tasks.process_upload,
        args=(str(db_job.id), file_path, project_id)
    )
    
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
    action: schemas.JobAction,
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
    
    # 处理不同的操作
    if action.action == schemas.JobAction.PAUSE:
        if job.status != schemas.JobStatus.PROCESSING:
            raise HTTPException(status_code=400, detail="Can only pause processing jobs")
        job.status = schemas.JobStatus.PAUSED
    
    elif action.action == schemas.JobAction.RESUME:
        if job.status != schemas.JobStatus.PAUSED:
            raise HTTPException(status_code=400, detail="Can only resume paused jobs")
        job.status = schemas.JobStatus.PROCESSING
        # 重新加入队列
        task_queue.enqueue(
            tasks.process_upload,
            args=(str(job.id), f"uploads/{current_user.id}/{job.id}", job.project_id)  # 使用位置参数确保正确的参数顺序
        )
    
    elif action.action == schemas.JobAction.CANCEL:
        if job.status in [schemas.JobStatus.COMPLETED, schemas.JobStatus.FAILED, schemas.JobStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="Cannot cancel completed, failed or cancelled jobs")
        job.status = schemas.JobStatus.CANCELLED
    
    elif action.action == schemas.JobAction.RETRY:
        # 只有已完成、失败或取消的任务可以重试
        if job.status not in [schemas.JobStatus.COMPLETED, schemas.JobStatus.FAILED, schemas.JobStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail="Can only retry completed, failed or cancelled jobs")
        
        # 重置任务状态和进度
        job.status = schemas.JobStatus.PENDING
        job.progress = 0
        job.logs = ""
        
        # 根据任务类型重新加入队列
        if job.task == "process_upload":
            # 对于上传任务，使用已存在的文件路径
            file_path = f"uploads/{current_user.id}/{job.id}"
            task_queue.enqueue(
                tasks.process_upload,
                args=(str(job.id), file_path, job.project_id)
            )
        elif job.task == "process_ai_review":
            # 对于AI审阅任务，需要获取关联的文章ID
            article = db.query(models.Article).filter(
                models.Article.project_id == job.project_id
            ).first()
            if not article:
                raise HTTPException(status_code=404, detail="Associated article not found")
            task_queue.enqueue(
                tasks.process_ai_review,
                args=(article.id, job.id)
            )
    
    db.commit()
    db.refresh(job)
    return job

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
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # 检查项目是否属于当前用户
    project = db.query(models.Project).filter(
        models.Project.id == job.project_id,
        models.Project.owner_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Not authorized to update this job")
    
    if job_update.status is not None:
        job.status = job_update.status
    if job_update.progress is not None:
        job.progress = job_update.progress
    if job_update.logs is not None:
        job.logs = job_update.logs
    
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

        while True:
            current_time = datetime.utcnow().timestamp()

            # 检查是否需要发送心跳
            if current_time - last_heartbeat >= heartbeat_interval:
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                last_heartbeat = current_time

            # 查询最近10秒内更新的任务
            recent_jobs = db.query(models.Job).join(
                models.Project
            ).filter(
                models.Project.owner_id == current_user.id,
                models.Job.updated_at >= datetime.utcnow() - timedelta(seconds=10)
            ).all()

            if recent_jobs:
                for job in recent_jobs:
                    data = {
                        "id": job.id,
                        "status": job.status,
                        "progress": job.progress,
                        "task": job.task
                    }
                    yield f"data: {json.dumps(data)}\n\n"
            
            await asyncio.sleep(2)  # Poll every 2 seconds
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
