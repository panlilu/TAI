import axios from 'axios';
import config from '../config';

const request = axios.create({
  baseURL: config.apiBaseURL,
  timeout: 5000,
});

// 请求拦截器
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器
request.interceptors.response.use(
  (response) => {
    // 检查响应类型
    const contentType = response.headers['content-type'];
    // 如果是二进制数据（如文件下载），直接返回响应数据
    if (contentType && (
      contentType.includes('application/octet-stream') || 
      contentType.includes('application/vnd.ms-excel') ||
      contentType.includes('text/csv') ||
      contentType.includes('application/zip')
    )) {
      return response.data;
    }
    // 对于JSON等数据，返回响应主体
    return response.data;
  },
  (error) => {
    // 确保错误对象包含完整的响应信息
    if (error.response) {
      error.response.data = error.response.data || {};
      // 只有在非登录页面时，401错误才自动重定向到登录页
      if (error.response.status === 401 && !window.location.pathname.includes('/login')) {
        localStorage.removeItem('token');
        localStorage.removeItem('userRole');
        window.location.href = '/login';
      }
    }
    return Promise.reject({
      ...error,
      message: error.response?.data?.detail || error.response?.data?.message || error.message
    });
  }
);

export default request;
