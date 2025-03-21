import { notification } from 'antd';
import { getToken } from './auth';
import { EventSourcePolyfill } from 'event-source-polyfill';
import config from '../config';

class EventService {
  constructor() {
    this.eventSource = null;
    this.aiReviewEventSource = null;
    this.structuredDataEventSource = null;
    this.eventListeners = {
      job_update: [],
      task_update: [],
      heartbeat: []
    };
  }

  // 添加事件监听器
  addEventListener(eventType, callback) {
    if (this.eventListeners[eventType]) {
      this.eventListeners[eventType].push(callback);
      return true;
    }
    return false;
  }

  // 移除事件监听器
  removeEventListener(eventType, callback) {
    if (this.eventListeners[eventType]) {
      this.eventListeners[eventType] = this.eventListeners[eventType].filter(
        cb => cb !== callback
      );
      return true;
    }
    return false;
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
      
      // 根据事件类型分发事件
      if (data.type) {
        // 调用对应类型的事件处理器
        if (this.eventListeners[data.type]) {
          this.eventListeners[data.type].forEach(callback => callback(data));
        }
      } else if (data.status === 'COMPLETED' || data.status === 'FAILED') {
        // 向下兼容，处理旧版本事件
        notification.info({
          message: `任务${data.status === 'COMPLETED' ? '完成' : '失败'}`,
          description: `任务 #${data.id} ${data.task_type || ''} ${data.status === 'COMPLETED' ? '已完成' : '执行失败'}`,
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

  connectToAIReview(aiReviewId, onMessage, onError) {
    if (this.aiReviewEventSource) {
      this.aiReviewEventSource.close();
      this.aiReviewEventSource = null;
    }

    const token = getToken();
    if (!token) {
      if (onError) onError(new Error('No authentication token available'));
      return;
    }

    try {
      const url = `${config.apiBaseURL}/events_ai_review/${aiReviewId}`;
      console.log(`正在连接到AI审阅事件源: ${url}`);
      
      this.aiReviewEventSource = new EventSourcePolyfill(
        url,
        {
          headers: {
            'Authorization': `Bearer ${token}`
          },
          heartbeatTimeout: 60000 // 增加心跳超时时间到60秒
        }
      );

      this.aiReviewEventSource.onmessage = onMessage;
      
      this.aiReviewEventSource.onerror = (error) => {
        console.error('AI Review SSE Error:', error);
        
        // 如果连接已关闭，尝试重新连接
        if (this.aiReviewEventSource && this.aiReviewEventSource.readyState === 2) {
          console.log('AI审阅连接已关闭，尝试重新连接...');
          
          // 关闭现有连接
          this.aiReviewEventSource.close();
          this.aiReviewEventSource = null;
          
          // 5秒后尝试重新连接
          setTimeout(() => {
            if (!this.aiReviewEventSource) {
              this.connectToAIReview(aiReviewId, onMessage, onError);
            }
          }, 5000);
        }
        
        if (onError) onError(error);
      };
      
      // 添加打开连接的处理函数
      this.aiReviewEventSource.onopen = () => {
        console.log('AI审阅事件源连接已建立');
      };
    } catch (error) {
      console.error('创建AI审阅事件源连接失败:', error);
      if (onError) onError(error);
    }
  }

  disconnectAIReview() {
    if (this.aiReviewEventSource) {
      this.aiReviewEventSource.close();
      this.aiReviewEventSource = null;
    }
  }

  connectToStructuredData(reportId, onMessage, onError) {
    if (this.structuredDataEventSource) {
      this.structuredDataEventSource.close();
    }

    const token = getToken();
    if (!token) return;

    this.structuredDataEventSource = new EventSourcePolyfill(
      `${config.apiBaseURL}/events_structured_data/${reportId}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    this.structuredDataEventSource.onmessage = onMessage;
    this.structuredDataEventSource.onerror = (error) => {
      console.error('Structured Data SSE Error:', error);
      this.structuredDataEventSource.close();
      if (onError) onError(error);
    };
  }

  disconnectStructuredData() {
    if (this.structuredDataEventSource) {
      this.structuredDataEventSource.close();
      this.structuredDataEventSource = null;
    }
  }
}

export const eventService = new EventService();