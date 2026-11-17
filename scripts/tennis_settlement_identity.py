"""Join explicitly verified archive names to native results without fuzzy matching."""
from collections import defaultdict


def verified_names(players, aliases, tour, normalize):
    owners = defaultdict(set)
    native = {}
    for person in players:
        pid = person.get("id")
        if pid and person.get("name"):
            native[pid] = person
            owners[normalize(person["name"])].add(pid)
    candidates = defaultdict(set)
    for row in aliases:
        pid = row.get("native_id")
        person = native.get(pid, {})
        birth = row.get("native_birthdate")
        if (row.get("tour") != tour or not row.get("archive_id") or not birth
                or birth != row.get("archive_birthdate") or birth != person.get("birthdate")
                or not row.get("country") or row["country"] != person.get("country")
                or not row.get("verified_at") or not row.get("player_name")
                or normalize(row.get("alias")) != normalize(person.get("name"))):
            continue
        candidates[normalize(row["player_name"])].add(pid)
    return {name: (pid, native[pid]["name"]) for name, ids in candidates.items()
            if len(ids | owners[name]) == 1 for pid in ids}


def with_native_aliases(directory, signals, read, normalize, pair_key, load):
    aliases = read(directory.parent / "tennis-props/player-name-aliases.csv")
    translated = []
    requests = []
    for tour in {str(s.get("tour") or "").upper() for s in signals} & {"ATP", "WTA"}:
        names = verified_names(read(directory / f"players_{tour.lower()}.csv"), aliases, tour, normalize)
        for s in signals:
            if str(s.get("tour") or "").upper() != tour:
                continue
            year = str(s.get("date") or "")[:4]
            if not year.isdigit():
                continue
            a, b = s.get("player"), s.get("opponent")
            replacements = {normalize(n): names[normalize(n)] for n in (a, b) if normalize(n) in names}
            if not replacements:
                continue
            native_a = names.get(normalize(a), (None, a))[1]
            native_b = names.get(normalize(b), (None, b))[1]
            original, native = pair_key(a, b), pair_key(native_a, native_b)
            if native == original:
                continue
            translated.append(dict(s, player=native_a, opponent=native_b))
            requests.append((tour, int(year), original, native, {pid: n for n,(pid,_) in replacements.items()}))
    index = load(directory, signals + translated)
    for tour, year, original, native, names in requests:
        dest = index.setdefault((tour, year, original), [])
        for record in index.get((tour, year, native), []):
            ids = {record.get("winner_id"), record.get("loser_id")}
            if not names.keys() <= ids:
                continue
            row = dict(record, _verified_native_alias=True)
            for side in ("winner", "loser"):
                row[side + "_name"] = names.get(row[side + "_id"], row[side + "_name"])
            if row not in dest:
                dest.append(row)
        # The exact original pair may also appear under its native spelling
        # in the opponent's appearances. It cannot prove a replacement/void.
        for person in original:
            for appearance in index.get((tour, year, ("__participant__", person)), []):
                if pair_key(appearance["winner_name"], appearance["loser_name"]) == native:
                    appearance.setdefault("_equivalent_pairs", set()).add(original)
    return index
