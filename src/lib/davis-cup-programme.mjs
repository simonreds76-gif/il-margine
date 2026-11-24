// Only dated, confirmed singles from the shared refresh may enter the match board.
export function davisCupProgramme(now, document) {
  const day = new Intl.DateTimeFormat('en-CA', {timeZone:'Europe/London', year:'numeric', month:'2-digit', day:'2-digit'}).format(now);
  const stamp = Date.parse(document?.verifiedAt);
  if (document?.version !== 1 || document.day !== day || !Number.isFinite(stamp) || stamp > +now + 60000 || !Array.isArray(document.ties)) return [];
  const cleanName = value => typeof value === 'string' && value.trim().length >= 2 && value.length <= 90 && !/[<>&/]/.test(value);
  const rows = [];
  const seen = new Set();
  for (const tie of document.ties) {
    if (!tie || !Array.isArray(tie.teams) || tie.teams.length !== 2 || !tie.teams.every(cleanName) || tie.teams[0] === tie.teams[1]
      || !Array.isArray(tie.singles) || tie.singles.length !== 2 || !tie.singles.every(p => Array.isArray(p) && p.length === 2 && p.every(cleanName))
      || new Set(tie.singles.flat()).size !== 4 || typeof tie.session !== 'string' || tie.session.slice(0,10) !== day
      || !Number.isFinite(Date.parse(tie.session))) continue;
    const key = [...tie.teams].sort().join('|');
    if (seen.has(key)) return [];
    seen.add(key);
    const bologna = tie.venue === 'Bologna';
    for (const [index, [player1_name, player2_name]] of tie.singles.entries()) {
      rows.push({league:'ATP', league_name:bologna ? 'Davis Cup · Bologna' : 'Davis Cup', kickoff_iso:tie.session, player1_name, player2_name,
        programme:{day, session:tie.session, tie:tie.teams.join(' v '), teams:tie.teams, order:index + 1,
          country:bologna ? {code:'it',name:'Italy',flag:'/flags/it.png'} : null, surface:bologna ? 'indoor-hard' : 'unknown'}});
    }
  }
  return rows;
}
