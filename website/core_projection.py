"""Four derived views of the same complete gauge–matter catalogue."""
from copy import deepcopy
from nonabelian_core import restrict_nonabelian, algebra_key, full_algebra_key
from presentation import matrix, algebra_label

def group_factors(canonical):
    return [{'key':'factor:'+str(i),'id':'u1' if a['family']=='U1' else a['family']+str(a['rank']),
        'type':a['family'],'rank':a['rank'],'label':algebra_label(a['family'],a['rank']),
        'role':str(1+sum(b==a for b in canonical['gauge_factors'][:i])) if canonical['gauge_factors'].count(a)>1 else ''}
        for i,a in enumerate(canonical['gauge_factors'])]

def label(factors):
    return ' ⊕ '.join(a['label'] for a in factors) or '0 (no non-Abelian factors)'

def attach_layers(entries):
    cores,algebras,full={},{},{}
    for entry in entries:
        spec=entry['specification']
        core=restrict_nonabelian(spec)
        algebra=algebra_key({'gauge_factors':[a for a in spec['gauge_factors'] if a['family']!='U1']})
        whole=full_algebra_key(spec)
        entry.update(coreId=core['id'],semisimpleId=algebra['id'],fullAlgebraId=whole['id'],abelianRank=whole['abelianRank'])
        if core['id'] not in cores:
            c=core['canonical']; fs=group_factors(c)
            # Restriction has no U(1); temporarily add a trivial spectator for a
            # zero semisimple algebra only while deriving the readable rows.
            s={'schema_version':'field-content-2','inventory_complete':True,
                'gauge_factors':[{'id':a['key'],'family':a['type'],'rank':a['rank']} for a in fs],
                'matter':[{**{k:deepcopy(f[k]) for k in ['lorentz','reality','copies']},
                    'gauge_representations':{a['key']:rep for a,rep in zip(fs,f['gauge'])}} for f in c['matter']]}
            regime=matrix(s); regime['coreRows']=regime.pop('rows')
            cores[core['id']]={'id':core['id'],'canonical':c,'algebra':label(fs),
                'semisimpleId':algebra['id'],'entryIds':[],'paperIds':[],'abelianRanks':[],
                'fullAlgebraIds':[],'regime':regime}
        if algebra['id'] not in algebras:
            fs=group_factors(algebra['canonical'])
            algebras[algebra['id']]={**algebra,'algebra':label(fs),
                'algebraSignature':'+'.join(sorted(a['id'] for a in fs)),
                'factors':fs,'entryIds':[],'paperIds':[],'coreIds':[],'fullAlgebraIds':[]}
        if whole['id'] not in full:
            fs=group_factors(whole['canonical'])
            full[whole['id']]={**whole,'algebra':label(fs),'factors':fs,
                'entryIds':[],'paperIds':[],'coreIds':[]}
        for group in [cores[core['id']],algebras[algebra['id']],full[whole['id']]]:
            group['entryIds'].append(entry['id'])
            group['paperIds']=sorted(set(group['paperIds'])|set(entry['paperIds']))
            if 'coreIds' in group:group['coreIds']=sorted(set(group['coreIds'])|{core['id']})
            if 'fullAlgebraIds' in group:group['fullAlgebraIds']=sorted(set(group['fullAlgebraIds'])|{whole['id']})
        cores[core['id']]['abelianRanks']=sorted(set(cores[core['id']]['abelianRanks'])|{whole['abelianRank']})
    for groups in [cores,algebras,full]:
        for group in groups.values():group['entryIds'].sort()
    return tuple(sorted(groups.values(),key=lambda g:(g['algebra'],g['id'])) for groups in [cores,algebras,full])
