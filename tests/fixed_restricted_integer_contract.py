"""Finite regression for accepted fixed/restricted certificate integer fields."""
from copy import deepcopy
from itertools import product
import json
from pathlib import Path

from countcuts import checker, restricted, restricted_check

BASE = Path(__file__).resolve().parents[1]


def ensure(ok, message):
    if not ok:
        raise AssertionError(message)


def reject(check, exception, case, certificate, edit, label):
    changed = deepcopy(certificate)
    edit(changed)
    try:
        check(case, changed)
    except exception:
        return
    except Exception as error:
        raise AssertionError(f'{label}: escaped rejection as {type(error).__name__}') from error
    raise AssertionError(f'{label}: noninteger certificate accepted')


def decode(case, certificate, word):
    # Consume the certified group/start/stop indices, not reconstructed boundaries.
    return tuple(certificate['offset'][q] + sum(
        sum(word[token] == color for token in case['groups'][block['group']][block['start']:block['stop']])
        * block['weights'][q][color]
        for block in certificate['blocks'] for color in range(case['classes']))
        for q in range(len(case['queries'])))


def main():
    row = json.loads((BASE / 'results/observed/fixed/ordered-fifo.json').read_text(encoding='utf-8'))
    case, certificate = row['case'], row['certificate']
    checker.check(case, certificate)
    trace, _ = checker.replay(case)
    words = list(product(range(2), repeat=6))
    for word in words:
        ensure(decode(case, certificate, word) == checker.answers(case, word, trace), 'fixed decoder disagreement')
        checker.abstract(case, word, certificate['cuts'])

    mutations = []
    for field in ('required', 'cuts'):
        for index, values in ((0, (0.0, False)), (1, (4.0, True, 0, 6))):
            for value in values:
                mutations.append((f'{field}/{index}/{value!r}', lambda c, f=field, i=index, v=value: c[f][0].__setitem__(i, v)))
        mutations.append((f'{field}/shape', lambda c, f=field: c[f].__setitem__(0, [0])))
    for field in ('group', 'start', 'stop'):
        original = certificate['blocks'][0][field]
        for value in (float(original), bool(original), -1, 7):
            mutations.append((f'block/{field}/{value!r}', lambda c, f=field, v=value: c['blocks'][0].__setitem__(f, v)))
    for field in ('group', 'rank', 'query'):
        original = certificate['witnesses'][0][field]
        for value in (float(original), bool(original), -1, 80):
            mutations.append((f'witness/{field}/{value!r}', lambda c, f=field, v=value: c['witnesses'][0].__setitem__(f, v)))
    for value in (0.0, False):
        mutations.append((f'offset/{value!r}', lambda c, v=value: c['offset'].__setitem__(0, v)))
        mutations.append((f'weight/{value!r}', lambda c, v=value: c['blocks'][0]['weights'][0].__setitem__(0, v)))
    for label, edit in mutations:
        reject(checker.check, checker.Rejected, case, certificate, edit, label)

    nr = json.loads((BASE / 'results/observed/fixed/scale-00.json').read_text(encoding='utf-8'))
    checker.check(nr['case'], nr['certificate'])
    negative_checks = 0
    for index in (0, 1):
        original = nr['certificate']['missing'][index]
        for value in (float(original), bool(original)):
            reject(checker.check, checker.Rejected, nr['case'], nr['certificate'],
                   lambda c, i=index, v=value: c['missing'].__setitem__(i, v), 'negative/missing')
            negative_checks += 1

    rc = restricted.make_case(2, [[1]], 'integer-positive')
    rb, _ = restricted.synthesize(rc)
    restricted_check.check(rc, rb)
    restricted_checks = 0
    for value in (1.0, True, 0, 3, [1]):
        reject(restricted_check.check, restricted_check.Rejected, rc, rb,
               lambda c, v=value: c['cuts'].__setitem__(0, v), 'restricted/cut')
        restricted_checks += 1
    for field in ('cut', 'context', 'left', 'right'):
        original = rb['private_pairs'][0][field]
        for value in (float(original), bool(original)):
            reject(restricted_check.check, restricted_check.Rejected, rc, rb,
                   lambda c, f=field, v=value: c['private_pairs'][0].__setitem__(f, v), 'restricted/private')
            restricted_checks += 1
    gap = restricted.make_case(2, [[2]], 'integer-negative')
    gap['library'] = [1]
    gb, _ = restricted.synthesize(gap)
    restricted_check.check(gap, gb)
    for value in (0.0, False):
        reject(restricted_check.check, restricted_check.Rejected, gap, gb,
               lambda c, v=value: c['pair'].__setitem__('context', v), 'restricted/negative')
        restricted_checks += 1
    print(json.dumps({'status': 'fixed_restricted_integer_contract_passed',
                      'fixed_decoder_words': len(words),
                      'fixed_positive_rejections': len(mutations),
                      'fixed_negative_rejections': negative_checks,
                      'restricted_rejections': restricted_checks}, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
