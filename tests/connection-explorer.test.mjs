import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const website=new URL('../website/',import.meta.url);
const context={URLSearchParams,location:{hash:'#problems'},history:{replaceState(_s,_t,h){context.location.hash=h;}},localStorage:{getItem(){return 'light';},setItem(){}}};
context.window=context;context.addEventListener=()=>{};
for(const file of ['problem-data.js','mechanism-data.js','problem-explorer.js','connection-explorer.js','field-matrix.js','field-catalogue.js'])vm.runInNewContext(fs.readFileSync(new URL(file,website),'utf8'),context);
const data=JSON.parse(fs.readFileSync(new URL('field-catalogue.json',website)));
const problems=context.ATLAS_PROBLEMS,mechanisms=context.ATLAS_MECHANISMS;
const explorer=context.ConnectionExplorer.create(data,problems,mechanisms);
const ids=entries=>Array.from(entries,e=>e.id);
assert.equal(mechanisms.mechanisms.length,31);
const baseline=JSON.parse(fs.readFileSync(new URL('../atlas/literature_baseline.json',website))).mechanisms;
for(const [entry,terms] of Object.entries(baseline.links))for(const [term,rows] of Object.entries(terms)){
 for(const row of rows)assert(mechanisms.links[entry]?.[term]?.some(actual=>JSON.stringify(actual)===JSON.stringify(row)));
}
for(const [id,terms] of Object.entries(mechanisms.links)){
 const entry=data.entries.find(e=>e.id===id);assert(entry);
 assert(mechanisms.assessed.includes(id));
 for(const [term,rows] of Object.entries(terms)){
  assert(mechanisms.mechanisms.some(t=>t.id===term));assert(rows.length);
  for(const row of rows){
   assert(entry.paperIds.includes(row.paperId));assert(row.evidence.length);
   assert.equal(row.needsReview,row.reviewReasons.length>0);
  }
 }
}
const multipleProblems={view:'problems',problems:['dark_matter','neutrino_masses']};
const multipleMechanisms={view:'mechanisms',mechanisms:['thermal_freeze_out','coannihilation']};
const mixed={problems:['dark_matter','neutrino_masses'],mechanisms:['thermal_freeze_out','coannihilation']};
for(const state of [multipleProblems,multipleMechanisms,mixed]){
 const expected=data.entries.filter(e=>(state.problems||[]).every(p=>problems.links[e.id]?.[p]?.length)&&(state.mechanisms||[]).every(m=>mechanisms.links[e.id]?.[m]?.length));
 assert(expected.length>0);
 assert.deepEqual(ids(explorer.find(state)),ids(expected));
 assert.deepEqual(ids(explorer.filterEntries(data.entries,state)),ids(expected));
 const parsed=explorer.parse(explorer.url(state));
 assert.deepEqual(ids(explorer.find(parsed)),ids(expected));
}
// No selections leaves the entire structural catalogue, including unassessed entries.
assert.deepEqual(ids(explorer.filterEntries(data.entries,{})),ids(data.entries));
assert(explorer.find({view:'mechanisms'}).length<data.entries.length);
for(const id of ['does_not_exist','__proto__','toString']){
 assert.equal(explorer.find({mechanisms:[id]}).length,0);
 assert.equal(explorer.filterEntries(data.entries,{mechanisms:[id]}).length,0);
}
assert.equal(explorer.normalize({problems:['dark_matter','dark_matter']}).problems.length,1);
assert.equal(explorer.parse('#problems/dark_matter?search=nuMSM').problems[0],'dark_matter');
assert.equal(explorer.parse('#mechanisms/thermal_freeze_out').mechanisms[0],'thermal_freeze_out');
assert(explorer.find({view:'mechanisms',q:'nuMSM',mechanisms:['thermal_freeze_out']}).some(e=>e.id==='numsm'));
assert(explorer.results({mechanisms:['does_not_exist']}).includes('No entries match'));
const mechanismPage=explorer.page(multipleMechanisms);
assert(mechanismPage.includes('type="checkbox"'));
assert(mechanismPage.includes('data-connection-kind="mechanisms"'));
assert(!mechanismPage.includes('data-filter-layer="problems"'));
assert(!mechanismPage.includes('class="connection-result-tag problems"'));
assert(mechanismPage.includes('mechanism=thermal_freeze_out&amp;mechanism=coannihilation'));
assert(explorer.page(multipleProblems).includes('data-filter-layer="problems"'));
assert(!explorer.page(multipleProblems).includes('data-filter-layer="mechanisms"'));
assert.equal((explorer.results({view:'mechanisms'}).match(/class="connection-result"/g)||[]).length,20);
assert(explorer.page({view:'mechanisms',mechanisms:['<script>unsafe</script>']}).includes('&lt;script&gt;'));
const panel=context.MechanismExplorer.create(data,mechanisms).entry('numsm');
assert(panel.includes('Mechanism associations'));assert(panel.includes('Leptogenesis'));
assert(panel.includes('https://arxiv.org/abs/'));
assert(panel.includes('Quote not found')||panel.includes('Quote not near cited lines'));
assert(!panel.includes('Problem associations'));

