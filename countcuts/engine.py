"""Producer: queue-list execution and coefficient-based cut synthesis.

No network access, dynamic code, random traffic, or class-sensitive scheduling.
The independent checker intentionally does not import this module.
"""
from __future__ import annotations
from collections import deque
from typing import Any


def validate(case: dict[str, Any]) -> None:
    if set(case) != {'id', 'classes', 'horizon', 'queues', 'arrivals', 'active',
                     'policy', 'weights', 'sink', 'groups', 'library', 'workload', 'queries'}:
        raise ValueError('unsupported or missing model fields')
    k, h, qs = case['classes'], case['horizon'], case['queues']
    if type(k) is not int or type(h) is not int or not 2 <= k <= 4 or not 1 <= h <= 48 or not 1 <= len(qs) <= 4:
        raise ValueError('model dimension outside declared envelope')
    for q in qs:
        if set(q) != {'capacity', 'discipline', 'initial'} or q['discipline'] not in ('fifo', 'lifo'):
            raise ValueError('unsupported queue')
        if type(q['capacity']) is not int or not 1 <= q['capacity'] <= 24 or len(q['initial']) > q['capacity']:
            raise ValueError('initial capacity')
    if case['policy'] not in ('priority', 'rr', 'wrr'):
        raise ValueError('class-blind policy required')
    if len(case['active']) != h or any(type(b) is not bool for b in case['active']):
        raise ValueError('active schedule')
    if len(case['weights']) != len(qs) or any(type(w) is not int or not 1 <= w <= 4 for w in case['weights']):
        raise ValueError('calendar weights')
    sink = case['sink']
    if sink is not None:
        if set(sink) != {'capacity', 'discipline', 'active'} or sink['discipline'] not in ('fifo', 'lifo'):
            raise ValueError('sink')
        if type(sink['capacity']) is not int or not 1 <= sink['capacity'] <= 24 or len(sink['active']) != h or any(type(b) is not bool for b in sink['active']):
            raise ValueError('sink schedule')
    groups = case['groups']
    flat = [v for g in groups for v in g]
    if not groups or any(not g for g in groups) or len(groups) > 4 or any(type(v) is not int for v in flat) or sorted(flat) != list(range(len(flat))) or len(flat) > 192:
        raise ValueError('token partition')
    offered = [v for q in qs for v in q['initial']]
    last_t = 0
    for a in case['arrivals']:
        if (set(a) != {'time', 'queue', 'token'} or type(a['time']) is not int or
                type(a['queue']) is not int or type(a['token']) is not int or
                not 1 <= a['time'] <= h or not 0 <= a['queue'] < len(qs)):
            raise ValueError('arrival')
        if a['time'] < last_t:
            raise ValueError('arrivals must be sorted by nondecreasing time; list order breaks ties')
        last_t = a['time']; offered.append(a['token'])
    if sorted(offered) != sorted(flat):
        raise ValueError('each offered token occurs exactly once')
    lib = [tuple(c) for c in case['library']]
    if len(lib) > 6 or len(lib) != len(set(lib)) or any(not 0 <= g < len(groups) or not 1 <= r < len(groups[g]) for g, r in lib):
        raise ValueError('cut library: at most six distinct cuts')
    w = case['workload']
    if w == {'kind': 'full'}:
        pass
    elif set(w) == {'kind', 'totals'} and w['kind'] == 'hist':
        if len(w['totals']) != len(groups):
            raise ValueError('histogram groups')
        for g, hist in zip(groups, w['totals']):
            if len(hist) != k or any(type(a) is not int or a < 0 for a in hist) or sum(hist) != len(g):
                raise ValueError('histogram')
    else:
        raise ValueError('only full or shuffle-complete fixed-histogram workloads')
    if not 1 <= len(case['queries']) <= 32:
        raise ValueError('query count')
    for query in case['queries']:
        if set(query) != {'terms'} or not 1 <= len(query['terms']) <= 8:
            raise ValueError('query syntax')
        for t in query['terms']:
            if set(t) != {'event', 'queue', 'start', 'end', 'weights'}:
                raise ValueError('term syntax')
            if t['event'] not in ('depart', 'drop', 'transfer', 'occupancy') or not -1 <= t['queue'] <= len(qs):
                raise ValueError('query event')
            if not 1 <= t['start'] <= t['end'] <= h or len(t['weights']) != k:
                raise ValueError('query bounds')
            if any(type(a) is not int or abs(a) > 8 for a in t['weights']):
                raise ValueError('bounded integer weights')


