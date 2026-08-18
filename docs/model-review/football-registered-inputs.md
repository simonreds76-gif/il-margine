# Registered football model inputs

Team Shots v4 and Corners v3 must use the canonical rolling-form table built
from the tracked Football-Data spine plus the tracked Understat xG overlay:

```powershell
python scripts/build-football-form-layer.py `
  --xg-source data/team-shots/understat/all-understat-matches.csv
```

The registered lock files contain the expected SHA-256 of
`data/football-form/team-rolling-form.csv`. Both fold scripts fail closed when
the file is stale, rebuilt from a different source, or otherwise mismatched.
This protects the frozen reports from silently running with an empty xG layer.

To register a genuinely new input window, rebuild the table, re-run every
walk-forward fold, review the resulting model-risk report, and create a new
experiment version. Do not overwrite the existing lock hash merely to make a
failed check pass.
