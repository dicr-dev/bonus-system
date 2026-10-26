export function bitrixLoginUrl(location:{pathname:string;search:string;hash:string}):string {
 const returnTo=location.pathname+location.search+location.hash
 return `/api/v1/auth/bitrix/login?return_to=${encodeURIComponent(returnTo)}`
}
