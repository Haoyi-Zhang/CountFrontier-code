"""Exact tiny-coloring oracle and elementary cut-lattice baselines."""
from itertools import combinations, product
from .checker import abstract, answers, permitted, replay


def subsets(items):
    return [list(combo) for r in range(len(items)+1) for combo in combinations(items, r)]


def oracle(case):
    n, k = sum(map(len, case['groups'])), case['classes']
    if k**n > 4096:
        raise ValueError('exact oracle limited to 4096 colorings')
    trace, ticks = replay(case)
    words = [list(w) for w in product(range(k), repeat=n) if permitted(case, list(w))]
    values = {tuple(w): answers(case, w, trace) for w in words}
    results, obligations = [], 0
    for cuts in subsets(case['library']):
        seen = {}
        adequate, witness = True, None
        # Visit the complete table even after finding a collision, for exact accounting.
        for word in words:
            obligations += 1
            key, value = abstract(case, word, cuts), values[tuple(word)]
            if key in seen and seen[key][0] != value:
                adequate = False
                if witness is None: witness = [seen[key][1], word]
            else:
                seen.setdefault(key, (value, word))
        results.append({'cuts': cuts, 'adequate': adequate, 'witness': witness})
    return {'candidates': results, 'colorings': len(words), 'word_candidate_obligations': obligations,
            'simulation_ticks': ticks}
