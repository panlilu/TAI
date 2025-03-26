# TAI - 论文智能审阅系统

TAI是一个基于AI的论文自动审阅系统，专为高校师生设计，用于对毕业论文等学术文档进行智能化审阅与评估。系统可自动分析文档内容，提供评分、反馈和改进建议，大幅提高审阅效率和一致性。

## 主要功能

- **文档智能分析**: 支持多种格式的文档上传和自动解析
- **AI审阅评估**: 使用大型语言模型对论文进行智能评价，提供分数和详细反馈
- **结构化数据提取**: 自动从评审结果中提取关键指标，便于数据分析和管理
- **批量处理**: 支持项目批量上传和并行处理多份文档
- **用户权限管理**: 完善的用户角色系统，支持管理员、VIP和普通用户
- **任务管理**: 可视化任务进度监控，支持暂停、恢复和取消任务
- **数据导出**: 支持导出评审结果为CSV格式，便于后续统计分析

## 技术架构

- **后端**: FastAPI, SQLAlchemy, Redis, RQ
- **AI模型集成**: LiteLLM支持多种大型语言模型(如Qwen, DeepSeek等)
- **数据库**: SQLite
- **前端**: React (位于frontend目录)

## 安装部署

### 系统要求

- Python 3.8+
- Redis

### 安装步骤

1. 克隆项目仓库

```bash
git clone https://github.com/panlilu/TAI.git
cd TAI
```

2. 创建并激活虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/MacOS
# 或 .venv\Scripts\activate  # Windows
```

3. 安装依赖

```bash
pip install -r requirements.txt
```

4. 配置环境变量

创建`.env`文件，参考`.env_example`配置信息

5. 初始化数据库

```bash
bash reset_db.sh
```

### 启动服务

1. 启动后端API服务

```bash
python run.py
```

2. 启动worker服务(用于处理后台任务)

```bash
bash run_worker.sh
```

3. 启动前端开发环境

```bash
cd frontend/tai_frontend/
pnpm install && pnpm start
```
## Docker部署

项目支持Docker部署:

```bash
# 构建镜像
bash docker_build.sh

# 运行容器
bash docker_run.sh
```

## 使用指南

1. 访问系统: 打开浏览器访问 `http://localhost:8000`
2. 注册/登录: 第一个注册的用户将自动成为管理员
3. 创建文章类型: 设置评审标准和提示词
4. 创建项目: 基于文章类型创建项目，用于批量处理文档
5. 上传文档: 上传需要审阅的文档
6. 启动审阅: 系统将自动处理文档并生成审阅报告
7. 查看结果: 在系统中查看审阅结果，包括评分、评语和改进建议

## API文档

- API文档访问地址: `http://localhost:8000/api/docs`
- ReDoc文档: `http://localhost:8000/api/redoc`

## 许可证

[MIT License](LICENSE) 