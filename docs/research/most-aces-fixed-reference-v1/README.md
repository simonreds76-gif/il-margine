Frozen forward Most Aces gate comparison, registered 14 November 2026.

Uses existing Windows capture/settlement and private snapshot. No new alerts, schedules or model formula changes. Cloud weekly reporting consumes the existing private snapshot section tennis_most_aces_reference. Both arms and profit histories use the existing dynamic Monitor cards.

The active runtime includes admin_active_models.py from the production Monitor release, which is absent from this data branch. runtime-monitor.patch is the exact installed adapter diff for that module; preserve it when reconciling runtime scripts. Do not replace the active runtime with this older branch tree.

20 focused comparison tests, 12 existing Most Aces settlement tests, 7 capture tests and 5 snapshot tests pass. The broad weekly report suite has five pre-existing missing Match Shape fixtures errors on both the unchanged baseline and this branch. The new reporting section is isolated from failures and was additionally verified against the active runtime payload.

Historical exploratory replay is excluded; ROI remains undefined until genuine prospective bets settle. Count is primary; Direct is secondary. No automatic promotion.
