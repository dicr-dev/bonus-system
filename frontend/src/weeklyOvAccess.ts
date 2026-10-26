export function canViewWeeklyOv(user:{is_admin:boolean; department_name?:string|null}):boolean {
 return user.is_admin||Boolean(user.department_name?.split(';').some(name=>name.trim()==='Отдел внедрения'))
}