def run(case: dict[str, Any]) -> tuple[list[list[Any]], int]:
    """Return events [time, kind, queue, token]; arrivals precede both services.

    Downstream service precedes upstream service. Occupancy is sampled last.
    A transferred packet therefore cannot depart the tandem in the same tick.
    """
    validate(case)
    qs = [deque(q['initial']) for q in case['queues']]
    sink = deque()
    events: list[list[Any]] = []
    m = len(qs)
    calendar = [i for i, w in enumerate(case['weights']) for _ in range(w)] if case['policy'] == 'wrr' else list(range(m))
    pointer = 0
    arrivals: dict[int, list[dict[str, int]]] = {}
    for a in case['arrivals']:
        arrivals.setdefault(a['time'], []).append(a)
    for tick in range(1, case['horizon'] + 1):
        for a in arrivals.get(tick, []):
            q, v = a['queue'], a['token']
            if len(qs[q]) == case['queues'][q]['capacity']:
                events.append([tick, 'drop', q, v])
            else:
                qs[q].append(v)
        sk = case['sink']
        if sk is not None and sk['active'][tick-1] and sink:
            v = sink.popleft() if sk['discipline'] == 'fifo' else sink.pop()
            events.append([tick, 'depart', m, v])
        if case['active'][tick-1]:
            chosen = None
            if case['policy'] == 'priority':
                chosen = next((i for i, q in enumerate(qs) if q), None)
            else:
                for offset in range(len(calendar)):
                    slot = (pointer + offset) % len(calendar)
                    if qs[calendar[slot]]:
                        chosen = calendar[slot]
                        pointer = (slot + 1) % len(calendar)
                        break
            if chosen is not None:
                q = qs[chosen]
                v = q.popleft() if case['queues'][chosen]['discipline'] == 'fifo' else q.pop()
                if sk is None:
                    events.append([tick, 'depart', chosen, v])
                else:
                    events.append([tick, 'transfer', chosen, v])
                    if len(sink) == sk['capacity']:
                        events.append([tick, 'drop', m, v])
                    else:
                        sink.append(v)
        for i, q in enumerate(qs + ([sink] if sk is not None else [])):
            for v in q:
                events.append([tick, 'occupancy', i, v])
    return events, case['horizon']


def coefficients(case: dict[str, Any], events: list[list[Any]]) -> list[list[list[int]]]:
    n, k, nq = sum(map(len, case['groups'])), case['classes'], len(case['queries'])
    a = [[[0] * k for _ in range(nq)] for _ in range(n)]
    for tick, event, queue, token in events:
        for qi, query in enumerate(case['queries']):
            for term in query['terms']:
                if term['event'] == event and term['start'] <= tick <= term['end'] and term['queue'] in (-1, queue):
                    for c, w in enumerate(term['weights']):
                        a[token][qi][c] += w
    return a


def palettes(case: dict[str, Any]) -> list[list[int]]:
    if case['workload']['kind'] == 'full':
        return [list(range(case['classes'])) for _ in case['groups']]
    return [[c for c, n in enumerate(h) if n] for h in case['workload']['totals']]


def default_word(case: dict[str, Any]) -> list[int]:
    out = [0] * sum(map(len, case['groups']))
    if case['workload']['kind'] == 'hist':
        for group, hist in zip(case['groups'], case['workload']['totals']):
            colors = [c for c, amount in enumerate(hist) for _ in range(amount)]
            for token, color in zip(group, colors):
                out[token] = color
    return out


def swap_witness(case: dict[str, Any], group: int, rank: int, c: int, d: int, query: int) -> dict[str, Any]:
    ids = case['groups'][group]
    left = default_word(case)
    if case['workload']['kind'] == 'hist':
        hist = case['workload']['totals'][group].copy()
        hist[c] -= 1; hist[d] -= 1
        rest = [col for col, amount in enumerate(hist) for _ in range(amount)]
        for v, color in zip([v for j, v in enumerate(ids) if j not in (rank-1, rank)], rest):
            left[v] = color
    left[ids[rank-1]], left[ids[rank]] = c, d
    right = left.copy()
    right[ids[rank-1]], right[ids[rank]] = d, c
    return {'group': group, 'rank': rank, 'query': query, 'left': left, 'right': right}


def synthesize(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    events, ticks = run(case)
    a = coefficients(case, events)
    palette = palettes(case)
    required, witnesses = [], []
    nq = len(case['queries'])
    for gi, group in enumerate(case['groups']):
        ref = palette[gi][0]
        for r in range(1, len(group)):
            x, y = group[r-1:r+1]
            found = next(((q, c) for q in range(nq) for c in palette[gi][1:]
                          if a[x][q][c] - a[x][q][ref] != a[y][q][c] - a[y][q][ref]), None)
            if found is not None:
                q, c = found
                required.append([gi, r])
                witnesses.append(swap_witness(case, gi, r, c, ref, q))
    available = {tuple(x) for x in case['library']}
    missing = [x for x in required if tuple(x) not in available]
    result: dict[str, Any] = {'case': case['id'], 'required': required}
    if missing:
        idx = required.index(missing[0])
        result.update({'status': 'insufficient_library', 'missing': missing[0], 'witness': witnesses[idx]})
    else:
        offset = [0] * nq
        blocks = []
        for gi, group in enumerate(case['groups']):
            ref = palette[gi][0]
            for token in group:
                for q in range(nq):
                    offset[q] += a[token][q][ref]
            bounds = [0] + [r for g, r in required if g == gi] + [len(group)]
            for start, stop in zip(bounds, bounds[1:]):
                token = group[start]
                values = [[a[token][q][c]-a[token][q][ref] if c in palette[gi] else 0
                           for c in range(case['classes'])] for q in range(nq)]
                blocks.append({'group': gi, 'start': start, 'stop': stop, 'weights': values})
        result.update({'status': 'adequate', 'cuts': required, 'offset': offset, 'blocks': blocks, 'witnesses': witnesses})
    return result, {'simulation_ticks': ticks, 'event_records': len(events),
                    'coefficient_cells': len(a)*nq*case['classes']}
