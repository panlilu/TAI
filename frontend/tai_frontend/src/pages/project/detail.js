import React, { useState, useEffect, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Table, Button, Input, Form, Upload, message, Tabs } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import request from '../../utils/request';
import config from '../../config';

const { TextArea } = Input;

const ProjectDetail = () => {
  const { id } = useParams();
  const [project, setProject] = useState(null);
  const [articles, setArticles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [form] = Form.useForm(); // 移到组件内部

  // 使用useCallback来缓存函数
  const fetchProject = useCallback(async () => {
    try {
      const response = await request(`/projects/${id}`);
      setProject(response);
      form.setFieldsValue({
        prompt: response.prompt,
        schema_prompt: response.schema_prompt,
      });
    } catch (error) {
      message.error('获取项目详情失败');
    }
  }, [id, form]);

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
        data: values,
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
    action: `${config.apiBaseURL}/jobs?project_id=${id}`,
    headers: {
      Authorization: `Bearer ${localStorage.getItem('token')}`,
    },
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
        <Button type="link" danger onClick={() => handleDeleteArticle(record.id)}>
          删除
        </Button>
      ),
    },
  ];

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
          layout="vertical"
        >
          <Form.Item
            name="prompt"
            label="审核Prompt"
          >
            <TextArea rows={4} placeholder="请输入审核用的prompt" />
          </Form.Item>

          <Form.Item
            name="schema_prompt"
            label="格式化Prompt"
          >
            <TextArea rows={4} placeholder="请输入用于生成格式化数据的prompt" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit">
              保存
            </Button>
          </Form.Item>
        </Form>
      )
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
