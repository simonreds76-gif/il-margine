"""Conservative compatibility for extra tennis score detail in historical refreshes."""
import re


def score_detail_enrichment(previous, candidate):
    """Allow missing tie-break detail to be added, never a score/result correction."""
    pattern = r'\d+-\d+(?:\(\d+\))?(?:\s+\d+-\d+(?:\(\d+\))?)*'
    if not all(isinstance(s, str) and re.fullmatch(pattern, s.strip())
               for s in (previous, candidate)):
        return False
    parse = lambda s: re.findall(r'(\d+)-(\d+)(?:\((\d+)\))?', s)
    old, new = parse(previous), parse(candidate)
    if len(old) != len(new):
        return False
    for (a, b, detail), (x, y, added) in zip(old, new):
        if (a, b) != (x, y) or (detail and detail != added):
            return False
        if detail != added and {int(a), int(b)} != {6, 7}:
            return False
    return True

