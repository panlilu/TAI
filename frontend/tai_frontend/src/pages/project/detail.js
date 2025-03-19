import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Table, Button, Input, Form, Upload, Tabs, Space, Switch, Alert, Divider, Collapse, Select, InputNumber } from 'antd';
import { UploadOutlined, EyeOutlined, DeleteOutlined } from '@ant-design/icons';
import { message, App } from 'antd';
import request from '../../utils/request';
import config from '../../config';

// 添加CSS样式
const styles = {
  inheritedConfig: {
    marginBottom: '24px',
    padding: '16px',
    backgroundColor: '#f8f8f8',
    borderRadius: '4px',
  },
  configItem: {
    marginBottom: '16px',
  },
  preWrap: {
    whiteSpace: 'pre-wrap',
    backgroundColor: '#fff',
    padding: '8px',
    borderRadius: '4px',
    border: '1px solid #d9d9d9',
  }
};

const ProjectDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [articles, setArticles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [settingsForm] = Form.useForm();  // 为项目设置添加单独的 form 实例
  const [articleType, setArticleType] = useState(null); // 添加文章类型状态
  const [messageApi, contextHolder] = message.useMessage(); // 使用 message 的 hook API
  
  // 移到组件顶层的模型状态
  const [processWithLlmModels, setProcessWithLlmModels] = useState([]);
  const [imageDescriptionModels, setImageDescriptionModels] = useState([]);
  const [extractStructuredDataModels, setExtractStructuredDataModels] = useState([]);
  
  // 获取模型数据的useEffect移到组件顶层
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const processModelsData = await request.get('/tasks/process_with_llm/models');
        setProcessWithLlmModels(processModelsData);
        
        const imageDescriptionModelsData = await request.get('/tasks/convert_to_markdown/image_description_models');
        setImageDescriptionModels(imageDescriptionModelsData);
        
        const extractStructuredDataModelsData = await request.get('/tasks/extract_structured_data/models');
        setExtractStructuredDataModels(extractStructuredDataModelsData);
      } catch (error) {
        console.error('获取模型配置失败:', error);
      }
    };
    
    fetchModels();
  }, []);

  // 使用useCallback来缓存函数
  const fetchProject = useCallback(async () => {
    try {
      const response = await request(`/projects/${id}`);
      setProject(response);
      
      // 加载文章类型信息
      if (response.article_type_id) {
        try {
          const articleTypeData = await request.get(`/article-types/${response.article_type_id}`);
          setArticleType(articleTypeData);
        } catch (error) {
          console.error('获取文章类型失败', error);
        }
      }
      
      // 解析数值字段，确保它们是数字类型
      const processTempValue = response.config?.tasks?.process_with_llm?.temperature;
      const processMaxTokensValue = response.config?.tasks?.process_with_llm?.max_tokens;
      const processTopPValue = response.config?.tasks?.process_with_llm?.top_p;
      
      const extractTempValue = response.config?.tasks?.extract_structured_data?.temperature;
      const extractMaxTokensValue = response.config?.tasks?.extract_structured_data?.max_tokens;
      const extractTopPValue = response.config?.tasks?.extract_structured_data?.top_p;
      
      // 设置表单初始值
      settingsForm.setFieldsValue({
        name: response.name,
        auto_approve: response.auto_approve,
        
        // 设置LLM配置的初始值
        process_model: response.config?.tasks?.process_with_llm?.model || '',
        process_temperature: processTempValue !== undefined ? parseFloat(processTempValue) : 0.7,
        process_max_tokens: processMaxTokensValue !== undefined ? parseInt(processMaxTokensValue) : 2000,
        process_top_p: processTopPValue !== undefined ? parseFloat(processTopPValue) : 0.95,
        
        // 从process_with_llm中获取prompt
        process_prompt: response.config?.tasks?.process_with_llm?.prompt || '',
        review_criteria: response.config?.review_criteria || '',

        
        // Markdown转换相关配置
        markdown_conversion_type: response.config?.tasks?.convert_to_markdown?.conversion_type || 'simple',
        enable_image_description: response.config?.tasks?.convert_to_markdown?.enable_image_description || false,
        image_description_model: response.config?.tasks?.convert_to_markdown?.image_description_model || '',
        
        // 结构化数据提取相关配置
        extract_structured_data_model: response.config?.tasks?.extract_structured_data?.model || '',
        extract_structured_data_temperature: extractTempValue !== undefined ? parseFloat(extractTempValue) : 0.7,
        extract_structured_data_max_tokens: extractMaxTokensValue !== undefined ? parseInt(extractMaxTokensValue) : 2000,
        extract_structured_data_top_p: extractTopPValue !== undefined ? parseFloat(extractTopPValue) : 0.95,
        extract_structured_data_extraction_prompt: response.config?.tasks?.extract_structured_data?.extraction_prompt || ''
      });
      
      console.log('获取到的项目数据:', response);
      console.log('表单初始值:', settingsForm.getFieldsValue());
    } catch (error) {
      console.error('获取项目详情失败:', error);
      messageApi.error('获取项目详情失败');
    }
  }, [id, settingsForm, messageApi]);

  const fetchArticles = useCallback(async () => {
    try {
      const response = await request('/articles?project_id=' + id);
      // 只显示属于当前项目的文章
      setArticles(response);
    } catch (error) {
      messageApi.error('获取文章列表失败');
    }
  }, [id, messageApi]);

  useEffect(() => {
    fetchProject();
    fetchArticles();
  }, [id, fetchProject, fetchArticles]);

  // 删除文章
  const handleDeleteArticle = async (articleId) => {
    try {
      await request(`/articles/${articleId}`, {
        method: 'DELETE',
      });
      messageApi.success('删除文章成功');
      fetchArticles();
    } catch (error) {
      messageApi.error('删除文章失败');
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
        messageApi.success(`${info.file.name} 上传成功`);
        fetchArticles();
      } else if (info.file.status === 'error') {
        setUploading(false);
        messageApi.error(`${info.file.name} 上传失败`);
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
      // 详细打印表单的所有字段值
      console.log('表单字段详细值:');
      console.log('基本信息:', {
        name: values.name,
        auto_approve: values.auto_approve
      });
      console.log('LLM处理配置:', {
        process_model: values.process_model,
        process_temperature: values.process_temperature,
        process_max_tokens: values.process_max_tokens,
        process_top_p: values.process_top_p,
        process_prompt: values.process_prompt
      });
      console.log('Markdown转换配置:', {
        markdown_conversion_type: values.markdown_conversion_type,
        enable_image_description: values.enable_image_description,
        image_description_model: values.image_description_model
      });
      console.log('结构化数据提取配置:', {
        extract_structured_data_model: values.extract_structured_data_model,
        extract_structured_data_temperature: values.extract_structured_data_temperature,
        extract_structured_data_max_tokens: values.extract_structured_data_max_tokens,
        extract_structured_data_top_p: values.extract_structured_data_top_p,
        extract_structured_data_extraction_prompt: values.extract_structured_data_extraction_prompt
      });
      console.log('审阅标准:', {
        review_criteria: values.review_criteria
      });
      
      // 创建一个完整的config对象，确保所有字段都有有效值
      const processWithLlm = {
        model: values.process_model || '',
        temperature: parseFloat(values.process_temperature) || 0.7,
        max_tokens: parseInt(values.process_max_tokens) || 2000,
        top_p: parseFloat(values.process_top_p) || 0.95,
      };
      
      // 仅当有值时添加prompt字段
      if (values.process_prompt !== undefined && values.process_prompt !== null) {
        processWithLlm.prompt = values.process_prompt;
      }
      
      const convertToMarkdown = {
        conversion_type: values.markdown_conversion_type || 'simple',
        enable_image_description: Boolean(values.enable_image_description),
      };
      
      // 仅当启用图片描述时添加模型
      if (values.enable_image_description && values.image_description_model) {
        convertToMarkdown.image_description_model = values.image_description_model;
      }
      
      const extractStructuredData = {
        model: values.extract_structured_data_model || '',
        temperature: parseFloat(values.extract_structured_data_temperature) || 0.7,
        max_tokens: parseInt(values.extract_structured_data_max_tokens) || 2000,
        top_p: parseFloat(values.extract_structured_data_top_p) || 0.95,
      };
      
      // 仅当有值时添加提取提示词字段
      if (values.extract_structured_data_extraction_prompt !== undefined && 
          values.extract_structured_data_extraction_prompt !== null) {
        extractStructuredData.extraction_prompt = values.extract_structured_data_extraction_prompt;
      }
      
      // 构建完整的config对象
      const config = {
        tasks: {
          process_with_llm: processWithLlm,
          convert_to_markdown: convertToMarkdown,
          extract_structured_data: extractStructuredData
        }
      };
      
      // 添加可选字段
      if (values.review_criteria !== undefined && values.review_criteria !== null) {
        config.review_criteria = values.review_criteria;
      }
      
      // 打印提交的数据，用于调试
      console.log('提交的表单数据:', values);
      console.log('提交的config数据:', config);

      const formData = {
        name: values.name,
        config: config,
        auto_approve: values.auto_approve !== undefined ? values.auto_approve : true
      };

      await request.put(`/projects/${id}`, formData);
      messageApi.success('更新成功');
      fetchProject();
    } catch (error) {
      console.error('更新失败：', error);
      messageApi.error(`更新失败: ${error.message || '未知错误'}`);
    }
  };

  // 渲染继承的配置
  const renderInheritedConfig = () => {
    if (!articleType) return null;
    
    return (
      <div style={styles.inheritedConfig} className="inherited-config">
        <h4>继承自文章类型的配置</h4>
        <Divider />
        
        {articleType.config?.tasks?.process_with_llm?.prompt && (
          <div style={styles.configItem} className="config-item">
            <h5>LLM审阅提示词</h5>
            <div style={styles.preWrap} className="pre-wrap">{articleType.config.tasks.process_with_llm.prompt}</div>
          </div>
        )}
        {articleType?.config?.tasks?.process_with_llm?.prompt && (
          <Alert 
            message="提示词已从文章类型继承" 
            description="如果设置了新的提示词，将覆盖从文章类型继承的提示词。" 
            type="info" 
            showIcon 
            style={{ marginBottom: '20px' }}
          />
        )}
        
        {articleType.config?.tasks?.extract_structured_data?.extraction_prompt && (
          <div style={styles.configItem} className="config-item">
            <h5>结构化数据提取提示词</h5>
            <div style={styles.preWrap} className="pre-wrap">{articleType.config.tasks.extract_structured_data.extraction_prompt}</div>
          </div>
        )}
        {articleType?.config?.tasks?.extract_structured_data?.extraction_prompt && (
          <Alert 
            message="结构化数据提取提示词已从文章类型继承" 
            description="如果设置了新的提取提示词，将覆盖从文章类型继承的提取提示词。" 
            type="info" 
            showIcon 
            style={{ marginBottom: '20px' }}
          />
        )}
        
        {articleType.config?.tasks?.convert_to_markdown?.conversion_type && (
          <div style={styles.configItem} className="config-item">
            <h5>Markdown转换类型</h5>
            <div style={styles.preWrap}>{articleType.config.tasks.convert_to_markdown.conversion_type === 'simple' ? '简单模式' : '高级模式'}</div>
          </div>
        )}
      </div>
    );
  };

  // 渲染项目设定
  const renderProjectSettings = () => {
    if (!project) {
      return <div>加载中...</div>;
    }
    
    // 不再在这里定义模型状态和加载数据，使用组件顶层的状态
    
    // 项目设置相关的Collapse项
    const configCollapseItems = [
      {
        key: 'markdown_conversion',
        label: 'Markdown转换配置',
        children: (
          <>
            <Form.Item
              name="markdown_conversion_type"
              label="Markdown转换类型"
              help="选择文档转换为Markdown的方式，高级模式需要配置Mistral API Key"
            >
              <Select 
                placeholder="选择转换类型"
                onChange={(value) => {
                  // 如果切换到简单模式，自动禁用图片描述
                  if (value !== 'advanced' && settingsForm) {
                    settingsForm.setFieldsValue({ enable_image_description: false });
                  }
                }}
              >
                <Select.Option value="simple">简单模式（默认）</Select.Option>
                <Select.Option value="advanced">高级模式（支持OCR和图片描述）</Select.Option>
              </Select>
            </Form.Item>
            
            <Form.Item
              shouldUpdate={(prevValues, currentValues) => 
                prevValues.markdown_conversion_type !== currentValues.markdown_conversion_type
              }
            >
              {({ getFieldValue }) => {
                const conversionType = getFieldValue('markdown_conversion_type');
                const showImageDescriptionOptions = conversionType === 'advanced';
                
                return showImageDescriptionOptions ? (
                  <>
                    <Form.Item
                      name="enable_image_description"
                      label="启用图片描述"
                      valuePropName="checked"
                      help="启用后会使用AI生成图片描述"
                    >
                      <Switch onChange={(checked) => {
                        // 如果禁用了图片描述，清空模型选择
                        if (!checked && settingsForm) {
                          settingsForm.setFieldsValue({ image_description_model: '' });
                        }
                      }} />
                    </Form.Item>
                    
                    <Form.Item
                      shouldUpdate={(prevValues, currentValues) => 
                        prevValues.enable_image_description !== currentValues.enable_image_description
                      }
                    >
                      {({ getFieldValue }) => {
                        const isEnabled = getFieldValue('enable_image_description');
                        return (
                          <Form.Item
                            name="image_description_model"
                            label="图片描述模型"
                            help="选择用于生成图片描述的模型"
                            rules={[
                              { 
                                required: isEnabled, 
                                message: '启用图片描述时，请选择模型' 
                              }
                            ]}
                          >
                            <Select 
                              placeholder="选择模型"
                              disabled={!isEnabled}
                            >
                              {imageDescriptionModels.map(model => (
                                <Select.Option key={model.id} value={model.id}>
                                  {model.name} - {model.description}
                                </Select.Option>
                              ))}
                            </Select>
                          </Form.Item>
                        );
                      }}
                    </Form.Item>
                  </>
                ) : null;
              }}
            </Form.Item>
          </>
        )
      },
      {
        key: 'process_llm',
        label: '大模型审阅配置',
        children: (
          <>
            <Form.Item
              name="process_prompt"
              label="审阅提示词"
              rules={[{ required: true, message: '请输入提示词' }]}
              help="设定AI审阅时的主要提示词，将被项目继承"
            >
              <Input.TextArea rows={6} placeholder="请输入提示词" />
            </Form.Item>

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
          </>
        )
      },
      {
        key: 'extract_structured_data',
        label: '结构化数据提取配置',
        children: (
          <>
            <Form.Item
              name="extract_structured_data_model"
              label="数据提取模型"
              help="选择用于结构化数据提取任务的模型"
            >
              <Select placeholder="选择模型">
                {extractStructuredDataModels.map(model => (
                  <Select.Option key={model.id} value={model.id}>
                    {model.name} - {model.description}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>

            <div style={{ display: 'flex', gap: '16px' }}>
              <Form.Item
                name="extract_structured_data_temperature"
                label="温度"
                style={{ flex: 1 }}
                help="控制输出的随机性，值越低越确定"
              >
                <InputNumber min={0} max={1} step={0.1} />
              </Form.Item>

              <Form.Item
                name="extract_structured_data_max_tokens"
                label="最大Token数"
                style={{ flex: 1 }}
                help="生成文本的最大长度"
              >
                <InputNumber min={100} max={8000} step={100} />
              </Form.Item>

              <Form.Item
                name="extract_structured_data_top_p"
                label="Top P"
                style={{ flex: 1 }}
                help="控制输出的多样性"
              >
                <InputNumber min={0} max={1} step={0.05} />
              </Form.Item>
            </div>

            <Form.Item
              name="extract_structured_data_extraction_prompt"
              label="提取提示词"
              help="用于指导结构化数据提取的提示词"
            >
              <Input.TextArea rows={6} placeholder="请输入提示词" />
            </Form.Item>
          </>
        )
      }
    ];
    
    return (
      <Card title="项目设定" bordered={false}>
        {renderInheritedConfig()}
        
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

          <Collapse 
            defaultActiveKey={['markdown_conversion', 'process_llm']} 
            items={configCollapseItems}
          />

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
      label: '项目设定',
      children: renderProjectSettings()
    }
  ];

  if (!project) {
    return <div>加载中...</div>;
  }

  return (
    <App>
      {contextHolder}
      <div style={{ padding: '24px' }}>
        <Card title={project.name}>
          <Tabs defaultActiveKey="1" items={items} />
        </Card>
      </div>
    </App>
  );
};

export default ProjectDetail;
