"""Six pure extraction controls, with a test-local adjacent-membership oracle.

Only owned finite inputs are used; no historical source or private paths.
Full reachability states, operation counters and independent checker remain.
"""
from copy import deepcopy
from itertools import product
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from countcuts import frontier, frontier_check


def owned_cases():
    rows = [
        ([3], ['fifo'], 'priority', [1], 1, None, None),
        ([3], ['lifo'], 'wrr', [3], 2, None, None),
        ([2, 2], ['fifo', 'lifo'], 'rr', [1, 1], 2, None, None),
        ([2, 2], ['lifo', 'fifo'], 'wrr', [2, 1], 1, None, None),
        ([3, 1], ['lifo', 'lifo'], 'priority', [1, 1], 2, (0, 1), None),
        ([1, 3], ['fifo', 'fifo'], 'rr', [1, 1], 1, (1, 0), None),
        ([2, 2], ['fifo', 'lifo'], 'wrr', [1, 2], 2, (1, 1), [[1, 1, 0], [1, 1, 0]]),
        ([3, 1], ['lifo', 'fifo'], 'rr', [1, 1], 2, (1, 1), [[3, 0, 0], [0, 1, 0]]),
    ]
    result = []
    for index, (lengths, disciplines, policy, weights, capacity, budget, totals) in enumerate(rows):
        result.append({'id': 'projection-' + str(index), 'classes': 3, 'horizon': 4,
                       'lengths': lengths, 'disciplines': disciplines, 'policy': policy,
                       'weights': weights, 'sink_capacity': capacity,
                       'environment': {'kind': 'free'} if budget is None else
                           {'kind': 'budget', 'up_stalls': budget[0], 'down_stalls': budget[1]},
                       'queries': [{'time': t, 'class': col} for t, col in
                                   ((4, 0), (2, 1), (4, 0), (3, 2), (3, 1))],
                       'library': [[g, r] for g, n in enumerate(lengths) for r in range(1, n)],
                       'workload': {'kind': 'full'} if totals is None else {'kind': 'hist', 'totals': totals}})
    return result


def direct_layers(case):
    """Enumerate complete four-tick service words through actual token queues."""
    layers = [set() for _ in range(case['horizon'] + 1)]
    for sequence in product(product((0, 1), repeat=2), repeat=case['horizon']):
        env = case['environment']
        if env['kind'] == 'budget' and (sum(1-a for a, _ in sequence) > env['up_stalls'] or
                                        sum(1-b for _, b in sequence) > env['down_stalls']):
            continue
        sources = [[(g, rank) for rank in range(n)] for g, n in enumerate(case['lengths'])]
        calendar = [g for g in range(len(sources)) for _ in range(case['weights'][g]
                    if case['policy'] == 'wrr' else 1)]
        pointer = up = down = transferred = 0
        sink, departed = [], []
        layers[0].add((0, 0, 0, 0))
        for t, (a, b) in enumerate(sequence, 1):
            if env['kind'] == 'budget':
                up += 1-a; down += 1-b
            if b and sink:
                departed.append(sink.pop(0))
            if a and len(sink) < case['sink_capacity'] and any(sources):
                if case['policy'] == 'priority':
                    group = min(g for g in range(len(sources)) if sources[g])
                else:
                    while not sources[calendar[pointer]]:
                        pointer = (pointer + 1) % len(calendar)
                    group = calendar[pointer]; pointer = (pointer + 1) % len(calendar)
                sink.append(sources[group].pop(0 if case['disciplines'][group] == 'fifo' else -1))
                transferred += 1
            layers[t].add((transferred, len(departed), up, down))
    return layers


def membership_reference(case, layers, word):
    """Adjacent departed-membership changes; not producer prefix counts."""
    records = []
    for qi, query in enumerate(case['queries']):
        layer = layers[query['time']]
        for d in {state[1] for state in layer}:
            canonical = min(state for state in layer if state[1] == d)
            departed = set(map(tuple, word[:d]))
            for g, length in enumerate(case['lengths']):
                palette = set(range(case['classes'])) if case['workload']['kind'] == 'full' else {
                    col for col, count in enumerate(case['workload']['totals'][g]) if count}
                if query['class'] not in palette or len(palette) < 2:
                    continue
                for r in range(1, length):
                    if ((g, r-1) in departed) != ((g, r) in departed):
                        records.append((query['time'], qi, g, r, canonical))
    return sorted(records)


