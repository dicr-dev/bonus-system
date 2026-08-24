import json
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.core.config import settings
from cr_portal.models.deal import Deal
from cr_portal.repositories.users import UserRepository
from cr_portal.repositories.deals import DealRepository
async def sync_users(s:AsyncSession,c):
    items=(await c.call('user.get',{'FILTER':{'ACTIVE':True}})).get('result',[]); repo=UserRepository(s)
    for x in items:
        name=' '.join(v for v in [x.get('NAME'),x.get('LAST_NAME')] if v).strip() or f"Bitrix user {x['ID']}"; await repo.upsert(int(x['ID']),x.get('EMAIL'),name,x.get('WORK_POSITION'))
    await s.commit(); return len(items)
def funnels():
    pairs=[(settings.BITRIX_TECH_INTEGRATION_CATEGORY_ID,'tech_integration'),(settings.BITRIX_IMPLEMENTATION_CATEGORY_ID,'implementation'),(settings.BITRIX_CR_START_CATEGORY_ID,'cr_start'),(settings.BITRIX_SUPPORT_CATEGORY_ID,'support')]; return {int(i):n for i,n in pairs if i is not None}
async def sync_deals(s:AsyncSession,c):
    fr=funnels(); repo=DealRepository(s); users=UserRepository(s); n=0
    for cat,funnel in fr.items():
        items=await c.call_all('crm.item.list',{'entityTypeId':2,'select':['id','title','categoryId','stageId','assignedById','opportunity','createdTime','closedTime'],'filter':{'categoryId':cat}})
        for x in items:
            d=await repo.by_bitrix_id(int(x['id']))
            if d is None: d=Deal(bitrix_id=int(x['id']),category_id=cat,funnel=funnel,stage_id='',status='in_progress',title=''); s.add(d)
            aid=int(x.get('assignedById') or 0) or None; u=await users.by_bitrix_id(aid) if aid else None; closed=x.get('closedTime')
            d.category_id=cat; d.funnel=funnel; d.stage_id=str(x.get('stageId','')); d.status=('success' if closed and 'WON' in d.stage_id.upper() else 'failed' if closed else 'in_progress'); d.title=str(x.get('title','')); d.opportunity=Decimal(str(x.get('opportunity') or 0)); d.bitrix_assigned_by_id=aid; d.responsible_user_id=u.id if u else None; d.raw_json=json.dumps(x,ensure_ascii=False,default=str)
            try: d.created_time=datetime.fromisoformat(str(x.get('createdTime')).replace('Z','+00:00')) if x.get('createdTime') else None
            except ValueError: d.created_time=None
            try: d.closed_time=datetime.fromisoformat(str(closed).replace('Z','+00:00')) if closed else None
            except ValueError: d.closed_time=None
            n+=1
    await s.commit(); return n
