"""Generic coupling-space quotients from a gauge/matter specification.

No model names or source-paper symmetries enter this calculation. Schur-Weyl
duality constructs the flavor representations of gauge-invariant interactions.
An exact generic mass slice removes basis transformations already fixed by
masses. The remaining orbit rank is certified by a nonzero finite-field minor
and a rational upper bound, or by fraction-free symbolic elimination.
"""
from collections import Counter
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
from itertools import combinations_with_replacement, permutations, product
from math import prod

from .characters import Algebra, CountingLimit
from .field_conventions import weyl_dimension
from .lie_indices import twice_index
from .scalar_conventions import conjugate_reps, orient_reps, representation_type

METHOD = 'schur-mass-slice-orbit-2'
MAX_GROUP = 100
MAX_BLOCKS = 40
MAX_TERMS = 12000
MAX_AMBIENT = 4096
MAX_ROWS = 12000
PRIME = 1000000007


def signature(reps, factors):
    return tuple((int(reps[a['id']]['charge']),) if a['family'] == 'U1'
                 else tuple(reps[a['id']]['dynkin']) for a in factors)


def sparse_rank(rows, modulus=None):
    """Exact sparse row elimination over Q or a prime field."""
    basis = {}
    for source in rows:
        row = {i: (int(v) % modulus if modulus else Fraction(v))
               for i, v in source.items() if v}
        while row:
            pivot = min(row)
            if pivot not in basis:
                scale = pow(row[pivot], -1, modulus) if modulus else 1 / row[pivot]
                basis[pivot] = {i: (v * scale) % modulus if modulus else v * scale
                                for i, v in row.items()}
                break
            scale = row[pivot]
            for i, v in basis[pivot].items():
                value = row.get(i, 0) - scale * v
                if modulus:
                    value %= modulus
                if value:
                    row[i] = value
                else:
                    row.pop(i, None)
    return len(basis)


