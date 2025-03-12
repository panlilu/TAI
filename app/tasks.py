import os
import zipfile
import io
from datetime import datetime
from rq import get_current_job
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Job, JobTask, Article, Project, AIReviewReport
from .schemas import ArticleCreate, JobStatus, JobTaskType
from docx import Document
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
from litellm import completion
import json
from .file_converter import convert_file_to_markdown
from redis import Redis
from rq import Queue

ALLOWED_EXTENSIONS = {'.md', '.doc', '.pdf', '.txt', '.docx'}
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}

# 创建Redis连接和队列
redis_conn = Redis()
task_queue = Queue(connection=redis_conn)

def is_allowed_file(filename: str) -> bool:
    """检查文件是否为允许的类型"""
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS or ext in ALLOWED_IMAGE_EXTENSIONS

def extract_text_from_docx(file_path: str) -> str:
    """从docx文件中提取文本"""
    doc = Document(file_path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])

def extract_text_from_pdf(file_path: str) -> str:
    """从PDF文件中提取文本"""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_text_from_image(file_path: str) -> str:
    """从图片中提取文本"""
    try:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        return f"Error: Failed to extract text from image: {str(e)}"

def analyze_with_openai(prompt: str, text: str, require_json: bool = False, model_name: str = None) -> str:
    """使用LiteLLM分析文本"""
    try:
        # 使用指定的模型或默认模型
        model = model_name or os.getenv("LLM_MODEL", "deepseek/deepseek-chat")
        
        # 如果需要JSON响应，添加格式要求
        if require_json:
            prompt = f"""
{prompt}

重要提示：你必须返回一个有效的JSON对象。确保：
1. 响应必须是一个合法的JSON格式
2. 所有字符串必须使用双引号
3. 不要包含任何额外的解释文本
4. 确保所有的键名使用双引号
"""

        response = completion(
            model=model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        error_msg = f"Error: Failed to analyze text with LLM: {str(e)}"
        try:
            db = SessionLocal()
            current_job = get_current_job()
            if current_job and current_job.id:
                job_task = db.query(JobTask).filter(JobTask.id == current_job.id).first()
                if job_task:
                    job_task.logs = error_msg if not job_task.logs else f"{job_task.logs}\n{error_msg}"
                    db.commit()
        except Exception:
            pass
        finally:
            if 'db' in locals():
                db.close()
        return error_msg

def update_job_status(db: Session, job_id: int):
    """根据所有子任务的状态更新Job的状态和进度"""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return
    
    # 获取所有子任务
    tasks = db.query(JobTask).filter(JobTask.job_id == job_id).all()
    if not tasks:
        return
    
    # 计算总进度
    total_progress = sum(task.progress or 0 for task in tasks) / len(tasks)
    job.progress = int(total_progress)
    
    # 确定整体状态
    statuses = [task.status for task in tasks]
    
    # 如果所有任务都完成
    if all(status == JobStatus.COMPLETED for status in statuses):
        job.status = JobStatus.COMPLETED
    # 如果有任务失败
    elif any(status == JobStatus.FAILED for status in statuses):
        job.status = JobStatus.FAILED
    # 如果有任务被取消
    elif any(status == JobStatus.CANCELLED for status in statuses):
        job.status = JobStatus.CANCELLED
    # 如果有任务被暂停，且没有正在处理的任务
    elif any(status == JobStatus.PAUSED for status in statuses) and not any(status == JobStatus.PROCESSING for status in statuses):
        job.status = JobStatus.PAUSED
    # 如果有任务正在处理
    elif any(status == JobStatus.PROCESSING for status in statuses):
        job.status = JobStatus.PROCESSING
    # 如果有任务等待中，且没有正在处理的任务
    elif any(status == JobStatus.PENDING for status in statuses) and not any(status == JobStatus.PROCESSING for status in statuses):
        job.status = JobStatus.PENDING
    
    db.commit()

def check_job_task_status(db: Session, job_task: JobTask) -> bool:
    """检查任务是否应该继续执行"""
    # 刷新任务状态
    db.refresh(job_task)
    
    # 如果任务被取消或暂停，返回False
    if job_task.status in [JobStatus.CANCELLED, JobStatus.PAUSED]:
        return False
    return True

def execute_task(task_id: int):
    """执行单个任务"""
    db = SessionLocal()
    try:
        # 获取任务信息
        task = db.query(JobTask).filter(JobTask.id == task_id).first()
        if not task:
            return
        
        # 更新任务状态为处理中
        task.status = JobStatus.PROCESSING
        task.progress = 0
        db.commit()
        
        # 获取任务参数
        params = task.params or {}
        
        # 根据任务类型执行不同的操作
        if task.task_type == JobTaskType.CONVERT_TO_MARKDOWN:
            convert_to_markdown_task(task.id, task.article_id)
        elif task.task_type == JobTaskType.PROCESS_WITH_LLM:
            process_with_llm_task(task.id, task.article_id)
        elif task.task_type == JobTaskType.PROCESS_AI_REVIEW:
            process_ai_review_task(task.id, task.article_id)
        elif task.task_type == JobTaskType.PROCESS_UPLOAD:
            file_path = params.get("file_path")
            project_id = params.get("project_id")
            if file_path and project_id:
                process_upload_task(task.id, file_path, project_id)
            else:
                raise Exception("Missing required parameters for process_upload task")
        
        # 更新任务状态
        task.status = JobStatus.COMPLETED
        task.progress = 100
        db.commit()
        
        # 更新Job状态
        update_job_status(db, task.job_id)
        
    except Exception as e:
        # 更新任务状态为失败
        task.status = JobStatus.FAILED
        task.logs = f"Error: {str(e)}" if not task.logs else f"{task.logs}\nError: {str(e)}"
        db.commit()
        
        # 更新Job状态
        update_job_status(db, task.job_id)
        
        raise
    finally:
        db.close()

def schedule_job_tasks(job_id: int):
    """调度Job的所有任务，考虑并行度"""
    db = SessionLocal()
    try:
        # 获取Job信息
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        
        # 获取所有待处理的任务
        pending_tasks = db.query(JobTask).filter(
            JobTask.job_id == job_id,
            JobTask.status == JobStatus.PENDING
        ).all()
        
        # 获取当前正在处理的任务数量
        processing_tasks_count = db.query(JobTask).filter(
            JobTask.job_id == job_id,
            JobTask.status == JobStatus.PROCESSING
        ).count()
        
        # 计算可以启动的任务数量
        available_slots = max(0, job.parallelism - processing_tasks_count)
        
        # 启动任务
        for i in range(min(available_slots, len(pending_tasks))):
            task = pending_tasks[i]
            # 将任务加入队列
            task_queue.enqueue(execute_task, args=(task.id,))
        
        db.commit()
    except Exception as e:
        print(f"Error scheduling tasks: {str(e)}")
    finally:
        db.close()

def convert_to_markdown_task(task_id: int, article_id: int):
    """将文章附件转换为Markdown格式"""
    db = SessionLocal()
    try:
        # 获取任务信息
        task = db.query(JobTask).filter(JobTask.id == task_id).first()
        if not task:
            return
            
        # 更新任务状态为处理中
        task.status = JobStatus.PROCESSING
        db.commit()
        
        # 获取文章信息
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise Exception(f"Error: Article {article_id} not found")
        
        # 处理激活的附件
        active_attachment = None
        for attachment in article.attachments:
            if attachment.get("is_active"):
                active_attachment = attachment
                break
                
        if not active_attachment:
            raise Exception("No active attachment found")
        
        # 转换文件
        file_path = active_attachment["path"]
        markdown_text = convert_file_to_markdown(file_path)
        
        # 更新文章的processed_text
        ai_review = db.query(AIReviewReport).filter(
            AIReviewReport.article_id == article_id,
        ).first()
        
        if not ai_review:
            ai_review = AIReviewReport(
                article_id=article_id,
                job_id=task.job_id,
                is_active=True
            )
            db.add(ai_review)
            
        ai_review.processed_attachment_text = markdown_text
        db.commit()
        
        # 更新任务状态为完成
        task.status = JobStatus.COMPLETED
        task.progress = 100
        db.commit()
        
    except Exception as e:
        error_msg = f"Error: Markdown conversion failed: {str(e)}"
        task.status = JobStatus.FAILED
        task.logs = error_msg if not task.logs else f"{task.logs}\n{error_msg}"
        db.commit()
        raise
    finally:
        db.close()

def process_with_llm_task(task_id: int, article_id: int):
    """处理文章内容并生成AI审阅报告"""
    db = SessionLocal()
    try:
        # 获取任务信息
        task = db.query(JobTask).filter(JobTask.id == task_id).first()
        if not task:
            raise Exception("Task not found")
            
        # 更新任务状态
        task.status = JobStatus.PROCESSING
        task.progress = 0
        db.commit()

        # 获取文章信息
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise Exception("Article not found")

        # 获取项目信息
        project = db.query(Project).filter(Project.id == article.project_id).first()
        if not project:
            raise Exception("Project not found")

        # 获取AI审阅报告
        ai_review = db.query(AIReviewReport).filter(
            AIReviewReport.article_id == article_id
        ).first()

        if not ai_review or not ai_review.processed_attachment_text:
            raise Exception("No processed text found. Please run convert_to_markdown first.")
        
        processed_text = ai_review.processed_attachment_text
        # 使用LLM处理文章内容
        try:
            # 从config中获取提示词
            prompt = project.config.get('prompt', '')
            if not prompt:
                raise Exception("No prompt configured in project")

            model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")

            # 使用litellm的流式API
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": processed_text}
                ],
                stream=True  # 启用流式输出
            )

            # 初始化累积的响应文本
            accumulated_response = ""
            
            # 处理流式响应
            for chunk in response:
                # 检查任务状态
                if not check_job_task_status(db, task):
                    return

                # 从chunk中提取文本
                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        accumulated_response += content
                        # 更新AI审阅报告的source_data
                        ai_review.source_data = accumulated_response
                        db.commit()

                # 更新进度（这里使用一个近似值）
                current_length = len(accumulated_response)
                if current_length > 0:
                    progress = min(95, int((current_length / 1000) * 5))  # 假设平均响应长度为1000字符
                    task.progress = progress
                    db.commit()

            # 完成处理
            task.progress = 100
            task.status = JobStatus.COMPLETED
            ai_review.status = "completed"
            
        except Exception as e:
            task.status = JobStatus.FAILED
            task.logs += f"\nError during LLM processing: {str(e)}"
            ai_review.status = "failed"
            raise

        db.commit()
        return task

    except Exception as e:
        task.status = JobStatus.FAILED
        task.logs += f"\nError: {str(e)}"
        db.commit()
        raise

    finally:
        db.close()

