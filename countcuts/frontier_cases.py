"""Deterministic input family, selected before the main evaluation."""
def make(name,lengths,h,policy='rr',disc=None,b=2,env=None,times=None,lib=None,hist=False,weights=None,k=4):
    disc = disc or ['fifo']*len(lengths)
    env = env or {'kind':'budget','up_stalls':0,'down_stalls':1}
    times = times or [h]
    return {'id':name,'classes':k,'horizon':h,'lengths':lengths,'disciplines':disc,'policy':policy,
            'weights':weights or [1]*len(lengths),'sink_capacity':b,'environment':env,
            'queries':[{'time':t,'class':col} for t in times for col in range(k)],
            'library':lib or [], 'workload':{'kind':'hist','totals':[[n//k+int(j<n%k) for j in range(k)] for n in lengths]} if hist else {'kind':'full'}}

def cases():
    return [
      make('frontier01',[4],3,k=2,b=1,hist=True,env={'kind':'free'},times=[1,3],lib=[[0,r] for r in range(1,4)]),
      make('frontier02',[2,2],3,k=2,b=1,env={'kind':'free'},disc=['fifo','lifo'],times=[2,3],lib=[[0,1],[1,1]]),
      make('frontier03',[24,24],24,lib=[[g,r] for g in range(2) for r in (11,12)]),
      make('frontier04',[24,24],24,policy='priority',lib=[[0,r] for r in (21,22,23)]+[[1,r] for r in (1,12,23)]),
      make('frontier05',[24,24],24,policy='wrr',weights=[1,2],b=3,env={'kind':'budget','up_stalls':1,'down_stalls':1},hist=True,lib=[[0,r] for r in (7,8,9)]+[[1,r] for r in (13,14,15)]),
      make('frontier06',[24,24],48,env={'kind':'budget','up_stalls':1,'down_stalls':1},lib=[[g,r] for g in range(2) for r in (22,23)]),
      make('frontier07',[24,24],32,b=2,env={'kind':'free'},times=[2,4,16,32],lib=[[g,r] for g in range(2) for r in (1,8,16)]),
      make('frontier08',[6],5,k=2,b=2,env={'kind':'budget','up_stalls':0,'down_stalls':0},lib=[[0,r] for r in range(1,6)]),
    ]
