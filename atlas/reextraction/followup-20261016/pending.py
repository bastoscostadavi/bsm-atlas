"""Reuse actual frozen source checks, with newly explicit legacy-field maps.

No claim of a second independent whole-paper read; named passages were checked
in the corpus run and are referenced without changing those frozen artifacts.
"""
from stage import *

# Exact old field IDs, not fuzzy name matching. Missing IDs on inherited template
# rows mean no legacy field row exists: their provenance is the declared baseline.
MAPS={
 ('P07','gm'):{'H':[57],'xi':[58],'chi':[59],'Q':[62],'u^c':[62],'d^c':[62],'L':[62],'e^c':[62]},
 ('P09','octet'):{'S':[65],'H':[66],'Q':[67],'u^c':[68],'d^c':[69]},
 ('P11','r2'):{'R2':[90],'u^c':[91],'L':[92],'e^c':[93],'Q':[94],'H':[95]},
 ('P11','rtilde2-nur'):{'Rtilde2':[96],'d^c':[97],'L':[98],'Q':[99],'nu_R':[100],'H':[101]},
 ('P12','quintuplet'):{'X5':[130]},('P12','septuplet'):{'X7':[131],'H':[132]},
 ('P16','331'):{'lepton triplets':[193],'Q1_L':[194],'Q23_L':[195],'u_R':[196],'d_R':[197],'J1_R':[198],'J23_R':[199],'eta':[200],'rho':[201],'chi':[202]},
 ('P16','331-extra'):{'lepton triplets':[193],'Q1_L':[194],'Q23_L':[195],'u_R':[196],'d_R':[197],'J1_R':[198],'J23_R':[199],'eta':[200,207],'rho':[201],'chi':[202],'sigma,omega':[205,206]},
 ('P17','421-dirac'):{'FQL':[208],'Fu':[209],'Fd':[210],'chi':[211],'H':[212],'Phi':[213]},
 ('P17','421-inverse'):{'FQL':[208],'Fu':[209,221],'Fd':[210],'chi':[211,222],'H':[212],'Phi':[213],'N':[220]},
 ('P20','trinification-adjoint'):{'QL':[235],'QR':[236],'L':[237],'H':[238],'8L':[239]},
 ('P20','trinification-N'):{'QL':[235],'QR':[236],'L':[237,241],'H':[238,242],'N':[240]},
 ('P22','rpv-singlets'):{'H_u':[264],'higgsino H_u':[264],'H_d':[265],'higgsino H_d':[265],'L':[266],'scalar L':[266],'Nc scalar':[267],'Nc Weyl':[267],'S scalar':[268],'S Weyl':[268],'Phi scalar':[269],'Phi Weyl':[269]},
 ('P23','split'):{'H':[272],'higgsino_u':[273],'higgsino_d':[274],'gluino':[275],'wino':[276],'bino':[277],'Q':[278],'u^c':[279],'d^c':[280],'L':[281],'e^c':[282]},
 ('P26','ksvz'):{'Q_KSVZ':[311,312],'Phi':[313]},
 ('P26','dfsz'):{'Hu':[317,325],'Hd':[318],'Phi':[319],'Q':[320],'u^c':[321],'d^c':[322],'L':[323,326],'e^c':[324,327]},
 ('P31','flavour-su3'):{'QL':[388],'UR':[389],'DR':[390],'PsiuR':[391],'PsidR':[392],'Psiu':[393],'Psid':[394],'Yu':[395],'Yd':[396],'H':[397]},
 ('P31','flavour-u3'):{'QL':[388],'UR':[389],'DR':[390],'PsiuR':[391],'PsidR':[392],'Psiu':[393],'Psid':[394],'Yu':[395],'Yd':[396],'H':[397]},
 ('P32','numsm'):{'N_R':[401]},
 ('P33','ma'):{'N':[402],'eta':[403],'H':[404],'L':[405],'e^c':[406]},
 ('P35','hypercolour'):{'psi_plus':[421],'psi_minus':[421],'psi_zero':[421],'chi':[422],'chitilde':[423]},
 ('P37','twin-linear'):{'ordinary H':[450],'twin H':[450]},
 ('P38','fraternal'):{'H':[460],'B':[461],'Qhat':[462],'that_R':[463],'bhat_R':[464],'Lhat':[465],'tauhat_R':[466]},
 ('P41','ued-5d'):{'Q':[489],'U':[490],'D':[491],'L':[492],'E':[493],'H':[494]},
 ('P43','valley-benchmark'):{'U':[510],'Ubar':[511],'C':[512],'Cbar':[513],'N^c':[514],'phi':[515],'H':[516],'Q':[517],'u^c':[517],'e^c':[517],'d^c':[518],'L':[518]},
 ('P44','secluded-u1'):{'psi':[524],'phi':[525]},
 ('P44','secluded-scalar'):{'psi':[528],'phi':[529],'H':[530]},
 ('P46','abelian-higgs'):{'S':[554],'H':[555]},
 ('P46','vector-eft'):{'X':[542],'H':[543]},
 ('P50','zeta'):{'zeta':[567],'Q':[568],'L':[569]}
}

