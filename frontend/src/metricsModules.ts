export const startModules=['CR Start','CR Start Эксплуатация','CR Start ТМ']
export const logisticsOptions=['Вся логистика','Логистика без интеграции','Логистика с интеграцией','Логистика только интеграция']
export const otherModules=[...logisticsOptions,'Эксплуатация','Топливный модуль','Загрузки','Топливный планировщик','Дальнобой + ТМ','Маршрутизация','Каргоран Лайт + ТМ']
export function matchesModule(deal:{module:string;logistics_type:string|null},selected:string[]){
 if(!selected.length)return true
 if(deal.module==='Логистика')return selected.includes('Вся логистика')||!!deal.logistics_type&&selected.includes(deal.logistics_type)
 return selected.includes(deal.module)
}
