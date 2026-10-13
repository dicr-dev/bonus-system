"""Restore user-confirmed task metadata and version an informational breakdown."""
import argparse
import asyncio
import json
from datetime import date
from uuid import UUID

from sqlalchemy import select

from cr_portal.db.session import async_session_factory
from cr_portal.models.bonus import BonusCalculation, BonusCalculationItem
from cr_portal.models.deal import Deal
from cr_portal.models.task import BitrixTask
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.bonus import raw_date


async def restore(args):
    async with async_session_factory() as session:
        task = await session.get(BitrixTask, args.task_id)
        if task is None:
            raise RuntimeError("Task is not present in local cache")
        deal = (await session.execute(select(Deal).where(Deal.bitrix_id == args.deal_id))).scalar_one()
        previous = (await session.execute(select(BonusCalculation).where(
            BonusCalculation.employee_id == args.employee_id,
            BonusCalculation.month == args.month,
        ).order_by(BonusCalculation.version.desc()).limit(1).with_for_update())).scalar_one()
        items = list((await session.execute(select(BonusCalculationItem).where(
            BonusCalculationItem.calculation_id == previous.id,
        ))).scalars())
        affected = [item for item in items if item.source_external_id == str(args.task_id)]
        if not affected or any(item.bonus_type != "task_hours_reference" or item.amount_final != 0 for item in affected):
            raise RuntimeError("Expected an existing informational task row only")
        payload = json.loads(task.raw_json or "{}")
        payload.update({"ID": str(args.task_id), "TITLE": args.title,
                        "UF_CRM_TASK": [f"D_{args.deal_id}"], "metadata_source": "user_confirmed"})
        result = {"task_id": args.task_id, "deal_id": args.deal_id,
                  "previous_version": previous.version, "total_unchanged": str(previous.total_bonus), "apply": args.apply}
        if args.apply:
            task.title = args.title
            task.crm_deal_ids_json = json.dumps([args.deal_id])
            task.raw_json = json.dumps(payload, ensure_ascii=False)
            business = await get_business_settings(session)
            commercial = raw_date(deal, business.field_cr_start_commercial_use_date)
            group = f"cr_start_{'commercial' if commercial and commercial <= args.month else 'before_commercial'}" if deal.funnel == "cr_start" else None
            values = {column.name: getattr(previous, column.name) for column in BonusCalculation.__table__.columns
                      if column.name not in {"id", "created_at", "version", "details_json"}}
            audit = json.loads(previous.details_json or "{}")
            audit["task_metadata_correction"] = {"previous_calculation_id": str(previous.id), "task_id": args.task_id, "metadata_source": "user_confirmed"}
            corrected = BonusCalculation(**values, version=previous.version + 1, details_json=json.dumps(audit))
            session.add(corrected)
            await session.flush()
            for item in items:
                values = {column.name: getattr(item, column.name) for column in BonusCalculationItem.__table__.columns
                          if column.name not in {"id", "calculation_id"}}
                if item in affected:
                    details = json.loads(item.details_json or "{}")
                    details.update({"task": payload, "client_deal_funnel": deal.funnel, "task_hours_group": group})
                    values.update(deal_id=deal.id, description=f"Справочные часы: {args.title} — {item.quantity} ч",
                                  details_json=json.dumps(details, ensure_ascii=False))
                session.add(BonusCalculationItem(**values, calculation_id=corrected.id))
            await session.commit()
            result.update(version=corrected.version, calculation_id=str(corrected.id))
        print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True, type=int)
    parser.add_argument("--deal-id", required=True, type=int)
    parser.add_argument("--title", required=True)
    parser.add_argument("--employee-id", required=True, type=UUID)
    parser.add_argument("--month", required=True, type=date.fromisoformat)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(restore(args))
