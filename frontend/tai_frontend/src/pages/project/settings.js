import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Form, Input, Button, message, Switch, Select, Descriptions, Tag } from 'antd';
import request from '../../utils/request';

const Settings = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [project, setProject] = useState(null);
  const [articleType, setArticleType] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const projectData = await request.get(`/projects/${id}`);
      setProject(projectData);
      
      // 加载文章类型信息
      if (projectData.article_type_id) {
        const articleTypeData = await request.get(`/article-types/${projectData.article_type_id}`);
        setArticleType(articleTypeData);
      }

      // 设置表单初始值
      form.setFieldsValue({
        name: projectData.name,
        auto_approve: projectData.auto_approve,
        ...projectData.config
      });
    } catch (error) {
      message.error('加载项目信息失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [id]);

  const handleSubmit = async (values) => {
    try {
      const formData = {
        name: values.name,
        config: {
          prompt: values.prompt,
          format_prompt: values.format_prompt,
          review_criteria: values.review_criteria,
          language: values.language || 'zh',
        },
        auto_approve: values.auto_approve
      };

      await request.put(`/projects/${id}`, formData);
      message.success('更新成功');
      navigate(`/project/${id}`);
    } catch (error) {
      message.error('更新失败');
    }
  };

  const renderInheritedConfig = () => {
    if (!articleType?.config) return null;

    return (
      <Card title="继承的配置" style={{ marginBottom: 24 }}>
        <Descriptions bordered column={1}>
          {articleType.config.prompt && (
            <Descriptions.Item label="提示词">
              {articleType.config.prompt}
            </Descriptions.Item>
          )}
          {articleType.config.format_prompt && (
            <Descriptions.Item label="格式化提示词">
              {articleType.config.format_prompt}
            </Descriptions.Item>
          )}
          {articleType.config.review_criteria && (
            <Descriptions.Item label="评审标准">
              {articleType.config.review_criteria}
            </Descriptions.Item>
          )}
          {(articleType.config.min_words > 0 || articleType.config.max_words > 0) && (
            <Descriptions.Item label="字数限制">
              {articleType.config.min_words || 0} - {articleType.config.max_words || '∞'}
            </Descriptions.Item>
          )}
          {articleType.config.language && (
            <Descriptions.Item label="语言">
              {articleType.config.language === 'zh' ? '中文' : 'English'}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>
    );
  };

  if (loading) {
    return <div>加载中...</div>;
  }

  return (
    <div style={{ padding: 24 }}>
      {renderInheritedConfig()}
      
      <Card title="项目设置">
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            auto_approve: false,
            language: 'zh'
          }}
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
            style={{ flex: 1 }}
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

          <Form.Item>
            <Button type="primary" htmlType="submit">
              保存设置
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Settings;