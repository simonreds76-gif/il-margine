from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ONCOURT_DIR = ROOT / "data" / "oncourt"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "vnext"


@dataclass(frozen=True)
class ServeCountRow:
    match_key: str
    date: str
    date_ord: int
    year: int
    tour_id: int
    tournament: str
    tour_rank: int
    tour_level: str
    surface: str
    round_id: int
    server_id: int
    returner_id: int
    server_won_match: int
    serve_points: int
    first_in: int
    first_won: int
    second_attempts: int
    second_in: int
    second_won: int
    aces: int
    double_faults: int


COUNT_FIELDS = (
    "serve_points",
    "first_in",
    "first_won",
    "second_attempts",
    "second_in",
    "second_won",
    "aces",
    "double_faults",
)


def int_value(value: object, default: int | None = None) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_surface(court_name: str) -> str:
    value = str(court_name or "").strip().lower()
    if "clay" in value or "terre" in value:
        return "Clay"
    if "grass" in value:
        return "Grass"
    if "indoor" in value or "carpet" in value or "i.hard" in value:
        return "I.hard"
    if "hard" in value or "acrylic" in value or "decoturf" in value:
        return "Hard"
    return "N/A"


def tour_level(name: str, rank: int) -> str:
    upper = str(name or "").upper()
    if rank == 1 or "CHALLENGER" in upper:
        return "Challenger"
    if rank == 4 or any(token in upper for token in ("WIMBLEDON", "ROLAND GARROS", "US OPEN", "AUSTRALIAN OPEN")):
        return "Grand Slam"
    if rank in {2, 3}:
        return "ATP"
    return "Other"


def supported_tour(name: str, rank: int) -> bool:
    upper = str(name or "").upper()
    if "ITF" in upper or "FUTURES" in upper:
        return False
    return rank in {1, 2, 3, 4} or any(
        token in upper for token in ("ATP", "CHALLENGER", "MASTERS", "GRAND SLAM", "WIMBLEDON", "ROLAND GARROS", "US OPEN", "AUSTRALIAN OPEN")
    )


