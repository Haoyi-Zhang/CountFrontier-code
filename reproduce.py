#!/usr/bin/env python3
"""Run the locked finite campaign offline in one worker, from retained inputs.

No third-party packages are required. A fresh output is recommended. --resume
continues only missing cases with identical retained model dictionaries; after
code changes use a clean run. Scientific metrics are not hashes or fingerprints.
"""
from __future__ import annotations
import argparse,json,os,resource,time,sys,csv,math
from pathlib import Path
from functools import reduce

BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from countcuts import engine,checker,frontier,frontier_check,restricted,restricted_check
from countcuts.cases import tiny_cases,large_cases
from countcuts.frontier_cases import cases as frontier_cases
from countcuts.oracle import oracle as fixed_oracle
from countcuts.frontier_oracle import oracle as frontier_oracle
from countcuts.frontier_audit import run as frontier_audit
from countcuts.controls import run as controls


def ensure(condition, message):
    """Keep scientific consistency checks active under ``python -O``."""
    if not condition:
        raise RuntimeError(message)


def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    temp.replace(path)


def frozen_inputs():
    generated={'fixed':tiny_cases()+large_cases(),'frontier':frontier_cases(),'restricted':restricted.all_cases()}
    retained=json.loads((BASE/'inputs/cases.json').read_text())
    if generated!=retained:raise ValueError('generated selection differs from retained frozen inputs')
    return retained


