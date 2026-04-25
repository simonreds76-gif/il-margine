# Corners Home-Correction Diagnostic

Generated: 2026-04-25T20:12:20+00:00
Latest form date: `2026-04-23`
Recent cutoff: `2026-01-23`

This is diagnostic only. It does not change corners publication.

## Derived Home Shifts

| League | Shift |
| --- | ---: |
| bundesliga | 0.4801 |
| epl | 0.5440 |
| la-liga | 0.6445 |
| ligue-1 | 0.5110 |
| serie-a | 0.5285 |

## Best Reads

- Symmetric home/away correction has no effect on total-corners O/U because the home addition is cancelled by the away subtraction.
- One-sided home premium worsens Bundesliga and La Liga, the exact leagues we need to rescue.
- The next corners test should target total-corners calibration or pressure, not home/away redistribution.

## Last-90 Candidate MAE

| Mode | Scale | Current ALL | Candidate ALL | Bundesliga | La Liga |
| --- | ---: | ---: | ---: | ---: | ---: |
| symmetric | 0.00 | 2.6663 | 2.6309 | 2.6594 | 2.7749 |
| symmetric | 0.25 | 2.6663 | 2.6309 | 2.6594 | 2.7749 |
| symmetric | 0.50 | 2.6663 | 2.6309 | 2.6594 | 2.7749 |
| symmetric | 0.75 | 2.6663 | 2.6309 | 2.6594 | 2.7749 |
| symmetric | 1.00 | 2.6663 | 2.6309 | 2.6594 | 2.7749 |
| home_only | 0.00 | 2.6663 | 2.6309 | 2.6594 | 2.7749 |
| home_only | 0.25 | 2.6663 | 2.6395 | 2.6694 | 2.8104 |
| home_only | 0.50 | 2.6663 | 2.6521 | 2.6854 | 2.8464 |
| home_only | 0.75 | 2.6663 | 2.6710 | 2.7089 | 2.8865 |
| home_only | 1.00 | 2.6663 | 2.6930 | 2.7364 | 2.9278 |
