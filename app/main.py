from datetime import timedelta
from typing import List
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from . import models, schemas, auth
from .database import engine, get_db
from .models import UserRole

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="User Management API")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/token", response_model=schemas.Token)
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

@app.post("/users/register", response_model=schemas.User)
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

@app.get("/users/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    return current_user

@app.get("/users", response_model=List[schemas.User])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.check_admin_user),
    db: Session = Depends(get_db)
):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users

@app.get("/users/{user_id}", response_model=schemas.User)
async def get_user(
    user_id: int,
    current_user: models.User = Depends(auth.check_admin_user),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/users/{user_id}", response_model=schemas.User)
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

@app.delete("/users/{user_id}", response_model=schemas.User)
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
@app.post("/article-types", response_model=schemas.ArticleType)
async def create_article_type(
    article_type: schemas.ArticleTypeCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_article_type = models.ArticleType(
        name=article_type.name,
        is_public=article_type.is_public,
        prompt=article_type.prompt,
        fields=article_type.fields,
        owner_id=current_user.id
    )
    db.add(db_article_type)
    db.commit()
    db.refresh(db_article_type)
    return db_article_type

@app.get("/article-types", response_model=List[schemas.ArticleType])
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

@app.put("/article-types/{article_type_id}", response_model=schemas.ArticleType)
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
    db_article_type.fields = article_type.fields
    db.commit()
    db.refresh(db_article_type)
    return db_article_type

@app.delete("/article-types/{article_type_id}")
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
@app.post("/articles", response_model=schemas.Article)
async def create_article(
    article: schemas.ArticleCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_article = models.Article(
        name=article.name,
        attachments=article.attachments,
        article_type_id=article.article_type_id
    )
    db.add(db_article)
    db.commit()
    db.refresh(db_article)
    return db_article

@app.get("/articles", response_model=List[schemas.Article])
async def get_articles(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    articles = db.query(models.Article).offset(skip).limit(limit).all()
    return articles

@app.get("/articles/{article_id}", response_model=schemas.Article)
async def get_article(
    article_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@app.put("/articles/{article_id}", response_model=schemas.Article)
async def update_article(
    article_id: int,
    article: schemas.ArticleUpdate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if db_article is None:
        raise HTTPException(status_code=404, detail="Article not found")
    
    db_article.name = article.name
    db_article.attachments = article.attachments
    db.commit()
    db.refresh(db_article)
    return db_article

@app.delete("/articles/{article_id}")
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

# AI批阅报告管理API
@app.post("/ai-reviews", response_model=schemas.AIReviewReport)
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

@app.get("/ai-reviews", response_model=List[schemas.AIReviewReport])
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

@app.put("/ai-reviews/{ai_review_id}", response_model=schemas.AIReviewReport)
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
@app.post("/projects", response_model=schemas.Project)
async def create_project(
    project: schemas.ProjectCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    db_project = models.Project(
        name=project.name,
        prompt=project.prompt,
        fields=project.fields,
        auto_approve=project.auto_approve,
        owner_id=current_user.id,
        article_type_id=project.article_type_id
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@app.get("/projects", response_model=List[schemas.Project])
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

@app.get("/projects/{project_id}", response_model=schemas.Project)
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

@app.put("/projects/{project_id}", response_model=schemas.Project)
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
    if project.fields is not None:
        db_project.fields = project.fields
    if project.auto_approve is not None:
        db_project.auto_approve = project.auto_approve
    
    db.commit()
    db.refresh(db_project)
    return db_project

@app.delete("/projects/{project_id}")
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