def uniform_counts(lengths,required):
    """Analytic representation baseline, NOT an enumerated full-rank lattice."""
    per=[]
    for g,n in enumerate(lengths):
        ranks=[r for i,r in required if i==g]
        per.append(reduce(math.gcd,ranks) if ranks else n)
    common=reduce(math.gcd,[r for _,r in required]) if required else max(lengths)
    return {'least_blocks':len(lengths)+len(required),'common_width':common,
            'common_uniform_blocks':sum((n+common-1)//common for n in lengths),
            'source_widths':per,'source_uniform_blocks':sum((n+w-1)//w for n,w in zip(lengths,per)),
            'ordered_positions':sum(lengths)}


def fixed_case(c):
    begin=time.process_time_ns()
    cert,stats=engine.synthesize(c)
    producer_ns=time.process_time_ns()-begin
    begin=time.process_time_ns();verified=checker.check(c,cert);checker_ns=time.process_time_ns()-begin
    n=sum(map(len,c['groups']));boundaries=n-len(c['groups'])
    # Two scheduling interpreters, two necessary-cut scans, colored witness replays.
    charge=stats['simulation_ticks']+verified['simulation_ticks']+2*boundaries+2*c['horizon']*verified['witness_pairs']
    exact=None
    if c['id'].startswith(('tiny','ordered')):
        exact=fixed_oracle(c)
        for r in exact['candidates']:
            ensure(r['adequate']==all(v in r['cuts'] for v in cert['required']),
                   'fixed exact oracle disagrees with the synthesized required-cut criterion')
        charge+=exact['simulation_ticks']+exact['word_candidate_obligations']
    return {'case':c,'certificate':cert,'producer':stats,'checker':verified,'oracle':exact,
            'obligations':charge,'producer_cpu_ns':producer_ns,'checker_cpu_ns':checker_ns,
            'certificate_bytes':len(json.dumps(cert,separators=(',',':')).encode()),
            'baselines':{'count_only_adequate':not cert['required'],'library_top_adequate':cert['status']=='adequate',
                         **uniform_counts([len(g) for g in c['groups']],cert['required'])}}


def frontier_case(c):
    begin=time.process_time_ns();cert,stats=frontier.synthesize(c);producer_ns=time.process_time_ns()-begin
    begin=time.process_time_ns();verified=frontier_check.check(c,cert);checker_ns=time.process_time_ns()-begin
    charge=stats['states']+stats['transitions']+verified['states']+verified['transitions']+verified['witness_replay_ticks']+verified['earlier_query_checks']+2*sum(n-1 for n in c['lengths'])
    exact=frontier_oracle(c,cert) if c['id'] in ('frontier01','frontier02') else None
    if exact:charge+=exact['word_candidate_obligations']+exact['packet_replay_ticks']
    return {'case':c,'certificate':cert,'producer':stats,'checker':verified,'oracle':exact,'obligations':charge,
            'producer_cpu_ns':producer_ns,'checker_cpu_ns':checker_ns,
            'certificate_bytes':len(json.dumps(cert,separators=(',',':')).encode()),
            'baselines':{'count_only_adequate':not cert['required'],'library_top_adequate':cert['status']=='adequate',
                         **uniform_counts(c['lengths'],cert['required'])}}


def restricted_case(c):
    begin=time.process_time_ns();cert,stats=restricted.synthesize(c);producer_ns=time.process_time_ns()-begin
    begin=time.process_time_ns();verified=restricted_check.check(c,cert);checker_ns=time.process_time_ns()-begin
    exact=restricted_check.enumerate_candidates(c)
    ensure(sorted(stats['minima'],key=lambda x:(len(x),x))==exact['minima'],
           'restricted producer and independent enumerator disagree on the minimal candidates')
    ensure(cert['cuts'] in exact['minima'],
           'restricted producer returned a candidate outside the independently enumerated minima')
    charge=stats['pair_candidate_obligations']+exact['word_candidate_obligations']+exact['replay_ticks']+verified['word_checks']+verified['replay_ticks']
    return {'case':c,'certificate':cert,'producer':stats,'checker':verified,'oracle':exact,'obligations':charge,
            'producer_cpu_ns':producer_ns,'checker_cpu_ns':checker_ns,
            'certificate_bytes':len(json.dumps(cert,separators=(',',':')).encode())}


def canonical_coverage(rows):
    catalog={tuple(tuple(e['cuts']) for e in row['producer']['separators']):row for row in rows}
    mappings=[];checks=0
    for mask,edges in enumerate(restricted.specifications()):
        canonical=restricted.canonical_edges(edges)
        key=tuple(map(tuple,canonical))
        # Empty family has a dummy context, but no bad pair.
        row=catalog[key]
        for candidate in row['oracle']['candidates']:
            s=set(candidate['cuts']);hits=True
            for e in edges:
                checks+=1
                if not s&set(e):hits=False
            ensure(hits==candidate['adequate'],
                   'canonical restricted-support mapping changed a candidate decision')
        mappings.append({'edge_mask':mask,'canonical_case':row['case']['id']})
    return {'specifications':128,'physical_canonical_cases':len(rows),'pair_candidate_obligations':checks,'mappings':mappings}


def run(output,resume=False):
    if hasattr(os,'sched_setaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    resource.setrlimit(resource.RLIMIT_CPU,(110,110))
    if output.exists() and any(output.iterdir()) and not resume:raise ValueError('use a fresh output directory or explicit --resume')
    output.mkdir(parents=True,exist_ok=True)
    start=time.process_time();wall=time.monotonic();inputs=frozen_inputs()
    all_rows={};total=0;executed=0
    for kind,fn in (('fixed',fixed_case),('frontier',frontier_case),('restricted',restricted_case)):
        rows=[]
        for c in inputs[kind]:
            path=output/kind/(c['id']+'.json')
            if resume and path.exists():
                row=json.loads(path.read_text())
                if row['case']!=c:raise ValueError('resumed result has a different model')
            else:
                row=fn(c);dump(path,row);executed+=row['obligations']
            rows.append(row);total+=row['obligations']
            if total>120000:raise RuntimeError('INCOMPLETE: per-campaign 120,000-obligation limit exceeded')
        all_rows[kind]=rows
    control=controls(all_rows['fixed'],all_rows['frontier']);dump(output/'controls.json',control)
    cov=canonical_coverage(all_rows['restricted']);dump(output/'coverage.json',cov)
    total+=control['obligations']+cov['pair_candidate_obligations'];executed+=control['obligations']+cov['pair_candidate_obligations']
    audit_input=json.loads((BASE/'inputs/exhaustive_frontier_audit.json').read_text())
    audit_path=output/'exhaustive_frontier_audit.json'
    if resume and audit_path.exists():
        audit=json.loads(audit_path.read_text())
        if audit.get('status')!='all_exhaustive_micro_audits_passed':raise ValueError('resumed exhaustive audit is not complete')
    else:
        audit=frontier_audit(audit_input);dump(audit_path,audit);executed+=audit['obligations']
    total+=audit['obligations']
    if total>120000:raise RuntimeError('INCOMPLETE: per-campaign 120,000-obligation limit exceeded')
    summary={'status':'all_finite_checks_passed','scope':'generated bounded models; handwritten general proofs are not mechanized',
             'case_counts':{k:len(v) for k,v in all_rows.items()},'aggregate_obligations':total,'executed_obligations_this_invocation':executed,
             'timed_cpu_seconds':time.process_time()-start,'whole_process_cpu_seconds':time.process_time(),
             'wall_seconds':time.monotonic()-wall,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
             'workers':1,'resumed':resume,'control_count':len(control['mutations']),
             'rejected_certificate_or_schema_mutations':sum(m['outcome']=='rejected' for m in control['mutations']),
             'incomplete_resource_controls':sum(m['outcome']=='INCOMPLETE' for m in control['mutations']),
             'exhaustive_micro_audit_models':audit['model_count'],
             'exhaustive_micro_audit_traces':audit['concrete_traces'],
             'exhaustive_micro_audit_candidate_comparisons':audit['candidate_comparisons'],
             'exhaustive_micro_audit_abstract_query_evaluations':audit['abstract_query_evaluations'],
             'finite_adequacy_counts':{k:{s:sum(r['certificate']['status']==s for r in rows) for s in ('adequate','insufficient_library')} for k,rows in all_rows.items()},
             'fixed_word_candidate_obligations':sum(r['oracle']['word_candidate_obligations'] for r in all_rows['fixed'] if r['oracle']),
             'frontier_word_candidate_obligations':sum(r['oracle']['word_candidate_obligations'] for r in all_rows['frontier'] if r['oracle']),
             'frontier_packet_replay_ticks':sum(r['oracle']['packet_replay_ticks'] for r in all_rows['frontier'] if r['oracle']),
             'oracle_disagreements':0}
    dump(output/'summary.json',summary)
    with (output/'case_table.csv').open('w',newline='') as f:
        fields=['family','case','tokens','classes','horizon','queries','library_elements','status','required_cuts','producer_states','producer_transitions','least_blocks','common_uniform_blocks','source_uniform_blocks','certificate_bytes','producer_cpu_ns','checker_cpu_ns','obligations']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for kind in ('fixed','frontier'):
            for r in all_rows[kind]:
                c=r['case'];bs=r['baselines'];ps=r['producer']
                writer.writerow({'family':kind,'case':c['id'],'tokens':sum(map(len,c['groups'])) if kind=='fixed' else sum(c['lengths']),
                  'classes':c['classes'],'horizon':c['horizon'],'queries':len(c['queries']),'library_elements':2**len(c['library']),
                  'status':r['certificate']['status'],'required_cuts':len(r['certificate']['required']),
                  'producer_states':ps.get('states',''),'producer_transitions':ps.get('transitions',''),
                  **{k:bs[k] for k in ('least_blocks','common_uniform_blocks','source_uniform_blocks')},
                  **{k:r[k] for k in ('certificate_bytes','producer_cpu_ns','checker_cpu_ns','obligations')}})
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args()
    try:print(json.dumps(run(args.output,args.resume),indent=2))
    except Exception as error:
        args.output.mkdir(parents=True,exist_ok=True)
        dump(args.output/'failure.json',{'status':'INCOMPLETE','error_type':type(error).__name__,'message':str(error),
            'whole_process_cpu_seconds':time.process_time(),'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
        raise
