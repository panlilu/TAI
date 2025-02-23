#!/bin/bash

# 删除现有的数据库文件
rm -f data/sql_app.db

# 使用alembic重新创建数据库结构
alembic upgrade head

echo "数据库内容已清空"
