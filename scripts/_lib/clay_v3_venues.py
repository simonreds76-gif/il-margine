"""Venue geo cache for Clay ML v3 Phase A."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VenueGeo:
    venue_key: str
    venue_name: str
    lat: float
    lon: float
    altitude_m: float
    source: str


# Hand-curated venue coordinates and elevations for the clay tournaments present in
# backtest-results 2022-2024. Altitudes are venue/city-level approximations and are
# explicitly audited by the Phase A report, not treated as official measurements.
VENUE_GEO = {
    "buenos_aires_lawn_tennis_club": VenueGeo("buenos_aires_lawn_tennis_club", "Buenos Aires Lawn Tennis Club", -34.5697, -58.4358, 25.0, "manual:venue_geo_reference"),
    "mtc_iphitos_munich": VenueGeo("mtc_iphitos_munich", "MTTC Iphitos Munich", 48.1800, 11.6030, 520.0, "manual:venue_geo_reference"),
    "real_club_tenis_barcelona": VenueGeo("real_club_tenis_barcelona", "Real Club de Tenis Barcelona", 41.3930, 2.1170, 90.0, "manual:venue_geo_reference"),
    "club_deportivo_uc_san_carlos": VenueGeo("club_deportivo_uc_san_carlos", "Club Deportivo Universidad Catolica San Carlos", -33.3940, -70.5040, 670.0, "manual:venue_geo_reference"),
    "polo_deportivo_kempes_cordoba": VenueGeo("polo_deportivo_kempes_cordoba", "Polo Deportivo Kempes Cordoba", -31.3680, -64.2460, 430.0, "manual:venue_geo_reference"),
    "stella_maris_umag": VenueGeo("stella_maris_umag", "Stella Maris ATP Stadium Umag", 45.4470, 13.5180, 5.0, "manual:venue_geo_reference"),
    "clube_tenis_estoril": VenueGeo("clube_tenis_estoril", "Clube de Tenis do Estoril", 38.7070, -9.3940, 60.0, "manual:venue_geo_reference"),
    "am_rothenbaum_hamburg": VenueGeo("am_rothenbaum_hamburg", "Am Rothenbaum Hamburg", 53.5730, 9.9910, 8.0, "manual:venue_geo_reference"),
    "roland_garros_paris": VenueGeo("roland_garros_paris", "Stade Roland Garros Paris", 48.8470, 2.2490, 35.0, "manual:venue_geo_reference"),
    "tennisstadion_kitzbuhel": VenueGeo("tennisstadion_kitzbuhel", "Tennisstadion Kitzbuhel", 47.4470, 12.3920, 762.0, "manual:venue_geo_reference"),
    "tennis_club_geneve": VenueGeo("tennis_club_geneve", "Tennis Club de Geneve", 46.2080, 6.1660, 375.0, "manual:venue_geo_reference"),
    "royal_tennis_club_marrakech": VenueGeo("royal_tennis_club_marrakech", "Royal Tennis Club de Marrakech", 31.6340, -8.0100, 460.0, "manual:venue_geo_reference"),
    "foro_italico_rome": VenueGeo("foro_italico_rome", "Foro Italico Rome", 41.9299, 12.4563, 20.0, "manual:venue_geo_reference"),
    "parc_tete_or_lyon": VenueGeo("parc_tete_or_lyon", "Parc de la Tete d'Or Lyon", 45.7770, 4.8520, 175.0, "manual:venue_geo_reference"),
    "monte_carlo_country_club": VenueGeo("monte_carlo_country_club", "Monte Carlo Country Club", 43.7517, 7.4408, 50.0, "manual:venue_geo_reference"),
    "madrid_caja_magica": VenueGeo("madrid_caja_magica", "Caja Magica Madrid", 40.3687, -3.6844, 660.0, "manual:venue_geo_reference"),
    "bastad_tennis_stadium": VenueGeo("bastad_tennis_stadium", "Bastad Tennis Stadium", 56.4330, 12.8370, 5.0, "manual:venue_geo_reference"),
    "jockey_club_brasileiro_rio": VenueGeo("jockey_club_brasileiro_rio", "Jockey Club Brasileiro Rio de Janeiro", -22.9710, -43.2240, 5.0, "manual:venue_geo_reference"),
    "novak_tennis_center_belgrade": VenueGeo("novak_tennis_center_belgrade", "Novak Tennis Center Belgrade", 44.8230, 20.4570, 90.0, "manual:venue_geo_reference"),
    "national_tennis_center_banja_luka": VenueGeo("national_tennis_center_banja_luka", "National Tennis Center Banja Luka", 44.7760, 17.1990, 165.0, "manual:venue_geo_reference"),
    "roy_emerson_arena_gstaad": VenueGeo("roy_emerson_arena_gstaad", "Roy Emerson Arena Gstaad", 46.4740, 7.2860, 1050.0, "manual:venue_geo_reference"),
    "nastase_marica_sports_club_bucharest": VenueGeo("nastase_marica_sports_club_bucharest", "Nastase & Marica Sports Club Bucharest", 44.4520, 26.0760, 85.0, "manual:venue_geo_reference"),
    "river_oaks_houston": VenueGeo("river_oaks_houston", "River Oaks Country Club Houston", 29.7510, -95.4300, 20.0, "manual:venue_geo_reference"),
}


FIELDNAMES = ["venue_key", "venue_name", "lat", "lon", "altitude_m", "source"]


def write_venue_geo_csv(path: Path, required_venue_keys: set[str] | None = None) -> list[VenueGeo]:
    keys = sorted(required_venue_keys or set(VENUE_GEO.keys()))
    rows = [VENUE_GEO[key] for key in keys if key in VENUE_GEO]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)
    return rows


def load_venue_geo_csv(path: Path) -> dict[str, VenueGeo]:
    out: dict[str, VenueGeo] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            out[row["venue_key"]] = VenueGeo(
                venue_key=row["venue_key"],
                venue_name=row["venue_name"],
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                altitude_m=float(row["altitude_m"]),
                source=row.get("source", ""),
            )
    return out
