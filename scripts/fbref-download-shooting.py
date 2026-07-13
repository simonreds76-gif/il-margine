#!/usr/bin/env python3
"""Deprecated compatibility shim for ``understat-download-shots.py``.

Scheduled jobs and documentation should use the corrected Understat filename.
This path remains temporarily so older local commands fail safe rather than
silently losing the refresh step.
"""

from __future__ import annotations

import runpy
import warnings
from pathlib import Path


warnings.warn(
    "fbref-download-shooting.py is deprecated; use understat-download-shots.py",
    DeprecationWarning,
    stacklevel=2,
)
runpy.run_path(str(Path(__file__).with_name("understat-download-shots.py")), run_name="__main__")
