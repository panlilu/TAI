import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, message, Button, Tabs, Space } from 'antd';
import { FullscreenOutlined, FullscreenExitOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import 'github-markdown-css';
import request from '../../../utils/request';
import config from '../../../config';

const ArticleViewer = () => {
  const { projectId, articleId } = useParams();
  const [article, setArticle] = useState(null);
  const [content, setContent] = useState(null);
  const [markdownContent, setMarkdownContent] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [aiReview, setAiReview] = useState(null);

  useEffect(() => {
    const fetchArticle = async () => {
      try {
        const response = await request(`/articles/${articleId}`);
        setArticle(response);
        
        if (response.name.toLowerCase().endsWith('.pdf')) {
          // For PDF files, fetch as blob
          const pdfResponse = await fetch(`${config.apiBaseURL}/articles/${articleId}/content`, {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('token')}`,
            },
          });
          const blob = await pdfResponse.blob();
          const url = URL.createObjectURL(blob);
          setPdfUrl(url);
        } else {
          // For other file types, fetch as before
          const contentResponse = await request(`/articles/${articleId}/content`);
          setContent(contentResponse);
        }

        // 获取 AI review 内容
        const aiReviewResponse = await request(`/ai-reviews?article_id=${articleId}`);
        if (aiReviewResponse && aiReviewResponse.length > 0) {
          // 取最新的一条记录
          const latestReview = aiReviewResponse[0];
          setAiReview(latestReview);
          if (latestReview.processed_attachment_text) {
            setMarkdownContent(latestReview.processed_attachment_text);
          }
        }
      } catch (error) {
        message.error('获取文章详情失败');
      }
    };

    fetchArticle();

    // Cleanup function to revoke blob URL
    return () => {
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
      }
    };
  }, [articleId]);

  const handleConvertToMarkdown = async () => {
    try {
      const response = await request.post(`/jobs`, {
        task: 'convert_to_markdown',
        article_id: articleId
      });
      message.success('已创建转换任务，请稍后查看任务状态');
    } catch (error) {
      message.error('创建转换任务失败');
    }
  };

  const handleAIProcess = async () => {
    try {
      const response = await request.post(`/jobs`, {
        task: 'process_with_llm',
        article_id: articleId
      });
      message.success('已创建AI处理任务，请稍后查看任务状态');
    } catch (error) {
      message.error('创建AI处理任务失败');
    }
  };

  const renderContent = () => {
    if (!article) return null;

    const fileExtension = article.name.split('.').pop().toLowerCase();

    switch (fileExtension) {
      case 'pdf':
        return pdfUrl ? (
          <iframe
            src={pdfUrl}
            style={{ width: '100%', height: '800px', border: 'none' }}
            title="PDF Viewer"
          />
        ) : (
          <div>加载中...</div>
        );
      case 'md':
        return content ? (
          <div className="markdown-body" style={{ 
            padding: '20px',
            maxWidth: '900px',
            margin: '0 auto',
            backgroundColor: 'var(--color-canvas-default)',
            color: 'var(--color-fg-default)'
          }}>
            <ReactMarkdown key={content}>{content}</ReactMarkdown>
          </div>
        ) : null;
      case 'txt':
        return content ? (
          <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
            {content}
          </pre>
        ) : null;
      default:
        return <p>不支持的文件格式</p>;
    }
  };

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  if (!article) {
    return <div>加载中...</div>;
  }

  const items = [
    {
      key: '1',
      label: '原始内容',
      children: renderContent()
    },
    {
      key: '2',
      label: 'Markdown预览',
      children: markdownContent ? (
        <div className="markdown-body" style={{ 
          padding: '20px',
          maxWidth: '900px',
          margin: '0 auto',
          backgroundColor: 'var(--color-canvas-default)',
          color: 'var(--color-fg-default)'
        }}>
          <ReactMarkdown key={markdownContent}>{markdownContent}</ReactMarkdown>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '20px' }}>暂无Markdown内容</div>
      )
    },
    {
      key: '3',
      label: 'AI审阅报告',
      children: aiReview ? (
        <div className="markdown-body" style={{ 
          padding: '20px',
          maxWidth: '900px',
          margin: '0 auto',
          backgroundColor: 'var(--color-canvas-default)',
          color: 'var(--color-fg-default)'
        }}>
          <ReactMarkdown key={aiReview.source_data}>{aiReview.source_data}</ReactMarkdown>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '20px' }}>暂无AI审阅报告</div>
      )
    }
  ];

  return (
    <div style={{ padding: isFullscreen ? '0' : '24px' }}>
      <Card 
        title={
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>{article.name}</span>
            <Space>
              <Button onClick={handleConvertToMarkdown}>转换为Markdown</Button>
              <Button type="primary" onClick={handleAIProcess}>AI审阅</Button>
              <Button 
                type="text" 
                icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />} 
                onClick={toggleFullscreen}
              />
            </Space>
          </div>
        }
        style={{ height: isFullscreen ? '100vh' : 'auto' }}
      >
        <div style={{ 
          height: isFullscreen ? 'calc(100vh - 57px)' : 'auto',
          overflow: 'auto'
        }}>
          <Tabs items={items} />
        </div>
      </Card>
    </div>
  );
};

export default ArticleViewer;