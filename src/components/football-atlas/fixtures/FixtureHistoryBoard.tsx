'use client';

import { useEffect, useState } from 'react';
import ArchiveHistoryScope, { useArchiveScope } from '@/components/ArchiveHistoryScope';
import FixtureBoard from './FixtureBoard';
import type { FixtureBoard as Board } from './types';
import release from '@/data/covered-leagues-release.json';

export default function FixtureHistoryBoard({ board }: { board: Board }) {
  const available = release.baseBoardVersion === board.version;
  const { covered, choose } = useArchiveScope(available);
  const [expanded, setExpanded] = useState<Board | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!covered) return;
    const controller = new AbortController();
    fetch(release.boardUrl, { signal: controller.signal }).then(async r => {
      if (!r.ok) throw Error('History unavailable');
      const value = await r.json() as Board;
      if (value.version !== release.version) throw Error('History version mismatch');
      const originals = new Map(board.fixtures.map(f => [f.id, f]));
      if (value.fixtures.length !== originals.size || new Set(value.fixtures.map(f => f.id)).size !== originals.size || value.fixtures.some(f => {
        const original = originals.get(f.id);
        return !original || f.league === 'championship' || f.league !== original.league || f.kickoff !== original.kickoff
          || JSON.stringify(f.home) !== JSON.stringify(original.home) || JSON.stringify(f.away) !== JSON.stringify(original.away)
          || JSON.stringify(f.managers) !== JSON.stringify(original.managers);
      })) throw Error('History extension must preserve fixtures and manager records');
      setExpanded(value); setError(false);
    }).catch(() => { if (!controller.signal.aborted) setError(true); });
    return () => controller.abort();
  }, [covered, attempt, board.fixtures]);
  const additions = available ? release.additionalClubMeetings : {};
  return <><ArchiveHistoryScope covered={covered} choose={choose} available={available} />
    {covered && !expanded ? <p role="status">{error ? <>The wider history could not load. <button onClick={() => setAttempt(attempt + 1)}>Retry</button> or select the original archive.</> : 'Loading the wider league history…'}</p> : <FixtureBoard key={covered ? release.version : board.version} board={covered ? expanded! : board} covered={covered} additions={additions} onExpand={() => choose(true)} />}
  </>;
}
