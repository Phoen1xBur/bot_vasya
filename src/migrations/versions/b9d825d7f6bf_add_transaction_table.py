"""Add Transaction table

Revision ID: b9d825d7f6bf
Revises: 4d1cb3095f09
Create Date: 2024-11-18 16:07:15.979404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b9d825d7f6bf'
down_revision: Union[str, None] = '4d1cb3095f09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE "user" ALTER COLUMN rank TYPE VARCHAR(255);')
    op.execute('DROP TYPE IF EXISTS rank;')
    op.execute("CREATE TYPE rank AS ENUM ('USER', 'VIP', 'PREMIUM', 'OWNER');")
    op.execute('ALTER TABLE "user" ALTER COLUMN rank TYPE rank USING (rank::rank);')
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('group_user_from_id', sa.Integer(), nullable=True),
        sa.Column('group_user_to_id', sa.Integer(), nullable=True),
        sa.Column('transaction_type',
                  sa.Enum('WORK', 'ROB', 'TAX_AND_FINE', 'USER_TRANSFER', 'BANK_TRANSFER',
                          name='transactiontype'), nullable=False),
        sa.Column('transferred_money', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['group_user_from_id'], ['group_user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['group_user_to_id'], ['group_user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transaction_group_user_from_id'), 'transaction', ['group_user_from_id'], unique=False)
    op.create_index(op.f('ix_transaction_group_user_to_id'), 'transaction', ['group_user_to_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    op.execute('ALTER TABLE "user" ALTER COLUMN rank TYPE VARCHAR(255);')
    op.execute('DROP TYPE IF EXISTS rank;')
    op.execute("CREATE TYPE rank AS ENUM ('USER', 'VIP', 'PREMIUM');")
    op.execute('ALTER TABLE "user" ALTER COLUMN rank TYPE rank USING (rank::rank);')

    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_transaction_group_user_to_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_group_user_from_id'), table_name='transaction')
    op.drop_table('transaction')
    op.execute('DROP TYPE transactiontype')
    # ### end Alembic commands ###
