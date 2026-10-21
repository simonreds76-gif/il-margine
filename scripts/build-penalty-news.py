"""Build factual penalty news without loading reviews or changing club hierarchies.

The collector is a batch job, never a website request. Only completed top-five
league matches with shot-level evidence are published. Failed sources preserve
the last validated articles and return a failing exit code for the operator.
"""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import gzip
import json
from pathlib import Path
import re
import time
import unicodedata
import requests
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from penalty_news_context import incident_context, match_context

ROOT = Path(__file__).resolve().parents[1]
LEAGUES = {47: ("epl", "Premier League"), 55: ("serie-a", "Serie A"),
           87: ("la-liga", "La Liga"), 54: ("bundesliga", "Bundesliga"), 53: ("ligue-1", "Ligue 1")}
OUTCOMES = {"Goal": "scored", "AttemptSaved": "saved", "ShotSaved": "saved", "Miss": "missed", "Post": "woodwork"}


def slug(value):
    value = unicodedata.normalize("NFKD", value.replace("&", " and "))
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def read(path, fallback):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else fallback


def atomic_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def normalize(payload, source_url, observed_at, club_map, commentary=None, notes=None):
    q = payload.get("props", {}).get("pageProps", {})
    g, h, c = q.get("general", {}), q.get("header", {}), q.get("content", {})
    league = LEAGUES.get(g.get("leagueId"))
    status = h.get("status", {})
    if not league or g.get("finished") is not True or status.get("finished") is not True:
        raise ValueError("Not a completed supported league match")
    if status.get("cancelled") or status.get("awarded"):
        raise ValueError("Cancelled or awarded match")
    teams = h.get("teams", [])
    if len(teams) != 2 or any(type(t.get("score")) is not int for t in teams):
        raise ValueError("Missing final score")
    if commentary and [commentary.get('HometeamId'), commentary.get('AwayteamId')] != [t['id'] for t in teams]:
        raise ValueError('Commentary belongs to different teams')
    shots = c.get("shotmap", {}).get("shots")
    if not isinstance(shots, list):
        raise ValueError("Missing shot map")
    match_id = str(g["matchId"])
    match_date = g["matchTimeUTCDate"][:10]
    articles, excluded, seen = [], [], set()
    penalty_shots = [s for s in shots if s.get("situation") == "Penalty" and s.get("period") != "PenaltyShootout"]
    for shot in penalty_shots:
        sid = str(shot.get("id") or "")
        if sid in seen:
            continue
        seen.add(sid)
        team = next((t for t in teams if t["id"] == shot.get("teamId")), None)
        outcome = OUTCOMES.get(shot.get("eventType"))
        # Do not guess whether two near-identical attempts were retakes.
        ambiguous = any(other.get("id") != shot.get("id") and other.get("teamId") == shot.get("teamId")
                        and abs(int(other.get("min", 0)) - int(shot.get("min", 0))) <= 2 for other in penalty_shots)
        if not sid or not team or not outcome or not shot.get("playerId") or ambiguous:
            excluded.append({"matchId": match_id, "eventId": sid, "reason": "ambiguous_retaken_or_incomplete_penalty"})
            continue
        minute = int(shot.get("min") or 0)
        if not minute or not (shot.get("fullName") or shot.get("playerName")):
            excluded.append({"matchId": match_id, "eventId": sid, "reason": "missing_taker_or_minute"})
            continue
        added = shot.get("minAdded")
        minute_label = str(minute) + (f"+{added}" if added else "")
        player = shot.get("fullName") or shot["playerName"]
        opponent = next(t for t in teams if t["id"] != team["id"])
        club = club_map.get(str(team["id"]))
        if not club:
            excluded.append({"matchId": match_id, "eventId": sid, "reason": "unmapped_club"})
            continue
        verb = {"scored": "converted a penalty", "saved": "had a penalty saved", "missed": "missed a penalty", "woodwork": "hit the woodwork with a penalty"}[outcome]
        title_verb = {"scored": "scores from the spot", "saved": "has penalty saved", "missed": "misses from the spot", "woodwork": "hits the woodwork from the spot"}[outcome]
        score = f"{teams[0]['name']} {teams[0]['score']}–{teams[1]['score']} {teams[1]['name']}"
        incident = incident_context(shot, commentary or {}, notes or {})
        stats, keeper, moment, context = match_context(c, shot, teams, penalty_shots)
        sentences = [f"{player} {verb} for {club['name']} in minute {minute_label} against {opponent['name']}.",
                     f"The match finished {score}."]
        incident_text = incident['sentence'] if incident else ''
        if keeper and outcome == 'saved':
            incident_text += f' {keeper} kept out the spot kick.'
        if moment and outcome == 'scored':
            after = moment['after']
            own = 0 if team['id'] == teams[0]['id'] else 1
            diff = after[own] - after[1-own]
            impact = 'brought the sides level' if diff == 0 else 'put the team ahead' if diff == 1 else 'extended the lead' if diff > 1 else 'reduced the deficit'
            incident_text += f" The goal {impact} at {after[own]}–{after[1-own]}."
        suffix = 'th' if 10 <= minute % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(minute % 10, 'th')
        when = f'in the {minute}{suffix} minute' if not added else f'in added time ({minute_label} minutes)'
        own_score, other_score = team['score'], opponent['score']
        result = f"{own_score}–{other_score} draw with" if own_score == other_score else f"{own_score}–{other_score} win over" if own_score > other_score else f"{own_score}–{other_score} defeat to"
        lead = f"{player} {verb} {when} of {club['name']}’s {result} {opponent['name']}."
        paragraphs = [lead] + ([incident_text.strip()] if incident_text.strip() else []) + ([' '.join(context)] if context else [])
        raw = {"general": g, "teams": teams, "shot": shot, "incident": incident, "stats": stats, "keeper": keeper, "moment": moment, "paragraphs": paragraphs}
        articles.append({"id": f"fotmob:{match_id}:{sid}", "slug": f"{match_date}-{slug(player)}-{match_id}-{sid}",
                         "matchId": match_id, "eventId": sid, "date": match_date, "kickoff": g["matchTimeUTCDate"],
                         "league": league[0], "leagueLabel": league[1], "round": str(g.get("matchRound") or ""),
                         "player": player, "playerId": shot["playerId"], "portrait": f"https://images.fotmob.com/image_resources/playerimages/{shot['playerId']}.png",
                         "club": club["name"], "clubSlug": slug(club["name"]), "clubUrl": f"/penalty-takers/{league[0]}/{slug(club['name'])}",
                         "crest": club["logo"], "opponent": opponent["name"], "home": teams[0]["name"], "away": teams[1]["name"],
                         "homeScore": teams[0]["score"], "awayScore": teams[1]["score"], "minute": minute_label,
                         "outcome": outcome, "title": f"{player} {title_verb} against {opponent['name']}", "sentences": sentences,
                         "cause": incident['type'] if incident else None, "incident": incident, "stats": stats, "keeper": keeper, "moment": moment, "paragraphs": paragraphs,
                         "sourceUrl": source_url, "sourceHash": hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest(),
                         "publishedAt": observed_at, "updatedAt": observed_at})
    return match_id, articles, excluded


