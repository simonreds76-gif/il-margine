"""
Shared Sackmann/TML -> OnCourt player ID mapping helpers.

Run:
  python scripts/sackmann_tml_id_map.py [--show-unmapped] [--limit 30]
"""

import argparse
import csv
import os
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SACKMANN_DIR = ROOT / "data" / "sackmann"
TML_DIR = ROOT / "tml-data"

# Strip common suffixes before normalization (Jr/Sr/II/III/etc.)
_SUFFIX_RE = re.compile(
    r"(?:,\s*|\s+)(?:jr|sr|junior|senior|ii|iii|iv|v|vi|vii|viii|ix|x|2nd|3rd|4th|5th)\.?$",
    re.IGNORECASE,
)

# Find hyphenated chunks (e.g. ramos-vinolas)
_HYPHEN_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+", re.IGNORECASE)

# Extra folds for chars that NFKD alone won't always solve to desired ASCII
_SPECIAL_FOLDS = str.maketrans(
    {
        "ß": "ss",
        "æ": "ae",
        "Æ": "ae",
        "œ": "oe",
        "Œ": "oe",
        "ø": "o",
        "Ø": "o",
        "đ": "d",
        "Đ": "d",
        "ð": "d",
        "Ð": "d",
        "þ": "th",
        "Þ": "th",
        "ł": "l",
        "Ł": "l",
    }
)


def load_env():
    for name in [".env.local", "env.local"]:
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip().replace("\r", "")
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_supabase_rest():
    url = (os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not url or not key:
        raise RuntimeError("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in .env.local")
    base = f"{url}/rest/v1"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    return base, headers


def _read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def _ascii_fold(text):
    s = str(text or "")
    s = s.translate(_SPECIAL_FOLDS)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("\u2019", "'").replace("`", "'")
    s = s.replace("–", "-").replace("—", "-").replace("‑", "-")
    return s


def _strip_suffixes(name):
    s = str(name or "").strip()
    if not s:
        return ""
    prev = None
    while s and s != prev:
        prev = s
        s = _SUFFIX_RE.sub("", s).strip(" ,.")
    return s


def _normalize_tokens(name):
    s = _ascii_fold(name).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_name(name):
    """
    Public normalizer used by scripts and reports.
    """
    return _normalize_tokens(_strip_suffixes(name))


def _normalized_variants(name):
    """
    Keep both raw-normalized and suffix-stripped normalized variants.
    """
    out = []
    seen = set()
    for raw in (str(name or ""), _strip_suffixes(name)):
        norm = _normalize_tokens(raw)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def _name_keys(name):
    """
    Return (full, first_last, initial_last, first_last_compact, last_only).
    Kept for compatibility.
    """
    norm = normalize_name(name)
    if not norm:
        return "", "", "", "", ""
    toks = norm.split()
    first = toks[0]
    last = toks[-1]

    first_last = f"{first} {last}" if first and last else ""
    initial_last = f"{first[:1]} {last}" if first and last else ""

    # Compact surname prefix variants: "o connell" -> "oconnell"
    first_last_compact = first_last
    if len(toks) >= 2 and toks[-2] in {"o", "mc", "mac"}:
        first_last_compact = f"{first} {toks[-2]}{toks[-1]}"

    return norm, first_last, initial_last, first_last_compact, last


def canonical_surface(surface_raw, indoor_raw=None):
    s = (surface_raw or "").strip().lower()
    indoor = (indoor_raw or "").strip().upper()

    if "clay" in s or "terre" in s:
        return "Clay"
    if "grass" in s:
        return "Grass"
    if "hard" in s:
        if indoor in {"I", "Y", "1", "TRUE", "T"}:
            return "I.hard"
        return "Hard"
    if "indoor" in s and "hard" in s:
        return "I.hard"
    return "N/A"


def parse_tourney_date(value):
    s = (value or "").strip()
    if not s:
        return None
    if re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s[:10]):
        return s[:10]
    return None


def _parse_dob_yyyymmdd(value):
    s = (value or "").strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    return None