MSSM={'scalar Q':[245,258],'Q':[245,258],'scalar u^c':[247,259],'u^c':[247,259],'scalar d^c':[248,260],'d^c':[248,260],'scalar L':[246,261],'L':[246,261],'scalar e^c':[249,262],'e^c':[249,262],'H_u':[243,256],'higgsino H_u':[243,256],'H_d':[244,257],'higgsino H_d':[244,257],'gluino':[250,263],'wino':[250,263],'bino':[250,263]}
MAPS[('P21','mssm')]=MSSM

def main():
    frozen_unchanged()
    decisions=load(HISTORICAL/'corpus-decisions.json')
    # Current public readiness is only used to avoid redoing accepted old entries.
    public={e['id']:e for e in load(ROOT/'website/field-catalogue.json')['entries']}
    with __import__('sqlite3').connect((ROOT/'atlas/atlas.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=__import__('sqlite3').Row
        oldfields={r['field_id']:dict(r) for r in db.execute('select field_id,model_id,regime_id,field_label from theory_fields')}
    for pid in sorted(decisions):
        checkpoint=load(HISTORICAL/pid/'checkpoint.json')
        for c in decisions[pid]['candidates']:
            stem=c['stem'];entry=c['target_existing_entry_id'];key=(pid,stem)
            if public[entry]['identity']['status']!='unresolved' or key not in MAPS:continue
            raw=deepcopy(c['spec'])
            if key==('P26','ksvz'):
                for f in raw['matter']:
                    if f['label']=='Q' and len(f['lorentz']['irreps'])==2:f['label']='Q_KSVZ'
            if key==('P21','mssm'):raw['paper_ids']=['P21','P22']
            mappings=[]
            for f in raw['matter']:
                label=f['label'];ids=MAPS[key].get(label,[])
                if key==('P22','rpv-singlets') and not ids:ids=MSSM.get(label,[])
                refs=c['field_evidence_claim_ids'].get(label,c['field_evidence_claim_ids'].get('Q',[]))
                m=mapping(label,ids,refs,basis='explicit_legacy_container_to_source_component_map' if ids else 'declared_source_inherited_baseline_no_separate_legacy_field_row')
                m['legacy_fields']=[oldfields[i] for i in ids]
                if not ids:m['baseline_provenance']='Frozen source check baseline claim plus source inheritance statement; absence of an old row is not a scientific unknown.'
                if key==('P31','flavour-su3'):m['cross_variant_scope']='Same P31 field table, but SU3-only gauging of Section5.2; source IDs come from the older U3 projection and do not imply U1 factors are kept.'
                if key==('P35','hypercolour') and not ids:m['baseline_provenance']='External ordinary SM fermions explicitly inherited in the microscopic HC EFT; no elementary Higgs is appended. No old microscopic baseline field ID exists.'
                mappings.append(m)
            ev={'source_review_reused_from_frozen_checkpoint':str((HISTORICAL/pid/'checkpoint.json').relative_to(ROOT)),'frozen_checkpoint_sha256':sha256((HISTORICAL/pid/'checkpoint.json').read_bytes()).hexdigest(),'source':checkpoint['source'],'inspection':checkpoint['inspection'],'claims':checkpoint['claims'],'review_scope_note':'Source definitions actually checked in earlier pass are reused; not represented as a fresh independent review or whole-paper reread. This additive follow-up supplies exact legacy container IDs and current real-module normalization.'}
            limits=deepcopy(checkpoint.get('limitations',[]))
            if key==('P37','twin-linear'):limits.append('This full linear unextended twin completion uses the explicit two-SM-copy construction; it is not the nonlinear or extended-top model, and old field450 is only its scalar container.')
            if key==('P41','ued-5d'):limits.append('Fixed5D specialization explicitly defined by source; genericdelta/evenD anomaly completions remain a separate family. Do not overwrite all dimensional regimes with5D.')
            if key==('P43','valley-benchmark'):limits.append('Only explicit nv3,k0,qplus=-2 benchmark is numerical here. Genericcharge/rank family is not collapsed into this member. Table N is interpreted in common left-chiral coordinates, with source prose right-handed-species naming retained.')
            if key==('P26','dfsz'):limits.append('DFSZ-I/II are one real-module field-content class; source Hu negative hypercharge reorients as a scalar conjugate under current convention, not a fermion conjugation.')
            stage(entry,pid,checkpoint['arxiv_version'],raw,ev,mappings,limitations=limits,regime={'source_regime_ids':sorted({oldfields[i]['regime_id'] for m in mappings for i in m['source_field_ids']}),'frozen_candidate_stem':stem,'description':'Exactly the source-scoped frozen candidate, not union of all source regimes.'})
    frozen_unchanged()

if __name__=='__main__':main()
