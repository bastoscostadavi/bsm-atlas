import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const directory = path.dirname(fileURLToPath(import.meta.url));
const context = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(directory, 'data.js'), 'utf8'), context);
vm.runInNewContext(fs.readFileSync(path.join(directory, 'manifest.js'), 'utf8'), context);
const manifest=context.window.ATLAS_MANIFEST;
if (manifest.papers.length!==50 || new Set(manifest.papers.map(p=>p.id)).size!==50) throw new Error('Expected independent inventory of all 50 seed papers');
if(manifest.papers.some(p=>!p.arxivVersion || !p.plannedScope || !p.kind)) throw new Error('Incomplete manifest metadata');
const data = context.window.ATLAS_DATA;
for(const [name,table] of Object.entries(data.relational?.tables || {})) {
  if(!Array.isArray(table.rows) || !Array.isArray(table.columns) || !Array.isArray(table.foreignKeys)) throw new Error('Incomplete relational export: '+name);
  for(const row of table.rows) for(const column of table.columns) if(!Object.hasOwn(row,column.name)) throw new Error('Column omitted from row: '+name+'.'+column.name);
}
const models = data.modelData.models;
const ids = new Set();
for (const model of models) {
  if (!model.i || !model.n || ids.has(model.i)) throw new Error('Missing or duplicate model identity: ' + model.i);
  ids.add(model.i);
  for (const key of ['g','f','x','p','y','ya','a','v','k','z','rg']) if (!Array.isArray(model[key])) throw new Error('Missing model section: ' + model.i + '/' + key);
  for (const source of model.z) if (!source[0] || !source[1]) throw new Error('Missing source identity for ' + model.i);
}
const names = data.schema.groups.flatMap(group => group[2]);
if (new Set(names).size !== names.length) throw new Error('Duplicate schema table');
for (const name of names) {
  if (!data.schema.info[name]) throw new Error('Missing table description: ' + name);
  for (const related of data.schema.info[name][3]) if (!names.includes(related)) throw new Error('Unknown related table: ' + related);
}
const html = fs.readFileSync(path.join(directory, 'index.html'), 'utf8');
const favicon = fs.readFileSync(path.join(directory, 'favicon.svg'), 'utf8');
const photonPath = source => source.match(/data-propagator="photon" d="([^"]+)"/)?.[1];
for (const [name, source] of [['header', html], ['favicon', favicon]]) {
  if (!source.includes('data-diagram="s-channel"') || !photonPath(source)) throw new Error(`Missing photon-exchange logo in ${name}`);
  if ([...source.matchAll(/data-fermion-arrow=/g)].length !== 4) throw new Error(`Expected four fermion-flow arrows in ${name}`);
}
if (photonPath(html) !== photonPath(favicon)) throw new Error('Header and favicon photon paths differ');
for (const match of html.matchAll(/(?:src|href)="([^"#]+)"/g)) {
  if (!/^(https?:|mailto:)/.test(match[1]) && !fs.existsSync(path.join(directory, match[1]))) throw new Error('Missing asset: ' + match[1]);
}
console.log(`Snapshot validated: ${models.length} model records, ${names.length} tables, local assets present.`);
