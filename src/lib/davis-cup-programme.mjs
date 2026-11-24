// Confirmed singles in playing order. The session time belongs to the tie.
// Never derive pairings from a squad list or use team-winner odds for a player.
const ties = [{
  verifiedAt: '2026-11-24T15:43:00Z', session: '2026-11-24T15:00:00Z', event: 'Davis Cup · Bologna', tie: 'Czechia v Canada',
  country: { code: 'it', name: 'Italy', flag: '/flags/it.png' }, surface: 'indoor-hard',
  teams: ['Czech Republic', 'Canada'],
  singles: [['Tomas Machac', 'Liam Draxl'], ['Jiri Lehecka', 'Felix Auger Aliassime']],
}];

export function davisCupProgramme(now) {
  const localDay = new Intl.DateTimeFormat('en-CA', {timeZone:'Europe/London', year:'numeric', month:'2-digit', day:'2-digit'}).format(now);
  return ties.filter(t => Date.parse(t.verifiedAt) <= +now && t.session.slice(0,10) >= localDay && Date.parse(t.session) <= +now + 72 * 3_600_000)
    .flatMap(t => t.singles.map(([player1_name, player2_name], index) => ({
      league: 'ATP', league_name: t.event, kickoff_iso: t.session, player1_name, player2_name,
      programme: { day: t.session.slice(0,10), session: t.session, tie: t.tie, teams: t.teams, order: index + 1, country:t.country, surface:t.surface },
    })));
}
