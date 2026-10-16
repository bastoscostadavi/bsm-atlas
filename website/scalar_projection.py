"""Project source scalar containers into canonical real gauge-module rows."""
from copy import deepcopy
from fractions import Fraction
from scalar_conventions import CONVENTION, real_scalar
from field_conventions import dynkin_representation, young_rows

def migrate_field(field, factors):
    columns = [{'id':str(i),'family':a['type'],'rank':a['rank']} for i,a in enumerate(factors)]
    for l in field['lorentz']:
        if l['component'] != 'S':
            l['copies'] = field['copies']
            continue
        if l.get('scalarNormalization',{}).get('status') == 'canonical': continue
        original = deepcopy(l.get('gaugeComponents',field['components']))
        source_reality = str(l.get('reality') or '').lower()
        reality = 'complex' if source_reality.startswith('complex') else 'real' if source_reality.startswith('real') else None
        l['sourceScalar'] = {'reality':l.get('reality'),'copies':field['copies'],'gaugeComponents':original}
        try:
            if reality is None or field['copies'] is None or not factors:
                raise ValueError('Source scalar counting is not established')
            if len(original) != len(factors):
                raise ValueError('Missing gauge factor assignments')
            reps = {}
            for i,(a,c) in enumerate(zip(factors,original)):
                if a['type'] == 'U1':
                    q = Fraction(c['value'])
                    if q.denominator != 1: raise ValueError('Shared integer charge unit is unresolved')
                    reps[str(i)] = {'charge':str(q)}
                elif c.get('dynkin') is not None and a['type'] in {'A','B','C','D','E','F','G'}:
                    reps[str(i)] = {'dynkin':c['dynkin']}
                else: raise ValueError('Exact gauge irrep is unresolved')
            result,kind = real_scalar({'copies':field['copies'],'reality':reality,'gauge_representations':reps},columns)
            actual = deepcopy(original)
            for i,(a,c) in enumerate(zip(factors,actual)):
                r = result['gauge_representations'][str(i)]
                if a['type'] == 'U1': c['value'] = r['charge']
                else:
                    if r['dynkin'] != c['dynkin']:
                        v = c['value'];c['value'] = v[4:-1] if v.startswith('bar(') else 'bar('+v+')'
                    c['dynkin'] = r['dynkin'];c['youngRows'] = young_rows(a,r['dynkin'])
            l.update(copies=result['copies'],reality='real_module',gaugeComponents=actual,
                dynkinRepresentation=dynkin_representation(actual),
                scalarNormalization={'status':'canonical','convention':CONVENTION['id'],'complexIrrepType':kind,
                    'copyMultiplier':result['copies']//field['copies'],'realDimensionMultiplier':1 if kind=='real' else 2})
        except (ValueError,TypeError,KeyError,ZeroDivisionError) as error:
            l.update(copies=None,scalarNormalization={'status':'pending','reason':str(error)})
    field['componentCounting'] = 'Component copies are canonical; source-container copies remain provenance only'

def migrate_catalogue(entries, templates, sm_factors):
    for template in templates.values():
        for f in template['fields']: migrate_field(f,sm_factors)
    for e in entries:
        for v in e['variants']:
            for r in v['regimes']:
                for f in r['fields']: migrate_field(f,r['factors'])