class MassSlice:
    def __init__(self, spec):
        self.factors = spec['gauge_factors']
        self.groups, self.generators = [], []
        self.scalars, self.fermions = [], []
        self.fixed_rank = 0
        self.full_dimension = 0
        scalars, fermions = {}, {}
        for row in spec['matter']:
            target = scalars if row['lorentz']['irreps'] == [['0', '0']] else fermions
            reps = row['gauge_representations']
            if target is scalars:
                reps = orient_reps(reps, self.factors)
            key = signature(reps, self.factors)
            if key not in target:
                target[key] = [reps, 0]
            target[key][1] += row['copies']
        neutral_scalar = any(all(not x for block in signature(reps, self.factors) for x in block)
                             for reps, _ in scalars.values())
        for reps, n in scalars.values():
            kind = representation_type(self.factors, reps)
            neutral = all(not x for block in signature(reps, self.factors) for x in block)
            if kind == 'real':
                self.fixed_rank += n * (n - 1) // 2 + (n if neutral else 0)
                self.block(self.scalars, reps, dimension=n)
            elif kind == 'complex':
                # Distinct masses fix mixing. Generic (phi_1^dagger phi_j)^2
                # fix relative phases, leaving only the common U(1). These
                # chosen quartics are invariant under the remaining group.
                self.fixed_rank += n * n - 1
                group = self.group('GL', 1)
                self.block(self.scalars, reps, group, dimension=n, phase=True)
                self.block(self.scalars, conjugate_reps(reps, self.factors), group,
                           dual=True, dimension=n, phase=True)
            elif n > 1:
                # After mass diagonalization each pair of quaternionic fields
                # has four real invariant cross-bilinears. A generic quadratic
                # form in these bilinears breaks Sp(1)xSp(1) to a finite group.
                # Pairs (1,j) therefore fix all of Sp(n) for n >= 2.
                self.fixed_rank += n * (2 * n + 1)
                self.block(self.scalars, reps, dimension=2 * n)
            else:
                self.block(self.scalars, reps, self.group('SL2', 2))
        done = set()
        for key, (reps, n) in fermions.items():
            if key in done:
                continue
            done.add(key)
            kind = representation_type(self.factors, reps)
            if kind == 'real':
                self.fixed_rank += n * n  # Takagi masses, distinct and nonzero
                self.block(self.fermions, reps, dimension=n)
            elif kind == 'pseudoreal':
                pairs, odd = divmod(n, 2)
                self.fixed_rank += n * n - 3 * pairs - odd
                for _ in range(pairs):
                    self.block(self.fermions, reps, self.group('SL2', 2))
                if odd:
                    self.block(self.fermions, reps, self.group('GL', 1))
            else:
                dual = conjugate_reps(reps, self.factors)
                other_key = signature(dual, self.factors)
                done.add(other_key)
                m = fermions.get(other_key, (None, 0))[1]
                pairs, rest = min(n, m), abs(n - m)
                if pairs and neutral_scalar:
                    # A generic singlet Yukawa on the massive square subblock
                    # fixes relative Dirac-pair phases. It is invariant under
                    # the common phase and under the remaining massless group.
                    self.fixed_rank += n * n + m * m - 1 - rest * rest
                    group = self.group('GL', 1)
                    self.block(self.fermions, reps, group, dimension=pairs, phase=True)
                    self.block(self.fermions, dual, group, dual=True, dimension=pairs, phase=True)
                else:
                    self.fixed_rank += n * n + m * m - pairs - rest * rest
                    for _ in range(pairs):
                        group = self.group('GL', 1)
                        self.block(self.fermions, reps, group)
                        self.block(self.fermions, dual, group, dual=True)
                if rest:
                    self.block(self.fermions, reps if n > m else dual, self.group('GL', rest))
        self.full_dimension = self.fixed_rank + len(self.generators)
        if len(self.generators) > MAX_GROUP:
            raise CountingLimit('Residual field-redefinition group exceeds the orbit budget.')

    def group(self, kind, n):
        group = len(self.groups)
        matrices = ([{(0, 0): 1, (1, 1): -1}, {(0, 1): 1}, {(1, 0): 1}]
                    if kind == 'SL2' else [{(i, j): 1} for i in range(n) for j in range(n)])
        self.groups.append((kind, n))
        for matrix in matrices:
            self.generators.append((group, matrix))
        return group

    def block(self, target, reps, group=None, dual=False, dimension=None, phase=False):
        n = dimension if dimension is not None else self.groups[group][1] if group is not None else 1
        target.append({'reps': reps, 'n': n, 'group': group, 'dual': dual, 'phase': phase})
        if len(self.scalars) + len(self.fermions) > MAX_BLOCKS:
            raise CountingLimit('Mass-slice field inventory exceeds the orbit budget.')

    def theta_rows(self):
        simple = [a for a in self.factors if a['family'] != 'U1']
        result = []
        for a in simple:
            row = {}
            for block in self.fermions:
                reps = block['reps']
                spectator = prod(weyl_dimension(b['family'], reps[b['id']]['dynkin'])
                                 for b in simple if b['id'] != a['id'])
                index = twice_index(a['family'], tuple(reps[a['id']]['dynkin'])) * spectator
                for j, (group, matrix) in enumerate(self.generators):
                    if block['group'] == group:
                        trace = sum(v for (x, y), v in matrix.items() if x == y)
                        if block['phase']:
                            trace *= block['n']
                        row[j] = row.get(j, 0) + index * trace * (-1 if block['dual'] else 1)
            result.append({j: int(v) for j, v in row.items() if v})
        return result


@lru_cache(maxsize=64)
def partitions(n, maximum=None):
    if not n:
        return ((),)
    return tuple((k,) + tail for k in range(min(n, maximum or n), 0, -1)
                 for tail in partitions(n - k, k))


