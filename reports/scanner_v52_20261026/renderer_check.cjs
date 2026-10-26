// Actual status fixture through the production renderer; no browser/visual claim.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const dir=__dirname;
const html=fs.readFileSync('coin_analysis/dashboard_assets/index.html','utf8');
const script=fs.readFileSync('coin_analysis/dashboard_assets/app.js','utf8');
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
assert.equal(new Set(ids).size,ids.length);
for(const m of script.matchAll(/(?:\$|value)\('([^']+)'/g))assert(ids.includes(m[1]),`Missing ID ${m[1]}`);
const fixture=JSON.parse(fs.readFileSync(dir+'/renderer_fixture.json','utf8'));
function run(data){
  const elements=new Map();
  const element=()=>({textContent:'',className:'',hidden:false,append(){},replaceChildren(){}});
  const document={getElementById(id){assert(ids.includes(id));if(!elements.has(id))elements.set(id,element());return elements.get(id);},createElement:element};
  const context={document,location:{pathname:'/'},sessionStorage:{getItem(){return null}},fixture:data};
  vm.runInNewContext(script.split('function renderRows(){')[0]+'\nrenderStatus(fixture);',context);
  return Object.fromEntries([...elements].map(([id,e])=>[id,{text:e.textContent,hidden:e.hidden}]));
}
const live=run(fixture);
assert.equal(live.markets.text,'363');
assert.equal(live['ws-subscriptions'].text,'787 / 787 / 773');
assert.equal(live['ws-evaluated'].text,'0 / 0');
assert.equal(live['ws-panel'].hidden,false);
const stopped=JSON.parse(JSON.stringify(fixture));
stopped.scanner.websocket.fresh=false;stopped.scanner.status='STOPPED';stopped.scanner.live_collecting=false;
const terminal=run(stopped);assert.equal(terminal.markets.text,'0');
assert.equal(terminal['ws-subscriptions'].text,'787 / 0 / 0');
const old=JSON.parse(JSON.stringify(stopped));old.scanner.websocket=null;
assert.equal(run(old)['ws-panel'].hidden,true);
const result={status:'PASS',unique_html_ids:ids.length,menus:[...html.matchAll(/href="(\/|\/analysis)"/g)].map(m=>m[1]),
  production_js_rendered:true,live:{active:live.markets.text,registered_requested_confirmed:live['ws-subscriptions'].text,evaluated_complete:live['ws-evaluated'].text},
  stopped:{active:terminal.markets.text,registered_requested_confirmed:terminal['ws-subscriptions'].text},
  fixture_note:'Actual peak snapshot; historical registered/confirmed field semantics normalized to final API schema from per-market evidence',
  browser_visual_qa:false};
assert.deepEqual(result.menus,['/','/analysis']);
fs.writeFileSync(dir+'/renderer_check.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
