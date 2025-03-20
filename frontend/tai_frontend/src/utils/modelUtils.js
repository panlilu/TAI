import request from './request';

/**
 * 获取特定任务类型的可用模型
 * @param {string} taskType - 任务类型，例如: 'process_with_llm', 'extract_structured_data'
 * @returns {Promise<Array>} - 模型列表
 */
export const getTaskModels = async (taskType) => {
  try {
    return await request.get(`/tasks/${taskType}/models`);
  } catch (error) {
    console.error(`获取${taskType}模型失败:`, error);
    return [];
  }
};

/**
 * 获取图片描述模型
 * @returns {Promise<Array>} - 图片描述模型列表
 */
export const getImageDescriptionModels = async () => {
  try {
    return await request.get('/tasks/convert_to_markdown/image_description_models');
  } catch (error) {
    console.error('获取图片描述模型失败:', error);
    return [];
  }
};

/**
 * 获取所有常用模型数据
 * @returns {Promise<Object>} - 包含各类模型数据的对象
 */
export const getAllModels = async () => {
  try {
    const [processModels, imageDescriptionModels, extractModels] = await Promise.all([
      getTaskModels('process_with_llm'),
      getImageDescriptionModels(),
      getTaskModels('extract_structured_data')
    ]);
    
    return {
      processModels,
      imageDescriptionModels,
      extractModels
    };
  } catch (error) {
    console.error('获取模型数据失败:', error);
    return {
      processModels: [],
      imageDescriptionModels: [],
      extractModels: []
    };
  }
};

export default {
  getTaskModels,
  getImageDescriptionModels,
  getAllModels
}; 