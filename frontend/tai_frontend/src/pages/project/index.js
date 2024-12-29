import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Select, Switch, message } from 'antd';
import request from '../../utils/request';
import { useNavigate } from 'react-router-dom';

const ProjectList = () => {
  const [projects, setProjects] = useState([]);
  const [articleTypes, setArticleTypes] = useState([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [form] = Form.useForm();
  const navigate = useNavigate();

  // 获取项目列表
  const fetchProjects = async () => {
    try {
      const response = await request('/projects');
      setProjects(response);
    } catch (error) {
      message.error('获取项目列表失败');
    }
  };

  // 获取文章类型列表
  const fetchArticleTypes = async () => {
    try {
      const response = await request('/article-types');
      setArticleTypes(response);
    } catch (error) {
      message.error('获取文章类型列表失败');
    }
  };

  useEffect(() => {
    fetchProjects();
    fetchArticleTypes();
  }, []);

  // 创建新项目
  const handleCreate = async (values) => {
    try {
      await request('/projects', {
        method: 'POST',
        data: values,
      });
      message.success('创建项目成功');
      setIsModalVisible(false);
      form.resetFields();
      fetchProjects();
    } catch (error) {
      message.error('创建项目失败');
    }
  };

  // 删除项目
  const handleDelete = async (id) => {
    try {
      await request(`/projects/${id}`, {
        method: 'DELETE',
      });
      message.success('删除项目成功');
      fetchProjects();
    } catch (error) {
      message.error('删除项目失败');
    }
  };

  const columns = [
    {
      title: '项目名称',
      dataIndex: 'name',
      key: 'name',
      render: (text, record) => (
        <Button type="link" onClick={() => navigate(`/project/${record.id}`)}>
          {text}
        </Button>
      ),
    },
    {
      title: '文章类型',
      dataIndex: 'article_type_id',
      key: 'article_type_id',
      render: (id) => articleTypes.find(type => type.id === id)?.name || id,
    },
    {
      title: '自动批阅',
      dataIndex: 'auto_approve',
      key: 'auto_approve',
      render: (value) => value ? '是' : '否',
    },
    {
      title: '操作',
      fixed: 'right',
      key: 'action',
      render: (_, record) => (
        <Button type="link" danger onClick={() => handleDelete(record.id)}>
          删除
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: '16px' }}>
        <Button type="primary" onClick={() => setIsModalVisible(true)}>
          新建项目
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={projects}
        scroll={{ x: 'max-content' }}
        rowKey="id"
      />

      <Modal
        title="新建项目"
        open={isModalVisible}
        onOk={() => form.submit()}
        onCancel={() => {
          setIsModalVisible(false);
          form.resetFields();
        }}
      >
        <Form
          form={form}
          onFinish={handleCreate}
          layout="vertical"
        >
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="请输入项目名称" />
          </Form.Item>

          <Form.Item
            name="article_type_id"
            label="文章类型"
            rules={[{ required: true, message: '请选择文章类型' }]}
          >
            <Select placeholder="请选择文章类型">
              {articleTypes.map(type => (
                <Select.Option key={type.id} value={type.id}>
                  {type.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="auto_approve"
            label="自动批阅"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ProjectList;
