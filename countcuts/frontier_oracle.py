"""Complete service-word-cut cross product, only for tiny frontier models."""
from itertools import product,combinations
from .frontier_check import packet_replay,observation
from .frontier_eval import encode,evaluate


def ensure(condition, message):
    """Oracle consistency check that remains active under ``python -O``."""
    if not condition:
        raise RuntimeError(message)


def oracle(c,cert):
    n=sum(c['lengths']);h=c['horizon'];k=c['classes']
    if c['environment']!={'kind':'free'} or h>3 or k**n>16:
        raise ValueError('oracle bound: free service, <=3 ticks, <=16 words')
    cuts=[list(combo) for r in range(len(c['library'])+1) for combo in combinations(c['library'],r)]
    tables=[{} for _ in cuts];adequate=[True]*len(cuts)
    words=[]
    for flat in product(range(k),repeat=n):
        rows=[];offset=0
        for size in c['lengths']:rows.append(list(flat[offset:offset+size]));offset+=size
        if c['workload']['kind']=='hist' and any([row.count(col) for col in range(k)]!=hist for row,hist in zip(rows,c['workload']['totals'])):continue
        words.append(rows)
    comparisons=ticks=decodes=0
    reached=[set() for _ in range(h+1)]
    for sequence in product(((0,0),(0,1),(1,0),(1,1)),repeat=h):
        for rows in words:
            path,values,departures=packet_replay(c,rows,[list(a) for a in sequence]);ticks+=h
            for t,s in enumerate(path):reached[t].add(s)
            ensure(departures==[tuple(v) for v in cert['merge_word'][:path[-1][1]]],
                   'packet replay violates the certified merge-prefix invariant')
            q=tuple(values[x['time']][x['class']] for x in c['queries'])
            for i,s in enumerate(cuts):
                key=(tuple(path),observation(c,rows,s));comparisons+=1
                if key in tables[i] and tables[i][key]!=q:adequate[i]=False
                else:tables[i][key]=q
            if cert['status']=='adequate':
                blocks=encode(c,rows,cert['cuts'])
                for qi,query in enumerate(c['queries']):
                    ensure(evaluate(c,cert,blocks,qi,path[query['time']][1])==q[qi],
                           'abstract decoder disagrees with direct packet replay')
                    decodes+=1
    ensure(reached==[set(map(tuple,layer)) for layer in cert['layers']],
           'complete tiny oracle and certified reachable layers disagree')
    for s,good in zip(cuts,adequate):
        ensure(good==all(cut in s for cut in cert['required']),
               'complete tiny oracle disagrees with the required-cut criterion')
    return {'service_paths':4**h,'colorings':len(words),'candidate_count':len(cuts),
            'candidates':[{'cuts':s,'adequate':a} for s,a in zip(cuts,adequate)],
            'word_candidate_obligations':comparisons,'packet_replay_ticks':ticks,'abstract_query_evaluations':decodes}
