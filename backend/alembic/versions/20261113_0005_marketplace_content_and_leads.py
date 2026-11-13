"""Marketplace: product publishing and features, website content pages, leads and enquiries

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "features",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "products",
        sa.Column("is_published", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column("products", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "content_pages",
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("draft_title", sa.String(length=150), nullable=False),
        sa.Column("draft_summary", sa.String(length=500), nullable=False),
        sa.Column(
            "draft_sections",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("draft_seo_description", sa.String(length=300), nullable=False),
        sa.Column("published_title", sa.String(length=150), nullable=True),
        sa.Column("published_summary", sa.String(length=500), nullable=True),
        sa.Column("published_sections", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("published_seo_description", sa.String(length=300), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.UUID(), nullable=True),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], name=op.f("fk_content_pages_company_id_companies"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["users.id"],
            name=op.f("fk_content_pages_published_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_content_pages_updated_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_pages")),
        sa.UniqueConstraint("company_id", "slug", name=op.f("uq_content_pages_company_id_slug")),
    )
    op.create_index(op.f("ix_content_pages_company_id"), "content_pages", ["company_id"])

    op.create_table(
        "leads",
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("organization", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("expected_value", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("next_follow_up", sa.Date(), nullable=True),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("marketing_consent", sa.Boolean(), nullable=False),
        sa.Column("last_enquiry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_leads_email_lowercase")),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high')", name=op.f("ck_leads_priority_valid")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], name=op.f("fk_leads_company_id_companies"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["users.id"], name=op.f("fk_leads_owner_user_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_leads_product_id_products"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leads")),
        sa.UniqueConstraint(
            "company_id",
            "email",
            "product_id",
            name=op.f("uq_leads_company_id_email_product_id"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index("ix_leads_company_id_status", "leads", ["company_id", "status"])
    op.create_index(op.f("ix_leads_owner_user_id"), "leads", ["owner_user_id"])
    op.create_index(op.f("ix_leads_product_id"), "leads", ["product_id"])

    op.create_table(
        "enquiries",
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("lead_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("preferred_date", sa.Date(), nullable=True),
        sa.Column("consent_privacy", sa.Boolean(), nullable=False),
        sa.Column("consent_marketing", sa.Boolean(), nullable=False),
        sa.Column("privacy_notice_version", sa.String(length=40), nullable=False),
        sa.Column("utm_source", sa.String(length=100), nullable=True),
        sa.Column("utm_medium", sa.String(length=100), nullable=True),
        sa.Column("utm_campaign", sa.String(length=100), nullable=True),
        sa.Column("referrer", sa.String(length=500), nullable=True),
        sa.Column("landing_page", sa.String(length=500), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("type IN ('contact', 'demo')", name=op.f("ck_enquiries_type_valid")),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], name=op.f("fk_enquiries_company_id_companies"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"], ["leads.id"], name=op.f("fk_enquiries_lead_id_leads"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_enquiries")),
    )
    op.create_index(op.f("ix_enquiries_company_id"), "enquiries", ["company_id"])
    op.create_index(op.f("ix_enquiries_lead_id"), "enquiries", ["lead_id"])
    op.create_index("ix_enquiries_ip_hash_created_at", "enquiries", ["ip_hash", "created_at"])
    op.create_index("ix_enquiries_email_created_at", "enquiries", ["email", "created_at"])


def downgrade() -> None:
    op.drop_table("enquiries")
    op.drop_table("leads")
    op.drop_table("content_pages")
    op.drop_column("products", "published_at")
    op.drop_column("products", "is_published")
    op.drop_column("products", "features")
