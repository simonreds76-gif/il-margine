# Corners V0 Venue Diagnostic

Generated: 2026-04-25T19:42:49+00:00

Corners v0 already uses pooled opponent corner concession, not venue-specific opponent concession.
This report checks whether the blocked Bundesliga/La Liga segments still show a home/away component bias.

## Last-90 Component Split

| League | N | Current total MAE | V0 total MAE | Delta | Current home MAE | V0 home MAE | Home lambda gap | Current away MAE | V0 away MAE | Away lambda gap | Worse share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ALL | 570 | 2.6663 | 2.6309 | -0.0354 | 2.1975 | 2.1989 | -0.0775 | 1.9674 | 2.0773 | 0.6242 | 0.4965 |
| bundesliga | 111 | 2.5871 | 2.6594 | 0.0723 | 2.1426 | 2.2073 | -0.2155 | 1.8236 | 2.0076 | 0.5388 | 0.5586 |
| epl | 112 | 2.6609 | 2.5618 | -0.099 | 2.0621 | 2.1065 | -0.0398 | 2.2459 | 2.373 | 0.7195 | 0.4643 |
| la-liga | 121 | 2.7026 | 2.7749 | 0.0723 | 2.3163 | 2.2887 | -0.3106 | 1.8605 | 1.9673 | 0.4351 | 0.5868 |
| ligue-1 | 106 | 2.6321 | 2.4323 | -0.1998 | 2.2066 | 2.2273 | -0.1646 | 1.8528 | 1.852 | 0.4588 | 0.3774 |
| serie-a | 120 | 2.7383 | 2.6993 | -0.039 | 2.247 | 2.1616 | 0.3267 | 2.0493 | 2.1759 | 0.9509 | 0.4833 |

## Read

- If home lambda gap is strongly positive and home MAE regresses, corners may share the team-shots home overshoot shape.
- If not, Bundesliga/La Liga corners need a corners-specific fix rather than the team-shots pooled-opponent defence patch.
- Worst rows written to `data/football-form/corners-v0-venue-worst.csv`.

