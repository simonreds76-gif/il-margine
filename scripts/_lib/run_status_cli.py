"""CLI wrapper for run_status used by PowerShell entrypoints.

Not used by Python callers. They use the run_status() context manager.

Usage:
    python -m scripts._lib.run_status_cli start \\
        --run-id <uuid> --pipeline <name> --trigger-kind schedule

    python -m scripts._lib.run_status_cli complete \\
        --run-id <uuid> --status ok --rows-out 42

    python -m scripts._lib.run_status_cli complete \\
        --run-id <uuid> --status failed \\
        --error-type TimeoutError --error-message "process hung"

Can also be invoked as a path:
    python scripts/_lib/run_status_cli.py start ...

Exit code is always 0, on success and on internal failure. This CLI must
never break the calling pipeline. Errors are logged to stderr only.
"""
from __future__ import annotations

import argparse
import logging
import sys

if __package__ in (None, ""):
    import os

    _here = os.path.dirname(os.path.abspath(__file__))
    _repo_root = os.path.dirname(os.path.dirname(_here))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    from scripts._lib.run_status import cli_insert_running, cli_update_finished
else:
    from .run_status import cli_insert_running, cli_update_finished


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_status_cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start", help="Insert a running row.")
    start.add_argument("--run-id", required=True)
    start.add_argument("--pipeline", required=True)
    start.add_argument("--trigger-kind", default="schedule")

    complete = sub.add_parser("complete", help="Update a row to a terminal status.")
    complete.add_argument("--run-id", required=True)
    complete.add_argument(
        "--status",
        required=True,
        choices=["ok", "failed", "timeout", "aborted"],
    )
    complete.add_argument("--rows-out", type=int, default=None)
    complete.add_argument("--error-type", default=None)
    complete.add_argument("--error-message", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    args = _build_parser().parse_args(argv)

    try:
        if args.cmd == "start":
            cli_insert_running(
                run_id=args.run_id,
                pipeline=args.pipeline,
                trigger_kind=args.trigger_kind,
            )
        elif args.cmd == "complete":
            cli_update_finished(
                run_id=args.run_id,
                status=args.status,
                rows_out=args.rows_out,
                error_type=args.error_type,
                error_message=args.error_message,
            )
    except Exception as exc:
        logging.warning("run_status_cli top-level error: %s", exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
