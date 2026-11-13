import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {webcrypto} from 'node:crypto';
import {gzipSync} from 'node:zlib';
const website=new URL('../website/',import.meta.url);
const full=JSON.parse(fs.readFileSync(new URL('field-catalogue.json',website)));
const context={URL,URLSearchParams,TextEncoder,crypto:webcrypto,setTimeout,clearTimeout,location:{href:'https://atlas.test/',hash:'#full-algebras'},history:{replaceState(_s,_t,h){context.location.hash=h;}}};context.window=context;context.addEventListener=()=>{};
for(const name of ['atlas-bootstrap.js','atlas-store.js','field-matrix.js','problem-explorer.js','connection-explorer.js','field-catalogue.js'])vm.runInNewContext(fs.readFileSync(new URL(name,website),'utf8'),context);
const requests=[];let failure=null,delay=()=>0;
const fetcher=async url=>{
 const name=new URL(url).pathname.slice(1);requests.push(name);
 const milliseconds=delay(name);if(milliseconds)await new Promise(resolve=>setTimeout(resolve,milliseconds));
 if(failure?.name===name){const status=failure.status;failure=null;return {ok:false,status};}
 const target=new URL(name,website);if(!fs.existsSync(target))return {ok:false,status:404};
 const text=fs.readFileSync(target,'utf8');return {ok:true,status:200,text:async()=>text};
};
const open=()=>context.AtlasStore.open(context.ATLAS_MANIFEST_URL,{base:'https://atlas.test/',fetch:fetcher});
const store=await open();context.ATLAS_PROBLEMS=store.annotations.problems;context.ATLAS_MECHANISMS=store.annotations.mechanisms;
const initial=[...requests];
assert.equal(initial.length,4);
assert(initial.every(name=>name.startsWith('data/')));
assert(!initial.some(name=>/field-catalogue|problem-data|mechanism-data/.test(name)));
assert.equal(store.data.papers.length,0);
assert(store.data.entries.every(entry=>!entry.specification&&!entry.regime&&!entry.references));
assert(store.data.cores.every(core=>!core.regime));
assert.equal(store.data.entries.length,full.entries.length);
const bootstrapBytes=initial.reduce((n,name)=>n+fs.statSync(new URL(name,website)).size,0);
const bootstrapGzipBytes=initial.reduce((n,name)=>n+gzipSync(fs.readFileSync(new URL(name,website))).length,0);
assert(bootstrapGzipBytes<5*1024**2,'Bootstrap exceeded the compressed size budget');
const state={view:'catalogue',browse:'full-algebras',q:'',core:'',semisimple:'',fullAlgebra:'',paper:'',abelianRank:'',open:'',panel:'references',limit:20,referencePage:1,connections:{problems:[],mechanisms:[]}};
assert.equal(store.ensure(state),null);
const deep={...state,browse:'entries',open:store.data.entries.at(-1).id,panel:'problems'};
const deepRequirements=store.requirements(deep);
assert.equal(deepRequirements.bodies.length,21,'A deep entry link loaded every preceding model');
assert(deepRequirements.bodies.includes(deep.open));
assert.equal(store.visibleEntries(store.data.entries,deep).length,21);
const landing={...state,view:'sources',paperQuery:'',paperYear:'',paperPage:1};
await store.prepare(landing);assert.equal(requests.length,initial.length,'Opening Papers fetched the entire bibliography');
assert.equal(store.paperResults.total,0);

