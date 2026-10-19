export type EmployeeVisibility = {id:string;name:string;active:boolean|null}

export function isCollapsedEmployee(employee:Pick<EmployeeVisibility,'name'|'active'>):boolean{
 const names=employee.name.toLocaleLowerCase('ru').trim().split(/\s+/)
 const additional=(names.includes('дамир')&&names.includes('искандеров'))
  ||(names.includes('михаил')&&names.includes('дорофеев'))
 return employee.active===false||additional
}

export function partitionEmployeeRows<T>(rows:T[],employees:EmployeeVisibility[],
 employeeId:(row:T)=>string,employeeName:(row:T)=>string=()=> ''):{visible:T[];collapsed:T[]}{
 const byId=new Map(employees.map(employee=>[employee.id,employee]))
 const visible:T[]=[],collapsed:T[]=[]
 for(const row of rows){
  const employee=byId.get(employeeId(row))??{name:employeeName(row),active:null}
  ;(isCollapsedEmployee(employee)?collapsed:visible).push(row)
 }
 return {visible,collapsed}
}
