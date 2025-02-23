import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';

import MainLayout from './layouts/MainLayout';
import LoginPage from './pages/login';
import RegisterPage from './pages/register';
import HomePage from './pages/home';
import Dashboard from './pages/dashboard';
import UserManagement from './pages/user';
import ArticleType from './pages/article-type';
import Jobs from './pages/jobs';
import ProjectList from './pages/project';
import ProjectDetail from './pages/project/detail';
import ArticleViewer from './pages/project/article';
import ReviewWizard from './pages/review-wizard';
import AuthRoute from './components/AuthRoute';
import { eventService } from './utils/eventService';
import { getToken } from './utils/auth';

import './App.css';

function App() {
  useEffect(() => {
    const token = getToken();
    if (token) {
      eventService.connect();
    }
    
    return () => {
      eventService.disconnect();
    };
  }, []);

  return (
    <ConfigProvider locale={zhCN}>
      <Router>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          
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

          <Route
            path="/article-type"
            element={
              <AuthRoute requiredRole="admin">
                <MainLayout>
                  <ArticleType />
                </MainLayout>
              </AuthRoute>
            }
          />

          <Route
            path="/jobs"
            element={
              <AuthRoute>
                <MainLayout>
                  <Jobs />
                </MainLayout>
              </AuthRoute>
            }
          />

          <Route
            path="/project"
            element={
              <AuthRoute>
                <MainLayout>
                  <ProjectList />
                </MainLayout>
              </AuthRoute>
            }
          />

          <Route
            path="/project/:id"
            element={
              <AuthRoute>
                <MainLayout>
                  <ProjectDetail />
                </MainLayout>
              </AuthRoute>
            }
          />

          <Route
            path="/project/:projectId/articles/:articleId"
            element={
              <AuthRoute>
                <MainLayout>
                  <ArticleViewer />
                </MainLayout>
              </AuthRoute>
            }
          />

          <Route
            path="/review-wizard"
            element={
              <AuthRoute>
                <MainLayout>
                  <ReviewWizard />
                </MainLayout>
              </AuthRoute>
            }
          />

          <Route path="/" element={<HomePage />} />
        </Routes>
      </Router>
    </ConfigProvider>
  );
}

export default App;
