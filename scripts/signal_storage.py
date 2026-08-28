from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "backtest"


@dataclass(frozen=True)
class SignalCsvPaths:
    legacy: Path
    live: Path
    archive: Path


def derive_signal_csv_paths(path: Path | str) -> SignalCsvPaths:
    requested = Path(path)
    suffix = requested.suffix or ".csv"
    stem = requested.stem

    if stem.endswith("-live"):
        base_stem = stem[:-5]
        live = requested
        archive = requested.with_name(f"{base_stem}-archive{suffix}")
        legacy = requested.with_name(f"{base_stem}{suffix}")
        return SignalCsvPaths(legacy=legacy, live=live, archive=archive)

    if stem.endswith("-archive"):
        base_stem = stem[:-8]
        live = requested.with_name(f"{base_stem}-live{suffix}")
        archive = requested
        legacy = requested.with_name(f"{base_stem}{suffix}")
        return SignalCsvPaths(legacy=legacy, live=live, archive=archive)

    legacy = requested
    live = requested.with_name(f"{stem}-live{suffix}")
    archive = requested.with_name(f"{stem}-archive{suffix}")
    return SignalCsvPaths(legacy=legacy, live=live, archive=archive)


STRICT_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals.csv")
STRICT_INTERNAL_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-internal-5pct.csv")
VOLUME_275_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-volume275.csv")
VOLUME_275_INTERNAL_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-volume275-internal.csv")
VOLUME_200_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-volume200.csv")
VOLUME_200_INTERNAL_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-volume200-internal.csv")
SPREAD_SHADOW_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-spreadshadow.csv")
SPREAD_V1_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-spreadv1.csv")
SPREAD_V1_CLAY_FAV_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-clay-fav.csv")
SLAM_BO5_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-slam-bo5.csv")
LEGACY_CHALLENGER_ML_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-challenger-ml.csv")
CHALLENGER_ML_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-challenger-ml-v2.csv")
CHALLENGER_ML_NEARMISS_PATH = DATA_DIR / "challenger-ml-v2-nearmiss.csv"
CLAY_BO3_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-clay_bo3.csv")
CLAY_BO3_NEARMISS_PATH = DATA_DIR / "clay_bo3-shadow-nearmiss.csv"
GRASS_BO3_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-grass_bo3.csv")
GRASS_BO3_NEARMISS_PATH = DATA_DIR / "grass_bo3-shadow-nearmiss.csv"
CPI_SPEED_SIGNAL_PATHS = derive_signal_csv_paths(DATA_DIR / "strict-signals-cpi_speed.csv")
CPI_SPEED_NEARMISS_PATH = DATA_DIR / "cpi_speed-shadow-nearmiss.csv"

SIGNAL_PROFILE_PATHS: dict[str, tuple[SignalCsvPaths, SignalCsvPaths | None]] = {
    "strict": (STRICT_SIGNAL_PATHS, STRICT_INTERNAL_SIGNAL_PATHS),
    "volume_275": (VOLUME_275_SIGNAL_PATHS, VOLUME_275_INTERNAL_SIGNAL_PATHS),
    "volume_200": (VOLUME_200_SIGNAL_PATHS, VOLUME_200_INTERNAL_SIGNAL_PATHS),
    "spread_shadow": (SPREAD_SHADOW_SIGNAL_PATHS, None),
    "spread_v1_shadow": (SPREAD_V1_SIGNAL_PATHS, None),
    "spread_v1_clay_fav": (SPREAD_V1_CLAY_FAV_SIGNAL_PATHS, None),
    "slam_bo5": (SLAM_BO5_SIGNAL_PATHS, None),
    "challenger_ml_shadow": (CHALLENGER_ML_SIGNAL_PATHS, None),
    "clay_bo3": (CLAY_BO3_SIGNAL_PATHS, None),
    "grass_bo3": (GRASS_BO3_SIGNAL_PATHS, None),
    "cpi_speed_shadow": (CPI_SPEED_SIGNAL_PATHS, None),
}

SIGNALS_CURRENT_JSON = DATA_DIR / "signals-current.json"
