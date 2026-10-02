#!/usr/bin/env python3
"""Regenerate the independent exhaustive frontier micro-audit."""
from __future__ import annotations
import json
from pathlib import Path
from countcuts.frontier_audit import run

BASE = Path(__file__).resolve().parents[1]
models = json.loads((BASE / 'inputs' / 'exhaustive_frontier_audit.json').read_text())
print(json.dumps(run(models), indent=2, sort_keys=True))
