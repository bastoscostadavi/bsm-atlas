"""Canonical gauge/matter identity with irreducible-real scalar modules.

Version-1 source inputs are accepted explicitly and normalized to version 2.
The frozen v1 implementation is used only to audit historical extraction files.
"""
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
from hashlib import sha256
from itertools import permutations, product
from math import factorial
import json

from catalogue_identity_v1 import (IncompleteContent, object_keys,
    primitive_charge_scale, conjugate, normalize_spec as normalize_v1)
from scalar_conventions import real_scalar, orient_reps, is_scalar

SCHEMA = 'field-content-2'


def normalize_spec(spec):
    if not isinstance(spec,dict) or spec.get('schema_version') not in {'field-content-1',SCHEMA}:
        raise IncompleteContent('Use field-content-1 source inputs or field-content-2 canonical inputs')
    source = deepcopy(spec)
    validation = deepcopy(spec)
    validation['schema_version'] = 'field-content-1'
    for f in validation.get('matter',[]) if isinstance(validation.get('matter'),list) else []:
        if isinstance(f,dict) and f.get('reality') == 'real_module':
            if spec['schema_version'] != SCHEMA:
                raise IncompleteContent('Real-module units require field-content-2')
            # v1 validates shape/Lorentz/Dynkin/charges; the explicit v2 unit is
            # validated below, not mistaken for an ordinary real charged irrep.
            f['reality'] = 'complex'
    result = normalize_v1(validation)
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


def from_regime(regime,templates,weight_resolver):
    factors = regime['factors']
    columns = [{'id':a['key'],'family':a['type'],'rank':a['rank']} for a in factors]
    if any(a['family'] not in {'A','B','C','D','E','F','G','U1'} or not a['rank'] for a in columns):
        raise IncompleteContent('Gauge factors are not fixed')
    matter = []

    def reps_from_components(cs):
        if len(cs) != len(factors): raise IncompleteContent('Missing gauge factor assignments')
        result = {}
        for a,c in zip(factors,cs):
            if a['type'] == 'U1':
                try: q = Fraction(c['value'])
                except (ValueError,TypeError,ZeroDivisionError): raise IncompleteContent('Abelian assignment is not numerical')
                result[a['key']] = {'charge':str(q)}
            elif c.get('dynkin') is not None:
                result[a['key']] = {'dynkin':c['dynkin']}
            else: raise IncompleteContent('Canonical Dynkin labels are missing')
        return result

    def append(field,reps,template=False):
        for l in field['lorentz']:
            if l['status'] != 'resolved': raise IncompleteContent('Unresolved Lorentz or scalar counting')
            d = l['spacetime']['dimension']
            if not d or not str(d).isdigit(): raise IncompleteContent('Spacetime dimension is not fixed')
            actual = deepcopy(reps)
            if not template and l.get('gaugeComponents') is not None:
                actual = reps_from_components(l['gaugeComponents'])
            elif l.get('conjugateGauge'):
                actual = {a['id']:conjugate(actual[a['id']],a) for a in columns}
            reality = str(l.get('reality') or '').lower()
            if l['component'] == 'S':
                if reality == 'real_module': pass
                elif reality.startswith('complex'): reality = 'complex'
                elif reality.startswith('real'): reality = 'real'
                else: raise IncompleteContent('Scalar count is pending source extraction')
            elif l['component'] in {'F','F_D'}: reality = 'none'
            elif reality.startswith('real'): reality = 'real'
            elif reality.startswith('complex'): reality = 'complex'
            else: raise IncompleteContent('Vector reality is not extracted')
            count = l.get('copies',field['copies'])
            if count is None: raise IncompleteContent('Copy count is not extracted')
            matter.append({'label':field['label'],
                'lorentz':{'dimension':int(d),'scheme':l['scheme'],'irreps':l['irreps']},
                'reality':reality,'copies':count,'gauge_representations':actual})

    if regime['baseline']:
        for f in templates[regime['baseline']]['fields']:
            reps = {}
            for a in factors:
                if a['id']=='A2' and a['role']=='colour': i=0
                elif a['id']=='A1' and a['role'] in {'weak_L','left'}: i=1
                elif a['id']=='u1' and a['role']=='hypercharge': i=2
                else: raise IncompleteContent('Baseline charges under extra factors require explicit assignments')
                if i == 2: reps[a['key']] = {'charge':f['representation'][i]}
                else:
                    w = weight_resolver(a,f['representation'][i])
                    if w is None: raise IncompleteContent('Reference irrep is unresolved')
                    reps[a['key']] = {'dynkin':w}
            append(f,reps,True)
    for f in regime['fields']:
        if f['excludedCoordinate'] or regime['baseline'] and f['inherited']: continue
        append(f,reps_from_components(f['components']))
    return {'schema_version':SCHEMA,'inventory_complete':True,'gauge_factors':columns,'matter':matter}
