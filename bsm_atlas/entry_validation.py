"""Strict numerical input validation shared by normalization and identity."""
from copy import deepcopy
from fractions import Fraction
from functools import reduce
from math import gcd,lcm
import re

SCHEMA='field-content-2'

class IncompleteContent(ValueError):pass

def object_keys(value,required,optional=()):
    if not isinstance(value,dict) or not set(required)<=set(value) or set(value)-set(required)-set(optional):
        raise IncompleteContent('Object has missing or unsupported schema fields; use atlas/entry.schema.json')

def primitive_charge_scale(charges):
    nonzero=[Fraction(q) for q in charges if Fraction(q)]
    if not nonzero:return None
    denominator=lcm(*(q.denominator for q in nonzero))
    return Fraction(denominator,reduce(gcd,(abs(int(q*denominator)) for q in nonzero)))

def conjugate(rep,factor):
    if factor['family']=='U1':return {'charge':str(-Fraction(rep['charge']))}
    a=rep['dynkin'][:];family=factor['family'];rank=factor['rank']
    if family=='A':a.reverse()
    elif family=='D' and rank%2:a[-2:]=a[-2:][::-1]
    elif family=='E' and rank==6:raise IncompleteContent('E6 charge-conjugation conversion requires an explicit node-convention mapping')
    return {'dynkin':a}

