#!/usr/bin/env python3
"""Recompute every published figure from data/measures.jsonl.

Kept at the repository root because the manuscript cites it by name. The
implementation lives in src/policyprop; this is a thin wrapper.

    python3 verify_numbers.py     # exits non-zero if any figure disagrees
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from policyprop.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["verify"]))
