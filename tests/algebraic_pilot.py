"""Bounded one-worker scientific pilot; no external dependencies or network."""
from itertools import product
from time import process_time, perf_counter
from pathlib import Path
import json, os, resource

os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
resource.setrlimit(resource.RLIMIT_CPU, (110, 110))
t0, w0 = process_time(), perf_counter()
checks = 0

def alpha(word, cuts):
    return (sum(word), *(sum(word[:i]) for i in sorted(cuts)))

def direct(coeff):
    # A row is [coefficient for class 0, coefficient for class 1].
    sig = [r[1] - r[0] for r in coeff]
    return {i for i in range(1, len(sig)) if sig[i-1] != sig[i]}

def oracle(coeff, cuts, support):
    global checks
    by_key = {}
    adequate = True
    for x in support:
        checks += 1
        k = alpha(x, cuts)
        q = sum(coeff[i][c] for i, c in enumerate(x))
        if k in by_key and by_key[k] != q:
            adequate = False
        by_key[k] = q
    return adequate

n=6
words=list(product(range(2),repeat=n))
profiles = {
    'fifo_prefix4': [[0, int(i<4)] for i in range(n)],
    'lifo_last2': [[0, int(i>=4)] for i in range(n)],
    'signed_fairness': [[-int(i<3), int(i<3)] for i in range(n)],
    'class_independent_offsets': [[i,i] for i in range(n)],
}
profile_results={}
for name, coeff in profiles.items():
    needed=direct(coeff)
    for mask in range(2**(n-1)):
        cuts={i for i in range(1,n) if mask>>(i-1)&1}
        exact=oracle(coeff,cuts,words)
        assert exact == (needed <= cuts), (name, mask)
    profile_results[name]={'required_cuts':sorted(needed), 'candidates':2**(n-1), 'colorings':len(words)}

# A purely combinatorial support construction, replayed as a FIFO prefix.
hyper_checks=0
m=4
for edge_mask in range(1,2**m):
    E={i for i in range(1,m+1) if edge_mask>>(i-1)&1}
    d=[0]+[int(i in E) for i in range(1,m+1)]+[0]
    x=tuple(int(d[i]-d[i-1]==1) for i in range(1,m+2))
    y=tuple(int(d[i]-d[i-1]==-1) for i in range(1,m+2))
    assert sum(x)==sum(y)
    r=min(E)
    assert sum(x[:r])-sum(y[:r])==1
    for mask in range(2**m):
        S={i for i in range(1,m+1) if mask>>(i-1)&1}
        hyper_checks += 1
        assert (alpha(x,S)!=alpha(y,S)) == bool(E&S)

coeff=profiles['fifo_prefix4']
widths={str(w):oracle(coeff, set(range(w,n,w)), words) for w in range(1,n+1)}
assert widths['4'] and not widths['3']
assert direct(profiles['class_independent_offsets'])==set()

# Incomparable minimal sufficient count partitions in a restricted model.
edges=[{1,3},{2,3}]
adequate=[set(i+1 for i in range(3) if mask>>i&1) for mask in range(8)]
adequate=[S for S in adequate if all(S&E for E in edges)]
minima=[S for S in adequate if not any(T<S for T in adequate)]
assert {tuple(sorted(S)) for S in minima}=={(3,), (1,2)}
result={
    'status':'passed_bounded_pilot', 'workers':1,
    'profile_cases':profile_results,
    'oracle_word_candidate_obligations':checks,
    'hypergraph_pair_candidate_obligations':hyper_checks,
    'uniform_width_adequacy':widths,
    'restricted_minimal_sets':[sorted(S) for S in minima],
    'cpu_seconds':process_time()-t0,
    'wall_seconds':perf_counter()-w0,
    'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    'negative_controls':{'width_chain_assumption':'refuted', 'uncentered_signature_overprecision':'detected', 'universal_least_element_assumption':'refuted'},
    'scope':'finite checks, not a machine-checked general proof',
}
Path('results/algebraic_pilot.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
