import os
import zipfile
import io
from datetime import datetime
from rq import get_current_job
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Job, Article, Project, AIReviewReport
from .schemas import ArticleCreate, JobStatus
from docx import Document
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
from litellm import completion

ALLOWED_EXTENSIONS = {'.md', '.doc', '.pdf', '.txt', '.docx'}
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}

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

def analyze_with_openai(prompt: str, text: str, require_json: bool = False) -> str:
    """使用LiteLLM分析文本"""
    try:
        # 从环境变量获取模型配置
        model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")
        
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
            # 尝试获取当前任务并记录错误
            db = SessionLocal()
            current_job = get_current_job()
            if current_job and current_job.id:
                job = db.query(Job).filter(Job.id == current_job.id).first()
                if job:
                    job.logs = error_msg if not job.logs else f"{job.logs}\n{error_msg}"
                    db.commit()
        except Exception:
            pass
        finally:
            db.close()
        return error_msg

def process_ai_review(article_id: int, job_id: int):
    """处理AI审阅任务"""
    db = SessionLocal()
    try:
        # 获取任务信息
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
            
        # 更新任务状态为处理中
        job.status = JobStatus.PROCESSING
        db.commit()
        
        # 获取文章信息
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise Exception(f"Error: Article {article_id} not found")
            
        # 获取项目信息
        project = article.project
        if not project:
            raise Exception("Error: Project not found")
            
        # 查找是否已存在相同job的AI审阅报告
        ai_review = db.query(AIReviewReport).filter(
            AIReviewReport.job_id == job_id
        ).first()
        
        # 如果不存在，则创建新的
        if not ai_review:
            ai_review = AIReviewReport(
                article_id=article_id,
                job_id=job_id,
                is_active=True
            )
            db.add(ai_review)
            db.commit()
        
        # 处理激活的附件
        processed_text = ""
        active_attachment = None
        for attachment in article.attachments:
            if attachment.get("is_active"):
                active_attachment = attachment
                break
                
        if active_attachment:
            file_path = active_attachment["path"]
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # 根据文件类型处理
            if file_ext in ['.txt', '.md']:
                with open(file_path, 'r', encoding='utf-8') as f:
                    processed_text = f.read()
            elif file_ext == '.docx':
                processed_text = extract_text_from_docx(file_path)
            elif file_ext == '.pdf':
                processed_text = extract_text_from_pdf(file_path)
            
            # 如果是图片文件，添加图片描述
            if file_ext in ALLOWED_IMAGE_EXTENSIONS:
                image_text = extract_text_from_image(file_path)
                if image_text:
                    processed_text += f"\nImage Text:\n{image_text}\n"
        
        # 更新处理后的文本
        ai_review.processed_attachment_text = processed_text
        db.commit()
        
        # 使用项目的prompt分析文本
        if project.prompt:
            source_data = analyze_with_openai(project.prompt, processed_text)
            ai_review.source_data = source_data
            
            # 使用schema_prompt生成结构化数据
            if project.schema_prompt:
                combined_text = f"{processed_text}\n\n分析报告:\n{source_data}"
                structured_data_str = analyze_with_openai(project.schema_prompt, combined_text, require_json=True)
                # 尝试将返回的字符串解析为JSON对象
                try:
                    import json
                    structured_data = json.loads(structured_data_str)
                    ai_review.structured_data = structured_data
                except json.JSONDecodeError as e:
                    # 记录错误信息到job.logs
                    error_msg = f"Error: Failed to parse structured data as JSON: {str(e)}\nReceived data: {structured_data_str}"
                    job.logs = error_msg if not job.logs else f"{job.logs}\n{error_msg}"
                    # 使用空JSON对象
                    ai_review.structured_data = {}
            else:
                # 如果没有schema_prompt，使用空JSON对象
                ai_review.structured_data = {}
                
        db.commit()
        
        # 更新任务状态为完成
        job.status = JobStatus.COMPLETED
        job.progress = 100
        db.commit()
        
    except Exception as e:
        # 更新任务状态为失败
        error_msg = f"Error: Task execution failed: {str(e)}"
        job.status = JobStatus.FAILED
        job.logs = error_msg if not job.logs else f"{job.logs}\n{error_msg}"
        db.commit()
        raise
    finally:
        db.close()


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
        
        # 获取项目所有者ID
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise Exception(f"Error: Project {project_id} not found")
            
        # 使用与上传相同的目录结构
        extract_dir = f"data/uploads/{project.owner_id}/{job_id}"
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
        error_msg = f"Error: File processing failed: {str(e)}"
        job.status = JobStatus.FAILED
        job.logs = error_msg if not job.logs else f"{job.logs}\n{error_msg}"
        db.commit()
        raise
    finally:
        db.close()
