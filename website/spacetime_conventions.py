"""Dimension-aware Lorentz FIELD representations, not Wigner particle spin.

4D uses Spin^+(1,3), with left-handed=(1/2,0). Scalars' reality and
spinors' conjugacy conditions remain separate from highest-weight labels.
Higher-dimensional labels are for the complexified Lorentz algebra in
Bourbaki B/D ordering, never an SU(2)xSU(2) label applied to a bulk spinor.
"""
import re

CONVENTION={
    "id":"lorentz-field-1",
    "fourDimensions":{"algebra":"so(1,3)","cover":"Spin^+(1,3)","labels":"(j_L,j_R)","leftWeyl":["1/2","0"],"vector":["1/2","1/2"],"scalar":["0","0"],"fermionBasis":"Independent left-handed Weyl fields only. A RH field is replaced by its LH charge conjugate: conjugate every non-Abelian irrep and negate every U(1) charge. A Dirac field is two LH fields in R and conjugate(R)."},
    "higherDimensions":"Complexified B/D Dynkin labels; standard vector node first and spinor node(s) last. No dimensional reduction is inferred.",
    "scope":"Finite-dimensional Lorentz field representations, not on-shell polarization counts or Poincare particle representations.",
    "unrecordedDimension":"Ordinary non-bulk field descriptions use an explicitly marked editorial 4D interpretation. Bulk/extra-dimensional descriptions with missing dimension remain unresolved. Brane fields are distinguished from bulk fields.",
}

def spacetime(regime,field=None):
    raw=str(regime.get('spacetime_dimension') or '').strip()
    kind=str((field or {}).get('field_kind') or '').lower()
    description=str(regime.get('description_kind') or '').lower()
    if 'brane' in kind:
        d='4';basis='boundary_field';note='Four-dimensional brane field, distinguished from the ambient bulk.'
    elif raw:
        d=raw;basis='source_dimension';note='Dimension retained from the source extraction.'
    elif any(w in kind+' '+description for w in ['bulk','extra-dimensional','extra dimension','vortex']):
        d=None;basis='dimension_unresolved';note='No fixed spacetime dimension inferred for an unresolved bulk description.'
    else:
        d='4';basis='editorial_4d_interpretation';note='Four-dimensional interpretation of this ordinary field description; the original extraction did not record a dimension. Not a new checked source assertion.'
    return {'dimension':d,'algebra':'so(1,'+str(int(d)-1)+')' if d and d.isdigit() else 'so(1,D−1)', 'basis':basis,'note':note}

def field_reps(kinds,source_kind='',chirality='',reality=None,scope=None,converted_right=False):
    scope=scope or {'dimension':'4','algebra':'so(1,3)','basis':'declared_reference_template','note':'Explicit 4D reference template.'}
    d=scope['dimension'];kind=source_kind.lower();hand=chirality.lower()
    result=[]
    for component in kinds:
        item={'component':component,'spacetime':scope,'label':None,'scheme':None,'irreps':[],'alternatives':[],'status':'resolved','reality':('complex' if kinds==['S','F'] and component=='S' else reality),'note':''}
        if d=='4':
            item['scheme']='jL_jR'
            if component=='S': item['irreps']=[['0','0']]
            elif component=='V': item['irreps']=[['1/2','1/2']]
            elif component=='F_D':
                item['irreps']=[['1/2','0']]
                item['component']='F'
                item['note']='Left-handed component of a source Dirac field. Its independent charge-conjugated RH component is a separate LH row.'
            elif component=='F':
                if converted_right or kinds==['S','F'] or hand.startswith('left') or 'majorana' in (kind+' '+str(reality or '').lower()):
                    item['irreps']=[['1/2','0']]
                    if 'majorana' in kind+' '+str(reality or '').lower(): item['note']='One independent left-handed Weyl field; the source Majorana/conjugacy condition is retained separately, not counted as a second multiplet.'
                elif hand.startswith('right'):
                    item['irreps']=[['1/2','0']];item['conjugateGauge']=True
                else:
                    item['status']='source_chirality_unresolved';item['irreps']=[['1/2','0']]
                    item['note']='LH basis fixed, but the source handedness is missing: the gauge assignment R versus conjugate(R) is not resolved. This row is not eligible for a complete fingerprint.'
            else:item['status']='field_type_unresolved'
            fmt=lambda rs:' ⊕ '.join('('+', '.join(r)+')' for r in rs)
            item['label']=fmt(item['irreps']) if item['irreps'] else ' or '.join(fmt(rs) for rs in item['alternatives']) or 'not extracted'
        elif d and d.isdigit() and int(d)>=5:
            n=int(d);rank=n//2;family='D' if n%2==0 else 'B'
            item['scheme']=family+str(rank)+'_Dynkin'
            zero=[0]*rank
            if component=='S': item['irreps']=[zero]
            elif component=='V': item['irreps']=[[1]+[0]*(rank-1)]
            elif component in {'F','F_D'}:
                if family=='B': item['irreps']=[[0]*(rank-1)+[1]]
                else:
                    a=[0]*(rank-2)+[1,0];b=[0]*(rank-2)+[0,1]
                    if component=='F_D':item['irreps']=[a,b]
                    else:item['status']='chirality_unresolved';item['alternatives']=[[a],[b]]
            else:item['status']='field_type_unresolved'
            fmt=lambda rs:' ⊕ '.join('['+','.join(map(str,r))+']' for r in rs)
            item['label']=fmt(item['irreps']) if item['irreps'] else ' or '.join(fmt(rs) for rs in item['alternatives']) or 'not extracted'
        else:
            item['scheme']='dimension_parameterized'
            item['label']='1' if component=='S' else 'vector' if component=='V' else 'spinor' if component in {'F','F_D'} else 'not extracted'
            item['status']='dimension_unresolved'
        result.append(item)
        if d=='4' and component=='F_D':
            result.append({**item,'conjugateGauge':True,'note':'Charge conjugate of the source RH component; every gauge representation is conjugated and every Abelian charge negated.'})
    return result
