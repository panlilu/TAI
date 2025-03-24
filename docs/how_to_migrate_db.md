（以增加一个数据库字段为例）的方法如下。
## 创建新的迁移脚本
使用 alembic revision --autogenerate -m "add_structured_data" 命令
这会在 versions 目录下生成一个新的迁移脚本文件
文件名格式类似 {revision_id}_add_structured_data.py

## 检查并编辑迁移脚本
迁移脚本会包含 upgrade() 和 downgrade() 两个函数
upgrade() 函数包含添加字段的操作
downgrade() 函数包含回滚操作

## 运行数据库迁移
使用 alembic upgrade head 命令执行迁移
这会将数据库更新到最新版本，应用新添加的 structured_data 字段

## 验证迁移结果
检查数据库表结构确认字段已添加
可以通过应用程序测试新字段的功能

## 如果需要回滚
使用 alembic downgrade {revision_id} 回滚到特定版本
或使用 alembic downgrade -1 回滚一个版本
