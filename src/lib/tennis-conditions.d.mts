export type Conditions = {name:string;tour:string;year:number;family:string|null;edition:unknown;history:unknown[];estimate:unknown;checkedAt:string};
export function conditionsFor(input:{event:string;tour:string;date:string}):Conditions|null;
export function latestSharedConditions(schedules:unknown[][],asOf:string):Conditions|null;
export function renderConditions(c:Conditions|null,options?:{compact?:boolean;embedded?:boolean;contextLabel?:string}):string;