def load_tours(oncourt_dir: Path) -> dict[int, dict[str, object]]:
    courts: dict[int, str] = {}
    with (oncourt_dir / "courts.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            court_id = int_value(row.get("id"))
            if court_id is not None:
                courts[court_id] = str(row.get("name") or "")

    tours: dict[int, dict[str, object]] = {}
    with (oncourt_dir / "tours_atp.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            tour_id = int_value(row.get("id"))
            court_id = int_value(row.get("court_id"), 0) or 0
            rank = int_value(row.get("rank"), 0) or 0
            event_date = parse_date(row.get("date"))
            if tour_id is None or event_date is None:
                continue
            name = str(row.get("name") or "").strip()
            tours[tour_id] = {
                "id": tour_id,
                "name": name,
                "rank": rank,
                "date": event_date,
                "surface": canonical_surface(courts.get(court_id, "")),
                "supported": supported_tour(name, rank),
                "level": tour_level(name, rank),
            }
    return tours


def load_player_ids(oncourt_dir: Path) -> set[int]:
    ids: set[int] = set()
    with (oncourt_dir / "players_atp.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            player_id = int_value(row.get("id"))
            name = str(row.get("name") or "")
            if player_id is not None and "/" not in name:
                ids.add(player_id)
    return ids


def _load_stat_queues(stat_path: Path) -> dict[tuple[int, int, int, int], deque[dict[str, str]]]:
    queues: dict[tuple[int, int, int, int], deque[dict[str, str]]] = defaultdict(deque)
    with stat_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            winner_id = int_value(row.get("winner_id"))
            loser_id = int_value(row.get("loser_id"))
            tour_id = int_value(row.get("tour_id"))
            round_id = int_value(row.get("round_id"), 0) or 0
            if winner_id is None or loser_id is None or tour_id is None:
                continue
            queues[(winner_id, loser_id, tour_id, round_id)].append(row)
    return queues


def _side_counts(row: dict[str, str], prefix: str) -> tuple[dict[str, int] | None, str | None]:
    serve_points = int_value(row.get(f"{prefix}_svpt"), int_value(row.get(f"{prefix}_fsof"), 0)) or 0
    first_in = int_value(row.get(f"{prefix}_fs"), 0) or 0
    first_won = int_value(row.get(f"{prefix}_w1s"), 0) or 0
    second_attempts = int_value(row.get(f"{prefix}_w2sof"), max(0, serve_points - first_in)) or 0
    second_won = int_value(row.get(f"{prefix}_w2s"), 0) or 0
    aces = int_value(row.get(f"{prefix}_ace"), 0) or 0
    double_faults = int_value(row.get(f"{prefix}_df"), 0) or 0
    second_in = max(0, second_attempts - double_faults)

    counts = {
        "serve_points": serve_points,
        "first_in": first_in,
        "first_won": first_won,
        "second_attempts": second_attempts,
        "second_in": second_in,
        "second_won": second_won,
        "aces": aces,
        "double_faults": double_faults,
    }
    if serve_points <= 0:
        return None, "zero_serve_points"
    if not (0 <= first_in <= serve_points):
        return None, "invalid_first_in"
    if not (0 <= first_won <= first_in):
        return None, "invalid_first_won"
    if not (0 <= second_attempts <= serve_points):
        return None, "invalid_second_attempts"
    if not (0 <= double_faults <= second_attempts):
        return None, "invalid_double_faults"
    if not (0 <= second_won <= second_in):
        return None, "invalid_second_won"
    if not (0 <= aces <= first_in):
        return None, "invalid_aces"
    return counts, None


def iter_serve_count_rows(
    oncourt_dir: Path,
    *,
    start_year: int,
    end_year: int,
    surface: str | None = None,
) -> tuple[Iterator[ServeCountRow], dict[str, int]]:
    tours = load_tours(oncourt_dir)
    player_ids = load_player_ids(oncourt_dir)
    stats = _load_stat_queues(oncourt_dir / "stat_atp.csv")
    counters: dict[str, int] = defaultdict(int)

    def generate() -> Iterator[ServeCountRow]:
        occurrences: dict[tuple[int, int, int, int], int] = defaultdict(int)
        with (oncourt_dir / "games_atp.csv").open("r", encoding="utf-8-sig", newline="") as handle:
            for game in csv.DictReader(handle):
                winner_id = int_value(game.get("winner_id"))
                loser_id = int_value(game.get("loser_id"))
                tour_id = int_value(game.get("tour_id"))
                round_id = int_value(game.get("round_id"), 0) or 0
                if winner_id is None or loser_id is None or tour_id is None:
                    counters["bad_game_ids"] += 1
                    continue
                tour = tours.get(tour_id)
                if not tour or not bool(tour["supported"]):
                    counters["unsupported_tour"] += 1
                    continue
                event_date = parse_date(game.get("date")) or tour["date"]
                assert isinstance(event_date, date)
                if event_date.year < start_year or event_date.year > end_year:
                    continue
                if surface:
                    allowed_surfaces = {"Hard", "I.hard"} if surface == "Hard" else {surface}
                    if str(tour["surface"]) not in allowed_surfaces:
                        continue
                if winner_id not in player_ids or loser_id not in player_ids:
                    counters["missing_or_team_player"] += 1
                    continue
                key = (winner_id, loser_id, tour_id, round_id)
                queue = stats.get(key)
                if not queue:
                    counters["missing_stat_row"] += 1
                    continue
                stat = queue.popleft()
                occurrence = occurrences[key]
                occurrences[key] += 1
                match_key = f"{event_date.isoformat()}:{tour_id}:{round_id}:{winner_id}:{loser_id}:{occurrence}"
                winner_counts, winner_error = _side_counts(stat, "w")
                loser_counts, loser_error = _side_counts(stat, "l")
                if winner_error or loser_error:
                    counters[winner_error or loser_error or "invalid_counts"] += 1
                    continue
                assert winner_counts is not None and loser_counts is not None
                base = {
                    "match_key": match_key,
                    "date": event_date.isoformat(),
                    "date_ord": event_date.toordinal(),
                    "year": event_date.year,
                    "tour_id": tour_id,
                    "tournament": str(tour["name"]),
                    "tour_rank": int(tour["rank"]),
                    "tour_level": str(tour["level"]),
                    "surface": str(tour["surface"]),
                    "round_id": round_id,
                }
                counters["matches"] += 1
                counters["player_rows"] += 2
                yield ServeCountRow(**base, server_id=winner_id, returner_id=loser_id, server_won_match=1, **winner_counts)
                yield ServeCountRow(**base, server_id=loser_id, returner_id=winner_id, server_won_match=0, **loser_counts)

    return generate(), counters


def write_rows_csv_gz(rows: Iterable[ServeCountRow], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    # mtime=0 keeps the compressed artifact hash stable across identical runs.
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as compressed, io.TextIOWrapper(compressed, encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ServeCountRow.__dataclass_fields__))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
            count += 1
    return count


def read_rows_csv_gz(path: Path) -> list[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
