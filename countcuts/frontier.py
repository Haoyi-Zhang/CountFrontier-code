"""Producer for a lossless, preloaded contention point followed by a FIFO.

An immutable class-blind merge word separates packet order from uncertain
service timing. Timed reachability uses (transferred, departed, up-stalls,
down-stalls). The checker is in frontier_check.py and imports no code here.
"""
from __future__ import annotations
from collections import deque
from typing import Any


def validate(c: dict[str, Any]) -> None:
    if set(c) != {'id', 'classes', 'horizon', 'lengths', 'disciplines', 'policy', 'weights',
                  'sink_capacity', 'environment', 'queries', 'library', 'workload'}:
        raise ValueError('frontier schema: initial queues only, FIFO sink, blocking admission')
    k, h, lengths = c['classes'], c['horizon'], c['lengths']
    if type(k) is not int or not 2 <= k <= 4 or type(h) is not int or not 1 <= h <= 48:
        raise ValueError('frontier dimensions')
    if not 1 <= len(lengths) <= 4 or any(type(n) is not int or not 1 <= n <= 24 for n in lengths):
        raise ValueError('source capacities')
    if len(c['disciplines']) != len(lengths) or any(d not in ('fifo', 'lifo') for d in c['disciplines']):
        raise ValueError('source discipline')
    if c['policy'] not in ('priority', 'rr', 'wrr') or len(c['weights']) != len(lengths) or any(type(w) is not int or not 1 <= w <= 4 for w in c['weights']):
        raise ValueError('class-blind arbitration')
    if type(c['sink_capacity']) is not int or not 1 <= c['sink_capacity'] <= 24:
        raise ValueError('sink capacity')
    env = c['environment']
    if env != {'kind': 'free'}:
        if set(env) != {'kind', 'up_stalls', 'down_stalls'} or env['kind'] != 'budget' or any(type(env[f]) is not int or not 0 <= env[f] <= 2 for f in ('up_stalls', 'down_stalls')):
            raise ValueError('environment')
    if not 1 <= len(c['queries']) <= 32 or any(set(q) != {'time', 'class'} or type(q['time']) is not int or not 1 <= q['time'] <= h or type(q['class']) is not int or not 0 <= q['class'] < k for q in c['queries']):
        raise ValueError('prefix count queries')
    lib = c['library']
    if len(lib) > 6 or any(len(a) != 2 or any(type(v) is not int for v in a) for a in lib) or len(set(map(tuple, lib))) != len(lib) or any(not 0 <= g < len(lengths) or not 1 <= r < lengths[g] for g, r in lib):
        raise ValueError('at most six eligible cuts')
    w = c['workload']
    if w != {'kind': 'full'}:
        if set(w) != {'kind', 'totals'} or w['kind'] != 'hist' or len(w['totals']) != len(lengths):
            raise ValueError('shuffle-complete workload')
        if any(len(hist) != k or any(type(v) is not int or v < 0 for v in hist) or sum(hist) != n for hist, n in zip(w['totals'], lengths)):
            raise ValueError('histogram support')


def merge_word(c: dict[str, Any]) -> list[list[int]]:
    queues = [deque(range(n)) for n in c['lengths']]
    calendar = [g for g, w in enumerate(c['weights']) for _ in range(w)] if c['policy'] == 'wrr' else list(range(len(queues)))
    cursor, word = 0, []
    while any(queues):
        if c['policy'] == 'priority':
            chosen = next(g for g, queue in enumerate(queues) if queue)
        else:
            slot = next((cursor+j) % len(calendar) for j in range(len(calendar)) if queues[calendar[(cursor+j) % len(calendar)]] )
            chosen = calendar[slot]; cursor = (slot+1) % len(calendar)
        rank = queues[chosen].popleft() if c['disciplines'][chosen] == 'fifo' else queues[chosen].pop()
        word.append([chosen, rank])
    return word


def actions(c, state):
    _, _, su, sd = state
    env = c['environment']
    for a in (0, 1):
        for b in (0, 1):
            if env['kind'] == 'free' or (su+1-a <= env['up_stalls'] and sd+1-b <= env['down_stalls']):
                yield a, b


