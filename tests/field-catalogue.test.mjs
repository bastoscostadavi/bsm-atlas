import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const website=new URL('../website/',import.meta.url);
const context={URLSearchParams,location:{hash:'#catalogue'},history:{replaceState(_s,_t,hash){context.location.hash=hash;}}};
for(const file of ['representation-diagrams.js','field-matrix.js','field-catalogue.js'])vm.runInNewContext(fs.readFileSync(new URL(file,website),'utf8'),context);
const {findEntries,findPapers,esc,create,dynkinTuple,representationMarkup,arxivDate,comparePapers}=context.FieldCatalogue;
const data=JSON.parse(fs.readFileSync(new URL('field-catalogue.json',website)));
const referenceCount=id=>data.entries.find(e=>e.id===id).references.length;
assert.equal(findEntries(data).length,data.entries.length);
assert(findEntries(data,{paper:'P15'}).length>=3);
assert.equal(findEntries(data,{paper:'R01'}).length,0);
assert(findEntries(data,{q:'singlet'}).length>0);
assert(findEntries(data,{q:'vector-like'}).length>0);
assert.equal(esc('<img onerror="x">'),'&lt;img onerror=&quot;x&quot;&gt;');
assert.equal(arxivDate({arxiv:'hep-ph/9212278v1'}).value,'1992-12');
assert.equal(arxivDate({arxiv:'hep-ph/0011335v3'}).value,'2000-11');
assert.equal(arxivDate({arxiv:'0704.0001v9'}).value,'2007-04');
assert.equal(arxivDate({arxiv:'1905.13729v1'}).label,'May 2019');
assert.equal(arxivDate({arxiv:'1905.13729v10'}).value,'2019-05');
assert.equal(arxivDate({arxiv:'1913.13729v1'}),null);
const dates=[{arxiv:'1501.00010v1',title:'c'},{arxiv:'hep-ph/9912345v2',title:'a'},{arxiv:'1501.00002v8',title:'b'}];
assert.deepEqual(Array.from([...dates].sort(comparePapers),p=>p.title),['a','b','c']);
assert.equal(comparePapers({arxiv:'0910.1785v5',title:'same'},{arxiv:'0910.1785v1',title:'same'}),0);
const bibliography=[
 {arxiv:'hep-ph/9212278v1',title:'Legacy model',authors:'René Example'},
 {arxiv:'2001.00001v2',title:'Modern gauge theory',authors:'Other Author'},
 {arxiv:'2002.00002v1',title:'Modern matter',authors:'René Example'}];
assert.equal(findPapers(bibliography).length,0);
assert.equal(findPapers(bibliography,{q:'  '}).length,0);
assert.equal(findPapers(bibliography,{q:'GAUGE THEORY'})[0],bibliography[1]);
assert.equal(findPapers(bibliography,{q:'rene'}).length,2);
assert.equal(findPapers(bibliography,{q:'modern author'})[0],bibliography[1]);
assert.equal(findPapers(bibliography,{q:'arXiv:hep-ph/9212278'})[0],bibliography[0]);
assert.equal(findPapers(bibliography,{q:'https://arxiv.org/abs/2001.00001v2'})[0],bibliography[1]);
assert.equal(findPapers(bibliography,{year:'1992'})[0],bibliography[0]);
assert.equal(findPapers(bibliography,{year:'2020'}).length,2);
assert.equal(findPapers(bibliography,{q:'rene',year:'2020'})[0],bibliography[2]);
assert.equal(findPapers(bibliography,{q:'gauge',year:'1992'}).length,0);
const nodes=new Map(),document={getElementById(id){if(!nodes.has(id))nodes.set(id,{});return nodes.get(id);}};
const app=create(data,document),content=()=>nodes.get('view-content').innerHTML,results=()=>nodes.get('model-entries').innerHTML;
const viewTitles={
 algebras:'Gauge algebras',
 'full-algebras':'Gauge algebras',
 cores:'Gauge algebras and matter representations',
 entries:'Gauge algebras and matter representations'};
const viewSubtitles={
 algebras:'The semisimple part of the gauge algebra, with U(1) factors and matter representations omitted.',
 'full-algebras':'Gauge algebras, with matter representations omitted.',
 cores:'The semisimple part of the gauge algebra and its matter representations, with U(1) factors omitted.',
 entries:'Complete gauge–matter specifications, with multiplicities and charge assignments.'};
