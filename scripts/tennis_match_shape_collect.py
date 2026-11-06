"""Bounded ATP-only fallback inside the existing refresh. No new schedule.

The shared ATP/WTA collector's earliest twelve events can all be WTA. Only when
it provides no eligible ATP games contract, fetch at most four ATP events using
the same public Grosvenor source. No Odds-API credits or betting alerts.
"""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import time
import requests
from tennis_grosvenor import BASE, PARAMS, eligible
from tennis_match_shape import RELATIVE, parse_receipt, refresh as model_refresh, digest, immutable, read, atomic
from tennis_match_shape_prepare import prepare, readiness


from tennis_match_shape_quotes import collect
from tennis_match_shape_results import refresh_with_results

def refresh(root, *args, **kwargs):
    return refresh_with_results(root, *args, **kwargs)


def capture_shared(root,receipt):
    out=root/RELATIVE
    if not (out/'registration.json').exists():return {}
    prepared=prepare(root)
    if not prepared['ready']:
        atomic(out/'capture-status.json',dict(state='INPUT_REFRESH_REQUIRED',reason=prepared['reason'],captured=0,checked_at=datetime.now(timezone.utc).isoformat()))
        return refresh(root,settle_only=True)
    clock=datetime.now(timezone.utc)
    if prepared.get('refreshed') or not parse_receipt(receipt,clock):
        receipt=collect()
    path=out/'quote-evidence'/(digest(receipt)+'.json')
    if not path.exists():immutable(path,receipt)
    return refresh(root,receipt=receipt)


def refresh_saved(root):
    """No network. Reconcile after forecast generation and settle on every upload."""
    out=root/RELATIVE
    if not (out/'registration.json').exists():return {}
    clock=datetime.now(timezone.utc)
    current=readiness(root,clock)
    if not current['ready']:
        atomic(out/'capture-status.json',dict(state='INPUT_REFRESH_REQUIRED',reason=current['reason'],captured=0,checked_at=clock.isoformat()))
        return refresh(root,clock,settle_only=True)
    paths=sorted((out/'quote-evidence').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:4]
    for path in paths:
        if path.stat().st_size>32*1024*1024:continue
        receipt=read(path)
        if parse_receipt(receipt,clock):return refresh(root,clock,receipt=receipt)
    return refresh(root,clock,settle_only=True)
