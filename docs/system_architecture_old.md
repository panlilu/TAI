graph TD
    %% 前端部分
    subgraph Frontend[前端 - React + Ant Design]
        UI[用户界面]
        EventService[事件服务]
        AuthService[认证服务]
        ApiClient[API客户端]
    end

    %% 后端API部分
    subgraph Backend[后端 - FastAPI]
        API[API层]
        Auth[认证授权]
        DB[数据库层]
        FileHandler[文件处理]
        TaskQueue[任务队列]
        FileConverter[文件转换器]
        ModelService[模型服务]
    end

    %% 数据存储
    subgraph Storage[存储层]
        SQLite[(SQLite数据库)]
        FileSystem[文件系统]
    end

    %% 任务处理
    subgraph Workers[Worker系统]
        Redis[(Redis)]
        RQWorker[RQ Worker]
        Tasks[任务处理器]
        AIProcessor[AI处理器]
        StructuredDataExtractor[结构化数据提取器]
    end

    %% 图例说明
    subgraph Legend[图例]
        L1[直接调用] --> L2[被调用]
        L3[事件源] -.-> L4[事件消费]
        style L1 fill:#ffffff,stroke:#333
        style L2 fill:#ffffff,stroke:#333
        style L3 fill:#ffffff,stroke:#333
        style L4 fill:#ffffff,stroke:#333
    end

    %% 连接关系
    UI --> EventService
    UI --> AuthService
    UI --> ApiClient
    ApiClient --> API
    API --> Auth
    API --> DB
    API --> FileHandler
    API --> TaskQueue
    API --> FileConverter
    API --> ModelService
    DB --> SQLite
    FileHandler --> FileSystem
    FileConverter --> FileSystem
    TaskQueue --> Redis
    Redis --> RQWorker
    RQWorker --> Tasks
    Tasks --> AIProcessor
    Tasks --> StructuredDataExtractor
    Tasks --> DB
    Tasks --> FileSystem
    AIProcessor --> ModelService
    StructuredDataExtractor --> ModelService

    %% 数据流
    EventService -.-> API
    AuthService -.-> Auth

    %% 样式
    classDef frontend fill:#d4e6f1
    classDef backend fill:#d5f5e3
    classDef storage fill:#fad7a0
    classDef workers fill:#d2b4de
    
    class Frontend,UI,EventService,AuthService,ApiClient frontend
    class Backend,API,Auth,DB,FileHandler,TaskQueue,FileConverter,ModelService backend
    class Storage,SQLite,FileSystem storage
    class Workers,Redis,RQWorker,Tasks,AIProcessor,StructuredDataExtractor workers

**箭头说明：**
- 实线箭头(-->)：表示组件间的直接依赖关系，如函数调用、数据访问等核心业务流程
- 虚线箭头(-.->)：表示组件间的间接依赖或事件驱动的异步通信，如WebSocket/SSE事件推送

**主要组件说明：**

1. 前端层
- UI：基于React和Ant Design的用户界面
- EventService：处理实时事件和通知，基于Server-Sent Events (SSE)
- AuthService：处理用户认证和授权
- ApiClient：与后端API通信，基于Axios

2. 后端API层
- API：FastAPI提供的RESTful接口，支持OpenAPI文档
- Auth：基于OAuth2和JWT的认证和授权
- DB：SQLAlchemy数据库访问层
- FileHandler：文件上传、下载和处理
- TaskQueue：基于Redis和RQ的异步任务队列管理
- FileConverter：支持多种格式文件（包括DOC、PDF、图片等）转换为Markdown
- ModelService：LLM模型服务配置和管理

3. 存储层
- SQLite：关系型数据库存储用户、文章、项目等数据
- FileSystem：文件存储系统，用于存储上传的文档和图片

4. Worker系统
- Redis：任务队列和事件存储
- RQ Worker：异步任务处理器
- Tasks：具体任务实现，包括文件转换、AI处理等
- AIProcessor：使用LLM处理文章内容
- StructuredDataExtractor：提取文章的结构化数据

