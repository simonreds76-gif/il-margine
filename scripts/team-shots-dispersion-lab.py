from __future__ import annotations

import csv
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / "data" / "team-shots" / "team-shots-predictions.csv"
MARKETS = ROOT / "data" / "team-shots" / "team-shots-comparison.csv"
REPORT_TXT = ROOT / "data" / "team-shots" / "team-shots-dispersion-lab.txt"
REPORT_CSV = ROOT / "data" / "team-shots" / "team-shots-dispersion-lab.csv"

ALPHAS = [0.0, 0.03, 0.06, 0.10, 0.15, 0.25]
EDGE_THRESHOLDS = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25]
LAMBDA_SOURCES = [
    "lambda_venue",
    "lambda_shots",
    "lambda_recent",
    "blend_70venue_30recent",
    "blend_60venue_40recent",
]

TEAM_ALIASES = {
    "1 cologne": "koln",
    "1 heidenheim": "heidenheim",
    "as roma": "roma",
    "athletic bilbao": "ath bilbao",
    "atletico madrid": "ath madrid",
    "bayer leverkusen": "leverkusen",
    "borussia dortmund": "dortmund",
    "ca osasuna": "osasuna",
    "deportivo alaves": "alaves",
    "eintracht frankfurt": "ein frankfurt",
    "espanyol barcelona": "espanol",
    "fsv mainz": "mainz",
    "hamburger": "hamburg",
    "hamburger sv": "hamburg",
    "hellas verona": "verona",
    "inter milano": "inter",
    "internazionale": "inter",
    "juventus turin": "juventus",
    "manchester city": "man city",
    "manchester united": "man united",
    "newcastle united": "newcastle",
    "nottingham forest": "nott m forest",
    "rayo vallecano": "vallecano",
    "rc celta vigo": "celta",
    "real betis seville": "betis",
    "real sociedad san sebastian": "sociedad",
    "ssc napoli": "napoli",
    "sunderland": "sunderland",
    "sunderland afc": "sunderland",
    "tottenham hotspur": "tottenham",
    "tsg hoffenheim": "hoffenheim",
    "us cremonese": "cremonese",
    "us lecce": "lecce",
    "vfb stuttgart": "stuttgart",
    "west ham united": "west ham",
    "wolverhampton wanderers": "wolves",
}


