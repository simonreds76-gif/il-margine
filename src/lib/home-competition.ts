// Presentation only: venue names, never player nationality or model inputs.
// Unknown or relocated event brands deliberately receive no country flag.
const venues: [RegExp, string, string][] = [
  [/^(Shanghai|Beijing|Chengdu|Hangzhou|Zhuhai|Shenzhen)\b/i, 'cn', 'China'],
  [/^(Tokyo)\b/i, 'jp', 'Japan'],
  [/^(Seoul)\b/i, 'kr', 'South Korea'],
  [/^(Hong Kong)\b/i, 'hk', 'Hong Kong'],
  [/^(Australian Open|Melbourne|Adelaide|Brisbane|Sydney)\b/i, 'au', 'Australia'],
  [/^(Auckland)\b/i, 'nz', 'New Zealand'],
  [/^(Indian Wells|Miami|Cincinnati|US Open|U\.S\. Open|New York|Dallas|Delray Beach|Houston|Washington|Winston Salem|Winston-Salem|Newport|Atlanta)\b/i, 'us', 'United States'],
  [/^(Toronto|Montreal)\b/i, 'ca', 'Canada'],
  [/^(Wimbledon|London|Queens|Queen's|Eastbourne|Nottingham)\b/i, 'gb', 'United Kingdom'],
  [/^(Roland Garros|French Open|Paris|Marseille|Montpellier|Lyon|Metz)\b/i, 'fr', 'France'],
  [/^(Madrid|Barcelona|Mallorca)\b/i, 'es', 'Spain'],
  [/^(Rome|Roma|Turin)\b/i, 'it', 'Italy'],
  [/^(Hamburg|Halle|Munich|Stuttgart)\b/i, 'de', 'Germany'],
  [/^(Vienna|Kitzbuhel|Kitzbühel)\b/i, 'at', 'Austria'],
  [/^(Basel|Geneva|Gstaad)\b/i, 'ch', 'Switzerland'],
  [/^(Rotterdam|Rosmalen|s-Hertogenbosch)\b/i, 'nl', 'Netherlands'],
  [/^(Brussels|Antwerp)\b/i, 'be', 'Belgium'],
  [/^(Stockholm|Bastad|Båstad)\b/i, 'se', 'Sweden'],
  [/^(Doha)\b/i, 'qa', 'Qatar'],
  [/^(Dubai|Abu Dhabi)\b/i, 'ae', 'United Arab Emirates'],
  [/^(Almaty|Astana)\b/i, 'kz', 'Kazakhstan'],
  [/^(Acapulco|Los Cabos)\b/i, 'mx', 'Mexico'],
  [/^(Buenos Aires|Cordoba|Córdoba)\b/i, 'ar', 'Argentina'],
  [/^(Rio de Janeiro|Rio)\b/i, 'br', 'Brazil'],
  [/^(Santiago)\b/i, 'cl', 'Chile'],
  [/^(Estoril)\b/i, 'pt', 'Portugal'],
  [/^(Marrakech)\b/i, 'ma', 'Morocco'],
  [/^(Umag)\b/i, 'hr', 'Croatia'],
];

export function tennisCompetition(event: string) {
  const name = event.replace(/^ATP\s+/i, '').trim();
  const venue = venues.find(([pattern]) => pattern.test(name));
  const label = name.replace(/\s*[·-]?\s+QF$/i, ' · Quarter-finals')
    .replace(/\s*[·-]?\s+SF$/i, ' · Semi-finals');
  return { label, country: venue ? { code: venue[1], name: venue[2] } : null };
}

export const homeLeagueLogos: Record<string, string> = {
  'Premier League': '/league-logos/epl.png',
  'Serie A': '/league-logos/serie-a.png',
  'La Liga': '/league-logos/la-liga.png',
  Bundesliga: '/league-logos/bundesliga.png',
  'Ligue 1': '/league-logos/ligue-1.png',
};
