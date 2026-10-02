"""Independent exhaustive micro-model audit for symbolic frontier certificates.

For each retained small model, this module enumerates every admitted initial
coloring, every valid service-bit word, and every subset of the ambient source
cuts.  Its direct packet simulator and abstraction-key construction do not
import producer or checker helpers.  The producer, standalone checker, and
numeric evaluator are invoked only after the direct oracle has computed the
expected result.
"""
from __future__ import annotations

from copy import deepcopy
from itertools import combinations, permutations, product
from typing import Any, Iterable

from . import frontier, frontier_check
from .frontier_eval import encode, evaluate


def _histogram(length: int, reverse: bool) -> list[int]:
    values = [(length + 1) // 2, length // 2]
    return list(reversed(values)) if reverse else values


def models() -> list[dict[str, Any]]:
    """Coverage-designed small models; exhaustive claims apply within each one."""
    # lengths, disciplines, policy, weights, sink capacity, environment,
    # workload kind, horizon.  The table deliberately crosses all supported
    # policy/discipline/environment modes without pretending to exhaust the
    # unbounded model family.
    rows = [
        ([3],   ['fifo'],        'priority', [1],   1, {'kind':'free'},                                      'full', 2),
        ([3],   ['lifo'],        'rr',       [1],   2, {'kind':'budget','up_stalls':0,'down_stalls':0},       'hist', 3),
        ([4],   ['fifo'],        'wrr',      [2],   1, {'kind':'budget','up_stalls':1,'down_stalls':0},       'full', 3),
        ([4],   ['lifo'],        'priority', [1],   2, {'kind':'free'},                                      'hist', 3),
        ([2],   ['fifo'],        'rr',       [1],   1, {'kind':'budget','up_stalls':0,'down_stalls':1},       'full', 2),
        ([2],   ['lifo'],        'wrr',      [3],   2, {'kind':'free'},                                      'hist', 2),
        ([3],   ['fifo'],        'priority', [1],   2, {'kind':'budget','up_stalls':1,'down_stalls':1},       'hist', 3),
        ([4],   ['lifo'],        'rr',       [1],   1, {'kind':'budget','up_stalls':0,'down_stalls':0},       'full', 3),
        ([2,1], ['fifo','fifo'], 'priority', [1,1], 1, {'kind':'free'},                                      'full', 2),
        ([1,2], ['fifo','lifo'], 'rr',       [1,1], 2, {'kind':'budget','up_stalls':0,'down_stalls':0},       'hist', 3),
        ([2,2], ['lifo','fifo'], 'wrr',      [1,2], 1, {'kind':'budget','up_stalls':1,'down_stalls':0},       'full', 2),
        ([3,1], ['lifo','lifo'], 'wrr',      [2,1], 2, {'kind':'free'},                                      'hist', 3),
        ([1,3], ['fifo','fifo'], 'priority', [1,1], 1, {'kind':'budget','up_stalls':0,'down_stalls':1},       'full', 3),
        ([2,2], ['fifo','lifo'], 'rr',       [1,1], 2, {'kind':'budget','up_stalls':1,'down_stalls':1},       'hist', 2),
        ([2,1], ['lifo','fifo'], 'wrr',      [1,2], 2, {'kind':'free'},                                      'hist', 3),
        ([1,2], ['lifo','lifo'], 'priority', [1,1], 1, {'kind':'budget','up_stalls':0,'down_stalls':0},       'full', 2),
        ([2,2], ['fifo','fifo'], 'wrr',      [2,1], 2, {'kind':'budget','up_stalls':1,'down_stalls':0},       'hist', 3),
        ([3,1], ['fifo','lifo'], 'rr',       [1,1], 1, {'kind':'free'},                                      'full', 2),
        ([1,3], ['lifo','fifo'], 'wrr',      [1,2], 2, {'kind':'budget','up_stalls':0,'down_stalls':1},       'hist', 3),
        ([2,1], ['lifo','lifo'], 'priority', [1,1], 1, {'kind':'budget','up_stalls':1,'down_stalls':1},       'full', 2),
        ([1,2], ['fifo','fifo'], 'wrr',      [2,1], 2, {'kind':'free'},                                      'hist', 2),
        ([2,2], ['lifo','lifo'], 'rr',       [1,1], 1, {'kind':'budget','up_stalls':0,'down_stalls':0},       'full', 3),
        ([3,1], ['fifo','fifo'], 'wrr',      [1,2], 2, {'kind':'budget','up_stalls':1,'down_stalls':0},       'hist', 2),
        ([1,3], ['fifo','lifo'], 'priority', [1,1], 1, {'kind':'free'},                                      'full', 3),
        ([2,2], ['lifo','fifo'], 'wrr',      [2,1], 2, {'kind':'budget','up_stalls':0,'down_stalls':1},       'full', 2),
        ([2,1], ['fifo','lifo'], 'rr',       [1,1], 1, {'kind':'budget','up_stalls':1,'down_stalls':1},       'hist', 3),
        ([1,2], ['lifo','fifo'], 'wrr',      [1,2], 2, {'kind':'free'},                                      'full', 2),
        ([2,2], ['fifo','lifo'], 'priority', [1,1], 1, {'kind':'budget','up_stalls':0,'down_stalls':0},       'hist', 3),
        ([3,1], ['lifo','fifo'], 'rr',       [1,1], 2, {'kind':'budget','up_stalls':1,'down_stalls':0},       'full', 2),
        ([1,3], ['lifo','lifo'], 'wrr',      [2,1], 1, {'kind':'free'},                                      'hist', 3),
        ([2,1], ['fifo','fifo'], 'wrr',      [1,2], 2, {'kind':'budget','up_stalls':0,'down_stalls':1},       'full', 3),
        ([2,2], ['lifo','lifo'], 'priority', [1,1], 1, {'kind':'budget','up_stalls':1,'down_stalls':1},       'hist', 2),
    ]
    result: list[dict[str, Any]] = []
    for index, (lengths, disciplines, policy, weights, capacity, environment, workload, horizon) in enumerate(rows, 1):
        cuts = [[g, rank] for g, length in enumerate(lengths) for rank in range(1, length)]
        times = sorted({1, horizon} | ({2} if horizon == 3 else set()))
        support = ({'kind':'full'} if workload == 'full' else
                   {'kind':'hist', 'totals':[_histogram(n, (index + g) % 2 == 0) for g, n in enumerate(lengths)]})
        result.append({
            'id': f'audit{index:02d}', 'classes': 2, 'horizon': horizon,
            'lengths': lengths, 'disciplines': disciplines, 'policy': policy,
            'weights': weights, 'sink_capacity': capacity,
            'environment': environment,
            'queries': [{'time': t, 'class': col} for t in times for col in range(2)],
            'library': cuts, 'workload': support,
        })
    return result


def _unique_words(multiset: list[int]) -> list[tuple[int, ...]]:
    return sorted(set(permutations(multiset)))


def colorings(case: dict[str, Any]) -> list[list[list[int]]]:
    choices: list[list[tuple[int, ...]]] = []
    if case['workload']['kind'] == 'full':
        for length in case['lengths']:
            choices.append(list(product(range(case['classes']), repeat=length)))
    else:
        for totals in case['workload']['totals']:
            multiset = [col for col, count in enumerate(totals) for _ in range(count)]
            choices.append(_unique_words(multiset))
    return [[list(word) for word in rows] for rows in product(*choices)]


def action_words(case: dict[str, Any]) -> list[tuple[tuple[int, int], ...]]:
    valid = []
    for word in product(product((0, 1), repeat=2), repeat=case['horizon']):
        if case['environment']['kind'] == 'budget':
            upstream = sum(1-a for a, _ in word)
            downstream = sum(1-b for _, b in word)
            if upstream > case['environment']['up_stalls'] or downstream > case['environment']['down_stalls']:
                continue
        valid.append(tuple(word))
    return valid


def _calendar(case: dict[str, Any]) -> list[int]:
    if case['policy'] == 'wrr':
        return [g for g, weight in enumerate(case['weights']) for _ in range(weight)]
    return list(range(len(case['lengths'])))


def direct_merge(case: dict[str, Any]) -> list[list[int]]:
    sources = [list(range(length)) for length in case['lengths']]
    calendar = _calendar(case)
    pointer = 0
    merged: list[list[int]] = []
    while any(sources):
        if case['policy'] == 'priority':
            group = next(g for g, queue in enumerate(sources) if queue)
        else:
            for _ in range(len(calendar)):
                group = calendar[pointer]
                pointer = (pointer + 1) % len(calendar)
                if sources[group]:
                    break
        rank = sources[group].pop(0 if case['disciplines'][group] == 'fifo' else -1)
        merged.append([group, rank])
    return merged


def direct_simulate(case: dict[str, Any], rows: list[list[int]], actions: Iterable[tuple[int, int]]):
    sources = [[(g, rank) for rank in range(length)] for g, length in enumerate(case['lengths'])]
    calendar = _calendar(case)
    pointer = transferred = departed_count = upstream_stalls = downstream_stalls = 0
    sink: list[tuple[int, int]] = []
    departed: list[tuple[int, int]] = []
    path = [(0, 0, 0, 0)]
    answers = [tuple(0 for _ in range(case['classes']))]
    for upstream_on, downstream_on in actions:
        if case['environment']['kind'] == 'budget':
            upstream_stalls += 1-upstream_on
            downstream_stalls += 1-downstream_on
        if downstream_on and sink:
            departed.append(sink.pop(0)); departed_count += 1
        if upstream_on and len(sink) < case['sink_capacity'] and any(sources):
            if case['policy'] == 'priority':
                group = next(g for g, queue in enumerate(sources) if queue)
            else:
                for _ in range(len(calendar)):
                    group = calendar[pointer]
                    pointer = (pointer + 1) % len(calendar)
                    if sources[group]:
                        break
            sink.append(sources[group].pop(0 if case['disciplines'][group] == 'fifo' else -1))
            transferred += 1
        path.append((transferred, departed_count,
                     upstream_stalls if case['environment']['kind'] == 'budget' else 0,
                     downstream_stalls if case['environment']['kind'] == 'budget' else 0))
        answers.append(tuple(sum(rows[g][rank] == col for g, rank in departed)
                             for col in range(case['classes'])))
    return tuple(path), tuple(answers), tuple(departed)


def _blocks(case: dict[str, Any], rows: list[list[int]], cuts: tuple[tuple[int, int], ...]) -> tuple[int, ...]:
    result: list[int] = []
    selected = set(cuts)
    for g, length in enumerate(case['lengths']):
        ends = [0] + [rank for group, rank in sorted(selected) if group == g] + [length]
        for left, right in zip(ends, ends[1:]):
            result.extend(rows[g][left:right].count(col) for col in range(case['classes']))
    return tuple(result)


def _all_cut_sets(case: dict[str, Any]) -> list[tuple[tuple[int, int], ...]]:
    ambient = [tuple(cut) for cut in case['library']]
    return [tuple(combo) for size in range(len(ambient)+1) for combo in combinations(ambient, size)]


def direct_oracle(case: dict[str, Any]) -> dict[str, Any]:
    words = colorings(case)
    services = action_words(case)
    candidates = _all_cut_sets(case)
    tables: list[dict[tuple[Any, ...], tuple[int, ...]]] = [{} for _ in candidates]
    adequate = [True] * len(candidates)
    earliest_failures: list[int | None] = [None] * len(candidates)
    layers = [set() for _ in range(case['horizon']+1)]
    traces = []
    merge = tuple(map(tuple, direct_merge(case)))
    comparisons = ticks = 0
    for actions in services:
        for rows in words:
            path, answers, departed = direct_simulate(case, rows, actions)
            ticks += case['horizon']
            for t, state in enumerate(path):
                layers[t].add(state)
            if departed != merge[:path[-1][1]]:
                raise AssertionError('direct simulator violated merge-prefix property')
            query_vector = tuple(answers[q['time']][q['class']] for q in case['queries'])
            traces.append((rows, path, answers, query_vector))
            for index, cuts in enumerate(candidates):
                key = (path, _blocks(case, rows, cuts))
                comparisons += 1
                prior = tables[index].get(key)
                if prior is not None and prior != query_vector:
                    adequate[index] = False
                    failure = min(case['queries'][qi]['time']
                                  for qi, (left, right) in enumerate(zip(prior, query_vector))
                                  if left != right)
                    if earliest_failures[index] is None or failure < earliest_failures[index]:
                        earliest_failures[index] = failure
                else:
                    tables[index][key] = query_vector
    required = [cut for cut in map(tuple, case['library'])
                if not any(good and cut not in cuts for cuts, good in zip(candidates, adequate))]
    expected = [all(cut in cuts for cut in required) for cuts in candidates]
    if adequate != expected:
        raise AssertionError('adequacy family is not generated by a unique least cut set')
    return {
        'merge_word': [list(item) for item in merge],
        'layers': layers,
        'required': [list(cut) for cut in required],
        'candidate_results': [
            {'cuts':[list(c) for c in cuts], 'adequate':good,
             'earliest_failure': earliest_failures[index]}
            for index, (cuts, good) in enumerate(zip(candidates, adequate))],
        'service_words': len(services), 'colorings': len(words),
        'concrete_traces': len(traces), 'candidate_count': len(candidates),
        'candidate_comparisons': comparisons, 'packet_replay_ticks': ticks,
        '_traces': traces,
    }


def audit_case(case: dict[str, Any]) -> dict[str, Any]:
    direct = direct_oracle(case)
    certificate, producer = frontier.synthesize(case)
    checked = frontier_check.check(case, certificate)
    if certificate['status'] != 'adequate':
        raise AssertionError('full ambient library was not adequate')
    if certificate['merge_word'] != direct['merge_word']:
        raise AssertionError('producer merge word disagrees with direct simulation')
    certified_layers = [set(map(tuple, layer)) for layer in certificate['layers']]
    if certified_layers != direct['layers']:
        raise AssertionError('producer reachability disagrees with direct service enumeration')
    if certificate['required'] != direct['required'] or certificate['cuts'] != direct['required']:
        raise AssertionError('producer least cuts disagree with exhaustive candidate classification')

    abstract_evaluations = 0
    for rows, path, answers, _ in direct['_traces']:
        blocks = encode(case, rows, certificate['cuts'])
        for query_index, query in enumerate(case['queries']):
            observed = evaluate(case, certificate, blocks, query_index, path[query['time']][1])
            if observed != answers[query['time']][query['class']]:
                raise AssertionError('numeric evaluator disagrees with direct packet execution')
            abstract_evaluations += 1

    negative = None
    negative_charge = 0
    if certificate['required']:
        missing = certificate['required'][0]
        altered = deepcopy(case)
        altered['library'] = [cut for cut in altered['library'] if cut != missing]
        bad_certificate, bad_producer = frontier.synthesize(altered)
        bad_checked = frontier_check.check(altered, bad_certificate)
        target_cuts = sorted(tuple(cut) for cut in altered['library'])
        direct_negative = next(row for row in direct['candidate_results']
                               if sorted(tuple(cut) for cut in row['cuts']) == target_cuts)
        if (bad_certificate['status'] != 'insufficient_library' or
                bad_certificate['witness']['cut'] != missing or
                direct_negative['adequate'] or
                direct_negative['earliest_failure'] != bad_certificate['earliest_failure']):
            raise AssertionError('missing-cut certificate disagrees with direct semantic classification')
        negative = {
            'omitted_cut': missing,
            'status': bad_certificate['status'],
            'earliest_failure': bad_certificate['earliest_failure'],
            'direct_earliest_failure': direct_negative['earliest_failure'],
            'producer_states': bad_producer['states'],
            'producer_transitions': bad_producer['transitions'],
            'checker_states': bad_checked['states'],
            'checker_transitions': bad_checked['transitions'],
        }
        negative_charge = (bad_producer['states'] + bad_producer['transitions'] +
                           bad_checked['states'] + bad_checked['transitions'] +
                           bad_checked['witness_replay_ticks'] +
                           bad_checked['earlier_query_checks'])

    obligation_count = (direct['candidate_comparisons'] + direct['packet_replay_ticks'] +
                        abstract_evaluations + producer['states'] + producer['transitions'] +
                        checked['states'] + checked['transitions'] +
                        checked['witness_replay_ticks'] + checked['earlier_query_checks'] +
                        negative_charge)
    return {
        'case': case['id'], 'lengths': case['lengths'], 'horizon': case['horizon'],
        'policy': case['policy'], 'disciplines': case['disciplines'],
        'environment': case['environment'], 'workload': case['workload']['kind'],
        'service_words': direct['service_words'], 'colorings': direct['colorings'],
        'concrete_traces': direct['concrete_traces'],
        'candidate_count': direct['candidate_count'],
        'candidate_comparisons': direct['candidate_comparisons'],
        'packet_replay_ticks': direct['packet_replay_ticks'],
        'abstract_query_evaluations': abstract_evaluations,
        'required': direct['required'], 'negative_library': negative,
        'producer_states': producer['states'], 'producer_transitions': producer['transitions'],
        'checker_states': checked['states'], 'checker_transitions': checked['transitions'],
        'obligations': obligation_count,
    }


def run(retained_models: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    generated = models()
    if retained_models is not None and retained_models != generated:
        raise ValueError('generated exhaustive-audit models differ from retained input')
    rows = [audit_case(case) for case in generated]
    return {
        'status': 'all_exhaustive_micro_audits_passed',
        'scope': 'exhaustive colors, valid service words, and ambient cut subsets within each retained small model',
        'model_count': len(rows),
        'models_with_missing_cut_negative': sum(row['negative_library'] is not None for row in rows),
        'concrete_traces': sum(row['concrete_traces'] for row in rows),
        'candidate_comparisons': sum(row['candidate_comparisons'] for row in rows),
        'packet_replay_ticks': sum(row['packet_replay_ticks'] for row in rows),
        'abstract_query_evaluations': sum(row['abstract_query_evaluations'] for row in rows),
        'oracle_disagreements': 0,
        'obligations': sum(row['obligations'] for row in rows),
        'cases': rows,
    }
