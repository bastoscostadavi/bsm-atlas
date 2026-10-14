(function(root) {
  'use strict';
  // Text matching preserves case-sensitive charge and factor suffixes.
  // Whitespace normalization is not mathematical group equivalence.
  const normalized = value => String(value || '').trim().replace(/\s+/g, ' ');
  const factorsFor = model => model.g.flatMap(group => group[4] ? group[4].split(' × ').map(normalized) : []);
  function matchedGroups(model, query, mode = 'contains') {
    const wanted = normalized(query);
    if (!wanted) return model.g.map(group => ({ label: group[0], factor: '' }));
    return model.g.flatMap(group => {
      if (mode === 'factor') {
        return (group[4] ? group[4].split(' × ') : []).filter(factor => normalized(factor) === wanted)
          .map(factor => ({ label: group[0], factor }));
      }
      const label = normalized(group[0]);
      const match = mode === 'exact' ? label === wanted : label.toLowerCase().includes(wanted.toLowerCase());
      return match ? [{ label: group[0], factor: '' }] : [];
    });
  }
  function categoriesFor(role) {
    const label = String(role || '').toLowerCase();
    if (/review|survey/.test(label)) return ['review'];
    const categories = [];
    if (/formulation|construction|definition|realization|completion|extension|alternative/.test(label)) categories.push('formulation');
    if (/analysis|constraints|calculation|matching|phenomenolog|application|validation/.test(label)) categories.push('analysis');
    if (/classification/.test(label)) categories.push('classification');
    return categories.length ? categories : ['other'];
  }
  const roleMatches = (role, filter) => !filter || (filter.startsWith('category:')
    ? categoriesFor(role).includes(filter.slice(9)) : role === filter);
  function findPapers(models, { text = '', gauge = '', mode = 'contains', role = '' } = {}) {
    const results = new Map();
    const query = text.trim().toLowerCase();
    const gaugeActive = Boolean(normalized(gauge));
    for (const model of models) {
      const groups = matchedGroups(model, gauge, mode);
      if (gaugeActive && !groups.length) continue;
      for (const source of model.z) {
        if (!roleMatches(source[3], role)) continue;
        if (query && ![source[0],source[1],source[2]].join(' ').toLowerCase().includes(query)) continue;
        if (!results.has(source[0])) results.set(source[0], { id: source[0], arxiv: source[1], title: source[2], matches: [] });
        const paper = results.get(source[0]);
        paper.matches.push({ modelId: model.i, modelName: model.n, groups,
          role: source[3], sourceLocation: source[4], contribution: source[5], reconciliation: source[6] });
      }
    }
    return [...results.values()].sort((a,b) => a.id.localeCompare(b.id));
  }
  root.AtlasSearch = { normalized, factorsFor, matchedGroups, categoriesFor, roleMatches, findPapers };
})(typeof window === 'undefined' ? globalThis : window);
