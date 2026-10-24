"""Finalize only after the bounded worker has exited. No network/backtest."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from coin_analysis import forward_scanner_v42 as observation
from coin_analysis.forward_scanner_v42_review import review_episode
from coin_analysis.legacy_open_reconciliation import digest

OUT=Path(__file__).resolve().parent


def stamp(t):
    return datetime.fromtimestamp(t,observation.scanner.collector.KST).strftime('%Y-%m-%d %H:%M:%S KST') if t is not None else 'UNKNOWN'


def main():
    runtime=ROOT/'data/scanner_v42_live'
    episodes=[review_episode(runtime/name) for name in ('episode_20261024','episode_20261024_supported')]
    actual=episodes[-1]
    protected=json.loads((ROOT/'reports/scanner_v41_validation_20261024/input_manifest.json').read_text(encoding='utf8'))['inputs']
    preservation={p:digest(p)==row['sha256'] for p,row in protected.items()}
    original=sqlite3.connect((ROOT/'data/forward_scanner_v4.db').as_uri()+'?mode=ro',uri=True)
    try:
        original_signals=original.execute('SELECT COUNT(*) FROM signals').fetchone()[0]
        original_integrity=original.execute('PRAGMA quick_check').fetchone()[0]
    finally:original.close()
    private_hashes={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=digest(p)) for p in (runtime/'episode_20261024_supported').iterdir() if p.is_file()}
    result=dict(finalized_at=time.time(),verdict='INSUFFICIENT_DATA',baseline_commit='4426c56',episodes=episodes,
        protected_inputs=len(preservation),preservation=preservation,all_preserved=all(preservation.values()),
        original_signals=original_signals,original_integrity=original_integrity,private_evidence_hashes=private_hashes,
        total_http_attempts=sum(e['http']['attempts'] for e in episodes),task_http_budget=220,
        original_163_merged=False,automatic_restart=False,worker_left_running=False)
    if result['total_http_attempts']>220:raise AssertionError('Unexpected task budget excess')
    if not all(preservation.values()) or original_signals!=163:raise AssertionError('Protected inputs changed; investigate without overwrite')
    with (OUT/'summary.json').open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    total_signals=sum(e['signal_count'] for e in actual['per_exchange'].values())
    live=sum(e['source_counts'].get('LIVE',0) for e in actual['per_exchange'].values())
    lines=['# Scanner V4.2 제한 LIVE 관측 및 조기 탐지 검증 — 2026-10-24','',
        '## 판정: INSUFFICIENT_DATA','',
        f"별도 공개 시세 관측을 실제로 실행했다. 지원 확인을 통과한 episode의 신규 신호는 **{total_signals}개(LIVE {live}개)**다. 이 짧은 관측으로 조기 탐지 능력·승률·누락률·수익성을 판단하지 않는다. 기존163개 신호와 신규 성과는 혼합하지 않았다.",'',
        '기준: `4426c56`, [V4.1 보고서](scanner_v41_repair_validation_20261024.md). [최종 증거 JSON](../reports/scanner_v42_20261024/summary.json) · [사전 검사](../reports/scanner_v42_20261024/preflight.json) · [선별 테스트](../reports/scanner_v42_20261024/selective_tests.log) · [운영·종료·재시작 안내](scanner_v42_operations.md)。','',
        '## 1. 실행 구조와 동결 범위','',
        '- V4.1의 탐지·feature·label·임계값·5분 observation·LIVE/CATCHUP 정책을 그대로 재사용했다. 기존 core/collector/보관 V15 코드는 변경하지 않았다. 신규 wrapper는 주문·가상자금 체결·키·인증 endpoint를 사용하지 않는다.',
        '- V4는 원래 업비트 전용이며 점수가 없다. 빗썸에는 공개1분봉 transport와 KST 요청 시각 변환만 연결해 **같은 V4 정책**을 별도 DB에서 실행했다. 구형 빗썸 V15 점수 전략을 실행하거나 검증했다고 주장하지 않는다. score는 NULL/NOT_DEFINED_BY_V4, pattern은 RANGE_30M_GE4_FIRST_CLUSTER다.',
        '- 고정 cohort는 각 거래소 **BTC·ENA·ETH·FLOCK·SAND**, 거래소-시장10쌍/고유5종목이다. BTC는 benchmark이며 신호 대상은 각4개, 총8쌍이다. 원본50알트 universe와 다르므로 상대강도 등 secondary feature를 원본과 같은 모집단으로 해석하지 않는다.',
        '- 최초 ICX 포함 cohort는 업비트 시장 목록에서 ICX를 찾지 못해1회 조회 후 BLOCKED되었다. candle 수집·신호 생성·LIVE 완료로 집계하지 않았다. 가격/성과를 보고 고른 것이 아닌 지원 여부 때문에 ETH로 교체하고 **새 episode로 재동결**했다. 원본 frozen universe는 수정하지 않았다. [범위 변경 기록](../reports/scanner_v42_20261024/cohort_update.json)。','',
        '## 2. 실제 관측 시각과 범위','',
        '|항목|실제 기록|','|---|---|',
        f"|최초 지원 실패 시도|{stamp(episodes[0]['process_interval']['start'])} ~ {stamp(episodes[0]['process_interval']['end'])}; 캔들0|",
        f"|지원 통과 episode worker 시작|{stamp(actual['process_interval']['start'])}|",
        f"|worker 종료|{stamp(actual['process_interval']['end'])}|",
        f"|실제 worker 경과|{actual['worker']['elapsed_seconds']:.3f}초; 예정900초를 관측 완료로 대신 쓰지 않음|",
        f"|신규 신호 정책 시작|{stamp(actual['config']['signal_start'])}; 그 이전 봉은 warmup|",
        f"|종료 상태|{actual['worker']['status']} / {actual['worker']['reason']}|",
        f"|완료 round / task HTTP|{actual['worker']['completed_rounds']} / {result['total_http_attempts']}회(지원 실패1회 포함, 총한도220)|",'',
        '|거래소|수집 시장|전체 봉(warmup 포함)|signal_start 이후 저장 봉|최종 공통 verified_until|신규 신호 LIVE/CATCHUP|',
        '|---|---:|---:|---:|---|---:|']
    for exchange,info in actual['per_exchange'].items():
        counts=info['candle_counts']
        lines.append(f"|{exchange}|{len(counts)}|{sum(r['total'] for r in counts)}|{sum(r['new_candles'] for r in counts)}|{stamp(info['common_verified_until'])}|{info['source_counts'].get('LIVE',0)}/{info['source_counts'].get('CATCHUP',0)}|")
    lines+=['','6시간에 가까운 사전 API warmup은 실행 전 과거 봉이며 LIVE 실행 시간에 더하지 않았다. worker 생존 시간, 실제 수집 응답 시간, 확정봉 범위, 신호 평가 시각은 서로 다르다. 중단/종료 뒤 관측하지 않은 구간을 채우지 않았다.','',
        '## 3. 데이터와 신호 품질','',
        '- 기존 API pagination/UTC·KST/봉 마감5초 settle/원천 KRW 거래대금/OHLC×수량/중복 및 충돌 검증을 경유했다. quote나 수량을 임의로 원화 환산하지 않았다. validation 예외와 HTTP 오류는 raw 운영 로그에 남긴다.',
        '- 실제 disk close/reopen과 bootstrap backup 후 모든 논리 값 hash 일치를 확인했다. 실제 OS 재부팅은 하지 않았다. 프로세스 강제 종료/WAL 복원은 선별 합성 테스트 범위다.',
        '- 신호가 발생하면 canonical signal_time/price, detected_at, 직전 가격·거래대금 특징, 확정봉 asof를 저장한다. detection_price는 마지막 저장 확정 종가의 proxy이며 정확한 체결 시세·주문가는 아니다. 도착 시각 custody 한계가 있다.',
        '- 별도 live_horizons는5/15/30/60분 전체 미래 봉과 verified 범위가 있을 때만 COMPLETE, 그 외는 PENDING이다. 원래 V4 L1/L2 규칙을 바꾸지 않는다. 완료된 LIVE 표본만 아래 가격 변화 집계에 넣고 CATCHUP은 합산하지 않는다. 비용·슬리피지·실제 체결은 없다.','',
        '|거래소|quick_check|중복 신호/봉|정각 오류/종료 후 미래 봉|range 유효/전체 관측|최대 range30 %|','|---|---|---:|---:|---:|---:|']
    for exchange,info in actual['per_exchange'].items():
        q=info['quality'];p=info['range_observation_panel']
        widths=[v['range30_max_pct'] for v in p.values() if v['range30_max_pct'] is not None]
        maximum=f'{max(widths):.6f}' if widths else 'N/A'
        lines.append(f"|{exchange}|{q['quick_check']}|{q['duplicate_signals']}/{q['duplicate_candles']}|{q['timestamp_misalignment']}/{q['future_candles_at_stop']}|{sum(v['valid'] for v in p.values())}/{sum(v['grid'] for v in p.values())}|{maximum}|")
    lines+=['','|거래소|분|완료/PENDING|평균 가격 변화 %|평균 MFE %|평균 MAE %|','|---|---:|---:|---:|---:|---:|']
    def fmt(x):return 'N/A' if x is None else f'{x:.6f}'
    for exchange,info in actual['per_exchange'].items():
        for h,row in info['horizon_summary'].items():
            lines.append(f"|{exchange}|{h}|{row['complete']}/{row['pending']}|{fmt(row['return_pct']['mean'])}|{fmt(row['mfe_pct']['mean'])}|{fmt(row['mae_pct']['mean'])}|")
    lines+=['','自然 신호가 없거나 horizon이 미완료인 필드의 실측 성능은 미검증이다. synthetic 테스트에서 저장·PENDING·완료·불변성·재시작 경로를 확인했다는 사실과 실제 자연 신호에서 성공했다는 주장은 구분한다.','',
        '## 4. 조기 탐지·추격·실패·누락','',
        '종목별 UTC5분 기준 종가 t와 이후60개 실제1분봉이 모두 있을 때 +5%/+10% high 도달 사건을 정의한다. 최초 적격 anchor 이후 t+60분까지 같은 threshold 사건을 다시 세지 않는다. 실제 LIVE detected_at이 [t-30분,t]면 기준점 이전, (t,목표 도달 봉 마감)이면 추격, 이후60분 안이면 목표 도달 뒤로 분류한다. 기준점 이전은 진짜 급등 시작 전 예측과 같지 않고, 목표 도달 뒤도 전체 상승 종료 뒤와 같지 않다. 이 정의는 기존 진단의 고정 비교 기준을 재사용했으며 새 최적화가 아니다. [분석 기준 기록](../reports/scanner_v42_20261024/analysis_policy.json)은 실행 중에 작성했으므로 시작 전 동결 증거라고 표현하지 않는다.','',
        '|거래소|기준|완전 미래 기준점|상승 사건|목표 전 포착률|','|---|---|---:|---:|---:|']
    for exchange,info in actual['per_exchange'].items():
        for threshold,row in info['recall'].items():lines.append(f"|{exchange}|+{threshold}%/60m|{row['eligible_full_future_anchors']}|{row['events']}|{fmt(row['capture_before_target_pct'])}|")
    declines=sum(len(i['immediate_declines']) for i in actual['per_exchange'].values());surges=sum(len(i['additional_surge_cases']) for i in actual['per_exchange'].values())
    lines +=['',f"관측 내 완료5분 음수 사례 {declines}건, 완료 V4 목표 추가 상승 사례 {surges}건이다. 실제 사례의 세부 기록은 증거 JSON에 보존했다. 분모가 없으면 성공률·누락률을0% 또는100%로 만들지 않는다. 이번 시간·시장만의 자료를 전체 시장으로 일반화할 수 없다.",'',
        '## 5. 운영 안정성·발견 결점','',
        f"- worker RSS 최대 {actual['worker']['peak_rss_bytes']/1048576:.2f}MiB(상한256MiB), 종료 시 runtime 파일 합계 {actual['worker']['data_bytes']/1048576:.2f}MiB(상한64MiB). 로그 상한1MiB, 요청 timeout5초, 부모 hard deadline+30초. 무제한 loop·자동 재시작 없음.",
        f"- 지원 통과 episode HTTP 오류 {actual['http']['errors']}건; 실제 HTTP 시작 이력과 worker count 일치={actual['http']['count_matches_worker']}. 실패한 ICX 지원 확인은 별도 BLOCKED이며 성공 수집으로 바꾸지 않았다.",
        f"- DB close/reopen 검증={actual['worker']['disk_reopen_verified']}, close_errors={actual['worker']['close_errors']}, worker_reaped={actual['supervisor']['worker_reaped']}. 종료 후 별도 관측 프로세스를 유지하지 않는다.",
        '- 실행 중 실제 두 번째 supervisor 기동을 시도해 OS lock 거부를 확인했다. 새 worker·HTTP는 생성되지 않았고 기존 관측을 중단하지 않았다. [동시 기동 증거](../reports/scanner_v42_20261024/duplicate_guard.json)。',
        '- 확인한 결점: 원래 고정 universe의 ICX가 현재 업비트 지원 목록에 없다. 원본 설정을 조용히 탈락/대체하면 연구 분모가 변하므로 원본은 보존하고 새 cohort에만 지원 검사를 적용했다.',
        '- 짧은 제한 운용과 synthetic 오류/timeout 테스트는 장기 무인 운용·실제418/429 회복·OS 재부팅·원천 체결 진실성 전체를 입증하지 않는다. API volume은 입력 검사에 사용했지만 개별 raw 응답 전체를 연구 증거로 보존한 것은 아니다.',
        '- 안전 종료는 해당 episode의 STOP 파일 또는 foreground Ctrl+C. 재시작은 원래 deadline/호출 한도 안에서만 수동 가능하며 STOP·기한 만료 episode는 거부한다. 과거/새 episode 통계를 자동 합산하지 않는다. 상세 명령은 운영 안내를 따른다.','',
        '## 6. 보존·선별 검증·Git','',
        f"- 원본 신호 **{original_signals}개**, quick_check={original_integrity}; 보호 입력 **{len(preservation)}개** 전후 SHA-256 동일. 원본 V4·구형 DB의 사전 일관 backup과 무결성을 확인했다. 기존 연구 label/성과를 다시 계산하지 않았다.",
        '- 선별58개 테스트 통과: 신규 관측/예산·scope/STOP·watchdog·완료 가격 경로·재시작·event 분모·종료 오류 요약과 기존 V4.1 영향 범위만 검사했다. 전체 회귀·과거 대규모 backtest·최적화 없음.',
        '- 원시 DB·LIVE 로그·backup은 data/scanner_v42_live 및 data/backups의 Git 제외 경로에 보존한다. Git에는 코드·문서·작은 요약/보존 증거만 포함한다. 신규 runtime 파일 hash는 요약 JSON에 남겼다.',
        '- 실제 매수/매도·가상자금 체결·API 키·Windows 종료·다른 프로젝트 중단 없음.','',
        '## 7. V4.3 우선순위','',
        '1. 지원 시장 사전 검사와 cohort 동결 증거를 표준화하고, 상장/거래지원 변경을 원본 연구 분모와 구분한다.',
        '2. 감독하 더 긴 연속 노출에서 신규 signal과60분 완전 사건을 확보한다. 실제 관측 공백·late candle·UNKNOWN과 시장별 분모를 함께 기록한다.',
        '3. 실제 탐지 시각의 가격·마지막 체결 시각·source arrival 증거를 보강해 종가 proxy와 전달 후 움직임을 구분한다.',
        '4. 실제 네트워크/차단·수동 process resume·디스크 증가를 별도 한도에서 확인한다. 이번 결과만으로 무인 운영을 승인하지 않는다.',
        '5. frozen range 관찰기가 상승 초기에 도달하는지 고정 event 정의로 검증한다. 방향/점수/threshold를 같은 자료에서 최적화하지 않는다.','']
    report=ROOT/'docs/scanner_v42_live_review_20261024.md'
    if report.exists():raise FileExistsError(report)
    report.write_text('\n'.join(lines).replace('自然 신호','자연 신호').replace(')。',').'),encoding='utf8')
    print(json.dumps(dict(verdict='INSUFFICIENT_DATA',new_signals=total_signals,total_http=result['total_http_attempts'],protected_inputs=len(preservation),report=str(report))))


if __name__=='__main__':main()
