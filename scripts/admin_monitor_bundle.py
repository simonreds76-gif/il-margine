"""Bounded private Admin transport. Does not calculate, settle or select bets."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

def build_admin_bundle(root: Path) -> dict:
    catalog = json.loads((root / 'config/admin-monitor-catalog.json').read_text(encoding='utf-8-sig'))
    files, manifest = {}, []
    total = 0
    for view in catalog:
        target = (root / view['file']).resolve()
        entry = dict(view)
        try:
            if not target.is_relative_to(root.resolve()):
                raise ValueError('outside source root')
            if 'full-refresh-v1/' in view['file'] and (root / 'data/tennis-props/shadow/full-refresh-v1/upload-approval-pending.json').exists():
                raise ValueError('source upload approval pending')
            before = target.stat()
            if before.st_size > 4 * 1024 * 1024 or total + before.st_size > 12 * 1024 * 1024:
                raise ValueError('size limit exceeded')
            raw = target.read_bytes()
            after = target.stat()
            if (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
                raise ValueError('source changed during capture')
            content = raw.decode('utf-8-sig')
            if target.suffix == '.json': json.loads(content)
            files[view['id']] = content
            total += len(raw)
            entry.update(available=True, size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), modified_at=datetime.fromtimestamp(after.st_mtime,timezone.utc).isoformat())
        except (OSError,ValueError,UnicodeError) as error:
            entry.update(available=False,error=type(error).__name__)
        manifest.append(entry)
    # Historical display enrichment only. Source forecasts/ledgers remain exact
    # on disk; disclose both the original and transported hashes in the manifest.
    history_status = 'unavailable'
    try:
        from tennis_break_point_history import enrich_files
        updates = enrich_files(root, files)
        growth = sum(len(value.encode('utf-8')) - len(files[id].encode('utf-8')) for id, value in updates.items())
        if total + growth > 12 * 1024 * 1024 or any(len(v.encode('utf-8')) > 4 * 1024 * 1024 for v in updates.values()):
            raise ValueError('enriched bundle exceeds size limit')
        for id, content in updates.items():
            entry = next(e for e in manifest if e['id'] == id)
            raw = content.encode('utf-8')
            entry.update(source_sha256=entry['sha256'], sha256=hashlib.sha256(raw).hexdigest(),
                         size_bytes=len(raw), display_enrichment='tournament-break-points-v1')
            files[id] = content
        total += growth
        history_status = 'included' if updates else 'no_current_player_rows'
    except (OSError,ValueError,UnicodeError) as error:
        history_status = f'unavailable:{type(error).__name__}'
    return {'admin_files':files,'admin_manifest':manifest,'admin_bundle_bytes':total,
            'admin_break_point_history_status':history_status}
