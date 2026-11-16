from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font

COLUMNS = [
    ('employee_name','Сотрудник'),('funnel','Воронка'),('module','Направление (модуль)'),
    ('title','Название'),('deal_current_status','Текущий статус по сделке'),('stage_title','Стадия сделки'),
    ('opportunity','Сумма'),('timely_request_percent','Процент своевременности создания заявок'),
    ('planned_subscription_date','Расчетная дата перевода на подписку'),
    ('implementation_planned_billing_start','Внедрение: Плановая дата начала списаний'),
    ('implementation_planned_subscription','Внедрение: Плановая дата перевода на подписку'),
    ('billing_start_date','Дата начала списаний'),('machines_count','Кол-во машин'),
    ('salesperson_name','Ответственный продавец'),('implementation_responsible_name','Ответственный за внедрение'),
    ('integration_amount','Сумма за интеграцию'),('first_training_date','Дата первого обучения'),
    ('second_training_date','Дата второго обучения'),('reports_training_date','Дата обучения руководства по работе с отчетами'),
    ('cr_company_id','Идентификатор компании в КР'),
]
FUNNELS={'tech_integration':'Тех интеграция','implementation':'Внедрение','cr_start':'CR Start','support':'Сопровождение'}


def employee_plan_excel(plan, keys=None):
    rows=plan.planned_deals
    if keys is not None:
        available={f'{r.employee_id}-{r.id}':r for r in rows}
        rows=[available[k] for k in dict.fromkeys(keys) if k in available]
    book=Workbook(); sheet=book.active; sheet.title='Планы сотрудников'
    sheet.append([title for _,title in COLUMNS])
    for row in rows:
        values=[]
        for field,_ in COLUMNS:
            value=getattr(row,field)
            if field=='funnel':value=FUNNELS.get(value,value)
            if isinstance(value,str):value=ILLEGAL_CHARACTERS_RE.sub('',value)[:32767]
            values.append(value)
        sheet.append(values)
    totals=[None]*len(COLUMNS); totals[0]='Итого'
    totals[6]=sum((r.opportunity for r in rows),Decimal(0))
    totals[15]=sum((r.integration_amount or Decimal(0) for r in rows),Decimal(0))
    sheet.append(totals)
    for row in sheet:
        for cell in row:
            if isinstance(cell.value,str):cell.data_type='s'
            if cell.row in (1,sheet.max_row):cell.font=Font(bold=True)
        for index,(field,_) in enumerate(COLUMNS,1):
            if field in ('opportunity','integration_amount'):sheet.cell(row[0].row,index).number_format='#,##0.00'
            elif field.endswith('_date') or field.startswith('implementation_planned') or field=='planned_subscription_date':sheet.cell(row[0].row,index).number_format='dd.mm.yyyy'
    sheet.freeze_panes='E2';sheet.auto_filter.ref=f'A1:T{max(1,sheet.max_row-1)}'
    from openpyxl.utils import get_column_letter
    for i in range(1,21):sheet.column_dimensions[get_column_letter(i)].width=28
    sheet.column_dimensions['D'].width=50
    output=BytesIO();book.save(output);return output.getvalue()
