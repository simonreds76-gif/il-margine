import re
html = open("data/pinnacle-html/pinnacle-20260302-005934.html", encoding="utf-8").read()

# Find ALL over-under sections and check what line values they contain
matches = list(re.finditer(r'data-test-id="over-under"', html))
print(f"Total over-under sections: {len(matches)}")
for i, m in enumerate(matches):
    s = m.start()
    # Get next 800 chars
    chunk = html[s:s+800]
    # Find title values (these are the line numbers)
    titles = re.findall(r'title="([^"]+)"', chunk)
    prices = re.findall(r'class="price[^"]*">([^<]+)<', chunk)
    labels = re.findall(r'class="label[^"]*">([^<]+)<', chunk)
    print(f"\n  O/U #{i+1}: titles={titles}, prices={prices}, labels={labels[:5]}")

# Where are the 21.5 values?
print("\n=== Where 21.5 appears ===")
for m in re.finditer(r'21\.5', html):
    start = max(0, m.start()-100)
    snippet = html[start:m.start()+100]
    print(f"  ...{snippet}...")
    print()

# Check WTA vs ATP in URLs
urls = re.findall(r'href="(/en/tennis/[^"]+)"', html)
print(f"\n=== Tennis URLs ({len(urls)}) ===")
for u in set(urls[:20]):
    print(f"  {u}")
