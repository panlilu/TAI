import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Card, message, Button, Tabs, Space, Dropdown, Menu } from 'antd';
import { FullscreenOutlined, FullscreenExitOutlined, DownOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import 'github-markdown-css';
import request from '../../../utils/request';
import config from '../../../config';
import { eventService } from '../../../utils/eventService';

const ArticleViewer = () => {
  const { projectId, articleId } = useParams();
  const [article, setArticle] = useState(null);
  const [content, setContent] = useState(null);
  const [markdownContent, setMarkdownContent] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [aiReview, setAiReview] = useState(null);
  const [isAiProcessing, setIsAiProcessing] = useState(false);
  const [structuredData, setStructuredData] = useState(null);
  const [isStructuredDataProcessing, setIsStructuredDataProcessing] = useState(false);
  const [selectedAction, setSelectedAction] = useState('AI审阅');

  const connectToAIReviewEvents = (aiReviewId) => {
    setIsAiProcessing(true);
    
    eventService.connectToAIReview(
      aiReviewId,
      (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'content') {
          setAiReview(prev => ({
            ...prev,
            source_data: (prev?.source_data || '') + data.content
          }));

          if (data.is_final) {
            setIsAiProcessing(false);
            eventService.disconnectAIReview();
          }
        }
      },
      () => {
        setIsAiProcessing(false);
      }
    );
  };

  // 连接结构化数据提取事件
  const connectToStructuredDataEvents = (reportId) => {
    setIsStructuredDataProcessing(true);
    
    eventService.connectToStructuredData(
      reportId,
      (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'content') {
          // 如果数据是JSON格式的字符串，尝试解析
          try {
            const contentData = JSON.parse(data.content);
            setStructuredData(prev => contentData);
          } catch (e) {
            // 如果不是JSON格式，作为普通文本处理
            setStructuredData(prev => ({
              ...prev,
              raw_text: (prev?.raw_text || '') + data.content
            }));
          }

          if (data.is_final) {
            setIsStructuredDataProcessing(false);
            eventService.disconnectStructuredData();
          }
        }
      },
      () => {
        setIsStructuredDataProcessing(false);
      }
    );
  };

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
          // 使用文章的active_ai_review_report_id获取活跃的审阅报告
          const activeReviewId = response.active_ai_review_report_id;
          let activeReview = null;
          
          if (activeReviewId) {
            // 如果有活跃的review，查找对应的review
            activeReview = aiReviewResponse.find(review => review.id === activeReviewId);
          }
          
          // 如果没有找到活跃的review，使用最新的一个
          if (!activeReview) {
            activeReview = aiReviewResponse[0];
          }
          
          setAiReview(activeReview);
          if (activeReview.processed_attachment_text) {
            setMarkdownContent(activeReview.processed_attachment_text);
          }

          // 如果存在AI审阅报告且正在处理中，启动实时更新
          if (activeReview.status !== 'completed') {
            connectToAIReviewEvents(activeReview.id);
          }
        }
        
        // 获取结构化数据
        try {
          const structuredDataResponse = await request(`/structured-data?article_id=${articleId}`);
          if (structuredDataResponse) {
            setStructuredData(structuredDataResponse);
          }
        } catch (error) {
          // 如果是404错误（暂无数据），不显示错误信息
          if (error.response?.status !== 404) {
            console.error('获取结构化数据失败', error);
          } else {
            console.log('暂无结构化数据');
          }
        }
      } catch (error) {
        message.error('获取文章详情失败');
      }
    };

    fetchArticle();

    // Cleanup function
    return () => {
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
      }
      eventService.disconnectAIReview();
      eventService.disconnectStructuredData();
    };
  }, [articleId]);

  const handleConvertToMarkdown = async () => {
    try {
      const response = await request.post(`/jobs`, {
        project_id: parseInt(projectId),
        name: `转换文章 #${articleId} 为Markdown`,
        tasks: [
          {
            task_type: 'convert_to_markdown',
            article_id: parseInt(articleId)
          }
        ]
      });
      message.success('已创建转换任务，请稍后查看任务状态');
    } catch (error) {
      message.error('创建转换任务失败');
    }
  };

  const handleAIProcess = async () => {
    try {
      setIsAiProcessing(true);
      const response = await request.post('/jobs', {
        project_id: parseInt(projectId),
        name: `AI审阅文章 #${articleId}`,
        tasks: [
          {
            task_type: 'process_with_llm',
            article_id: parseInt(articleId)
          }
        ]
      });
      message.success('已创建AI处理任务，请稍后在AI审阅报告标签页查看进度');
      
      // 创建新的 AI 审阅报告记录并启动实时更新
      const aiReviewResponse = await request(`/ai-reviews?article_id=${articleId}`);
      if (aiReviewResponse && aiReviewResponse.length > 0) {
        const latestReview = aiReviewResponse[0];
        setAiReview(latestReview);
        connectToAIReviewEvents(latestReview.id);
      }
    } catch (error) {
      setIsAiProcessing(false);
      message.error('创建AI处理任务失败');
    }
  };
  
  const handleExtractStructuredData = async () => {
    try {
      setIsStructuredDataProcessing(true);
      const response = await request.post(`/articles/${articleId}/extract-structured-data`);
      message.success('已创建结构化数据提取任务，请稍后在结构化数据标签页查看进度');
      
      // 如果有活跃的AI审阅报告，连接到结构化数据事件流
      if (aiReview && aiReview.id) {
        connectToStructuredDataEvents(aiReview.id);
      }
      
      // 尝试获取结构化数据（可能刚开始还没准备好）
      try {
        const structuredDataResponse = await request(`/structured-data?article_id=${articleId}`);
        if (structuredDataResponse) {
          setStructuredData(structuredDataResponse);
        }
      } catch (error) {
        // 结构化数据尚未准备好，稍后将通过事件更新自动更新
        console.log('结构化数据尚未准备好，稍后将自动更新');
      }
    } catch (error) {
      setIsStructuredDataProcessing(false);
      message.error('创建结构化数据提取任务失败');
    }
  };

  const handleActionSelect = ({ key }) => {
    setSelectedAction(key);
  };

  const handleExecuteAction = () => {
    switch (selectedAction) {
      case '转换为Markdown':
        handleConvertToMarkdown();
        break;
      case 'AI审阅':
        handleAIProcess();
        break;
      case '提取结构化数据':
        handleExtractStructuredData();
        break;
      default:
        break;
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
  
  const menu = (
    <Menu onClick={handleActionSelect} selectedKeys={[selectedAction]}>
      <Menu.Item key="转换为Markdown">转换为Markdown</Menu.Item>
      <Menu.Item key="AI审阅">AI审阅</Menu.Item>
      <Menu.Item key="提取结构化数据">提取结构化数据</Menu.Item>
    </Menu>
  );

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
      children: (
        <div className="markdown-body" style={{ 
          padding: '20px',
          maxWidth: '900px',
          margin: '0 auto',
          backgroundColor: 'var(--color-canvas-default)',
          color: 'var(--color-fg-default)',
          position: 'relative'
        }}>
          {isAiProcessing && (
            <div style={{ 
              position: 'absolute', 
              top: '10px', 
              right: '10px', 
              padding: '5px 10px',
              background: '#1890ff',
              color: 'white',
              borderRadius: '4px'
            }}>
              正在生成...
            </div>
          )}
          {aiReview?.source_data ? (
            <ReactMarkdown key={aiReview.source_data}>{aiReview.source_data}</ReactMarkdown>
          ) : (
            <div style={{ textAlign: 'center', padding: '20px' }}>暂无AI审阅报告</div>
          )}
        </div>
      )
    },
    {
      key: '4',
      label: '结构化数据',
      children: (
        <div className="markdown-body" style={{ 
          padding: '20px',
          maxWidth: '900px',
          margin: '0 auto',
          backgroundColor: 'var(--color-canvas-default)',
          color: 'var(--color-fg-default)',
          position: 'relative'
        }}>
          {isStructuredDataProcessing && (
            <div style={{ 
              position: 'absolute', 
              top: '10px', 
              right: '10px', 
              padding: '5px 10px',
              background: '#1890ff',
              color: 'white',
              borderRadius: '4px'
            }}>
              正在提取...
            </div>
          )}
          {structuredData ? (
            <ReactMarkdown key={JSON.stringify(structuredData)}>
              {typeof structuredData === 'string' 
                ? structuredData
                : "```yaml\n" + Object.entries(structuredData).map(([key, value]) => {
                    if (Array.isArray(value)) {
                      return `${key}:\n${value.map(item => `  - ${item}`).join('\n')}`;
                    }
                    return `${key}: ${value}`;
                  }).join('\n') + "\n```"
              }
            </ReactMarkdown>
          ) : (
            <div style={{ textAlign: 'center', padding: '20px' }}>暂无结构化数据</div>
          )}
        </div>
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
              <Dropdown menu={menu} trigger={['click']}>
                <Button>
                  {selectedAction} <DownOutlined />
                </Button>
              </Dropdown>
              <Button type="primary" onClick={handleExecuteAction}>执行</Button>
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