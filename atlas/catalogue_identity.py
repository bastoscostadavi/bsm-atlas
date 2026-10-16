"""Canonical field-content identity, not physical-theory equivalence.

Names, paper IDs, source field names and row order are not identity. Abelian
charges are exact rationals, normalized over the WHOLE inventory. Repeated
factor permutations and independent U(1) sign choices are canonicalized.
General mixing of several U(1) generators and outer automorphisms of simple
algebras are deliberately not certified by an unmatched fingerprint.
"""
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
from functools import reduce
from hashlib import sha256
from itertools import permutations,product
from math import gcd,lcm,factorial
import json
import re

SCHEMA='field-content-1'

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

    Preserve factor IDs, source labels and generator orientation. The separate
    identity fingerprint additionally quotients factor permutations/signs.
    This does not extract facts, certify provenance or accept symbolic families.
    """
    object_keys(spec,{'schema_version','inventory_complete','gauge_factors','matter'},{'name','paper_ids'})
    if 'name' in spec and not isinstance(spec['name'],str):raise IncompleteContent('Name must be a string')
    if 'paper_ids' in spec and (not isinstance(spec['paper_ids'],list) or any(not isinstance(p,str) for p in spec['paper_ids'])):raise IncompleteContent('Paper IDs must be strings')
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
        object_keys(field,{'lorentz','reality','copies','gauge_representations'},{'label'})
        if 'label' in field and not isinstance(field['label'],str):raise IncompleteContent('Field label must be a string')
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

def canonicalize(spec):
    normalized=normalize_spec(spec)
    factors=normalized['gauge_factors'];canonical_fields=normalized['matter']
    groups=defaultdict(list)
    for a in factors:groups[(a['family'],a['rank'])].append(a)
    groups=[groups[k] for k in sorted(groups,key=lambda k:(k[0]=='U1',k[0],-k[1]))]
    bound=2**sum(a['family']=='U1' for a in factors)
    for group in groups:bound*=factorial(len(group))
    if bound>4096:raise IncompleteContent('Factor-permutation/sign search exceeds safe bound; manual reconciliation required')
    best=None
    for choices in product(*(permutations(g) for g in groups)):
        order=[a for group in choices for a in group];abelian=[i for i,a in enumerate(order) if a['family']=='U1']
        for signs in product((-1,1),repeat=len(abelian)):
            orientation=dict(zip(abelian,signs));merged=defaultdict(int)
            for f in canonical_fields:
                values=[]
                for i,a in enumerate(order):
                    rep=f['gauge_representations'][a['id']]
                    values.append({'charge':str(int(rep['charge'])*orientation[i])} if a['family']=='U1' else rep)
                content={'lorentz':f['lorentz'],'reality':f['reality'],'gauge':values}
                merged[json.dumps(content,sort_keys=True,separators=(',',':'))]+=f['copies']
            rows=[{**json.loads(k),'copies':n} for k,n in sorted(merged.items())]
            payload=json.dumps({'schema_version':SCHEMA,'gauge_factors':[{k:a[k] for k in ['family','rank']} for a in order],'matter':rows},sort_keys=True,separators=(',',':'))
            if best is None or payload<best:best=payload
    return {'fingerprint':sha256(best.encode()).hexdigest(),'canonical_json':best}

def from_regime(regime,templates,weight_resolver):
    """Convert one scoped catalogue regime; never union UV/IR inventories."""
    factors=regime['factors'];columns=[]
    for a in factors:
        if a['type'] not in {'A','B','C','D','E','F','G','U1'} or not a['rank']:raise IncompleteContent('Gauge factor not fixed')
        columns.append({'id':a['key'],'family':a['type'],'rank':a['rank']})
    matter=[]
    def append(field,reps):
        for lorentz in field['lorentz']:
            if lorentz['status']!='resolved':raise IncompleteContent('Unresolved Lorentz/source chirality for '+field['label'])
            d=lorentz['spacetime']['dimension']
            if not d or not str(d).isdigit():raise IncompleteContent('Parameterized spacetime dimension')
            actual=deepcopy(reps)
            if lorentz.get('conjugateGauge'):
                actual={a['id']:conjugate(reps[a['id']],a) for a in columns}
            reality=str(lorentz.get('reality') or '').lower()
            if lorentz['component']=='S':
                if reality.startswith('complex'):reality='complex'
                elif reality.startswith('real'):reality='real'
                else:raise IncompleteContent('Scalar reality not extracted for '+field['label'])
            elif lorentz['component'] in {'F','F_D'}:reality='none'
            elif reality.startswith('real'):reality='real'
            elif reality.startswith('complex'):reality='complex'
            else:raise IncompleteContent('Vector reality not extracted')
            matter.append({'label':field['label'],'lorentz':{'dimension':int(d),'scheme':lorentz['scheme'],'irreps':lorentz['irreps']},'reality':reality,'copies':field['copies'],'gauge_representations':actual})
    fields=[f for f in regime['fields'] if not f['excludedCoordinate'] and not (regime['baseline'] and f['inherited'])]
    if regime['baseline']:
        for f in templates[regime['baseline']]['fields']:
            reps={}
            for a in factors:
                if a['id']=='A2' and a['role']=='colour':i=0
                elif a['id']=='A1' and a['role'] in {'weak_L','left'}:i=1
                elif a['id']=='u1' and a['role']=='hypercharge':i=2
                else:raise IncompleteContent('Baseline charges under extra factors require explicit assignments')
                if i==2:reps[a['key']]={'charge':f['representation'][i]}
                else:
                    weight=weight_resolver(a,f['representation'][i])
                    if weight is None:raise IncompleteContent('Unresolved reference irrep')
                    reps[a['key']]={'dynkin':weight}
            append(f,reps)
    for f in fields:
        if f['copies'] is None:raise IncompleteContent('Multiplicity not extracted for '+f['label'])
        reps={}
        for a,c in zip(factors,f['components']):
            if a['type']=='U1':
                try:Fraction(c['value'])
                except (ValueError,ZeroDivisionError,TypeError):raise IncompleteContent('Unresolved Abelian assignment for '+f['label'])
                reps[a['key']]={'charge':c['value']}
            elif c['dynkin'] is not None:reps[a['key']]={'dynkin':c['dynkin']}
            else:raise IncompleteContent('Irrep not converted to canonical Dynkin labels for '+f['label'])
        append(f,reps)
    return {'schema_version':SCHEMA,'inventory_complete':True,'gauge_factors':columns,'matter':matter}
