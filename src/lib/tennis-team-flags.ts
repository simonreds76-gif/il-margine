// A tennis team is identified by both fixture participants, never the host venue.
const countries = [
  ["ae", "United Arab Emirates", "UAE"], ["ar", "Argentina", "ARG"],
  ["at", "Austria", "AUT"], ["au", "Australia", "AUS"],
  ["be", "Belgium", "BEL"], ["br", "Brazil", "BRA"], ["ca", "Canada", "CAN"],
  ["ch", "Switzerland", "SUI"], ["cl", "Chile", "CHI"], ["cn", "China", "CHN"],
  ["de", "Germany", "GER"], ["es", "Spain", "ESP"], ["fi", "Finland", "FIN"],
  ["fr", "France", "FRA"], ["gb", "Great Britain", "United Kingdom", "Britain", "GBR", "UK", "Team GB"],
  ["gr", "Greece", "GRE"], ["hk", "Hong Kong", "Hong Kong China", "HKG"], ["hr", "Croatia", "CRO"],
  ["it", "Italy", "ITA"], ["jp", "Japan", "JPN"], ["kr", "South Korea", "Korea Republic", "Republic of Korea", "KOR"],
  ["kz", "Kazakhstan", "KAZ"], ["ma", "Morocco", "MAR"], ["mx", "Mexico", "MEX"],
  ["nl", "Netherlands", "The Netherlands", "NED"], ["nz", "New Zealand", "NZL"],
  ["pe", "Peru", "PER"], ["pt", "Portugal", "POR"], ["qa", "Qatar", "QAT"], ["se", "Sweden", "SWE"],
  ["sk", "Slovakia", "Slovak Republic", "SVK"], ["tn", "Tunisia", "TUN"],
  ["tw", "Chinese Taipei", "Taiwan", "TPE"], ["us", "United States", "United States of America", "USA"],
  ["uy", "Uruguay", "URU"],
];

const flagPaths = new Map<string, string>();
for (const [code, ...aliases] of countries) {
  for (const label of [code, ...aliases]) flagPaths.set(label.toLowerCase(), `/flags/${code}.png`);
}

export function tennisTeamFlag(name: string): string | undefined {
  return flagPaths.get(name.trim().toLowerCase().replace(/\s+/g, " "));
}
