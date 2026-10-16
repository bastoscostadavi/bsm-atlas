(function(root){
 'use strict';
 const esc=x=>String(x??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
 const math=x=>esc(x).replaceAll('bar(3)','3̅').replaceAll('bar(4)','4̅').replaceAll('bar(5)','5̅').replaceAll('bar(6)','6̅').replaceAll('bar(10)','1̅0̅');
 const shorthand=x=>({'g_SM':'𝔤<sub>SM</sub>','R_SM':'R<sub>SM</sub>','F_SM':'F<sub>SM</sub>','H_SM':'H<sub>SM</sub>','R_MSSM':'R<sub>MSSM</sub>'}[x]||math(x));
 const statuses={recorded_content:'Recorded',partial:'Incomplete',parameterized:'Parameterized'};
 const sourceURL=p=>'https://arxiv.org/abs/'+p.arxiv;
 const pdfURL=e=>'https://arxiv.org/pdf/'+e.paper_version_id+(e.pdf_page?'#page='+e.pdf_page:'');
 function findEntries(data,{q='',algebra='',paper='',status=''}={}){
   const needle=q.trim().toLowerCase();
   return data.entries.filter(e=>(!algebra||e.algebraSignature===algebra)&&(!paper||e.paperIds.includes(paper))&&(!status||e.status===status)&&(!needle||[e.id,e.name,e.algebraExpanded,e.baseline,...e.paperIds,...e.variants.flatMap(v=>[v.name,v.id,...v.regimes.flatMap(r=>r.fields.flatMap(f=>[f.label,f.representation,...f.sourceRepresentations.map(s=>s.representation_label)]))]),...data.papers.filter(p=>e.paperIds.includes(p.id)).flatMap(p=>[p.title,p.authors,p.arxiv])].join(' ').toLowerCase().includes(needle)));
 }
 function young(component){
   if(!component.youngRows)return '<span class="young-caption">'+esc(component.factor)+': unavailable</span>';
   if(!component.youngRows.length)return '<span class="young-caption">'+esc(component.factor)+': singlet</span>';
   return '<span><span class="young-caption">'+esc(component.factor)+'</span><span class="young-diagram" role="img" aria-label="Young diagram with row lengths '+esc(component.youngRows.join(', '))+'">'+component.youngRows.map(n=>'<span class="young-row">'+'<i class="young-box"></i>'.repeat(Math.min(n,12))+(n>12?'…':'')+'</span>').join('')+'</span></span>';
 }
 function weight(f,mode){
   if(mode==='young')return '<span class="young-block">'+f.components.filter(c=>!c.factor.startsWith('u(')).map(young).join('')+'</span>'+f.components.filter(c=>c.factor==='u(1)').map(c=>'<span class="weight-label">q ['+esc(c.role)+'] = '+esc(c.value??'?')+'</span>').join('');
   if(mode==='dynkin')return f.components.map(c=>'<span class="weight-label">'+esc(c.factor)+(c.role?' ['+esc(c.role)+']':'')+': '+(c.factor==='u(1)'?'q = '+esc(c.value??'?'):c.dynkin?'['+c.dynkin.join(',')+']':'not uniquely converted')+'</span>').join('');
   return '<span class="math">'+math(f.representation)+'</span>';
 }
 function evidence(f){
   return '<details class="source-evidence"><summary>Source</summary><p>'+esc(f.sourceKind)+' · source field '+f.sourceFieldId+'</p><p>'+esc(f.conversion)+'</p>'+(f.sourceChirality?'<p>Source chirality: '+esc(f.sourceChirality)+'</p>':'')+'<p>Original multiplicity: '+esc(f.sourceMultiplicity??'not specified')+'</p>'+f.sourceRepresentations.map(r=>'<p><code>'+esc(r.representation_label||'')+(r.exact_charge!==null?' · charge '+esc(r.exact_charge):'')+'</code><br>'+esc(r.normalization_note||r.source_notation||'')+'</p>').join('')+(f.curatedCompletion?'<p>Completed colour assignment: '+esc(f.curatedCompletion.basis)+' <a href="'+esc(f.curatedCompletion.url)+'" target="_blank" rel="noopener noreferrer">'+esc(f.curatedCompletion.paper)+' · '+esc(f.curatedCompletion.locator)+' ↗</a></p>':'')+(f.sourceNote?'<p>'+esc(f.sourceNote)+'</p>':'')+(f.unconverted.length?'<p>Not fully converted: '+f.unconverted.map(esc).join('; ')+'</p>':'')+'<ul>'+f.evidence.map(a=>'<li>'+esc(a.claim)+'<br><span class="muted">'+esc(a.basis)+' · '+esc(a.review)+' · '+esc(a.stance)+' · assertion '+a.assertionId+'</span>'+a.locations.map(l=>'<p><a href="'+esc(pdfURL(l))+'" target="_blank" rel="noopener noreferrer">'+esc(l.paper_version_id)+' · '+esc(l.locator)+(l.pdf_page?' · PDF p. '+l.pdf_page:'')+' ↗</a></p>').join('')+'</li>').join('')+'</ul></details>';
 }
 function templateTable(template){return '<table class="template-table"><thead><tr><th>Multiplet</th><th>Type</th><th>Representation</th><th>Copies</th></tr></thead><tbody>'+template.fields.map(f=>'<tr><td>'+esc(f.label)+'</td><td>'+esc(f.kind)+(f.reality?' ('+esc(f.reality)+')':'')+'</td><td class="math">('+f.representation.slice(0,-1).map(math).join(', ')+'; '+math(f.representation.at(-1))+')</td><td>'+f.copies+'</td></tr>').join('')+'</tbody></table>';}

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
   const state={q:'',algebra:'',paper:'',status:'',open:'',variant:'',regime:'',mode:'dimensions',inherited:false,view:'catalogue',baselineOpen:{},limit:20};
   const paperById=new Map(data.papers.map(p=>[p.id,p]));
   function route(){
     const [raw,query='']=location.hash.slice(1).split('?');
     const p=new URLSearchParams(query);
     state.view=['notation','sources','about'].includes(raw)?raw:'catalogue';
     state.open='';
     if(raw.startsWith('entry/'))state.open=decodeURIComponent(raw.slice(6));
     if(raw.startsWith('model/')){
       const id=decodeURIComponent(raw.split('/')[1]);
       state.open=data.entries.find(e=>e.variants.some(v=>v.id===id))?.id||'';
     }
     for(const key of ['q','algebra','paper','status'])state[key]=p.get(key)||'';
   }
   function url(){
     const p=new URLSearchParams();
     for(const key of ['q','algebra','paper','status'])if(state[key])p.set(key,state[key]);
     history.replaceState(null,'','#'+(state.open?'entry/'+encodeURIComponent(state.open):state.view)+(p.size?'?'+p:''));
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
       (e.status==='partial'?'<p class="coverage-note">Incomplete field content. ? marks unresolved catalogue data.</p>':e.status==='parameterized'?'<p class="coverage-note">Parameterized family, not one fixed spectrum.</p>':'')+
       '<details class="detail-options"'+(state.mode!=='dimensions'||state.variant||state.regime?' open':'')+'><summary>Description & notation</summary><div class="detail-controls">'+
       (e.variants.length>1?'<label>Variant<select id="variant-select">'+e.variants.map(x=>'<option value="'+esc(x.id)+'"'+(x.id===v.id?' selected':'')+'>'+esc(x.name)+'</option>').join('')+'</select></label>':'')+
       (v.regimes.length>1?'<label>Regime<select id="regime-select">'+v.regimes.map(x=>'<option value="'+x.id+'"'+(x.id===r.id?' selected':'')+'>'+esc(x.description)+'</option>').join('')+'</select></label>':'')+
       '<label>Representations<select id="representation-mode"><option value="dimensions"'+(state.mode==='dimensions'?' selected':'')+'>Dimensions & charges</option><option value="dynkin"'+(state.mode==='dynkin'?' selected':'')+'>Dynkin labels</option><option value="young"'+(state.mode==='young'?' selected':'')+'>Young diagrams</option></select></label></div></details>'+
       '<p class="detail-algebra math">'+shorthand(r.algebra)+'<span class="subtle">'+(r.algebra==='g_SM'?'':esc(r.algebraExpanded))+'</span></p>'+
       (r.baseline?'<details class="baseline-expanded"><summary>'+shorthand(r.baseline)+' <span class="subtle">Show fields</span></summary>'+templateTable(data.templates[r.baseline])+'</details>':'')+
       '<details class="provenance"><summary>Provenance</summary><p>'+esc(e.groupingBasis)+'</p><p>'+esc(v.scope||'')+'</p><p>'+esc(v.baselineSource||'No complete baseline recorded.')+'</p>'+
       '<p class="subtle">'+esc(v.id)+' · regime '+r.id+(r.dimension?' · '+esc(r.dimension)+'D':'')+'</p>'+
       (v.baselineParent?'<p>Inherited sector: <a href="#model/'+encodeURIComponent(v.baselineParent)+'">parent record ↗</a>. Not silently copied into this regime.</p>':'')+
       '<p>Spacetime interpretation: '+esc((r.fields.find(f=>f.lorentz?.length)?.lorentz[0].spacetime.note)||'not extracted')+'</p>'+
       '<h3>Charge normalization</h3><ul>'+normalization+'</ul><ul>'+r.notes.map(n=>'<li>'+esc(n)+'</li>').join('')+'</ul>'+
       '<div class="field-sources">'+r.fields.filter(f=>!f.excludedCoordinate).map(f=>'<h3>'+esc(f.label)+'</h3>'+evidence(f)).join('')+'</div><p>Source assertions remain unchecked. A recorded inventory is not a completeness, anomaly or viability certificate.</p></details>'+
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
   function gaugeCell(row,column,regime){
     const cs=column.positions.map(i=>row.components[i]);
     if(state.mode==='dynkin')return cs.map(c=>'<span class="weight-label">'+(c.factor==='u(1)'?'q = '+esc(c.value??'?'):c.dynkin?'['+c.dynkin.join(',')+']':esc(c.value??'?'))+'</span>').join('');
     if(state.mode==='young')return cs.map(c=>c.factor==='u(1)'?'<span class="weight-label">q = '+esc(c.value??'?')+'</span>':young(c)).join('');
     if(column.sm)return '<span class="math">('+cs.slice(0,2).map(c=>math(c.value??'?')).join(', ')+'; '+math(cs[2].value??'?')+')</span>';
     return '<span class="math">'+math(cs[0]?.value??'?')+'</span>';
   }
   function matrix(e,r){
     const columns=root.FieldMatrix.gaugeColumns(r),include=!!state.baselineOpen[e.id];
     const rows=root.FieldMatrix.matrixRows(r,data.templates,include);
     const dimensions=[...new Set(rows.map(x=>x.lorentz.spacetime.dimension))];
     const algebra=dimensions.length===1?(dimensions[0]&&/^\d+$/.test(dimensions[0])?'so(1,'+(Number(dimensions[0])-1)+')':dimensions[0]?'so(1,D−1), D = '+dimensions[0]:'dimension unrecorded'):'mixed dimensions';
     return '<div class="matrix-wrap"><table style="'+(columns.length>2?'min-width:'+((columns.length+2)*105+80)+'px':'')+'" class="representation-matrix" aria-label="Matter content of '+esc(e.name)+'"><thead><tr><th>Spacetime<span class="matrix-algebra">'+esc(algebra)+'</span></th>'+columns.map(c=>'<th>'+gaugeHeading(c)+'</th>').join('')+'<th>Copies</th></tr></thead><tbody>'+
       (r.baseline?'<tr class="baseline-group"><td colspan="'+(columns.length+2)+'"><button class="text-button" data-baseline="'+esc(e.id)+'" aria-expanded="'+include+'">'+shorthand(r.baseline)+'<span> '+(include?'−':'+')+'</span></button></td></tr>':'')+
       rows.map(row=>{
         const l=row.lorentz,real=String(l.reality||'').toLowerCase(),condition=l.component==='S'?(real.startsWith('complex')?'complex':real.startsWith('real')?'real':'reality unresolved'):'';
         return '<tr class="'+(row.template?'template-row':'')+'" title="'+esc(row.labels.join(', '))+'"><td><span class="math">'+esc(l.label).replaceAll('1/2','½')+'</span>'+(dimensions.length>1?'<span class="matrix-note">'+esc(l.spacetime.dimension||'D unknown')+'D</span>':'')+(condition?'<span class="matrix-note">'+esc(condition)+'</span>':'')+(l.status!=='resolved'?'<span class="matrix-note unresolved">'+(l.status==='source_chirality_unresolved'?'source handedness unresolved':'unresolved')+'</span>':'')+'</td>'+columns.map(c=>'<td>'+gaugeCell(row,c,r)+'</td>').join('')+'<td>'+esc(row.copies??'?')+'</td></tr>';
       }).join('')+(!rows.length?'<tr><td colspan="'+(columns.length+2)+'" class="subtle">No independent additional fields extracted for this description.</td></tr>':'')+'</tbody></table></div>';
   }
   function rows(){
     const entries=findEntries(data,state),openIndex=entries.findIndex(e=>e.id===state.open);
     state.limit=Math.max(state.limit,openIndex+1);
     const visible=entries.slice(0,state.limit);
     document.getElementById('result-count').textContent=entries.length+(entries.length===1?' model':' models')+(entries.length!==data.entries.length?' / '+data.entries.length:'');
     document.getElementById('model-entries').innerHTML=visible.map(e=>{
       const r=chosen(e).r;
       return '<article class="model-entry" id="model-'+esc(e.id)+'"><header class="model-heading"><h2>'+esc(e.name)+'</h2><div class="source-buttons">'+e.paperIds.map(id=>'<button class="source-badge" data-paper="'+esc(id)+'" title="'+esc(paperById.get(id).title)+'">'+esc(id)+'</button>').join('')+'</div><button class="text-button" data-open="'+esc(e.id)+'" aria-expanded="'+(state.open===e.id)+'">Details '+(state.open===e.id?'−':'+')+'</button></header>'+(e.status!=='recorded_content'?'<p class="coverage-label">'+esc(statuses[e.status])+'</p>':'')+matrix(e,r)+(state.open===e.id?detail(e):'')+'</article>';
     }).join('')+(entries.length>visible.length?'<button class="load-more" data-more>Show more models ('+(entries.length-visible.length)+' remaining)</button>':'')+(!entries.length?'<p class="empty">No linked models match these filters. <button class="text-button" data-reset>Reset</button></p>':'');
   }
   function notation(){return '<section id="notation"><div class="section-heading"><h2>Notation</h2><span class="eyebrow">Convention '+esc(data.version)+'</span></div><details class="notation-panel" id="notation-guide"><summary>How to read the algebras, representations & baselines</summary><div class="notation-grid"><div><h3>Local algebra, not global group</h3><p><span class="math">𝔤<sub>SM</sub> = su(3) ⊕ su(2) ⊕ u(1)</span>. Internally, simple factors use Cartan type and rank (A₂, A₁), with fixed factor slots. A global quotient is not specified or inferred by this notation.</p><h3>Representations</h3><p><span class="math">(3, 2; 1)</span> means the colour triplet, weak doublet and integer Abelian charge +1. Entries before the semicolon follow the non-Abelian factor order; charges after it follow the Abelian factor order. Factors follow Cartan family and descending rank; identified hypercharge is the first Abelian slot. Repeated factors retain role labels in the expanded inventory.</p><p>Dynkin labels use the ordered A-series chain: the fundamental is [1,0,…,0], its conjugate [0,…,0,1]. Young diagrams are derived displays for A-series factors; a column of N boxes is removed for su(N). Dimensions alone are not unique irrep identifiers: unresolved cases stay marked, with original notation retained.</p><h3>Lorentz representations</h3><p>For 4D field representations of Spin⁺(1,3), use (j<sub>L</sub>,j<sub>R</sub>): scalar (0,0), LH Weyl (½,0), vector (½,½). Scalar reality is a separate condition. Five- and six-dimensional fields use dimension-appropriate B/D Dynkin labels; brane fields are distinguished from bulk fields. Missing source dimensions have an explicit editorial 4D interpretation in the export, not a newly checked source assertion. These are field representations, not on-shell spin/polarization counts.</p><h3>Types and copies</h3><p>F: source fermion (handedness shown when known); Dirac/vector-like fields are expanded into a left-handed pair R ⊕ R̅; S: scalar; Scalar + Weyl fermion: one chiral supermultiplet represented by one complex scalar plus one Weyl fermion in the same gauge representation. V flags an additional vector-matter sector, not an implied gauge connection. Source chirality and scalar reality remain explicit. Every identified 4D Weyl fermion is stored left-handed, in Lorentz representation (½,0). A right-handed field is replaced by its left-handed charge conjugate: every U(1) charge is negated, and every non-Abelian irrep is conjugated. A Dirac field is two independent LH rows in R and conjugate(R), not an extra model entry. When source handedness is missing, R versus conjugate(R) remains unresolved.</p><p>Copies count repeated multiplets, not gauge dimension. For example, three copies of (3,2;1) have gauge dimension 6 each. Composite coordinates and mass eigenstates are retained in the download but not counted as new independent matter.</p><h3>Integer Abelian charges</h3><p>One positive common rescaling per concrete charge assignment makes its charges integral and coprime. A declared SM baseline supplies its reference charge unit. For the ordinary SM this is q = 6Y, with g<sub>q</sub> = g<sub>Y</sub>/6. Scalars and fermions share the same generator normalization. Source orientation is retained; fields are not permuted into the ordering used for unlabeled charge-set classifications.</p><p>Symbolic families, incomplete assignments and kinetic-mixing-dependent charges are not declared primitive. Their source expressions and normalization scope remain visible. Separate U(1) rescalings do not resolve all changes of basis among multiple Abelian factors.</p></div><div><h3>SM shorthand, expanded</h3><p><span class="math">R<sub>SM</sub> = F<sub>SM</sub> ⊕ H<sub>SM</sub></span>. F<sub>SM</sub> contains three generations of left-handed Weyl fermions. H<sub>SM</sub> is one complex scalar doublet. No right-handed neutrino is included. Gauge connections are implied by the algebra and are not additional matter.</p>'+templateTable(data.templates.R_SM)+'<h3>Supersymmetric baseline</h3><p>R<sub>MSSM</sub> contains three families of Q, uᶜ, dᶜ, L, eᶜ chiral multiplets; two Higgs chiral multiplets; and the three gauge-adjoint gaugino multiplets. It replaces, rather than supplements, R<sub>SM</sub>. Inherited templates are presentation definitions, not a claim that every source re-enumerates those fields.</p><details><summary>Expand R<sub>MSSM</sub></summary>'+templateTable(data.templates.R_MSSM)+'</details><h3>What an entry means</h3><p>Source variants are grouped only through the documented field-content decisions. Different interactions or global symmetries can share an entry; they are not declared equivalent physical theories. Separate description regimes are never combined into one spectrum. Partial and parameterized entries are not silently deduplicated or promoted to complete models.</p><p>This release reorganizes the saved, source-scoped extraction of all 50 seed papers. It is not a new independent reading or verification of all full texts. P21, P22 and P26 have partial profiles; every source assertion remains unchecked.</p><p>'+data.references.map(r=>'<a href="'+esc(r.url)+'" target="_blank" rel="noopener noreferrer">'+esc(r.title)+' ↗</a>').join('<br>')+'</p></div></div></details></section>';}

   function sources(){
     return '<section id="sources"><p class="section-note">Papers are independent records. Some have no associated model.</p><div class="source-list">'+data.papers.map(p=>
       '<details class="paper-item" id="source-'+esc(p.id)+'"><summary><span class="source-badge">'+esc(p.id)+'</span><span class="paper-title">'+esc(p.title)+'</span><span class="paper-count">'+p.entryIds.length+'</span></summary><div class="paper-body"><p>'+esc(p.authors)+'</p><a href="'+esc(sourceURL(p))+'" target="_blank" rel="noopener noreferrer">arXiv:'+esc(p.arxiv)+' ↗</a>'+
       (p.entryIds.length?'<p><button class="text-button" data-paper="'+esc(p.id)+'">View '+p.entryIds.length+' linked models →</button></p>':'<p>'+esc(p.noModelReason||p.referenceNotes?.join(' ')||'No linked BSM model.')+'</p>')+
       '<details class="provenance"><summary>Inspection details</summary><p>'+esc(p.kind)+' · '+esc(p.inspectionStatus)+' · '+esc(p.reviewStatus)+'</p><h3>Scope</h3><p>'+esc(p.inspectedScope)+'</p><h3>Limitations</h3><p>'+esc(p.limitations||'No limitation text recorded; completeness not established.')+'</p></details></div></details>').join('')+'</div></section>';
   }
   function about(){
     return '<section class="about-data"><p>A provisional catalogue built from the saved, scoped extraction of 50 seed papers. This is not an independently verified list of complete theories.</p><p>Incomplete and parameterized entries are marked. ? means unresolved in this catalogue, not necessarily unspecified in the paper. Source assertions remain unchecked; paper–model links are provisional.</p><p>Field-content entries may share interactions or global symmetries not displayed here; conversely, identical fields do not imply identical physical theories. Separate description regimes are never combined into one spectrum.</p><p>The original database and all provenance are preserved. No underlying records were deleted to simplify the interface.</p><p>Before adding a model, use the <a href="entry.schema.json">entry schema</a> and the <a href="https://github.com/bastoscostadavi/bsm-atlas/blob/main/atlas/check_entry.py">duplicate checker</a>. An exact field-content match reuses the existing entry; incomplete data require reconciliation.</p><a href="https://github.com/bastoscostadavi/bsm-atlas/tree/main/atlas">Data & methodology ↗</a></section>';
   }
   function catalogue(){
     const algebras=[...new Map(data.entries.map(e=>[e.algebraSignature,e.algebraExpanded])).entries()].sort((a,b)=>a[1].localeCompare(b[1]));
     const active=['algebra','paper','status'].filter(k=>state[k]).length;
     const p=paperById.get(state.paper);
     return '<div class="toolbar" role="search" aria-label="Filter models"><label class="search-label"><span class="sr-only">Search models</span><input type="search" id="entry-search" placeholder="Search models, algebras or papers" value="'+esc(state.q)+'"></label>'+
       '<details class="filter-panel"'+(active?' open':'')+'><summary>Filters'+(active?' · '+active:'')+'</summary><div class="filter-fields"><label>Gauge algebra<select id="algebra-filter"><option value="">All algebras</option>'+algebras.map(([id,label])=>'<option value="'+esc(id)+'"'+(state.algebra===id?' selected':'')+'>'+esc(label)+'</option>').join('')+'</select></label><label>Paper<select id="paper-filter"><option value="">All papers</option>'+data.papers.map(p=>'<option value="'+esc(p.id)+'"'+(state.paper===p.id?' selected':'')+'>'+esc(p.id)+' — '+esc(p.title)+'</option>').join('')+'</select></label><label>Coverage<select id="status-filter"><option value="">Any coverage</option>'+Object.entries(statuses).map(([id,label])=>'<option value="'+id+'"'+(state.status===id?' selected':'')+'>'+label+'</option>').join('')+'</select></label></div></details>'+
       '<details class="download-menu"><summary>Download</summary><div><a href="downloads/field-catalogue.csv" download>CSV</a><a href="field-catalogue.json" download>JSON</a><a href="downloads/field-catalogue.sqlite" download>SQLite</a></div></details></div>'+
       (p?'<div class="selected-paper"><span>'+esc(p.id)+'</span><a href="'+esc(sourceURL(p))+'" target="_blank" rel="noopener noreferrer">'+esc(p.title)+' ↗</a></div>':'')+
       '<div class="results-bar"><span id="result-count"></span><span class="catalogue-disclaimer">Provisional · ? = unresolved</span>'+(['q','algebra','paper','status'].some(k=>state[k])?'<button class="text-button" data-reset>Reset</button>':'')+'</div>'+
       '<div id="model-entries" aria-label="Model matter content"></div>';
   }
   function render(){
     const titles={catalogue:'Gauge algebras & matter.',sources:'Papers.',notation:'Notation.',about:'About the data.'};
     document.getElementById('page-title').textContent=titles[state.view];
     const key=document.getElementById('notation-key');
     if(key)key.hidden=state.view!=='catalogue';
     const content=document.getElementById('view-content');
     content.className=state.view+'-view';
     content.innerHTML=state.view==='sources'?sources():state.view==='notation'?notation():state.view==='about'?about():catalogue();
     if(state.view==='catalogue')rows();
     if(state.view==='notation')document.getElementById('notation-guide').open=true;
     if(document.querySelectorAll)document.querySelectorAll('nav a').forEach(a=>a.setAttribute('aria-current',a.getAttribute('href')==='#'+state.view?'page':'false'));
   }
   function start(){
     route();render();
     const content=document.getElementById('view-content');
     content.addEventListener('input',e=>{if(e.target.id==='entry-search'){state.q=e.target.value;state.open='';url();rows();}});
     content.addEventListener('change',e=>{
       const key={'algebra-filter':'algebra','paper-filter':'paper','status-filter':'status'}[e.target.id];
       if(key){state[key]=e.target.value;state.open='';state.limit=20;url();render();}
       else if(e.target.id==='variant-select'){state.variant=e.target.value;state.regime='';rows();}
       else if(e.target.id==='regime-select'){state.regime=e.target.value;rows();}
       else if(e.target.id==='representation-mode'){state.mode=e.target.value;rows();}
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
       else if(paper){state.view='catalogue';state.paper=paper.dataset.paper;state.open='';url();render();document.getElementById('catalogue').scrollIntoView();}
       else if(e.target.closest('[data-reset]')){Object.assign(state,{q:'',algebra:'',paper:'',status:'',open:''});url();render();}
     });
     window.addEventListener('hashchange',()=>{route();render();});
     let theme='light';try{theme=localStorage.getItem('atlas-theme')||'light';}catch{}
     const button=document.getElementById('theme-toggle');
     const setTheme=t=>{document.documentElement.dataset.theme=t;button.setAttribute('aria-label','Switch to '+(t==='dark'?'light':'dark')+' theme');button.setAttribute('title','Switch to '+(t==='dark'?'light':'dark')+' theme');};
     setTheme(theme==='dark'?'dark':'light');
     button.addEventListener('click',()=>{theme=document.documentElement.dataset.theme==='dark'?'light':'dark';setTheme(theme);try{localStorage.setItem('atlas-theme',theme);}catch{}});
   }
   return {start,state,render,rows};
 }
 root.FieldCatalogue={create,findEntries,esc,young,weight,kindText,compactFields};
 if(root.document&&root.FIELD_CATALOGUE)create(root.FIELD_CATALOGUE,root.document).start();
})(typeof window==='undefined'?globalThis:window);
