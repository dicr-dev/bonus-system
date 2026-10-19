import {QuestionCircleOutlined} from '@ant-design/icons'
import {Tooltip} from 'antd'
import type {ColumnsType} from 'antd/es/table'
import {columnHelp} from './crStartColumnHelp'

export function withColumnHelp<T extends object>(columns:ColumnsType<T>|undefined):ColumnsType<T>|undefined{
 return columns?.map(column=>{
  const label=typeof column.title==='string'?column.title:undefined
  const key='dataIndex' in column?String(column.dataIndex??''):''
  const explanation=label?columnHelp(key,label):undefined
  const title=label&&explanation?<span>{label}<Tooltip title={explanation} trigger={['hover','focus','click']}>
   <button type="button" className="cr-start-column-help" aria-label={`Что означает «${label}»`}
    onClick={event=>event.stopPropagation()} onKeyDown={event=>event.stopPropagation()}>
    <QuestionCircleOutlined aria-hidden="true"/>
   </button>
  </Tooltip></span>:column.title
  return 'children' in column?{...column,title,children:withColumnHelp(column.children)!}:{...column,title}
 })
}
