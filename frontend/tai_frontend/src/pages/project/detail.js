import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Table, Button, Input, Form, Upload, message, Tabs, Space, Descriptions, Tag, Select, Switch } from 'antd';
import { UploadOutlined, EyeOutlined, DeleteOutlined, SettingOutlined } from '@ant-design/icons';
import request from '../../utils/request';
import config from '../../config';

const { TextArea } = Input;

const ProjectDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [articles, setArticles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [articleType, setArticleType] = useState(null);
  const [form] = Form.useForm();
  const [settingsForm] = Form.useForm();  // 为项目设置添加单独的 form 实例

  // 使用useCallback来缓存函数
  const fetchProject = useCallback(async () => {
    try {
      const response = await request(`/projects/${id}`);
      setProject(response);
      settingsForm.setFieldsValue({
        name: response.name,
        auto_approve: response.auto_approve,
        prompt: response.config?.prompt || '',
        format_prompt: response.config?.format_prompt || '',
        review_criteria: response.config?.review_criteria || '',
        language: response.config?.language || 'zh'
      });
      form.setFieldsValue({
        prompt: response.config?.prompt || '',
      });
    } catch (error) {
      message.error('获取项目详情失败');
    }
  }, [id, form, settingsForm]);

  const fetchArticles = useCallback(async () => {
    try {
      const response = await request('/articles?project_id=' + id);
      // 只显示属于当前项目的文章
      setArticles(response);
    } catch (error) {
      message.error('获取文章列表失败');
    }
  }, [id]);

  useEffect(() => {
    fetchProject();
    fetchArticles();
  }, [id, fetchProject, fetchArticles]);

  // 更新项目Prompt
  const handleUpdatePrompt = async (values) => {
    try {
      await request(`/projects/${id}`, {
        method: 'PUT',
        data: {
          config: {
            ...project.config,  // 保留其他配置
            prompt: values.prompt
          }
        }
      });
      message.success('更新成功');
      fetchProject();
    } catch (error) {
      message.error('更新失败');
    }
  };

  // 删除文章
  const handleDeleteArticle = async (articleId) => {
    try {
      await request(`/articles/${articleId}`, {
        method: 'DELETE',
      });
      message.success('删除文章成功');
      fetchArticles();
    } catch (error) {
      message.error('删除文章失败');
    }
  };

  // 文件上传配置
  const uploadProps = {
    name: 'file',
    action: `${config.apiBaseURL}/jobs_upload?project_id=${id}`,
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token')}`,
    },
    multiple: true, // 添加多文件上传支持
    accept: '.doc,.docx,.pdf,.txt,.md', // 添加文件类型限制
    onChange(info) {
      if (info.file.status === 'uploading') {
        setUploading(true);
      }
      if (info.file.status === 'done') {
        setUploading(false);
        message.success(`${info.file.name} 上传成功`);
        fetchArticles();
      } else if (info.file.status === 'error') {
        setUploading(false);
        message.error(`${info.file.name} 上传失败`);
      }
    },
  };

  const columns = [
    {
      title: '文章名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Button 
          type="link" 
          onClick={() => navigate(`/project/${id}/articles/${record.id}`)}
        >
          {text}
        </Button>
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
            onClick={() => navigate(`/project/${id}/articles/${record.id}`)}
          >
            查看
          </Button>
          <Button 
            type="link" 
            danger 
            icon={<DeleteOutlined />}
            onClick={() => handleDeleteArticle(record.id)}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  // 更新项目设置
  const handleUpdateSettings = async (values) => {
    try {
      await request(`/projects/${id}`, {
        method: 'PUT',
        data: {
          name: values.name,
          config: {
            prompt: values.prompt,
            format_prompt: values.format_prompt,
            review_criteria: values.review_criteria,
            language: values.language || 'zh',
          },
          auto_approve: values.auto_approve
        }
      });
      message.success('更新成功');
      fetchProject();
    } catch (error) {
      message.error('更新失败');
    }
  };

  // 渲染项目设定
  const renderProjectSettings = () => {
    if (!project) {
      return <div>加载中...</div>;
    }
    
    return (
      <Card title="项目设定" bordered={false}>
        <Form
          form={settingsForm}
          layout="vertical"
          onFinish={handleUpdateSettings}
        >
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input />
          </Form.Item>

          <Form.Item
            name="prompt"
            label={
              <span>
                提示词
                {articleType?.config?.prompt && (
                  <Tag color="blue" style={{ marginLeft: 8 }}>可继承</Tag>
                )}
              </span>
            }
            help="如果不设置，将使用文章类型中的提示词"
          >
            <Input.TextArea rows={6} />
          </Form.Item>

          <Form.Item
            name="format_prompt"
            label={
              <span>
                格式化提示词
                {articleType?.config?.format_prompt && (
                  <Tag color="blue" style={{ marginLeft: 8 }}>可继承</Tag>
                )}
              </span>
            }
            help="如果不设置，将使用文章类型中的格式化提示词"
          >
            <Input.TextArea rows={4} />
          </Form.Item>

          <Form.Item
            name="review_criteria"
            label="评审标准"
            help="设置具体的评审标准和要求"
          >
            <Input.TextArea rows={4} />
          </Form.Item>

          <Form.Item
            name="language"
            label="语言"
          >
            <Select>
              <Select.Option value="zh">中文</Select.Option>
              <Select.Option value="en">English</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="auto_approve"
            valuePropName="checked"
            label="自动批准"
          >
            <Switch />
          </Form.Item>

          {articleType && (
            <div style={{ marginBottom: 16 }}>
              <h3>文章类型: {articleType.name}</h3>
              {articleType.config && (
                <Descriptions bordered column={1} size="small" style={{ marginTop: 8 }}>
                  {articleType.config?.min_words > 0 || articleType.config?.max_words > 0 ? (
                    <Descriptions.Item label="字数限制">
                      {articleType.config?.min_words || 0} - {articleType.config?.max_words || '∞'}
                    </Descriptions.Item>
                  ) : null}
                </Descriptions>
              )}
            </div>
          )}

          <Form.Item>
            <Button type="primary" htmlType="submit">
              保存设置
            </Button>
          </Form.Item>
        </Form>
      </Card>
    );
  };

  const items = [
    {
      key: '1',
      label: '文章管理',
      children: (
        <>
          <div style={{ marginBottom: '16px' }}>
            <Upload {...uploadProps}>
              <Button icon={<UploadOutlined />} loading={uploading}>
                上传文章
              </Button>
            </Upload>
          </div>

          <Table
            columns={columns}
            dataSource={articles}
            rowKey="id"
          />
        </>
      )
    },
    {
      key: '2',
      label: 'Prompt设置',
      children: (
        <Form
          form={form}
          onFinish={handleUpdatePrompt}
          initialValues={{ prompt: project?.config?.prompt }}
          layout="vertical"
        >
          <Form.Item
            name="prompt"
            label="审阅提示"
          >
            <Input.TextArea rows={10} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">
              保存
            </Button>
          </Form.Item>
        </Form>
      )
    },
    {
      key: '3',
      label: '项目设定',
      children: renderProjectSettings()
    }
  ];

  if (!project) {
    return <div>加载中...</div>;
  }

  return (
    <div style={{ padding: '24px' }}>
      <Card title={project.name}>
        <Tabs defaultActiveKey="1" items={items} />
      </Card>
    </div>
  );
};

export default ProjectDetail;
