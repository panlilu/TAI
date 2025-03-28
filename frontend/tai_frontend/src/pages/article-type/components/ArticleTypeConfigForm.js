import React, { useState, useEffect, useCallback } from 'react';
import { Form, Select, Input, InputNumber, Switch, Collapse } from 'antd';
import { getTaskModels, getImageDescriptionModels } from '../../../utils/modelUtils';

const ArticleTypeConfigForm = ({ 
  form, 
  showBasicSettings = true,
  externalProcessModels = null,
  externalExtractModels = null,
  externalImageModels = null
}) => {
  const [processWithLlmModels, setProcessWithLlmModels] = useState([]);
  const [imageDescriptionModels, setImageDescriptionModels] = useState([]);
  const [extractStructuredDataModels, setExtractStructuredDataModels] = useState([]);
  const [loading, setLoading] = useState(false);
  
  const fetchModels = useCallback(async () => {
    try {
      setLoading(true);
      
      // 只获取未提供的模型数据
      const fetchPromises = [];
      
      if (!externalProcessModels) {
        fetchPromises.push(
          getTaskModels('process_with_llm')
            .then(data => setProcessWithLlmModels(data))
        );
      }
      
      // 只有当外部没有提供图片描述模型时才获取
      if (!externalImageModels) {
        fetchPromises.push(
          getImageDescriptionModels()
            .then(data => setImageDescriptionModels(data))
        );
      }
      
      if (!externalExtractModels) {
        fetchPromises.push(
          getTaskModels('extract_structured_data')
            .then(data => setExtractStructuredDataModels(data))
        );
      }
      
      await Promise.all(fetchPromises);
    } catch (error) {
      console.error('获取模型配置失败:', error);
    } finally {
      setLoading(false);
    }
  }, [externalProcessModels, externalExtractModels, externalImageModels]);

  useEffect(() => {
    // 如果外部提供了模型数据，优先使用外部数据
    if (externalProcessModels) {
      setProcessWithLlmModels(externalProcessModels);
    }
    if (externalExtractModels) {
      setExtractStructuredDataModels(externalExtractModels);
    }
    if (externalImageModels) {
      setImageDescriptionModels(externalImageModels);
    }
    
    // 如果外部没有提供数据，则自行获取
    if (!externalProcessModels || !externalExtractModels || !externalImageModels) {
      fetchModels();
    }
  }, [externalProcessModels, externalExtractModels, externalImageModels, fetchModels]);

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
            name={["tasks", "convert_to_markdown", "conversion_type"]}
            label="Markdown转换类型"
            help="选择文档转换为Markdown的方式，高级模式需要配置Mistral API Key"
          >
            <Select 
              placeholder="选择转换类型"
              onChange={(value) => {
                // 如果切换到简单模式，自动禁用图片描述
                if (value !== 'advanced' && form) {
                  form.setFieldsValue({ 
                    tasks: { 
                      convert_to_markdown: { 
                        enable_image_description: false 
                      } 
                    } 
                  });
                }
              }}
            >
              <Select.Option value="simple">简单模式（默认）</Select.Option>
              <Select.Option value="advanced">高级模式（支持OCR和图片描述）</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item
            shouldUpdate={(prevValues, currentValues) => {
              const prevType = prevValues?.tasks?.convert_to_markdown?.conversion_type;
              const currentType = currentValues?.tasks?.convert_to_markdown?.conversion_type;
              return prevType !== currentType;
            }}
          >
            {({ getFieldValue }) => {
              const conversionType = getFieldValue(['tasks', 'convert_to_markdown', 'conversion_type']);
              const showImageDescriptionOptions = conversionType === 'advanced';
              
              return showImageDescriptionOptions ? (
                <>
                  <Form.Item
                    name={["tasks", "convert_to_markdown", "enable_image_description"]}
                    label="启用图片描述"
                    valuePropName="checked"
                    help="启用后会使用AI生成图片描述"
                  >
                    <Switch onChange={(checked) => {
                      // 如果禁用了图片描述，清空模型选择
                      if (!checked && form) {
                        form.setFieldsValue({ 
                          tasks: { 
                            convert_to_markdown: { 
                              image_description_model: '' 
                            } 
                          } 
                        });
                      }
                    }} />
                  </Form.Item>
                  
                  <Form.Item
                    shouldUpdate={(prevValues, currentValues) => {
                      const prevEnabled = prevValues?.tasks?.convert_to_markdown?.enable_image_description;
                      const currentEnabled = currentValues?.tasks?.convert_to_markdown?.enable_image_description;
                      return prevEnabled !== currentEnabled;
                    }}
                  >
                    {({ getFieldValue }) => {
                      const isEnabled = getFieldValue(['tasks', 'convert_to_markdown', 'enable_image_description']);
                      return (
                        <Form.Item
                          name={["tasks", "convert_to_markdown", "image_description_model"]}
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
                            loading={loading}
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
                  
                  <Form.Item
                    shouldUpdate={(prevValues, currentValues) => {
                      const prevEnabled = prevValues?.tasks?.convert_to_markdown?.enable_image_description;
                      const currentEnabled = currentValues?.tasks?.convert_to_markdown?.enable_image_description;
                      return prevEnabled !== currentEnabled;
                    }}
                  >
                    {({ getFieldValue }) => (
                      <Form.Item
                        name={["tasks", "convert_to_markdown", "max_images"]}
                        label="图片描述上限"
                        help="最多处理的图片数量，超过将被忽略"
                        initialValue={10}
                      >
                        <InputNumber 
                          min={1} 
                          disabled={!getFieldValue(['tasks', 'convert_to_markdown', 'enable_image_description'])}
                          placeholder="默认10张" 
                          style={{ width: '100%' }} 
                        />
                      </Form.Item>
                    )}
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
    <Collapse defaultActiveKey={['process_llm', 'markdown_conversion', 'extract_structured_data']} items={collapseItems} />
  );
};

export default ArticleTypeConfigForm; 