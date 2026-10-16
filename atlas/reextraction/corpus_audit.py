"""Follow-up targeted source checks and field-claim audit; no accepted writes."""
from corpus_batch5 import *

CASES['P11']['claims'].append(claim('P11','su5-definitions','Section2.1 pp19-22, Table2 and explicit scalar contractions','one 5-dimensional and two 10-dimensional','SU5 GG: three LH10+bar5 families, scalar5+24; light-LQ completion adds one extra5 and two scalar10. Alternative adds one scalar15. Upper-index10 is [0,1,0,0], upper symmetric15 is [2,0,0,0], fundamental5 [1,0,0,0],bar5 [0,0,0,1],adj24 [1,0,0,1]. Source15 decomposes (1,3,1)+(6,1,-2/3)+(3,2,1/6); do not count its components again under a separate GSM factor.',basis='source_statement_and_tensor_highest_weight_conversion'))
for item in CASES['P11']['source_descriptions']:
    if 'su5-georgi-glashow-review' in item.get('target_entry_ids',[]):
        item.update({'value_status':'source_scoped_GUT_inventory_with_unestablished_scalar_reality','fields':[{'label':'LH fermion10+bar5','copies':3,'evidence':['su5-definitions']},{'label':'GG scalar5+24','copies':'one each','evidence':['su5-definitions']},{'label':'extra scalar5 and two10','copies':{'5':1,'10':2},'evidence':['su5-definitions']},{'label':'alternative extra scalar15','copies':1,'evidence':['su5-definitions']}],'reason':'Targeted review definition now inspected; scalar24 real-versus-complex condition not established in the displayed review definition. Do not infer field reality solely from real-type adjoint irrep.'})
CASES['P11']['inspection']['scope']+=' Targeted SU5 GG, extra5/two10 and15 completion definitions re-read; source tensor orientations converted explicitly.'

CASES['P13']['claims'].append(claim('P13','singleS','SectionIV.B.2 Eqs.(54)-(55)','with a single S','Single-S UMSSM Higgs sector contains complex Hu,Hd,S and their chiral superpartners, with source free charges Qu,Qd,QS satisfying QS nonzero,QS+Qu+Qd=0, superpotential lambdaS S Hu Hd. This sector alone does not supply unique exotic/anomaly completion or full numerical fermion charges. Do not identify it with ungauged-U1 NMSSM simply because scalar names agree.'))
CASES['P13']['inspection']['scope']+=' Single-S UMSSM SectionIV.B.2 Higgs potential and source charge constraint inspected.'
CASES['P13']['source_descriptions'][0]['reason']='Charge templates and single-S Higgs-sector definitions inspected. Numerical full Higgs/exotic/fermion completion is not selected by these symbolic source families; no automatic NMSSM equivalence.'

CASES['P15']['claims'] += [claim('P15','leptonic','Section3.2 two-family example after Eq.(3.13)','(a, −a, a, −a, b, −b)','With all quarks uncharged, source lepton family gives (FL2,FL3,Fe2,Fe3,Fnu2,Fnu3)=(a,-a,a,-a,b,-b), arbitrary integersa,b; pure opposite RH-neutrino charges are a=0. All identified RH assignments must negate when stored all-LH.'),claim('P15','left23','Section4.1 Table1 solution5 discussion','FQ3 = 1, FQ2 = −1','Source now uses actual weak-basis family indices: FQ3=FL3=+1,FQ2=FL2=-1,all other U1F charges zero. This is distinct from species-wise sorted table vectors. Breaking scalar completion remains unselected.')]
CASES['P15']['source_descriptions'][0]['reason']='All recorded source charge-example scopes now targeted: leptonic two-family, left23, top-only Eq4.2, Table5 row14, and all-SM-Yukawa family. They remain charge assignments/families, not fully specified numerical Higgs/breaking theories.'
CASES['P15']['inspection']['scope']+=' Also re-read two-family leptonic formula and actual-family left23 example.'

CASES['P24']['claims'][-1]['basis']='source_statement_and_standard_SU5_adjoint_branching_derivation'

CASES['P28']['claims'].append(claim('P28','supersymmetry','Introduction; Section7 Eqs.(7.4)-(7.8)','the theory is supersymmetric','Section7 high-energy example explicitly assumes SUSY (no Si-dagger holomorphic entries), so U/Ubar,D/Dbar and singletS coordinates belong to chiral supermultiplets in that regime, not just Dirac fermions without scalar partners. The text prefers an anomaly-free discrete horizontal subgroup; lepton/R-symmetry assignments are left undecided there. Continuous horizontal U1 labels are not automatically gauged.'))
CASES['P28']['inspection']['scope']+=' Introduction and explicit SUSY statement following Eq7.8 re-read; high-energy regime SUSY established.'
CASES['P28']['source_descriptions'][0]['value_status']='source_scoped_SUSY_quark_completion_with_unselected_lepton_extension'
CASES['P28']['source_descriptions'][0]['reason']='High-energy example is explicitly supersymmetric; each heavy pair therefore has chiral scalar/fermion partners. Remaining full lepton/optional completion alignment is not asserted from a quark-sector table. Earlier uncertainty about whether this particular regime is SUSY has been resolved, not converted into a source omission.'

CASES['P42']['claims'].append(claim('P42','quartic','Section3.2 Eq.(20)','transform as 62/3','Quartic mediator is actual 5D bulk complex scalar Phi in SU3L symmetric6 with X=2/3, coupled Sigma Phi-dagger Sigma on TeV brane. Thus DynkinA2[2,0],colour singlet by the displayed invariant. Auxiliary4D elementary source phi/CFT operator is not an additional independent5D scalar. Other boundary-origin framework has an unspecified example representationr.',basis='source_statement_and_symmetric_tensor_conversion'))
CASES['P42']['source_descriptions'][0]['fields']=[{'label':'bulk Phi','lorentz':{'dimension':5,'scheme':'B2_Dynkin','irreps':[[0,0]]},'gauge_irrep':{'su3L':[2,0]},'source_X':'2/3','reality':'complex','copies':1,'evidence':['quartic']}]
CASES['P42']['inspection']['scope']+=' Full Section3.2 scalar mediator definition and quartic mechanism inspected.'

# These were actually rendered and inspected, rather than inferred from text extraction.
for pid,pages in {'P14':[5],'P20':[3],'P31':[4],'P35':[5],'P43':[1],'P50':[8]}.items():
    CASES[pid]['inspection']['visually_inspected_pdf_pages']=pages

if __name__=='__main__':save()
