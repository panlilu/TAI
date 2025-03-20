import pytest
from fastapi.testclient import TestClient
from app.schemas import UserRole

@pytest.mark.api
class TestUserAPI:
    """用户API测试类"""
    
    def test_register_user(self, client: TestClient):
        """测试用户注册"""
        response = client.post(
            "/users/register",
            json={"username": "newuser", "password": "password123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "newuser"
        assert "id" in data
        
    def test_register_duplicate_user(self, client: TestClient, test_user):
        """测试重复用户名注册"""
        response = client.post(
            "/users/register",
            json={"username": test_user.username, "password": "password123"}
        )
        
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]
    
    def test_read_users_me(self, client: TestClient, user_token_headers):
        """测试获取当前用户信息"""
        response = client.get("/users/me", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["role"] == UserRole.NORMAL.value
    
    def test_read_users_me_unauthorized(self, client: TestClient):
        """测试未授权获取当前用户信息"""
        response = client.get("/users/me")
        
        assert response.status_code == 401
    
    def test_list_users(self, client: TestClient, admin_token_headers, test_user):
        """测试管理员获取用户列表"""
        response = client.get("/users", headers=admin_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2  # 至少有测试用户和管理员
        assert any(user["username"] == test_user.username for user in data)
    
    def test_list_users_unauthorized(self, client: TestClient, user_token_headers):
        """测试普通用户获取用户列表"""
        response = client.get("/users", headers=user_token_headers)
        
        assert response.status_code == 403  # 只有管理员可以获取用户列表
    
    def test_get_user(self, client: TestClient, admin_token_headers, test_user):
        """测试管理员获取指定用户信息"""
        response = client.get(f"/users/{test_user.id}", headers=admin_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username
        assert data["id"] == test_user.id
    
    def test_get_user_not_found(self, client: TestClient, admin_token_headers):
        """测试获取不存在的用户"""
        response = client.get("/users/999", headers=admin_token_headers)
        
        assert response.status_code == 404
    
    def test_update_user(self, client: TestClient, admin_token_headers, test_user):
        """测试管理员更新用户角色"""
        response = client.put(
            f"/users/{test_user.id}",
            json={"user_role": UserRole.VIP.value},
            headers=admin_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == UserRole.VIP.value
    
    def test_delete_user(self, client: TestClient, admin_token_headers, test_user):
        """测试管理员删除用户"""
        # 先创建一个用户，专门用于删除
        response = client.post(
            "/users/register",
            json={"username": "user_to_delete", "password": "password123"}
        )
        user_id = response.json()["id"]
        
        # 测试删除
        response = client.delete(f"/users/{user_id}", headers=admin_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == user_id
        
        # 确认用户被删除
        response = client.get(f"/users/{user_id}", headers=admin_token_headers)
        assert response.status_code == 404 