class OpportunityProjectionRegression(unittest.TestCase):
    def test_full_layers_and_membership_reference(self):
        for case in owned_cases():
            layers, _, _ = frontier.explore(case)
            self.assertEqual(layers, direct_layers(case))
            word = frontier.merge_word(case)
            self.assertEqual(frontier.opportunities(case, layers, word), membership_reference(case, layers, word))

    def test_first_canonical_state_and_unmodified_arguments(self):
        shared = 0
        for case in owned_cases():
            layers, _, _ = frontier.explore(case); word = frontier.merge_word(case)
            snapshot = deepcopy((case, layers, word))
            records = frontier.opportunities(case, layers, word)
            for t, _, _, _, state in records:
                peers = [s for s in layers[t] if s[1] == state[1]]
                self.assertEqual(state, min(peers))
                shared += len(peers) > 1
            self.assertEqual((case, layers, word), snapshot)
        self.assertGreater(shared, 0)

    def test_all_cuts_earliest_missing_witness_and_checker(self):
        for case in owned_cases():
            layers, _, _ = frontier.explore(case); word = frontier.merge_word(case)
            records = membership_reference(case, layers, word)
            certificate, stats = frontier.synthesize(case)
            self.assertEqual(certificate['required'], [list(cut) for cut in sorted({r[2:4] for r in records})])
            checked = frontier_check.check(case, certificate)
            self.assertEqual(checked['transitions'], stats['transitions'])
            for missing in certificate['required']:
                negative = deepcopy(case); negative['library'].remove(missing)
                cert, actual = frontier.synthesize(negative)
                first = next(r for r in records if list(r[2:4]) == missing)
                self.assertEqual(cert['status'], 'insufficient_library')
                self.assertEqual(cert['earliest_failure'], first[0])
                self.assertEqual(cert['witness']['query'], first[1])
                self.assertEqual(cert['witness']['cut'], missing)
                self.assertEqual(actual, stats)
                frontier_check.check(negative, cert)

    def test_query_identity_and_inactive_palettes(self):
        for case in owned_cases():
            layers, _, _ = frontier.explore(case); word = frontier.merge_word(case)
            records = frontier.opportunities(case, layers, word)
            # Duplicate endpoints/classes keep separate query identities.
            self.assertEqual([(g, r, s) for _, qi, g, r, s in records if qi == 0],
                             [(g, r, s) for _, qi, g, r, s in records if qi == 2])
            if case['workload']['kind'] == 'hist':
                self.assertFalse(any(case['queries'][qi]['class'] == 2 for _, qi, _, _, _ in records))
        self.assertEqual(frontier.opportunities(case, layers, word), [])  # Both sources monochromatic.

    def test_full_states_not_merged_and_exact_transition_limits(self):
        case = owned_cases()[2]
        layers, parents, total = frontier.explore(case)
        self.assertTrue(any(len(layer) > len({s[1] for s in layer}) for layer in layers))
        self.assertTrue(any(len({s[0]-s[1] for s in layer if s[1] == d}) > 1
                            for layer in layers for d in {s[1] for s in layer}))
        self.assertEqual(frontier.explore(case, max_transitions=total), (layers, parents, total))
        for cap in (0, 1, total-1):
            with self.assertRaisesRegex(RuntimeError, '^INCOMPLETE: frontier transition budget exhausted$'):
                frontier.explore(case, max_transitions=cap)
        cert, _ = frontier.synthesize(case)
        with self.assertRaisesRegex(frontier_check.Rejected, '^INCOMPLETE: checker transition budget exhausted$'):
            frontier_check.check(case, cert, max_transitions=total-1)

    def test_checker_rejects_missing_fabricated_and_late_evidence(self):
        case = owned_cases()[2]; certificate, _ = frontier.synthesize(case)
        bad = deepcopy(certificate); bad['layers'][2].pop()
        with self.assertRaises(frontier_check.Rejected): frontier_check.check(case, bad)
        bad = deepcopy(certificate); bad['layers'][1].append([0, 0, 0, 0])
        with self.assertRaises(frontier_check.Rejected): frontier_check.check(case, bad)
        bad = deepcopy(certificate); bad['required'].clear()
        with self.assertRaises(frontier_check.Rejected): frontier_check.check(case, bad)
        bad = deepcopy(certificate); bad['witnesses'][0]['time'] = 1
        with self.assertRaises(frontier_check.Rejected): frontier_check.check(case, bad)


if __name__ == '__main__':
    unittest.main(verbosity=2)
