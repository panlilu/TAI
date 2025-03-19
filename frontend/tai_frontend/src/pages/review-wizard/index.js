import React, { useState, useEffect, useRef } from 'react';
import { Steps, Button, Form, Select, Upload, message, Input } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import request from '../../utils/request';
import './style.css';

const { Step } = Steps;
const { Option } = Select;

const getArticleTypes = async (q) => {
  return await request.get('/article-types?q='+q);
}

const getProject = async (id) => {
  return await request.get('/projects/'+id);
}

const createProject = async (articleTypeId) => {
  return await request.post('/projects', {
    article_type_id: articleTypeId
  });
}

const updateProject = async (id, data) => {
  return await request.put(`/projects/${id}`, data);
}

const uploadFile = async (projectId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return await request.post(`/jobs_upload?project_id=${projectId}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
}

const ReviewWizard = () => {
  const [current, setCurrent] = useState(0);
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [articleTypes, setArticleTypes] = useState([]);
  const [projectId, setProjectId] = useState(null);
  const prevArticleTypeId = useRef(null);

  const handleSearch = async (q) => {
    try {
      setLoading(true);
      const data = await getArticleTypes(q);
      setArticleTypes(data);
    } catch (error) {
      console.log(error);
      message.error('获取文章类型失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleSearch('');
  }, []);

  useEffect(() => {
    if (current === 1 && projectId) {
      const fetchProject = async () => {
        try {
          const project = await getProject(projectId);
          form.setFieldsValue({
            projectName: project.name,
            prompt: project.config?.tasks?.process_with_llm?.prompt || '',
          });
        } catch (error) {
          console.log(error);
          message.error('获取项目信息失败');
        }
      };
      fetchProject();
    }
  }, [current, projectId, form]);

  const steps = [
    {
      title: '选择文章类型',
      content: (
        <Form.Item
          name="articleType"
          label="文章类型"
          rules={[{ required: true, message: '请选择文章类型' }]}
        >
          <Select
            showSearch
            placeholder="请选择文章类型"
            filterOption={false}
            onSearch={handleSearch}
            loading={loading}
          >
            {articleTypes.map(type => (
              <Option key={type.id} value={type.id}>
                {type.name}
              </Option>
            ))}
          </Select>
        </Form.Item>
      ),
    },
    {
      title: '修改项目参数',
      content: (
        <>
          <Form.Item
            name="projectName"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="请输入项目名称" />
          </Form.Item>
          <Form.Item
            name="prompt"
            label="提示"
            rules={[{ required: true, message: '请输入提示' }]}
          >
            <Input.TextArea rows={4} placeholder="请输入提示" />
          </Form.Item>
        </>
      ),
    },
    {
      title: '上传文章',
      content: (
        <Form.Item
          name="file"
          label="上传文件"
          valuePropName="fileList"
          getValueFromEvent={(e) => e.fileList}
          rules={[{ required: true, message: '请上传文件' }]}
        >
          <Upload
            beforeUpload={() => false}
            multiple
            accept=".doc,.docx,.pdf"
          >
            <Button icon={<UploadOutlined />}>上传文件</Button>
          </Upload>
        </Form.Item>
      ),
    },
    {
      title: '完成',
      content: '审阅结果将在此显示',
    },
  ];

  const next = async () => {
    try {
      await form.validateFields();
      
      const values = form.getFieldsValue();
      const currentArticleTypeId = values.articleType;
      
      // 如果文章类型发生变化，创建新项目
      if (current === 0) {
        if (currentArticleTypeId !== prevArticleTypeId.current) {
          const project = await createProject(currentArticleTypeId);
          setProjectId(project.id);
          prevArticleTypeId.current = currentArticleTypeId;
        }
      }
      
      // 如果是第二步，保存项目参数
      if (current === 1) {
        const { projectName, prompt } = values;
        await updateProject(projectId, {
          name: projectName,
          config: {
            tasks: {
              process_with_llm: {
                prompt: prompt
              }
            }
          }
        });
      }
      
      // 如果是第三步,上传文件
      if (current === 2) {
        const { file } = values;
        const fileList = file || [];
        
        // 使用Promise.all同时上传多个文件
        await Promise.all(fileList.map(fileItem => 
          uploadFile(projectId, fileItem.originFileObj)
        ));
      }
      setCurrent(current + 1);
    } catch (error) {
      console.log(error);
      message.error('请先完成当前步骤');
    }
  };

  const prev = () => {
    setCurrent(current - 1);
  };

  return (
    <div className="review-wizard-container">
      <Steps current={current}>
        {steps.map((item) => (
          <Step key={item.title} title={item.title} />
        ))}
      </Steps>

      <div className="steps-content">
        <Form form={form} layout="vertical">
          {steps[current].content}
        </Form>
      </div>

      <div className="steps-action">
        {(
          <Button style={{ margin: '0 8px' }} onClick={prev}>
            上一步
          </Button>
        )}
        {current < steps.length - 1 && (
          <Button type="primary" onClick={next}>
            下一步
          </Button>
        )}
        {current === steps.length - 1 && (
          <Button type="primary" onClick={() => message.success('处理完成!')}>
            完成
          </Button>
        )}
      </div>
    </div>
  );
};

export default ReviewWizard;
