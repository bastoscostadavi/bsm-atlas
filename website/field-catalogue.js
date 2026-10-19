(function(root){
 'use strict';
 const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
 const math=x=>esc(x).replace(/bar\(([^()]*)\)/g,(_,label)=>'<span class="rep-conjugate" aria-label="conjugate '+label+'">'+label+'</span>');
 const shorthand=x=>({'g_SM':'𝔤<sub>SM</sub>','R_SM':'R<sub>SM</sub>','F_SM':'F<sub>SM</sub>','H_SM':'H<sub>SM</sub>','R_MSSM':'R<sub>MSSM</sub>'}[x]||math(x));
 const notationModes={dimensions:'Dimensions',dynkin:'Dynkin labels',young:'Young diagrams',compare:'Compare notations'};
 const sourceURL=p=>'https://arxiv.org/abs/'+p.arxiv;
 const pdfURL=e=>'https://arxiv.org/pdf/'+e.paper_version_id+(e.pdf_page?'#page='+e.pdf_page:'');
 function findEntries(data,{q='',algebra='',paper='',status='',core='',semisimple='',fullAlgebra='',abelianRank='',includePending=false}={}){
   const needle=q.trim().toLowerCase();
   return data.entries.filter(e=>e.publicationStatus==='ready'&&(!core||e.coreId===core)&&(!semisimple||e.semisimpleId===semisimple)&&(!fullAlgebra||e.fullAlgebraId===fullAlgebra)&&(abelianRank===''||e.abelianRank!==null&&String(e.abelianRank)===String(abelianRank))&&(!algebra||(algebra.startsWith('na:')?(data.semisimpleAlgebras||[]).some(a=>a.id===e.semisimpleId&&a.algebraSignature===algebra.slice(3)):e.algebraSignature===algebra))&&(!paper||e.paperIds.includes(paper))&&(!needle||[e.id,e.name,...(e.aliases||[]).flatMap(a=>[a.id,a.name]),e.algebraExpanded,e.baseline,...e.paperIds,...e.variants.flatMap(v=>[v.name,v.id,...v.regimes.flatMap(r=>r.fields.flatMap(f=>[f.label,f.representation,f.dynkinRepresentation,...(f.lorentz||[]).map(l=>l.dynkinRepresentation),...f.sourceRepresentations.map(s=>s.representation_label)]))]),...data.papers.filter(p=>e.paperIds.includes(p.id)).flatMap(p=>[p.title,p.authors,p.arxiv])].join(' ').toLowerCase().includes(needle)));
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
   const isCharge=components[0].factor==='u(1)',d=bundle?dimensionTuple(components):(components[0].value??'?');
   const exact=bundle?dynkinTuple(components):dynkinLabel(components[0]);
   const weights='<span class="math" title="'+esc(components.some(c=>c.factor!=='u(1)'&&!c.dynkin)?'Dynkin labels unresolved; original notation is retained in provenance':'Highest-weight Dynkin labels')+'">'+esc(exact)+'</span>';
   const readable='<span class="math" title="Dynkin labels: '+esc(exact)+'">'+math(d)+'</span>';
   const diagrams='<span class="young-block">'+components.map(c=>c.factor==='u(1)'?'<span class="young-charge">'+esc(c.value??'?')+'</span>':young(c)).join('')+'</span>';
   if(mode==='dynkin')return weights;
   if(mode==='young')return diagrams;
   if(mode==='compare')return '<div class="representation-compare">'+readable+'<span class="dynkin-alternative"><span class="notation-label">Dynkin</span>'+weights+'</span>'+diagrams+'</div>';
   return readable;
 }
 function weight(f,mode='dynkin'){
   if(mode==='young')return '<span class="young-block">'+f.components.filter(c=>!c.factor.startsWith('u(')).map(young).join('')+'</span>'+f.components.filter(c=>c.factor==='u(1)').map(c=>'<span class="weight-label">'+esc(c.role)+': '+esc(c.value??'?')+'</span>').join('');
   if(mode==='dynkin')return f.components.map(c=>'<span class="weight-label">'+esc(c.factor)+(c.role?' ['+esc(c.role)+']':'')+': '+esc(dynkinLabel(c))+'</span>').join('');
   return '<span class="math">'+math(f.representation)+'</span>';
 }
 function evidence(f){
   return '<details class="source-evidence"><summary>Source</summary><p>'+esc(f.sourceKind)+(f.sourceFieldId!==null&&f.sourceFieldId!==undefined?' · legacy source field '+f.sourceFieldId:'')+'</p><p>'+esc(f.conversion)+'</p>'+(f.sourceChirality?'<p>Source chirality: '+esc(f.sourceChirality)+'</p>':'')+'<p>Original multiplicity: '+esc(f.sourceMultiplicity??'not specified')+'</p>'+f.sourceRepresentations.map(r=>'<p><code>'+esc(r.representation_label||'')+(r.exact_charge!==null?' · charge '+esc(r.exact_charge):'')+'</code><br>'+esc(r.normalization_note||r.source_notation||'')+'</p>').join('')+(f.curatedCompletion?'<p>Completed colour assignment: '+esc(f.curatedCompletion.basis)+' <a href="'+esc(f.curatedCompletion.url)+'" target="_blank" rel="noopener noreferrer">'+esc(f.curatedCompletion.paper)+' · '+esc(f.curatedCompletion.locator)+' ↗</a></p>':'')+(f.sourceNote?'<p>'+esc(f.sourceNote)+'</p>':'')+(f.unconverted.length?'<p>Not fully converted: '+f.unconverted.map(esc).join('; ')+'</p>':'')+'<ul>'+f.evidence.map(a=>'<li>'+esc(a.claim)+'<br><span class="muted">'+esc(a.basis)+' · '+esc(a.review)+' · '+esc(a.stance)+' · assertion '+a.assertionId+'</span>'+a.locations.map(l=>'<p><a href="'+esc(pdfURL(l))+'" target="_blank" rel="noopener noreferrer">'+esc(l.paper_version_id)+' · '+esc(l.locator)+(l.pdf_page?' · PDF p. '+l.pdf_page:'')+' ↗</a></p>').join('')+'</li>').join('')+'</ul></details>';
 }
 function templateTable(template){return '<div class="matrix-wrap"><table class="template-table" aria-label="'+esc(template.name)+' reference"><thead><tr><th>Spacetime</th><th>𝔤<sub>SM</sub> · dimensions / Dynkin</th><th>Multiplicity</th></tr></thead><tbody>'+template.fields.flatMap(f=>f.lorentz.map(l=>'<tr title="'+esc(f.label)+'"><td class="math">'+esc(l.label).replaceAll('1/2','½')+'</td><td>'+representationMarkup(l.gaugeComponents||f.components,'dimensions')+'<span class="baseline-dynkin math">'+esc(dynkinTuple(l.gaugeComponents||f.components))+'</span></td><td>'+(Object.hasOwn(l,'copies')?l.copies:f.copies)+'</td></tr>')).join('')+'</tbody></table></div>';}
 function scalarRealityLabel(lorentz){return lorentz.component==='S'&&lorentz.reality!=='real_module'?'count pending':'';}

 function kindText(kinds){
   if(kinds.includes('S')&&kinds.includes('F'))return 'Scalar + Weyl fermion';
   return ({S:'Scalar',F:'Fermion',F_D:'Dirac fermion',V:'Vector','?':'Type unresolved'}[kinds[0]]||kinds.join(' + '));
 }
 function fieldType(f){
   if(f.kinds.length===2)return '<span title="One complex scalar and one left-handed Weyl fermion (a chiral supermultiplet)">'+kindText(f.kinds)+'</span>';
   const reality=(f.reality||'').toLowerCase();
   const scalar=f.kinds[0]==='S';
   const label=scalar&&reality==='complex'?'Complex scalar':scalar&&reality==='real'?'Real scalar':kindText(f.kinds);
   return esc(label);
 }
 function compactFields(fields){
   const result=[];
   for(const f of fields){
     const match=!f.representation.includes('?')&&f.copies!==null&&f.kinds.includes('S')&&result.find(p=>p.representation===f.representation&&p.kinds.join()===f.kinds.join()&&p.reality===f.reality&&p.copies!==null);
     if(match)match.copies+=f.copies;else result.push({...f});
   }
   return result;
 }

 function create(data,document){
   const state={q:'',algebra:'',paper:'',status:'',open:'',variant:'',regime:'',mode:'dimensions',inherited:false,view:'catalogue',browse:'algebras',core:'',semisimple:'',fullAlgebra:'',abelianRank:'',baselineOpen:{},limit:20};
   const paperById=new Map(data.papers.map(p=>[p.id,p]));
   const coreById=new Map((data.cores||[]).map(c=>[c.id,c]));
   const algebraById=new Map((data.semisimpleAlgebras||[]).map(a=>[a.id,a]));
   const fullAlgebraById=new Map((data.fullAlgebras||[]).map(a=>[a.id,a]));
   const entryById=new Map(data.entries.map(e=>[e.id,e]));
   for(const e of data.entries)for(const a of e.aliases||[])entryById.set(a.id,e);
   const linked=(p,coverage)=>data.entries.filter(e=>p.entryIds.includes(e.id)&&e.publicationStatus===coverage).length;
   function route(){
     const [raw,query='']=location.hash.slice(1).split('?');
     const p=new URLSearchParams(query);
     if(p.has('notation'))state.mode=Object.hasOwn(notationModes,p.get('notation'))?p.get('notation'):'dimensions';
     state.view=raw==='about'?'atlas':['atlas','notation','sources'].includes(raw)?raw:'catalogue';
     state.browse=raw==='entries'||/^(entry|model|core|full-algebra)\//.test(raw)?'entries':raw==='full-algebras'?'full-algebras':raw==='cores'||raw.startsWith('algebra/')?'cores':'algebras';
     state.core=raw.startsWith('core/')?decodeURIComponent(raw.slice(5)):p.get('core')||'';
     state.fullAlgebra=raw.startsWith('full-algebra/')?decodeURIComponent(raw.slice(13)):p.get('fullAlgebra')||'';
     state.semisimple=raw.startsWith('algebra/')?decodeURIComponent(raw.slice(8)):p.get('semisimple')||'';
     state.open='';
     if(raw.startsWith('entry/'))state.open=decodeURIComponent(raw.slice(6));
     if(raw.startsWith('model/')){
       const id=decodeURIComponent(raw.split('/')[1]);
       state.open=data.entries.find(e=>e.variants.some(v=>v.id===id))?.id||'';
     }
     for(const key of ['q','algebra','paper','status','abelianRank'])state[key]=p.get(key)||'';
     if(state.open&&!state.core)state.core=entryById.get(state.open)?.coreId||'';
     if(state.core)state.semisimple=coreById.get(state.core)?.semisimpleId||'';
     else if(state.open)state.semisimple=entryById.get(state.open)?.semisimpleId||'';
     else if(state.fullAlgebra)state.semisimple=fullAlgebraById.get(state.fullAlgebra)?.semisimpleId||'';
     if(entryById.has(state.open))state.open=entryById.get(state.open).id;
     state.status='';
   }
   function url(){
     const p=new URLSearchParams();
     for(const key of ['q','algebra','paper','status','abelianRank'])if(state[key])p.set(key,state[key]);
     if(state.open&&state.core)p.set('core',state.core);
     if(state.fullAlgebra&&(state.open||state.core||state.browse!=='entries'))p.set('fullAlgebra',state.fullAlgebra);
     if(state.browse==='entries'&&state.semisimple&&!state.core)p.set('semisimple',state.semisimple);
     if(state.browse==='full-algebras'&&state.semisimple)p.set('semisimple',state.semisimple);
     if(state.mode!=='dimensions')p.set('notation',state.mode);
     const target=state.view!=='catalogue'?state.view:state.open?'entry/'+encodeURIComponent(state.open):state.browse==='entries'?(state.core?'core/'+encodeURIComponent(state.core):state.fullAlgebra?'full-algebra/'+encodeURIComponent(state.fullAlgebra):'entries'):state.browse==='cores'?(state.semisimple?'algebra/'+encodeURIComponent(state.semisimple):'cores'):state.browse==='full-algebras'?'full-algebras':'catalogue';
     history.replaceState(null,'','#'+target+(p.size?'?'+p:''));
   }
   function level(){return state.browse;}
   function browseLink(target,extra={}){
     const p=new URLSearchParams();
     for(const key of ['q','algebra','paper','status','abelianRank'])if(state[key])p.set(key,state[key]);
     if(state.mode!=='dimensions')p.set('notation',state.mode);
     for(const [key,value] of Object.entries(extra))if(value)p.set(key,value);
     return '#'+target+(p.size?'?'+p:'');
   }
   function catalogueLinks(){
     const parent=coreById.get(state.core)?.semisimpleId||fullAlgebraById.get(state.fullAlgebra)?.semisimpleId||state.semisimple;
     const entryTarget=state.core?'core/'+state.core:state.fullAlgebra?'full-algebra/'+state.fullAlgebra:'entries';
     const entryContext=state.core&&state.fullAlgebra?{fullAlgebra:state.fullAlgebra}:!state.core&&!state.fullAlgebra?{semisimple:parent}:{};
     const links=[['algebras','Semisimple part',browseLink('catalogue')],
       ['full-algebras','Full',browseLink('full-algebras',{semisimple:parent})],
       ['cores','Semisimple part',browseLink(parent?'algebra/'+parent:'cores')],
       ['entries','Full',browseLink(entryTarget,entryContext)]];
     const link=([id,label,href],group)=>'<li><a aria-label="'+group+' — '+label+'" href="'+esc(href)+'"'+(state.view==='catalogue'&&level()===id?' aria-current="page"':'')+'>'+label+'</a></li>';
     const group=(id,label,items)=>'<div class="catalogue-group"><p id="'+id+'" class="catalogue-group-label">'+label+'</p><ul aria-labelledby="'+id+'">'+items.map(item=>link(item,label)).join('')+'</ul></div>';
     return group('catalogue-algebra-label','Gauge algebra',links.slice(0,2))+
       group('catalogue-matter-label','Gauge algebra and matter representations',links.slice(2));
   }
   function updateCatalogueMenu(){
     const navigation=document.getElementById('catalogue-views');
     if(navigation)navigation.innerHTML=catalogueLinks();
     document.getElementById('catalogue-menu')?.setAttribute?.('data-active',String(state.view==='catalogue'));
   }
   function baseline(code){
     return code?'<a class="baseline-chip" href="#notation" title="See the '+esc(code)+' definition">'+shorthand(code)+'</a>':'';
   }
   function summary(e){
     const fs=compactFields(e.summaryFields);
     return baseline(e.baseline)+(fs.length&&e.baseline?' <span class="sum-sign">+</span>':'')+
       fs.slice(0,3).map(f=>'<span class="summary-multiplet"><span class="type-tag">'+fieldType(f)+'</span><span class="math">'+esc(f.copies??'?')+' × '+math(f.representation)+'</span></span>').join('')+
       (fs.length>3?'<button class="text-button" data-open="'+esc(e.id)+'">+'+(fs.length-3)+' more</button>':'')+
       (!fs.length&&e.baseline!=='R_MSSM'?'<span class="subtle">Additional sector not extracted</span>':'');
   }
   function detail(e){
     const v=e.variants.find(v=>v.id===state.variant)||e.variants.find(v=>v.id===e.primaryVariant)||e.variants[0];
     const r=v.regimes.find(r=>String(r.id)===String(state.regime))||v.regimes.find(r=>r.id===e.primaryRegime)||v.regimes.find(r=>r.factors.length)||v.regimes[0];
     const fields=r.fields.filter(f=>!f.excludedCoordinate&&(state.inherited||!f.inherited));
     const normalization=r.factors.filter(f=>f.normalization).map(f=>'<li>'+esc(f.label)+' ['+esc(f.role)+']: '+(f.normalization.scale?'q<sub>atlas</sub> = '+esc(f.normalization.scale)+' q<sub>source</sub>':'Primitive unit unresolved')+' · '+esc(f.normalization.scope)+' · '+esc(f.normalization.status.replaceAll('_',' '))+'</li>').join('');
     return '<section class="entry-detail" id="detail-'+esc(e.id)+'">'+
       '<div class="detail-heading"><h2>'+esc(e.name)+'</h2><button class="icon-button" data-close aria-label="Close model details">×</button></div>'+
       (e.parameters?'<p class="coverage-note">Source-defined symbolic charge family.</p>':'')+
       '<details class="detail-options"'+(state.variant||state.regime?' open':'')+'><summary>Description</summary><div class="detail-controls">'+
       (e.variants.length>1?'<label>Variant<select id="variant-select">'+e.variants.map(x=>'<option value="'+esc(x.id)+'"'+(x.id===v.id?' selected':'')+'>'+esc(x.name)+'</option>').join('')+'</select></label>':'')+
       (v.regimes.length>1?'<label>Regime<select id="regime-select">'+v.regimes.map(x=>'<option value="'+x.id+'"'+(x.id===r.id?' selected':'')+'>'+esc(x.description)+'</option>').join('')+'</select></label>':'')+
       '</div></details>'+
       '<p class="detail-algebra math">'+shorthand(r.algebra)+'<span class="subtle">'+(r.algebra==='g_SM'?'':esc(r.algebraExpanded))+'</span></p>'+
       (r.baseline?'<details class="baseline-expanded"><summary>'+shorthand(r.baseline)+' <span class="subtle">Show fields</span></summary>'+templateTable(data.templates[r.baseline])+'</details>':'')+
       '<details class="provenance"><summary>Provenance</summary><p>'+esc(e.groupingBasis)+'</p><p>'+esc(v.scope||'')+'</p><p>'+esc(v.baselineSource||'No complete baseline recorded.')+'</p>'+
       (e.reextractions?.length?'<h3>Source-backed re-extraction</h3>'+e.reextractions.map(x=>'<p>'+esc(x.paperId)+' · '+esc(x.reviewedOn)+' · agent source-checked within this scope: '+esc(x.inspectedScope)+' <a href="'+esc(x.evidenceURL)+'" target="_blank" rel="noopener noreferrer">Evidence & normalized candidate ↗</a></p>').join('')+'<p>Not an independent physics or whole-paper verification. Original assertions retain their original review state.</p>':'')+
       '<p class="subtle">'+esc(v.id)+' · regime '+r.id+(r.dimension?' · '+esc(r.dimension)+'D':'')+'</p>'+
       (v.baselineParent?'<p>Inherited sector: <a href="#model/'+encodeURIComponent(v.baselineParent)+'">parent record ↗</a>. Not silently copied into this regime.</p>':'')+
       '<p>Spacetime interpretation: '+esc((r.fields.find(f=>f.lorentz?.length)?.lorentz[0].spacetime.note)||'not extracted')+'</p>'+
       '<h3>Charge normalization</h3><ul>'+normalization+'</ul><ul>'+r.notes.map(n=>'<li>'+esc(n)+'</li>').join('')+'</ul>'+
       '<div class="field-sources">'+r.fields.filter(f=>!f.excludedCoordinate).map(f=>'<h3>'+esc(f.label)+'</h3>'+evidence(f)).join('')+'</div><p>Legacy assertions remain unchanged; accepted re-extractions have their own scoped review state. A recorded inventory is not an anomaly, viability or independent physics certificate.</p></details>'+
       '<div class="entry-source-links">'+e.paperIds.map(id=>'<a href="'+esc(sourceURL(paperById.get(id)))+'" target="_blank" rel="noopener noreferrer">'+esc(id)+' · '+esc(paperById.get(id).arxiv)+' ↗</a>').join('')+'</div></section>';
   }

   function chosen(e){
     const v=e.variants.find(v=>v.id===state.variant)||e.variants.find(v=>v.id===e.primaryVariant)||e.variants[0];
     const r=v.regimes.find(r=>String(r.id)===String(state.regime))||v.regimes.find(r=>r.id===e.primaryRegime)||v.regimes.find(r=>r.factors.length)||v.regimes[0];
     return {v,r};
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
     return parameterMetadata(r)+'<div class="matrix-wrap"><table style="'+(columns.length>2?'min-width:'+((columns.length+2)*105+80)+'px':'')+'" class="representation-matrix'+(isCore?' core-matrix':'')+'" aria-label="'+(isCore?'Representations in non-Abelian core ':'Matter content of ')+esc(e.name)+'"><thead><tr><th>Spacetime<span class="matrix-algebra">'+esc(algebra)+'</span></th>'+columns.map(c=>'<th>'+gaugeHeading(c)+(r.chargeConvention&&c.positions.some(i=>r.factors[i].type==='U1')?'<span class="matrix-algebra">'+esc(r.chargeConvention)+'</span>':'')+algebraDiagrams(c,r)+'</th>').join('')+'<th>Multiplicity</th>'+'</tr></thead><tbody>'+
       (r.baseline?'<tr class="baseline-group"><td colspan="'+(columns.length+2)+'"><button class="text-button" data-baseline="'+esc(e.id)+'" aria-expanded="'+include+'">'+shorthand(r.baseline)+'<span> '+(include?'−':'+')+'</span></button></td></tr>':'')+
       rows.map(row=>{
         const l=row.lorentz,condition=scalarRealityLabel(l,row.components);
         return '<tr class="'+(row.template?'template-row':'')+'" title="'+esc(row.labels.join(', '))+'"><td><span class="math">'+esc(l.label).replaceAll('1/2','½')+'</span>'+(dimensions.length>1?'<span class="matrix-note">'+esc(l.spacetime.dimension||'D unknown')+'D</span>':'')+(condition?'<span class="matrix-note">'+esc(condition)+'</span>':'')+(l.status!=='resolved'?'<span class="matrix-note unresolved">'+(l.status==='source_chirality_unresolved'?'source handedness unresolved':'unresolved')+'</span>':'')+'</td>'+columns.map(c=>'<td>'+gaugeCell(row,c,r)+'</td>').join('')+'<td>'+esc(row.copies??'?')+'</td>'+'</tr>';
       }).join('')+(!rows.length?'<tr><td colspan="'+(columns.length+2)+'" class="subtle">No independent additional fields extracted for this description.</td></tr>':'')+'</tbody></table></div>';
   }
   function parameterMetadata(r){
     if(!Object.keys(r.parameters||{}).length)return '';
     const mapping=r.reextraction?.parameterRenaming;
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
       const names=c.entryIds.filter(id=>matched.has(id)).map(id=>entryById.get(id)?.name).filter(Boolean);
       const count=c.entryIds.filter(id=>matched.has(id)).length,href=browseLink('core/'+c.id);
       return '<article class="model-entry core-entry"><header class="model-heading"><h2><a class="core-title" href="'+esc(href)+'">'+math(c.algebra)+'</a></h2><a class="core-open" href="'+esc(href)+'">Open '+count+' '+(count===1?'entry':'entries')+' →</a></header><p class="core-members">'+names.map(esc).join(' · ')+'</p>'+matrix({id:c.id,name:c.algebra},c.regime)+'</article>';
     }).join('')+(cores.length>visible.length?'<button class="load-more" data-more>Show more cores ('+(cores.length-visible.length)+' remaining)</button>':'')+(!cores.length?'<p class="empty">No matter spectra match these filters. <button class="text-button" data-reset>Reset</button></p>':'');
     root.AtlasDiagrams?.render(document);
   }
   function rows(){
     updateCatalogueMenu();
     const reset=document.getElementById('reset-filters');
     if(reset)reset.hidden=!['q','algebra','paper','status','abelianRank'].some(k=>state[k]);
     const entries=findEntries(data,{...state,includePending:level()!=='entries'}),openIndex=entries.findIndex(e=>e.id===state.open);
     if(level()==='algebras')return algebraCards(entries);
     if(level()==='full-algebras')return fullAlgebraCards(entries);
     if(level()==='cores')return coreCards(entries);
     state.limit=Math.max(state.limit,openIndex+1);
     const visible=entries.slice(0,state.limit);
     document.getElementById('result-count').textContent=entries.length+(entries.length===1?' entry':' entries');
     document.getElementById('model-entries').innerHTML=visible.map(e=>{
       const r=chosen(e).r;
       return '<article class="model-entry" id="model-'+esc(e.id)+'"><header class="model-heading"><h2>'+esc(e.name)+'</h2><div class="source-buttons">'+e.paperIds.map(id=>'<button class="source-badge" data-paper="'+esc(id)+'" title="'+esc(paperById.get(id).title)+'">'+esc(id)+'</button>').join('')+'</div><button class="text-button" data-open="'+esc(e.id)+'" aria-expanded="'+(state.open===e.id)+'">Details '+(state.open===e.id?'−':'+')+'</button></header>'+matrix(e,r)+(state.open===e.id?detail(e):'')+'</article>';
     }).join('')+(entries.length>visible.length?'<button class="load-more" data-more>Show more models ('+(entries.length-visible.length)+' remaining)</button>':'')+(!entries.length?'<p class="empty">No entries match these filters. <button class="text-button" data-reset>Reset</button></p>':'');
     root.AtlasDiagrams?.render(document);
   }
   function notation(){return '<section id="notation"><div class="section-heading"><h2>Notation</h2><span class="eyebrow">Convention '+esc(data.version)+'</span></div><details class="notation-panel" id="notation-guide"><summary>Notation guide</summary><div class="notation-grid"><div>'+
     '<h3>Gauge algebra</h3><p>The atlas records the local gauge algebra of each model. For the Standard Model we write <span class="math">𝔤<sub>SM</sub> = su(3) ⊕ su(2) ⊕ u(1)</span>. Its semisimple part is su(3) ⊕ su(2), obtained by omitting the U(1) factor. These labels do not specify a global gauge group or a quotient by its centre.</p><p>Simple factors are identified by Cartan type and rank, and their order is standardized throughout the database. Each matter representation follows that same order. Swapping factors, together with their representations, therefore does not create a new entry.</p>'+
     '<h3>Gauge representations</h3><p>The tables initially show representations by their dimensions. For <span class="math">𝔤<sub>SM</sub></span>, the tuple <span class="math">(3, 2; 1)</span> denotes an su(3) triplet, an su(2) doublet and U(1) charge +1. Non-Abelian representations appear before the semicolon; Abelian charges follow it.</p><p>Dimensions do not always distinguish representations, so the database stores their highest-weight Dynkin labels. There is one nonnegative integer for each simple-root node, in <a href="'+esc(data.representationConvention.nodeNumberingReference)+'">Bourbaki order</a>. The same example is <span class="math">([1,0], [1]; 1)</span>. For su(3), [1,0] is the fundamental and [0,1] its conjugate; all-zero labels denote a singlet.</p>'+
     '<h3>Spacetime representations</h3><p>The Spacetime column describes how the field transforms under Lorentz symmetry, independently of its gauge representation. In four dimensions we use <span class="math">(j<sub>L</sub>, j<sub>R</sub>)</span>: a scalar is (0,0), a left-handed Weyl fermion (½,0), and a vector (½,½). These are field representations, not counts of on-shell polarizations.</p><p>All independent 4D Weyl fermions are written as left-handed fields. A right-handed field is replaced by its left-handed charge conjugate, which conjugates its non-Abelian representations and negates its U(1) charges. A Dirac fermion contributes two independent Weyl components. Higher-dimensional entries use the appropriate Lorentz Dynkin labels.</p>'+
     '<h3>Multiplicity</h3><p>Multiplicity counts independent fields with the same Lorentz and gauge representations; it is not the dimension of either representation. The SM quark doublet, for example, has multiplicity 3 because there are three generations, not 6 because it transforms as a colour triplet and a weak doublet.</p><p>Scalars count irreducible real gauge modules. A complex scalar in a real-type gauge representation contributes two such modules; in a complex- or pseudoreal-type representation it contributes one. A neutral complex singlet therefore counts 2, while a charged Higgs doublet counts 1. Conjugate scalar representations describe the same real module; this identification does not apply to Weyl fermions.</p></div><div>'+
     '<h3>U(1) charges</h3><p>For each U(1) factor, a fixed charge assignment is rescaled so that all charges are integers with gcd 1. The same normalization is applied to the entire matter content, including scalars and fermions. Ordinary SM hypercharge is therefore written as <span class="math">q = 6Y</span>.</p><p>Each row carries one charge per U(1) factor. Three generations with charges [0,−3,3] must be recorded as separate rows, rather than as three identical fields. With several U(1) factors, the charges follow the generator order shown in the columns.</p>'+
     '<h3>Symbolic charge families</h3><p>A paper may specify a family of charge assignments rather than a single numerical choice. We keep the family as one entry, with integer parameters <code>z1, z2, …</code> and the constraints stated by the source. Charge polynomials are expanded, like terms are collected, and monomials follow descending lexicographic order. For example:</p><p><code>(z1 + z2)**2 → z1**2 + 2*z1*z2 + z2**2</code></p><p>Parameter names are assigned consistently across the charges and constraints. Renaming parameters or reordering factors and rows does not create a new template. Constraints remain part of the entry, but we do not try to prove that differently written domains or general reparameterizations describe the same family. Choosing an allowed integer point gives a numerical assignment, which is then normalized to primitive charges. Original parameter names are available under Parameter constraints.</p>'+
     '<h3>Display and diagrams</h3><p>The notation selector changes how a representation is displayed, not how it is stored. Choose Dimensions, Dynkin labels, Young diagrams or Compare notations to see the alternatives together. Young diagrams are available for A-series representations; an unavailable diagram does not mean the representation is unknown. The small Dynkin diagrams in column headings describe the gauge algebra, not an individual matter representation.</p>'+
     '<h3>SM shorthand</h3><p>We use <span class="math">R<sub>SM</sub> = F<sub>SM</sub> ⊕ H<sub>SM</sub></span> to avoid repeating the SM matter content in every entry. F<sub>SM</sub> contains three generations of left-handed Weyl fermions, and H<sub>SM</sub> is one complex Higgs doublet. No right-handed neutrino is included. Gauge connections are already implied by the algebra and are not additional matter rows.</p><p>The supersymmetric baseline <span class="math">R<sub>MSSM</sub></span> replaces R<sub>SM</sub>; it is not added to it. Its chiral multiplets each contain one complex scalar and one left-handed Weyl fermion.</p><details id="sm-reference"><summary>SM matter table</summary>'+templateTable(data.templates.R_SM)+'</details>'+
     '<details id="mssm-reference"><summary>MSSM matter table</summary><p>The MSSM contains three chiral matter families, two Higgs chiral multiplets and the gauge-adjoint gauginos.</p>'+templateTable(data.templates.R_MSSM)+'</details>'+
     '<p><a href="https://github.com/bastoscostadavi/bsm-atlas/blob/main/atlas/FIELD_CONTENT_CONVENTIONS.md">Full conventions ↗</a></p></div></div></details></section>';}

   function sources(){
     return '<section id="sources"><p class="section-note">Papers are independent records. Some have no associated model.</p><div class="source-list">'+data.papers.map(p=>
       '<details class="paper-item" id="source-'+esc(p.id)+'"><summary><span class="source-badge">'+esc(p.id)+'</span><span class="paper-title">'+esc(p.title)+'</span><span class="paper-count">'+p.entryIds.length+'</span></summary><div class="paper-body"><p>'+esc(p.authors)+'</p><a href="'+esc(sourceURL(p))+'" target="_blank" rel="noopener noreferrer">arXiv:'+esc(p.arxiv)+' ↗</a>'+
       (p.entryIds.length?'<p>'+(linked(p,'ready')?'<button class="text-button" data-paper="'+esc(p.id)+'">'+linked(p,'ready')+' concrete spectra →</button>':'')+'</p>':'<p>'+esc(p.noModelReason||p.referenceNotes?.join(' ')||'No linked BSM model.')+'</p>')+
       '<details class="provenance"><summary>Inspection details</summary><p>'+esc(p.kind)+' · '+esc(p.inspectionStatus)+' · '+esc(p.reviewStatus)+'</p><h3>Original scope</h3><p>'+esc(p.inspectedScope)+'</p>'+(p.reextractions?.length?'<h3>Accepted gauge/matter re-extraction</h3>'+[...new Map(p.reextractions.map(x=>[x.inspectedScope,x])).values()].map(x=>'<p>'+esc(x.reviewedOn)+' · '+esc(x.inspectedScope)+' <a href="'+esc(x.evidenceURL)+'" target="_blank" rel="noopener noreferrer">Evidence ↗</a></p>').join('')+'<p>Agent source-checked within the stated scope; not a whole-paper or independent physics review.</p>':'')+'<h3>Limitations</h3><p>'+esc(p.limitations||'No limitation text recorded; completeness not established.')+'</p></details></div></details>').join('')+'</div></section>';
   }
   function atlasIntroduction(){
     return '<article class="about-data"><p>Gauge symmetry and the representations of matter are the defining ingredients of the Standard Model. Its peculiar gauge algebra, chiral matter content and three generations form a striking structure whose origin remains unexplained. It can seem ungainly, even arbitrary, in its particulars, yet beautiful in its workings: gauge anomalies cancel exactly, and its dynamics span confinement, spontaneous symmetry breaking and weakly coupled scattering. In its minimal form, with massless neutrinos, the theory has just 19 free parameters. Once their values are fixed, it makes infinitely many predictions, including the <a href="https://arxiv.org/abs/2209.13084">electron’s magnetic moment</a>, among the most precise in all of science. BSM Atlas takes these defining ingredients as a starting point for charting extensions of the Standard Model. Each entry gives the gauge algebra, the Lorentz and gauge representations of the matter fields, and their multiplicities, using a common notation and linking to the papers in which they are studied.</p>'+
       '<p>The catalogue can be read at different levels of detail. The <a href="#full-algebras">gauge-algebra view</a> shows which algebras occur, while the <a href="#entries">full entries</a> also give their matter representations, multiplicities and charges. To compare models independently of their U(1) factors, the semisimple views retain either <a href="#catalogue">the algebras alone</a> or <a href="#cores">the algebras and their matter</a>. For U(1) factors, an entry may specify fixed charges or a family of charge assignments described by integer parameters and constraints.</p>'+
       '<p>We build the atlas from arXiv papers, extracting the gauge algebra, matter representations and multiplicities in each model. Before an entry is added, its content is converted to the atlas conventions and checked against the existing catalogue. Models with identical field content share an entry, with links to their source papers and extraction evidence. Only complete specifications are included. Papers may study different interactions or physical assumptions for the same field content; grouping them together does not identify them as equivalent physical theories or certify their consistency.</p>'+
       '<p>We also intend to use the atlas in two related projects. In <a href="https://github.com/bastoscostadavi/bsm-ai-search">bsm-ai-search</a>, we aim to use AI to propose theories and calculate and test their predictions. In <a href="https://github.com/bastoscostadavi/bsm-foundation-model">bsm-foundation-model</a>, we aim to learn from simulations how to infer probability distributions over theories and their parameters from experimental data.</p></article>';
   }
   function catalogue(){
     const current=level(),isCores=current==='cores',isAlgebras=current==='algebras',isFullAlgebras=current==='full-algebras',isGauge=isAlgebras||isFullAlgebras;
     const algebras=(data.semisimpleAlgebras||[]).map(a=>['na:'+a.algebraSignature,a.algebra]).sort((a,b)=>a[1].localeCompare(b[1]));
     if(state.algebra&&!algebras.some(([id])=>id===state.algebra))algebras.push([state.algebra,data.entries.find(e=>e.algebraSignature===state.algebra)?.algebraExpanded||state.algebra]);
     const ranks=[...new Set(data.entries.map(e=>e.abelianRank).filter(n=>Number.isInteger(n)))].sort((a,b)=>a-b);
     const active=['algebra','paper','status','abelianRank'].filter(k=>state[k]).length;
     const p=paperById.get(state.paper);
     const core=coreById.get(state.core);
     const fullAlgebra=fullAlgebraById.get(state.fullAlgebra);
     const algebra=algebraById.get(core?.semisimpleId||state.semisimple);
     const context=state.fullAlgebra?'<span class="math">'+math(fullAlgebra?.algebra||'Full algebra not found')+'</span>':state.core?'<span class="math">'+math(core?.algebra||'Core not found')+'</span>':state.semisimple?'<span class="math">'+math(algebra?.algebra||'Algebra not found')+'</span>':'';
     const description=isAlgebras?'Gauge algebras, with matter and all U(1) factors omitted.':isFullAlgebras?'Gauge algebras, with matter omitted and all U(1) factors included.':isCores?'Gauge algebras and matter representations, with all U(1) factors omitted.':'Gauge algebras and matter representations, with all U(1) factors included.';
     return (context?'<p class="layer-context">'+context+'</p>':'')+'<p class="section-note">'+description+'</p><div class="toolbar" role="search" aria-label="Catalogue search"><label class="search-label"><span class="sr-only">Catalogue search</span><input type="search" id="entry-search" placeholder="Gauge algebra, representation, model or paper" value="'+esc(state.q)+'"></label>'+
       (!isGauge?'<label class="notation-select"><span class="sr-only">Representation notation</span><select id="notation-select">'+Object.entries(notationModes).map(([id,label])=>'<option value="'+id+'"'+(state.mode===id?' selected':'')+'>'+label+'</option>').join('')+'</select></label>':'')+
       '<details class="filter-panel"'+(active?' open':'')+'><summary>Filters'+(active?' · '+active:'')+'</summary><div class="filter-fields"><label>Semisimple part<select id="algebra-filter"><option value="">All semisimple parts</option>'+algebras.map(([id,label])=>'<option value="'+esc(id)+'"'+(state.algebra===id?' selected':'')+'>'+esc(label)+'</option>').join('')+'</select></label><label>Paper<select id="paper-filter"><option value="">All papers</option>'+data.papers.map(p=>'<option value="'+esc(p.id)+'"'+(state.paper===p.id?' selected':'')+'>'+esc(p.id)+' — '+esc(p.title)+'</option>').join('')+'</select></label><label>U(1) factors<select id="abelian-rank-filter"><option value="">Any number</option>'+ranks.map(n=>'<option value="'+n+'"'+(String(n)===state.abelianRank?' selected':'')+'>'+n+'</option>').join('')+'</select></label></div></details>'+
       '<details class="download-menu"><summary>Download</summary><div><a href="downloads/'+(isAlgebras?'semisimple-algebras.csv':isFullAlgebras?'full-gauge-algebras.csv':isCores?'nonabelian-cores.csv':'field-catalogue.csv')+'" download>CSV</a><a href="field-catalogue.json" download>JSON</a><a href="downloads/field-catalogue.sqlite" download>SQLite</a></div></details></div>'+
       (p?'<div class="selected-paper"><span>'+esc(p.id)+'</span><a href="'+esc(sourceURL(p))+'" target="_blank" rel="noopener noreferrer">'+esc(p.title)+' ↗</a></div>':'')+
       '<div class="results-bar"><span id="result-count"></span><span class="catalogue-disclaimer">'+(isAlgebras?'Matter & U(1) factors omitted':isFullAlgebras?'Matter omitted':isCores?'All U(1) factors omitted':'Real scalar modules · LH Weyl')+'</span><button id="reset-filters" class="text-button" data-reset'+(['q','algebra','paper','status','abelianRank'].some(k=>state[k])?'':' hidden')+'>Reset</button></div>'+
       '<div id="model-entries" aria-label="Model matter content"></div>';
   }
   function render(){
     const titles={catalogue:'Gauge algebras & matter.',atlas:'What is the atlas?',sources:'Papers.',notation:'Notation.'};
     document.getElementById('page-title').textContent=state.view==='catalogue'?({algebras:'Semisimple parts of gauge algebras.','full-algebras':'Full gauge algebras.',cores:'Semisimple matter spectra.',entries:'Full matter spectra.'}[level()]):titles[state.view];
     const key=document.getElementById('notation-key');
     if(key)key.hidden=state.view!=='catalogue'||level()!=='entries';
     const content=document.getElementById('view-content');
     content.className=state.view+'-view';
     content.innerHTML=state.view==='atlas'?atlasIntroduction():state.view==='sources'?sources():state.view==='notation'?notation():catalogue();
     if(state.view==='catalogue')rows();else updateCatalogueMenu();
     if(state.view==='notation')document.getElementById('notation-guide').open=true;
     root.AtlasDiagrams?.render(document);
     if(document.querySelectorAll)document.querySelectorAll('.site-header nav > a').forEach(a=>a.setAttribute('aria-current',a.getAttribute('href')==='#'+state.view?'page':'false'));
   }
   function start(){
     route();render();
     const menu=document.getElementById('catalogue-menu');
     const closeMenu=()=>{menu.open=false;};
     menu.addEventListener('click',e=>{if(e.target.closest('a'))closeMenu();});
     menu.addEventListener('focusout',e=>{if(e.relatedTarget&&!menu.contains(e.relatedTarget))closeMenu();});
     document.addEventListener('click',e=>{if(!menu.contains(e.target))closeMenu();});
     document.addEventListener('keydown',e=>{if(e.key==='Escape'&&menu.open){closeMenu();menu.querySelector('summary').focus();e.preventDefault();}});
     const content=document.getElementById('view-content');
     content.addEventListener('input',e=>{if(e.target.id==='entry-search'){state.q=e.target.value;state.open='';url();rows();}});
     content.addEventListener('change',e=>{
       const key={'algebra-filter':'algebra','paper-filter':'paper','status-filter':'status','abelian-rank-filter':'abelianRank'}[e.target.id];
       if(key){state[key]=e.target.value;state.open='';state.limit=20;url();render();}
       else if(e.target.id==='variant-select'){state.variant=e.target.value;state.regime='';rows();}
       else if(e.target.id==='regime-select'){state.regime=e.target.value;rows();}
       else if(e.target.id==='notation-select'){state.mode=e.target.value;url();rows();}
       else if(e.target.id==='show-inherited'){state.inherited=e.target.checked;rows();}
     });
     content.addEventListener('click',e=>{
       const open=e.target.closest('[data-open]'),paper=e.target.closest('[data-paper]');
       if(e.target.closest('[data-more]')){state.limit+=20;rows();return;}
       const base=e.target.closest('[data-baseline]');
       if(base){state.baselineOpen[base.dataset.baseline]=!state.baselineOpen[base.dataset.baseline];rows();return;}
       if(open){
         const same=state.open===open.dataset.open;
         state.open=same?'':open.dataset.open;state.variant='';state.regime='';state.inherited=false;
         url();rows();
       }else if(e.target.closest('[data-close]')){state.open='';url();rows();}
       else if(paper){state.view='catalogue';state.browse='entries';state.core='';state.semisimple='';state.fullAlgebra='';state.algebra='';state.abelianRank='';state.paper=paper.dataset.paper;state.status='';state.open='';url();render();document.getElementById('catalogue').scrollIntoView();}
       else if(e.target.closest('[data-reset]')){Object.assign(state,{q:'',algebra:'',paper:'',status:'',abelianRank:'',open:''});url();render();}
     });
     window.addEventListener('hashchange',()=>{closeMenu();route();render();});
     let theme='light';try{theme=localStorage.getItem('atlas-theme')||'light';}catch{}
     const button=document.getElementById('theme-toggle');
     const setTheme=t=>{document.documentElement.dataset.theme=t;button.setAttribute('aria-label','Switch to '+(t==='dark'?'light':'dark')+' theme');button.setAttribute('title','Switch to '+(t==='dark'?'light':'dark')+' theme');};
     setTheme(theme==='dark'?'dark':'light');
     button.addEventListener('click',()=>{theme=document.documentElement.dataset.theme==='dark'?'light':'dark';setTheme(theme);try{localStorage.setItem('atlas-theme',theme);}catch{}});
   }
   return {start,state,render,rows,route,url};
 }
 root.FieldCatalogue={create,findEntries,esc,young,weight,kindText,compactFields,dynkinTuple,scalarRealityLabel};
 if(root.document&&root.FIELD_CATALOGUE)create(root.FIELD_CATALOGUE,root.document).start();
})(typeof window==='undefined'?globalThis:window);
