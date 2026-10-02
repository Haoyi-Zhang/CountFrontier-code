"""Offline synthesis and separate certificate checking for retained bounded models."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

MAX_INPUT_BYTES = 2 * 1024 * 1024


def read_json(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError('input must be a regular JSON file of at most 2 MiB')
    value = json.loads(path.read_text(encoding='utf-8'))
    if type(value) is not dict:
        raise ValueError('top-level JSON must be an object')
    return value


def limits() -> None:
    """One worker and the same POSIX limits as the campaign runner."""
    import resource
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (110, 110))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('synthesize', 'check'))
    parser.add_argument('--family', required=True, choices=('fixed', 'frontier', 'restricted'))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--case', help='Exact identifier in inputs/cases.json')
    source.add_argument('--input', type=Path, help='Standalone model dictionary')
    parser.add_argument('--certificate', type=Path, help='Required for check')
    parser.add_argument('--output', type=Path, help='New file; never overwrites an existing file')
    args = parser.parse_args()
    try:
        limits()
        if args.operation == 'check' and args.certificate is None:
            raise ValueError('check requires --certificate')
        if args.operation == 'synthesize' and args.certificate is not None:
            raise ValueError('synthesize does not accept --certificate')
        if args.input:
            model = read_json(args.input)
        else:
            path = Path(__file__).resolve().parents[1] / 'inputs' / 'cases.json'
            cases = read_json(path)[args.family]
            matches = [c for c in cases if c.get('id') == args.case]
            if len(matches) != 1:
                raise ValueError('case identifier is missing or ambiguous')
            model = matches[0]
        # In check mode no producer is imported.
        if args.family == 'frontier':
            from .frontier_check import check
        elif args.family == 'fixed':
            from .checker import check
        else:
            from .restricted_check import check
        if args.operation == 'check':
            envelope = read_json(args.certificate)
            certificate = envelope.get('certificate', envelope)
            result = {'status': 'accepted', 'decision': certificate.get('status'),
                      'case': model['id'], 'checker': check(model, certificate)}
        else:
            if args.family == 'frontier':
                from .frontier import synthesize
            elif args.family == 'fixed':
                from .engine import synthesize
            else:
                from .restricted import synthesize
            certificate, statistics = synthesize(model)
            result = {'case': model['id'], 'certificate': certificate,
                      'producer': statistics, 'checker': check(model, certificate)}
        text = json.dumps(result, indent=2, sort_keys=True) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8') as f:
                f.write(text)
        else:
            sys.stdout.write(text)
        return 0
    except (ValueError, TypeError, KeyError, IndexError, OSError, RuntimeError,
            MemoryError, ImportError, OverflowError, RecursionError) as error:
        status = 'INCOMPLETE' if isinstance(error, (MemoryError, ImportError)) or 'INCOMPLETE' in str(error) else 'rejected'
        print(json.dumps({'status': status, 'reason': str(error)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
