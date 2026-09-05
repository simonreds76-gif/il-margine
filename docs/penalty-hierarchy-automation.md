# Penalty hierarchy review and manual control

The updated evidence workflow builds a review for all current clubs once merged into the effective default branch. A routine scan preserves every curated hierarchy, editorial note, verification date and public URL. The current default is **review mode**. No public hierarchy is changed simply because a backup scores a penalty.

## Local admin workflow

Sign in at `/admin`, open `/model-monitor/goalscorer#penalty-watchlist`, and choose **Open review controls**. Select a club to inspect the evidence, source links, observation times and availability uncertainty.

- **Save override and lock** writes the entered order, source citation and reason to the local repository. It also creates a persistent override and lock. Empty unverified backup slots are allowed; placeholders such as “TBC” are rejected.
- **Lock current order** prevents the automated engine from changing that club.
- **Unlock only** removes the lock but deliberately keeps any manual override active.
- **Release override and lock** allows subsequent supported automated proposals. It retains the currently filed order until stronger evidence qualifies.
- **Revert this transaction and lock** restores the prior hierarchy and curated context, records the reversal and protects it from immediate reapplication. The original evidence verification date remains intact; the public change date records the actual reversal. A revert that would overwrite a newer entry or control decision is rejected.

Every write requires a reason, current control revision and exact entry hash. Reload on conflict; do not resubmit stale values. Manual source links are the editor's attestation and must support the names and current club membership. These controls are authenticated, same-origin and local only. A hosted/serverless process returns an explicit unavailable response rather than pretending an ephemeral file write is durable. Deployment remains a separate step; include the hierarchy, control store and transaction journals together in the reviewed repository change.

## Automatic evidence rule

An opt-in automatic change requires one already ranked backup to take penalties in **at least two distinct completed competitive fixtures** within 45 days, after the last editorial hierarchy review. Both events must be in the current season, have exact match and source-event identifiers, HTTPS source links, and actual event-time evidence that the current primary was on the pitch. Repeated attempts in one match count as one fixture. Conversion success is not used as a duty signal.

The current squad audit and latest complete event scan must each be at most 48 hours old. All filed players must match the current squad without ambiguity. Squad membership is not a claim about current injury availability. A conditional/disputed order, contrary taker, provider correction, old manual ticket decision, missing event context, source failure, manual override or lock keeps the club in review.

The FotMob collector records completed-match starting-lineup and player substitution/dismissal evidence. It does not equate a predicted or pre-match starter with event-time availability. Same-minute substitutions or red cards and missing explicit timelines remain unknown. Shootouts are excluded. Corrections retain the previous evidence version and block promotion.

## Commands and scheduled operation

```powershell
python scripts/club-penalty-hierarchy-review.py --summary
python scripts/club-penalty-hierarchy-review.py --inspect
python scripts/club-penalty-hierarchy-review.py --apply-safe --summary
```

The existing daily/weekly GitHub evidence workflow scans penalties, checks squads, runs this engine, validates public hierarchy data and retains its existing commit process. `PENALTY_AUTO_APPLY=true` as a repository Actions variable opts that job into the strict apply rule. Leaving the variable unset keeps review mode. The automatic mode must remain unset until this workflow is merged into the effective default branch and the shared controls are reconciled with local manual overrides. A local override protects the local engine immediately; a hosted job only sees controls committed to its checked-out branch.

The persistent files are:

- `data/goalscorer/club-penalty-hierarchy-review.json`: current club decisions and source health.
- `data/goalscorer/club-penalty-event-evidence.json`: recent observations, retained between short daily scans.
- `data/goalscorer/club-penalty-controls.json`: control revision, overrides, locks and audit summaries. Created on the first manual or approved automatic change.
- `data/goalscorer/penalty-transactions/<id>.json`: durable before/after club snapshots, provenance and transaction status. These are required for reliable reverts and recovery.

The legacy log-based hierarchy seeder now refuses to overwrite curated data or active controls. Its explicit replacement flag only allows replacement of an unreviewed generated seed. Current public data remains authoritative; do not use seed generation as a refresh command.

## API

Authenticated `GET /api/admin/penalty-hierarchy` returns `{ok, report}` with `revision`, `clubs`, source health, proposed changes and recent audit records. Each club has `id`, `current`, `entry_hash`, `status`, `confidence`, `reasons`, `evidence` and `control`.

Authenticated local same-origin `POST` accepts:

```json
{
  "action": "override",
  "id": "epl|Example FC",
  "expected_revision": 0,
  "expected_entry_hash": "<hash from GET>",
  "reason": "Verified current club and penalty-duty evidence",
  "hierarchy": {"primary": "First Player", "secondary": "Second Player", "tertiary": ""},
  "sources": [{"label": "Club report", "url": "https://example.org/report"}]
}
```

Other actions are `lock`, `unlock`, `release` and `revert`; revert also needs `transaction_id`. HTTP 409 means a stale revision, changed entry or recovery requirement. HTTP 503 means no durable local worker was available; no successful save is claimed. The existing ticket-resolution POST also now requires the admin session and same origin.

## Recovery

Writes use an exclusive lock and a journal written before the public data changes. An interrupted transaction blocks further writes and inspection until resolved. Stop all writers and, only after confirming that its recorded process is no longer running, remove an abandoned `.club-penalty-writer.lock`. Then run:

```powershell
python scripts/club-penalty-hierarchy-review.py --recover
```

Recovery completes the recorded change only if the hierarchy and control store still match known before/after hashes. It refuses to overwrite intervening edits. Journals are not deleted, and reverting creates another audit record.
