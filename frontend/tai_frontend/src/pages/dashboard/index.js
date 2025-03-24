import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Spin, Typography } from 'antd';
import { FileTextOutlined, ProjectOutlined, AppstoreOutlined, ScheduleOutlined, LoadingOutlined, FileSyncOutlined } from '@ant-design/icons';
import request from '../../utils/request';
import './style.css';

const { Title } = Typography;

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await request.get('/user/stats');
        setStats(response);
      } catch (error) {
        console.error('获取统计数据失败:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '50px' }}>
        <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
        <p style={{ marginTop: 16 }}>加载中...</p>
      </div>
    );
  }

  return (
    <div className="dashboard-container" style={{ padding: isMobile ? '8px' : '16px' }}>
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} md={8} lg={8} xl={8}>
          <Card hoverable style={{ height: '100%' }}>
            <Statistic
              title="我的文章"
              value={stats?.article_count || 0}
              prefix={<FileTextOutlined style={{ color: '#3f8600' }} />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={8} xl={8}>
          <Card hoverable style={{ height: '100%' }}>
            <Statistic
              title="我的项目"
              value={stats?.project_count || 0}
              prefix={<ProjectOutlined style={{ color: '#1890ff' }} />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={8} lg={8} xl={8}>
          <Card hoverable style={{ height: '100%' }}>
            <Statistic
              title="可用文章类型"
              value={stats?.article_type_count || 0}
              prefix={<AppstoreOutlined style={{ color: '#722ed1' }} />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} sm={12} md={12} lg={12} xl={12}>
          <Card hoverable style={{ height: '100%' }}>
            <Statistic
              title="任务总数"
              value={stats?.total_jobs || 0}
              prefix={<ScheduleOutlined style={{ color: '#cf1322' }} />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={12} lg={12} xl={12}>
          <Card hoverable style={{ height: '100%' }}>
            <Statistic
              title="进行中任务"
              value={stats?.active_jobs || 0}
              prefix={<FileSyncOutlined style={{ color: '#faad14' }} />}
              valueStyle={{ color: '#faad14' }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
