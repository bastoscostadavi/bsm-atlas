"""Readable projections of exact core keys; full entries remain authoritative."""
from catalogue_identity import IncompleteContent
from nonabelian_core import restrict_nonabelian, algebra_key, CONVENTION
from scalar_conventions import is_scalar
from field_conventions import dimension_a, young_rows

def algebra_label(family,rank):
    if family=='A':return 'su('+str(rank+1)+')'
    if family=='B':return 'so('+str(2*rank+1)+')'
    if family=='C':return 'sp_rank('+str(rank)+')'
    if family=='D':return 'so('+str(2*rank)+')'
    return family.lower()+str(rank)

def display_rows(canonical,factors):
    rows=[]
    for source in canonical['matter']:
        l=source['lorentz'];d=l['dimension'];weights=l['irreps']
        component='S' if is_scalar(l) else 'F' if d==4 and weights==[['1/2','0']] else 'V' if d==4 and weights==[['1/2','1/2']] else 'matter'
        label='('+', '.join(weights[0])+')' if d==4 and len(weights)==1 else ' ⊕ '.join('['+','.join(map(str,w))+']' for w in weights)
        components=[]
        for a,rep in zip(factors,source['gauge']):
            w=rep['dynkin'];dimension=dimension_a(w) if a['type']=='A' else 1 if not any(w) else None
            value=str(dimension) if dimension is not None else '['+','.join(map(str,w))+']'
            if a['type']=='A' and a['rank']>1 and w<w[::-1]:value='bar('+value+')'
            components.append({'factorKey':a['key'],'factor':a['label'],'role':a['role'],
                'dynkin':w,'value':value,'dimension':dimension,'youngRows':young_rows(a,w)})
        rows.append({'copies':source['copies'],'components':components,'labels':[],
            'lorentz':{'component':component,'status':'resolved','reality':source['reality'],
                'scheme':l['scheme'],'irreps':weights,'label':label,
                'spacetime':{'dimension':str(d),'algebra':'so(1,'+str(d-1)+')'}}})
    return sorted(rows,key=lambda r:(int(r['lorentz']['spacetime']['dimension']),{'S':0,'F':1,'V':2}.get(r['lorentz']['component'],3),tuple(tuple(c['dynkin']) for c in r['components'])))

def attach_cores(entries):
    """Group primary complete regimes only; never infer a core from omissions."""
    cores={}
    for entry in entries:
        regime=next(r for v in entry['variants'] for r in v['regimes'] if r['id']==entry['primaryRegime'])
        entry['abelianRank']=sum(a['type']=='U1' for a in regime['factors']) if regime['factors'] and all(a['type'] in {'A','B','C','D','E','F','G','U1'} for a in regime['factors']) else None
        entry['coreId']=None
        if not entry['identity']['fingerprint']:
            entry['coreStatus']={'status':'unresolved','reason':'Primary complete inventory is not established; no core inferred from missing data'}
            continue
        try:
            projected=restrict_nonabelian(entry['identity']['input'])
        except IncompleteContent as error:
            entry['coreStatus']={'status':'unresolved','reason':str(error)}
            continue
        entry['coreId']=projected['id'];entry['coreStatus']={'status':'resolved','convention':CONVENTION['id']}
        core=cores.get(projected['id'])
        if core is None:
            canonical=projected['canonical']
            factors=[{'key':'core:'+str(i),'id':a['family']+str(a['rank']),
                'type':a['family'],'rank':a['rank'],'label':algebra_label(a['family'],a['rank']),
                'role':str(1+sum(b==a for b in canonical['gauge_factors'][:i])) if canonical['gauge_factors'].count(a)>1 else ''} for i,a in enumerate(canonical['gauge_factors'])]
            label=' ⊕ '.join(a['label'] for a in factors) or '0 (no non-Abelian factors)'
            core={'id':projected['id'],'algebra':label,'algebraSignature':'+'.join(sorted(a['id'] for a in factors)),'canonical':canonical,'entryIds':[],
                'paperIds':[],'abelianRanks':[],
                'regime':{'factors':factors,'baseline':None,'fields':[],
                    'coreRows':display_rows(canonical,factors)}}
            cores[core['id']]=core
        core['entryIds'].append(entry['id'])
        core['paperIds']=sorted(set(core['paperIds'])|set(entry['paperIds']))
        core['abelianRanks']=sorted(set(core['abelianRanks'])|{entry['abelianRank']})
    return sorted(cores.values(),key=lambda c:(c['algebra'],min(c['paperIds'] or ['Z']),c['id']))

