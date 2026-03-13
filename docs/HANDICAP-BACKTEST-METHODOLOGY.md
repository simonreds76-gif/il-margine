# Handicap Backtest — Methodology

## Why ML-odds inversion is wrong

You cannot synthesise reliable handicap lines from moneyline odds alone.

**The problem:** Many different `(p_a, p_b)` pairs produce the same match win probability. The K-M recursion maps `(p_a, p_b)` → match win prob, but the inverse is not unique.

**Example:**
- Sinner (p_a=0.70) vs Shapovalov (p_b=0.58) → ~85% Sinner wins
- Two players at 0.64 ± 0.03 → also ~85% for the favourite

Both give the same match win probability, but **completely different margin distributions**. Sinner–Shapovalov has a different expected game margin and P(fav covers -4.5) than the symmetric case.

**What the flawed backtest did:** Invert Pinnacle ML → generic `(p_a, p_b)` → "Pinnacle implied handicap probs". Compare to model's real decomposed `(p_a, p_b)` → model handicap probs. The ROI measured the difference between our serve decomposition and a generic inversion — not a real market inefficiency.

## Correct approach

1. **Spread scrape** — Done. Pinnacle spread lines are scraped and stored in `bookmaker_odds_snapshot` (spread_line, spread_odds1, spread_odds2).

2. **Collect 2–3 weeks** — Let the daily pipeline run. No shortcut.

3. **Backtest against real lines** — For each match with a real Pinnacle spread:
   - Model: `handicap_probs.prob_fav_covers(p_a, p_b, line)` and `prob_dog_covers`
   - Market: actual `spread_odds1`, `spread_odds2` from Pinnacle
   - Edge = model prob vs implied prob from market odds
   - Settle against actual game score

That is the only honest test of whether the serve decomposition adds value for handicap markets.