// Semisimple matter tables load separately, only for visible filtered cores.
const coreStore=await open(),coreState={...state,browse:'cores',limit:3};
const coreRequirements=coreStore.requirements(coreState);
assert.equal(coreRequirements.bodies.length,0);
assert.equal(coreRequirements.cores.length,3);
assert.equal(coreStore.ready(coreState),false);
await coreStore.prepare(coreState);
assert.equal(coreStore.ready(coreState),true);
assert.equal(coreStore.coreBodies.size,3);
for(const id of coreRequirements.cores){
 const core=coreStore.coreById.get(id),expected=full.cores.find(row=>row.id===id);
 assert.deepEqual(JSON.parse(JSON.stringify(core.regime)),expected.regime);
 assert(core.regime.coreRows.length>0);
 assert(core.regime.factors.every(factor=>factor.type!=='U1'));
}
const coreNodes=new Map(),coreDocument={getElementById(id){if(!coreNodes.has(id))coreNodes.set(id,{setAttribute(){}});return coreNodes.get(id);}};
const coreApp=context.FieldCatalogue.create(coreStore.data,coreDocument);
Object.assign(coreApp.state,coreState);coreApp.render();
const coreHTML=coreNodes.get('model-entries').innerHTML;
assert.equal((coreHTML.match(/class="representation-matrix core-matrix"/g)||[]).length,3);
assert(coreHTML.includes('<th>Multiplicity</th>'));
assert(coreHTML.includes('class="core-open"'));
assert(!coreHTML.includes('class="core-members"'));
assert(!coreHTML.includes('u(1)'));
const selected=coreStore.data.entries[0],filteredCores=coreStore.requirements({...coreState,core:selected.coreId});
assert.deepEqual(Array.from(filteredCores.cores),[selected.coreId]);
coreApp.state.browse='algebras';coreApp.render();
assert(!coreNodes.get('model-entries').innerHTML.includes('representation-matrix'));

// A model with many references loads only one reference page and visible tables.
const many=[...store.data.entries].sort((a,b)=>b.referenceCount-a.referenceCount)[0];
assert(many.referenceCount>20);
const opened={...state,browse:'entries',open:many.id,core:many.coreId};
await store.prepare(opened);
assert.equal(store.papers.size,20);
assert.equal(store.data.entries.find(e=>e.id===many.id).regime.baseline,full.entries.find(e=>e.id===many.id).regime.baseline);
const firstCount=requests.length;await store.prepare(opened);assert.equal(requests.length,firstCount,'Repeated page fetched cached records again');
await store.prepare({...opened,referencePage:2});assert.equal(store.papers.size,40);

// Existing routes render from lazy records; reference DOM is actually paged.
const nodes=new Map(),document={getElementById(id){if(!nodes.has(id))nodes.set(id,{setAttribute(){}});return nodes.get(id);}};
const app=context.FieldCatalogue.create(store.data,document);
context.location.hash='#entry/'+many.id;app.route();await store.prepare(app.state);app.render();
let html=nodes.get('model-entries').innerHTML;
const referenceList=/<ol class="reference-list"[^>]*>([\s\S]*?)<\/ol>/.exec(html)[1];
assert.equal((referenceList.match(/<li>/g)||[]).length,20);
assert(html.includes('data-reference-page="2"'));
for(const [alias,target] of [['minimal-atomic-dark-matter','atomic-dark-matter-secluded'],['minimal-left-right-model','lr-triplet-matter']]){
 context.location.hash='#entry/'+alias;app.route();assert.equal(app.state.open,target);
}

// Evidence fetches no quotation or paper metadata before disclosure.
const annotations=store.annotations.problems;
const [model,term]=Object.entries(annotations.linkCounts).flatMap(([id,terms])=>Object.entries(terms).filter(([,count])=>count>20).map(([term])=>[id,term]))[0];
const explorer=context.ProblemExplorer.create(store.data,annotations);
const beforeEvidence=requests.length;
assert(!explorer.evidence(model,term).includes('<blockquote>'));
assert(explorer.evidence(model,term).includes('data-lazy-evidence'));
assert.equal(requests.length,beforeEvidence);
const page=await store.loadEvidence('problems',model,term);
assert(page.rows.length<=20);assert(page.total>page.rows.length);
assert(explorer.evidence(model,term).includes('<blockquote>'));
assert(explorer.evidence(model,term).includes('data-evidence-page="2"'));
const next=await store.loadEvidence('problems',model,term,2);assert.equal(next.offset,page.rows.length);
assert.equal(store.annotations.problems.linkCounts[model][term],page.total);
const afterEvidence=requests.length;await store.loadEvidence('problems',model,term,2);assert.equal(requests.length,afterEvidence);