for(const [browse,count] of [['algebras',data.semisimpleAlgebras.length],['full-algebras',data.fullAlgebras.length],['cores',data.cores.length],['entries',data.entries.length]]){
 app.state.browse=browse;app.render();
 assert.equal(nodes.get('page-title').textContent,viewTitles[browse]);
 assert(content().includes('<p class="section-note">'+viewSubtitles[browse]+'</p>'));
 assert.equal((content().match(/class="section-note"/g)||[]).length,1);
 assert(nodes.get('result-count').textContent.startsWith(String(count)+' '));
 const menu=nodes.get('catalogue-views').innerHTML;
 assert.equal((menu.match(/<a /g)||[]).length,4);
 assert.equal((menu.match(/aria-current="page"/g)||[]).length,1);
 assert.equal((menu.match(/class="catalogue-group-label"/g)||[]).length,2);
 assert(!content().includes('catalogue-back'));
 if(browse==='cores'||browse==='entries'){
  assert(results().includes('class="representation-matrix'));
  assert(results().includes('<th>Multiplicity</th>'));
 }
 if(browse==='cores')assert(!results().includes('u(1)'));
}
assert(!data.semisimpleAlgebras.some(a=>a.algebra==='su(2)'));
assert(data.semisimpleAlgebras.some(a=>a.algebra==='su(5)'));
// Algebra cards and filter options preserve the generated mathematical order.
const orderingAlgebras=['su(3) ⊕ su(2)','su(5)','so(10)'].map(label=>data.semisimpleAlgebras.find(a=>a.algebra===label));
const orderingEntries=orderingAlgebras.map((a,i)=>({...data.entries.find(e=>e.semisimpleId===a.id),name:i===1?'Ordering middle':'Ordering visible'}));
const orderingApp=create({...data,entries:orderingEntries,semisimpleAlgebras:orderingAlgebras},document);
const algebraCardIds=()=>Array.from(results().matchAll(/href="#algebra\/([^"?]+)/g),m=>m[1]);
const algebraFilterSignatures=()=>Array.from(content().match(/<select id="algebra-filter">(.*?)<\/select>/s)[1].matchAll(/<option value="na:([^"]+)"/g),m=>m[1]);
orderingApp.render();
assert.deepEqual(algebraCardIds(),orderingAlgebras.map(a=>a.id));
assert.deepEqual(algebraFilterSignatures(),orderingAlgebras.map(a=>a.algebraSignature));
orderingApp.state.q='Ordering visible';orderingApp.render();
assert.deepEqual(algebraCardIds(),[orderingAlgebras[0].id,orderingAlgebras[2].id]);
assert.deepEqual(algebraFilterSignatures(),orderingAlgebras.map(a=>a.algebraSignature));
// Matter cards preserve generated representation order, including filtered
// results; model names, identities and core hashes are not sorting criteria.
const matterOrderingIds=['real-singlet-z2','complex-singlet-portal','two-higgs-doublets'];
const matterOrderingEntries=matterOrderingIds.map((id,i)=>({...data.entries.find(e=>e.id===id),name:(i===0?'Z ':i===1?'M ':'A ')+(i===1?'Matter ordering middle':'Matter ordering visible')}));
const matterOrderingCores=matterOrderingEntries.map(e=>({...data.cores.find(c=>c.id===e.coreId),entryIds:[e.id]}));
const matterOrderingApp=create({...data,entries:matterOrderingEntries,cores:matterOrderingCores},document);
const matterEntryIds=()=>Array.from(results().matchAll(/<article class="model-entry" id="model-([^"]+)"/g),m=>m[1]);
const matterCoreIds=()=>Array.from(results().matchAll(/class="core-title" href="#core\/([^"?]+)/g),m=>m[1]);
for(const browse of ['entries','cores']){
 matterOrderingApp.state.browse=browse;matterOrderingApp.state.q='';matterOrderingApp.render();
 const renderedIds=browse==='entries'?matterEntryIds:matterCoreIds;
 const expectedIds=browse==='entries'?matterOrderingIds:matterOrderingCores.map(c=>c.id);
 assert.deepEqual(renderedIds(),expectedIds);
 matterOrderingApp.state.q='Matter ordering visible';matterOrderingApp.render();
 assert.deepEqual(renderedIds(),[expectedIds[0],expectedIds[2]]);
}
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
assert(!/>P\d+</.test(results()));
assert(results().includes('aria-label="References for Standard Model with a vector-like T singlet ('+referenceCount('vlq-t-singlet')+')"'));
assert(results().includes('>References ('+referenceCount('vlq-t-singlet')+') −</button>'));
assert.equal((results().match(/data-open=/g)||[]).length,findEntries(data,{q:app.state.q}).length);
app.state.q='nmssm-matter';app.state.open='nmssm-matter';app.render();
assert(results().includes('>References ('+referenceCount('nmssm-matter')+') −</button>'));
assert(!results().includes('Oldest first'));
assert(!results().includes('reference-order'));
assert(results().includes('<ol class="reference-list" aria-label="Papers in chronological order">'));
assert(results().indexOf('hep-ph/9212278v1')<results().indexOf('0910.1785v5'));
assert(results().includes('<time datetime="1992-12">Dec 1992</time>'));
assert(results().includes('<time datetime="2009-10">Oct 2009</time>'));
assert(results().indexOf('class="reference-list"')<results().indexOf('class="representation-matrix'));
const savedOrder=data.entries.find(e=>e.id==='nmssm-matter').references.map(ref=>ref.paper_id).join(',');
app.render();assert.equal(data.entries.find(e=>e.id==='nmssm-matter').references.map(ref=>ref.paper_id).join(','),savedOrder);
const many=JSON.parse(JSON.stringify(data)),manyEntry=many.entries.find(e=>e.id==='nmssm-matter');
many.papers=Array.from({length:100},(_,i)=>({id:'internal-'+i,arxiv:'2001.'+String(100-i).padStart(5,'0')+'v1',title:'Paper '+(100-i),authors:'Example author',entryIds:[manyEntry.id]}));
manyEntry.paperIds=many.papers.map(p=>p.id);manyEntry.references=many.papers.map(p=>({paper_id:p.id,locators:['main.tex: Eq. (internal-source-marker)']}));many.entries=[manyEntry];
const manyApp=create(many,document);manyApp.state.browse='entries';manyApp.state.open=manyEntry.id;manyApp.render();
assert.equal((results().match(/data-open=/g)||[]).length,1);
assert(results().includes('>References (100) −</button>'));
assert.equal((results().match(/<li><time/g)||[]).length,100);
assert(results().indexOf('2001.00001v1')<results().indexOf('2001.00100v1'));
assert(results().includes('Example author'));
assert(!results().includes('main.tex'));
assert(!results().includes('internal-source-marker'));
assert.deepEqual(manyEntry.references[0].locators,['main.tex: Eq. (internal-source-marker)']);
app.state.q='u1-ybl-charge-family';app.render();
assert(results().includes('Integer parameters:'));
assert(results().includes('Parameter constraints'));
assert(results().includes('Source parameter names:'));
assert(!results().includes('q = '));
app.state.q='smash-down';app.state.open='';app.render();
assert(results().includes('>References ('+referenceCount('smash-down')+') +</button>'));
assert(!results().includes('Demonstrated results'));
assert(!content().includes('id="problem-filter"'));
app.state.view='notation';app.render();
for(const phrase of ['Bourbaki','all-zero labels denote a singlet','left-handed fields','negates its U(1) charges','Scalars count irreducible real gauge modules','three generations, not 6','Symbolic charge families','descending lexicographic order','we do not try to prove that differently written domains','SM matter table','MSSM matter table'])assert(content().includes(phrase),phrase);
assert(content().includes('([0,1], [0]; -4)'));
assert.equal(nodes.get('notation-guide').open,true);
app.state.view='sources';app.render();
assert(content().includes('id="paper-search-form"'));
assert(content().includes('id="paper-year"'));
assert(!content().includes('class="paper-item"'));
assert(!content().includes('General solution to the U(1) anomaly equations'));
app.state.paperQuery='General solution to the U(1) anomaly equations';app.render();
assert(content().includes('General solution to the U(1) anomaly equations'));
assert.equal((content().match(/class="paper-item"/g)||[]).length,1);
assert(content().includes('href="https://arxiv.org/abs/'));
assert(!/>P\d+</.test(content()));
// Search result pages stay bounded, preserve criteria and link to individual entries.
manyApp.state.view='sources';manyApp.state.paperQuery='example';manyApp.render();
assert.equal((content().match(/class="paper-item"/g)||[]).length,20);
assert(content().includes('1–20 of 100 papers'));
assert(content().includes('Page 1 of 5'));
assert(content().includes('href="#sources?search=example&amp;page=2" rel="next"'));
assert(content().includes('href="#entry/'+manyEntry.id+'"'));
assert(content().indexOf('2001.00001v1')<content().indexOf('2001.00020v1'));
assert(!content().includes('2001.00021v1'));
context.location.hash='#sources?search=example&year=2020&page=5';manyApp.route();manyApp.render();
assert.equal(manyApp.state.paperPage,5);
assert(content().includes('81–100 of 100 papers'));
assert(content().includes('href="#sources?search=example&amp;year=2020&amp;page=4" rel="prev"'));
assert(!content().includes('rel="next"'));
manyApp.url();assert.equal(context.location.hash,'#sources?search=example&year=2020&page=5');
for(const page of ['-1','0','1.5','NaN','999999999999999999999']){
 context.location.hash='#sources?search=example&page='+page;manyApp.route();manyApp.render();
 assert.equal(manyApp.state.paperPage,1);
}
context.location.hash='#sources?search=example&page=100';manyApp.route();manyApp.render();
assert.equal(manyApp.state.paperPage,5);
context.location.hash='#sources?year=2020';manyApp.route();manyApp.render();
assert(content().includes('1–20 of 100 papers'));
context.location.hash='#sources?search=unmatched';manyApp.route();manyApp.render();
assert(content().includes('No papers match your search.'));
assert(!content().includes('class="paper-item"'));
assert(!content().includes('paper-pagination'));
context.location.hash='#sources';manyApp.route();manyApp.render();
assert.equal(manyApp.state.paperQuery,'');assert.equal(manyApp.state.paperYear,'');
assert(!content().includes('class="paper-item"'));
const unlinked=create({...many,papers:[{...many.papers[0],entryIds:[],title:'<script>unsafe</script>'}]},document);
unlinked.state.view='sources';unlinked.state.paperQuery='unsafe';unlinked.render();
assert(content().includes('No linked atlas entries.'));
assert(content().includes('&lt;script&gt;unsafe&lt;/script&gt;'));
assert(!content().includes('<script>'));
app.state.view='atlas';app.render();
for(const phrase of ['Gauge symmetry and the representations of matter','19 free parameters','infinitely many predictions','electron’s magnetic moment','Only complete specifications are included','catalogue grows both by adding models','bsm-ai-search','bsm-foundation-model'])assert(content().includes(phrase),phrase);
assert(content().includes('Supervised learning would turn collections of simulation outputs into a classification task: identifying their underlying gauge algebra and matter representation.'));
for(const route of ['#catalogue','#full-algebras','#cores','#entries'])assert(content().includes('href="'+route+'"'));
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
 assert(!content().includes('catalogue-back'));
}
// The global menu always opens a catalogue-wide view, never the current drill-down.
const menuHrefs=()=>Array.from(nodes.get('catalogue-views').innerHTML.matchAll(/href="([^"]+)"/g),m=>m[1].replaceAll('&amp;','&'));
const menuTargets=['#catalogue','#full-algebras','#cores','#entries'];
app.state.mode='dimensions';
for(const hash of [
 '#full-algebra/2198b5a34a3b9308100b195aa59bd4e51b773bf46ce03c92905a34b6ca973c54',
 '#full-algebras?semisimple='+smAlgebra,'#algebra/'+smAlgebra,
 '#core/'+core+'?fullAlgebra='+smFull.id,'#entry/vlq-t-singlet']){
 context.location.hash=hash;app.route();app.render();assert.deepEqual(menuHrefs(),menuTargets,hash);
 for(const target of menuHrefs()){
  context.location.hash=target;app.route();app.render();
  for(const key of ['core','fullAlgebra','semisimple','open'])assert.equal(app.state[key],'');
 }
 assert.equal(nodes.get('result-count').textContent,data.entries.length+' entries');
}
context.location.hash='#full-algebra/'+smFull.id+'?q=vector-like&paper=P15&abelianRank=1&notation=compare';
app.route();app.render();
for(const [i,href] of menuHrefs().entries()){
 const [target,query]=href.split('?');assert.equal(target,menuTargets[i]);
 const params=new URLSearchParams(query);
 for(const [key,value] of Object.entries({q:'vector-like',paper:'P15',abelianRank:'1',notation:'compare'}))assert.equal(params.get(key),value);
 for(const key of ['core','fullAlgebra','semisimple'])assert.equal(params.has(key),false);
}
context.location.hash='#algebra/'+smAlgebra+'?fullAlgebra='+smFull.id;
app.route();app.render();assert(results().includes('fullAlgebra='+smFull.id));
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
    if(!uiNodes.has(id))uiNodes.set(id,{events:new Map(),attributes:new Map(),setAttribute(name,value){this.attributes.set(name,value);},addEventListener(name,fn){this.events.set(name,fn);},
      contains(target){return Boolean(target.insideCatalogue);},querySelector(){return {focus(){triggerFocused=true;}};}});
    return uiNodes.get(id);
  }};
