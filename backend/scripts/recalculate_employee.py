"""Preview or persist a scoped employee calculation using current Bitrix data."""
import argparse
import asyncio
import json
from datetime import date
from uuid import UUID

from sqlalchemy import func, select

from cr_portal.api.deps import bitrix_client
from cr_portal.db.session import async_session_factory
from cr_portal.models.bonus import BonusCalculation, BonusCalculationItem
from cr_portal.models.deal import Deal
from cr_portal.services.bonus import calculate_month


async def recalculate(args):
    async with async_session_factory() as session:
        previous = (await session.execute(select(BonusCalculation).where(
            BonusCalculation.employee_id == args.employee_id,
            BonusCalculation.month == args.month,
        ).order_by(BonusCalculation.version.desc()).limit(1))).scalar_one()
        unrelated_query = select(func.count()).select_from(BonusCalculation).where(
            BonusCalculation.month == args.month,
            BonusCalculation.employee_id != args.employee_id,
        )
        unrelated_count = await session.scalar(unrelated_query)
        client = await bitrix_client(session)
        print(json.dumps({"status": "calculating", "previous_version": previous.version}), flush=True)
        calculations = await calculate_month(session, args.month, client=client,
                                              employee_ids={args.employee_id}, commit=False)
        await session.flush()
        if len(calculations) != 1 or calculations[0].employee_id != args.employee_id:
            raise RuntimeError("Expected one calculation for the selected employee")
        if await session.scalar(unrelated_query) != unrelated_count:
            raise RuntimeError("Other employees' calculations changed during preview; retry")
        calculation = calculations[0]
        items = list((await session.execute(select(BonusCalculationItem).where(
            BonusCalculationItem.calculation_id == calculation.id,
        ))).scalars())
        previous_items = list((await session.execute(select(BonusCalculationItem).where(
            BonusCalculationItem.calculation_id == previous.id,
        ))).scalars())
        def amounts(rows):
            totals = {}
            for item in rows:
                key = (item.bonus_type, item.source_external_id)
                totals[key] = totals.get(key, 0) + item.amount_final
            return totals
        old_amounts, new_amounts = amounts(previous_items), amounts(items)
        changes = [{"type": key[0], "source_id": key[1],
                    "old_final": str(old_amounts.get(key, 0)), "new_final": str(new_amounts.get(key, 0))}
                   for key in old_amounts.keys() | new_amounts.keys()
                   if old_amounts.get(key, 0) != new_amounts.get(key, 0)]
        expected_items = []
        if args.expected_deal_id:
            deal = (await session.execute(select(Deal).where(Deal.bitrix_id == args.expected_deal_id))).scalar_one()
            expected_items = [item for item in items if item.deal_id == deal.id and item.bonus_type == "implementation"]
            if not expected_items:
                raise RuntimeError("Expected implementation deal is still missing; calculation not saved")
        result = {"old_total": str(previous.total_bonus), "new_total": str(calculation.total_bonus),
                  "previous_version": previous.version, "version": calculation.version,
                  "calculation_id": str(calculation.id), "apply": args.apply,
                  "expected_items": [{"type": item.bonus_type, "base": str(item.base_amount),
                                      "rate": str(item.rate), "before_divider": str(item.amount_before_divider),
                                      "final": str(item.amount_final), "details": json.loads(item.details_json)}
                                     for item in expected_items], "other_employees_unchanged": True,
                  "changes": changes}
        if args.apply:
            await session.commit()
        else:
            await session.rollback()
        print(json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--employee-id", required=True, type=UUID)
    parser.add_argument("--month", required=True, type=date.fromisoformat)
    parser.add_argument("--expected-deal-id", type=int)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.month.day != 1:
        parser.error("--month must be the first day of a month")
    asyncio.run(recalculate(args))
