import React, { useState, useEffect } from 'react';
import { Layout, Menu, Button, Drawer } from 'antd';
import {
  UserOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  FileTextOutlined,
  ScheduleOutlined,
  ProjectOutlined,
  DashboardOutlined,
  MenuOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Header, Sider, Content } = Layout;

const MainLayout = ({ children }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const userRole = localStorage.getItem('userRole');

  // 检测屏幕尺寸
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const menuItems = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: '仪表盘',
    },
    {
      key: '/review-wizard',
      icon: <ProjectOutlined />,
      label: '审阅向导',
    },
    {
      key: '/project',
      icon: <ProjectOutlined />,
      label: '项目管理',
    },
    {
      key: '/article-type',
      icon: <FileTextOutlined />,
      label: '文章类型',
    },
    {
      key: '/jobs',
      icon: <ScheduleOutlined />,
      label: '任务管理',
    },
    ...(userRole === 'admin' ? [
      {
        key: '/user',
        icon: <UserOutlined />,
        label: '用户管理',
      }
    ] : [])
  ];

  const onMenuClick = ({ key }) => {
    navigate(key);
    if (isMobile) {
      setDrawerVisible(false);
    }
  };

  // 移动端布局
  if (isMobile) {
    return (
      <Layout style={{ minHeight: '100vh' }}>
        <Header style={{ 
          padding: '0 16px', 
          background: '#fff', 
          display: 'flex', 
          alignItems: 'center',
          justifyContent: 'space-between' 
        }}>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ marginRight: '8px' }}>
              <rect x="6" y="5" width="20" height="22" rx="2" stroke="#1890ff" strokeWidth="2" fill="#fff"/>
              <path d="M10 10H22" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M10 14H22" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M10 18H18" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M10 22H16" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <span style={{ fontSize: '18px', fontWeight: 'bold' }}>TAI</span>
          </div>
          <Button 
            type="text" 
            icon={<MenuOutlined />} 
            onClick={() => setDrawerVisible(true)} 
          />
        </Header>
        <Content style={{ margin: '8px', padding: '16px', background: '#fff' }}>
          {children}
        </Content>
        <Drawer
          title="菜单"
          placement="left"
          closable={true}
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
          bodyStyle={{ padding: 0 }}
          width={250}
        >
          <Menu
            theme="light"
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={onMenuClick}
            style={{ height: '100%' }}
          />
        </Drawer>
      </Layout>
    );
  }

  // 桌面端布局
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider trigger={null} collapsible collapsed={collapsed}>
        <div className="logo-container" style={{ 
          height: '64px', 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center',
          padding: '16px',
          background: '#001529'
        }}>
          {collapsed ? (
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="6" y="5" width="20" height="22" rx="2" stroke="#1890ff" strokeWidth="2" fill="#001529"/>
              <path d="M10 10H22" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M10 14H22" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M10 18H18" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
              <path d="M10 22H16" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ marginRight: '8px' }}>
                <rect x="6" y="5" width="20" height="22" rx="2" stroke="#1890ff" strokeWidth="2" fill="#001529"/>
                <path d="M10 10H22" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
                <path d="M10 14H22" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
                <path d="M10 18H18" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
                <path d="M10 22H16" stroke="#1890ff" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              <span style={{ color: '#fff', fontSize: '18px', fontWeight: 'bold' }}>TAI</span>
            </div>
          )}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={onMenuClick}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: 0, background: '#fff' }}>
          {React.createElement(collapsed ? MenuUnfoldOutlined : MenuFoldOutlined, {
            className: 'trigger',
            onClick: () => setCollapsed(!collapsed),
            style: { fontSize: '18px', padding: '0 24px', cursor: 'pointer' }
          })}
        </Header>
        <Content style={{ margin: '24px 16px', padding: 24, background: '#fff' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default MainLayout;
