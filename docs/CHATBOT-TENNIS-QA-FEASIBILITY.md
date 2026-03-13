# Public tennis Q&A chatbot – feasibility and design

**Goal:** A chatbot on the website that answers questions like:
- How did Tsitsipas do at [tournament] in past years? What’s his best result there?
- What’s Rune’s H2H vs Cobolli?
- What was the highest-price winner we had in last year’s Indian Wells matches?

---

## Feasibility: yes, with the data you have

| Question type | Data source | Notes |
|--------------|-------------|--------|
| **H2H (e.g. Rune vs Cobolli)** | Supabase `player_h2h` + `oncourt_players` | Resolve names → OnCourt IDs (player_a_id < player_b_id), query by surface or all surfaces. Already in weekly pipeline. |
| **Player at tournament / best result** | Supabase `oncourt_games` + `oncourt_tours` + `oncourt_players` | Games have winner_id, loser_id, tour_id, round_id, date. Tours have name (e.g. "Indian Wells"). "How did X do" = games where X is winner or loser and tour name matches; "best result" = best round (need round_id → label, or use Sackmann for round names F/SF/QF/R16). |
| **Tournament-level “our” stats (e.g. highest price winner at Indian Wells)** | Backtest results CSVs or a DB | `backtest-results-20XX.csv` have tournament, date, player1, player2, actual_winner, our_odds, pinnacle_odds_loser. Winner’s decimal odds = our_odds if actual_winner==player1 else pinnacle_odds_loser. Filter by tournament (e.g. Indian Wells) and year → max odds among winners. Needs an API that reads these files or a table populated from them. |
| **Richer tournament history (seeds, qualifiers, narrative)** | Sackmann + tournament historical stats (once built) | After `build-tournament-historical-stats.py` and optional Phase 3, you can add answers like "qualifiers at this tournament", "seed 1–2 never made the final here". |

So: **H2H and player-at-tournament are already supportable from Supabase.** "Highest price winner at Indian Wells" (and similar "our" model/odds questions) needs backtest results exposed via an API or DB.

---

## Two ways to build it

### 1. Structured API + simple NL (recommended to start)

- **Backend:** One API (e.g. `/api/tennis-qa`) that accepts **intent + parameters** (e.g. `intent=h2h`, `player_a=Rune`, `player_b=Cobolli`; or `intent=player_tournament_history`, `player=Tsitsipas`, `tournament=Indian Wells`; or `intent=highest_odds_winner`, `tournament=Indian Wells`, `year=2024`).
- **Intent types you can support from day one:**
  - `h2h` – H2H for two players (Supabase).
  - `player_tournament_history` – List of results (W/L, round, year) at a tournament (Supabase games/tours).
  - `player_best_result` – Best round reached at a tournament (same data).
  - `highest_odds_winner` – Match with highest winner decimal odds at tournament in year (backtest).
  - Optional later: `tournament_fav_dog_roi`, `qualifiers_at_tournament`, etc. (from tournament historical stats).
- **Frontend:** Chat UI that either (a) sends a **natural-language** string to a small parser (keyword/regex or a small LLM) that maps to intent + entities and calls the API, or (b) uses **quick questions / dropdowns** (e.g. "H2H", "Player at tournament", "Our stats" + autocomplete for players/tournaments). Answers are **deterministic** from your data (no hallucination).
- **Pros:** Reliable, cheap, no LLM required for answers. **Cons:** Only answers the question types you implement.

### 2. RAG-style chatbot (LLM + retrieval)

- User asks in free form. You **retrieve** relevant rows (e.g. H2H table, games for player X at tournament Y, backtest rows for Indian Wells). You pass **retrieved context** + user question to an LLM and ask it to answer in one short paragraph.
- **Pros:** More flexible phrasing, one model for many question types. **Cons:** Cost (LLM per request), need rate limiting and abuse controls; must design retrieval so the model only answers from your data (grounding) and you guard against hallucination.
- Best used **after** you have the structured API and a clear set of supported question types, so retrieval can target the same data.

---

## What to add technically

1. **Player and tournament resolution**
   - **Names → OnCourt IDs:** Use `oncourt_players` (fuzzy or autocomplete) so "Tsitsipas", "Stefanos Tsitsipas" resolve to one id. You may already have this for the fair-odds page.
   - **Tournament name → keys:** Normalize tournament names (e.g. "Indian Wells", "Indian Wells Masters") to the same key or tour_id list so "Indian Wells" hits the right tours in `oncourt_tours` and, for backtest, the right rows in backtest-results (e.g. tournament column or tournament_key).

2. **Backtest results queryable**
   - Either:
     - **Option A:** Load `backtest-results-20XX.csv` into a Supabase table (e.g. `backtest_results`) and query by tournament and year; or
     - **Option B:** Server-side only: read CSVs in an API route (or a small Node/Python service), filter by tournament + year, return highest-odds winner and any other stats you want. No need to expose raw CSVs to the client.

3. **Round labels for “best result”**
   - OnCourt has `round_id` (integer). You need a mapping round_id → "Final", "Semifinal", "R16", etc., either from an existing OnCourt table (e.g. `ep_atp` if it holds round names) or a small static map. Alternatively, for "best result" you could query Sackmann (which has round names) and join by player + tournament + year if you already have that pipeline.

4. **Public API and safety**
   - **Rate limit:** Per IP or per session (e.g. 20–50 requests/minute) so the chatbot can’t be abused.
   - **Timeout and limits:** Cap query size (e.g. last N years, max 500 rows) so one user can’t drag down the DB.
   - **Caching:** Cache common answers (e.g. "Rune vs Cobolli H2H") for a few hours to reduce load.
   - **Scope:** Only return aggregated or precomputed answers, not raw dumps of PII or full tables.

---

## Suggested order of work

1. **Phase 1 – Structured API**
   - Implement 3–5 intents: `h2h`, `player_tournament_history`, `player_best_result`, `highest_odds_winner` (and optionally one tournament-stats intent).
   - Backend: Supabase for H2H and games/tours; backtest CSVs or a `backtest_results` table for "highest price winner" and similar.
   - Add player name resolution and tournament name normalization (reuse or extend existing logic).

2. **Phase 2 – Simple chat UI**
   - Chat interface that calls the API: either quick-select (dropdown + autocomplete) or a single text box that you parse (keywords/regex or a very small model) into intent + entities.
   - Show answers as short, deterministic text (e.g. "Rune leads Cobolli 2–0 (1–0 on hard)." / "Tsitsipas at Indian Wells: 2023 R16, 2024 SF, best result SF." / "Last year’s Indian Wells highest price winner: [name] at [odds].").

3. **Phase 3 – Optional RAG**
   - If you want free-form questions, add retrieval over the same data (and tournament historical stats when ready), then an LLM step that answers from retrieved context only. Keep rate limits and a clear disclaimer that answers are from historical data.

4. **Use “more data” as you build it**
   - Tournament historical stats (fav/dog ROI, seed/entry, segment ROI) can feed new intents (e.g. "How do favs do at this tournament?"). Same for Sackmann-based narratives. Add them as new question types to the structured API first; then expose via chat.

---

## Summary

- **Yes,** you can run a public tennis Q&A chatbot using existing data (Supabase for H2H and player–tournament history; backtest results for "our" odds questions; later, tournament stats and Sackmann for richer narratives).
- **Best starting point:** Structured API with a few intents (H2H, player at tournament, best result, highest price winner at tournament/year), plus a simple chat UI that calls it. Keep answers deterministic and data-bound.
- **Then** add more question types and, if you want, an LLM-backed layer with retrieval and rate limiting.
