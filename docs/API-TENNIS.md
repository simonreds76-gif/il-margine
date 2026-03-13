# API-Tennis (trial)

## Where to put the key

In the **project root** file **`.env.local`** (the same file where you have `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, etc.) add **one line** anywhere:

```
API_TENNIS_KEY=your_actual_key_here
```

No quotes needed unless the key has spaces. Don’t commit `.env.local`; it’s gitignored.

## Probe all methods

From the project root:

```
python scripts/api-tennis-probe.py
```

This calls every main method (events, tournaments, fixtures for today, standings, livescore, players, H2H, odds, live_odds) and prints what comes back. Use the output to decide what’s useful; we already have Pinnacle for odds.

## After the trial

If we keep using it: keep the key in `.env.local` only; for Vercel add `API_TENNIS_KEY` in the project’s Environment Variables. If we don’t renew, remove the key and any code that calls the API.