def attach_algebras(entries,cores):
    """Key recorded primary algebras even when their matter remains pending.

    An empty factor list is unknown, not the zero semisimple algebra. A fixed
    purely Abelian algebra, however, does have zero semisimple part. No matter
    data or fingerprint is required to establish an algebra-only membership.
    """
    algebras={}
    core_by_id={c['id']:c for c in cores}
    for entry in entries:
        entry['semisimpleId']=None
        regime=next(r for v in entry['variants'] for r in v['regimes'] if r['id']==entry['primaryRegime'])
        recorded=regime['factors']
        try:
            if not recorded or any(a['type'] not in {'A','B','C','D','E','F','G','U1'} or type(a['rank']) is not int or a['type']=='U1' and a['rank']!=1 for a in recorded):
                raise IncompleteContent('Primary gauge algebra is parameterized or not fully established; no fixed semisimple algebra inferred')
            projected=algebra_key({'gauge_factors':[{'family':a['type'],'rank':a['rank']} for a in recorded if a['type']!='U1']})
        except IncompleteContent as error:
            entry['semisimpleStatus']={'status':'unresolved','reason':str(error)}
            continue
        entry['semisimpleId']=projected['id']
        entry['semisimpleStatus']={'status':'resolved','basis':'recorded_primary_regime','regimeId':regime['id']}
        if projected['id'] not in algebras:
            canonical=projected['canonical']
            factors=[{'key':'algebra:'+str(i),'id':a['family']+str(a['rank']),
                'type':a['family'],'rank':a['rank'],'label':algebra_label(a['family'],a['rank']),
                'role':str(1+sum(b==a for b in canonical['gauge_factors'][:i])) if canonical['gauge_factors'].count(a)>1 else ''} for i,a in enumerate(canonical['gauge_factors'])]
            algebras[projected['id']]={**projected,'algebra':' ⊕ '.join(a['label'] for a in factors) or '0 (no non-Abelian factors)',
                'algebraSignature':'+'.join(sorted(a['id'] for a in factors)),'factors':factors,
                'coreIds':[],'entryIds':[],'readyEntryIds':[],'pendingEntryIds':[],'paperIds':[],'abelianRanks':[]}
        algebra=algebras[projected['id']]
        algebra['entryIds'].append(entry['id'])
        algebra['readyEntryIds' if entry['publicationStatus']=='ready' else 'pendingEntryIds'].append(entry['id'])
        algebra['paperIds']=sorted(set(algebra['paperIds'])|set(entry['paperIds']))
        if entry['abelianRank'] is not None:algebra['abelianRanks']=sorted(set(algebra['abelianRanks'])|{entry['abelianRank']})
        if entry['coreId']:
            core=core_by_id[entry['coreId']]
            if algebra_key(core['canonical'])['id']!=projected['id']:
                raise ValueError('Complete core differs from its recorded primary semisimple algebra: '+entry['id'])
            core['semisimpleId']=projected['id']
            algebra['coreIds']=sorted(set(algebra['coreIds'])|{core['id']})
    for a in algebras.values():
        for key in ['entryIds','readyEntryIds','pendingEntryIds']:a[key].sort()
    return sorted(algebras.values(),key=lambda a:(a['algebra'],a['id']))