def to_float(value: object, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def normalize_text(value: object) -> str:
    text = str(value or "")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [
        w
        for w in text.split()
        if w
        not in {
            "fc",
            "afc",
            "cf",
            "sc",
            "ac",
            "bc",
            "calcio",
            "club",
            "football",
            "de",
            "the",
        }
    ]
    return " ".join(words)


def canonical_team(value: object) -> str:
    text = normalize_text(value)
    return TEAM_ALIASES.get(text, text)


def key(date: str, league: str, team: str) -> tuple[str, str, str]:
    return ((date or "").strip()[:10], normalize_text(league), canonical_team(team))


def load_predictions() -> dict[tuple[str, str, str], dict[str, str]]:
    if not PREDICTIONS.exists():
        raise FileNotFoundError(f"Missing input: {PREDICTIONS}")
    out: dict[tuple[str, str, str], dict[str, str]] = {}
    with PREDICTIONS.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            out.setdefault(key(row.get("date", ""), row.get("league", ""), row.get("team", "")), row)
    return out


def poisson_cdf(k: int, mu: float) -> float:
    if k < 0:
        return 0.0
    if mu <= 0:
        return 1.0
    pmf = math.exp(-mu)
    total = pmf
    for x in range(1, k + 1):
        pmf *= mu / x
        total += pmf
    return min(max(total, 0.0), 1.0)


def negbin_cdf(k: int, mu: float, alpha: float) -> float:
    if k < 0:
        return 0.0
    if mu <= 0:
        return 1.0
    if alpha <= 0:
        return poisson_cdf(k, mu)
    r = 1.0 / alpha
    p = r / (r + mu)
    log_p = math.log(p)
    log_1mp = math.log1p(-p)
    total = 0.0
    for x in range(k + 1):
        log_pmf = math.lgamma(x + r) - math.lgamma(r) - math.lgamma(x + 1) + r * log_p + x * log_1mp
        total += math.exp(log_pmf)
    return min(max(total, 0.0), 1.0)


def over_prob(line: float, mu: float, alpha: float) -> float:
    # For .5 lines this is P(X >= ceil(line)). For whole-number lines it treats exact line as push.
    k = math.floor(line)
    return 1.0 - negbin_cdf(k, mu, alpha)


def under_prob(line: float, mu: float, alpha: float) -> float:
    if abs(line - round(line)) < 1e-9:
        k = int(round(line)) - 1
    else:
        k = math.floor(line)
    return negbin_cdf(k, mu, alpha)


def lambda_for(source: str, pred: dict[str, str]) -> float | None:
    venue = to_float(pred.get("lambda_venue"))
    recent = to_float(pred.get("lambda_recent"))
    shots = to_float(pred.get("lambda_shots"))
    if source == "lambda_venue":
        return venue
    if source == "lambda_recent":
        return recent
    if source == "lambda_shots":
        return shots
    if source == "blend_70venue_30recent" and venue is not None and recent is not None:
        return 0.7 * venue + 0.3 * recent
    if source == "blend_60venue_40recent" and venue is not None and recent is not None:
        return 0.6 * venue + 0.4 * recent
    return None


def result_for(side: str, line: float, actual: float, odds: float) -> tuple[str, float]:
    side = side.strip().lower()
    if side == "over":
        if actual > line:
            return "win", odds - 1.0
        if abs(actual - line) < 1e-9:
            return "push", 0.0
        return "loss", -1.0
    if actual < line:
        return "win", odds - 1.0
    if abs(actual - line) < 1e-9:
        return "push", 0.0
    return "loss", -1.0


def market_fixture_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        (row.get("date") or "").strip()[:10],
        normalize_text(row.get("league")),
        normalize_text(row.get("home_team")),
        normalize_text(row.get("away_team")),
        canonical_team(row.get("team")),
    )


def load_market_rows(predictions: dict[tuple[str, str, str], dict[str, str]]) -> tuple[list[dict[str, object]], int, int]:
    if not MARKETS.exists():
        raise FileNotFoundError(f"Missing input: {MARKETS}")
    priced = 0
    matched = 0
    rows: list[dict[str, object]] = []
    with MARKETS.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            priced += 1
            line = to_float(row.get("line"))
            odds = to_float(row.get("book_odds"))
            actual = to_float(row.get("actual_shots"))
            if line is None or odds is None or actual is None:
                continue
            pred = predictions.get(key(row.get("date", ""), row.get("league", ""), row.get("team", "")))
            if pred is None:
                continue
            matched += 1
            rows.append({**row, "_line": line, "_odds": odds, "_actual": actual, "_prediction": pred})
    return rows, priced, matched


