"""Add V1.4.0 tenant knowledge base and AI assistant.

Revision ID: 20260701_0013
Revises: 20260701_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0013"
down_revision: str | None = "20260701_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(36)),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("is_authorized", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.String(500)),
        sa.Column("indexed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_knowledge_company_status", "knowledge_sources", ["company_id", "status"])
    op.create_index(
        "ix_knowledge_company_type_source",
        "knowledge_sources",
        ["company_id", "source_type", "source_id"],
    )
    op.create_table(
        "ai_configurations",
        sa.Column("company_id", sa.String(36), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("public_qa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "sales_assistant_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("welcome_message", sa.String(500), nullable=False),
        sa.Column("system_prompt", sa.String(2000), nullable=False),
        sa.Column("daily_limit", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36)),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("uncertain", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("feedback", sa.Integer()),
        sa.Column("feedback_comment", sa.String(500)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_ai_interactions_company_time", "ai_interactions", ["company_id", "created_at"]
    )
    connection = op.get_bind()
    permissions = {
        "knowledge.manage": ("company_admin", "content_admin"),
        "ai.generate": ("company_admin", "content_admin", "sales"),
        "ai.audit": ("company_admin", "content_admin"),
    }
    for code, roles in permissions.items():
        role_list = ",".join(f"'{role}'" for role in roles)
        connection.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id,permission_code,created_at) "
                "SELECT id,:code,CURRENT_TIMESTAMP FROM tenant_roles "
                f"WHERE code IN ({role_list})"
            ),
            {"code": code},
        )  # noqa: S608


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_code IN "
            "('knowledge.manage','ai.generate','ai.audit')"
        )
    )
    op.drop_table("ai_interactions")
    op.drop_table("ai_configurations")
    op.drop_table("knowledge_sources")
