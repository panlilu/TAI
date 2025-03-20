import pytest
import os
from unittest.mock import patch, MagicMock, mock_open
from app.file_converter import (
    is_allowed_file,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_image,
    convert_file_to_markdown,
    AdvancedMarkdownConverter
)

@pytest.mark.unit
class TestFileConverter:
    """文件转换器功能测试"""
    
    def test_is_allowed_file(self):
        """测试文件类型检查"""
        # 允许的文件类型
        assert is_allowed_file("test.md") == True
        assert is_allowed_file("test.doc") == True
        assert is_allowed_file("test.pdf") == True
        assert is_allowed_file("test.txt") == True
        assert is_allowed_file("test.docx") == True
        assert is_allowed_file("test.png") == True
        assert is_allowed_file("test.jpg") == True
        assert is_allowed_file("test.jpeg") == True
        assert is_allowed_file("test.gif") == True
        assert is_allowed_file("test.bmp") == True
        
        # 不允许的文件类型
        assert is_allowed_file("test.exe") == False
        assert is_allowed_file("test.zip") == False
        assert is_allowed_file("test.html") == False
        
        # 大写扩展名应该也被允许
        assert is_allowed_file("test.PDF") == True
        assert is_allowed_file("test.DOCX") == True
        assert is_allowed_file("test.JPG") == True
    
    @patch("app.file_converter.Document")
    def test_extract_text_from_docx(self, mock_document):
        """测试从docx提取文本"""
        # 模拟Document对象及其方法
        mock_doc = MagicMock()
        mock_document.return_value = mock_doc
        
        # 模拟段落
        mock_paragraph1 = MagicMock()
        mock_paragraph1.text = "This is paragraph 1"
        mock_paragraph2 = MagicMock()
        mock_paragraph2.text = "This is paragraph 2"
        
        mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2]
        
        # 测试函数
        result = extract_text_from_docx("test.docx")
        
        # 验证结果
        assert result == "This is paragraph 1\nThis is paragraph 2"
        mock_document.assert_called_once_with("test.docx")
    
    @patch("app.file_converter.PdfReader")
    def test_extract_text_from_pdf(self, mock_pdf_reader):
        """测试从PDF提取文本"""
        # 模拟PdfReader对象及其方法
        mock_reader = MagicMock()
        mock_pdf_reader.return_value = mock_reader
        
        # 模拟页面
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1 content"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2 content"
        
        mock_reader.pages = [mock_page1, mock_page2]
        
        # 测试函数
        result = extract_text_from_pdf("test.pdf")
        
        # 验证结果
        assert result == "Page 1 content\nPage 2 content\n"
        mock_pdf_reader.assert_called_once_with("test.pdf")
    
    @patch("app.file_converter.Image")
    @patch("app.file_converter.pytesseract")
    def test_extract_text_from_image(self, mock_pytesseract, mock_image):
        """测试从图像提取文本"""
        # 模拟Image.open
        mock_img = MagicMock()
        mock_image.open.return_value = mock_img
        
        # 模拟pytesseract.image_to_string
        mock_pytesseract.image_to_string.return_value = "Image text content"
        
        # 测试函数
        result = extract_text_from_image("test.jpg")
        
        # 验证结果
        assert result == "Image text content"
        mock_image.open.assert_called_once_with("test.jpg")
        mock_pytesseract.image_to_string.assert_called_once_with(mock_img)
    
    @patch("app.file_converter.is_allowed_file")
    @patch("app.file_converter.os.path.splitext")
    @patch("app.file_converter.extract_text_from_docx")
    def test_convert_file_to_markdown_docx(self, mock_extract_docx, mock_splitext, mock_is_allowed):
        """测试将docx文件转换为Markdown"""
        # 模拟文件类型检查
        mock_is_allowed.return_value = True
        mock_splitext.return_value = ["test", ".docx"]
        
        # 模拟文本提取
        mock_extract_docx.return_value = "Extracted docx content"
        
        # 测试函数
        result = convert_file_to_markdown("test.docx")
        
        # 验证结果
        assert result == "Extracted docx content"
        mock_is_allowed.assert_called_once_with("test.docx")
        mock_extract_docx.assert_called_once_with("test.docx")
    
    @patch("app.file_converter.is_allowed_file")
    @patch("app.file_converter.os.path.splitext")
    @patch("app.file_converter.extract_text_from_pdf")
    def test_convert_file_to_markdown_pdf(self, mock_extract_pdf, mock_splitext, mock_is_allowed):
        """测试将PDF文件转换为Markdown"""
        # 模拟文件类型检查
        mock_is_allowed.return_value = True
        mock_splitext.return_value = ["test", ".pdf"]
        
        # 模拟文本提取
        mock_extract_pdf.return_value = "Extracted PDF content"
        
        # 测试函数
        result = convert_file_to_markdown("test.pdf")
        
        # 验证结果
        assert result == "Extracted PDF content"
        mock_is_allowed.assert_called_once_with("test.pdf")
        mock_extract_pdf.assert_called_once_with("test.pdf")
    
    @patch("app.file_converter.is_allowed_file")
    @patch("app.file_converter.os.path.splitext")
    def test_convert_file_to_markdown_txt(self, mock_splitext, mock_is_allowed):
        """测试将txt文件转换为Markdown"""
        # 模拟文件类型检查
        mock_is_allowed.return_value = True
        mock_splitext.return_value = ["test", ".txt"]
        
        # 模拟open函数
        m = mock_open(read_data="Text file content")
        
        with patch("builtins.open", m):
            # 测试函数
            result = convert_file_to_markdown("test.txt")
        
        # 验证结果
        assert result == "Text file content"
        mock_is_allowed.assert_called_once_with("test.txt")
        m.assert_called_once_with("test.txt", 'r', encoding='utf-8')
    
    @patch("app.file_converter.is_allowed_file")
    def test_convert_file_to_markdown_unsupported_type(self, mock_is_allowed):
        """测试转换不支持的文件类型"""
        # 模拟文件类型检查
        mock_is_allowed.return_value = False
        
        # 测试函数并验证异常
        with pytest.raises(ValueError, match="Unsupported file type"):
            convert_file_to_markdown("test.xyz")
        
        mock_is_allowed.assert_called_once_with("test.xyz")

