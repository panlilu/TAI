# 第一阶段：构建前端
FROM node:18-alpine as frontend-builder
WORKDIR /app
COPY frontend/tai_frontend/package.json frontend/tai_frontend/pnpm-lock.yaml ./frontend/
RUN corepack enable && cd frontend && pnpm install
COPY frontend/tai_frontend/ ./frontend/
RUN cd frontend && pnpm run build

# 第二阶段：构建后端
FROM python:3.11-slim
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制Python依赖清单
COPY requirements.txt ./

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY app ./app
COPY run.py ./

# 从前端构建阶段复制产物
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8000"]