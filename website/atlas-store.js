/* Immutable static snapshot with demand-loaded records and bounded caches. */
(function(root){
 'use strict';
 const normalize=s=>String(s??'').normalize('NFD').replace(/\p{M}/gu,'').toLowerCase();
 const words=s=>[...new Set(normalize(s).replace(/(?:https?:\/\/arxiv\.org\/abs\/|arxiv:\s*)/g,'').match(/[\p{L}\p{N}]+/gu)||[])];
 function routeHash(value){let hash=2166136261;for(const byte of new TextEncoder().encode(value))hash=Math.imul(hash^byte,16777619)>>>0;return hash.toString(16).padStart(8,'0');}
 class SnapshotChangedError extends Error{constructor(message){super(message);this.name='SnapshotChangedError';}}
 class Store{
  constructor(manifest,base,fetcher,options={}){
   this.manifest=manifest;this.base=base;this.fetcher=fetcher;this.cache=new Map();this.pending=new Map();this.bytes=0;this.maxBytes=options.cacheBytes||8*1024*1024;
   this.papers=new Map();this.bodies=new Map();this.coreBodies=new Map();this.searches=new Map();this.evidence=new Map();this.queries=new Map();this.paperResults=null;this.useWorker=options.worker!==false;this.workerCalls=new Map();this.workerSequence=0;
  }
  async json(path){
   if(this.cache.has(path)){const item=this.cache.get(path);this.cache.delete(path);this.cache.set(path,item);return item.value;}
   if(this.pending.has(path))return this.pending.get(path);
   const request=(async()=>{
    const response=await this.fetcher(new URL(path,this.base).href);
    if(!response.ok){if(response.status===404)throw new SnapshotChangedError('The catalogue has been updated. Reload to continue.');throw new Error('Could not load the catalogue. Please retry.');}
    const text=await response.text(),raw=new TextEncoder().encode(text),match=/([a-f0-9]{64})\.json$/.exec(path);
    if(match&&root.crypto?.subtle){const hash=Array.from(new Uint8Array(await root.crypto.subtle.digest('SHA-256',raw)),n=>n.toString(16).padStart(2,'0')).join('');if(hash!==match[1])throw new SnapshotChangedError('The catalogue has been updated. Reload to continue.');}
    const value=JSON.parse(text);this.cache.set(path,{value,bytes:raw.length});this.bytes+=raw.length;
    while(this.bytes>this.maxBytes&&this.cache.size>1){const key=this.cache.keys().next().value;this.bytes-=this.cache.get(key).bytes;this.cache.delete(key);}
    return value;
   })();
   this.pending.set(path,request);try{return await request;}finally{this.pending.delete(path);}
  }
  async recordPath(kind,id){const routes=await this.json(this.manifest.records[kind]),hash=parseInt(routeHash(id),16).toString(2).padStart(32,'0');for(let n=0;n<=32;n++){const prefix=hash.slice(0,n);if(Object.hasOwn(routes,prefix))return routes[prefix];}throw new Error('Record is missing from this snapshot.');}
  async record(kind,id){const rows=await this.json(await this.recordPath(kind,id));if(!Object.hasOwn(rows,id))throw new Error('Record is missing from this snapshot.');return rows[id];}
  async paper(id){if(this.papers.has(id)){const value=this.papers.get(id);this.papers.delete(id);this.papers.set(id,value);return value;}const value=await this.record('papers',id);this.papers.set(id,value);while(this.papers.size>600)this.papers.delete(this.papers.keys().next().value);return value;}
  async body(id){if(this.bodies.has(id)){const row=this.bodies.get(id);this.bodies.delete(id);this.bodies.set(id,row);return;}const row=await this.record('entries',id);Object.assign(this.byId.get(id),row);this.bodies.set(id,row);}
  async coreBody(id){if(this.coreBodies.has(id)){const row=this.coreBodies.get(id);this.coreBodies.delete(id);this.coreBodies.set(id,row);return;}const row=await this.record('cores',id);Object.assign(this.coreById.get(id),row);this.coreBodies.set(id,row);}
  trimCoreBodies(active){const pinned=new Set(active);for(const [id] of this.coreBodies){if(this.coreBodies.size<=Math.max(64,pinned.size))break;if(pinned.has(id))continue;delete this.coreById.get(id).regime;this.coreBodies.delete(id);}}
  trimBodies(active){const pinned=new Set(active);for(const [id] of this.bodies){if(this.bodies.size<=Math.max(64,pinned.size))break;if(pinned.has(id))continue;const entry=this.byId.get(id);for(const key of ['specification','regime','referenceParameters','properties'])delete entry[key];this.bodies.delete(id);}}
  workerSearch(query,kind){
   if(!this.worker){
    try{this.worker=new root.Worker(new URL(this.manifest.searchWorker,this.base).href);}catch(error){this.useWorker=false;return Promise.reject(error);}
    this.worker.onmessage=event=>{const {id,rows,error}=event.data,request=this.workerCalls.get(id);if(!request)return;this.workerCalls.delete(id);if(error)request.reject(error.name==='SnapshotChangedError'?new SnapshotChangedError(error.message):new Error(error.message));else request.resolve(rows);};
    this.worker.onerror=()=>{this.useWorker=false;this.worker?.terminate();this.worker=null;for(const request of this.workerCalls.values())request.reject(new Error('Search worker unavailable'));this.workerCalls.clear();};
    this.worker.postMessage({type:'init',manifest:this.manifest,base:this.base.href,entries:this.data.entries.map(entry=>({algebraExpanded:entry.algebraExpanded}))});
   }
   const id=++this.workerSequence;return new Promise((resolve,reject)=>{this.workerCalls.set(id,{resolve,reject});this.worker.postMessage({type:'search',id,query,kind});});
  }
  rememberSearch(key,rows){
   this.searches.set(key,rows);
   let count=[...this.searches.values()].reduce((n,value)=>n+value.length,0);
   while(this.searches.size>1&&(this.searches.size>40||count>250000)){const old=this.searches.keys().next().value;count-=this.searches.get(old).length;this.searches.delete(old);}
   return rows;
  }
  async search(query,kind){
   const key=kind+'\n'+normalize(query).trim();if(this.searches.has(key))return this.searches.get(key);
   if(this.queries.has(key))return this.queries.get(key);
   const request=(async()=>{
    if(this.useWorker&&root.Worker&&this.manifest.searchWorker){
     try{return this.rememberSearch(key,await this.workerSearch(query,kind));}
     catch(error){if(this.useWorker)throw error;}
    }
    const groups=[];let text=query;
    if(kind==='m')text=text.replace(/\b(su|so|sp|u)\s*\(\s*(\d+)\s*\)/gi,(_s,a,n)=>{groups.push(a.toLowerCase()+'('+n+')');return ' ';});
    const queryWords=words(text),directory=queryWords.length?await this.json(this.manifest.search):{};
    let matched=null;
    for(const word of queryWords){
     const keys=Object.entries(directory).filter(([prefix])=>word.length>=3?prefix===word.slice(0,3):prefix.startsWith(word)).flatMap(([prefix,count])=>Array.from({length:count},(_,i)=>prefix+'\n'+i));
     const values=new Set();for(const block of await Promise.all(keys.map(key=>this.record('search',key))))for(const [token,postings] of Object.entries(block))if(token.startsWith(word))for(const id of postings[kind])values.add(id);
     matched=matched===null?values:new Set([...matched].filter(id=>values.has(id)));if(!matched.size)break;
    }
    if(matched===null)matched=new Set(kind==='m'?this.data.entries.map((_e,i)=>i):[]);
    if(groups.length){const counts=new Map();for(const group of groups)counts.set(group,(counts.get(group)||0)+1);matched=new Set([...matched].filter(id=>{const factors=this.data.entries[id].algebraExpanded.split(' ⊕ ');return [...counts].every(([group,count])=>factors.filter(factor=>factor===group).length>=count);}));}
    const result=[...matched].sort((a,b)=>a-b);return this.rememberSearch(key,result);
   })();this.queries.set(key,request);try{return await request;}finally{this.queries.delete(key);}
  }
  entryMatches(query,id){return !query.trim()||this.entryQuery?.query===query&&this.entryQuery.ids.has(id);}
  filtered(state){
   const q=state.q||'',selected=state.connections||{};
   return this.data.entries.filter(e=>root.FieldCatalogue.matchesProperties(e,state)&&(!q||this.entryMatches(q,e.id))&&(!state.core||e.coreId===state.core)&&(!state.semisimple||e.semisimpleId===state.semisimple)&&(!state.fullAlgebra||e.fullAlgebraId===state.fullAlgebra)&&(!state.paper||e.paperIds.includes(state.paper))&&(state.abelianRank===''||state.abelianRank===undefined||String(e.abelianRank)===String(state.abelianRank))&&(!state.algebra||(state.algebra.startsWith('na:')?this.data.semisimpleAlgebras.some(a=>a.id===e.semisimpleId&&a.algebraSignature===state.algebra.slice(3)):e.algebraSignature===state.algebra))&&['problems','mechanisms'].every(kind=>(selected[kind]||[]).every(term=>Object.hasOwn(this.annotations[kind].links[e.id]||{},term))));
  }
  visibleEntries(entries,state){const visible=entries.slice(0,state.limit||20),opened=entries.find(entry=>entry.id===state.open);if(opened&&!visible.includes(opened))visible.push(opened);return visible;}
  requirements(state){
   if(state.view!=='catalogue')return {bodies:[],cores:[],papers:[]};
   const entries=this.filtered(state),visible=state.browse==='entries'?this.visibleEntries(entries,state):[];
   const matched=new Set(entries.map(entry=>entry.id)),cores=state.browse==='cores'?this.data.cores.filter(core=>core.entryIds.some(id=>matched.has(id))).slice(0,state.limit||20):[];
   const paperIds=state.paper?[state.paper]:[],entry=this.byId.get(state.open);
   if(entry&&state.panel==='references'){const pages=Math.max(1,Math.ceil(entry.paperIds.length/20)),page=Math.min(Math.max(1,state.referencePage||1),pages);paperIds.push(...entry.paperIds.slice((page-1)*20,page*20));}
   return {bodies:visible.map(e=>e.id),cores:cores.map(core=>core.id),papers:[...new Set(paperIds)]};
  }
  ready(state){
   if(state.view==='sources')return this.paperKey===JSON.stringify([state.paperQuery,state.paperYear,state.paperPage])&&this.paperResults?.rows.every(p=>this.papers.has(p.id));
   if(state.view==='catalogue'&&state.q&&this.entryQuery?.query!==state.q)return false;
   const needed=this.requirements(state);return needed.bodies.every(id=>this.bodies.has(id))&&needed.cores.every(id=>this.coreBodies.has(id))&&needed.papers.every(id=>this.papers.has(id));
  }
  ensure(state){this.select(state);if(state.q){const cached=this.searches.get('m\n'+normalize(state.q).trim());if(cached)this.entryQuery={query:state.q,ids:new Set(cached.map(i=>this.data.entries[i].id))};}if(this.ready(state))return null;const copy=JSON.parse(JSON.stringify(state));return this.prepare(copy);}
  async prepare(state){
   if(state.view==='sources'){
    const query=state.paperQuery?.trim(),year=state.paperYear;
    if(!query&&!year){const key=JSON.stringify([state.paperQuery,state.paperYear,state.paperPage]);this.paperResults={rows:[],total:0,pages:1,page:1};this.paperResultCache??=new Map();this.paperResultCache.set(key,this.paperResults);this.paperKey=key;return;}
    const order=await this.json(this.manifest.paperOrder);
    let ids=query?await this.search(query,'p'):year?Array.from({length:(order.years[year]?.[1]||0)-(order.years[year]?.[0]||0)},(_,i)=>(order.years[year]?.[0]||0)+i):[];
    if(year){const range=order.years[year]||[0,0];ids=ids.filter(id=>id>=range[0]&&id<range[1]);}
    const pages=Math.max(1,Math.ceil(ids.length/20)),page=Math.min(Math.max(1,state.paperPage||1),pages),visible=ids.slice((page-1)*20,page*20);
    const rows=await Promise.all(visible.map(id=>this.paper(order.ids[id])));
    // Prepared results are keyed to their request; the render generation guard
    // prevents an older request from overwriting a newer visible result.
    const key=JSON.stringify([state.paperQuery,state.paperYear,state.paperPage]);
    this.paperResultCache??=new Map();this.paperResultCache.set(key,{rows,total:ids.length,pages,page});while(this.paperResultCache.size>8)this.paperResultCache.delete(this.paperResultCache.keys().next().value);
    this.paperKey=key;this.paperResults=this.paperResultCache.get(key);return;
   }
   if(state.view==='catalogue'&&state.q){const ordinals=await this.search(state.q,'m');this.entryQuery={query:state.q,ids:new Set(ordinals.map(i=>this.data.entries[i].id))};}
   const needed=this.requirements(state);await Promise.all([...needed.bodies.map(id=>this.body(id)),...needed.cores.map(id=>this.coreBody(id)),...needed.papers.map(id=>this.paper(id))]);this.trimBodies(needed.bodies);this.trimCoreBodies(needed.cores);
  }
  select(state){if(state.view==='sources'){const key=JSON.stringify([state.paperQuery,state.paperYear,state.paperPage]);const result=this.paperResultCache?.get(key);if(result){this.paperKey=key;this.paperResults=result;}}}
  evidencePage(kind,id,term){return this.evidence.get([kind,id,term].join('\n'));}
  async loadEvidence(kind,id,term,page=1){
   if(!['problems','mechanisms'].includes(kind)||!Object.hasOwn(this.annotations[kind].links[id]||{},term))throw new Error('Unknown source association.');
   const maximum=this.annotations[kind].pageCounts[id][term];page=Math.min(Math.max(1,Number(page)||1),maximum);
   const value=await this.record('evidence_'+kind,[id,term,String(page)].join('\n'));
   const records=await Promise.all([...new Set(value.rows.map(row=>row.paperId))].map(key=>this.paper(key)));
   const pageValue={...value,paperRecords:new Map(records.map(paper=>[paper.id,paper]))};
   const key=[kind,id,term].join('\n');this.evidence.delete(key);this.evidence.set(key,pageValue);while(this.evidence.size>32)this.evidence.delete(this.evidence.keys().next().value);return pageValue;
  }
 }
 async function open(manifestURL,options={}){
  const absolute=new URL(manifestURL,options.base||root.location?.href||'http://localhost/'),base=new URL('../',absolute);
  const store=new Store(null,base,options.fetch||root.fetch.bind(root),options),manifest=await store.json(absolute.href);
  if(manifest.schema_version!=='atlas-static-1')throw new Error('Unsupported catalogue snapshot.');store.manifest=manifest;
  const [data,problems,mechanisms]=await Promise.all([store.json(manifest.catalogue),store.json(manifest.annotations.problems),store.json(manifest.annotations.mechanisms)]);
  store.data=data;store.annotations={problems,mechanisms};store.byId=new Map(data.entries.map(e=>[e.id,e]));store.coreById=new Map(data.cores.map(core=>[core.id,core]));
  Object.defineProperty(data,'_store',{value:store});return store;
 }
 root.AtlasStore={open,routeHash,words,SnapshotChangedError,searchEngine:(manifest,base,entries)=>{const store=new Store(manifest,new URL(base),root.fetch.bind(root),{worker:false});store.data={entries};return store;}};
})(typeof window==='undefined'?globalThis:window);
