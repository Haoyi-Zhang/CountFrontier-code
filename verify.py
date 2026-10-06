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
LOGS: Path | None = None
COMMAND_NUMBER = 0


def run(
    work: Path,
    *args: str,
    expected: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, object]:
    global COMMAND_NUMBER
    COMMAND_NUMBER += 1
    environment = {**os.environ, **(env_overrides or {}), "PYTHONPATH": str(work),
                   "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        completed = subprocess.run(
            [sys.executable, "-B", *args],
            cwd=work,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        if LOGS is not None:
            for stream in ("stdout", "stderr"):
                value = getattr(error, stream) or b""
                if isinstance(value, str):
                    value = value.encode("utf-8")
                (LOGS / f"{COMMAND_NUMBER:02d}.{stream}").write_bytes(value)
        raise
    if LOGS is not None:
        (LOGS / f"{COMMAND_NUMBER:02d}.stdout").write_text(completed.stdout, encoding="utf-8")
        (LOGS / f"{COMMAND_NUMBER:02d}.stderr").write_text(completed.stderr, encoding="utf-8")
        (LOGS / f"{COMMAND_NUMBER:02d}.command.json").write_text(json.dumps({
            "argv": [sys.executable, "-B", *args], "cwd": str(work),
            "returncode": completed.returncode, "environment_overrides": env_overrides or {},
        }, indent=2) + "\n", encoding="utf-8")
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
    all_files = list(work.rglob("*.py"))
    production_files = [path for path in all_files if "tests" not in path.relative_to(work).parts]
    assert_nodes = 0
    for path in all_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if path in production_files:
            assert_nodes += sum(isinstance(node, ast.Assert) for node in ast.walk(tree))
    if assert_nodes:
        raise RuntimeError(f"production source contains {assert_nodes} optimization-sensitive assert statements")
    return {"all_python_files_parsed": len(all_files),
            "production_python_files_parsed": len(production_files),
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
    global LOGS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="retain the temporary copy and print its path")
    parser.add_argument("--work-dir", type=Path, help="new, absent isolation directory; always retained")
    parser.add_argument("--logs", type=Path, help="new, absent directory for raw command outputs")
    args = parser.parse_args()

    if args.logs:
        LOGS = args.logs.resolve()
        LOGS.mkdir(parents=True, exist_ok=False)
    temporary = None if args.work_dir else tempfile.mkdtemp(prefix="countcuts-verify-")
    work = args.work_dir.resolve() if args.work_dir else Path(temporary) / "precision-minimal-count-abstractions"
    try:
        shutil.copytree(
            BASE,
            work,
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "reproduced*", "example-certificate.json"
            ),
        )
        source = source_audit(work)
        commands = [
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
            run(work, "tests/fixed_restricted_integer_contract.py", expected="fixed_restricted_integer_contract_passed"),
        ]
        parsed = parse_all(work)
        report = {
            "status": "all_documented_checks_passed",
            "isolation": "temporary repository copy",
            "commands": commands,
            **source,
            **parsed,
            "scope": "finite execution and deterministic comparison; handwritten general proofs are not mechanized",
        }
        if LOGS is not None:
            (LOGS / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
    finally:
        if args.keep or args.work_dir:
            print(f"temporary_copy={work}", file=sys.stderr)
        else:
            shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    main()
