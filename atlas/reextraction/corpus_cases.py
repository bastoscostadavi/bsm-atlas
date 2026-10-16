#!/usr/bin/env python3
"""Source-inspection decisions for corpus staging, never accepted database writes."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import re
from corpus import HERE, ROOT, manifest, emit
from pilot import sm_fermions, higgs, SM_FACTORS, nmssm_source

CASES={}

def claim(pid,key,section,anchor,value,basis='source_statement'):
    filename=manifest()[pid]['filename']
    pages=(HERE/'sources'/filename).with_suffix('.txt').read_text().split('\f')
    # PDF line-end hyphenation is presentation, not a distinct source claim.
    compact=lambda s: re.sub(r'\s+',' ',re.sub(r'-\s*','',s)).strip()
    found=[i+1 for i,page in enumerate(pages) if compact(anchor) in compact(page)]
    if not found:raise ValueError(f'{pid} anchor not found: {anchor}')
    return {'id':key,'basis':basis,'locator':{'section_equations':section,'pdf_pages':found,'anchor':anchor},'value':value}

BASELINE={'id':'baseline','basis':'declared_atlas_baseline','locator':{'file':'atlas/FIELD_CONTENT_CONVENTIONS.md','section':'explicit F_SM/R_SM/R_MSSM templates'},'value':'Source-explicit SM/MSSM inheritance is expanded using the declared atlas baseline: three ordinary SM chiral families, no independent RH neutrino unless stated. Exact Dynkin and all-LH conversion are conventions/derivations, not newly printed source tables. Gauge connections and dependent conjugates are not extra matter.'}

def field(label,c=[0,0],w=0,q='0',kind='S',copies=1,reality=None):
    return {'label':label,'lorentz':{'dimension':4,'scheme':'jL_jR','irreps':[['0','0']] if kind=='S' else [['1/2','1/2']] if kind=='V' else [['1/2','0'],['0','1/2']] if kind=='D' else [['0','1/2']] if kind=='R' else [['1/2','0']]},'reality':reality or ('complex' if kind in {'S','V'} else 'none'),'copies':copies,'gauge_representations':{'colour':{'dynkin':c},'weak':{'dynkin':[w]},'hypercharge':{'charge':str(q)}}}

def smplus(pid,name,extra,include_higgs=True):
    return {'schema_version':'field-content-1','inventory_complete':True,'name':name,'paper_ids':[pid],'gauge_factors':deepcopy(SM_FACTORS),'matter':sm_fermions()+([higgs()] if include_higgs else [])+extra}

def candidate(stem,spec,target,evidence):
    return {'stem':stem,'spec':spec,'target_existing_entry_id':target,'field_evidence_claim_ids':{f['label']:list(dict.fromkeys(evidence+(['baseline'] if f['label'] in {'Q','u^c','d^c','L','e^c','H'} else []))) for f in spec['matter']}}

def record(pid,claims,inspection,models=None,candidates=None,status='partial_scoped_reextraction_staged',reason=None):
    CASES[pid]={'status':status,'inspection':{'scope':inspection,'whole_paper_scientifically_read':False},'claims':[deepcopy(BASELINE),*claims],'source_descriptions':models or [],'candidates':candidates or [],'limitations':reason or [],'value_status_policy':{'not_extracted':'unfinished work, never source omission','not_specified_by_source':'only within identified inspected source scope','symbolic_family':'explicit source parameter, not unknown'},'reconciliation_policy':'Reuse/correct the known source-linked existing entry after review; no unmatched fingerprint is a novelty claim.'}

# P06: distinguish 4D composite coordinates from actual 5D matter.
record('P06',[
 claim('P06','regimes','Sections 2,3; Eqs.(4),(8),(27)-(29)','The 5D spacetime metric','4D strong sector global SU(3)c x SO(5) x U(1)B-L; only SM subgroup gauged externally. 5D bulk gauges SU(3)c x SO(5) x U(1)B-L with different UV/IR boundary subalgebras. Do not union their spectra.'),
 claim('P06','sources','Section 2 after Eq.(8)','non-dynamical external','The added components completing spinorial SO(5) source multiplets are explicitly non-dynamical; they are not additional independent matter.'),
 claim('P06','bulk','Section 3 Eq.(28)','For each quark family','Three bulk Dirac spinors xi_q,xi_u,xi_d per quark family in spinorial 4_(1/3), plus leptons realized similarly and an IR-brane Q_R removing unwanted modes. Bulk spinor is Lorentz B2 [0,1], not a 4D Weyl. Gauge so(5)=C2 canonical alias: spinor 4 is C2 [1,0]; ordinary colour fundamental inherited.'),
 claim('P06','deformation','Appendix B Eqs.(60)-(64)','traceless symmetric','The scalar deformation has SO(5) traceless symmetric 14_0, decomposing 9+4+1 under SO(4); auxiliary external sources need not be dynamical. The 5D implementation adds an actual bulk scalar 14_0. C2 weight [0,2] is a mathematical conversion.')],
 'Sections 2 and 3 definitions; Appendix B scalar deformation. Composite, bulk and boundary descriptions remain separate.',
 models=[{'target_entry_id':'mchm-spinorial','regime':'4D CFT / 5D bulk and branes','status':'partial','reason':'4D microscopic strong-sector elementary matter not specified; full lepton/brane assignments and scalar reality of 5D deformation not fully enumerated in this extraction. Do not promote source-completion coordinates or all KK modes to new elementary rows.','value_status':'not_extracted_for_remaining_boundary_slots','fields':[{'label':'xi_q,xi_u,xi_d','lorentz':{'dimension':5,'scheme':'B2_Dynkin','irreps':[[0,1]]},'gauge_irrep':{'C2':[1,0]},'source_B-L':'1/3','copies':'one each per quark family','evidence':['bulk']}]},
         {'target_entry_id':'mchm-spinorial-scalar14','status':'partial','fields':[{'label':'bulk Phi','gauge_irrep':{'C2':[0,2]},'source_B-L':'0','evidence':['deformation']}],'reason':'Source auxiliary 4D deformation and actual 5D scalar must not be conflated; full cross-regime inventory is not a single numerical schema payload.'}])

gm=smplus('P07','Georgi-Machacek matter',[field('xi',w=2,q='0',reality='real'),field('chi',w=2,q='1')])
record('P07',[claim('P07','scalars','Section II Eqs.(1)-(4), footnote 1','a real triplet','Usual complex Higgs doublet source Y=1, one real weak triplet xi with Y=0 and one complex triplet chi with Y=2; Q=T3+Y/2. In textbook Y coordinates xi=0,chi=1; full SM normalization gives q=6 for chi. Custodial multiplets are not additional gauge factors/fields.')],
 'Section II complete gauge-basis scalar definition and adjacent custodial decomposition.',candidates=[candidate('gm',gm,'georgi-machacek-general',['scalars','baseline'])],status='completed_scoped_reextraction_staged')

record('P08',[claim('P08','doublets','Section 2.1 Eq.(1)','N complex Higgs doublets','Scalar-only NHDM definition: N complex electroweak doublets with Y=1/2; N=3 here. Source explicitly focuses only on the scalar sector, so no complete Yukawa/fermion completion is fixed.'),claim('P08','D6','Section 6.2 Eqs.(22)-(26)','Constructing D6','D6=S3 example uses diag(omega,omega^2,1), swaps first two doublets with a phase, and restricts the scalar potential. It has the same three gauge doublets as the D8 example.'),claim('P08','D8','Section 6.3 Eqs.(31)-(33)','Constructing D8','D8 example uses diag(i,-i,1) with the same doublet inventory. Discrete family action is not another gauge algebra.')],
 'Scalar-only definition and explicit D6 and D8 constructions; no claim to a specified complete fermion sector.',models=[{'target_entry_id':'three-higgs-doublets','status':'partial','value_status':'not_specified_by_source_in_scalar_only_scope','fields':[{'label':'phi_a','copies':3,'lorentz':'(0,0)','reality':'complex','gauge_irrep':{'A1':[1]},'source_Y':'1/2','evidence':['doublets']}],'missing':['fermion/Yukawa completion not specified in classification scope'],'source_variants':['D6','D8']}])

octet=smplus('P09','SM with MFV colour-octet weak doublet',[field('S',c=[1,1],w=1,q='1/2')])
record('P09',[claim('P09','octet','Section III Eqs.(5)-(6),(12)','S A0','One complex colour-octet SU(2) doublet (8,2)_(1/2) added to the minimal SM. Neutral complex component is decomposed into real and imaginary parts, not independent additional multiplets.'),claim('P09','triplets','Introduction and Section VIII Eq.(42)','nT real (1, 3)0','Optional unification completion adds three real colour-singlet weak triplets of zero hypercharge. Source Section VIII calls the octet (8,1)_(1/2), conflicting with the main defined (8,2); conclusion also prints (1,2)_0 for the triplets. Preserve apparent source typographical conflicts instead of silently certifying them.')],
 'Main scalar definition and optional Section VIII triplet extension; source notation conflicts explicitly retained.',candidates=[candidate('octet',octet,'sm-octet-doublet-mfv',['octet','baseline'])],models=[{'target_entry_id':'sm-octet-doublet-mfv-triplets','status':'partial','value_status':'ambiguous_conflicting_source_labels','fields':[{'label':'T_j','copies':3,'lorentz':'(0,0)','reality':'real','gauge_irrep':{'A2':[0,0],'A1':[2]},'source_Y':'0','evidence':['triplets']}],'reason':'Optional extension main octet label inconsistent in Section VIII; retain source conflict for curator review.'}])

vlqs=[]
for stem,label,w,q in [('t-singlet','T',0,'2/3'),('b-singlet','B',0,'-1/3'),('xt-doublet','XT',1,'7/6'),('tb-doublet','TB',1,'1/6'),('by-doublet','BY',1,'-5/6'),('xtb-triplet','XTB',2,'2/3'),('tby-triplet','TBY',2,'-1/3')]:
    vlqs.append(candidate(stem,smplus('P10','SM plus one vector-like '+label,[field(label,c=[1,0],w=w,q=q,kind='D')]),'vlq-'+stem,['vlq','baseline']))
record('P10',[claim('P10','vlq','Introduction; Section 2 Eq.(1) and paragraphs below','only one extra multiplet','Seven alternative colour-triplet vector-like quark multiplets, one at a time: T,B singlets; XT,TB,BY doublets; XTB,TBY triplets. Component charges X=5/3,T=2/3,B=-1/3,Y=-4/3 fix Y=Q-T3, yielding 2/3,-1/3,7/6,1/6,-5/6,2/3,-1/3 respectively. Each source Dirac multiplet expands to LH R plus LH conjugate R; do not count dimensions as copies.')],
 'Introduction colour/vector-like definition; full seven-multiplet list and electric charges in Section 2.',candidates=vlqs,status='completed_scoped_reextraction_staged')

lqs=[candidate('r2',smplus('P11','SM plus scalar R2',[field('R2',c=[1,0],w=1,q='7/6')]),'lq-r2-general',['taxonomy','r2','baseline'])]
rt=smplus('P11','SM plus Rtilde2 and three RH neutrinos',[field('Rtilde2',c=[1,0],w=1,q='1/6'),field('nu_R',kind='R',copies=3)])
lqs.append(candidate('rtilde2-nur',rt,'lq-rtilde2-nur',['taxonomy','rtilde','baseline']))
record('P11',[claim('P11','taxonomy','Section 1.1, Table 1','List of scalar and vector LQs','Exact SM representations are tabulated, with scalar/vector spin and conjugation conventions; a vector LQ tuple is not itself a complete UV gauge theory.'),claim('P11','r2','Section 1.3 Eqs.(3)-(4)','Yukawa couplings of R2','R2 is a scalar (3,2,7/6) coupling to SM fermions; one complex multiplet in the displayed single-LQ description.'),claim('P11','rtilde','Section 1.4 Eq.(5)','three right-chiral neutrinos','Rtilde2 is scalar (3,2,1/6); source explicitly assumes three nu_R. Convert these singlet RH Weyl fields to LH conjugates.' )],
 'Representation taxonomy and scalar R2/Rtilde2 model definitions. Vector/UV-completion examples require additional source-specific completion work.',candidates=lqs,
 models=[{'target_entry_ids':['lq-u1-effective','lq-u3-effective','lq-utilde1-effective','lq-ubar1-nur-effective'],'status':'partial','value_status':'not_extracted','reason':'Vector-current taxonomy read, but each full gauge completion and additional matter not re-established; do not declare complete gauge theories from vector tuples.'},{'target_entry_ids':['su5-georgi-glashow-review','su5-gg-scalar15','su5-gg-extra5-two10'],'status':'partial','value_status':'not_extracted','reason':'SU(5) completion subscopes remain to be re-read and fully component/irrep resolved, not source omissions.'}])

mdm=[candidate('quintuplet',smplus('P12','SM plus Majorana quintuplet',[field('X5',w=4,kind='F')]),'mdm-majorana-quintuplet',['mdm','baseline']),candidate('septuplet',smplus('P12','SM plus real scalar septuplet',[field('X7',w=6,reality='real')]),'mdm-real-septuplet-displayed',['mdm','baseline'])]
record('P12',[claim('P12','mdm','Section 2 Eq.(1), Table 1','c = 1/2','Source adds a single minimal non-chiral colour-singlet scalar/fermion multiplet to SM; c=1/2 for real scalar or Majorana, c=1 for complex/Dirac. Table 1 gives Y=0 fermion quintuplet and scalar septuplet. Thus LH Weyl [4] with one copy and real scalar [6] with one copy; all SM charges included in primitive normalization.')],
 'Section 2 definition, Table 1 and adjacent stability discussion; quintuplet/septuplet representatives only.',candidates=mdm,status='completed_scoped_reextraction_staged')

record('P13',[claim('P13','ybl','Section III.A Eq.(45), Table I','QY BL = aY','Extra generator Q_YBL=aY+b(B-L)/2, b nonzero, is an explicit symbolic family. Source Table I is left-chiral including conjugate RH fermions. Do not normalize a numerical subset of a symbolic full assignment.'),claim('P13','e6','Section III.A.3 Eq.(47), Table II','full 27-plets','E6-inspired charges use Q(theta)=cos(theta)Qchi+sin(theta)Qpsi. Psi requires three full 27-plets; chi may omit non-chiral 10+1. Nonsupersymmetric and supersymmetric interpretations differ and Higgs/extra-singlet completion is not uniquely fixed by a charge table.')],
 'Generator families, left-chiral charge Table I, E6 Table II discussion; model-dependent Higgs completion not synthesized.',models=[{'target_entry_ids':['u1-ybl-charge-family','e6-full27-charge-template','u1-chi-minimal16-charge','umssm-single-s-higgs-sector'],'status':'partial','value_status':'explicit_symbolic_family_or_scoped_charge_template','parameters':[{'id':'z','domain':'source free real/rational charge coordinate','definition':'Q=b(zY+(B-L)/2)'},{'id':'theta_E6','domain':'0 <= theta < pi','definition':'Q=cos(theta)Qchi+sin(theta)Qpsi'}],'reason':'Full numerical Higgs/exotic spectrum not uniquely supplied by these charge templates; source-specific completion still requires extraction.'}])

bl=smplus('P14','Minimal gauged B-L',[field('nu_R',kind='R',copies=3),field('chi',q='0')])
bl['gauge_factors'].append({'id':'bl','family':'U1','rank':1})
for f in bl['matter']:
    q={'Q':'1/3','u^c':'-1/3','d^c':'-1/3','L':'-1','e^c':'1','H':'0','nu_R':'-1','chi':'2'}[f['label']]
    f['gauge_representations']['bl']={'charge':q}
record('P14',[claim('P14','bl','Section II.A Eqs.(1),(5)-(9), Tables I-II','Fermion content and charges','Source explicitly gives SU(3)c x SU(2)L x U(1)Y x U(1)B-L, three generations including nu_R, complex H=(1,2,1/2,0) and complex chi=(1,1,0,2). Tables I-II give all source charges. All-LH conjugation flips each RH U1 and colour. Joint primitive scales are 6 for Y and 3 for B-L; chi has atlas B-L charge 6.')],
 'Section II.A complete tables and Lagrangian definition; no kinetic mixing (“pure” model) is an interaction assumption, not extra matter.',candidates=[candidate('bl',bl,'minimal-bl-pure',['bl'])],status='completed_scoped_reextraction_staged')

record('P15',[claim('P15','scope','Introduction and Section 2 anomaly-domain definition','agnostic about the heavy gauge boson','Classification fixes chiral fermion charges for SM or SM plus up to three RH neutrinos, not a unique full Higgs/breaking completion.'),claim('P15','examples','Section 4.3 Eq.(4.2), Table 5 solution 14','only solution 14','Eq.(4.2): Q=(0,-3,3), e_R=(0,-3,3),u_R=(0,-1,1),L=(0,-4,4),d_R=(0,0,0). Source then chooses Higgs F=+2 for a top-only Yukawa example. Table 5 solution 14 gives Q=(-1,-1,2),nu_R=(-3,-1,4),e_R=(-1,0,1),u_R=d_R=0,L=(-2,0,2); columns are sorted charge sets, NOT a fixed family alignment.'),claim('P15','yukawa','Section 5 Eqs.(5.1)-(5.10)','FH =','All-SM-Yukawa compatible family is parameterized and RH-neutrino charges can remain family non-universal; further neutrino-mass model building is explicitly assumed. Do not turn charge solutions into fully specified BSM matter entries.')],
 'Fermion-domain definition, explicit Eq.(4.2)/Table 5 solution 14 and Section 5 family conditions; Higgs/breaking completion stays partial.',models=[{'target_entry_ids':['u1-smnur-all-sm-yukawas','u1-sm-top-only-charge','u1-leptonic-opposite-nur','u1-sm-left23-charge','u1-smnur-table5-14','u1-ybl-charge-family'],'status':'partial','value_status':'source_scoped_fermion_assignment_plus_unfinished_scalar_completion','reason':'Numeric examples and symbolic families preserved without inventing breaking scalars or family alignments. Remaining individual legacy charge-example checks are unfinished extraction, not paper omissions.'}])

def save():
    path=HERE/'corpus-decisions.json'
    existing=json.loads(path.read_text()) if path.exists() else {}
    existing.update(CASES)
    emit(path,existing)

if __name__=='__main__':save()
