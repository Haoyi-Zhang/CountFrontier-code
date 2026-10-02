"""Pre-lock discriminating pilot; explicit service paths, packet replay and mutants."""
import os,resource,time,json,copy,itertools
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
resource.setrlimit(resource.RLIMIT_CPU,(110,110))
from countcuts.frontier import synthesize
from countcuts.frontier_check import check,packet_replay,Rejected
from countcuts.frontier_cases import cases,make
start,wall=time.process_time(),time.monotonic()
obligations=0;rows=[]
from pathlib import Path
for c in json.loads(Path('inputs/pilots.json').read_text())['frontier']:
    cert,stats=synthesize(c);verified=check(c,cert)
    obligations+=stats['states']+stats['transitions']+verified['states']+verified['transitions']+verified['witness_replay_ticks']+verified['earlier_query_checks']
    row={'case':c['id'],'required':cert['required'],'status':cert['status'],'producer':stats,'checker':verified}
    if c['horizon']==3:
        reached=[set() for _ in range(4)]
        for seq in itertools.product(((0,0),(0,1),(1,0),(1,1)),repeat=3):
            path,_,dep=packet_replay(c,[[0]*4],[list(a) for a in seq])
            for t,s in enumerate(path):reached[t].add(s)
            assert dep==[tuple(x) for x in cert['merge_word'][:path[-1][1]]]
            obligations+=3
        assert reached==[set(map(tuple,layer)) for layer in cert['layers']]
        row['explicit_service_paths']=64
    mutant=copy.deepcopy(cert)
    mutant['layers'][-1]=mutant['layers'][-1][1:] if len(mutant['layers'][-1])>1 else [[0,0,0,0]]
    try:check(c,mutant)
    except Rejected:row['omitted_reachable_state_rejected']=True
    else:raise AssertionError('checker accepted omission')
    # Conservative charge: the whole clean check, even for early rejection.
    obligations+=verified['states']+verified['transitions']+verified['witness_replay_ticks']+verified['earlier_query_checks']
    rows.append(row)
result={'status':'passed_frontier_finite_pilot','rows':rows,'obligations':obligations,'cpu_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1}
from pathlib import Path
Path('results/frontier_pilot.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
