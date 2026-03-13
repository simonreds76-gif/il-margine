# Session Report for Claude — March 2026

Summary of changes, implementations, and backtest results from this session.

---

## 1. Grand Slam Calibration Analysis

**Script:** `scripts/slam-calibration.py`

**Purpose:** Analyse historical favourite/dog performance at Grand Slams to find systematic biases the model can exploit or correct.

**Usage:**
```bash
python scripts/slam-calibration.py --files data/backtest/backtest-results-2022.csv data/backtest/backtest-results-2023.csv data/backtest/backtest-results-2024.csv data/backtest/backtest-results-2025.csv
```

**Key findings (1,898 Grand Slam matches, 2022–2025):**
- **Early rounds (R128/R64, R64/R32):** Model overestimates favourites by ~2–3pp
- **Final:** Model underestimates favourites by ~6pp (actual 77.9% vs model 71.9%)
- **US Open:** Model overestimates favourites across rounds
- **Finals at AO, RG, Wimbledon:** Model underestimates favourites by ~10–11pp
- **Calibration overlay:** R128/R64 −0.029 (boost dog), R64/R32 −0.021, F +0.060 (boost fav)
- **Conclusion:** Bias is inconsistent across rounds/slams; a single round overlay did not improve simulated ROI

**Outputs:** `data/diagnostics/slam-calibration-report.txt`, `slam-round-calibration.png`, `slam-bias-heatmap.png`

---

## 2. Class Gap Adjustment (Tighter Thresholds)

**File:** `scripts/class_gap.py`

**Problem:** Model couldn't produce extreme probabilities for heavy mismatches (e.g. Djokovic 1.33 vs Pinnacle 1.10, Sinner 1.20 vs bookies 1.01).

**Change:** Lowered thresholds so the Elo blend kicks in earlier:
- `elo_gap_onset`: 250 → **150**
- `elo_gap_full`: 500 → **350**
- `rank_gap_onset`: 40 → **30**
- `rank_gap_full`: 120 → **100**
- `max_blend`: 0.85 → **0.90**

**Effect:** For Djokovic vs Majchrzak (gap ~330), full adjustment now applies. Sinner vs qualifier scenario: adjusted 0.9554 (odds 1.05) vs model 0.83 (odds 1.20).

---

## 3. Misprice Filter: Model Fav Odds < 1.25

**Files:** `scripts/strict-policy-report.py`, `src/app/api/fair-odds/route.ts`, `scripts/backtest-fair-odds.py`

**Rule:** Skip the entire match from signals when model favourite odds < 1.25. Both favourite and dog signals are unreliable at extreme mismatches (e.g. Shapovalov +141.9% "value" vs Sinner).

**Implementation:**
```python
model_fav_odds = min(odds1, odds2)
if model_fav_odds < 1.25:
    continue
```

**Wired into:**
- Strict policy report (CSV output)
- Fair-odds API (policy_match, policy signals)
- Backtest (for ROI evaluation)

---

## 4. Roger Chatbot Updates (Codex)

**Files:** `src/app/api/chat/route.ts`, `src/lib/chat-tools.ts`, `src/lib/chat-rag.ts`

**Changes:**
- **Underdog handling:** "Best underdog bet" returns underdog spots, not favourites
- **Tournament-edition results:** Match-level history by tournament/year/round (QF/SF/Final)
- **Deterministic follow-ups:** "Who did he beat in the quarters?" uses conversation context
- **X vs Y + tip:** "Michelsen vs Humbert today? What's your tip?" returns specific matchup lean, not generic list
- **Tips mode:** "Best tips" returns split output: Best value first, Best favourites second
- **Value engine:** `valuePicksToday()` — Pinnacle vs fair odds, ML only, min 35% win, fair_odds ≤ 4.5
- **Favourites cap:** When value list has entries, favourites capped to top 3; else up to 5
- **Last-year fix:** "How did Djokovic do at Indian Wells last year?" correctly treated as 2025

---

## 5. Daily Pipeline Schedule

**File:** `scripts/setup-automation-tasks.ps1`

