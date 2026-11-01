"""Display-only native match history. Never write forecasts, odds or settlements."""
import csv
import io
import json
import math
import re
from datetime import date
from pathlib import Path

VERSION = "tournament-break-points-v1"
FIELDS = ("bpof", "bpw", "bpfaced", "bpsaved")


def count(value):
    try:
        n = float(value)
        return int(n) if math.isfinite(n) and n >= 0 and n.is_integer() else None
    except (ValueError, TypeError):
        return None


def identity(row, tour=""):
    return (str(row.get("tour") or tour).upper(), str(row.get("tour_id") or ""),
            str(row.get("player_id") or "").removeprefix("oc:"), str(row.get("date") or "")[:10])


def key(row):
    return tuple(str(row.get(k) or "") for k in ("tour_id", "winner_id", "loser_id", "round_id"))


def valid_counts(stat):
    values = {f"{p}_{f}": count(stat.get(f"{p}_{f}")) for p in ("w", "l") for f in FIELDS}
    if any(v is None for v in values.values()):
        return None
    for p, other in (("w", "l"), ("l", "w")):
        if not (values[f"{p}_bpof"] == values[f"{other}_bpfaced"]
                and values[f"{p}_bpw"] <= values[f"{p}_bpof"]
                and values[f"{p}_bpsaved"] <= values[f"{p}_bpfaced"]
                and values[f"{p}_bpw"] == values[f"{other}_bpfaced"] - values[f"{other}_bpsaved"]):
            return None
    return values


def histories(root: Path, requested: list[tuple]):
    """Read each tour once, retaining only exact editions/players before cutoff."""
    result = {}
    for tour in ("ATP", "WTA"):
        wanted = {(edition, player, cutoff) for t, edition, player, cutoff in requested
                  if t == tour and edition and player and re.fullmatch(r"\d{4}-\d{2}-\d{2}", cutoff)}
        if not wanted:
            continue
        editions = {x[0] for x in wanted}
        players = {x[1] for x in wanted}
        max_date = max(x[2] for x in wanted)
        folder = root / "data/oncourt"
        paths = [folder / f"{name}_{tour.lower()}.csv" for name in ("games", "stat", "players")]
        signatures = {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in paths}
        games, conflicts, stats, stat_conflicts = {}, set(), {}, set()
        with paths[0].open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("tour_id") not in editions or not players.intersection((row.get("winner_id"), row.get("loser_id"))):
                    continue
                try:
                    played = date.fromisoformat(row.get("date", "")[:10]).isoformat()
                except ValueError:
                    continue
                if played >= max_date or not re.search(r"\d+[-:]\d+", row.get("result", "")):
                    continue  # walkovers/byes are not played appearances
                row = dict(row, date=played)
                k = key(row)
                if k in games and games[k] != row:
                    conflicts.add(k)
                games[k] = row
        with paths[1].open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                k = key(row)
                if k not in games:
                    continue
                values = {f"{p}_{f}": row.get(f"{p}_{f}") for p in ("w", "l") for f in FIELDS}
                if k in stats and stats[k] != values:
                    stat_conflicts.add(k)
                stats[k] = values
        opponent_ids = {r[p] for r in games.values() for p in ("winner_id", "loser_id")}
        with paths[2].open(encoding="utf-8-sig", newline="") as stream:
            names = {r["id"]: r["name"] for r in csv.DictReader(stream) if r["id"] in opponent_ids}
        if any((p.stat().st_size, p.stat().st_mtime_ns) != signatures[str(p)] for p in paths):
            raise ValueError("Native history changed during snapshot; retry next normal refresh")
        observed = max(p.stat().st_mtime for p in paths)
        for edition, player, cutoff in wanted:
            logs = []
            for k, game in games.items():
                if k[0] != edition or player not in k[1:3] or game["date"] >= cutoff:
                    continue
                prefix, other = ("w", "l") if player == k[1] else ("l", "w")
                values = None if k in conflicts or k in stat_conflicts else valid_counts(stats.get(k, {}))
                status = "retired" if re.search(r"RET|ABD|DEF", game["result"], re.I) else "completed"
                logs.append({"date": game["date"], "round_id": k[3], "opponent_id": game[f"{'loser' if prefix == 'w' else 'winner'}_id"],
                    "opponent": names.get(game[f"{'loser' if prefix == 'w' else 'winner'}_id"], "Name unavailable"),
                    "result": game["result"], "status": status, "stats_status": "verified" if values is not None else "unavailable",
                    "created": values[f"{prefix}_bpof"] if values is not None else None,
                    "converted": values[f"{prefix}_bpw"] if values is not None else None,
                    "faced": values[f"{prefix}_bpfaced"] if values is not None else None,
                    "saved": values[f"{prefix}_bpsaved"] if values is not None else None,
                    "match_chances": values[f"{prefix}_bpof"] + values[f"{prefix}_bpfaced"] if values is not None else None,
                    "source_key": "|".join((tour,) + k),
                    "issue": "conflicting_result" if k in conflicts else "conflicting_stats" if k in stat_conflicts else "missing_or_inconsistent_stats" if values is None else ""})
            logs.sort(key=lambda r: (r["date"], count(r["round_id"]) or 0, r["source_key"]))
            result[(tour, edition, player, cutoff)] = {"version": VERSION, "tour": tour, "tour_id": edition,
                "player_id": player, "before_date": cutoff, "source_observed_epoch": observed, "logs": logs}
    return result


def enrich_files(root: Path, files: dict[str, str]) -> dict[str, str]:
    """Return enriched transport copies only; original files are never altered."""
    board = list(csv.DictReader(io.StringIO(files.get("props-board", ""))))
    report = json.loads(files["most-aces-current"]) if "most-aces-current" in files else {}
    nested = [(r, str(m.get("tour") or "")) for m in report.get("matches", [])
              for r in m.get("tournament_players", []) if isinstance(r, dict)]
    requests = [identity(r) for r in board] + [identity(r, tour) for r, tour in nested]
    if not requests:
        return {}
    evidence = histories(root, requests)
    for row, tour in [(r, "") for r in board] + nested:
        history = evidence.get(identity(row, tour))
        if history:
            row["break_point_history"] = json.dumps(history, ensure_ascii=False, separators=(",", ":"))
    output = {}
    if board:
        out = io.StringIO(newline="")
        fields = list(board[0])
        if "break_point_history" not in fields:
            fields.append("break_point_history")
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        writer.writerows(board)
        output["props-board"] = out.getvalue()
    if nested:
        output["most-aces-current"] = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
    return output
