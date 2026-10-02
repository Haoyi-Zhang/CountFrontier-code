"""Standalone certificate checker; deliberately independent of engine.py.

Queue contents are encoded as token locations and insertion timestamps, not
producer queue lists. Query coefficients are accumulated term-first. The
required-cut test compares all active class pairs, not centered signatures.
This is implementation diversity, not independent human review or mechanization.
"""
from __future__ import annotations
from typing import Any


class Rejected(ValueError):
    """Invalid model, certificate, or replay obligation."""


def insist(test: bool, message: str) -> None:
    if not test:
        raise Rejected(message)


def wellformed(c: dict[str, Any]) -> tuple[int, int, int]:
    insist(isinstance(c, dict) and set(c) == {'id', 'classes', 'horizon', 'queues', 'arrivals', 'active', 'policy', 'weights', 'sink', 'groups', 'library', 'workload', 'queries'}, 'case schema')
    k, h, m = c['classes'], c['horizon'], len(c['queues'])
    insist(type(k) is int and 2 <= k <= 4 and type(h) is int and 1 <= h <= 48 and 1 <= m <= 4, 'dimensions')
    insist(isinstance(c['id'], str) and 0 < len(c['id']) <= 80, 'case identifier')
    insist(c['policy'] in ('priority', 'rr', 'wrr'), 'unsupported class-sensitive or unknown policy')
    insist(len(c['weights']) == m and all(type(w) is int and 1 <= w <= 4 for w in c['weights']), 'weights')
    insist(len(c['active']) == h and all(type(b) is bool for b in c['active']), 'service schedule')
    offered = []
    for q in c['queues']:
        insist(set(q) == {'capacity', 'discipline', 'initial'}, 'queue fields')
        insist(type(q['capacity']) is int and 1 <= q['capacity'] <= 24 and len(q['initial']) <= q['capacity'], 'queue capacity')
        insist(q['discipline'] in ('fifo', 'lifo'), 'queue discipline')
        offered.extend(q['initial'])
    s = c['sink']
    if s is not None:
        insist(set(s) == {'capacity', 'discipline', 'active'}, 'sink fields')
        insist(type(s['capacity']) is int and 1 <= s['capacity'] <= 24 and s['discipline'] in ('fifo', 'lifo'), 'sink queue')
        insist(len(s['active']) == h and all(type(b) is bool for b in s['active']), 'sink active')
    last = 0
    for a in c['arrivals']:
        insist(set(a) == {'time', 'queue', 'token'}, 'arrival fields')
        insist(type(a['time']) is int and last <= a['time'] <= h and a['time'] >= 1, 'arrival time/order')
        insist(type(a['queue']) is int and 0 <= a['queue'] < m, 'arrival queue')
        last = a['time']; offered.append(a['token'])
    gs = c['groups']
    insist(1 <= len(gs) <= 4 and all(isinstance(g, list) and g for g in gs), 'source groups')
    tokens = [p for g in gs for p in g]
    n = len(tokens)
    insist(n <= 192 and all(type(p) is int for p in tokens+offered), 'token types/count')
    insist(sorted(tokens) == list(range(n)) and sorted(offered) == list(range(n)), 'unique offered token partition')
    lib = c['library']
    insist(len(lib) <= 6 and all(isinstance(a, list) and len(a) == 2 and all(type(v) is int for v in a) for a in lib), 'library syntax')
    insist(len({tuple(a) for a in lib}) == len(lib) and all(0 <= g < len(gs) and 1 <= r < len(gs[g]) for g, r in lib), 'library bounds')
    w = c['workload']
    if w != {'kind': 'full'}:
        insist(set(w) == {'kind', 'totals'} and w['kind'] == 'hist' and len(w['totals']) == len(gs), 'workload schema')
        insist(all(len(hist) == k and all(type(v) is int and v >= 0 for v in hist) and sum(hist) == len(g) for g, hist in zip(gs, w['totals'])), 'histogram support')
    insist(1 <= len(c['queries']) <= 32, 'query count')
    for q in c['queries']:
        insist(set(q) == {'terms'} and 1 <= len(q['terms']) <= 8, 'query syntax')
        for t in q['terms']:
            insist(set(t) == {'event', 'queue', 'start', 'end', 'weights'}, 'term syntax')
            insist(t['event'] in ('depart', 'drop', 'transfer', 'occupancy'), 'event alphabet')
            insist(type(t['queue']) is int and -1 <= t['queue'] <= m, 'query queue')
            insist(type(t['start']) is int and type(t['end']) is int and 1 <= t['start'] <= t['end'] <= h, 'time window')
            insist(len(t['weights']) == k and all(type(v) is int and -8 <= v <= 8 for v in t['weights']), 'query weights')
    return n, k, h