def score_rows(market_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    scored: list[dict[str, object]] = []
    for row in market_rows:
        line = float(row["_line"])
        odds = float(row["_odds"])
        actual = float(row["_actual"])
        side = str(row.get("side") or "").strip().lower()
        pred = row["_prediction"]
        assert isinstance(pred, dict)
        for source in LAMBDA_SOURCES:
            mu = lambda_for(source, pred)
            if mu is None or mu <= 0:
                continue
            for alpha in ALPHAS:
                p_over = over_prob(line, mu, alpha)
                p_under = under_prob(line, mu, alpha)
                prob = p_over if side == "over" else p_under
                edge = prob * odds - 1.0
                result, pnl = result_for(side, line, actual, odds)
                scored.append(
                    {
                        "date": row.get("date", ""),
                        "league": row.get("league", ""),
                        "home_team": row.get("home_team", ""),
                        "away_team": row.get("away_team", ""),
                        "team": row.get("team", ""),
                        "side": side,
                        "line": line,
                        "odds": odds,
                        "actual": actual,
                        "lambda_source": source,
                        "alpha": alpha,
                        "mu": mu,
                        "model_prob": prob,
                        "edge": edge,
                        "result": result,
                        "pnl": pnl,
                        "fixture_key": market_fixture_key(row),
                    }
                )
    return scored


def select_candidates(scored: list[dict[str, object]], source: str, alpha: float, threshold: float) -> list[dict[str, object]]:
    by_fixture: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
    for row in scored:
        if row["lambda_source"] != source or abs(float(row["alpha"]) - alpha) > 1e-12:
            continue
        if float(row["edge"]) < threshold:
            continue
        fixture_key = row["fixture_key"]
        assert isinstance(fixture_key, tuple)
        prev = by_fixture.get(fixture_key)
        if prev is None or float(row["edge"]) > float(prev["edge"]):
            by_fixture[fixture_key] = row
    return list(by_fixture.values())


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    wins = sum(1 for r in rows if r["result"] == "win")
    losses = sum(1 for r in rows if r["result"] == "loss")
    pushes = sum(1 for r in rows if r["result"] == "push")
    pnl = sum(float(r["pnl"]) for r in rows)
    staked = sum(1.0 for r in rows if r["result"] != "push")
    roi = (pnl / staked * 100.0) if staked else 0.0
    probs = [float(r["model_prob"]) for r in rows]
    edges = [float(r["edge"]) for r in rows]
    odds = [float(r["odds"]) for r in rows]
    return {
        "n": len(rows),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "pnl": pnl,
        "staked": staked,
        "roi_pct": roi,
        "avg_prob": mean(probs) if probs else 0.0,
        "avg_edge": mean(edges) if edges else 0.0,
        "avg_odds": mean(odds) if odds else 0.0,
        "overs": sum(1 for r in rows if r["side"] == "over"),
        "unders": sum(1 for r in rows if r["side"] == "under"),
    }


def build_summary(scored: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for source in LAMBDA_SOURCES:
        for alpha in ALPHAS:
            for threshold in EDGE_THRESHOLDS:
                selected = select_candidates(scored, source, alpha, threshold)
                stats = summarize(selected)
                output.append(
                    {
                        "scope": "overall",
                        "league": "ALL",
                        "lambda_source": source,
                        "alpha": alpha,
                        "edge_threshold": threshold,
                        **stats,
                    }
                )
                leagues: dict[str, list[dict[str, object]]] = defaultdict(list)
                for row in selected:
                    leagues[str(row.get("league") or "unknown")].append(row)
                for league, league_rows in leagues.items():
                    output.append(
                        {
                            "scope": "league",
                            "league": league,
                            "lambda_source": source,
                            "alpha": alpha,
                            "edge_threshold": threshold,
                            **summarize(league_rows),
                        }
                    )
    output.sort(
        key=lambda r: (
            str(r["scope"]),
            str(r["lambda_source"]),
            float(r["alpha"]),
            float(r["edge_threshold"]),
            str(r["league"]),
        )
    )
    return output


def write_csv(rows: list[dict[str, object]]) -> None:
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scope",
        "league",
        "lambda_source",
        "alpha",
        "edge_threshold",
        "n",
        "wins",
        "losses",
        "pushes",
        "pnl",
        "staked",
        "roi_pct",
        "avg_prob",
        "avg_edge",
        "avg_odds",
        "overs",
        "unders",
    ]
    with REPORT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "alpha": f"{float(row['alpha']):.2f}",
                    "edge_threshold": f"{float(row['edge_threshold']):.2f}",
                    "pnl": round(float(row["pnl"]), 4),
                    "staked": round(float(row["staked"]), 4),
                    "roi_pct": round(float(row["roi_pct"]), 4),
                    "avg_prob": round(float(row["avg_prob"]), 5),
                    "avg_edge": round(float(row["avg_edge"]), 5),
                    "avg_odds": round(float(row["avg_odds"]), 4),
                }
            )


