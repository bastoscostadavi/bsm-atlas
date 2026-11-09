/* Search computation stays off the rendering thread when Workers are available. */
let engine;
self.onmessage=async event=>{
 const message=event.data;
 if(message.type==='init'){engine=AtlasStore.searchEngine(message.manifest,message.base,message.entries);return;}
 if(message.type!=='search')return;
 try{self.postMessage({id:message.id,rows:await engine.search(message.query,message.kind)});}
 catch(error){self.postMessage({id:message.id,error:{name:error.name,message:error.message}});}
};
