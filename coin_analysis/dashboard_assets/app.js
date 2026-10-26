'use strict';
const $ = id => document.getElementById(id);
const names = {ARCHIVE:'과거 DB · 버전 출처 미확정',CURRENT_LIVE:'현재 V15 DB',STORED_OBSERVATION:'이전 관측 저장'};
const groups={ARCHIVE_LIVE:'연구 보관 · LIVE',ARCHIVE_CATCHUP:'연구 보관 · 지연 수집',OBSERVATION_LIVE:'신규 관측 · LIVE',OBSERVATION_CATCHUP:'신규 관측 · 지연 수집'};
Object.assign(groups,{V15_CURRENT:'현재 V15 DB',V15_LEGACY:'과거 V15 계열 DB',SCORE:'저장 SURGE 점수'});
const quality={MISSING_SAMPLES:'중간 가격 누락',DELAYED_OR_INVALID_SAMPLE_TIMES:'추적 지연·시각 이상',UNVERIFIED_CHECKPOINT_TIME:'시점 검증 불가',SAVED_ENDPOINT_MISMATCH:'저장 값 불일치'};
const states={COMPLETE:'평가 완료',PENDING:'평가 대기',NO_DATA:'데이터 부족',INSUFFICIENT_DATA:'데이터 부족',UNKNOWN:'확인 불가'};
const patternName=p=>p==='RANGE_30M_GE4_FIRST_CLUSTER'?'30분 변동폭 ≥ 4% · 첫 클러스터':p==='UNKNOWN'?'패턴 미정의':p;
const number = n => Number.isFinite(n) ? new Intl.NumberFormat('ko-KR',{maximumFractionDigits:2}).format(n) : '—';
const price = n => Number.isFinite(n) ? new Intl.NumberFormat('ko-KR',{minimumFractionDigits:2,maximumFractionDigits:2}).format(n) : '—';
const pct = n => Number.isFinite(n) ? `${n>0?'+':''}${n.toFixed(2)}%` : '—';
const date = n => Number.isFinite(n) ? new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(n*1000)) : 'UNKNOWN';
const tone = n => !Number.isFinite(n) ? 'muted' : n>0 ? 'positive' : n<0 ? 'negative' : '';
const isAnalysis=location.pathname==='/analysis';
let latest = null, analysisReport=null, selected = null, busy = false, detailVersion = 0, renderedSignature = null, offset=0, csrf=null, controlBusy=false, controlData=null;
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
  const scope=s.market_scope,total=scope?.total,focus=scope?.focus;
  value('configured-scope',scope?`설정 ${number(scope.configured_unique)}종목 / ${number(scope.configured_venue_pairs)}쌍 · 고정 관측`:'상세 범위는 웹 서버 갱신 후 확인');
  if(scope?.mode==='ALL_KRW_WEBSOCKET')value('configured-scope','전체 KRW · 실제 카탈로그 및 수신 상태 확인 중');
  value('total-markets',total?.unique==null?'UNKNOWN':number(total.unique));
  value('total-by-exchange',total?.unique==null?'거래소 시장목록 근거 없음':`UPBIT ${number(total.by_exchange.UPBIT)} · BITHUMB ${number(total.by_exchange.BITHUMB)} · 합계 ${number(total.venue_pairs)}쌍`);
  value('total-market-time',total?.at?`${date(total.at)} KST${total.status==='STALE'?' · 오래된 조회값':''}`:'명시적 시장목록 확인 후 표시');
  value('focus-markets',focus?.unique==null?'UNKNOWN':number(focus.unique));
  value('focus-pairs',focus?.venue_pairs==null?'평가 추적 근거 없음':`${number(focus.venue_pairs)} 거래소·종목 쌍 · 평가 대기 신호 기준`);
  const ws=s.websocket;const venues=Object.values(ws?.exchanges||{});
  $('ws-panel').hidden=!venues.length;
  if(venues.length){
    const sum=k=>venues.reduce((n,v)=>n+(v[k]||0),0);const live=ws.fresh;
    value('configured-scope',`전체 KRW 등록 ${number(sum('registered'))}쌍 · WebSocket`);
    value('ws-subscriptions',`${number(sum('registered'))} / ${live?number(sum('subscription_sent')):'0'} / ${live?number(sum('subscription_confirmed')):'0'}`);
    value('markets',live?number(sum('active')):'0');value('pairs','최근 60초 유효 데이터 수신 거래소·종목 쌍');
    value('ws-active',live?`${number(sum('active'))} / ${number(sum('stale'))} / ${number(sum('blocked'))}`:'0 / 과거 수집 상태');
    const last=Math.max(...venues.map(v=>v.last_received||0));
    value('ws-last',`최근 정상 수신 ${last?date(last):'UNKNOWN'} KST`);
    value('ws-evaluated',`${number(sum('evaluated'))} / ${number(sum('complete_30m'))}`);
    value('ws-requests',`누적 HTTP ${number(ws.requests)} · ${live?'현재':'마지막 저장'} 5분 격자 평가`);
    value('total-by-exchange',Object.entries(ws.exchanges).map(([e,v])=>`${e} 적격 ${number(v.eligible)} / 목록 ${number(v.listed)}`).join(' · '));
    value('scope-note','전체 공개 KRW 목록을 구독합니다. 정지·종료 상태가 확인되면 제외합니다. 구독 요청, 실제 수신, 결측을 포함한 평가 시도, 30분 완전 자료는 각각 다릅니다.');
  }
  value('today-signals',data.errors.length?'UNKNOWN':number(data.today_live_signals));
  const connections=$('connections');connections.replaceChildren();
  Object.entries(s.connections||{}).forEach(([name,c])=>{const r=node('small');r.append(node('span',name),node('span',c.status,c.status==='CONNECTED'?'positive':c.status==='ERROR'?'warning':'muted'));r.title=`최근 ${ws?'WebSocket 수신':'API 응답'} ${date(c.at)} KST`;connections.append(r);});
  const clock=s.clock||'UNKNOWN';value('clock-status',clock.startsWith('PASS')?'PASS':clock.startsWith('FAIL')?'FAIL':'UNKNOWN',clock.startsWith('PASS')?'positive':clock.startsWith('FAIL')?'warning':'muted');
  value('clock-detail',clock.startsWith('PASS')?clock.includes('cross-check')?'직접 NTP 교차 검증 통과 · Windows 루트 품질 경고 유지':clock.replace('PASS ',''):clock.startsWith('FAIL')?'마지막 시계 검사 실패 · 시작 시 재검증':clock.includes('stale')?'과거 PASS 만료 · 시작 시 재검증':'검증 근거 없음 · 시작 시 전체 검증');
  value('storage',`DB ${s.db_saved||'UNKNOWN'} · ${s.size===null||s.size===undefined?'크기 UNKNOWN':(s.size/1048576).toFixed(2)+' MiB'} · 수집 ${date(s.collected)}`);
  const messages=[...data.errors];if(s.reason)messages.push(`최근 시작·운영 결과: ${s.reason} · 다시 시작하면 시계를 새로 검증합니다.`);
  $('api-error').hidden=!messages.length;$('api-error').textContent=messages.join(' / ');
  if(data.engine==='V15'){
    value('scanner-phase',s.status==='EXTERNAL_RUNNING'?'별도 실행 V15 · 웹 제어 제외':`${s.phase} · 원본 V15 스캔 상태`);
    value('clock-status',s.heartbeat_fresh?'FRESH':s.process_alive?'UNKNOWN':'STOPPED',s.heartbeat_fresh?'positive':'muted');
    value('clock-detail',`최근 heartbeat ${date(s.heartbeat)} KST · V15 NTP 검사 미지원`);
    value('markets',number(s.markets));value('pairs',s.venue_pairs==null?'실제 수신 수 확인 불가':`${number(s.venue_pairs)} 거래소·종목 쌍 · 누적 유효 수신`);
    value('configured-scope','기존 V15 전체 KRW 구독 · 실제 수신 확인 수와 구분');
    value('total-markets',number(s.listed_unique));value('total-by-exchange',Object.entries(s.exchanges||{}).map(([e,v])=>`${e} 목록 ${number(v.listed)} / 수신 ${number(v.received)} / 최근60초 ${number(v.active)}`).join(' · ')||'현재 실행의 목록 근거 없음');
    value('total-market-time',s.started_at?`현재/마지막 실행 ${date(s.started_at)} KST`:'조회 시각 미확인');
    value('focus-markets',s.heartbeat_fresh?number(s.scanned_pairs):'UNKNOWN');value('focus-pairs',`원본 analyze ${number(s.analyze_calls)}회 · 최근 ${date(s.last_analyze)} KST`);
    value('scope-note','V15는 미검증 실험 전략입니다. 목록·실제 수신·스캔 완료 수를 구분합니다. 별도 실행의 상세 수집 상태는 추정하지 않습니다.');
    if(s.reason){$('api-error').hidden=false;value('api-error',[...data.errors,`최근 V15 상태: ${s.reason}`].join(' / '));}
  }
}
function renderRows(){
  const data=isAnalysis?analysisReport:latest;if(!data)return;
  const scope=isAnalysis?'ALL':$('scope').value;
  const total=isAnalysis?data.summary.total:data.total;
  const signature=JSON.stringify([scope,data.signals,total,selected?.key,offset]);
  if(signature===renderedSignature)return;
  renderedSignature=signature;
  const rows=data.signals.filter(r=>scope==='ALL'||r.scope===scope);
  const body=$('signal-rows');body.replaceChildren();
  value('signal-count',`${total}건`);
  $('empty').hidden=rows.length>0;
  value('list-note',isAnalysis?`표시 ${rows.length?offset+1:0}–${offset+rows.length} / ${total}건 · 통계는 전체 표본 기준`:`표시 ${rows.length} / 저장 ${total}건 · 최신 ${data.limit}건 범위`);
  $('previous-page').disabled=offset===0;$('next-page').disabled=offset+rows.length>=total;
  rows.forEach(r=>{
    const tr=node('tr');const key=`${r.dataset}:${r.signal_id}`;
    if(selected?.key===key)tr.className='selected';
    const time=node('td');const button=node('button',date(r.detected_at),'signal-button');button.type='button';button.setAttribute('aria-label',`${r.market} ${date(r.detected_at)} 신호 상세`);button.addEventListener('click',()=>choose(r));time.append(button,node('span',`신호 ${date(r.signal_time).slice(11)}`,'sub'));tr.append(time);
    const market=node('td');market.append(node('div',r.exchange,'exchange'),node('div',r.market,'market'));tr.append(market);
    const pattern=node('td');pattern.append(node('span',groups[r.cohort]||names[r.scope]||'확인 불가',`tag ${r.scope==='CURRENT_LIVE'?'live':''}`),node('div',patternName(r.pattern),'pattern'),node('span',r.source==='V15'?'원천 V15 · 별도 기준 시각 미저장':r.source==='LIVE'?'원천 LIVE':'원천 지연 수집','sub'));tr.append(pattern);
    tr.append(node('td',Number.isFinite(r.score)?number(r.score):'미정의','number muted'),node('td',price(r.detection_price),'number'));
    const completed=r.horizons.filter(h=>h.status==='COMPLETE'&&Number.isFinite(h.return_pct)).at(-1);
    r={...r,return_pct:completed?.return_pct,return_minutes:completed?.minutes};
    const change=node('td',pct(r.return_pct),`number ${tone(r.return_pct)}`);change.append(node('span',r.return_minutes?`${r.return_minutes}분 후 · 저장 데이터`:'평가 데이터 부족','sub'));tr.append(change);
    const evaluation=node('td',undefined,'eval');r.horizons.forEach((h,i)=>{evaluation.append(node('span',`${h.minutes}분 ${states[h.status]||'확인 불가'}`));if(i===1)evaluation.append(document.createElement('br'));else if(i!==3)evaluation.append(document.createTextNode(' · '));});tr.append(evaluation);
    // The explicit button supports keyboard navigation; the full row is also clickable.
    tr.addEventListener('click',event=>{if(event.target!==button)choose(r);});body.append(tr);
  });
}
async function choose(r){selected={dataset:r.dataset,id:r.signal_id,key:`${r.dataset}:${r.signal_id}`};try{sessionStorage.setItem('chio-selected',JSON.stringify(selected));}catch{}renderRows();await loadDetail();}
async function loadDetail(){
  if(!selected)return;
  const version=++detailVersion;
  try{
    const r=await get(`/api/${isAnalysis?'analysis/':''}signal?dataset=${encodeURIComponent(selected.dataset)}&id=${encodeURIComponent(selected.id)}`);
    if(version!==detailVersion)return;
    $('detail-empty').hidden=true;$('detail-content').hidden=false;
    value('detail-market',`${r.exchange} · ${r.market}`);value('detail-scope',names[r.scope]||'UNKNOWN');
    value('detail-subtitle',`기준 ${date(r.signal_time)} KST · 탐지 ${date(r.detected_at)} KST · ${patternName(r.pattern)}`);
    if(r.engine==='V15')value('detail-subtitle',`저장 탐지 ${date(r.detected_at)} KST · 별도 기준 시각 미지원 · ${patternName(r.pattern)}`);
    value('detail-price',price(r.detection_price));value('detail-score',Number.isFinite(r.score)?number(r.score):'미정의','muted');
    $('horizons').replaceChildren();r.horizons.forEach(h=>{const card=node('div',undefined,'horizon');card.append(node('small',`${h.minutes}분 후`),node('strong',h.status==='COMPLETE'?pct(h.return_pct):'—',tone(h.return_pct)),node('span',states[h.status]||'확인 불가','sub'));$('horizons').append(card);});
    const complete=r.horizons.filter(h=>h.status==='COMPLETE');const longest=complete.at(-1);
    value('mfe',pct(longest?.mfe_pct),tone(longest?.mfe_pct));value('mae',pct(longest?.mae_pct),tone(longest?.mae_pct));
    value('mfe-horizon',longest?`(${longest.minutes}분)`:'');value('mae-horizon',longest?`(${longest.minutes}분)`:'');
    value('metric-note',r.horizons.some(h=>h.basis==='STORED_CANDLES_VIEW_ONLY')?'가격 지표는 연속된 저장 원천봉으로 화면에서만 계산합니다. 결측을 채우거나 원래 연구 평가를 변경하지 않습니다.':'DB에 저장된 후속 평가만 표시합니다. 미완성 구간의 수익률은 계산하지 않습니다.');
    if(r.engine==='V15')value('metric-note','원래 저장 지표만 표시합니다. 누락·지연·미도래 구간은 집계에서 제외합니다. PRE-PUMP 시각 검증은 미지원이며 관측 극값은 시장 전체 고가·저가가 아닙니다.');
    const labels={SUCCESS:'조건 도달',FAILURE:'조건 미도달',PENDING:'평가 대기',UNKNOWN:'자료 부족'};
    value('outcomes',`기존 연구 평가: ${r.outcomes.length?r.outcomes.map(o=>`${o.label} ${labels[o.status]||'확인 불가'} (${o.observed_minutes}/${o.expected_minutes}분)`).join(' · '):'자료 없음'} · 평가 기준가격 ${price(r.signal_price)} KRW · 단순 가격 변화이며 실제 거래 수익률이 아닙니다.`);
    if(r.engine==='V15'){
      value('outcomes','원래 저장 탐지 시각(KST 가정) 기준 · 별도 신호 기준 시각/기존 연구 label 미지원 · 실제 체결 수익이 아닙니다.');
      value('metric-note',$('metric-note').textContent+' '+r.horizons.filter(h=>h.status==='INSUFFICIENT_DATA').map(h=>`${h.minutes}분 ${quality[h.reason]||'자료 검증 불가'}`).join(' / '));
    }
    chart(r);
  }catch(e){if(version===detailVersion){$('detail-content').hidden=true;$('detail-empty').hidden=false;value('detail-empty',e.message);}}
}
function svg(tag,attrs,text){const e=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;return e;}
function chart(r){
  const wrap=$('chart');wrap.replaceChildren();
  const bars=r.candles.filter(c=>Number.isFinite(c.close)&&c.close>0);
  if(!bars.length){wrap.append(node('div','저장된 원천 가격이 없습니다.','chart-empty'));return;}
  const w=900,h=210,l=70,right=20,top=16,bottom=30;
  const isV15=r.engine==='V15';
  const start=r.signal_time-(isV15?0:1800),end=Math.max(r.signal_time+3600,...bars.map(b=>b.ts));
  let low=Math.min(...bars.map(b=>b.close)),high=Math.max(...bars.map(b=>b.close));
  const pad=Math.max((high-low)*.14,high*.0005);low-=pad;high+=pad;
  const x=t=>l+(t-start)/(end-start)*(w-l-right),y=p=>top+(high-p)/(high-low)*(h-top-bottom);
  const s=svg('svg',{viewBox:`0 0 ${w} ${h}`,role:'img','aria-label':`${r.market} 실제 저장 종가 ${bars.length}개. 빈 구간은 연결하지 않음.`});
  for(let i=0;i<4;i++){const p=low+(high-low)*i/3;const at=y(p);s.append(svg('line',{x1:l,x2:w-right,y1:at,y2:at,stroke:'#2b3b30','stroke-width':.7}),svg('text',{x:l-10,y:at+3,'text-anchor':'end',fill:'#7e9787','font-size':10},price(p)));}
  for(const offset of (isV15?[0,5,10,30,60]:[-30,0,15,30,60])){const at=x(r.signal_time+offset*60);s.append(svg('text',{x:at,y:h-8,'text-anchor':'middle',fill:offset===0?'#b2cfaa':'#7e9787','font-size':10},offset===0?'신호':`${offset>0?'+':''}${offset}분`));}
  s.append(svg('line',{x1:x(r.signal_time),x2:x(r.signal_time),y1:top,y2:h-bottom,stroke:'#91a785','stroke-dasharray':'4 4'}));
  let path='',prev=null;bars.forEach(b=>{const t=b.ts+(isV15?0:60);const contiguous=prev!==null&&(isV15?b.minute===prev.minute+1&&b.ts-prev.ts<120:b.ts-prev.ts===60);path+=`${contiguous?'L':'M'}${x(t).toFixed(2)},${y(b.close).toFixed(2)} `;prev=b;});
  s.append(svg('path',{d:path,fill:'none',stroke:'#8bdbac','stroke-width':2,'stroke-linejoin':'round'}));
  bars.forEach(b=>{const at=b.ts+(isV15?0:60);const c=svg('circle',{cx:x(at),cy:y(b.close),r:2,fill:'#8bdbac'});c.append(svg('title',{},`${date(at)} KST · ${number(b.close)} KRW`));s.append(c);});
  wrap.append(s);
}
async function refresh(){
  if(busy)return;busy=true;
  try{latest=await get(`/api/snapshot?scope=${encodeURIComponent($('scope').value)}`);renderStatus(latest);if(isAnalysis){analysisReport=await get(`/api/analysis?group=${$('analysis-group').value}&offset=${offset}`);renderAnalysis();}renderRows();if(selected)await loadDetail();await refreshControl();}
  catch(e){value('web-state','웹 서버 연결 끊김','warning');value('scanner-status','UNKNOWN','muted');value('scanner-phase','서버 응답 없음 · 마지막 표시는 과거 자료입니다.');value('markets','UNKNOWN','muted');for(const id of ['ws-subscriptions','ws-active','ws-evaluated'])value(id,'UNKNOWN','muted');value('today-signals','UNKNOWN','muted');value('clock-status','UNKNOWN','muted');$('connections').replaceChildren(node('small','UPBIT / BITHUMB · UNKNOWN'));$('api-error').hidden=false;value('api-error',`${e.message} · 서버 상태를 확인하세요. 아래 신호 목록은 마지막 조회 결과입니다.`);}
  finally{busy=false;}
}
function renderAnalysis(){
  const s=analysisReport.summary;
  value('analyzed',`${number(s.analyzed)}개`);value('analyzed-n',`유효 표본 ${number(s.analyzed)} / 저장 ${number(s.total)}개 · 1개 이상 구간 완료`);
  if(analysisReport.analyzer){value('analyzed-n',`유효 ${number(s.analyzed)} / 저장 ${number(s.total)} · 미도래 ${number(s.pending)} · 누락·시각미검증 ${number(s.incomplete)}`);value('analysis-note',`기존 V7 분석기 연결 · 저장 값만 집계 · 5·10·30·60분. PRE-PUMP 시각 검증/장기 차트 미지원. ${Object.entries(analysisReport.paper||{}).map(([g,p])=>`${groups[g]} 가상매매 종료 n=${p.n}, 평균 ${pct(p.mean_pct)}, 승률 ${pct(p.win_pct)}, OPEN ${p.open}건 제외`).join(' / ')}. 실제 체결 수익이 아닙니다.`);}
  for(const [id,key] of [['rise-30m','rise_30m'],['return-30m','return_30m'],['mfe-30m','mfe_30m']]){
    const m=s[key];value(id,pct(m.value),id==='rise-30m'?'':tone(m.value));value(`${id}-n`,`유효 표본 ${number(m.n)}개 · 30분 평가 완료`);
  }
  const body=$('pattern-rows');body.replaceChildren();$('patterns-empty').hidden=analysisReport.patterns.length>0;
  for(const p of [...analysisReport.patterns,...(analysisReport.score_groups||[])]){
    const tr=node('tr'),name=node('td');name.append(node('span',groups[p.cohort]||p.cohort,'tag'),node('div',patternName(p.pattern),'pattern'),node('small','성능 판단 보류','sub'));tr.append(name,node('td',`${p.return_30m.n} / ${p.total}개`,'number'));
    for(const k of ['return_30m','rise_30m']){const td=node('td',pct(p[k].value),`number ${k==='return_30m'?tone(p[k].value):''}`);td.append(node('small',`n=${p[k].n}`,'sub'));tr.append(td);}
    const exc=node('td',undefined,'number');exc.append(node('span',pct(p.mfe_30m.value),tone(p.mfe_30m.value)),document.createTextNode(' / '),node('span',pct(p.mae_30m.value),tone(p.mae_30m.value)),node('small',`n=${p.mfe_30m.n} / ${p.mae_30m.n}`,'sub'));tr.append(exc);body.append(tr);
  }
  const samples=$('curve-samples');samples.replaceChildren();for(const m of s.curve){samples.append(node('span',`${m.minutes}분 ${pct(m.value)} · n=${m.n}`));}
  averageChart(s);
  if(analysisReport.errors.length){$('api-error').hidden=false;value('api-error',analysisReport.errors.join(' / '));}
}
function averageChart(summary){
  const wrap=$('average-chart');wrap.replaceChildren();const curve=summary.curve;
  if(!curve.some(m=>m.n>0&&Number.isFinite(m.value))){wrap.append(node('div','아직 완료된 후속 평가가 없습니다. 저장 가격이 확보되면 표시됩니다.','chart-empty'));return;}
  const w=940,h=240,l=65,right=36,top=30,bottom=38;
  const vals=[0,...curve.map(m=>m.value).filter(Number.isFinite)];let lo=Math.min(...vals),hi=Math.max(...vals);const pad=Math.max((hi-lo)*.23,.15);lo-=pad;hi+=pad;
  const x=m=>l+m/60*(w-l-right),y=v=>top+(hi-v)/(hi-lo)*(h-top-bottom);
  const s=svg('svg',{viewBox:`0 0 ${w} ${h}`,role:'img','aria-label':'신호 후 평균 가격 변화. 각 시점의 유효 표본 수를 함께 표시합니다.'});
  for(let i=0;i<4;i++){const v=lo+(hi-lo)*i/3;s.append(svg('line',{x1:l,x2:w-right,y1:y(v),y2:y(v),stroke:'#293a30','stroke-width':.8}),svg('text',{x:l-10,y:y(v)+3,fill:'#82958a','text-anchor':'end','font-size':11},`${v.toFixed(2)}%`));}
  s.append(svg('line',{x1:l,x2:w-right,y1:y(0),y2:y(0),stroke:'#617366','stroke-dasharray':'4 4'}));
  const points=[{minutes:0,value:0,n:summary.analyzed},...curve];let path='',previous=false;
  for(const p of points){const at=x(p.minutes);s.append(svg('text',{x:at,y:h-12,fill:'#a0b5a7','text-anchor':'middle','font-size':11},p.minutes===0?'기준 시점':`${p.minutes}분`));
    if(!p.n||!Number.isFinite(p.value)){previous=false;continue;}
    path+=`${previous?'L':'M'}${at},${y(p.value)} `;previous=true;
  }
  s.append(svg('path',{d:path,fill:'none',stroke:'#86d9ad','stroke-width':2.5}));
  for(const p of points){if(!p.n||!Number.isFinite(p.value))continue;const c=svg('circle',{cx:x(p.minutes),cy:y(p.value),r:4,fill:p.value<0?'#ef9191':'#86d9ad'});c.append(svg('title',{},`${p.minutes}분 ${pct(p.value)} · n=${p.n}`));s.append(c);if(p.minutes)s.append(svg('text',{x:x(p.minutes),y:y(p.value)-13,fill:p.value<0?'#ef9191':'#86d9ad','text-anchor':'middle','font-size':11},`${pct(p.value)} · n=${p.n}`));}
  wrap.append(s);
}
function renderControl(data){
  controlData=data;csrf=data.token||csrf;
  $('start-scanner').disabled=controlBusy||data.busy||data.process_alive!==false;
  $('stop-scanner').disabled=controlBusy||data.stopping||!(data.starting||(data.stop_allowed??data.process_alive));
  value('control-message',data.message,data.state==='FAILED'?'warning':data.state==='SUCCEEDED'?'positive':'');
  value('control-bounds',`관측 전용 · 최대 ${number(data.seconds)}초 / HTTP ${number(data.max_requests)}회 · ${data.engine==='V15'?'원본 V15 · 외부 실행 보호 · NTP 검사 미지원':'시계 검증 후 시작'}`);
}
async function refreshControl(){try{renderControl(await get('/api/control'));}catch{csrf=null;$('start-scanner').disabled=true;$('stop-scanner').disabled=true;value('control-message','로컬 제어 연결을 확인할 수 없습니다. 상태 BAT를 확인하세요.','warning');}}
async function operate(action){
  if(controlBusy||!csrf)return;controlBusy=true;$('start-scanner').disabled=true;$('stop-scanner').disabled=true;
  try{const response=await fetch(`/api/control/${action}`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:'{}',signal:AbortSignal.timeout(4500)});const data=await response.json();if(!response.ok)throw new Error(data.error||'제어 요청 실패');renderControl(data);}
  catch(e){value('control-message',`${e.message} · 실제 상태를 다시 확인합니다.`, 'warning');}
  finally{controlBusy=false;await refreshControl();await refresh();}
}
$('live-page').hidden=isAnalysis;$('live-controls').hidden=isAnalysis;$('analysis-page').hidden=!isAnalysis;$('scope').hidden=isAnalysis;$('pagination').hidden=!isAnalysis;
$(isAnalysis?'nav-analysis':'nav-live').setAttribute('aria-current','page');
try{const savedGroup=sessionStorage.getItem('chio-analysis-group');if(savedGroup&&[...$('analysis-group').options].some(o=>o.value===savedGroup))$('analysis-group').value=savedGroup;}catch{}
$('analysis-group').addEventListener('change',()=>{offset=0;selected=null;detailVersion++;$('detail-content').hidden=true;$('detail-empty').hidden=false;value('detail-market','선택 대기');value('detail-subtitle','목록에서 신호를 선택하세요.');try{sessionStorage.removeItem('chio-selected');sessionStorage.setItem('chio-analysis-group',$('analysis-group').value);}catch{}refresh();});
$('previous-page').addEventListener('click',()=>{offset=Math.max(0,offset-200);refresh();});$('next-page').addEventListener('click',()=>{offset+=200;refresh();});
$('start-scanner').addEventListener('click',()=>operate('start'));$('stop-scanner').addEventListener('click',()=>operate('stop'));
$('scope').addEventListener('change',refresh);$('refresh').addEventListener('click',refresh);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
setInterval(()=>{if(!document.hidden)refresh();},5000);refresh();
setInterval(()=>{if(!document.hidden&&controlData?.busy)refreshControl();},1000);
