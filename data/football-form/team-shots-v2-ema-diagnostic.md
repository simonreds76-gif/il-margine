# Team-Shots V2 EMA Diagnostic

Generated: 2026-04-25T20:12:19+00:00
Latest form date: `2026-04-23`
Recent cutoff: `2026-01-23`

This is a diagnostic only. It does not promote a v3 model.

## Best Aggregate Weight By Source

| Source | Best weight | Current MAE | Candidate MAE | Improvement | Passing leagues at best weight | Blocked leagues at best weight |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| venue20 | 0.5 | 3.7321 | 3.6965 | 0.95% | `bundesliga, la-liga, ligue-1, serie-a` | `epl` |
| recent6 | 0.0 | 3.7321 | 3.7270 | 0.14% | `bundesliga, la-liga, ligue-1` | `epl, serie-a` |

## Read

- Blending v2 with the current 20-match venue EMA improves aggregate last-90 MAE and helps Serie A, but does not rescue EPL under the configured +0.5% count gate.
- Blending v2 with the short 6-match recent-form lambda is worse than v2, so it should not be promoted.
- Next useful work is not a blind v3 promotion; it is either a clean canonical EMA implementation followed by the same gate, or a separate EPL-specific diagnostic.

