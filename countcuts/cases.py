"""Deterministic, fully retained case specifications (not external workloads)."""
from __future__ import annotations
from copy import deepcopy


def term(event: str, end: int, k: int = 2, color: int = 1, start: int = 1, queue: int = -1, signed: bool = False) -> dict:
    weights = [int(c == color) for c in range(k)]
    if signed:
        weights[0] = -1
    return {'event': event, 'queue': queue, 'start': start, 'end': end, 'weights': weights}


def build(identifier: str, initial: list[int], incoming: list[list[int]], capacities: list[int], h: int,
          k: int = 2, policy: str = 'priority', discipline: str = 'fifo', tandem: bool = False,
          query_count: int = 4, hist: bool = False, sink_capacity: int = 2) -> dict:
    queues, groups, arrivals = [], [], []
    counter = 0
    for qi, (count, times, capacity) in enumerate(zip(initial, incoming, capacities)):
        ids = list(range(counter, counter+count+len(times))); counter += len(ids)
        groups.append(ids)
        queues.append({'capacity': capacity, 'discipline': discipline, 'initial': ids[:count]})
        arrivals.extend({'time': t, 'queue': qi, 'token': p} for t, p in zip(times, ids[count:]))
    arrivals.sort(key=lambda a: (a['time'], a['queue'], a['token']))
    candidates = []
    for divisor in (2, 4, 1, 3, 5):
        for g, group in enumerate(groups):
            r = max(1, len(group)//divisor)
            if r < len(group) and [g, r] not in candidates:
                candidates.append([g, r])
    for g, group in enumerate(groups):
        for r in range(1, len(group)):
            if [g, r] not in candidates:
                candidates.append([g, r])
    library = sorted(candidates[:6])
    queries = []
    for qi in range(query_count):
        col = (qi//8 + 1) % k
        mode = qi % 8
        if mode == 0: ts = [term('depart', h, k, col)]
        elif mode == 1: ts = [term('occupancy', h, k, col, start=h)]
        elif mode == 2: ts = [term('drop', h, k, col)]
        elif mode == 3: ts = [term('transfer', h, k, col)]
        elif mode == 4: ts = [term('depart', max(1, h//2), k, col)]
        elif mode == 5: ts = [term('depart', h, k, col, signed=True)]
        elif mode == 6: ts = [term('depart', h, k, col, start=max(1, h//2+1))]
        else: ts = [term('occupancy', h, k, col)]
        queries.append({'terms': ts})
    workload = {'kind': 'full'}
    if hist:
        totals = []
        for group in groups:
            counts = [0]*k
            for j in range(len(group)): counts[j % k] += 1
            totals.append(counts)
        workload = {'kind': 'hist', 'totals': totals}
    return {'id': identifier, 'classes': k, 'horizon': h, 'queues': queues,
            'arrivals': arrivals, 'active': [True]*h, 'policy': policy,
            'weights': [(q % 3)+1 for q in range(len(queues))],
            'sink': {'capacity': sink_capacity, 'discipline': 'fifo',
                     'active': [(t % 3 != 1) for t in range(h)]} if tandem else None,
            'groups': groups, 'library': library, 'workload': workload, 'queries': queries}


def tiny_cases() -> list[dict]:
    out = []
    for policy in ('priority', 'rr', 'wrr'):
        for discipline in ('fifo', 'lifo'):
            for tandem in (False, True):
                i = len(out)
                # Four tokens, two initially resident and two same-tick arrivals.
                c = build(f'tiny-{i:02d}', [1, 1], [[1], [1]], [1+(i % 2), 2], 5,
                          k=2+(i % 3 == 0), policy=policy, discipline=discipline,
                          tandem=tandem, query_count=6, sink_capacity=1)
                c['active'] = [True, False, True, True, True]
                out.append(c)
    # Fixed histogram copies: exact shuffle support, not a distributional sample.
    for base in out[:6]:
        c = deepcopy(base); c['id'] += '-hist'
        c['workload'] = {'kind': 'hist', 'totals': [[1, 1]+[0]*(c['classes']-2) for _ in c['groups']]}
        out.append(c)
    for disc in ('fifo', 'lifo'):
        c = build('ordered-'+disc, [6], [[]], [6], 6, discipline=disc, query_count=1)
        c['queries'] = [{'terms': [term('depart', 4)]}]
        out.append(c)
    return out


def large_cases() -> list[dict]:
    out = []
    for policy in ('priority', 'rr', 'wrr'):
        for discipline in ('fifo', 'lifo'):
            for n in (12, 24, 48, 96):
                m = 1 if n == 12 else (2 if n == 24 else 4)
                size = n//m
                initial = [size//2]*m
                incoming = [[1 + 2*j for j in range(size-size//2)] for _ in range(m)]
                capacities = [min(24, max(2, size//2))]*m
                h = 48 if n >= 48 else 24
                i = len(out)
                c = build(f'scale-{i:02d}', initial, incoming, capacities, h,
                          k=4, policy=policy, discipline=discipline,
                          tandem=(i % 2 == 1), query_count={12: 4, 24: 8, 48: 16, 96: 32}[n],
                          hist=(i % 3 == 0), sink_capacity=2+(i % 3))
                c['active'] = [t % 5 != 2 for t in range(h)]
                out.append(c)
    # Structured success cases: terminal service/remaining counts, four sources.
    for policy in ('priority', 'rr', 'wrr'):
        for size in (12, 24):
            n, h = 4*size, 2*size
            c = build(f'terminal-{policy}-{size}', [size]*4, [[]]*4, [size]*4, h,
                      k=4, policy=policy, query_count=4)
            # Cut library chosen by a fixed arithmetic rule, not after synthesis.
            c['library'] = sorted([[g, size//2] for g in range(4)]+[[0, size//4], [1, size//4]])
            out.append(c)
    # Monochromatic support is a declared negative control, not breadth evidence.
    c = deepcopy(out[-1]); c['id'] = 'monochrome-control'
    c['workload'] = {'kind': 'hist', 'totals': [[len(g), 0, 0, 0] for g in c['groups']]}
    out.append(c)
    return out
