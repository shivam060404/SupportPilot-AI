"""Create SupportPilot persistence tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("tickets",
        sa.Column("id", sa.String(), nullable=False), sa.Column("status", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=True), sa.Column("priority", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_tickets_id", "tickets", ["id"])
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_category", "tickets", ["category"])
    op.create_table("audit_logs",
        sa.Column("id", sa.String(), nullable=False), sa.Column("session_id", sa.String(), nullable=True),
        sa.Column("action", sa.String(), nullable=True), sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_session_id", "audit_logs", ["session_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_table("session_messages",
        sa.Column("id", sa.String(), nullable=False), sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("message_json", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_session_messages_id", "session_messages", ["id"])
    op.create_index("ix_session_messages_session_id", "session_messages", ["session_id"])
    op.create_table("approval_requests",
        sa.Column("id", sa.String(), nullable=False), sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False), sa.Column("target", sa.String(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True), sa.Column("status", sa.String(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True), sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_approval_requests_id", "approval_requests", ["id"])
    op.create_index("ix_approval_requests_session_id", "approval_requests", ["session_id"])
    op.create_index("ix_approval_requests_action", "approval_requests", ["action"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])

def downgrade() -> None:
    op.drop_table("approval_requests")
    op.drop_table("session_messages")
    op.drop_table("audit_logs")
    op.drop_table("tickets")
