# Path B: Strategic Edge Research Roadmap

**Context:** The model is a competent probability estimator (log-loss 0.630) competing against an elite one (Pinnacle 0.580). The 0.050 gap is the problem — but you don't need to close all of it. You need to close enough, in specific spots, to overcome the ~2–3% margin Pinnacle charges. That means finding situations where your model can be 0.580 or better — not everywhere, just somewhere exploitable.

**Core asset:** 25 years compiling odds. You know where soft spots exist in tennis markets better than any model can discover from data alone. The question is which intuitions can be systematised.

---

## Edge Sources (Ranked by Feasibility × Payoff)

### 1. Market Timing — Highest Feasibility, Fastest to Test

**Hypothesis:** Pinnacle's opening lines for early-week ATP matches are set with less sharp money than closing lines. If you scraped at market open AND at close, you could measure how much lines move and whether your model is closer to the closing line than the opening line.

**Edge:** Positive CLV against the opener (even if not against the closer) is tradeable — bet early at soft books, not at Pinnacle close.

**Current state:** You scrape Pinnacle at 23:55 UTC — one snapshot.

**Data requirement:** Two snapshots per match — open and close. Or: scrape more frequently; compare model to opener vs closer.

**Effort:** 2–3 weeks. Extend Pinnacle scraper; store open/close; compute CLV vs opener and vs closer; segment by tournament, round, time-to-match.

---

### 2. Scheduling and Fatigue — Builds on Existing Data

**Hypothesis:** The real edge is in compound scheduling: a player who played a 3-hour semifinal yesterday on outdoor hard, now facing a fresh opponent who had a walkover. The current model treats "played yesterday" as binary. The actual impact depends on match duration, conditions, and opponent rest differential.

**Current state:** Form/fatigue factors are crude (played yesterday = -0.008 penalty). You have `player_recent_activity`.

**Data requirement:** Match duration (from Sackmann or OnCourt), opponent rest days. Enrich `player_recent_activity` with duration and opponent freshness differential.

**Effort:** 2–3 weeks. Add duration to history; compute opponent rest; model fatigue as a function of duration × conditions × rest differential.

---

### 3. Surface-Speed Granularity — Extends Existing Infrastructure

**Hypothesis:** "Hard" is not one surface — Miami plays differently from the Australian Open. A sharper version would model player-specific speed preferences: some players overperform on fast hard courts and underperform on slow ones, regardless of overall hard court stats.

**Current state:** You have `tournament_serve_profile` with venue SPW. The model adjusts with a blunt residual shift. CPI overlay tested — no edge.

**Data requirement:** Sackmann ace rates and first-serve-in % by tournament (proxy for court speed). Player × court-speed interaction terms.

**Effort:** 2–3 weeks. Build player speed-preference profiles; add interaction to model; backtest.

---

### 4. Matchup-Specific Tactical Data — Highest Potential, Hardest to Build

**Hypothesis:** Beyond H2H W/L, the key is play-style interaction: how does Player A's heavy topspin game perform against Player B's flat-hitting counterpunching? The market systematically misprices certain archetype vs archetype matchups.

**Current state:** H2H records in data but barely used. Vs-leftie, vs-big-servers exist but are coarse.

**Data requirement:** Classify players into tactical archetypes (serve-and-volley, baseline grinder, all-court, heavy spin, big server). Model archetype vs archetype win rates. Your domain expertise is critical here — you know which matchups the market misprices.

**Effort:** 4–6 weeks. Archetype classification is manual or semi-automated; then backtest archetype × archetype segments.

---

### 5. In-Play / Set-Level Modelling — Completely Different Approach

**Hypothesis:** Pre-match markets are most efficient. Set and game markets are less efficient because they require conditional probability estimation. Your K-M recursion already computes set-level probabilities. A live model that updates after each set (or game) and compares to in-play markets could find edge — and in-play tennis is where bookmaker margins are widest.

**Current state:** K-M recursion exists. No live data feed.

**Data requirement:** Live odds feed (Betfair, Pinnacle live, etc.). Different architecture — real-time updates.

**Effort:** Multi-month. New data pipeline, live model, in-play comparison.

---

## Research Sprint Framework

For each edge source:

1. **Hypothesis** — One sentence. What do we believe?
2. **Data requirements** — What do we need? What do we have?
3. **Backtest framework** — How do we test it? Same segment validation as baseline.
4. **Go/no-go criteria** — Pass segment-edge-validation (year stability, multiplicity correction, log-loss gap, forward projection). If WEAK, stop. If MODERATE or STRONG, consider live trial.

**Rule:** No code changes to the live pipeline until something passes segment validation.

---

## Pick One

Choose the edge source your gut says has the most unexploited value. In the next session we'll build the research sprint for it: hypothesis, data requirements, backtest framework, and go/no-go criteria.

One edge source, done properly.
