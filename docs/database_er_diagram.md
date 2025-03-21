# 数据库ER图

下面是系统数据库实体关系图，使用Mermaid语法生成：

```mermaid
erDiagram
    User {
        int id PK
        string username
        string hashed_password
        enum role
        boolean is_active
    }
    
    ArticleType {
        int id PK
        string name
        boolean is_public
        json config
        int owner_id FK
    }
    
    Article {
        int id PK
        string name
        json attachments
        int article_type_id FK
        json json_result
        int project_id FK
        datetime created_at
        int active_ai_review_report_id
    }
    
    AIReviewReport {
        int id PK
        int article_id FK
        int job_id FK
        string source_data
        text processed_attachment_text
        datetime created_at
        datetime updated_at
        string status
        json structured_data
    }
    
    Project {
        int id PK
        string name
        json config
        boolean auto_approve
        int owner_id FK
        int article_type_id FK
    }
    
    JobTask {
        int id PK
        int job_id FK
        enum task_type
        enum status
        int progress
        text logs
        int article_id FK
        json params
        datetime created_at
        datetime updated_at
    }
    
    Job {
        int id PK
        int project_id FK
        string name
        enum status
        int progress
        text logs
        int parallelism
        datetime created_at
        datetime updated_at
    }
    
    User ||--o{ ArticleType : "创建"
    User ||--o{ Project : "拥有"
    ArticleType ||--o{ Article : "包含"
    ArticleType ||--o{ Project : "应用于"
    Project ||--o{ Article : "包含"
    Project ||--o{ Job : "关联"
    Article ||--o{ AIReviewReport : "拥有"
    Job ||--o{ JobTask : "包含"
    Article o|--o{ JobTask : "被处理"
    Job o|--o{ AIReviewReport : "生成"
```

## 数据库关系说明

1. **User(用户)** - 系统用户，可以创建文章类型和项目
2. **ArticleType(文章类型)** - 定义了不同类型的文章及其处理配置
3. **Project(项目)** - 包含多个文章的集合，基于特定的文章类型
4. **Article(文章)** - 系统中的主要内容实体，属于特定项目和文章类型
5. **AIReviewReport(AI审阅报告)** - 存储AI对文章的审阅结果
6. **Job(任务)** - 处理项目中文章的任务
7. **JobTask(任务项)** - 具体任务的子任务，如处理上传、转换文档等

主要关系:
- 用户创建文章类型和项目
- 项目基于特定文章类型并包含多个文章
- 文章可以有多个AI审阅报告
- 任务关联到项目并包含多个子任务
- 任务可能生成AI审阅报告
- 子任务可能处理特定文章 