def parity(perm):
    return (-1) ** sum(perm[i] > perm[j] for i in range(len(perm)) for j in range(i + 1, len(perm)))


def schur_dimension(n, shape):
    """Hook-content formula; never expand a trivial flavor multiplicity."""
    numerator = denominator = 1
    for i, length in enumerate(shape):
        for j in range(length):
            numerator *= n + j - i
            denominator *= length - j + sum(k > j for k in shape[i + 1:])
    return numerator // denominator


@lru_cache(maxsize=128)
def young_basis(n, shape):
    """An integer basis of the image of one Young symmetrizer in V^tensor k."""
    k = sum(shape)
    if n ** k > MAX_AMBIENT:
        raise CountingLimit('Schur tensor exceeds the orbit storage budget.')
    rows, position = [], 0
    for length in shape:
        rows.append(tuple(range(position, position + length)))
        position += length
    cols = [tuple(row[j] for row in rows if len(row) > j) for j in range(shape[0])]

    def perm_group(parts, signed):
        result = []
        for choices in product(*(tuple(permutations(part)) for part in parts)):
            p = list(range(k))
            for part, choice in zip(parts, choices):
                for i, j in zip(part, choice):
                    p[i] = j
            result.append((tuple(p), parity(p) if signed else 1))
        return result

    row_group, col_group = perm_group(rows, False), perm_group(cols, True)
    basis, echelon = [], {}
    for indices in product(range(n), repeat=k):
        vector = Counter()
        for cp, sign in col_group:
            col = tuple(indices[j] for j in cp)
            for rp, _ in row_group:
                vector[tuple(col[j] for j in rp)] += sign
        vector = {i: v for i, v in vector.items() if v}
        residual = {i: Fraction(v) for i, v in vector.items()}
        while residual:
            pivot = min(residual)
            if pivot not in echelon:
                scale = residual[pivot]
                echelon[pivot] = {i: v / scale for i, v in residual.items()}
                basis.append(vector)
                break
            scale = residual[pivot]
            for i, v in echelon[pivot].items():
                value = residual.get(i, 0) - scale * v
                if value:
                    residual[i] = value
                else:
                    residual.pop(i, None)
    return tuple(basis)


class Couplings:
    def __init__(self, mass_slice):
        self.slice = mass_slice
        self.algebra = Algebra(mass_slice.factors)
        self.characters, self.schurs, self.multiplicities = {}, {}, {}
        self.terms = 0

    def schur(self, block, shape):
        key = signature(block['reps'], self.slice.factors), shape
        if key in self.schurs:
            return self.schurs[key]
        rep = key[0]
        if rep not in self.characters:
            char = self.algebra.representation(block['reps'])
            self.characters[rep] = self.algebra.symmetric(char, 4)
        h = self.characters[rep]
        result = {}
        # Jacobi-Trudi; Schur-Weyl also handles antisymmetric gauge contractions.
        for p in permutations(range(len(shape))):
            degrees = [shape[i] - i + p[i] for i in range(len(shape))]
            if any(n < 0 for n in degrees):
                continue
            char = {self.algebra.zero: parity(p)}
            for n in degrees:
                char = self.algebra.multiply(char, h[n])
            for weight, value in char.items():
                result[weight] = result.get(weight, 0) + value
        result = {w: v for w, v in result.items() if v}
        self.schurs[key] = result
        return result

    def modules(self, blocks, counts):
        self.terms += 1
        if self.terms > MAX_TERMS:
            raise CountingLimit('Interaction enumeration exceeds the orbit budget.')
        for shapes in product(*(tuple(p for p in partitions(k) if len(p) <= b['n'])
                                for b, k in zip(blocks, counts))):
            key = tuple((signature(b['reps'], self.slice.factors), p) for b, p in zip(blocks, shapes))
            if key not in self.multiplicities:
                char = {self.algebra.zero: 1}
                for b, p in zip(blocks, shapes):
                    char = self.algebra.multiply(char, self.schur(b, p))
                self.multiplicities[key] = self.algebra.singlets(char)
            multiplicity = self.multiplicities[key]
            if multiplicity:
                yield blocks, shapes, multiplicity

    def interactions(self):
        scalars, fermions = self.slice.scalars, self.slice.fermions
        for degree in (3, 4):
            for indices in combinations_with_replacement(range(len(scalars)), degree):
                counts = Counter(indices)
                yield from self.modules([scalars[i] for i in counts], list(counts.values()))
        for scalar in scalars:
            for i, j in combinations_with_replacement(range(len(fermions)), 2):
                blocks = [scalar, fermions[i]] + ([] if i == j else [fermions[j]])
                counts = [1, 2] if i == j else [1, 1, 1]
                for module in self.modules(blocks, counts):
                    yield module
                    # Complex Yukawas plus their conjugates form a real coupling space.
                    yield [dict(b, dual=not b['dual']) for b in module[0]], module[1], module[2]


