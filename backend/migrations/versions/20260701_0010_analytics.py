"""Add V1.1.0 unified business analytics events.

Revision ID: 20260701_0010
Revises: 20260701_0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260701_0010"
down_revision: str | None = "20260701_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("company_id", sa.String(36), nullable=False),
        sa.Column("department_id", sa.String(36), nullable=True),
        sa.Column("employee_id", sa.String(36), nullable=True),
        sa.Column("card_id", sa.String(36), nullable=True),
        sa.Column("product_id", sa.String(36), nullable=True),
        sa.Column("lead_id", sa.String(36), nullable=True),
        sa.Column("customer_id", sa.String(36), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_category", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(64), nullable=False, server_default="direct"),
        sa.Column("visitor_hash", sa.String(64), nullable=True),
        sa.Column("dedupe_key", sa.String(128), nullable=False),
        sa.Column("is_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["card_id"], ["digital_cards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        "ix_business_events_company_time", "business_events", ["company_id", "occurred_at"]
    )
    op.create_index(
        "ix_business_events_employee_time", "business_events", ["employee_id", "occurred_at"]
    )
    op.create_index(
        "ix_business_events_type_time", "business_events", ["event_type", "occurred_at"]
    )
    op.create_index("ix_business_events_card_time", "business_events", ["card_id", "occurred_at"])
    op.create_index(
        "ix_business_events_product_time", "business_events", ["product_id", "occurred_at"]
    )
    op.create_index("ix_business_events_department_id", "business_events", ["department_id"])
    op.create_index("ix_business_events_lead_id", "business_events", ["lead_id"])
    op.create_index("ix_business_events_customer_id", "business_events", ["customer_id"])

    connection = op.get_bind()
    connection.execute(
        sa.text("""
        INSERT INTO business_events
        (id, company_id, department_id, employee_id, card_id, event_type, event_category,
         channel, visitor_hash, dedupe_key, is_bot, is_internal, details, occurred_at, created_at)
        SELECT lower(hex(randomblob(16))), ce.company_id, e.department_id, dc.employee_id,
               ce.card_id, ce.event_type,
               CASE WHEN ce.event_type = 'view' THEN 'view'
                    WHEN ce.event_type IN ('share_copy', 'qr_open') THEN 'share'
                    ELSE 'click' END,
               ce.source, ce.visitor_hash, 'legacy-card:' || ce.dedupe_key, 0,
               CASE WHEN ce.source = 'internal' THEN 1 ELSE 0 END,
               '{}', ce.occurred_at, ce.occurred_at
        FROM card_events ce
        JOIN digital_cards dc ON dc.id = ce.card_id
        LEFT JOIN employees e ON e.id = dc.employee_id
    """)
    )
    connection.execute(
        sa.text("""
        INSERT INTO business_events
        (id, company_id, department_id, employee_id, card_id, product_id, lead_id,
         event_type, event_category, channel, visitor_hash, dedupe_key, is_bot,
         is_internal, details, occurred_at, created_at)
        SELECT lower(hex(randomblob(16))), l.company_id, e.department_id, l.owner_employee_id,
               l.card_id, l.product_id, l.id, 'lead_submitted', 'lead', l.source, NULL,
               'legacy-lead:' || l.id || '-' || 'submitted', 0,
               CASE WHEN l.source = 'internal' THEN 1 ELSE 0 END,
               '{}', l.created_at, l.created_at
        FROM leads l
        LEFT JOIN employees e ON e.id = l.owner_employee_id
    """)
    )
    connection.execute(
        sa.text("""
        INSERT INTO business_events
        (id, company_id, department_id, employee_id, card_id, product_id, lead_id,
         customer_id, event_type, event_category, channel, dedupe_key, is_bot,
         is_internal, details, occurred_at, created_at)
        SELECT lower(hex(randomblob(16))), l.company_id, e.department_id,
               COALESCE(l.assigned_employee_id, l.owner_employee_id), l.card_id, l.product_id,
               l.id, l.converted_customer_id, 'lead_converted', 'conversion', l.source,
               'legacy-lead:' || l.id || '-' || 'converted', 0,
               CASE WHEN l.source = 'internal' THEN 1 ELSE 0 END,
               '{}', l.updated_at, l.updated_at
        FROM leads l
        LEFT JOIN employees e ON e.id = COALESCE(l.assigned_employee_id, l.owner_employee_id)
        WHERE l.converted_customer_id IS NOT NULL
    """)
    )
    permissions = {
        "analytics.read": ("company_admin", "content_admin", "sales", "employee"),
        "analytics.all": ("company_admin", "content_admin"),
        "analytics.export": ("company_admin", "content_admin"),
    }
    for permission_code, roles in permissions.items():
        role_list = ",".join(f"'{role}'" for role in roles)
        connection.execute(
            sa.text(f"""INSERT INTO role_permissions (role_id, permission_code, created_at)
            SELECT id, :permission_code, CURRENT_TIMESTAMP FROM tenant_roles
            WHERE code IN ({role_list})"""),  # noqa: S608
            {"permission_code": permission_code},
        )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_code IN :permissions").bindparams(
            sa.bindparam(
                "permissions",
                expanding=True,
                value=("analytics.read", "analytics.all", "analytics.export"),
            )
        )
    )
    op.drop_table("business_events")
