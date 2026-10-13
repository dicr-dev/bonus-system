"""Create a corrected calculation version without reloading unrelated task data.

Preview by default; --apply preserves the original snapshot and its items.
"""
import argparse
import asyncio
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from cr_portal.db.session import async_session_factory
from cr_portal.models.bonus import BonusCalculation, BonusCalculationItem
from cr_portal.models.deal import Deal
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.bonus import add_months, dt, implementation_bonus_stopped, money


async def correct(employee_id: UUID, month: date, deal_bitrix_id: int, apply: bool):
    async with async_session_factory() as session:
        previous = (await session.execute(select(BonusCalculation).where(
            BonusCalculation.employee_id == employee_id,
            BonusCalculation.month == month,
        ).order_by(BonusCalculation.version.desc()).limit(1).with_for_update())).scalar_one()
        deal = (await session.execute(select(Deal).where(Deal.bitrix_id == deal_bitrix_id))).scalar_one()
        business = await get_business_settings(session)
        support = list((await session.execute(select(Deal).where(
            Deal.funnel == "support", Deal.status == "lost",
        ))).scalars())
        if not implementation_bonus_stopped(deal, support, business.field_source_deal_id, dt(add_months(month, 1))):
            raise RuntimeError("No linked support loss before the end of the calculation month")
        items = list((await session.execute(select(BonusCalculationItem).where(
            BonusCalculationItem.calculation_id == previous.id,
        ))).scalars())
        removed = [item for item in items if item.deal_id == deal.id and item.bonus_type == "implementation"]
        if not removed:
            print(json.dumps({"status": "already_excluded", "calculation_id": str(previous.id), "version": previous.version}))
            return
        kept = [item for item in items if item not in removed]
        divider = Decimal(json.loads(previous.rules_snapshot_json)["divider"])
        subtotal = money(sum((item.amount_before_divider for item in kept if item.divider_applied), Decimal(0)))
        non_dividable = sum((item.amount_before_divider for item in kept if not item.divider_applied), Decimal(0))
        total = money(subtotal / divider + non_dividable)
        result = {"previous_calculation_id": str(previous.id), "previous_version": previous.version,
                  "old_total": str(previous.total_bonus), "new_total": str(total),
                  "removed_before_divider": str(sum(item.amount_before_divider for item in removed)),
                  "removed_final": str(sum(item.amount_final for item in removed)), "apply": apply}
        if apply:
            values = {column.name: getattr(previous, column.name) for column in BonusCalculation.__table__.columns
                      if column.name not in {"id", "created_at", "version", "details_json"}}
            corrected = BonusCalculation(**values, version=previous.version + 1,
                details_json=json.dumps({"correction": {"reason": "linked_support_lost", "previous_calculation_id": str(previous.id), "excluded_deal_bitrix_id": deal_bitrix_id}}))
            corrected.subtotal_dividable = subtotal
            corrected.total_bonus = total
            corrected.implementation_total = money(sum((item.base_amount for item in kept if item.bonus_type in {"implementation", "cr_start_implementation"}), Decimal(0)))
            session.add(corrected)
            await session.flush()
            for item in kept:
                values = {column.name: getattr(item, column.name) for column in BonusCalculationItem.__table__.columns
                          if column.name not in {"id", "calculation_id"}}
                session.add(BonusCalculationItem(**values, calculation_id=corrected.id))
            result.update({"calculation_id": str(corrected.id), "version": corrected.version})
            await session.commit()
        print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--employee-id", required=True, type=UUID)
    parser.add_argument("--month", required=True, type=date.fromisoformat)
    parser.add_argument("--deal-id", required=True, type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.month.day != 1:
        parser.error("--month must be the first day of a month")
    asyncio.run(correct(args.employee_id, args.month, args.deal_id, args.apply))
