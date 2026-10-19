"""Canonical gauge–matter identity with irreducible-real scalar modules."""
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from itertools import permutations, product
from math import factorial
import json

from entry_validation import (IncompleteContent, object_keys,
    primitive_charge_scale, conjugate, normalize_spec as validate_numerical)
from scalar_conventions import real_scalar, orient_reps, is_scalar

SCHEMA = 'field-content-2'


def normalize_spec(spec):
    if isinstance(spec,dict) and spec.get('schema_version')=='field-content-3':
        raise IncompleteContent('Use prepare_entry for parameterized validation or specialize with --values before numerical identity checking')
    if not isinstance(spec,dict) or spec.get('schema_version') != SCHEMA:
        raise IncompleteContent('Use field-content-2 numerical inputs')
    source = deepcopy(spec)
    validation = deepcopy(spec)
    validation['schema_version'] = SCHEMA
    for f in validation.get('matter',[]) if isinstance(validation.get('matter'),list) else []:
        if isinstance(f,dict) and f.get('reality') == 'real_module':
            # Validate shape/Lorentz/Dynkin/charges; the explicit real-module unit is
            # validated below, not mistaken for an ordinary real charged irrep.
            f['reality'] = 'complex'
    result = validate_numerical(validation)
    sources = []
    for f in source['matter']:
        l = f['lorentz']
        weights = [[str(Fraction(x)) for x in w] for w in l['irreps']]
        pair = l['dimension'] == 4 and sorted(weights) == sorted([['1/2','0'],['0','1/2']])
        sources.extend([f] * (2 if pair and f['reality'] != 'majorana' else 1))
    if len(sources) != len(result['matter']):
        raise IncompleteContent('Source/component correspondence failed')
    fields = []
    for f,original in zip(result['matter'],sources):
        if is_scalar(f['lorentz']):
            try:
                f,_ = real_scalar(f,result['gauge_factors'],original['reality'])
            except (ValueError,KeyError,TypeError) as error:
                raise IncompleteContent(str(error)) from error
        elif original['reality'] == 'real_module':
            raise IncompleteContent('real_module is a scalar counting unit, not a fermion convention')
        fields.append(f)
    result.update(schema_version=SCHEMA,matter=fields)
    return result


def canonicalize(spec):
    normalized = normalize_spec(spec)
    factors,fields = normalized['gauge_factors'],normalized['matter']
    groups = defaultdict(list)
    for a in factors: groups[(a['family'],a['rank'])].append(a)
    groups = [groups[k] for k in sorted(groups,key=lambda k:(k[0]=='U1',k[0],-k[1]))]
    bound = 2 ** sum(a['family']=='U1' for a in factors)
    for group in groups: bound *= factorial(len(group))
    if bound > 4096:
        raise IncompleteContent('Factor-permutation/sign search exceeds safe bound; reconcile manually')
    best = None
    for choices in product(*(permutations(g) for g in groups)):
        order = [a for group in choices for a in group]
        abelian = [a for a in order if a['family']=='U1']
        for signs in product((-1,1),repeat=len(abelian)):
            orientation = {a['id']:s for a,s in zip(abelian,signs)}
            merged = defaultdict(int)
            for f in fields:
                reps = deepcopy(f['gauge_representations'])
                for a in abelian:
                    reps[a['id']]['charge'] = str(int(reps[a['id']]['charge'])*orientation[a['id']])
                if f['reality'] == 'real_module':
                    # Rechoose the scalar representative after every factor
                    # permutation/generator sign choice, not only at intake.
                    reps = orient_reps(reps,order)
                content = {'lorentz':f['lorentz'],'reality':f['reality'],
                           'gauge':[reps[a['id']] for a in order]}
                merged[json.dumps(content,sort_keys=True,separators=(',',':'))] += f['copies']
            rows = [{**json.loads(k),'copies':n} for k,n in sorted(merged.items())]
            payload = json.dumps({'schema_version':SCHEMA,
                'gauge_factors':[{k:a[k] for k in ['family','rank']} for a in order],
                'matter':rows},sort_keys=True,separators=(',',':'))
            if best is None or payload < best: best = payload
    return {'fingerprint':sha256(best.encode()).hexdigest(),'canonical_json':best}
