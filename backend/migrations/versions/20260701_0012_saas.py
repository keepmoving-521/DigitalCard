"""Add V1.3.0 SaaS plans, subscriptions and support grants.

Revision ID: 20260701_0012
Revises: 20260701_0011
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0012"
down_revision: str | None = "20260701_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRIAL_PLAN_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "saas_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("employee_limit", sa.Integer(), nullable=False),
        sa.Column("card_limit", sa.Integer(), nullable=False),
        sa.Column("storage_limit_bytes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "tenant_subscriptions",
        sa.Column("company_id", sa.String(36), primary_key=True),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="trial"),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime()),
        sa.Column("cancel_effective_at", sa.DateTime()),
        sa.Column("cancelled_at", sa.DateTime()),
        sa.Column("data_cleanup_after", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["saas_plans.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "subscription_renewals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("plan_id", sa.String(36), nullable=False),
        sa.Column("previous_expires_at", sa.DateTime(), nullable=False),
        sa.Column("new_expires_at", sa.DateTime(), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["saas_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_subscription_renewals_company_time",
        "subscription_renewals",
        ["company_id", "created_at"],
    )
    op.create_table(
        "platform_operation_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36)),
        sa.Column("actor_user_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_platform_logs_company_time", "platform_operation_logs", ["company_id", "created_at"]
    )
    op.create_table(
        "tenant_support_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("granted_to_user_id", sa.String(36), nullable=False),
        sa.Column("granted_by_user_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_to_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_support_grants_company_expiry", "tenant_support_grants", ["company_id", "expires_at"]
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO saas_plans "
            "(id,code,name,employee_limit,card_limit,storage_limit_bytes,"
            "is_active,created_at,updated_at) "
            "VALUES (:id,'trial','试用版',20,20,1073741824,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
        ),
        {"id": TRIAL_PLAN_ID},
    )
    connection.execute(
        sa.text(
            "INSERT INTO tenant_subscriptions "
            "(company_id,plan_id,status,starts_at,expires_at,updated_at) "
            "SELECT id,:plan,'trial',created_at,datetime(CURRENT_TIMESTAMP,'+14 days'),"
            "CURRENT_TIMESTAMP FROM companies"
        ),
        {"plan": TRIAL_PLAN_ID},
    )


def downgrade() -> None:
    op.drop_table("tenant_support_grants")
    op.drop_table("platform_operation_logs")
    op.drop_table("subscription_renewals")
    op.drop_table("tenant_subscriptions")
    op.drop_table("saas_plans")
