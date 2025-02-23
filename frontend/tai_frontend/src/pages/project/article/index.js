import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, message, Button } from 'antd';
import { FullscreenOutlined, FullscreenExitOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import 'github-markdown-css';
import request from '../../../utils/request';
import config from '../../../config';

const ArticleViewer = () => {
  const { projectId, articleId } = useParams();
  const [article, setArticle] = useState(null);
  const [content, setContent] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

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
          <div className="markdown-body" style={{ padding: '20px' }}>
            <ReactMarkdown>{content}</ReactMarkdown>
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

  return (
    <div style={{ padding: isFullscreen ? '0' : '24px' }}>
      <Card 
        title={article.name}
        extra={
          <Button 
            type="text" 
            icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />} 
            onClick={toggleFullscreen}
          />
        }
        style={{ height: isFullscreen ? '100vh' : 'auto' }}
        bodyStyle={{ 
          height: isFullscreen ? 'calc(100vh - 57px)' : 'auto',
          overflow: 'auto'
        }}
      >
        {renderContent()}
      </Card>
    </div>
  );
};

export default ArticleViewer;