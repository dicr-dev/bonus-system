from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import AsyncSession
from cr_portal.api.deps import db_session
from cr_portal.models.deal import Deal
from cr_portal.models.user import User
from cr_portal.models.distribution import DistributionDecision
router=APIRouter()
@router.post('/{deal_id}/propose')
async def propose(deal_id:UUID,s:AsyncSession=Depends(db_session)):
    d=await s.get(Deal,deal_id)
    if not d: raise HTTPException(404,'Deal not found')
    if d.funnel!='tech_integration': raise HTTPException(400,'Only Tech Integration deals are distributed')
    users=list((await s.execute(select(User).where(User.is_active.is_(True)).order_by(User.full_name))).scalars().all())
    if not users: raise HTTPException(400,'No active users')
    rows=await s.execute(select(Deal.responsible_user_id,func.count(Deal.id)).where(Deal.status=='in_progress',Deal.responsible_user_id.is_not(None)).group_by(Deal.responsible_user_id)); load=dict(rows.all()); u=min(users,key=lambda x:(load.get(x.id,0),x.full_name)); dec=DistributionDecision(deal_id=d.id,proposed_user_id=u.id,reason=f"Минимальная текущая загрузка: {load.get(u.id,0)} сделок"); s.add(dec); await s.commit(); await s.refresh(dec); return {'decision_id':str(dec.id),'deal_id':str(d.id),'proposed_user_id':str(u.id),'reason':dec.reason}
