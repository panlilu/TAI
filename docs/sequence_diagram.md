```mermaid
sequenceDiagram
    actor 用户
    participant UI as 前端界面
    participant API as 后端API
    participant TaskMgr as 任务管理器
    participant DocProc as 文档处理器
    participant Queue as 任务队列
    participant AI as AI引擎
    participant CSV as CSV生成器
    participant DB as 数据库
    participant Storage as 文件存储

    用户->>UI: 上传文档文件
    UI->>API: 发送文件和处理请求
    API->>DocProc: 提交文件处理
    DocProc->>Storage: 保存原始文件
    DocProc->>DocProc: 转换文件格式(如需)
    DocProc->>DB: 记录文件信息
    DocProc->>TaskMgr: 创建分析任务
    TaskMgr->>DB: 保存任务状态
    TaskMgr->>Queue: 添加任务到队列
    API->>UI: 返回任务ID和状态
    UI->>用户: 显示任务已创建
    
    Queue->>AI: 分发任务
    AI->>Storage: 获取处理后文件
    AI->>AI: 分析文档内容
    AI->>CSV: 发送提取数据
    CSV->>CSV: 生成CSV文件
    CSV->>Storage: 保存CSV文件
    CSV->>DB: 更新结果状态
    
    Note over UI,DB: 轮询或WebSocket实时更新
    
    UI->>API: 查询任务状态
    API->>DB: 获取任务信息
    DB->>API: 返回任务完成状态
    API->>UI: 返回任务状态和结果链接
    UI->>用户: 显示处理完成
    
    用户->>UI: 点击下载CSV
    UI->>API: 请求下载文件
    API->>Storage: 获取CSV文件
    Storage->>API: 返回文件内容
    API->>UI: 传输CSV文件
    UI->>用户: 下载CSV文件