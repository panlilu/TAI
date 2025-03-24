-- 项目数据库结构SQL DDL
-- 基于SQLAlchemy模型定义生成

-- 用户表
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    role VARCHAR NOT NULL,  -- admin, vip, normal
    is_active BOOLEAN DEFAULT TRUE
);

-- 文章类型表
CREATE TABLE article_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR NOT NULL,
    is_public BOOLEAN DEFAULT FALSE,
    config JSON NOT NULL DEFAULT '{}',  -- 配置信息，包含prompt等
    owner_id INTEGER,
    FOREIGN KEY (owner_id) REFERENCES users (id)
);

-- 项目表
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR NOT NULL,
    config JSON NOT NULL DEFAULT '{}',  -- 配置信息，包含prompt等
    auto_approve BOOLEAN DEFAULT TRUE,  -- 是否自动审批
    owner_id INTEGER NOT NULL,
    article_type_id INTEGER NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users (id),
    FOREIGN KEY (article_type_id) REFERENCES article_types (id)
);

-- 文章表
CREATE TABLE articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR NOT NULL,
    attachments JSON,  -- 附件列表
    article_type_id INTEGER NOT NULL,
    json_result JSON NOT NULL DEFAULT '{}',  -- AI审阅结果
    project_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active_ai_review_report_id INTEGER,
    FOREIGN KEY (article_type_id) REFERENCES article_types (id),
    FOREIGN KEY (project_id) REFERENCES projects (id)
);

-- AI审阅报告表
CREATE TABLE ai_review_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id INTEGER NOT NULL,
    job_id INTEGER,
    source_data TEXT,  -- 源数据
    processed_attachment_text TEXT,  -- 处理后的附件文本内容
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR DEFAULT 'pending',  -- pending, processing, completed, failed
    structured_data JSON,  -- 结构化的数据
    FOREIGN KEY (article_id) REFERENCES articles (id),
    FOREIGN KEY (job_id) REFERENCES jobs (id)
);

-- 任务表
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid VARCHAR UNIQUE NOT NULL,
    project_id INTEGER NOT NULL,
    name VARCHAR,  -- 任务名称
    status VARCHAR NOT NULL,  -- pending, processing, paused, completed, failed, cancelled
    progress INTEGER,
    logs TEXT,
    parallelism INTEGER DEFAULT 1,  -- 并行度设置
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects (id)
);

-- 任务子项表
CREATE TABLE job_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    task_type VARCHAR NOT NULL,  -- process_upload, convert_to_markdown, process_with_llm, process_ai_review, extract_structured_data
    status VARCHAR NOT NULL,  -- pending, processing, paused, completed, failed, cancelled
    progress INTEGER,
    logs TEXT,
    article_id INTEGER,
    params JSON,  -- 存储任务参数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs (id),
    FOREIGN KEY (article_id) REFERENCES articles (id)
);

-- 添加索引以优化查询性能
CREATE INDEX idx_article_types_name ON article_types (name);
CREATE INDEX idx_article_types_owner_id ON article_types (owner_id);
CREATE INDEX idx_articles_name ON articles (name);
CREATE INDEX idx_articles_article_type_id ON articles (article_type_id);
CREATE INDEX idx_articles_project_id ON articles (project_id);
CREATE INDEX idx_projects_name ON projects (name);
CREATE INDEX idx_projects_owner_id ON projects (owner_id);
CREATE INDEX idx_projects_article_type_id ON projects (article_type_id);
CREATE INDEX idx_ai_review_reports_article_id ON ai_review_reports (article_id);
CREATE INDEX idx_ai_review_reports_job_id ON ai_review_reports (job_id);
CREATE INDEX idx_jobs_uuid ON jobs (uuid);
CREATE INDEX idx_jobs_project_id ON jobs (project_id);
CREATE INDEX idx_jobs_status ON jobs (status);
CREATE INDEX idx_job_tasks_job_id ON job_tasks (job_id);
CREATE INDEX idx_job_tasks_article_id ON job_tasks (article_id);
CREATE INDEX idx_job_tasks_status ON job_tasks (status);
CREATE INDEX idx_job_tasks_task_type ON job_tasks (task_type); 