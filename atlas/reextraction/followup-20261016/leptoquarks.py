from stage import *

def main():
    frozen_unchanged()
    base=load(HISTORICAL/'P11/r2-source-candidate.json')
    base['matter']=[f for f in base['matter'] if f['label']!='R2']
    common=load(HISTORICAL/'P11/checkpoint.json')
    claims=deepcopy(common['claims'])+[
      {'id':'vectors','basis':'source_statement','locator':'P11 Sections1.8,1.11-1.13 Eqs11-12,17-20; Table1 pp6-7; vector mass/UV caveat Section3.3 PDF/printedp50','fact':'Single-vector descriptions U3=(3,3,2/3),Utilde1=(3,1,5/3),U1=(3,1,2/3),Ubar1=(3,1,-1/3). These are complex Lorentz vectors, not scalar reps. Source explicitly discusses SM plus a massive vector with explicit mass as a nonrenormalizable EFT, with extended gauge completion needed only for a renormalizable UV model. Thus fixed GSM+vector EFT inventory can be complete at its stated scope without inventing an enlarged gauge algebra.'},
      {'id':'optional-nur','basis':'source_statement_and_declared_source_option','locator':'P11 Section1.1 optional neutrino paragraph pp5-6; Section1.4 p10 three-neutrino choice; Section1.7 p11; Section1.12 Eq18 and1.13 Eq20 p13','fact':'RH-neutrinos are explicitly optional additions. The selected U1 entry here omits the barred neutrino coupling/sector and contains ordinary SM fields only, matching its previously recorded unbarred LL/RR current scope. Ubar1 requires neutrinos; use the explicitly adopted three-right-chiral-neutrino option, normalized to three LH singlets. Optional U1+three-neutrinos is a different matter variant, not silently unioned.'}
    ]
    cases=[('lq-u3-effective','U3',2,'2/3',102,{'Q':[103],'L':[104],'H':[105]},31,False),('lq-utilde1-effective','Utilde1',0,'5/3',106,{'u^c':[107],'e^c':[108],'H':[109]},32,False),('lq-u1-effective','U1',0,'2/3',110,{'Q':[111],'L':[112],'d^c':[113],'e^c':[114],'H':[115]},33,False),('lq-ubar1-nur-effective','Ubar1',0,'-1/3',116,{'d^c':[117],'nu_R':[118],'H':[119]},34,True)]
    for entry,label,w,y,identifier,ids,reg,nur in cases:
        raw=deepcopy(base);raw['name']='SM plus '+label+' vector EFT';raw['matter'].append({'label':label,'lorentz':{'dimension':4,'scheme':'jL_jR','irreps':[['1/2','1/2']]},'reality':'complex','copies':1,'gauge_representations':{'colour':{'dynkin':[1,0]},'weak':{'dynkin':[w]},'hypercharge':{'charge':y}}})
        if nur:
            raw['matter'].append({'label':'nu_R','lorentz':{'dimension':4,'scheme':'jL_jR','irreps':[['0','1/2']]},'reality':'none','copies':3,'gauge_representations':{'colour':{'dynkin':[0,0]},'weak':{'dynkin':[0]},'hypercharge':{'charge':'0'}}})
        ids[label]=[identifier]
        maps=[mapping(f['label'],ids.get(f['label'],[]),['vectors','optional-nur','baseline'],basis='direct_source_field_or_declared_SM_baseline',model=entry,regime=reg) for f in raw['matter']]
        stage(entry,'P11','1603.04993v3',raw,{'source':common['source'],'inspection':{'scope':'Actual Table1/Sections1.1,1.4,1.7,1.8,1.11-1.13 and Section3.3 vector-EFT caveat read. Not whole review.'},'claims':claims,'scope_resolution':'Earlier audit unnecessarily left the vector EFT inventories pending for lack of a UV completion. The source itself distinguishes the finite SM-plus-vector EFT from its renormalizable UV completion; this follow-up completes only the former.'},maps,limitations=['Source-scoped massive-vector EFT, not an identified complete extended-gauge UV model. No anomaly or viability intake gate.',*(['Selected source option excludes optional RH-neutrino sector.'] if label=='U1' else [])],regime={'source_regime_id':reg,'description':'Single complex vector matter multiplet under GSM; connections of unknown UV symmetry not added.'})
    frozen_unchanged()

if __name__=='__main__':main()
