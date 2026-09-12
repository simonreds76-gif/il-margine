# Team Shots v4 selection-rule feasibility

Audit of the saved 12 September 18:39 UTC candidate board, evaluated at 19:09 UTC. These are historical board estimates, not fresh betting prices or newly issued selections.

The locked configuration combines a 3% minimum expected return, 18% model weight in a logit blend, and a 12-percentage-point cap on raw model-versus-market disagreement during matchdays 4–6. There are 100 candidate rows, 96 subject to this cap.

For each affected row, let m be its market fair probability, o its decimal odds, w=0.18 and c=0.12. Because the logit blend is monotone, the maximum allowed edge is:

`o * sigmoid(w * logit(min(1-epsilon, m+c)) + (1-w) * logit(m)) - 1`

Across all 96 affected rows, **none can reach the required 3%** while obeying the gap cap. The largest possible allowed edge is approximately 2.106%. This is a statement about these quoted prices and parameters, not mathematical impossibility for every possible price.

Five board rows exceed 3% using their actual raw estimates but fail the raw-gap cap:

| Fixture date | Selection | Archived odds | Model-estimated return | Raw probability gap |
|---|---|---:|---:|---:|
| 12 September | Real Madrid under 20.5 | 1.800 | +8.66% | 27.81 points |
| 13 September | Celta under 13.5 | 1.800 | +4.95% | 19.80 points |
| 13 September | Barcelona under 19.5 | 1.909 | +11.85% | 33.34 points |
| 13 September | Levante over 9.5 | 2.000 | +4.35% | 41.63 points |
| 13 September | PSG under 19.5 | 1.833 | +8.73% | 28.56 points |

All five have team/opponent effective history counts of 20; insufficient history is not their blocker. They span four fixtures; these are not five independent match outcomes. Calculated return is a model estimate, not measured ROI.

The gate now reports EARLY_RULE_COMBINATION_BLOCKS_PRICED_LINES with the affected count, feasible count, edge ceiling and actual configuration. It requests operational review when no eligible candidates exist and the entire affected set is infeasible. Thirteen gate tests passed, including infeasible and feasible configurations. This diagnostic does not relax model rules, route bets or retroactively add signals.

The prior explanation that these were simply ordinary non-qualifying opportunities was incomplete. The restrictive interaction between the gap guard, blend and bookmaker margin requires explicit validation as a combined selection policy. Removing the guard merely because five estimates look positive would not demonstrate profitability.
