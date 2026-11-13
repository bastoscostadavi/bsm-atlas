"""Exact quadratic and cubic indices in the atlas's Bourbaki convention."""
from fractions import Fraction
from functools import lru_cache

from .field_conventions import weyl_dimension
from .scalar_conventions import cartan


def inverse(matrix):
    n = len(matrix)
    rows = [[Fraction(x) for x in row] + [Fraction(i == j) for j in range(n)]
            for i, row in enumerate(matrix)]
    for i in range(n):
        pivot = next(j for j in range(i, n) if rows[j][i])
        rows[i], rows[pivot] = rows[pivot], rows[i]
        scale = rows[i][i]
        rows[i] = [x / scale for x in rows[i]]
        for j in range(n):
            if j != i:
                scale = rows[j][i]
                rows[j] = [x - scale * y for x, y in zip(rows[j], rows[i])]
    return tuple(tuple(row[n:]) for row in rows)


@lru_cache(maxsize=128)
def weight_metric(family, rank):
    """Fundamental-weight Gram matrix, with long roots of squared length 2."""
    a = cartan(family, rank)
    lengths = {0: Fraction(1)}
    while len(lengths) < rank:
        for i in tuple(lengths):
            for j in range(rank):
                if i != j and a[i][j] and j not in lengths:
                    lengths[j] = lengths[i] * Fraction(a[j][i], a[i][j])
    largest = max(lengths.values())
    inv = inverse(a)
    return tuple(tuple(inv[i][j] * lengths[j] / largest for j in range(rank))
                 for i in range(rank))


def inner(left, right, metric):
    return sum((x * y * metric[i][j] for i, x in enumerate(left)
                for j, y in enumerate(right) if x and y), Fraction(0))


def algebra_dimension(family, rank):
    return {'A': rank * (rank + 2), 'B': rank * (2 * rank + 1),
            'C': rank * (2 * rank + 1), 'D': rank * (2 * rank - 1),
            'E': {6: 78, 7: 133, 8: 248}.get(rank), 'F': 52, 'G': 14}[family]


@lru_cache(maxsize=8192)
def twice_index(family, labels):
    """2 T(R), with T(SU(N) or Sp fundamental)=1/2 and T(SO vector)=1."""
    metric = weight_metric(family, len(labels))
    value = (weyl_dimension(family, labels)
             * inner(labels, tuple(x + 2 for x in labels), metric)
             / algebra_dimension(family, len(labels)))
    if value.denominator != 1:
        raise ArithmeticError('Nonintegral quadratic index')
    return int(value)


@lru_cache(maxsize=8192)
def cubic_index(family, labels):
    """A(R), normalized to +1 on SU(N)'s first fundamental, N >= 3.

    The shifted-weight cubic Casimir is proportional to sum_i (lambda+rho)_i^3.
    Only A_r (r >= 2) admits a cubic invariant. This is a Lie-algebra test;
    E6's cubic *representation* invariant is not an adjoint cubic invariant.
    """
    if family != 'A' or len(labels) == 1:
        return Fraction(0)
    n = len(labels) + 1

    def moment(weight):
        rows = [sum(weight[i:]) for i in range(n)]
        mean = Fraction(sum(rows), n)
        return sum((row - mean + Fraction(n - 1 - 2 * i, 2)) ** 3
                   for i, row in enumerate(rows))

    fundamental = (1,) + (0,) * (n - 2)
    return Fraction(weyl_dimension(family, labels), n) * moment(labels) / moment(fundamental)
