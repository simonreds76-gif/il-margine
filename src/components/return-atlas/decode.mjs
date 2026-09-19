export function decodeAtlas(index, checkedAt) {
  if (index.schema !== 1 || !Array.isArray(index.matches) || !Array.isArray(index.players) || index.matches.length !== index.metadata.matches) throw new Error('Invalid Return Atlas release');
  const { players, surfaces, sources } = index;
  const matches = index.matches.map(([id,date,p1,p2,o1,o2,winner,surface,source]) => ({
    id,date,p1:players[p1].id,p2:players[p2].id,o1,o2,winner:players[winner===0?p1:p2].id,
    surface:surfaces[surface],source:sources[source],status:'completed',level:'ATP-main',
  }));
  return { players, matches, portraits:index.portraits, metadata:{...index.metadata,checkedAt},
    eligibleRecords:index.eligible.map(([p,date,s])=>[players[p].id,date,surfaces[s]]) };
}
