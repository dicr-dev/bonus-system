import json
from datetime import UTC, datetime
from types import SimpleNamespace as Obj
from uuid import uuid4
from unittest.mock import AsyncMock, patch

import pytest

from cr_portal.services.app_settings import initial_metrics_employee_ids
from cr_portal.schemas.app_settings import AppSettingsPayload
from cr_portal.services.implementation_metrics import build_report, implementation_metrics, report_module, logistics_details
from cr_portal.services.implementation_speed import build_speed_report
from cr_portal.services.implementation_conversion import build_conversion_report


def dt(value):
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def deal(**values):
    return Obj(**(dict(id=uuid4(), bitrix_id=1, funnel="support", category_id=1,
                      implementation_responsible_user_id=uuid4(), title="Тест", stage_title="В работе",
                      stage_id="active", module_name="Логистика", company_bitrix_id=10,
                      company_name="Компания", created_time=dt("2026-01-02T00:00:00"),
                      closed_time=None, status="in_progress", raw_json="{}", opportunity=0, monthly_amount=0, machines_count=0) | values))


def event(d, date, stage, title, number):
    return Obj(deal_id=d.id, occurred_at=dt(date), stage_id=stage, stage_title=title,
               bitrix_event_id=number, category_id=d.category_id)


BUSINESS = Obj(field_cr_start_commercial_use_date="START", field_source_deal_id="SOURCE")


def report(deals, history=(), now="2026-05-02T00:00:00"):
    return build_report(deals, [], history, BUSINESS, dt(now))


def test_control_month_and_continuation():
    old = deal(status="lost", closed_time=dt("2026-02-01T00:00:00"))
    new = deal(bitrix_id=2, created_time=dt("2026-04-20T00:00:00"))
    rows = report([old, new])
    assert len(rows) == 1
    assert rows[0]["result"] == "retained"
    assert rows[0]["control_end"] == "2026-05-01"
    assert report([old, new], now="2026-04-25T00:00:00")[0]["result"] == "pending"


def test_report_includes_deal_and_monthly_amounts():
    row = report([deal(opportunity=12500.25, monthly_amount=350.50, machines_count=7)])[0]
    assert row['opportunity'] == '12500.25'
    assert row['monthly_amount'] == '350.5'
    assert row['machines_count'] == 7


def test_overlap_is_an_error():
    first = deal()
    second = deal(bitrix_id=2, created_time=dt("2026-02-01T00:00:00"))
    assert all(row["result"] == "unknown" for row in report([first, second]))


def test_successful_deals_are_excluded_from_report_and_support_chain():
    won_support = deal(status="won")
    won_start = deal(bitrix_id=2, funnel="cr_start", status="won", module_name=None,
                     raw_json=json.dumps({"START": "2026-01-02"}))
    active = deal(bitrix_id=3, created_time=dt("2026-02-01T00:00:00"))
    rows = report([won_support, won_start, active], now="2026-06-02T00:00:00")
    assert len(rows) == 1
    assert rows[0]["bitrix_id"] == 3
    assert rows[0]["result"] == "retained"


def test_cr_start_uses_existing_temporary_working_stage_rule():
    d = deal(funnel="cr_start", module_name="КР Старт", stage_title="Коммерческое использование",
             stage_id="commercial", raw_json=json.dumps({"START": "2026-01-02"}))
    history = [event(d, "2026-01-02T00:00:00", "commercial", "Коммерческое использование", 1),
               event(d, "2026-02-02T00:00:00", "working", "Начали работать", 2),
               event(d, "2026-02-03T00:00:00", "commercial", "Коммерческое использование", 3)]
    assert report([d], history)[0]["result"] == "retained"


def test_missing_company_is_not_a_loss():
    assert report([deal(company_bitrix_id=None)])[0]["result"] == "unknown"


def test_empty_module_defaults_to_cr_start_only_in_cr_start_funnel():
    start_deal = deal(funnel="cr_start", module_name=None, raw_json=json.dumps({"START": "2026-01-02"}))
    assert report([start_deal])[0]["module"] == "CR Start"
    assert report([deal(module_name="  ")]) == []


def test_missing_responsible_is_excluded_from_both_funnels():
    support = deal(implementation_responsible_user_id=None)
    start = deal(bitrix_id=2, funnel="cr_start", implementation_responsible_user_id=None,
                 raw_json=json.dumps({"START": "2026-01-02"}))
    assert report([support, start]) == []


def test_unassigned_continuation_still_confirms_subscription():
    old = deal(status="lost", closed_time=dt("2026-02-01T00:00:00"))
    new = deal(bitrix_id=2, created_time=dt("2026-04-20T00:00:00"),
               implementation_responsible_user_id=None)
    rows = report([old, new])
    assert len(rows) == 1
    assert rows[0]["result"] == "retained"


