(function(root){
 'use strict';
 const ids=['A2','A1','u1'];
 function conjugateComponents(components,factors){
   return components.map((c,i)=>{
     const a=factors[i],copy={...c},v=c.value;
     if(v===null)return copy;
     if(a.type==='U1'){
       if(/^[+-]?\d+$/.test(v))copy.value=String(-BigInt(v));
       else copy.value='−('+v+')';
     }else if(a.type==='A'&&a.rank>1){
       copy.dynkin=c.dynkin?[...c.dynkin].reverse():null;
       const self=c.dynkin&&JSON.stringify(c.dynkin)===JSON.stringify(copy.dynkin);
       if(!self&&v!=='1'&&v!=='Adj')copy.value=v.startsWith('bar(')?v.slice(4,-1):'bar('+v+')';
       copy.youngRows=copy.dynkin?copy.dynkin.map((_,j)=>copy.dynkin.slice(j).reduce((a,b)=>a+b,0)).filter(Boolean):null;
     }else if(a.type==='D'&&a.rank%2){
       if(c.dynkin){copy.dynkin=[...c.dynkin];[copy.dynkin[a.rank-2],copy.dynkin[a.rank-1]]=[copy.dynkin[a.rank-1],copy.dynkin[a.rank-2]];}
       if(v!=='1'&&v!=='Adj')copy.value='conj('+v+')';
     }
     return copy;
   });
 }
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
   const result=[];
   function add(field,lorentz,components,template=false){
     result.push({labels:[field.label+(lorentz.conjugateGauge?'ᶜ':'')],sourceFieldIds:field.sourceFieldId?[field.sourceFieldId]:[],lorentz,components:lorentz.gaugeComponents||(lorentz.conjugateGauge?conjugateComponents(components,regime.factors):components),copies:field.copies,template,field});
   }
   if(includeBaseline&&regime.baseline){
     for(const f of templates[regime.baseline].fields){
       const components=regime.factors.map(a=>{
         const roles=['colour','weak_L','hypercharge'];
         const i=roles.findIndex((r,j)=>a.role===r&&a.id===ids[j]);
         const weak=i<0&&a.role==='left'&&a.id==='A1'?1:i;
         return {factor:a.label,role:a.role,value:weak<0?null:f.representation[weak],dynkin:weak<0?null:f.components[weak].dynkin,youngRows:weak<0?null:f.components[weak].youngRows};
       });
       // Reference templates do not assign unspecified charges under new factors.
       for(const l of f.lorentz)add(f,l,components,true);
     }
   }
   for(const f of regime.fields){
     if(f.excludedCoordinate||(regime.baseline&&f.inherited))continue;
     for(const l of f.lorentz||[])add(f,l,f.components);
   }
   const merged=[];
   for(const row of result){
     const safe=row.copies!==null&&row.lorentz.status==='resolved'&&row.components.length&&row.components.every(c=>c.value!==null&&!String(c.value).includes('?'));
     const key=safe?JSON.stringify([row.lorentz.spacetime.dimension,row.lorentz.scheme,row.lorentz.irreps,row.lorentz.reality,row.components.map(c=>[c.factor,c.role,c.value])]):null;
     const same=key&&merged.find(r=>r.key===key);
     if(same){same.copies+=row.copies;same.template=same.template&&row.template;same.labels.push(...row.labels);same.sourceFieldIds.push(...row.sourceFieldIds);}
     else merged.push({...row,key});
   }
   return merged;
 }
 root.FieldMatrix={gaugeColumns,matrixRows,conjugateComponents};
})(typeof window==='undefined'?globalThis:window);
