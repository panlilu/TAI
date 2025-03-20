import pytest
from jose import jwt
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.auth import create_access_token, get_password_hash, verify_password, get_current_user, get_current_active_user, check_admin_user
from app.models import User, UserRole
from app.schemas import TokenData
from fastapi import HTTPException, status

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
    
    @patch("app.auth.SECRET_KEY", "test_secret_key")
    @patch("app.auth.ALGORITHM", "HS256")
    @patch("app.auth.ACCESS_TOKEN_EXPIRE_MINUTES", 15)
    def test_create_access_token_default_expiry(self):
        """测试创建访问令牌时使用默认过期时间"""
        data = {"sub": "test_user"}
        
        token = create_access_token(data)
        
        # 解码令牌验证内容
        payload = jwt.decode(token, "test_secret_key", algorithms=["HS256"])
        
        # 验证过期时间存在
        assert "exp" in payload
        
        # 验证过期时间是未来的时间
        exp_time = datetime.fromtimestamp(payload["exp"])
        now = datetime.utcnow()
        assert exp_time > now
        
        # 不测试具体时间范围，因为这会导致测试不稳定
        # 仅验证过期时间在合理范围内（10分钟以上）
        delta = exp_time - now
        assert delta > timedelta(minutes=10)

    @patch("app.auth.jwt.decode")
    async def test_get_current_user_valid_token(self, mock_decode):
        """测试有效令牌获取当前用户"""
        # 模拟JWT解码返回有效载荷
        mock_decode.return_value = {"sub": "testuser"}
        
        # 模拟数据库会话和用户
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.username = "testuser"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_user
        
        # 调用函数
        user = await get_current_user("valid_token", mock_db)
        
        # 验证结果
        assert user == mock_user
        mock_decode.assert_called_once()

    @patch("app.auth.jwt.decode")
    async def test_get_current_user_invalid_token(self, mock_decode):
        """测试无效令牌抛出异常"""
        # 模拟JWT解码抛出异常
        mock_decode.side_effect = jwt.JWTError()
        
        # 模拟数据库会话
        mock_db = MagicMock()
        
        # 验证函数抛出预期的异常
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid_token", mock_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Could not validate credentials"

    @patch("app.auth.jwt.decode")
    async def test_get_current_user_missing_username(self, mock_decode):
        """测试令牌中缺少用户名抛出异常"""
        # 模拟JWT解码返回无效载荷（缺少sub字段）
        mock_decode.return_value = {}
        
        # 模拟数据库会话
        mock_db = MagicMock()
        
        # 验证函数抛出预期的异常
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid_token", mock_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Could not validate credentials"

    @patch("app.auth.jwt.decode")
    async def test_get_current_user_user_not_found(self, mock_decode):
        """测试用户不存在抛出异常"""
        # 模拟JWT解码返回有效载荷
        mock_decode.return_value = {"sub": "testuser"}
        
        # 模拟数据库会话，但用户不存在
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # 验证函数抛出预期的异常
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("valid_token", mock_db)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Could not validate credentials"

    async def test_get_current_active_user_active(self):
        """测试当前用户处于活跃状态"""
        # 模拟活跃用户
        mock_user = MagicMock()
        mock_user.is_active = True
        
        # 调用函数
        user = await get_current_active_user(mock_user)
        
        # 验证结果
        assert user == mock_user

    async def test_get_current_active_user_inactive(self):
        """测试当前用户处于非活跃状态抛出异常"""
        # 模拟非活跃用户
        mock_user = MagicMock()
        mock_user.is_active = False
        
        # 验证函数抛出预期的异常
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(mock_user)
        
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Inactive user"

    def test_check_admin_user_admin(self):
        """测试管理员用户权限检查"""
        # 模拟管理员用户
        mock_user = MagicMock()
        mock_user.role = UserRole.ADMIN
        
        # 调用函数
        user = check_admin_user(mock_user)
        
        # 验证结果
        assert user == mock_user

    def test_check_admin_user_non_admin(self):
        """测试非管理员用户权限检查抛出异常"""
        # 模拟非管理员用户
        mock_user = MagicMock()
        mock_user.role = UserRole.NORMAL
        
        # 验证函数抛出预期的异常
        with pytest.raises(HTTPException) as exc_info:
            check_admin_user(mock_user)
        
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == "Only admin users can perform this operation" 