@pytest.mark.unit
class TestAdvancedMarkdownConverter:
    """高级Markdown转换器测试"""
    
    @patch("app.file_converter.os.environ.get")
    @patch("app.file_converter.MISTRAL_AVAILABLE", True)
    def test_init_with_default_config(self, mock_environ_get):
        """测试使用默认配置初始化转换器"""
        # 模拟API密钥在环境变量中
        mock_environ_get.return_value = "test_api_key"
        
        converter = AdvancedMarkdownConverter()
        
        # 验证默认配置
        assert converter.api_key == "test_api_key"
        assert converter.image_model == "lm_studio/qwen2.5-vl-7b-instruct"
        assert converter.enable_image_description == True
    
    @patch("app.file_converter.os.environ.get")
    @patch("app.file_converter.MISTRAL_AVAILABLE", True)
    def test_init_with_custom_config(self, mock_environ_get):
        """测试使用自定义配置初始化转换器"""
        # 模拟环境变量中没有API密钥
        mock_environ_get.return_value = None
        
        config = {
            "mistral_api_key": "test_mistral_key",
            "image_description_model": "custom_model",
            "enable_image_description": False
        }
        
        converter = AdvancedMarkdownConverter(config)
        
        # 验证配置应用
        assert converter.api_key == "test_mistral_key"
        assert converter.image_model == "custom_model"
        assert converter.enable_image_description == False
    
    def test_replace_images_in_markdown(self):
        """测试在Markdown中替换图像引用"""
        # 模拟环境变量以跳过API检查
        with patch("app.file_converter.os.environ.get") as mock_environ_get, \
             patch("app.file_converter.MISTRAL_AVAILABLE", True):
            
            mock_environ_get.return_value = "test_api_key"
            converter = AdvancedMarkdownConverter()
            
            markdown = """
            # Test Document
            
            ![image1](image1)
            
            Some text
            
            ![image2](image2)
            """
            
            images_dict = {
                "image1": "path/to/image1.png",
                "image2": "path/to/image2.jpg"
            }
            
            result = converter.replace_images_in_markdown(markdown, images_dict)
            
            # 验证结果
            assert "![image1](image1)" not in result
            assert "![image1](path/to/image1.png)" in result
            assert "![image2](image2)" not in result
            assert "![image2](path/to/image2.jpg)" in result 