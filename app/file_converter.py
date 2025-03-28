import os
import sys
import platform
from docx import Document
from pypdf import PdfReader
from PIL import Image
import pytesseract
from pathlib import Path
import base64
import json
from typing import Dict, List, Tuple, Optional
import time
import signal
from timeout_decorator import timeout, TimeoutError
import threading

# 全局超时处理设置
GLOBAL_TIMEOUT = 60  # 全局操作超时时间（秒）

# 检测操作系统类型
IS_MACOS = platform.system() == 'Darwin'

# 超时处理函数
def timeout_handler(signum, frame):
    raise TimeoutError("操作超时")

# 替代超时处理方法（适用于不支持SIGALRM的平台，如Windows和某些macOS版本）
def with_timeout(timeout_seconds, func, *args, **kwargs):
    """使用线程实现超时处理"""
    result = [None]
    exception = [None]
    completed = [False]
    
    def worker():
        try:
            result[0] = func(*args, **kwargs)
            completed[0] = True
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=worker)
    thread.daemon = True
    thread.start()
    thread.join(timeout_seconds)
    
    if not completed[0]:
        raise TimeoutError(f"操作超时（{timeout_seconds}秒）")
    if exception[0]:
        raise exception[0]
    return result[0]

# 尝试导入Mistral相关包
try:
    from mistralai import Mistral
    from mistralai import DocumentURLChunk
    from mistralai.models import OCRResponse
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False

# 尝试导入图像描述相关包
try:
    from litellm import completion
    IMAGE_DESCRIPTION_AVAILABLE = True
except ImportError:
    IMAGE_DESCRIPTION_AVAILABLE = False

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

def convert_file_to_markdown(file_path: str, conversion_type: str = "simple", config: Dict = None) -> str:
    """将文件转换为Markdown格式
    
    Args:
        file_path: 要转换的文件路径
        conversion_type: 转换类型，可选 "simple" 或 "advanced"
        config: 高级转换的配置参数
        
    Returns:
        转换后的Markdown文本
    """
    if conversion_type == "advanced" and file_path.lower().endswith('.pdf'):
        try:
            converter = AdvancedMarkdownConverter(config)
            return converter.convert_pdf(file_path)
        except Exception as e:
            print(f"高级转换失败: {str(e)}，回退到简单转换")
            # 如果高级转换失败，回退到简单转换
            conversion_type = "simple"
    
    # 简单转换
    if not is_allowed_file(file_path):
        raise ValueError(f"Unsupported file type: {file_path}")
        
    file_ext = os.path.splitext(file_path)[1].lower()
    
    # 根据文件类型处理
    if file_ext in ['.txt', '.md']:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    elif file_ext == '.docx':
        return extract_text_from_docx(file_path)
    elif file_ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_ext in ALLOWED_IMAGE_EXTENSIONS:
        image_text = extract_text_from_image(file_path)
        if image_text:
            return f"# Image Content\n\n{image_text}"
    
    return ""


