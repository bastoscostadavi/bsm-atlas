(function (root) {
  'use strict';
  const esc = value => String(value ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#039;');
  const value = v => v === null ? 'NULL — not asserted / not supplied' : typeof v === 'object' ? JSON.stringify(v) : String(v ?? 'Not exported');
  const note = text => '<p class="note">'+esc(text)+'</p>';
  const empty = text => '<p class="empty">'+esc(text)+'</p>';
  const modelLink = id => '#model/'+encodeURIComponent(id)+'/evidence';
  const paperLink = id => '#paper/'+encodeURIComponent(id);
  const arxivLink = id => /^([a-z-]+\/\d{7}|\d{4}\.\d{4,5})(v\d+)?$/i.test(id || '') ? '<a href="https://arxiv.org/abs/'+esc(id)+'" target="_blank" rel="noopener noreferrer">arXiv:'+esc(id)+' ↗</a>' : esc(id);
  const facts = row => '<dl class="raw-facts">'+Object.entries(row).map(([key,v])=>'<div><dt>'+esc(key)+'</dt><dd>'+esc(value(v))+'</dd></div>').join('')+'</dl>';
  const table = (headers, rows) => '<div class="table-wrap"><table><thead><tr>'+headers.map(h=>'<th scope="col">'+esc(h)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>'<td>'+c+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';
  function create(data, manifest, search) {
    const models = data.modelData.models;
    const tables = data.relational?.tables || {};
    const rows = name => tables[name]?.rows || [];
    const available = name => Object.hasOwn(tables,name);
    // Logical target vocabulary from atlas/DATA_DICTIONARY.md, not SQL foreign keys.
    const targets = {
      assumption:['theory_assumptions','assumption_id'],regime:['theory_regimes','regime_id'],
      boundary:['theory_boundaries','boundary_id'],regime_relation:['theory_regime_relations','relation_id'],
      gauge_group:['theory_gauge_groups','group_id'],gauge_factor:['theory_gauge_factors','factor_id'],
      field:['theory_fields','field_id'],field_representation:['theory_field_representations','representation_id'],
      field_boundary_condition:['theory_field_boundary_conditions','condition_id'],
      symmetry:['theory_symmetries','symmetry_id'],symmetry_action:['theory_symmetry_actions','action_id'],
      interaction:['theory_interactions','interaction_id'],interaction_participant:['theory_interaction_participants','participant_id'],
      parameter:['theory_parameters','parameter_id'],vacuum:['theory_vacua','vacuum_id'],
      breaking_step:['theory_breaking_steps','step_id'],model_relation:['theory_relations','relation_id']
    };
    const targetIndex=new Map(),supportsByTarget=new Map();
    const targetKey=(kind,id,revision,target)=>JSON.stringify([kind,id,revision,target]);
    for(const [kind,[name,key]] of Object.entries({...targets,specification:['theory_specifications','revision']})) for(const row of rows(name)) targetIndex.set(targetKey(kind,kind==='model_relation'?row.from_model_id:row.model_id,kind==='model_relation'?row.from_revision:row.model_revision ?? row.revision,kind==='specification'?null:row[key]),{name,row});
    for(const link of rows('theory_assertion_links')) {
      const target=targetRow(link);
      if(target) {if(!supportsByTarget.has(target.row)) supportsByTarget.set(target.row,[]);supportsByTarget.get(target.row).push(link);}
    }
    const latest = records => [...records].sort((a,b)=>String(b.updated_at || b.created_at || b.revision || '').localeCompare(String(a.updated_at || a.created_at || a.revision || '')))[0];
    const allMatches = search.findPapers(models);
    const byPaper = new Map(allMatches.map(p=>[p.id,p]));
    const papers = new Map((manifest?.papers || []).map(p=>[p.id,{...p,isSeed:true,metadataSource:'seed manifest'}]));
    for (const p of rows('papers')) papers.set(p.paper_id,{...(papers.get(p.paper_id)||{}),id:p.paper_id,arxiv:p.arxiv_id,kind:p.source_kind || papers.get(p.paper_id)?.kind,database:p});
    for (const p of allMatches) papers.set(p.id,{...(papers.get(p.id)||{}),id:p.id,arxiv:p.arxiv,title:p.title || papers.get(p.id)?.title,metadataSource:p.title?'model-link title; seed authors and pinned version':papers.get(p.id)?.metadataSource});
    for (const p of papers.values()) {
      p.versions = rows('paper_versions').filter(v=>v.paper_id===p.id);
      const ids = new Set(p.versions.map(v=>v.paper_version_id));
      p.profiles = rows('paper_profiles').filter(r=>ids.has(r.paper_version_id));
      p.summaries = rows('paper_summary_revisions').filter(r=>ids.has(r.paper_version_id));
      p.assertions = rows('paper_assertions').filter(r=>ids.has(r.paper_version_id));
      p.links = rows('paper_theory_links').filter(r=>ids.has(r.paper_version_id));
      p.descriptions = rows('paper_model_descriptions').filter(r=>ids.has(r.paper_version_id));
      p.matches = byPaper.get(p.id)?.matches || [];
      const profile = latest(p.profiles);
      p.title = profile?.verified_title || p.title || p.id;
      p.authors = profile?.verified_authors || p.authors || '';
      if (profile) p.metadataSource = 'exported paper profile';
    }
    const corpus = [...papers.values()].sort((a,b)=>a.id.localeCompare(b.id));
    function findPapers(options={}) {
      const linked = new Map(search.findPapers(models,{...options,text:''}).map(p=>[p.id,p.matches]));
      const text = (options.text || '').trim().toLowerCase();
      return corpus.filter(p=>(!text || [p.id,p.title,p.authors,p.arxiv,p.arxivVersion,p.kind].join(' ').toLowerCase().includes(text)) && (!(options.gauge || options.role) || linked.has(p.id)))
        .map(p=>({...p,matches:linked.get(p.id)||[]}));
    }
    function recordLink(name,row) {
      const columns = (tables[name]?.columns || []).filter(c=>c.pk).sort((a,b)=>a.pk-b.pk);
      if (!columns.length) return '#schema/'+encodeURIComponent(name);
      const key = Object.fromEntries(columns.map(c=>[c.name,row[c.name]]));
      return '#schema/'+encodeURIComponent(name)+'?key='+encodeURIComponent(JSON.stringify(key));
    }
    // Follow declared, including composite, foreign keys. Do not guess relations from labels.
    function related(name,row,target) {
      const result = [];
      function walk(from,to,source,reverse) {
        const groups = new Map();
        for (const fk of tables[from]?.foreignKeys || []) if(fk.table===to) {
          if (!groups.has(fk.id)) groups.set(fk.id,[]);
          groups.get(fk.id).push(fk);
        }
        for (const fks of groups.values()) for (const candidate of rows(reverse?from:to)) {
          if (fks.every(fk=>{
            const primary = tables[to]?.columns?.filter(c=>c.pk).sort((a,b)=>a.pk-b.pk);
            const targetColumn = fk.to || primary?.[fk.seq]?.name;
            const a = reverse ? candidate[fk.from] : source[fk.from];
            const b = reverse ? source[targetColumn] : candidate[targetColumn];
            return a!==null && a!==undefined && b!==null && b!==undefined && a===b;
          })) result.push(candidate);
        }
      }
      walk(name,target,row,false); walk(target,name,row,true);
      return [...new Set(result)];
    }
    function evidence(name,row,bridge) {
      const refs = new Set(related(name,row,'evidence_refs'));
      for (const link of related(name,row,bridge)) for (const ref of related(bridge,link,'evidence_refs')) refs.add(ref);
      return [...refs];
    }
    function evidenceHtml(name,row,bridge) {
      const refs = evidence(name,row,bridge);
      return refs.length ? '<details><summary>'+refs.length+' supporting source '+(refs.length===1?'location':'locations')+'</summary>'+refs.map(r=>'<div class="evidence-reference">'+facts(r)+pdfLink(r)+'<a href="'+recordLink('evidence_refs',r)+'">Inspect evidence row</a></div>').join('')+'</details>'
        : empty(available('evidence_refs')?'No evidence reference reachable through declared foreign keys for this row. Inspect its IDs before assuming there is no evidence.':'Passage-level evidence was not retained in this export. A model-wide citation is not evidence for each detailed charge or operator.');
    }
    function pdfLink(r) {
      if(!/^([a-z-]+\/\d{7}|\d{4}\.\d{4,5})v\d+$/i.test(r.paper_version_id || '')) return '';
      return '<p><a href="https://arxiv.org/pdf/'+esc(r.paper_version_id)+(Number.isInteger(r.pdf_page)&&r.pdf_page>0?'#page='+r.pdf_page:'')+'" target="_blank" rel="noopener noreferrer">Open pinned source PDF'+(r.pdf_page?' · page '+esc(r.pdf_page):'')+' ↗</a></p>';
    }
    function targetRow(link) {
      return targetIndex.get(targetKey(link.target_kind,link.model_id,link.model_revision,link.target_id)) || null;
    }
    function supportRows(name,row) {
      return (supportsByTarget.get(row)||[]).filter(link=>targetRow(link)?.name===name);
    }
    function supportHtml(name,row) {
      const links=supportRows(name,row);
      return links.length?'<details class="detail-support"><summary>'+links.length+' source-assertion links for this component</summary>'+note('These are stored logical target links, not declared SQL foreign keys. Support, qualification and dispute are distinct; claims retain their review status.')+links.map(link=>'<div class="support-reference"><p>'+esc([link.support_stance,link.subject_label,link.property_name].filter(Boolean).join(' · '))+'</p>'+(link.decision_note?'<p>'+esc(link.decision_note)+'</p>':'')+'<a href="'+recordLink('theory_assertion_links',link)+'">Inspect support row '+esc(link.support_id)+'</a>'+claimsHtml(related('theory_assertion_links',link,'paper_assertions'))+'</div>').join('')+'</details>':'';
    }
    function claimsHtml(claims) {
      if (!available('paper_assertions')) return empty('Assertions, their value/basis/review status, corrections and rechecks were not included in the old snapshot.');
      if (!claims.length) return empty('No assertion rows selected in the published export.');
      return claims.map(r=>'<details class="claim-card"><summary>'+esc(r.statement || r.assertion_text || r.claim_text || r.assertion_id || 'Stored assertion')+' <small>'+esc([r.basis,r.value_status,r.review_status].filter(Boolean).join(' · '))+'</small></summary>'+facts(r)+evidenceHtml('paper_assertions',r,'paper_assertion_evidence')+'<a href="'+recordLink('paper_assertions',r)+'">Inspect assertion and declared relationships</a></details>').join('');
    }
    function paperCard(p) {
      const groups=[...new Set(p.matches.flatMap(m=>m.groups.map(g=>g.factor?g.factor+' in '+g.label:g.label)))];
      return '<article class="source-card"><div class="eyebrow">'+esc(p.id)+' · '+esc(p.kind || 'Kind not exported')+(p.isSeed?'':' · Auxiliary source, not seed')+'</div><h2><a href="'+paperLink(p.id)+'">'+esc(p.title)+'</a></h2><p>'+esc(p.authors)+'</p><p>'+arxivLink(p.arxivVersion || p.arxiv)+'</p><p class="annotation">Metadata: '+esc(p.metadataSource || 'model-link snapshot')+'. '+(p.profiles.length?'Paper profile exported.':'Paper extraction/review profile not exported.')+'</p>'
        +(groups.length?'<p class="matched-gauge">Recorded groups: '+groups.map(esc).join(' · ')+'</p>':'')
        +(p.matches.length?'<details><summary>'+p.matches.length+' recorded contributions · '+new Set(p.matches.map(m=>m.modelId)).size+' model records</summary>'+p.matches.map(m=>'<div class="matched-contribution"><a href="'+modelLink(m.modelId)+'">'+esc(m.modelName)+'</a><p class="role-label">'+esc(m.role)+' · '+esc(m.reconciliation)+'</p><p>'+esc(m.contribution)+'</p>'+ (m.sourceLocation?'<p class="annotation">Source model label / scope: '+esc(m.sourceLocation)+'</p>':'')+'</div>').join('')+'</details>':note(p.kind==='tool'?'Tool/methods source: a physical-model association is not required. Its extraction status cannot be inferred from missing links.':'No model link retained in this export; this is not a claim of completed extraction.'))+'<p><a href="'+paperLink(p.id)+'">Open paper profile →</a></p></article>';
    }
    function renderPaper(id) {
      const p = papers.get(id);
      if(!p) return empty('Paper ID is not present in the published corpus.');
      const profile = latest(p.profiles);
      const abstracts = [...p.profiles,...p.versions].filter(r=>r.author_abstract);
      const summaries = p.summaries;
      return '<article class="paper-profile"><a href="#papers">← All papers</a><div class="record-heading"><div class="eyebrow">'+esc(p.id)+' · '+esc(p.kind || 'Kind not exported')+'</div><h2>'+esc(p.title)+'</h2><p>'+esc(p.authors)+'</p><p>'+arxivLink(p.arxivVersion || p.arxiv)+'</p></div>'
        +(!profile?note('This is a corpus entry, not a completed paper profile. Planned scope comes from the seed; bibliographic fields identify their origin in the catalogue. This publication has no exported paper profile or review result for this source.'):'')
        +'<section class="section"><h3>Source versions & bibliography</h3><p>Manifest pinned version: '+esc(p.arxivVersion || 'Not in the seed')+'. Atlas model revisions and paper versions are separate identifiers.</p>'+(p.database?facts(p.database):empty('Full database bibliographic row not exported.'))+p.versions.map(r=>'<details><summary>'+esc(r.paper_version_id)+'</summary>'+facts(r)+'</details>').join('')+'</section>'
        +'<section class="section"><h3>Agent-written summary & provenance</h3>'+(summaries.length?summaries.map(r=>'<div class="agent-summary"><p class="eyebrow">Revision '+esc(r.revision ?? r.summary_id)+' · '+esc(r.review_status)+'</p><p class="preserve-lines">'+esc(r.summary_text)+'</p><details><summary>Coverage, generation and review metadata</summary>'+facts(Object.fromEntries(Object.entries(r).filter(([k])=>k!=='summary_text')))+'</details><a href="'+recordLink('paper_summary_revisions',r)+'">Inspect summary assertions and provenance links</a></div>').join(''):empty('No agent-written summary included in this export. Contribution snippets below are not substitutes for a paper summary.'))+'</section>'
        +'<section class="section"><h3>Authors’ abstract — source text</h3>'+(abstracts.length?abstracts.map(r=>'<div class="source-abstract"><p>'+esc(r.author_abstract)+'</p><small>Source version: '+esc(r.paper_version_id)+'</small></div>').join(''):empty('Authors’ abstract not exported.'))+'</section>'
        +'<section class="section"><h3>Actual inspection, limitations & review</h3>'+(p.profiles.length?p.profiles.map(r=>facts(Object.fromEntries(Object.entries(r).filter(([k])=>k!=='author_abstract')))).join(''):empty('Inspection scope, extraction run, completion and review status are unknown in this publication.'))+'</section>'
        +(p.plannedScope?'<section class="section"><h3>Planned first-pass scope — not an extraction result</h3><p class="preserve-lines">'+esc(p.plannedScope)+'</p><p class="annotation">Verbatim scope from BSM_ATLAS_SEED.md. This does not certify that these sections were inspected.</p></section>':'')
        +'<section class="section"><h3>Source-scoped model descriptions</h3>'+note('These describe constructions or examples within this paper. They are not automatically independent canonical models.')+(p.descriptions.length?p.descriptions.map(r=>'<details class="raw-section"><summary>'+esc(r.source_label)+' · '+esc(r.completeness_status)+' · '+esc(r.review_status)+'</summary>'+facts(r)+'<a href="'+recordLink('paper_model_descriptions',r)+'">Inspect description and its assertions</a></details>').join(''):empty('No source-description rows exported for this paper.'))+'</section>'
        +'<section class="section"><h3>Paper–model relationships</h3>'+(p.links.length?p.links.map(r=>'<details open><summary><a href="'+modelLink(r.model_id)+'">'+esc(r.model_id)+' · revision '+esc(r.model_revision)+'</a> — '+esc(r.role)+'</summary>'+facts(r)+evidenceHtml('paper_theory_links',r,'paper_theory_link_evidence')+'</details>').join(''):p.matches.map(m=>'<div class="matched-contribution"><a href="'+modelLink(m.modelId)+'">'+esc(m.modelName)+'</a><p>'+esc(m.role)+' · '+esc(m.reconciliation)+'</p><p>'+esc(m.contribution)+'</p><p>Source model label / scope: '+esc(m.sourceLocation)+'</p></div>').join('') || empty(profile?.no_model_link_reason || 'No model links retained; see source kind and actual extraction status.'))+'</section>'
        +'<section class="section"><h3>Attributed assertions & passage evidence</h3>'+claimsHtml(p.assertions)+'</section></article>';
    }
    function modelRows(name,m) { return rows(name).filter(r=>r.model_id===m.i && (r.model_revision===m.r || r.revision===m.r)); }
    function inRegime(name,r,regimeId) {
      if(regimeId===undefined) return true;
      if(r.regime_id!==undefined && r.regime_id!==null) return String(r.regime_id)===String(regimeId);
      // These rows inherit their regime through an explicitly declared parent.
      const parent=name==='theory_parameters' && r.interaction_id!=null?['theory_interactions','interaction_id',r.interaction_id]
        :name==='theory_breaking_steps'?['theory_vacua','vacuum_id',r.vacuum_id]:null;
      if(parent) return rows(parent[0]).some(p=>p[parent[1]]===parent[2] && p.model_id===r.model_id && p.model_revision===r.model_revision && String(p.regime_id)===String(regimeId));
      return true;
    }
    function modelSupplement(m,section,regimeId) {
      if (!data.relational) return (m.rg.length>1?note('Multiple description regimes are listed. The old export dropped component-to-regime IDs: do not treat all rows as one simultaneous field content or Lagrangian.'):'')+(section==='evidence'?note('Only paper–model contribution snippets are available. Detailed assertion and evidence rows require a fresh database export.'):'');
      const names = section==='structure'?['theory_regimes','theory_gauge_groups','theory_gauge_factors','theory_fields','theory_field_representations','theory_field_boundary_conditions','theory_boundaries']
        :section==='operators'?['theory_interactions','theory_interaction_participants','theory_parameters','theory_assumptions']
        :section==='phases'?['theory_symmetries','theory_symmetry_actions','theory_vacua','theory_breaking_steps']
        :['theory_aliases','theory_families','theory_relations','theory_regime_relations','theory_assertion_links','theory_assertion_rechecks'];
      let html = '<section class="section"><h3>Complete stored rows & description-regime IDs</h3><p class="annotation">The overview above is a compact projection. These rows retain every exported column, including original notation and regime IDs. NULL, value status, source basis and review status remain distinct.</p>';
      for (const name of names) {
        const spec = modelRows('theory_specifications',m)[0];
        const selected = [...new Set([...modelRows(name,m),...(spec?related('theory_specifications',spec,name):[])])].filter(r=>inRegime(name,r,regimeId));
        html += '<details class="raw-section"><summary>'+esc(name)+' · '+selected.length+' selected rows</summary>'+(selected.length?selected.map(r=>'<div class="component-row">'+facts(r)+'<a href="'+recordLink(name,r)+'">Inspect row and declared foreign keys</a>'+supportHtml(name,r)+'</div>').join(''):empty('No rows selected by model ID/revision; other association patterns can be inspected in Database.'))+'</details>';
      }
      if(section==='evidence') {
        const links=modelRows('theory_assertion_links',m);
        const claims=new Set();
        for(const link of links) for(const assertion of related('theory_assertion_links',link,'paper_assertions')) claims.add(assertion);
        html+='<h3>Assertions supporting this model revision</h3>'+claimsHtml([...claims]);
      }
      return html+'</section>';
    }
    function projectRegime(m,regimeId) {
      if(!data.relational) return m;
      const take=name=>modelRows(name,m).filter(r=>inRegime(name,r,regimeId));
      const pack=(rs,cols)=>rs.map(r=>cols.map(c=>r[c] ?? ''));
      const p={...m};
      p.rg=pack(take('theory_regimes'),['description_kind','spacetime_dimension','eft_truncation','validity_assumptions','geometry_boundary_notes']);
      p.g=take('theory_gauge_groups').map(g=>{const fs=take('theory_gauge_factors').filter(f=>f.group_id===g.group_id).sort((a,b)=>a.factor_order-b.factor_order);return [g.group_label,g.global_form_status,g.global_form_expression,g.normalization_note,fs.map(f=>f.factor_label).join(' × '),fs.map(f=>f.factor_label)];});
      p.f=take('theory_fields').flatMap(f=>{const reps=take('theory_field_representations').filter(r=>r.field_id===f.field_id);return (reps.length?reps:[{}]).map(r=>[f.field_label,f.field_kind,f.spin,f.chirality,f.multiplicity,r.representation_label,r.exact_charge,take('theory_gauge_factors').find(g=>g.factor_id===r.factor_id)?.factor_label || take('theory_gauge_groups').find(g=>g.group_id===r.group_id)?.group_label,f.field_reality_condition,f.inherited_baseline_label]);});
      p.x=take('theory_interactions').map(r=>['operator_label','interaction_kind','expression','coefficient_restriction','assumptions','allowed_by_symmetry','included_in_specification','set_to_zero_by_assumption'].map(c=>r[c]));
      for(const [key,name,cols] of [['p','theory_parameters',['symbol','definition','normalization_convention','restriction','value_status']],['a','theory_assumptions',['statement','assumption_kind','status']],['y','theory_symmetries',['symmetry_label','internal_or_spacetime','global_or_gauged','imposed_or_accidental','breaking_status','anomaly_statement']],['v','theory_vacua',['vacuum_label','phase_assumptions','parameter_assumptions','status']],['k','theory_breaking_steps',['step_order','order_parameter','from_symmetry','residual_symmetry','assumed_or_established']]]) p[key]=pack(take(name),cols);
      p.ya=take('theory_symmetry_actions').map(r=>[take('theory_symmetries').find(s=>s.symmetry_id===r.symmetry_id)?.symmetry_label,take('theory_fields').find(f=>f.field_id===r.field_id)?.field_label,r.transformation_rule,r.exact_charge,r.conditions]);
      return p;
    }
    function regimeControls(m,selected) {
      const regimes=modelRows('theory_regimes',m);
      if(!regimes.length) return '';
      return '<div class="regime-controls"><label for="model-regime">Description regime</label><select id="model-regime" aria-label="Description regime">'+regimes.map(r=>'<option value="'+esc(r.regime_id)+'"'+(String(r.regime_id)===String(selected)?' selected':'')+'>Regime '+esc(r.regime_id)+' — '+esc(r.description_kind)+'</option>').join('')+'</select><p class="annotation">Physics tables below show this regime and any shared rows. Model-wide assumptions, sources and cross-regime relations remain available. Different descriptions are not combined into one Lagrangian.</p></div>';
    }
    function tablePanel(name,{q='',page=0,key=''}={}) {
      if(!available(name)) return note(data.relational?'This name is retained in the conceptual dictionary but is not among the exported SQLite tables. It has no row/schema payload in this publication.':'Rows and SQL constraints for this table were not included in the October 7 export. The column list above is schema metadata, not the table’s contents. A fresh export will enable this browser.')+'<button class="quiet-button" data-download-snapshot>Download the available model snapshot (JSON)</button>';
      const definition=tables[name], needle=q.toLowerCase();
      const filtered=rows(name).filter(r=>!needle || Object.values(r).some(v=>value(v).toLowerCase().includes(needle)));
      const pages=Math.max(1,Math.ceil(filtered.length/20)); page=Math.max(0,Math.min(page,pages-1));
      let selected;
      try {const parsed=JSON.parse(key);if(parsed && !Array.isArray(parsed) && typeof parsed==='object' && Object.keys(parsed).length) selected=rows(name).find(r=>Object.entries(parsed).every(([k,v])=>r[k]===v));} catch {}
      const shown=filtered.slice(page*20,page*20+20), cols=definition.columns.slice(0,4).map(c=>c.name);
      const logicalTarget=selected&&name==='theory_assertion_links'?targetRow(selected):null;
      const selectedHtml=selected?'<section class="selected-row"><h3>Selected database row</h3>'+facts(selected)+(name==='evidence_refs'?pdfLink(selected):'')+supportHtml(name,selected)+(logicalTarget?'<p>Stored logical target (not a SQL foreign key): <a href="'+recordLink(logicalTarget.name,logicalTarget.row)+'">'+esc(logicalTarget.name)+' →</a></p>':'')+'<h4>Rows connected by declared foreign keys</h4>'+Object.keys(tables).map(target=>related(name,selected,target).map(r=>'<p><a href="'+recordLink(target,r)+'">'+esc(target)+' · '+esc(JSON.stringify(Object.fromEntries((tables[target].columns||[]).filter(c=>c.pk).map(c=>[c.name,r[c.name]]))))+'</a></p>').join('')).join('')+'</section>':key?empty('The requested primary-key row is not present in this snapshot.'):'';
      return '<h3>Published table contents</h3><p>'+rows(name).length+' stored rows · '+definition.columns.length+' columns. NULL is displayed explicitly.</p>'+selectedHtml+'<label>Search stored rows<input id="table-search" type="search" value="'+esc(q)+'" placeholder="Search any column"></label>'
        +table(['Inspect',...cols],shown.map(r=>['<a href="'+recordLink(name,r)+'">Row →</a>',...cols.map(c=>esc(value(r[c]).slice(0,150)))]))
        +'<div class="data-pagination"><button type="button" class="quiet-button" data-data-page="'+(page-1)+'"'+(page===0?' disabled':'')+'>Previous</button><span>'+filtered.length+' matches · page '+(page+1)+' / '+pages+'</span><button type="button" class="quiet-button" data-data-page="'+(page+1)+'"'+(page===pages-1?' disabled':'')+'>Next</button></div>'
        +'<details><summary>Exact column types, primary keys & foreign keys</summary>'+facts({columns:definition.columns,foreign_keys:definition.foreignKeys})+'</details><details><summary>Original CREATE TABLE definition</summary><pre>'+esc(definition.sql)+'</pre></details>';
    }
    function review() {
      const metric=(name,n,meaning)=>'<article class="coverage-metric"><div class="eyebrow">'+esc(name)+'</div><strong>'+esc(n)+'</strong><p>'+esc(meaning)+'</p></article>';
      const count=name=>available(name)?rows(name).length:'Not exported';
      const statuses = Object.entries(models.reduce((r,m)=>(r[m.s]=(r[m.s]||0)+1,r),{}));
      const downloads=(data.downloads||[]).filter(d=>/^(downloads\/[\w.-]+|atlas-data\.json)$/.test(d.path));
      return '<div class="coverage-grid">'+metric('Seed bibliography',manifest?.papers.length || 'Not supplied','Manifest entries; not extraction completion.')+metric('Database papers',data.paperCount ?? 'Not retained','Registered publication rows, when freshly exported.')+metric('Paper profiles',count('paper_profiles'),'Version-specific inspected scope and review.')+metric('Summary revisions',count('paper_summary_revisions'),'Stored summaries; not independently checked.')+metric('Model records',models.length,'Latest revisions; partial constructions included.')+metric('Paper–model contributions',models.reduce((n,m)=>n+m.z.length,0),'Latest-model links, not unique paper/model pairs.')+'</div>'
        +'<section class="section"><h2>Scientific completeness is not publication completeness</h2>'+table(['Model specification status','Records'],statuses.map(([s,n])=>[esc(s),String(n)]))+'<p>“Defined for stated scope” is not a scientific validation certificate. A partial specification may faithfully reflect a partial source; a framework is not a complete Lagrangian. Missing values never establish absence.</p></section>'
        +'<section class="section"><h2>What this publication preserves</h2>'+table(['Repository requirement','Published coverage'],[
          ['Independent paper catalogue',corpus.length+' entries, including tool/methods sources; metadata origin is labelled'],
          ['Original rows and NULL values',data.relational?Object.keys(tables).length+' complete table exports':'Legacy selected model fields only; full rows unavailable'],
          ['Exact SQL column definitions / relationships',data.relational?'SQLite types, primary keys and declared foreign keys exported':'19 column lists; conceptual connections only'],
          ['Paper profiles / authors’ abstracts / summaries',available('paper_profiles')?'Stored version-specific rows available':'Not retained; not fabricated from contribution snippets'],
          ['Assertions, passage evidence and review checks',available('paper_assertions')?'Stored claims and evidence browser available':'Not retained in legacy snapshot'],
          ['Component-to-regime associations and model history',data.relational?'Original IDs and all stored revisions preserved in Database':'Regime descriptions retained; component regime IDs and history omitted'],
          ['SQLite / SQL / readable reports',downloads.length?downloads.length+' download artifacts':'Requires a new export from DSI']
        ].map(r=>r.map(esc)))+'</section>'
        +'<section class="section"><h2>Validation & reconciliation</h2>'+(data.relational?facts(data.relational.validation):note('No database integrity, foreign-key or reconstruction results were retained in this snapshot. Browser tests validate the website, not the underlying physics.'))+'<p>Value status, source/agent basis, and review status are separate dimensions. Paper–model reconciliation states remain visible in the contributions; a provisional link is not a verified equivalence.</p>'+(available('paper_assertions')?table(['Stored status dimension','Counts'],['paper_profiles','paper_assertions','paper_theory_links'].map(name=>[esc(name),esc(JSON.stringify(rows(name).reduce((counts,r)=>{const status=r.review_status ?? r.reconciliation_status ?? 'not supplied';counts[status]=(counts[status]||0)+1;return counts;},{})))])):'')+(data.sourceSnapshot?'<h3>Snapshot provenance — retrieval, not new extraction</h3>'+facts(data.sourceSnapshot):'')+'</section>'
        +'<section class="section"><h2>Reproducible queries</h2><p><a href="queries.sql" download>Download read-only SQL recipes</a> for papers associated with a gauge-group label, paper inspection/review coverage, and operators distinguishing the left-right and NMSSM variants. These are query definitions, not live DSI results. They require the database snapshot and preserve source versions, model revisions and regime IDs.</p></section>'
        +'<section class="section"><h2>Reusable exports & atlas reports</h2>'+(downloads.length?'<ul>'+downloads.map(d=>'<li><a href="'+esc(d.path)+'" download>'+esc(d.label)+'</a> · '+d.bytes.toLocaleString()+' bytes <details><summary>SHA-256</summary><code>'+esc(d.sha256)+'</code></details></li>').join('')+'</ul>':empty('Full database files and reports are not bundled yet. The current model snapshot can still be downloaded.'))+'<button class="quiet-button" data-download-snapshot>Download currently published snapshot (JSON)</button>'
        +['ATLAS.md','PAPERS.md','SCHEMA.md','REVIEW.md','DATA_DICTIONARY.md','DATABASE_DESIGN.md'].map(name=>'<details class="raw-section"><summary>'+name+' — '+(data.reports?.[name]?'exported':'not exported')+'</summary>'+(data.reports?.[name]?'<pre class="report-text">'+esc(data.reports[name].content)+'</pre>':empty('This report is not in the published snapshot; its conclusions cannot be inferred from row counts.'))+'</details>').join('')+'</section>';
    }
    function comparison(left,right) {
      const a=models.find(m=>m.i===left)||models[0],b=models.find(m=>m.i===right)||models[1];
      const selector=(label,m)=>'<label>'+label+' model<select id="compare-'+label.toLowerCase()+'">'+models.map(x=>'<option value="'+esc(x.i)+'"'+(x.i===m.i?' selected':'')+'>'+esc(x.n)+'</option>').join('')+'</select></label>';
      const lines=items=>'<div class="preserve-lines">'+esc(items.filter(v=>v!==''&&v!==undefined&&v!==null).join('\n') || 'Not recorded in this export')+'</div>';
      const definitions=[['Revision, completeness & scope',m=>[m.i+' · revision '+m.r,m.s,m.c,m.o]],['Baseline & conventions',m=>[m.b,...m.g.map(g=>g[3])]],['Gauge groups',m=>m.g.map(g=>g[0])],['Description regimes',m=>m.rg.map(r=>r.join(' · '))],['Fields & representations',m=>m.f.map(f=>[f[0],f[1],f[3],f[5],f[6]!==''&&f[6]!==null?'charge: '+f[6]:'',f[7]].filter(Boolean).join(' · '))],['Interactions & restrictions',m=>m.x.map(x=>[x[0],x[2],x[3],x[4],'allowed='+value(x[5])+', included='+value(x[6])+', zero='+value(x[7])].filter(Boolean).join(' · '))],['Symmetries & actions',m=>[...m.y,...m.ya].map(r=>r.filter(Boolean).join(' · '))],['Assumptions',m=>m.a.map(r=>r.filter(Boolean).join(' · '))],['Vacuum & breaking',m=>[...m.v,...m.k].map(r=>r.filter(v=>v!==''&&v!==null).join(' · '))]];
      return '<div class="comparison-controls">'+selector('Left',a)+selector('Right',b)+'</div><div class="related comparison-examples"><a href="#compare?left=lr-triplet-parity&right=lr-triplet-charge-conjugation">Parity vs charge conjugation</a><a href="#compare?left=nmssm-general-rpc-cpc&right=nmssm-z3-rpc-cpc">General vs Z3 NMSSM</a></div>'+note('Side-by-side recorded definitions, not an equivalence or viability test. Compare source conventions, scope and description regime before interpreting similarities.')+(!data.relational&&(a.rg.length>1||b.rg.length>1)?note('Component-to-regime IDs were not retained. Rows from multiple descriptions must not be read as a single combined Lagrangian.'):'')+table(['Recorded property',a.n,b.n],definitions.map(([label,fn])=>[esc(label),lines(fn(a)),lines(fn(b))]))+'<div class="related"><a href="'+modelLink(a.i)+'">Left model sources →</a><a href="'+modelLink(b.i)+'">Right model sources →</a></div>';
    }
    return {papers:corpus,findPapers,paperCard,renderPaper,modelSupplement,projectRegime,regimeControls,tablePanel,review,comparison,rows,related,evidence,recordLink,targetRow,supportRows,
      download(){const url=URL.createObjectURL(new Blob([JSON.stringify({...data,corpusManifest:manifest},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='bsm-atlas-'+data.snapshot+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}};
  }
  root.AtlasCatalog={create,esc};
})(typeof window==='undefined'?globalThis:window);
