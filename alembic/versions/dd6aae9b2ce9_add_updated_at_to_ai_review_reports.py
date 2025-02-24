"""add_updated_at_to_ai_review_reports

Revision ID: dd6aae9b2ce9
Revises: 0ebb874ca321
Create Date: 2025-02-24 20:20:58.060846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dd6aae9b2ce9'
down_revision: Union[str, None] = '0ebb874ca321'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add updated_at column with server default
    op.add_column('ai_review_reports', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))


def downgrade() -> None:
    # Remove updated_at column
    op.drop_column('ai_review_reports', 'updated_at')