def _year_from_iso_date(value):
    s = (value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s[:10]):
        try:
            return int(s[:4])
        except ValueError:
            return None
    return None


def _norm_country(value):
    s = (value or "").strip().upper()
    return s if re.fullmatch(r"[A-Z]{3}", s) else None


def _infer_birth_year_from_age(age_value, tourney_date_value):
    """
    Conservative year inference from age + match date.
    """
    dt = parse_tourney_date(tourney_date_value)
    if not dt:
        return None
    year = _year_from_iso_date(dt)
    if year is None:
        return None

    try:
        age = float(str(age_value or "").strip())
    except (ValueError, TypeError):
        return None
    if age < 12 or age > 60:
        return None

    approx = year - age
    by = int(approx)
    if by < 1900 or by > year:
        return None
    return by


def discover_match_files(tml_min_year=2025, tml_max_year=None):
    sackmann = sorted(p for p in SACKMANN_DIR.glob("atp_matches*.csv") if p.is_file())

    # Keep only one challenger alias per year/type if both *_challenge and *_challenger exist.
    tml_map = {}
    pat = re.compile(r"^(\d{4})(?:_(challenger|challenge))?\.csv$", re.IGNORECASE)
    for p in TML_DIR.glob("*.csv"):
        m = pat.match(p.name)
        if not m:
            continue
        year = int(m.group(1))
        if year < tml_min_year:
            continue
        if tml_max_year is not None and year > tml_max_year:
            continue

        kind = "challenger" if m.group(2) else "main"
        key = (year, kind)
        prev = tml_map.get(key)
        if prev is None:
            tml_map[key] = p
        elif "_challenger" in p.name.lower():
            tml_map[key] = p

    tml = sorted(tml_map.values())
    return sackmann, tml


def iter_match_rows(sackmann_files, tml_files):
    for path in sackmann_files:
        for row in _read_csv(path):
            yield "sackmann", path, row
    for path in tml_files:
        for row in _read_csv(path):
            yield "tml", path, row


