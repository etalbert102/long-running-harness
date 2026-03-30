"""Agent-ID Harness — Autonomous coding orchestrator."""

import sys
from pathlib import Path

_FIDELITY_DIR = Path(__file__).resolve().parent.parent.parent.parent / "fidelity_framework"
if _FIDELITY_DIR.is_dir() and str(_FIDELITY_DIR) not in sys.path:
    sys.path.insert(0, str(_FIDELITY_DIR))
