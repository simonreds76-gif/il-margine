#!/usr/bin/env python3
"""Build a canonical, real-price tennis spread settlement dataset.

The scorer uses local Pinnacle capture history and OnCourt results only. It is
deliberately conservative: full-name identities must resolve uniquely, match
dates must resolve unambiguously, and uncertain timing remains visible in the
output instead of being presented as a true closing price.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY_DIR = ROOT / "data" / "pinnacle-history"
DEFAULT_PLAYERS = ROOT / "data" / "oncourt" / "players_atp.csv"
DEFAULT_GAMES = ROOT / "data" / "oncourt" / "games_atp.csv"
DEFAULT_TOURS = ROOT / "data" / "oncourt" / "tours_atp.csv"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "backtest"
VALID_LANES = {"ATP", "Challenger"}
RESULT_EXCLUSIONS = ("RET", "W/O", "WALKOVER", "DEF", "ABD", "ABN", "BYE")
TOUR_TOKEN_STOPWORDS = {
    "atp",
    "challenger",
    "open",
    "tennis",
    "championships",
    "championship",
    "mens",
    "men",
    "r1",
    "r2",
    "r3",
    "r4",
    "qf",
    "sf",
    "final",
    "qualification",
    "qualifying",
}


OUTPUT_FIELDS = [
    "lane",
    "match_key",
    "match_date",
    "tour_id",
    "tour_name",
    "tour_rank",
    "surface",
    "round_id",
    "result",
    "result_join_method",
    "player1_id",
    "player1",
    "player2_id",
    "player2",
    "publication_at",
    "publication_capture_mode",
    "publication_source_file",
    "publication_timing_quality",
    "kickoff_iso",
    "spread_line_p1",
    "spread_odds1",
    "spread_odds2",
    "spread_market_p1_devig",
    "ml_odds1",
    "ml_odds2",
    "close_at",
    "close_capture_mode",
    "close_odds1",
    "close_odds2",
    "close_market_p1_devig",
    "published_to_close_clv_p1",
    "published_to_close_clv_p2",
    "close_gap_hours",
    "close_is_stale",
    "clv_eligible",
    "latest_line_at",
    "latest_spread_line_p1",
    "line_move_p1",
    "actual_game_margin_p1",
    "p1_cover_result",
    "p2_cover_result",
    "p1_cover_binary",
    "market_brier",
    "market_log_loss",
    "p1_flat_pnl",
    "p2_flat_pnl",
    "snapshot_count",
    "same_line_snapshot_count",
]

ML_OUTPUT_FIELDS = [
    "lane",
    "match_key",
    "match_date",
    "tour_id",
    "tour_name",
    "tour_rank",
    "surface",
    "round_id",
    "result",
    "result_join_method",
    "player1_id",
    "player1",
    "player2_id",
    "player2",
    "publication_at",
    "publication_capture_mode",
    "publication_source_file",
    "publication_timing_quality",
    "kickoff_iso",
    "ml_odds1",
    "ml_odds2",
    "market_p1_devig",
    "close_at",
    "close_capture_mode",
    "close_ml_odds1",
    "close_ml_odds2",
    "close_market_p1_devig",
    "published_to_close_clv_p1",
    "published_to_close_clv_p2",
    "close_gap_hours",
    "close_is_stale",
    "clv_eligible",
    "actual_winner_id",
    "p1_win_binary",
    "market_brier",
    "market_log_loss",
    "p1_flat_pnl",
    "p2_flat_pnl",
    "snapshot_count",
]

UNMATCHED_FIELDS = [
    "lane",
    "reason",
    "player1_name",
    "player2_name",
    "player1_normalized",
    "player2_normalized",
    "capture_date_first",
    "capture_date_last",
    "snapshot_count",
    "source_files",
    "details",
]


def normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def parse_int(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def devig_probability(odds1: float, odds2: float) -> float:
    inverse1, inverse2 = 1.0 / odds1, 1.0 / odds2
    return inverse1 / (inverse1 + inverse2)


def score_margin(result: str) -> tuple[int, int, int] | None:
    upper = str(result or "").strip().upper()
    if not upper or any(marker in upper for marker in RESULT_EXCLUSIONS):
        return None
    sets = re.findall(r"(?<!\d)(\d+)-(\d+)", upper)
    if not sets:
        return None
    winner_games = sum(int(left) for left, _ in sets)
    loser_games = sum(int(right) for _, right in sets)
    if winner_games <= loser_games:
        return None
    return winner_games, loser_games, winner_games - loser_games


def grade_spread(actual_margin: float, line: float) -> str:
    covered = actual_margin + line
    if covered > 1e-9:
        return "WIN"
    if covered < -1e-9:
        return "LOSS"
    return "PUSH"


def opposite_result(result: str) -> str:
    return {"WIN": "LOSS", "LOSS": "WIN", "PUSH": "PUSH"}[result]


def flat_pnl(result: str, odds: float) -> float:
    if result == "WIN":
        return odds - 1.0
    if result == "LOSS":
        return -1.0
    return 0.0


def rounded(value: float | None, digits: int = 6) -> str | float:
    return "" if value is None else round(value, digits)


@dataclass(frozen=True)
class PlayerResolution:
    player_id: int | None
    canonical_name: str
    method: str
    reason: str


class FullNameResolver:
    """Resolve only complete normalized names or complete token-order variants."""

    def __init__(self, player_rows: Iterable[dict[str, str]]):
        self.names_by_id: dict[int, str] = {}
        exact: dict[str, set[int]] = defaultdict(set)
        token_sets: dict[str, set[int]] = defaultdict(set)
        for row in player_rows:
            player_id = parse_int(row.get("id"))
            canonical_name = str(row.get("name") or "").strip()
            normalized = normalize_name(canonical_name)
            if player_id is None or not normalized or "/" in canonical_name:
                continue
            self.names_by_id[player_id] = canonical_name
            exact[normalized].add(player_id)
            token_sets[" ".join(sorted(normalized.split()))].add(player_id)
        self.exact = dict(exact)
        self.token_sets = dict(token_sets)

    def resolve(self, name: str) -> PlayerResolution:
        normalized = normalize_name(name)
        if not normalized:
            return PlayerResolution(None, "", "", "empty_name")
        exact_ids = self.exact.get(normalized, set())
        if len(exact_ids) == 1:
            player_id = next(iter(exact_ids))
            return PlayerResolution(
                player_id,
                self.names_by_id[player_id],
                "full_exact",
                "",
            )
        if len(exact_ids) > 1:
            return PlayerResolution(None, "", "", "ambiguous_full_name")

        token_ids = self.token_sets.get(" ".join(sorted(normalized.split())), set())
        if len(token_ids) == 1:
            player_id = next(iter(token_ids))
            return PlayerResolution(
                player_id,
                self.names_by_id[player_id],
                "full_token_order",
                "",
            )
        if len(token_ids) > 1:
            return PlayerResolution(None, "", "", "ambiguous_full_token_order")
        return PlayerResolution(None, "", "", "unresolved_full_name")


@dataclass(frozen=True)
class Tour:
    tour_id: int
    name: str
    rank: int | None
    court_id: int | None = None

    @property
    def surface(self) -> str:
        return {
            1: "Hard",
            2: "Clay",
            3: "I.hard",
            4: "Carpet",
            5: "Grass",
            6: "Acrylic",
        }.get(self.court_id, "N/A")


@dataclass(frozen=True)
class Game:
    winner_id: int
    loser_id: int
    tour_id: int
    round_id: int | None
    result: str
    match_date: date

    @property
    def pair(self) -> tuple[int, int]:
        return tuple(sorted((self.winner_id, self.loser_id)))

    @property
    def key(self) -> tuple[str, int, int, int]:
        return (
            self.match_date.isoformat(),
            self.tour_id,
            self.winner_id,
            self.loser_id,
        )


@dataclass(frozen=True)
class Snapshot:
    lane: str
    league_name: str
    player1_name: str
    player2_name: str
    player1_id: int
    player2_id: int
    captured_at: datetime
    capture_date: date
    capture_mode: str
    match_date: date | None
    kickoff: datetime | None
    ml_odds1: float
    ml_odds2: float
    spread_line: float | None
    spread_odds1: float | None
    spread_odds2: float | None
    source_file: str
    resolve_method1: str
    resolve_method2: str

    @property
    def pair(self) -> tuple[int, int]:
        return tuple(sorted((self.player1_id, self.player2_id)))


class Diagnostics:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def add(
        self,
        reason: str,
        lane: str,
        player1: str,
        player2: str,
        capture_date: date | None,
        source_file: str,
        details: str = "",
    ) -> None:
        key = (lane, normalize_name(player1), normalize_name(player2), reason)
        capture_text = capture_date.isoformat() if capture_date else ""
        if key not in self._rows:
            self._rows[key] = {
                "lane": lane,
                "reason": reason,
                "player1_name": player1,
                "player2_name": player2,
                "player1_normalized": key[1],
                "player2_normalized": key[2],
                "capture_date_first": capture_text,
                "capture_date_last": capture_text,
                "snapshot_count": 0,
                "source_files": set(),
                "details": set(),
            }
        row = self._rows[key]
        row["snapshot_count"] += 1
        if capture_text:
            existing_first = row["capture_date_first"]
            existing_last = row["capture_date_last"]
            row["capture_date_first"] = (
                min(existing_first, capture_text) if existing_first else capture_text
            )
            row["capture_date_last"] = (
                max(existing_last, capture_text) if existing_last else capture_text
            )
        if source_file:
            row["source_files"].add(source_file)
        if details:
            row["details"].add(details)

    def rows(self) -> list[dict[str, Any]]:
        output = []
        for row in self._rows.values():
            serial = dict(row)
            serial["source_files"] = "|".join(sorted(row["source_files"]))
            serial["details"] = "|".join(sorted(row["details"]))
            output.append(serial)
        return sorted(
            output,
            key=lambda row: (
                row["lane"],
                row["reason"],
                row["player1_normalized"],
                row["player2_normalized"],
            ),
        )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_tours(path: Path) -> dict[int, Tour]:
    tours: dict[int, Tour] = {}
    for row in read_csv(path):
        tour_id = parse_int(row.get("id"))
        if tour_id is None:
            continue
        tours[tour_id] = Tour(
            tour_id=tour_id,
            name=str(row.get("name") or "").strip(),
            rank=parse_int(row.get("rank")),
            court_id=parse_int(row.get("court_id")),
        )
    return tours


def load_games(
    path: Path,
    start_date: date,
    end_date: date,
) -> tuple[list[Game], dict[tuple[int, int], list[Game]]]:
    games: list[Game] = []
    by_pair: dict[tuple[int, int], list[Game]] = defaultdict(list)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            match_date = parse_date(row.get("date"))
            if match_date is None or not start_date <= match_date <= end_date:
                continue
            winner_id = parse_int(row.get("winner_id"))
            loser_id = parse_int(row.get("loser_id"))
            tour_id = parse_int(row.get("tour_id"))
            if (
                winner_id is None
                or loser_id is None
                or tour_id is None
                or winner_id == loser_id
            ):
                continue
            game = Game(
                winner_id=winner_id,
                loser_id=loser_id,
                tour_id=tour_id,
                round_id=parse_int(row.get("round_id")),
                result=str(row.get("result") or "").strip(),
                match_date=match_date,
            )
            games.append(game)
            by_pair[game.pair].append(game)
    for candidates in by_pair.values():
        candidates.sort(key=lambda game: (game.match_date, game.tour_id))
    return games, dict(by_pair)


def normalized_lane(value: Any) -> str:
    text = str(value or "").strip().lower()
    if "challenger" in text:
        return "Challenger"
    if text == "atp" or text.startswith("atp "):
        return "ATP"
    return ""


def load_snapshots(
    history_dir: Path,
    resolver: FullNameResolver,
    start_date: date,
    end_date: date,
    diagnostics: Diagnostics,
) -> list[Snapshot]:
    snapshots: list[Snapshot] = []
    seen: set[tuple[Any, ...]] = set()
    for path in sorted(history_dir.glob("pinnacle-history-*.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                lane = normalized_lane(row.get("league"))
                if lane not in VALID_LANES:
                    continue
                captured_at = parse_datetime(row.get("captured_at"))
                capture_date = parse_date(row.get("capture_date"))
                if capture_date is None and captured_at is not None:
                    capture_date = captured_at.date()
                if (
                    captured_at is None
                    or capture_date is None
                    or not start_date <= capture_date <= end_date
                ):
                    continue

                player1 = str(row.get("player1_name") or "").strip()
                player2 = str(row.get("player2_name") or "").strip()
                spread_line = parse_float(row.get("spread_line"))
                spread_odds1 = parse_float(row.get("spread_odds1"))
                spread_odds2 = parse_float(row.get("spread_odds2"))
                ml_odds1 = parse_float(row.get("odds1"))
                ml_odds2 = parse_float(row.get("odds2"))
                if (
                    ml_odds1 is None
                    or ml_odds2 is None
                    or min(ml_odds1, ml_odds2) <= 1.0
                ):
                    diagnostics.add(
                        "incomplete_ml_price",
                        lane,
                        player1,
                        player2,
                        capture_date,
                        path.name,
                    )
                    continue

                resolution1 = resolver.resolve(player1)
                resolution2 = resolver.resolve(player2)
                if resolution1.player_id is None:
                    diagnostics.add(
                        resolution1.reason,
                        lane,
                        player1,
                        player2,
                        capture_date,
                        path.name,
                        "player1",
                    )
                    continue
                if resolution2.player_id is None:
                    diagnostics.add(
                        resolution2.reason,
                        lane,
                        player1,
                        player2,
                        capture_date,
                        path.name,
                        "player2",
                    )
                    continue
                if resolution1.player_id == resolution2.player_id:
                    diagnostics.add(
                        "same_player_id",
                        lane,
                        player1,
                        player2,
                        capture_date,
                        path.name,
                    )
                    continue

                dedupe_key = (
                    lane,
                    captured_at.isoformat(),
                    resolution1.player_id,
                    resolution2.player_id,
                    spread_line,
                    spread_odds1,
                    spread_odds2,
                    ml_odds1,
                    ml_odds2,
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                snapshots.append(
                    Snapshot(
                        lane=lane,
                        league_name=str(row.get("league_name") or "").strip(),
                        player1_name=resolution1.canonical_name,
                        player2_name=resolution2.canonical_name,
                        player1_id=resolution1.player_id,
                        player2_id=resolution2.player_id,
                        captured_at=captured_at,
                        capture_date=capture_date,
                        capture_mode=str(row.get("capture_mode") or "").strip().lower(),
                        match_date=parse_date(row.get("match_date")),
                        kickoff=parse_datetime(row.get("kickoff_iso")),
                        ml_odds1=ml_odds1,
                        ml_odds2=ml_odds2,
                        spread_line=spread_line,
                        spread_odds1=spread_odds1,
                        spread_odds2=spread_odds2,
                        source_file=path.name,
                        resolve_method1=resolution1.method,
                        resolve_method2=resolution2.method,
                    )
                )
    return snapshots


def tour_tokens(value: str) -> set[str]:
    return {
        token
        for token in normalize_name(value).split()
        if token not in TOUR_TOKEN_STOPWORDS and not token.isdigit()
    }


def disambiguate_by_tour(
    candidates: list[Game],
    league_name: str,
    tours: dict[int, Tour],
) -> Game | None:
    if len(candidates) == 1:
        return candidates[0]
    league_tokens = tour_tokens(league_name)
    scores = [
        (
            len(league_tokens & tour_tokens(tours.get(game.tour_id, Tour(0, "", None)).name)),
            game,
        )
        for game in candidates
    ]
    scores.sort(key=lambda item: item[0], reverse=True)
    if scores and scores[0][0] > 0 and (
        len(scores) == 1 or scores[0][0] > scores[1][0]
    ):
        return scores[0][1]
    return None


def resolve_snapshot_game(
    snapshot: Snapshot,
    games_by_pair: dict[tuple[int, int], list[Game]],
    tours: dict[int, Tour],
    fallback_days: int,
) -> tuple[Game | None, str, str]:
    pair_games = games_by_pair.get(snapshot.pair, [])
    if snapshot.match_date is not None:
        exact = [
            game for game in pair_games if game.match_date == snapshot.match_date
        ]
        selected = disambiguate_by_tour(exact, snapshot.league_name, tours)
        if selected is not None:
            return selected, "pair_exact_match_date", ""
        if len(exact) > 1:
            return None, "", "ambiguous_exact_match_date"

    window_end = snapshot.capture_date + timedelta(days=fallback_days)
    fallback = [
        game
        for game in pair_games
        if snapshot.capture_date <= game.match_date <= window_end
    ]
    selected = disambiguate_by_tour(fallback, snapshot.league_name, tours)
    if selected is not None:
        method = (
            "pair_capture_window_tour"
            if len(fallback) > 1
            else "pair_capture_window_unique"
        )
        return selected, method, ""
    if not fallback:
        return None, "", "result_not_found_in_window"
    return None, "", "ambiguous_capture_window"


def timing_quality(snapshot: Snapshot, game: Game) -> str:
    if snapshot.kickoff is not None:
        return "verified_prestart"
    if snapshot.capture_date < game.match_date:
        return "inferred_prior_day"
    return "same_day_unverified"


def is_eligible_snapshot(snapshot: Snapshot, game: Game) -> bool:
    if snapshot.kickoff is not None:
        return snapshot.captured_at < snapshot.kickoff
    return snapshot.capture_date <= game.match_date


@dataclass(frozen=True)
class OrientedSnapshot:
    source: Snapshot
    line_p1: float | None
    spread_odds1: float | None
    spread_odds2: float | None
    ml_odds1: float
    ml_odds2: float


def orient_snapshot(snapshot: Snapshot, player1_id: int) -> OrientedSnapshot:
    if snapshot.player1_id == player1_id:
        return OrientedSnapshot(
            source=snapshot,
            line_p1=snapshot.spread_line,
            spread_odds1=snapshot.spread_odds1,
            spread_odds2=snapshot.spread_odds2,
            ml_odds1=snapshot.ml_odds1,
            ml_odds2=snapshot.ml_odds2,
        )
    if snapshot.player2_id != player1_id:
        raise ValueError("Snapshot does not contain requested player1_id")
    return OrientedSnapshot(
        source=snapshot,
        line_p1=-snapshot.spread_line if snapshot.spread_line is not None else None,
        spread_odds1=snapshot.spread_odds2,
        spread_odds2=snapshot.spread_odds1,
        ml_odds1=snapshot.ml_odds2,
        ml_odds2=snapshot.ml_odds1,
    )


def choose_close(candidates: list[OrientedSnapshot]) -> OrientedSnapshot:
    close_mode = [
        candidate
        for candidate in candidates
        if candidate.source.capture_mode == "close"
    ]
    pool = close_mode or candidates
    return max(pool, key=lambda candidate: candidate.source.captured_at)


def score_match(
    lane: str,
    game: Game,
    assigned: list[tuple[Snapshot, str]],
    tours: dict[int, Tour],
) -> tuple[dict[str, Any] | None, str]:
    valid = [
        (snapshot, method)
        for snapshot, method in assigned
        if is_eligible_snapshot(snapshot, game)
        and snapshot.spread_line is not None
        and snapshot.spread_odds1 is not None
        and snapshot.spread_odds2 is not None
    ]
    if not valid:
        return None, "no_prestart_spread_snapshot"
    valid.sort(key=lambda item: item[0].captured_at)
    publication, join_method = valid[0]
    player1_id = publication.player1_id
    player2_id = publication.player2_id
    oriented = [
        orient_snapshot(snapshot, player1_id)
        for snapshot, _ in valid
    ]
    pub = oriented[0]
    assert pub.line_p1 is not None
    assert pub.spread_odds1 is not None
    assert pub.spread_odds2 is not None
    same_line = [
        snapshot
        for snapshot in oriented
        if snapshot.line_p1 is not None
        and math.isclose(snapshot.line_p1, pub.line_p1, abs_tol=1e-9)
    ]
    close = choose_close(same_line)
    assert close.spread_odds1 is not None
    assert close.spread_odds2 is not None
    latest = max(oriented, key=lambda snapshot: snapshot.source.captured_at)

    margin = score_margin(game.result)
    if margin is None:
        return None, "unscorable_result"
    _, _, winner_margin = margin
    actual_margin_p1 = (
        winner_margin if game.winner_id == player1_id else -winner_margin
    )
    p1_result = grade_spread(actual_margin_p1, pub.line_p1)
    p2_result = opposite_result(p1_result)
    market_p1 = devig_probability(pub.spread_odds1, pub.spread_odds2)
    cover_binary = (
        1.0 if p1_result == "WIN" else 0.0 if p1_result == "LOSS" else None
    )
    brier = (
        (market_p1 - cover_binary) ** 2 if cover_binary is not None else None
    )
    log_loss = None
    if cover_binary is not None:
        clipped = min(max(market_p1, 1e-12), 1.0 - 1e-12)
        log_loss = -(
            cover_binary * math.log(clipped)
            + (1.0 - cover_binary) * math.log(1.0 - clipped)
        )

    kickoff = publication.kickoff
    if kickoff is None:
        kickoff_values = [
            snapshot.source.kickoff
            for snapshot in oriented
            if snapshot.source.kickoff is not None
        ]
        kickoff = min(kickoff_values) if kickoff_values else None
    close_gap_hours = (
        (kickoff - close.source.captured_at).total_seconds() / 3600.0
        if kickoff is not None
        else None
    )
    close_is_stale = (
        close_gap_hours > 12.0 if close_gap_hours is not None else None
    )
    clv_eligible = close_gap_hours is not None and not close_is_stale
    close_market_p1 = devig_probability(
        close.spread_odds1,
        close.spread_odds2,
    )
    tour = tours.get(game.tour_id, Tour(game.tour_id, "", None))
    return {
        "lane": lane,
        "match_key": (
            f"{game.match_date.isoformat()}|{game.tour_id}|"
            f"{min(player1_id, player2_id)}|{max(player1_id, player2_id)}"
        ),
        "match_date": game.match_date.isoformat(),
        "tour_id": game.tour_id,
        "tour_name": tour.name,
        "tour_rank": tour.rank if tour.rank is not None else "",
        "surface": tour.surface,
        "round_id": game.round_id if game.round_id is not None else "",
        "result": game.result,
        "result_join_method": join_method,
        "player1_id": player1_id,
        "player1": publication.player1_name,
        "player2_id": player2_id,
        "player2": publication.player2_name,
        "publication_at": publication.captured_at.isoformat(),
        "publication_capture_mode": publication.capture_mode,
        "publication_source_file": publication.source_file,
        "publication_timing_quality": timing_quality(publication, game),
        "kickoff_iso": kickoff.isoformat() if kickoff is not None else "",
        "spread_line_p1": rounded(pub.line_p1, 3),
        "spread_odds1": rounded(pub.spread_odds1, 4),
        "spread_odds2": rounded(pub.spread_odds2, 4),
        "spread_market_p1_devig": rounded(market_p1, 8),
        "ml_odds1": rounded(pub.ml_odds1, 4),
        "ml_odds2": rounded(pub.ml_odds2, 4),
        "close_at": close.source.captured_at.isoformat(),
        "close_capture_mode": close.source.capture_mode,
        "close_odds1": rounded(close.spread_odds1, 4),
        "close_odds2": rounded(close.spread_odds2, 4),
        "close_market_p1_devig": rounded(close_market_p1, 8),
        "published_to_close_clv_p1": rounded(
            pub.spread_odds1 / close.spread_odds1 - 1.0,
            8,
        ),
        "published_to_close_clv_p2": rounded(
            pub.spread_odds2 / close.spread_odds2 - 1.0,
            8,
        ),
        "close_gap_hours": rounded(close_gap_hours, 4),
        "close_is_stale": (
            "1" if close_is_stale else "0"
            if close_is_stale is not None
            else ""
        ),
        "clv_eligible": "1" if clv_eligible else "0",
        "latest_line_at": latest.source.captured_at.isoformat(),
        "latest_spread_line_p1": rounded(latest.line_p1, 3),
        "line_move_p1": rounded(latest.line_p1 - pub.line_p1, 3),
        "actual_game_margin_p1": actual_margin_p1,
        "p1_cover_result": p1_result,
        "p2_cover_result": p2_result,
        "p1_cover_binary": rounded(cover_binary, 0),
        "market_brier": rounded(brier, 8),
        "market_log_loss": rounded(log_loss, 8),
        "p1_flat_pnl": rounded(flat_pnl(p1_result, pub.spread_odds1), 6),
        "p2_flat_pnl": rounded(flat_pnl(p2_result, pub.spread_odds2), 6),
        "snapshot_count": len(oriented),
        "same_line_snapshot_count": len(same_line),
    }, ""


def score_ml_match(
    lane: str,
    game: Game,
    assigned: list[tuple[Snapshot, str]],
    tours: dict[int, Tour],
) -> tuple[dict[str, Any] | None, str]:
    if any(marker in game.result.upper() for marker in RESULT_EXCLUSIONS):
        return None, "unscorable_result"
    valid = [
        (snapshot, method)
        for snapshot, method in assigned
        if is_eligible_snapshot(snapshot, game)
    ]
    if not valid:
        return None, "no_prestart_snapshot"
    valid.sort(key=lambda item: item[0].captured_at)
    publication, join_method = valid[0]
    player1_id = publication.player1_id
    player2_id = publication.player2_id
    oriented = [orient_snapshot(snapshot, player1_id) for snapshot, _ in valid]
    pub = oriented[0]
    close = choose_close(oriented)

    market_p1 = devig_probability(pub.ml_odds1, pub.ml_odds2)
    close_market_p1 = devig_probability(close.ml_odds1, close.ml_odds2)
    p1_won = 1.0 if game.winner_id == player1_id else 0.0
    clipped = min(max(market_p1, 1e-12), 1.0 - 1e-12)
    market_brier = (market_p1 - p1_won) ** 2
    market_log_loss = -(
        p1_won * math.log(clipped)
        + (1.0 - p1_won) * math.log(1.0 - clipped)
    )

    kickoff = publication.kickoff
    if kickoff is None:
        known_kickoffs = [
            snapshot.source.kickoff
            for snapshot in oriented
            if snapshot.source.kickoff is not None
        ]
        kickoff = min(known_kickoffs) if known_kickoffs else None
    close_gap_hours = (
        (kickoff - close.source.captured_at).total_seconds() / 3600.0
        if kickoff is not None
        else None
    )
    close_is_stale = close_gap_hours > 12.0 if close_gap_hours is not None else None
    clv_eligible = close_gap_hours is not None and close_gap_hours >= 0 and not close_is_stale
    tour = tours.get(game.tour_id, Tour(game.tour_id, "", None))
    return {
        "lane": lane,
        "match_key": (
            f"{game.match_date.isoformat()}|{game.tour_id}|"
            f"{min(player1_id, player2_id)}|{max(player1_id, player2_id)}"
        ),
        "match_date": game.match_date.isoformat(),
        "tour_id": game.tour_id,
        "tour_name": tour.name,
        "tour_rank": tour.rank if tour.rank is not None else "",
        "surface": tour.surface,
        "round_id": game.round_id if game.round_id is not None else "",
        "result": game.result,
        "result_join_method": join_method,
        "player1_id": player1_id,
        "player1": publication.player1_name,
        "player2_id": player2_id,
        "player2": publication.player2_name,
        "publication_at": publication.captured_at.isoformat(),
        "publication_capture_mode": publication.capture_mode,
        "publication_source_file": publication.source_file,
        "publication_timing_quality": timing_quality(publication, game),
        "kickoff_iso": kickoff.isoformat() if kickoff is not None else "",
        "ml_odds1": rounded(pub.ml_odds1, 4),
        "ml_odds2": rounded(pub.ml_odds2, 4),
        "market_p1_devig": rounded(market_p1, 8),
        "close_at": close.source.captured_at.isoformat(),
        "close_capture_mode": close.source.capture_mode,
        "close_ml_odds1": rounded(close.ml_odds1, 4),
        "close_ml_odds2": rounded(close.ml_odds2, 4),
        "close_market_p1_devig": rounded(close_market_p1, 8),
        "published_to_close_clv_p1": rounded(pub.ml_odds1 / close.ml_odds1 - 1.0, 8),
        "published_to_close_clv_p2": rounded(pub.ml_odds2 / close.ml_odds2 - 1.0, 8),
        "close_gap_hours": rounded(close_gap_hours, 4),
        "close_is_stale": "1" if close_is_stale else "0" if close_is_stale is not None else "",
        "clv_eligible": "1" if clv_eligible else "0",
        "actual_winner_id": game.winner_id,
        "p1_win_binary": int(p1_won),
        "market_brier": rounded(market_brier, 8),
        "market_log_loss": rounded(market_log_loss, 8),
        "p1_flat_pnl": rounded(pub.ml_odds1 - 1.0 if p1_won else -1.0, 6),
        "p2_flat_pnl": rounded(pub.ml_odds2 - 1.0 if not p1_won else -1.0, 6),
        "snapshot_count": len(oriented),
    }, ""


def score_history(
    snapshots: list[Snapshot],
    games_by_pair: dict[tuple[int, int], list[Game]],
    tours: dict[int, Tour],
    fallback_days: int,
    diagnostics: Diagnostics,
) -> dict[str, list[dict[str, Any]]]:
    assigned: dict[
        tuple[str, tuple[str, int, int, int]],
        list[tuple[Snapshot, str]],
    ] = defaultdict(list)
    for snapshot in snapshots:
        game, method, reason = resolve_snapshot_game(
            snapshot,
            games_by_pair,
            tours,
            fallback_days,
        )
        if game is None:
            diagnostics.add(
                reason,
                snapshot.lane,
                snapshot.player1_name,
                snapshot.player2_name,
                snapshot.capture_date,
                snapshot.source_file,
                snapshot.match_date.isoformat() if snapshot.match_date else "",
            )
            continue
        if not is_eligible_snapshot(snapshot, game):
            diagnostics.add(
                "snapshot_not_prestart",
                snapshot.lane,
                snapshot.player1_name,
                snapshot.player2_name,
                snapshot.capture_date,
                snapshot.source_file,
                snapshot.captured_at.isoformat(),
            )
            continue
        assigned[(snapshot.lane, game.key)].append((snapshot, method))

    scored: dict[str, list[dict[str, Any]]] = {"ATP": [], "Challenger": []}
    for (lane, _), match_snapshots in assigned.items():
        first_snapshot = min(
            match_snapshots,
            key=lambda item: item[0].captured_at,
        )[0]
        game, _, _ = resolve_snapshot_game(
            first_snapshot,
            games_by_pair,
            tours,
            fallback_days,
        )
        if game is None:
            continue
        row, reason = score_match(lane, game, match_snapshots, tours)
        if row is None:
            for snapshot, _ in match_snapshots:
                diagnostics.add(
                    reason,
                    lane,
                    snapshot.player1_name,
                    snapshot.player2_name,
                    snapshot.capture_date,
                    snapshot.source_file,
                    game.result,
                )
            continue
        scored[lane].append(row)
    for rows in scored.values():
        rows.sort(
            key=lambda row: (
                row["match_date"],
                row["tour_id"],
                row["player1_id"],
                row["player2_id"],
            )
        )
    return scored


def score_ml_history(
    snapshots: list[Snapshot],
    games_by_pair: dict[tuple[int, int], list[Game]],
    tours: dict[int, Tour],
    fallback_days: int,
    diagnostics: Diagnostics,
) -> dict[str, list[dict[str, Any]]]:
    assigned: dict[
        tuple[str, tuple[str, int, int, int]],
        list[tuple[Snapshot, str]],
    ] = defaultdict(list)
    games_by_key: dict[tuple[str, tuple[str, int, int, int]], Game] = {}
    for snapshot in snapshots:
        game, method, reason = resolve_snapshot_game(snapshot, games_by_pair, tours, fallback_days)
        if game is None:
            diagnostics.add(
                reason,
                snapshot.lane,
                snapshot.player1_name,
                snapshot.player2_name,
                snapshot.capture_date,
                snapshot.source_file,
                snapshot.match_date.isoformat() if snapshot.match_date else "",
            )
            continue
        if not is_eligible_snapshot(snapshot, game):
            diagnostics.add(
                "snapshot_not_prestart",
                snapshot.lane,
                snapshot.player1_name,
                snapshot.player2_name,
                snapshot.capture_date,
                snapshot.source_file,
                snapshot.captured_at.isoformat(),
            )
            continue
        key = (snapshot.lane, game.key)
        assigned[key].append((snapshot, method))
        games_by_key[key] = game

    scored: dict[str, list[dict[str, Any]]] = {"ATP": [], "Challenger": []}
    for key, match_snapshots in assigned.items():
        lane = key[0]
        row, reason = score_ml_match(lane, games_by_key[key], match_snapshots, tours)
        if row is None:
            for snapshot, _ in match_snapshots:
                diagnostics.add(
                    reason,
                    lane,
                    snapshot.player1_name,
                    snapshot.player2_name,
                    snapshot.capture_date,
                    snapshot.source_file,
                    games_by_key[key].result,
                )
            continue
        scored[lane].append(row)
    for rows in scored.values():
        rows.sort(key=lambda row: (row["match_date"], row["tour_id"], row["player1_id"], row["player2_id"]))
    return scored


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def average(values: Iterable[float]) -> float | None:
    materialized = list(values)
    return sum(materialized) / len(materialized) if materialized else None


def build_report(
    scored: dict[str, list[dict[str, Any]]],
    diagnostics: list[dict[str, Any]],
    history_files: int,
    snapshots: int,
) -> str:
    lines = [
        "IL MARGINE - Canonical Tennis Spread Real-Price Scorer",
        "",
        "Purpose: identity-safe settlement and real-price scoring only.",
        "This artifact does not authorise a live spread betting lane.",
        "",
        f"History files read: {history_files}",
        f"Valid unique spread snapshots: {snapshots}",
        "",
    ]
    for lane in ("ATP", "Challenger"):
        rows = scored[lane]
        non_push = [row for row in rows if row["p1_cover_result"] != "PUSH"]
        briers = [
            float(row["market_brier"])
            for row in non_push
            if row["market_brier"] != ""
        ]
        log_losses = [
            float(row["market_log_loss"])
            for row in non_push
            if row["market_log_loss"] != ""
        ]
        timing = Counter(row["publication_timing_quality"] for row in rows)
        true_close = sum(int(row["clv_eligible"]) for row in rows)
        pushes = sum(row["p1_cover_result"] == "PUSH" for row in rows)
        lines.extend(
            [
                f"{lane}:",
                f"- scored matches: {len(rows)}",
                f"- non-push / pushes: {len(non_push)} / {pushes}",
                f"- real-market M0 Brier: {average(briers):.6f}"
                if briers
                else "- real-market M0 Brier: n/a",
                f"- real-market M0 log loss: {average(log_losses):.6f}"
                if log_losses
                else "- real-market M0 log loss: n/a",
                f"- true-close eligible: {true_close}/{len(rows)}",
                f"- publication timing: {dict(sorted(timing.items()))}",
                "",
            ]
        )
    reason_counts = Counter()
    for row in diagnostics:
        reason_counts[row["reason"]] += int(row["snapshot_count"])
    lines.extend(
        [
            "Unmatched/dropped snapshots by reason:",
            *[
                f"- {reason}: {count}"
                for reason, count in reason_counts.most_common()
            ],
            "",
            "Integrity rules:",
            "- No surname-only or fuzzy identity fallback.",
            "- ATP and Challenger outputs are separate.",
            "- Integer handicap pushes are preserved, never mirrored as losses.",
            "- CLV eligibility requires a same-line snapshot within 12h of known kickoff.",
            "- Same-day captures without kickoff remain explicitly unverified.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_ml_report(
    scored: dict[str, list[dict[str, Any]]],
    diagnostics: list[dict[str, Any]],
    history_files: int,
    snapshots: int,
) -> str:
    lines = [
        "IL MARGINE - Canonical Tennis ML Real-Price Scorer",
        "",
        "Purpose: identity-safe ML settlement and real-price market benchmarking.",
        "This artifact contains no model edge and authorises no betting lane.",
        "",
        f"History files read: {history_files}",
        f"Valid unique ML snapshots: {snapshots}",
        "",
    ]
    for lane in ("ATP", "Challenger"):
        rows = scored[lane]
        briers = [float(row["market_brier"]) for row in rows]
        log_losses = [float(row["market_log_loss"]) for row in rows]
        timing = Counter(row["publication_timing_quality"] for row in rows)
        true_close = sum(int(row["clv_eligible"]) for row in rows)
        lines.extend(
            [
                f"{lane}:",
                f"- scored matches: {len(rows)}",
                f"- real-market Brier: {average(briers):.6f}" if briers else "- real-market Brier: n/a",
                f"- real-market log loss: {average(log_losses):.6f}" if log_losses else "- real-market log loss: n/a",
                f"- true-close eligible: {true_close}/{len(rows)}",
                f"- publication timing: {dict(sorted(timing.items()))}",
                "",
            ]
        )
    reason_counts = Counter()
    for row in diagnostics:
        reason_counts[row["reason"]] += int(row["snapshot_count"])
    lines.extend(
        [
            "Unmatched/dropped snapshots by reason:",
            *[f"- {reason}: {count}" for reason, count in reason_counts.most_common()],
            "",
            "Integrity rules:",
            "- Full-name identity resolution only; ambiguous matches are rejected.",
            "- Publication snapshots must be pre-start when kickoff is known.",
            "- Decision-grade CLV requires a known kickoff and a close no older than 12h.",
            "- Outcomes are oriented independently of winner-first source ordering.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    parser.add_argument("--players", type=Path, default=DEFAULT_PLAYERS)
    parser.add_argument("--games", type=Path, default=DEFAULT_GAMES)
    parser.add_argument("--tours", type=Path, default=DEFAULT_TOURS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-date", default="2026-01-01")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--fallback-days", type=int, default=4)
    args = parser.parse_args()

    start_date = parse_date(args.start_date)
    end_date = parse_date(args.end_date)
    if start_date is None or end_date is None or end_date < start_date:
        parser.error("Invalid --start-date/--end-date range")
    required = (args.history_dir, args.players, args.games, args.tours)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        parser.error(f"Missing required input(s): {', '.join(missing)}")

    diagnostics = Diagnostics()
    resolver = FullNameResolver(read_csv(args.players))
    _, games_by_pair = load_games(
        args.games,
        start_date,
        end_date + timedelta(days=args.fallback_days),
    )
    tours = load_tours(args.tours)
    snapshots = load_snapshots(
        args.history_dir,
        resolver,
        start_date,
        end_date,
        diagnostics,
    )
    spread_snapshot_count = sum(
        snapshot.spread_line is not None
        and snapshot.spread_odds1 is not None
        and snapshot.spread_odds2 is not None
        and min(snapshot.spread_odds1, snapshot.spread_odds2) > 1.0
        for snapshot in snapshots
    )
    scored = score_history(
        snapshots,
        games_by_pair,
        tours,
        max(0, args.fallback_days),
        diagnostics,
    )
    diagnostic_rows = diagnostics.rows()

    ml_diagnostics = Diagnostics()
    ml_scored = score_ml_history(
        snapshots,
        games_by_pair,
        tours,
        max(0, args.fallback_days),
        ml_diagnostics,
    )
    ml_diagnostic_rows = ml_diagnostics.rows()

    outputs = {
        "ATP": args.output_dir / "spread-real-scored-atp.csv",
        "Challenger": args.output_dir / "spread-real-scored-challenger.csv",
    }
    for lane, path in outputs.items():
        write_csv(path, scored[lane], OUTPUT_FIELDS)
    unmatched_path = args.output_dir / "spread-real-scored-unmatched.csv"
    write_csv(unmatched_path, diagnostic_rows, UNMATCHED_FIELDS)
    report_path = args.output_dir / "spread-real-scored-report.txt"
    report_path.write_text(
        build_report(
            scored,
            diagnostic_rows,
            len(list(args.history_dir.glob("pinnacle-history-*.csv"))),
            spread_snapshot_count,
        ),
        encoding="utf-8",
    )

    ml_outputs = {
        "ATP": args.output_dir / "ml-real-scored-atp.csv",
        "Challenger": args.output_dir / "ml-real-scored-challenger.csv",
    }
    for lane, path in ml_outputs.items():
        write_csv(path, ml_scored[lane], ML_OUTPUT_FIELDS)
    ml_unmatched_path = args.output_dir / "ml-real-scored-unmatched.csv"
    write_csv(ml_unmatched_path, ml_diagnostic_rows, UNMATCHED_FIELDS)
    ml_report_path = args.output_dir / "ml-real-scored-report.txt"
    ml_report_path.write_text(
        build_ml_report(
            ml_scored,
            ml_diagnostic_rows,
            len(list(args.history_dir.glob("pinnacle-history-*.csv"))),
            len(snapshots),
        ),
        encoding="utf-8",
    )

    print(f"ATP scored: {len(scored['ATP'])} -> {outputs['ATP']}")
    print(
        f"Challenger scored: {len(scored['Challenger'])} "
        f"-> {outputs['Challenger']}"
    )
    print(f"Unmatched diagnostics: {len(diagnostic_rows)} -> {unmatched_path}")
    print(f"Report: {report_path}")
    print(f"ATP ML scored: {len(ml_scored['ATP'])} -> {ml_outputs['ATP']}")
    print(f"Challenger ML scored: {len(ml_scored['Challenger'])} -> {ml_outputs['Challenger']}")
    print(f"ML unmatched diagnostics: {len(ml_diagnostic_rows)} -> {ml_unmatched_path}")
    print(f"ML report: {ml_report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
