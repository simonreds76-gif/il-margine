# Roger Chatbot – Test Message for Codex

**Context:** Roger ("Ask Margine") is Il Margine's tennis analyst chatbot. It answers ATP tennis questions using 18 tools that query Supabase (match data, player stats, H2H, tournament history, etc.). We recently fixed a bug in the vs-lefties surface mapping (tours with id > 10000 were defaulting to "Hard"). We need to verify the chatbot works correctly and uses the right tools.

**Query budget:** ~1000 free queries. Use them wisely — each question = 1+ API calls (often 2–4 due to search + tool chains). Aim for **~50–80 test questions** to leave headroom for follow-ups and retests.

---

## What to Test

### 1. Correct tool triggers
Does Roger call the right tool for each question type? Wrong tool = wrong answer or no answer.

### 2. Data accuracy
Are the numbers correct? Especially:
- **Vs-lefties surface breakdown** — should show Hard, Clay, Grass, I.hard, Carpet where applicable (not everything as Hard).
- **H2H** — matches our data.
- **Tournament records** — W-L at Indian Wells, Monte Carlo, etc.
- **Today's matches** — win probs, expected games (when matches exist).

### 3. Edge cases
- Typos (e.g. "Maroszan" → Marozsan)
- Tournament aliases ("Roland Garros" → French Open, "Monte-Carlo" → Monte Carlo)
- Retired players (Federer, Nadal, Murray) — don't treat as current; historical questions can list them
- "Who wins Indian Wells?" → use tournament history + form, NOT today's match list
- "Is X playing?" → use tournament_entrants (Pinnacle outrights)

### 4. Formatting & style
- British currency: "quid" not "bucks", "£" not "$"
- SPW wording: "68%+ of service points won" not "hold serve 68%"
- No mention of "model", "fair odds model", "algorithm"
- Short, punchy answers (not waffle)

---

## Focused Test Set (~50 questions)

Use these in order. If something fails, note it and move on — don't burn queries retrying.

### Player search & basics (5)
1. `Rune vs Cobolli H2H` — should call search_player ×2, head_to_head
2. `How does Van de Zandschulp do against lefties?` — search_player, player_record_vs_lefties; **check surface breakdown** (Hard, Clay, I.hard, Grass, Carpet — not all Hard)
3. `Tsitsipas record at Indian Wells` — search_player, player_record_at_tournament
4. `Dimitrov at Monte Carlo` — should resolve "Monte Carlo" / "Monte-Carlo"
5. `Maroszan` (typo for Marozsan) — should still find the player

### H2H & match context (5)
6. `Sinner vs Alcaraz head to head`
7. `Who wins Borges vs Nava?` — should give win prob, surface, form, H2H if relevant
8. `Paul vs a leftie — how does he do?` — player_record_vs_lefties
9. `How does Fritz do against big servers?` — player_record_vs_big_server (SPW ≥ 68%)
10. `Sinner's best surface?` — player_record_by_surface

### Tournament & outrights (5)
11. `Who's won Indian Wells the most?` — tournament_past_winners (historical, can include retired)
12. `Who wins Indian Wells?` — should use player_record_at_tournament, form, past winners — NOT match_prediction
13. `Is Sinner in the Indian Wells draw?` — tournament_entrants
14. `How do favourites do at Indian Wells?` — tournament_fav_dog_stats
15. `Court speed at Madrid?` — court_pace

### Today's matches (3)
16. `What are today's matches?` — match_prediction; should group by tournament, highlight 3–5 interesting ones
17. `Today's picks` — match_prediction + analysis
18. `Who wins Tsitsipas vs Korda?` (if they're playing today) — match_prediction + focused take

### Edge cases (5)
19. `Who's won Wimbledon the most?` — historical, include Federer/Djokovic etc.
20. `Active players with best record at Rome?` — tournament_past_winners; note who's retired if relevant
21. `Is Merida in the French Open draw?` (in March) — should say draw not known until May/June
22. `Auger Aliassime` (spacing variant) — should find FAA
23. `Where does Djokovic have the best record?` — player_record_by_surface + player_record_at_tournament for likely venues

### Formatting & style (spot-check 2–3)
24. Ask for a tip — response should use "quid" not "bucks"
25. Ask about big servers — should say "service points won" or "SPW", not "hold serve"
26. Should never say "our model" or "fair odds algorithm"

---

## What to Report

For each failure, note:
- **Question** (exact text)
- **Expected:** which tool(s), or what the answer should look like
- **Actual:** what Roger said, or which tool was called (if you can see it)
- **Issue:** wrong tool, wrong data, hallucination, formatting, etc.

### Priority checks
1. **Vs-lefties surface breakdown** — Van de Zandschulp (question 2) and any right-hander vs lefties. Surfaces should be varied (Hard, Clay, I.hard, Grass, Carpet), not all "Hard".
2. **Tournament winner vs today's matches** — "Who wins Indian Wells?" must NOT just list today's matches.
3. **Tool chaining** — search_player should run first for player-based questions.

---

## How to Access Roger

- **Local:** Run `npm run dev`, open site, click "Ask Margine" in nav or use ChatPrompt on homepage / tennis-tips.
- **Preview:** If deployed to Vercel preview from `golden-with-speed-insights`, use that URL.
- **Production:** Roger is live. Test on local, preview, or production.

---

## Summary for Codex

**Task:** Test Roger with ~50 focused questions. Verify correct tool triggers, data accuracy (especially vs-lefties surface fix), and edge cases. Stay under ~100–150 total API calls to preserve query budget.

**Deliverable:** A short report: which questions passed, which failed, and any bugs (wrong tool, wrong data, formatting). Priority: vs-lefties surface breakdown, tournament-winner logic, and search/tool chaining.