const nodes=new Map(),document={getElementById(id){if(!nodes.has(id))nodes.set(id,{events:new Map(),attributes:new Map(),setAttribute(k,v){this.attributes.set(k,v);},addEventListener(k,v){this.events.set(k,v);},contains(){return false;}});return nodes.get(id);},addEventListener(){},documentElement:{dataset:{}}};
const app=context.FieldCatalogue.create(data,document);
const render=hash=>{context.location.hash=hash;app.route();app.render();};
render('#entries?problem=dark_matter&problem=neutrino_masses&mechanism=thermal_freeze_out&mechanism=coannihilation');
assert.equal(nodes.get('result-count').textContent,explorer.find(mixed).length+' entries');
assert(nodes.get('view-content').innerHTML.includes('Entries must connect to every selection'));
assert(nodes.get('view-content').innerHTML.includes('data-picker="problems"'));
assert(nodes.get('view-content').innerHTML.includes('data-picker="mechanisms"'));
app.url();
for(const value of ['problem=dark_matter','problem=neutrino_masses','mechanism=thermal_freeze_out','mechanism=coannihilation'])assert(context.location.hash.includes(value));
const menu=['nav-forces','nav-matter'].map(id=>nodes.get(id).href);
for(const href of menu)for(const value of ['problem=dark_matter','problem=neutrino_masses','mechanism=thermal_freeze_out','mechanism=coannihilation'])assert(href.includes(value));
render('#catalogue?mechanism=linear_seesaw');
const linearSeesawAlgebras=new Set(explorer.find({mechanisms:['linear_seesaw']}).map(entry=>entry.semisimpleId)).size;
assert.equal(nodes.get('result-count').textContent,linearSeesawAlgebras+' semisimple '+(linearSeesawAlgebras===1?'part':'parts'));
render('#entries?problem=dark_matter&mechanism=thermal_freeze_out&q=nuMSM');
const searchCount=explorer.filterEntries(context.FieldCatalogue.findEntries(data,{q:'nuMSM'}),{problems:['dark_matter'],mechanisms:['thermal_freeze_out']}).length;
assert.equal(nodes.get('result-count').textContent,searchCount+' '+(searchCount===1?'entry':'entries'));
render('#mechanisms?mechanism=thermal_freeze_out&mechanism=coannihilation');
assert.equal(nodes.get('page-title').textContent,'Mechanisms');
assert(nodes.get('view-content').innerHTML.includes(explorer.find(multipleMechanisms).length+' entries'));
render('#problems?problem=dark_matter&problem=neutrino_masses');
assert.equal(nodes.get('page-title').textContent,'Problems');
assert(nodes.get('view-content').innerHTML.includes(explorer.find(multipleProblems).length+' entries'));
render('#entry/numsm?panel=mechanisms');
assert(nodes.get('model-entries').innerHTML.includes('Mechanism associations'));
app.url();assert(context.location.hash.includes('panel=mechanisms'));

// Exercise delegated checkbox, removal, clear and pagination handlers.
render('#mechanisms');app.start();
const content=nodes.get('view-content');
const change=(kind,value,checked)=>content.events.get('change')({target:{type:'checkbox',dataset:{connectionKind:kind},value,checked,closest(){return {classList:{toggle(){}}};}}});
change('mechanisms','thermal_freeze_out',true);change('mechanisms','coannihilation',true);
assert.equal(app.state.connections.mechanisms.length,2);
assert(nodes.get('connection-results').innerHTML.includes(explorer.find(multipleMechanisms).length+' entries'));
change('mechanisms','coannihilation',false);assert.equal(app.state.connections.mechanisms.length,1);
content.events.get('click')({target:{closest(selector){return selector==='[data-connection-clear]'?{}:null;}}});
assert.equal(app.state.connections.mechanisms.length,0);
render('#entries');change('problems','dark_matter',true);change('mechanisms','thermal_freeze_out',true);
const expected=explorer.find({problems:['dark_matter'],mechanisms:['thermal_freeze_out']}).length;
assert.equal(nodes.get('result-count').textContent,expected+' entries');
const toggle=checked=>content.events.get('change')({target:{id:'semisimple-only',checked}});
for(const full of ['entries','full-algebras']){
 render('#'+full+'?problem=dark_matter&mechanism=thermal_freeze_out&q=singlet');
 const expectedEntries=explorer.filterEntries(context.FieldCatalogue.findEntries(data,{q:'singlet'}),{problems:['dark_matter'],mechanisms:['thermal_freeze_out']});
 toggle(true);assert.equal(app.state.browse,full==='entries'?'cores':'algebras');
 const grouping=full==='entries'?'coreId':'semisimpleId';
 assert(nodes.get('result-count').textContent.startsWith(String(new Set(expectedEntries.map(e=>e[grouping])).size)+' '));
 app.route();assert.equal(app.state.connections.problems[0],'dark_matter');assert.equal(app.state.connections.mechanisms[0],'thermal_freeze_out');assert.equal(app.state.q,'singlet');
 toggle(false);assert.equal(app.state.browse,full);
 assert.equal(app.state.connections.problems[0],'dark_matter');assert.equal(app.state.connections.mechanisms[0],'thermal_freeze_out');
}
render('#entries?problem=dark_matter&mechanism=thermal_freeze_out');
content.events.get('click')({target:{closest(selector){return selector==='[data-reset]'?{}:null;}}});
assert.equal(nodes.get('result-count').textContent,data.entries.length+' entries');
console.log('Mechanism evidence, multiple selections, cross-layer intersection, catalogue grouping, routes and controls passed.');