def test_deals_without_start_are_excluded_but_other_unknowns_remain():
    no_cr_start_date = deal(funnel="cr_start", module_name=None, raw_json="{}")
    no_support_date = deal(bitrix_id=2, created_time=None)
    missing_company = deal(bitrix_id=3, company_bitrix_id=None)
    rows = report([no_cr_start_date, no_support_date, missing_company])
    assert len(rows) == 1
    assert rows[0]["bitrix_id"] == 3
    assert rows[0]["result"] == "unknown"


def test_default_roster_matches_full_names_in_either_order():
    users = [Obj(id="1", full_name="Гейдарова Лейла"), Obj(id="2", full_name="Андрей Трунов"),
             Obj(id="3", full_name="Рушан Кашапов")]
    assert initial_metrics_employee_ids(users) == ["1", "2"]


@pytest.mark.asyncio
async def test_report_filters_deals_and_keeps_selected_employee_without_deals():
    users = [Obj(id=uuid4(), full_name="Первый"), Obj(id=uuid4(), full_name="Второй"),
             Obj(id=uuid4(), full_name="Другой")]
    data = [deal(implementation_responsible_user_id=users[0].id),
            deal(bitrix_id=2, company_bitrix_id=11, implementation_responsible_user_id=users[2].id)]
    results = [Obj(scalars=lambda: data), Obj(scalars=lambda: users), Obj(scalars=lambda: [])]
    session = Obj(execute=AsyncMock(side_effect=results))
    business = Obj(implementation_metrics_employee_ids=[str(users[0].id), str(users[1].id)],
                   implementation_metrics_hire_dates={str(users[0].id): '2026-08-01'})
    with patch('cr_portal.services.implementation_metrics.build_report', return_value=[
        {'employee_id': str(users[0].id)}, {'employee_id': str(users[2].id)}
    ]):
        result = await implementation_metrics(session, business)
    assert len(result['employees']) == 2
    assert result['employees'][0]['hire_date'] == '2026-08-01'
    assert result['employees'][1]['hire_date'] is None
    assert result['deals'] == [{'employee_id': str(users[0].id)}]


def test_hire_dates_are_validated_and_serialized_as_dates():
    payload = AppSettingsPayload(implementation_metrics_hire_dates={'employee': '2026-08-01'}, employee_termination_dates={'employee': '2027-01-01'})
    assert payload.model_dump(mode='json')['implementation_metrics_hire_dates'] == {'employee': '2026-08-01'}
    assert payload.model_dump(mode='json')['employee_termination_dates'] == {'employee': '2027-01-01'}
    with pytest.raises(ValueError):
        AppSettingsPayload(implementation_metrics_hire_dates={'employee': '2026-02-30'})


@pytest.mark.parametrize('module', ['Топливный планировщик', 'Дальнобой + ТМ', 'Маршрутизация', 'Каргоран Лайт + ТМ'])
def test_new_support_modules_are_recognized(module):
    d = deal(module_name=module)
    assert report_module(d) == module
    assert report([d])[0]['result'] == 'retained'


def test_cr_start_transfer_to_logistics_is_excluded():
    d = deal(funnel='cr_start', stage_title='Перешли в Логистику', module_name=None,
             raw_json=json.dumps({'START': '2026-01-02'}))
    assert report([d]) == []


def test_no_money_is_a_loss_and_waits_until_end_of_control_month():
    d = deal(funnel='cr_start', stage_title='Нет денег', stage_id='no_money', status='lost',
             raw_json=json.dumps({'START': '2026-09-29'}), created_time=dt('2026-09-07T00:00:00'))
    history = [event(d, '2026-09-29T12:00:00', 'commercial', 'Коммерческое использование', 1),
               event(d, '2026-11-09T06:04:49', 'no_money', 'Нет денег', 2)]
    assert report([d], history, now='2026-11-25T00:00:00')[0]['result'] == 'pending'
    assert report([d], history, now='2027-01-02T00:00:00')[0]['result'] == 'lost'


def test_speed_uses_inclusive_days_and_creation_cohort():
    owner=uuid4()
    tech=deal(bitrix_id=10,funnel='tech_integration',created_time=dt('2026-03-01T09:00:00'))
    impl=deal(bitrix_id=11,funnel='implementation',status='won',closed_time=dt('2026-03-03T08:00:00'),
              implementation_responsible_user_id=owner,raw_json=json.dumps({'SOURCE':['D_10']}))
    row=build_speed_report([tech,impl],[],BUSINESS)[0]
    assert row['start']=='2026-03-01' and row['days']==3
    assert [link['bitrix_id'] for link in row['links']]==[11,10]
    impl.closed_time=dt('2026-03-01T10:00:00')
    assert build_speed_report([tech,impl],[],BUSINESS)[0]['days']==1


def test_speed_excludes_successfully_closed_cr_start_even_with_date():
    closed=deal(funnel='cr_start', status='won', raw_json=json.dumps({'START':'2026-01-10'}))
    active=deal(bitrix_id=2, funnel='cr_start', status='in_progress', raw_json=json.dumps({'START':'2026-01-10'}))
    rows=build_speed_report([closed,active],[],BUSINESS)
    assert [row['bitrix_id'] for row in rows]==[2]


