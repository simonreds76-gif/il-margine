# Tennis integrity and monitor reconciliation

30 September audit of the running local pipeline and existing saved prices.
No probability weights, stake rules or selection thresholds changed.

* Strict's last selection date is 22 August. This is a hard-court Masters
  policy, not a generic ATP model. The 30 September run evaluated the current
  board and returned zero eligible Strict selections. Do not label it broken
  merely because Beijing/Tokyo ATP 500 matches are outside that scope.
* The 29 September scheduled morning run succeeded. The 30 September core
  refresh completed; its outer run failed later during Atlas publication
  because another deployment changed production. The last archive was retained
  and publication was subsequently recovered. Retain that failure in ops history.
* Six old unresolved archive entries (two Strict, four Volume) have no completed
  matching pair in the local archive within 14 days. Keep them unresolved,
  separated from recent pending observations. Do not silently void them.
* Most aces has 104 quarantined observations. These remain quarantined.
* Bet365 supplied 1,148 one-sided ace/DF milestone rows, with raw samples
  showing over prices only. This is legitimate market structure. Model EV can
  use an offered milestone price. No-vig market probabilities require two
  sides; do not invent the missing side. The old structural-error health flag
  was wrong and suppressed the health summary's actionable shadow count.
  Freshness, kickoff, matching and model selection guards remain in force.
* Shared qualifier handling includes generic ATP 250/500 qualifying, including
  Beijing. Current captures have no upcoming qualifying quotes. Regression
  coverage checks tournament identity, fallback discovery and post-start exclusion.
* Invalidated hard calibration remains explicitly off by default even though
  obsolete environment values exist. CPI is paused in scheduled PowerShell;
  this change also gates the direct Python daily runner instead of always
  appending the unused experiment. Historical files are retained.

Challenger reconciliation uses the existing logical-bet deduplicator: 83
settled bets, 36 wins, 47 losses, -6.239 hypothetical units, -7.5169% ROI.
One duplicated observation is not a second bet. Clay: 40 bets, -3.811u.
Hard: 43 bets, -2.428u. Both are exposed, small samples; neither justifies
choosing a profitable-looking filter. Mean predicted probability 50.90%
versus observed 43.37%, Brier 0.22873, is diagnostic, not a calibration proof.
Existing 46 accepted pre-match price comparisons are incomplete and roughly
flat. Keep real stakes at zero; no newly validated profitable fix established.

The monitor now receives a compact integrity section in its existing snapshot,
with current refresh/capture times and per-lane unresolved/overdue counts.
Raw data and quarantined histories are not deleted or relabelled as forward ROI.
