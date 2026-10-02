#!/usr/bin/env python3
"""Exercise valid and tampered restricted-support negative certificates."""
from copy import deepcopy
from countcuts import restricted, restricted_check

case=restricted.make_case(2,[[2]],'restricted-library-gap')
case['library']=[1]
certificate,stats=restricted.synthesize(case)
assert certificate['status']=='insufficient_library'
checked=restricted_check.check(case,certificate)
assert checked=={'word_checks':2,'replay_ticks':4}

false_model=deepcopy(case);false_model['library']=[1,2]
try:
    restricted_check.check(false_model,certificate)
except restricted_check.Rejected:
    pass
else:
    raise AssertionError('false insufficiency was accepted')

bad=deepcopy(certificate);bad['pair']['right']=bad['pair']['left']
try:
    restricted_check.check(case,bad)
except restricted_check.Rejected:
    pass
else:
    raise AssertionError('nonseparating negative pair was accepted')

print({'status':'passed','producer':stats,'checker':checked})
