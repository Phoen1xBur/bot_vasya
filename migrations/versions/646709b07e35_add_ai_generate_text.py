"""add ai_generate_text

Revision ID: 646709b07e35
Revises: 23665d24b17f
Create Date: 2026-04-20 16:40:39.357814

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '646709b07e35'
down_revision: Union[str, None] = '23665d24b17f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'telegram_chat',
        sa.Column('ai_generate_text', sa.Boolean(), server_default='false', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('telegram_chat', 'ai_generate_text')
