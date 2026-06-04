#!/usr/bin/env python3
"""
Fetch ATP tournament surface-speed proxy ratings from Tennis Abstract and
store them locally (CSV) plus optional Supabase upsert.

Source:
  https://www.tennisabstract.com/reports/atp_surface_speed.html
  https://www.tennisabstract.com/cgi-bin/surface-speed.cgi?year=YYYY

Examples:
  python scripts/scrape-tennisabstract-surface-speed.py
    # default run refreshes current and previous season
  python scripts/scrape-tennisabstract-surface-speed.py --years 2024,2025,2026
  python scripts/scrape-tennisabstract-surface-speed.py --start-year 1991 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Install dependency: pip install beautifulsoup4", file=sys.stderr)
    sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_CSV = ROOT / "data" / "backtest" / "tennisabstract-atp-surface-speed.csv"
DEFAULT_TABLE = "tournament_surface_speed"
SOURCE_URL_FMT = "https://www.tennisabstract.com/cgi-bin/surface-speed.cgi?year={year}"
USER_AGENT = "Mozilla/5.0 (compatible; il-margine-cpi-scraper/1.0)"
REQUEST_TIMEOUT = 35
REQUEST_PAUSE_SEC = 0.8

KNOWN_NAME_FIXES = {
    "nd garros": "Roland Garros",
    "garros": "Roland Garros",
}


def _apply_known_name_fixes(name: str) -> str:
    compact = re.sub(r"[^a-z0-9]+", " ", (name or "").strip().lower()).strip()
    return KNOWN_NAME_FIXES.get(compact, name)


def load_env() -> None:
    for name in ("env.local", ".env.local"):
        path = ROOT / name
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip().replace("\r", "")
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")


def _parse_years_arg(raw: str) -> list[int]:
    years = set()
    for part in (raw or "").split(","):
        p = part.strip()
        if not p:
            continue
        if "-" in p:
            a, b = p.split("-", 1)
            y0 = int(a.strip())
            y1 = int(b.strip())
            lo, hi = min(y0, y1), max(y0, y1)
            for y in range(lo, hi + 1):
                years.add(y)
        else:
            years.add(int(p))
    return sorted(years)


def _normalize_surface(text: str) -> str:
    t = (text or "").strip().lower().replace(".", " ").replace("_", " ").replace("-", " ")
    t = " ".join(t.split())
    if "hard" in t:
        return "Hard"
    if "clay" in t:
        return "Clay"
    if "grass" in t:
        return "Grass"
    return ""


def _parse_float(value: str) -> float | None:
    raw = (value or "").strip().replace(",", "")
    if not raw:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", raw)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    raw = (value or "").strip().replace(",", "")
    if not raw:
        return None
    m = re.search(r"\d+", raw)
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def _tour_key(name: str) -> str:
    name = _apply_known_name_fixes(name)
    raw = (name or "").strip().lower()
    if not raw:
        return ""
    parts = [p.strip() for p in re.split(r"\s*-\s*", raw) if p.strip()]
    core = parts[-1] if len(parts) >= 2 and len(parts[-1]) >= 4 else raw
    core = re.sub(r"\b\d{4}\b", " ", core)
    core = re.sub(r"\b(challenger|qualifiers?|qualifying|qualification|atp|wta)\b", " ", core)
    core = re.sub(r"[^a-z0-9]+", " ", core)
    return " ".join(core.split())


def _extract_sample_size(name: str) -> int | None:
    m = re.search(r"\((\d{1,5})\)\s*$", (name or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _clean_tournament_name(name: str) -> str:
    n = (name or "").strip()
    n = re.sub(r"\s*\((\d{1,5})\)\s*$", "", n).strip()
    n = _apply_known_name_fixes(n)
    return n


def _parse_year_rows_from_html(html: str, season_year: int, source_url: str, scraped_at: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict] = []

    # Primary path: parse tabular rows from HTML.
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue

        cells = [td.get_text("", strip=True) for td in tds]
        surface = ""
        cpi = None
        tournament_raw = ""
        sample_size = None

        # Current format:
        #   Date | Tournament | Surface | Ace% | Surface Speed
        if len(cells) >= 5:
            s = _normalize_surface(cells[2])
            c = _parse_float(cells[4])
            t = cells[1].strip()
            if s and c is not None and t:
                surface = s
                cpi = c
                tournament_raw = t

        # Older/alternate format:
        #   Surface | Rating | Tournament | ...
        if not surface and len(cells) >= 3:
            s = _normalize_surface(cells[0])
            c = _parse_float(cells[1])
            t = cells[2].strip()
            if s and c is not None and t:
                surface = s
                cpi = c
                tournament_raw = t
                if len(cells) >= 4:
                    sample_size = _parse_int(cells[3])

        if not surface or cpi is None:
            continue

        tournament_name = _clean_tournament_name(tournament_raw)
        if not tournament_name:
            continue
        if sample_size is None:
            sample_size = _extract_sample_size(tournament_raw)
        key = _tour_key(tournament_name)
        if not key:
            continue
        out.append(
            {
                "season_year": int(season_year),
                "surface": surface,
                "tournament_name": tournament_name,
                "tournament_key": key,
                "cpi": float(cpi),
                "ta_surface_speed": float(cpi),
                "sample_size": sample_size,
                "source_url": source_url,
                "updated_at": scraped_at,
            }
        )

    if out:
        return out

    # Fallback path: parse text lines if table structure changes.
    # Example line:
    #   Hard 0.95 Indian Wells (ATP Masters 1000) (73)
    txt = soup.get_text("\n")
    for line in txt.splitlines():
        ln = " ".join((line or "").strip().split())
        if not ln:
            continue
        m = re.match(r"^(?:\d+\s*\|\s*)?(Hard|Clay|Grass)\s+(-?\d+(?:\.\d+)?)\s+(.+)$", ln, flags=re.IGNORECASE)
        if not m:
            continue
        surface = _normalize_surface(m.group(1))
        cpi = _parse_float(m.group(2))
        tournament_raw = m.group(3).strip()
        tournament_name = _clean_tournament_name(tournament_raw)
        if not surface or cpi is None or not tournament_name:
            continue
        key = _tour_key(tournament_name)
        if not key:
            continue
        out.append(
            {
                "season_year": int(season_year),
                "surface": surface,
                "tournament_name": tournament_name,
                "tournament_key": key,
                "cpi": float(cpi),
                "ta_surface_speed": float(cpi),
                "sample_size": _extract_sample_size(tournament_raw),
                "source_url": source_url,
                "updated_at": scraped_at,
            }
        )
    return out


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    best: dict[tuple[int, str, str], dict] = {}
    for r in rows:
        key = (int(r["season_year"]), str(r["surface"]), str(r["tournament_key"]))
        prev = best.get(key)
        if prev is None:
            best[key] = r
            continue
        n_prev = int(prev.get("sample_size") or -1)
        n_new = int(r.get("sample_size") or -1)
        if n_new > n_prev:
            best[key] = r
    out = list(best.values())
    out.sort(key=lambda x: (int(x["season_year"]), str(x["surface"]), str(x["tournament_name"])))
    return out


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "season_year",
        "surface",
        "tournament_name",
        "tournament_key",
        "cpi",
        "ta_surface_speed",
        "sample_size",
        "source_url",
        "updated_at",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _upsert_supabase(rows: list[dict], table: str) -> None:
    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment.")

    endpoint = f"{url.rstrip('/')}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    batch_size = 500
    sent = 0
    for i in range(0, len(rows), batch_size):
        # The local CSV keeps ta_surface_speed as a backwards-compatible alias
        # for older research scripts; the Supabase table stores the canonical
        # value as cpi only.
        chunk = [
            {k: v for k, v in row.items() if k != "ta_surface_speed"}
            for row in rows[i : i + batch_size]
        ]
        r = requests.post(endpoint, headers=headers, json=chunk, timeout=45)
        if r.status_code >= 300:
            raise RuntimeError(f"Supabase upsert failed [{r.status_code}]: {r.text[:400]}")
        sent += len(chunk)
    print(f"Upserted {sent:,} rows into '{table}'.")


def _get_with_retry(session: requests.Session, url: str, timeout_s: int, max_attempts: int = 4) -> str:
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(url, timeout=timeout_s)
            if resp.status_code == 429:
                retry_after_raw = resp.headers.get("Retry-After", "").strip()
                try:
                    retry_after = float(retry_after_raw) if retry_after_raw else 0.0
                except ValueError:
                    retry_after = 0.0
                wait_s = max(1.0, retry_after) + (attempt - 1) * 0.75
                time.sleep(wait_s)
                continue
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            last_err = e
            if attempt >= max_attempts:
                break
            time.sleep(0.75 * attempt)
    if last_err is None:
        raise RuntimeError("Unknown HTTP error")
    raise last_err


def main() -> int:
    default_start = max(1991, date.today().year - 1)
    parser = argparse.ArgumentParser(description="Fetch ATP CPI/surface-speed by year from Tennis Abstract.")
    parser.add_argument("--start-year", type=int, default=default_start, help="Start year (default: current-1).")
    parser.add_argument("--end-year", type=int, default=date.today().year, help="End year (default: current year).")
    parser.add_argument("--years", default="", help="Explicit years or ranges, e.g. 2024,2025,2026 or 1991-2026.")
    parser.add_argument("--out-csv", default=str(DEFAULT_OUT_CSV), help="Output CSV path.")
    parser.add_argument("--table", default=DEFAULT_TABLE, help="Supabase target table name.")
    parser.add_argument("--dry-run", action="store_true", help="Do not upsert to Supabase.")
    parser.add_argument("--no-supabase", action="store_true", help="Skip Supabase upsert and only write CSV.")
    parser.add_argument("--timeout", type=int, default=REQUEST_TIMEOUT, help="HTTP timeout seconds.")
    args = parser.parse_args()

    load_env()

    if args.years.strip():
        years = _parse_years_arg(args.years.strip())
    else:
        lo, hi = min(args.start_year, args.end_year), max(args.start_year, args.end_year)
        years = list(range(lo, hi + 1))
    years = [y for y in years if 1980 <= y <= date.today().year]
    if not years:
        print("No years to fetch after filtering.", file=sys.stderr)
        return 2

    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    all_rows: list[dict] = []
    failed: list[int] = []
    for y in years:
        url = SOURCE_URL_FMT.format(year=y)
        try:
            html = _get_with_retry(session, url, timeout_s=max(5, int(args.timeout)))
            rows = _parse_year_rows_from_html(html, y, url, scraped_at)
            if not rows:
                print(f"{y}: 0 rows parsed")
            else:
                print(f"{y}: {len(rows)} rows")
                all_rows.extend(rows)
            time.sleep(REQUEST_PAUSE_SEC)
        except Exception as e:
            failed.append(y)
            print(f"{y}: ERROR {e}", file=sys.stderr)

    if not all_rows:
        print("No rows collected from source. Nothing written.", file=sys.stderr)
        return 1

    rows = _dedupe_rows(all_rows)
    out_csv = Path(args.out_csv)
    _write_csv(out_csv, rows)
    print(f"Wrote {len(rows):,} deduped rows to {out_csv}")

    by_year: dict[int, int] = {}
    for r in rows:
        y = int(r["season_year"])
        by_year[y] = by_year.get(y, 0) + 1
    if by_year:
        min_y = min(by_year)
        max_y = max(by_year)
        print(f"Years covered: {min_y}-{max_y} ({len(by_year)} years)")

    if failed:
        print(f"Failed years: {failed}", file=sys.stderr)

    if args.no_supabase or args.dry_run:
        print("Supabase upsert skipped (--no-supabase or --dry-run).")
        return 0

    try:
        _upsert_supabase(rows, args.table)
    except Exception as e:
        print(f"Supabase upsert error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