def fmt_stats(row: dict[str, object]) -> str:
    return (
        f"{int(row['n'])} bets, {int(row['wins'])}W/{int(row['losses'])}L/"
        f"{int(row['pushes'])}P, PnL {float(row['pnl']):+.2f}u, "
        f"ROI {float(row['roi_pct']):+.1f}%, avg edge {float(row['avg_edge']) * 100:.1f}%"
    )


def write_report(summary: list[dict[str, object]], priced: int, matched: int) -> None:
    overall = [r for r in summary if r["scope"] == "overall" and int(r["n"]) >= 15]
    overall.sort(key=lambda r: (float(r["roi_pct"]), int(r["n"])), reverse=True)
    stable = [r for r in overall if int(r["n"]) >= 25]
    best = stable[0] if stable else (overall[0] if overall else None)

    league_rows = [r for r in summary if r["scope"] == "league" and int(r["n"]) >= 8]
    bad_leagues = sorted([r for r in league_rows if float(r["roi_pct"]) <= -10.0], key=lambda r: float(r["roi_pct"]))[:10]
    good_leagues = sorted([r for r in league_rows if float(r["roi_pct"]) >= 5.0], key=lambda r: float(r["roi_pct"]), reverse=True)[:10]

    lines = [
        "Team-shots dispersion lab",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Markets input: {MARKETS.relative_to(ROOT)}",
        f"Predictions input: {PREDICTIONS.relative_to(ROOT)}",
        f"Priced market rows: {priced}",
        f"Matched settled rows with prediction lambdas: {matched}",
        "",
        "Method",
        "- Reprices settled team-shot O/U market rows using Poisson and negative-binomial variants.",
        "- Dedupes to one best-edge line per team per fixture for each variant/threshold.",
        "- This tests model probability shape and league gates; it does not change production yet.",
        "",
        "Best overall variants (minimum 15 deduped bets)",
    ]
    if overall:
        for row in overall[:12]:
            lines.append(
                f"- {row['lambda_source']} alpha={float(row['alpha']):.2f} "
                f"edge>={float(row['edge_threshold']) * 100:.0f}%: {fmt_stats(row)}"
            )
    else:
        lines.append("- No variant has enough bets for a read.")

    if best:
        lines.extend(
            [
                "",
                "Current best candidate",
                f"- {best['lambda_source']} alpha={float(best['alpha']):.2f} "
                f"edge>={float(best['edge_threshold']) * 100:.0f}%: {fmt_stats(best)}",
            ]
        )

    lines.extend(["", "League block/watch candidates (minimum 8 bets)"])
    if bad_leagues:
        for row in bad_leagues:
            lines.append(
                f"- Block/watch {row['league']} under {row['lambda_source']} alpha={float(row['alpha']):.2f} "
                f"edge>={float(row['edge_threshold']) * 100:.0f}%: {fmt_stats(row)}"
            )
    else:
        lines.append("- No league bucket reaches a hard negative gate on this sample.")

    lines.extend(["", "League positive watch candidates (minimum 8 bets)"])
    if good_leagues:
        for row in good_leagues:
            lines.append(
                f"- Keep/promote {row['league']} under {row['lambda_source']} alpha={float(row['alpha']):.2f} "
                f"edge>={float(row['edge_threshold']) * 100:.0f}%: {fmt_stats(row)}"
            )
    else:
        lines.append("- No league bucket clears the positive watch threshold yet.")

    lines.extend(
        [
            "",
            "Interpretation",
            "- Negative-binomial alpha > 0 adds over-dispersion; it usually softens extreme Poisson confidence.",
            "- If NB variants outperform current Poisson on stable samples, production should use NB probabilities before calibration.",
            "- League gates should be applied only when the same league stays bad under the best overall variant and the live shadow record agrees.",
        ]
    )
    REPORT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    predictions = load_predictions()
    market_rows, priced, matched = load_market_rows(predictions)
    scored = score_rows(market_rows)
    summary = build_summary(scored)
    write_csv(summary)
    write_report(summary, priced, matched)
    print(f"Wrote {REPORT_TXT}")
    print(f"Wrote {REPORT_CSV}")


if __name__ == "__main__":
    main()
