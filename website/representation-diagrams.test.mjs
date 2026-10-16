import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import vm from 'node:vm';
const context={};
vm.runInNewContext(fs.readFileSync(new URL('representation-diagrams.js',import.meta.url),'utf8'),context);
const {dynkinLayout,youngCells,render}=context.AtlasDiagrams;
const plain=x=>JSON.parse(JSON.stringify(x));
assert.equal(youngCells([3,1]).length,4);
assert.deepEqual(plain(youngCells([1,1])),[{x:1,y:1},{x:1,y:13}]);
assert.equal(youngCells([1,2]),null);
assert.equal(youngCells([0]),null);
assert.equal(youngCells([25]),null);
assert.equal(youngCells(Array(24).fill(24)),null);
assert.equal(dynkinLayout('U1',1),null);
assert.equal(dynkinLayout('D',3),null);
assert.equal(dynkinLayout('A','N'),null);
assert.deepEqual(plain(dynkinLayout('A',2).edges),[{from:1,to:2,multiplicity:1,short:null}]);
assert.equal(dynkinLayout('A',1).edges.length,0);
for(const [family,rank] of [['B',3],['C',3],['D',5],['E',6],['E',7],['E',8],['F',4],['G',2]]){
  const g=dynkinLayout(family,rank);
  assert.equal(g.nodes.length,rank);
  assert.equal(g.edges.length,rank-1);
  assert.equal(new Set(g.nodes.map(n=>n.id)).size,rank);
}
assert.equal(dynkinLayout('B',3).edges.at(-1).short,3);
assert.equal(dynkinLayout('C',3).edges.at(-1).short,2);
assert.equal(dynkinLayout('F',4).edges[1].short,3);
assert.equal(dynkinLayout('G',2).edges[0].short,1);
assert.equal(dynkinLayout('G',2).edges[0].multiplicity,3);
assert(dynkinLayout('E',6).edges.some(e=>e.from===2&&e.to===4));
assert(dynkinLayout('D',5).edges.some(e=>e.from===3&&e.to===4));
assert(dynkinLayout('D',5).edges.some(e=>e.from===3&&e.to===5));
// Verify the renderer calls the package API, without a browser/DOM dependency in CI.
const counts={rect:0,circle:0,line:0};
context.SVG=()=>{
  const draw={};
  for(const method of ['addTo','size','attr','move','fill','stroke','center','font','plain','polyline'])draw[method]=()=>draw;
  for(const method of ['rect','circle','line'])draw[method]=()=>{counts[method]++;return draw;};
  return draw;
};
const young={dataset:{youngRows:'[2,1]'},textContent:'fallback',replaceChildren(){}},dynkin={dataset:{dynkinFamily:'A',dynkinRank:'2'},textContent:'A2',replaceChildren(){}};
render({querySelectorAll(selector){return selector.startsWith('[data-young')?[young]:[dynkin];}});
assert.deepEqual(counts,{rect:3,circle:2,line:1});
assert.equal(young.dataset.rendered,'true');
assert.equal(dynkin.dataset.rendered,'true');
const vendor=fs.readFileSync(new URL('vendor/svgjs/svg.min.js',import.meta.url));
assert.equal(crypto.createHash('sha256').update(vendor).digest('hex'),'90fc33bcba8181aa5e96e5c975da19f0912d7097a4ec9056ba130fc3ce328ec6');
console.log('Young geometry, Bourbaki Dynkin layouts, SVG.js API and vendored integrity passed.');
