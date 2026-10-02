"""Numeric labels for a validated frontier certificate.

Call the standalone checker first. Counts here concern immutable source blocks;
this module is not a physical queue update implementation.
"""
def encode(c, colors, cuts):
    blocks=[]
    for g,n in enumerate(c['lengths']):
        ends=[0]+sorted(r for i,r in cuts if i==g)+[n]
        blocks.append([(a,b,[colors[g][a:b].count(col) for col in range(c['classes'])]) for a,b in zip(ends,ends[1:])])
    return blocks


def evaluate(c, certificate, blocks, query_index, departed):
    q=c['queries'][query_index]
    if departed not in {s[1] for s in certificate['layers'][q['time']]}:
        raise ValueError('unreachable queried frontier')
    count=[0]*len(c['lengths'])
    for source,_ in certificate['merge_word'][:departed]:count[source]+=1
    total=0
    for g,n in enumerate(c['lengths']):
        palette=list(range(c['classes'])) if c['workload']['kind']=='full' else [j for j,v in enumerate(c['workload']['totals'][g]) if v]
        if q['class'] not in palette:continue
        if len(palette)==1:
            total+=count[g];continue
        lo,hi=(0,count[g]) if c['disciplines'][g]=='fifo' else (n-count[g],n)
        for a,b,hist in blocks[g]:
            if max(a,lo)<min(b,hi):
                if not (lo<=a and b<=hi):raise ValueError('query cuts through a retained block')
                total+=hist[q['class']]
    return total
