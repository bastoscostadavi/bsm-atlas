import assert from 'node:assert/strict';
import fs from 'node:fs';
const website=new URL('.',import.meta.url),read=p=>fs.readFileSync(new URL(p,website),'utf8');
const data=JSON.parse(read('field-catalogue.json'));
const source=JSON.parse(read('../atlas/catalogue.json'));
assert.equal(read('../atlas/FIELD_CONTENT_CATALOGUE.json'),read('field-catalogue.json'));
assert.equal(read('catalogue.json'),read('../atlas/catalogue.json'));
assert.equal(data.schema_version,'bsm-atlas-export-1');
assert.equal(read('entry.schema.json'),read('../atlas/entry.schema.json'));
assert.equal(read('catalogue.schema.json'),read('../atlas/catalogue.schema.json'));
assert.equal(read('field-catalogue-data.js'),'window.FIELD_CATALOGUE = '+read('field-catalogue.json').trimEnd()+';\n');
assert.equal(data.entries.length,source.entries.length);
assert.equal(data.papers.length,source.papers.length);
assert.equal(new Set(data.entries.map(e=>e.identity.fingerprint)).size,data.entries.length);
assert.deepEqual(Object.keys(data).sort(),['version','schema_version','representationConvention','entries','papers','templates','cores','semisimpleAlgebras','fullAlgebras','counts'].sort());
const entryKeys=new Set(['id','name','specification','references','aliases','identity','paperIds','regime','algebraExpanded','algebraSignature','coreId','semisimpleId','fullAlgebraId','abelianRank']);
for(const e of data.entries)for(const key of Object.keys(e))assert(entryKeys.has(key),key);
const html=read('index.html');
const repository=new URL('../',website);
for(const file of ['README.md','BSM_ATLAS_AGENT_PROMPT.md','atlas/README.md','atlas/FIELD_CONTENT_CONVENTIONS.md','website/README.md']){
 const document=new URL(file,repository);
 for(const match of fs.readFileSync(document,'utf8').matchAll(/\[[^\]]+\]\(([^)]+)\)/g)){
  const target=match[1].split('#')[0];if(!target||/^(https?:|mailto:)/.test(target))continue;
  assert(fs.existsSync(new URL(target,document)),file+': '+target);
 }
}
for(const match of html.matchAll(/(?:src|href)="([^"#]+)"/g)){
 const reference=match[1].split('?')[0];if(/^(https?:|mailto:)/.test(reference))continue;
 assert(fs.existsSync(new URL(reference,website)),reference);
}
assert(html.includes('data-diagram="s-channel"'));
assert.equal((html.match(/data-fermion-arrow=/g)||[]).length,4);
const lightIcon=read('favicon.svg'),darkIcon=read('favicon-dark.svg');
assert(lightIcon.includes('color="#1d1d1f"'));
assert(lightIcon.includes('fill="#fff"'));
assert(darkIcon.includes('color="#f5f5f7"'));
assert(darkIcon.includes('fill="#161617"'));
assert.equal(darkIcon.replace('color="#f5f5f7"','color="#1d1d1f"').replace('fill="#161617"','fill="#fff"'),lightIcon);
for(const file of ['field-catalogue.sqlite','field-catalogue.csv','nonabelian-cores.csv','semisimple-algebras.csv','full-gauge-algebras.csv'])assert(fs.existsSync(new URL('downloads/'+file,website)));
console.log('Static assets and catalogue exports agree.');