def process_ai_review_task(task_id: int, article_id: int):
    """处理文章内容并生成完整的AI审阅报告"""
    db = SessionLocal()
    try:
        task = db.query(JobTask).filter(JobTask.id == task_id).first()
        if not task:
            raise Exception("Task not found")
            
        # 更新任务状态
        task.status = JobStatus.PROCESSING
        task.progress = 0
        db.commit()

        # 获取文章、项目和AI审阅报告
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise Exception("Article not found")

        project = db.query(Project).filter(Project.id == article.project_id).first()
        if not project:
            raise Exception("Project not found")

        ai_review = db.query(AIReviewReport).filter(
            AIReviewReport.article_id == article_id
        ).first()

        if not ai_review or not ai_review.processed_attachment_text:
            raise Exception("No processed text found. Please run convert_to_markdown first.")
        
        processed_text = ai_review.processed_attachment_text
        
        # 处理配置信息
        config = project.config or {}
        main_prompt = config.get('prompt', '')
        format_prompt = config.get('format_prompt', '')
        review_criteria = config.get('review_criteria', [])
        min_words = config.get('min_words', 0)
        max_words = config.get('max_words', 0)
        language = config.get('language', 'zh')

        if not main_prompt:
            raise Exception("No prompt configured in project")

        # 构建完整的提示词
        full_prompt = main_prompt
        if format_prompt:
            full_prompt += f"\n\n输出格式要求：\n{format_prompt}"
        if review_criteria:
            full_prompt += f"\n\n评审标准：\n{review_criteria}"
        if min_words or max_words:
            full_prompt += f"\n\n字数要求：{min_words}-{max_words}字"
        
        try:
            model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": full_prompt},
                    {"role": "user", "content": processed_text}
                ],
                stream=True
            )

            accumulated_response = ""
            for chunk in response:
                if not check_job_task_status(db, task):
                    return

                if hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content'):
                    content = chunk.choices[0].delta.content
                    if content:
                        accumulated_response += content
                        ai_review.source_data = accumulated_response
                        db.commit()

                current_length = len(accumulated_response)
                if current_length > 0:
                    progress = min(95, int((current_length / 1000) * 5))
                    task.progress = progress
                    db.commit()

            task.progress = 100
            task.status = JobStatus.COMPLETED
            ai_review.status = "completed"
            
        except Exception as e:
            task.status = JobStatus.FAILED
            task.logs += f"\nError during LLM processing: {str(e)}"
            ai_review.status = "failed"
            raise

        db.commit()
        return task

    except Exception as e:
        task.status = JobStatus.FAILED
        task.logs += f"\nError: {str(e)}"
        db.commit()
        raise

    finally:
        db.close()

