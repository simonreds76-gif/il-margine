"""Altitude helpers for Clay ML v3 Phase A."""

from __future__ import annotations

from dataclasses import dataclass

from .clay_v3_venues import VenueGeo


@dataclass(frozen=True)
class AltitudeCoverage:
    required_venues: int
    resolved_venues: int
    unresolved_venues: list[str]
    low_altitude_defaults: list[str]

    @property
    def coverage(self) -> float:
        return self.resolved_venues / self.required_venues if self.required_venues else 1.0


def altitude_coverage(required_venue_keys: set[str], venue_geo: dict[str, VenueGeo]) -> AltitudeCoverage:
    unresolved = sorted(key for key in required_venue_keys if key not in venue_geo)
    resolved = sorted(key for key in required_venue_keys if key in venue_geo)
    low_defaults = sorted(
        key for key in resolved if venue_geo[key].altitude_m == 0 and "manual" in venue_geo[key].source.lower()
    )
    return AltitudeCoverage(
        required_venues=len(required_venue_keys),
        resolved_venues=len(resolved),
        unresolved_venues=unresolved,
        low_altitude_defaults=low_defaults,
    )