// Search is an indexed word-prefix intersection; bibliography loads by page.
await store.prepare({...landing,paperQuery:'2212.02487'});
assert.equal(store.paperResults.total,1);assert.equal(store.paperResults.rows[0].arxiv,'2212.02487v2');
await store.prepare({...landing,paperYear:'2020'});
const expected2020=full.papers.filter(p=>context.FieldCatalogue.arxivDate(p)?.year===2020).sort(context.FieldCatalogue.comparePapers);
assert.equal(store.paperResults.total,expected2020.length);
assert.deepEqual(Array.from(store.paperResults.rows,p=>p.id),expected2020.slice(0,20).map(p=>p.id));
await store.prepare({...landing,paperYear:'2020',paperPage:2});
assert.deepEqual(Array.from(store.paperResults.rows,p=>p.id),expected2020.slice(20,40).map(p=>p.id));
await store.prepare({...state,q:'su(5)'});
const found=context.FieldCatalogue.findEntries(store.data,{q:'su(5)'});
assert(found.length>0);assert(found.every(entry=>entry.algebraExpanded.includes('su(5)')));
const repeated=await store.search('su(2) su(2)','m');assert(repeated.length>0);assert(repeated.every(i=>store.data.entries[i].algebraExpanded.split(' ⊕ ').filter(factor=>factor==='su(2)').length>=2));

// A failed request is retryable; removed snapshot chunks require a reload.
const id=store.data.entries.at(-1).id,path=await store.recordPath('entries',id);
store.cache.delete(path);failure={name:path,status:503};await assert.rejects(store.record('entries',id),/retry/);
assert(await store.record('entries',id));
store.cache.delete(path);failure={name:path,status:404};await assert.rejects(store.record('entries',id),error=>error instanceof context.AtlasStore.SnapshotChangedError);
assert(await store.record('entries',id));

// The UI ignores old asynchronous search results after a newer query wins.
const fresh=await open(),directory=await fresh.json(fresh.manifest.search),slowPaths=new Set(await Promise.all(Array.from({length:directory.sup||0},(_,i)=>fresh.recordPath('search','sup\n'+i))));
delay=name=>slowPaths.has(name)?80:0;
const freshNodes=new Map(),freshDocument={getElementById(id){if(!freshNodes.has(id))freshNodes.set(id,{setAttribute(){}});return freshNodes.get(id);}};
context.ATLAS_PROBLEMS=fresh.annotations.problems;context.ATLAS_MECHANISMS=fresh.annotations.mechanisms;
const race=context.FieldCatalogue.create(fresh.data,freshDocument);race.state.browse='entries';race.state.q='supersymmetry';race.rows();
race.state.q='2212.02487';race.rows();
for(let i=0;i<100;i++){await new Promise(resolve=>setTimeout(resolve,10));if(!fresh.pending.size&&!fresh.queries.size)break;}
html=freshNodes.get('model-entries').innerHTML;assert(html.includes('Secluded atomic dark matter'));assert(!html.includes('Loading…'));
assert.equal(race.state.q,'2212.02487');
console.log(`Lazy catalogue: ${bootstrapBytes.toLocaleString()} bootstrap bytes; paged references/evidence, indexed search, retries, aliases and stale-request handling passed.`);

// Execute the actual bundled search code in a separate JavaScript thread.
const {Worker:ThreadWorker}=await import('node:worker_threads');
class BrowserWorker{
 constructor(url){
  const filename=new URL(new URL(url).pathname.slice(1),website).pathname;
  const program=`const {parentPort}=require('node:worker_threads'),fs=require('node:fs'),vm=require('node:vm');
   global.self=global;global.postMessage=data=>parentPort.postMessage(data);
   global.fetch=async url=>{const file=new URL(new URL(url).pathname.slice(1),${JSON.stringify(website.href)});parentPort.postMessage({resource:new URL(url).pathname});return fs.existsSync(file)?{ok:true,status:200,text:async()=>fs.readFileSync(file,'utf8')}:{ok:false,status:404};};
   vm.runInThisContext(fs.readFileSync(${JSON.stringify(filename)},'utf8'));
   parentPort.on('message',data=>global.onmessage({data}));`;
  this.requests=[];this.thread=new ThreadWorker(program,{eval:true});
  this.thread.on('message',data=>{if(data.resource)this.requests.push(data.resource);else this.onmessage?.({data});});
  this.thread.on('error',error=>this.onerror?.(error));
 }
 postMessage(data){this.thread.postMessage(data);}
 terminate(){return this.thread.terminate();}
}
context.Worker=BrowserWorker;
const threaded=await open();
try{
 const before=requests.length,rows=await threaded.search('2212.02487','p');
 assert.equal(rows.length,1);assert(threaded.worker.requests.length>0);
 assert.equal(requests.length,before,'Worker search downloaded indexes on the rendering thread');
 const selected=await threaded.search('su(5)','m');assert(selected.length>0);
 assert(selected.every(i=>threaded.data.entries[i].algebraExpanded.includes('su(5)')));
}finally{await threaded.worker?.terminate();}
context.Worker=class{constructor(){throw new Error('Workers unavailable');}};
const fallback=await open();assert.equal((await fallback.search('2212.02487','p')).length,1);assert.equal(fallback.useWorker,false);
delete context.Worker;
console.log('Actual search-worker execution and worker-unavailable fallback passed.');

