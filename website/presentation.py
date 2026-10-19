"""Readable matrices derived from exact specifications, never intake inference."""
from copy import deepcopy
import json
from scalar_conventions import is_scalar, uniform_scalar
from field_conventions import irrep_dimension, irrep_dimension_label, young_rows


def algebra_label(family,rank):
    return {'A':f'su({rank+1})','B':f'so({2*rank+1})','C':f'sp_rank({rank})','D':f'so({2*rank})','U1':'u(1)'}.get(family,family.lower()+str(rank))


def factors(spec):
    return [{'key':a['id'],'id':'u1' if a['family']=='U1' else a['family']+str(a['rank']),
             'type':a['family'],'rank':a['rank'],'label':algebra_label(a['family'],a['rank']),
             'role':a['id']} for a in spec['gauge_factors']]




def matrix(spec):
    columns=factors(spec); rows=[]; symbolic=spec['schema_version']=='field-content-3'
    for source in spec['matter']:
        f=uniform_scalar(source,spec['gauge_factors'],spec['parameters']) if symbolic and is_scalar(source['lorentz']) else source
        l=f['lorentz']; d=l['dimension']; w=l['irreps']
        component='S' if is_scalar(l) else 'F' if d==4 and w==[['1/2','0']] else 'matter'
        label=' ⊕ '.join('('+', '.join(x)+')' for x in w) if d==4 else ' ⊕ '.join('['+','.join(map(str,x))+']' for x in w)
        components=[]
        for a in columns:
            r=f['gauge_representations'][a['key']]
            c={'factorKey':a['key'],'factor':a['label'],'role':a['role']}
            if a['type']=='U1':
                c.update(value=r['charge'],dynkin=None,youngRows=None)
                if symbolic:c['chargeExpression']=r['charge']
            else:c.update(value=irrep_dimension_label(a,r['dynkin']),dynkin=r['dynkin'],dimension=irrep_dimension(a,r['dynkin']),youngRows=young_rows(a,r['dynkin']))
            components.append(c)
        rows.append({'labels':[f.get('label','')],'copies':f['copies'],'components':components,'lorentz':{
            'component':component,'reality':f['reality'],'scheme':l['scheme'],'irreps':w,
            'label':label,'spacetime':{'dimension':str(d),'algebra':f'so(1,{d-1})'}}})
    # Combine only exact Lorentz × gauge representations, never dimension labels.
    merged={}
    for row in rows:
        key=json.dumps([row['lorentz'],[{'dynkin':c['dynkin']} if c['dynkin'] is not None else {'charge':c['value']} for c in row['components']]],sort_keys=True)
        if key in merged:
            merged[key]['copies']+=row['copies']; merged[key]['labels']+=row['labels']
        else:merged[key]=row
    return {'factors':columns,'rows':list(merged.values()),'parameters':spec.get('parameters',{}),'constraints':spec.get('constraints',[])}


def compact_baseline(regime,templates):
    """A display shortcut only when a complete reference is literally present."""
    fs=regime['factors']
    expected=[('A2',{'colour'}),('A1',{'weak_L','left'}),('u1',{'hypercharge'})]
    if len(fs)!=3:return
    positions=[]
    for identifier,roles in expected:
        matches=[i for i,a in enumerate(fs) if a['id']==identifier and a['role'] in roles]
        if len(matches)!=1:return
        positions.append(matches[0])
    def key(row,order):
        l=row['lorentz']
        return json.dumps([l['spacetime']['dimension'],l['scheme'],l['irreps'],l['reality'],
            [row['components'][i]['dynkin'] if row['components'][i]['dynkin'] is not None else row['components'][i]['value'] for i in order]])
    codes=['R_MSSM','R_SM','F_SM']
    scalars=[row for row in regime['rows'] if row['lorentz']['component']=='S']
    # Keep all Higgs doublets together rather than hide one in R_SM.
    if len(scalars)==1 and scalars[0]['copies']>1 and key(scalars[0],positions)==key(templates['H_SM']['rows'][0],[0,1,2]):
        codes=['R_MSSM','F_SM','R_SM']
    for code in codes:
        remaining=deepcopy(regime['rows'])
        for reference in templates[code]['rows']:
            match=next((row for row in remaining if key(row,positions)==key(reference,[0,1,2]) and row['copies']>=reference['copies']),None)
            if match is None:break
            match['copies']-=reference['copies']
        else:
            regime['baseline']=code
            regime['additionalRows']=[row for row in remaining if row['copies']]
            return
