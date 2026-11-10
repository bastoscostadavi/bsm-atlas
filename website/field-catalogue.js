(function(root){
 'use strict';
 const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
 const math=x=>esc(x).replace(/bar\(([^()]*)\)/g,(_,label)=>'<span class="rep-conjugate" aria-label="conjugate '+label+'">'+label+'</span>');
 const shorthand=x=>({'g_SM':'𝔤<sub>SM</sub>','R_SM':'R<sub>SM</sub>','F_SM':'F<sub>SM</sub>','H_SM':'H<sub>SM</sub>','R_MSSM':'R<sub>MSSM</sub>'}[x]||math(x));
 const notationModes={dimensions:'Dimensions',dynkin:'Dynkin labels',young:'Young diagrams',compare:'Compare notations'};
 const sourceURL=p=>'https://arxiv.org/abs/'+p.arxiv;
 const months=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
 function arxivDate(paper){
   const id=paper.arxiv.replace(/v[1-9]\d*$/,'');
   const modern=/^(\d{2})(\d{2})\.(\d{4,5})$/.exec(id);
   const legacy=/^([a-z-]+)\/(\d{2})(\d{2})(\d{3})$/.exec(id);
   if(!modern&&!legacy)return null;
   const yy=Number(modern?modern[1]:legacy[2]),month=Number(modern?modern[2]:legacy[3]);
   if(month<1||month>12)return null;
   const year=modern?(yy<7?2100:2000)+yy:(yy>=91?1900:2000)+yy;
   return {year,month,sequence:Number(modern?modern[3]:legacy[4]),archive:modern?'':legacy[1],
     value:year+'-'+String(month).padStart(2,'0'),label:months[month-1]+' '+year};
 }
 function comparePapers(a,b){
   const x=arxivDate(a),y=arxivDate(b);
   // Old-style sequences are comparable only within the same archive.
   return (x?.year??Infinity)-(y?.year??Infinity)||(x?.month??Infinity)-(y?.month??Infinity)||
     (x?.archive||'').localeCompare(y?.archive||'')||(x?.sequence??Infinity)-(y?.sequence??Infinity)||
     a.arxiv.replace(/v[1-9]\d*$/,'').localeCompare(b.arxiv.replace(/v[1-9]\d*$/,''))||a.title.localeCompare(b.title);
 }
 const paperDate=p=>{const date=arxivDate(p);return date?'<time datetime="'+date.value+'">'+date.label+'</time>':'';};
 const searchText=value=>String(value??'').normalize('NFD').replace(/\p{M}/gu,'').toLowerCase().replace(/\s+/g,' ').trim();
 function findPapers(papers,{q='',year=''}={}){
   const terms=searchText(q).replace(/(?:https?:\/\/arxiv\.org\/abs\/|arxiv:\s*)/g,'').split(' ').filter(Boolean);
   if(!terms.length&&!year)return [];
   return papers.filter(p=>{
     if(year&&String(arxivDate(p)?.year)!==String(year))return false;
     const text=searchText([p.title,p.authors,p.arxiv].join(' '));
     return terms.every(term=>text.includes(term));
   });
 }
 const entryTextIndexes=new WeakMap();
 function findEntries(data,{q='',algebra='',paper='',core='',semisimple='',fullAlgebra='',abelianRank=''}={}){
   const needle=q.trim().toLowerCase();let index;
   if(needle&&!data._store){
     index=entryTextIndexes.get(data);
     if(!index){const papers=new Map(data.papers.map(p=>[p.id,p]));index=new Map(data.entries.map(e=>[e.id,[e.id,e.name,...(e.aliases||[]).flatMap(a=>[a.id,a.name]),e.algebraExpanded,JSON.stringify(e.specification),...e.paperIds,...e.paperIds.flatMap(id=>{const p=papers.get(id);return p?[p.title,p.authors,p.arxiv]:[];})].join(' ').toLowerCase()]));entryTextIndexes.set(data,index);}
   }
   return data.entries.filter(e=>(!core||e.coreId===core)&&(!semisimple||e.semisimpleId===semisimple)&&(!fullAlgebra||e.fullAlgebraId===fullAlgebra)&&(abelianRank===''||String(e.abelianRank)===String(abelianRank))&&(!algebra||(algebra.startsWith('na:')?data.semisimpleAlgebras.some(a=>a.id===e.semisimpleId&&a.algebraSignature===algebra.slice(3)):e.algebraSignature===algebra))&&(!paper||e.paperIds.includes(paper))&&(!needle||(data._store?data._store.entryMatches(q,e.id):index.get(e.id).includes(needle))));
 }
 const dynkinLabel=c=>c.factor==='u(1)'?String(c.value??'?'):c.dynkin?'['+c.dynkin.join(',')+']':'?';
 function dynkinTuple(components){
   if(!components.length)return '?';
   const nonabelian=components.filter(c=>c.factor!=='u(1)').map(dynkinLabel),charges=components.filter(c=>c.factor==='u(1)').map(dynkinLabel);
   return '('+nonabelian.join(', ')+(charges.length?'; '+charges.join(', '):'')+')';
 }
 function young(component){
   if(!component.youngRows)return '<span class="young-caption">'+esc(component.factor)+': Young diagram unavailable</span>';
   if(!component.youngRows.length)return '<span class="young-component"><span class="young-caption">'+esc(component.factor)+'</span><span class="math" title="Trivial representation: empty Young diagram">1</span></span>';
   const rows=component.youngRows;
   return '<span class="young-component"><span class="young-caption">'+esc(component.factor)+'</span><span class="young-shape" data-young-rows="'+esc(JSON.stringify(rows))+'">'+esc('rows ['+rows.join(',')+']')+'</span></span>';
 }
 function dimensionTuple(components){
   const ns=components.filter(c=>c.factor!=='u(1)').map(c=>c.value??'?'),qs=components.filter(c=>c.factor==='u(1)').map(c=>c.value??'?');
   return '('+ns.join(', ')+(qs.length?'; '+qs.join(', '):'')+')';
 }
 function representationMarkup(components,mode,bundle=true){
   if(!components.length)return '<span class="unresolved" title="Gauge algebra and representation unresolved">?</span>';
   const d=bundle?dimensionTuple(components):(components[0].value??'?');
   const exact=bundle?dynkinTuple(components):dynkinLabel(components[0]);
   const weights='<span class="math" title="'+esc(components.some(c=>c.factor!=='u(1)'&&!c.dynkin)?'Dynkin labels':'Highest-weight Dynkin labels')+'">'+esc(exact)+'</span>';
   const readable='<span class="math" title="Dynkin labels: '+esc(exact)+'">'+math(d)+'</span>';
   const diagrams='<span class="young-block">'+components.map(c=>c.factor==='u(1)'?'<span class="young-charge">'+esc(c.value??'?')+'</span>':young(c)).join('')+'</span>';
   if(mode==='dynkin')return weights;
   if(mode==='young')return diagrams;
   if(mode==='compare')return '<div class="representation-compare">'+readable+'<span class="dynkin-alternative"><span class="notation-label">Dynkin</span>'+weights+'</span>'+diagrams+'</div>';
   return readable;
 }
 function templateTable(template){return '<div class="matrix-wrap"><table class="template-table" aria-label="'+esc(template.name)+' reference"><thead><tr><th>Spacetime</th><th>𝔤<sub>SM</sub> · dimensions / Dynkin</th><th>Multiplicity</th></tr></thead><tbody>'+template.rows.map(row=>'<tr><td class="math">'+esc(row.lorentz.label).replaceAll('1/2','½')+'</td><td>'+representationMarkup(row.components,'dimensions')+'<span class="baseline-dynkin math">'+esc(dynkinTuple(row.components))+'</span></td><td>'+row.copies+'</td></tr>').join('')+'</tbody></table></div>';}

 function create(data,document){
   const state={q:'',algebra:'',paper:'',open:'',panel:'references',mode:'dimensions',view:'catalogue',browse:'full-algebras',core:'',semisimple:'',fullAlgebra:'',abelianRank:'',baselineOpen:{},limit:20,paperQuery:'',paperYear:'',paperPage:1,referencePage:1,problem:'',problemQuery:'',problemCategory:'',problemLayer:false,problemLimit:20,connections:{problems:[],mechanisms:[],view:'problems',q:'',filterQuery:'',limit:20}};
   const problemExplorer=root.ProblemExplorer?.create(data,root.ATLAS_PROBLEMS);
   const mechanismExplorer=root.MechanismExplorer?.create(data,root.ATLAS_MECHANISMS);
   const connectionExplorer=root.ConnectionExplorer?.create(data,root.ATLAS_PROBLEMS,root.ATLAS_MECHANISMS);
   const papersPerPage=20;
   const paperById=data._store?.papers||new Map(data.papers.map(p=>[p.id,p]));
   const orderedPapers=[...data.papers].sort(comparePapers);
   const coreById=new Map((data.cores||[]).map(c=>[c.id,c]));
   const algebraById=new Map((data.semisimpleAlgebras||[]).map(a=>[a.id,a]));
   const fullAlgebraById=new Map((data.fullAlgebras||[]).map(a=>[a.id,a]));
   const entryById=new Map(data.entries.map(e=>[e.id,e]));
   const entryOrder=new Map(data.entries.map((e,i)=>[e.id,i]));
   const orderedEntryIds=ids=>[...ids].sort((a,b)=>(entryOrder.get(a)??Infinity)-(entryOrder.get(b)??Infinity));
   for(const e of data.entries)for(const a of e.aliases||[])entryById.set(a.id,e);
   let renderGeneration=0,entrySearchTimer;
   function defer(action){
     const generation=++renderGeneration;
     if(!data._store)return false;
     const pending=data._store.ensure(state);
     if(!pending)return false;
     const container=document.getElementById('model-entries')||document.getElementById('view-content');
     container.setAttribute?.('aria-busy','true');
     container.innerHTML='<p class="subtle" role="status">Loading…</p>';
     pending.then(()=>{if(generation===renderGeneration){container.setAttribute?.('aria-busy','false');action();}}).catch(error=>{
       if(generation!==renderGeneration)return;
       const reload=error instanceof root.AtlasStore.SnapshotChangedError;
       container.setAttribute?.('aria-busy','false');
       container.innerHTML='<p class="empty" role="alert">'+esc(error.message)+' <button type="button" class="text-button" '+(reload?'data-reload-catalogue':'data-load-retry')+'>'+(reload?'Reload catalogue':'Retry')+'</button></p>';
     });return true;
   }
   function downloadLink(name){return data.downloads?.[name]||({catalogue:'catalogue.json',sqlite:'downloads/field-catalogue.sqlite'}[name]||'downloads/'+name+'.csv');}
   function route(){
     ++renderGeneration;root.clearTimeout?.(entrySearchTimer);state.referencePage=1;
     const [raw,query='']=location.hash.slice(1).split('?');
     const p=new URLSearchParams(query);
     if(p.has('notation'))state.mode=Object.hasOwn(notationModes,p.get('notation'))?p.get('notation'):'dimensions';
     state.view=raw==='about'?'atlas':raw==='problems'||raw.startsWith('problems/')?'problems':raw==='mechanisms'||raw.startsWith('mechanisms/')?'mechanisms':['atlas','notation','sources'].includes(raw)?raw:'catalogue';
     if(connectionExplorer)state.connections=connectionExplorer.parse(location.hash);
     state.panel=['problems','mechanisms'].includes(p.get('panel'))?p.get('panel'):'references';
     state.problemLayer=['problems','mechanisms'].includes(state.view)&&p.get('about')==='layer';
     if(state.view==='problems'){
       state.problem=raw.startsWith('problems/')?decodeURIComponent(raw.slice(9)):'';
       state.problemQuery=(p.get('search')||'').trim();
       state.problemCategory=p.get('category')||'';
       state.problemLimit=20;
     }
     if(state.view==='sources'){
       state.paperQuery=(p.get('search')||'').trim();
       state.paperYear=p.get('year')||'';
       const page=Number(p.get('page'));
       state.paperPage=Number.isSafeInteger(page)&&page>0?page:1;
     }
     state.browse=raw==='entries'||/^(entry|model|core|full-algebra)\//.test(raw)?'entries':raw==='full-algebras'?'full-algebras':raw==='cores'||raw.startsWith('algebra/')?'cores':raw==='catalogue'?'algebras':'full-algebras';
     state.core=raw.startsWith('core/')?decodeURIComponent(raw.slice(5)):p.get('core')||'';
     state.fullAlgebra=raw.startsWith('full-algebra/')?decodeURIComponent(raw.slice(13)):p.get('fullAlgebra')||'';
     state.semisimple=raw.startsWith('algebra/')?decodeURIComponent(raw.slice(8)):p.get('semisimple')||'';
     state.open='';
     if(raw.startsWith('entry/'))state.open=decodeURIComponent(raw.slice(6));
     if(raw.startsWith('model/')){
       const id=decodeURIComponent(raw.split('/')[1]);
       state.open=entryById.get(id)?.id||'';
     }
     for(const key of ['q','algebra','paper','abelianRank'])state[key]=p.get(key)||'';
     if(state.open&&!state.core)state.core=entryById.get(state.open)?.coreId||'';
     if(state.core)state.semisimple=coreById.get(state.core)?.semisimpleId||'';
     else if(state.open)state.semisimple=entryById.get(state.open)?.semisimpleId||'';
     else if(state.fullAlgebra)state.semisimple=fullAlgebraById.get(state.fullAlgebra)?.semisimpleId||'';
     if(entryById.has(state.open))state.open=entryById.get(state.open).id;

   }
   function appendConnections(p){
     state.connections.problems.forEach(id=>p.append('problem',id));
     state.connections.mechanisms.forEach(id=>p.append('mechanism',id));
   }
   function currentEntries(){
     const entries=findEntries(data,state);
     return connectionExplorer?connectionExplorer.filterEntries(entries,state.connections):entries;
   }
   function url(){
     if(connectionExplorer&&['problems','mechanisms'].includes(state.view)){
       history.replaceState(null,'',connectionExplorer.url(state.connections));return;
     }
     if(state.view==='problems'){
       history.replaceState(null,'',problemExplorer.problemLink(state.problem,state.problemQuery,state.problemCategory));
       return;
     }
     if(state.view==='sources'){
       history.replaceState(null,'',sourcesLink(state.paperPage));
       return;
     }
     const p=new URLSearchParams();
     if(state.open&&['problems','mechanisms'].includes(state.panel))p.set('panel',state.panel);
     appendConnections(p);
     for(const key of ['q','algebra','paper','abelianRank'])if(state[key])p.set(key,state[key]);
     if(state.core&&(state.open||state.browse==='cores'))p.set('core',state.core);
     if(state.fullAlgebra&&(state.open||state.core||state.browse!=='entries'))p.set('fullAlgebra',state.fullAlgebra);
     if(state.browse==='entries'&&state.semisimple&&!state.core)p.set('semisimple',state.semisimple);
     if(['algebras','full-algebras'].includes(state.browse)&&state.semisimple)p.set('semisimple',state.semisimple);
     if(state.mode!=='dimensions')p.set('notation',state.mode);
     const target=state.view!=='catalogue'?state.view:state.open?'entry/'+encodeURIComponent(state.open):state.browse==='entries'?(state.core?'core/'+encodeURIComponent(state.core):state.fullAlgebra?'full-algebra/'+encodeURIComponent(state.fullAlgebra):'entries'):state.browse==='cores'?(state.semisimple?'algebra/'+encodeURIComponent(state.semisimple):'cores'):state.browse==='full-algebras'?'full-algebras':'catalogue';
     history.replaceState(null,'','#'+target+(p.size?'?'+p:''));
   }
   function level(){return state.browse;}
   function browseLink(target,extra={}){
     const p=new URLSearchParams();appendConnections(p);
     for(const key of ['q','algebra','paper','abelianRank'])if(state[key])p.set(key,state[key]);
     if(state.mode!=='dimensions')p.set('notation',state.mode);
     for(const [key,value] of Object.entries(extra))if(value)p.set(key,value);
     return '#'+target+(p.size?'?'+p:'');
   }
   function updateCatalogueNavigation(){
     const gauge=['algebras','full-algebras'].includes(level());
     for(const [id,target,active] of [['nav-forces','full-algebras',gauge],['nav-matter','entries',!gauge]]){
       const link=document.getElementById(id);
       if(link){link.href=browseLink(target);link.setAttribute?.('aria-current',state.view==='catalogue'&&active?'page':'false');}
     }
   }
   function detail(e){
     const all=data._store?e.paperIds.map(id=>({paper_id:id})):[...e.references].sort((a,b)=>comparePapers(paperById.get(a.paper_id),paperById.get(b.paper_id)));
     const pages=data._store?Math.max(1,Math.ceil(all.length/20)):1;
     state.referencePage=Math.min(Math.max(1,state.referencePage),pages);
     const references=data._store?all.slice((state.referencePage-1)*20,state.referencePage*20):all;
     const pagination=pages>1?'<nav class="paper-pagination" aria-label="Reference pages">'+(state.referencePage>1?'<button type="button" class="text-button" data-reference-page="'+(state.referencePage-1)+'">← Previous</button>':'<span></span>')+'<span>Page '+state.referencePage+' of '+pages+'</span>'+(state.referencePage<pages?'<button type="button" class="text-button" data-reference-page="'+(state.referencePage+1)+'">Next →</button>':'<span></span>')+'</nav>':'';
     return '<section class="entry-detail" id="detail-'+esc(e.id)+'"><div class="detail-heading"><h2>References</h2><button class="icon-button" data-close aria-label="Close references">×</button></div><ol class="reference-list"'+(data._store?' start="'+((state.referencePage-1)*20+1)+'"':'')+' aria-label="Papers in chronological order">'+
       references.map(ref=>{const p=paperById.get(ref.paper_id);return '<li>'+paperDate(p)+'<div><a href="'+esc(sourceURL(p))+'" target="_blank" rel="noopener noreferrer">'+esc(p.title)+' ↗</a><p class="reference-meta">'+esc(p.authors)+'<br>arXiv:'+esc(p.arxiv)+'</p></div></li>';}).join('')+'</ol>'+pagination+'</section>';
   }
   function gaugeHeading(c){
     if(c.sm)return c.label==='g_SM'?shorthand('g_SM'):'𝔤<sub>SM,'+esc(c.label.slice(5))+'</sub>';
     return math(c.label)+(c.role&&(c.repeated||c.label==='u(1)')?'<sub>'+esc(c.role)+'</sub>':'');
   }
   function algebraDiagrams(column,regime){
     if(!root.AtlasDiagrams)return '';
     const parts=column.positions.map(i=>regime.factors[i]).map(a=>{
       if(a.type==='U1')return '<span class="abelian-caption" title="Abelian factor: no ordinary Dynkin diagram">u(1)</span>';
       if(!root.AtlasDiagrams.dynkinLayout(a.type,a.rank))return '';
       return '<span class="dynkin-factor"><span class="dynkin-sketch" data-dynkin-family="'+esc(a.type)+'" data-dynkin-rank="'+a.rank+'">'+esc(a.id)+'</span><span class="diagram-caption">'+esc(a.label)+'</span></span>';
     });
     return '<span class="algebra-diagrams" aria-label="Gauge algebra Dynkin diagrams">'+parts.join('')+'</span>';
   }
   function gaugeCell(row,column,regime){
     const cs=column.positions.map(i=>{
       const c=row.components[i];
       const typedExpression=Object.keys(regime.parameters||{}).length>0&&typeof c.chargeExpression==='string'&&c.value===c.chargeExpression;
       return regime.factors[i].type==='U1'&&!/^-?\d+$/.test(String(c.value??''))&&!typedExpression?{...c,value:null}:c;
     });
     return representationMarkup(cs,state.mode,column.sm);
   }
   function matrix(e,r){
     const isCore=Array.isArray(r.coreRows),columns=isCore&&!r.factors.length?[]:root.FieldMatrix.gaugeColumns(r),include=!!state.baselineOpen[e.id];
     const rows=isCore?r.coreRows:root.FieldMatrix.matrixRows(r,data.templates,include);
     const dimensions=[...new Set(rows.map(x=>x.lorentz.spacetime.dimension))];
     const algebra=dimensions.length===1?(dimensions[0]&&/^\d+$/.test(dimensions[0])?'so(1,'+(Number(dimensions[0])-1)+')':dimensions[0]?'so(1,D−1), D = '+dimensions[0]:'dimension unrecorded'):'mixed dimensions';
     return parameterMetadata(r,e)+'<div class="matrix-wrap"><table style="'+(columns.length>2?'min-width:'+((columns.length+2)*105+80)+'px':'')+'" class="representation-matrix'+(isCore?' core-matrix':'')+'" aria-label="'+(isCore?'Representations in non-Abelian core ':'Matter content of ')+esc(e.name)+'"><thead><tr><th>Spacetime<span class="matrix-algebra">'+esc(algebra)+'</span></th>'+columns.map(c=>'<th>'+gaugeHeading(c)+(r.chargeConvention&&c.positions.some(i=>r.factors[i].type==='U1')?'<span class="matrix-algebra">'+esc(r.chargeConvention)+'</span>':'')+algebraDiagrams(c,r)+'</th>').join('')+'<th>Multiplicity</th>'+'</tr></thead><tbody>'+
       (r.baseline?'<tr class="baseline-group"><td colspan="'+(columns.length+2)+'"><button class="text-button" data-baseline="'+esc(e.id)+'" aria-expanded="'+include+'">'+shorthand(r.baseline)+'<span> '+(include?'−':'+')+'</span></button></td></tr>':'')+
       rows.map(row=>{
         const l=row.lorentz;
         return '<tr class="'+(row.template?'template-row':'')+'"><td><span class="math">'+esc(l.label).replaceAll('1/2','½')+'</span>'+(dimensions.length>1?'<span class="matrix-note">'+esc(l.spacetime.dimension||'D unknown')+'D</span>':'')+'</td>'+columns.map(c=>'<td>'+gaugeCell(row,c,r)+'</td>').join('')+'<td>'+esc(row.copies??'?')+'</td>'+'</tr>';
       }).join('')+(!rows.length?'<tr><td colspan="'+(columns.length+2)+'" class="subtle">No additional matter beyond this reference spectrum.</td></tr>':'')+'</tbody></table></div>';
   }
   function parameterMetadata(r,e){
     if(!Object.keys(r.parameters||{}).length)return '';
     const mapping=e.referenceParameters||e.references?.find(ref=>ref.parameter_names)?.parameter_names;
     return '<div class="family-parameters"><p>Integer parameters: <span class="math">'+Object.keys(r.parameters).map(esc).join(', ')+'</span>.</p><details><summary>Parameter constraints</summary><ul>'+r.constraints.map(c=>'<li><code>'+esc(c)+'</code></li>').join('')+'</ul>'+(mapping?'<p>Source parameter names: <code>'+Object.entries(mapping).map(([source,target])=>esc(source)+' → '+esc(target)).join(', ')+'</code>.</p>':'')+'<p>Charges use expanded integer polynomials. Constraints are retained, not solved for equivalent domains. Shared primitive normalization is applied after specialization. A family is one entry, not an enumeration of its members.</p></details></div>';
   }
   function algebraCards(entries){
     const matched=new Set(entries.map(e=>e.id));
     const algebras=(data.semisimpleAlgebras||[]).filter(a=>a.entryIds.some(id=>matched.has(id)));
     document.getElementById('result-count').textContent=algebras.length+' semisimple '+(algebras.length===1?'part':'parts');
     document.getElementById('model-entries').innerHTML=algebras.slice(0,state.limit).map(a=>{
       const members=entries.filter(e=>e.semisimpleId===a.id),count=new Set(members.map(e=>e.coreId).filter(Boolean)).size;
       const fullCount=new Set(members.map(e=>e.fullAlgebraId)).size;
       return '<article class="model-entry algebra-entry"><header class="model-heading"><h2 class="math">'+math(a.algebra)+'</h2><div class="algebra-branches"><a href="'+esc(browseLink('full-algebras',{semisimple:a.id}))+'">'+fullCount+' full gauge '+(fullCount===1?'algebra':'algebras')+' →</a><a href="'+esc(browseLink('algebra/'+a.id))+'">'+count+' matter '+(count===1?'spectrum':'spectra')+' ↓</a></div></header><div class="algebra-overview">'+algebraDiagrams({positions:a.factors.map((_,i)=>i)},{factors:a.factors})+'<span class="subtle">'+members.length+' '+(members.length===1?'entry':'entries')+'</span></div></article>';
     }).join('')+(algebras.length>state.limit?'<button class="load-more" data-more>Show more algebras</button>':'')+(!algebras.length?'<p class="empty">No algebras match these filters. <button class="text-button" data-reset>Reset</button></p>':'');
     root.AtlasDiagrams?.render(document);
   }
   function fullAlgebraCards(entries){
     const matched=new Set(entries.map(e=>e.id));
     const algebras=(data.fullAlgebras||[]).filter(a=>a.entryIds.some(id=>matched.has(id)));
     document.getElementById('result-count').textContent=algebras.length+' full gauge '+(algebras.length===1?'algebra':'algebras');
     document.getElementById('model-entries').innerHTML=algebras.slice(0,state.limit).map(a=>{
       const count=a.entryIds.filter(id=>matched.has(id)).length,href=browseLink('full-algebra/'+a.id);
       return '<article class="model-entry algebra-entry full-algebra-entry"><header class="model-heading"><h2><a class="core-title math" href="'+esc(href)+'">'+math(a.algebra)+'</a></h2><a class="core-open" href="'+esc(href)+'">Open '+count+' '+(count===1?'entry':'entries')+' ↓</a></header><div class="algebra-overview">'+algebraDiagrams({positions:a.factors.map((_,i)=>i)},{factors:a.factors})+'</div></article>';
     }).join('')+(algebras.length>state.limit?'<button class="load-more" data-more>Show more algebras</button>':'')+(!algebras.length?'<p class="empty">No full gauge algebras match these filters. <button class="text-button" data-reset>Reset</button></p>':'');
     root.AtlasDiagrams?.render(document);
   }
   function coreCards(entries){
     const matched=new Set(entries.map(e=>e.id));
     const cores=(data.cores||[]).filter(c=>c.entryIds.some(id=>matched.has(id)));
     const visible=cores.slice(0,state.limit);
     document.getElementById('result-count').textContent=cores.length+' semisimple matter '+(cores.length===1?'spectrum':'spectra');
     document.getElementById('model-entries').innerHTML=visible.map(c=>{
       const count=c.entryIds.filter(id=>matched.has(id)).length,href=browseLink('core/'+c.id,{fullAlgebra:state.fullAlgebra});
       return '<article class="model-entry core-entry"><header class="model-heading"><h2><a class="core-title" href="'+esc(href)+'">'+math(c.algebra)+'</a></h2><a class="core-open" href="'+esc(href)+'">Open '+count+' '+(count===1?'entry':'entries')+' →</a></header></article>';
     }).join('')+(cores.length>visible.length?'<button class="load-more" data-more>Show more cores ('+(cores.length-visible.length)+' remaining)</button>':'')+(!cores.length?'<p class="empty">No matter spectra match these filters. <button class="text-button" data-reset>Reset</button></p>':'');
     root.AtlasDiagrams?.render(document);
   }
   function rows(){
     if(defer(rows))return;
     updateCatalogueNavigation();
     const reset=document.getElementById('reset-filters');
     if(reset)reset.hidden=!['q','algebra','paper','abelianRank'].some(k=>state[k]);
     const entries=currentEntries(),openIndex=entries.findIndex(e=>e.id===state.open);
     if(level()==='algebras')return algebraCards(entries);
     if(level()==='full-algebras')return fullAlgebraCards(entries);
     if(level()==='cores')return coreCards(entries);
     if(!data._store)state.limit=Math.max(state.limit,openIndex+1);
     const visible=data._store?data._store.visibleEntries(entries,state):entries.slice(0,state.limit);
     document.getElementById('result-count').textContent=entries.length+(entries.length===1?' entry':' entries');
     document.getElementById('model-entries').innerHTML=visible.map(e=>{
       const r=e.regime;
       const refsOpen=state.open===e.id&&state.panel==='references',problemsOpen=state.open===e.id&&state.panel==='problems',mechanismsOpen=state.open===e.id&&state.panel==='mechanisms';
       const mechanismLabel=mechanismExplorer?.assessed(e.id)?'Mechanisms ('+mechanismExplorer.count(e.id)+')':'Mechanisms · unassessed';
       const problemLabel=problemExplorer?.assessed(e.id)?'Problems ('+problemExplorer.count(e.id)+')':'Problems · unassessed';
       return '<article class="model-entry" id="model-'+esc(e.id)+'"><header class="model-heading"><h2>'+esc(e.name)+'</h2><div class="entry-actions"><button class="text-button" data-open="'+esc(e.id)+'" aria-label="References for '+esc(e.name)+' ('+(e.referenceCount??e.references.length)+')" aria-expanded="'+refsOpen+'">References ('+(e.referenceCount??e.references.length)+') '+(refsOpen?'−':'+')+'</button>'+(problemExplorer?'<button class="text-button problem-entry-button" data-problems="'+esc(e.id)+'" aria-label="Problems for '+esc(e.name)+'" aria-expanded="'+problemsOpen+'">'+problemLabel+' '+(problemsOpen?'−':'+')+'</button>':'')+(mechanismExplorer?'<button class="text-button problem-entry-button" data-mechanisms="'+esc(e.id)+'" aria-label="Mechanisms for '+esc(e.name)+'" aria-expanded="'+mechanismsOpen+'">'+mechanismLabel+' '+(mechanismsOpen?'−':'+')+'</button>':'')+'</div></header>'+(state.open===e.id?(state.panel==='problems'&&problemExplorer?problemExplorer.entry(e.id):state.panel==='mechanisms'&&mechanismExplorer?mechanismExplorer.entry(e.id):detail(e)):'')+matrix(e,r)+'</article>';
     }).join('')+(entries.length>visible.length?'<button class="load-more" data-more>Show more models ('+(entries.length-visible.length)+' remaining)</button>':'')+(!entries.length?'<p class="empty">No entries match these filters. <button class="text-button" data-reset>Reset</button></p>':'');
     root.AtlasDiagrams?.render(document);
   }
   function notation(){return '<section id="notation"><div class="section-heading"><h2>Notation</h2><span class="eyebrow">Convention '+esc(data.version)+'</span></div><details class="notation-panel" id="notation-guide"><summary>Notation guide</summary><div class="notation-grid"><div>'+
     '<h3>Forces</h3><p>The atlas records the local gauge algebra of each model, its forces. For the Standard Model we write <span class="math">𝔤<sub>SM</sub> = su(3) ⊕ su(2) ⊕ u(1)</span>. Its semisimple part is su(3) ⊕ su(2), obtained by omitting the u(1) factor. These labels do not specify a global gauge group or a quotient by its centre.</p><p>Simple factors are identified by Cartan type and rank, and their order is standardized throughout the database. Each matter representation follows that same order. Swapping factors, together with their representations, therefore does not create a new entry.</p>'+
     '<h3>Matter</h3><p>The atlas records the gauge representations of each model, its matter. These specify how the fields transform under gauge symmetry. The tables initially show representations by their dimensions. For <span class="math">𝔤<sub>SM</sub></span>, the tuple <span class="math">(3, 2; 1)</span> denotes an su(3) triplet, an su(2) doublet and u(1) charge +1. Non-Abelian representations appear before the semicolon; Abelian charges follow it.</p><p>Dimensions do not always distinguish representations, so the database stores their highest-weight Dynkin labels. There is one nonnegative integer for each simple-root node, in <a href="'+esc(data.representationConvention.nodeNumberingReference)+'">Bourbaki order</a>. The same example is <span class="math">([1,0], [1]; 1)</span>. For su(3), [1,0] is the fundamental and [0,1] its conjugate; all-zero labels denote a singlet.</p>'+
     '<h3>Spacetime representations</h3><p>The Spacetime column describes how the field transforms under Lorentz symmetry, independently of its gauge representation. In four dimensions we use <span class="math">(j<sub>L</sub>, j<sub>R</sub>)</span>: a scalar is (0,0), a left-handed Weyl fermion (½,0), and a vector (½,½). These are field representations, not counts of on-shell polarizations.</p><p>All independent 4D Weyl fermions are written as left-handed fields. A right-handed field is replaced by its left-handed charge conjugate, which conjugates its non-Abelian representations and negates its u(1) charges. A Dirac fermion contributes two independent Weyl components. Higher-dimensional entries use the appropriate Lorentz Dynkin labels.</p>'+
     '<h3>Multiplicity</h3><p>Multiplicity counts independent fields with the same Lorentz and gauge representations; it is not the dimension of either representation. The SM quark doublet, for example, has multiplicity 3 because there are three generations, not 6 because it transforms as a colour triplet and a weak doublet.</p><p>Scalars count irreducible real gauge modules. A complex scalar in a real-type gauge representation contributes two such modules; in a complex- or pseudoreal-type representation it contributes one. A neutral complex singlet therefore counts 2, while a charged Higgs doublet counts 1. Conjugate scalar representations describe the same real module; this identification does not apply to Weyl fermions.</p></div><div>'+
     '<h3>u(1) charges</h3><p>For each u(1) factor, a fixed charge assignment is rescaled so that all charges are integers with gcd 1. The same normalization is applied to the entire matter content, including scalars and fermions. Ordinary SM hypercharge is therefore written as <span class="math">q = 6Y</span>.</p><p>Each row carries one charge per u(1) factor. Three generations with charges [0,−3,3] must be recorded as separate rows, rather than as three identical fields. With several u(1) factors, the charges follow the generator order shown in the columns.</p>'+
     '<h3>Symbolic charge families</h3><p>A paper may specify a family of charge assignments rather than a single numerical choice. We keep the family as one entry, with integer parameters <code>z1, z2, …</code> and the constraints stated by the source. Charge polynomials are expanded, like terms are collected, and monomials follow descending lexicographic order. For example:</p><p><code>(z1 + z2)**2 → z1**2 + 2*z1*z2 + z2**2</code></p><p>Parameter names are assigned consistently across the charges and constraints. Renaming parameters or reordering factors and rows does not create a new template. Constraints remain part of the entry, but we do not try to prove that differently written domains or general reparameterizations describe the same family. Choosing an allowed integer point gives a numerical assignment, which is then normalized to primitive charges. Original parameter names are available under Parameter constraints.</p>'+
     '<h3>Catalogue order</h3><p>Algebras are ordered by semisimple rank, dimension and Cartan type, then by the number of u(1) factors. Within each algebra, matter spectra are ordered by total real dimension of the Lorentz × gauge field representation, including multiplicities. Equal dimensions are resolved by the exact canonical representation labels and symbolic metadata.</p><p>For example, the SM field representation has dimension 184. Adding a real singlet, a complex singlet or a second Higgs doublet gives 185, 186 or 188. This counts the recorded field components, not on-shell polarizations. Gauge connections are already specified by the algebra.</p>'+
     '<h3>Display and diagrams</h3><p>The notation selector changes how a representation is displayed, not how it is stored. Choose Dimensions, Dynkin labels, Young diagrams or Compare notations to see the alternatives together. Young diagrams are available for A-series representations; an unavailable diagram does not mean the representation is unknown. The small Dynkin diagrams in column headings describe the gauge algebra, not an individual matter representation.</p>'+
     '<h3>SM shorthand</h3><p>We use <span class="math">R<sub>SM</sub> = F<sub>SM</sub> ⊕ H<sub>SM</sub></span> to avoid repeating the SM matter content in every entry. F<sub>SM</sub> contains three generations of left-handed Weyl fermions, and H<sub>SM</sub> is one complex Higgs doublet. No right-handed neutrino is included. Gauge connections are already implied by the algebra and are not additional matter rows.</p><p>The supersymmetric baseline <span class="math">R<sub>MSSM</sub></span> replaces R<sub>SM</sub>; it is not added to it. Its chiral multiplets each contain one complex scalar and one left-handed Weyl fermion.</p><details id="sm-reference"><summary>SM matter table</summary>'+templateTable(data.templates.R_SM)+'</details>'+
     '<details id="mssm-reference"><summary>MSSM matter table</summary><p>The MSSM contains three chiral matter families, two Higgs chiral multiplets and the gauge-adjoint gauginos.</p>'+templateTable(data.templates.R_MSSM)+'</details>'+
     '<p><a href="https://github.com/bastoscostadavi/bsm-atlas/blob/main/atlas/FIELD_CONTENT_CONVENTIONS.md">Full conventions ↗</a></p></div></div></details></section>';}

   function sourcesLink(page){
     const p=new URLSearchParams();
     if(state.paperQuery.trim())p.set('search',state.paperQuery.trim());
     if(state.paperYear)p.set('year',state.paperYear);
     if(page>1)p.set('page',page);
     return '#sources'+(p.size?'?'+p:'');
   }
   function sources(){
     const searched=Boolean(state.paperQuery.trim()||state.paperYear);
     const prepared=data._store?.paperResults;
     const papers=prepared?prepared.rows:findPapers(orderedPapers,{q:state.paperQuery,year:state.paperYear});
     const total=prepared?prepared.total:papers.length;
     const pages=prepared?prepared.pages:Math.max(1,Math.ceil(total/papersPerPage));
     state.paperPage=prepared?prepared.page:Math.min(Math.max(1,state.paperPage),pages);
     const offset=(state.paperPage-1)*papersPerPage,visible=prepared?papers:papers.slice(offset,offset+papersPerPage);
     const count=(pages>1?(offset+1)+'–'+(offset+visible.length)+' of ':'')+total+' '+(total===1?'paper':'papers');
     const years=data._store?[...data._store.manifest.years]:[...new Set(orderedPapers.map(p=>arxivDate(p)?.year).filter(Boolean).map(String))];
     if(state.paperYear&&!years.includes(state.paperYear))years.push(state.paperYear);
     years.sort((a,b)=>Number(b)-Number(a));
     const pagination=pages>1?'<nav class="paper-pagination" aria-label="Bibliography pages">'+
       (state.paperPage>1?'<a href="'+esc(sourcesLink(state.paperPage-1))+'" rel="prev">← Previous</a>':'<span aria-disabled="true">← Previous</span>')+
       '<span>Page '+state.paperPage+' of '+pages+'</span>'+
       (state.paperPage<pages?'<a href="'+esc(sourcesLink(state.paperPage+1))+'" rel="next">Next →</a>':'<span aria-disabled="true">Next →</span>')+'</nav>':'';
     return '<section id="sources"><p class="section-note">Search the bibliography. References are also available directly from each model.</p>'+
       '<form id="paper-search-form" class="toolbar paper-search" role="search" aria-label="Bibliography search">'+
       '<label class="search-label"><span class="sr-only">Title, author or arXiv identifier</span><input type="search" id="paper-search" placeholder="Title, author or arXiv identifier" value="'+esc(state.paperQuery)+'"></label>'+
       '<label class="paper-year"><span class="sr-only">Year of first arXiv submission</span><select id="paper-year"><option value="">All years</option>'+years.map(year=>'<option value="'+esc(year)+'"'+(state.paperYear===year?' selected':'')+'>'+esc(year)+'</option>').join('')+'</select></label>'+
       '<button class="search-button" type="submit">Search</button></form>'+
       '<div id="paper-results" role="region" tabindex="-1" aria-label="Bibliography results">'+(!searched?'<p class="empty">Search by title, author or arXiv identifier, or choose a year.</p>':
         '<div class="results-bar"><span>'+count+(total?' · Oldest first':'')+'</span><a href="#sources">Clear search</a></div>'+
         (!total?'<p class="empty">No papers match your search. Try another title, author, arXiv identifier or year.</p>':
           '<div class="source-list">'+visible.map(p=>'<article class="paper-item"><h2 class="paper-title"><a href="'+esc(sourceURL(p))+'" target="_blank" rel="noopener noreferrer">'+esc(p.title)+' ↗</a></h2>'+
             '<p class="reference-meta">'+esc(p.authors)+'</p><p class="paper-meta">'+paperDate(p)+'<span>arXiv:'+esc(p.arxiv)+'</span></p>'+
             (p.entryIds.length?'<details class="paper-entries"><summary>'+p.entryIds.length+' atlas '+(p.entryIds.length===1?'entry':'entries')+'</summary><ul>'+orderedEntryIds(p.entryIds).map(id=>'<li><a href="#entry/'+esc(encodeURIComponent(id))+'">'+esc(entryById.get(id)?.name||id)+'</a></li>').join('')+'</ul></details>':'<p class="reference-meta">No linked atlas entries.</p>')+
             '</article>').join('')+'</div>'+pagination))+'</div></section>';
   }
   function atlasIntroduction(){
     return '<article class="about-data"><p>Gauge symmetry and the representations of matter are the defining ingredients of the Standard Model. It can seem ungainly, even arbitrary, in its particulars, yet beautiful in its workings: gauge anomalies cancel exactly, and its dynamics span confinement, spontaneous symmetry breaking and weakly coupled scattering. In its minimal form, with massless neutrinos, the theory has just 19 free parameters, yet makes infinitely many predictions once their values are fixed. BSM Atlas takes these defining ingredients as a starting point for charting extensions of the Standard Model. Each entry gives the gauge algebra, the Lorentz and gauge representations of the matter fields, and their multiplicities, using a common notation and linking to the papers in which they are studied.</p>'+
       '<h2>How we build it</h2><p>We construct the atlas by ingesting arXiv papers, extracting complete gauge–matter specifications and expressing them in common conventions. Papers studying the same structure are linked to one entry. The <a href="#problems">Problems</a> and <a href="#mechanisms">Mechanisms</a> layers help navigate this space through the physics questions and processes studied in those papers.</p>'+
       '<h2>Prospective applications</h2><ul>'+
       '<li><strong><a href="https://github.com/bastoscostadavi/bsm-ai-search">BSM AI Search</a>.</strong> Use the atlas to guide AI agents in proposing new gauge–matter structures and investigating them through the BSM research workflow: constructing interactions, exploring parameter spaces, calculating observables and comparing predictions with experiments. Our hope is to uncover unexplored regions of model space with interesting physical features.</li>'+
       '<li><strong><a href="https://github.com/bastoscostadavi/bsm-foundation-model">BSM Foundation Model</a>.</strong> Use atlas entries to organize diverse simulations across theories, parameters and experimental settings. Map this into a supervised learning classification task: given simulated observations, identify the underlying gauge algebra and matter representations. Standard searches often seek clear signals that distinguish theories, but a subtler signal may be hidden across diverse experimental datasets and revealed only by correlating them.</li>'+
       '<li><strong><a href="https://github.com/bastoscostadavi/bsm-benchmark">BSM Benchmark</a>.</strong> Turn the atlas and its source papers into a reproducible benchmark for AI systems on BSM research tasks. Each task would supply a model specification and ask a question answered in one of the papers that studies it, using the paper’s result as a reference answer.</li></ul>'+
       '<h2>Bottom-up physics, from the top down</h2><p>The Atlas and its applications are motivated by the hypothesis that the characteristic scales of a BSM theory lie far below the scale of further new physics. This separation makes a renormalizable Lagrangian a useful starting description, with higher-dimensional operators suppressed by the higher scale. The observable effects of the BSM theory may themselves be small, but a common underlying theory relates departures from Standard Model predictions across measurements. Their collective pattern may reveal a signal hidden in individual observations. By charting candidate theories and tracing their observable consequences, the Atlas aims to help us work backward from measurements to the theory realized in nature: bottom-up physics, from the top down.</p></article>';
   }
   function catalogue(){
     const current=level(),isCores=current==='cores',isAlgebras=current==='algebras',isFullAlgebras=current==='full-algebras',isGauge=isAlgebras||isFullAlgebras;
     const semisimpleOnly=isAlgebras||isCores;
     const csvLabel=isAlgebras?'All semisimple algebras':isFullAlgebras?'All full gauge algebras':isCores?'All semisimple matter spectra':'All model entries';
     const csvKey=isAlgebras?'semisimple-algebras':isFullAlgebras?'full-gauge-algebras':isCores?'nonabelian-cores':'field-catalogue';
     const csvDescription=isGauge?'One row per gauge algebra.':isCores?'One row per semisimple matter spectrum.':'One row per model, with its exact specification.';
     const connectionCount=state.connections.problems.length+state.connections.mechanisms.length;
     const active=['algebra','paper','abelianRank'].filter(k=>state[k]).length+connectionCount;
     const p=paperById.get(state.paper);
     const core=coreById.get(state.core);
     const fullAlgebra=fullAlgebraById.get(state.fullAlgebra);
     const algebra=algebraById.get(core?.semisimpleId||state.semisimple);
     const context=state.fullAlgebra?'<span class="math">'+math(fullAlgebra?.algebra||'Full algebra not found')+'</span>':state.core?'<span class="math">'+math(core?.algebra||'Core not found')+'</span>':state.semisimple?'<span class="math">'+math(algebra?.algebra||'Algebra not found')+'</span>':'';
     const descriptions={
       algebras:'The semisimple part of the gauge algebra, with u(1) factors and matter representations omitted.',
       'full-algebras':'Gauge algebras, with matter representations omitted.',
       cores:'The semisimple part of the gauge algebra and its matter representations, with u(1) factors omitted.',
       entries:'Gauge algebras and matter representations'};
     return '<div class="catalogue-view-controls"><p class="section-note">'+descriptions[current]+'</p><label class="semisimple-toggle" title="Compare semisimple parts with u(1) factors omitted"><input id="semisimple-only" type="checkbox"'+(semisimpleOnly?' checked':'')+'><span>Semisimple part only</span></label></div>'+(context?'<p class="layer-context">'+context+'</p>':'')+'<div class="toolbar" role="search" aria-label="Catalogue search"><label class="search-label"><span class="sr-only">Catalogue search</span><input type="search" id="entry-search" placeholder="Gauge algebra, representation, model or paper" value="'+esc(state.q)+'"></label>'+
       (!isGauge?'<label class="notation-select"><span class="notation-control-label">Matter representation notation</span><select id="notation-select">'+Object.entries(notationModes).map(([id,label])=>'<option value="'+id+'"'+(state.mode===id?' selected':'')+'>'+label+'</option>').join('')+'</select></label>':'')+
       '<details class="filter-panel"'+(active?' open':'')+'><summary>Filters'+(active?' · '+active:'')+'</summary><div class="filter-fields">'+(connectionExplorer?connectionExplorer.catalogueFilters(state.connections):'')+'</div></details>'+
       '<details class="download-menu"><summary>Download</summary><div><p class="download-note">Complete datasets. Current search and filters are not applied.</p><a href="'+esc(downloadLink(csvKey))+'" download><strong>'+csvLabel+' · CSV'+(downloadLink(csvKey).endsWith('.gz')?' (gzip)':'')+'</strong><span>'+csvDescription+'</span></a><a href="'+esc(downloadLink('catalogue'))+'" download><strong>Complete catalogue · JSON'+(downloadLink('catalogue').endsWith('.gz')?' (gzip)':'')+'</strong><span>All model specifications and paper references.</span></a><a href="'+esc(downloadLink('sqlite'))+'" download><strong>Catalogue database · SQLite'+(downloadLink('sqlite').endsWith('.gz')?' (gzip)':'')+'</strong><span>All models and references in a relational database.</span></a><p class="download-note">Problem and mechanism annotations are not included.</p></div></details></div>'+
       (p?'<div class="selected-paper">'+paperDate(p)+'<a href="'+esc(sourceURL(p))+'" target="_blank" rel="noopener noreferrer">'+esc(p.title)+' ↗</a></div>':'')+
       '<div class="results-bar"><span id="result-count"></span><button id="reset-filters" class="text-button" data-reset'+(['q','algebra','paper','abelianRank'].some(k=>state[k])||connectionCount?'':' hidden')+'>Reset</button></div>'+
       '<div id="model-entries" aria-label="Model matter content"></div>';
   }
   function render(){
     if(defer(render))return;
     const titles={catalogue:'Forces and Matter',atlas:'What is the atlas?',sources:'Papers',notation:'Notation',problems:'Problems',mechanisms:'Mechanisms'};
     document.getElementById('page-title').textContent=state.view==='catalogue'?(level()==='algebras'||level()==='full-algebras'?'Forces':'Forces and Matter'):titles[state.view];
     const key=document.getElementById('notation-key');
     if(key)key.hidden=state.view!=='catalogue'||level()!=='entries';
     const content=document.getElementById('view-content');
     content.className=state.view+'-view';
     content.innerHTML=connectionExplorer&&['problems','mechanisms'].includes(state.view)?connectionExplorer.page(state.connections):state.view==='problems'?(problemExplorer?(state.problem?problemExplorer.problem(state.problem,state.problemQuery,state.problemLimit):problemExplorer.overview()):'<p class="empty">Problem preview unavailable.</p>'):state.view==='atlas'?atlasIntroduction():state.view==='sources'?sources():state.view==='notation'?notation():catalogue();
     if(state.view==='catalogue')rows();else updateCatalogueNavigation();
     if(state.view==='notation')document.getElementById('notation-guide').open=true;
     if(state.problemLayer){
       const layer=document.getElementById('problems-layer');
       if(layer){layer.open=true;layer.scrollIntoView?.({block:'start'});layer.querySelector?.('summary')?.focus?.({preventScroll:true});}
     }
     root.AtlasDiagrams?.render(document);
     if(document.querySelectorAll)document.querySelectorAll('.site-header nav > a').forEach(a=>{if(!['nav-forces','nav-matter'].includes(a.id))a.setAttribute('aria-current',a.getAttribute('href')==='#'+state.view?'page':'false');});
   }
   function refreshConnections(){
     url();
     if(defer(refreshConnections))return;
     if(state.view==='catalogue'){
       const focused=document.activeElement,kind=focused?.dataset?.connectionKind,value=focused?.value;
       const scrolls=new Map(Array.from(document.querySelectorAll?.('.connection-picker')||[],picker=>[picker.dataset.picker,picker.querySelector('.connection-picker-options').scrollTop]));
       render();
       document.querySelectorAll?.('.connection-picker').forEach(picker=>{picker.querySelector('.connection-picker-options').scrollTop=scrolls.get(picker.dataset.picker)||0;});
       if(kind)Array.from(document.querySelectorAll?.('input[data-connection-kind]')||[]).find(input=>input.dataset.connectionKind===kind&&input.value===value)?.focus({preventScroll:true});
       return;
     }
     const results=document.getElementById('connection-results'),selection=document.getElementById('connection-selection');
     if(results)results.innerHTML=connectionExplorer.results(state.connections);
     if(selection)selection.outerHTML=connectionExplorer.chips(state.connections);
     const link=document.querySelector?.('.connection-intro>a');
     link?.setAttribute('href',connectionExplorer.catalogueURL(state.connections));
   }
   function start(){
     route();render();
     const content=document.getElementById('view-content');
     async function loadEvidence(holder,page=1){
       if(!data._store)return;
       const {evidenceKind:kind,evidenceEntry:entry,evidenceTerm:term}=holder.dataset;
       holder.innerHTML='<p class="subtle" role="status">Loading references…</p>';
       try{await data._store.loadEvidence(kind,entry,term,page);if(holder.isConnected){const renderer=kind==='problems'?problemExplorer:mechanismExplorer;holder.outerHTML=renderer.evidence(entry,term);}}
       catch(error){if(holder.isConnected){const reload=error instanceof root.AtlasStore.SnapshotChangedError;holder.innerHTML='<p role="alert">'+esc(error.message)+' <button type="button" class="text-button" '+(reload?'data-reload-catalogue':'data-evidence-page="'+page+'"')+'>'+(reload?'Reload catalogue':'Retry')+'</button></p>';}}
     }
     content.addEventListener('toggle',event=>{
       if(!event.target.open||!data._store)return;
       for(const holder of event.target.querySelectorAll('[data-lazy-evidence]'))if(!holder.dataset.loaded)loadEvidence(holder);
     },true);
     content.addEventListener('click',event=>{
       const target=event.target.closest('[data-evidence-page]');if(target){const holder=target.closest('[data-lazy-evidence]');if(holder){event.preventDefault();loadEvidence(holder,Number(target.dataset.evidencePage));}}
     });

     content.addEventListener('submit',e=>{
       if(e.target.id==='problem-search-form'){
         e.preventDefault();state.problemQuery=document.getElementById('problem-search').value.trim();state.problemLimit=20;url();render();return;
       }
       if(e.target.id!=='paper-search-form')return;
       e.preventDefault();
       state.paperQuery=document.getElementById('paper-search').value.trim();
       state.paperYear=document.getElementById('paper-year').value;
       state.paperPage=1;
       url();render();
       document.getElementById('paper-results')?.focus?.({preventScroll:true});
     });
     content.addEventListener('input',e=>{
       if(connectionExplorer&&e.target.id==='connection-filter-search'){
         state.connections.filterQuery=e.target.value;document.getElementById('connection-filter-groups').innerHTML=connectionExplorer.filterGroups(state.connections,[state.view]);return;
       }
       if(connectionExplorer&&e.target.id==='connection-model-search'){state.connections.q=e.target.value;state.connections.limit=20;refreshConnections();return;}
       if(e.target.id==='entry-search'){state.q=e.target.value;state.open='';url();if(data._store){root.clearTimeout(entrySearchTimer);entrySearchTimer=root.setTimeout(()=>{if(state.view==='catalogue')rows();},250);}else rows();}});
     content.addEventListener('change',e=>{
       if(e.target.id==='semisimple-only'){
         const gauge=['algebras','full-algebras'].includes(level());
         state.browse=gauge?(e.target.checked?'algebras':'full-algebras'):(e.target.checked?'cores':'entries');
         state.open='';state.limit=20;url();render();
         document.getElementById('semisimple-only')?.focus?.({preventScroll:true});return;
       }
       if(connectionExplorer&&e.target.dataset?.connectionKind&&e.target.type==='checkbox'){
         const kind=e.target.dataset.connectionKind,ids=new Set(state.connections[kind]);
         if(e.target.checked)ids.add(e.target.value);else ids.delete(e.target.value);
         state.connections[kind]=[...ids];state.connections.limit=20;state.limit=20;state.open='';
         e.target.closest('label')?.classList.toggle('is-selected',e.target.checked);refreshConnections();return;
       }
       if(e.target.id==='notation-select'){state.mode=e.target.value;url();rows();}
     });
     content.addEventListener('click',e=>{
       if(e.target.closest('[data-load-retry]')){render();return;}
       if(e.target.closest('[data-reload-catalogue]')){root.location.reload();return;}
       const referencePage=e.target.closest('[data-reference-page]');
       if(referencePage){state.referencePage=Number(referencePage.dataset.referencePage);rows();return;}

       const remove=e.target.closest('[data-connection-remove]');
       if(connectionExplorer&&remove){
         const kind=remove.dataset.connectionKind;state.connections[kind]=state.connections[kind].filter(id=>id!==remove.dataset.connectionRemove);
         url();render();return;
       }
       if(connectionExplorer&&e.target.closest('[data-connection-clear]')){state.connections.problems=[];state.connections.mechanisms=[];state.connections.limit=20;state.limit=20;url();render();return;}
       if(connectionExplorer&&e.target.closest('[data-connection-more]')){state.connections.limit+=20;refreshConnections();return;}
       const mechanisms=e.target.closest('[data-mechanisms]');
       if(mechanisms){state.open=state.open===mechanisms.dataset.mechanisms&&state.panel==='mechanisms'?'':mechanisms.dataset.mechanisms;state.panel='mechanisms';url();rows();return;}
       if(e.target.closest('[data-problem-more]')){state.problemLimit+=20;render();return;}
       const problems=e.target.closest('[data-problems]');
       if(problems){state.open=state.open===problems.dataset.problems&&state.panel==='problems'?'':problems.dataset.problems;state.panel='problems';url();rows();return;}
       const open=e.target.closest('[data-open]');
       if(e.target.closest('[data-more]')){state.limit+=20;rows();return;}
       const base=e.target.closest('[data-baseline]');
       if(base){state.baselineOpen[base.dataset.baseline]=!state.baselineOpen[base.dataset.baseline];rows();return;}
       if(open){
         const same=state.open===open.dataset.open&&state.panel==='references';
         state.open=same?'':open.dataset.open;
         state.panel='references';state.referencePage=1;
         url();rows();
       }else if(e.target.closest('[data-close]')){state.open='';url();rows();}
       else if(e.target.closest('[data-reset]')){Object.assign(state,{q:'',algebra:'',paper:'',abelianRank:'',open:''});state.connections.problems=[];state.connections.mechanisms=[];url();render();}
     });
     window.addEventListener('hashchange',()=>{
       const wasSources=state.view==='sources',page=state.paperPage;
       route();render();
       if(wasSources&&state.view==='sources'&&state.paperPage!==page){
         const results=document.getElementById('paper-results');
         results?.scrollIntoView?.({block:'start'});
         results?.focus?.({preventScroll:true});
       }
     });
     let theme='';try{theme=localStorage.getItem('atlas-theme')||'';}catch{}
     if(theme!=='dark'&&theme!=='light')theme=root.matchMedia?.('(prefers-color-scheme: dark)').matches?'dark':'light';
     const button=document.getElementById('theme-toggle');
     const setTheme=t=>{
       document.documentElement.dataset.theme=t;
       button.setAttribute('aria-label','Switch to '+(t==='dark'?'light':'dark')+' theme');
       button.setAttribute('title','Switch to '+(t==='dark'?'light':'dark')+' theme');
       document.getElementById('atlas-favicon')?.setAttribute('href',(t==='dark'?'favicon-dark.svg':'favicon.svg')+'?v=20261023-01');
       document.getElementById('theme-color')?.setAttribute('content',t==='dark'?'#1f1e1d':'#ffffff');
     };
     setTheme(theme==='dark'?'dark':'light');
     button.addEventListener('click',()=>{theme=document.documentElement.dataset.theme==='dark'?'light':'dark';setTheme(theme);try{localStorage.setItem('atlas-theme',theme);}catch{}});
   }
   return {start,state,render,rows,route,url};
 }
 root.FieldCatalogue={create,findEntries,findPapers,esc,young,dynkinTuple,representationMarkup,arxivDate,comparePapers};
 if(root.document&&root.ATLAS_MANIFEST_URL&&root.AtlasStore){
   const container=root.document.getElementById('view-content');container.innerHTML='<p class="subtle" role="status">Loading catalogue…</p>';
   root.AtlasStore.open(root.ATLAS_MANIFEST_URL).then(store=>{root.ATLAS_PROBLEMS=store.annotations.problems;root.ATLAS_MECHANISMS=store.annotations.mechanisms;create(store.data,root.document).start();}).catch(error=>{container.innerHTML='<p role="alert">'+esc(error.message)+' <button type="button" class="text-button" id="reload-catalogue">Retry</button></p>';root.document.getElementById('reload-catalogue').addEventListener('click',()=>root.location.reload());});
 }else if(root.document&&root.FIELD_CATALOGUE)create(root.FIELD_CATALOGUE,root.document).start();
})(typeof window==='undefined'?globalThis:window);
