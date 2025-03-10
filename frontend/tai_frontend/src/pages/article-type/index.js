import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, message, Popconfirm, Switch, Select } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import request from '../../utils/request';

const ArticleType = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [editingId, setEditingId] = useState(null);

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

  useEffect(() => {
    fetchData();
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
      language: record.config?.language || 'zh'
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
            language: 'zh'
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
