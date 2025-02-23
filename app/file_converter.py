import os
from docx import Document
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract

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

def convert_file_to_markdown(file_path: str) -> str:
    """将文件转换为Markdown格式
    
    这是基础实现版本。未来可以扩展支持更复杂的转换逻辑，
    例如保留文档格式、图片处理、表格转换等。
    """
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

# 未来可以在这里添加更多复杂的转换实现
# 例如：
# class AdvancedMarkdownConverter:
#     """支持更复杂格式转换的实现"""
#     pass