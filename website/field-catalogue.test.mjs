import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const context={URLSearchParams,location:{hash:'#catalogue'},history:{replaceState(_s,_t,hash){context.location.hash=hash;}}};
for(const file of ['representation-diagrams.js','field-matrix.js','field-catalogue.js'])vm.runInNewContext(fs.readFileSync(new URL(file,import.meta.url),'utf8'),context);
const {findEntries,esc,create,dynkinTuple,representationMarkup}=context.FieldCatalogue;
const data=JSON.parse(fs.readFileSync(new URL('field-catalogue.json',import.meta.url)));
assert.equal(findEntries(data).length,data.entries.length);
assert(findEntries(data,{paper:'P15'}).length>=3);
assert.equal(findEntries(data,{paper:'R01'}).length,0);
assert(findEntries(data,{q:'singlet'}).length>0);
assert(findEntries(data,{q:'vector-like'}).length>0);
assert.equal(esc('<img onerror="x">'),'&lt;img onerror=&quot;x&quot;&gt;');
const nodes=new Map(),document={getElementById(id){if(!nodes.has(id))nodes.set(id,{});return nodes.get(id);}};
const app=create(data,document),content=()=>nodes.get('view-content').innerHTML,results=()=>nodes.get('model-entries').innerHTML;
const descriptions={
 algebras:'Gauge algebras, with matter and all U(1) factors omitted.',
 'full-algebras':'Gauge algebras, with matter omitted and all U(1) factors included.',
 cores:'Gauge algebras and matter representations, with all U(1) factors omitted.',
 entries:'Gauge algebras and matter representations, with all U(1) factors included.'};
