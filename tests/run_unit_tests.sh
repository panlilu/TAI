#!/bin/bash

# 导入环境变量
source .env

# 设置Python路径
export PYTHONPATH=.

# 运行单元测试
pytest tests/unit -v -m unit 