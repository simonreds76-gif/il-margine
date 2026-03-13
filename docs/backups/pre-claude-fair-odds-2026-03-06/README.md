# Pre-Claude Fair Odds Backup — 2026-03-06

Backup of the fair-odds model files **before** applying Claude's calibration changes.

## Files

| Backup | Restore to |
|--------|------------|
| `oncourt-compute-fair-odds.py` | `scripts/oncourt-compute-fair-odds.py` |
| `tennis_prob.py` | `src/lib/tennis_prob.py` |
| `route.ts` | `src/app/api/fair-odds/route.ts` |
| `page.tsx` | `src/app/fair-odds/page.tsx` |

## Restore (PowerShell)

```powershell
cd c:\Users\44746\Downloads\il-margine
Copy-Item "docs/backups/pre-claude-fair-odds-2026-03-06/oncourt-compute-fair-odds.py" "scripts/"
Copy-Item "docs/backups/pre-claude-fair-odds-2026-03-06/tennis_prob.py" "src/lib/"
Copy-Item "docs/backups/pre-claude-fair-odds-2026-03-06/route.ts" "src/app/api/fair-odds/"
Copy-Item "docs/backups/pre-claude-fair-odds-2026-03-06/page.tsx" "src/app/fair-odds/"
```

Or use git: `git checkout 6c4057f -- scripts/oncourt-compute-fair-odds.py src/lib/tennis_prob.py src/app/api/fair-odds/route.ts src/app/fair-odds/page.tsx`
