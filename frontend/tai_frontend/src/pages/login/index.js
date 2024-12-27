import React from 'react';
import { Form, Input, Button, message } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { login } from '../../services/auth';
import request from '../../utils/request';
import './style.css';

const LoginPage = () => {
  const navigate = useNavigate();

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
      message.success('登录成功！');
      navigate('/dashboard');
    } catch (error) {
      message.error(error.response?.data?.detail || '登录失败，请重试');
    }
  };

  return (
    <div className="login-container">
      <div className="login-form">
        <h1>系统登录</h1>
        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
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
