import registry from '../data/tennis-tournament-countries.json' with { type: 'json' };

const key = s => s.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').trim().toLowerCase().replace(/\s+/g, ' ');

// Presentation only: a verified tournament edition, never a player's nationality.
// Date bounds deliberately prevent a relocated future edition inheriting a flag.
export function lookupTournamentCountry(event, tour, dateISO, editions) {
  if (typeof event !== 'string' || typeof dateISO !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(dateISO)) return null;
  const parsed = new Date(`${dateISO}T12:00:00Z`);
  if (!Number.isFinite(parsed.getTime()) || parsed.toISOString().slice(0,10) !== dateISO) return null;
  const matches = editions.filter(e => e.tour === tour && e.from <= dateISO && e.through >= dateISO && [e.event, ...e.aliases].some(n => key(n) === key(event)));
  const countries = new Set(matches.map(e => e.code));
  if (countries.size !== 1) return null;
  const e = matches[0];
  return { code:e.code, name:e.name, flag:`/flags/${e.code}.png` };
}
export const countryForTournament = (event, tour, dateISO) => lookupTournamentCountry(event, tour, dateISO, registry.editions);
