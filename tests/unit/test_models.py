import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, User, ArticleType, Article, Project, Job, JobTask, AIReviewReport
from app.schemas import UserRole, JobStatus, JobTaskType

@pytest.fixture
def engine():
    """创建内存数据库引擎"""
    return create_engine("sqlite:///:memory:")

@pytest.fixture
def session(engine):
    """创建测试用的数据库会话"""
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

@pytest.mark.unit
class TestUserModel:
    """用户模型测试"""
    
    def test_create_user(self, session):
        """测试创建用户"""
        user = User(
            username="testuser",
            hashed_password="hashed_password",
            role=UserRole.NORMAL,
            is_active=True
        )
        session.add(user)
        session.commit()
        
        # 验证用户被创建
        db_user = session.query(User).filter(User.username == "testuser").first()
        assert db_user is not None
        assert db_user.username == "testuser"
        assert db_user.hashed_password == "hashed_password"
        assert db_user.role == UserRole.NORMAL
        assert db_user.is_active == True

    def test_user_article_type_relationship(self, session):
        """测试用户与文章类型的关系"""
        # 创建用户
        user = User(
            username="testuser",
            hashed_password="hashed_password",
            role=UserRole.NORMAL
        )
        session.add(user)
        session.commit()
        
        # 为用户创建文章类型
        article_type = ArticleType(
            name="测试类型",
            is_public=False,
            config={"prompt": "测试提示"},
            owner_id=user.id
        )
        session.add(article_type)
        session.commit()
        
        # 验证关系
        db_user = session.query(User).filter(User.id == user.id).first()
        assert len(db_user.article_types) == 1
        assert db_user.article_types[0].name == "测试类型"
        assert db_user.article_types[0].owner_id == user.id

@pytest.mark.unit
class TestArticleTypeModel:
    """文章类型模型测试"""
    
    def test_create_article_type(self, session):
        """测试创建文章类型"""
        user = User(username="testuser", hashed_password="hashed_password")
        session.add(user)
        session.commit()
        
        article_type = ArticleType(
            name="技术文档",
            is_public=True,
            config={"prompt": "这是一个技术文档的prompt"},
            owner_id=user.id
        )
        session.add(article_type)
        session.commit()
        
        # 验证文章类型被创建
        db_article_type = session.query(ArticleType).filter(ArticleType.name == "技术文档").first()
        assert db_article_type is not None
        assert db_article_type.name == "技术文档"
        assert db_article_type.is_public == True
        assert db_article_type.config == {"prompt": "这是一个技术文档的prompt"}
        assert db_article_type.owner_id == user.id

@pytest.mark.unit
class TestArticleModel:
    """文章模型测试"""
    
    def test_create_article(self, session):
        """测试创建文章"""
        # 创建用户
        user = User(username="testuser", hashed_password="hashed_password")
        session.add(user)
        
        # 创建文章类型
        article_type = ArticleType(
            name="技术文档",
            owner_id=user.id
        )
        session.add(article_type)
        
        # 创建项目
        project = Project(
            name="测试项目",
            owner_id=user.id,
            article_type_id=article_type.id
        )
        session.add(project)
        session.commit()
        
        # 创建文章
        article = Article(
            name="测试文章",
            attachments=[{"path": "test.txt", "filename": "test.txt", "is_active": True}],
            article_type_id=article_type.id,
            project_id=project.id
        )
        session.add(article)
        session.commit()
        
        # 验证文章被创建
        db_article = session.query(Article).filter(Article.name == "测试文章").first()
        assert db_article is not None
        assert db_article.name == "测试文章"
        assert len(db_article.attachments) == 1
        assert db_article.attachments[0]["path"] == "test.txt"
        assert db_article.article_type_id == article_type.id
        assert db_article.project_id == project.id

    def test_article_relationships(self, session):
        """测试文章与其他模型的关系"""
        # 创建用户
        user = User(username="testuser", hashed_password="hashed_password")
        session.add(user)
        
        # 创建文章类型
        article_type = ArticleType(
            name="技术文档",
            owner_id=user.id
        )
        session.add(article_type)
        
        # 创建项目
        project = Project(
            name="测试项目",
            owner_id=user.id,
            article_type_id=article_type.id
        )
        session.add(project)
        session.commit()
        
        # 创建文章
        article = Article(
            name="测试文章",
            attachments=[],
            article_type_id=article_type.id,
            project_id=project.id
        )
        session.add(article)
        session.commit()
        
        # 验证关系
        db_article = session.query(Article).filter(Article.id == article.id).first()
        assert db_article.article_type.name == "技术文档"
        assert db_article.project.name == "测试项目"

@pytest.mark.unit
class TestProjectModel:
    """项目模型测试"""
    
    def test_create_project(self, session):
        """测试创建项目"""
        # 创建用户
        user = User(username="testuser", hashed_password="hashed_password")
        session.add(user)
        
        # 创建文章类型
        article_type = ArticleType(
            name="技术文档",
            owner_id=user.id
        )
        session.add(article_type)
        session.commit()
        
        # 创建项目
        project = Project(
            name="测试项目",
            config={"key": "value"},
            auto_approve=True,
            owner_id=user.id,
            article_type_id=article_type.id
        )
        session.add(project)
        session.commit()
        
        # 验证项目被创建
        db_project = session.query(Project).filter(Project.name == "测试项目").first()
        assert db_project is not None
        assert db_project.name == "测试项目"
        assert db_project.config == {"key": "value"}
        assert db_project.auto_approve == True
        assert db_project.owner_id == user.id
        assert db_project.article_type_id == article_type.id 