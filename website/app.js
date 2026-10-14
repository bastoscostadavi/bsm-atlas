(() => {
  'use strict';
  const data = window.ATLAS_DATA;
  if (!data?.modelData?.models?.length) {
    document.getElementById('view-content').textContent = 'The atlas snapshot could not be loaded. Reload this page to try again.';
    return;
  }
  const models = data.modelData.models;
  const schema = data.schema;
  const tableNames = schema.groups.flatMap(group => group[2]);
  const snapshotDate = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(data.snapshot + 'T12:00:00Z'));
  const corpusSize = data.paperCount || 50;
  const snapshotTime = document.querySelector('.snapshot-line time');
  snapshotTime.dateTime = data.snapshot;
  snapshotTime.textContent = snapshotDate;
  document.querySelector('.snapshot-numbers').textContent = models.length + ' theory records · ' + corpusSize + ' source papers · ' + tableNames.length + ' tables';
  const content = document.getElementById('view-content');
  const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
  const human = value => String(value || 'Not recorded').replaceAll('_', ' ');
  const has = value => value !== null && value !== undefined && value !== '';
  const statuses = { defined_for_stated_scope: 'Defined for stated scope', partial_structural_specification: 'Partial specification', framework_or_template: 'Framework / template' };
  const sections = ['structure', 'operators', 'phases', 'evidence'];
  const sectionLabels = ['Gauge & matter', 'Operators & parameters', 'Symmetry & phases', 'Sources'];
  const state = { view: 'models', model: 'u1-smnur-all-sm-yukawas', section: 'structure', search: '', status: '', table: 'theory_specifications', paperSearch: '', paperGauge: '', paperGaugeMode: 'contains', paperRole: '' };
  const searchEngine = window.AtlasSearch;
  const contributionTypes = { review: 'Review / survey', formulation: 'Formulation / construction', analysis: 'Analysis / phenomenology', classification: 'Classification', other: 'Other recorded roles' };
  const recordedRoles = [...new Set(models.flatMap(m => m.z.map(z => z[3])).filter(Boolean))].sort();
  const papers = new Map();
  models.forEach(model => model.z.forEach(source => {
    if (!papers.has(source[0])) papers.set(source[0], { id: source[0], arxiv: source[1], title: source[2], models: [] });
    const paper = papers.get(source[0]);
    if (!paper.models.includes(model.i)) paper.models.push(model.i);
  }));
  const modelLink = (id, section = 'structure') => '#model/' + encodeURIComponent(id) + '/' + section;
  const empty = text => '<p class="empty">' + escape(text) + '</p>';
  const fact = (label, value, fallback = 'Not recorded') => '<div class="fact"><div class="label">' + escape(label) + '</div><div class="value">' + escape(has(value) ? value : fallback) + '</div></div>';
  const table = (headers, rows, fallback) => rows.length ? '<div class="table-wrap"><table><thead><tr>' + headers.map(h => '<th scope="col">' + escape(h) + '</th>').join('') + '</tr></thead><tbody>' + rows.map(row => '<tr>' + row.map(cell => '<td>' + cell + '</td>').join('') + '</tr>').join('') + '</tbody></table></div>' : empty(fallback);
  const textCell = value => escape(has(value) ? value : 'Not recorded');
  const mathCell = value => '<span class="math-text">' + textCell(value) + '</span>';
  const yesNo = value => value === 1 ? 'Yes' : value === 0 ? 'No' : 'Not asserted';
  function parseRoute() {
    let parts;
    const fragment = location.hash.slice(1);
    const queryIndex = fragment.indexOf('?');
    const route = queryIndex < 0 ? fragment : fragment.slice(0,queryIndex);
    const parameters = new URLSearchParams(queryIndex < 0 ? '' : fragment.slice(queryIndex + 1));
    try { parts = route.split('/').map(decodeURIComponent); } catch { parts = []; }
    if (parts[0] === 'model') {
      state.view = 'models';
      if (models.some(m => m.i === parts[1])) state.model = parts[1];
      state.section = sections.includes(parts[2]) ? parts[2] : 'structure';
    } else if (['models', 'schema', 'papers', 'about'].includes(parts[0])) {
      state.view = parts[0];
      if (state.view === 'schema' && tableNames.includes(parts[1])) state.table = parts[1];
      if (state.view === 'papers') {
        state.paperSearch = parameters.get('q') || '';
        state.paperGauge = parameters.get('gauge') || '';
        state.paperGaugeMode = ['contains','exact','factor'].includes(parameters.get('mode')) ? parameters.get('mode') : 'contains';
        const role = parameters.get('role') || '';
        state.paperRole = recordedRoles.includes(role) || Object.keys(contributionTypes).some(type => role === 'category:' + type) ? role : '';
      }
    } else state.view = 'models';
  }
  function renderPage() {
    const copy = {
      models: ['Beyond the Standard Model', 'Explore the structure of a theory.', 'Gauge groups, matter representations, defining constraints, and the papers behind them.'],
      schema: ['Database architecture', 'From source evidence to theory structure.', 'Explore the 34 tables and follow the connections between papers, assertions, model identities, and physics components.'],
      papers: ['Source literature', 'Find the papers behind a gauge group.', 'Search the recorded gauge structure and distinguish reviews, constructions, and analyses through each paper’s contribution roles.'],
      about: ['Scope & conventions', 'An atlas with its assumptions visible.', 'How to read the records, what this snapshot includes, and where its limits are.']
    }[state.view];
    document.getElementById('page-eyebrow').textContent = copy[0];
    document.getElementById('page-title').textContent = copy[1];
    document.getElementById('page-description').textContent = copy[2];
    document.querySelectorAll('[data-view]').forEach(a => { if (a.dataset.view === state.view) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
    if (state.view === 'models') renderCatalog();
    if (state.view === 'schema') renderSchema();
    if (state.view === 'papers') renderPapers();
    if (state.view === 'about') renderAbout();
    document.title = (state.view === 'models' ? (models.find(m => m.i === state.model)?.n || 'Models') : copy[1]) + ' — BSM Atlas';
  }
  function renderCatalog() {
    content.innerHTML = '<div class="catalog-layout"><aside class="catalog" aria-label="Model catalog"><div class="catalog-controls"><label>Find a theory<input id="model-search" type="search" placeholder="Name, gauge group, sector…" value="' + escape(state.search) + '"></label><label>Record scope<select id="model-status"><option value="">All records</option>' + Object.entries(statuses).map(([key,label]) => '<option value="' + key + '"' + (state.status === key ? ' selected' : '') + '>' + label + '</option>').join('') + '</select></label></div><div class="list-meta"><span id="model-match-count"></span><span>125 total</span></div><div class="model-list" id="model-list" role="listbox" aria-label="Theory specifications"></div></aside><article class="record" id="model-record"></article></div>';
    renderModelList(); renderRecord();
    document.getElementById('model-search').addEventListener('input', event => { state.search = event.target.value; renderModelList(); });
    document.getElementById('model-status').addEventListener('change', event => { state.status = event.target.value; renderModelList(); });
  }
  function renderModelList() {
    const query = state.search.trim().toLowerCase();
    const matching = models.filter(m => (!state.status || m.s === state.status) && (!query || [m.i,m.n,m.c,m.b,...m.g.map(g=>g[0])].join(' ').toLowerCase().includes(query)));
    document.getElementById('model-match-count').textContent = matching.length + ' records shown';
    document.getElementById('model-list').innerHTML = matching.length ? matching.map(m => '<button class="model-choice" role="option" aria-selected="' + (state.model === m.i) + '" data-model="' + escape(m.i) + '"><span>' + escape(m.n || m.i) + '</span><small>' + escape(m.i) + '</small></button>').join('') : empty('No records match this search.');
  }
  function renderRecord() {
    const m = models.find(model => model.i === state.model) || models[0];
    const gauge = m.g.map(g=>g[0]).filter(Boolean).join(' · ');
    document.getElementById('model-record').innerHTML = '<div class="record-heading"><div class="record-tools"><span class="badge' + (m.s === 'partial_structural_specification' ? ' provisional' : '') + '">' + escape(statuses[m.s] || human(m.s)) + '</span><button class="quiet-button" id="copy-model-link" type="button">Copy model link</button></div><h2>' + escape(m.n || m.i) + '</h2><div class="record-identifiers"><span class="record-id">' + escape(m.i) + '</span><span>· revision ' + m.r + '</span></div>' + (gauge ? '<div class="gauge-expression">' + escape(gauge) + '</div>' : '') + '<p class="scope">' + escape(m.c || 'Scope not recorded') + '</p></div><div class="tabs" role="tablist" aria-label="Model sections">' + sections.map((key,i)=>'<button class="tab" id="tab-' + key + '" role="tab" aria-selected="' + (state.section === key) + '" aria-controls="record-panel" data-section="' + key + '">' + sectionLabels[i] + '</button>').join('') + '</div><div class="record-body" id="record-panel" role="tabpanel" aria-labelledby="tab-' + state.section + '">' + renderModelSection(m) + '</div>';
  }
  function renderModelSection(m) {
    if (state.section === 'structure') return '<section class="section"><h3>Gauge convention</h3>' + (m.g.length ? m.g.map(g => fact('Group',g[0]) + fact('Global form',g[2] || human(g[1])) + (g[3] ? fact('Normalization',g[3]) : '') + (g[4] ? fact('Separate factors',g[4]) : '')).join('') : empty('No gauge-group record is stored.')) + '</section><section class="section"><h3>Matter representations & charges</h3>' + table(['Field','Kind / chirality','Gauge group or factor','Representation / exact charge'],m.f.map(f=>[mathCell(f[0]),textCell([f[1],f[3],f[2] ? 'spin '+f[2] : ''].filter(Boolean).join(' · ')) + (f[4] ? '<small>Multiplicity: '+escape(f[4])+'</small>' : ''),mathCell(f[7]),mathCell(f[5])+(has(f[6])?'<small>Exact charge: <span class="math-text">'+escape(f[6])+'</span></small>':'')]),'No field records are stored.') + '<p class="annotation">Representations and charges retain the source convention. An empty exact-charge value does not imply zero charge; it may be encoded inside the representation tuple.</p></section><section class="section"><h3>Baseline & description regime</h3>' + fact('Baseline',m.b) + m.rg.map(r=>fact('Description',r[0])+(r[1]?fact('Dimensions',r[1]):'')+(r[2]?fact('EFT / truncation',r[2]):'')+(r[3]?fact('Validity',r[3]):'')+(r[4]?fact('Geometry',r[4]):'')).join('') + '</section>' + scopeNote(m);
    if (state.section === 'operators') return '<section class="section"><h3>Operator expressions & coefficient restrictions</h3>' + table(['Operator / kind','Expression','Restrictions & assumptions','Recorded status'],m.x.map(x=>[textCell(x[0])+'<small>'+escape(human(x[1]))+'</small>',mathCell(x[2]),textCell([x[3],x[4]].filter(Boolean).join(' · ')), '<small>Allowed by symmetry: '+yesNo(x[5])+'<br>Included: '+yesNo(x[6])+'<br>Set to zero: '+yesNo(x[7])+'</small>']),'No interactions are stored for this record.') + '<p class="annotation">An allowed operator, an included operator, and an operator set to zero are recorded separately.</p></section><section class="section"><h3>Parameters & conventions</h3>' + table(['Symbol','Definition','Normalization','Restriction'],m.p.map(p=>[mathCell(p[0]),textCell(p[1]),mathCell(p[2]),textCell(p[3])+(p[4]?'<small>'+escape(human(p[4]))+'</small>':'')]),'No parameter records are stored.') + '</section>' + renderAssumptions(m) + scopeNote(m);
    if (state.section === 'phases') return '<section class="section"><h3>Symmetries</h3>' + table(['Symmetry','Classification','Breaking status','Anomaly statement'],m.y.map(y=>[mathCell(y[0]),textCell([y[1],y[2],y[3]].filter(Boolean).map(human).join(' · ')),textCell(y[4]),textCell(y[5])]),'No separate symmetry rows are stored. Gauge groups may still be recorded in Gauge & matter.') + '</section><section class="section"><h3>Actions on fields</h3>' + table(['Symmetry','Field','Transformation / charge','Conditions'],m.ya.map(a=>[mathCell(a[0]),mathCell(a[1]),mathCell([a[2],a[3]].filter(Boolean).join(' · ')),textCell(a[4])]),'No symmetry-action records are stored.') + '</section>' + renderAssumptions(m) + '<section class="section"><h3>Vacuum realization</h3>' + table(['Vacuum','Phase assumptions','Parameter assumptions','Status'],m.v.map(v=>v.map(textCell)),'No vacuum realization is recorded in this snapshot.') + '</section><section class="section"><h3>Symmetry-breaking chain</h3>' + table(['Step','Order parameter','From','Residual','Status'],m.k.map(k=>k.map(mathCell)),'No breaking steps are stored for this record.') + '</section>' + scopeNote(m);
    return '<section class="section"><h3>Source evidence for this theory identity</h3>' + (m.z.length ? m.z.map(z=>'<div class="paper-link"><div class="paper-tag">'+escape(z[0])+' · <a href="https://arxiv.org/abs/'+encodeURIComponent(z[1])+'" target="_blank" rel="noopener noreferrer">arXiv:'+escape(z[1])+' ↗</a></div><h3>'+escape(z[2]||z[0])+'</h3>'+fact('Source location',z[4])+fact('Role',human(z[3]))+fact('Contribution',z[5])+fact('Reconciliation',human(z[6]))+'</div>').join('') : empty('No paper–theory link is stored.')) + '</section>' + scopeNote(m);
  }
  function scopeNote(m) { return m.o ? '<section class="section"><h3>Scope & unresolved sectors</h3><div class="note">'+escape(m.o)+'</div></section>' : ''; }
  function renderAssumptions(m) { return '<section class="section"><h3>Defining assumptions & constraints</h3>' + (m.a.length ? m.a.map(a=>'<div class="constraint"><small>'+escape(human(a[1]))+' · '+escape(human(a[2]))+'</small><p>'+escape(a[0])+'</p></div>').join('') : empty('No explicit assumption records are stored.')) + '</section>'; }
  function renderSchema() {
    content.innerHTML='<div class="schema-top" aria-label="Core database reading path">'+['papers','paper_assertions','paper_theory_links','theory_specifications','theory_field_representations'].map((name,i)=> (i?'<span aria-hidden="true">→</span>':'')+'<button data-table="'+name+'">'+['Papers','Claims','Paper–theory bridge','Theory identity','Physics'][i]+'</button>').join('')+'</div><div class="schema-layout"><div class="schema-groups">'+schema.groups.map(group=>'<section class="schema-group"><h3>'+escape(group[0])+' <span class="annotation">· '+group[2].length+'</span></h3><p>'+escape(group[1])+'</p>'+group[2].map(name=>'<button class="schema-choice" data-table="'+name+'" aria-pressed="'+(state.table===name)+'">'+name+'</button>').join('')+'</section>').join('')+'</div><section class="schema-details" id="schema-details" aria-live="polite"></section></div>';
    renderSchemaDetails();
  }
  function renderSchemaDetails() {
    const d=schema.info[state.table];
    const connections=new Set(d[3]);
    tableNames.forEach(name=>{if(schema.info[name][3].includes(state.table))connections.add(name);});
    document.getElementById('schema-details').innerHTML='<div class="eyebrow">Selected table</div><h2>'+escape(state.table)+'</h2>'+fact('One row',d[0])+fact('Purpose',d[1])+fact('Example',d[2])+'<h3>Connected concepts</h3><div class="related">'+[...connections].map(name=>'<button class="link-button" data-table="'+name+'">'+name+'</button>').join('')+'</div><h3>Recorded columns</h3>'+(schema.cols[state.table]?'<div class="columns">'+schema.cols[state.table].split(' ').map(c=>'<code>'+c+'</code>').join('')+'</div>':empty('The complete column list was not retained for this table.'))+'<p class="annotation">These connections explain the structure of the data. They are conceptual links, not a verified diagram of SQL foreign-key constraints.</p>';
  }
  function renderPapers() {
    content.innerHTML = `
      <div class="paper-filters">
        <label>Find a source paper<input id="paper-search" aria-label="Find a source paper" type="search" placeholder="Title, paper ID, or arXiv ID" value="${escape(state.paperSearch)}"></label>
        <label>Gauge-group notation<input id="paper-gauge" aria-label="Gauge-group notation" type="search" list="gauge-suggestions" placeholder="e.g. SU(5)" value="${escape(state.paperGauge)}" autocomplete="off"><datalist id="gauge-suggestions"></datalist></label>
        <label>Matching rule<select id="paper-gauge-mode" aria-label="Matching rule">
          <option value="contains" ${state.paperGaugeMode === 'contains' ? 'selected' : ''}>Group label contains text</option>
          <option value="exact" ${state.paperGaugeMode === 'exact' ? 'selected' : ''}>Exact stored group label</option>
          <option value="factor" ${state.paperGaugeMode === 'factor' ? 'selected' : ''}>Exact recorded factor</option>
        </select></label>
        <label>Paper contribution<select id="paper-role" aria-label="Paper contribution"><option value="">Any recorded role</option>
          <optgroup label="Role categories">${Object.entries(contributionTypes).map(([key,label]) => '<option value="category:' + key + '"' + (state.paperRole === 'category:' + key ? ' selected' : '') + '>' + label + '</option>').join('')}</optgroup>
          <optgroup label="Exact recorded roles">${recordedRoles.map(role => '<option value="' + escape(role) + '"' + (state.paperRole === role ? ' selected' : '') + '>' + escape(human(role)) + '</option>').join('')}</optgroup>
        </select></label>
      </div>
      <p id="gauge-search-note" class="annotation paper-filter-note"></p>
      <div class="paper-result-heading"><p id="paper-result-count" role="status" aria-live="polite"></p><div class="related"><button class="quiet-button" id="gauge-example" type="button">Try SU(5)</button><button class="quiet-button" id="reset-paper-search" type="button">Clear filters</button><button class="quiet-button" id="copy-paper-search" type="button">Copy search link</button></div></div>
      <div class="source-grid" id="source-grid" aria-label="Matching source papers"></div>`;
    renderGaugeSuggestions();
    renderPaperCards();
    document.getElementById('paper-search').addEventListener('input',e=>{state.paperSearch=e.target.value;updatePaperSearch();});
    document.getElementById('paper-gauge').addEventListener('input',e=>{state.paperGauge=e.target.value;updatePaperSearch();});
    document.getElementById('paper-gauge-mode').addEventListener('change',e=>{state.paperGaugeMode=e.target.value;renderGaugeSuggestions();updatePaperSearch();});
    document.getElementById('paper-role').addEventListener('change',e=>{state.paperRole=e.target.value;updatePaperSearch();});
    document.getElementById('gauge-example').addEventListener('click',()=>{state.paperSearch='';state.paperGauge='SU(5)';state.paperGaugeMode='contains';state.paperRole='';syncPaperControls();updatePaperSearch();});
    document.getElementById('reset-paper-search').addEventListener('click',()=>{state.paperSearch='';state.paperGauge='';state.paperGaugeMode='contains';state.paperRole='';syncPaperControls();updatePaperSearch();});
    document.getElementById('copy-paper-search').addEventListener('click',async e=>{const url=new URL(location.href);url.hash=paperSearchLink();try{await navigator.clipboard.writeText(url.href);e.target.textContent='Link copied';}catch{e.target.textContent='Link is in address bar';}});
  }
  function syncPaperControls() {
    document.getElementById('paper-search').value=state.paperSearch;
    document.getElementById('paper-gauge').value=state.paperGauge;
    document.getElementById('paper-gauge-mode').value=state.paperGaugeMode;
    document.getElementById('paper-role').value=state.paperRole;
    renderGaugeSuggestions();
  }
  function paperSearchLink() {
    const parameters=new URLSearchParams();
    if(state.paperSearch)parameters.set('q',state.paperSearch);
    if(state.paperGauge)parameters.set('gauge',state.paperGauge);
    if(state.paperGaugeMode!=='contains')parameters.set('mode',state.paperGaugeMode);
    if(state.paperRole)parameters.set('role',state.paperRole);
    return '#papers'+(parameters.size?'?'+parameters.toString():'');
  }
  function updatePaperSearch() {
    history.replaceState(null,'',paperSearchLink());
    document.getElementById('copy-paper-search').textContent='Copy search link';
    renderPaperCards();
  }
  function renderGaugeSuggestions() {
    const labels=[...new Set(models.flatMap(m=>state.paperGaugeMode==='factor'?searchEngine.factorsFor(m):m.g.map(g=>g[0])).filter(Boolean))].sort();
    document.getElementById('gauge-suggestions').innerHTML=labels.map(label=>'<option value="'+escape(label)+'"></option>').join('');
  }
  function renderPaperCards() {
    const shown=searchEngine.findPapers(models,{text:state.paperSearch,gauge:state.paperGauge,mode:state.paperGaugeMode,role:state.paperRole});
    const modelCount=new Set(shown.flatMap(p=>p.matches.map(match=>match.modelId))).size;
    const groupCount=models.filter(m=>m.g.length).length;
    const factorCount=models.filter(m=>searchEngine.factorsFor(m).length).length;
    const filtered=Boolean(state.paperSearch||state.paperGauge||state.paperRole);
    document.getElementById('paper-result-count').textContent=shown.length+' distinct '+(shown.length===1?'paper':'papers')+' · '+modelCount+' linked theory '+(modelCount===1?'record':'records');
    document.getElementById('gauge-search-note').textContent=(state.paperGaugeMode==='factor'
      ? 'Separate factors are recorded for '+factorCount+' of '+models.length+' theories. Missing factor rows can hide otherwise relevant papers. Exact factor matching preserves the stored suffix and case.'
      : 'Gauge groups are recorded for '+groupCount+' of '+models.length+' theories. Searches match stored labels, including inherited or regime-specific groups. Exact label matching is not mathematical group equivalence.')
      +' Role categories group the recorded labels and can overlap; exact roles and source scope are shown with each result.';
    document.getElementById('source-grid').innerHTML=shown.length?shown.map(p=>{
      const theoryCount=new Set(p.matches.map(match=>match.modelId)).size;
      const roles=[...new Set(p.matches.map(match=>human(match.role)))];
      const groups=[...new Set(p.matches.flatMap(match=>match.groups.map(g=>g.factor?g.factor+' in '+g.label:g.label)))];
      return '<article class="source-card"><div class="eyebrow">'+escape(p.id)+'</div><h2>'+escape(p.title||p.id)+'</h2><p><a href="https://arxiv.org/abs/'+encodeURIComponent(p.arxiv)+'" target="_blank" rel="noopener noreferrer">arXiv:'+escape(p.arxiv)+' ↗</a></p>'
        +(state.paperGauge?'<div class="matched-gauge">'+groups.map(escape).join(' · ')+'</div>':'')
        +'<p class="role-label">Recorded roles: '+roles.map(escape).join('; ')+'</p><details'+(filtered?' open':'')+'><summary>'+p.matches.length+' matching '+(p.matches.length===1?'contribution':'contributions')+' · '+theoryCount+' theory '+(theoryCount===1?'record':'records')+'</summary>'
        +p.matches.map(match=>'<div class="matched-contribution"><a href="'+modelLink(match.modelId,'evidence')+'">'+escape(match.modelName||match.modelId)+'</a><div class="role-label">'+escape(human(match.role))+' · '+escape(human(match.reconciliation))+'</div>'+(match.sourceLocation?'<p>Source scope: '+escape(match.sourceLocation)+'</p>':'')+(match.contribution?'<p>'+escape(match.contribution)+'</p>':'')+'</div>').join('')+'</details></article>';
    }).join(''):empty('No recorded matches. This does not establish that no relevant papers exist; label conventions and extraction coverage affect the results.');
  }
  function renderAbout() {
    content.innerHTML='<div class="about"><section><h2>What is a “model” here?</h2><p>A theory record identifies a construction at a stated revision and scope. It may describe a specific theory, a partially specified family, or a framework. The 125 records are therefore not necessarily 125 fully independent, complete Lagrangians.</p><p>The central table, <code>theory_specifications</code>, stores the identity and scope. Related tables store gauge groups, regimes, fields, representations, interactions, parameters, symmetries, vacua, and source support.</p></section><section><h2>Read the scope before drawing conclusions</h2><ul><li><strong>Defined for stated scope:</strong> the recorded construction is defined within its stated sectors and assumptions.</li><li><strong>Partial specification:</strong> some defining structure remains unspecified or deferred.</li><li><strong>Framework / template:</strong> the entry describes a class of constructions rather than one completely fixed theory.</li></ul><p>“Allowed by symmetry” does not mean an interaction was included. A missing charge does not mean the charge is zero. “No stored vacuum” does not establish that a theory has no vacuum.</p></section><section><h2>Notation belongs to the source</h2><p>This explorer displays the stored group labels, representation tuples, charge formulas, and operator expressions. Signs, right-handed versus charge-conjugated fields, Higgs hypercharge conventions, and normalization can differ across sources. Read each model’s convention and scope notes before comparing records.</p><p>Some charges are stored inside a combined representation label instead of the dedicated <code>exact_charge</code> column. Gauge-group factorization is not uniformly populated across the atlas.</p></section><section><h2>Snapshot and provenance</h2><p>This site uses the database material recovered on 7 October 2026: 125 theory records from a 50-paper corpus. Provenance links for 49 papers were retained in the website snapshot. Records and mappings may be provisional and have not all received scientific review.</p><p>The database map includes all 34 table names. Detailed column lists are available for the 19 tables retained in the local schema snapshot. Its displayed connections describe conceptual relationships; they are not verified foreign-key constraints.</p><p>The site is a static research snapshot. Updating the cluster database does not automatically update this publication. The repository includes an exporter to refresh its model dataset from a SQLite database.</p></section><section><h2>Reuse and contribute</h2><p><a href="https://github.com/bastoscostadavi/bsm-atlas">Browse the source repository</a> to inspect the website and data export workflow. Source papers retain their original rights; this site links to them on arXiv.</p></section></div>';
  }
  content.addEventListener('click',async e=>{
    const model=e.target.closest('[data-model]');
    if(model){state.model=model.dataset.model;history.replaceState(null,'',modelLink(state.model,state.section));renderModelList();renderRecord();document.querySelector('[data-model="'+CSS.escape(state.model)+'"]')?.focus({preventScroll:true});document.title=(models.find(m=>m.i===state.model)?.n||state.model)+' — BSM Atlas';return;}
    const section=e.target.closest('[data-section]');
    if(section){state.section=section.dataset.section;history.replaceState(null,'',modelLink(state.model,state.section));renderRecord();document.getElementById('tab-'+state.section).focus();return;}
    const t=e.target.closest('[data-table]');
    if(t){state.table=t.dataset.table;history.replaceState(null,'','#schema/'+state.table);renderSchemaDetails();document.querySelectorAll('.schema-choice').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.table===state.table)));return;}
    const copy=e.target.closest('#copy-model-link');
    if(copy){const url=new URL(location.href);url.hash=modelLink(state.model,state.section);try{await navigator.clipboard.writeText(url.href);copy.textContent='Link copied';}catch{location.hash=modelLink(state.model,state.section);copy.textContent='Link is in address bar';}}
  });
  content.addEventListener('keydown',e=>{
    const option=e.target.closest('.model-choice');
    if(option&&['ArrowDown','ArrowUp','Home','End'].includes(e.key)){const buttons=[...document.querySelectorAll('.model-choice')];let index=buttons.indexOf(option);index=e.key==='Home'?0:e.key==='End'?buttons.length-1:(index+(e.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length;e.preventDefault();buttons[index].focus();buttons[index].click();}
    const tab=e.target.closest('[data-section]');
    if(tab&&['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();const index=(sections.indexOf(state.section)+(e.key==='ArrowRight'?1:-1)+sections.length)%sections.length;document.getElementById('tab-'+sections[index]).click();}
  });
  const themeButton=document.getElementById('theme-toggle');
  let theme;try{theme=localStorage.getItem('atlas-theme');}catch{}
  function setTheme(value){document.documentElement.dataset.theme=value;themeButton.textContent=value==='dark'?'Light theme':'Dark theme';themeButton.setAttribute('aria-label','Switch to '+(value==='dark'?'light':'dark')+' theme');}
  setTheme(theme==='dark'?'dark':'light');
  themeButton.addEventListener('click',()=>{const value=document.documentElement.dataset.theme==='dark'?'light':'dark';setTheme(value);try{localStorage.setItem('atlas-theme',value);}catch{}});
  window.addEventListener('hashchange',()=>{parseRoute();renderPage();});
  parseRoute();renderPage();
})();
