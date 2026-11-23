"""Resolve the exact stadium before retrieving a private match-window forecast."""
from datetime import datetime, timezone
import requests

COUNTRIES = {"Premier League":{"Q145","Q21","Q25"},"Bundesliga":{"Q183"},"Serie A":{"Q38"},
             "La Liga":{"Q29"},"Ligue 1":{"Q142","Q235"}}
AGENT = {"User-Agent":"IlMargineFixtureResearch/1.0 (partners@ilmargine.bet)"}


def weather(f):
    name = f.get("venue")
    if not name:
        return None
    try:
        api = "https://www.wikidata.org/w/api.php"
        def wiki(params):
            r=requests.get(api,params={"format":"json",**params},headers=AGENT,timeout=6)
            r.raise_for_status()
            return r.json()
        rows=wiki(dict(action="wbsearchentities",search=name,language="en",limit=5)).get("search",[])
        ids=[a["id"] for a in rows if str(a.get("label","")).casefold()==name.casefold()]
        if not ids:
            return None
        entities=wiki(dict(action="wbgetentities",ids="|".join(ids),props="claims")).get("entities",{})
        places=[]
        for entity in entities.values():
            claims=entity.get("claims",{})
            def values(prop):
                return [c["mainsnak"]["datavalue"]["value"] for c in claims.get(prop,[])
                        if c.get("rank")!="deprecated" and "datavalue" in c.get("mainsnak",{})]
            countries={x.get("id") for x in values("P17")}
            coords=values("P625")
            if countries & COUNTRIES[f["league"]] and len(coords)==1:
                places.append(coords[0])
        if len(places)!=1:
            return None
        xy=places[0]
        r=requests.get("https://api.met.no/weatherapi/locationforecast/2.0/compact",
              params=dict(lat=round(xy["latitude"],4),lon=round(xy["longitude"],4)),headers=AGENT,timeout=8)
        r.raise_for_status()
        props=r.json()["properties"]
        ko=datetime.fromisoformat(f["ko"])
        nearest=min(props["timeseries"],key=lambda t:abs((datetime.fromisoformat(t["time"])-ko).total_seconds()))
        if abs((datetime.fromisoformat(nearest["time"])-ko).total_seconds())>3600:
            return None
        vals=nearest["data"]["instant"]["details"]
        return dict(venue=name,at=nearest["time"],issued=props["meta"].get("updated_at"),
                    temperatureC=vals.get("air_temperature"),windMS=vals.get("wind_speed"),
                    nextHourRainMM=nearest["data"].get("next_1_hours",{}).get("details",{}).get("precipitation_amount"),
                    attribution="MET Norway, CC BY 4.0; Wikidata coordinates",officialPitchInspection="unknown")
    except (requests.RequestException,ValueError,TypeError,KeyError,IndexError):
        return None
