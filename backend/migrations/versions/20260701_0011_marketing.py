"""Add V1.2.0 marketing forms and campaigns.

Revision ID: 20260701_0011
Revises: 20260701_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0011"
down_revision: str | None = "20260701_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marketing_forms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("privacy_notice", sa.Text(), nullable=False),
        sa.Column("success_message", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_marketing_forms_company_active", "marketing_forms", ["company_id", "is_active"]
    )
    op.create_table(
        "campaigns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("form_id", sa.String(36), nullable=False),
        sa.Column("card_id", sa.String(36)),
        sa.Column("product_id", sa.String(36)),
        sa.Column("owner_employee_id", sa.String(36)),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("channel", sa.String(64), nullable=False, server_default="direct"),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("capacity", sa.Integer()),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("submission_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["form_id"], ["marketing_forms.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["card_id"], ["digital_cards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_employee_id"], ["employees.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_campaigns_company_status", "campaigns", ["company_id", "status"])
    op.create_index("ix_campaigns_time", "campaigns", ["starts_at", "ends_at"])
    op.create_table(
        "campaign_submissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("campaign_id", sa.String(36), nullable=False),
        sa.Column("lead_id", sa.String(36)),
        sa.Column("form_revision", sa.Integer(), nullable=False),
        sa.Column("form_snapshot", sa.JSON(), nullable=False),
        sa.Column("values", sa.JSON(), nullable=False),
        sa.Column("contact_hash", sa.String(64), nullable=False),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(64), nullable=False),
        sa.Column("privacy_agreed", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="submitted"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_campaign_submissions_campaign_time",
        "campaign_submissions",
        ["campaign_id", "created_at"],
    )
    op.create_index(
        "ix_campaign_submissions_company_status", "campaign_submissions", ["company_id", "status"]
    )
    op.create_index(
        "ix_campaign_submissions_contact", "campaign_submissions", ["campaign_id", "contact_hash"]
    )
    op.create_index(
        "ix_campaign_submissions_ip_time",
        "campaign_submissions",
        ["campaign_id", "ip_hash", "created_at"],
    )
    connection = op.get_bind()
    permissions = {
        "marketing.read": ("company_admin", "content_admin", "sales"),
        "marketing.manage": ("company_admin", "content_admin"),
        "marketing.export": ("company_admin", "content_admin"),
    }
    for code, roles in permissions.items():
        role_list = ",".join(f"'{role}'" for role in roles)
        connection.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_code, created_at) "
                "SELECT id, :code, CURRENT_TIMESTAMP FROM tenant_roles "
                f"WHERE code IN ({role_list})"
            ),
            {"code": code},
        )  # noqa: S608


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_code IN "
            "('marketing.read','marketing.manage','marketing.export')"
        )
    )
    op.drop_table("campaign_submissions")
    op.drop_table("campaigns")
    op.drop_table("marketing_forms")