def merge(existing, fresh, completed_ids):
    old = {a["id"]: a for a in existing}
    merged = [a for a in existing if a["matchId"] not in completed_ids]
    for item in fresh:
        article = dict(item)
        prior = old.get(article["id"])
        if prior:
            article["publishedAt"] = prior["publishedAt"]
            article["slug"] = prior["slug"]
            article["updatedAt"] = prior["updatedAt"] if article["sourceHash"] == prior["sourceHash"] else article["updatedAt"]
        merged.append(article)
    return sorted(merged, key=lambda a: (a["kickoff"], int(a["minute"].split("+")[0]), a["id"]), reverse=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / "src/data/penalty-news.json")
    parser.add_argument("--evidence-dir", type=Path, default=ROOT / "outputs/penalty-news-capture")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.days <= 8:
        parser.error("Use a bounded 1–8 day window")
    now = datetime.now(timezone.utc).isoformat()
    logo_map = read(ROOT / "data/goalscorer/team-logo-map.json", {})
    clubs = {str(v["fotmob_team_id"]): {"name": k, "logo": v.get("logo_path") or f"https://images.fotmob.com/image_resources/logo/teamlogo/{v['fotmob_team_id']}.png"}
             for league in logo_map.get("leagues", {}).values() for k, v in league.get("teams", {}).items() if v.get("fotmob_team_id")}
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    def get(url):
        for attempt in range(3):
            response = session.get(url, timeout=30)
            if response.status_code not in (429, 500, 502, 503, 504):
                response.raise_for_status()
                return response
            time.sleep(2 ** attempt)
        response.raise_for_status()
    errors, excluded, fresh, completed = [], [], [], set()
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    notes = read(ROOT / 'data/penalty-news/editorial-evidence.json', {})
    match_ids = set()
    for offset in range(args.days):
        day = (date.fromisoformat(args.end_date) - timedelta(days=offset)).strftime("%Y%m%d")
        path = args.evidence_dir / f"fixtures-{day}.json"
        try:
            fixtures = read(path, {}) if args.offline else get(f"https://www.fotmob.com/api/data/matches?date={day}&timezone=Europe/London").json()
            if not isinstance(fixtures.get("leagues"), list):
                raise ValueError("Missing fixture list")
            if not args.offline:
                atomic_write(path, fixtures)
            for league in fixtures["leagues"]:
                if league.get("id") in LEAGUES:
                    match_ids.update(str(m["id"]) for m in league.get("matches", []) if m.get("status", {}).get("finished") is True)
        except Exception as exc:
            errors.append({"date": day, "reason": str(exc)})
    for mid in sorted(match_ids):
        path = args.evidence_dir / f"match-{mid}.json"
        try:
            if args.offline:
                packet = read(path, {})
            else:
                info = get(f"https://www.fotmob.com/api/data/match?id={mid}").json()
                url = "https://www.fotmob.com" + info["pageUrl"]
                html = get(url).text
                found = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
                if not found:
                    raise ValueError("Missing match payload")
                packet = {"sourceUrl": url, "observedAt": now, "payload": json.loads(found.group(1))}
                atomic_write(path, packet)
            q = packet['payload']['props']['pageProps']
            commentary = {}
            if any(s.get('situation') == 'Penalty' for s in q.get('content', {}).get('shotmap', {}).get('shots', [])):
                cp = args.evidence_dir / f'commentary-{mid}.json'
                if not args.offline:
                    langs = q.get('content', {}).get('liveticker', {}).get('langs', '').split(',')
                    lang = 'en' if 'en' in langs else 'en_gen' if 'en_gen' in langs else None
                    if lang:
                        url = f'https://data.fotmob.com/webcl/ltc/gsm/{mid}_{lang}.json.gz'
                        body = get(url).content
                        if body[:2] == b'\x1f\x8b':
                            body = gzip.decompress(body)
                        atomic_write(cp, {'sourceUrl': url, 'observedAt': now, 'payload': json.loads(body)})
                commentary = read(cp, {}).get('payload', {})
            match_id, articles, omitted = normalize(packet["payload"], packet["sourceUrl"], packet["observedAt"], clubs, commentary, notes)
            for article in articles:
                article['updatedAt'] = now
            completed.add(match_id)
            fresh.extend(articles)
            excluded.extend(omitted)
            if articles:
                print(f"Match {mid}: {len(articles)} verified penalties")
        except Exception as exc:
            errors.append({"matchId": mid, "reason": str(exc)})
    previous = read(args.output, {"articles": []})
    articles = merge(previous["articles"], fresh, completed)
    report = {"checkedAt": now, "windowEnd": args.end_date, "days": args.days, "matchesChecked": len(completed),
              "matchesExpected": len(match_ids), "articles": len(articles), "errors": errors, "excluded": excluded}
    report['incidentCoverage'] = {'verified': sum(bool(a.get('incident')) for a in fresh), 'total': len(fresh),
                                  'missing': [a['id'] for a in fresh if not a.get('incident')]}
    atomic_write(args.evidence_dir / "report.json", report)
    # Fail closed as a batch: never publish a partially refreshed news feed.
    if errors or excluded:
        print(json.dumps(report, ensure_ascii=False))
        raise SystemExit(1)
    old_articles = {a["id"]: a for a in previous["articles"]}
    changes = [{"id": a["id"], "previous": old_articles[a["id"]], "replacement": a} for a in articles
               if a["id"] in old_articles and a["sourceHash"] != old_articles[a["id"]]["sourceHash"]]
    removed = [a for a in previous["articles"] if a["matchId"] in completed and a["id"] not in {v["id"] for v in articles}]
    if changes or removed:
        atomic_write(args.evidence_dir / f"corrections-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.json", {"changedAt": now, "changes": changes, "removed": removed})
    atomic_write(args.output, {"schemaVersion": 1, "generatedAt": now, "coverageStart": min((a["date"] for a in articles), default=args.end_date),
                              "checkedThrough": args.end_date, "matchesChecked": len(completed), "articles": articles})
    print(f"Saved {len(articles)} articles from {len(completed)} completed matches")


if __name__ == "__main__":
    main()
