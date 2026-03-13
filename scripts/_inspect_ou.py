import re
html = open("data/pinnacle-html/pinnacle-20260302-005934.html", encoding="utf-8").read()

# Find first over-under and show context
idx = html.find('data-test-id="over-under"')
if idx > 0:
    start = max(0, idx - 200)
    end = min(len(html), idx + 600)
    print("=== FIRST OVER-UNDER CONTEXT ===")
    print(html[start:end])
    print()

# Find what's inside the over-under div
matches = list(re.finditer(r'data-test-id="over-under"', html))
print(f"Found {len(matches)} over-under sections")
for i, m in enumerate(matches[:2]):
    s = m.start()
    chunk = html[s:s+500]
    print(f"\n=== O/U #{i+1} ===")
    print(chunk)

# Check for 22.5 or similar lines
lines = re.findall(r'(?:1[5-9]|2[0-9]|3[0-5])\.5', html)
print(f"\nO/U line values found: {lines[:20]}")

# Check ATP/WTA text
atp_matches = re.findall(r'ATP|WTA|Men|Women', html, re.I)
print(f"\nLeague mentions: {atp_matches[:20]}")
