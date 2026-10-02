"""Benign negative controls and malformed-certificate tests.

Tests are of owned, finite toy inputs. No third-party systems are contacted.
"""
from copy import deepcopy
from . import engine,checker,frontier,frontier_check,restricted,restricted_check
from .cases import build,term


def ensure(condition, message):
    """Explicit test invariant that remains active with interpreter optimization."""
    if not condition:
        raise AssertionError(message)


def run(fixed_rows,frontier_rows):
    outcomes=[];charged=0
    # A genuine adequate fixed-schedule result with one required boundary.
    row=next(r for r in fixed_rows if r['case']['id']=='ordered-fifo')
    c,cert=row['case'],row['certificate']
    cost=row['checker']['simulation_ticks']*(1+2*row['checker']['witness_pairs'])+sum(len(g)-1 for g in c['groups'])+1
    def bad_fixed(name,change):
        nonlocal charged
        cc,bc=deepcopy(c),deepcopy(cert);change(cc,bc)
        try:checker.check(cc,bc)
        except (ValueError,TypeError,KeyError,IndexError):outcomes.append({'test':name,'outcome':'rejected'})
        else:raise AssertionError('accepted fixed mutation: '+name)
        charged+=cost
    bad_fixed('constant_offset',lambda c,b:b['offset'].__setitem__(0,b['offset'][0]+1))
    bad_fixed('block_coefficient',lambda c,b:b['blocks'][0]['weights'][0].__setitem__(0,9))
    bad_fixed('required_cut_omission',lambda c,b:b['required'].clear())
    bad_fixed('necessity_pair_omission',lambda c,b:b['witnesses'].clear())
    bad_fixed('nonseparating_pair',lambda c,b:b['witnesses'][0].__setitem__('right',b['witnesses'][0]['left'].copy()))
    bad_fixed('invalid_packet_class',lambda c,b:b['witnesses'][0]['left'].__setitem__(0,8))
    bad_fixed('query_mutation',lambda c,b:c['queries'][0]['terms'][0].__setitem__('end',3))
    bad_fixed('class_sensitive_policy',lambda c,b:c.__setitem__('policy','class_priority'))

    row=next(r for r in frontier_rows if r['case']['id']=='frontier03')
    c,cert=row['case'],row['certificate']
    cost=row['checker']['states']+row['checker']['transitions']+row['checker']['witness_replay_ticks']+row['checker']['earlier_query_checks']+sum(n-1 for n in c['lengths'])+1
    def bad_frontier(name,change):
        nonlocal charged
        cc,bc=deepcopy(c),deepcopy(cert);change(cc,bc)
        try:frontier_check.check(cc,bc)
        except (ValueError,TypeError,KeyError,IndexError):outcomes.append({'test':name,'outcome':'rejected'})
        else:raise AssertionError('accepted frontier mutation: '+name)
        charged+=cost
    bad_frontier('reachable_layer_omission',lambda c,b:b['layers'][-1].pop())
    bad_frontier('fabricated_reachable_state',lambda c,b:b['layers'][1].append([0,0,0,0]))
    bad_frontier('merge_order_mutation',lambda c,b:b['merge_word'].__setitem__(0,b['merge_word'][1]))
    bad_frontier('frontier_required_omission',lambda c,b:b['required'].pop())
    bad_frontier('unneeded_candidate_cut',lambda c,b:b['cuts'].append([1,12]))
    bad_frontier('service_budget_violation',lambda c,b:b['witnesses'][0]['actions'].__setitem__(0,[0,0]))
    bad_frontier('shorter_unqueried_endpoint',lambda c,b:b['witnesses'][0].__setitem__('time',1))
    bad_frontier('frontier_nonsenseparation',lambda c,b:b['witnesses'][0].__setitem__('right',deepcopy(b['witnesses'][0]['left'])))
    bad_frontier('earlier_query_added',lambda c,b:c['queries'].append({'time':2,'class':0}))
    bad_frontier('library_cut_removed',lambda c,b:c['library'].remove([0,11]))
    bad_frontier('taildrop_schema_extension',lambda c,b:c.__setitem__('taildrop',True))
    bad_frontier('downstream_lifo_schema_extension',lambda c,b:c.__setitem__('sink_discipline','lifo'))
    bad_frontier('arrivals_schema_extension',lambda c,b:c.__setitem__('arrivals',[]))
    bad_frontier('frontier_class_sensitive_policy',lambda c,b:c.__setitem__('policy','class_priority'))
    # A bounded incomplete exploration must never return an adequacy answer.
    try:frontier.explore(c,max_transitions=1)
    except RuntimeError as e:
        ensure('INCOMPLETE' in str(e), 'producer resource exception lost the INCOMPLETE marker')
        outcomes.append({'test':'producer_transition_limit','outcome':'INCOMPLETE'})
    else:raise AssertionError('limit produced an answer')
    try:frontier_check.check(c,cert,max_transitions=1)
    except frontier_check.Rejected as e:
        ensure('INCOMPLETE' in str(e), 'checker resource exception lost the INCOMPLETE marker')
        outcomes.append({'test':'checker_transition_limit','outcome':'INCOMPLETE'})
    else:raise AssertionError('checker limit accepted')
    charged+=6

    negatives=[]
    # A valid restricted-support negative certificate must be accepted, while the
    # same certificate becomes false as soon as the missing separator is eligible.
    rc=restricted.make_case(2,[[2]],'restricted-library-gap');rc['library']=[1]
    rcert,rstats=restricted.synthesize(rc)
    ensure(rcert['status']=='insufficient_library', 'restricted gap did not produce an insufficiency certificate')
    rchecked=restricted_check.check(rc,rcert)
    negatives.append({'model':rc,'control':'restricted_insufficient_library','certificate':rcert,'checker':rchecked})
    charged+=rstats['pair_candidate_obligations']+rchecked['word_checks']+rchecked['replay_ticks']
    false_model=deepcopy(rc);false_model['library']=[1,2]
    try:restricted_check.check(false_model,rcert)
    except (ValueError,TypeError,KeyError,IndexError):outcomes.append({'test':'restricted_false_insufficiency','outcome':'rejected'})
    else:raise AssertionError('accepted false restricted insufficiency')
    charged+=rchecked['word_checks']+rchecked['replay_ticks']

    t=build('taildrop-boundary',[3],[[]],[3],4,k=2,tandem=True,query_count=1,sink_capacity=1)
    t['active']=[True,True,True,False];t['sink']['active']=[False,False,True,True]
    l=build('lifo-boundary',[2],[[]],[2],3,k=2,tandem=True,query_count=1,sink_capacity=2)
    l['active']=[True,True,False];l['sink']['active']=[False,False,True];l['sink']['discipline']='lifo'
    for cc,expected in ((t,[0,2]),(l,[1])):
        a,_=engine.run(cc);b,_=checker.replay(cc)
        ensure(sorted(a)==sorted(b), 'boundary producer/checker trace mismatch')
        deps=[p for _,ev,_,p in a if ev=='depart']
        ensure(deps==expected, 'boundary control has an unexpected departure sequence')
        ensure(deps!=list(range(len(deps))), 'boundary control failed to refute a prefix-order extension')
        negatives.append({'model':cc,'departed_tokens':deps,'merge_prefix_extension':'refuted'})
        charged+=2*cc['horizon']
    arrival=build('arrival-boundary',[0,1],[[2],[]],[1,1],2,k=2,query_count=1)
    orders=[]
    for acts in ([True,True],[False,True]):
        cc=deepcopy(arrival);cc['active']=acts
        a,_=engine.run(cc);b,_=checker.replay(cc)
        ensure(sorted(a)==sorted(b), 'arrival producer/checker trace mismatch')
        orders.append([p for _,e,_,p in a if e=='depart']);charged+=4
    ensure(orders==[[1,0],[0]], 'arrival control has unexpected departure sequences')
    negatives.append({'model':arrival,'schedules':[[True,True],[False,True]],'departure_sequences':orders,'fixed_merge_extension':'refuted'})
    table=[{'left':a,'right':b,'first_class_one':int(bool(a or b))} for a in (0,1) for b in (0,1)]
    ensure(table[3]['first_class_one']-table[2]['first_class_one']-table[1]['first_class_one']+table[0]['first_class_one']==-1,
           'class-sensitive OR control lost its nonzero mixed difference')
    negatives.append({'control':'class_sensitive_OR','truth_table':table,'mixed_difference':-1});charged+=4

    # Centering ablation with real occupancy events, not invented coefficients.
    cc=build('centering-control',[6],[[]],[6],6,k=2,query_count=1)
    cc['queries']=[{'terms':[dict(term('occupancy',6),weights=[1,1])]}]
    good,st=engine.synthesize(cc);ck=checker.check(cc,good)
    trace,_=engine.run(cc);a=engine.coefficients(cc,trace)
    raw=[r for r in range(1,6) if a[r-1]!=a[r]]
    ensure(good['required']==[] and raw==[1,2,3,4,5],
           'centering control no longer distinguishes correct and uncentered cuts')
    negatives.append({'model':cc,'control':'no_centering','correct_required':[],'uncentered_cuts':raw})
    charged+=3*cc['horizon']+3*5
    # Active palette is part of the theorem, not an optimization to assume away.
    mono=next(r for r in fixed_rows if r['case']['id']=='monochrome-control')
    mc=deepcopy(mono['case']);mc['workload']={'kind':'full'}
    full,st=engine.synthesize(mc)
    ensure(mono['certificate']['required']==[] and bool(full['required']),
           'active-palette control no longer distinguishes restricted and full support')
    negatives.append({'control':'ignore_active_palette','correct_required':[],'full_palette_required':full['required'],'case':'monochrome-control'})
    charged+=mc['horizon']+sum(len(g)-1 for g in mc['groups'])
    return {'mutations':outcomes,'negative_controls':negatives,'obligations':charged}
