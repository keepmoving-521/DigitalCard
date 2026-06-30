"""Add the V0.3.0 tenant, organization and permission tables.

Revision ID: 20260630_0003
Revises: 20260630_0002
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260630_0003"
down_revision: str | None = "20260630_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("logo_url", sa.String(length=1024), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.String(length=100), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_companies_code", "companies", ["code"], unique=True)
    op.create_index("ix_companies_status", "companies", ["status"])

    op.create_table(
        "departments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "code", name="uq_departments_company_code"),
    )
    op.create_index("ix_departments_company_id", "departments", ["company_id"])
    op.create_index("ix_departments_company_parent", "departments", ["company_id", "parent_id"])
    op.create_index("ix_departments_is_active", "departments", ["is_active"])

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("company_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("department_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_users_company_id_companies",
            "companies",
            ["company_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_users_department_id_departments",
            "departments",
            ["department_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_users_company_id", ["company_id"])
        batch_op.create_index("ix_users_department_id", ["department_id"])

    op.execute("UPDATE users SET role = 'platform_admin' WHERE role = 'admin'")
    op.execute("UPDATE users SET role = 'employee' WHERE role = 'user'")

    op.create_table(
        "tenant_roles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "code", name="uq_tenant_roles_company_code"),
    )
    op.create_index("ix_tenant_roles_company_id", "tenant_roles", ["company_id"])

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(length=36), nullable=False),
        sa.Column("permission_code", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["tenant_roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("role_id", "permission_code"),
    )

    op.create_table(
        "tenant_audits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_audits_company_id", "tenant_audits", ["company_id"])
    op.create_index(
        "ix_tenant_audits_company_created", "tenant_audits", ["company_id", "created_at"]
    )
    op.create_index("ix_tenant_audits_created_at", "tenant_audits", ["created_at"])


def downgrade() -> None:
    op.drop_table("tenant_audits")
    op.drop_table("role_permissions")
    op.drop_table("tenant_roles")
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'platform_admin'")
    op.execute("UPDATE users SET role = 'user' WHERE role != 'admin'")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_department_id")
        batch_op.drop_index("ix_users_company_id")
        batch_op.drop_constraint("fk_users_department_id_departments", type_="foreignkey")
        batch_op.drop_constraint("fk_users_company_id_companies", type_="foreignkey")
        batch_op.drop_column("department_id")
        batch_op.drop_column("company_id")
    op.drop_table("departments")
    op.drop_table("companies")
