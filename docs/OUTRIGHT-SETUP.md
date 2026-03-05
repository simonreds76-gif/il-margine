# Outright Odds Setup (Tournament Winner / "Is X Playing?")

## 1. SQL — Run once in Supabase

**File:** [RUN-THIS-FOR-OUTRIGHTS.sql](../RUN-THIS-FOR-OUTRIGHTS.sql) — click to open, copy all, paste into Supabase SQL Editor, run.

## 2. Why only ~16 players?

Pinnacle's outright market lists only the **top ~16 favorites** per tournament plus "The Field" for everyone else. That's the full list they provide — we can't get the full 96‑player draw from their API. The chatbot can answer "is Draper playing?" for the top contenders; for others it will say "no data" if they're not in Pinnacle's list.

## 3. Daily pipeline (full commands)

**PowerShell (from project root):**

```powershell
cd c:\Users\44746\Downloads\il-margine
npm run daily-odds
```

**Or Python directly:**

```powershell
cd c:\Users\44746\Downloads\il-margine
python scripts/run-daily-odds.py
```

**Skip strict report (only Pinnacle + fair odds):**

```powershell
cd c:\Users\44746\Downloads\il-margine
python scripts/run-daily-odds.py --skip-strict-report
```

**Pinnacle only (no fair odds, no strict report):**

```powershell
cd c:\Users\44746\Downloads\il-margine
python scripts/pinnacle-scrape-odds.py
```

The daily pipeline runs: (1) Pinnacle scraper (match odds + outrights), (2) fair-odds compute, (3) strict policy report.
