"""Restricted exact integer polynomials and comparisons; never Python eval.

This is a charge-expression language, not a general symbolic algebra engine.
Its bounds protect intake from accidentally enormous expansions/evaluations.
"""
import ast
from dataclasses import dataclass
import keyword
import operator
import re

from entry_validation import IncompleteContent, object_keys

MAX_PARAMETERS = 16
MAX_TERMS = 256
MAX_DEGREE = 32
MAX_BITS = 4096
MAX_CONSTRAINTS = 64
COMPARISONS = {
    ast.Eq: ('==', operator.eq), ast.NotEq: ('!=', operator.ne),
    ast.Lt: ('<', operator.lt), ast.LtE: ('<=', operator.le),
    ast.Gt: ('>', operator.gt), ast.GtE: ('>=', operator.ge),
}


def parameter_names(parameters):
    if not isinstance(parameters, dict) or len(parameters) > MAX_PARAMETERS:
        raise IncompleteContent('parameters must be an object with at most 16 integer declarations')
    for name, declaration in parameters.items():
        if (not isinstance(name, str) or
                not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}', name) or keyword.iskeyword(name)):
            raise IncompleteContent('Use named parameters such as z1, z2 or n, not code or reserved words')
        object_keys(declaration, {'domain'})
        if declaration['domain'] != 'integer':
            raise IncompleteContent('The initial charge-expression convention supports integer parameters only')
    return tuple(sorted(parameters))


def _bounded(terms):
    terms = {powers: coefficient for powers, coefficient in terms.items() if coefficient}
    if (len(terms) > MAX_TERMS or any(sum(p) > MAX_DEGREE for p in terms) or
            any(abs(c).bit_length() > MAX_BITS for c in terms.values())):
        raise IncompleteContent('Charge polynomial exceeds safe size/degree limits')
    return terms


def _add(left, right, sign=1):
    result = dict(left)
    for powers, coefficient in right.items():
        result[powers] = result.get(powers, 0) + sign * coefficient
    return _bounded(result)


def _multiply(left, right):
    result = {}
    for p, c in left.items():
        for q, d in right.items():
            powers = tuple(a + b for a, b in zip(p, q))
            result[powers] = result.get(powers, 0) + c * d
            if len(result) > MAX_TERMS:
                raise IncompleteContent('Charge polynomial exceeds safe term limit')
    return _bounded(result)


def _syntax(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 1024:
        raise IncompleteContent('Use one nonempty charge/constraint expression, at most 1024 characters')
    try:
        tree = ast.parse(text.strip(), mode='eval')
    except (SyntaxError, RecursionError, ValueError) as error:
        raise IncompleteContent('Invalid charge/constraint expression syntax') from error
    if sum(1 for _ in ast.walk(tree)) > 128:
        raise IncompleteContent('Charge/constraint expression exceeds safe syntax limit')
    return tree.body


def _polynomial(node, names):
    zero = (0,) * len(names)
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return _bounded({zero: node.value})
    if isinstance(node, ast.Name) and node.id in names:
        return {tuple(int(name == node.id) for name in names): 1}
    if isinstance(node, ast.Name):
        raise IncompleteContent('Undeclared charge parameter: ' + node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _polynomial(node.operand, names)
        return value if isinstance(node.op, ast.UAdd) else {p: -c for p, c in value.items()}
    if isinstance(node, ast.BinOp):
        left = _polynomial(node.left, names)
        if isinstance(node.op, ast.Pow):
            if not (isinstance(node.right, ast.Constant) and type(node.right.value) is int
                    and 0 <= node.right.value <= MAX_DEGREE):
                raise IncompleteContent('Charge powers must be literal integers between 0 and 32')
            result = {zero: 1}
            for _ in range(node.right.value):
                result = _multiply(result, left)
            return result
        if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult)):
            right = _polynomial(node.right, names)
            if isinstance(node.op, ast.Mult):
                return _multiply(left, right)
            return _add(left, right, -1 if isinstance(node.op, ast.Sub) else 1)
    raise IncompleteContent('Charges allow integer literals, declared parameters, +, -, *, ** and parentheses only')


@dataclass
class Polynomial:
    names: tuple
    terms: dict

    @property
    def symbols(self):
        return {name for i, name in enumerate(self.names) if any(p[i] for p in self.terms)}

    def render(self):
        pieces = []
        for powers in sorted(self.terms, reverse=True):
            coefficient = self.terms[powers]
            monomial = '*'.join(name if power == 1 else f'{name}**{power}'
                                for name, power in zip(self.names, powers) if power)
            magnitude = abs(coefficient)
            body = (('' if magnitude == 1 else str(magnitude) + '*') + monomial
                    if monomial else str(magnitude))
            pieces.append((('-' if coefficient < 0 else '') if not pieces else
                           (' - ' if coefficient < 0 else ' + ')) + body)
        return ''.join(pieces) or '0'

    def evaluate(self, values):
        result = 0
        for powers, coefficient in self.terms.items():
            term = coefficient
            for name, power in zip(self.names, powers):
                if not power:
                    continue
                term *= values[name] ** power
                if abs(term).bit_length() > MAX_BITS:
                    raise IncompleteContent('Evaluated charge exceeds safe integer size')
            result += term
        if abs(result).bit_length() > MAX_BITS:
            raise IncompleteContent('Evaluated charge exceeds safe integer size')
        return result


def parse_charge(text, names):
    result = Polynomial(names, _polynomial(_syntax(text), names))
    # Canonical output must itself fit the language, not become an unusable
    # payload on a second preflight after a large expansion.
    _syntax(result.render())
    return result


def parse_constraints(constraints, names):
    if not isinstance(constraints, list) or len(constraints) > MAX_CONSTRAINTS:
        raise IncompleteContent('constraints must be a list of at most 64 comparisons')
    atoms = []
    for text in constraints:
        node = _syntax(text)
        if not isinstance(node, ast.Compare) or any(type(op) not in COMPARISONS for op in node.ops):
            raise IncompleteContent('Each constraint must use ==, !=, <, <=, > or >=; list items are joined by AND')
        values = [node.left, *node.comparators]
        for left, op, right in zip(values, node.ops, values[1:]):
            a = Polynomial(names, _polynomial(left, names))
            b = Polynomial(names, _polynomial(right, names))
            symbol, compare = COMPARISONS[type(op)]
            _syntax(f'{a.render()} {symbol} {b.render()}')
            if not a.symbols and not b.symbols:
                if not compare(a.evaluate({}), b.evaluate({})):
                    raise IncompleteContent('Constraint is identically false: ' + text)
                continue
            atoms.append((a, symbol, b, compare))
            if len(atoms) > MAX_CONSTRAINTS:
                raise IncompleteContent('Too many constraint comparisons after expanding chains')
    return atoms


def validate_values(values, names):
    if not isinstance(values, dict) or set(values) != set(names):
        raise IncompleteContent('Provide exactly one integer value for every declared parameter')
    if any(type(value) is not int or abs(value).bit_length() > 256 for value in values.values()):
        raise IncompleteContent('Parameter values must be exact integers of at most 256 bits, not floats or booleans')


def constraint_text(atom):
    left, symbol, right, _ = atom
    return f'{left.render()} {symbol} {right.render()}'


def check_constraints(atoms, values):
    for left, symbol, right, compare in atoms:
        if not compare(left.evaluate(values), right.evaluate(values)):
            raise IncompleteContent(f'Parameter assignment violates constraint: {left.render()} {symbol} {right.render()}')
