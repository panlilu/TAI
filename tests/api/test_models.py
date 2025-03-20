import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

@pytest.mark.api
class TestModelConfigAPI:
    """模型配置API测试类"""
    
    @patch("app.main.tasks.get_model_config")
    def test_get_models(self, mock_get_model_config, client: TestClient, user_token_headers):
        """测试获取模型列表"""
        # 模拟返回值
        mock_get_model_config.return_value = {
            "models": {
                "gpt-3.5": {"type": "openai", "max_tokens": 4096},
                "gpt-4": {"type": "openai", "max_tokens": 8192}
            }
        }
        
        response = client.get("/models", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert "gpt-3.5" in data
        assert "gpt-4" in data
    
    @patch("app.main.tasks.get_model_config")
    def test_get_model_details(self, mock_get_model_config, client: TestClient, user_token_headers):
        """测试获取模型详情"""
        # 模拟返回值
        mock_get_model_config.return_value = {
            "models": {
                "gpt-3.5": {"type": "openai", "max_tokens": 4096},
                "gpt-4": {"type": "openai", "max_tokens": 8192}
            }
        }
        
        response = client.get("/models/gpt-4", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "openai"
        assert data["max_tokens"] == 8192
    
    @patch("app.main.tasks.get_model_config")
    def test_get_task_models(self, mock_get_model_config, client: TestClient, user_token_headers):
        """测试获取任务模型"""
        # 模拟返回值
        mock_get_model_config.return_value = {
            "task_models": {
                "ai_review": ["gpt-3.5", "gpt-4"],
                "convert_to_markdown": ["gpt-3.5"]
            }
        }
        
        response = client.get("/tasks/ai_review/models", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert "gpt-3.5" in data
        assert "gpt-4" in data
    
    @patch("app.main.tasks.get_model_config")
    def test_get_model_config(self, mock_get_model_config, client: TestClient, user_token_headers):
        """测试获取模型配置"""
        # 模拟返回值
        config = {
            "models": {
                "gpt-3.5": {"type": "openai", "max_tokens": 4096},
                "gpt-4": {"type": "openai", "max_tokens": 8192}
            },
            "task_models": {
                "ai_review": ["gpt-3.5", "gpt-4"],
                "convert_to_markdown": ["gpt-3.5"]
            }
        }
        mock_get_model_config.return_value = config
        
        response = client.get("/model-config", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data == config 