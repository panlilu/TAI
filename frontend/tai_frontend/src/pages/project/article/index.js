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
  const [isFullscreen, setIsFullscreen] = useState(false);

  useEffect(() => {
    const fetchArticle = async () => {
      try {
        const response = await request(`/articles/${articleId}`);
        setArticle(response);
        // 获取文章内容
        const contentResponse = await request(`/articles/${articleId}/content`);
        setContent(contentResponse);
      } catch (error) {
        message.error('获取文章详情失败');
      }
    };

    fetchArticle();
  }, [articleId]);

  const renderContent = () => {
    if (!article || !content) return null;

    const fileExtension = article.name.split('.').pop().toLowerCase();

    switch (fileExtension) {
      case 'pdf':
        return (
          <iframe
            src={`${config.apiBaseURL}/articles/${articleId}/content`}
            style={{ width: '100%', height: '800px', border: 'none' }}
            title="PDF Viewer"
          />
        );
      case 'md':
        return (
          <div className="markdown-body" style={{ padding: '20px' }}>
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        );
      case 'txt':
        return (
          <pre style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
            {content}
          </pre>
        );
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