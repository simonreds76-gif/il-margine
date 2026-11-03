"""Additive research-only provider lookup. Existing live registry is untouched."""
from football_identity import key, read, resolve

SUPPLEMENT = 'data/football-identity/reep-research.json.gz'
REVIEWS = 'config/football-identity-reviewed.json'


def lookup(root, player_id, provider, namespace, existing_id=None):
    registry = read(root / SUPPLEMENT, {})
    result = resolve(registry, 'fotmob', 'person', player_id, provider, namespace,
                     existing_target_id=existing_id)
    reviewed = read(root / REVIEWS, {}).get('players', {}).get(str(player_id), {})
    bridge = reviewed.get('targets', {}).get(key(provider, namespace, ''))
    if not bridge:
        return result
    target = str(bridge['id'])
    if (existing_id is not None and str(existing_id) != target or
            result.get('id') is not None and result['id'] != target or
            result['status'] in ('target_collision', 'ambiguous_source', 'ambiguous_target',
                                 'withdrawn_or_inactive_source', 'existing_id_conflict')):
        return {'status': 'reviewed_id_conflict'}
    return {'status': 'reviewed_identity', 'id': target, 'evidence': bridge['evidence'],
            'reviewed_at': reviewed['reviewed_at']}
