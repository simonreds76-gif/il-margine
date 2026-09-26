"""Reviewed source aliases preserve already-published player URLs and history."""

# First present in the odds feed on 2026-09-25; matched to the existing
# OnCourt identities through full-name, fixture and result reconciliation.
PUBLISHED_ALIASES = {
    '14507': '45197',  # Jie Cui
    '60351': '97973',  # Yi Zhou
}


def source_player_id(source_id, oncourt_id):
    source_id, oncourt_id = str(source_id), str(oncourt_id)
    expected = PUBLISHED_ALIASES.get(source_id)
    if expected is not None:
        if oncourt_id != expected:
            raise ValueError('Reviewed player alias disagrees with result identity')
        return 'oc-' + expected
    return 'vbt-' + source_id
