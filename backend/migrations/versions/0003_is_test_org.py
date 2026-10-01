"""add is_test to organizations

Revision ID: 0003_is_test_org
Revises: 0002_password_reset
Create Date: 2026-10-01

Additive migration: adds organizations.is_test BOOLEAN NOT NULL DEFAULT false.
Safe to run against existing data — all existing rows get false.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_is_test_org"
down_revision = "0002_password_reset"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organizations",
        sa.Column(
            "is_test",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Index to make the common query (status=ACTIVE AND is_test=false) fast.
    op.create_index(
        "ix_organizations_status_is_test",
        "organizations",
        ["status", "is_test"],
    )


def downgrade():
    op.drop_index("ix_organizations_status_is_test", table_name="organizations")
    op.drop_column("organizations", "is_test")