**主要功能流：**

1. 用户认证流程：
   - 用户通过UI登录 -> AuthService -> API -> Auth验证 -> 返回JWT令牌
   - 前端存储令牌用于后续请求认证

2. 文件处理流程：
   - 用户上传文件 -> API -> FileHandler -> FileSystem存储
   - FileHandler -> TaskQueue -> Redis -> FileConverter处理
   - 支持多种格式转换为Markdown格式

3. AI审阅流程：
   - 创建审阅任务 -> TaskQueue -> Redis -> AIProcessor执行
   - AIProcessor调用外部LLM -> 处理结果存入DB
   - EventService通过SSE实时推送处理进度和结果

4. 结构化数据提取：
   - 创建数据提取任务 -> TaskQueue -> Redis -> StructuredDataExtractor执行
   - 提取文章关键数据结构 -> 存入DB -> EventService实时推送结果

5. 项目管理流程：
   - 用户创建项目 -> 关联文章类型 -> 设置AI处理参数
   - 项目中创建文章和批量任务 -> 统一管理和导出结果
   
6. 实时通知流程：
   - Worker状态更新 -> Redis -> API Events -> SSE -> EventService -> UI显示通知
   - 支持任务进度、AI审阅和结构化数据提取的实时反馈

# API设计

本系统采用RESTful API架构设计，基于FastAPI框架实现，提供了完整的用户认证、资源管理和任务处理功能。API设计遵循以下主要原则：

## 1. 统一的认证机制

系统实现了基于OAuth2的token认证机制，所有API端点（除登录注册外）都需要进行身份验证：

- 用户通过`/token`端点获取JWT访问令牌
- 使用Bearer token方式在请求头中携带认证信息
- 通过中间件进行统一的认证和授权管理
- 支持角色权限控制，管理员用户拥有额外权限

## 2. 模块化的资源管理

API按照不同的资源类型进行模块化设计，主要包括：

- 用户管理（User Management）：用户的CRUD操作
- 文章类型管理（Article Type Management）：支持自定义和公共文章模板
- 文章管理（Article Management）：文章的上传、查询和处理
- 项目管理（Project Management）：项目的创建和管理
- 作业管理（Job Management）：异步任务的执行和监控
- AI审阅管理（AI Review Management）：AI批阅报告的生成和查询
- 模型配置管理（Model Configuration）：LLM模型配置和管理

## 3. 异步任务处理

系统采用异步任务队列处理耗时操作：

- 使用Redis作为消息队列后端
- 基于Python RQ实现任务队列管理
- 支持任务的并行处理、暂停、恢复、取消等状态管理
- 实现了基于Server-Sent Events (SSE)的实时任务状态推送
- 支持细粒度的任务进度报告和错误处理

## 4. 文件处理

- 支持多种格式文件的处理，包括DOC、DOCX、PDF、图片等
- 使用专用的文件转换器将不同格式转换为Markdown
- 支持图片内文本提取（OCR）和图片描述生成
- 提供批量文件上传和处理功能

## 5. RESTful设计规范

API的设计严格遵循RESTful原则：

- 使用HTTP标准方法（GET, POST, PUT, DELETE）
- 采用资源导向的URL设计
- 统一的请求响应格式和错误处理
- 清晰的状态码使用
- 完整的OpenAPI文档支持

## 6. 实时数据推送

针对长时间运行的任务处理，实现了多个事件流端点：

- `/events`：推送任务执行状态变更
- `/events_ai_review/{ai_review_id}`：推送AI审阅报告的实时生成内容
- `/events_structured_data/{report_id}`：推送结构化数据提取进度

## 7. 数据导出

- 支持项目数据的CSV格式导出
- 包含文章信息和AI审阅结果
- 可选择是否包含详细报告内容

这种API设计确保了系统的可扩展性、可维护性和用户体验，为论文批阅系统提供了稳定可靠的后端服务支持。