"""Add V0.8.0 leads and in-app notifications.

Revision ID: 20260701_0008
Revises: 20260630_0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0008"
down_revision: str | None = "20260630_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("card_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("owner_employee_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_employee_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("contact", sa.String(length=320), nullable=False),
        sa.Column("normalized_contact", sa.String(length=320), nullable=False),
        sa.Column("demand", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="direct"),
        sa.Column("privacy_agreed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="assigned"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_submitted_at", sa.DateTime(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["digital_cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_employee_id"], ["employees.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_company_id", "leads", ["company_id"])
    op.create_index("ix_leads_card_id", "leads", ["card_id"])
    op.create_index("ix_leads_product_id", "leads", ["product_id"])
    op.create_index("ix_leads_company_assignee", "leads", ["company_id", "assigned_employee_id"])
    op.create_index("ix_leads_company_status", "leads", ["company_id", "status"])
    op.create_index("ix_leads_company_contact", "leads", ["company_id", "normalized_contact"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("content", sa.String(length=500), nullable=False),
        sa.Column("related_type", sa.String(length=50), nullable=True),
        sa.Column("related_id", sa.String(length=36), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_company_id", "notifications", ["company_id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "read_at"])

    connection = op.get_bind()
    permissions = {
        "lead.read": ("company_admin", "content_admin", "sales"),
        "lead.manage": ("company_admin",),
        "lead.claim": ("company_admin", "sales"),
        "notification.read": ("company_admin", "content_admin", "sales", "employee"),
    }
    for permission_code, roles in permissions.items():
        role_list = ",".join(f"'{role}'" for role in roles)
        connection.execute(
            sa.text(
                f"""INSERT INTO role_permissions (role_id, permission_code, created_at)
                SELECT id, :permission_code, CURRENT_TIMESTAMP FROM tenant_roles
                WHERE code IN ({role_list})"""  # noqa: S608
            ),
            {"permission_code": permission_code},
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_code IN :permissions").bindparams(
            sa.bindparam(
                "permissions",
                expanding=True,
                value=("lead.read", "lead.manage", "lead.claim", "notification.read"),
            )
        )
    )
    op.drop_table("notifications")
    op.drop_table("leads")
