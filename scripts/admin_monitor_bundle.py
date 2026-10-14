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
    return {'admin_files':files,'admin_manifest':manifest,'admin_bundle_bytes':total}
