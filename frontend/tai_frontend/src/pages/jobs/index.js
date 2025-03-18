import React, { useState, useEffect } from 'react';
import { Table, Button, message, Space, Progress, Collapse, Tag, InputNumber, Tooltip, Modal } from 'antd';
import { 
  ReloadOutlined, 
  PauseCircleOutlined, 
  PlayCircleOutlined,
  StopOutlined,
  DownOutlined,
  RightOutlined,
  SettingOutlined,
  FileTextOutlined
} from '@ant-design/icons';
import request from '../../utils/request';

const { Panel } = Collapse;

const Jobs = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedRowKeys, setExpandedRowKeys] = useState([]);
  const [logModalVisible, setLogModalVisible] = useState(false);
  const [currentLogs, setCurrentLogs] = useState('');
  const [logModalTitle, setLogModalTitle] = useState('');

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

  const handleRetry = async (id, taskId = null) => {
    try {
      if (taskId) {
        await request.post(`/jobs/${id}/tasks/${taskId}/action`, { action: 'retry' });
        message.success('重试子任务成功');
      } else {
        await request.post(`/jobs/${id}/action`, { action: 'retry' });
        message.success('重试任务成功');
      }
      fetchData();
    } catch (error) {
      message.error('重试任务失败');
    }
  };

  const handlePause = async (id, taskId = null) => {
    try {
      if (taskId) {
        await request.post(`/jobs/${id}/tasks/${taskId}/action`, { action: 'pause' });
        message.success('暂停子任务成功');
      } else {
        await request.post(`/jobs/${id}/action`, { action: 'pause' });
        message.success('暂停任务成功');
      }
      fetchData();
    } catch (error) {
      message.error('暂停任务失败');
    }
  };

  const handleResume = async (id, taskId = null) => {
    try {
      if (taskId) {
        await request.post(`/jobs/${id}/tasks/${taskId}/action`, { action: 'resume' });
        message.success('启动子任务成功');
      } else {
        await request.post(`/jobs/${id}/action`, { action: 'resume' });
        message.success('启动任务成功');
      }
      fetchData();
    } catch (error) {
      message.error('启动任务失败');
    }
  };

  const handleCancel = async (id, taskId = null) => {
    try {
      if (taskId) {
        await request.post(`/jobs/${id}/tasks/${taskId}/action`, { action: 'cancel' });
        message.success('取消子任务成功');
      } else {
        await request.post(`/jobs/${id}/action`, { action: 'cancel' });
        message.success('取消任务成功');
      }
      fetchData();
    } catch (error) {
      message.error('取消任务失败');
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

  const handleUpdateParallelism = async (id, value) => {
    try {
      await request.put(`/jobs/${id}`, { parallelism: value });
      message.success('更新并行度成功');
      fetchData();
    } catch (error) {
      message.error('更新并行度失败');
    }
  };

  const getStatusTag = (status) => {
    const statusMap = {
      pending: { text: '等待中', color: 'gold' },
      processing: { text: '运行中', color: 'blue' },
      completed: { text: '已完成', color: 'green' },
      failed: { text: '失败', color: 'red' },
      paused: { text: '已暂停', color: 'orange' },
      cancelled: { text: '已取消', color: 'gray' }
    };
    
    const statusInfo = statusMap[status] || { text: status, color: 'default' };
    return <Tag color={statusInfo.color}>{statusInfo.text}</Tag>;
  };

  const getTaskTypeText = (taskType) => {
    const taskTypeMap = {
      process_upload: '处理上传',
      convert_to_markdown: '转换为Markdown',
      process_with_llm: 'LLM处理',
      process_ai_review: 'AI审阅'
    };
    return taskTypeMap[taskType] || taskType;
  };

  const expandRow = (record) => {
    const newExpandedRowKeys = [...expandedRowKeys];
    const index = newExpandedRowKeys.indexOf(record.id);
    if (index > -1) {
      newExpandedRowKeys.splice(index, 1);
    } else {
      newExpandedRowKeys.push(record.id);
    }
    setExpandedRowKeys(newExpandedRowKeys);
  };

  // 显示任务日志弹窗
  const showTaskLogs = (task, jobName) => {
    setCurrentLogs(task.logs || '暂无日志');
    setLogModalTitle(`${jobName || `任务 #${task.job_id}`} - ${getTaskTypeText(task.task_type)}日志`);
    setLogModalVisible(true);
  };

  // 关闭日志弹窗
  const handleLogModalClose = () => {
    setLogModalVisible(false);
  };

  const renderTasksTable = (tasks) => {
    const taskColumns = [
      // {
      //   title: 'ID',
      //   dataIndex: 'id',
      //   key: 'id',
      //   width: 60
      // },
      {
        title: '任务类型',
        dataIndex: 'task_type',
        key: 'task_type',
        render: (taskType) => getTaskTypeText(taskType)
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        render: (status) => getStatusTag(status)
      },
      {
        title: '进度',
        dataIndex: 'progress',
        key: 'progress',
        render: (progress) => (
          <Progress percent={progress} size="small" />
        )
      },
      {
        title: '操作',
        key: 'action',
        render: (_, task) => (
          <Space>
            <Button
              type="link"
              size="small"
              icon={<FileTextOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                const job = data.find(j => j.id === task.job_id);
                showTaskLogs(task, job?.name);
              }}
            >
              查看日志
            </Button>
            {task.status === 'failed' && (
              <Button
                type="link"
                size="small"
                icon={<ReloadOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  handleRetry(task.job_id, task.id);
                }}
              >
                重试
              </Button>
            )}
            {task.status === 'processing' && (
              <Button
                type="link"
                size="small"
                icon={<PauseCircleOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  handlePause(task.job_id, task.id);
                }}
              >
                暂停
              </Button>
            )}
            {task.status === 'paused' && (
              <Button
                type="link"
                size="small"
                icon={<PlayCircleOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  handleResume(task.job_id, task.id);
                }}
              >
                启动
              </Button>
            )}
            {(task.status === 'pending' || task.status === 'processing' || task.status === 'paused') && (
              <Button
                type="link"
                size="small"
                danger
                icon={<StopOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  handleCancel(task.job_id, task.id);
                }}
              >
                取消
              </Button>
            )}
          </Space>
        )
      }
    ];

    return (
      <Table
        columns={taskColumns}
        dataSource={tasks}
        rowKey="id"
        pagination={false}
        size="small"
      />
    );
  };

  const columns = [
    {
      title: '',
      key: 'expand',
      width: 50,
      render: (_, record) => (
        <Button
          type="text"
          icon={expandedRowKeys.includes(record.id) ? <DownOutlined /> : <RightOutlined />}
          onClick={() => expandRow(record)}
        />
      )
    },
    // {
    //   title: 'ID',
    //   dataIndex: 'id',
    //   key: 'id',
    //   width: 60
    // },
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
      render: (name, record) => name || `任务 #${record.id}`
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status) => getStatusTag(status)
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      render: (progress) => (
        <Progress percent={progress} size="small" />
      )
    },
    {
      title: '并行度',
      dataIndex: 'parallelism',
      key: 'parallelism',
      render: (parallelism, record) => {
        // 对于已完成、失败或已取消的任务，只显示并行度值，不提供编辑功能
        if (['completed', 'failed', 'cancelled'].includes(record.status)) {
          return <span>{parallelism || 1}</span>;
        }
        
        // 对于其他状态的任务，显示可编辑的并行度控件
        return (
          <Tooltip title="设置任务并行度">
            <InputNumber
              min={1}
              max={10}
              defaultValue={parallelism || 1}
              onChange={(value) => handleUpdateParallelism(record.id, value)}
              addonAfter={<SettingOutlined />}
              style={{ width: '100px' }}
            />
          </Tooltip>
        );
      }
    },
    {
      title: '子任务数',
      key: 'taskCount',
      render: (_, record) => record.tasks?.length || 0
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time) => new Date(time).toLocaleString()
    },
    {
      title: '操作',
      fixed: 'right',
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
          {record.status === 'processing' && (
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
          {(record.status === 'pending' || record.status === 'processing' || record.status === 'paused') && (
            <Button
              type="link"
              danger
              icon={<StopOutlined />}
              onClick={() => handleCancel(record.id)}
            >
              取消
            </Button>
          )}
        </Space>
      )
    }
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
        scroll={{ x: 'max-content' }}
        loading={loading}
        expandedRowKeys={expandedRowKeys}
        expandable={{
          expandedRowRender: (record) => renderTasksTable(record.tasks || []),
          expandRowByClick: false,
          expandIcon: () => null
        }}
      />
      
      {/* 日志查看弹窗 */}
      <Modal 
        title={logModalTitle}
        open={logModalVisible}
        onCancel={handleLogModalClose}
        footer={[
          <Button key="close" onClick={handleLogModalClose}>
            关闭
          </Button>
        ]}
        width={800}
      >
        <pre style={{ 
          maxHeight: '500px', 
          overflowY: 'auto', 
          backgroundColor: '#f5f5f5', 
          padding: '12px',
          borderRadius: '4px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word'
        }}>
          {currentLogs}
        </pre>
      </Modal>
    </div>
  );
};

export default Jobs;
