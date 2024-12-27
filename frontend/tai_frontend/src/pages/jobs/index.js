import React, { useState, useEffect } from 'react';
import { Table, Button, message, Space, Progress } from 'antd';
import { 
  ReloadOutlined, 
  PauseCircleOutlined, 
  PlayCircleOutlined,
  StopOutlined
} from '@ant-design/icons';
import request from '../../utils/request';

const Jobs = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await request.get('/jobs'); // 默认按id倒序
      setData(response);
    } catch (error) {
      message.error('获取任务列表失败');
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
    // 定期刷新任务状态
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleRetry = async (id) => {
    try {
      await request.post(`/jobs/${id}/retry`);
      message.success('重试任务成功');
      fetchData();
    } catch (error) {
      message.error('重试任务失败');
    }
  };

  const handlePause = async (id) => {
    try {
      await request.post(`/jobs/${id}/pause`);
      message.success('暂停任务成功');
      fetchData();
    } catch (error) {
      message.error('暂停任务失败');
    }
  };

  const handleResume = async (id) => {
    try {
      await request.post(`/jobs/${id}/resume`);
      message.success('启动任务成功');
      fetchData();
    } catch (error) {
      message.error('启动任务失败');
    }
  };

  const handleCancelAll = async () => {
    try {
      await request.post('/jobs/cancel-all');
      message.success('取消所有任务成功');
      fetchData();
    } catch (error) {
      message.error('取消所有任务失败');
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id'
    },
    {
      title: '任务名称',
      dataIndex: 'task',
      key: 'task',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => {
        const statusMap = {
          pending: '等待中',
          running: '运行中',
          completed: '已完成',
          failed: '失败',
          paused: '已暂停',
          cancelled: '已取消'
        };
        return statusMap[status] || status;
      },
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      render: (progress) => (
        <Progress percent={Math.round(progress * 100)} size="small" />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time) => new Date(time).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <Space>
          {record.status === 'failed' && (
            <Button
              type="link"
              icon={<ReloadOutlined />}
              onClick={() => handleRetry(record.id)}
            >
              重试
            </Button>
          )}
          {record.status === 'running' && (
            <Button
              type="link"
              icon={<PauseCircleOutlined />}
              onClick={() => handlePause(record.id)}
            >
              暂停
            </Button>
          )}
          {record.status === 'paused' && (
            <Button
              type="link"
              icon={<PlayCircleOutlined />}
              onClick={() => handleResume(record.id)}
            >
              启动
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Button
        type="primary"
        danger
        icon={<StopOutlined />}
        onClick={handleCancelAll}
        style={{ marginBottom: 16 }}
      >
        取消全部任务
      </Button>
      <Table
        columns={columns}
        dataSource={data}
        rowKey="id"
        loading={loading}
      />
    </div>
  );
};

export default Jobs;
