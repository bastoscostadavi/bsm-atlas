"""Derived non-Abelian restrictions; never a replacement for a full spectrum."""
from copy import deepcopy
from hashlib import sha256
import json

from catalogue_identity import normalize_spec, canonicalize, IncompleteContent
from scalar_conventions import is_scalar, representation_type

CONVENTION = {
    'id':'nonabelian-core-1',
    'projection':'Restrict the full matter representation to the semisimple gauge algebra; omit every Abelian factor, including hypercharge',
    'counting':'Preserve Lorentz representations and real scalar degrees of freedom; decompose and aggregate copy counts after restriction',
    'identity':'Gauge-factor/row order and identical-factor permutations removed; no general simple-algebra outer-automorphism quotient',
    'meaning':'Coarse grouping, not physical-theory equivalence, symmetry breaking, or an SM-embedding certificate',
}

ALGEBRA_CONVENTION = {
    'id':'semisimple-algebra-1',
    'projection':'Retain the multiset of resolved canonical simple gauge factors independently of matter-inventory completeness; omit every Abelian factor',
    'meaning':'Derived algebra-only grouping, not a global group, quotient, physical theory or additional source inventory',
}

FULL_ALGEBRA_CONVENTION = {
    'id':'full-gauge-algebra-1',
    'projection':'Retain canonical simple factors and the number of u(1) factors; omit matter, charges and source generator names',
    'meaning':'Abstract local gauge algebra, not a choice of Abelian basis, global group or quotient',
}

def algebra_key(core):
    """Key only the canonical semisimple algebra, independently of matter."""
    factors=[{'family':a['family'],'rank':a['rank']} for a in core['gauge_factors']]
    if any(a['family'] not in {'A','B','C','D','E','F','G'} for a in factors):
        raise IncompleteContent('Algebra-only keys require fixed canonical simple gauge factors')
    for a in factors:
        family,rank=a['family'],a['rank']
        if type(rank) is not int or not (family=='A' and rank>=1 or family=='B' and rank>=3 or family=='C' and rank>=2 or family=='D' and rank>=4 or family=='E' and rank in {6,7,8} or family=='F' and rank==4 or family=='G' and rank==2):
            raise IncompleteContent('Unresolved/noncanonical simple Cartan type or rank')
    factors.sort(key=lambda a:(a['family'],-a['rank']))
    canonical={'schema_version':ALGEBRA_CONVENTION['id'],'gauge_factors':factors}
    encoded=json.dumps(canonical,sort_keys=True,separators=(',',':'))
    return {'id':sha256(encoded.encode()).hexdigest(),'canonical':canonical}


def full_algebra_key(spec):
    """Algebra-only key shared by numerical spectra and symbolic families."""
    factors=spec['gauge_factors']
    if not factors or any(a['family']=='U1' and (type(a['rank']) is not int or a['rank']!=1) for a in factors):
        raise IncompleteContent('Full gauge algebra requires resolved canonical factors')
    simple=algebra_key({'gauge_factors':[a for a in factors if a['family']!='U1']})
    rank=sum(a['family']=='U1' for a in factors)
    canonical={'schema_version':FULL_ALGEBRA_CONVENTION['id'],
               'gauge_factors':simple['canonical']['gauge_factors']+[{'family':'U1','rank':1} for _ in range(rank)]}
    encoded=json.dumps(canonical,sort_keys=True,separators=(',',':'))
    return {'id':sha256(encoded.encode()).hexdigest(),'canonical':canonical,
            'semisimpleId':simple['id'],'abelianRank':rank}

def restrict_nonabelian(spec):
    """Return a canonical core from one complete numerical description regime.

    A charged scalar's underlying real module may split on restriction. If
    its complex representative becomes real type, each copy becomes two real
    copies. Removing columns alone would lose half its degrees of freedom.
    """
    if spec.get('schema_version')=='field-content-3':
        from parameterized_entry import normalize_parameterized
        source=normalize_parameterized(spec)
        factors=[a for a in source['gauge_factors'] if a['family']!='U1']
        # Restrict source complex fields BEFORE realification. This forgets
        # charges exactly; it does not evaluate parameters at a fictitious point.
        reduced={'schema_version':'field-content-2','inventory_complete':True,
                 'gauge_factors':deepcopy(factors),'matter':deepcopy(source['matter'])}
        for row in reduced['matter']:
            row['gauge_representations']={a['id']:row['gauge_representations'][a['id']] for a in factors}
            if not is_scalar(row['lorentz']) and row['reality']=='complex' and representation_type(factors,row['gauge_representations'])=='real':
                row['reality']='real'
                row['copies']*=2
        if not factors:
            reduced['gauge_factors']=[{'id':'empty-core-spectator','family':'A','rank':1}]
            for row in reduced['matter']:row['gauge_representations']={'empty-core-spectator':{'dynkin':[0]}}
        payload=json.loads(canonicalize(reduced)['canonical_json'])
        if not factors:
            payload['gauge_factors']=[]
            for row in payload['matter']:row['gauge']=[]
        payload['schema_version']=CONVENTION['id']
        encoded=json.dumps(payload,sort_keys=True,separators=(',',':'))
        return {'id':sha256(encoded.encode()).hexdigest(),'canonical':payload,
                'abelianRank':sum(a['family']=='U1' for a in source['gauge_factors'])}
    full=normalize_spec(spec)
    result=deepcopy(full)
    factors=[a for a in full['gauge_factors'] if a['family']!='U1']
    result['gauge_factors']=deepcopy(factors)
    for field,original in zip(result['matter'],full['matter']):
        field['gauge_representations']={a['id']:deepcopy(original['gauge_representations'][a['id']]) for a in factors}
        if is_scalar(field['lorentz']):
            before=representation_type(full['gauge_factors'],original['gauge_representations'])
            after=representation_type(factors,field['gauge_representations'])
            if before!='real' and after=='real': field['copies']*=2
        elif field['reality']=='complex':
            # A source complex vector stays a complex field when its restricted
            # gauge irrep is complex/pseudoreal. If it becomes real type, its
            # real and imaginary parts are two independent real vectors.
            if representation_type(factors,field['gauge_representations'])=='real':
                field['reality']='real'
                field['copies']*=2
    # The public numerical schema requires at least one gauge factor. A
    # temporary trivial spectator validates the zero semisimple algebra too;
    # it is removed before the core is encoded or hashed.
    if not factors:
        result['gauge_factors']=[{'id':'empty-core-spectator','family':'A','rank':1}]
        for field in result['matter']:
            field['gauge_representations']={'empty-core-spectator':{'dynkin':[0]}}
    payload=json.loads(canonicalize(result)['canonical_json'])
    if not factors:
        payload['gauge_factors']=[]
        for row in payload['matter']: row['gauge']=[]
    payload['schema_version']=CONVENTION['id']
    encoded=json.dumps(payload,sort_keys=True,separators=(',',':'))
    return {'id':sha256(encoded.encode()).hexdigest(),'canonical':payload,
        'abelianRank':sum(a['family']=='U1' for a in full['gauge_factors'])}
