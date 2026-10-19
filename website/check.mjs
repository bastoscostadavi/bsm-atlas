import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.dirname(directory);
const data = JSON.parse(fs.readFileSync(path.join(directory, 'field-catalogue.json'), 'utf8'));
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(directory, 'field-catalogue-data.js'), 'utf8'), context);
assert.equal(JSON.stringify(context.window.FIELD_CATALOGUE), JSON.stringify(data), 'Browser payload differs from downloadable JSON');
assert.equal(fs.readFileSync(path.join(root, 'atlas/FIELD_CONTENT_CATALOGUE.json'), 'utf8'),
  fs.readFileSync(path.join(directory, 'field-catalogue.json'), 'utf8'));
assert.equal(fs.readFileSync(path.join(root, 'atlas/entry.schema.json'), 'utf8'),
  fs.readFileSync(path.join(directory, 'entry.schema.json'), 'utf8'));

const seed = fs.readFileSync(path.join(root, 'BSM_ATLAS_SEED.md'), 'utf8');
const versions = [...seed.matchAll(/^\| (P\d{2}) \| \[([^\]]+)\]/gm)];
assert.equal(versions.length, 50);
assert.equal(new Set(versions.map(m => m[1])).size, 50);
for (const [, id, version] of versions) {
  assert.equal(data.papers.find(p => p.id === id)?.arxiv, version, 'Missing or changed seed version: ' + id);
}
assert.equal(new Set(data.entries.map(e => e.id)).size, data.entries.length);
assert.equal(new Set(data.papers.map(p => p.id)).size, data.papers.length);
const paperIds = new Set(data.papers.map(p => p.id));
for (const entry of data.entries) {
  for (const id of entry.paperIds) assert(paperIds.has(id), 'Unknown source paper: ' + id);
}
for (const name of ['field-catalogue.csv', 'field-catalogue.sqlite', 'nonabelian-cores.csv', 'semisimple-algebras.csv', 'full-gauge-algebras.csv']) {
  assert(fs.statSync(path.join(directory, 'downloads', name)).size > 0, 'Missing download: ' + name);
}

const html = fs.readFileSync(path.join(directory, 'index.html'), 'utf8');
const catalogueMenu = html.match(/<details id="catalogue-menu"[\s\S]*?<\/details>/)?.[0];
assert(catalogueMenu?.includes('<summary>Catalogue'), 'Missing native Catalogue disclosure');
assert.equal((catalogueMenu.match(/<a /g)||[]).length,4, 'Only the four catalogue choices should be links');
assert.equal((catalogueMenu.match(/class="catalogue-group-label"/g)||[]).length,2);
for(const target of ['catalogue','full-algebras','cores','entries'])assert(catalogueMenu.includes('href="#'+target+'"'));
const favicon = fs.readFileSync(path.join(directory, 'favicon.svg'), 'utf8');
const photonPath = source => source.match(/data-propagator="photon" d="([^"]+)"/)?.[1];
for (const [name, source] of [['header', html], ['favicon', favicon]]) {
  assert(source.includes('data-diagram="s-channel"') && photonPath(source), 'Missing photon-exchange logo in ' + name);
  assert.equal([...source.matchAll(/data-fermion-arrow=/g)].length, 4, 'Expected four fermion-flow arrows in ' + name);
}
assert.equal(photonPath(html), photonPath(favicon));
for (const match of html.matchAll(/(?:src|href)="([^"#]+)"/g)) {
  if (!/^(https?:|mailto:)/.test(match[1])) {
    assert(fs.existsSync(path.join(directory, match[1].split(/[?#]/)[0])), 'Missing asset: ' + match[1]);
  }
}
for (const name of ['README.md', 'BSM_ATLAS_AGENT_PROMPT.md', 'atlas/README.md', 'atlas/FIELD_CONTENT_CONVENTIONS.md', 'website/README.md']) {
  const filename = path.join(root, name);
  const markdown = fs.readFileSync(filename, 'utf8');
  for (const [, target] of markdown.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
    if (/^(https?:|#)/.test(target)) continue;
    assert(fs.existsSync(path.resolve(path.dirname(filename), target.split('#')[0])), 'Broken documentation link in ' + name + ': ' + target);
  }
}
console.log('Active catalogue assets, downloads, documentation links, source versions and photon-exchange logo validated.');
