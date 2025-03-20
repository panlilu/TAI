import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.schemas import JobTaskType, JobStatus, JobAction

@pytest.fixture
def test_job(db, test_project):
    """创建测试任务"""
    from app import models
    
    job = models.Job(
        project_id=test_project.id,
        name="测试任务",
        status=JobStatus.PENDING,
        progress=0,
        logs="任务日志",
        parallelism=1
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    
    # 添加任务项
    task = models.JobTask(
        job_id=job.id,
        task_type=JobTaskType.PROCESS_AI_REVIEW,
        status=JobStatus.PENDING,
        progress=0,
        params={"param": "value"}
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return job

@pytest.mark.api
class TestJobAPI:
    """任务API测试类"""
    
    @patch("app.main.task_queue.enqueue")
    def test_create_job(self, mock_enqueue, client: TestClient, user_token_headers, test_project):
        """测试创建任务"""
        response = client.post(
            "/jobs",
            json={
                "project_id": test_project.id,
                "name": "新任务",
                "parallelism": 2,
                "tasks": [
                    {
                        "task_type": JobTaskType.PROCESS_AI_REVIEW.value,
                        "params": {"model": "gpt-4"}
                    }
                ]
            },
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "新任务"
        assert data["project_id"] == test_project.id
        assert data["parallelism"] == 2
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_type"] == JobTaskType.PROCESS_AI_REVIEW.value
        # 验证任务是否入队
        assert mock_enqueue.called
    
    def test_get_jobs(self, client: TestClient, user_token_headers, test_job):
        """测试获取任务列表"""
        response = client.get("/jobs", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(j["id"] == test_job.id for j in data)
    
    def test_get_jobs_by_project(self, client: TestClient, user_token_headers, test_job, test_project):
        """测试按项目获取任务列表"""
        response = client.get(f"/jobs?project_id={test_project.id}", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(j["project_id"] == test_project.id for j in data)
    
    def test_get_job(self, client: TestClient, user_token_headers, test_job):
        """测试获取指定任务"""
        response = client.get(f"/jobs/{test_job.id}", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_job.id
        assert data["name"] == test_job.name
        assert len(data["tasks"]) == 1
    
    def test_get_job_not_found(self, client: TestClient, user_token_headers):
        """测试获取不存在的任务"""
        response = client.get("/jobs/999", headers=user_token_headers)
        
        assert response.status_code == 404
    
    @patch("app.main.task_queue.enqueue")
    def test_job_action(self, mock_enqueue, client: TestClient, user_token_headers, test_job):
        """测试任务操作(暂停/恢复/取消/重试)"""
        # 测试暂停
        response = client.post(
            f"/jobs/{test_job.id}/action",
            json={"action": JobAction.PAUSE.value},
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == JobStatus.PAUSED.value
        
        # 测试恢复
        response = client.post(
            f"/jobs/{test_job.id}/action",
            json={"action": JobAction.RESUME.value},
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == JobStatus.PENDING.value
    
    def test_get_job_tasks(self, client: TestClient, user_token_headers, test_job):
        """测试获取任务下的子任务列表"""
        response = client.get(f"/jobs/{test_job.id}/tasks", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["job_id"] == test_job.id
        assert data[0]["task_type"] == JobTaskType.PROCESS_AI_REVIEW.value
    
    def test_get_job_task(self, client: TestClient, user_token_headers, test_job):
        """测试获取指定子任务"""
        # 先获取任务的子任务ID
        response = client.get(f"/jobs/{test_job.id}/tasks", headers=user_token_headers)
        task_id = response.json()[0]["id"]
        
        # 测试获取特定子任务
        response = client.get(f"/jobs/{test_job.id}/tasks/{task_id}", headers=user_token_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == task_id
        assert data["job_id"] == test_job.id
    
    @patch("app.main.task_queue.enqueue")
    def test_update_job(self, mock_enqueue, client: TestClient, user_token_headers, test_job):
        """测试更新任务"""
        response = client.put(
            f"/jobs/{test_job.id}",
            json={"name": "更新后的任务名称"},
            headers=user_token_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后的任务名称"
    
    @patch("app.main.task_queue.enqueue")
    def test_cancel_all_jobs(self, mock_enqueue, client: TestClient, user_token_headers, test_job):
        """测试取消所有任务"""
        response = client.post("/jobs/cancel-all", headers=user_token_headers)
        
        assert response.status_code == 200
        
        # 验证任务状态
        response = client.get(f"/jobs/{test_job.id}", headers=user_token_headers)
        data = response.json()
        assert data["status"] == JobStatus.CANCELLED.value 