def test_speed_includes_only_successfully_closed_implementation():
    tech=deal(bitrix_id=10,funnel='tech_integration')
    won=deal(bitrix_id=11,funnel='implementation',status='won',closed_time=dt('2026-01-10T00:00:00'),raw_json=json.dumps({'SOURCE':['D_10']}))
    active=deal(bitrix_id=12,funnel='implementation',status='in_progress',company_bitrix_id=20)
    lost=deal(bitrix_id=13,funnel='implementation',status='lost',company_bitrix_id=30)
    rows=build_speed_report([tech,won,active,lost],[],BUSINESS)
    assert [row['bitrix_id'] for row in rows]==[11]
    assert rows[0]['days'] is not None


def test_speed_marks_missing_or_multiple_links_and_invalid_dates():
    tech=deal(bitrix_id=10,funnel='tech_integration')
    impl=deal(bitrix_id=11,funnel='implementation',status='won',closed_time=dt('2026-03-03T08:00:00'),raw_json=json.dumps({'SOURCE':['D_10']}))
    duplicate=deal(bitrix_id=12,funnel='implementation',status='lost',raw_json=json.dumps({'SOURCE':['D_10']}))
    row=build_speed_report([tech,impl,duplicate],[],BUSINESS)[0]
    assert row['days'] is None and 'Несколько' in row['reason']
    assert {item['bitrix_id'] for item in row['links']}=={10,11,12}
    assert build_speed_report([impl],[],BUSINESS)[0]['start'] is None
    start=deal(funnel='cr_start',created_time=dt('2026-03-03T00:00:00'),raw_json=json.dumps({'START':'2026-03-01'}))
    assert build_speed_report([start],[],BUSINESS)[0]['days'] is None


@pytest.mark.parametrize(('flag','machines','expected'),[(199,2,'Логистика с интеграцией'),(199,1,'Логистика только интеграция'),(200,3,'Логистика без интеграции')])
def test_logistics_uses_bitrix_enum_and_vehicle_count(flag,machines,expected):
    d=deal(raw_json=json.dumps({'INTEGRATION':flag,'MACHINES':machines}))
    business=Obj(field_integration_1c='INTEGRATION',field_machines_count='MACHINES')
    assert logistics_details(d,business)==(expected,'')


def test_logistics_keeps_no_integration_class_when_vehicle_count_missing():
    d=deal(raw_json=json.dumps({'INTEGRATION':200}))
    kind,warning=logistics_details(d,Obj(field_integration_1c='INTEGRATION',field_machines_count='MACHINES'))
    assert kind=='Логистика без интеграции' and 'количество ТС' in warning


def test_conversion_counts_started_deals_and_completed_implementations():
    tech=deal(bitrix_id=10,funnel='tech_integration')
    won=deal(bitrix_id=11,funnel='implementation',status='won',closed_time=dt('2026-03-03T08:00:00'),raw_json=json.dumps({'SOURCE':['D_10']}))
    cr=deal(bitrix_id=12,funnel='cr_start',status='lost',raw_json=json.dumps({'START':'2026-01-10'}))
    missing=deal(bitrix_id=13,funnel='tech_integration',company_bitrix_id=11)
    rows=build_conversion_report([tech,won,cr,missing],[],BUSINESS)
    assert {row['bitrix_id']:row['result'] for row in rows}=={10:'retained',12:'retained',13:'lost'}
    assert len(rows[0]['links'])==2


def test_conversion_pending_and_duplicate_implementations_are_distinct():
    tech=deal(bitrix_id=10,funnel='tech_integration')
    active=deal(bitrix_id=11,funnel='implementation',status='in_progress',raw_json=json.dumps({'SOURCE':['D_10']}))
    duplicate=deal(bitrix_id=12,funnel='implementation',status='lost',raw_json=json.dumps({'SOURCE':['D_10']}))
    assert build_conversion_report([tech,active],[],BUSINESS)[0]['result']=='pending'
    row=build_conversion_report([tech,active,duplicate],[],BUSINESS)[0]
    assert row['result']=='unknown' and len(row['links'])==3


def test_speed_known_cr_start_date_issue_is_in_details_not_error_count():
    d=deal(bitrix_id=48941,funnel='cr_start',created_time=dt('2025-10-21T07:00:00'),raw_json=json.dumps({'START':'2025-10-17'}))
    row=build_speed_report([d],[],BUSINESS)[0]
    assert row['days'] is None and row['reason']=='Дата завершения раньше даты начала'
    assert row['is_error'] is False
    d.bitrix_id=48942
    assert build_speed_report([d],[],BUSINESS)[0]['is_error'] is True


@pytest.mark.parametrize(('name','expected'),[('КР Старт','Логистика'),('КР Старт Эксплуатация','Эксплуатация')])
def test_integration_funnels_map_cr_start_directions(name,expected):
    d=deal(funnel='implementation',module_name=name)
    assert report_module(d)==expected