def tensor_action(blocks, shapes, basis, group, matrix):
    """Infinitesimal action in the ambient tensor basis; image stays in Schur space."""
    result = Counter()
    offset = 0
    for block, shape in zip(blocks, shapes):
        degree = sum(shape)
        if block['group'] == group:
            entries = {(y, x): -v for (x, y), v in matrix.items()} if block['dual'] else matrix
            for indices, value in basis.items():
                for slot in range(offset, offset + degree):
                    for (target, source), coefficient in entries.items():
                        if indices[slot] == source:
                            output = indices[:slot] + (target,) + indices[slot + 1:]
                            result[output] += coefficient * value
        offset += degree
    return {i: v for i, v in result.items() if v}


def module_rows(blocks, shapes, generators):
    bases = [young_basis(b['n'], p) for b, p in zip(blocks, shapes)]
    if prod(b['n'] ** sum(p) for b, p in zip(blocks, shapes)) > MAX_AMBIENT:
        raise CountingLimit('Coupling tensor exceeds the orbit storage budget.')
    rows = {}
    dimension = prod(map(len, bases))
    for coordinate, parts in enumerate(product(*bases)):
        basis = {}
        for factors in product(*(tuple(v.items()) for v in parts)):
            index = sum((item[0] for item in factors), ())
            basis[index] = prod(item[1] for item in factors)
        for column, (group, matrix) in enumerate(generators):
            for index, value in tensor_action(blocks, shapes, basis, group, matrix).items():
                rows.setdefault(index, {}).setdefault(column, {})[coordinate] = value
    return list(rows.values()), dimension


def _symbolic_rank_exact(rows, columns, variables):
    """Optional exact polynomial elimination, never numerical extrapolation."""
    if len(rows) > 200 or columns > 60 or variables > 150:
        raise CountingLimit('Symbolic orbit matrix exceeds the exact elimination budget.')
    try:
        from sympy import ZZ
        from sympy.polys.matrices import DomainMatrix
    except ImportError:
        raise CountingLimit('Install requirements-properties.txt for symbolic orbit elimination.') from None
    domain = ZZ.poly_ring(*(f'c{i}' for i in range(variables))) if variables else ZZ
    symbols = domain.gens if variables else ()
    matrix = {i: {j: sum((v * symbols[k] if k >= 0 else domain(v)
                         for k, v in value.items()), domain.zero)
                  for j, value in row.items()} for i, row in enumerate(rows)}
    _, _, pivots = DomainMatrix(matrix, (len(rows), columns), domain).rref_den(method='FF')
    return len(pivots)


