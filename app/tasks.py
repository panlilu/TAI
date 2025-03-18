import os
import zipfile
import io
from datetime import datetime, timedelta
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
import tomli
from .file_converter import convert_file_to_markdown
from redis import Redis
from rq import Queue
import logging

ALLOWED_EXTENSIONS = {'.md', '.doc', '.pdf', '.txt', '.docx'}
ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}

# 创建Redis连接和队列
redis_conn = Redis()
# 创建一个默认队列，用于并行执行不同job的任务
task_queue = Queue(connection=redis_conn)
# 创建一个执行任务的队列字典，用于跟踪每个job的任务执行
# 键为job_id，值为当前正在执行的任务数量
job_tasks = {}

# 加载模型配置
def load_model_config():
    """加载模型配置文件"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'model_config.toml')
    try:
        with open(config_path, 'rb') as f:
            return tomli.load(f)
    except Exception as e:
        print(f"Error loading model config: {str(e)}")
        return {"models": [], "tasks": {}}

# 全局模型配置
MODEL_CONFIG = load_model_config()

# 获取任务可用的模型列表
def get_available_models_for_task(task_type):
    """获取特定任务类型可用的模型列表"""
    task_config = MODEL_CONFIG.get("tasks", {}).get(task_type, {})
    return task_config.get("available_models", [])

# 获取任务的默认模型
def get_default_model_for_task(task_type):
    """获取特定任务类型的默认模型"""
    task_config = MODEL_CONFIG.get("tasks", {}).get(task_type, {})
    default_model = task_config.get("default_model", "")
    if not default_model and task_config.get("available_models"):
        return task_config["available_models"][0]
    return default_model or os.getenv("LLM_MODEL", "deepseek/deepseek-chat")

# 获取任务的默认配置
def get_task_default_config(task_type):
    """获取特定任务类型的默认配置"""
    task_config = MODEL_CONFIG.get("tasks", {}).get(task_type, {})
    return task_config.get("default_config", {})

# 获取任务配置
def get_task_config(task_type, project_config):
    """获取特定任务类型的配置，合并项目配置和默认配置"""
    default_config = get_task_default_config(task_type)
    project_task_config = project_config.get("tasks", {}).get(task_type, {})
    
    # 合并配置，项目配置优先级更高
    merged_config = default_config.copy()
    merged_config.update(project_task_config)
    return merged_config

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
    """执行任务"""
    db = SessionLocal()
    try:
        task = db.query(JobTask).filter(JobTask.id == task_id).first()
        if not task:
            raise ValueError(f"找不到任务ID {task_id}")
            
        if task.status != JobStatus.PENDING and task.status != JobStatus.PROCESSING:
            logging.info(f"任务 {task_id} 不处于等待或处理状态，当前状态: {task.status}")
            return
        
        # 更新任务状态为处理中
        task.status = JobStatus.PROCESSING
        db.commit()
            
        if task.task_type == JobTaskType.CONVERT_TO_MARKDOWN:
            convert_to_markdown_task(task.id, task.article_id)
        elif task.task_type == JobTaskType.PROCESS_WITH_LLM:
            process_with_llm_task(task.id, task.article_id)
        elif task.task_type == JobTaskType.PROCESS_AI_REVIEW:
            process_ai_review_task(task.id, task.article_id)
        elif task.task_type == JobTaskType.PROCESS_UPLOAD:
            if not task.params or 'file_path' not in task.params or 'project_id' not in task.params:
                raise ValueError(f"任务缺少必要参数，需要 file_path 和 project_id")
            process_upload_task(task.id, task.params['file_path'], task.params['project_id'])
        elif task.task_type == JobTaskType.EXTRACT_STRUCTURED_DATA:
            extract_structured_data_task(task.id, task.article_id)
        else:
            raise ValueError(f"未知的任务类型: {task.task_type}")
        
        # 更新job_tasks计数
        if task.job_id in job_tasks:
            job_tasks[task.job_id] = max(0, job_tasks[task.job_id] - 1)
        
        # 任务执行完成后，立即调度下一个任务
        task_queue.enqueue(schedule_job_tasks, args=(task.job_id,))
            
    except Exception as e:
        logging.error(f"执行任务 {task_id} 出错: {str(e)}")
        db.query(JobTask).filter(JobTask.id == task_id).update(
            {"status": JobStatus.FAILED, "logs": f"【错误】执行失败: {str(e)}"}
        )
        db.commit()
        
        # 更新job_tasks计数
        task = db.query(JobTask).filter(JobTask.id == task_id).first()
        if task and task.job_id in job_tasks:
            job_tasks[task.job_id] = max(0, job_tasks[task.job_id] - 1)
        
        # 即使任务失败，也调度下一个任务
        task_queue.enqueue(schedule_job_tasks, args=(db.query(JobTask).filter(JobTask.id == task_id).first().job_id,))
        raise
    finally:
        db.close()

def schedule_job_tasks(job_id: int):
    """调度Job的所有任务，确保Job内部的任务按严格顺序执行，但允许不同job并行执行"""
    db = SessionLocal()
    try:
        # 获取Job信息
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
        
        # 获取作业的并行度设置
        job_parallelism = job.parallelism or 1
        
        # 获取所有任务及其状态
        all_tasks = db.query(JobTask).filter(JobTask.job_id == job_id).all()
        
        # 检查当前是否有任务正在处理中
        processing_tasks = [t for t in all_tasks if t.status == JobStatus.PROCESSING]
        
        # 在单个作业内部仍然保持严格顺序执行的策略
        if processing_tasks:
            # 如果有任务正在处理中，等待它完成
            # 在当前作业内部，保持严格的任务顺序执行
            print(f"Job {job_id} - 已有任务正在处理中，等待完成")
            task_queue.enqueue_in(timedelta(seconds=15), schedule_job_tasks, args=(job_id,))
            return
        
        # 获取所有待处理的任务
        pending_tasks = [t for t in all_tasks if t.status == JobStatus.PENDING]
        if not pending_tasks:
            # 没有待处理的任务，检查任务是否全部完成
            if all(t.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] for t in all_tasks):
                # 所有任务都已经完成、失败或取消
                print(f"Job {job_id} - 所有任务已处理完成")
                # 更新Job状态
                update_job_status(db, job_id)
                # 从job_tasks字典中移除此job
                if job_id in job_tasks:
                    del job_tasks[job_id]
            else:
                # 可能有暂停的任务，15秒后再检查
                task_queue.enqueue_in(timedelta(seconds=15), schedule_job_tasks, args=(job_id,))
            return
        
        # 按照任务类型和创建时间排序，确保Markdown转换任务优先执行
        # 首先，找出所有Markdown转换任务
        markdown_tasks = [t for t in pending_tasks if t.task_type == JobTaskType.CONVERT_TO_MARKDOWN]
        other_tasks = [t for t in pending_tasks if t.task_type != JobTaskType.CONVERT_TO_MARKDOWN]
        
        # 排序后的任务列表
        sorted_tasks = markdown_tasks + other_tasks
        
        if sorted_tasks:
            # 每次只执行一个任务，严格按顺序
            next_task = sorted_tasks[0]
            
            # 将任务加入队列
            task_queue.enqueue(execute_task, args=(next_task.id,))
            print(f"Job {job_id} - 调度任务 {next_task.id} 类型: {next_task.task_type}")
            
            # 更新任务状态
            next_task.status = JobStatus.PROCESSING
            db.commit()
            
            # 记录此job当前正在执行的任务数
            job_tasks[job_id] = job_tasks.get(job_id, 0) + 1
        
        # 15秒后再次检查
        task_queue.enqueue_in(timedelta(seconds=15), schedule_job_tasks, args=(job_id,))
        
        # 检查Job状态统计
        completed_count = sum(1 for t in all_tasks if t.status == JobStatus.COMPLETED)
        pending_or_processing_count = sum(1 for t in all_tasks if t.status in [JobStatus.PENDING, JobStatus.PROCESSING])
        print(f"Job {job_id} - {completed_count} 已完成, {pending_or_processing_count} 待处理/处理中")
            
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
            raise Exception("Task not found")
            
        # 更新任务状态
        task.status = JobStatus.PROCESSING
        task.progress = 0
        task.logs = "【开始】开始将文章转换为Markdown格式...\n"
        db.commit()

        # 获取文章信息
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            error_msg = f"错误：找不到文章ID {article_id}"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)

        task.logs += f"【信息】正在处理文章: {article.name}，ID: {article.id}\n"
        db.commit()

        # 检查文章是否有附件
        if not article.attachments or len(article.attachments) == 0:
            error_msg = "错误：文章没有附件"
            task.logs += f"【错误】{error_msg}\n"
            task.status = JobStatus.FAILED
            db.commit()
            return
            
        # 找到活动的附件
        active_attachment = None
        for attachment in article.attachments:
            if attachment.get("is_active"):
                active_attachment = attachment
                break
                
        if not active_attachment:
            error_msg = "错误：未找到活动的附件"
            task.logs += f"【错误】{error_msg}\n"
            task.status = JobStatus.FAILED
            db.commit()
            return

        file_path = active_attachment.get("path")
        if not file_path:
            error_msg = "错误：附件中没有文件路径"
            task.logs += f"【错误】{error_msg}\n"
            task.status = JobStatus.FAILED
            db.commit()
            return

        task.logs += f"【信息】处理附件: {file_path}\n"
        db.commit()

        # 检查文件是否存在
        if not os.path.exists(file_path):
            error_msg = f"错误：找不到文件 {file_path}"
            task.logs += f"【错误】{error_msg}\n"
            task.status = JobStatus.FAILED
            db.commit()
            return

        # 检查任务状态
        if not check_job_task_status(db, task):
            task.logs += "【中止】任务已暂停或取消\n"
            db.commit()
            return

        # 检查文件类型
        file_name = os.path.basename(file_path)
        task.logs += f"【信息】文件名: {file_name}\n"
        db.commit()

        # 获取文件扩展名（小写）
        file_ext = os.path.splitext(file_name)[1].lower()
        task.logs += f"【信息】文件扩展名: {file_ext}\n"
        db.commit()

        # 更新任务进度
        task.progress = 20
        db.commit()

        try:
            # 根据文件类型转换文件
            task.logs += "【处理】开始转换文件为Markdown...\n"
            db.commit()
            
            markdown_text = convert_file_to_markdown(file_path)
            
            task.progress = 80
            task.logs += "【处理】文件转换完成，正在保存结果...\n"
            db.commit()
            
            # 检查任务状态
            if not check_job_task_status(db, task):
                task.logs += "【中止】任务已暂停或取消\n"
                db.commit()
                return
            
            # 保存转换后的Markdown文本
            # 检查是否已经有AI审阅报告
            ai_review = db.query(AIReviewReport).filter(
                AIReviewReport.article_id == article_id,
                AIReviewReport.job_id == task.job_id
            ).first()
            
            if not ai_review:
                task.logs += "【信息】创建新的AI审阅报告...\n"
                ai_review = AIReviewReport(
                    article_id=article_id,
                    job_id=task.job_id
                )
                db.add(ai_review)
                db.commit()
                db.refresh(ai_review)
            else:
                task.logs += "【信息】更新现有的AI审阅报告...\n"
                
            ai_review.processed_attachment_text = markdown_text
            
            # 更新文章的active_ai_review_report_id
            article.active_ai_review_report_id = ai_review.id
            db.commit()
            
            task.logs += f"【信息】已保存Markdown格式内容，字符长度: {len(markdown_text)}\n"
            db.commit()
            
            # 最后检查任务状态
            if not check_job_task_status(db, task):
                task.logs += "【中止】任务已暂停或取消\n"
                db.commit()
                return
            
            # 更新任务状态为完成
            task.status = JobStatus.COMPLETED
            task.progress = 100
            task.logs += "【完成】文档成功转换为Markdown格式！\n"
            db.commit()
            
            # 更新父Job的状态由schedule_job_tasks负责
        except Exception as e:
            task.status = JobStatus.FAILED
            task.logs += f"【错误】Markdown转换失败: {str(e)}\n"
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
            
        # 检查是否有相同job_id的Markdown转换任务已完成
        markdown_task = db.query(JobTask).filter(
            JobTask.job_id == task.job_id,
            JobTask.task_type == JobTaskType.CONVERT_TO_MARKDOWN,
            JobTask.article_id == article_id
        ).first()
        
        if not markdown_task:
            error_msg = "错误：找不到对应的Markdown转换任务"
            print(f"Task {task_id} error: {error_msg}")
            task.logs = f"【错误】{error_msg}\n"
            task.status = JobStatus.FAILED
            db.commit()
            return
            
        if markdown_task.status != JobStatus.COMPLETED:
            # 如果Markdown任务未完成，将当前任务重新设为等待状态，延迟执行
            if task.status != JobStatus.PENDING:
                task.status = JobStatus.PENDING
                task.logs = f"【等待】等待Markdown转换任务完成，当前状态: {markdown_task.status}\n"
                db.commit()
            print(f"Task {task_id} waiting for markdown task {markdown_task.id} to complete")
            return
            
        # 更新任务状态
        task.status = JobStatus.PROCESSING
        task.progress = 0
        task.logs = "【开始】开始处理文档内容生成AI审阅报告...\n"
        task.logs += f"【信息】Markdown转换任务 {markdown_task.id} 已完成，继续处理\n"
        db.commit()

        # 获取文章信息
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            error_msg = f"错误：找不到文章ID {article_id}"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)

        task.logs += f"【信息】正在处理文章: {article.name}，ID: {article.id}\n"
        db.commit()

        # 获取项目信息
        project = db.query(Project).filter(Project.id == article.project_id).first()
        if not project:
            error_msg = "错误：找不到项目信息"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)

        task.logs += f"【信息】项目名称: {project.name}，ID: {project.id}\n"
        db.commit()

        # 获取AI审阅报告
        ai_review = db.query(AIReviewReport).filter(
            AIReviewReport.article_id == article_id
        ).first()
        
        if not ai_review:
            error_msg = "错误：找不到AI审阅报告"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)
            
        # 检查是否已经有Markdown格式的文本
        if not ai_review.processed_attachment_text:
            error_msg = "错误：AI审阅报告中缺少处理后的文档内容"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)
            
        markdown_text = ai_review.processed_attachment_text
        
        task.logs += f"【信息】获取到Markdown格式内容，字符长度: {len(markdown_text)}\n"
        db.commit()
        
        # 检查任务状态
        if not check_job_task_status(db, task):
            task.logs += "【中止】任务已暂停或取消\n"
            db.commit()
            return
            
        # 获取任务特定的配置
        task_config = get_task_config('process_with_llm', project.config)
        
        # 从任务配置中获取模型
        model = task_config.get('model')
        if not model:
            model = get_default_model_for_task('process_with_llm')
            task.logs += f"【信息】使用默认模型: {model}\n"
        else:
            task.logs += f"【信息】使用配置指定模型: {model}\n"
        db.commit()
            
        # 检查模型是否在可用列表中
        available_models = get_available_models_for_task('process_with_llm')
        if available_models and model not in available_models:
            old_model = model
            model = available_models[0] if available_models else "deepseek/deepseek-coder"
            task.logs += f"【警告】指定模型 {old_model} 不可用，切换为: {model}\n"
            db.commit()
        
        task.logs += "【处理】开始调用大语言模型处理内容...\n"
        task.progress = 40
        db.commit()
        
        # 构建评审提示词
        system_prompt = """你是一位专业的文档审阅助手，需要对文档内容进行全面审阅并提供详细报告。
