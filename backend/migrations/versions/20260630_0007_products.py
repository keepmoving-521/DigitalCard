"""Add V0.7.0 products and material library.

Revision ID: 20260630_0007
Revises: 20260630_0006
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260630_0007"
down_revision: str | None = "20260630_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("access", sa.String(length=20), nullable=False, server_default="private"),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_materials_company_id", "materials", ["company_id"])
    op.create_index("ix_materials_kind", "materials", ["kind"])
    op.create_index("ix_materials_access", "materials", ["access"])
    op.create_index("ix_materials_company_kind", "materials", ["company_id", "kind"])

    op.create_table(
        "product_categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "code", name="uq_product_categories_company_code"),
    )
    op.create_index("ix_product_categories_company_id", "product_categories", ["company_id"])
    op.create_index("ix_product_categories_is_active", "product_categories", ["is_active"])

    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("category_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("specifications", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("cover_material_id", sa.String(length=36), nullable=True),
        sa.Column("video_material_id", sa.String(length=36), nullable=True),
        sa.Column("gallery_material_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("attachment_material_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("video_url", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("offline_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cover_material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["video_material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_company_id", "products", ["company_id"])
    op.create_index("ix_products_category_id", "products", ["category_id"])
    op.create_index("ix_products_status", "products", ["status"])
    op.create_index(
        "ix_products_company_status_sort", "products", ["company_id", "status", "sort_order"]
    )

    connection = op.get_bind()
    permissions = {
        "product.read": ("company_admin", "content_admin", "sales", "employee"),
        "material.read": ("company_admin", "content_admin", "sales"),
        "product.manage": ("company_admin", "content_admin"),
        "material.manage": ("company_admin", "content_admin"),
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
                value=("product.read", "material.read", "product.manage", "material.manage"),
            )
        )
    )
    op.drop_table("products")
    op.drop_table("product_categories")
    op.drop_table("materials")
