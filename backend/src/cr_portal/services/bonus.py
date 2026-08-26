import json
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
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
    return value.quantize(
        CENT,
        rounding=ROUND_HALF_UP,
    )


def month_start(value: date) -> date:
    return date(
        value.year,
        value.month,
        1,
    )


def add_months(
    value: date,
    months: int,
) -> date:
    year = (
        value.year
        + (
            value.month
            - 1
            + months
        )
        // 12
    )

    month = (
        (
            value.month
            - 1
            + months
        )
        % 12
        + 1
    )

    return date(
        year,
        month,
        1,
    )


def dt(
    value: date,
) -> datetime:
    return datetime(
        value.year,
        value.month,
        value.day,
        tzinfo=timezone.utc,
    )


def raw_value(
    deal: Deal,
    field_name: str,
):
    if (
        not field_name
        or not deal.raw_json
    ):
        return None

    try:
        data = json.loads(
            deal.raw_json
        )
    except Exception:
        return None

    return data.get(
        field_name
    )


def truthy(
    value,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    return (
        str(value)
        .strip()
        .upper()
        in {
            "Y",
            "YES",
            "TRUE",
            "1",
            "ДА",
            "199",
        }
    )


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

    session.add(
        row
    )

    return row


async def diagnose_month(
    session: AsyncSession,
    month: date,
):
    month = month_start(
        month
    )

    end = add_months(
        month,
        1,
    )

    start3 = add_months(
        month,
        -2,
    )

    #
    # Удаляем предыдущую диагностику
    # этого месяца.
    #
    result = await session.execute(
        select(
            CalculationIssue
        ).where(
            CalculationIssue.month
            == month,
            CalculationIssue
            .calculation_id
            .is_(None),
        )
    )

    for issue in (
        result
        .scalars()
        .all()
    ):
        await session.delete(
            issue
        )

    #
    # Настройки,
    # которые пока TBD.
    #
    if (
        not settings
        .BITRIX_FIELD_SOURCE_DEAL_ID
    ):
        await add_issue(
            session,
            month,
            "warning",
            "SOURCE_DEAL_FIELD_NOT_CONFIGURED",
            (
                "Не настроено поле "
                "ID сделки-источника."
            ),
        )

    if (
        not settings
        .BITRIX_FIELD_SALES_BONUS_USER_ID
    ):
        await add_issue(
            session,
            month,
            "warning",
            "SALES_USER_FIELD_NOT_CONFIGURED",
            (
                "Не настроено поле "
                "сотрудника, получающего "
                "бонус за продажу."
            ),
        )

    if (
        not settings
        .cr_start_boolean_fields
    ):
        await add_issue(
            session,
            month,
            "warning",
            "CR_START_FIELDS_NOT_CONFIGURED",
            (
                "Не настроены поля "
                "«КР Старт: ...»."
            ),
        )

    if (
        not settings
        .BITRIX_TASK_TRAINING_BONUS_FIELD
    ):
        await add_issue(
            session,
            month,
            "warning",
            "TRAINING_TASK_FIELD_NOT_CONFIGURED",
            (
                "Не настроено поле задачи "
                "«Бонус за обучение = Да»."
            ),
        )

    if (
        not settings
        .BITRIX_FIELD_CLIENT_WORKS
    ):
        await add_issue(
            session,
            month,
            "warning",
            "CLIENT_WORKS_NOT_CONFIGURED",
            (
                "Не задано техническое "
                "определение "
                "«клиент работает»."
            ),
        )

    #
    # 1. Тех интеграция.
    #
    # Проверяем только успешно
    # закрытые сделки текущего месяца.
    #
    tech_result = (
        await session.execute(
            select(
                Deal
            ).where(
                Deal.funnel
                == "tech_integration",
                Deal.status
                == "won",
                Deal.closed_time
                >= dt(month),
                Deal.closed_time
                < dt(end),
            )
        )
    )

    for deal in (
        tech_result
        .scalars()
        .all()
    ):
        if (
            deal
            .implementation_responsible_user_id
            is None
        ):
            await add_issue(
                session,
                month,
                "critical",
                "NO_IMPLEMENTATION_RESPONSIBLE",
                (
                    "Нет "
                    "«Ответственного "
                    "за внедрение»."
                ),
                deal_id=deal.id,
            )

    #
    # 2. Внедрение.
    #
    # В расчете месяца участвуют
    # сделки, закрытые в текущем
    # месяце и двух предыдущих.
    #
    implementation_result = (
        await session.execute(
            select(
                Deal
            ).where(
                Deal.funnel
                == "implementation",
                Deal.status
                == "won",
                Deal.closed_time
                >= dt(start3),
                Deal.closed_time
                < dt(end),
            )
        )
    )

    for deal in (
        implementation_result
        .scalars()
        .all()
    ):
        if (
            deal
            .implementation_responsible_user_id
            is None
        ):
            await add_issue(
                session,
                month,
                "critical",
                "NO_IMPLEMENTATION_RESPONSIBLE",
                (
                    "Нет "
                    "«Ответственного "
                    "за внедрение»."
                ),
                deal_id=deal.id,
            )

        if (
            Decimal(
                deal.monthly_amount
                or 0
            )
            <= 0
        ):
            await add_issue(
                session,
                month,
                "critical",
                "NO_MONTHLY_AMOUNT",
                (
                    "Нет суммы оплаты "
                    "в месяц."
                ),
                employee_id=(
                    deal
                    .implementation_responsible_user_id
                ),
                deal_id=deal.id,
            )

    #
    # 3. CR Start.
    #
    # Сначала определяем вариант:
    # фиксированный или как внедрение.
    #
    cr_start_result = (
        await session.execute(
            select(
                Deal
            ).where(
                Deal.funnel
                == "cr_start",
                Deal.status
                == "won",
                Deal.closed_time
                >= dt(start3),
                Deal.closed_time
                < dt(end),
            )
        )
    )

    for deal in (
        cr_start_result
        .scalars()
        .all()
    ):
        if (
            deal
            .implementation_responsible_user_id
            is None
        ):
            await add_issue(
                session,
                month,
                "critical",
                "NO_IMPLEMENTATION_RESPONSIBLE",
                (
                    "Нет "
                    "«Ответственного "
                    "за внедрение»."
                ),
                deal_id=deal.id,
            )

        fields = (
            settings
            .cr_start_boolean_fields
        )

        #
        # Реальные поля пока
        # не настроены —
        # не пытаемся угадывать.
        #
        if not fields:
            continue

        values = [
            raw_value(
                deal,
                field,
            )
            for field
            in fields
        ]

        is_fixed = any(
            truthy(
                value
            )
            for value
            in values
        )

        #
        # Для фиксированного
        # CR Start monthly_amount
        # не требуется.
        #
        if is_fixed:
            continue

        #
        # Для CR Start,
        # считающегося как внедрение,
        # сумма оплаты обязательна.
        #
        if (
            Decimal(
                deal.monthly_amount
                or 0
            )
            <= 0
        ):
            await add_issue(
                session,
                month,
                "critical",
                "NO_MONTHLY_AMOUNT",
                (
                    "Нет суммы оплаты "
                    "в месяц для CR Start, "
                    "рассчитываемого "
                    "как внедрение."
                ),
                employee_id=(
                    deal
                    .implementation_responsible_user_id
                ),
                deal_id=deal.id,
            )

    #
    # 4. Сопровождение.
    #
    # Машины проверяем только
    # если настроена реальная
    # логика текущих клиентов.
    #
    if (
        settings
        .BITRIX_FIELD_SOURCE_DEAL_ID
        and settings
        .BITRIX_FIELD_CLIENT_WORKS
    ):
        support_result = (
            await session.execute(
                select(
                    Deal
                ).where(
                    Deal.funnel
                    == "support",
                    Deal.status
                    == "in_progress",
                )
            )
        )

        for deal in (
            support_result
            .scalars()
            .all()
        ):
            if not truthy(
                raw_value(
                    deal,
                    settings
                    .BITRIX_FIELD_CLIENT_WORKS,
                )
            ):
                continue

            if (
                deal
                .machines_count
                <= 0
            ):
                await add_issue(
                    session,
                    month,
                    "warning",
                    "NO_MACHINES",
                    (
                        "Нет количества "
                        "машин для "
                        "текущего клиента."
                    ),
                    employee_id=(
                        deal
                        .implementation_responsible_user_id
                    ),
                    deal_id=deal.id,
                )

    await session.flush()

    result = (
        await session.execute(
            select(
                CalculationIssue
            )
            .where(
                CalculationIssue.month
                == month
            )
            .order_by(
                CalculationIssue.severity,
                CalculationIssue.code,
            )
        )
    )

    return list(
        result
        .scalars()
        .all()
    )


async def latest_version(
    session: AsyncSession,
    employee_id,
    month,
):
    result = (
        await session.execute(
            select(
                func.max(
                    BonusCalculation.version
                )
            ).where(
                BonusCalculation.employee_id
                == employee_id,
                BonusCalculation.month
                == month,
            )
        )
    )

    return (
        int(
            result.scalar_one_or_none()
            or 0
        )
        + 1
    )


async def calculate_month(
    session: AsyncSession,
    month: date,
    initiated_by_id: UUID | None = None,
):
    month = month_start(
        month
    )

    end = add_months(
        month,
        1,
    )

    period_to = date.fromordinal(
        end.toordinal()
        - 1
    )

    rules_version, rules = (
        await get_rules(
            session,
            month,
        )
    )

    issues = (
        await diagnose_month(
            session,
            month,
        )
    )

    users_result = (
        await session.execute(
            select(
                User
            )
        )
    )

    users = (
        users_result
        .scalars()
        .all()
    )

    user_ids = {
        user.id
        for user
        in users
    }

    contributions = defaultdict(
        list
    )

    #
    # 1. Тех интеграция.
    #
    tech_result = (
        await session.execute(
            select(
                Deal
            ).where(
                Deal.funnel
                == "tech_integration",
                Deal.status
                == "won",
                Deal.closed_time
                >= dt(month),
                Deal.closed_time
                < dt(end),
            )
        )
    )

    for deal in (
        tech_result
        .scalars()
        .all()
    ):
        employee_id = (
            deal
            .implementation_responsible_user_id
        )

        if not employee_id:
            continue

        if not deal.integration_1c:
            continue

        base = Decimal(
            deal.opportunity
            or 0
        )

        rate = decimal(
            rules[
                "tech_integration_rate"
            ]
        )

        before = money(
            base
            * rate
        )

        contributions[
            employee_id
        ].append(
            (
                deal,
                "tech_integration",
                base,
                rate,
                Decimal("1"),
                before,
                True,
                (
                    "Тех интеграция: "
                    "50% × сумма сделки"
                ),
            )
        )

    #
    # 2. Внедрение
    # и CR Start как внедрение.
    #
    eligible = defaultdict(
        list
    )

    start3 = add_months(
        month,
        -2,
    )

    implementation_result = (
        await session.execute(
            select(
                Deal
            ).where(
                Deal.funnel.in_(
                    [
                        "implementation",
                        "cr_start",
                    ]
                ),
                Deal.status
                == "won",
                Deal.closed_time
                >= dt(start3),
                Deal.closed_time
                < dt(end),
            )
        )
    )

    for deal in (
        implementation_result
        .scalars()
        .all()
    ):
        employee_id = (
            deal
            .implementation_responsible_user_id
        )

        if (
            not employee_id
            or not deal.closed_time
        ):
            continue

        closed_month = (
            month_start(
                deal
                .closed_time
                .date()
            )
        )

        delta = (
            (
                month.year
                - closed_month.year
            )
            * 12
            + month.month
            - closed_month.month
        )

        if delta not in {
            0,
            1,
            2,
        }:
            continue

        #
        # CR Start.
        #
        if (
            deal.funnel
            == "cr_start"
        ):
            fields = (
                settings
                .cr_start_boolean_fields
            )

            #
            # Пока поля не настроены,
            # не угадываем вариант.
            #
            if not fields:
                continue

            values = [
                raw_value(
                    deal,
                    field,
                )
                for field
                in fields
            ]

            is_fixed = any(
                truthy(
                    value
                )
                for value
                in values
            )

            #
            # Фиксированный CR Start.
            #
            if is_fixed:
                #
                # Один раз,
                # только в месяц закрытия.
                #
                if delta == 0:
                    fixed = decimal(
                        rules[
                            "cr_start_fixed"
                        ]
                    )

                    contributions[
                        employee_id
                    ].append(
                        (
                            deal,
                            "cr_start_fixed",
                            fixed,
                            Decimal("1"),
                            Decimal("1"),
                            fixed,
                            False,
                            (
                                "CR Start: "
                                "фиксированный "
                                "бонус 10 000 ₽"
                            ),
                        )
                    )

                continue

        #
        # Обычное внедрение
        # или CR Start как внедрение.
        #
        if (
            Decimal(
                deal.monthly_amount
                or 0
            )
            <= 0
        ):
            continue

        bonus_type = (
            "cr_start_implementation"
            if (
                deal.funnel
                == "cr_start"
            )
            else "implementation"
        )

        eligible[
            employee_id
        ].append(
            (
                deal,
                bonus_type,
            )
        )

    #
    # Ставка внедрения
    # определяется по общей сумме
    # сотрудника за месяц.
    #
    for (
        employee_id,
        rows,
    ) in eligible.items():
        total = sum(
            (
                Decimal(
                    deal.monthly_amount
                    or 0
                )
                for (
                    deal,
                    _
                )
                in rows
            ),
            Decimal("0"),
        )

        rate = (
            implementation_rate(
                total,
                rules,
            )
        )

        for (
            deal,
            bonus_type,
        ) in rows:
            base = Decimal(
                deal.monthly_amount
                or 0
            )

            before = money(
                base
                * rate
            )

            contributions[
                employee_id
            ].append(
                (
                    deal,
                    bonus_type,
                    base,
                    rate,
                    Decimal("1"),
                    before,
                    True,
                    (
                        "Внедрение: "
                        f"{rate * 100}% × "
                        "сумма оплаты в месяц"
                    ),
                )
            )

    #
    # 3. Продажа.
    #
    if (
        settings
        .BITRIX_FIELD_SALES_BONUS_USER_ID
    ):
        sales_result = (
            await session.execute(
                select(
                    Deal
                ).where(
                    Deal.funnel
                    == "tech_integration",
                    Deal
                    .sales_bonus_user_id
                    .is_not(None),
                    Deal.closed_time
                    >= dt(month),
                    Deal.closed_time
                    < dt(end),
                )
            )
        )

        for deal in (
            sales_result
            .scalars()
            .all()
        ):
            employee_id = (
                deal
                .sales_bonus_user_id
            )

            if not employee_id:
                continue

            base = Decimal(
                deal.opportunity
                or 0
            )

            rate = decimal(
                rules[
                    "sales_rate"
                ]
            )

            before = money(
                base
                * rate
            )

            contributions[
                employee_id
            ].append(
                (
                    deal,
                    "sale",
                    base,
                    rate,
                    Decimal("1"),
                    before,
                    False,
                    (
                        "Продажа: "
                        "10% × сумма сделки"
                    ),
                )
            )

    #
    # 4. Ручные часы
    # и обучение.
    #
    manual_result = (
        await session.execute(
            select(
                ManualBonusEvent
            ).where(
                ManualBonusEvent.event_date
                >= month,
                ManualBonusEvent.event_date
                < end,
            )
        )
    )

    for event in (
        manual_result
        .scalars()
        .all()
    ):
        if (
            event.event_type
            == "support_hours"
        ):
            rate = decimal(
                rules[
                    "support_hour_rate"
                ]
            )

            before = money(
                Decimal(
                    event.quantity
                )
                * rate
            )

            contributions[
                event.employee_id
            ].append(
                (
                    None,
                    "support_hours",
                    rate,
                    rate,
                    Decimal(
                        event.quantity
                    ),
                    before,
                    True,
                    (
                        "Сопровождение: "
                        f"{event.quantity} ч "
                        f"× {rate} ₽"
                    ),
                    event,
                )
            )

        elif (
            event.event_type
            == "training"
        ):
            rate = decimal(
                rules[
                    "training_bonus"
                ]
            )

            before = money(
                Decimal(
                    event.quantity
                )
                * rate
            )

            contributions[
                event.employee_id
            ].append(
                (
                    None,
                    "training",
                    rate,
                    rate,
                    Decimal(
                        event.quantity
                    ),
                    before,
                    True,
                    (
                        "Обучение: "
                        f"{event.quantity} "
                        f"× {rate} ₽"
                    ),
                    event,
                )
            )

    #
    # 5. Текущие клиенты.
    #
    if (
        settings
        .BITRIX_FIELD_SOURCE_DEAL_ID
        and settings
        .BITRIX_FIELD_CLIENT_WORKS
    ):
        support_result = (
            await session.execute(
                select(
                    Deal
                ).where(
                    Deal.funnel
                    == "support",
                    Deal.status
                    == "in_progress",
                    Deal
                    .source_deal_bitrix_id
                    .is_not(None),
                )
            )
        )

        for deal in (
            support_result
            .scalars()
            .all()
        ):
            if not truthy(
                raw_value(
                    deal,
                    settings
                    .BITRIX_FIELD_CLIENT_WORKS,
                )
            ):
                continue

            source_result = (
                await session.execute(
                    select(
                        Deal
                    ).where(
                        Deal.bitrix_id
                        == deal
                        .source_deal_bitrix_id
                    )
                )
            )

            source_deal = (
                source_result
                .scalar_one_or_none()
            )

            if (
                not source_deal
                or source_deal.funnel
                != "implementation"
                or source_deal.status
                != "won"
                or not source_deal
                .implementation_responsible_user_id
            ):
                continue

            before = (
                current_client_bonus(
                    deal.machines_count,
                    rules,
                )
            )

            if (
                before
                <= 0
            ):
                continue

            employee_id = (
                source_deal
                .implementation_responsible_user_id
            )

            contributions[
                employee_id
            ].append(
                (
                    deal,
                    "current_client",
                    Decimal(
                        deal.machines_count
                    ),
                    before,
                    Decimal("1"),
                    before,
                    True,
                    (
                        "Текущий клиент: "
                        f"{deal.machines_count} "
                        "машин → "
                        f"{before} ₽"
                    ),
                )
            )

    #
    # Формирование
    # расчетов сотрудников.
    #
    divider = decimal(
        rules[
            "divider"
        ]
    )

    calculations = []

    for (
        employee_id,
        rows,
    ) in contributions.items():
        if (
            employee_id
            not in user_ids
        ):
            continue

        subtotal_dividable = sum(
            (
                row[5]
                for row
                in rows
                if row[6]
            ),
            Decimal("0"),
        )

        cr_start_fixed_total = sum(
            (
                row[5]
                for row
                in rows
                if row[1]
                == "cr_start_fixed"
            ),
            Decimal("0"),
        )

        sales_total = sum(
            (
                row[5]
                for row
                in rows
                if row[1]
                == "sale"
            ),
            Decimal("0"),
        )

        implementation_total = sum(
            (
                row[2]
                for row
                in rows
                if row[1]
                in {
                    "implementation",
                    "cr_start_implementation",
                }
            ),
            Decimal("0"),
        )

        tech_integration_total = sum(
            (
                row[2]
                for row
                in rows
                if row[1]
                == "tech_integration"
            ),
            Decimal("0"),
        )

        support_hours = sum(
            (
                row[4]
                for row
                in rows
                if row[1]
                == "support_hours"
            ),
            Decimal("0"),
        )

        training_count = int(
            sum(
                (
                    row[4]
                    for row
                    in rows
                    if row[1]
                    == "training"
                ),
                Decimal("0"),
            )
        )

        total_bonus = money(
            (
                subtotal_dividable
                / divider
            )
            + cr_start_fixed_total
            + sales_total
        )

        calculation = (
            BonusCalculation(
                employee_id=employee_id,
                period_from=month,
                period_to=period_to,
                implementation_total=(
                    implementation_total
                ),
                tech_integration_total=(
                    tech_integration_total
                ),
                support_hours=(
                    support_hours
                ),
                sales_total=(
                    sales_total
                ),
                training_count=(
                    training_count
                ),
                total_bonus=(
                    total_bonus
                ),
                details_json="{}",
                month=month,
                version=(
                    await latest_version(
                        session,
                        employee_id,
                        month,
                    )
                ),
                status="completed",
                rules_version=(
                    rules_version
                ),
                rules_snapshot_json=(
                    json.dumps(
                        rules,
                        ensure_ascii=False,
                    )
                ),
                subtotal_dividable=(
                    money(
                        subtotal_dividable
                    )
                ),
                cr_start_fixed_total=(
                    money(
                        cr_start_fixed_total
                    )
                ),
                issues_count=len(
                    issues
                ),
                initiated_by_id=(
                    initiated_by_id
                ),
            )
        )

        session.add(
            calculation
        )

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

            event = (
                row[8]
                if len(row) > 8
                else None
            )

            if use_divider:
                final_amount = money(
                    before
                    / divider
                )
            else:
                final_amount = money(
                    before
                )

            calculation_item = (
                BonusCalculationItem(
                    calculation_id=(
                        calculation.id
                    ),
                    employee_id=(
                        employee_id
                    ),
                    deal_id=(
                        deal.id
                        if deal
                        else (
                            event.deal_id
                            if event
                            else None
                        )
                    ),
                    bonus_type=(
                        bonus_type
                    ),
                    source_type=(
                        "manual_event"
                        if event
                        else "deal"
                    ),
                    source_external_id=(
                        str(
                            event.id
                        )
                        if event
                        else (
                            str(
                                deal.bitrix_id
                            )
                            if deal
                            else None
                        )
                    ),
                    base_amount=(
                        money(
                            base
                        )
                    ),
                    rate=rate,
                    quantity=quantity,
                    amount_before_divider=(
                        money(
                            before
                        )
                    ),
                    divider_applied=(
                        use_divider
                    ),
                    amount_final=(
                        final_amount
                    ),
                    description=(
                        description
                    ),
                    details_json=(
                        json.dumps(
                            {
                                "divider": (
                                    str(
                                        divider
                                    )
                                    if use_divider
                                    else None
                                ),
                            },
                            ensure_ascii=False,
                        )
                    ),
                )
            )

            session.add(
                calculation_item
            )

        calculations.append(
            calculation
        )

    await session.commit()

    return calculations


#
# Обратная совместимость
# со старым тестом
# и legacy API.
#
def calculate_bonus(
    data: BonusInput,
) -> BonusResult:
    config = (
        DEFAULT_RULES
    )

    implementation_bonus = money(
        data.implementation_total
        * implementation_rate(
            data.implementation_total,
            config,
        )
    )

    tech_integration_bonus = money(
        data.tech_integration_total
        * decimal(
            config[
                "tech_integration_rate"
            ]
        )
    )

    support_bonus = money(
        data.support_hours
        * decimal(
            config[
                "support_hour_rate"
            ]
        )
    )

    sales_bonus = money(
        data.sales_total
        * decimal(
            config[
                "sales_rate"
            ]
        )
    )

    training_bonus = money(
        Decimal(
            data.training_count
        )
        * decimal(
            config[
                "training_bonus"
            ]
        )
    )

    cr_start_fixed_bonus = money(
        data.cr_start_fixed_total
    )

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
        (
            dividable
            / decimal(
                config[
                    "divider"
                ]
            )
        )
        + sales_bonus
        + cr_start_fixed_bonus
    )

    return BonusResult(
        employee_id=(
            data.employee_id
        ),
        implementation_bonus=(
            implementation_bonus
        ),
        tech_integration_bonus=(
            tech_integration_bonus
        ),
        support_bonus=(
            support_bonus
        ),
        sales_bonus=(
            sales_bonus
        ),
        training_bonus=(
            training_bonus
        ),
        cr_start_fixed_bonus=(
            cr_start_fixed_bonus
        ),
        subtotal=(
            subtotal
        ),
        total=(
            total
        ),
    )