"""Exact browsing order for canonical Lorentz × gauge matter spectra.

Dimension means real field-space dimension, not on-shell polarizations. Gauge
connections are already specified by the algebra and are not extra matter.
"""
from fractions import Fraction
import json
from math import prod

from .charge_expressions import parse_charge
from .field_conventions import weyl_dimension
from .scalar_conventions import is_scalar, representation_type


def lorentz_dimension(lorentz):
    dimension=lorentz['dimension']
    if dimension==4 and lorentz['scheme']=='jL_jR':
        weights=[tuple(Fraction(x) for x in weight) for weight in lorentz['irreps']]
        if not weights or any(len(w)!=2 or any(x<0 or (2*x).denominator!=1 for x in w) for w in weights):
            raise ValueError('Invalid Lorentz spins for matter ordering')
        return int(sum(prod(2*x+1 for x in weight) for weight in weights))
    if dimension>4:
        family='D' if dimension%2==0 else 'B'
        rank=dimension//2
        if lorentz['scheme']==f'{family}{rank}_Dynkin' and lorentz['irreps']:
            if any(len(weight)!=rank for weight in lorentz['irreps']):
                raise ValueError('Lorentz rank mismatch for matter ordering')
            return sum(weyl_dimension(family,weight) for weight in lorentz['irreps'])
    raise ValueError('Unsupported Lorentz convention for matter ordering')


def _real_scalar_multiplier(factors,gauge,parameters):
    # Determine the non-Abelian type without giving a symbolic charge a value.
    simple=[{**factor,'id':str(i)} for i,factor in enumerate(factors) if factor['family']!='U1']
    reps={str(i):rep for i,rep in enumerate(gauge)}
    if representation_type(simple,reps)!='real':return 2
    symbolic=False
    for factor,rep in zip(factors,gauge):
        if factor['family']=='U1':
            charge=parse_charge(rep['charge'],parameters)
            if charge.symbols:symbolic=True
            elif int(charge.render()):return 2
    if symbolic:
        raise ValueError('Nonuniform symbolic real-module dimension; retain source scalar counting')
    return 1


def matter_dimension(canonical):
    """Total real dimension, with multiplicities and explicit reality imposed."""
    factors=canonical['gauge_factors']
    parameters=tuple(sorted(canonical.get('parameters',{})))
    total=0
    for row in canonical['matter']:
        if len(row['gauge'])!=len(factors):raise ValueError('Gauge representation rank mismatch')
        if any(len(rep['dynkin'])!=factor['rank'] for factor,rep in zip(factors,row['gauge'])
               if factor['family']!='U1'):raise ValueError('Gauge Dynkin rank mismatch')
        lorentz=lorentz_dimension(row['lorentz'])
        gauge=prod(weyl_dimension(factor['family'],rep['dynkin'])
                   for factor,rep in zip(factors,row['gauge']) if factor['family']!='U1')
        reality=row['reality']
        if reality=='real_module':
            if not is_scalar(row['lorentz']):raise ValueError('real_module is a scalar convention')
            multiplier=_real_scalar_multiplier(factors,row['gauge'],parameters)
        elif reality in {'none','complex'}:multiplier=2
        elif reality in {'real','majorana'}:multiplier=1
        else:raise ValueError('Unsupported matter reality convention')
        total+=row['copies']*lorentz*gauge*multiplier
    return total


def _charge_signature(charge,parameters):
    try:return (0,Fraction(charge))
    except ValueError:
        polynomial=parse_charge(charge,parameters)
        return (1,tuple(sorted(polynomial.terms.items(),reverse=True)))


def matter_sort_key(canonical):
    """Descending dimension, then exact labels; canonical metadata resolves ties.

    Callers provide identity-canonical data, so names, row splitting, parameter
    relabelings and permutations of identical gauge factors cannot affect order.
    """
    parameters=tuple(sorted(canonical.get('parameters',{})))
    rows=[]
    for row in canonical['matter']:
        lorentz=row['lorentz']
        rows.append((lorentz['dimension'],lorentz['scheme'],
                     tuple(sorted(tuple(Fraction(x) for x in weight) for weight in lorentz['irreps'])),
                     tuple((0,tuple(rep['dynkin'])) if 'dynkin' in rep else
                           (1,_charge_signature(rep['charge'],parameters)) for rep in row['gauge']),
                     row['reality'],row['copies']))
    return (-matter_dimension(canonical),tuple(sorted(rows)),
            json.dumps(canonical,sort_keys=True,separators=(',',':')))
