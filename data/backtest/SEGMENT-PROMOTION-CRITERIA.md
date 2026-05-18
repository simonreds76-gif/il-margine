# Segment Promotion Criteria

Research segments do not become active policy because they look good in one aggregate table. A segment needs written evidence before it can move into a scheduled or public lane.

## Grand Slam ML

Candidate rows use the same staking convention as `policy-profile-backtest-2022-2025.txt`: value-tiered stakes where `5-10% = 0.5u`, `10-15% = 1u`, `15-20% = 1.5u`, and `20%+ = 2u`.

A Grand Slam ML segment is evidence-positive only if all conditions hold:

- `bets >= 150`
- `tier_roi_pct >= +5%`
- `positive_years >= 3` across the tested year window
- latest tested year has `tier_roi_pct >= 0%`

Until those gates pass, the segment can be displayed as evidence on the monitor, but it must not be added to a new production rule or public output.

## Tennis Handicap Research

Handicap segments must be evaluated separately from ML. A profitable ML segment does not imply a profitable handicap segment.

Minimum shadow-promotion evidence for a handicap segment:

- `settled >= 80` rows for the exact orientation/line/surface gate
- hard-surface subset ROI `>= +5%` over at least `40` settled rows
- average CLV `>= 0`
- no sub-segment with `n >= 20` and ROI `<= -10%`
- two consecutive months without rolling-20 regression

These criteria are research gates only. Passing them authorises a follow-up implementation plan, not direct public publication.