context.window={addEventListener(name,fn){windowEvents.set(name,fn);}};
context.localStorage={getItem(){return null;},setItem(){}};
const disclosure=create(data,uiDocument);disclosure.start();
assert.equal(uiNodes.get('atlas-favicon').attributes.get('href'),'favicon.svg?v=20261023-01');
assert.equal(uiNodes.get('theme-color').attributes.get('content'),'#ffffff');
uiNodes.get('theme-toggle').events.get('click')();
assert.equal(uiNodes.get('atlas-favicon').attributes.get('href'),'favicon-dark.svg?v=20261023-01');
assert.equal(uiNodes.get('theme-color').attributes.get('content'),'#1f1e1d');
uiNodes.get('theme-toggle').events.get('click')();
assert.equal(uiNodes.get('atlas-favicon').attributes.get('href'),'favicon.svg?v=20261023-01');
disclosure.state.browse='entries';disclosure.render();
const referenceClick={target:{closest(selector){return selector==='[data-open]'?{dataset:{open:'nmssm-matter'}}:null;}}};
uiNodes.get('view-content').events.get('click')(referenceClick);
assert.equal(disclosure.state.open,'nmssm-matter');
assert(uiNodes.get('model-entries').innerHTML.includes('Papers in chronological order'));
uiNodes.get('view-content').events.get('click')(referenceClick);
assert.equal(disclosure.state.open,'');
assert(!uiNodes.get('model-entries').innerHTML.includes('class="reference-list"'));
const menu=uiNodes.get('catalogue-menu');
menu.open=true;documentEvents.get('keydown')({key:'Escape',preventDefault(){escapePrevented=true;}});
assert.equal(menu.open,false);assert(triggerFocused);assert(escapePrevented);
menu.open=true;documentEvents.get('click')({target:{insideCatalogue:true}});assert.equal(menu.open,true);
documentEvents.get('click')({target:{}});assert.equal(menu.open,false);
menu.open=true;menu.events.get('click')({target:{closest(){return {};}}});assert.equal(menu.open,false);
menu.open=true;menu.events.get('focusout')({relatedTarget:{insideCatalogue:true}});assert.equal(menu.open,true);
menu.events.get('focusout')({relatedTarget:{}});assert.equal(menu.open,false);
menu.open=true;windowEvents.get('hashchange')();assert.equal(menu.open,false);

context.location.hash='#sources?search=example&year=2020&page=3';
windowEvents.get('hashchange')();
uiDocument.getElementById('paper-search').value='  singlet  ';uiDocument.getElementById('paper-year').value='';
let submitted=false;
uiNodes.get('view-content').events.get('submit')({target:{id:'paper-search-form'},preventDefault(){submitted=true;}});
assert(submitted);assert.equal(disclosure.state.paperQuery,'singlet');assert.equal(disclosure.state.paperPage,1);
assert.equal(context.location.hash,'#sources?search=singlet');
assert.equal(disclosure.state.q,'');
assert(uiNodes.get('view-content').innerHTML.includes('class="paper-item"'));
context.location.hash='#sources';windowEvents.get('hashchange')();
assert(!uiNodes.get('view-content').innerHTML.includes('class="paper-item"'));
uiNodes.get('paper-search').value=' ';uiNodes.get('paper-year').value='';
uiNodes.get('view-content').events.get('submit')({target:{id:'paper-search-form'},preventDefault(){}});
assert.equal(context.location.hash,'#sources');
assert(!uiNodes.get('view-content').innerHTML.includes('class="paper-item"'));

console.log('Catalogue views, bibliography search and pagination, notation, routes, references and disclosure checks passed.');
