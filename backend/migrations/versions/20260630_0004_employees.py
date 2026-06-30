"""Add the V0.4.0 employee and invitation tables.

Revision ID: 20260630_0004
Revises: 20260630_0003
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260630_0004"
down_revision: str | None = "20260630_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALL_ROLE_PERMISSIONS = ("employee.read", "employee.self_update")
ADMIN_PERMISSIONS = (
    "employee.create",
    "employee.update",
    "employee.status",
    "employee.import",
    "employee.invite",
)


def upgrade() -> None:
    with op.batch_alter_table("companies") as batch_op:
        batch_op.add_column(
            sa.Column(
                "inactive_employee_visibility",
                sa.String(length=32),
                nullable=False,
                server_default="hidden",
            )
        )
        batch_op.add_column(
            sa.Column(
                "employee_self_editable_fields",
                sa.JSON(),
                nullable=False,
                server_default='["avatar_url","phone","bio"]',
            )
        )

    op.create_table(
        "employees",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("employee_no", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("position", sa.String(length=100), nullable=True),
        sa.Column("department_id", sa.String(length=36), nullable=True),
        sa.Column("manager_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column(
            "account_disabled_by_employee", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["manager_id"], ["employees.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "employee_no", name="uq_employees_company_no"),
        sa.UniqueConstraint("company_id", "phone", name="uq_employees_company_phone"),
        sa.UniqueConstraint("company_id", "email", name="uq_employees_company_email"),
    )
    op.create_index("ix_employees_company_id", "employees", ["company_id"])
    op.create_index("ix_employees_company_department", "employees", ["company_id", "department_id"])
    op.create_index("ix_employees_company_status", "employees", ["company_id", "status"])
    op.create_index("ix_employees_department_id", "employees", ["department_id"])
    op.create_index("ix_employees_manager_id", "employees", ["manager_id"])
    op.create_index("ix_employees_status", "employees", ["status"])
    op.create_index("ix_employees_user_id", "employees", ["user_id"], unique=True)

    op.create_table(
        "employee_invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("employee_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_employee_invitations_company_id", "employee_invitations", ["company_id"])
    op.create_index("ix_employee_invitations_employee_id", "employee_invitations", ["employee_id"])
    op.create_index("ix_employee_invitations_expires_at", "employee_invitations", ["expires_at"])
    op.create_index(
        "ix_employee_invitations_token_hash", "employee_invitations", ["token_hash"], unique=True
    )
    op.create_index("ix_employee_invitations_user_id", "employee_invitations", ["user_id"])

    connection = op.get_bind()
    for permission_code in ALL_ROLE_PERMISSIONS:
        connection.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role_id, permission_code, created_at)
                SELECT id, :permission_code, CURRENT_TIMESTAMP
                FROM tenant_roles
                WHERE code IN ('company_admin', 'content_admin', 'sales', 'employee')
                """
            ),
            {"permission_code": permission_code},
        )
    for permission_code in ADMIN_PERMISSIONS:
        connection.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role_id, permission_code, created_at)
                SELECT id, :permission_code, CURRENT_TIMESTAMP
                FROM tenant_roles
                WHERE code = 'company_admin'
                """
            ),
            {"permission_code": permission_code},
        )


def downgrade() -> None:
    permissions = (*ALL_ROLE_PERMISSIONS, *ADMIN_PERMISSIONS)
    op.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_code IN :permissions").bindparams(
            sa.bindparam("permissions", expanding=True, value=permissions)
        )
    )
    op.drop_table("employee_invitations")
    op.drop_table("employees")
    with op.batch_alter_table("companies") as batch_op:
        batch_op.drop_column("employee_self_editable_fields")
        batch_op.drop_column("inactive_employee_visibility")
