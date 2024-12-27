"""add processed attachment text field

Revision ID: 7823b18bc4b1
Revises: e93c0b27118a
Create Date: 2024-01-09 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7823b18bc4b1'
down_revision: Union[str, None] = 'e93c0b27118a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('ai_review_reports', sa.Column('processed_attachment_text', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('ai_review_reports', 'processed_attachment_text')
    # ### end Alembic commands ###