请按照以下结构返回你的审阅报告：

# 摘要
[简要总结文档的主要内容和目的，2-3句话]

# 文档结构评估
[分析文档的组织结构是否清晰、逻辑是否连贯，段落划分是否合理]

# 内容完整性
[评估文档内容是否完整，是否缺少重要信息]

# 语言表达
[评估文档的语言表达是否清晰、准确、专业]

# 专业性评估
[评估文档的专业水平，包括术语使用、论证方式等]

# 格式规范
[评估文档格式是否符合规范，包括标点、排版等]

# 具体问题清单
[列出文档中发现的具体问题，包括错误、不一致、不清晰的表述等]

# 改进建议
[提供具体的改进建议]

# 总体评分
[给出总体评分，1-10分]
"""

        user_prompt = f"""请对以下文档内容进行专业审阅：

{markdown_text}
"""
        
        try:
            # 调用AI模型生成审阅报告
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                **{k: v for k, v in task_config.items() if k != 'model'}  # 排除model字段，添加其他配置
            )
            
            ai_review_content = response.choices[0].message.content
            
            task.logs += "【信息】AI模型响应完成，保存审阅报告...\n"
            task.progress = 80
            db.commit()
            
            # 检查任务状态
            if not check_job_task_status(db, task):
                task.logs += "【中止】任务已暂停或取消\n"
                db.commit()
                return
                
            # 更新AI审阅报告内容
            ai_review.review_content = ai_review_content
            ai_review.source_data = ai_review_content
            
            # 更新文章的active_ai_review_report_id
            article.active_ai_review_report_id = ai_review.id
            
            db.commit()
            
            task.logs += f"【信息】审阅报告已保存，字符长度: {len(ai_review_content)}\n"
            db.commit()
            
            # 更新任务状态为完成
            task.status = JobStatus.COMPLETED
            task.progress = 100
            task.logs += "【完成】AI审阅报告生成成功！\n"
            db.commit()
            
            # 不再调用update_job_status，由schedule_job_tasks负责
            
        except Exception as e:
            task.status = JobStatus.FAILED
            task.logs += f"【错误】AI审阅失败: {str(e)}\n"
            db.commit()
            raise
            
    except Exception as e:
        print(f"Error processing task {task_id}: {str(e)}")
        if task:
            task.status = JobStatus.FAILED
            task.logs += f"【错误】处理失败: {str(e)}\n"
            db.commit()
        raise
    finally:
        db.close()

def process_ai_review_task(task_id: int, article_id: int):
    """处理AI审阅报告，生成最终的AI审阅结果"""
    db = SessionLocal()
    try:
        # 获取任务信息
        task = db.query(JobTask).filter(JobTask.id == task_id).first()
        if not task:
            raise Exception("Task not found")
            
        # 更新任务状态
        task.status = JobStatus.PROCESSING
        task.progress = 0
        task.logs = "【开始】开始处理AI审阅报告...\n"
        db.commit()

        # 获取文章信息
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            error_msg = f"错误：找不到文章ID {article_id}"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)

        task.logs += f"【信息】正在处理文章: {article.name}，ID: {article.id}\n"
        db.commit()

        # 获取项目信息
        project = db.query(Project).filter(Project.id == article.project_id).first()
        if not project:
            error_msg = "错误：找不到项目信息"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)

        task.logs += f"【信息】项目名称: {project.name}，ID: {project.id}\n"
        db.commit()
        
        # 获取AI审阅报告
        ai_review = db.query(AIReviewReport).filter(
            AIReviewReport.article_id == article_id,
            AIReviewReport.job_id == task.job_id
        ).first()
        
        if not ai_review:
            error_msg = "错误：找不到AI审阅报告"
            task.logs += f"【错误】{error_msg}\n"
            task.status = JobStatus.FAILED
            db.commit()
            return
            
        if not ai_review.source_data:
            error_msg = "错误：AI审阅报告中缺少源数据"
            task.logs += f"【错误】{error_msg}\n"
            task.status = JobStatus.FAILED
            db.commit()
            return
        
        # 检查任务状态
        if not check_job_task_status(db, task):
            task.logs += "【中止】任务已暂停或取消\n"
            db.commit()
            return
        
        # 处理AI审阅结果
        task.logs += "【处理】开始生成最终的AI审阅结果...\n"
        task.progress = 50
        db.commit()
        
        # 解析AI审阅结果，这里简单地将source_data保存为review_content
        ai_review.review_content = ai_review.source_data
        
        # 更新文章的active_ai_review_report_id
        article.active_ai_review_report_id = ai_review.id
        
        # 如果项目配置中有自动设置文章状态，则设置
        if project.config and project.config.get('auto_set_status'):
            article.status = "reviewed"
            task.logs += "【信息】已自动将文章状态设置为已审阅\n"
        
        db.commit()
        
        task.logs += "【信息】已保存AI审阅结果\n"
        db.commit()
        
        # 检查任务状态
        if not check_job_task_status(db, task):
            task.logs += "【中止】任务已暂停或取消\n"
            db.commit()
            return
        
        # 更新任务状态为完成
        task.status = JobStatus.COMPLETED
        task.progress = 100
        task.logs += "【完成】AI审阅报告处理成功！\n"
        db.commit()
        
        # 不再调用update_job_status，由schedule_job_tasks负责
        
    except Exception as e:
        if task:
            task.status = JobStatus.FAILED
            task.logs += f"【错误】处理失败: {str(e)}\n"
            db.commit()
        print(f"Error processing AI review task {task_id}: {str(e)}")
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
        task.logs = "【开始】开始处理上传文件任务...\n"
        db.commit()
        
        # 获取项目所有者ID
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            error_msg = f"错误：找不到项目ID {project_id}"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)
            
        task.logs += f"【信息】项目名称: {project.name}\n"
        db.commit()
            
        # 使用与上传相同的目录结构
        extract_dir = f"data/uploads/{project.owner_id}/{task.job_id}"
        os.makedirs(extract_dir, exist_ok=True)
        
        task.logs += f"【信息】创建提取目录: {extract_dir}\n"
        db.commit()
        
        # 检查任务状态
        if not check_job_task_status(db, task):
            task.logs += "【中止】任务已暂停或取消\n"
            db.commit()
            return

        # 检查是否为zip文件
        if file_path.endswith('.zip'):
            task.logs += "【信息】检测到ZIP文件，准备解压...\n"
            db.commit()
            # 解压zip文件
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            # 移动zip文件
            zip_filename = os.path.basename(file_path)
            os.rename(file_path, os.path.join(extract_dir, zip_filename))
            task.logs += f"【信息】ZIP文件成功解压到 {extract_dir}\n"
            db.commit()
        else:
            # 如果不是zip文件,直接移动到extract_dir
            filename = os.path.basename(file_path)
            os.rename(file_path, os.path.join(extract_dir, filename))
            task.logs += f"【信息】文件 {filename} 已移动到 {extract_dir}\n"
            db.commit()

        # 获取所有可接受文件
        all_files = []
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                if is_allowed_file(file):
                    all_files.append((root, file))
        
        print(f"Found {len(all_files)} files to process")
        total_files = len(all_files)
        
        task.logs += f"【信息】发现 {total_files} 个可处理的文件\n"
        if total_files == 0:
            task.logs += "【警告】未找到可处理的文件，请检查上传内容是否符合要求\n"
        db.commit()
        
        for index, (root, file) in enumerate(all_files):
            print(f"Processing file {index + 1}/{total_files}: {file}")
            task.logs += f"【处理】({index + 1}/{total_files}) 开始处理文件: {file}\n"
            db.commit()
            
            # 检查任务状态
            if not check_job_task_status(db, task):
                task.logs += "【中止】任务已暂停或取消\n"
                db.commit()
                return
                
            # 获取project对应的article_type_id
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                error_msg = f"错误：找不到项目ID {project_id}"
                task.logs += f"【错误】{error_msg}\n"
                raise Exception(error_msg)

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
            db.refresh(db_article)
            
            task.logs += f"【信息】创建文档记录成功，文档ID: {db_article.id}\n"
            db.commit()
            
            # 如果项目设置了自动批阅，则为新文章创建批阅任务
            if project.auto_approve:
                task.logs += "【信息】项目已开启自动批阅，创建自动批阅任务...\n"
                db.commit()
                
                # 创建一个新的Job
                review_job = Job(
                    project_id=project_id,
                    name=f"Auto Review for {file}",
                    status=JobStatus.PENDING,
                    progress=0,
                    logs="",
                    parallelism=1
                )
                db.add(review_job)
                db.commit()
                db.refresh(review_job)
                
                # 创建convert_to_markdown任务
                convert_task = JobTask(
                    job_id=review_job.id,
                    task_type=JobTaskType.CONVERT_TO_MARKDOWN,
                    status=JobStatus.PENDING,
                    progress=0,
                    logs="",
                    article_id=db_article.id
                )
                db.add(convert_task)
                
                # 创建process_with_llm任务
                llm_task = JobTask(
                    job_id=review_job.id,
                    task_type=JobTaskType.PROCESS_WITH_LLM,
                    status=JobStatus.PENDING,
                    progress=0,
                    logs="",
                    article_id=db_article.id
                )
                db.add(llm_task)
                db.commit()
                
                # 调度任务
                task_queue.enqueue(
                    schedule_job_tasks,
                    args=(review_job.id,)
                )
                
                task.logs += f"【信息】自动批阅任务已创建，任务ID: {review_job.id}\n"
                db.commit()
                
                print(f"Auto review job {review_job.id} created for article {db_article.id}")
            
            # 更新进度
            progress = int((index + 1) / total_files * 100)
            task.progress = progress
            task.logs += f"【进度】处理进度更新为 {progress}%\n"
            db.commit()
        
        # 最后检查一次任务状态
        if not check_job_task_status(db, task):
            task.logs += "【中止】任务已暂停或取消\n"
            db.commit()
            return
            
        print(f"Task {task_id} completed successfully")
        # 更新任务状态为完成
        task.status = JobStatus.COMPLETED
        task.progress = 100
        task.logs += "【完成】所有文件处理完成！\n"
        db.commit()
        
        # 不再调用update_job_status，由schedule_job_tasks负责
        
    except Exception as e:
        print(f"Error occurred in task {task_id}: {str(e)}")
        # 更新任务状态为失败
        error_msg = f"Error: File processing failed: {str(e)}"
        task.status = JobStatus.FAILED
        task.logs += f"【错误】文件处理失败: {str(e)}\n"
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

# 获取模型详细信息
def get_model_details(model_id):
    """获取模型的详细信息"""
    models = MODEL_CONFIG.get("models", [])
    for model in models:
        if model.get("id") == model_id:
            return model
    return {"id": model_id, "name": model_id, "description": ""}

# 获取所有可用模型
def get_all_available_models():
    """获取所有配置的模型列表"""
    return MODEL_CONFIG.get("models", [])

def extract_structured_data_task(task_id: int, article_id: int):
    """从AI审阅的结果中提取结构化数据"""
    db = SessionLocal()
    try:
        task = db.query(JobTask).filter(JobTask.id == task_id).first()
        if not task:
            raise Exception("Task not found")
            
        # 更新任务状态
        task.status = JobStatus.PROCESSING
        task.progress = 0
        task.logs = "【开始】开始从AI审阅结果中提取结构化数据...\n"
        db.commit()

        # 获取文章和AI审阅报告
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            error_msg = f"错误：找不到文章ID {article_id}"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)

        task.logs += f"【信息】正在处理文章: {article.name}，ID: {article.id}\n"
        db.commit()

        project = db.query(Project).filter(Project.id == article.project_id).first()
        if not project:
            error_msg = "错误：找不到项目信息"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)

        task.logs += f"【信息】项目名称: {project.name}，ID: {project.id}\n"
        db.commit()

        # 使用article.active_ai_review_report_id查找活跃的review
        ai_review = None
        if article.active_ai_review_report_id:
            ai_review = db.query(AIReviewReport).filter(
                AIReviewReport.id == article.active_ai_review_report_id
            ).first()
            task.logs += f"【信息】使用文章指定的活跃AI审阅报告，ID: {article.active_ai_review_report_id}\n"
        
        # 如果没有找到活跃的review，尝试查找job关联的review
        if not ai_review:
            ai_review = db.query(AIReviewReport).filter(
                AIReviewReport.article_id == article_id,
                AIReviewReport.job_id == task.job_id
            ).first()
            if ai_review:
                task.logs += f"【信息】使用当前job关联的AI审阅报告，ID: {ai_review.id}\n"
        
        # 如果仍未找到，查找最新的review
        if not ai_review:
            ai_review = db.query(AIReviewReport).filter(
                AIReviewReport.article_id == article_id
            ).order_by(AIReviewReport.created_at.desc()).first()
            if ai_review:
                task.logs += f"【信息】使用最新的AI审阅报告，ID: {ai_review.id}\n"
        
        if not ai_review:
            error_msg = "错误：找不到AI审阅报告"
            task.logs += f"【错误】{error_msg}\n"
            task.status = JobStatus.FAILED
            db.commit()
            return
            
        # 获取审阅内容
        review_content = ai_review.review_content
        if not review_content:
            error_msg = "错误：AI审阅报告中缺少内容"
            task.logs += f"【错误】{error_msg}\n"
            task.status = JobStatus.FAILED
            db.commit()
            return
            
        # 获取原始内容作为上下文
        source_data = ai_review.processed_attachment_text or ""
        
        # 检查任务状态
        if not check_job_task_status(db, task):
            task.logs += "【中止】任务已暂停或取消\n"
            db.commit()
            return
            
        # 构建提取结构化数据的prompt
        extraction_prompt = """请从以下审阅报告中提取结构化数据，以YAML格式返回：