def step(c, state, action):
    u, d, su, sd = state; a, b = action
    if b and d < u: d += 1
    if a and u < sum(c['lengths']) and u-d < c['sink_capacity']: u += 1
    if c['environment']['kind'] == 'budget': su += 1-a; sd += 1-b
    return u, d, su, sd


def explore(c, max_transitions=40000):
    validate(c)
    layers = [{(0, 0, 0, 0)}]
    parents = [{}]
    transitions = 0
    for tick in range(1, c['horizon']+1):
        current, previous = set(), {}
        for s in sorted(layers[-1]):
            for action in actions(c, s):
                transitions += 1
                if transitions > max_transitions:
                    raise RuntimeError('INCOMPLETE: frontier transition budget exhausted')
                after = step(c, s, action)
                if after not in current:
                    previous[after] = (s, action)
                    current.add(after)
        layers.append(current); parents.append(previous)
    return layers, parents, transitions


def support(c):
    return [list(range(c['classes'])) for _ in c['lengths']] if c['workload']['kind'] == 'full' else [[j for j, v in enumerate(hist) if v] for hist in c['workload']['totals']]


def opportunities(c, layers, word):
    pal = support(c)
    prefixes = [[0]*len(c['lengths'])]
    for g, _ in word:
        row = prefixes[-1].copy(); row[g] += 1; prefixes.append(row)
    records = []
    for qi, query in enumerate(c['queries']):
        t, col = query['time'], query['class']
        seen_departures = set()
        for state in sorted(layers[t]):
            # Only extraction projects to departure count. Keep the smallest
            # full state as before; reachability and its parents stay intact.
            if state[1] in seen_departures:
                continue
            seen_departures.add(state[1])
            count = prefixes[state[1]]
            for g, amount in enumerate(count):
                if col not in pal[g] or len(pal[g]) < 2:
                    continue
                r = amount if c['disciplines'][g] == 'fifo' else c['lengths'][g]-amount
                if 0 < r < c['lengths'][g]:
                    records.append((t, qi, g, r, state))
    return sorted(records)


def witness(c, record, parents):
    time, qi, group, rank, state = record
    acts = []
    for tick in range(time, 0, -1):
        state, action = parents[tick][state]
        acts.append(list(action))
    acts.reverse()
    colors = []
    for g, n in enumerate(c['lengths']):
        if c['workload']['kind'] == 'full': colors.append([0]*n)
        else: colors.append([col for col, count in enumerate(c['workload']['totals'][g]) for _ in range(count)])
    col = c['queries'][qi]['class']
    other = next(v for v in support(c)[group] if v != col)
    if c['workload']['kind'] == 'hist':
        hist = c['workload']['totals'][group].copy(); hist[col] -= 1; hist[other] -= 1
        remaining = iter([v for v, n in enumerate(hist) for _ in range(n)])
        for j in range(c['lengths'][group]):
            if j not in (rank-1, rank): colors[group][j] = next(remaining)
    colors[group][rank-1], colors[group][rank] = col, other
    second = [row.copy() for row in colors]
    second[group][rank-1], second[group][rank] = other, col
    return {'cut': [group, rank], 'query': qi, 'time': time, 'actions': acts,
            'left': colors, 'right': second}


def synthesize(c):
    layers, parents, transitions = explore(c)
    word = merge_word(c)
    choices = opportunities(c, layers, word)
    required = sorted({(g, r) for _, _, g, r, _ in choices})
    unavailable = [record for record in choices if [record[2], record[3]] not in c['library']]
    cert = {'case': c['id'], 'merge_word': word,
            'layers': [[list(s) for s in sorted(layer)] for layer in layers],
            'required': [list(cut) for cut in required]}
    if unavailable:
        first = unavailable[0]
        cert.update({'status': 'insufficient_library', 'earliest_failure': first[0],
                     'witness': witness(c, first, parents)})
    else:
        witnesses = []
        for g, r in required:
            record = next(v for v in choices if v[2:4] == (g, r))
            witnesses.append(witness(c, record, parents))
        cert.update({'status': 'adequate', 'cuts': cert['required'], 'witnesses': witnesses})
    return cert, {'states': sum(map(len, layers)), 'transitions': transitions,
                  'max_layer_states': max(map(len, layers)),
                  'output_frontiers': {str(t): sorted({s[1] for s in layers[t]}) for t in sorted({q['time'] for q in c['queries']})}}
