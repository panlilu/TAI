import pytest
from fastapi.testclient import TestClient
import json
from datetime import datetime

@pytest.fixture
def test_article(db, test_user, test_article_type, test_project):
    """创建测试文章"""
    from app import models
    
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

@pytest.mark.api
class TestArticleAPI:
    """文章API测试类"""
    
    def test_create_article(self, client: TestClient, user_token_headers, test_project, test_article_type):
        """测试创建文章"""
        response = client.post(
            "/articles",
            json={
                "name": "新文章",
                "attachments": [
                    {
                        "path": "path/to/file.txt",
                        "is_active": True,
                        "filename": "file.txt",
                        "created_at": datetime.now().isoformat()
                    }
                ],
                "article_type_id": test_article_type.id,
                "project_id": test_project.id
            },
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新文章"
        assert len(data["attachments"]) == 1
        assert data["article_type_id"] == test_article_type.id
        assert data["project_id"] == test_project.id
    
    def test_get_articles(self, client: TestClient, user_token_headers, test_article):
        """测试获取文章列表"""
        response = client.get("/articles", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(a["id"] == test_article.id for a in data)
    
    def test_get_articles_by_project(self, client: TestClient, user_token_headers, test_article, test_project):
        """测试按项目获取文章列表"""
        response = client.get(f"/articles?project_id={test_project.id}", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(a["project_id"] == test_project.id for a in data)
    
    def test_get_article(self, client: TestClient, user_token_headers, test_article):
        """测试获取指定文章"""
        response = client.get(f"/articles/{test_article.id}", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_article.id
        assert data["name"] == test_article.name
        assert data["article_type_id"] == test_article.article_type_id
    
    def test_get_article_not_found(self, client: TestClient, user_token_headers):
        """测试获取不存在的文章"""
        response = client.get("/articles/999", headers=user_token_headers)
        
        assert response.status_code == 404
    
    def test_update_article(self, client: TestClient, user_token_headers, test_article):
        """测试更新文章"""
        response = client.put(
            f"/articles/{test_article.id}",
            json={
                "name": "更新后的文章",
                "attachments": [
                    {
                        "path": "updated/path.txt",
                        "is_active": True,
                        "filename": "updated.txt",
                        "created_at": datetime.now().isoformat()
                    }
                ]
            },
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后的文章"
        assert data["attachments"][0]["filename"] == "updated.txt"
    
    def test_delete_article(self, client: TestClient, user_token_headers, test_project, test_article_type):
        """测试删除文章"""
        # 先创建一个要删除的文章
        response = client.post(
            "/articles",
            json={
                "name": "要删除的文章",
                "attachments": [],
                "article_type_id": test_article_type.id,
                "project_id": test_project.id
            },
            headers=user_token_headers
        )
        article_id = response.json()["id"]
        
        # 测试删除
        response = client.delete(f"/articles/{article_id}", headers=user_token_headers)
        
        assert response.status_code == 200
        
        # 验证已删除
        response = client.get(f"/articles/{article_id}", headers=user_token_headers)
        assert response.status_code == 404
    
    def test_get_article_content(self, client: TestClient, user_token_headers, test_article):
        """测试获取文章内容"""
        response = client.get(f"/articles/{test_article.id}/content", headers=user_token_headers)
        
        # 由于这个接口可能返回文件或JSON，我们只验证状态码
        assert response.status_code == 200 