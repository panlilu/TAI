import pytest
from fastapi.testclient import TestClient

@pytest.mark.api
class TestArticleTypeAPI:
    """文章类型API测试类"""
    
    def test_create_article_type(self, client: TestClient, user_token_headers):
        """测试创建文章类型"""
        response = client.post(
            "/article-types",
            json={
                "name": "新文章类型",
                "is_public": True,
                "config": {"prompt": "测试提示"}
            },
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新文章类型"
        assert data["is_public"] == True
        assert data["config"]["prompt"] == "测试提示"
    
    def test_get_article_types(self, client: TestClient, user_token_headers, test_article_type):
        """测试获取文章类型列表"""
        response = client.get("/article-types", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(at["id"] == test_article_type.id for at in data)
    
    def test_get_article_type(self, client: TestClient, user_token_headers, test_article_type):
        """测试获取指定文章类型"""
        response = client.get(f"/article-types/{test_article_type.id}", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_article_type.id
        assert data["name"] == test_article_type.name
    
    def test_get_article_type_not_found(self, client: TestClient, user_token_headers):
        """测试获取不存在的文章类型"""
        response = client.get("/article-types/999", headers=user_token_headers)
        
        assert response.status_code == 404
    
    def test_update_article_type(self, client: TestClient, user_token_headers, test_article_type):
        """测试更新文章类型"""
        response = client.put(
            f"/article-types/{test_article_type.id}",
            json={
                "name": "更新后的文章类型",
                "config": {"prompt": "更新后的提示"}
            },
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后的文章类型"
        assert data["config"]["prompt"] == "更新后的提示"
    
    def test_update_article_type_unauthorized(self, client: TestClient, admin_token_headers, test_article_type):
        """测试未授权更新文章类型"""
        # 管理员尝试更新普通用户的文章类型
        response = client.put(
            f"/article-types/{test_article_type.id}",
            json={"name": "非法更新"},
            headers=admin_token_headers
        )
        
        assert response.status_code == 403
    
    def test_delete_article_type(self, client: TestClient, user_token_headers, test_user):
        """测试删除文章类型"""
        # 先创建一个要删除的文章类型
        response = client.post(
            "/article-types",
            json={"name": "要删除的类型", "is_public": False},
            headers=user_token_headers
        )
        article_type_id = response.json()["id"]
        
        # 测试删除
        response = client.delete(f"/article-types/{article_type_id}", headers=user_token_headers)
        
        assert response.status_code == 200
        
        # 验证已删除
        response = client.get(f"/article-types/{article_type_id}", headers=user_token_headers)
        assert response.status_code == 404 