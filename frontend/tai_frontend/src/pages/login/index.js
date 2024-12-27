import React from 'react';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { login } from '../../services/auth';
import request from '../../utils/request';
import './style.css';

const LoginPage = () => {
  const navigate = useNavigate();
  const [messageApi, contextHolder] = message.useMessage();

  const onFinish = async (values) => {
    try {
      const response = await login(values);
      localStorage.setItem('token', response.access_token);
      // 获取用户信息
      const userResponse = await request({
        url: '/users/me',
        method: 'get'
      });
      localStorage.setItem('userRole', userResponse.role);
      messageApi.success('登录成功！');
      navigate('/dashboard');
    } catch (error) {
      console.error('Login error:', error);
      // 使用统一处理后的错误信息
      messageApi.error(error.message || '登录失败，请检查用户名和密码');
    }
  };

  return (
    <div className="login-container">
      {contextHolder}
      <div className="login-form">
        <h1>Teaching Assistant AI</h1>
        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
          onFinishFailed={({ values, errorFields, outOfDate }) => {
            // 处理表单验证失败的情况
            messageApi.error('请正确填写表单');
          }}
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名！' }]}
          >
            <Input 
              prefix={<UserOutlined />} 
              placeholder="用户名" 
              size="large"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码！' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              size="large"
            />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" block size="large">
              登录
            </Button>
          </Form.Item>
          
          <Form.Item>
            <Button type="link" block onClick={() => navigate('/register')}>
              还没有账号？立即注册
            </Button>
          </Form.Item>
        </Form>
      </div>
    </div>
  );
};

export default LoginPage;