def symbolic_rank(rows, columns, variables):
    # Bound the optional CAS separately, so a difficult model cannot stall an
    # atlas build or leave a partial rank masquerading as a count.
    import json
    import subprocess
    import sys
    try:
        import sympy  # noqa: F401 -- check before launching the isolated worker
    except ImportError:
        raise CountingLimit('Install requirements-properties.txt for symbolic orbit elimination.') from None
    if len(rows) > 200 or columns > 60 or variables > 150:
        raise CountingLimit('Symbolic orbit matrix exceeds the exact elimination budget.')
    payload = json.dumps({'rows': rows, 'columns': columns, 'variables': variables})
    try:
        result = subprocess.run([sys.executable, '-B', '-m', __name__, '--symbolic-rank'],
                                input=payload, text=True, capture_output=True, timeout=12)
    except subprocess.TimeoutExpired:
        raise CountingLimit('Exact symbolic orbit elimination exceeded its time budget.') from None
    if result.returncode:
        raise ArithmeticError('Exact symbolic orbit worker failed: ' + result.stderr[-1000:])
    return int(result.stdout)


def isolated_matrix_stabilizers(modules, mass_slice):
    """Guaranteed traceless stabilizers of isolated generic Yukawa matrices.

    A sole n-by-m bifundamental and its conjugate have singular-value
    stabilizer U(min(n,m)) x U(abs(n-m)). Its traceless subgroup survives all
    theta rows. This handles arbitrary such sectors, not named models.
    """
    appearances = {}
    for number, (blocks, shapes, multiplicity) in enumerate(modules):
        for group in {b['group'] for b in blocks if b['group'] is not None}:
            appearances.setdefault(group, set()).add(number)
    correction, used = 0, set()
    for a, (kind, n) in enumerate(mass_slice.groups):
        if kind != 'GL' or n < 2 or a in used:
            continue
        occurs = appearances.get(a, set())
        if len(occurs) != 2:
            continue
        first = modules[min(occurs)]
        blocks, shapes, multiplicity = first
        large = [b for b in blocks if b['n'] > 1]
        if (multiplicity != 1 or len(large) != 2
                or any(p != (1,) for p in shapes)
                or any(b['group'] is None for b in large)):
            continue
        b = next((v['group'] for v in large if v['group'] != a), None)
        if b is None or b in used or appearances.get(b) != occurs:
            continue
        other_kind, m = mass_slice.groups[b]
        if other_kind != 'GL':
            continue
        # The other occurrence must be precisely the dual module, not a
        # second independent matrix (which generically breaks family phases).
        second = modules[max(occurs)]
        if (second[1:] != first[1:] or len(second[0]) != len(blocks)
                or any(x['group'] != y['group'] or x['n'] != y['n']
                       or x['dual'] == y['dual'] for x, y in zip(blocks, second[0]))):
            continue
        d = abs(n - m)
        correction += min(n, m) - 1 + max(0, d * d - 1)
        used.update((a, b))
    return correction


