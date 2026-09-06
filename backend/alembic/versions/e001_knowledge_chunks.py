"""Add curated knowledge; SQLite JSON is fake-test storage only."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "e001_knowledge_chunks"
down_revision = "549733be0747"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sourcing_requests", sa.Column("knowledge_chunk_ids", sa.JSON(), nullable=False, server_default="[]"))
    postgres = op.get_context().dialect.name == "postgresql"
    if postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_ref", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("embedding", Vector(384) if postgres else sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('part_reference_note', 'vehicle_compatibility', "
            "'substitution_rule', 'procurement_policy', 'call_policy')",
            name="ck_knowledge_source_type",
        ),
        sa.UniqueConstraint("source_ref", name="uq_knowledge_source_ref"),
    )


def downgrade() -> None:
    op.drop_column("sourcing_requests", "knowledge_chunk_ids")
    op.drop_table("knowledge_chunks")
    # The vector extension may be shared by other tables/applications; retain it.
