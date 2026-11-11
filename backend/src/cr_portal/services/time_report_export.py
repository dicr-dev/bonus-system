from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from cr_portal.schemas.time_report import TimeReport

TIME_FORMAT = "[h]:mm:ss"


def _append(sheet, values):
    sheet.append([ILLEGAL_CHARACTERS_RE.sub("", v)[:32767] if isinstance(v, str) else v for v in values])


def time_report_excel(report: TimeReport, portal_url: str) -> bytes:
    """Render the already permission-filtered report; never query additional employees/tasks."""
    if len(report.days) > 16380:
        raise ValueError("Слишком большой период для Excel: выберите не более 16 380 дней")
    book = Workbook()
    summary = book.active
    summary.title = "Сводка"
    _append(summary, ["Сотрудник", "Отдел", "Общее время", "Всего часов", *report.days])
    details = book.create_sheet("Задачи по дням")
    _append(details, ["Сотрудник", "Отдел", "Дата", "ID задачи", "Название задачи",
                    "Время", "Часы", "Секунды", "Ссылка на задачу"])
    for employee in report.employees:
        days = {day.date: day for day in employee.days}
        _append(summary, [
            employee.full_name, employee.department_name or "", employee.total_seconds / 86400,
            employee.total_seconds / 3600,
            *[days[day].seconds / 86400 if day in days else None for day in report.days],
        ])
        summary.cell(summary.max_row, 3).number_format = TIME_FORMAT
        summary.cell(summary.max_row, 4).number_format = "0.00"
        for column in range(5, len(report.days) + 5):
            summary.cell(summary.max_row, column).number_format = TIME_FORMAT
        for day in employee.days:
            for task in day.tasks:
                if details.max_row >= 1048576:
                    raise ValueError("Слишком много задач для Excel: сократите период или фильтры")
                if task.group_id and task.group_id > 0:
                    path = f"/workgroups/group/{task.group_id}/tasks/task/view/{task.task_bitrix_id}/"
                else:
                    responsible = max(task.responsible_bitrix_id or 0, 0)
                    path = f"/company/personal/user/{responsible}/tasks/task/view/{task.task_bitrix_id}/"
                url = portal_url.rstrip("/") + path
                _append(details, [
                    employee.full_name, employee.department_name or "", day.date,
                    task.task_bitrix_id, task.title, task.seconds / 86400,
                    task.seconds / 3600, task.seconds, url,
                ])
                details.cell(details.max_row, 3).number_format = "dd.mm.yyyy"
                details.cell(details.max_row, 6).number_format = TIME_FORMAT
                details.cell(details.max_row, 7).number_format = "0.00"
                details.cell(details.max_row, 9).hyperlink = url
                details.cell(details.max_row, 9).style = "Hyperlink"
    for col in range(5, len(report.days) + 5):
        summary.cell(1, col).number_format = "dd.mm.yyyy"
        summary.column_dimensions[get_column_letter(col)].width = 14
    for sheet in book:
        sheet.freeze_panes = "E2" if sheet is summary else "C2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    # CRM text is data, never an Excel formula, even when it starts with '='.
                    cell.value = ILLEGAL_CHARACTERS_RE.sub("", cell.value)[:32767]
                    cell.data_type = "s"
        sheet.column_dimensions["A"].width = 30
        sheet.column_dimensions["B"].width = 28
    for column, width in {"C":18,"D":16,"E":60,"F":18,"G":14,"H":14,"I":65}.items():
        details.column_dimensions[column].width = width
    summary.column_dimensions["C"].width = 20
    summary.column_dimensions["D"].width = 16
    output = BytesIO()
    book.save(output)
    return output.getvalue()