def normalize_spec(spec):
    """Validate and normalize a complete numerical intake BEFORE persistence.

    Preserve factor IDs and generator orientation. The separate
    identity fingerprint additionally quotients factor permutations/signs.
    This does not extract facts, certify provenance or accept symbolic families.
    """
    object_keys(spec,{'schema_version','inventory_complete','gauge_factors','matter'})
    if spec.get('schema_version')!=SCHEMA:raise IncompleteContent('Unsupported or missing schema_version')
    if spec.get('inventory_complete') is not True:raise IncompleteContent('A complete declared inventory is required; partial inputs only support candidate reconciliation')
    factors=deepcopy(spec.get('gauge_factors',[]));matter=deepcopy(spec.get('matter',[]))
    if not isinstance(factors,list) or not isinstance(matter,list) or not factors or not matter:raise IncompleteContent('A full gauge algebra and matter inventory are required')
    for a in factors:object_keys(a,{'id','family','rank'})
    ids=[a['id'] for a in factors]
    if any(not isinstance(i,str) or not i for i in ids):raise IncompleteContent('Factor IDs must be nonempty strings')
    if len(ids)!=len(set(ids)):raise IncompleteContent('Duplicate factor IDs')
    for a in factors:
        if a.get('family') not in {'A','B','C','D','E','F','G','U1'} or type(a.get('rank')) is not int or a['rank']<1:raise IncompleteContent('Unresolved Cartan type/rank')
        if a['family']=='U1' and a['rank']!=1:raise IncompleteContent('Every U(1) has rank 1')
        family,rank=a['family'],a['rank']
        if (family=='B' and rank<3) or (family=='C' and rank<2) or (family=='D' and rank<4) or (family=='E' and rank not in {6,7,8}) or (family=='F' and rank!=4) or (family=='G' and rank!=2):raise IncompleteContent('Use canonical simple factors: A1 instead of B1/C1, C2 instead of B2, A3 instead of D3, and A1+A1 instead of D2')
    canonical_fields=[]
    for field in matter:
        object_keys(field,{'lorentz','reality','copies','gauge_representations'})
        if type(field.get('copies')) is not int or field['copies']<1:raise IncompleteContent('Copies must be a positive integer, not representation dimension')
        lorentz=field.get('lorentz',{})
        object_keys(lorentz,{'dimension','scheme','irreps'})
        d=lorentz.get('dimension')
        if type(d) is not int or d<4:raise IncompleteContent('A fixed spacetime dimension is required')
        irreps=lorentz.get('irreps',[])
        if not isinstance(irreps,list) or not irreps or any(not isinstance(w,list) for w in irreps):raise IncompleteContent('A unique Lorentz representation is required')
        if field.get('reality') not in {'real','complex','none','majorana'}:raise IncompleteContent('Explicit reality/conjugacy convention required')
        reps=field.get('gauge_representations',{})
        if not isinstance(reps,dict) or set(reps)!=set(ids):raise IncompleteContent('Assign every gauge factor explicitly; missing is not singlet/zero')
        for a in factors:
            rep=reps[a['id']]
            object_keys(rep,{'charge'} if a['family']=='U1' else {'dynkin'})
            if a['family']=='U1':
                try:
                    if not isinstance(rep['charge'],str) or not re.fullmatch(r'[+-]?\d+(?:/[1-9]\d*)?',rep['charge']):raise ValueError('Use an exact rational string')
                    q=Fraction(rep['charge'])
                except (ValueError,KeyError,ZeroDivisionError,TypeError):raise IncompleteContent('Charges must be exact rational strings')
                rep['charge']=str(q)
            elif not isinstance(rep.get('dynkin'),list) or len(rep['dynkin'])!=a['rank'] or any(type(n) is not int or n<0 for n in rep['dynkin']):raise IncompleteContent('Dynkin label rank mismatch or invalid coefficient')
        if d==4:
            if lorentz.get('scheme')!='jL_jR':raise IncompleteContent('4D Lorentz labels must use the jL_jR scheme')
            if any(any(type(x) not in {str,int} for x in w) for w in irreps):raise IncompleteContent('Use exact integer/rational Lorentz labels')
            try:weights=[[str(Fraction(x)) for x in w] for w in irreps]
            except (ValueError,TypeError,ZeroDivisionError):raise IncompleteContent('Invalid (jL,jR) labels')
            if any(len(w)!=2 or any(Fraction(x)<0 or (2*Fraction(x)).denominator!=1 for x in w) for w in weights):raise IncompleteContent('Lorentz spins must be nonnegative half-integers')
            if weights==[['0','0']]:
                if field['reality'] not in {'real','complex'}:raise IncompleteContent('A scalar needs a real or complex field convention')
                if field['reality']=='real' and any(a['family']=='U1' and Fraction(reps[a['id']]['charge']) for a in factors):raise IncompleteContent('A single real scalar irrep cannot carry a nonzero Abelian charge')
            # One 4D Dirac field in R = LH R plus LH conjugate(R).
            if sorted(weights)==sorted([['1/2','0'],['0','1/2']]):
                left={**field,'lorentz':{'dimension':4,'scheme':'jL_jR','irreps':[['1/2','0']]},'reality':'none'}
                canonical_fields.append(left)
                if field['reality']!='majorana':canonical_fields.append({**deepcopy(left),'gauge_representations':{a['id']:conjugate(reps[a['id']],a) for a in factors}})
                continue
            if weights==[['0','1/2']]:
                reps={a['id']:conjugate(reps[a['id']],a) for a in factors};weights=[['1/2','0']]
            if weights==[['1/2','0']]:field['reality']='none' # A mass restriction is not a new independent Weyl field.
            lorentz={'dimension':4,'scheme':'jL_jR','irreps':weights}
        else:
            rank=d//2;family='D' if d%2==0 else 'B'
            if lorentz.get('scheme')!=family+str(rank)+'_Dynkin' or any(len(w)!=rank or any(type(n) is not int or n<0 for n in w) for w in irreps):raise IncompleteContent('Use dimension-appropriate B/D Dynkin labels, not 4D spins')
            lorentz={'dimension':d,'scheme':lorentz['scheme'],'irreps':irreps}
        canonical_fields.append({**field,'lorentz':lorentz,'gauge_representations':reps})
    for a in factors:
        if a['family']!='U1':continue
        qs=[Fraction(f['gauge_representations'][a['id']]['charge']) for f in canonical_fields]
        scale=primitive_charge_scale(qs)
        if scale is None:continue
        for f,q in zip(canonical_fields,qs):f['gauge_representations'][a['id']]['charge']=str(int(q*scale))
    return {**deepcopy(spec),'gauge_factors':factors,'matter':canonical_fields}
