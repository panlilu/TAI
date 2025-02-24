"""add_status_and_job_id_to_ai_review_reports

Revision ID: 0ebb874ca321
Revises: 649318d463ed
Create Date: 2025-02-24 19:38:20.472238

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ebb874ca321'
down_revision: Union[str, None] = '649318d463ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 添加 status 字段，默认值为 'pending'
    op.add_column('ai_review_reports', sa.Column('status', sa.String(), server_default='pending', nullable=True))


def downgrade() -> None:
    # 删除 status 字段
    op.drop_column('ai_review_reports', 'status')
