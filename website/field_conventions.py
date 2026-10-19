"""Exact dimension and Young-diagram displays; Dynkin labels remain identity."""
from fractions import Fraction

REPRESENTATION_CONVENTION = {
    "id":"dynkin-gauge-1",
    "nonAbelian":"Highest-weight Dynkin labels, one nonnegative integer per node",
    "nodeNumbering":"Bourbaki numbering, as in Sage finite Cartan types",
    "nodeNumberingReference":"https://doc.sagemath.org/html/en/reference/combinat/sage/combinat/root_system/cartan_type.html",
    "abelian":"Exact charges in the recorded factor basis and common normalization",
    "dimensionShorthandD":"For odd D_r, the penultimate spinor node is unbarred and its dual is barred in dimension shorthand; exact Dynkin labels remain the identifiers",
}

def dimension_a(labels):
    """Weyl dimension formula for A_r; exact integer arithmetic."""
    if labels is None: return None
    n=len(labels)+1
    value=Fraction(1)
    for i in range(n):
        for j in range(i+1,n): value*=Fraction(sum(labels[i:j])+j-i,j-i)
    return int(value)


def dimension_d(labels):
    """Exact Weyl dimension formula in the Bourbaki D_r node convention."""
    if labels is None: return None
    n=len(labels)
    if n<4 or any(type(a) is not int or a<0 for a in labels):
        raise ValueError('D_r dimensions require nonnegative rank-r labels, r >= 4')
    weight=[Fraction(0) for _ in labels]
    for i,a in enumerate(labels):
        fundamental=[Fraction(j<=i) for j in range(n)] if i<n-2 else [Fraction(1,2)]*n
        if i==n-2: fundamental[-1]=-fundamental[-1]
        weight=[x+a*y for x,y in zip(weight,fundamental)]
    rho=list(range(n-1,-1,-1));value=Fraction(1)
    for i in range(n):
        for j in range(i+1,n):
            value*=((weight[i]+rho[i])**2-(weight[j]+rho[j])**2)/Fraction(rho[i]**2-rho[j]**2)
    if value.denominator!=1 or value<=0: raise ValueError('Invalid Weyl dimension')
    return int(value)


def irrep_dimension(algebra,labels):
    if labels is None: return None
    if len(labels)!=algebra['rank']: raise ValueError('Gauge irrep rank mismatch')
    if algebra['type']=='A': return dimension_a(labels)
    if algebra['type']=='D': return dimension_d(labels)
    return 1 if not any(labels) else None


def irrep_dimension_label(algebra,labels):
    dimension=irrep_dimension(algebra,labels)
    if dimension is None: return '['+','.join(map(str,labels))+']' if labels is not None else '?'
    conjugate=(algebra['type']=='A' and labels<labels[::-1] or
               algebra['type']=='D' and algebra['rank']%2 and labels[-2]<labels[-1])
    return 'bar('+str(dimension)+')' if conjugate else str(dimension)


def young_rows(algebra,labels):
    if algebra.get("type")!="A" or labels is None: return None
    return [sum(labels[i:]) for i in range(len(labels)) if sum(labels[i:])]
