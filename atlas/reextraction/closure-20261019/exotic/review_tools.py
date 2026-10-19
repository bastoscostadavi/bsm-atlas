"""Read-only construction of source-reviewed closure artifacts; stdout only."""
import json,sys,hashlib
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'atlas'))
from prepare_entry import prepare
HERE=Path(__file__).resolve().parent
config=json.loads(sys.argv[1])
entry=config['entry']
frozen=ROOT/'atlas/reextraction/followup-20261016'
source=config['source_override'] if config.get('source_override') else json.loads((frozen/(entry+'-source-candidate.json')).read_text())
old=json.loads((frozen/(entry+'-evidence.json')).read_text()) if (frozen/(entry+'-evidence.json')).exists() else {}
prepared=prepare(source,ROOT/'website/downloads/field-catalogue.sqlite')
normalized=prepared['normalized_entry']
repeat=prepare(normalized,ROOT/'website/downloads/field-catalogue.sqlite')
assert normalized==repeat['normalized_entry']
pdf=ROOT/config['pdf']
srcpdf={'path':config['pdf'],'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':config['pages']}
mapping=config.get('mapping',old.get('source_field_mapping',[]))
assert len(mapping)==len(source['matter'])
for m in mapping:
 m['claim_ids']=config.get('row_claim_ids',{}).get(m['candidate_label'],[c['id'] for c in config['claims']])
 if not m.get('source_field_ids'):
  m['mapping_basis']='source_declared_SM_baseline_expanded_in_new_review'
  m['baseline_provenance']='Source explicitly retains the SM; three ordinary SM families and one Higgs are the declared Atlas R_SM convention, not a newly printed component table.'
 for k in ['source_model_id','source_regime_id']:
  if m.get(k) is None and m.get('legacy_fields'):
   m[k]=m['legacy_fields'][0]['model_id' if k=='source_model_id' else 'regime_id']
evidence={'target_entry_id':entry,'paper_id':config['paper'],'arxiv_version':config['arxiv'],'reviewed_on':'2026-10-19','review':'agent_source_reinspection_for_complete_inventory','source_pdfs':[srcpdf],'inspection':{'scope':config['scope'],'whole_paper_read':False,'rendered_complete_relevant_pages_inspected':config['pages'],'historical_review_is_lead_only':True},'claims':config['claims'],'source_field_mapping':mapping,'description_regime':{'source_regime_id':config['regime'],'description':config['scope']},'decision':{'inventory_complete':True,'not_extracted':[],'not_specified_by_source':[]},'limitations':config.get('limitations',[]),'no_anomaly_or_viability_gate':True}
fieldrows=[]
for row,m in zip(source['matter'],mapping):
 single=deepcopy(source);single['matter']=[row]
 # Preserve full-inventory U(1) scale; normalizing each source row alone would be incorrect.
 labels={row['label'],row['label']+'_L',row['label']+'_R^c'}
 components=[r for r in normalized['matter'] if r.get('label') in labels or r.get('source_fermion',{}).get('label')==row['label'] or r.get('sourceScalar',{}).get('label')==row['label']]
 if not components:
  # Repository normalizer retains label for its first Weyl component and annotates handedness in labels.
  components=[r for r in normalized['matter'] if r.get('label','').startswith(row['label']+' ')]
 fieldrows.append({'source_row':row,'normalized_components':components,'mapping':m})
base='atlas/reextraction/closure-20261019/exotic/'
paths={k:base+entry+'-'+s+'.json' for k,s in [('source','source-candidate'),('normalized','normalized'),('evidence','evidence'),('fields','field-evidence'),('preflight','preflight'),('require_normalized','require-normalized'),('duplicates','duplicates')]}
field={'target_entry_id':entry,'source_locator_evidence':paths['evidence'],'rows':fieldrows,'scalar_convention':'scalar-real-modules-1','fermion_convention':'all identified 4D Weyl LH; conjugate every factor'}
decision={'entry':entry,'paper':config['paper'],'arxiv':config['arxiv'],'regime':config['regime'],'decision':'accept','reason':config['reason'],'inspected_scope':config['scope'],'source_pdfs':[srcpdf],'claims':config['claims'],'limitations':config.get('limitations',[]),'source_path':paths['source'],'normalized_path':paths['normalized'],'evidence_path':paths['evidence'],'fields_path':paths['fields'],'fingerprint':prepared['fingerprint']}
reviews=json.loads((HERE/'reviews.json').read_text()) if (HERE/'reviews.json').exists() else []
reviews=[r for r in reviews if r['entry']!=entry]+[decision]
files={paths['source']:source,paths['normalized']:normalized,paths['evidence']:evidence,paths['fields']:field,paths['preflight']:prepared,paths['require_normalized']:repeat,paths['duplicates']:prepared['duplicate_check'],base+'reviews.json':reviews}
print(json.dumps({'files':files,'decision':decision,'prior_reviews_text':(HERE/'reviews.json').read_text() if (HERE/'reviews.json').exists() else None}))