def process_upload_task(task_id: int, file_path: str, project_id: int):
    """处理上传的文件"""
    print(f"Starting process_upload_task with task_id: {task_id}, file_path: {file_path}, project_id: {project_id}")
    db = SessionLocal()
    try:
        task = db.query(JobTask).filter(JobTask.id == task_id).first()
        if not task:
            print(f"Task {task_id} not found")
            return
        
        # 如果任务已经完成、失败或取消，直接返回
        if task.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            print(f"Task {task_id} is already in status: {task.status}")
            return
        
        print(f"Processing task {task_id}, updating status to PROCESSING")
        # 更新任务状态为处理中
        task.status = JobStatus.PROCESSING
        db.commit()
        
        # 获取项目所有者ID
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise Exception(f"Error: Project {project_id} not found")
            
        # 使用与上传相同的目录结构
        extract_dir = f"data/uploads/{project.owner_id}/{task.job_id}"
        os.makedirs(extract_dir, exist_ok=True)
        
        # 检查任务状态
        if not check_job_task_status(db, task):
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
        
        print(f"Found {len(all_files)} files to process")
        total_files = len(all_files)
        for index, (root, file) in enumerate(all_files):
            print(f"Processing file {index + 1}/{total_files}: {file}")
            # 检查任务状态
            if not check_job_task_status(db, task):
                return
                
            # 获取project对应的article_type_id
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise Exception(f"Error: Project {project_id} not found")

            # 创建article
            file_path = os.path.join(root, file)
            from fastapi.encoders import jsonable_encoder
            
            attachments = [{
                "path": file_path,
                "is_active": True,  # 默认第一个附件为active
                "filename": file,
                "created_at": datetime.utcnow().isoformat()
            }]
            
            db_article = Article(
                name=file,
                attachments=jsonable_encoder(attachments),
                article_type_id=project.article_type_id,
                project_id=project_id
            )
            db.add(db_article)
            db.commit()
            
            # 更新进度
            progress = int((index + 1) / total_files * 100)
            task.progress = progress
            db.commit()
        
        # 最后检查一次任务状态
        if not check_job_task_status(db, task):
            return
            
        print(f"Task {task_id} completed successfully")
        # 更新任务状态为完成
        task.status = JobStatus.COMPLETED
        task.progress = 100
        db.commit()
        
    except Exception as e:
        print(f"Error occurred in task {task_id}: {str(e)}")
        # 更新任务状态为失败
        error_msg = f"Error: File processing failed: {str(e)}"
        task.status = JobStatus.FAILED
        task.logs = error_msg if not task.logs else f"{task.logs}\n{error_msg}"
        db.commit()
        raise
    finally:
        db.close()

