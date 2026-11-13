"""Bounded exact characters and singlet multiplicities for parameter counting.

Weights use Dynkin coordinates. Freudenthal recursion reconstructs irrep
multiplicities; the Weyl denominator projects a character onto its singlets.
Limits are operation counts, so incomplete results are reproducible.
"""
from collections import deque
from functools import lru_cache
from itertools import product

from .field_conventions import weyl_dimension
from .lie_indices import inner, weight_metric
from .scalar_conventions import cartan

MAX_WEIGHTS = 2048
MAX_CHARACTER = 20000
MAX_OPERATIONS = 300000
MAX_WEYL = 4096


class CountingLimit(ValueError):
    pass


@lru_cache(maxsize=128)
def positive_roots(family, rank):
    a = cartan(family, rank)
    pending = [tuple(int(i == j) for j in range(rank)) for i in range(rank)]
    roots = set(pending)
    while pending:
        root = pending.pop()
        for i in range(rank):
            pairing = sum(root[j] * a[j][i] for j in range(rank))
            reflected = root[:i] + (root[i] - pairing,) + root[i + 1:]
            if reflected not in roots:
                roots.add(reflected)
                pending.append(reflected)
    return tuple(tuple(sum(root[j] * a[j][i] for j in range(rank)) for i in range(rank))
                 for root in roots if all(x >= 0 for x in root))


@lru_cache(maxsize=8192)
def irrep_character(family, labels):
    rank = len(labels)
    if weyl_dimension(family, labels) > 4096:
        raise CountingLimit('Irrep dimension exceeds the exact character budget.')
    a = cartan(family, rank)
    # Saturate downward simple-root strings. Depth orders Freudenthal's
    # recursion; duplicate routes must give the same depth.
    depths = {labels: 0}
    pending = deque([labels])
    while pending:
        weight = pending.popleft()
        for i in range(rank):
            for k in range(1, max(0, weight[i]) + 1):
                lower = tuple(x - k * y for x, y in zip(weight, a[i]))
                if lower not in depths:
                    depths[lower] = depths[weight] + k
                    pending.append(lower)
                    if len(depths) > MAX_WEIGHTS:
                        raise CountingLimit('Irrep weight count exceeds the exact character budget.')
    metric = weight_metric(family, rank)
    shifted = tuple(x + 1 for x in labels)
    top_norm = inner(shifted, shifted, metric)
    roots = positive_roots(family, rank)
    multiplicities = {labels: 1}
    for weight in sorted(depths, key=depths.get)[1:]:
        numerator = 0
        for root in roots:
            upper = tuple(x + y for x, y in zip(weight, root))
            while upper in depths:
                numerator += inner(upper, root, metric) * multiplicities.get(upper, 0)
                upper = tuple(x + y for x, y in zip(upper, root))
        shifted = tuple(x + 1 for x in weight)
        value = 2 * numerator / (top_norm - inner(shifted, shifted, metric))
        if value.denominator != 1 or value <= 0:
            raise ArithmeticError('Invalid Freudenthal multiplicity')
        multiplicities[weight] = int(value)
    if sum(multiplicities.values()) != weyl_dimension(family, labels):
        raise ArithmeticError('Character dimension mismatch')
    return tuple(multiplicities.items())


@lru_cache(maxsize=128)
def denominator(family, rank):
    a = cartan(family, rank)
    rho = (1,) * rank
    signs = {rho: 1}
    pending = [rho]
    while pending:
        weight = pending.pop()
        for i in range(rank):
            reflected = tuple(x - weight[i] * y for x, y in zip(weight, a[i]))
            if reflected not in signs:
                signs[reflected] = -signs[weight]
                pending.append(reflected)
                if len(signs) > MAX_WEYL:
                    raise CountingLimit('Weyl group exceeds the exact singlet-projection budget.')
    return tuple((tuple(x - y for x, y in zip(rho, weight)), sign)
                 for weight, sign in signs.items())


class Algebra:
    def __init__(self, factors):
        self.factors = factors
        self.zero = (0,) * sum(a['rank'] for a in factors)
        self.operations = 0
        terms = [((), 1)]
        for a in factors:
            block = (((0,), 1),) if a['family'] == 'U1' else denominator(a['family'], a['rank'])
            if len(terms) * len(block) > MAX_WEYL:
                raise CountingLimit('Product Weyl group exceeds the exact singlet-projection budget.')
            terms = [(x + y, s * t) for (x, s), (y, t) in product(terms, block)]
        self.projection = terms

    def representation(self, reps):
        terms = [((), 1)]
        for a in self.factors:
            rep = reps[a['id']]
            block = (((int(rep['charge']),), 1),) if a['family'] == 'U1' else irrep_character(a['family'], tuple(rep['dynkin']))
            if len(terms) * len(block) > MAX_WEIGHTS:
                raise CountingLimit('Product representation exceeds the exact character budget.')
            terms = [(x + y, s * t) for (x, s), (y, t) in product(terms, block)]
        return dict(terms)

    def multiply(self, left, right):
        self.operations += len(left) * len(right)
        if self.operations > MAX_OPERATIONS:
            raise CountingLimit('Character multiplication exceeds the exact operation budget.')
        result = {}
        for p, x in left.items():
            for q, y in right.items():
                key = tuple(a + b for a, b in zip(p, q))
                result[key] = result.get(key, 0) + x * y
        result = {key: value for key, value in result.items() if value}
        if len(result) > MAX_CHARACTER:
            raise CountingLimit('Character exceeds the exact storage budget.')
        return result

    def symmetric(self, character, degree):
        result = [{self.zero: 1}]
        for n in range(1, degree + 1):
            total = {}
            for k in range(1, n + 1):
                adams = {tuple(k * x for x in weight): mult for weight, mult in character.items()}
                for weight, value in self.multiply(adams, result[n - k]).items():
                    total[weight] = total.get(weight, 0) + value
            if any(value % n for value in total.values()):
                raise ArithmeticError('Nonintegral symmetric-power character')
            result.append({w: value // n for w, value in total.items() if value})
        return result

    def singlets(self, character):
        value = sum(sign * character.get(weight, 0) for weight, sign in self.projection)
        if value < 0:
            raise ArithmeticError('Negative singlet multiplicity')
        return value
