// Execute the real renderer with the real HTTP snapshot and a minimal DOM.
// This verifies displayed values; it is not browser visual QA.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const dir=__dirname;
const snapshot=JSON.parse(fs.readFileSync(dir+'/snapshot.json','utf8'));
const code=fs.readFileSync('coin_analysis/dashboard_assets/app.js','utf8');
const elements=new Map();
function element(){return {textContent:'',className:'',hidden:false,children:[],append(...items){this.children.push(...items)},replaceChildren(...items){this.children=items}}}
const document={getElementById(id){if(!elements.has(id))elements.set(id,element());return elements.get(id)},createElement:element};
const context=vm.createContext({document,location:{pathname:'/'},sessionStorage:{getItem:()=>null},Intl,AbortSignal});
vm.runInContext(code.slice(0,code.indexOf('function renderRows()')),context);
context.snapshot=snapshot;vm.runInContext('renderStatus(snapshot)',context);
assert.equal(elements.get('markets').textContent,'5');
assert.equal(elements.get('total-markets').textContent,'493');
assert.equal(elements.get('focus-markets').textContent,String(snapshot.scanner.market_scope.focus.unique));
assert(elements.get('total-by-exchange').textContent.includes('298'));
assert(elements.get('total-by-exchange').textContent.includes('489'));
assert(elements.get('total-by-exchange').textContent.includes('787'));
context.snapshot=structuredClone(snapshot);context.snapshot.scanner.market_scope=null;
vm.runInContext('renderStatus(snapshot)',context);
assert.equal(elements.get('total-markets').textContent,'UNKNOWN');
assert.equal(elements.get('focus-markets').textContent,'UNKNOWN');
context.snapshot=structuredClone(snapshot);context.snapshot.scanner.market_scope.total.status='STALE';
vm.runInContext('renderStatus(snapshot)',context);
assert(elements.get('total-market-time').textContent.includes('오래된'));
const html=fs.readFileSync('coin_analysis/dashboard_assets/index.html','utf8');
assert.equal((html.match(/<nav[\s\S]*?<\/nav>/)[0].match(/<a /g)||[]).length,2);
const result={real_snapshot_counts:{scan:5,listed_unique:493,upbit:298,bithumb:489,pairs:787,followup:snapshot.scanner.market_scope.focus.unique},missing_counts:'UNKNOWN',stale_receipt_marked:true,menus:2,renderer:'PASS',browser_visual:'NOT_VERIFIED_COMPUTER_USE_URL_CONFIDENCE_BLOCK'};
fs.writeFileSync(dir+'/renderer_check.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