# 兼容旧版本的函数，调用新的任务处理函数
def convert_to_markdown(article_id: int, job_id: int):
    """将文章附件转换为Markdown格式（兼容旧版本）"""
    db = SessionLocal()
    try:
        # 创建一个JobTask
        job_task = JobTask(
            job_id=job_id,
            task_type=JobTaskType.CONVERT_TO_MARKDOWN,
            status=JobStatus.PENDING,
            article_id=article_id,
            progress=0,
            logs=""
        )
        db.add(job_task)
        db.commit()
        db.refresh(job_task)
        
        # 执行任务
        convert_to_markdown_task(job_task.id, article_id)
        
    except Exception as e:
        # 更新Job状态为失败
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.logs = f"Error: {str(e)}" if not job.logs else f"{job.logs}\nError: {str(e)}"
            db.commit()
        raise
    finally:
        db.close()

def process_with_llm(article_id: int, job_id: int):
    """处理文章内容并生成AI审阅报告（兼容旧版本）"""
    db = SessionLocal()
    try:
        # 创建一个JobTask
        job_task = JobTask(
            job_id=job_id,
            task_type=JobTaskType.PROCESS_WITH_LLM,
            status=JobStatus.PENDING,
            article_id=article_id,
            progress=0,
            logs=""
        )
        db.add(job_task)
        db.commit()
        db.refresh(job_task)
        
        # 执行任务
        process_with_llm_task(job_task.id, article_id)
        
    except Exception as e:
        # 更新Job状态为失败
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.logs = f"Error: {str(e)}" if not job.logs else f"{job.logs}\nError: {str(e)}"
            db.commit()
        raise
    finally:
        db.close()

