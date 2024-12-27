"""add_graduation_thesis_article_type

Revision ID: 6f19526185b4
Revises: f00794b71eb5
Create Date: 2024-12-27 21:28:14.585266

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String, Boolean, JSON, Integer


# revision identifiers, used by Alembic.
revision: str = '6f19526185b4'
down_revision: Union[str, None] = 'f00794b71eb5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建一个临时表对象，用于插入数据
    article_types = table('article_types',
        column('id', Integer),
        column('name', String),
        column('is_public', Boolean),
        column('prompt', String),
        column('schema_prompt', String),
        column('fields', JSON)
    )

    # 插入毕业论文类型数据
    op.bulk_insert(article_types, [
        {
            'id': 1,  # 使用固定ID便于后续删除
            'name': '毕业论文',
            'is_public': True,
            'prompt': '''#论文标准
## 论文内容要求
* 具体的项目描述（需求分析）：
  - 项目背景，使用环境，要解决的问题：有参数，要定量；
* 相关理论知识的简单介绍（解决问题的思路）；
* 利用有关理论解决问题的过程：重点论述"为什么"，而不是"是什么"
* 最终设计成果展示：能运行的软件，硬件或系统照片，模拟运行截图，可操作的设计方案等
* 项目总结：心得、未尽事宜、改进方案、自我评估、闪光点等
* 附录：参考文献，源代码，电路图等

## 评判标准
* 未有具体的设计内容/基本要求未达到 -- 不及格
* 有设计结果没有设计过程（缺乏中间文档，计算，设计结果没有数据支撑）-- 及格
* 有设计过程及设计结果展示，设计过程有逻辑性，可自圆其说，可以有小瑕疵 -- 良好
* 设计工作量大，有真正应用价值，个人逻辑清楚，查重小于10% -- 优秀

根据这个论文标准评价一下这篇论文''',
            'schema_prompt': '''请根据以上信息回复一个json，包含以下字段
author 作者
title 标题
grade 评价''',
            'fields': {
                'author': '作者',
                'title': '标题',
                'grade': '评价'
            }
        }
    ])


def downgrade() -> None:
    # 删除添加的毕业论文类型数据
    op.execute("DELETE FROM article_types WHERE id = 1")