class AdvancedMarkdownConverter:
    """支持更复杂格式转换的实现
    
    使用Mistral的OCR API处理PDF文件，保留格式，并添加图片描述
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """初始化转换器
        
        Args:
            config: 配置字典，包含API密钥等
        """
        self.config = config or {}
        self.api_key = os.environ.get("MISTRAL_API_KEY")
        self.image_model = self.config.get("image_description_model", "lm_studio/qwen2.5-vl-7b-instruct")
        self.enable_image_description = self.config.get("enable_image_description", True)
        # 添加日志记录功能
        self.logger = self.config.get("logger", lambda msg: print(msg))
        # 添加临时文件目录列表
        self.temp_dirs = []
        
        if not MISTRAL_AVAILABLE:
            raise ImportError("高级转换需要安装mistralai包: pip install mistralai")
            
        if not self.api_key:
            raise ValueError("高级转换需要提供Mistral API密钥，可以通过环境变量MISTRAL_API_KEY设置或在项目配置中提供")
    
    def __del__(self):
        """清理临时文件"""
        self.cleanup()
    
    def cleanup(self):
        """清理所有临时文件"""
        for temp_dir in self.temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    import shutil
                    shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"清理临时目录失败: {str(e)}")
    
    def replace_images_in_markdown(self, markdown_str: str, images_dict: Dict[str, str]) -> str:
        """替换Markdown中的图片路径
        
        Args:
            markdown_str: Markdown文本
            images_dict: 图片ID到路径的映射
            
        Returns:
            替换后的Markdown文本
        """
        for img_name, img_path in images_dict.items():
            markdown_str = markdown_str.replace(f"![{img_name}]({img_name})", f"![{img_name}]({img_path})")
        return markdown_str
    
    def save_ocr_results(self, ocr_response: OCRResponse, output_dir: str) -> Tuple[str, Dict[str, str]]:
        """保存OCR结果
        
        Args:
            ocr_response: Mistral OCR响应
            output_dir: 输出目录
            
        Returns:
            包含完整Markdown内容的文件路径以及图片路径字典
        """
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        images_dir = os.path.join(output_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        
        # 记录临时目录
        self.temp_dirs.append(output_dir)
        
        all_markdowns = []
        all_images = {}
        
        for page in ocr_response.pages:
            # 保存图片
            page_images = {}
            for img in page.images:
                img_data = base64.b64decode(img.image_base64.split(',')[1])
                img_path = os.path.join(images_dir, f"{img.id}.png")
                with open(img_path, 'wb') as f:
                    f.write(img_data)
                
                rel_img_path = f"images/{img.id}.png"
                page_images[img.id] = rel_img_path
                all_images[img.id] = {
                    "path": img_path,
                    "rel_path": rel_img_path
                }
            
            # 处理markdown内容
            page_markdown = self.replace_images_in_markdown(page.markdown, {k: v for k, v in page_images.items()})
            all_markdowns.append(page_markdown)
        
        # 保存完整markdown
        complete_md_path = os.path.join(output_dir, "complete.md")
        with open(complete_md_path, 'w', encoding='utf-8') as f:
            f.write("\n\n".join(all_markdowns))
        
        return complete_md_path, all_images
    
    def _generate_single_image_description(self, img_path: str, model_params: Dict) -> str:
        """生成单张图片的描述
        
        Args:
            img_path: 图片路径
            model_params: 模型参数
            
        Returns:
            图片描述文本
        """
        # 使用自定义超时处理代替装饰器，更加可靠
        with open(img_path, "rb") as img_file:
            base64_image = base64.b64encode(img_file.read()).decode("utf-8")
        
        # 根据平台选择不同的超时处理方式
        if IS_MACOS:
            # macOS可能不支持信号处理或在某些环境中有限制，使用线程超时
            try:
                def make_api_call():
                    response = completion(
                        model=self.image_model,
                        messages=[
                            {"role": "system", "content": "你是一个图像描述助手。描述图像内容，详细且简洁。"},
                            {"role": "user", "content": [
                                {"type": "text", "text": "请描述这张图片的内容，提供清晰、准确的描述。"},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                            ]}
                        ],
                        **model_params
                    )
                    return response.choices[0].message.content
                
                return with_timeout(30, make_api_call)
            except Exception as e:
                raise Exception(f"图片描述API调用失败: {str(e)}")
        else:
            # 在支持信号的平台上使用SIGALRM
            original_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(30)  # 设置30秒超时
            
            try:
                response = completion(
                    model=self.image_model,
                    messages=[
                        {"role": "system", "content": "你是一个图像描述助手。描述图像内容，详细且简洁。"},
                        {"role": "user", "content": [
                            {"type": "text", "text": "请描述这张图片的内容，提供清晰、准确的描述。"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]}
                    ],
                    **model_params
                )
                
                # 成功后取消超时
                signal.alarm(0)
                signal.signal(signal.SIGALRM, original_handler)
                
                return response.choices[0].message.content
            except Exception as e:
                # 确保取消超时设置
                try:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, original_handler)
                except:
                    pass
                # 显式抛出异常以便被外层捕获
                raise Exception(f"图片描述API调用失败: {str(e)}")

    def generate_image_descriptions(self, images: Dict[str, Dict]) -> Dict[str, str]:
        """生成图片描述
        
        Args:
            images: 图片ID到信息的映射
            
        Returns:
            图片ID到描述的映射
        """
        if not IMAGE_DESCRIPTION_AVAILABLE or not self.enable_image_description:
            return {}
        
        descriptions = {}
        total_images = len(images)
        self.logger(f"开始处理 {total_images} 张图片的描述")
        
        # 检查是否使用 lm_studio 模型，如果是则添加 base_url 参数
        model_params = {}
        if self.image_model.startswith("lm_studio"):
            model_params["base_url"] = "http://127.0.0.1:1234/v1"
        
        for idx, (img_id, img_info) in enumerate(images.items(), 1):
            # 重试机制
            max_retries = 3
            retry_delay = 5
            last_error = None
            
            self.logger(f"正在处理第 {idx}/{total_images} 张图片 (ID: {img_id})")
            img_path = img_info["path"]
            
            # 设置单个图片处理的安全超时，确保即使内部处理函数失败也能继续
            overall_timeout = threading.Timer(60, lambda: self.logger(f"警告：图片 {img_id} 处理超时60秒，强制跳过"))
            overall_timeout.start()
            
            try:
                for retry in range(max_retries):
                    try:
                        self.logger(f"使用模型 {self.image_model} 生成图片描述 (尝试 {retry + 1}/{max_retries})")
                        desc_text = self._generate_single_image_description(img_path, model_params)
                        descriptions[img_id] = desc_text
                        self.logger(f"图片 {img_id} 描述生成完成")
                        # 成功生成描述，跳出重试循环
                        break
                    except TimeoutError:
                        last_error = "请求超时"
                        self.logger(f"图片 {img_id} 描述生成超时，{retry_delay}秒后重试")
                        if retry < max_retries - 1:
                            time.sleep(retry_delay)
                    except Exception as e:
                        last_error = str(e)
                        self.logger(f"图片 {img_id} 描述生成失败: {last_error}，{retry_delay}秒后重试")
                        if retry < max_retries - 1:
                            time.sleep(retry_delay)
                
                # 如果所有重试都失败，记录最终错误并继续下一张图片
                if img_id not in descriptions:
                    error_msg = f"在{max_retries}次尝试后仍然失败：{last_error}"
                    descriptions[img_id] = f"[图片描述失败: {error_msg}]"
                    self.logger(f"图片 {img_id} 描述生成最终失败: {error_msg}")
            except Exception as e:
                self.logger(f"图片 {img_id} 处理过程中发生严重错误: {str(e)}，跳过此图片")
                descriptions[img_id] = f"[图片处理错误: {str(e)}]"
            finally:
                # 取消超时定时器，确保不会触发
                if overall_timeout.is_alive():
                    overall_timeout.cancel()
        
        self.logger(f"所有 {total_images} 张图片描述处理完成")
        return descriptions
    
    def create_image_description_markdown(self, descriptions: Dict[str, str], output_dir: str) -> str:
        """创建图片描述Markdown文件
        
        Args:
            descriptions: 图片ID到描述的映射
            output_dir: 输出目录
            
        Returns:
            描述Markdown文件的路径
        """
        desc_md_path = os.path.join(output_dir, "image_description.md")
        
        with open(desc_md_path, 'w', encoding='utf-8') as f:
            f.write("# 图片描述\n\n")
            
            for img_id, description in descriptions.items():
                f.write(f"## 图片 {img_id}\n\n")
                f.write(f"![{img_id}](images/{img_id}.png)\n\n")
                f.write(f"{description}\n\n")
        
        return desc_md_path
    
    def create_final_markdown(self, complete_md_path: str, desc_md_path: str, output_dir: str) -> str:
        """创建最终Markdown文件
        
        Args:
            complete_md_path: 完整Markdown文件路径
            desc_md_path: 描述Markdown文件路径
            output_dir: 输出目录
            
        Returns:
            最终Markdown文件的内容
        """
        result_md_path = os.path.join(output_dir, "result.md")
        
        # 读取完整Markdown
        with open(complete_md_path, 'r', encoding='utf-8') as f:
            complete_content = f.read()
        
        # 如果存在描述Markdown且启用了图片描述，则添加
        final_content = complete_content
        if os.path.exists(desc_md_path) and self.enable_image_description:
            # 读取描述Markdown
            with open(desc_md_path, 'r', encoding='utf-8') as f:
                desc_content = f.read()
            
            # 合并内容
            final_content = f"{complete_content}\n\n#以下图片描述信息为系统生成\n{desc_content}"
        
        # 保存最终文件
        with open(result_md_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        return final_content
    
    def convert_pdf(self, pdf_path: str) -> str:
        """转换PDF文件为高级Markdown
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            转换后的Markdown文本
        """
        if not self.api_key:
            raise ValueError("需要提供Mistral API密钥")
        
        # 初始化客户端
        self.logger("初始化Mistral客户端")
        client = Mistral(api_key=self.api_key)
        
        # 确认PDF文件存在
        pdf_file = Path(pdf_path)
        if not pdf_file.is_file():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        # 创建输出目录
        output_dir = os.path.join(os.path.dirname(pdf_path), "ocr_results")
        self.logger(f"创建输出目录: {output_dir}")
        
        # 上传并处理PDF，设置超时保护
        try:
            # 根据平台选择不同的超时处理方式
            if IS_MACOS:
                # macOS使用线程超时
                def process_pdf():
                    # 上传PDF文件
                    self.logger(f"开始上传PDF文件: {pdf_file.name}")
                    uploaded_file = client.files.upload(
                        file={
                            "file_name": pdf_file.stem,
                            "content": pdf_file.read_bytes(),
                        },
                        purpose="ocr",
                    )
                    
                    # 获取签名URL并处理OCR
                    self.logger("获取签名URL并开始OCR处理")
                    signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=1)
                    
                    self.logger("调用Mistral OCR API处理PDF")
                    return client.ocr.process(
                        document=DocumentURLChunk(document_url=signed_url.url), 
                        model="mistral-ocr-latest", 
                        include_image_base64=True
                    )
                
                try:
                    pdf_response = with_timeout(GLOBAL_TIMEOUT, process_pdf)
                except TimeoutError as e:
                    error_msg = f"PDF处理超时: {str(e)}"
                    self.logger(f"【错误】{error_msg}")
                    raise Exception(error_msg)
            else:
                # 非macOS使用信号超时
                # 注册信号处理器用于超时处理
                original_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(GLOBAL_TIMEOUT)  # 设置超时时间
                
                self.logger(f"开始上传PDF文件: {pdf_file.name}")
                uploaded_file = client.files.upload(
                    file={
                        "file_name": pdf_file.stem,
                        "content": pdf_file.read_bytes(),
                    },
                    purpose="ocr",
                )
                
                # 获取签名URL并处理OCR
                self.logger("获取签名URL并开始OCR处理")
                signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=1)
                
                self.logger("调用Mistral OCR API处理PDF")
                pdf_response = client.ocr.process(
                    document=DocumentURLChunk(document_url=signed_url.url), 
                    model="mistral-ocr-latest", 
                    include_image_base64=True
                )
                
                # 取消超时设置
                signal.alarm(0)
                signal.signal(signal.SIGALRM, original_handler)
        except Exception as e:
            # 确保取消超时设置（在非macOS平台）
            if not IS_MACOS:
                try:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, original_handler)
                except:
                    pass
                
            error_msg = f"PDF处理失败: {str(e)}"
            self.logger(f"【错误】{error_msg}")
            raise Exception(error_msg)
        
        # 保存OCR结果
        self.logger("OCR处理完成，开始保存结果")
        try:
            complete_md_path, images = self.save_ocr_results(pdf_response, output_dir)
        except Exception as e:
            error_msg = f"保存OCR结果失败: {str(e)}"
            self.logger(f"【错误】{error_msg}")
            raise Exception(error_msg)
        
        # 如果启用了图片描述，则生成图片描述
        final_content = ""
        try:
            if self.enable_image_description and IMAGE_DESCRIPTION_AVAILABLE:
                self.logger("开始生成图片描述")
                image_descriptions = self.generate_image_descriptions(images)
                
                self.logger("创建图片描述Markdown文件")
                desc_md_path = self.create_image_description_markdown(image_descriptions, output_dir)
                
                self.logger("合并OCR结果和图片描述")
                final_content = self.create_final_markdown(complete_md_path, desc_md_path, output_dir)
            else:
                # 如果未启用图片描述，直接返回OCR结果
                self.logger("图片描述功能未启用，直接使用OCR结果")
                with open(complete_md_path, 'r', encoding='utf-8') as f:
                    final_content = f.read()
        except Exception as e:
            error_msg = f"处理图片描述失败: {str(e)}"
            self.logger(f"【警告】{error_msg}，使用原始OCR结果")
            # 如果图片描述处理失败，仍然返回OCR结果
            try:
                with open(complete_md_path, 'r', encoding='utf-8') as f:
                    final_content = f.read()
            except:
                raise Exception("无法读取OCR结果")
        
        self.logger("高级PDF转换完成")
        return final_content