def replay(c: dict[str, Any]) -> tuple[list[list[Any]], int]:
    """Token-location interpreter with explicit tail-drop and insertion order."""
    n, _, h = wellformed(c)
    m = len(c['queues'])
    loc, stamp = [-2] * n, [-1] * n  # -2 unoffered, -1 retired
    clock = 0
    for qi, q in enumerate(c['queues']):
        for token in q['initial']:
            loc[token], stamp[token] = qi, clock
            clock += 1
    trace: list[list[Any]] = []
    cursor = 0
    cal = []
    for qi in range(m):
        cal.extend([qi] * (c['weights'][qi] if c['policy'] == 'wrr' else 1))
    sk = c['sink']
    for time in range(1, h+1):
        for a in c['arrivals']:
            if a['time'] == time:
                token, qi = a['token'], a['queue']
                if loc.count(qi) >= c['queues'][qi]['capacity']:
                    loc[token] = -1
                    trace.append([time, 'drop', qi, token])
                else:
                    loc[token], stamp[token] = qi, clock
                    clock += 1
        if sk is not None and sk['active'][time-1]:
            candidates = [p for p in range(n) if loc[p] == m]
            if candidates:
                token = sorted(candidates, key=lambda p: stamp[p], reverse=(sk['discipline'] == 'lifo'))[0]
                loc[token] = -1
                trace.append([time, 'depart', m, token])
        if c['active'][time-1]:
            occupied = {v for v in loc if 0 <= v < m}
            selected = None
            if c['policy'] == 'priority' and occupied:
                selected = min(occupied)
            elif c['policy'] != 'priority':
                slots = [(cursor + j) % len(cal) for j in range(len(cal))]
                viable = [j for j in slots if cal[j] in occupied]
                if viable:
                    selected = cal[viable[0]]
                    cursor = (viable[0]+1) % len(cal)
            if selected is not None:
                members = [p for p in range(n) if loc[p] == selected]
                discipline = c['queues'][selected]['discipline']
                token = min(members, key=lambda p: stamp[p]) if discipline == 'fifo' else max(members, key=lambda p: stamp[p])
                loc[token] = -1
                if sk is None:
                    trace.append([time, 'depart', selected, token])
                else:
                    trace.append([time, 'transfer', selected, token])
                    if loc.count(m) >= sk['capacity']:
                        trace.append([time, 'drop', m, token])
                    else:
                        loc[token], stamp[token] = m, clock
                        clock += 1
        for token in range(n):
            if loc[token] >= 0:
                trace.append([time, 'occupancy', loc[token], token])
    return trace, h


def matrix(c: dict[str, Any], trace: list[list[Any]]) -> list[list[list[int]]]:
    n, k = sum(map(len, c['groups'])), c['classes']
    out = [[[0 for _ in range(k)] for _ in c['queries']] for _ in range(n)]
    for qi, query in enumerate(c['queries']):
        for term in query['terms']:
            hits = [(token, time) for time, event, queue, token in trace
                    if event == term['event'] and term['queue'] in (-1, queue) and term['start'] <= time <= term['end']]
            for token, _ in hits:
                out[token][qi] = [a+b for a, b in zip(out[token][qi], term['weights'])]
    return out


def permitted(c: dict[str, Any], word: list[int]) -> bool:
    if len(word) != sum(map(len, c['groups'])) or any(type(a) is not int or not 0 <= a < c['classes'] for a in word):
        return False
    if c['workload']['kind'] == 'hist':
        return all([sum(word[p] == color for p in group) for color in range(c['classes'])] == hist
                   for group, hist in zip(c['groups'], c['workload']['totals']))
    return True


def abstract(c: dict[str, Any], word: list[int], cuts: list[list[int]]) -> tuple[int, ...]:
    values = []
    for gi, group in enumerate(c['groups']):
        endpoints = sorted([r for g, r in cuts if g == gi]) + [len(group)]
        for stop in endpoints:
            values.extend(sum(word[p] == col for p in group[:stop]) for col in range(c['classes']))
    return tuple(values)


