import pytest
from fastapi.testclient import TestClient

@pytest.mark.api
class TestProjectAPI:
    """项目API测试类"""
    
    def test_create_project(self, client: TestClient, user_token_headers, test_article_type):
        """测试创建项目"""
        response = client.post(
            "/projects",
            json={
                "name": "新项目",
                "auto_approve": True,
                "article_type_id": test_article_type.id
            },
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新项目"
        assert data["auto_approve"] == True
        assert data["article_type_id"] == test_article_type.id
    
    def test_get_projects(self, client: TestClient, user_token_headers, test_project):
        """测试获取项目列表"""
        response = client.get("/projects", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(p["id"] == test_project.id for p in data)
    
    def test_get_project(self, client: TestClient, user_token_headers, test_project):
        """测试获取指定项目"""
        response = client.get(f"/projects/{test_project.id}", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_project.id
        assert data["name"] == test_project.name
        assert data["article_type_id"] == test_project.article_type_id
    
    def test_get_project_not_found(self, client: TestClient, user_token_headers):
        """测试获取不存在的项目"""
        response = client.get("/projects/999", headers=user_token_headers)
        
        assert response.status_code == 404
    
    def test_update_project(self, client: TestClient, user_token_headers, test_project):
        """测试更新项目"""
        response = client.put(
            f"/projects/{test_project.id}",
            json={
                "name": "更新后的项目",
                "config": {"custom_setting": "value"},
                "auto_approve": False
            },
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后的项目"
        assert data["config"]["custom_setting"] == "value"
        assert data["auto_approve"] == False
    
    def test_delete_project(self, client: TestClient, user_token_headers, test_article_type):
        """测试删除项目"""
        # 先创建一个要删除的项目
        response = client.post(
            "/projects",
            json={
                "name": "要删除的项目",
                "article_type_id": test_article_type.id
            },
            headers=user_token_headers
        )
        project_id = response.json()["id"]
        
        # 测试删除
        response = client.delete(f"/projects/{project_id}", headers=user_token_headers)
        
        assert response.status_code == 200
        
        # 验证已删除
        response = client.get(f"/projects/{project_id}", headers=user_token_headers)
        assert response.status_code == 404
    
    def test_export_project_to_csv(self, client: TestClient, user_token_headers, test_project):
        """测试导出项目为CSV"""
        response = client.get(
            f"/projects/{test_project.id}/export-csv",
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
        assert "attachment; filename=" in response.headers["Content-Disposition"] 