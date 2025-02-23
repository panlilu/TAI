import { notification } from 'antd';
import { getToken } from './auth';
import { EventSourcePolyfill } from 'event-source-polyfill';
import config from '../config';

class EventService {
  constructor() {
    this.eventSource = null;
  }

  connect() {
    if (this.eventSource) {
      this.eventSource.close();
    }

    const token = getToken();
    if (!token) return;

    this.eventSource = new EventSourcePolyfill(`${config.apiBaseURL}/events`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    this.eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      // Show notification for completed or failed jobs
      if (data.status === 'COMPLETED' || data.status === 'FAILED') {
        notification.info({
          message: `任务${data.status === 'COMPLETED' ? '完成' : '失败'}`,
          description: `任务 #${data.id} ${data.task} ${data.status === 'COMPLETED' ? '已完成' : '执行失败'}`,
          placement: 'topRight',
        });
      }
    };

    this.eventSource.onerror = (error) => {
      console.error('SSE Error:', error);
      this.eventSource.close();
      // Try to reconnect after 5 seconds
      setTimeout(() => this.connect(), 5000);
    };
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }
}

export const eventService = new EventService();