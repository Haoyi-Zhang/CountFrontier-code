"""Independent validation of frontier certificates; no producer imports.

The mathematical proof is handwritten, not mechanized. Implementation diversity
here means a separately expressed replay and boundary computation, not human-
independent review. Invalid input or certificates raise Rejected.
"""
from __future__ import annotations
from itertools import product
from typing import Any


class Rejected(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise Rejected(message)


def integer(x: Any, lo: int, hi: int) -> bool:
    return type(x) is int and lo <= x <= hi


def validate_merge_word(c: dict[str, Any], value: Any) -> None:
    """Require JSON-array token identities with strict bounded integer indices."""
    lengths = c['lengths']
    require(type(value) is list and len(value) == sum(lengths), 'merge word encoding')
    seen: set[tuple[int, int]] = set()
    for token in value:
        require(type(token) is list and len(token) == 2, 'merge token encoding')
        source = token[0]
        require(integer(source, 0, len(lengths)-1), 'merge source index')
        rank = token[1]
        require(integer(rank, 0, lengths[source]-1), 'merge rank index')
        pair = (source, rank)
        require(pair not in seen, 'duplicate merge token')
        seen.add(pair)
    require(len(seen) == sum(lengths), 'incomplete merge word')


def validate_cut(c: dict[str, Any], value: Any, message: str) -> tuple[int, int]:
    """Return a strictly typed interior source-rank cut."""
    lengths = c['lengths']
    require(type(value) is list and len(value) == 2, message)
    source = value[0]
    require(integer(source, 0, len(lengths)-1), message)
    rank = value[1]
    require(integer(rank, 1, lengths[source]-1), message)
    return source, rank


def validate_cut_list(c: dict[str, Any], value: Any, message: str) -> list[tuple[int, int]]:
    """Require a canonical, duplicate-free JSON list of strict integer cuts."""
    require(type(value) is list, message)
    pairs = [validate_cut(c, cut, message) for cut in value]
    require(len(pairs) <= sum(n-1 for n in c['lengths']), message)
    require(len(set(pairs)) == len(pairs), message)
    require(pairs == sorted(pairs), message)
    return pairs


def validate_witness_header(c: dict[str, Any], w: Any) -> tuple[int, int, dict[str, int]]:
    """Validate cut and declared-query endpoint fields before any comparison/use."""
    require(type(w) is dict and set(w) == {'cut','query','time','actions','left','right'}, 'witness fields')
    source, rank = validate_cut(c, w['cut'], 'witness cut')
    require(integer(w['query'], 0, len(c['queries'])-1), 'witness query')
    require(integer(w['time'], 1, c['horizon']), 'witness endpoint')
    query = c['queries'][w['query']]
    require(w['time'] == query['time'], 'witness endpoint')
    require(type(w['actions']) is list and len(w['actions']) == w['time'], 'witness endpoint')
    return source, rank, query


def wellformed(c: dict[str, Any]) -> None:
    require(type(c) is dict and set(c) == {'id','classes','horizon','lengths','disciplines','policy','weights','sink_capacity','environment','queries','library','workload'}, 'model fields')
    require(type(c['id']) is str and 0 < len(c['id']) <= 80, 'model identifier')
    require(integer(c['classes'], 2, 4) and integer(c['horizon'], 1, 48), 'model dimensions')
    ns = c['lengths']
    require(type(ns) is list and 1 <= len(ns) <= 4 and all(integer(n,1,24) for n in ns), 'initial source lengths')
    require(type(c['disciplines']) is list and len(c['disciplines']) == len(ns) and all(d in ('fifo','lifo') for d in c['disciplines']), 'source order')
    require(c['policy'] in ('priority','rr','wrr'), 'arbitration is class blind')
    require(type(c['weights']) is list and len(c['weights']) == len(ns) and all(integer(v,1,4) for v in c['weights']), 'calendar weights')
    require(integer(c['sink_capacity'],1,24), 'downstream capacity')
    e = c['environment']
    require(type(e) is dict, 'environment object')
    require(e == {'kind':'free'} or (set(e) == {'kind','up_stalls','down_stalls'} and e['kind'] == 'budget' and integer(e['up_stalls'],0,2) and integer(e['down_stalls'],0,2)), 'supported service language')
    qs = c['queries']
    require(type(qs) is list and 1 <= len(qs) <= 32, 'query family size')
    for q in qs:
        require(type(q) is dict and set(q) == {'time','class'} and integer(q['time'],1,c['horizon']) and integer(q['class'],0,c['classes']-1), 'prefix query')
    lib = c['library']
    require(type(lib) is list and len(lib) <= 6, 'candidate library')
    for cut in lib:
        require(type(cut) is list and len(cut) == 2 and integer(cut[0],0,len(ns)-1) and integer(cut[1],1,ns[cut[0]]-1), 'eligible rank')
    require(len({tuple(x) for x in lib}) == len(lib), 'duplicate cut')
    w = c['workload']
    require(type(w) is dict, 'workload object')
    if w != {'kind':'full'}:
        require(set(w) == {'kind','totals'} and w['kind'] == 'hist' and type(w['totals']) is list and len(w['totals']) == len(ns), 'shuffle support')
        for n, hist in zip(ns,w['totals']):
            require(type(hist) is list and len(hist) == c['classes'] and all(integer(v,0,n) for v in hist) and sum(hist) == n, 'fixed histogram')


def order(c: dict[str, Any]) -> list[list[int]]:
    """Generate token order using consumption counters, not packet queues."""
    used = [0] * len(c['lengths'])
    cyc = [i for i in range(len(used)) for _ in range(c['weights'][i] if c['policy'] == 'wrr' else 1)]
    cursor, out = 0, []
    for _ in range(sum(c['lengths'])):
        if c['policy'] == 'priority':
            g = min(i for i in range(len(used)) if used[i] < c['lengths'][i])
        else:
            while used[cyc[cursor]] == c['lengths'][cyc[cursor]]:
                cursor = (cursor+1) % len(cyc)
            g = cyc[cursor]; cursor = (cursor+1) % len(cyc)
        rank = used[g] if c['disciplines'][g] == 'fifo' else c['lengths'][g]-used[g]-1
        out.append([g,rank]); used[g] += 1
    return out


def next_states(c, state):
    n, b = sum(c['lengths']), c['sink_capacity']
    u,d,su,sd = state
    for enabled in product((False,True), repeat=2):
        eu,ed = enabled
        stalls = (su+int(not eu),sd+int(not ed))
        if c['environment']['kind'] == 'budget':
            if stalls[0] > c['environment']['up_stalls'] or stalls[1] > c['environment']['down_stalls']:
                continue
        else:
            stalls = (0,0)
        served = int(ed and u > d)
        transferred = int(eu and u < n and u-(d+served) < b)
        yield (u+transferred,d+served,*stalls)


def boundary_records(c, layers, word):
    """A cut is needed when exactly one adjacent token has departed."""
    result = []
    for qi,q in enumerate(c['queries']):
        t,col = q['time'],q['class']
        for d in sorted({s[1] for s in layers[t]}):
            membership = {tuple(token) for token in word[:d]}
            for g,n in enumerate(c['lengths']):
                allowed = list(range(c['classes'])) if c['workload']['kind'] == 'full' else [j for j,v in enumerate(c['workload']['totals'][g]) if v]
                if col not in allowed or len(allowed) < 2:
                    continue
                for r in range(1,n):
                    if ((g,r-1) in membership) != ((g,r) in membership):
                        result.append((t,qi,g,r))
    return sorted(set(result))


def valid_colors(c, rows):
    require(type(rows) is list and len(rows) == len(c['lengths']), 'colored sources')
    for g,(row,n) in enumerate(zip(rows,c['lengths'])):
        require(type(row) is list and len(row) == n and all(integer(v,0,c['classes']-1) for v in row), 'packet classes')
        if c['workload']['kind'] == 'hist':
            require([row.count(col) for col in range(c['classes'])] == c['workload']['totals'][g], 'word outside fixed-histogram support')


def observation(c, rows, cuts):
    return tuple(tuple(row[:r].count(col) for col in range(c['classes'])) for g,row in enumerate(rows) for r in [c['lengths'][g]] + sorted(k for i,k in cuts if i == g))


def packet_replay(c, rows, actions):
    """Actual token lists, cyclic arbiter, FIFO downstream, blocking transfer."""
    valid_colors(c, rows)
    sources = [[(g,j) for j in range(n)] for g,n in enumerate(c['lengths'])]
    sink, departed = [], []
    calendar = [i for i in range(len(sources)) for _ in range(c['weights'][i] if c['policy'] == 'wrr' else 1)]
    pointer = su = sd = u = 0
    path = [(0,0,0,0)]
    answer_vectors = [[0]*c['classes']]
    require(type(actions) is list and len(actions) <= c['horizon'], 'service trace length')
    for action in actions:
        require(type(action) is list and len(action) == 2 and all(integer(x,0,1) for x in action), 'service action')
        a,b = action; su += 1-a; sd += 1-b
        if c['environment']['kind'] == 'budget':
            require(su <= c['environment']['up_stalls'] and sd <= c['environment']['down_stalls'], 'service budget')
        if b and sink:
            departed.append(sink.pop(0))
        if a and len(sink) < c['sink_capacity'] and any(sources):
            if c['policy'] == 'priority':
                g = next(i for i,v in enumerate(sources) if v)
            else:
                for _ in calendar:
                    g = calendar[pointer]; pointer = (pointer+1) % len(calendar)
                    if sources[g]:
                        break
            item = sources[g].pop(0 if c['disciplines'][g] == 'fifo' else -1)
            sink.append(item); u += 1
        path.append((u,len(departed),su if c['environment']['kind']=='budget' else 0,sd if c['environment']['kind']=='budget' else 0))
        answer_vectors.append([sum(rows[g][j] == col for g,j in departed) for col in range(c['classes'])])
    return path,answer_vectors,departed


def check_witness(c,w,records,word,layers):
    g,r,q = validate_witness_header(c,w)
    require((g,r) in {(gg,rr) for _,_,gg,rr in records}, 'witness cut')
    require((q['time'],w['query'],g,r) in records, 'witness is a query boundary')
    earliest = min(t for t,_,gg,rr in records if (gg,rr)==(g,r))
    require(w['time'] == earliest, 'witness must reach the earliest query exposing this cut')
    for side in ('left','right'):
        valid_colors(c,w[side])
    diffs = [(i,j) for i,(a,b) in enumerate(zip(w['left'],w['right'])) for j,(x,y) in enumerate(zip(a,b)) if x != y]
    require(diffs == [(g,r-1),(g,r)], 'adjacent two-position witness')
    all_other = [(i,j) for i,n in enumerate(c['lengths']) for j in range(1,n) if (i,j)!=(g,r)]
    require(observation(c,w['left'],all_other) == observation(c,w['right'],all_other), 'witness changes another cut or a total')
    pa,aa,da = packet_replay(c,w['left'],w['actions'])
    pb,ab,db = packet_replay(c,w['right'],w['actions'])
    require(pa == pb and da == db, 'class-blind control differs')
    require(all(s in layers[t] for t,s in enumerate(pa)), 'witness outside certified reachability')
    require(da == [tuple(x) for x in word[:pa[-1][1]]], 'merge-prefix invariant in packet replay')
    earlier_checks = 0
    for earlier in c['queries']:
        if earlier['time'] < w['time']:
            earlier_checks += 1
            require(aa[earlier['time']][earlier['class']] == ab[earlier['time']][earlier['class']], 'witness separates an earlier declared query')
    require(aa[-1][q['class']] != ab[-1][q['class']], 'nonseparating witness')
    return 2*w['time'],earlier_checks


def check(c,cert,max_transitions=40000):
    wellformed(c)
    require(type(cert) is dict and cert.get('case') == c['id'], 'certificate identity')
    status = cert.get('status')
    common = {'case','merge_word','layers','required','status'}
    require(status in ('adequate','insufficient_library'), 'certificate status')
    require(set(cert) == common | ({'cuts','witnesses'} if status=='adequate' else {'earliest_failure','witness'}), 'certificate fields')
    validate_merge_word(c, cert['merge_word'])
    word = order(c)
    require(cert['merge_word'] == word, 'merge word')
    raw = cert['layers']
    require(type(raw) is list and len(raw) == c['horizon']+1, 'reachable layers')
    layers = []
    for layer in raw:
        require(type(layer) is list and 0 < len(layer) <= 40001, 'layer size')
        for s in layer:
            require(type(s) is list and len(s)==4 and all(type(x) is int for x in s), 'state encoding')
            require(0 <= s[1] <= s[0] <= sum(c['lengths']) and s[0]-s[1] <= c['sink_capacity'] and 0 <= s[2] <= 2 and 0 <= s[3] <= 2, 'state bounds')
        require(layer == [list(s) for s in sorted(set(map(tuple,layer)))], 'canonical distinct states')
        layers.append(set(map(tuple,layer)))
    require(layers[0] == {(0,0,0,0)}, 'initial reachability')
    transitions = 0
    for t in range(c['horizon']):
        image = set()
        for state in layers[t]:
            for after in next_states(c,state):
                transitions += 1
                require(transitions <= max_transitions, 'INCOMPLETE: checker transition budget exhausted')
                image.add(after)
        require(layers[t+1] == image, 'inexact reachable layer')
    records = boundary_records(c,layers,word)
    needed = [list(v) for v in sorted({(g,r) for _,_,g,r in records})]
    validate_cut_list(c, cert['required'], 'required cuts')
    require(cert['required'] == needed, 'required cuts')
    missing = [v for v in records if [v[2],v[3]] not in c['library']]
    ticks = 0
    earlier_checks = 0
    if status == 'adequate':
        validate_cut_list(c, cert['cuts'], 'candidate cuts')
        require(not missing and cert['cuts'] == needed, 'inadequate or nonleast candidate')
        ws = cert['witnesses']
        require(type(ws) is list and len(ws) == len(needed), 'necessity witnesses')
        witness_cuts = [[g,r] for g,r,_ in (validate_witness_header(c,w) for w in ws)]
        require(witness_cuts == needed, 'witness coverage')
        for w in ws:
            replay_ticks,prior = check_witness(c,w,records,word,layers)
            ticks += replay_ticks; earlier_checks += prior
    else:
        require(bool(missing), 'false insufficiency')
        earliest = min(v[0] for v in missing)
        require(integer(cert['earliest_failure'], 1, c['horizon']), 'earliest failure endpoint')
        witness = cert['witness']
        g,r,_ = validate_witness_header(c,witness)
        require(cert['earliest_failure'] == earliest and witness['time'] == earliest, 'shortest failing query time')
        require([g,r] not in c['library'], 'failure cut must be unavailable')
        replay_ticks,prior = check_witness(c,witness,records,word,layers)
        ticks += replay_ticks; earlier_checks += prior
    return {'states':sum(map(len,layers)),'transitions':transitions,'witness_replay_ticks':ticks,'earlier_query_checks':earlier_checks}
