import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
const website=new URL('.',import.meta.url),read=p=>fs.readFileSync(new URL(p,website),'utf8');
const data=JSON.parse(read('field-catalogue.json'));
assert.equal(read('../atlas/FIELD_CONTENT_CATALOGUE.json'),read('field-catalogue.json'));
assert.equal(read('catalogue.json'),read('../atlas/catalogue.json'));
assert.equal(data.schema_version,'bsm-atlas-export-1');
assert.equal(read('entry.schema.json'),read('../atlas/entry.schema.json'));
assert.equal(read('catalogue.schema.json'),read('../atlas/catalogue.schema.json'));
assert.equal(read('field-catalogue-data.js'),'window.FIELD_CATALOGUE = '+read('field-catalogue.json').trimEnd()+';\n');
assert(data.entries.length>=67);
assert.equal(new Set(data.entries.map(e=>e.identity.fingerprint)).size,data.entries.length);
for(const e of data.entries)for(const forbidden of ['variants','reextractions','publicationStatus','groupingBasis','legacyIdentity'])assert(!(forbidden in e));
for(const key of ['sourceDatabaseSha256','reextraction','sourceReview'])assert(!(key in data));
const html=read('index.html');
for(const match of html.matchAll(/(?:src|href)="([^"#]+)"/g)){
 const reference=match[1].split('?')[0];if(/^(https?:|mailto:)/.test(reference))continue;
 assert(fs.existsSync(new URL(reference,website)),reference);
}
assert(html.includes('data-diagram="s-channel"'));
assert.equal((html.match(/data-fermion-arrow=/g)||[]).length,4);
assert(!html.includes('About the data'));
for(const file of ['field-catalogue.sqlite','field-catalogue.csv','nonabelian-cores.csv','semisimple-algebras.csv','full-gauge-algebras.csv'])assert(fs.existsSync(new URL('downloads/'+file,website)));
console.log('Static assets and minimal exports agree.');
