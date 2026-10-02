#!/usr/bin/env python3
"""Run the documented artifact checks in an isolated temporary copy.

The verifier copies the standalone repository to a temporary directory so pilot
scripts and generated certificates cannot modify the retained evidence.  It uses
only the Python standard library and the files shipped in this repository.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent


def run(
    work: Path,
    *args: str,
    expected: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, object]:
    environment = {**os.environ, **(env_overrides or {}), "PYTHONPATH": str(work)}
    completed = subprocess.run(
        [sys.executable, *args],
        cwd=work,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
        env=environment,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): python {' '.join(args)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    if expected is not None and expected not in completed.stdout:
        raise RuntimeError(
            f"command did not report {expected!r}: python {' '.join(args)}\n{completed.stdout}"
        )
    return {
        "command": "python " + " ".join(args),
        "returncode": completed.returncode,
        "expected_marker": expected,
        "stderr_bytes": len(completed.stderr.encode("utf-8")),
        "environment_overrides": env_overrides or {},
    }


def source_audit(work: Path) -> dict[str, int]:
    """Parse shipped Python and forbid optimization-sensitive production asserts."""
    production_files = [
        path for path in work.rglob("*.py")
        if "tests" not in path.relative_to(work).parts
    ]
    assert_nodes = 0
    for path in production_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        assert_nodes += sum(isinstance(node, ast.Assert) for node in ast.walk(tree))
    if assert_nodes:
        raise RuntimeError(f"production source contains {assert_nodes} optimization-sensitive assert statements")
    return {"production_python_files_parsed": len(production_files),
            "production_assert_statements": assert_nodes}


def parse_all(work: Path) -> dict[str, int]:
    json_count = 0
    csv_count = 0
    for path in work.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
        json_count += 1
    for path in work.rglob("*.csv"):
        with path.open(newline="", encoding="utf-8") as handle:
            list(csv.reader(handle))
        csv_count += 1
    return {"json_files_parsed": json_count, "csv_files_parsed": csv_count}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="retain the temporary copy and print its path")
    args = parser.parse_args()

    temporary = tempfile.mkdtemp(prefix="countcuts-verify-")
    work = Path(temporary) / "precision-minimal-count-abstractions"
    try:
        shutil.copytree(
            BASE,
            work,
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "reproduced*", "example-certificate.json"
            ),
        )
        commands = [
            run(work, "-m", "compileall", "-q", "."),
            run(work, "reproduce.py", "--output", "results/reproduced", expected="all_finite_checks_passed"),
            run(
                work,
                "compare_results.py",
                "results/observed",
                "results/reproduced",
                expected="scientific_results_equal",
            ),
            run(
                work,
                "-O",
                "reproduce.py",
                "--output",
                "results/reproduced-optimized",
                expected="all_finite_checks_passed",
                env_overrides={"PYTHONHASHSEED": "17"},
            ),
            run(
                work,
                "compare_results.py",
                "results/observed",
                "results/reproduced-optimized",
                expected="scientific_results_equal",
            ),
            run(
                work,
                "reproduce.py",
                "--output",
                "results/reproduced-hash-seed",
                expected="all_finite_checks_passed",
                env_overrides={"PYTHONHASHSEED": "991"},
            ),
            run(
                work,
                "compare_results.py",
                "results/observed",
                "results/reproduced-hash-seed",
                expected="scientific_results_equal",
            ),
            run(
                work,
                "-m",
                "countcuts",
                "synthesize",
                "--family",
                "frontier",
                "--case",
                "frontier03",
                "--output",
                "results/example-certificate.json",
            ),
            run(
                work,
                "-m",
                "countcuts",
                "check",
                "--family",
                "frontier",
                "--case",
                "frontier03",
                "--certificate",
                "results/example-certificate.json",
                expected="accepted",
            ),
            run(work, "tests/algebraic_pilot.py", expected="passed_bounded_pilot"),
            run(work, "tests/end_to_end_pilot.py", expected="passed_end_to_end_finite_pilot"),
            run(work, "tests/frontier_pilot.py", expected="passed_frontier_finite_pilot"),
            run(work, "tests/exhaustive_frontier_audit.py", expected="all_exhaustive_micro_audits_passed"),
            run(work, "tests/restricted_negative.py", expected="passed"),
            run(work, "tests/fixed_interpreter_audit.py", expected="all_fixed_interpreter_audits_passed"),
            run(work, "tests/frontier_integer_contract.py", expected="strict_frontier_integer_contract_passed"),
        ]
        source = source_audit(work)
        parsed = parse_all(work)
        report = {
            "status": "all_documented_checks_passed",
            "isolation": "temporary repository copy",
            "commands": commands,
            **source,
            **parsed,
            "scope": "finite execution and deterministic comparison; handwritten general proofs are not mechanized",
        }
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        if args.keep:
            print(f"temporary_copy={work}", file=sys.stderr)
        else:
            shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    main()
