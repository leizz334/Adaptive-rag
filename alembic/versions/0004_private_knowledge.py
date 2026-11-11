"""Authoritative private knowledge ownership, revisions and generation locks."""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "private_knowledge_tenants",
        sa.Column("subject", sa.String(64), primary_key=True),
        sa.Column("generation", sa.Integer(), nullable=False),
    )
    op.create_table(
        "private_knowledge_documents",
        sa.Column("subject", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(64), primary_key=True),
        sa.Column("revision", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
    )


def downgrade():
    op.drop_table("private_knowledge_documents")
    op.drop_table("private_knowledge_tenants")
