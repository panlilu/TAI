import React, { useState, useEffect, useCallback } from 'react';
import { Card, Typography, Spin, Alert, Descriptions } from 'antd';
import request from '../../utils/request';

const { Title, Text } = Typography;

const AIReview = ({ articleId, projectConfig }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [aiReview, setAiReview] = useState(null);
  const [eventSource, setEventSource] = useState(null);

  const fetchAIReview = useCallback(async () => {
    try {
      const response = await request.get(`/ai-reviews?article_id=${articleId}`);
      if (response && response.length > 0) {
        // 获取文章信息，查找active_ai_review_report_id
        const articleResponse = await request.get(`/articles/${articleId}`);
        const activeReviewId = articleResponse.active_ai_review_report_id;
        
        if (activeReviewId) {
          // 如果有活跃的review，查找对应的review
          const activeReview = response.find(review => review.id === activeReviewId);
          if (activeReview) {
            setAiReview(activeReview);
            return;
          }
        }
        
        // 如果没有找到活跃的review，使用第一个
        setAiReview(response[0]);
      }
    } catch (error) {
      setError('获取AI审阅报告失败');
    } finally {
      setLoading(false);
    }
  }, [articleId]);

  useEffect(() => {
    fetchAIReview();
  }, [fetchAIReview]);

  useEffect(() => {
    if (aiReview?.id && aiReview.status !== 'completed') {
      const source = new EventSource(`/api/events_ai_review/${aiReview.id}`);
      
      source.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'content') {
          setAiReview(prev => ({
            ...prev,
            source_data: data.content,
            status: data.is_final ? 'completed' : prev.status
          }));
        }
      };

      source.onerror = () => {
        source.close();
      };

      setEventSource(source);

      return () => {
        source.close();
      };
    }
  }, [aiReview?.id]);

  if (loading) {
    return <Spin tip="加载中..." />;
  }

  if (error) {
    return <Alert type="error" message={error} />;
  }

  if (!aiReview) {
    return <Alert type="info" message="暂无AI审阅报告" />;
  }

  const renderReviewMeta = () => {
    const config = projectConfig || {};
    return (
      <Descriptions bordered column={1} size="small">
        {config.review_criteria && (
          <Descriptions.Item label="评审标准">
            <Text type="secondary">{config.review_criteria}</Text>
          </Descriptions.Item>
        )}
        {(config.min_words > 0 || config.max_words > 0) && (
          <Descriptions.Item label="字数要求">
            {config.min_words > 0 && config.max_words > 0 ? 
              `${config.min_words}-${config.max_words}字` :
              config.min_words > 0 ? 
                `最少${config.min_words}字` : 
                `最多${config.max_words}字`
            }
          </Descriptions.Item>
        )}
        {config.language && (
          <Descriptions.Item label="语言">
            {config.language === 'zh' ? '中文' : 'English'}
          </Descriptions.Item>
        )}
      </Descriptions>
    );
  };

  return (
    <Card>
      <Title level={4}>AI审阅报告</Title>
      {renderReviewMeta()}
      <div style={{ marginTop: '16px' }}>
        {aiReview.source_data ? (
          <div style={{ whiteSpace: 'pre-wrap' }}>
            {aiReview.source_data}
          </div>
        ) : (
          <Alert type="info" message="AI正在生成审阅报告..." />
        )}
      </div>
    </Card>
  );
};

export default AIReview;