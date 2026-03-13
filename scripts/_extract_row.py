import re, sys
with open("data/pinnacle-html/pinnacle-no-ou-20260301-203226.html", encoding="utf-8") as f:
    html = f.read()
# Find gameInfo blocks
pattern = r'<div[^>]*gameInfo[^>]*>.*?</div></div></div>'
matches = re.findall(pattern, html[:200000])
print(f"Found {len(matches)} gameInfo blocks")
if matches:
    print("=== FIRST ROW ===")
    print(matches[0][:3000])

# Also find market/price/button patterns
pattern2 = r'market-btn|price|moneyline|over-under|totalGames|Total Games'
found = re.findall(pattern2, html, re.I)
from collections import Counter
c = Counter(found)
print("\n=== Pattern counts ===")
for k, v in c.most_common(20):
    print(f"  {k}: {v}")

# Find all unique data-test-id values
dti = re.findall(r'data-test-id="([^"]+)"', html)
c2 = Counter(dti)
print("\n=== data-test-id values ===")
for k, v in c2.most_common(30):
    print(f"  {k}: {v}")
