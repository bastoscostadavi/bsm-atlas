(function(root){
 'use strict';
 // Mathematics is supplied by the canonical labels. SVG.js only draws geometry.
 function youngCells(rows){
   if(!Array.isArray(rows)||rows.length>24||rows.some((n,i)=>!Number.isInteger(n)||n<1||n>24||(i&&n>rows[i-1]))||rows.reduce((a,b)=>a+b,0)>256)return null;
   return rows.flatMap((n,y)=>Array.from({length:n},(_,x)=>({x:x*12+1,y:y*12+1})));
 }
 function dynkinLayout(family,rank){
   if(!Number.isInteger(rank)||rank<1||rank>24)return null;
   if(!({A:rank>=1,B:rank>=2,C:rank>=2,D:rank>=4,E:[6,7,8].includes(rank),F:rank===4,G:rank===2})[family])return null;
   const nodes=[],edges=[];
   const node=(id,x,y=18)=>nodes.push({id,x:x*22+10,y});
   const edge=(from,to,multiplicity=1,short=null)=>edges.push({from,to,multiplicity,short});
   const chain=ids=>{ids.forEach((id,i)=>node(id,i));ids.slice(1).forEach((id,i)=>edge(ids[i],id));};
   if(family==='D'){
     chain(Array.from({length:rank-2},(_,i)=>i+1));
     node(rank-1,rank-2,32);node(rank,rank-2,4);
     edge(rank-2,rank-1);edge(rank-2,rank);
   }else if(family==='E'){
     chain([1,...Array.from({length:rank-2},(_,i)=>i+3)]);
     nodes.forEach(n=>n.y=26);node(2,2,4);edge(2,4);
   }else{
     chain(Array.from({length:rank},(_,i)=>i+1));
     const last=edges.at(-1);
     if(family==='B'){last.multiplicity=2;last.short=rank;}
     if(family==='C'){last.multiplicity=2;last.short=rank-1;}
     if(family==='F'){edges[1].multiplicity=2;edges[1].short=3;}
     if(family==='G'){last.multiplicity=3;last.short=1;}
   }
   return {nodes,edges,width:Math.max(...nodes.map(n=>n.x))+10,height:Math.max(...nodes.map(n=>n.y))+17};
 }
 function render(document){
   if(typeof root.SVG!=='function'||!document.querySelectorAll)return;
   const ink={color:'currentColor',width:1};
   for(const holder of document.querySelectorAll('[data-young-rows]:not([data-rendered])')){
     const rows=JSON.parse(holder.dataset.youngRows),cells=youngCells(rows);
     if(!cells||!cells.length)continue;
     const fallback=holder.textContent;
     try{
       holder.replaceChildren();
       const draw=root.SVG().addTo(holder).size(rows[0]*12+2,rows.length*12+2).attr({role:'img','aria-label':'Young diagram with row lengths '+rows.join(', ')});
       for(const c of cells)draw.rect(12,12).move(c.x,c.y).fill('none').stroke(ink);
       holder.dataset.rendered='true';
     }catch{holder.textContent=fallback;}
   }
   for(const holder of document.querySelectorAll('[data-dynkin-family]:not([data-rendered])')){
     const family=holder.dataset.dynkinFamily,rank=Number(holder.dataset.dynkinRank),g=dynkinLayout(family,rank);
     if(!g)continue;
     const fallback=holder.textContent;
     try{
       holder.replaceChildren();
       const draw=root.SVG().addTo(holder).size(g.width,g.height).attr({role:'img','aria-label':family+rank+' Dynkin diagram, Bourbaki node numbering'});
       for(const e of g.edges){
         const a=g.nodes.find(n=>n.id===e.from),b=g.nodes.find(n=>n.id===e.to),distance=Math.hypot(b.x-a.x,b.y-a.y);
         const ux=(b.x-a.x)/distance,uy=(b.y-a.y)/distance,nx=-uy,ny=ux;
         for(let j=0;j<e.multiplicity;j++){
           const offset=(j-(e.multiplicity-1)/2)*3;
           draw.line(a.x+ux*4+nx*offset,a.y+uy*4+ny*offset,b.x-ux*4+nx*offset,b.y-uy*4+ny*offset).stroke(ink);
         }
         if(e.short){
           const direction=e.short===e.to?1:-1,mx=(a.x+b.x)/2,my=(a.y+b.y)/2;
           const tip=[mx+ux*3*direction,my+uy*3*direction],base=[mx-ux*2*direction,my-uy*2*direction];
           draw.polyline([[base[0]+nx*3,base[1]+ny*3],tip,[base[0]-nx*3,base[1]-ny*3]]).fill('none').stroke(ink);
         }
       }
       for(const n of g.nodes){
         draw.circle(6).center(n.x,n.y).fill('var(--bg)').stroke(ink);
         draw.plain(String(n.id)).font({size:8,family:'sans-serif'}).fill('currentColor').center(n.x,n.y+10);
       }
       holder.dataset.rendered='true';
     }catch{holder.textContent=fallback;}
   }
 }
 root.AtlasDiagrams={youngCells,dynkinLayout,render};
})(typeof window==='undefined'?globalThis:window);
