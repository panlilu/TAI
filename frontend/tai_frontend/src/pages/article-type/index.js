import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm, Switch, Select, InputNumber, Collapse } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import request from '../../utils/request';

const { Panel } = Collapse;

const ArticleType = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [editingId, setEditingId] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [aiReviewModels, setAiReviewModels] = useState([]);
  const [processWithLlmModels, setProcessWithLlmModels] = useState([]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await request.get('/article-types');
      setData(response);
    } catch (error) {
      message.error('获取文章类型失败');
    }
    setLoading(false);
  };

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

  useEffect(() => {
    fetchData();
    fetchModels();
  }, []);

  const handleAdd = () => {
    form.resetFields();
    setEditingId(null);
    setModalVisible(true);
  };

  const handleEdit = (record) => {
    form.setFieldsValue({
      name: record.name,
      is_public: record.is_public,
      prompt: record.config?.prompt || '',
      format_prompt: record.config?.format_prompt || '',
      review_criteria: record.config?.review_criteria || [],
      min_words: record.config?.min_words || 0,
      max_words: record.config?.max_words || 0,
      language: record.config?.language || 'zh',
      // LLM配置
      ai_review_model: record.config?.tasks?.ai_review?.model || '',
      ai_review_temperature: record.config?.tasks?.ai_review?.temperature || 0.3,
      ai_review_max_tokens: record.config?.tasks?.ai_review?.max_tokens || 4000,
      ai_review_top_p: record.config?.tasks?.ai_review?.top_p || 0.9,
      process_model: record.config?.tasks?.process_with_llm?.model || '',
      process_temperature: record.config?.tasks?.process_with_llm?.temperature || 0.7,
      process_max_tokens: record.config?.tasks?.process_with_llm?.max_tokens || 2000,
      process_top_p: record.config?.tasks?.process_with_llm?.top_p || 0.95,
    });
    setEditingId(record.id);
    setModalVisible(true);
  };

  const handleDelete = async (id) => {
    try {
      await request.delete(`/article-types/${id}`);
      message.success('删除成功');
      fetchData();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const formData = {
        name: values.name,
        is_public: values.is_public,
        config: {
          prompt: values.prompt || '',
          format_prompt: values.format_prompt || '',
          review_criteria: values.review_criteria || [],
          min_words: values.min_words || 0,
          max_words: values.max_words || 0,
          language: values.language || 'zh',
          tasks: {
            ai_review: {
              model: values.ai_review_model || '',
              temperature: values.ai_review_temperature || 0.3,
              max_tokens: values.ai_review_max_tokens || 4000,
              top_p: values.ai_review_top_p || 0.9,
            },
            process_with_llm: {
              model: values.process_model || '',
              temperature: values.process_temperature || 0.7,
              max_tokens: values.process_max_tokens || 2000,
              top_p: values.process_top_p || 0.95,
            }
          }
        }
      };

      if (editingId) {
        await request.put(`/article-types/${editingId}`, formData);
        message.success('更新成功');
      } else {
        await request.post('/article-types', formData);
        message.success('添加成功');
      }
      setModalVisible(false);
      fetchData();
    } catch (error) {
      message.error(editingId ? '更新失败' : '添加失败');
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: '类型名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
    },
    {
      title: '操作',
      fixed: 'right',
      key: 'action',
      render: (_, record) => (
        <>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除吗？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </>
      ),
    },
  ];

  return (
    <div>
      <Button
        type="primary"
        icon={<PlusOutlined />}
        onClick={handleAdd}
        style={{ marginBottom: 16 }}
      >
        添加文章类型
      </Button>
      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        scroll={{ x: 'max-content' }}
        loading={loading}
      />
      <Modal
        title={editingId ? '编辑文章类型' : '新建文章类型'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
          setEditingId(null);
        }}
        width={800}
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            is_public: false,
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
            label="类型名称"
            rules={[{ required: true, message: '请输入类型名称' }]}
          >
            <Input />
          </Form.Item>

          <Form.Item
            name="prompt"
            label="审阅提示词"
            rules={[{ required: true, message: '请输入提示词' }]}
            help="设定AI审阅时的主要提示词，将被项目继承"
          >
            <Input.TextArea rows={6} />
          </Form.Item>

          <Form.Item
            name="format_prompt"
            label="格式化提示词"
            help="用于规范AI输出格式的提示词"
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

          <div style={{ display: 'flex', gap: '16px' }}>
            <Form.Item
              name="min_words"
              label="最小字数"
              style={{ flex: 1 }}
            >
              <Input type="number" min={0} />
            </Form.Item>

            <Form.Item
              name="max_words"
              label="最大字数"
              style={{ flex: 1 }}
            >
              <Input type="number" min={0} />
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
          </div>

          <Collapse style={{ marginBottom: 16 }}>
            <Panel header="AI审阅模型配置" key="ai_review">
              <Form.Item
                name="ai_review_model"
                label="AI审阅模型"
                help="选择用于AI审阅任务的模型"
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

            <Panel header="文本处理模型配置" key="process_llm">
              <Form.Item
                name="process_model"
                label="文本处理模型"
                help="选择用于文本处理任务的模型"
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
            name="is_public"
            label="是否公开"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ArticleType;
