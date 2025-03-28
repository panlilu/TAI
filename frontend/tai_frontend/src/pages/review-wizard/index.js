import React, { useState, useEffect, useRef } from 'react';
import { Steps, Button, Form, Select, Upload, message, Input, Row, Col, Card, Typography } from 'antd';
import { UploadOutlined, CheckCircleOutlined } from '@ant-design/icons';
import request from '../../utils/request';
import { useNavigate } from 'react-router-dom';
import './style.css';
import ArticleTypeConfigForm from '../article-type/components/ArticleTypeConfigForm';
import { getTaskModels, getImageDescriptionModels } from '../../utils/modelUtils';

const { Step } = Steps;
const { Option } = Select;
const { Title, Paragraph } = Typography;

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
  const [configFormKey, setConfigFormKey] = useState(0);
  const [processModels, setProcessModels] = useState([]);
  const [extractModels, setExtractModels] = useState([]);
  const [imageModels, setImageModels] = useState([]);
  const navigate = useNavigate();

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

  // 当文章类型列表加载完成后，设置默认选中第一个
  useEffect(() => {
    if (articleTypes.length > 0) {
      form.setFieldsValue({
        articleType: articleTypes[0].id
      });
      prevArticleTypeId.current = articleTypes[0].id;
    }
  }, [articleTypes, form]);

  // 预加载模型数据
  useEffect(() => {
    if (current === 0) {
      // 当用户在第一步时，预加载模型数据
      const preloadModels = async () => {
        try {
          const [processModelsData, extractModelsData, imageModelsData] = await Promise.all([
            getTaskModels('process_with_llm'),
            getTaskModels('extract_structured_data'),
            getImageDescriptionModels()
          ]);
          setProcessModels(processModelsData);
          setExtractModels(extractModelsData);
          setImageModels(imageModelsData);
        } catch (error) {
          console.error('预加载模型数据失败:', error);
        }
      };
      preloadModels();
    }
  }, [current]);

  useEffect(() => {
    if (current === 1 && projectId) {
      // 当切换到步骤二时，更新key强制刷新配置表单
      setConfigFormKey(prevKey => prevKey + 1);
      
      const fetchProject = async () => {
        try {
          const project = await getProject(projectId);
          
          // 如果预加载的模型数据可用，确保表单能够获取到
          form.setFieldsValue({
            projectName: project.name,
            process_prompt: project.config?.tasks?.process_with_llm?.prompt || '',
            process_model: project.config?.tasks?.process_with_llm?.model || '',
            process_temperature: project.config?.tasks?.process_with_llm?.temperature || 0.7,
            process_max_tokens: project.config?.tasks?.process_with_llm?.max_tokens || 2000,
            process_top_p: project.config?.tasks?.process_with_llm?.top_p || 0.95,
            tasks: {
              convert_to_markdown: {
                conversion_type: project.config?.tasks?.convert_to_markdown?.conversion_type || 'simple',
                enable_image_description: project.config?.tasks?.convert_to_markdown?.enable_image_description || false,
                image_description_model: project.config?.tasks?.convert_to_markdown?.image_description_model || ''
              }
            },
            extract_structured_data_model: project.config?.tasks?.extract_structured_data?.model || '',
            extract_structured_data_temperature: project.config?.tasks?.extract_structured_data?.temperature || 0.7,
            extract_structured_data_max_tokens: project.config?.tasks?.extract_structured_data?.max_tokens || 2000,
            extract_structured_data_top_p: project.config?.tasks?.extract_structured_data?.top_p || 0.95,
            extract_structured_data_extraction_prompt: project.config?.tasks?.extract_structured_data?.extraction_prompt || '',
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
            optionFilterProp="children"
            defaultActiveFirstOption
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
          <ArticleTypeConfigForm 
            key={configFormKey} 
            form={form} 
            showBasicSettings={false}
            externalProcessModels={processModels}
            externalExtractModels={extractModels}
            externalImageModels={imageModels}
          />
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
      content: (
        <Card className="complete-card">
          <Row align="middle" justify="center">
            <Col span={24} style={{ textAlign: 'center' }}>
              <CheckCircleOutlined style={{ fontSize: '64px', color: '#52c41a', marginBottom: '24px' }} />
              <Title level={3}>恭喜！您已成功提交文章进行处理</Title>
              <Paragraph>
                系统正在为您处理文章，请通过以下链接查看处理进度和结果
              </Paragraph>
              <Row gutter={16} justify="center" style={{ marginTop: '32px' }}>
                <Col>
                  <Button type="primary" size="large" onClick={() => navigate('/jobs')}>
                    查看任务进度
                  </Button>
                </Col>
                <Col>
                  <Button size="large" onClick={() => navigate(`/project/${projectId}`)}>
                    查看项目详情
                  </Button>
                </Col>
              </Row>
            </Col>
          </Row>
        </Card>
      ),
    },
  ];

  const next = async () => {
    try {
      await form.validateFields();
      
      const values = form.getFieldsValue();
      const currentArticleTypeId = values.articleType;
      
      // 在第一步，始终创建新项目
      if (current === 0) {
        const project = await createProject(currentArticleTypeId);
        setProjectId(project.id);
        prevArticleTypeId.current = currentArticleTypeId;
      }
      
      // 如果是第二步，保存项目参数
      if (current === 1) {
        const { 
          projectName, 
          process_prompt, 
          process_model, 
          process_temperature, 
          process_max_tokens, 
          process_top_p,
          tasks,
          extract_structured_data_model,
          extract_structured_data_temperature,
          extract_structured_data_max_tokens,
          extract_structured_data_top_p,
          extract_structured_data_extraction_prompt
        } = values;
        
        await updateProject(projectId, {
          name: projectName,
          config: {
            tasks: {
              process_with_llm: {
                prompt: process_prompt,
                model: process_model,
                temperature: process_temperature,
                max_tokens: process_max_tokens,
                top_p: process_top_p
              },
              convert_to_markdown: {
                conversion_type: tasks?.convert_to_markdown?.conversion_type || 'simple',
                enable_image_description: tasks?.convert_to_markdown?.enable_image_description,
                image_description_model: tasks?.convert_to_markdown?.image_description_model || ''
              },
              extract_structured_data: {
                model: extract_structured_data_model,
                temperature: extract_structured_data_temperature,
                max_tokens: extract_structured_data_max_tokens,
                top_p: extract_structured_data_top_p,
                extraction_prompt: extract_structured_data_extraction_prompt
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
        {current > 0 && current < steps.length - 1 && (
          <Button style={{ margin: '0 8px' }} onClick={prev}>
            上一步
          </Button>
        )}
        {current < steps.length - 1 && (
          <Button type="primary" onClick={next}>
            下一步
          </Button>
        )}
      </div>
    </div>
  );
};

export default ReviewWizard;