def process_ai_review(article_id: int, job_id: int):
    """处理文章内容并生成完整的AI审阅报告（兼容旧版本）"""
    db = SessionLocal()
    try:
        # 创建一个JobTask
        job_task = JobTask(
            job_id=job_id,
            task_type=JobTaskType.PROCESS_AI_REVIEW,
            status=JobStatus.PENDING,
            article_id=article_id,
            progress=0,
            logs=""
        )
        db.add(job_task)
        db.commit()
        db.refresh(job_task)
        
        # 执行任务
        process_ai_review_task(job_task.id, article_id)
        
    except Exception as e:
        # 更新Job状态为失败
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.status = JobStatus.FAILED
            job.logs = f"Error: {str(e)}" if not job.logs else f"{job.logs}\nError: {str(e)}"
            db.commit()
        raise
    finally:
        db.close()

def process_upload(job_id, file_path, project_id):
    """处理上传的文件（兼容旧版本）"""
    db = SessionLocal()
    try:
        # 创建一个JobTask
        job_task = JobTask(
            job_id=int(job_id),
            task_type=JobTaskType.PROCESS_UPLOAD,
            status=JobStatus.PENDING,
            progress=0,
            logs="",
            params={
                "file_path": file_path,
                "project_id": int(project_id)
            }
        )
        db.add(job_task)
        db.commit()
        db.refresh(job_task)
        
        # 执行任务
        process_upload_task(job_task.id, file_path, int(project_id))
        
    except Exception as e:
        # 更新Job状态为失败
        job = db.query(Job).filter(Job.id == int(job_id)).first()
        if job:
            job.status = JobStatus.FAILED
            job.logs = f"Error: {str(e)}" if not job.logs else f"{job.logs}\nError: {str(e)}"
            db.commit()
        raise
    finally:
        db.close()
