import React from 'react';
import { Table, Button, Tag, Tooltip, Space } from 'antd';
import { useNavigate } from 'react-router-dom';
import { EyeOutlined, DeleteOutlined } from '@ant-design/icons';

const ProjectTable = ({ data, loading, onDelete }) => {
  const navigate = useNavigate();

  const renderConfig = (config, articleTypeConfig) => {
    if (!config && !articleTypeConfig) return '-';

    const mergedConfig = { 
      ...articleTypeConfig,
      ...config,
      tasks: {
        ...(articleTypeConfig?.tasks || {}),
        ...(config?.tasks || {})
      }
    };

    const hasPrompt = mergedConfig.tasks?.process_with_llm?.prompt;
    const isCustomPrompt = config?.tasks?.process_with_llm?.prompt;
    
    return (
      <Space direction="vertical">
        {hasPrompt && (
          <Tooltip title={mergedConfig.tasks.process_with_llm.prompt}>
            <Tag color="blue">
              {isCustomPrompt ? '已修改提示词' : '继承提示词'}
            </Tag>
          </Tooltip>
        )}
        {mergedConfig.review_criteria && (
          <Tooltip title={mergedConfig.review_criteria}>
            <Tag color="purple">
              {config?.review_criteria ? '已修改评审标准' : '继承评审标准'}
            </Tag>
          </Tooltip>
        )}
        {(mergedConfig.min_words > 0 || mergedConfig.max_words > 0) && (
          <Tag color="orange">
            字数限制: {mergedConfig.min_words || 0}-{mergedConfig.max_words || '∞'}
          </Tag>
        )}
      </Space>
    );
  };

  const columns = [
    {
      title: '项目名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Button 
          type="link" 
          onClick={() => navigate(`/project/${record.id}`)}
        >
          {text}
        </Button>
      ),
    },
    {
      title: '文章类型',
      dataIndex: 'article_type',
      key: 'article_type',
      render: (article_type) => article_type?.name || '-',
    },
    {
      title: '配置信息',
      key: 'config',
      render: (_, record) => renderConfig(record.config, record.article_type?.config),
    },
    {
      title: '自动批准',
      dataIndex: 'auto_approve',
      key: 'auto_approve',
      render: (auto_approve) => (
        <Tag color={auto_approve ? 'green' : 'orange'}>
          {auto_approve ? '是' : '否'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/project/${record.id}`)}
          >
            查看
          </Button>
          <Button
            type="link"
            danger
            icon={<DeleteOutlined />}
            onClick={() => onDelete(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={data}
      rowKey="id"
      loading={loading}
      scroll={{ x: 'max-content' }}
    />
  );
};

export default ProjectTable;