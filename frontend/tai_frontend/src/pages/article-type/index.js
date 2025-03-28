import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, message, Popconfirm } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import request from '../../utils/request';
import ArticleTypeConfigForm from './components/ArticleTypeConfigForm';

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
      process_prompt: record.config?.tasks?.process_with_llm?.prompt || '',
      tasks: {
        convert_to_markdown: {
          conversion_type: record.config?.tasks?.convert_to_markdown?.conversion_type || 'simple',
          enable_image_description: record.config?.tasks?.convert_to_markdown?.enable_image_description !== false,
          image_description_model: record.config?.tasks?.convert_to_markdown?.image_description_model || ''
        }
      },
      process_model: record.config?.tasks?.process_with_llm?.model || '',
      process_temperature: record.config?.tasks?.process_with_llm?.temperature || 0.7,
      process_max_tokens: record.config?.tasks?.process_with_llm?.max_tokens || 2000,
      process_top_p: record.config?.tasks?.process_with_llm?.top_p || 0.95,
      extract_structured_data_model: record.config?.tasks?.extract_structured_data?.model || '',
      extract_structured_data_temperature: record.config?.tasks?.extract_structured_data?.temperature || 0.2,
      extract_structured_data_max_tokens: record.config?.tasks?.extract_structured_data?.max_tokens || 3000,
      extract_structured_data_top_p: record.config?.tasks?.extract_structured_data?.top_p || 0.8,
      extract_structured_data_extraction_prompt: record.config?.tasks?.extract_structured_data?.extraction_prompt || '',
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
          format_prompt: values.format_prompt || '',
          tasks: {
            convert_to_markdown: {
              conversion_type: values.tasks?.convert_to_markdown?.conversion_type || 'simple',
              enable_image_description: values.tasks?.convert_to_markdown?.enable_image_description,
              image_description_model: values.tasks?.convert_to_markdown?.image_description_model || '',
            },
            process_with_llm: {
              model: values.process_model || '',
              temperature: values.process_temperature || 0.7,
              max_tokens: values.process_max_tokens || 2000,
              top_p: values.process_top_p || 0.95,
              prompt: values.process_prompt || '',
            },
            extract_structured_data: {
              model: values.extract_structured_data_model || '',
              temperature: values.extract_structured_data_temperature || 0.2,
              max_tokens: values.extract_structured_data_max_tokens || 3000,
              top_p: values.extract_structured_data_top_p || 0.8,
              extraction_prompt: values.extract_structured_data_extraction_prompt || '',
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
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: '是否公开',
      dataIndex: 'is_public',
      key: 'is_public',
      render: (text) => (text ? '是' : '否'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <span>
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
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </span>
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
            tasks: {
              convert_to_markdown: {
                conversion_type: 'simple',
                enable_image_description: false,
                image_description_model: ''
              }
            },
            process_temperature: 0.7,
            process_max_tokens: 2000,
            process_top_p: 0.95,
            extract_structured_data_temperature: 0.2,
            extract_structured_data_max_tokens: 3000,
            extract_structured_data_top_p: 0.8,
          }}
        >
          <ArticleTypeConfigForm 
            form={form} 
          />
        </Form>
      </Modal>
    </div>
  );
};

export default ArticleType;
