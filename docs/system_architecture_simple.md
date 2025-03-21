%%{init: {'theme': 'default', 'flowchart': {'htmlLabels': true}, 'themeVariables': { 'primaryColor': '#D6EAF8', 'primaryBorderColor': '#2E86C1', 'secondaryColor': '#D5F5E3', 'tertiaryColor': '#FCF3CF'}}}%%
graph TD
    subgraph "前端层 (Frontend)"
        Frontend[React前端应用]
    end

    subgraph "API层 (Backend)"
        API[FastAPI应用]
        Auth[认证服务]
    end

    subgraph "核心服务层 (Core Services)"
        TaskManager[任务管理服务]
        ArticleService[文章处理服务]
        FileConverter[文件转换服务]
    end

    subgraph "AI处理层 (AI Processing)"
        AIEngine[AI审阅引擎]
    end

    subgraph "数据层 (Data Layer)"
        DB[(SQL数据库)]
        Redis[(Redis队列)]
    end

    %% 连接关系
    Frontend <--> API
    API --> Auth
    API --> TaskManager
    API --> ArticleService
    
    TaskManager --> Redis
    TaskManager --> DB
    ArticleService --> DB
    ArticleService --> FileConverter
    
    Redis --> AIEngine
    AIEngine --> FileConverter
    AIEngine --> DB