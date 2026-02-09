# How the calculator numbers are calculated

The calculator shows **Player Props** and **Tennis Tips** only. Every number is:

**Baseline (fixed in code) + Live (from database `category_stats`).**

`category_stats` is fed by the `bets` table (view or trigger). When you add a pick, settle won/lost, or delete a bet in admin, the DB updates and the calculator refetches.

---

## 1. Where the numbers come from

| Source | What it is |
|--------|------------|
| **Baseline** | `src/lib/baseline.ts`: fixed historic stats (e.g. 780 props bets, +195u profit, 447 tennis bets, +38.4u profit). |
| **Live** | Supabase table `category_stats`: one row per category (e.g. props–pl, props–seriea, tennis–atp). Updated when `bets` changes. |

We **add** baseline and live for each market (props and tennis).

---

## 2. Formulas (same as tips pages “All Leagues” / “All Tennis”)

### Player Props

- **Live bets** = sum of `total_bets` over all `category_stats` rows with `market = 'props'`.
- **Live profit** = sum of `total_profit` over those same rows (in units).
- **Live stake** = sum of each settled bet’s `stake` from the `bets` table (props or tennis).
- **Avg odds (live)** = weighted average: `sum(avg_odds × total_bets) / sum(total_bets)` over those rows. If there are no live bets, we use 1.98.

Then we **combine with baseline**:

- **Total bets** = `BASELINE_STATS.props.total_bets` + live bets  
- **Total profit (u)** = `BASELINE_STATS.props.total_profit` + live profit  
- **Total stake (u)** = `BASELINE_STATS.props.total_stake` + live stake  
- **ROI (%)** = `(total profit / total stake) × 100`  
- **Avg odds** = live avg odds (from DB); if no live rows, 1.98  

### Tennis

Same idea, but for rows with `market = 'tennis'`, and we use tennis baseline and default avg odds 2.06 when there are no tennis rows.

---

## 3. Worked example (Player Props)

**Baseline (from code):**

- total_bets: 780  
- total_profit: 780 × 0.25 = **195u**  
- total_stake: 780u  

**Database `category_stats` (example) – only props rows:**

| market | category | total_bets | total_profit | avg_odds |
|--------|----------|------------|--------------|----------|
| props  | pl       | 10         | 2.2          | 1.95     |
| props  | seriea   | 5          | 1.4          | 2.02     |

**Live (sum over props rows):**

- propsLiveBets = 10 + 5 = **15**  
- propsLiveProfit = 2.2 + 1.4 = **3.6u**  
- propsLiveStake = 15u  
- propsAvgOdds = (1.95 + 2.02) / 2 = **1.985**  

**Combined (what the calculator shows):**

- **Total bets** = 780 + 15 = **795**  
- **Total profit** = 195 + 3.6 = **198.6u**  
- **Total stake** = 780 + 15 = **795u**  
- **ROI** = (198.6 / 795) × 100 = **24.98%**  
- **Avg odds** = 1.985  

**Returns by stake (e.g. £25/unit):**

- Total profit in £ = 198.6 × 25 = **£4,965**  
- Avg per bet = 4,965 / 795 = **£6.25/bet**  

If you then add or settle a bet in admin, `category_stats` changes, the calculator refetches, and these combined numbers (bets, profit, ROI, avg odds and the £ returns) all update automatically.

---

## 4. Tennis example (same logic)

**Baseline (from code):**

- total_bets: 447  
- total_profit: 447 × 0.086 = **38.44u**  
- total_stake: 447u  

**DB example – tennis rows only:**

| market | category  | total_bets | total_profit | avg_odds |
|--------|-----------|------------|--------------|----------|
| tennis | atp       | 3          | 0.24         | 2.10     |
| tennis | challenger| 2          | 0.12         | 2.05     |

**Live:** 5 bets, 0.36u profit, 5u stake, avg odds (2.10 + 2.05) / 2 = 2.075  

**Combined:**

- Total bets = 447 + 5 = **452**  
- Total profit = 38.44 + 0.36 = **38.8u**  
- Total stake = 447 + 5 = **452u**  
- ROI = (38.8 / 452) × 100 = **8.58%**  
- Avg odds = 2.075  

So: **numbers = baseline + database**, and the calculations above are exactly what the app applies.

---

## 5. Correctness

- **Total bets, total profit, total stake, ROI, returns in £, avg per bet**  
  All are correct given the data we have: we sum live from `category_stats`, add baseline, then apply the formulas above.

- **Avg odds**  
  We use a **weighted** average: `sum(avg_odds × total_bets) / sum(total_bets)` per market, so categories with more bets count more. If there are no live bets we use 1.98 (props) or 2.06 (tennis).

- **Live stake (exact)**  
  We fetch all settled bets (`won` / `lost`) from `bets`, then **sum each bet’s `stake`** per market (props and tennis). That total is used as live stake, so **ROI is exact** for any staking plan (1u, 2u, 0.5u, etc.). If for some reason no stakes are returned, we fall back to 1u per bet so the calculator still shows a number.
