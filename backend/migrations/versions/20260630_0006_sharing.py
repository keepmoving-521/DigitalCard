"""Add V0.6.0 public card event tracking.

Revision ID: 20260630_0006
Revises: 20260630_0005
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260630_0006"
down_revision: str | None = "20260630_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "card_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("card_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="direct"),
        sa.Column("visitor_hash", sa.String(length=64), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["digital_cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key", name="uq_card_events_dedupe_key"),
    )
    op.create_index("ix_card_events_card_id", "card_events", ["card_id"])
    op.create_index("ix_card_events_company_id", "card_events", ["company_id"])
    op.create_index("ix_card_events_event_type", "card_events", ["event_type"])
    op.create_index("ix_card_events_source", "card_events", ["source"])
    op.create_index("ix_card_events_visitor_hash", "card_events", ["visitor_hash"])
    op.create_index("ix_card_events_occurred_at", "card_events", ["occurred_at"])
    op.create_index("ix_card_events_card_occurred", "card_events", ["card_id", "occurred_at"])
    op.create_index("ix_card_events_company_occurred", "card_events", ["company_id", "occurred_at"])


def downgrade() -> None:
    op.drop_table("card_events")
