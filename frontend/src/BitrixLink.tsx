import type {ReactNode} from 'react'
import {Typography} from 'antd'
import type {CalculationItem} from './types'

const portal='https://bx.crg.im'
const validId=(value:unknown)=>/^[1-9]\d*$/.test(String(value??''))

export function dealUrl(id:unknown):string|undefined {
 return validId(id)?`${portal}/crm/deal/details/${id}/`:undefined
}

export function sourceUrl(item:CalculationItem):string|undefined {
 if(item.source_type==='task'){
  let task:Record<string,unknown>={}
  try{task=JSON.parse(item.details_json||'{}').task??{}}catch{/* Older snapshots may have no task data. */}
  if(!validId(item.source_external_id))return undefined
  const group=task.groupId??task.GROUP_ID
  if(validId(group))return `${portal}/workgroups/group/${group}/tasks/task/view/${item.source_external_id}/`
  const responsible=task.responsibleId??task.RESPONSIBLE_ID
  return `${portal}/company/personal/user/${validId(responsible)?responsible:0}/tasks/task/view/${item.source_external_id}/`
 }
 return dealUrl(item.deal_bitrix_id??(item.source_type==='deal'?item.source_external_id:undefined))
}

export function BitrixLink({href,children}:{href:string|undefined;children:ReactNode}){
 return href?<Typography.Link href={href} target="_blank" rel="noopener noreferrer">{children}</Typography.Link>:<>{children}</>
}
