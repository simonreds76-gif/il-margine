"""Tournament and venue mapping for Clay ML v3 Phase A."""

from __future__ import annotations

import re
import unicodedata


def normalize_key(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


# Raw backtest / tennis-data / TennisAbstract names and common variants -> canonical tournament key.
TOURNAMENT_ALIAS = {
    "argentina open": "argentina_open",
    "buenos aires": "argentina_open",
    "buenos aires open": "argentina_open",
    "bmw open": "bmw_open",
    "munich": "bmw_open",
    "munich open": "bmw_open",
    "barcelona open": "barcelona_open",
    "barcelona open banc sabadell": "barcelona_open",
    "barcelona": "barcelona_open",
    "chile open": "chile_open",
    "santiago": "chile_open",
    "cordoba open": "cordoba_open",
    "cordoba": "cordoba_open",
    "croatia open": "croatia_open",
    "umag": "croatia_open",
    "estoril open": "estoril_open",
    "millennium estoril open": "estoril_open",
    "estoril": "estoril_open",
    "european open": "european_open",
    "hamburg": "european_open",
    "hamburg european open": "european_open",
    "french open": "french_open",
    "roland garros": "french_open",
    "nd garros": "french_open",
    "garros": "french_open",
    "generali open": "generali_open",
    "kitzbuhel": "generali_open",
    "kitzbuehel": "generali_open",
    "geneva open": "geneva_open",
    "geneva": "geneva_open",
    "grand prix hassan ii": "grand_prix_hassan_ii",
    "marrakech": "grand_prix_hassan_ii",
    "internazionali bnl d italia": "internazionali_bnl_ditalia",
    "italian open": "internazionali_bnl_ditalia",
    "rome masters": "internazionali_bnl_ditalia",
    "rome": "internazionali_bnl_ditalia",
    "lyon open": "lyon_open",
    "lyon": "lyon_open",
    "monte carlo masters": "monte_carlo_masters",
    "monte carlo": "monte_carlo_masters",
    "rolex monte carlo masters": "monte_carlo_masters",
    "mutua madrid open": "mutua_madrid_open",
    "madrid masters": "mutua_madrid_open",
    "madrid": "mutua_madrid_open",
    "nordea open": "nordea_open",
    "bastad": "nordea_open",
    "swedish open": "nordea_open",
    "rio open": "rio_open",
    "rio de janeiro": "rio_open",
    "serbia open": "serbia_open",
    "belgrade": "serbia_open",
    "srpska open": "srpska_open",
    "banja luka": "srpska_open",
    "suisse open gstaad": "suisse_open_gstaad",
    "gstaad": "suisse_open_gstaad",
    "tiriac open": "tiriac_open",
    "bucharest": "tiriac_open",
    "u s men s clay court championships": "us_mens_clay_court_championships",
    "us men s clay court championships": "us_mens_clay_court_championships",
    "houston": "us_mens_clay_court_championships",
}


TOURNAMENT_VENUE = {
    "argentina_open": "buenos_aires_lawn_tennis_club",
    "bmw_open": "mtc_iphitos_munich",
    "barcelona_open": "real_club_tenis_barcelona",
    "chile_open": "club_deportivo_uc_san_carlos",
    "cordoba_open": "polo_deportivo_kempes_cordoba",
    "croatia_open": "stella_maris_umag",
    "estoril_open": "clube_tenis_estoril",
    "european_open": "am_rothenbaum_hamburg",
    "french_open": "roland_garros_paris",
    "generali_open": "tennisstadion_kitzbuhel",
    "geneva_open": "tennis_club_geneve",
    "grand_prix_hassan_ii": "royal_tennis_club_marrakech",
    "internazionali_bnl_ditalia": "foro_italico_rome",
    "lyon_open": "parc_tete_or_lyon",
    "monte_carlo_masters": "monte_carlo_country_club",
    "mutua_madrid_open": "madrid_caja_magica",
    "nordea_open": "bastad_tennis_stadium",
    "rio_open": "jockey_club_brasileiro_rio",
    "serbia_open": "novak_tennis_center_belgrade",
    "srpska_open": "national_tennis_center_banja_luka",
    "suisse_open_gstaad": "roy_emerson_arena_gstaad",
    "tiriac_open": "nastase_marica_sports_club_bucharest",
    "us_mens_clay_court_championships": "river_oaks_houston",
}


def canonical_tournament_key(value: str | None) -> str | None:
    key = normalize_key(value)
    if not key:
        return None
    if key in TOURNAMENT_ALIAS:
        return TOURNAMENT_ALIAS[key]
    # TennisAbstract sometimes carries suffixes or sponsor variants; try containment as a fallback.
    for alias, canonical in sorted(TOURNAMENT_ALIAS.items(), key=lambda item: len(item[0]), reverse=True):
        if alias and (alias in key or key in alias):
            return canonical
    return None


def venue_key_for_tournament(value: str | None) -> str | None:
    canonical = canonical_tournament_key(value)
    if canonical is None:
        return None
    return TOURNAMENT_VENUE.get(canonical)