**Change:** Added second daily run at 11:00 (existing 23:55 kept).

**Tasks:**
- `IlMargine-Daily`: 23:55
- `IlMargine-Daily-AM`: 11:00 (new)
- `IlMargine-Weekly`: Sunday 22:00

---

## 6. Debug Tool: Elo Lookup

**File:** `scripts/debug-elo.py`

**Purpose:** Query `player_elo` for given player names (e.g. Djokovic, Majchrzak).

**Usage:**
```bash
python scripts/debug-elo.py Djokovic Majchrzak
```

---

## 7. Backtest Results (With Both Misprice Filters)

**Filters applied:**
1. Model vs Pinnacle fav implied gap > 10pp
2. Model fav odds < 1.25

**Data:** 2022–2025 ATP, 9,889 matches

### Exclusions
- Misprice (10pp gap): 2,464
- Misprice (fav odds < 1.25): 1,670
- **Total excluded:** 3,578

### ROI by Value Threshold

| Threshold | Bets | ROI | P/L |
|-----------|------|-----|-----|
| Value>2% | 4,806 | **-3.05%** | -146.7u |
| Value>5% | 3,999 | **-3.23%** | -129.2u |
| Value>10% | 2,917 | **-4.74%** | -138.2u |

### ROI by Surface (5% threshold)

| Surface | Matches | ROI |
|---------|---------|-----|
| Hard | 5,638 | **+0.76%** |
| Clay | 3,046 | -8.61% |
| Grass | 1,205 | -7.70% |

### ROI by Series (5% threshold)

| Series | Matches | ROI |
|--------|---------|-----|
| Masters 1000 | 2,468 | **+1.18%** |
| Grand Slam | 1,898 | -4.16% |
| ATP250 | 3,896 | -5.26% |
| ATP500 | 1,569 | -6.56% |
| Masters Cup | 58 | +18.79% |

### Comparison: Before vs After Fav Odds < 1.25 Filter

| Metric | Before | After |
|--------|--------|-------|
| Value>2% ROI | -5.81% | **-3.05%** |
| Value>10% ROI | -9.35% | **-4.74%** |
| Hard | -3.56% | **+0.76%** |
| Masters 1000 | -1.71% | **+1.18%** |
| Grand Slam | -8.73% | **-4.16%** |
| Clay | -10.60% | -8.61% |
| Grass | -8.81% | -7.70% |

**Conclusion:** The fav odds < 1.25 filter materially improves ROI. Hard and Masters 1000 turn positive at 5% threshold. Grand Slam, Clay, and Grass remain negative but improve significantly.

---

## 8. Log Loss / Calibration

- **Log loss:** Ours 0.622 vs Pinnacle 0.585 (model does not beat Pinnacle)
- **Calibration:** Model overestimates in higher bins (80–85% pred 82.2%, actual 75.8%, gap −6.4pp)

---

## 9. Branch and Deployment

- All changes pushed to `golden-with-speed-insights`
- Production requires manual promote in Vercel
- Do not push to `main`

---

## 10. Files Modified (Summary)

| File | Change |
|------|--------|
| `scripts/slam-calibration.py` | New: Grand Slam calibration analysis |
| `scripts/class_gap.py` | Tighter thresholds (150/350, max_blend 0.90) |
| `scripts/strict-policy-report.py` | Misprice filter (fav odds < 1.25) |
| `scripts/backtest-fair-odds.py` | Misprice filter (fav odds < 1.25) |
| `scripts/setup-automation-tasks.ps1` | 11:00 daily task |
| `scripts/oncourt-daily.ps1` | Comment: runs at 11:00 and 23:55 |
| `scripts/debug-elo.py` | New: Elo lookup by player name |
| `src/app/api/chat/route.ts` | Value engine, split tips, X vs Y tip, underdog |
| `src/app/api/fair-odds/route.ts` | Misprice filter (fav odds < 1.25) |
| `src/lib/chat-tools.ts` | valuePicksToday(), tournament_edition_results |
| `src/lib/chat-rag.ts` | RAG intent hints |
