/* Filter the same Atlas entries through independently evidenced annotation layers. */
(function(root){
 'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const number=n=>n.toLocaleString('en-US');
 const text=s=>String(s??'').normalize('NFD').replace(/\p{M}/gu,'').toLowerCase();
 const unique=xs=>[...new Set(xs.filter(Boolean))];
 function create(catalogue,problems,mechanisms){
   const layers={
     problems:{label:'Problems',singular:'Problem',data:problems||{},renderer:root.ProblemExplorer?.create(catalogue,problems)},
     mechanisms:{label:'Mechanisms',singular:'Mechanism',data:mechanisms||{},renderer:root.MechanismExplorer?.create(catalogue,mechanisms)}
   };
   for(const [kind,layer] of Object.entries(layers)){
     layer.terms=layer.data[kind]||[];
     layer.byId=new Map(layer.terms.map(t=>[t.id,t]));
     layer.links=layer.data.links||{};
     layer.assessed=new Set(layer.data.assessed||[]);
     layer.members=new Map(layer.terms.map(t=>[t.id,new Set(catalogue.entries.filter(e=>Array.isArray(layer.links[e.id]?.[t.id])&&layer.links[e.id][t.id].length).map(e=>e.id))]));
   }
   const searchIndex=new Map(catalogue.entries.map(e=>[e.id,text([e.id,e.name,e.algebraExpanded,...(e.aliases||[]).flatMap(a=>[a.id,a.name])].join(' '))]));
   function normalize(state={}){
     return {view:state.view==='mechanisms'?'mechanisms':'problems',
       problems:unique(state.problems||[]),mechanisms:unique(state.mechanisms||[]),
       match:'all',q:state.q||'',filterQuery:state.filterQuery||'',
       limit:Math.max(20,state.limit||20)};
   }
   function selections(state){return Object.keys(layers).flatMap(kind=>state[kind].map(id=>({kind,id,term:layers[kind].byId.get(id)})));}
   function matches(id,selection){return layers[selection.kind].members.get(selection.id)?.has(id)||false;}
   function find(state={}){
     state=normalize(state);
     const selected=selections(state),query=text(state.q).trim();
     return catalogue.entries.filter(e=>{
       if(query&&!searchIndex.get(e.id).includes(query))return false;
       if(selected.length)return selected.every(s=>matches(e.id,s));
       return layers[state.view].terms.some(t=>layers[state.view].members.get(t.id).has(e.id));
     });
   }
   function parse(hash){
     const [raw,query='']=hash.replace(/^#/,'').split('?'),p=new URLSearchParams(query);
     const view=raw.split('/')[0],state=normalize({view,problems:p.getAll('problem'),mechanisms:p.getAll('mechanism'),match:p.get('match'),q:p.get('search')||''});
     if(raw.startsWith('problems/'))state.problems=unique([...state.problems,decodeURIComponent(raw.slice(9))]);
     if(raw.startsWith('mechanisms/'))state.mechanisms=unique([...state.mechanisms,decodeURIComponent(raw.slice(11))]);
     return state;
   }
   function url(state={}){
     state=normalize(state);const p=new URLSearchParams();
     state.problems.forEach(id=>p.append('problem',id));
     state.mechanisms.forEach(id=>p.append('mechanism',id));
     if(state.q)p.set('search',state.q);
     return '#'+state.view+(p.size?'?'+p:'');
   }
   function filterGroups(state,kinds=Object.keys(layers)){
     const query=text(state.filterQuery).trim();
     return kinds.map(kind=>{
       const layer=layers[kind];
       const categories=layer.data.categories||[];
       const groups=categories.map(category=>{
         const terms=layer.terms.filter(t=>t.category_id===category.id&&(!query||text(t.label+' '+(t.main_idea||t.include)+' '+category.label).includes(query)));
         if(!terms.length)return '';
         return '<fieldset class="connection-category"><legend>'+esc(category.label)+'</legend>'+terms.map(term=>{
           const selected=state[kind].includes(term.id),count=layer.members.get(term.id).size;
           return '<label class="connection-option'+(selected?' is-selected':'')+'"><input type="checkbox" data-connection-kind="'+kind+'" value="'+esc(term.id)+'"'+(selected?' checked':'')+'><span title="'+esc(term.main_idea||term.include)+'">'+esc(term.label)+'</span><span class="connection-option-count" aria-label="'+number(count)+' linked entries">'+number(count)+'</span></label>';
         }).join('')+'</fieldset>';
       }).join('');
       return '<section class="connection-filter-layer" data-filter-layer="'+kind+'"><h3>'+layer.label+' <span>'+layer.terms.length+'</span></h3>'+(!layer.terms.length?'<p class="subtle">Annotations unavailable.</p>':groups||'<p class="subtle">No matching '+kind+'.</p>')+'</section>';
     }).join('');
   }
   function chips(state){
     const selected=selections(state);
     return '<div class="connection-selection" id="connection-selection">'+(selected.length?selected.map(s=>'<button type="button" class="connection-chip '+s.kind+'" data-connection-remove="'+esc(s.id)+'" data-connection-kind="'+s.kind+'" aria-label="Remove '+esc(s.term?.label||s.id)+'"><span class="connection-chip-kind">'+layers[s.kind].singular+'</span>'+esc(s.term?.label||s.id)+' <span aria-hidden="true">×</span></button>').join('')+'<button type="button" class="text-button" data-connection-clear>Clear selection</button>':'<p class="connection-selection-hint">Select one or more '+state.view+'.</p>')+'</div>';
   }
   function resultCard(entry,state){
     const selected=selections(state),annotations=[];
     for(const [kind,layer] of Object.entries(layers))for(const term of layer.terms){
       const rows=layer.links[entry.id]?.[term.id];
       if(Array.isArray(rows)&&rows.length)annotations.push({kind,term,rows,matched:state[kind].includes(term.id)});
     }
     const relevant=selected.length?annotations.filter(a=>a.matched):annotations.filter(a=>a.kind===state.view);
     const paperIds=new Set(relevant.flatMap(a=>a.rows.map(r=>r.paperId)));
     const flagged=relevant.reduce((n,a)=>n+a.rows.filter(r=>r.needsReview).length,0);
     const matched=selected.filter(s=>matches(entry.id,s)).length;
     return '<article class="connection-result"><div class="connection-result-heading"><h3><a href="#entry/'+encodeURIComponent(entry.id)+'">'+esc(entry.name)+'</a></h3><a class="problem-entry-link" href="#entry/'+encodeURIComponent(entry.id)+'">View entry →</a></div><p class="connection-result-algebra">'+esc(entry.algebraExpanded||'')+'</p>'+
       '<div class="connection-result-tags">'+relevant.map(a=>'<a class="connection-result-tag '+a.kind+'" href="'+esc(url({...state,view:a.kind,[a.kind]:[a.term.id],[a.kind==='problems'?'mechanisms':'problems']:[],q:''}))+'"><span>'+layers[a.kind].singular+'</span>'+esc(a.term.label)+'</a>').join('')+'</div>'+
       '<p class="connection-result-meta">'+(selected.length?matched+' of '+selected.length+' selected filters · ':'')+number(paperIds.size)+' supporting '+(paperIds.size===1?'paper':'papers')+(flagged?' · '+number(flagged)+' '+(flagged===1?'association flagged':'associations flagged')+' for review':'')+'</p>'+
       '<details class="connection-evidence"><summary>Supporting papers & evidence</summary>'+relevant.map(a=>'<section class="connection-evidence-term"><h4>'+esc(a.term.label)+'</h4><p class="problem-definition">'+esc(a.term.main_idea||a.term.include)+'</p>'+layers[a.kind].renderer.evidence(entry.id,a.term.id)+'</section>').join('')+'</details></article>';
   }
   function results(state={}){
     state=normalize(state);const entries=find(state),selected=selections(state);
     return '<div class="connection-results-heading"><h2 id="connection-result-count" tabindex="-1">'+number(entries.length)+' '+(entries.length===1?'entry':'entries')+'</h2><span>'+(selected.length?'Connected to all '+selected.length+' selected filters':'With detected connections')+'</span></div>'+
       (entries.length?entries.slice(0,state.limit).map(e=>resultCard(e,state)).join(''):'<div class="connection-empty"><h3>No entries match these filters</h3><p>'+(selected.length>1?'Remove a filter to broaden the results, or try another model search.':'Try another selection or model search.')+'</p><button type="button" class="text-button" data-connection-clear>Clear selection</button></div>')+
       (entries.length>state.limit?'<button type="button" class="load-more" data-connection-more>Show more entries ('+number(entries.length-state.limit)+' remaining)</button>':'');
   }
   function method(){return '<details class="problem-method" id="problems-layer"><summary>About Problems & Mechanisms</summary><p>Problems adds a literature-based layer to the atlas, connecting model entries to the particle-physics questions they are studied to address. Mechanisms adds the physical processes used by those models. The explorer covers '+layers.problems.terms.length+' problems and '+layers.mechanisms.terms.length+' mechanisms.</p><p>Luna read each full paper alongside its linked atlas entries. Only positive, model-specific associations create links. “Not found”, uncertain assessments and processing failures do not create connections. Unassessed entries are distinguished in each entry’s annotation panels.</p><p>Selections match atlas entries across their papers. Matching several filters does not establish that the connections occur in the same paper, parameter choice, or complete theory, and does not establish simultaneous solutions.</p><p>All associations are machine-extracted and await scientific review. Flags identify quotation, length, line-reference, coverage or model-identification issues. Automated checks passing does not verify the interpretation. Source locators refer to extracted paper text.</p></details>';}
   function filterEntries(entries,state={}){
     const selected=selections(normalize(state));
     return selected.length?entries.filter(e=>selected.every(s=>matches(e.id,s))):entries;
   }
   function catalogueURL(state={}){
     state=normalize(state);const p=new URLSearchParams();
     state.problems.forEach(id=>p.append('problem',id));state.mechanisms.forEach(id=>p.append('mechanism',id));
     if(state.q)p.set('q',state.q);
     return '#entries'+(p.size?'?'+p:'');
   }
   function catalogueFilters(state={}){
     state=normalize(state);
     return '<section class="connection-catalogue-filters" aria-label="Problem and mechanism filters"><div class="connection-catalogue-heading"><h2>Problems & mechanisms</h2><span>Entries must connect to every selection</span></div><div class="connection-catalogue-choosers">'+Object.entries(layers).map(([kind,layer])=>'<details class="connection-picker" data-picker="'+kind+'"'+(state[kind].length?' open':'')+'><summary>'+layer.label+' <span>'+(state[kind].length?state[kind].length+' selected':'Select '+kind)+'</span></summary><div class="connection-picker-options">'+filterGroups(state,[kind])+'</div></details>').join('')+'</div>'+(selections(state).length?chips(state)+'<p class="connection-scope">Connections may be supported by different papers or model variants.</p>':'')+'</section>';
   }
   function page(state={}){
     state=normalize(state);state[state.view==='problems'?'mechanisms':'problems']=[];
     const layer=layers[state.view],description=state.view==='problems'?'Find model entries connected to the questions you select.':'Find model entries that use the physical mechanisms you select.';
     return '<div class="connection-intro"><p>'+description+'</p><a href="'+esc(catalogueURL(state))+'">Combine problems & mechanisms in the catalogue →</a></div>'+
       '<div class="connection-layout"><aside class="connection-filters" aria-label="'+layer.label+' filters"><div class="connection-filter-heading"><h2>Select '+state.view+'</h2><label><span class="sr-only">Find a '+layer.singular.toLowerCase()+'</span><input id="connection-filter-search" type="search" placeholder="Find a '+layer.singular.toLowerCase()+'" value="'+esc(state.filterQuery)+'"></label></div><div class="connection-filter-groups" id="connection-filter-groups">'+filterGroups(state,[state.view])+'</div></aside>'+
       '<section class="connection-main" aria-label="Matching model entries"><div class="connection-controls"><p>Entries must connect to <strong>all</strong> selected '+state.view+'.</p><label class="connection-model-search"><span class="sr-only">Search matching entries</span><input id="connection-model-search" type="search" placeholder="Search matching entries" value="'+esc(state.q)+'"></label></div>'+chips(state)+
       '<p class="connection-scope">Connections may be supported by different papers or model variants.</p><div id="connection-results" aria-live="polite">'+results(state)+'</div></section></div>'+method();
   }

   return {find,filterEntries,parse,url,page,results,chips,filterGroups,catalogueFilters,catalogueURL,normalize};
 }
 root.ConnectionExplorer={create};
})(typeof window==='undefined'?globalThis:window);
