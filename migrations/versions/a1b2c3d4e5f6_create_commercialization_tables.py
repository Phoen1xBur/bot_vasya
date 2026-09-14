"""create commercialization tables

Revision ID: a1b2c3d4e5f6
Revises: 646709b07e35
Create Date: 2026-09-14 16:00:00

Новые таблицы монетизации: payment, subscription, donation, order,
ad_campaign, chat_unique_users, game_room, game_participant.

Существующие таблицы (user, telegram_chat, group_user, message,
profession, transaction) НЕ трогаем.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = '646709b07e35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # payment
    op.create_table(
        "payment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(128), nullable=False, unique=True),
        sa.Column("payment_id", sa.String(128), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("payment_type", sa.String(32), nullable=False, index=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="NEW"),
        sa.Column("meta", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("fulfilled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # subscription
    op.create_table(
        "subscription",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("tier", sa.String(16), nullable=False, server_default="free"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("recurring_key", sa.String(256), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # donation
    op.create_table(
        "donation",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.String(128), nullable=False, unique=True),
        sa.Column("message", sa.String(1024), nullable=True),
        sa.Column("public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # order
    op.create_table(
        "order",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("order_id", sa.String(128), nullable=False, unique=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("product", sa.String(64), nullable=False, index=True),
        sa.Column("fulfilled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("meta", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # ad_campaign
    op.create_table(
        "ad_campaign",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("advertiser_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("text", sa.String(4096), nullable=False),
        sa.Column("link", sa.String(1024), nullable=False),
        sa.Column("target_unique_users", sa.Integer(), nullable=False),
        sa.Column("selected_chats", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("price", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft", index=True),
        sa.Column("ai_verdict", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("admin_comment", sa.String(1024), nullable=True),
        sa.Column("contact", sa.String(256), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("actual_reach", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # chat_unique_users
    op.create_table(
        "chat_unique_users",
        sa.Column("chat_id", sa.BigInteger(), primary_key=True),
        sa.Column("unique_user_ids", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("members_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )

    # game_room
    op.create_table(
        "game_room",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("game_type", sa.String(16), nullable=False, index=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("initiator_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="waiting", index=True),
        sa.Column("state", postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("bet", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("winner_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(), nullable=False, index=True),
    )

    # game_participant
    op.create_table(
        "game_participant",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("room_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("game_room.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("bet", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("game_participant")
    op.drop_table("game_room")
    op.drop_table("chat_unique_users")
    op.drop_table("ad_campaign")
    op.drop_table("order")
    op.drop_table("donation")
    op.drop_table("subscription")
    op.drop_table("payment")
