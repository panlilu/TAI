import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Typography, Button, Space, Tabs, message } from 'antd';
import request from '../../utils/request';
import AttachmentViewer from './attachment-viewer';
import AIReview from './ai-review';
import MarkdownView from './markdown-view';

const { Title } = Typography;

const ArticleDetail = () => {
  const { projectId, articleId } = useParams();
  const [article, setArticle] = useState(null);
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchArticle = useCallback(async () => {
    try {
      const response = await request.get(`/articles/${articleId}`);
      setArticle(response);
    } catch (error) {
      message.error('获取文章失败');
    }
  }, [articleId]);

  const fetchProject = useCallback(async () => {
    try {
      const response = await request.get(`/projects/${projectId}`);
      setProject(response);
    } catch (error) {
      message.error('获取项目信息失败');
    }
  }, [projectId]);

  useEffect(() => {
    Promise.all([fetchArticle(), fetchProject()]).finally(() => {
      setLoading(false);
    });
  }, [fetchArticle, fetchProject]);

  const handleAIReview = async () => {
    try {
      await request.post(`/articles/${articleId}/review`);
      message.success('已开始AI审阅');
    } catch (error) {
      message.error('启动AI审阅失败');
    }
  };

  if (loading || !article) {
    return <div>加载中...</div>;
  }

  const items = [
    {
      label: '文章内容',
      key: 'content',
      children: <AttachmentViewer article={article} onArticleChanged={fetchArticle} />
    },
    {
      label: 'Markdown预览',
      key: 'markdown',
      children: <MarkdownView articleId={articleId} />
    },
    {
      label: 'AI审阅',
      key: 'ai-review',
      children: (
        <>
          <Space style={{ marginBottom: 16 }}>
            <Button type="primary" onClick={handleAIReview}>
              开始AI审阅
            </Button>
          </Space>
          <AIReview articleId={articleId} projectConfig={project?.config} />
        </>
      )
    }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <Card>
        <Title level={3}>{article.name}</Title>
        <Tabs items={items} />
      </Card>
    </div>
  );
};

export default ArticleDetail;