"""Operational suspension only. Does not alter models, prices or past forecasts."""
import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / 'config/model-monitor-lifecycle.json'

def most_aces_suspended():
    if not CONFIG.exists():
        return False
    return json.loads(CONFIG.read_text(encoding='utf8')).get('most_aces', {}).get('status') == 'SUSPENDED_NO_PRICES'
