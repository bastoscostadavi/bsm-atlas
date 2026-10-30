/* Provisional paper-specific annotations, separate from the structural catalogue. */
(function(root){
 'use strict';
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const number=n=>n.toLocaleString('en-US');
 const flagLabels={quote_found:'Quote not found',quote_near_locator:'Quote not near cited lines',
   quote_within_35_words:'Quote exceeds 35 words',locator_has_valid_line:'Missing or invalid line reference',
   limited_text_coverage:'Limited text coverage',model_not_confirmed:'Model identification uncertain',
   scientific_uncertainty:'Uncertain association',mechanical_checks_missing_or_mismatched:'Source checks incomplete'};
 function sourceChecks(a){
   const reasons=[...new Set(a.reviewReasons||[])];
   if(!a.needsReview&&!reasons.length)return ' <span class="evidence-status">Automated checks passed</span>';
   if(!reasons.length)reasons.push('mechanical_checks_missing_or_mismatched');
   return reasons.map(reason=>' <span class="evidence-flag">'+esc(flagLabels[reason]||'Unrecognized source check flag')+'</span>').join('');
 }
 function create(catalogue,annotations){
   const data=annotations||{categories:[],problems:[],assessed:[],links:{}},links=data.links;
   const entries=new Map(catalogue.entries.map(e=>[e.id,e])),papers=new Map(catalogue.papers.map(p=>[p.id,p]));
   const assessed=new Set(data.assessed),byProblem=new Map(data.problems.map(p=>[p.id,p]));
   const categories=new Map(data.categories.map(c=>[c.id,c]));
   const search=(value,q)=>value.toLocaleLowerCase().includes(q.trim().toLocaleLowerCase());
   const entryLink=id=>'#entry/'+encodeURIComponent(id)+'?panel=problems';
   const problemLink=(id='',q='',category='')=>{
     const p=new URLSearchParams();if(q)p.set('search',q);if(category&&!id)p.set('category',category);
     return '#problems'+(id?'/'+encodeURIComponent(id):'')+(p.size?'?'+p:'');
   };
   function members(id,q=''){
     return [...entries.values()].filter(e=>links[e.id]?.[id]&&search(e.name,q));
   }
   const count=id=>Object.keys(links[id]||{}).length;
   const paperCount=id=>new Set(members(id).flatMap(e=>links[e.id][id].map(a=>a.paperId))).size;
   function method(){return '<details class="problem-method" id="problems-layer"><summary>About Problems</summary><p>Problems adds a literature-based layer to the atlas, connecting model entries to the particle-physics questions they are studied to address. It builds on the common gauge-algebra and matter representation, while retaining links to the supporting papers.</p><p>To construct this layer, Luna read each paper alongside its linked atlas entries and identified model-specific connections to the 13 problems shown here. Each association includes an explanation, source quotations and locators. Associations across papers may involve different interactions or parameter choices; they do not establish simultaneous solutions in one specified theory.</p><p>Other layers can be added in the same way, depending on the question or research interest: for example, mechanisms, experimental signatures, mass scales or observational constraints. Each layer can connect its own annotations and source evidence to the same underlying model entries.</p><p>The current associations are machine-extracted. Flags identify failed quotation, length, line-reference or text-coverage checks, including evidence used to identify the model. Passing these checks does not verify the scientific interpretation. Missing links mean none were detected; unassessed entries are identified separately. Source locators refer to the extracted paper text and may differ from PDF page numbers.</p></details>';}
   function searchForm(value,placeholder){return '<form id="problem-search-form" class="problem-search" role="search"><label class="search-label"><span class="sr-only">'+esc(placeholder)+'</span><input id="problem-search" type="search" placeholder="'+esc(placeholder)+'" value="'+esc(value)+'"></label><button class="problem-search-button" type="submit">Search</button></form>';}
   function overview(){
     if(!data.problems.length)return '<p class="empty">Problem annotations are unavailable.</p>';
     return '<p class="section-note problem-intro">Explore the problems studied with each model. <a href="#problems?about=layer">About this layer →</a></p>'+
       '<div class="problem-grid">'+data.problems.map(p=>{
         const models=members(p.id);
         return '<article class="problem-card"><p class="problem-eyebrow">'+esc(categories.get(p.category_id)?.label)+'</p><h2><a href="'+esc(problemLink(p.id))+'">'+esc(p.label)+'</a></h2><a class="problem-browse" href="'+esc(problemLink(p.id))+'" aria-label="Explore models for '+esc(p.label)+'"><span>'+number(models.length)+' model '+(models.length===1?'entry':'entries')+'</span><span aria-hidden="true">→</span></a></article>';
       }).join('')+'</div>'+method();
   }
   function source(a){
     const p=papers.get(a.paperId);if(!p)return '';
     return '<li class="problem-source"><a href="https://arxiv.org/abs/'+esc(p.arxiv)+'" target="_blank" rel="noopener noreferrer">'+esc(p.title)+' ↗</a><p class="reference-meta">arXiv:'+esc(p.arxiv)+sourceChecks(a)+'</p><p class="problem-rationale">'+esc(a.rationale)+'</p>'+a.evidence.map(e=>'<blockquote>'+esc(e.quote)+'<cite>'+esc(e.locator)+'</cite></blockquote>').join('')+'</li>';
   }
   function evidence(id,problem){
     const associations=[...(links[id]?.[problem]||[])].sort((a,b)=>Number(a.needsReview)-Number(b.needsReview)||a.paperId.localeCompare(b.paperId));
     return '<ol class="problem-sources">'+associations.slice(0,3).map(source).join('')+'</ol>'+(associations.length>3?'<details class="problem-more-sources"><summary>Show '+(associations.length-3)+' more supporting papers</summary><ol class="problem-sources">'+associations.slice(3).map(source).join('')+'</ol></details>':'');
   }
   function entry(id){
     if(!assessed.has(id))return '<section class="entry-detail problem-entry-panel"><h2>Problems</h2><p class="problem-empty">This entry has no valid paper assessment in the Luna run. It is unassessed, rather than a model with zero problems.</p><a href="#problems">Browse problems →</a></section>';
     const problems=data.problems.filter(p=>links[id]?.[p.id]);
     return '<section class="entry-detail problem-entry-panel"><div class="detail-heading"><h2>Problem associations</h2></div><p class="problem-panel-note">Detected across this entry’s papers. Associations may use different interactions or parameter choices.</p>'+(!problems.length?'<p class="problem-empty">No “addresses” associations were detected in the valid paper assessments. This does not establish that the model addresses no problems.</p>':'')+problems.map(p=>'<details class="problem-association"><summary><span>'+esc(p.label)+'</span><span class="problem-paper-count">'+links[id][p.id].length+' '+(links[id][p.id].length===1?'paper':'papers')+'</span></summary><p class="problem-definition">'+esc(p.include)+'</p>'+evidence(id,p.id)+'</details>').join('')+'<a class="problem-panel-link" href="#problems">Browse all problems →</a></section>';
   }
   function problem(id,q='',limit=20){
     const p=byProblem.get(id);
     if(!p)return '<p class="empty">Problem not found. <a href="#problems">Browse all problems</a></p>';
     const all=members(id),models=members(id,q),visible=models.slice(0,limit);
     return '<a class="problem-back" href="#problems">← All problems</a><div class="problem-focus-heading"><p class="problem-eyebrow">'+esc(categories.get(p.category_id)?.label)+'</p><h2>'+esc(p.label)+'</h2><p>'+esc(p.include)+'</p></div>'+
       '<div class="problem-result-toolbar">'+searchForm(q,'Search linked models')+'<span>'+number(models.length)+' model '+(models.length===1?'entry':'entries')+(q?' matching':'')+' · '+number(paperCount(id))+' supporting papers in total</span></div>'+
       '<div class="problem-models">'+visible.map(e=>'<article class="problem-model"><div class="problem-model-heading"><h3><a href="'+esc(entryLink(e.id))+'">'+esc(e.name)+'</a></h3><a class="problem-entry-link" href="'+esc(entryLink(e.id))+'">View entry →</a></div><p class="problem-model-meta">'+links[e.id][id].length+' supporting '+(links[e.id][id].length===1?'paper':'papers')+'</p><details class="problem-model-evidence"><summary>Supporting papers & evidence</summary>'+evidence(e.id,id)+'</details></article>').join('')+'</div>'+(!models.length?'<p class="empty">'+(all.length?'No linked models match this search.':'No associations were detected for this problem in the assessed corpus.')+'</p>':'')+(models.length>limit?'<button class="load-more" data-problem-more>Show more models ('+(models.length-limit)+' remaining)</button>':'')+method();
   }
   return {overview,problem,entry,count,assessed:id=>assessed.has(id),problemLink};
 }
 root.ProblemExplorer={create};
})(typeof window==='undefined'?globalThis:window);
