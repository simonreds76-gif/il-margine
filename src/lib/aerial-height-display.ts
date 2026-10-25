import type { Player } from '@/components/aerial/types';

type HeightPlayer = Pick<Player, 'id' | 'name' | 'role' | 'height_cm'>;

// Presentation only. Never substitute a partial average into model inputs or XI comparisons.
export function summarizeKnownHeights(players: HeightPlayer[]) {
  const outfield = players.filter(player => player.role !== 'GK');
  const known = outfield.filter(player => typeof player.height_cm === 'number' &&
    Number.isFinite(player.height_cm) && player.height_cm >= 130 && player.height_cm <= 230);
  const knownIds = new Set(known.map(player => player.id));
  const values = known.map(player => player.height_cm as number).sort((a, b) => a - b);
  return {
    known: known.length,
    complete: outfield.length === 10 && known.length === 10,
    players: known,
    missing: outfield.filter(player => !knownIds.has(player.id)).map(player => player.name),
    mean: values.length ? values.reduce((sum, height) => sum + height, 0) / values.length : null,
    tallestThreeMean: values.length >= 3 ? values.slice(-3).reduce((sum, height) => sum + height, 0) / 3 : null,
    atLeast185: values.length ? values.filter(height => height >= 185).length : null,
  };
}
