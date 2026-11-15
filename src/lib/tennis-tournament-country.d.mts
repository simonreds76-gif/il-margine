export type TournamentCountry = {code:string; name:string; flag:string};
export function countryForTournament(event:string, tour:string, dateISO:string):TournamentCountry|null;
export function lookupTournamentCountry(event:string, tour:string, dateISO:string, editions: {event:string; aliases:string[]; tour:string; from:string; through:string; code:string; name:string}[]):TournamentCountry|null;
