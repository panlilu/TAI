import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Form, Input, Button, message, Switch, Select, Descriptions, Tag, InputNumber, Collapse } from 'antd';
import request from '../../utils/request';

const { Panel } = Collapse;

const Settings = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [project, setProject] = useState(null);
  const [articleType, setArticleType] = useState(null);
  const [loading, setLoading] = useState(true);
  const [availableModels, setAvailableModels] = useState([]);
  const [aiReviewModels, setAiReviewModels] = useState([]);
  const [processWithLlmModels, setProcessWithLlmModels] = useState([]);

  const fetchModels = async () => {
    try {
      // 获取所有可用模型
      const allModels = await request.get('/models');
      setAvailableModels(allModels);

      // 获取AI审阅任务可用的模型
      const aiReviewModelsData = await request.get('/tasks/ai_review/models');
      setAiReviewModels(aiReviewModelsData);

      // 获取LLM处理任务可用的模型
      const processModelsData = await request.get('/tasks/process_with_llm/models');
      setProcessWithLlmModels(processModelsData);
    } catch (error) {
      message.error('获取模型配置失败');
    }
  };

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
        ...projectData.config,
        // 设置LLM配置的初始值
        ai_review_model: projectData.config?.ai_review_model || '',
        ai_review_temperature: projectData.config?.ai_review_temperature || 0.3,
        ai_review_max_tokens: projectData.config?.ai_review_max_tokens || 4000,
        ai_review_top_p: projectData.config?.ai_review_top_p || 0.9,
        process_model: projectData.config?.process_model || '',
        process_temperature: projectData.config?.process_temperature || 0.7,
        process_max_tokens: projectData.config?.process_max_tokens || 2000,
        process_top_p: projectData.config?.process_top_p || 0.95,
      });
    } catch (error) {
      message.error('加载项目信息失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
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
          // LLM配置
          ai_review_model: values.ai_review_model || '',
          ai_review_temperature: values.ai_review_temperature || 0.3,
          ai_review_max_tokens: values.ai_review_max_tokens || 4000,
          ai_review_top_p: values.ai_review_top_p || 0.9,
          process_model: values.process_model || '',
          process_temperature: values.process_temperature || 0.7,
          process_max_tokens: values.process_max_tokens || 2000,
          process_top_p: values.process_top_p || 0.95,
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
          {articleType.config.ai_review_model && (
            <Descriptions.Item label="AI审阅模型">
              {articleType.config.ai_review_model}
            </Descriptions.Item>
          )}
          {articleType.config.process_model && (
            <Descriptions.Item label="文本处理模型">
              {articleType.config.process_model}
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
            language: 'zh',
            ai_review_temperature: 0.3,
            ai_review_max_tokens: 4000,
            ai_review_top_p: 0.9,
            process_temperature: 0.7,
            process_max_tokens: 2000,
            process_top_p: 0.95,
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

          <Collapse style={{ marginBottom: 16 }}>
            <Panel 
              header={
                <span>
                  AI审阅模型配置
                  {articleType?.config?.ai_review_model && (
                    <Tag color="blue" style={{ marginLeft: 8 }}>可继承</Tag>
                  )}
                </span>
              } 
              key="ai_review"
            >
              <Form.Item
                name="ai_review_model"
                label="AI审阅模型"
                help="选择用于AI审阅任务的模型，如不设置将使用文章类型中的配置"
              >
                <Select placeholder="选择模型">
                  {aiReviewModels.map(model => (
                    <Select.Option key={model.id} value={model.id}>
                      {model.name} - {model.description}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <div style={{ display: 'flex', gap: '16px' }}>
                <Form.Item
                  name="ai_review_temperature"
                  label="温度"
                  style={{ flex: 1 }}
                  help="控制输出的随机性，值越低越确定"
                >
                  <InputNumber min={0} max={1} step={0.1} />
                </Form.Item>

                <Form.Item
                  name="ai_review_max_tokens"
                  label="最大Token数"
                  style={{ flex: 1 }}
                  help="生成文本的最大长度"
                >
                  <InputNumber min={100} max={8000} step={100} />
                </Form.Item>

                <Form.Item
                  name="ai_review_top_p"
                  label="Top P"
                  style={{ flex: 1 }}
                  help="控制输出的多样性"
                >
                  <InputNumber min={0} max={1} step={0.05} />
                </Form.Item>
              </div>
            </Panel>

            <Panel 
              header={
                <span>
                  文本处理模型配置
                  {articleType?.config?.process_model && (
                    <Tag color="blue" style={{ marginLeft: 8 }}>可继承</Tag>
                  )}
                </span>
              } 
              key="process_llm"
            >
              <Form.Item
                name="process_model"
                label="文本处理模型"
                help="选择用于文本处理任务的模型，如不设置将使用文章类型中的配置"
              >
                <Select placeholder="选择模型">
                  {processWithLlmModels.map(model => (
                    <Select.Option key={model.id} value={model.id}>
                      {model.name} - {model.description}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>

              <div style={{ display: 'flex', gap: '16px' }}>
                <Form.Item
                  name="process_temperature"
                  label="温度"
                  style={{ flex: 1 }}
                  help="控制输出的随机性，值越低越确定"
                >
                  <InputNumber min={0} max={1} step={0.1} />
                </Form.Item>

                <Form.Item
                  name="process_max_tokens"
                  label="最大Token数"
                  style={{ flex: 1 }}
                  help="生成文本的最大长度"
                >
                  <InputNumber min={100} max={8000} step={100} />
                </Form.Item>

                <Form.Item
                  name="process_top_p"
                  label="Top P"
                  style={{ flex: 1 }}
                  help="控制输出的多样性"
                >
                  <InputNumber min={0} max={1} step={0.05} />
                </Form.Item>
              </div>
            </Panel>
          </Collapse>

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