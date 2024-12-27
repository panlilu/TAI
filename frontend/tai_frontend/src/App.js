import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';

import MainLayout from './layouts/MainLayout';
import LoginPage from './pages/login';
import RegisterPage from './pages/register';
import Dashboard from './pages/dashboard';
import UserManagement from './pages/user';
import AuthRoute from './components/AuthRoute';

import './App.css';

function App() {
  return (
    <ConfigProvider locale={zhCN}>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          
          {/* 需要认证的路由 */}
          <Route
            path="/dashboard"
            element={
              <AuthRoute>
                <MainLayout>
                  <Dashboard />
                </MainLayout>
              </AuthRoute>
            }
          />
          
          <Route
            path="/user"
            element={
              <AuthRoute requiredRole="admin">
                <MainLayout>
                  <UserManagement />
                </MainLayout>
              </AuthRoute>
            }
          />

          {/* 重定向到仪表盘 */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;