for(const [browse,count] of [['algebras',data.semisimpleAlgebras.length],['full-algebras',data.fullAlgebras.length],['cores',data.cores.length],['entries',data.entries.length]]){
 app.state.browse=browse;app.render();
 assert(content().includes(descriptions[browse]));
 assert(nodes.get('result-count').textContent.startsWith(String(count)+' '));
 const menu=nodes.get('catalogue-views').innerHTML;
 assert.equal((menu.match(/<a /g)||[]).length,4);
 assert.equal((menu.match(/aria-current="page"/g)||[]).length,1);
 assert.equal((menu.match(/class="catalogue-group-label"/g)||[]).length,2);
 assert(!content().includes('layer-navigation'));
 assert(!content().includes('status-filter'));
 assert(!results().includes('count pending'));
 assert(!results().includes('reality unresolved'));
 assert(!results().includes('<th>Copies</th>'));
 if(browse==='cores')assert(!results().includes('u(1)'));
}
assert(!data.semisimpleAlgebras.some(a=>a.algebra==='su(2)'));
assert(data.semisimpleAlgebras.some(a=>a.algebra==='su(5)'));
app.state.q='two-higgs-doublets';app.state.browse='entries';app.render();
assert(results().includes('(1, 2; 3)'));
assert(results().includes('<th>Multiplicity</th>'));
assert(results().includes('data-dynkin-family="A"'));
for(const mode of ['dynkin','young','compare']){
 app.state.mode=mode;app.render();
 assert(results().includes(mode==='young'?'data-young-rows="[1]"':'([0,0], [1]; 3)'));
}
app.state.mode='dimensions';app.state.q='vlq-t-singlet';app.state.open='vlq-t-singlet';app.render();
assert(results().includes('rep-conjugate'));
assert(results().includes('aria-label="conjugate 3"'));
assert(results().includes('<h2>References</h2>'));
assert(results().includes('https://arxiv.org/abs/'));
for(const extra of ['Provenance','Inspection details','Source-backed re-extraction','assertion ','source field ','Description'])assert(!results().includes(extra));
app.state.q='u1-ybl-charge-family';app.render();
assert(results().includes('Integer parameters:'));
assert(results().includes('Parameter constraints'));
assert(results().includes('Source parameter names:'));
assert(!results().includes('q = '));
app.state.view='notation';app.render();
for(const phrase of ['Bourbaki','all-zero labels denote a singlet','left-handed fields','negates its U(1) charges','Scalars count irreducible real gauge modules','three generations, not 6','Symbolic charge families','descending lexicographic order','we do not try to prove that differently written domains','SM matter table','MSSM matter table'])assert(content().includes(phrase),phrase);
assert(content().includes('([0,1], [0]; -4)'));
assert.equal(nodes.get('notation-guide').open,true);
app.state.view='sources';app.render();
assert(content().includes('General solution to the U(1) anomaly equations'));
assert(!content().includes('Inspection details'));
app.state.view='atlas';app.render();
for(const phrase of ['Gauge symmetry and the representations of matter','19 free parameters','infinitely many predictions','electron’s magnetic moment','Only complete specifications are included','precise objects and their paper references','bsm-ai-search','bsm-foundation-model'])assert(content().includes(phrase),phrase);
for(const route of ['#catalogue','#full-algebras','#cores','#entries'])assert(content().includes('href="'+route+'"'));
assert(!content().includes('supporting passages'));
assert(!content().includes('50'));
assert(!content().includes('Once a Lagrangian is specified'));
const primary=id=>data.entries.find(e=>e.id===id).regime;
const nm=context.FieldMatrix.matrixRows(primary('nmssm-matter'),data.templates);
assert.equal(nm.length,2);
assert.deepEqual(Array.from(nm,r=>r.copies).sort(),[1,2]);
assert.equal(context.FieldMatrix.gaugeColumns(primary('nmssm-matter'))[0].label,'g_SM');
assert(!context.FieldMatrix.gaugeColumns(primary('su5-adjoint-renormalizable')).some(c=>c.sm));
const vlq=context.FieldMatrix.matrixRows(primary('vlq-t-singlet'),data.templates);
assert.equal(vlq.length,2);
assert(vlq.some(r=>dynkinTuple(r.components)==='([0,1], [0]; -4)'));
const thdm=context.FieldMatrix.matrixRows(primary('two-higgs-doublets'),data.templates,true);
assert(thdm.length>context.FieldMatrix.matrixRows(primary('two-higgs-doublets'),data.templates).length);
const safe=representationMarkup([{factor:'u(1)',value:'<script>'}],'dimensions',false);
assert(!safe.includes('<script>'));assert(safe.includes('&lt;script&gt;'));
const smFull=data.fullAlgebras.find(a=>a.algebra==='su(3) ⊕ su(2) ⊕ u(1)');
const smAlgebra=smFull.semisimpleId;
const core=data.entries.find(e=>e.id==='vlq-t-singlet').coreId;
for(const [hash,browse] of [['#catalogue','algebras'],['#full-algebras?semisimple='+smAlgebra,'full-algebras'],['#algebra/'+smAlgebra,'cores'],['#core/'+core,'entries'],['#full-algebra/'+smFull.id,'entries'],['#entry/vlq-t-singlet','entries']]){
 context.location.hash=hash;app.route();app.render();assert.equal(app.state.browse,browse);
}
context.location.hash='#core/'+core+'?fullAlgebra='+smFull.id+'&notation=compare';
app.route();app.render();assert.equal(nodes.get('result-count').textContent,findEntries(data,{core,fullAlgebra:smFull.id}).length+' entries');
assert.equal(app.state.mode,'compare');
app.state.q='vector-like';app.url();app.route();
assert.equal(app.state.core,core);assert.equal(app.state.fullAlgebra,smFull.id);assert.equal(app.state.q,'vector-like');
context.location.hash='#entry/lns-single-singlet-quarks';app.route();assert.equal(app.state.open,'nmssm-matter');
context.location.hash='#full-algebra/not-real';app.route();app.render();assert.equal(nodes.get('result-count').textContent,'0 entries');
context.location.hash='#about';app.route();assert.equal(app.state.view,'atlas');
context.location.hash='#catalogue';
// The native disclosure retains link semantics; dismissal returns focus on Escape.
const uiNodes=new Map(),documentEvents=new Map(),windowEvents=new Map();
let triggerFocused=false,escapePrevented=false;
const uiDocument={documentElement:{dataset:{}},addEventListener(name,fn){documentEvents.set(name,fn);},
  getElementById(id){
    if(!uiNodes.has(id))uiNodes.set(id,{events:new Map(),setAttribute(){},addEventListener(name,fn){this.events.set(name,fn);},
      contains(target){return Boolean(target.insideCatalogue);},querySelector(){return {focus(){triggerFocused=true;}};}});
    return uiNodes.get(id);
  }};
context.window={addEventListener(name,fn){windowEvents.set(name,fn);}};
context.localStorage={getItem(){return null;},setItem(){}};
const disclosure=create(data,uiDocument);disclosure.start();
const menu=uiNodes.get('catalogue-menu');
menu.open=true;documentEvents.get('keydown')({key:'Escape',preventDefault(){escapePrevented=true;}});
assert.equal(menu.open,false);assert(triggerFocused);assert(escapePrevented);
menu.open=true;documentEvents.get('click')({target:{insideCatalogue:true}});assert.equal(menu.open,true);
documentEvents.get('click')({target:{}});assert.equal(menu.open,false);
menu.open=true;menu.events.get('click')({target:{closest(){return {};}}});assert.equal(menu.open,false);
menu.open=true;menu.events.get('focusout')({relatedTarget:{insideCatalogue:true}});assert.equal(menu.open,true);
menu.events.get('focusout')({relatedTarget:{}});assert.equal(menu.open,false);
menu.open=true;windowEvents.get('hashchange')();assert.equal(menu.open,false);

console.log('Minimal explorer, notation, routes, references and disclosure checks passed.');