def assess(spec, total):
    """Return a certified generic quotient, or raise CountingLimit with no number."""
    mass_slice = MassSlice(spec)
    generators = mass_slice.generators
    rows, variables, represented, truncated = [], 0, 0, False
    couplings = Couplings(mass_slice)
    modules = []
    for original_blocks, original_shapes, original_multiplicity in couplings.interactions():
        dimension = prod(schur_dimension(b['n'], p) for b, p in zip(original_blocks, original_shapes))
        represented += original_multiplicity * dimension
        blocks, shapes, multiplicity = [], [], original_multiplicity
        for b, p in zip(original_blocks, original_shapes):
            if b['group'] is None:
                multiplicity *= schur_dimension(b['n'], p)
            elif b['phase']:
                multiplicity *= schur_dimension(b['n'], p)
                blocks.append(dict(b, n=1))
                shapes.append((sum(p),))
            else:
                blocks.append(b)
                shapes.append(p)
        if not blocks:
            continue
        modules.append((blocks, shapes, multiplicity))
        module, dimension = module_rows(blocks, shapes, generators)
        # A trivial representation has no orbit coordinates and needs no symbols.
        if not module:
            continue
        copies = min(multiplicity, len(generators) + 1)
        truncated |= copies != multiplicity
        for _ in range(copies):
            rows.extend({j: {k + variables: v for k, v in coefficients.items()}
                         for j, coefficients in row.items()} for row in module)
            variables += dimension
        if len(rows) > MAX_ROWS or variables > MAX_ROWS:
            raise CountingLimit('Coupling action exceeds the orbit matrix budget.')
    expected = sum(total['scalar_potential_by_degree'][2:]) + 2 * total['yukawa_complex_coefficients']
    if represented != expected:
        raise ArithmeticError(f'Coupling representation dimension mismatch: {represented} != {expected}')
    for row in mass_slice.theta_rows():
        if row:
            rows.append({j: {-1: v} for j, v in row.items()})
    universal = []
    for row in rows:
        for k in sorted({k for entries in row.values() for k in entries}):
            universal.append({j: entries[k] for j, entries in row.items() if k in entries})
    accidental = isolated_matrix_stabilizers(modules, mass_slice)
    upper = sparse_rank(universal) - accidental
    rank, proof = 0, 'exact universal-kernel bound saturated by a finite-field minor'
    point_hash = None
    for attempt in range(3):
        values = [int.from_bytes(sha256(f'{METHOD}:{attempt}:{i}'.encode()).digest()[:8], 'big') % PRIME
                  for i in range(variables)]
        evaluated = [{j: sum(v * (values[k] if k >= 0 else 1) for k, v in entries.items()) % PRIME
                      for j, entries in row.items()} for row in rows]
        candidate = sparse_rank(evaluated, PRIME)
        if candidate > rank or point_hash is None:
            rank = candidate
            point_hash = sha256(','.join(map(str, values)).encode()).hexdigest()
        if rank == upper:
            break
    if rank < upper:
        if truncated:
            raise CountingLimit('Selected coupling subspace did not saturate the full orbit bound.')
        rank = symbolic_rank(rows, len(generators), variables)
        proof = 'exact fraction-free polynomial orbit rank'
    if rank > upper:
        raise ArithmeticError('Orbit rank exceeds the universal-kernel bound')
    abelian = [a['id'] for a in spec['gauge_factors'] if a['family'] == 'U1']
    charge_rows = [{i: int(row['gauge_representations'][key]['charge'])
                    for i, key in enumerate(abelian)} for row in spec['matter']]
    active = sparse_rank(charge_rows)
    # Flat-space free Maxwell fields have removable kinetic normalizations and
    # mixing. Keep the charge basis fixed on the charged span; no monopoles.
    free_gauge_rank = (len(abelian) * (len(abelian) + 1) - active * (active + 1)) // 2
    orbit = mass_slice.fixed_rank + rank + free_gauge_rank
    if orbit > total['value']:
        raise ArithmeticError('Orbit dimension exceeds coupling-space dimension')
    return {'status': 'certified', 'value': total['value'] - orbit, 'method': METHOD,
            'orbit_rank': orbit, 'mass_slice_rank': mass_slice.fixed_rank,
            'residual_group_dimension': len(generators), 'residual_orbit_rank': rank,
            'generic_stabilizer_dimension': len(generators) - rank,
            'isolated_matrix_stabilizer_bound': accidental,
            'free_abelian_normalizations': free_gauge_rank,
            'coupling_representation_dimension': represented, 'proof': proof,
            'selected_subspace': truncated,
            'minor_prime': PRIME, 'point_sha256': point_hash,
            'source': 'atlas/DERIVED_PROPERTIES.md#generic-coupling-space-solver'}


if __name__ == '__main__':
    import json
    import sys
    if sys.argv[1:] != ['--symbolic-rank']:
        raise SystemExit('Use python -m bsm_atlas.properties to assess an entry or catalogue.')
    payload = json.load(sys.stdin)
    rows = [{int(j): {int(k): v for k, v in entries.items()}
             for j, entries in row.items()} for row in payload['rows']]
    print(_symbolic_rank_exact(rows, payload['columns'], payload['variables']))
