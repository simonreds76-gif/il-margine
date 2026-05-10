export type SignalMetric = {
  label: string;
  value: string;
  percentile?: number;
  note?: string;
  inverse?: boolean;
};

export type Signal = {
  id: string;
  match: string;
  competition: string;
  leagueSlug?: string;
  kickoff: string;
  kickoffUtc?: string;
  venue: string;
  player: string;
  team: string;
  position: string;
  playerNumber?: string;
  teamLogoPath?: string;
  leagueLogoPath?: string;
  teamPrimaryColor: string;
  teamSecondaryColor?: string;
  teamShirtPattern?: "solid" | "vertical-stripes" | "halves" | "sash";
  market: string;
  fairOdds: number;
  bestBookOdds: number;
  bestBookmaker: string;
  marketAverageOdds?: number;
  modelProbability: number;
  bookmakerProbability: number;
  projectedMinutes?: number;
  teamExpectedNpxg?: number;
  playerRecentNpxg?: number;
  attackingShare: number;
  opponentXga?: number;
  fixtureSwing: number;
  penaltyRole: string;
  lineupStatus: string;
  confidence: "High" | "Medium" | "Low";
  accent: string;
  recentChanceQuality?: string;
  teamAttackingOutlook?: string;
  opponentDefensiveWeakness?: string;
  playerMetrics: SignalMetric[];
  opponentMetrics: SignalMetric[];
  edgeReasons: string[];
};

export type LabArtifact = {
  generatedAt: string | null;
  edgeThresholdPp: number;
  fixturesEvaluated: number;
  signalsQualifying: number;
  leaguesCovered: string[];
  featuredSignalId?: string | null;
  signals: Signal[];
  isMock: boolean;
};

export type LabHighlight = {
  id: string;
  date: string;
  kickoff?: string;
  competition: string;
  league?: string;
  match: string;
  player: string;
  team?: string;
  bestBookmaker: string;
  bestOdds: number;
  fairOdds: number;
  modelChancePct: number;
  marketChancePct: number;
  priceGapPp: number;
  goalsScored: number;
  settledAt?: string;
};
