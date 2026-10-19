from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font

from cr_portal.api.deps import admin_user, db_session
from cr_portal.services.app_settings import get_business_settings
from cr_portal.services.cr_start_analytics import MODULES, cr_start_analytics

router = APIRouter(dependencies=[Depends(admin_user)])


async def report_data(session, employee_id, module):
    if module and module not in MODULES:
        raise HTTPException(422, "Неизвестный модуль")
    business = await get_business_settings(session)
    return await cr_start_analytics(session, business, employee_id=employee_id, module=module)


@router.get("/cr-start")
async def report(employee_id: str | None = Query(None), module: str | None = Query(None), session=Depends(db_session)):
    return await report_data(session, employee_id, module)


def cell(value):
    # CRM content must remain text, never an executable spreadsheet formula.
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


METRICS = [("deals_count", "Всего сделок"), ("companies_count", "Компаний с ID"), ("amount", "Сумма сделок"),
           ("working_count", "В работе"), ("working_amount", "Сумма в работе"),
           ("commercial_count", "Пользуются сейчас"), ("commercial_amount", "Сумма активных коммерческих"),
           ("ever_commercial_count", "Когда-либо запущены"), ("ever_commercial_amount", "Сумма когда-либо запущенных"),
           ("lost_before_count", "Отвал до запуска"), ("lost_before_amount", "Сумма отказов до запуска"),
           ("lost_after_count", "Отвал после запуска"), ("lost_after_amount", "Сумма отказов после запуска"),
           ("conversion", "Конверсия, %"), ("resolved_conversion", "Конверсия среди результатов, %"),
           ("average_commercial_amount", "Средняя сумма запущенной сделки"),
           ("launch_mean_days", "Средний срок до запуска, дни"), ("launch_median_days", "Медиана до запуска, дни"),
           ("launch_sample", "Выборка срока до запуска"),
           ("lost_usage_mean_days", "Средний срок ушедших, дни"), ("lost_usage_median_days", "Медиана ушедших, дни"),
           ("lost_usage_sample", "Выборка срока ушедших"),
           ("active_usage_mean_days", "Средний срок активных, дни"), ("active_usage_sample", "Выборка активных"),
           ("retention_1", "Удержание 1 месяц, %"), ("retention_1_sample", "Выборка 1 месяц"),
           ("retention_3", "Удержание 3 месяца, %"), ("retention_3_sample", "Выборка 3 месяца"),
           ("retention_6", "Удержание 6 месяцев, %"), ("retention_6_sample", "Выборка 6 месяцев"),
           ("early_loss_1_count", "Первый отвал раньше 1 месяца"), ("early_loss_3_count", "Первый отвал раньше 3 месяцев"),
           ("early_loss_6_count", "Первый отвал раньше 6 месяцев"),
           ("reconnections", "Возвращений"), ("hours", "Часы всех авторов по портфелю"),
           ("lost_before_hours", "Часы всех авторов по отказам до запуска"),
           ("overdue_tasks", "Просроченные задачи"), ("incomplete_history_count", "Сделок с замечаниями к истории")]
LABOR = [("author_hours", "Личные часы автора"), ("before_hours", "Личные часы до запуска"),
         ("lost_before_author_hours", "Личные часы по отказам до запуска"),
         ("commercial_hours", "Личные часы использования"), ("break_hours", "Личные часы перерывов"),
         ("unknown_hours", "Личные часы без определённого этапа"),
         ("launch_effort_mean_hours", "Средние личные часы до запуска"), ("launch_effort_sample", "Выборка трудозатрат до запуска")]


