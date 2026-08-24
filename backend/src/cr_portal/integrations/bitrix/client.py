from typing import Any
import httpx
from cr_portal.core.config import settings
class BitrixClient:
    def __init__(self,access_token:str|None=None,client_endpoint:str|None=None):
        self.access_token=access_token; self.client_endpoint=(client_endpoint or settings.BITRIX_BASE_URL.rstrip('/')+'/rest/').rstrip('/')+'/'; self.webhook=settings.BITRIX_WEBHOOK_URL.rstrip('/')
    def url(self,m:str): return f"{self.webhook}/{m}.json" if self.webhook else f"{self.client_endpoint}{m}.json"
    async def call(self,m:str,p:dict[str,Any]|None=None):
        data=dict(p or {}); 
        if self.access_token and not self.webhook: data['auth']=self.access_token
        async with httpx.AsyncClient(timeout=30) as c: r=await c.post(self.url(m),json=data); r.raise_for_status(); j=r.json()
        if 'error' in j: raise RuntimeError(j.get('error_description',j['error']))
        return j
    async def call_all(self,m:str,p:dict[str,Any]):
        out=[]; start=0
        while True:
            q=dict(p); q['start']=start; j=await self.call(m,q); result=j.get('result',{}); page=result.get('items',result if isinstance(result,list) else []); out+=page
            if j.get('next') is None: break
            start=int(j['next'])
        return out
