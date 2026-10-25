'use strict';
const $ = id => document.getElementById(id);
const names = {ARCHIVE:'기존 연구 보관',CURRENT_LIVE:'이번 LIVE 관측 기록',STORED_OBSERVATION:'이전 관측 저장'};
const number = n => Number.isFinite(n) ? new Intl.NumberFormat('ko-KR',{maximumFractionDigits:8}).format(n) : 'UNKNOWN';
const pct = n => Number.isFinite(n) ? `${n>0?'+':''}${n.toFixed(2)}%` : 'UNKNOWN';
const date = n => Number.isFinite(n) ? new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(n*1000)) : 'UNKNOWN';
const tone = n => !Number.isFinite(n) ? 'muted' : n>0 ? 'positive' : n<0 ? 'negative' : '';
let latest = null, selected = null, busy = false, detailVersion = 0, renderedSignature = null;
try { selected = JSON.parse(sessionStorage.getItem('chio-selected') || 'null'); } catch { selected = null; }
function node(tag,text,cls){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;}
function value(id,text,cls){const e=$(id);e.textContent=text;e.className=cls||'';}
async function get(path){const response=await fetch(path,{cache:'no-store',signal:AbortSignal.timeout(4500)});const data=await response.json();if(!response.ok)throw new Error(data.error||'조회 실패');return data;}
function renderStatus(data){
  const s=data.scanner;
  value('web-state','웹 서버 RUNNING');value('updated',`마지막 갱신 ${date(data.at)} KST`);
  value('scanner-status',s.status||'UNKNOWN',s.live_collecting?'positive':s.status==='BLOCKED'?'warning':'muted');
  value('scanner-phase',s.live_collecting?'OBSERVING · 실제 수집 중':s.status==='RUNNING'?`${s.phase||'PRECHECK'} · 수집 준비 중`:`${s.phase||'UNKNOWN'} · LIVE 수집 중 아님`);
  value('markets',s.markets===null?'UNKNOWN':number(s.markets));
  value('pairs',s.live_collecting?`${number(s.venue_pairs)} 거래소·종목 쌍 · BTC 기준 포함`:'활성 LIVE 없음 · 보관 종목 수와 구분');
  value('today-signals',data.errors.length?'UNKNOWN':number(data.today_live_signals));
  const connections=$('connections');connections.replaceChildren();
  Object.entries(s.connections||{}).forEach(([name,c])=>{const r=node('small');r.append(node('span',name),node('span',c.status,c.status==='CONNECTED'?'positive':c.status==='ERROR'?'warning':'muted'));r.title=`최근 API 응답 ${date(c.at)} KST`;connections.append(r);});
  const clock=s.clock||'UNKNOWN';value('clock-status',clock.startsWith('PASS')?'PASS':clock.startsWith('FAIL')?'FAIL':'UNKNOWN',clock.startsWith('PASS')?'positive':clock.startsWith('FAIL')?'warning':'muted');
  value('clock-detail',clock.startsWith('PASS')?clock.replace('PASS ',''):clock.startsWith('FAIL')?'시계 검증 실패 · LIVE 차단':clock.includes('stale')?'과거 PASS 만료 · 시작 시 재검증':'검증 근거 없음 · 시작 시 전체 검증');
  value('storage',`DB ${s.db_saved||'UNKNOWN'} · ${s.size===null||s.size===undefined?'크기 UNKNOWN':(s.size/1048576).toFixed(2)+' MiB'} · 수집 ${date(s.collected)}`);
  const messages=[...data.errors];if(s.reason)messages.push(`${s.reason} · status_coin_api.bat에서 원인을 확인하세요.`);
  $('api-error').hidden=!messages.length;$('api-error').textContent=messages.join(' / ');
}
function renderRows(){
  if(!latest)return;
  const scope=$('scope').value;
  const signature=JSON.stringify([scope,latest.signals,latest.total,selected?.key]);
  if(signature===renderedSignature)return;
  renderedSignature=signature;
  const rows=latest.signals.filter(r=>scope==='ALL'||r.scope===scope);
  const body=$('signal-rows');body.replaceChildren();
  value('signal-count',`${latest.total}건`);
  $('empty').hidden=rows.length>0;
  value('list-note',`표시 ${rows.length} / 저장 ${latest.total}건 · 최신 ${latest.limit}건 범위 · 점수 미정의는 UNKNOWN`);
  rows.forEach(r=>{
    const tr=node('tr');const key=`${r.dataset}:${r.signal_id}`;
    if(selected?.key===key)tr.className='selected';
    const time=node('td');const button=node('button',date(r.detected_at),'signal-button');button.type='button';button.setAttribute('aria-label',`${r.market} ${date(r.detected_at)} 신호 상세`);button.addEventListener('click',()=>choose(r));time.append(button,node('span',`신호 ${date(r.signal_time).slice(11)}`,'sub'));tr.append(time);
    const market=node('td');market.append(node('div',r.exchange,'exchange'),node('div',r.market,'market'));tr.append(market);
    const pattern=node('td');pattern.append(node('span',names[r.scope]||'UNKNOWN',`tag ${r.scope==='CURRENT_LIVE'?'live':''}`),node('div',r.pattern==='RANGE_30M_GE4_FIRST_CLUSTER'?'30분 변동폭 ≥ 4% · 첫 클러스터':r.pattern,'pattern'),node('span',`원천 구분 ${r.source}`,'sub'));tr.append(pattern);
    tr.append(node('td',number(r.score),'number muted'),node('td',number(r.detection_price),'number'));
    const change=node('td',pct(r.return_pct),`number ${tone(r.return_pct)}`);change.append(node('span',r.return_minutes?`${r.return_minutes}분 후 · 저장 데이터`:'평가 데이터 부족','sub'));tr.append(change);
    const evaluation=node('td',undefined,'eval');r.horizons.forEach((h,i)=>{evaluation.append(node('span',`${h.minutes}m ${h.status}`));if(i===1)evaluation.append(document.createElement('br'));else if(i!==3)evaluation.append(document.createTextNode(' · '));});tr.append(evaluation);
    // The explicit button supports keyboard navigation; the full row is also clickable.
    tr.addEventListener('click',event=>{if(event.target!==button)choose(r);});body.append(tr);
  });
}
async function choose(r){selected={dataset:r.dataset,id:r.signal_id,key:`${r.dataset}:${r.signal_id}`};try{sessionStorage.setItem('chio-selected',JSON.stringify(selected));}catch{}renderRows();await loadDetail();}
async function loadDetail(){
  if(!selected)return;
  const version=++detailVersion;
  try{
    const r=await get(`/api/signal?dataset=${encodeURIComponent(selected.dataset)}&id=${encodeURIComponent(selected.id)}`);
    if(version!==detailVersion)return;
    $('detail-empty').hidden=true;$('detail-content').hidden=false;
    value('detail-market',`${r.exchange} · ${r.market}`);value('detail-scope',names[r.scope]||'UNKNOWN');
    value('detail-subtitle',`신호 ${date(r.signal_time)} KST · 실제 탐지 ${date(r.detected_at)} KST · ${r.source}`);
    value('detail-price',number(r.detection_price));value('detail-score',number(r.score),'muted');
    $('horizons').replaceChildren();r.horizons.forEach(h=>{const card=node('div',undefined,'horizon');card.append(node('small',`${h.minutes}분 후`),node('strong',Number.isFinite(h.return_pct)?pct(h.return_pct):h.status,tone(h.return_pct)),node('span',h.status,'sub'));$('horizons').append(card);});
    const complete=r.horizons.filter(h=>h.status==='COMPLETE');const longest=complete.at(-1);
    value('mfe',pct(longest?.mfe_pct),tone(longest?.mfe_pct));value('mae',pct(longest?.mae_pct),tone(longest?.mae_pct));
    value('mfe-horizon',longest?`(${longest.minutes}분)`:'');value('mae-horizon',longest?`(${longest.minutes}분)`:'');
    value('metric-note',r.horizons.some(h=>h.basis==='STORED_CANDLES_VIEW_ONLY')?'가격 지표는 연속된 저장 원천봉으로 화면에서만 계산합니다. 결측을 채우거나 원래 연구 평가를 변경하지 않습니다.':'DB에 저장된 후속 평가만 표시합니다. 미완성 구간의 수익률은 계산하지 않습니다.');
    value('outcomes',`원래 연구 평가: ${r.outcomes.length?r.outcomes.map(o=>`${o.label} ${o.status} (${o.observed_minutes}/${o.expected_minutes}분)`).join(' · '):'NO_DATA'} · 후속 지표 기준가격 ${number(r.signal_price)} KRW · 탐지 가격 기준: ${r.price_basis}`);
    chart(r);
  }catch(e){if(version===detailVersion){$('detail-content').hidden=true;$('detail-empty').hidden=false;value('detail-empty',e.message);}}
}
function svg(tag,attrs,text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;return e;}
function chart(r){
  const wrap=$('chart');wrap.replaceChildren();
  const bars=r.candles.filter(c=>Number.isFinite(c.close)&&c.close>0);
  if(!bars.length){wrap.append(node('div','NO_DATA · 저장된 원천 가격이 없습니다.','chart-empty'));return;}
  const w=900,h=210,l=70,right=20,top=16,bottom=30;
  const start=r.signal_time-1800,end=r.signal_time+3600;
  let low=Math.min(...bars.map(b=>b.close)),high=Math.max(...bars.map(b=>b.close));
  const pad=Math.max((high-low)*.14,high*.0005);low-=pad;high+=pad;
  const x=t=>l+(t-start)/(end-start)*(w-l-right),y=p=>top+(high-p)/(high-low)*(h-top-bottom);
  const s=svg('svg',{viewBox:`0 0 ${w} ${h}`,role:'img','aria-label':`${r.market} 실제 저장 종가 ${bars.length}개. 빈 구간은 연결하지 않음.`});
  for(let i=0;i<4;i++){const p=low+(high-low)*i/3;const at=y(p);s.append(svg('line',{x1:l,x2:w-right,y1:at,y2:at,stroke:'#2b3b30','stroke-width':.7}),svg('text',{x:l-10,y:at+3,'text-anchor':'end',fill:'#7e9787','font-size':10},number(Number(p.toPrecision(6)))));}
  for(const offset of [-30,0,15,30,60]){const at=x(r.signal_time+offset*60);s.append(svg('text',{x:at,y:h-8,'text-anchor':'middle',fill:offset===0?'#b2cfaa':'#7e9787','font-size':10},offset===0?'신호':`${offset>0?'+':''}${offset}분`));}
  s.append(svg('line',{x1:x(r.signal_time),x2:x(r.signal_time),y1:top,y2:h-bottom,stroke:'#91a785','stroke-dasharray':'4 4'}));
  let path='',prev=null;bars.forEach(b=>{const t=b.ts+60;path+=`${prev!==null&&b.ts-prev===60?'L':'M'}${x(t).toFixed(2)},${y(b.close).toFixed(2)} `;prev=b.ts;});
  s.append(svg('path',{d:path,fill:'none',stroke:'#8bdbac','stroke-width':2,'stroke-linejoin':'round'}));
  bars.forEach(b=>{const c=svg('circle',{cx:x(b.ts+60),cy:y(b.close),r:2,fill:'#8bdbac'});c.append(svg('title',{},`${date(b.ts+60)} KST · ${number(b.close)} KRW`));s.append(c);});
  wrap.append(s);
}
async function refresh(){
  if(busy)return;busy=true;
  try{latest=await get(`/api/snapshot?scope=${encodeURIComponent($('scope').value)}`);renderStatus(latest);renderRows();if(selected)await loadDetail();}
  catch(e){value('web-state','웹 서버 연결 끊김','warning');value('scanner-status','UNKNOWN','muted');value('scanner-phase','서버 응답 없음 · 마지막 표시는 과거 자료입니다.');value('markets','UNKNOWN','muted');value('today-signals','UNKNOWN','muted');value('clock-status','UNKNOWN','muted');$('connections').replaceChildren(node('small','UPBIT / BITHUMB · UNKNOWN'));$('api-error').hidden=false;value('api-error',`${e.message} · 서버 상태를 확인하세요. 아래 신호 목록은 마지막 조회 결과입니다.`);}
  finally{busy=false;}
}
$('scope').addEventListener('change',refresh);$('refresh').addEventListener('click',refresh);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
setInterval(()=>{if(!document.hidden)refresh();},5000);refresh();
