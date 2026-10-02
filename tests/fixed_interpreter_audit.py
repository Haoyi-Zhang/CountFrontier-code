#!/usr/bin/env python3
"""Cross-check both fixed-schedule interpreters on every retained fixed case.

The producer represents physical queues as explicit deques.  The standalone
checker instead represents each token by a location and insertion timestamp.
This audit compares their complete event multisets and their independently
constructed query-coefficient matrices.  Event-list order within a tick is not
semantically observable by the fixed query language, so the comparison keeps
multiplicity while ignoring record enumeration order.
"""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import NoReturn

from countcuts import checker, engine

BASE = Path(__file__).resolve().parents[1]


def fail(case_id: str, message: str) -> NoReturn:
    raise RuntimeError(f"{case_id}: {message}")


def main() -> None:
    retained = json.loads((BASE / "inputs" / "cases.json").read_text(encoding="utf-8"))
    cases = retained.get("fixed")
    if not isinstance(cases, list) or not cases:
        raise RuntimeError("retained input does not contain a nonempty fixed-case list")

    producer_records = 0
    checker_records = 0
    coefficient_cells = 0
    for case in cases:
        case_id = case.get("id", "<missing-id>")
        producer_trace, producer_ticks = engine.run(case)
        checker_trace, checker_ticks = checker.replay(case)
        if producer_ticks != checker_ticks:
            fail(case_id, "interpreter horizons disagree")

        producer_events = Counter(tuple(event) for event in producer_trace)
        checker_events = Counter(tuple(event) for event in checker_trace)
        if producer_events != checker_events:
            missing = list((producer_events - checker_events).elements())[:5]
            extra = list((checker_events - producer_events).elements())[:5]
            fail(case_id, f"event multisets disagree; producer-only={missing}; checker-only={extra}")

        producer_matrix = engine.coefficients(case, producer_trace)
        checker_matrix = checker.matrix(case, checker_trace)
        if producer_matrix != checker_matrix:
            fail(case_id, "query-coefficient matrices disagree")

        producer_records += len(producer_trace)
        checker_records += len(checker_trace)
        coefficient_cells += sum(
            len(class_weights)
            for token_matrix in producer_matrix
            for class_weights in token_matrix
        )

    report = {
        "status": "all_fixed_interpreter_audits_passed",
        "fixed_cases": len(cases),
        "producer_event_records": producer_records,
        "checker_event_records": checker_records,
        "coefficient_cells": coefficient_cells,
        "comparison": "event multisets plus independently constructed coefficient matrices",
        "scope": "retained fixed-schedule cases; finite cross-implementation audit, not a general proof",
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
