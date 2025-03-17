import tomli
import os

# 创建一个新的配置文件
config_content = """# 模型配置文件
# 此文件定义了可用的AI模型及其配置

# 模型列表
[[models]]
id = "deepseek/deepseek-chat"
name = "DeepSeek Chat"
description = "DeepSeek Chat是一个通用的对话模型，适合日常对话和一般任务"

[[models]]
id = "deepseek/deepseek-reason"
name = "DeepSeek Reason"
description = "DeepSeek Reason是一个专注于推理能力的模型，适合需要逻辑分析的任务"

[[models]]
id = "openrouter/qwen/qwq-32b-free"
name = "Qwen 32B"
description = "Qwen 32B是一个大规模预训练模型，提供免费使用的版本，适合多种复杂任务"

# 任务配置
[tasks]

[tasks.process_with_llm]
available_models = [
    "deepseek/deepseek-chat",
    "deepseek/deepseek-reason",
    "openrouter/qwen/qwq-32b-free"
]
default_model = "deepseek/deepseek-chat"
description = "使用LLM处理文本内容的任务"
default_config = { temperature = 0.7, max_tokens = 2000, top_p = 0.95 }

[tasks.ai_review]
available_models = [
    "deepseek/deepseek-reason",
    "openrouter/qwen/qwq-32b-free"
]
default_model = "deepseek/deepseek-reason"
description = "AI审阅和分析文档的任务"
default_config = { temperature = 0.3, max_tokens = 4000, top_p = 0.9 }

[tasks.text_summarization]
available_models = [
    "deepseek/deepseek-chat",
    "openrouter/qwen/qwq-32b-free"
]
default_model = "deepseek/deepseek-chat"
description = "文本摘要生成任务"
default_config = { temperature = 0.5, max_tokens = 1000, top_p = 0.9 }
"""

# 写入新的配置文件
with open('model_config_fixed.toml', 'wb') as f:
    f.write(config_content.encode('utf-8'))

# 测试加载新的配置文件
try:
    with open('model_config_fixed.toml', 'rb') as f:
        config = tomli.load(f)
        print('成功加载配置文件')
        print(f'模型数量: {len(config.get("models", []))}')
        print(f'模型列表: {[model["name"] for model in config.get("models", [])]}')
except Exception as e:
    print(f'加载配置文件失败: {e}') 