def answers(c: dict[str, Any], word: list[int], trace: list[list[Any]]) -> tuple[int, ...]:
    """Direct colored-event evaluator; does not use coefficient compilation."""
    values = []
    for query in c['queries']:
        total = 0
        for term in query['terms']:
            for time, event, queue, token in trace:
                if event == term['event'] and term['queue'] in (-1, queue) and term['start'] <= time <= term['end']:
                    total += term['weights'][word[token]]
        values.append(total)
    return tuple(values)


def check(c: dict[str, Any], cert: dict[str, Any]) -> dict[str, int]:
    trace, ticks = replay(c)
    a = matrix(c, trace)
    n, k = len(a), c['classes']
    qs = len(c['queries'])
    pal = [list(range(k)) for _ in c['groups']] if c['workload']['kind'] == 'full' else [[j for j, num in enumerate(hist) if num] for hist in c['workload']['totals']]
    needed = []
    for g, group in enumerate(c['groups']):
        for r in range(1, len(group)):
            l, u = group[r-1], group[r]
            if any(a[l][q][c1]+a[u][q][c2] != a[l][q][c2]+a[u][q][c1]
                   for q in range(qs) for c1 in pal[g] for c2 in pal[g]):
                needed.append([g, r])
    insist(cert.get('case') == c['id'] and cert.get('required') == needed, 'case or required-cut mismatch')
    library = c['library']
    missing = [cut for cut in needed if cut not in library]
    if missing:
        insist(set(cert) == {'case', 'required', 'status', 'missing', 'witness'} and cert['status'] == 'insufficient_library', 'inadequate-library certificate schema')
        insist(cert['missing'] == missing[0], 'first unavailable required cut')
        witness_list = [cert['witness']]
        witness_cuts = [missing[0]]
    else:
        insist(set(cert) == {'case', 'required', 'status', 'cuts', 'offset', 'blocks', 'witnesses'} and cert['status'] == 'adequate', 'adequate certificate schema')
        insist(cert['cuts'] == needed and len(cert['witnesses']) == len(needed), 'minimality witness coverage')
        expected_offset = [sum(a[p][q][pal[g][0]] for g, group in enumerate(c['groups']) for p in group) for q in range(qs)]
        insist(cert['offset'] == expected_offset, 'constant contribution')
        block_at = 0
        for g, group in enumerate(c['groups']):
            ends = [0] + [r for gi, r in needed if gi == g] + [len(group)]
            for start, stop in zip(ends, ends[1:]):
                insist(block_at < len(cert['blocks']), 'missing block')
                b = cert['blocks'][block_at]; block_at += 1
                insist(set(b) == {'group', 'start', 'stop', 'weights'} and (b['group'], b['start'], b['stop']) == (g, start, stop), 'block partition')
                insist(len(b['weights']) == qs and all(len(v) == k for v in b['weights']), 'formula dimensions')
                for p in group[start:stop]:
                    for q in range(qs):
                        expect = [a[p][q][col]-a[p][q][pal[g][0]] if col in pal[g] else 0 for col in range(k)]
                        insist(b['weights'][q] == expect, 'block does not preserve numeric query')
        insist(block_at == len(cert['blocks']), 'extra block')
        witness_list, witness_cuts = cert['witnesses'], needed
    for w, cut in zip(witness_list, witness_cuts):
        insist(set(w) == {'group', 'rank', 'query', 'left', 'right'}, 'witness schema')
        insist([w['group'], w['rank']] == cut and type(w['query']) is int and 0 <= w['query'] < qs, 'witness location')
        x, y = w['left'], w['right']
        insist(permitted(c, x) and permitted(c, y), 'witness outside workload')
        diff = [p for p in range(n) if x[p] != y[p]]
        pair = c['groups'][cut[0]][cut[1]-1:cut[1]+1]
        insist(sorted(diff) == sorted(pair), 'not a two-position adjacent witness')
        strongest_without = [u for u in library if u != cut]
        insist(abstract(c, x, strongest_without) == abstract(c, y, strongest_without), 'witness not collapsed')
        ax, ay = answers(c, x, trace), answers(c, y, trace)
        insist(ax[w['query']] != ay[w['query']], 'witness has equal query answer')
    return {'simulation_ticks': ticks, 'witness_pairs': len(witness_list), 'event_records': len(trace),
            'coefficient_cells': n*qs*k}
