import React, { useState, useEffect } from 'react';
import { Form, Select, Input, InputNumber, Switch, Collapse } from 'antd';
import request from '../../utils/request';

const ArticleTypeConfigForm = ({ form, initialValues = {}, showBasicSettings = true }) => {
  const [processWithLlmModels, setProcessWithLlmModels] = useState([]);
  const [imageDescriptionModels, setImageDescriptionModels] = useState([]);
  const [extractStructuredDataModels, setExtractStructuredDataModels] = useState([]);
  const [showImageDescriptionOptions, setShowImageDescriptionOptions] = useState(false);

  useEffect(() => {
    fetchModels();
  }, []);

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

  // 定义Collapse的items配置
  const collapseItems = [
    ...(showBasicSettings ? [{
      key: 'basic_settings',
      label: '基本设置',
      children: (
        <>
          <Form.Item
            name="name"
            label="类型名称"
            rules={[{ required: true, message: '请输入类型名称' }]}
          >
            <Input />
          </Form.Item>

          <Form.Item
            name="is_public"
            label="是否公开"
            valuePropName="checked"
          >
            <Switch />
          </Form.Item>
        </>
      )
    }] : []),
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
              onChange={(value) => setShowImageDescriptionOptions(value === 'advanced')}
            >
              <Select.Option value="simple">简单模式（默认）</Select.Option>
              <Select.Option value="advanced">高级模式（支持OCR和图片描述）</Select.Option>
            </Select>
          </Form.Item>
          
          {showImageDescriptionOptions && (
            <>
              <Form.Item
                name="enable_image_description"
                label="启用图片描述"
                valuePropName="checked"
                help="启用后会使用AI生成图片描述"
              >
                <Switch />
              </Form.Item>
              
              <Form.Item
                name="image_description_model"
                label="图片描述模型"
                help="选择用于生成图片描述的模型"
                dependencies={['enable_image_description']}
              >
                <Select 
                  placeholder="选择模型"
                  disabled={!form.getFieldValue('enable_image_description')}
                >
                  {imageDescriptionModels.map(model => (
                    <Select.Option key={model.id} value={model.id}>
                      {model.name} - {model.description}
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </>
          )}
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
            <Input.TextArea rows={6} />
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
            <Input.TextArea rows={6} />
          </Form.Item>
        </>
      )
    }
  ];

  return (
    <Collapse 
      items={collapseItems} 
      style={{ marginBottom: 16 }} 
      defaultActiveKey={['basic_settings', 'markdown_conversion', 'process_llm', 'extract_structured_data']}
    />
  );
};

export default ArticleTypeConfigForm; 