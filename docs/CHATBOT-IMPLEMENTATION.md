# Chatbot Implementation Summary

All chatbot changes live in the codebase. This doc summarises what's built and the key rules.

## Files

| File | Purpose |
|------|---------|
| `src/app/api/chat/route.ts` | API route, system prompt, tool definitions, Groq/Kimi K2 |
| `src/lib/chat-tools.ts` | All Supabase query functions (tools) |
| `src/components/ChatWidget.tsx` | Chat UI, hidden in production |

## Tools (18)

| Tool | Use case |
|------|----------|
| `search_player` | Resolve name → player ID (always use first) |
| `player_info` | Rank, age, hand, Elo, country |
| `player_surface_stats` | SPW, RPW by surface (12m/36m) — per-point stats, not per-game |
| `player_advanced_stats` | First serve %, ace rate, BP save/convert |
| `head_to_head` | H2H with surface breakdown |
| `player_record_at_tournament` | W-L at a tournament |
| `player_recent_form` | Last 10 matches, fatigue |
| `player_record_vs_lefties` | W-L vs left-handed players |
| `player_record_vs_big_server` | W-L vs opponents with SPW ≥ 68% on that surface |
| `player_record_at_altitude` | W-L at high-altitude venues |
| `player_record_vs_rank_range` | W-L vs top N (e.g. top 10, top 20) |
| `player_record_by_round` | W-L by round (Final, SF, QF, etc.) |
| `player_record_by_surface` | W-L by surface (Hard, Clay, Grass) |
| `tournament_info` | Surface, country, altitude, past editions |
| `court_pace` | CPI / court speed (fast/slow) |
| `tournament_past_winners` | Past champions with runner-ups |
| `tournament_entrants` | "Is X playing?" — from Pinnacle outrights (~16 per tournament) |
| `match_prediction` | Today's matches, win probs, handicaps |

## System Prompt Rules

- **SPW vs hold %:** Say "serve points won %" or "SPW", never "hold %" for point-level stats. 68% SPW = big server (elite bar).
- **Big servers:** Opponents with SPW ≥ 68% on that surface. Say "68%+ of service points won", not "hold serve 68%".
- **Tournament winner:** Use player_record_at_tournament, player_recent_form, tournament_past_winners — NOT match_prediction.
- **"Is X playing?":** Use tournament_entrants (Pinnacle outrights).
- **British currency:** "quid" not "bucks", "£" not "$".
- **Retired players:** Don't reference Federer/Nadal/Murray as current. Be explicit: "beat Federer in 2019 when he was still active".
- **No model mentions:** Don't say "model", "fair odds model", "algorithm".
- **Text before tools:** Always output a short sentence before calling tools.

## Data Filters

- Juniors, doubles, qualifying, wheelchair: filtered via `isMainTour()` and `JUNK_TOUR_KEYWORDS`.
- Challenger: filtered from match_prediction; included in historical tools.
- Qualifying rounds: filtered from match_prediction (tour names with "QUALIF").

## Env

- `GROQ_API_KEY` — required
- `GROQ_MODEL` — optional, default `moonshotai/kimi-k2-instruct`
- `SUPABASE_SERVICE_ROLE_KEY` — for tools
- `NEXT_PUBLIC_SUPABASE_URL` — for tools

## Visibility

- **Localhost:** Chat widget visible.
- **Production:** Hidden (`process.env.NODE_ENV === "production" return null` in ChatWidget).

## Outright Setup

- Table: `tournament_outright_snapshot` — see `RUN-THIS-FOR-OUTRIGHTS.sql`
- Populated by `pinnacle-scrape-odds.py` (runs in daily pipeline)
- Pinnacle lists ~16 top favorites per tournament + "The Field"; we store the named players only.
