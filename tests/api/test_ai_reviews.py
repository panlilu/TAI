import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

@pytest.fixture
def test_ai_review(db, test_article):
    """创建测试AI审阅报告"""
    from app import models
    
    ai_review = models.AIReviewReport(
        article_id=test_article.id,
        source_data="测试源数据",
        processed_attachment_text="处理后的文本",
        status="completed",
        structured_data={"key": "value"}
    )
    db.add(ai_review)
    db.commit()
    db.refresh(ai_review)
    return ai_review

@pytest.mark.api
class TestAIReviewAPI:
    """AI审阅API测试类"""
    
    @patch("app.main.task_queue.enqueue")
    def test_create_article_review(self, mock_enqueue, client: TestClient, user_token_headers, test_article):
        """测试创建文章审阅任务"""
        response = client.post(
            f"/articles/{test_article.id}/review",
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["tasks"]) > 0
        # 验证任务是否入队
        assert mock_enqueue.called
    
    @patch("app.main.task_queue.enqueue")
    def test_extract_article_structured_data(self, mock_enqueue, client: TestClient, user_token_headers, test_article, test_ai_review):
        """测试提取文章结构化数据"""
        response = client.post(
            f"/articles/{test_article.id}/extract-structured-data",
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert len(data["tasks"]) > 0
        # 验证任务是否入队
        assert mock_enqueue.called
    
    def test_create_ai_review(self, client: TestClient, user_token_headers, test_article):
        """测试直接创建AI审阅报告"""
        response = client.post(
            "/ai-reviews",
            json={
                "article_id": test_article.id,
                "source_data": "手动创建的审阅数据",
                "status": "completed"
            },
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["article_id"] == test_article.id
        assert data["source_data"] == "手动创建的审阅数据"
        assert data["status"] == "completed"
    
    def test_get_ai_reviews(self, client: TestClient, user_token_headers, test_article, test_ai_review):
        """测试获取文章的AI审阅报告列表"""
        response = client.get(
            f"/ai-reviews?article_id={test_article.id}",
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(r["id"] == test_ai_review.id for r in data)
    
    def test_get_structured_data(self, client: TestClient, user_token_headers, test_article, test_ai_review):
        """测试获取结构化数据"""
        response = client.get(
            f"/structured-data?article_id={test_article.id}",
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "value"  # 匹配我们之前设置的结构化数据
    
    def test_update_ai_review(self, client: TestClient, user_token_headers, test_ai_review):
        """测试更新AI审阅报告"""
        response = client.put(
            f"/ai-reviews/{test_ai_review.id}",
            json={
                "source_data": "更新后的审阅数据",
                "structured_data": {"updated": "value"}
            },
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["source_data"] == "更新后的审阅数据"
        assert data["structured_data"]["updated"] == "value" 