1. 摘要
2. 结构评分 (1-10)
3. 内容完整性评分 (1-10)
4. 语言表达评分 (1-10)
5. 专业性评分 (1-10)
6. 格式规范评分 (1-10)
7. 总体评分 (1-10)
8. 问题清单 (列表)
9. 改进建议 (列表)

使用以下YAML格式：

```yaml
summary: 简短摘要
structure_score: 7
completeness_score: 8
language_score: 9
professionalism_score: 7
format_score: 8
overall_score: 8
issues:
  - 第一个问题
  - 第二个问题
suggestions:
  - 第一个建议
  - 第二个建议
```

审阅报告:
"""

        try:
            # 获取任务特定的配置
            task_config = get_task_config('extract_structured_data', project.config)
            
            # 从任务配置中获取模型
            model = task_config.get('model')
            if not model:
                model = get_default_model_for_task('extract_structured_data')
                task.logs += f"【信息】使用默认模型: {model}\n"
            else:
                task.logs += f"【信息】使用配置指定模型: {model}\n"
            db.commit()
                
            # 检查模型是否在可用列表中
            available_models = get_available_models_for_task('extract_structured_data')
            if available_models and model not in available_models:
                old_model = model
                model = available_models[0] if available_models else "deepseek/deepseek-reason"
                task.logs += f"【警告】指定模型 {old_model} 不可用，切换为: {model}\n"
                db.commit()
            
            task.logs += "【处理】开始调用大语言模型提取结构化数据...\n"
            task.progress = 40
            db.commit()
                
            # 使用AI模型提取结构化数据
            prompt = f"{extraction_prompt}\n\n{review_content}"
            
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个数据提取助手，擅长从文本中提取结构化数据。请根据给定的格式提取数据，并以YAML格式返回。"},
                    {"role": "user", "content": prompt}
                ],
                **{k: v for k, v in task_config.items() if k != 'model'}  # 排除model字段，添加其他配置
            )
            
            yaml_content = response.choices[0].message.content
            
            task.logs += "【信息】模型响应完成，准备解析结构化数据...\n"
            task.progress = 70
            db.commit()
            
            # 从YAML内容中提取```yaml和```之间的内容
            import re
            yaml_pattern = r"```(?:yaml)?\n(.*?)```"
            match = re.search(yaml_pattern, yaml_content, re.DOTALL)
            if match:
                yaml_content = match.group(1)
            
            # 保存结构化数据
            ai_review.structured_data = yaml_content
            db.commit()
            
            task.logs += "【信息】结构化数据已保存\n"
            db.commit()
            
            # 检查任务状态
            if not check_job_task_status(db, task):
                task.logs += "【中止】任务已暂停或取消\n"
                db.commit()
                return
            
            # 更新任务状态为完成
            task.status = JobStatus.COMPLETED
            task.progress = 100
            task.logs += "【完成】结构化数据提取成功！\n"
            db.commit()
            
            # 不再调用update_job_status，由schedule_job_tasks负责
            
        except Exception as e:
            task.status = JobStatus.FAILED
            task.logs += f"【错误】结构化数据提取失败: {str(e)}\n"
            db.commit()
            raise
            
    except Exception as e:
        print(f"Error extracting structured data: {str(e)}")
        if task:
            task.status = JobStatus.FAILED
            task.logs += f"【错误】处理失败: {str(e)}\n"
            db.commit()
        raise
    finally:
        db.close()

def extract_structured_data(article_id: int, job_id: int):
    """创建提取结构化数据任务"""
    db = SessionLocal()
    try:
        # 创建任务
        job_task = JobTask(
            job_id=job_id,
            task_type=JobTaskType.EXTRACT_STRUCTURED_DATA,
            status=JobStatus.PENDING,
            article_id=article_id
        )
        db.add(job_task)
        db.commit()
        
        # 立即执行任务
        extract_structured_data_task(job_task.id, article_id)
        
    except Exception as e:
        import traceback
        print(f"Error creating extract_structured_data task: {str(e)}\n{traceback.format_exc()}")
        raise
    finally:
        db.close()
