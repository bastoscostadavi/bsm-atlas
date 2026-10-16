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

def restrict_nonabelian(spec):
    """Return a canonical core from one complete numerical description regime.

    A charged scalar's underlying real module may split on restriction. If
    its complex representative becomes real type, each copy becomes two real
    copies. Removing columns alone would lose half its degrees of freedom.
    """
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
            raise IncompleteContent('Complex non-scalar real-module restriction requires a separate counting adapter')
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
