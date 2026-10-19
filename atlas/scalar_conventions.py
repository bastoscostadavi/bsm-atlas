"""Exact irreducible-real-module counting from Bourbaki highest weights.

For a self-dual complex irrep use Tits' indicator (-1)^<lambda,2rho^vee>.
No dimensions, source names or self-duality alone determine real vs quaternionic.
"""
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache

CONVENTION = {
    'id': 'scalar-real-modules-1',
    'unit': 'One irreducible real gauge module per scalar copy',
    'realType': 'Real form of the displayed complex highest-weight irrep; an unconstrained complex field contributes two copies',
    'complexType': 'Underlying real module of R; R and its full conjugate specify the same real module',
    'pseudorealType': 'Underlying real module; no half-dimensional ordinary real form is imposed',
    'orientation': 'First nonzero Abelian charge positive; otherwise lexicographically larger weight tuple, in factor order',
    'reference': 'https://arxiv.org/html/0704.0165v1',
    'method': 'Tits theorem 3.6; exact finite Cartan matrices and dominant dual weights',
}


@lru_cache(maxsize=None)
def cartan(family, rank):
    """A_ij=<alpha_i,alpha_j^vee>, Bourbaki numbering (root rows)."""
    valid = (family == 'A' and rank >= 1 or family in {'B','C'} and rank >= 2
             or family == 'D' and rank >= 4 or family == 'E' and rank in {6,7,8}
             or family == 'F' and rank == 4 or family == 'G' and rank == 2)
    if not valid or rank > 64:
        raise ValueError('Unsupported fixed Cartan type/rank for scalar counting')
    a = [[2 if i == j else 0 for j in range(rank)] for i in range(rank)]
    if family == 'E':
        edges = [(0,2),(2,3),(1,3)] + [(i,i+1) for i in range(3,rank-1)]
    elif family == 'D':
        edges = [(i,i+1) for i in range(rank-3)] + [(rank-3,rank-2),(rank-3,rank-1)]
    else:
        edges = [(i,i+1) for i in range(rank-1)]
    for i,j in edges:
        a[i][j] = a[j][i] = -1
    if family == 'B': a[-2][-1] = -2
    if family == 'C': a[-1][-2] = -2
    if family == 'F': a[1][2] = -2
    if family == 'G': a[1][0] = -3
    return tuple(tuple(row) for row in a)


@lru_cache(maxsize=None)
def dual_weight(family, weight):
    a = cartan(family, len(weight))
    w = [-x for x in weight]
    # Simple reflections carry -lambda to its unique dominant Weyl conjugate.
    for _ in range(20000):
        i = next((i for i,n in enumerate(w) if n < 0), None)
        if i is None: return tuple(w)
        k = w[i]
        w = [n-k*a[i][j] for j,n in enumerate(w)]
    raise ValueError('Dual-weight reflection safety limit exceeded')


@lru_cache(maxsize=None)
def twice_rho_coroot(family, rank):
    a = [list(map(Fraction,row)) + [Fraction(2)] for row in cartan(family,rank)]
    for i in range(rank):
        pivot = next(j for j in range(i,rank) if a[j][i])
        a[i],a[pivot] = a[pivot],a[i]
        divisor = a[i][i]
        a[i] = [x/divisor for x in a[i]]
        for j in range(rank):
            if j != i:
                multiple = a[j][i]
                a[j] = [x-multiple*y for x,y in zip(a[j],a[i])]
    result = tuple(row[-1] for row in a)
    if any(n.denominator != 1 for n in result):
        raise ValueError('Invalid 2rho-coroot coordinates')
    return tuple(map(int,result))


def conjugate_reps(reps, factors):
    return {a['id']: ({'charge': str(-Fraction(reps[a['id']]['charge']))}
            if a['family'] == 'U1' else
            {'dynkin': list(dual_weight(a['family'],tuple(reps[a['id']]['dynkin'])))})
            for a in factors}


def representation_type(factors, reps):
    sign = 1
    for a in factors:
        r = reps[a['id']]
        if a['family'] == 'U1':
            if Fraction(r['charge']): return 'complex'
            continue
        w = tuple(r['dynkin'])
        if w != dual_weight(a['family'],w): return 'complex'
        exponent = sum(x*y for x,y in zip(w,twice_rho_coroot(a['family'],a['rank'])))
        sign *= -1 if exponent % 2 else 1
    return 'real' if sign == 1 else 'pseudoreal'


def orient_reps(reps, factors):
    conjugate = False
    for a in factors:
        if a['family'] == 'U1' and Fraction(reps[a['id']]['charge']):
            conjugate = Fraction(reps[a['id']]['charge']) < 0
            break
    else:
        original = tuple(tuple(reps[a['id']]['dynkin']) for a in factors if a['family'] != 'U1')
        dual = tuple(dual_weight(a['family'],tuple(reps[a['id']]['dynkin'])) for a in factors if a['family'] != 'U1')
        conjugate = dual > original
    return conjugate_reps(reps,factors) if conjugate else deepcopy(reps)


def real_scalar(field, factors, source_reality=None):
    result = deepcopy(field)
    reality = source_reality or field['reality']
    kind = representation_type(factors,field['gauge_representations'])
    if reality == 'real' and kind != 'real':
        raise ValueError('An ordinary real scalar condition requires a real-type full gauge irrep')
    if reality not in {'real','complex','real_module'}:
        raise ValueError('Scalar source counting has not been established')
    if reality == 'complex' and kind == 'real': result['copies'] *= 2
    result['reality'] = 'real_module'
    result['gauge_representations'] = orient_reps(field['gauge_representations'],factors)
    return result,kind


def is_scalar(lorentz):
    d = lorentz['dimension']
    irreps = lorentz['irreps']
    return irreps == [['0','0']] if d == 4 else len(irreps) == 1 and not any(irreps[0])


def uniform_scalar(row, factors, parameters):
    """Require a uniform real-module count, without inventing a family member."""
    from charge_expressions import parse_charge
    probe=deepcopy(row); polynomials={}
    for a in factors:
        if a['family']=='U1':
            p=parse_charge(row['gauge_representations'][a['id']]['charge'],tuple(parameters))
            polynomials[a['id']]=p
            probe['gauge_representations'][a['id']]['charge']='0' if p.symbols else p.render()
    projected,kind=real_scalar(probe,factors,row['reality'])
    if any(p.symbols for p in polynomials.values()) and kind=='real':
        raise ValueError('Scalar real-module count changes on charge loci; split into uniform families')
    flip=any(not p.symbols and int(p.render())!=0 and int(projected['gauge_representations'][key]['charge'])==-int(p.render()) for key,p in polynomials.items())
    for key,p in polynomials.items():
        projected['gauge_representations'][key]['charge']=parse_charge('-('+p.render()+')' if flip else p.render(),tuple(parameters)).render()
    return projected
