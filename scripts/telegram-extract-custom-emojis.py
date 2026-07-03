#!/usr/bin/env python3
"""Extract Telegram custom emoji IDs from messages sent to a bot.

Usage:
  1. Send a private message to the bot with lines like:
       bet365 🟢
       virginbet 🔴
  2. Set WORLD_CUP_TELEGRAM_BOT_TOKEN in the environment or .env.local.
  3. Run:
       python scripts/telegram-extract-custom-emojis.py

The script prints a JSON-ish mapping you can copy into the site code.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_NAMES = (
    "WORLD_CUP_TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "OPS_ALERT_TELEGRAM_BOT_TOKEN",
)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def bot_api(token: str, method: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {})
    url = f"https://api.telegram.org/bot{token}/{method}"
    if query:
        url = f"{url}?{query}"
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        raise RuntimeError(json.dumps(payload, indent=2))
    return payload


def utf16_to_py_index(text: str, utf16_offset: int) -> int:
    """Convert Telegram UTF-16 code-unit offsets to Python string indexes."""
    units = 0
    for index, char in enumerate(text):
        if units >= utf16_offset:
            return index
        units += 2 if ord(char) > 0xFFFF else 1
    return len(text)


def entity_span(text: str, entity: dict[str, Any]) -> tuple[int, int]:
    offset = int(entity.get("offset") or 0)
    length = int(entity.get("length") or 0)
    start = utf16_to_py_index(text, offset)
    end = utf16_to_py_index(text, offset + length)
    return start, end


def entity_text(text: str, entity: dict[str, Any]) -> str:
    start, end = entity_span(text, entity)
    return text[start:end]


def extract_from_message(message: dict[str, Any]) -> list[dict[str, str]]:
    text = str(message.get("text") or message.get("caption") or "")
    entities = message.get("entities") or message.get("caption_entities") or []
    found: list[dict[str, str]] = []
    lines = text.splitlines() or [text]
    for entity in entities:
        if entity.get("type") != "custom_emoji":
            continue
        start, end = entity_span(text, entity)
        label = ""
        consumed = 0
        for line in lines:
            line_end = consumed + len(line)
            if consumed <= start <= line_end:
                local_start = max(0, start - consumed)
                local_end = max(local_start, end - consumed)
                label = (line[:local_start] + line[local_end:]).strip(" :-–—\t").strip()
                break
            consumed = line_end + 1
        found.append(
            {
                "label": label or "unknown",
                "custom_emoji_id": str(entity.get("custom_emoji_id") or ""),
                "sample": entity_text(text, entity),
            }
        )
    return found


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract custom emoji IDs from Telegram bot updates.")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env.local")
    parser.add_argument("--token-env", action="append", default=[])
    parser.add_argument("--limit", type=int, default=50)
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    load_dotenv(args.env_file)
    env_names = tuple(args.token_env) + DEFAULT_ENV_NAMES
    token = next((os.environ.get(name, "").strip() for name in env_names if os.environ.get(name, "").strip()), "")
    if not token:
        print(
            "Missing bot token. Set WORLD_CUP_TELEGRAM_BOT_TOKEN in .env.local or the current shell.",
            file=sys.stderr,
        )
        return 2

    updates = bot_api(token, "getUpdates", {"limit": str(args.limit), "allowed_updates": json.dumps(["message"])})
    rows: list[dict[str, str]] = []
    for update in updates.get("result") or []:
        message = update.get("message")
        if isinstance(message, dict):
            rows.extend(extract_from_message(message))

    if not rows:
        print("No custom emojis found in recent bot messages.")
        print("Send a private message to the bot like: bet365 [custom emoji]")
        return 1

    print("Found custom emoji IDs:")
    for row in rows:
        print(f"- {row['label']}: {row['custom_emoji_id']} ({row['sample']})")

    print("\nSuggested mapping:")
    print("{")
    seen: set[str] = set()
    for row in rows:
        key = row["label"].lower().replace(" ", "").replace("-", "")
        if not key or key in seen:
            continue
        seen.add(key)
        print(f'  "{key}": "{row["custom_emoji_id"]}",')
    print("}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
