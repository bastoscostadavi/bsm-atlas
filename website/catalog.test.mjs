import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const dir=path.dirname(fileURLToPath(import.meta.url)),context={window:{}};
for(const file of ['data.js','manifest.js','search.js','catalog.js']) vm.runInNewContext(fs.readFileSync(path.join(dir,file),'utf8'),context);
const {ATLAS_DATA:data,ATLAS_MANIFEST:manifest,AtlasSearch:search,AtlasCatalog:catalog}=context.window;
const app=catalog.create(data,manifest,search);
const factorModel={g:[['TEST GROUP','','','','misleading display',['Exact × recorded factor']]]};
assert.equal(search.matchedGroups(factorModel,'Exact × recorded factor','factor').length,1);
assert.equal(search.matchedGroups(factorModel,'Exact','factor').length,0);
assert.equal(app.findPapers().length,50);
assert.equal(app.findPapers({text:'F. Staub'})[0].id,'P47');
assert.equal(app.findPapers({gauge:'SU(5)'}).length,3);
assert.equal(app.findPapers({gauge:'SU(5)',role:'category:formulation'})[0].id,'P18');
assert.equal(app.papers.find(p=>p.id==='P47').matches.length,0);
assert.match(app.renderPaper('P47'),/not a completed paper profile/);
assert.match(app.renderPaper('P47'),/not an extraction result/);
assert.match(app.renderPaper('P47'),/No agent-written summary/);
assert.match(app.tablePanel('evidence_refs'),/not included/);
assert.match(app.review(),/Not exported/);
assert.match(app.comparison('nmssm-general-rpc-cpc','nmssm-z3-rpc-cpc'),/not an equivalence/);
const full=JSON.parse(JSON.stringify(data));
const definition=(cols,rows,foreignKeys=[])=>({columns:cols.map((name,i)=>({name,type:'TEXT',pk:i===0?1:0})),rows,foreignKeys,sql:'CREATE TABLE test;'});
const fk=(table,from,to,id=0,seq=0)=>({table,from,to,id,seq});
full.relational={tables:{
  papers:definition(['paper_id','arxiv_id'],[{paper_id:'P47',arxiv_id:'1309.7223'}]),
  paper_versions:definition(['paper_version_id','paper_id'],[{paper_version_id:'P47v2',paper_id:'P47'}],[fk('papers','paper_id','paper_id')]),
  paper_profiles:definition(['paper_version_id','author_abstract','inspected_scope'],[{paper_version_id:'P47v2',author_abstract:'AUTHORS ABSTRACT',inspected_scope:'Section 2 only',no_model_link_reason:'methods source',review_status:null}],[fk('paper_versions','paper_version_id','paper_version_id')]),
  paper_summary_revisions:definition(['summary_id','paper_version_id','summary_text'],[{summary_id:'S1',paper_version_id:'P47v2',summary_text:'AGENT SUMMARY',review_status:'unchecked'}]),
  paper_assertions:definition(['assertion_id','paper_version_id','statement'],[{assertion_id:'A1',paper_version_id:'P47v2',statement:'<script>unsafe</script>',basis:'source_stated',review_status:'unchecked',value_status:'specified'}]),
  evidence_refs:definition(['evidence_id','locator'],[{evidence_id:'E1',locator:'Eq. (2), PDF page 4'}]),
  paper_assertion_evidence:definition(['assertion_id','evidence_id'],[{assertion_id:'A1',evidence_id:'E1'}],[fk('paper_assertions','assertion_id','assertion_id'),fk('evidence_refs','evidence_id','evidence_id',1)]),
  parent: {columns:[{name:'model_id',pk:1},{name:'revision',pk:2}],rows:[{model_id:'m',revision:1},{model_id:'m',revision:2}],foreignKeys:[]},
  child:definition(['child_id','model_id','model_revision'],[{child_id:'c',model_id:'m',model_revision:2}],[fk('parent','model_id','model_id',0,0),fk('parent','model_revision','revision',0,1)])
},validation:{integrityCheck:['ok'],foreignKeyViolations:[]}};
const complete=catalog.create(full,manifest,search),paper=complete.renderPaper('P47');
assert.match(paper,/AUTHORS ABSTRACT/);assert.match(paper,/AGENT SUMMARY/);assert.match(paper,/Section 2 only/);
assert.match(paper,/Eq\. \(2\), PDF page 4/);assert.match(paper,/source_stated/);assert.match(paper,/NULL — not asserted/);
assert.ok(!paper.includes('<script>unsafe</script>'));assert.match(paper,/&lt;script&gt;/);
assert.equal(complete.evidence('paper_assertions',full.relational.tables.paper_assertions.rows[0],'paper_assertion_evidence').length,1);
assert.equal(complete.related('parent',{model_id:'m',revision:1},'child').length,0);
assert.equal(complete.related('parent',{model_id:'m',revision:2},'child').length,1);
assert.match(complete.tablePanel('paper_profiles'),/Published table contents/);
assert.match(complete.tablePanel('paper_profiles',{key:'{"paper_version_id":"P47v2"}'}),/Selected database row/);
assert.match(complete.tablePanel('paper_assertions',{q:'nothing'}),/0 matches/);
console.log('Catalogue validated: 50-paper inventory, methods sources, honest missing data, profiles, evidence, composite foreign keys, XSS escaping and comparisons.');
