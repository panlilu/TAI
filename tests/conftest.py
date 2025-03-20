import os
import sys
import pytest
import asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy_utils import database_exists, create_database, drop_database
from typing import Generator, Dict, Any

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import Base, get_db
from app import models
from app.auth import get_password_hash
from app.schemas import UserRole, JobStatus, JobTaskType, JobAction

# 测试数据库URL
TEST_DATABASE_URL = "sqlite:///./test.db"

# 创建测试数据库引擎
engine = create_engine(TEST_DATABASE_URL)

# 创建会话
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def event_loop():
    """创建一个会话范围的事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
def db():
    """每个测试函数创建一个新的数据库会话"""
    # 创建测试数据库结构
    Base.metadata.create_all(bind=engine)
    
    # 创建会话
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        # 清理数据
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

@pytest.fixture
def client(db) -> Generator:
    """创建一个FastAPI测试客户端"""
    from app.main import api_app
    
    # 重写依赖项
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    api_app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(api_app) as c:
        yield c

@pytest.fixture
def test_user(db):
    """创建测试用户"""
    user = models.User(
        username="testuser",
        hashed_password=get_password_hash("testpass"),
        role=UserRole.NORMAL,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def test_admin(db):
    """创建测试管理员用户"""
    admin = models.User(
        username="admin",
        hashed_password=get_password_hash("adminpass"),
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin

@pytest.fixture
def user_token_headers(client: TestClient, test_user) -> Dict[str, str]:
    """获取用户认证令牌的Headers"""
    login_data = {
        "username": test_user.username,
        "password": "testpass"
    }
    r = client.post("/token", data=login_data)
    tokens = r.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}

@pytest.fixture
def admin_token_headers(client: TestClient, test_admin) -> Dict[str, str]:
    """获取管理员认证令牌的Headers"""
    login_data = {
        "username": test_admin.username,
        "password": "adminpass"
    }
    r = client.post("/token", data=login_data)
    tokens = r.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}

@pytest.fixture
def test_article_type(db, test_user):
    """创建测试文章类型"""
    article_type = models.ArticleType(
        name="测试文章类型",
        is_public=True,
        config={},
        owner_id=test_user.id
    )
    db.add(article_type)
    db.commit()
    db.refresh(article_type)
    return article_type

@pytest.fixture
def test_project(db, test_user, test_article_type):
    """创建测试项目"""
    project = models.Project(
        name="测试项目",
        config={},
        auto_approve=True,
        owner_id=test_user.id,
        article_type_id=test_article_type.id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@pytest.fixture
def test_article(db, test_user, test_article_type, test_project):
    """创建测试文章"""
    from datetime import datetime
    
    article = models.Article(
        name="测试文章",
        attachments=[
            {
                "path": "test/path.txt",
                "is_active": True,
                "filename": "test.txt",
                "created_at": datetime.now().isoformat()
            }
        ],
        article_type_id=test_article_type.id,
        project_id=test_project.id
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article 