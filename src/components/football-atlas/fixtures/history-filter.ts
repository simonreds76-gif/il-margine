import type { FixtureCard, RecordSummary } from './types';

export type HistoryFilter = 'all' | 'any' | 'both';
export type OutcomeFilter = 'all' | 'home' | 'draw' | 'away';
const outcomeIndex = { home: 0, draw: 1, away: 2 };

function positive(record: RecordSummary, index: number) {
  const outcome = record.outcomes[index];
  return record.count >= 3 && outcome?.positive === true && outcome.roi !== null && outcome.roi > 0;
}

function verifiedManagers(fixture: FixtureCard) {
  return Boolean(fixture.home.manager?.id && fixture.away.manager?.id
    && fixture.home.manager.status === 'verified' && fixture.away.manager.status === 'verified');
}

/** Each qualifying index describes the same selection in both historical records. */
export function bothPositiveOutcomes(fixture: FixtureCard, stale = false): number[] {
  if (stale || !verifiedManagers(fixture)) return [];
  return [0, 1, 2].filter(index => positive(fixture.managers, index) && positive(fixture.clubs, index));
}

export function matchesHistoryFilter(fixture: FixtureCard, filter: HistoryFilter, outcome: OutcomeFilter, stale = false) {
  if (filter === 'all') return true;
  if (stale) return false;
  const indices = outcome === 'all' ? [0, 1, 2] : [outcomeIndex[outcome]];
  if (filter === 'both') {
    const paired = bothPositiveOutcomes(fixture);
    return indices.some(index => paired.includes(index));
  }
  return indices.some(index => positive(fixture.clubs, index)
    || verifiedManagers(fixture) && positive(fixture.managers, index));
}
