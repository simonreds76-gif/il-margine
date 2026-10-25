export const researchTools = [
  { id: 'matchday', href: '/football-atlas/fixtures', label: 'Football Matchday', description: 'Club & manager H2H', image: '/football-atlas/matchday/mark-v1.svg' },
  { id: 'football', href: '/football-atlas', label: 'Club returns', description: 'Historical betting returns', image: '/images/tools/football-v1.webp' },
  { id: 'managers', href: '/manager-atlas', label: 'Manager returns', description: 'Head to head returns', image: '/manager-atlas/mark-v2.svg' },
  { id: 'tennis', href: '/return-atlas', label: 'Tennis returns', description: 'Player betting returns', image: '/images/tools/tennis-v1.webp' },
  { id: 'tennis-matchday', href: '/tennis-matchday', label: 'Tennis Matchday', description: 'Daily fixtures & H2H', image: '/tennis-matchday/mark.svg' },
  { id: 'matchup', href: '/tennis-matchup', label: 'Matchup Lab', description: 'Serve, return & context', image: '/tennis-matchup/court-v1.webp' },
  { id: 'aerial', href: '/fair-odds-lab/aerial', label: 'Air Control', description: 'Lineup height & headers', image: '/aerial/mark.webp' },
] as const;
export type ResearchTool = typeof researchTools[number]['id'];

