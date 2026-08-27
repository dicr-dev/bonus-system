import json
from collections import defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.core.config import settings
from cr_portal.models.bonus import (
    BonusCalculation,
    BonusCalculationItem,
    ManualBonusEvent,
)
from cr_portal.models.deal import Deal
from cr_portal.models.kpi import CalculationIssue
from cr_portal.models.user import User
from cr_portal.schemas.bonus import BonusInput, BonusResult
from cr_portal.services.rules import (
    DEFAULT_RULES,
    current_client_bonus,
    decimal,
    get_rules,
    implementation_rate,
)

CENT = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def add_months(value: date, months: int) -> date:
    year = value.year + (value.month - 1 + months) // 12
    month = (value.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def dt(value: date) -> datetime:
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def end_of_month_dt(value: date) -> datetime:
    next_month = add_months(month_start(value), 1)
    return datetime.combine(next_month, time.min, tzinfo=timezone.utc)


def raw_value(deal: Deal, field_name: str):
    if not field_name or not deal.raw_json:
        return None
    try:
        data = json.loads(deal.raw_json)
    except Exception:
        return None
    return data.get(field_name)


def truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().upper() in {"Y", "YES", "TRUE", "1", "ДА", "199"}


async def add_issue(
    session: AsyncSession,
    month: date,
    severity: str,
    code: str,
    message: str,
    employee_id=None,
    deal_id=None,
):
    row = CalculationIssue(
        month=month,
        severity=severity,
        code=code,
        message=message,
        employee_id=employee_id,
        deal_id=deal_id,
        details_json="{}",
    )
    session.add(row)
    return row


def active_on_date_conditions(
    period_end_exclusive: datetime,
):
    """
    SQL-условия: сделка была активна на последнее число месяца.

    Если closed_time заполнен — используем его.
    Если closed_time пустой, но текущий статус won/lost,
    используем updated_time как резервную дату закрытия.
    """
    return (
        Deal.created_time < period_end_exclusive,
        or_(
            Deal.closed_time >= period_end_exclusive,
            (
                Deal.closed_time.is_(None)
                & (
                    (
                        Deal.status.in_(
                            ["won", "lost"]
                        )
                        & (
                            Deal.updated_time
                            >= period_end_exclusive
                        )
                    )
                    | (
                        ~Deal.status.in_(
                            ["won", "lost"]
                        )
                    )
                )
            ),
        ),
    )



def linked_deal_ids(deal: Deal) -> list[int]:
    """Возвращает все связанные ID сделок из CRM-поля сделки-источника."""
    field_name = settings.BITRIX_FIELD_SOURCE_DEAL_ID
    if not field_name or not deal.raw_json:
        return []

    try:
        data = json.loads(deal.raw_json)
    except Exception:
        return []

    value = data.get(field_name)
    if value in (None, "", []):
        return []

    values = value if isinstance(value, list) else [value]
    result: list[int] = []

    for item in values:
        if isinstance(item, dict):
            candidate = (
                item.get("ID")
                or item.get("id")
                or item.get("VALUE")
                or item.get("value")
            )
        else:
            candidate = item

        if candidate in (None, ""):
            continue

        candidate_str = str(candidate).strip()

        if candidate_str.upper().startswith("D_"):
            candidate_str = candidate_str[2:]

        if candidate_str.isdigit():
            result.append(int(candidate_str))

    return list(dict.fromkeys(result))


async def linked_implementation_deals(
    session: AsyncSession,
    support_deal: Deal,
) -> list[Deal]:
    """Ищет все связанные со сделкой Сопровождения сделки Внедрения."""
    ids = linked_deal_ids(support_deal)

    if not ids:
        return []

    result = await session.execute(
        select(Deal).where(
            Deal.bitrix_id.in_(ids),
            Deal.funnel == "implementation",
        )
    )

    return list(result.scalars().all())

def deal_active_at_period_end(
    deal: Deal,
    period_end_exclusive: datetime,
) -> bool:
    """
    Была ли сделка активна на последнее число расчётного месяца.

    Bitrix иногда не отдаёт closedTime для уже закрытых сделок.
    Поэтому для текущих won/lost при пустом closed_time используем
    updated_time как резервную дату закрытия.
    """
    if (
        deal.created_time
        and deal.created_time >= period_end_exclusive
    ):
        return False

    if deal.closed_time is not None:
        return deal.closed_time >= period_end_exclusive

    if deal.status in {"won", "lost"}:
        if deal.updated_time is not None:
            return deal.updated_time >= period_end_exclusive

        return False

    return True


def completed_implementation_for_bonus(
    deals: list[Deal],
    period_end_exclusive: datetime,
) -> Deal | None:
    """Выбирает последнее успешно завершённое Внедрение до конца месяца."""
    eligible = [
        deal
        for deal in deals
        if (
            deal.status == "won"
            and deal.closed_time is not None
            and deal.closed_time < period_end_exclusive
        )
    ]
    if not eligible:
        return None

    return max(
        eligible,
        key=lambda deal: (
            deal.closed_time,
            deal.bitrix_id,
        ),
    )


async def diagnose_month(session: AsyncSession, month: date):
    month = month_start(month)
    end = add_months(month, 1)
    start3 = add_months(month, -2)

    result = await session.execute(
        select(CalculationIssue).where(
            CalculationIssue.month == month,
            CalculationIssue.calculation_id.is_(None),
        )
    )
    for issue in result.scalars().all():
        await session.delete(issue)

    if not settings.BITRIX_FIELD_SOURCE_DEAL_ID:
        await add_issue(
            session,
            month,
            "warning",
            "SOURCE_DEAL_FIELD_NOT_CONFIGURED",
            "Не настроено поле ID сделки-источника.",
        )

    if not settings.BITRIX_FIELD_SALES_BONUS_USER_ID:
        await add_issue(
            session,
            month,
            "warning",
            "SALES_USER_FIELD_NOT_CONFIGURED",
            "Не настроено поле сотрудника, получающего бонус за продажу.",
        )

    if not settings.cr_start_boolean_fields:
        await add_issue(
            session,
            month,
            "warning",
            "CR_START_FIELDS_NOT_CONFIGURED",
            "Не настроены поля «КР Старт: ...».",
        )

    if not settings.BITRIX_TASK_TRAINING_BONUS_FIELD:
        await add_issue(
            session,
            month,
            "warning",
            "TRAINING_TASK_FIELD_NOT_CONFIGURED",
            "Не настроено поле задачи «Бонус за обучение = Да».",
        )

    tech_result = await session.execute(
        select(Deal).where(
            Deal.funnel == "tech_integration",
            Deal.status == "won",
            Deal.closed_time >= dt(month),
            Deal.closed_time < dt(end),
        )
    )
    for deal in tech_result.scalars().all():
        if deal.implementation_responsible_user_id is None:
            await add_issue(
                session,
                month,
                "critical",
                "NO_IMPLEMENTATION_RESPONSIBLE",
                "Нет «Ответственного за внедрение».",
                deal_id=deal.id,
            )

    implementation_result = await session.execute(
        select(Deal).where(
            Deal.funnel == "implementation",
            Deal.status == "won",
            Deal.closed_time >= dt(start3),
            Deal.closed_time < dt(end),
        )
    )
    for deal in implementation_result.scalars().all():
        if deal.implementation_responsible_user_id is None:
            await add_issue(
                session,
                month,
                "critical",
                "NO_IMPLEMENTATION_RESPONSIBLE",
                "Нет «Ответственного за внедрение».",
                deal_id=deal.id,
            )
        if Decimal(deal.monthly_amount or 0) <= 0:
            await add_issue(
                session,
                month,
                "critical",
                "NO_MONTHLY_AMOUNT",
                "Нет суммы оплаты в месяц.",
                employee_id=deal.implementation_responsible_user_id,
                deal_id=deal.id,
            )

    cr_start_result = await session.execute(
        select(Deal).where(
            Deal.funnel == "cr_start",
            Deal.status == "won",
            Deal.closed_time >= dt(start3),
            Deal.closed_time < dt(end),
        )
    )
    for deal in cr_start_result.scalars().all():
        if deal.implementation_responsible_user_id is None:
            await add_issue(
                session,
                month,
                "critical",
                "NO_IMPLEMENTATION_RESPONSIBLE",
                "Нет «Ответственного за внедрение».",
                deal_id=deal.id,
            )

        fields = settings.cr_start_boolean_fields
        if not fields:
            continue

        values = [raw_value(deal, field) for field in fields]
        is_fixed = any(truthy(value) for value in values)
        if is_fixed:
            continue

        if Decimal(deal.monthly_amount or 0) <= 0:
            await add_issue(
                session,
                month,
                "critical",
                "NO_MONTHLY_AMOUNT",
                "Нет суммы оплаты в месяц для CR Start, рассчитываемого как внедрение.",
                employee_id=deal.implementation_responsible_user_id,
                deal_id=deal.id,
            )

    if settings.BITRIX_FIELD_SOURCE_DEAL_ID:
        period_end_exclusive = end_of_month_dt(month)

        support_result = await session.execute(
            select(Deal).where(
                Deal.funnel == "support",
                *active_on_date_conditions(period_end_exclusive),
            )
        )

        for deal in support_result.scalars().all():
            implementations = await linked_implementation_deals(
                session,
                deal,
            )

            #
            # Если среди связанных сделок есть Внедрение,
            # которое было активно на конец месяца,
            # клиент еще не считается текущим.
            #
            active_implementation_exists = any(
                deal_active_at_period_end(
                    implementation,
                    period_end_exclusive,
                )
                for implementation in implementations
            )

            if active_implementation_exists:
                continue

            #
            # Если ссылки на Внедрение нет или Внедрение
            # среди связанных ID не найдено, бонус это НЕ блокирует.
            # Но диагностика должна показать проблему связи.
            #
            if not implementations:
                linked_ids = linked_deal_ids(deal)

                issue = await add_issue(
                    session,
                    month,
                    "warning",
                    "SUPPORT_WITHOUT_IMPLEMENTATION_LINK",
                    (
                        "У активной сделки Сопровождения "
                        "нет ссылки на сделку Внедрения."
                    ),
                    deal_id=deal.id,
                )

                issue.details_json = json.dumps(
                    {
                        "support_bitrix_id": deal.bitrix_id,
                        "support_title": deal.title,
                        "linked_bitrix_ids": linked_ids,
                    },
                    ensure_ascii=False,
                )

            #
            # Ответственного для бонуса текущего клиента
            # ВСЕГДА берем из самой сделки Сопровождения.
            #
            if (
                deal.implementation_responsible_user_id
                is None
            ):
                await add_issue(
                    session,
                    month,
                    "critical",
                    "NO_IMPLEMENTATION_RESPONSIBLE",
                    (
                        "У сделки Сопровождения нет "
                        "«Ответственного за внедрение». "
                        "Бонус текущего клиента начислить некому."
                    ),
                    deal_id=deal.id,
                )

            #
            # Количество машин также всегда берем
            # из сделки Сопровождения.
            #
            if deal.machines_count <= 0:
                await add_issue(
                    session,
                    month,
                    "warning",
                    "NO_MACHINES",
                    (
                        "Нет количества машин у активного "
                        "клиента сопровождения."
                    ),
                    employee_id=(
                        deal.implementation_responsible_user_id
                    ),
                    deal_id=deal.id,
                )

    await session.flush()

    result = await session.execute(
        select(CalculationIssue)
        .where(CalculationIssue.month == month)
        .order_by(CalculationIssue.severity, CalculationIssue.code)
    )
    return list(result.scalars().all())


async def latest_version(session: AsyncSession, employee_id, month):
    result = await session.execute(
        select(func.max(BonusCalculation.version)).where(
            BonusCalculation.employee_id == employee_id,
            BonusCalculation.month == month,
        )
    )
    return int(result.scalar_one_or_none() or 0) + 1


async def calculate_month(
    session: AsyncSession,
    month: date,
    initiated_by_id: UUID | None = None,
):
    month = month_start(month)
    end = add_months(month, 1)
    period_to = date.fromordinal(end.toordinal() - 1)

    rules_version, rules = await get_rules(session, month)
    issues = await diagnose_month(session, month)

    users_result = await session.execute(select(User))
    users = users_result.scalars().all()
    user_ids = {user.id for user in users}

    contributions = defaultdict(list)

    tech_result = await session.execute(
        select(Deal).where(
            Deal.funnel == "tech_integration",
            Deal.status == "won",
            Deal.closed_time >= dt(month),
            Deal.closed_time < dt(end),
        )
    )
    for deal in tech_result.scalars().all():
        employee_id = deal.implementation_responsible_user_id
        if not employee_id or not deal.integration_1c:
            continue

        base = Decimal(deal.opportunity or 0)
        rate = decimal(rules["tech_integration_rate"])
        before = money(base * rate)

        contributions[employee_id].append(
            (
                deal,
                "tech_integration",
                base,
                rate,
                Decimal("1"),
                before,
                True,
                "Тех интеграция: 50% × сумма сделки",
            )
        )

    eligible = defaultdict(list)
    start3 = add_months(month, -2)

    implementation_result = await session.execute(
        select(Deal).where(
            Deal.funnel.in_(["implementation", "cr_start"]),
            Deal.status == "won",
            Deal.closed_time >= dt(start3),
            Deal.closed_time < dt(end),
        )
    )
    for deal in implementation_result.scalars().all():
        employee_id = deal.implementation_responsible_user_id
        if not employee_id or not deal.closed_time:
            continue

        closed_month = month_start(deal.closed_time.date())
        delta = (
            (month.year - closed_month.year) * 12
            + month.month
            - closed_month.month
        )
        if delta not in {0, 1, 2}:
            continue

        if deal.funnel == "cr_start":
            fields = settings.cr_start_boolean_fields
            if not fields:
                continue

            values = [raw_value(deal, field) for field in fields]
            is_fixed = any(truthy(value) for value in values)

            if is_fixed:
                if delta == 0:
                    fixed = decimal(rules["cr_start_fixed"])
                    contributions[employee_id].append(
                        (
                            deal,
                            "cr_start_fixed",
                            fixed,
                            Decimal("1"),
                            Decimal("1"),
                            fixed,
                            False,
                            "CR Start: фиксированный бонус 10 000 ₽",
                        )
                    )
                continue

        if Decimal(deal.monthly_amount or 0) <= 0:
            continue

        bonus_type = (
            "cr_start_implementation"
            if deal.funnel == "cr_start"
            else "implementation"
        )
        eligible[employee_id].append((deal, bonus_type))

    for employee_id, rows in eligible.items():
        total = sum(
            (Decimal(deal.monthly_amount or 0) for deal, _ in rows),
            Decimal("0"),
        )
        rate = implementation_rate(total, rules)

        for deal, bonus_type in rows:
            base = Decimal(deal.monthly_amount or 0)
            before = money(base * rate)
            contributions[employee_id].append(
                (
                    deal,
                    bonus_type,
                    base,
                    rate,
                    Decimal("1"),
                    before,
                    True,
                    f"Внедрение: {rate * 100}% × сумма оплаты в месяц",
                )
            )

    if settings.BITRIX_FIELD_SALES_BONUS_USER_ID:
        sales_result = await session.execute(
            select(Deal).where(
                Deal.funnel == "tech_integration",
                Deal.sales_bonus_user_id.is_not(None),
                Deal.closed_time >= dt(month),
                Deal.closed_time < dt(end),
            )
        )
        for deal in sales_result.scalars().all():
            employee_id = deal.sales_bonus_user_id
            if not employee_id:
                continue

            base = Decimal(deal.opportunity or 0)
            rate = decimal(rules["sales_rate"])
            before = money(base * rate)

            contributions[employee_id].append(
                (
                    deal,
                    "sale",
                    base,
                    rate,
                    Decimal("1"),
                    before,
                    False,
                    "Продажа: 10% × сумма сделки",
                )
            )

    manual_result = await session.execute(
        select(ManualBonusEvent).where(
            ManualBonusEvent.event_date >= month,
            ManualBonusEvent.event_date < end,
        )
    )
    for event in manual_result.scalars().all():
        if event.event_type == "support_hours":
            rate = decimal(rules["support_hour_rate"])
            before = money(Decimal(event.quantity) * rate)
            contributions[event.employee_id].append(
                (
                    None,
                    "support_hours",
                    rate,
                    rate,
                    Decimal(event.quantity),
                    before,
                    True,
                    f"Сопровождение: {event.quantity} ч × {rate} ₽",
                    event,
                )
            )
        elif event.event_type == "training":
            rate = decimal(rules["training_bonus"])
            before = money(Decimal(event.quantity) * rate)
            contributions[event.employee_id].append(
                (
                    None,
                    "training",
                    rate,
                    rate,
                    Decimal(event.quantity),
                    before,
                    True,
                    f"Обучение: {event.quantity} × {rate} ₽",
                    event,
                )
            )

    # Текущие клиенты.
    #
    # Итоговая согласованная логика:
    #
    # 1. Берем сделку Сопровождения, активную на конец месяца.
    # 2. Если связанная сделка Внедрения найдена и была активна
    #    на конец месяца — клиент еще не текущий, бонус не начисляем.
    # 3. Если Внедрение найдено, но уже завершено — бонус начисляем.
    # 4. Если Внедрение не найдено / ссылка отсутствует —
    #    бонус все равно начисляем, а диагностика показывает warning.
    # 5. Количество машин всегда берем из Сопровождения.
    # 6. Ответственного за внедрение всегда берем из Сопровождения.
    #
    if settings.BITRIX_FIELD_SOURCE_DEAL_ID:
        period_end_exclusive = end_of_month_dt(month)

        support_result = await session.execute(
            select(Deal).where(
                Deal.funnel == "support",
                *active_on_date_conditions(period_end_exclusive),
            )
        )

        for deal in support_result.scalars().all():
            implementations = await linked_implementation_deals(
                session,
                deal,
            )

            #
            # Если хотя бы одно связанное Внедрение
            # активно на конец месяца — бонус текущего
            # клиента не начисляем.
            #
            if any(
                deal_active_at_period_end(
                    implementation,
                    period_end_exclusive,
                )
                for implementation in implementations
            ):
                continue

            #
            # Ответственный — только из Сопровождения.
            #
            employee_id = (
                deal.implementation_responsible_user_id
            )

            if not employee_id:
                continue

            #
            # Машины — только из Сопровождения.
            #
            before = current_client_bonus(
                deal.machines_count,
                rules,
            )

            if before <= 0:
                continue

            contributions[employee_id].append(
                (
                    deal,
                    "current_client",
                    Decimal(deal.machines_count),
                    before,
                    Decimal("1"),
                    before,
                    True,
                    (
                        f"Текущий клиент: {deal.machines_count} "
                        f"машин → {before} ₽"
                    ),
                )
            )

    divider = decimal(rules["divider"])
    calculations = []

    for employee_id, rows in contributions.items():
        if employee_id not in user_ids:
            continue

        subtotal_dividable = sum(
            (row[5] for row in rows if row[6]),
            Decimal("0"),
        )
        cr_start_fixed_total = sum(
            (row[5] for row in rows if row[1] == "cr_start_fixed"),
            Decimal("0"),
        )
        sales_total = sum(
            (row[5] for row in rows if row[1] == "sale"),
            Decimal("0"),
        )
        implementation_total = sum(
            (
                row[2]
                for row in rows
                if row[1] in {"implementation", "cr_start_implementation"}
            ),
            Decimal("0"),
        )
        tech_integration_total = sum(
            (row[2] for row in rows if row[1] == "tech_integration"),
            Decimal("0"),
        )
        support_hours = sum(
            (row[4] for row in rows if row[1] == "support_hours"),
            Decimal("0"),
        )
        training_count = int(
            sum(
                (row[4] for row in rows if row[1] == "training"),
                Decimal("0"),
            )
        )

        total_bonus = money(
            subtotal_dividable / divider
            + cr_start_fixed_total
            + sales_total
        )

        calculation = BonusCalculation(
            employee_id=employee_id,
            period_from=month,
            period_to=period_to,
            implementation_total=implementation_total,
            tech_integration_total=tech_integration_total,
            support_hours=support_hours,
            sales_total=sales_total,
            training_count=training_count,
            total_bonus=total_bonus,
            details_json="{}",
            month=month,
            version=await latest_version(session, employee_id, month),
            status="completed",
            rules_version=rules_version,
            rules_snapshot_json=json.dumps(rules, ensure_ascii=False),
            subtotal_dividable=money(subtotal_dividable),
            cr_start_fixed_total=money(cr_start_fixed_total),
            issues_count=len(issues),
            initiated_by_id=initiated_by_id,
        )

        session.add(calculation)
        await session.flush()

        for row in rows:
            (
                deal,
                bonus_type,
                base,
                rate,
                quantity,
                before,
                use_divider,
                description,
            ) = row[:8]

            event = row[8] if len(row) > 8 else None
            final_amount = money(before / divider) if use_divider else money(before)

            calculation_item = BonusCalculationItem(
                calculation_id=calculation.id,
                employee_id=employee_id,
                deal_id=(
                    deal.id
                    if deal
                    else (
                        event.deal_id
                        if event
                        else None
                    )
                ),
                bonus_type=bonus_type,
                source_type=("manual_event" if event else "deal"),
                source_external_id=(
                    str(event.id)
                    if event
                    else (
                        str(deal.bitrix_id)
                        if deal
                        else None
                    )
                ),
                base_amount=money(base),
                rate=rate,
                quantity=quantity,
                amount_before_divider=money(before),
                divider_applied=use_divider,
                amount_final=final_amount,
                description=description,
                details_json=json.dumps(
                    {
                        "divider": (
                            str(divider)
                            if use_divider
                            else None
                        ),
                    },
                    ensure_ascii=False,
                ),
            )
            session.add(calculation_item)

        calculations.append(calculation)

    await session.commit()
    return calculations


# Обратная совместимость со старым тестом и legacy API.
def calculate_bonus(data: BonusInput) -> BonusResult:
    config = DEFAULT_RULES

    implementation_bonus = money(
        data.implementation_total
        * implementation_rate(
            data.implementation_total,
            config,
        )
    )
    tech_integration_bonus = money(
        data.tech_integration_total
        * decimal(config["tech_integration_rate"])
    )
    support_bonus = money(
        data.support_hours
        * decimal(config["support_hour_rate"])
    )
    sales_bonus = money(
        data.sales_total
        * decimal(config["sales_rate"])
    )
    training_bonus = money(
        Decimal(data.training_count)
        * decimal(config["training_bonus"])
    )
    cr_start_fixed_bonus = money(data.cr_start_fixed_total)

    dividable = (
        implementation_bonus
        + tech_integration_bonus
        + support_bonus
        + training_bonus
    )

    subtotal = money(
        dividable
        + sales_bonus
        + cr_start_fixed_bonus
    )

    total = money(
        dividable / decimal(config["divider"])
        + sales_bonus
        + cr_start_fixed_bonus
    )

    return BonusResult(
        employee_id=data.employee_id,
        implementation_bonus=implementation_bonus,
        tech_integration_bonus=tech_integration_bonus,
        support_bonus=support_bonus,
        sales_bonus=sales_bonus,
        training_bonus=training_bonus,
        cr_start_fixed_bonus=cr_start_fixed_bonus,
        subtotal=subtotal,
        total=total,
    )
