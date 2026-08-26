"""KPI and bonus calculation core.

Revision ID: 0004_kpi_bonus
Revises: 0003_impl_resp
"""
from uuid import uuid4
import sqlalchemy as sa
from alembic import op

revision = "0004_kpi_bonus"
down_revision = "0003_impl_resp"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("deals", sa.Column("updated_time", sa.DateTime(timezone=True), nullable=True))
    op.add_column("deals", sa.Column("source_deal_bitrix_id", sa.Integer(), nullable=True))
    op.add_column("deals", sa.Column("sales_bonus_user_id", sa.Uuid(), nullable=True))
    op.create_index("ix_deals_source_deal_bitrix_id", "deals", ["source_deal_bitrix_id"])
    op.create_index("ix_deals_sales_bonus_user_id", "deals", ["sales_bonus_user_id"])
    op.create_foreign_key(
        "fk_deals_sales_bonus_user_id_users", "deals", "users",
        ["sales_bonus_user_id"], ["id"], ondelete="SET NULL"
    )
    op.execute("UPDATE deals SET status='won' WHERE status='success'")
    op.execute("UPDATE deals SET status='lost' WHERE status='failed'")

    op.create_table(
        "bonus_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_bonus_rules"),
        sa.UniqueConstraint("version", name="uq_bonus_rules_version"),
    )
    op.create_index("ix_bonus_rules_effective_from", "bonus_rules", ["effective_from"])

    op.add_column("bonus_calculations", sa.Column("month", sa.Date(), nullable=True))
    op.add_column("bonus_calculations", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("bonus_calculations", sa.Column("status", sa.String(32), nullable=False, server_default="completed"))
    op.add_column("bonus_calculations", sa.Column("rules_version", sa.Integer(), nullable=True))
    op.add_column("bonus_calculations", sa.Column("rules_snapshot_json", sa.Text(), nullable=True))
    op.add_column("bonus_calculations", sa.Column("subtotal_dividable", sa.Numeric(14,2), nullable=False, server_default="0"))
    op.add_column("bonus_calculations", sa.Column("cr_start_fixed_total", sa.Numeric(14,2), nullable=False, server_default="0"))
    op.add_column("bonus_calculations", sa.Column("issues_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("bonus_calculations", sa.Column("initiated_by_id", sa.Uuid(), nullable=True))
    op.create_index("ix_bonus_calculations_month", "bonus_calculations", ["month"])
    op.create_foreign_key(
        "fk_bonus_calculations_initiated_by_id_users",
        "bonus_calculations", "users", ["initiated_by_id"], ["id"], ondelete="SET NULL"
    )

    op.create_table(
        "bonus_calculation_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("calculation_id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("bonus_type", sa.String(64), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False, server_default="deal"),
        sa.Column("source_external_id", sa.String(128), nullable=True),
        sa.Column("base_amount", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("rate", sa.Numeric(14,6), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Numeric(14,2), nullable=False, server_default="1"),
        sa.Column("amount_before_divider", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("divider_applied", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("amount_final", sa.Numeric(14,2), nullable=False, server_default="0"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.PrimaryKeyConstraint("id", name="pk_bonus_calculation_items"),
        sa.ForeignKeyConstraint(["calculation_id"], ["bonus_calculations.id"], name="fk_bonus_items_calc", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], name="fk_bonus_items_employee", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], name="fk_bonus_items_deal", ondelete="SET NULL"),
    )
    op.create_index("ix_bonus_items_calculation_id", "bonus_calculation_items", ["calculation_id"])
    op.create_index("ix_bonus_items_employee_id", "bonus_calculation_items", ["employee_id"])
    op.create_index("ix_bonus_items_deal_id", "bonus_calculation_items", ["deal_id"])

    op.create_table(
        "monthly_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("plan_value", sa.Numeric(14,2), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("author_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_monthly_plans"),
        sa.UniqueConstraint("month", name="uq_monthly_plans_month"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], name="fk_monthly_plans_author", ondelete="SET NULL"),
    )
    op.create_index("ix_monthly_plans_month", "monthly_plans", ["month"])

    op.create_table(
        "kpi_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(128), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("value", sa.Numeric(14,2), nullable=False, server_default="1"),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_kpi_events"),
        sa.UniqueConstraint("event_key", name="uq_kpi_events_event_key"),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], name="fk_kpi_events_employee", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], name="fk_kpi_events_deal", ondelete="CASCADE"),
    )
    op.create_index("ix_kpi_events_month", "kpi_events", ["month"])
    op.create_index("ix_kpi_events_employee_id", "kpi_events", ["employee_id"])

    op.create_table(
        "calculation_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("calculation_id", sa.Uuid(), nullable=True),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=True),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_calculation_issues"),
        sa.ForeignKeyConstraint(["calculation_id"], ["bonus_calculations.id"], name="fk_issues_calc", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], name="fk_issues_employee", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], name="fk_issues_deal", ondelete="SET NULL"),
    )
    op.create_index("ix_calculation_issues_month", "calculation_issues", ["month"])

    op.create_table(
        "manual_bonus_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Numeric(14,2), nullable=False, server_default="1"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_manual_bonus_events"),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], name="fk_manual_event_employee", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], name="fk_manual_event_deal", ondelete="SET NULL"),
    )

    default_config = (
        '{"divider":"2.5","tech_integration_rate":"0.50","sales_rate":"0.10",'
        '"support_hour_rate":"200","training_bonus":"2000","cr_start_fixed":"10000",'
        '"implementation_thresholds":[{"from":"0","rate":"0.10"},{"from":"100000","rate":"0.11"},'
        '{"from":"150000","rate":"0.12"},{"from":"175000","rate":"0.13"},{"from":"200000","rate":"0.15"}],'
        '"current_clients_tiers":[{"from":1,"to":99,"bonus":"1000"},{"from":100,"to":299,"bonus":"2000"},'
        '{"from":300,"to":499,"bonus":"3000"},{"from":500,"to":null,"bonus":"4000"}]}'
    )
    op.execute(
        sa.text(
            "INSERT INTO bonus_rules (id, version, effective_from, effective_to, config_json, comment) "
            "VALUES (:id, 1, DATE '2020-01-01', NULL, :config, :comment)"
        ).bindparams(
            id=uuid4(),
            config=default_config,
            comment="Initial approved CR Integration Portal rules",
        )
    )

def downgrade() -> None:
    op.drop_table("manual_bonus_events")
    op.drop_table("calculation_issues")
    op.drop_table("kpi_events")
    op.drop_table("monthly_plans")
    op.drop_table("bonus_calculation_items")
    op.drop_constraint("fk_bonus_calculations_initiated_by_id_users", "bonus_calculations", type_="foreignkey")
    op.drop_index("ix_bonus_calculations_month", table_name="bonus_calculations")
    for c in ["initiated_by_id","issues_count","cr_start_fixed_total","subtotal_dividable","rules_snapshot_json","rules_version","status","version","month"]:
        op.drop_column("bonus_calculations", c)
    op.drop_table("bonus_rules")
    op.drop_constraint("fk_deals_sales_bonus_user_id_users", "deals", type_="foreignkey")
    op.drop_index("ix_deals_sales_bonus_user_id", table_name="deals")
    op.drop_index("ix_deals_source_deal_bitrix_id", table_name="deals")
    op.drop_column("deals", "sales_bonus_user_id")
    op.drop_column("deals", "source_deal_bitrix_id")
    op.drop_column("deals", "updated_time")
