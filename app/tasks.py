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
task_queue = Queue(connection=redis_conn)

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
            
        if task.status != JobStatus.PENDING:
            logging.info(f"任务 {task_id} 不处于等待状态，当前状态: {task.status}")
            return
            
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
            
    except Exception as e:
        logging.error(f"执行任务 {task_id} 出错: {str(e)}")
        db.query(JobTask).filter(JobTask.id == task_id).update(
            {"status": JobStatus.FAILED, "logs": f"【错误】执行失败: {str(e)}"}
        )
        db.commit()
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
        
        # 优先选择Markdown转换任务
        markdown_tasks = [task for task in pending_tasks if task.task_type == JobTaskType.CONVERT_TO_MARKDOWN]
        other_tasks = [task for task in pending_tasks if task.task_type != JobTaskType.CONVERT_TO_MARKDOWN]
        
        # 重新排序任务列表，确保Markdown转换任务优先执行
        sorted_tasks = markdown_tasks + other_tasks
        
        # 启动任务
        scheduled_count = 0
        for i in range(min(available_slots, len(sorted_tasks))):
            task = sorted_tasks[i]
            # 将任务加入队列
            task_queue.enqueue(execute_task, args=(task.id,))
            scheduled_count += 1
        
        # 检查Job是否完成
        all_tasks = db.query(JobTask).filter(JobTask.job_id == job_id).all()
        completed_count = sum(1 for t in all_tasks if t.status == JobStatus.COMPLETED)
        pending_or_processing_count = sum(1 for t in all_tasks if t.status in [JobStatus.PENDING, JobStatus.PROCESSING])
        
        # 如果还有待处理或处理中的任务，15秒后再次检查
        if pending_or_processing_count > 0:
            print(f"Job {job_id} - {completed_count} completed, {pending_or_processing_count} pending/processing")
            task_queue.enqueue_in(timedelta(seconds=15), schedule_job_tasks, args=(job_id,))
            
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
        task.logs = "【开始】开始转换文档为Markdown格式...\n"
        db.commit()
        
        # 获取文章信息
        article = db.query(Article).filter(Article.id == article_id).first()
        if not article:
            error_msg = f"错误：找不到文章ID {article_id}"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)
        
        task.logs += f"【信息】正在处理文章: {article.name}，ID: {article.id}\n"
        db.commit()
        
        # 处理激活的附件
        active_attachment = None
        for attachment in article.attachments:
            if attachment.get("is_active"):
                active_attachment = attachment
                break
                
        if not active_attachment:
            error_msg = "错误：未找到激活的附件"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)
        
        task.logs += f"【信息】找到激活的附件: {active_attachment['filename']}\n"
        db.commit()
        
        # 检查任务状态
        if not check_job_task_status(db, task):
            task.logs += "【中止】任务已暂停或取消\n"
            db.commit()
            return
        
        # 转换文件
        file_path = active_attachment["path"]
        task.logs += f"【处理】开始转换文件: {file_path}\n"
        db.commit()
        
        # 更新进度
        task.progress = 20
        task.logs += "【进度】文件解析中... 20%\n"
        db.commit()
        
        markdown_text = convert_file_to_markdown(file_path)
        
        # 更新进度
        task.progress = 60
        task.logs += "【进度】文件转换完成，准备更新数据库... 60%\n"
        db.commit()
        
        # 创建或更新AIReviewReport
        ai_review = db.query(AIReviewReport).filter(
            AIReviewReport.article_id == article_id,
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
        
        # 更新父Job的状态
        update_job_status(db, task.job_id)
        
    except Exception as e:
        error_msg = f"Error: Markdown conversion failed: {str(e)}"
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

        if not ai_review or not ai_review.processed_attachment_text:
            error_msg = "错误：未找到处理过的文本内容，请先执行转换为Markdown的任务"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)
        
        # 检查任务状态
        if not check_job_task_status(db, task):
            task.logs += "【中止】任务已暂停或取消\n"
            db.commit()
            return
            
        processed_text = ai_review.processed_attachment_text
        text_length = len(processed_text)
        task.logs += f"【信息】获取到处理过的文本内容，长度: {text_length} 字符\n"
        db.commit()
        
        # 使用LLM处理文章内容
        try:
            # 从config中获取提示词
            prompt = project.config.get('prompt', '')
            
            # 如果项目配置中没有prompt，则从article_type中获取
            if not prompt and hasattr(project, 'article_type') and project.article_type:
                article_type = project.article_type
                if article_type and article_type.config:
                    prompt = article_type.config.get('prompt', '')
                    if prompt:
                        task.logs += f"【信息】从文章类型 '{article_type.name}' 获取提示词\n"
                
            # 如果仍然没有prompt，使用默认提示词
            if not prompt:
                default_prompt = "请分析以下文档内容，给出主要观点和建议。"
                prompt = default_prompt
                task.logs += f"【警告】未找到配置的提示词，使用默认提示词\n"
            
            task.logs += f"【信息】使用的提示词长度: {len(prompt)} 字符\n"
            db.commit()

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
                model = available_models[0] if available_models else "deepseek/deepseek-chat"
                task.logs += f"【警告】指定模型 {old_model} 不可用，切换为: {model}\n"
                db.commit()

            task.logs += "【处理】开始调用大语言模型...\n"
            task.progress = 10
            db.commit()

            # 使用litellm的流式API，包含任务特定的配置
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": processed_text}
                ],
                stream=True,  # 启用流式输出
                **{k: v for k, v in task_config.items() if k != 'model'}  # 排除model字段，添加其他配置
            )

            # 初始化累积的响应文本
            accumulated_response = ""
            last_progress_update = 0
            
            task.logs += "【进度】模型开始响应...\n"
            db.commit()
            
            # 处理流式响应
            for chunk in response:
                # 检查任务状态
                if not check_job_task_status(db, task):
                    task.logs += "【中止】任务已暂停或取消\n"
                    db.commit()
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
                    progress = min(95, int((current_length / 1000) * 5) + 10)  # 假设平均响应长度为1000字符，起始进度为10%
                    
                    # 仅在进度变化超过5%时更新日志，避免日志过多
                    if progress >= last_progress_update + 5:
                        task.logs += f"【进度】模型响应中... {progress}%\n"
                        last_progress_update = progress
                        
                    task.progress = progress
                    db.commit()

            # 完成处理
            task.progress = 100
            task.status = JobStatus.COMPLETED
            ai_review.status = "completed"
            
            task.logs += f"【信息】模型响应完成，生成内容长度: {len(accumulated_response)} 字符\n"
            task.logs += "【完成】AI审阅报告生成成功！\n"
            db.commit()
            
            # 更新父Job的状态
            update_job_status(db, task.job_id)
            
        except Exception as e:
            task.status = JobStatus.FAILED
            task.logs += f"【错误】LLM处理过程中出错: {str(e)}\n"
            ai_review.status = "failed"
            raise

        db.commit()
        return task

    except Exception as e:
        task.status = JobStatus.FAILED
        task.logs += f"【错误】任务执行失败: {str(e)}\n"
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
            # 获取任务特定的配置
            task_config = get_task_config('ai_review', project.config)
            
            # 从任务配置中获取模型
            model = task_config.get('model')
            if not model:
                model = get_default_model_for_task('ai_review')
                
            # 检查模型是否在可用列表中
            available_models = get_available_models_for_task('ai_review')
            if available_models and model not in available_models:
                model = available_models[0] if available_models else "deepseek/deepseek-reason"
                
            # 使用litellm的流式API，包含任务特定的配置
            response = completion(
                model=model,
                messages=[
                    {"role": "system", "content": full_prompt},
                    {"role": "user", "content": processed_text}
                ],
                stream=True,
                **{k: v for k, v in task_config.items() if k != 'model'}  # 排除model字段，添加其他配置
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
        
        # 更新父Job的状态
        update_job_status(db, task.job_id)
        
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
        
        if not ai_review:
            # 如果没有活跃的review，尝试获取最新的一个
            task.logs += "【信息】未找到活跃的AI审阅报告，尝试获取最新的报告...\n"
            ai_review = db.query(AIReviewReport).filter(
                AIReviewReport.article_id == article_id
            ).order_by(AIReviewReport.created_at.desc()).first()
            
            # 如果找到了review，更新article的active_ai_review_report_id
            if ai_review:
                article.active_ai_review_report_id = ai_review.id
                task.logs += f"【信息】找到最新的AI审阅报告，ID: {ai_review.id}，已设置为活跃\n"
                db.commit()

        if not ai_review or not ai_review.source_data:
            error_msg = "错误：未找到源数据，请先执行LLM处理任务"
            task.logs += f"【错误】{error_msg}\n"
            raise Exception(error_msg)
        
        # 检查任务状态
        if not check_job_task_status(db, task):
            task.logs += "【中止】任务已暂停或取消\n"
            db.commit()
            return
            
        source_data = ai_review.source_data
        task.logs += f"【信息】获取到源数据，长度: {len(source_data)} 字符\n"
        db.commit()
        
        # 处理配置信息
        config = project.config or {}
        extraction_prompt = config.get('extraction_prompt', '请根据以下分析报告内容数据提取，并按照要求输出结果：\n输出示例:\nroot:\n  score: 80\n  result: 优秀')
        
        task.logs += "【信息】已获取数据提取提示词\n"
        task.progress = 20
        db.commit()
        
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
            prompt = f"{extraction_prompt}\n\n{source_data}"
            
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
            task.progress = 60
            db.commit()
            
            # 尝试解析YAML内容
            try:
                # 移除可能存在的代码块标记
                yaml_content = yaml_content.replace('```yaml', '').replace('```', '').strip()
                
                task.logs += "【处理】解析YAML数据...\n"
                task.progress = 80
                db.commit()
                
                # 解析YAML为Python字典
                import yaml
                structured_data = yaml.safe_load(yaml_content)
                
                # 保存结构化数据
                ai_review.structured_data = structured_data
                db.commit()
                
                task.logs += "【信息】结构化数据解析成功并已保存\n"
                task.status = JobStatus.COMPLETED
                task.progress = 100
                task.logs += "【完成】成功从AI审阅结果中提取结构化数据！\n"
                db.commit()
                
                # 更新父Job的状态
                update_job_status(db, task.job_id)
                return
                
            except Exception as e:
                error_msg = f"解析YAML失败: {str(e)}"
                task.logs += f"【错误】{error_msg}\n"
                task.logs += f"【详情】响应内容: {yaml_content}\n"
                task.status = JobStatus.FAILED
                db.commit()
                return
            
        except Exception as e:
            import traceback
            error_msg = f"错误: {str(e)}"
            task.logs += f"【错误】{error_msg}\n"
            task.logs += f"【详情】{traceback.format_exc()}\n"
            task.status = JobStatus.FAILED
            db.commit()
            raise
        
    except Exception as e:
        import traceback
        if task:
            error_msg = f"错误: {str(e)}"
            task.logs += f"【错误】{error_msg}\n"
            task.logs += f"【详情】{traceback.format_exc()}\n"
            task.status = JobStatus.FAILED
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
