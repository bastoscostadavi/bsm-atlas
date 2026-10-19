(function(root){
 'use strict';
 const ids=['A2','A1','u1'];
 function gaugeColumns(regime){
   const factors=regime.factors,used=new Set(),columns=[];
   if(!factors.length)return [{id:'unresolved',label:'Gauge algebra unresolved',positions:[],sm:false}];
   // Only actual direct factors are bundled. No subgroup branching is inferred.
   for(const suffix of ['', '_A','_B']){
     const matches=ids.map((id,k)=>{
       const roles=[['colour'],['weak_L','left'],['hypercharge']][k].map(r=>r+suffix);
       let candidates=factors.map((f,i)=>({f,i})).filter(x=>x.f.id===id&&roles.includes(x.f.role));
       if(!suffix&&!candidates.length&&id!=='u1'){
         const unique=factors.map((f,i)=>({f,i})).filter(x=>x.f.id===id);
         if(unique.length===1&&unique[0].f.role.startsWith('factor_'))candidates=unique;
       }
       return candidates.length===1?candidates[0].i:null;
     });
     if(matches.every(i=>i!==null)&&matches.every(i=>!used.has(i))){
       columns.push({id:'g_SM'+suffix,label:'g_SM'+suffix,positions:matches,sm:true});
       matches.forEach(i=>used.add(i));
     }
   }
   factors.forEach((f,i)=>{if(!used.has(i))columns.push({id:f.key,label:f.label,role:f.role,positions:[i],sm:false,repeated:factors.filter(a=>a.id===f.id).length>1});});
   return columns;
 }

 function matrixRows(regime,templates,includeBaseline=false){
   return includeBaseline?regime.rows:(regime.additionalRows||regime.rows);
 }
 root.FieldMatrix={gaugeColumns,matrixRows};
})(typeof window==='undefined'?globalThis:window);