def fetch_oncourt_players(base, headers, timeout=60):
    rows = []
    offset = 0
    select = "id,name,birthdate,country"

    # Fallback to id,name if needed.
    probe = requests.get(
        f"{base}/oncourt_players",
        headers=headers,
        params={"select": select, "limit": 1},
        timeout=timeout,
    )
    if probe.status_code == 400:
        select = "id,name"

    while True:
        r = requests.get(
            f"{base}/oncourt_players",
            headers=headers,
            params={"select": select, "limit": 1000, "offset": offset},
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json() or []
        if not data:
            break
        rows.extend(data)
        offset += len(data)
        if len(data) < 1000:
            break
    return rows


def _append_unique(lst, value):
    if value and value not in lst:
        lst.append(value)


def _extract_hyphen_variants(name):
    """
    Extract hyphenated chunks and variants:
      - compact: "ramosvinolas"
      - spaced: "ramos vinolas"
      - parts: ["ramos", "vinolas"]
    """
    out = []
    seen = set()

    for raw in (str(name or ""), _strip_suffixes(name)):
        folded = _ascii_fold(raw).lower()
        for m in _HYPHEN_TOKEN_RE.finditer(folded):
            token = m.group(0)
            parts = [p for p in token.split("-") if p]
            if len(parts) < 2:
                continue
            compact = "".join(parts)
            spaced = " ".join(parts)
            key = (compact, spaced, tuple(parts))
            if key in seen:
                continue
            seen.add(key)
            out.append((compact, spaced, parts))

    return out


def _collect_key_values(name):
    """
    Build ordered key values used for index and source lookups.
    """
    key_values = defaultdict(list)
    first_tokens = []

    for norm in _normalized_variants(name):
        toks = norm.split()
        if not toks:
            continue

        first = toks[0]
        last = toks[-1]
        _append_unique(first_tokens, first)

        _append_unique(key_values["full"], norm)
        _append_unique(key_values["first_last"], f"{first} {last}")
        _append_unique(key_values["initial_last"], f"{first[:1]} {last}")
        _append_unique(key_values["last_only"], last)
        _append_unique(key_values["last_first"], f"{last} {first}")

        compact_last = last
        if len(toks) >= 2 and toks[-2] in {"o", "mc", "mac"}:
            compact_last = toks[-2] + toks[-1]
        _append_unique(key_values["first_last_compact"], f"{first} {compact_last}")

        if len(toks) >= 2:
            last_two = f"{toks[-2]} {toks[-1]}"
            _append_unique(key_values["last_two"], last_two)
            if len(toks) >= 3:
                _append_unique(key_values["first_last_two"], f"{first} {last_two}")

    # Hyphen-specific variants
    for compact, spaced, parts in _extract_hyphen_variants(name):
        _append_unique(key_values["hyphen_compact"], compact)
        _append_unique(key_values["hyphen_space"], spaced)
        for p in parts:
            _append_unique(key_values["hyphen_part"], p)
        for first in first_tokens:
            _append_unique(key_values["first_hyphen_compact"], f"{first} {compact}")
            _append_unique(key_values["first_hyphen_space"], f"{first} {spaced}")

    return key_values


def _build_oncourt_indexes(oncourt_players):
    key_names = [
        "full",
        "first_last",
        "initial_last",
        "first_last_compact",
        "last_only",
        "last_two",
        "first_last_two",
        "last_first",
        "hyphen_compact",
        "hyphen_space",
        "hyphen_part",
        "first_hyphen_compact",
        "first_hyphen_space",
    ]
    indexes = {k: defaultdict(set) for k in key_names}
    pid_to_norm_names = defaultdict(set)
    pid_meta = {}

    for row in oncourt_players:
        pid = row.get("id")
        name = row.get("name")
        if pid is None or not name:
            continue
        pid = int(pid)

        kv = _collect_key_values(name)
        for k in key_names:
            for value in kv.get(k, []):
                indexes[k][value].add(pid)

        for norm in _normalized_variants(name):
            pid_to_norm_names[pid].add(norm)
        for k in ("first_last", "last_first", "first_last_two", "hyphen_space", "first_hyphen_space"):
            for v in kv.get(k, []):
                pid_to_norm_names[pid].add(v)

        bd = (row.get("birthdate") or "").strip()[:10]
        by = _year_from_iso_date(bd)
        ctry = _norm_country(row.get("country"))
        pid_meta[pid] = {"birthdate": bd if by else None, "birth_year": by, "country": ctry}

    return indexes, pid_to_norm_names, pid_meta


def _lookup_unique(index, values):
    for v in values:
        cands = index.get(v, set())
        if len(cands) == 1:
            return next(iter(cands))
    return None


def _collect_candidates(index, values):
    out = set()
    for v in values:
        out |= index.get(v, set())
    return out


def _best_counter_value(counter):
    if not counter:
        return None
    top = counter.most_common(2)
    if len(top) == 1:
        return top[0][0]
    if top[0][1] > top[1][1]:
        return top[0][0]
    return None


def _levenshtein_max(a, b, max_dist=2):
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    if abs(len(a) - len(b)) > max_dist:
        return max_dist + 1

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        row_min = curr[0]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
            if curr[j] < row_min:
                row_min = curr[j]
        if row_min > max_dist:
            return max_dist + 1
        prev = curr
    return prev[-1]


def _is_close_name(source_norm, target_norm, max_dist=2):
    if not source_norm or not target_norm:
        return False
    if source_norm == target_norm:
        return True

    if _levenshtein_max(source_norm, target_norm, max_dist=max_dist) <= max_dist:
        return True

    s_comp = source_norm.replace(" ", "")
    t_comp = target_norm.replace(" ", "")
    if _levenshtein_max(s_comp, t_comp, max_dist=max_dist) <= max_dist:
        return True

    st = source_norm.split()
    tt = target_norm.split()
    if st and tt and st[-1] == tt[-1]:
        if len(st) == len(tt):
            mism = sum(1 for a, b in zip(st, tt) if a != b)
            if mism <= 1:
                return True
        elif abs(len(st) - len(tt)) == 1:
            short = st if len(st) < len(tt) else tt
            long_ = tt if len(st) < len(tt) else st
            i = j = mism = 0
            while i < len(short) and j < len(long_):
                if short[i] == long_[j]:
                    i += 1
                    j += 1
                else:
                    mism += 1
                    j += 1
                    if mism > 1:
                        break
            mism += len(long_) - j
            if mism <= 1:
                return True

    return False


def _disambiguate_with_meta(candidates, source_meta, pid_meta):
    if not candidates or not source_meta:
        return None, None

    working = set(candidates)

    src_ioc = _norm_country(source_meta.get("ioc"))
    src_dob = source_meta.get("dob")
    src_by = source_meta.get("birth_year")

    # Country filter
    if src_ioc:
        m = {pid for pid in working if (pid_meta.get(pid, {}).get("country") == src_ioc)}
        if len(m) == 1:
            return next(iter(m)), "country"
        if len(m) > 1:
            working = m

    # Exact DOB filter
    if src_dob:
        m = {pid for pid in working if (pid_meta.get(pid, {}).get("birthdate") == src_dob)}
        if len(m) == 1:
            return next(iter(m)), "dob"
        if len(m) > 1:
            working = m

    # Birth year exact then +/-1
    if src_by is not None:
        m_exact = {pid for pid in working if (pid_meta.get(pid, {}).get("birth_year") == src_by)}
        if len(m_exact) == 1:
            return next(iter(m_exact)), "birth_year"
        if len(m_exact) > 1:
            working = m_exact
        else:
            m_pm1 = {
                pid
                for pid in working
                if pid_meta.get(pid, {}).get("birth_year") is not None
                and abs(pid_meta[pid]["birth_year"] - src_by) <= 1
            }
            if len(m_pm1) == 1:
                return next(iter(m_pm1)), "birth_year_pm1"
            if len(m_pm1) > 1:
                working = m_pm1

    if len(working) == 1:
        return next(iter(working)), "meta_singleton"

    return None, None


def _resolve_oncourt_id(source_name, indexes, source_meta=None):
    """
    Resolve source name to OnCourt ID.
    Kept compatible with existing signature; source_meta is optional.
    """
    indexes_map, pid_to_norm_names, pid_meta = indexes
    source_kv = _collect_key_values(source_name)

    # Existing strict order + new strict-safe additions
    strict_attempts = [
        ("full", "full", "full"),
        ("first_last", "first_last", "first_last"),
        ("initial_last", "initial_last", "initial_last"),
        ("first_last_compact", "first_last_compact", "first_last_compact"),
        ("last_only", "last_only", "last_only"),
        # new
        ("first_last_two", "first_last_two", "first_last_two"),
        ("last_two", "last_two", "last_two"),
        ("last_first", "last_first", "last_first"),
        # cross order: source first_last against OnCourt last_first index
        ("last_first_cross", "last_first", "first_last"),
        ("first_hyphen_space", "first_hyphen_space", "first_hyphen_space"),
        ("first_hyphen_compact", "first_hyphen_compact", "first_hyphen_compact"),
        ("hyphen_space", "hyphen_space", "hyphen_space"),
        ("hyphen_compact", "hyphen_compact", "hyphen_compact"),
        ("hyphen_part", "hyphen_part", "hyphen_part"),
    ]

    for method, index_key, source_key in strict_attempts:
        vals = source_kv.get(source_key, [])
        if not vals:
            continue

        # strict unique
        pid = _lookup_unique(indexes_map[index_key], vals)
        if pid is not None:
            return pid, method

        # metadata disambiguation on ambiguous candidates per value
        if source_meta:
            for v in vals:
                cands = set(indexes_map[index_key].get(v, set()))
                if len(cands) > 1:
                    pid_meta_resolved, why = _disambiguate_with_meta(cands, source_meta, pid_meta)
                    if pid_meta_resolved is not None:
                        return pid_meta_resolved, f"{method}_meta_{why}"

            # metadata disambiguation on union over method values
            cands_union = _collect_candidates(indexes_map[index_key], vals)
            if len(cands_union) > 1:
                pid_meta_resolved, why = _disambiguate_with_meta(cands_union, source_meta, pid_meta)
                if pid_meta_resolved is not None:
                    return pid_meta_resolved, f"{method}_meta_{why}"

    # Union fallback over all key families
    union_keys = [
        "full",
        "first_last",
        "initial_last",
        "first_last_compact",
        "last_only",
        "first_last_two",
        "last_two",
        "last_first",
        "first_hyphen_space",
        "first_hyphen_compact",
        "hyphen_space",
        "hyphen_compact",
        "hyphen_part",
    ]
    candidates = set()
    for k in union_keys:
        candidates |= _collect_candidates(indexes_map[k], source_kv.get(k, []))
    candidates |= _collect_candidates(indexes_map["last_first"], source_kv.get("first_last", []))  # cross

    if len(candidates) == 1:
        return next(iter(candidates)), "union"

    if len(candidates) > 1 and source_meta:
        pid_meta_resolved, why = _disambiguate_with_meta(candidates, source_meta, pid_meta)
        if pid_meta_resolved is not None:
            return pid_meta_resolved, f"union_meta_{why}"

    # Optional fuzzy: only when weak candidate pool is singleton
    weak_candidates = set()
    for k in ("last_only", "last_two", "hyphen_space", "hyphen_compact", "hyphen_part", "last_first"):
        weak_candidates |= _collect_candidates(indexes_map[k], source_kv.get(k, []))
    weak_candidates |= _collect_candidates(indexes_map["last_first"], source_kv.get("first_last", []))

    if len(weak_candidates) > 1 and source_meta:
        pid_meta_resolved, why = _disambiguate_with_meta(weak_candidates, source_meta, pid_meta)
        if pid_meta_resolved is not None:
            return pid_meta_resolved, f"weak_meta_{why}"

    if len(weak_candidates) == 1:
        pid = next(iter(weak_candidates))
        src_norms = _normalized_variants(source_name)
        tgt_norms = pid_to_norm_names.get(pid, set())
        for s_norm in src_norms:
            for t_norm in tgt_norms:
                if _is_close_name(s_norm, t_norm, max_dist=2):
                    return pid, "fuzzy_singleton"

    return None, None


def _collect_source_profiles(sackmann_files, tml_files, include_sackmann_players=True):
    """
    Build per-(source,id) profile:
      names counter, ioc counter, dob counter, birth_year counter.
    """
    profiles = defaultdict(
        lambda: {
            "names": Counter(),
            "ioc": Counter(),
            "dob": Counter(),
            "birth_year": Counter(),
        }
    )

    for source, _path, row in iter_match_rows(sackmann_files, tml_files):
        tdate = row.get("tourney_date")
        for side in ("winner", "loser"):
            sid = (row.get(f"{side}_id") or "").strip()
            name = (row.get(f"{side}_name") or "").strip()
            if not sid or not name:
                continue

            p = profiles[(source, sid)]
            p["names"][name] += 1

            ioc = _norm_country(row.get(f"{side}_ioc"))
            if ioc:
                p["ioc"][ioc] += 1

            by = _infer_birth_year_from_age(row.get(f"{side}_age"), tdate)
            if by is not None:
                p["birth_year"][by] += 1

    # Add stronger metadata for Sackmann IDs from atp_players.csv
    if include_sackmann_players:
        players_csv = SACKMANN_DIR / "atp_players.csv"
        if players_csv.exists():
            for row in _read_csv(players_csv):
                sid = (row.get("player_id") or "").strip()
                if not sid:
                    continue
                p = profiles[("sackmann", sid)]

                first = (row.get("name_first") or "").strip()
                last = (row.get("name_last") or "").strip()
                full_name = f"{first} {last}".strip()
                if full_name:
                    p["names"][full_name] += 5  # prioritize canonical full name

                ioc = _norm_country(row.get("ioc"))
                if ioc:
                    p["ioc"][ioc] += 5

                dob = _parse_dob_yyyymmdd(row.get("dob"))
                if dob:
                    p["dob"][dob] += 5
                    by = _year_from_iso_date(dob)
                    if by is not None:
                        p["birth_year"][by] += 5

    return profiles


def _collect_source_name_counts(sackmann_files, tml_files, include_sackmann_players=True):
    """
    Back-compat helper: returns {(source,id): Counter(name)}.
    """
    profiles = _collect_source_profiles(
        sackmann_files,
        tml_files,
        include_sackmann_players=include_sackmann_players,
    )
    return {k: v["names"] for k, v in profiles.items()}


def build_player_id_map(base, headers, sackmann_files, tml_files, timeout=60):
    oncourt_players = fetch_oncourt_players(base, headers, timeout=timeout)
    indexes = _build_oncourt_indexes(oncourt_players)
    source_profiles = _collect_source_profiles(sackmann_files, tml_files, include_sackmann_players=True)

    id_map = {}
    method_counts = Counter()
    unmapped = []

    for (source, sid), profile in source_profiles.items():
        names_counter = profile.get("names", Counter())
        if not names_counter:
            unmapped.append((source, sid, ""))
            continue

        best_name = sorted(names_counter.items(), key=lambda x: (x[1], len(x[0])), reverse=True)[0][0]
        source_meta = {
            "ioc": _best_counter_value(profile.get("ioc", Counter())),
            "dob": _best_counter_value(profile.get("dob", Counter())),
            "birth_year": _best_counter_value(profile.get("birth_year", Counter())),
        }

        oncourt_id, method = _resolve_oncourt_id(best_name, indexes, source_meta=source_meta)
        if oncourt_id is None:
            unmapped.append((source, sid, best_name))
            continue

        id_map[(source, sid)] = oncourt_id
        method_counts[method] += 1

    report = {
        "oncourt_players": len(oncourt_players),
        "source_ids_total": len(source_profiles),
        "mapped_ids": len(id_map),
        "unmapped_ids": len(unmapped),
        "unmapped_examples": unmapped[:200],
        "method_counts": dict(method_counts),
        "mapped_by_source": {
            "sackmann": sum(1 for (src, _sid) in id_map if src == "sackmann"),
            "tml": sum(1 for (src, _sid) in id_map if src == "tml"),
        },
        "total_by_source": {
            "sackmann": sum(1 for (src, _sid) in source_profiles if src == "sackmann"),
            "tml": sum(1 for (src, _sid) in source_profiles if src == "tml"),
        },
    }
    return id_map, report


def main():
    parser = argparse.ArgumentParser(description="Preview Sackmann/TML -> OnCourt ID mapping.")
    parser.add_argument("--show-unmapped", action="store_true")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--tml-min-year", type=int, default=2025)
    parser.add_argument("--tml-max-year", type=int, default=None)
    args = parser.parse_args()

    load_env()
    base, headers = get_supabase_rest()
    sackmann_files, tml_files = discover_match_files(args.tml_min_year, args.tml_max_year)
    id_map, report = build_player_id_map(base, headers, sackmann_files, tml_files)

    print(f"Sackmann files: {len(sackmann_files)}")
    print(f"TML files: {len(tml_files)}")
    print(f"OnCourt players: {report['oncourt_players']:,}")
    print(f"Source IDs: {report['source_ids_total']:,}")
    print(f"Mapped IDs: {report['mapped_ids']:,}")
    print(f"Unmapped IDs: {report['unmapped_ids']:,}")
    print(f"Methods: {report['method_counts']}")
    print(f"Mapped Sackmann: {report['mapped_by_source']['sackmann']:,} / {report['total_by_source']['sackmann']:,}")
    print(f"Mapped TML: {report['mapped_by_source']['tml']:,} / {report['total_by_source']['tml']:,}")

    if args.show_unmapped and report["unmapped_examples"]:
        print("\nUnmapped examples:")
        for src, sid, name in report["unmapped_examples"][: args.limit]:
            print(f"  {src}:{sid} -> {name}")


if __name__ == "__main__":
    main()
