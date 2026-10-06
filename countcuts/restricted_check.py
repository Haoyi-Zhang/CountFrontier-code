"""Explicit-word FIFO oracle and checker, without importing restricted.py."""
from itertools import product


class Rejected(ValueError):pass


def need(test,reason):
    if not test:raise Rejected(reason)


def wellformed(c):
    need(type(c) is dict and set(c)=={'id','capacity','horizon','classes','library','modes'},'model fields')
    need(type(c['id']) is str and 0<len(c['id'])<=80,'model id')
    need(type(c['capacity']) is int and 1<=c['capacity']<=24 and type(c['horizon']) is int and 1<=c['horizon']<=48 and type(c['classes']) is int and c['classes']==2,'FIFO dimensions')
    lib=c['library']
    need(type(lib) is list and len(lib)<=6 and all(type(r) is int and 1<=r<c['capacity'] for r in lib) and len(lib)==len(set(lib)),'eligible cuts')
    need(type(c['modes']) is list and 1<=len(c['modes'])<=64,'finite contexts')
    contexts=[]
    for mode in c['modes']:
        need(type(mode) is dict and set(mode)=={'context','service','words'},'context fields')
        need(type(mode['context']) is int,'retained context')
        contexts.append(mode['context'])
        need(type(mode['service']) is list and len(mode['service'])==c['horizon'] and all(type(v) is bool for v in mode['service']),'service schedule')
        need(type(mode['words']) is list and 1<=len(mode['words'])<=16,'explicit support')
        for row in mode['words']:
            need(type(row) is list and len(row)==c['capacity'] and all(type(v) is int and v in (0,1) for v in row),'binary word')
    need(len(contexts)==len(set(contexts)),'duplicate context')


def replay(word,schedule):
    queue=word.copy();outputs=[]
    for enabled in schedule:
        if enabled and queue:outputs.append(queue.pop(0))
    return outputs.count(1)


def signature(c,mode,row,cuts):
    return (mode['context'],row.count(1),*(row[:r].count(1) for r in sorted(cuts)))


def enumerate_candidates(c):
    wellformed(c)
    evaluated=[(mode,row,replay(row,mode['service'])) for mode in c['modes'] for row in mode['words']]
    answers=[];comparisons=0
    for bits in product((0,1),repeat=len(c['library'])):
        cuts=[r for r,bit in zip(c['library'],bits) if bit]
        table={};okay=True
        for mode,row,q in evaluated:
            comparisons+=1
            key=signature(c,mode,row,cuts)
            if key in table and table[key]!=q:okay=False
            else:table[key]=q
        answers.append({'cuts':cuts,'adequate':okay})
    minima=[a['cuts'] for a in answers if a['adequate'] and not any(b['adequate'] and set(b['cuts'])<set(a['cuts']) for b in answers)]
    return {'candidates':answers,'minima':sorted(minima,key=lambda x:(len(x),x)),
            'word_candidate_obligations':comparisons,'replay_ticks':len(evaluated)*c['horizon']}


def check(c,cert):
    wellformed(c)
    need(type(cert) is dict and cert.get('case')==c['id'],'certificate identity')
    status=cert.get('status')
    need(status in ('adequate','insufficient_library'),'certificate status')
    if status=='insufficient_library':
        need(set(cert)=={'case','status','pair'},'insufficiency certificate')
        p=cert['pair']
        need(type(p) is dict and set(p)=={'context','left','right','cuts'},'pair fields')
        need(type(p['context']) is int,'retained context reference')
        modes=[m for m in c['modes'] if m['context']==p['context']]
        need(len(modes)==1,'unknown context');mode=modes[0]
        need(all(type(p[z]) is int and 0<=p[z]<len(mode['words']) for z in ('left','right')) and p['left']<p['right'],'word references')
        x,y=mode['words'][p['left']],mode['words'][p['right']]
        separating=[r for r in c['library'] if sum(x[:r])!=sum(y[:r])]
        need(type(p['cuts']) is list and p['cuts']==separating==[],'eligible library separates the pair')
        need(signature(c,mode,x,c['library'])==signature(c,mode,y,c['library']),'pair does not collapse under the full eligible library')
        need(replay(x,mode['service'])!=replay(y,mode['service']),'no query disagreement')
        return {'word_checks':2,'replay_ticks':2*c['horizon']}

    need(set(cert)=={'case','status','cuts','private_pairs'},'adequacy certificate')
    cuts=cert['cuts']
    need(type(cuts) is list and all(type(r) is int and r in c['library'] for r in cuts) and len(cuts)==len(set(cuts)),'candidate cuts')
    table={};word_checks=0
    for mode in c['modes']:
        for row in mode['words']:
            key=signature(c,mode,row,cuts);q=replay(row,mode['service']);word_checks+=1
            need(key not in table or table[key]==q,'nonconstant query on an abstract cell')
            table[key]=q
    pairs=cert['private_pairs']
    need(type(pairs) is list and len(pairs)==len(cuts) and [p.get('cut') for p in pairs if type(p) is dict]==cuts,'minimality pair coverage')
    for p in pairs:
        need(set(p)=={'cut','context','left','right'},'pair fields')
        need(type(p['cut']) is int and p['cut'] in cuts and type(p['context']) is int,'integer private-pair references')
        modes=[m for m in c['modes'] if m['context']==p['context']]
        need(len(modes)==1,'unknown context');mode=modes[0]
        need(all(type(p[z]) is int and 0<=p[z]<len(mode['words']) for z in ('left','right')) and p['left']<p['right'],'word references')
        x,y=mode['words'][p['left']],mode['words'][p['right']]
        coarser=[r for r in cuts if r!=p['cut']]
        need(signature(c,mode,x,coarser)==signature(c,mode,y,coarser),'not a private pair')
        need(replay(x,mode['service'])!=replay(y,mode['service']),'no query disagreement')
    return {'word_checks':word_checks,'replay_ticks':(word_checks+2*len(pairs))*c['horizon']}
