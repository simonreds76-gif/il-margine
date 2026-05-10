#!/usr/bin/env python3
"""Upload Fair Odds Lab public JSON artifacts to Vercel Blob.

The public page can read these stable Blob URLs at runtime, so model refreshes
do not require a production deployment promotion. The script intentionally
skips when BLOB_READ_WRITE_TOKEN is absent unless --require-token is passed,
which keeps existing scheduled jobs safe while Blob is being configured.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACTS = (
    ("signals", ROOT / "public" / "fair-odds-lab" / "signals.json", "fair-odds-lab/signals.json"),
    ("highlights", ROOT / "public" / "fair-odds-lab" / "highlights.json", "fair-odds-lab/highlights.json"),
)


def load_blob_client() -> Any:
    try:
        from vercel.blob import BlobClient  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on CI/local env
        raise SystemExit(
            "Missing Python package 'vercel'. Install with: pip install vercel"
        ) from exc
    return BlobClient()


def validate_json_file(path: Path) -> bytes:
    data = path.read_bytes()
    json.loads(data.decode("utf-8"))
    return data


def upload_file(client: Any, label: str, path: Path, pathname: str, cache_seconds: int) -> str:
    body = validate_json_file(path)
    blob = client.put(
        pathname,
        body,
        access="public",
        content_type="application/json",
        overwrite=True,
        cache_control_max_age=cache_seconds,
    )
    url = getattr(blob, "url", None)
    if not url and isinstance(blob, dict):
        url = blob.get("url")
    if not url:
        raise RuntimeError(f"Vercel Blob upload for {label} succeeded without returning a URL")
    print(f"{label}: {path.relative_to(ROOT)} -> {url}")
    return str(url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload Fair Odds Lab artifacts to Vercel Blob")
    parser.add_argument("--token-env", default="BLOB_READ_WRITE_TOKEN", help="Environment variable holding the Blob RW token")
    parser.add_argument("--require-token", action="store_true", help="Fail if the Blob token is missing")
    parser.add_argument("--cache-seconds", type=int, default=60, help="Blob public cache max-age for these JSON files")
    args = parser.parse_args()

    token = os.environ.get(args.token_env, "").strip()
    if not token:
        message = f"{args.token_env} is not set; skipping Fair Odds Lab Blob upload."
        if args.require_token:
            raise SystemExit(message)
        print(f"::warning::{message}")
        return

    client = load_blob_client()
    uploaded: dict[str, str] = {}
    for label, path, pathname in DEFAULT_ARTIFACTS:
        if not path.exists():
            print(f"::warning::{path.relative_to(ROOT)} missing; skipping {label} upload.")
            continue
        uploaded[label] = upload_file(client, label, path, pathname, args.cache_seconds)

    if uploaded:
        print("Fair Odds Lab Blob upload complete.")
        if "signals" in uploaded:
            print(f"Set FAIR_ODDS_LAB_ARTIFACT_URL={uploaded['signals']} in Vercel runtime env.")
        if "highlights" in uploaded:
            print(f"Set FAIR_ODDS_LAB_HIGHLIGHTS_URL={uploaded['highlights']} in Vercel runtime env.")


if __name__ == "__main__":
    main()
