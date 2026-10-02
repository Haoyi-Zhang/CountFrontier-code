"""FIFO realization of explicit separator families.

The hitting-set characterization and deletion algorithm are classical, not a
claimed algorithmic innovation. The mathematical construction is the object tested.
"""
from itertools import combinations


def make_case(m, edges, name):
    modes=[]
    for idx,edge in enumerate(edges):
        if not edge or not set(edge)<=set(range(1,m+1)):raise ValueError('nonempty rank edge')
        d=[0]+[int(i in edge) for i in range(1,m+1)]+[0]
        x=[int(d[i]-d[i-1]==1) for i in range(1,m+2)]
        y=[int(d[i]-d[i-1]==-1) for i in range(1,m+2)]
        modes.append({'context':idx,'service':[t<min(edge) for t in range(m)],'words':[x,y]})
    if not modes:modes=[{'context':0,'service':[False]*m,'words':[[0]*(m+1)]}]
    return {'id':name,'capacity':m+1,'horizon':m,'classes':2,'library':list(range(1,m+1)),'modes':modes}


def specifications():
    edges=[list(combo) for r in range(1,4) for combo in combinations(range(1,4),r)]
    return [[e for j,e in enumerate(edges) if mask>>j&1] for mask in range(128)]


def canonical_edges(edges):
    # Superset edges add no hitting-set constraint. This preserves all candidates.
    return sorted([e for e in edges if not any(set(f)<set(e) for f in edges)],key=lambda x:(len(x),x))


def all_cases():
    keys=sorted({tuple(map(tuple,canonical_edges(edges))) for edges in specifications()},key=lambda x:(len(x),x))
    return [make_case(3,[list(e) for e in key],f'support-{i:02d}') for i,key in enumerate(keys)]


def query(word, service):
    return sum(word[:sum(service)])


def observation(word,cuts):
    return (sum(word),*(sum(word[:r]) for r in sorted(cuts)))


def synthesize(c):
    separators=[]
    for mode in c['modes']:
        for i,j in combinations(range(len(mode['words'])),2):
            x,y=mode['words'][i],mode['words'][j]
            if sum(x)==sum(y) and query(x,mode['service'])!=query(y,mode['service']):
                separators.append({'context':mode['context'],'left':i,'right':j,
                                   'cuts':[r for r in c['library'] if sum(x[:r])!=sum(y[:r])]})
    if any(not e['cuts'] for e in separators):
        return {'case':c['id'],'status':'insufficient_library','pair':next(e for e in separators if not e['cuts'])}, {'minima':[],'separators':separators,'pair_candidate_obligations':len(separators)}
    # One inclusion-minimal result by deletion; no minimum-cardinality claim.
    chosen=c['library'].copy()
    for r in c['library']:
        trial=[v for v in chosen if v!=r]
        if all(set(trial)&set(e['cuts']) for e in separators):chosen=trial
    private=[]
    for r in chosen:
        edge=next(e for e in separators if set(e['cuts'])&set(chosen)=={r})
        private.append({'cut':r,'context':edge['context'],'left':edge['left'],'right':edge['right']})
    candidates=[list(combo) for r in range(len(c['library'])+1) for combo in combinations(c['library'],r)]
    adequate=[s for s in candidates if all(set(s)&set(e['cuts']) for e in separators)]
    minima=[s for s in adequate if not any(set(t)<set(s) for t in adequate)]
    return {'case':c['id'],'status':'adequate','cuts':chosen,'private_pairs':private}, {'minima':minima,'separators':separators,'pair_candidate_obligations':len(candidates)*len(separators),'candidate_count':len(candidates)}
