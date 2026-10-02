#!/usr/bin/env python3
"""Compare deterministic scientific content, excluding run-dependent timing/RSS.

This is a comparison of two executed campaigns, not another scientific oracle.
No model is simulated, and no certificate is accepted solely by this comparison.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path

VOLATILE = {'producer_cpu_ns', 'checker_cpu_ns', 'cpu_seconds', 'wall_seconds',
            'peak_rss_kib', 'timed_cpu_seconds', 'whole_process_cpu_seconds',
            'executed_obligations_this_invocation', 'resumed'}


def scientific(value):
    if isinstance(value, dict):
        return {k: scientific(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [scientific(v) for v in value]
    return value


def compare(left: Path, right: Path) -> dict:
    left_files = {p.relative_to(left) for p in left.rglob('*.json')}
    right_files = {p.relative_to(right) for p in right.rglob('*.json')}
    if not left_files or left_files != right_files:
        raise ValueError('result JSON sets differ or are empty')
    for relative in sorted(left_files):
        a = json.loads((left / relative).read_text())
        b = json.loads((right / relative).read_text())
        if scientific(a) != scientific(b):
            raise ValueError(f'scientific result differs: {relative}')
    with (left / 'case_table.csv').open() as f:
        a = [scientific(r) for r in csv.DictReader(f)]
    with (right / 'case_table.csv').open() as f:
        b = [scientific(r) for r in csv.DictReader(f)]
    if a != b:
        raise ValueError('scientific case table differs')
    return {'status': 'scientific_results_equal', 'json_files_compared': len(left_files),
            'case_table_rows_compared': len(a), 'new_scientific_executions': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left', type=Path)
    parser.add_argument('right', type=Path)
    args = parser.parse_args()
    print(json.dumps(compare(args.left, args.right), indent=2))
