import os
import zipfile
from datetime import datetime
from rq import get_current_job
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Job, Article, Project
from .schemas import ArticleCreate, JobStatus

ALLOWED_EXTENSIONS = {'.md', '.doc', '.pdf', '.txt', '.docx'}

def is_allowed_file(filename: str) -> bool:
    """检查文件是否为允许的类型"""
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


def check_job_status(db: Session, job: Job) -> bool:
    """检查任务是否应该继续执行"""
    # 刷新任务状态
    db.refresh(job)
    
    # 如果任务被取消或暂停，返回False
    if job.status in [JobStatus.CANCELLED, JobStatus.PAUSED]:
        return False
    return True

def process_upload(job_id, file_path, project_id):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == int(job_id)).first()
        if not job:
            return
        
        # 如果任务已经完成、失败或取消，直接返回
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return
        
        # 更新任务状态为处理中
        job.status = JobStatus.PROCESSING
        db.commit()
        
        # 解压文件
        extract_dir = f"uploads/{job_id}"
        os.makedirs(extract_dir, exist_ok=True)
        
        # 检查任务状态
        if not check_job_status(db, job):
            return

        # 检查是否为zip文件
        if file_path.endswith('.zip'):
            # 解压zip文件
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            # 移动zip文件
            zip_filename = os.path.basename(file_path)
            os.rename(file_path, os.path.join(extract_dir, zip_filename))
        else:
            # 如果不是zip文件,直接移动到extract_dir
            filename = os.path.basename(file_path)
            os.rename(file_path, os.path.join(extract_dir, filename))

        # 获取所有可接受文件
        all_files = []
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                if is_allowed_file(file):
                    all_files.append((root, file))
        
        total_files = len(all_files)
        for index, (root, file) in enumerate(all_files):
            # 检查任务状态
            if not check_job_status(db, job):
                return
                
            # 获取project对应的article_type_id
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise Exception(f"Project {project_id} not found")

            # 创建article
            file_path = os.path.join(root, file)
            article_data = ArticleCreate(
                name=file,
                attachments=[{
                    "path": file_path,
                    "is_active": True,  # 默认第一个附件为active
                    "filename": file,
                    "created_at": datetime.utcnow().isoformat()
                }],
                article_type_id=project.article_type_id
            )
            db_article = Article(
                name=article_data.name,
                attachments=article_data.attachments,
                article_type_id=article_data.article_type_id,
                project_id=project_id
            )
            db.add(db_article)
            db.commit()
            
            # 更新进度
            progress = int((index + 1) / total_files * 100)
            job.progress = progress
            db.commit()
        
        # 最后检查一次任务状态
        if not check_job_status(db, job):
            return
            
        # 更新任务状态为完成
        job.status = JobStatus.COMPLETED
        job.progress = 100
        db.commit()
        
    except Exception as e:
        # 更新任务状态为失败
        job.status = JobStatus.FAILED
        job.logs = str(e)
        db.commit()
        raise
    finally:
        db.close()
