"""Measured pre-lock pilot: arrivals, contention, drops, tandem, and exact oracle."""
import json, os, resource, time
from pathlib import Path
from countcuts.cases import tiny_cases, large_cases
from countcuts.engine import synthesize, run
from countcuts.checker import check, replay
from countcuts.oracle import oracle


def main():
    if hasattr(os, 'sched_getaffinity'):
        os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS, (2*1024**3, 2*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (110, 110))
    begin, wall = time.process_time(), time.perf_counter()
    selected = [tiny_cases()[j] for j in (1, 7, 11)]
    hard = large_cases()[3]
    hardcert, hm = synthesize(hard)
    hc = check(hard, hardcert)
    rows = []
    total = hm['simulation_ticks']+hc['simulation_ticks']+hc['witness_pairs']
    for c in selected:
        cert, sm = synthesize(c)
        cm = check(c, cert)
        left, _ = run(c); right, _ = replay(c)
        assert sorted(left) == sorted(right)
        exact = oracle(c)
        r = {tuple(v) for v in cert['required']}
        assert all(row['adequate'] == (r <= {tuple(v) for v in row['cuts']}) for row in exact['candidates'])
        used = exact['word_candidate_obligations'] + sm['simulation_ticks']+cm['simulation_ticks']+exact['simulation_ticks']+2*c['horizon']+cm['witness_pairs']
        total += used
        rows.append({'id': c['id'], 'certificate': cert['status'], 'required': cert['required'],
                     'colorings': exact['colorings'], 'candidates': len(exact['candidates']), 'obligations': used})
    # Changed certificate must be rejected, rather than used as an oracle label.
    import copy
    bad = copy.deepcopy(cert); bad['blocks'][0]['weights'][0][0] += 1
    try: check(selected[-1], bad)
    except ValueError: rejected = True
    else: rejected = False
    assert rejected
    result = {'status': 'passed_end_to_end_finite_pilot', 'cases': rows,
              'hardest_dimensions': {'tokens': 96, 'classes': 4, 'horizon': 48, 'queries': 32, 'library_elements': 64, 'status': hardcert['status']},
              'obligations': total + selected[-1]['horizon'], 'coefficient_mutation_rejected': rejected,
              'cpu_seconds': time.process_time()-begin, 'wall_seconds': time.perf_counter()-wall,
              'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'workers': 1,
              'scope': 'finite independent-implementation cross-check, not mechanized general proof'}
    path = Path('results/end_to_end_pilot.json'); path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
