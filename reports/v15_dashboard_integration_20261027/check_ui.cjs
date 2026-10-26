// Real localhost GET responses rendered through the existing app.js in a tiny DOM.
// This is a code/rendering regression check, NOT browser/visual QA. No control POST.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('coin_analysis/dashboard_assets/index.html','utf8');
const script=fs.readFileSync('coin_analysis/dashboard_assets/app.js','utf8');
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.textContent='';this.hidden=false;this.options=[];this.value='';this.attrs={};}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=items;}
 setAttribute(k,v){this.attrs[k]=v;}
 addEventListener(){}
}
async function check(path){
 const elements=Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],new Element('div')]));
 for(const m of html.matchAll(/<select id="([^"]+)">(.*?)<[/]select>/gs)){
  const e=elements[m[1]];e.options=[...m[2].matchAll(/value="([^"]+)"/g)].map(x=>({value:x[1]}));e.value=e.options[0].value;
 }
 const document={getElementById:id=>{assert(elements[id],`missing #${id}`);return elements[id];},
  createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),
  createTextNode:text=>({textContent:text}),addEventListener(){},hidden:false};
 const errors=[];const context=vm.createContext({document,location:{pathname:path},
  sessionStorage:{getItem(){return null;},setItem(){},removeItem(){}},
  fetch:(url,opts)=>fetch('http://127.0.0.1:8765'+url,opts),AbortSignal,Intl,setInterval(){},console});
 vm.runInContext(script,context);
 for(let i=0;i<150&&vm.runInContext('busy',context);i++)await new Promise(r=>setTimeout(r,30));
 assert(!vm.runInContext('busy',context),'refresh timed out');
 assert.equal(elements['web-state'].textContent,'웹 서버 RUNNING');
 if(path==='/analysis'){
  assert.equal(vm.runInContext('analysisReport.group',context),'V15_CURRENT');
  assert.equal(elements['analysis-page'].hidden,false);
  assert.equal(vm.runInContext('analysisReport.analyzer.optimization_called',context),false);
  assert(elements['pattern-rows'].children.length>0);
  await vm.runInContext("choose(analysisReport.signals.find(r=>r.horizons.some(h=>h.status==='COMPLETE'))||analysisReport.signals[0])",context);
  assert.equal(elements['detail-content'].hidden,false);
  assert(elements.chart.children.length>0);
 }else{
  assert.equal(elements['live-page'].hidden,false);
  assert.equal(elements['scanner-status'].textContent,'STOPPED');
  assert.equal(elements['stop-scanner'].disabled,true);
 }
 return {path,rows:elements['signal-rows'].children.length,detailRendered:elements['detail-content'].hidden===false,
         engine:vm.runInContext('latest.engine',context),web:elements['web-state'].textContent};
}
(async()=>{const result={method:'Node VM minimal DOM + actual localhost GET; not a real browser',pages:[await check('/'),await check('/analysis')],result:'PASS'};
 fs.writeFileSync('reports/v15_dashboard_integration_20261027/ui_render.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));})().catch(e=>{console.error(e);process.exitCode=1;});
