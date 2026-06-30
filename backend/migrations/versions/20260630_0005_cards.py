"""Add V0.5.0 card templates, drafts and published snapshots.

Revision ID: 20260630_0005
Revises: 20260630_0004
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260630_0005"
down_revision: str | None = "20260630_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SELF_PERMISSIONS = ("card.read", "card.edit_self", "card.publish_self")
MANAGE_PERMISSIONS = ("card.manage", "card.template.manage")


def upgrade() -> None:
    op.create_table(
        "card_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False, server_default="企业默认模板"),
        sa.Column("theme_color", sa.String(length=7), nullable=False, server_default="#1c6a42"),
        sa.Column("logo_url", sa.String(length=1024), nullable=True),
        sa.Column(
            "module_order",
            sa.JSON(),
            nullable=False,
            server_default='["profile","contact","social","bio"]',
        ),
        sa.Column(
            "locked_fields",
            sa.JSON(),
            nullable=False,
            server_default='["theme_color","logo_url","module_order"]',
        ),
        sa.Column(
            "employee_editable_fields",
            sa.JSON(),
            nullable=False,
            server_default='["display_name","headline","avatar_url","bio","phone","email","wechat","website","socials"]',
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_card_templates_company_id", "card_templates", ["company_id"], unique=True)

    op.create_table(
        "digital_cards",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("employee_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("draft_data", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("published_data", sa.JSON(), nullable=True),
        sa.Column("draft_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("published_revision", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("offline_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "employee_id", name="uq_digital_cards_company_employee"),
    )
    op.create_index("ix_digital_cards_company_id", "digital_cards", ["company_id"])
    op.create_index("ix_digital_cards_employee_id", "digital_cards", ["employee_id"], unique=True)
    op.create_index("ix_digital_cards_status", "digital_cards", ["status"])
    op.create_index("ix_digital_cards_company_status", "digital_cards", ["company_id", "status"])

    connection = op.get_bind()
    for permission_code in SELF_PERMISSIONS:
        connection.execute(
            sa.text(
                """INSERT INTO role_permissions (role_id, permission_code, created_at)
                SELECT id, :permission_code, CURRENT_TIMESTAMP FROM tenant_roles
                WHERE code IN ('company_admin', 'content_admin', 'sales', 'employee')"""
            ),
            {"permission_code": permission_code},
        )
    for permission_code in MANAGE_PERMISSIONS:
        connection.execute(
            sa.text(
                """INSERT INTO role_permissions (role_id, permission_code, created_at)
                SELECT id, :permission_code, CURRENT_TIMESTAMP FROM tenant_roles
                WHERE code IN ('company_admin', 'content_admin')"""
            ),
            {"permission_code": permission_code},
        )


def downgrade() -> None:
    permissions = (*SELF_PERMISSIONS, *MANAGE_PERMISSIONS)
    op.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_code IN :permissions").bindparams(
            sa.bindparam("permissions", expanding=True, value=permissions)
        )
    )
    op.drop_table("digital_cards")
    op.drop_table("card_templates")