// Disclosure and pagination controls invoke the lazy loader, not just its API.
class Element{
 constructor(){this.events=new Map();this.innerHTML='';}
 addEventListener(type,callback){if(!this.events.has(type))this.events.set(type,[]);this.events.get(type).push(callback);}
 setAttribute(){}
}
const controls=new Map(),controlDocument={documentElement:{dataset:{}},getElementById(id){if(!controls.has(id))controls.set(id,new Element());return controls.get(id);},querySelectorAll(){return [];}};
context.ATLAS_PROBLEMS=store.annotations.problems;context.ATLAS_MECHANISMS=store.annotations.mechanisms;context.location.hash='#problems';
const controlled=context.FieldCatalogue.create(store.data,controlDocument);controlled.start();
const holder={dataset:{evidenceKind:'problems',evidenceEntry:model,evidenceTerm:term},isConnected:true,innerHTML:'',outerHTML:''};
for(const listener of controls.get('view-content').events.get('toggle'))listener({target:{open:true,querySelectorAll(){return [holder];}}});
for(let i=0;i<100&&!holder.outerHTML.includes('<blockquote>');i++)await new Promise(resolve=>setTimeout(resolve,1));
assert(holder.outerHTML.includes('<blockquote>'));assert.equal(store.evidencePage('problems',model,term).page,1);
const nextButton={dataset:{evidencePage:'2'},closest(selector){return selector==='[data-evidence-page]'?this:selector==='[data-lazy-evidence]'?holder:null;}};
for(const listener of controls.get('view-content').events.get('click'))listener({target:nextButton,preventDefault(){}});
for(let i=0;i<100&&store.evidencePage('problems',model,term).page!==2;i++)await new Promise(resolve=>setTimeout(resolve,1));
assert.equal(store.evidencePage('problems',model,term).page,2);
// Even simultaneous disclosures cannot lose metadata to the general LRU.
store.papers.clear();assert(explorer.evidence(model,term).includes('<blockquote>'));
assert(explorer.evidence(model,term).includes('arXiv:'));
console.log('Disclosure events, evidence page controls and pinned page metadata passed.');

// Browsing does not keep every previously opened field table in memory.
const bounded=await context.AtlasStore.open(context.ATLAS_MANIFEST_URL,{base:'https://atlas.test/',fetch:fetcher,cacheBytes:4096});
const openedIds=bounded.data.entries.slice(0,90).map(entry=>entry.id);
await Promise.all(openedIds.map(id=>bounded.body(id)));bounded.trimBodies(openedIds.slice(-20));
assert.equal(bounded.bodies.size,64);
assert(openedIds.slice(-20).every(id=>bounded.byId.get(id).regime));
assert(!bounded.byId.get(openedIds[0]).regime);
assert(bounded.bytes<=bounded.maxBytes||bounded.cache.size===1);
await bounded.body(openedIds[0]);assert(bounded.byId.get(openedIds[0]).regime);
const coreIds=bounded.data.cores.slice(0,90).map(core=>core.id);
await Promise.all(coreIds.map(id=>bounded.coreBody(id)));bounded.trimCoreBodies(coreIds.slice(-20));
assert.equal(bounded.coreBodies.size,64);
assert(coreIds.slice(-20).every(id=>bounded.coreById.get(id).regime));
assert(!bounded.coreById.get(coreIds[0]).regime);
await bounded.coreBody(coreIds[0]);assert(bounded.coreById.get(coreIds[0]).regime);
console.log('Bounded decoded-chunk and materialized-model caches reload evicted records correctly.');
