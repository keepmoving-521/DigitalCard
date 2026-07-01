"""Add V0.9.0 customer CRM and opportunities.

Revision ID: 20260701_0009
Revises: 20260701_0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0009"
down_revision: str | None = "20260701_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("owner_employee_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("primary_contact", sa.String(320), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("merged_into_id", sa.String(36), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["merged_into_id"], ["customers.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_customers_company_id", "customers", ["company_id"])
    op.create_index("ix_customers_company_owner", "customers", ["company_id", "owner_employee_id"])
    op.create_index("ix_customers_company_status", "customers", ["company_id", "status"])
    op.create_table(
        "customer_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("contact_type", sa.String(32), nullable=False),
        sa.Column("contact_value", sa.String(320), nullable=False),
        sa.Column("position", sa.String(100), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_customer_contacts_company_id", "customer_contacts", ["company_id"])
    op.create_index(
        "ix_customer_contacts_customer", "customer_contacts", ["customer_id", "sort_order"]
    )
    op.create_table(
        "follow_ups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("created_by_user_id", sa.String(36), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("next_follow_up_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_follow_ups_company_id", "follow_ups", ["company_id"])
    op.create_index("ix_follow_ups_customer_occurred", "follow_ups", ["customer_id", "occurred_at"])
    op.create_table(
        "customer_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_customer_events_company_id", "customer_events", ["company_id"])
    op.create_index(
        "ix_customer_events_customer_occurred", "customer_events", ["customer_id", "occurred_at"]
    )
    op.create_table(
        "opportunity_stages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("probability", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_won", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_lost", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", "code", name="uq_opportunity_stages_company_code"),
    )
    op.create_index("ix_opportunity_stages_company_id", "opportunity_stages", ["company_id"])
    op.create_index(
        "ix_opportunity_stages_company_sort", "opportunity_stages", ["company_id", "sort_order"]
    )
    op.create_table(
        "opportunities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=False),
        sa.Column("owner_employee_id", sa.String(36), nullable=False),
        sa.Column("stage_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("expected_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_employee_id"], ["employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["stage_id"], ["opportunity_stages.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_opportunities_company_id", "opportunities", ["company_id"])
    op.create_index("ix_opportunities_company_stage", "opportunities", ["company_id", "stage_id"])
    op.create_index("ix_opportunities_customer", "opportunities", ["customer_id"])
    op.create_table(
        "opportunity_stage_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("opportunity_id", sa.String(36), nullable=False),
        sa.Column("from_stage_id", sa.String(36), nullable=True),
        sa.Column("to_stage_id", sa.String(36), nullable=False),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["from_stage_id"], ["opportunity_stages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["to_stage_id"], ["opportunity_stages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_opportunity_history_opportunity",
        "opportunity_stage_history",
        ["opportunity_id", "changed_at"],
    )
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("converted_customer_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_leads_converted_customer",
            "customers",
            ["converted_customer_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_leads_converted_customer_id", ["converted_customer_id"])

    connection = op.get_bind()
    permission_roles = {
        "customer.read": ("company_admin", "content_admin", "sales"),
        "customer.all_manage": ("company_admin",),
        "customer.self_manage": ("company_admin", "sales"),
        "opportunity.manage": ("company_admin", "sales"),
        "opportunity.stage.manage": ("company_admin",),
    }
    for permission_code, roles in permission_roles.items():
        role_list = ",".join(f"'{role}'" for role in roles)
        connection.execute(
            sa.text(f"""INSERT INTO role_permissions (role_id, permission_code, created_at)
            SELECT id, :permission_code, CURRENT_TIMESTAMP FROM tenant_roles
            WHERE code IN ({role_list})"""),  # noqa: S608
            {"permission_code": permission_code},
        )
    stages = (
        ("initial", "初步接洽", 10, 10, 0, 0),
        ("proposal", "方案沟通", 20, 40, 0, 0),
        ("negotiation", "商务谈判", 30, 70, 0, 0),
        ("won", "成交", 40, 100, 1, 0),
        ("lost", "丢单", 50, 0, 0, 1),
    )
    for code, name, order, probability, won, lost in stages:
        connection.execute(
            sa.text("""INSERT INTO opportunity_stages
            (id, company_id, code, name, sort_order, probability, is_won, is_lost,
             is_active, created_at, updated_at)
            SELECT lower(hex(randomblob(16))), id, :code, :name, :sort_order,
                   :probability, :won, :lost, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM companies"""),
            {
                "code": code,
                "name": name,
                "sort_order": order,
                "probability": probability,
                "won": won,
                "lost": lost,
            },
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_code IN :permissions").bindparams(
            sa.bindparam(
                "permissions",
                expanding=True,
                value=(
                    "customer.read",
                    "customer.all_manage",
                    "customer.self_manage",
                    "opportunity.manage",
                    "opportunity.stage.manage",
                ),
            )
        )
    )
    with op.batch_alter_table("leads") as batch:
        batch.drop_index("ix_leads_converted_customer_id")
        batch.drop_constraint("fk_leads_converted_customer", type_="foreignkey")
        batch.drop_column("converted_customer_id")
    op.drop_table("opportunity_stage_history")
    op.drop_table("opportunities")
    op.drop_table("opportunity_stages")
    op.drop_table("customer_events")
    op.drop_table("follow_ups")
    op.drop_table("customer_contacts")
    op.drop_table("customers")
