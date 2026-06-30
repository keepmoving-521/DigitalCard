"""Create the V0.1.0 database baseline.

Revision ID: 20260629_0001
Revises:
Create Date: 2026-06-29
"""

from collections.abc import Sequence

revision: str = "20260629_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Reserve the initial schema revision before business tables are introduced."""


def downgrade() -> None:
    """Remove the initial schema revision."""
