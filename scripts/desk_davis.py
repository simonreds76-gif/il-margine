"""Davis Cup price-board markets and tie identities in the men's results archive."""
import re
import unicodedata
from datetime import date, datetime

def folded(value):
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.findall(r"[a-z0-9]+", text))

# Federation names and codes from the 2026 Davis Cup nominations. The final
# entries cover alternative country names used on the price board.
FEDERATIONS = """
ALB Albania
ALG Algeria
AND Andorra
ANG Angola
ANT Antigua & Barbuda
ARG Argentina
ARM Armenia
ARU Aruba
AUS Australia
AUT Austria
AZE Azerbaijan
BRN Bahrain
BAN Bangladesh
BAR Barbados
BEL Belgium
BEN Benin
BER Bermuda
BHU Bhutan
BOL Bolivia
BIH Bosnia and Herzegovina
BOT Botswana
BRA Brazil
BRU Brunei
BUL Bulgaria
BDI Burundi
CMR Cameroon
CAN Canada
CHI Chile
CHN China, P.R.
TPE Chinese Taipei
COL Colombia
CGO Congo
COD Congo, Dem. Rep.
CRC Costa Rica
CIV Cote D'Ivoire
CRO Croatia
CUB Cuba
CYP Cyprus
CZE Czechia
DEN Denmark
DOM Dominican Republic
ECU Ecuador
EGY Egypt
ESA El Salvador
EST Estonia
ETH Ethiopia
FIN Finland
FRA France
GAB Gabon
GEO Georgia
GER Germany
GHA Ghana
GBR Great Britain
GRE Greece
GUM Guam
GUA Guatemala
HON Honduras
HKG Hong Kong, China
HUN Hungary
ISL Iceland
IND India
INA Indonesia
IRI Iran
IRQ Iraq
IRL Ireland
ISR Israel
ITA Italy
JAM Jamaica
JPN Japan
JOR Jordan
KAZ Kazakhstan
KEN Kenya
KOR Korea, Rep.
KOS Kosovo
KUW Kuwait
KGZ Kyrgyzstan
LAO Laos
LAT Latvia
LBN Lebanon
LBA Libya
LIE Liechtenstein
LTU Lithuania
LUX Luxembourg
MAC Macau
MAD Madagascar
MAS Malaysia
MDV Maldives
MLT Malta
MTN Mauritania
MEX Mexico
MDA Moldova
MON Monaco
MGL Mongolia
MNE Montenegro
MAR Morocco
MOZ Mozambique
NAM Namibia
NEP Nepal
NED Netherlands
NZL New Zealand
NGR Nigeria
MKD North Macedonia
MNP Northern Mariana Islands
NOR Norway
POC Pacific Oceania
PAK Pakistan
PAR Paraguay
PER Peru
PHI Philippines
POL Poland
POR Portugal
PUR Puerto Rico
QAT Qatar
ROU Romania
RWA Rwanda
SMR San Marino
KSA Saudi Arabia
SEN Senegal
SRB Serbia
SEY Seychelles
SGP Singapore
SVK Slovakia
SLO Slovenia
RSA South Africa
ESP Spain
SRI Sri Lanka
SUR Suriname
SWE Sweden
SUI Switzerland
SYR Syria
TJK Tajikistan
TAN Tanzania
THA Thailand
TOG Togo
TTO Trinidad & Tobago
TUN Tunisia
TUR Turkiye
TKM Turkmenistan
ISV US Virgin Islands
USA USA
UGA Uganda
UKR Ukraine
UAE United Arab Emirates
URU Uruguay
UZB Uzbekistan
VEN Venezuela
VIE Vietnam
YEM Yemen
ZAM Zambia
ZIM Zimbabwe
CHN China
CZE Czech Republic
KOR South Korea
KOR Republic of Korea
GBR United Kingdom
USA United States
USA United States of America
TUR Turkey
TPE Taiwan
HKG Hong Kong
""".strip().splitlines()
COUNTRIES = {}
for entry in FEDERATIONS:
    code, name = entry.split(" ", 1)
    COUNTRIES[folded(name)] = COUNTRIES[code.lower()] = code

DAVIS = re.compile(r"^(?:ATP\s+)?Davis Cup\b", re.I)
STAGES = {"qf":"QF", "quarterfinals":"QF", "quarter finals":"QF",
          "sf":"SF", "semifinals":"SF", "semi finals":"SF", "f":"F", "final":"F",
          "q1":"Q1", "q2":"Q2", "r1":"1R", "r2":"2R", "r16":"R16",
          "qualifiers":"", "qualifying":"", "singles":"", "groups":""}
ARCHIVE = re.compile(r"^Davis Cup,\s*([^,]+),\s*([^,]+),\s*([A-Z]{3})-([A-Z]{3})(?:\s+(\d)-(\d))?$", re.I)

def market(league):
    if not DAVIS.match(league):
        return None
    tail = folded(DAVIS.sub("", league, count=1))
    tail = re.sub(r"^(?:finals|world group)\b\s*", "", tail)
    if tail == "tie winner":
        return "tie"
    if tail in STAGES or not tail:
        return "singles"
    return None

def valid_sides(kind, names):
    codes = [COUNTRIES.get(folded(n)) for n in names]
    if kind == "tie":
        return all(codes) and codes[0] != codes[1]
    return not any(codes) and all(len(folded(n).split()) >= 2 for n in names)

def singles_round(league, archive):
    parsed = ARCHIVE.fullmatch(archive)
    if not parsed or market(league) != "singles":
        return False
    suffix = folded(league.rpartition(" - ")[2])
    stage = STAGES.get(suffix, "")
    return not stage or stage == parsed[2].upper()

def tie_result(ticket, tours, games, now):
    if ticket.get("market", "winner") != "winner" or now < datetime.fromisoformat(ticket["start"].replace("Z", "+00:00")):
        return None
    pair = [COUNTRIES.get(folded(ticket[key])) for key in ("player","opponent")]
    if not all(pair) or pair[0] == pair[1]:
        return None
    day = date.fromisoformat(ticket["start"][:10])
    # The archive edition date is often the Monday of the tournament. Require
    # a played rubber in the tie on its quoted day as an independent date check.
    played = {g["tour_id"] for g in games if (g.get("date") or "")[:10] == day.isoformat() and g.get("result")}
    found = []
    for tid in played:
        row = tours.get(tid)
        parsed = ARCHIVE.fullmatch(row["name"]) if row else None
        if not parsed or set(parsed.group(3,4)) != set(pair):
            continue
        found.append((tid, parsed))
    if len(found) != 1:
        return None
    tid, tie = found[0]
    if tie[5] is None:
        return None
    a,b = int(tie[5]),int(tie[6])
    finals = day.year >= 2019 and tie[1].casefold() == "world group" and tie[2].upper() in {"QF","SF","F"}
    needed = 2 if finals else 3
    if a == b or max(a,b) < needed or a+b > 2*needed-1:
        return None
    picked = a if pair[0] == tie[3] else b
    return (["davis-tie", tid, *pair],
            {"score": f"{tie[3]} {a}-{b} {tie[4]}", "result": "Won" if picked == max(a,b) else "Lost"})
