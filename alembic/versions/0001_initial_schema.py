"""Boshlang'ich sxema: barcha jadvallar va Enrollment partial unique index.

Revision ID: 0001
Revises:
Create Date: 2026-07-29
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(150), nullable=False, unique=True),
        sa.Column("phone", sa.String(30), nullable=True, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("student", "teacher", "manager", "superadmin", name="user_role"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", "blocked", name="user_status"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "teacher_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("specialization", sa.String(100), nullable=True),
        sa.Column("experience_years", sa.Integer(), nullable=False),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "student_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("replaced_by_token_hash", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"])

    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("teacher_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subject", sa.String(100), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "archived", name="course_status"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_courses_subject", "courses", ["subject"])

    op.create_table(
        "groups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("course_id", sa.Uuid(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("teacher_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("schedule", sa.String(200), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "closed", "archived", name="group_status"),
            nullable=False,
        ),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "lessons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "group_id", sa.Uuid(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("kinescope_video_id", sa.String(100), nullable=False),
        sa.Column("kinescope_url", sa.String(500), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id", sa.Uuid(), sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "status",
            sa.Enum(
                "awaiting_payment",
                "waitlisted",
                "active",
                "expired",
                "cancelled",
                name="enrollment_status",
            ),
            nullable=False,
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("waitlist_position", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # PARTIAL unique index — oddiy UNIQUE(student_id, group_id) EMAS.
    # Faqat yakunlanmagan yozilishlar cheklanadi, shu sababli bekor qilingan yoki
    # muddati o'tgan yozuvdan keyin student o'sha guruhga qayta yozila oladi.
    # Alembic autogenerate partial index'ni ishonchli yarata olmaydi — shuning uchun raw SQL.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_enrollment_active_per_group
        ON enrollments (student_id, group_id)
        WHERE status IN ('awaiting_payment', 'waitlisted', 'active')
        """
    )

    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "lesson_id",
            sa.Uuid(),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("watched", sa.Boolean(), nullable=False),
        sa.Column("watched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("student_id", "lesson_id", name="uq_lesson_progress_student_lesson"),
    )

    op.create_table(
        "payment_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "enrollment_id",
            sa.Uuid(),
            sa.ForeignKey("enrollments.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("installments_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "completed", "cancelled", name="payment_plan_status"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "installments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "payment_plan_id",
            sa.Uuid(),
            sa.ForeignKey("payment_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("amount_due", sa.Numeric(10, 2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "paid", "overdue", name="installment_status"),
            nullable=False,
        ),
        sa.UniqueConstraint("payment_plan_id", "sequence_number", name="uq_installment_sequence"),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "enrollment_id",
            sa.Uuid(),
            sa.ForeignKey("enrollments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("student_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "installment_id", sa.Uuid(), sa.ForeignKey("installments.id"), nullable=True
        ),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("method", sa.Enum("manual", name="payment_method"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "confirmed", "rejected", name="payment_status"),
            nullable=False,
        ),
        sa.Column("confirmed_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "type",
            sa.Enum(
                "profile_approved",
                "profile_rejected",
                "payment_confirmed",
                "payment_rejected",
                "enrollment_activated",
                "waitlist_promoted",
                "group_assigned",
                "lesson_added",
                "installment_overdue",
                "enrollment_expired",
                "account_blocked",
                "account_unblocked",
                name="notification_type",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "entity_type",
            sa.Enum("course", "group", "lesson", name="audit_entity_type"),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column(
            "action",
            sa.Enum("create", "update", "delete", "restore", name="audit_action"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notifications")
    op.drop_table("payments")
    op.drop_table("installments")
    op.drop_table("payment_plans")
    op.drop_table("lesson_progress")
    op.execute("DROP INDEX IF EXISTS uq_enrollment_active_per_group")
    op.drop_table("enrollments")
    op.drop_table("lessons")
    op.drop_table("groups")
    op.drop_table("courses")
    op.drop_table("refresh_tokens")
    op.drop_table("student_profiles")
    op.drop_table("teacher_profiles")
    op.drop_table("users")

    for enum_name in (
        "audit_action",
        "audit_entity_type",
        "notification_type",
        "payment_status",
        "payment_method",
        "installment_status",
        "payment_plan_status",
        "enrollment_status",
        "group_status",
        "course_status",
        "user_status",
        "user_role",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
