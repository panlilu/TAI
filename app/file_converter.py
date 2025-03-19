import os
from docx import Document
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
from pathlib import Path
import base64
import json
from typing import Dict, List, Tuple, Optional

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
        # 优先从环境变量获取API密钥，如果环境变量中没有，则从配置中获取
        self.api_key = os.environ.get("MISTRAL_API_KEY") or self.config.get("mistral_api_key")
        self.image_model = self.config.get("image_description_model", "lm_studio/qwen2.5-vl-7b-instruct")
        self.enable_image_description = self.config.get("enable_image_description", True)
        
        if not MISTRAL_AVAILABLE:
            raise ImportError("高级转换需要安装mistralai包: pip install mistralai")
            
        if not self.api_key:
            raise ValueError("高级转换需要提供Mistral API密钥，可以通过环境变量MISTRAL_API_KEY设置或在项目配置中提供")
    
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
        
        for img_id, img_info in images.items():
            try:
                img_path = img_info["path"]
                # 读取图片为base64
                with open(img_path, "rb") as img_file:
                    base64_image = base64.b64encode(img_file.read()).decode("utf-8")
                
                # 使用LLM生成图片描述
                response = completion(
                    model=self.image_model,
                    messages=[
                        {"role": "system", "content": "你是一个图像描述助手。描述图像内容，详细且简洁。"},
                        {"role": "user", "content": [
                            {"type": "text", "text": "请描述这张图片的内容，提供清晰、准确的描述。"},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                        ]}
                    ]
                )
                
                # 获取描述文本
                desc_text = response.choices[0].message.content
                descriptions[img_id] = desc_text
                
            except Exception as e:
                descriptions[img_id] = f"无法生成描述：{str(e)}"
        
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
            final_content = f"{complete_content}\n\n{desc_content}"
        
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
        client = Mistral(api_key=self.api_key)
        
        # 确认PDF文件存在
        pdf_file = Path(pdf_path)
        if not pdf_file.is_file():
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")
        
        # 创建输出目录
        output_dir = os.path.join(os.path.dirname(pdf_path), "ocr_results")
        
        # 上传并处理PDF
        uploaded_file = client.files.upload(
            file={
                "file_name": pdf_file.stem,
                "content": pdf_file.read_bytes(),
            },
            purpose="ocr",
        )
        
        # 获取签名URL并处理OCR
        signed_url = client.files.get_signed_url(file_id=uploaded_file.id, expiry=1)
        pdf_response = client.ocr.process(
            document=DocumentURLChunk(document_url=signed_url.url), 
            model="mistral-ocr-latest", 
            include_image_base64=True
        )
        
        # 保存OCR结果
        complete_md_path, images = self.save_ocr_results(pdf_response, output_dir)
        
        # 如果启用了图片描述，则生成图片描述
        final_content = ""
        if self.enable_image_description and IMAGE_DESCRIPTION_AVAILABLE:
            image_descriptions = self.generate_image_descriptions(images)
            desc_md_path = self.create_image_description_markdown(image_descriptions, output_dir)
            final_content = self.create_final_markdown(complete_md_path, desc_md_path, output_dir)
        else:
            # 如果未启用图片描述，直接返回OCR结果
            with open(complete_md_path, 'r', encoding='utf-8') as f:
                final_content = f.read()
        
        return final_content

