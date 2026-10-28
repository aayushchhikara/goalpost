"""MVP tables: settings, planning (weeks, tasks, occurrences) and evidence

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("secret_ref", sa.String(length=128), nullable=True),
        sa.Column("cursor", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connectors")),
    )
    op.create_index(op.f("ix_connectors_user_id"), "connectors", ["user_id"], unique=False)

    op.create_table(
        "settings",
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("week_start", sa.String(length=16), nullable=False),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_settings")),
        sa.UniqueConstraint("user_id", name=op.f("uq_settings_user_id")),
    )
    op.create_table(
        "weeks",
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "planning", "active", "closed", name="weekstatus", native_enum=False, length=32
            ),
            nullable=False,
        ),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weeks")),
        sa.UniqueConstraint("user_id", "start_date", name=op.f("uq_weeks_user_id_start_date")),
    )
    op.create_index(op.f("ix_weeks_user_id"), "weeks", ["user_id"], unique=False)

    op.create_table(
        "events",
        sa.Column("connector_id", sa.String(length=26), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(
            ["connector_id"], ["connectors.id"], name=op.f("fk_events_connector_id_connectors")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
        sa.UniqueConstraint(
            "connector_id", "source_id", name=op.f("uq_events_connector_id_source_id")
        ),
    )
    op.create_index(op.f("ix_events_local_date"), "events", ["local_date"], unique=False)
    op.create_index(op.f("ix_events_user_id"), "events", ["user_id"], unique=False)

    op.create_table(
        "sync_runs",
        sa.Column("connector_id", sa.String(length=26), nullable=False),
        sa.Column(
            "trigger",
            sa.Enum(
                "startup", "schedule", "manual", name="synctrigger", native_enum=False, length=32
            ),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ok", "partial", "failed", name="syncstatus", native_enum=False, length=32),
            nullable=True,
        ),
        sa.Column("events_added", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(
            ["connector_id"], ["connectors.id"], name=op.f("fk_sync_runs_connector_id_connectors")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_runs")),
    )
    op.create_index(op.f("ix_sync_runs_connector_id"), "sync_runs", ["connector_id"], unique=False)
    op.create_index(op.f("ix_sync_runs_user_id"), "sync_runs", ["user_id"], unique=False)

    op.create_table(
        "tasks",
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("one_off", "recurring", name="taskkind", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("high", "medium", "low", name="priority", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("recurrence_days", sa.Integer(), nullable=True),
        sa.Column("in_backlog", sa.Boolean(), nullable=False),
        sa.Column("first_planned_week_id", sa.String(length=26), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "done", "dropped", name="taskstatus", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(
            ["first_planned_week_id"],
            ["weeks.id"],
            name=op.f("fk_tasks_first_planned_week_id_weeks"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(op.f("ix_tasks_user_id"), "tasks", ["user_id"], unique=False)

    op.create_table(
        "occurrences",
        sa.Column("task_id", sa.String(length=26), nullable=False),
        sa.Column("week_id", sa.String(length=26), nullable=False),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "done",
                "missed",
                "skipped",
                name="occurrencestatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("late", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_occurrences_task_id_tasks")
        ),
        sa.ForeignKeyConstraint(
            ["week_id"], ["weeks.id"], name=op.f("fk_occurrences_week_id_weeks")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_occurrences")),
        sa.UniqueConstraint(
            "task_id", "week_id", "date", name=op.f("uq_occurrences_task_id_week_id_date")
        ),
    )
    op.create_index(op.f("ix_occurrences_task_id"), "occurrences", ["task_id"], unique=False)
    op.create_index(op.f("ix_occurrences_user_id"), "occurrences", ["user_id"], unique=False)
    op.create_index(op.f("ix_occurrences_week_id"), "occurrences", ["week_id"], unique=False)

    op.create_table(
        "rules",
        sa.Column("task_id", sa.String(length=26), nullable=False),
        sa.Column("connector_type", sa.String(length=64), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=False),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_rules_task_id_tasks"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rules")),
        sa.UniqueConstraint("task_id", name=op.f("uq_rules_task_id")),
    )
    op.create_index(op.f("ix_rules_user_id"), "rules", ["user_id"], unique=False)

    op.create_table(
        "evidence",
        sa.Column("occurrence_id", sa.String(length=26), nullable=False),
        sa.Column("event_id", sa.String(length=26), nullable=False),
        sa.Column(
            "added_by",
            sa.Enum("suggestion", "manual", name="evidenceaddedby", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], name=op.f("fk_evidence_event_id_events")
        ),
        sa.ForeignKeyConstraint(
            ["occurrence_id"],
            ["occurrences.id"],
            name=op.f("fk_evidence_occurrence_id_occurrences"),
        ),
        sa.PrimaryKeyConstraint("occurrence_id", "event_id", name=op.f("pk_evidence")),
    )
    op.create_index(op.f("ix_evidence_user_id"), "evidence", ["user_id"], unique=False)

    op.create_table(
        "suggestions",
        sa.Column("occurrence_id", sa.String(length=26), nullable=False),
        sa.Column(
            "source",
            sa.Enum("rule", "ai", name="suggestionsource", native_enum=False, length=32),
            nullable=False,
        ),
        sa.Column("rule_id", sa.String(length=26), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted",
                "rejected",
                name="suggestionstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(
            ["occurrence_id"],
            ["occurrences.id"],
            name=op.f("fk_suggestions_occurrence_id_occurrences"),
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["rules.id"],
            name=op.f("fk_suggestions_rule_id_rules"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suggestions")),
    )
    op.create_index(
        op.f("ix_suggestions_occurrence_id"), "suggestions", ["occurrence_id"], unique=False
    )
    op.create_index(op.f("ix_suggestions_user_id"), "suggestions", ["user_id"], unique=False)

    op.create_table(
        "rule_exclusions",
        sa.Column("rule_id", sa.String(length=26), nullable=False),
        sa.Column("filter", sa.JSON(), nullable=False),
        sa.Column("created_from_suggestion_id", sa.String(length=26), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_from_suggestion_id"],
            ["suggestions.id"],
            name=op.f("fk_rule_exclusions_created_from_suggestion_id_suggestions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["rules.id"],
            name=op.f("fk_rule_exclusions_rule_id_rules"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_exclusions")),
    )
    op.create_index(
        op.f("ix_rule_exclusions_rule_id"), "rule_exclusions", ["rule_id"], unique=False
    )
    op.create_index(
        op.f("ix_rule_exclusions_user_id"), "rule_exclusions", ["user_id"], unique=False
    )

    op.create_table(
        "suggestion_events",
        sa.Column("suggestion_id", sa.String(length=26), nullable=False),
        sa.Column("event_id", sa.String(length=26), nullable=False),
        sa.Column("user_id", sa.String(length=26), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], name=op.f("fk_suggestion_events_event_id_events")
        ),
        sa.ForeignKeyConstraint(
            ["suggestion_id"],
            ["suggestions.id"],
            name=op.f("fk_suggestion_events_suggestion_id_suggestions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("suggestion_id", "event_id", name=op.f("pk_suggestion_events")),
    )
    op.create_index(
        op.f("ix_suggestion_events_user_id"), "suggestion_events", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_suggestion_events_user_id"), table_name="suggestion_events")

    op.drop_table("suggestion_events")
    op.drop_index(op.f("ix_rule_exclusions_user_id"), table_name="rule_exclusions")
    op.drop_index(op.f("ix_rule_exclusions_rule_id"), table_name="rule_exclusions")

    op.drop_table("rule_exclusions")
    op.drop_index(op.f("ix_suggestions_user_id"), table_name="suggestions")
    op.drop_index(op.f("ix_suggestions_occurrence_id"), table_name="suggestions")

    op.drop_table("suggestions")
    op.drop_index(op.f("ix_evidence_user_id"), table_name="evidence")

    op.drop_table("evidence")
    op.drop_index(op.f("ix_rules_user_id"), table_name="rules")

    op.drop_table("rules")
    op.drop_index(op.f("ix_occurrences_week_id"), table_name="occurrences")
    op.drop_index(op.f("ix_occurrences_user_id"), table_name="occurrences")
    op.drop_index(op.f("ix_occurrences_task_id"), table_name="occurrences")

    op.drop_table("occurrences")
    op.drop_index(op.f("ix_tasks_user_id"), table_name="tasks")

    op.drop_table("tasks")
    op.drop_index(op.f("ix_sync_runs_user_id"), table_name="sync_runs")
    op.drop_index(op.f("ix_sync_runs_connector_id"), table_name="sync_runs")

    op.drop_table("sync_runs")
    op.drop_index(op.f("ix_events_user_id"), table_name="events")
    op.drop_index(op.f("ix_events_local_date"), table_name="events")

    op.drop_table("events")
    op.drop_index(op.f("ix_weeks_user_id"), table_name="weeks")

    op.drop_table("weeks")
    op.drop_table("settings")
    op.drop_index(op.f("ix_connectors_user_id"), table_name="connectors")

    op.drop_table("connectors")
