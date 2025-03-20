import pytest
from jose import jwt
from datetime import datetime, timedelta
from unittest.mock import patch

from app.auth import create_access_token, get_password_hash, verify_password

@pytest.mark.unit
class TestAuthFunctions:
    """认证相关函数单元测试"""
    
    def test_password_hashing(self):
        """测试密码哈希功能"""
        password = "test_password"
        hashed = get_password_hash(password)
        
        # 确保哈希后的密码不同于原始密码
        assert hashed != password
        
        # 验证密码哈希是否正确
        assert verify_password(password, hashed)
        
        # 验证错误密码不匹配
        assert not verify_password("wrong_password", hashed)
    
    @patch("app.auth.SECRET_KEY", "test_secret_key")
    @patch("app.auth.ALGORITHM", "HS256")
    def test_create_access_token(self):
        """测试创建访问令牌"""
        data = {"sub": "test_user"}
        expires_delta = timedelta(minutes=30)
        
        token = create_access_token(data, expires_delta)
        
        # 解码令牌验证内容
        payload = jwt.decode(token, "test_secret_key", algorithms=["HS256"])
        
        # 验证用户数据
        assert payload.get("sub") == "test_user"
        
        # 验证过期时间存在
        assert "exp" in payload
        
        # 验证过期时间是未来的时间
        exp_time = datetime.fromtimestamp(payload["exp"])
        now = datetime.utcnow()
        assert exp_time > now 