def workbook(data):
    book = Workbook()
    book.remove(book.active)

    def sheet(title, rows, fields):
        page = book.create_sheet(title)
        page.append([label for _, label in fields])
        for row in rows:
            values = []
            for key, _ in fields:
                value = row.get(key)
                if value is not None and (key == "amount" or key.endswith("_amount")):
                    value = float(value)
                values.append(cell(value))
            page.append(values)
        page.freeze_panes = "A2"
        page.auto_filter.ref = page.dimensions
        for column in page.columns:
            page.column_dimensions[column[0].column_letter].width = 25
            column[0].font = Font(bold=True)

    sheet("Правила", [{"text": "Срез за весь срок на " + data["as_of"]},
                     *[{"text": warning} for warning in data["warnings"]]], [("text", "Правила и ограничения")])
    sheet("Менеджеры", data["managers"], [("name", "Сотрудник"), *METRICS, *LABOR])
    sheet("Модули менеджеров", [dict(name=m["name"], **mod) for m in data["managers"] for mod in m["modules"]],
          [("name", "Сотрудник"), ("module", "Модуль"), *METRICS, *LABOR])
    sheet("Модули", data["modules"], [("module", "Модуль"), *METRICS])
    sheet("Сделки", [dict(**d, notes="; ".join(d["warnings"])) for d in data["deals"]],
          [("bitrix_id", "ID сделки"), ("title", "Сделка"), ("company", "Компания"), ("module", "Модуль"),
           ("owner_name", "Текущий ответственный"), ("stage", "Стадия"), ("amount", "Сумма"),
           ("created_at", "Создана"), ("first_commercial_at", "Первое использование"), ("loss_at", "Последний отвал"),
           ("usage_days", "Использование без перерывов, дни"), ("usage_months", "Условные месяцы"),
           ("current_period_days", "Текущий период, дни"), ("reconnections", "Возвращений"),
           ("stage_days", "Дней на стадии"), ("age_days", "Возраст, дни"), ("hours", "Часы всех сотрудников"), ("notes", "Замечания")])
    sheet("Периоды", [dict(deal=d["title"], deal_id=d["bitrix_id"], reliable=d["history_reliable"], **p)
                      for d in data["deals"] for p in d["periods"]],
          [("deal_id", "ID сделки"), ("deal", "Сделка"), ("start", "Начало"), ("end", "Конец (пусто — открыт)"),
           ("days", "Длительность, дни"), ("reason", "Причина окончания"), ("reliable", "История подтверждена")])
    sheet("История стадий", [dict(deal_id=d["bitrix_id"], **h) for d in data["deals"] for h in d["history"]],
          [("deal_id", "ID сделки"), ("at", "Дата МСК"), ("stage", "Стадия")])
    sheet("Задачи", [dict(deal_id=d["bitrix_id"], **{k: v for k, v in t.items() if k != "entries"})
                     for d in data["deals"] for t in d["tasks"]],
          [("deal_id", "ID сделки"), ("task_id", "ID задачи"), ("title", "Задача"), ("status", "Статус"),
           ("deadline", "Крайний срок"), ("overdue", "Просрочена"), ("hours", "Списано часов")])
    sheet("Списания времени", [dict(deal_id=d["bitrix_id"], task_id=t["task_id"], **e)
                               for d in data["deals"] for t in d["tasks"] for e in t["entries"]],
          [("deal_id", "ID сделки"), ("task_id", "ID задачи"), ("id", "ID списания"), ("author", "Автор"),
           ("at", "Дата МСК"), ("seconds", "Секунды"), ("hours", "Часы"), ("phase", "Этап: before/commercial/break/unknown")])
    sheet("Динамика", data["monthly"], [("month", "Месяц"), ("created", "Создано"), ("first_launch", "Первые запуски"),
                                      ("lost_before", "Отказы до запуска по истории"),
                                      ("departures", "Отказы после запуска (подтверждены)"), ("reconnections", "Возвращения (подтверждены)")])
    sheet("Когорты", data["cohorts"], [("month", "Месяц создания"), *METRICS])
    sheet("Причины отказов", data["losses"], [("owner_name", "Менеджер"), ("module", "Модуль"), ("reason", "Причина"),
                                           ("after_commercial", "После запуска"), ("count", "Сделок"), ("amount", "Сумма")])
    sheet("Ошибки связей", data["issues"], [("task_id", "ID задачи"), ("title", "Задача"), ("reason", "Ошибка")])
    return book


@router.get("/cr-start/export")
async def export(employee_id: str | None = Query(None), module: str | None = Query(None), session=Depends(db_session)):
    data = await report_data(session, employee_id, module)
    buffer = BytesIO()
    workbook(data).save(buffer)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            headers={"Content-Disposition": 'attachment; filename="cr-start-analytics.xlsx"'})
