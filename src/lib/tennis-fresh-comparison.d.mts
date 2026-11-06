export type FreshComparison={side:string;probability:number|null;fair:number|null;odds:number|null;bookmaker:string|null;observedAt:string|null;ageMinutes:number|null;ev:number|null;buffer:number|null;reason:string};
export function bestFreshComparison(row:Record<string,unknown>,now:number):FreshComparison[];
