from stage import *

def main():
    frozen_unchanged()
    raw=load(HISTORICAL/'P09/octet-source-candidate.json')
    raw['name']='SM octet doublet plus three real weak triplets'
    triplet=deepcopy(next(f for f in raw['matter'] if f['label']=='S'))
    triplet.update(label='T_j',copies=3,reality='real')
    triplet['gauge_representations']={'colour':{'dynkin':[0,0]},'weak':{'dynkin':[2]},'hypercharge':{'charge':'0'}}
    raw['matter'].append(triplet)
    c=load(HISTORICAL/'P09/checkpoint.json')
    claims=deepcopy(c['claims'])+[{'id':'indexed-potential','basis':'explicit_source_indexed_Lagrangian_resolves_prose_typographical_conflicts','locator':'P09 SectionVIII Eq42 PDF/printedp7, paragraph immediately following; SectionIII scalar definition Eqs5-6','fact':'Eq42 contains(S_A^dagger sigma^a S_A)T_j^a and(H^dagger sigma^a H)T_j^a,epsilon_abc T_i^a T_j^b T_k^c; a is weak-adjoint index and j=1..3 labels triplets. Source explicitly says SU2 indices on H and S are suppressed. Thus S is the original weak DOUBLEt, and T consists of THREE real weak TRIPLET copies, colour-singletY0. The SectionVIII(8,1) label and conclusion(1,2) label conflict with these explicit tensors, not with each other as viable alternatives: Pauli-matrix bilinears and epsilon_abc fix the displayed construction. Preserve these source misprints in evidence instead of treating a bare dimension as authoritative or pretending they never occurred.'}]
    ids={'Q':[67],'u^c':[68],'d^c':[69],'H':[71],'S':[72],'T_j':[70]}
    maps=[mapping(f['label'],ids.get(f['label'],[]),['octet','triplets','indexed-potential','baseline'],basis='explicit_source_field_or_inherited_SM_baseline',model='sm-octet-doublet-mfv-triplets',regime=21) for f in raw['matter']]
    stage('sm-octet-doublet-mfv-triplets','P09','hep-ph/0606172v3',raw,{'source':c['source'],'inspection':{'scope':'SectionVIII full indexed potential, adjoining triplet/count statements, and comparison with SectionIII re-read; source notation conflicts resolved explicitly by the displayed invariant.'},'claims':claims,'source_notation_conflict_retained':['SectionVIII prose prints(8,1)1/2, but Eq42 explicitly uses weak Pauli matrices onS.','Conclusion prints real(1,2)0, but SectionVIII explicitly real(1,3)0 and indexedadjointT^a.']},maps,limitations=['This is an indexed-Lagrangian-based editorial correction of source misprints, explicitly disclosed for curator review; it is not a literal agreement of all source prose labels.'],regime={'source_regime_id':21,'description':'GSM EFT with original octet weak doublet and three real weak triplets, not a separately reconstructed SU5 completion.'})
    frozen_unchanged()

if __name__=='__main__':main()
