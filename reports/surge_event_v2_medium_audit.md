# V2 중간 규모 데이터 검증

종목 40개 / KST 08-19 00:00 ~ 08-24 00:00

선정: 가격 상승률을 보지 않고 일별 분봉 관측률로 5일 구간과 40종목을 결정했습니다. 유동적인 종목에 치우친 품질 표본이며 시장 무작위 표본은 아닙니다.
매칭 조건과 이벤트 알고리즘은 변경하지 않았습니다. 전체 DB 조회는 일별 개수 집계뿐이며 이벤트 분석은 선정된 40종목에만 수행했습니다.

KRW-ARX, KRW-AVAX, KRW-CAP, KRW-CFG, KRW-CHIP, KRW-DATA, KRW-DOS, KRW-ENSO, KRW-ETC, KRW-EUL, KRW-FIL, KRW-GRVT, KRW-HBAR, KRW-HOLO, KRW-HOME, KRW-KAITO, KRW-LA, KRW-LINK, KRW-ME, KRW-MMT, KRW-NEAR, KRW-ONDO, KRW-ONG, KRW-ONT, KRW-PENGU, KRW-PIEVERSE, KRW-PROM, KRW-PUMP, KRW-RVN, KRW-SAHARA, KRW-SAND, KRW-SHIB, KRW-SUI, KRW-TAO, KRW-UNI, KRW-VIRTUAL, KRW-WLD, KRW-XLM, KRW-ZBT, KRW-ZRO

## 요약

| 유형 | 사건 | 주 매칭 | 주 % | 보조 매칭 | 보조 % |
|---|---|---|---|---|---|
| A | 43 | 5 | 11.628 | 9 | 20.930 |
| B | 10 | 0 | 0.000 | 0 | 0.000 |

고유 episode 37 / A+B 혼합 9 / A 여러 개 5
제약 없는 과거 최저 종가 정의와 t0가 다른 사건: 1
미래 창 일부 누락 사건 23 / 최초 목표 도달 이전 일부 누락 17. 누락 구간의 더 이른 목표 도달이나 최고가는 배제할 수 없습니다.
실제 데이터 미래 제거 검증 50개 통과

## 매칭 필터별 통과 수

후보 수는 사건×대조 후보 조합 수입니다. 순차 필터의 첫 탈락 원인으로 집계하므로 원인 비중은 필터 순서에 의존합니다. 모든 후보를 검사한 수이며, 실제 선택은 원본 V2의 순위와 재사용 규칙을 그대로 따릅니다. case_liquidity는 사건 자체의 과거 기준 거래대금입니다.

### A / primary

| 단계 | 통과 후보 | 해당 단계 탈락 |
|---|---|---|
| candidates | 1677 | 0 |
| case_liquidity | 429 | 1248 |
| not_reused | 426 | 3 |
| candidate_liquidity | 73 | 353 |
| liquidity_ratio | 65 | 8 |
| time_bounds | 65 | 0 |
| price_at_t0 | 64 | 1 |
| past_complete | 38 | 26 |
| future_complete | 36 | 2 |
| no_event_overlap | 18 | 18 |
| no_future_surge | 18 | 0 |
| no_control_overlap | 8 | 10 |
| selected | 5 | 0 |

미매칭 사건 사유: {"case_preperiod_liquidity_unavailable": 32, "no_eligible_liquidity_matched_control": 6}

### A / auxiliary

| 단계 | 통과 후보 | 해당 단계 탈락 |
|---|---|---|
| candidates | 5160 | 0 |
| case_liquidity | 1320 | 3840 |
| not_reused | 1316 | 4 |
| candidate_liquidity | 317 | 999 |
| liquidity_ratio | 220 | 97 |
| time_bounds | 220 | 0 |
| price_at_t0 | 217 | 3 |
| past_complete | 100 | 117 |
| future_complete | 82 | 18 |
| no_event_overlap | 65 | 17 |
| no_future_surge | 65 | 0 |
| no_control_overlap | 65 | 0 |
| selected | 9 | 0 |

미매칭 사건 사유: {"case_preperiod_liquidity_unavailable": 32, "no_eligible_liquidity_matched_control": 2}

### B / primary

| 단계 | 통과 후보 | 해당 단계 탈락 |
|---|---|---|
| candidates | 390 | 0 |
| case_liquidity | 0 | 390 |
| not_reused | 0 | 0 |
| candidate_liquidity | 0 | 0 |
| liquidity_ratio | 0 | 0 |
| time_bounds | 0 | 0 |
| price_at_t0 | 0 | 0 |
| past_complete | 0 | 0 |
| future_complete | 0 | 0 |
| no_event_overlap | 0 | 0 |
| no_future_surge | 0 | 0 |
| no_control_overlap | 0 | 0 |
| selected | 0 | 0 |

미매칭 사건 사유: {"case_preperiod_liquidity_unavailable": 10}

### B / auxiliary

| 단계 | 통과 후보 | 해당 단계 탈락 |
|---|---|---|
| candidates | 1200 | 0 |
| case_liquidity | 0 | 1200 |
| not_reused | 0 | 0 |
| candidate_liquidity | 0 | 0 |
| liquidity_ratio | 0 | 0 |
| time_bounds | 0 | 0 |
| price_at_t0 | 0 | 0 |
| past_complete | 0 | 0 |
| future_complete | 0 | 0 |
| no_event_overlap | 0 | 0 |
| no_future_surge | 0 | 0 |
| no_control_overlap | 0 | 0 |
| selected | 0 | 0 |

미매칭 사건 사유: {"case_preperiod_liquidity_unavailable": 10}

## 기존 8종목 0건 원인 재검증

저장된 사건을 그대로 사용해 매칭 진단만 수행했습니다. 기존 주/보조 대조군 ID와 모두 일치했습니다.

### 기존 A 주 대조군

| 단계 | 통과 | 탈락 |
|---|---|---|
| candidates | 175 | 0 |
| case_liquidity | 91 | 84 |
| not_reused | 91 | 0 |
| candidate_liquidity | 12 | 79 |
| liquidity_ratio | 3 | 9 |
| time_bounds | 3 | 0 |
| price_at_t0 | 3 | 0 |
| past_complete | 2 | 1 |
| future_complete | 2 | 0 |
| no_event_overlap | 0 | 2 |
| no_future_surge | 0 | 0 |
| no_control_overlap | 0 | 0 |
| selected | 0 | 0 |
### 기존 B 주 대조군

| 단계 | 통과 | 탈락 |
|---|---|---|
| candidates | 56 | 0 |
| case_liquidity | 14 | 42 |
| not_reused | 14 | 0 |
| candidate_liquidity | 1 | 13 |
| liquidity_ratio | 0 | 1 |
| time_bounds | 0 | 0 |
| price_at_t0 | 0 | 0 |
| past_complete | 0 | 0 |
| future_complete | 0 | 0 |
| no_event_overlap | 0 | 0 |
| no_future_surge | 0 | 0 |
| no_control_overlap | 0 | 0 |
| selected | 0 | 0 |
## 모든 episode

상승폭은 episode의 첫 t0 가격 대비 병합 구간의 관측 최고가입니다. 구간 중첩의 전이적 연결이므로 여러 번의 상승·하락을 한 episode로 합칠 수 있습니다.

A는 60분 평가 창 종료 후 5% 되돌림이 확인되면 다시 생성됩니다. B의 360분 창 안에 이 A 사건들이 여러 개 들어갈 수 있어 동일 episode에 A가 여러 건 포함됩니다. 연결된 평가 창은 실제 가격 흐름의 자연스러운 구분을 보장하지 않습니다.

| episode_id | 종목 | A | B | 시작 KST | 종료 KST | 상승폭 % |
|---|---|---|---|---|---|---|
| e98639d4528fde707fe5 | KRW-CHIP | 1 | 0 | 08-20 19:53 | 08-20 20:53 | 10.909 |
| 0e2d9c054d00e338372d | KRW-ONG | 2 | 1 | 08-20 21:19 | 08-21 03:19 | 43.032 |
| 9e6d70f358f13ef539bd | KRW-ONT | 1 | 1 | 08-21 00:32 | 08-21 06:32 | 36.788 |
| 79c76b4be3d74e1d1270 | KRW-ONT | 2 | 1 | 08-21 08:12 | 08-21 14:12 | 21.605 |
| 70fae5fea685f99ed2aa | KRW-ONG | 4 | 1 | 08-21 08:22 | 08-21 14:49 | 52.152 |
| a00a953572828ee1da02 | KRW-PROM | 1 | 0 | 08-21 15:31 | 08-21 16:31 | 10.340 |
| 53fabceceb515a9bd1ff | KRW-PIEVERSE | 2 | 1 | 08-21 16:32 | 08-21 22:32 | 23.767 |
| dc50d98d259637cd1ff9 | KRW-ONG | 1 | 0 | 08-21 17:34 | 08-21 18:34 | 17.117 |
| f4f3f9bdc8c088a41a16 | KRW-CAP | 1 | 0 | 08-21 17:46 | 08-21 18:46 | 10.022 |
| 01df31359396db18313b | KRW-PROM | 1 | 1 | 08-21 20:35 | 08-22 02:35 | 24.037 |
| ddc0bd97182b9ba27e15 | KRW-RVN | 1 | 0 | 08-22 09:59 | 08-22 10:59 | 12.778 |
| 4739ce7ec3b0425aaf63 | KRW-DOS | 1 | 0 | 08-22 14:11 | 08-22 15:11 | 12.759 |
| 52f33e1f9898cb427d01 | KRW-MMT | 1 | 0 | 08-22 14:11 | 08-22 15:11 | 11.842 |
| 12c596c7e10d98e2a05a | KRW-ONG | 1 | 0 | 08-22 14:11 | 08-22 15:11 | 16.000 |
| 77fbd0d139ac6c95463c | KRW-PUMP | 1 | 1 | 08-22 14:11 | 08-22 20:11 | 32.389 |
| 24164e37b7a076bef80c | KRW-SUI | 1 | 0 | 08-22 14:11 | 08-22 15:11 | 10.415 |
| 0c0ee4322b595d185dfe | KRW-WLD | 1 | 0 | 08-22 14:11 | 08-22 15:11 | 12.016 |
| 23f6410fb085fee372e7 | KRW-ARX | 0 | 1 | 08-22 14:12 | 08-22 20:12 | 20.370 |
| 1c0ce376da6957e282f9 | KRW-CFG | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 10.440 |
| c8b4317329197d1f9972 | KRW-ENSO | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 15.132 |
| a8c3af7259968196df9a | KRW-ETC | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 10.145 |
| 760a1f560d13398d8350 | KRW-EUL | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 14.969 |
| 4f51863a570e67a25a2e | KRW-GRVT | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 12.577 |
| efb7af91b5194ab0b31e | KRW-HOLO | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 10.048 |
| 61386e5b25c8aeec9f5c | KRW-KAITO | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 11.790 |
| bd802e77ed56bc6ca5f4 | KRW-LA | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 19.080 |
| 169a82d0ee2d7f71ef77 | KRW-ME | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 10.613 |
| 9a41ff17e45fb42320a4 | KRW-NEAR | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 13.777 |
| 61f4772a67eb61590137 | KRW-ONDO | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 14.526 |
| fcf1a682d510f0d37926 | KRW-PENGU | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 15.238 |
| 07057ce5ea662c656cc1 | KRW-PROM | 1 | 1 | 08-22 14:12 | 08-22 20:12 | 31.142 |
| 8b265dd15a2db95c1fdd | KRW-RVN | 2 | 1 | 08-22 14:12 | 08-22 20:12 | 30.508 |
| b0be523135740d352c65 | KRW-UNI | 1 | 0 | 08-22 14:12 | 08-22 15:12 | 11.133 |
| 228b3d17a27fb9d80be1 | KRW-EUL | 1 | 0 | 08-23 09:14 | 08-23 10:14 | 17.958 |
| 92b3c78e87e6d05dbc07 | KRW-ONT | 1 | 0 | 08-23 12:16 | 08-23 13:16 | 16.465 |
| f866253b6b125f316c21 | KRW-PUMP | 1 | 0 | 08-23 15:14 | 08-23 16:14 | 11.077 |
| 0d886592d9cb24b4f67f | KRW-PROM | 1 | 0 | 08-23 21:42 | 08-23 22:42 | 19.293 |

## 대표 사례 10개

종목 다양성을 우선하고 다중 A/긴 episode를 포함한 진단용 사례입니다. 각 episode의 첫 event를 대표로 사용합니다. 모든 시각은 KST, 목표 도달은 관측 분봉 고가 기준입니다.

### 1. KRW-ONG / A / 70fae5fea685f99ed2aa

t0 08-21 08:22, 가격 99.9; 목표 08-21 09:00, 고가 110.0; 최대 상승 16.116%; 도달 38.0~39.0분.
직전 120분 관측 최저가 99.3, 최저 종가 99.9, t0 1분 전 종가 100.0.

t0 이후 평가 창 최저가 수익률 -0.400%, 종료 종가 116.000, 종료 수익률 16.116%. 구간 관측률 1.000.

| t0 상대 분 | KST | 확정 종가 | t0 대비 % |
|---|---|---|---|
| -120 | 08-21 06:22 | 114.000 | 14.114 |
| -60 | 08-21 07:22 | 109.000 | 9.109 |
| -30 | 08-21 07:52 | 108.000 | 8.108 |
| -15 | 08-21 08:07 | 104.000 | 4.104 |
| -5 | 08-21 08:17 | 100.000 | 0.100 |
| 0 | 08-21 08:22 | 99.900 | 0.000 |
| 5 | 08-21 08:27 | 101.000 | 1.101 |
| 15 | 08-21 08:37 | 103.000 | 3.103 |
| 30 | 08-21 08:52 | 103.000 | 3.103 |
| 60 | 08-21 09:22 | 116.000 | 16.116 |
| 목표 도달 봉 고가 | 08-21 09:00 | 110.000 | 10.110 |

가격 흐름과 중복 event 목록:

| 유형 | t0 | 기준 가격 | 목표 도달 | 평가 종료 | 최대 상승 % |
|---|---|---|---|---|---|
| A | 08-21 08:22 | 99.900 | 08-21 09:00 | 08-21 09:22 | 16.116 |
| B | 08-21 08:22 | 99.900 | 08-21 09:23 | 08-21 14:22 | 52.152 |
| A | 08-21 09:56 | 125.000 | 08-21 10:27 | 08-21 10:56 | 14.400 |
| A | 08-21 11:05 | 128.000 | 08-21 11:35 | 08-21 12:05 | 16.406 |
| A | 08-21 13:49 | 130.000 | 08-21 14:02 | 08-21 14:49 | 10.769 |

사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):

| 분 전 | return_5m_pct | return_15m_pct | return_30m_pct | return_60m_pct | trade_value_ratio | trade_value_acceleration | ma5 | ma20 | range_30m_pct | distance_to_prior_high_pct | alt_relative_60m_pct | MA5>MA20 | 돌파 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | 0.000 | 0.000 | -0.870 | 1.786 | 0.815 | 0.686 | 113.400 | 113.750 | 2.679 | 2.632 | 0.989 | False | False |
| 60 | -1.802 | -0.909 | -0.909 | -4.386 | 0.763 | 1.621 | 109.600 | 109.500 | 2.778 | 5.505 | -4.485 | True | False |
| 30 | -0.917 | 0.000 | -0.917 | -1.818 | 0.967 | 0.846 | 108.400 | 108.850 | 3.738 | 2.778 | -2.029 | False | False |
| 15 | -2.804 | -3.704 | -3.704 | -5.455 | 3.708 | 4.562 | 105.400 | 107.300 | 7.843 | 6.731 | -5.528 | False | False |
| 5 | -0.990 | -6.542 | -8.257 | -9.910 | 3.537 | 0.840 | 100.580 | 103.395 | 9.438 | 11.000 | -10.279 | False | False |

### 2. KRW-ONT / B / 79c76b4be3d74e1d1270

t0 08-21 08:12, 가격 64.8; 목표 08-21 11:48, 고가 78.1; 최대 상승 21.605%; 도달 216.0~217.0분.
직전 120분 관측 최저가 65.2, 최저 종가 65.2, t0 1분 전 종가 65.2.

t0 이후 평가 창 최저가 수익률 -0.154%, 종료 종가 73.500, 종료 수익률 13.426%. 구간 관측률 1.000.

| t0 상대 분 | KST | 확정 종가 | t0 대비 % |
|---|---|---|---|
| -120 | 08-21 06:12 | 73.400 | 13.272 |
| -60 | 08-21 07:12 | 65.900 | 1.698 |
| -30 | 08-21 07:42 | 67.200 | 3.704 |
| -15 | 08-21 07:57 | 69.600 | 7.407 |
| -5 | 08-21 08:07 | 68.400 | 5.556 |
| 0 | 08-21 08:12 | 64.800 | 0.000 |
| 5 | 08-21 08:17 | 65.500 | 1.080 |
| 15 | 08-21 08:27 | 65.300 | 0.772 |
| 30 | 08-21 08:42 | 65.600 | 1.235 |
| 60 | 08-21 09:12 | 69.000 | 6.481 |
| 목표 도달 봉 고가 | 08-21 11:48 | 78.100 | 20.525 |

가격 흐름과 중복 event 목록:

| 유형 | t0 | 기준 가격 | 목표 도달 | 평가 종료 | 최대 상승 % |
|---|---|---|---|---|---|
| B | 08-21 08:12 | 64.800 | 08-21 11:48 | 08-21 14:12 | 21.605 |
| A | 08-21 08:40 | 65.300 | 08-21 09:25 | 08-21 09:40 | 15.314 |
| A | 08-21 11:05 | 70.900 | 08-21 11:48 | 08-21 12:05 | 10.155 |

사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):

| 분 전 | return_5m_pct | return_15m_pct | return_30m_pct | return_60m_pct | trade_value_ratio | trade_value_acceleration | ma5 | ma20 | range_30m_pct | distance_to_prior_high_pct | alt_relative_60m_pct | MA5>MA20 | 돌파 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | -2.133 | -3.801 | -2.133 | 15.773 | 0.332 | 0.219 | 73.660 | 74.930 | 9.695 | 7.902 | 15.773 | False | False |
| 60 | 0.304 | -2.515 | -4.215 | -10.218 | 0.438 | 0.024 | 65.920 | 67.000 | 6.126 | 12.747 | -10.297 | False | False |
| 30 | -0.444 | 0.299 | 1.973 | -2.326 | 0.456 | 1.369 | 67.400 | 67.370 | 4.421 | 3.125 | -2.384 | True | False |
| 15 | 0.578 | 3.571 | 3.881 | 2.959 | 1.198 | 0.533 | 69.180 | 68.360 | 4.328 | 0.431 | 2.568 | True | False |
| 5 | -1.299 | -1.156 | 1.333 | 4.110 | 0.725 | 0.845 | 68.440 | 68.990 | 4.018 | 2.193 | 4.110 | False | False |

### 3. KRW-PIEVERSE / B / 53fabceceb515a9bd1ff

t0 08-21 16:32, 가격 1338.0; 목표 08-21 21:15, 고가 1630.0; 최대 상승 23.767%; 도달 283.0~284.0분.
직전 120분 관측 최저가 1334.0, 최저 종가 1334.0, t0 1분 전 종가 None.

t0 이후 평가 창 최저가 수익률 0.299%, 종료 종가 1602.000, 종료 수익률 19.731%. 구간 관측률 0.878.

| t0 상대 분 | KST | 확정 종가 | t0 대비 % |
|---|---|---|---|
| -120 | 08-21 14:32 | NULL | NULL |
| -60 | 08-21 15:32 | 1352.000 | 1.046 |
| -30 | 08-21 16:02 | NULL | NULL |
| -15 | 08-21 16:17 | 1339.000 | 0.075 |
| -5 | 08-21 16:27 | NULL | NULL |
| 0 | 08-21 16:32 | 1338.000 | 0.000 |
| 5 | 08-21 16:37 | 1345.000 | 0.523 |
| 15 | 08-21 16:47 | NULL | NULL |
| 30 | 08-21 17:02 | 1355.000 | 1.271 |
| 60 | 08-21 17:32 | NULL | NULL |
| 목표 도달 봉 고가 | 08-21 21:15 | 1630.000 | 21.824 |

가격 흐름과 중복 event 목록:

| 유형 | t0 | 기준 가격 | 목표 도달 | 평가 종료 | 최대 상승 % |
|---|---|---|---|---|---|
| B | 08-21 16:32 | 1338.000 | 08-21 21:15 | 08-21 22:32 | 23.767 |
| A | 08-21 17:34 | 1347.000 | 08-21 18:30 | 08-21 18:34 | 12.992 |
| A | 08-21 20:22 | 1369.000 | 08-21 21:02 | 08-21 21:22 | 20.088 |

사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):

| 분 전 | return_5m_pct | return_15m_pct | return_30m_pct | return_60m_pct | trade_value_ratio | trade_value_acceleration | ma5 | ma20 | range_30m_pct | distance_to_prior_high_pct | alt_relative_60m_pct | MA5>MA20 | 돌파 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 60 | 0.520 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 30 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 15 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 5 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |

- 120분 전 NULL: return_5m_pct: missing exact close: 2026-08-21T05:32:00+00:00,2026-08-21T05:27:00+00:00; return_15m_pct: missing exact close: 2026-08-21T05:32:00+00:00,2026-08-21T05:17:00+00:00; return_30m_pct: missing exact close: 2026-08-21T05:32:00+00:00; return_60m_pct: missing exact close: 2026-08-21T05:32:00+00:00; trade_value_5m: 5..0m: 3/5 candles; prior_mean_trade_value_5m: 65..5m: 32/60 candles; trade_value_ratio: 5..0m: 3/5 candles; 65..5m: 32/60 candles; trade_value_change_pct: 5..0m: 3/5 candles; 10..5m: 0/5 candles; trade_value_acceleration: 5..0m: 3/5 candles; 10..5m: 0/5 candles; 15..10m: 1/5 candles; ma5: 5..0m: 3/5 candles; ma20: 20..0m: 6/20 candles; ma5_ma20_ratio: 5..0m: 3/5 candles; 20..0m: 6/20 candles; ma20_slope_5m_pct: 20..0m: 6/20 candles; 25..5m: 6/20 candles; range_30m_pct: 30..0m: 10/30 candles; range_change_pct: 30..0m: 10/30 candles; 60..30m: 20/30 candles; distance_to_prior_high_pct: 61..1m: 31/60 candles; missing current close; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

- 60분 전 NULL: return_15m_pct: missing exact close: 2026-08-21T06:17:00+00:00; return_30m_pct: missing exact close: 2026-08-21T06:02:00+00:00; return_60m_pct: missing exact close: 2026-08-21T05:32:00+00:00; trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 33/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 33/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; 10..5m: 2/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; 10..5m: 2/5 candles; 15..10m: 3/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 10/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 10/20 candles; ma20_slope_5m_pct: 20..0m: 10/20 candles; 25..5m: 9/20 candles; range_30m_pct: 30..0m: 15/30 candles; range_change_pct: 30..0m: 15/30 candles; 60..30m: 19/30 candles; distance_to_prior_high_pct: 61..1m: 33/60 candles; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

- 30분 전 NULL: return_5m_pct: missing exact close: 2026-08-21T07:02:00+00:00,2026-08-21T06:57:00+00:00; return_15m_pct: missing exact close: 2026-08-21T07:02:00+00:00,2026-08-21T06:47:00+00:00; return_30m_pct: missing exact close: 2026-08-21T07:02:00+00:00; return_60m_pct: missing exact close: 2026-08-21T07:02:00+00:00,2026-08-21T06:02:00+00:00; trade_value_5m: 5..0m: 1/5 candles; prior_mean_trade_value_5m: 65..5m: 23/60 candles; trade_value_ratio: 5..0m: 1/5 candles; 65..5m: 23/60 candles; trade_value_change_pct: 5..0m: 1/5 candles; 10..5m: 1/5 candles; trade_value_acceleration: 5..0m: 1/5 candles; 10..5m: 1/5 candles; 15..10m: 1/5 candles; ma5: 5..0m: 1/5 candles; ma20: 20..0m: 3/20 candles; ma5_ma20_ratio: 5..0m: 1/5 candles; 20..0m: 3/20 candles; ma20_slope_5m_pct: 20..0m: 3/20 candles; 25..5m: 3/20 candles; range_30m_pct: 30..0m: 6/30 candles; range_change_pct: 30..0m: 6/30 candles; 60..30m: 15/30 candles; distance_to_prior_high_pct: 61..1m: 21/60 candles; missing current close; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

- 15분 전 NULL: return_5m_pct: missing exact close: 2026-08-21T07:12:00+00:00; return_15m_pct: missing exact close: 2026-08-21T07:02:00+00:00; return_30m_pct: missing exact close: 2026-08-21T06:47:00+00:00; return_60m_pct: missing exact close: 2026-08-21T06:17:00+00:00; trade_value_5m: 5..0m: 2/5 candles; prior_mean_trade_value_5m: 65..5m: 20/60 candles; trade_value_ratio: 5..0m: 2/5 candles; 65..5m: 20/60 candles; trade_value_change_pct: 5..0m: 2/5 candles; 10..5m: 1/5 candles; trade_value_acceleration: 5..0m: 2/5 candles; 10..5m: 1/5 candles; 15..10m: 3/5 candles; ma5: 5..0m: 2/5 candles; ma20: 20..0m: 7/20 candles; ma5_ma20_ratio: 5..0m: 2/5 candles; 20..0m: 7/20 candles; ma20_slope_5m_pct: 20..0m: 7/20 candles; 25..5m: 6/20 candles; range_30m_pct: 30..0m: 9/30 candles; range_change_pct: 30..0m: 9/30 candles; 60..30m: 12/30 candles; distance_to_prior_high_pct: 61..1m: 20/60 candles; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

- 5분 전 NULL: return_5m_pct: missing exact close: 2026-08-21T07:27:00+00:00,2026-08-21T07:22:00+00:00; return_15m_pct: missing exact close: 2026-08-21T07:27:00+00:00,2026-08-21T07:12:00+00:00; return_30m_pct: missing exact close: 2026-08-21T07:27:00+00:00,2026-08-21T06:57:00+00:00; return_60m_pct: missing exact close: 2026-08-21T07:27:00+00:00; trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 20/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 20/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; 10..5m: 2/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; 10..5m: 2/5 candles; 15..10m: 2/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 9/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 9/20 candles; ma20_slope_5m_pct: 20..0m: 9/20 candles; 25..5m: 8/20 candles; range_30m_pct: 30..0m: 13/30 candles; range_change_pct: 30..0m: 13/30 candles; 60..30m: 9/30 candles; distance_to_prior_high_pct: 61..1m: 23/60 candles; missing current close; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

### 4. KRW-RVN / B / 8b265dd15a2db95c1fdd

t0 08-22 14:12, 가격 3.54; 목표 08-22 17:36, 고가 4.28; 최대 상승 30.508%; 도달 204.0~205.0분.
직전 120분 관측 최저가 3.58, 최저 종가 3.6, t0 1분 전 종가 3.6.

t0 이후 평가 창 최저가 수익률 0.282%, 종료 종가 3.980, 종료 수익률 12.429%. 구간 관측률 0.897.

| t0 상대 분 | KST | 확정 종가 | t0 대비 % |
|---|---|---|---|
| -120 | 08-22 12:12 | 3.780 | 6.780 |
| -60 | 08-22 13:12 | 3.740 | 5.650 |
| -30 | 08-22 13:42 | 3.800 | 7.345 |
| -15 | 08-22 13:57 | 3.800 | 7.345 |
| -5 | 08-22 14:07 | 3.750 | 5.932 |
| 0 | 08-22 14:12 | 3.540 | 0.000 |
| 5 | 08-22 14:17 | 3.630 | 2.542 |
| 15 | 08-22 14:27 | 3.610 | 1.977 |
| 30 | 08-22 14:42 | NULL | NULL |
| 60 | 08-22 15:12 | 3.730 | 5.367 |
| 목표 도달 봉 고가 | 08-22 17:36 | 4.280 | 20.904 |

가격 흐름과 중복 event 목록:

| 유형 | t0 | 기준 가격 | 목표 도달 | 평가 종료 | 최대 상승 % |
|---|---|---|---|---|---|
| B | 08-22 14:12 | 3.540 | 08-22 17:36 | 08-22 20:12 | 30.508 |
| A | 08-22 16:59 | 3.660 | 08-22 17:30 | 08-22 17:59 | 22.951 |
| A | 08-22 19:03 | 3.860 | 08-22 19:24 | 08-22 20:03 | 13.990 |

사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):

| 분 전 | return_5m_pct | return_15m_pct | return_30m_pct | return_60m_pct | trade_value_ratio | trade_value_acceleration | ma5 | ma20 | range_30m_pct | distance_to_prior_high_pct | alt_relative_60m_pct | MA5>MA20 | 돌파 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | -0.526 | -0.787 | -0.264 | -2.073 | NULL | 2.378 | 3.788 | NULL | NULL | NULL | -4.051 | NULL | NULL |
| 60 | -0.532 | 0.268 | -1.058 | -1.058 | NULL | NULL | NULL | NULL | NULL | NULL | -1.661 | NULL | NULL |
| 30 | 0.796 | NULL | 1.604 | 0.529 | NULL | NULL | 3.786 | NULL | NULL | NULL | -0.351 | NULL | NULL |
| 15 | 0.000 | 0.000 | NULL | 1.877 | NULL | NULL | 3.808 | NULL | NULL | NULL | 1.095 | NULL | NULL |
| 5 | -1.575 | -1.316 | -0.531 | -0.266 | NULL | 1.557 | 3.766 | 3.791 | NULL | NULL | -1.012 | False | NULL |

- 120분 전 NULL: prior_mean_trade_value_5m: 65..5m: 57/60 candles; trade_value_ratio: 65..5m: 57/60 candles; ma20: 20..0m: 18/20 candles; ma5_ma20_ratio: 20..0m: 18/20 candles; ma20_slope_5m_pct: 20..0m: 18/20 candles; 25..5m: 17/20 candles; range_30m_pct: 30..0m: 27/30 candles; range_change_pct: 30..0m: 27/30 candles; distance_to_prior_high_pct: 61..1m: 57/60 candles

- 60분 전 NULL: trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 59/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 59/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 19/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 19/20 candles; ma20_slope_5m_pct: 20..0m: 19/20 candles; 25..5m: 19/20 candles; range_30m_pct: 30..0m: 28/30 candles; range_change_pct: 30..0m: 28/30 candles; distance_to_prior_high_pct: 61..1m: 58/60 candles

- 30분 전 NULL: return_15m_pct: missing exact close: 2026-08-22T04:27:00+00:00; prior_mean_trade_value_5m: 65..5m: 53/60 candles; trade_value_ratio: 65..5m: 53/60 candles; trade_value_change_pct: 10..5m: 4/5 candles; trade_value_acceleration: 10..5m: 4/5 candles; 15..10m: 4/5 candles; ma20: 20..0m: 15/20 candles; ma5_ma20_ratio: 20..0m: 15/20 candles; ma20_slope_5m_pct: 20..0m: 15/20 candles; 25..5m: 15/20 candles; range_30m_pct: 30..0m: 25/30 candles; range_change_pct: 30..0m: 25/30 candles; 60..30m: 28/30 candles; distance_to_prior_high_pct: 61..1m: 53/60 candles

- 15분 전 NULL: return_30m_pct: missing exact close: 2026-08-22T04:27:00+00:00; prior_mean_trade_value_5m: 65..5m: 52/60 candles; trade_value_ratio: 65..5m: 52/60 candles; trade_value_acceleration: 15..10m: 3/5 candles; ma20: 20..0m: 18/20 candles; ma5_ma20_ratio: 20..0m: 18/20 candles; ma20_slope_5m_pct: 20..0m: 18/20 candles; 25..5m: 17/20 candles; range_30m_pct: 30..0m: 26/30 candles; range_change_pct: 30..0m: 26/30 candles; 60..30m: 26/30 candles; distance_to_prior_high_pct: 61..1m: 52/60 candles

- 5분 전 NULL: prior_mean_trade_value_5m: 65..5m: 52/60 candles; trade_value_ratio: 65..5m: 52/60 candles; ma20_slope_5m_pct: 25..5m: 18/20 candles; range_30m_pct: 30..0m: 28/30 candles; range_change_pct: 30..0m: 28/30 candles; 60..30m: 24/30 candles; distance_to_prior_high_pct: 61..1m: 52/60 candles

### 5. KRW-PROM / B / 01df31359396db18313b

t0 08-21 20:35, 가격 3245.0; 목표 08-22 01:39, 고가 3929.0; 최대 상승 24.037%; 도달 304.0~305.0분.
직전 120분 관측 최저가 3235.0, 최저 종가 3249.0, t0 1분 전 종가 3262.0.

t0 이후 평가 창 최저가 수익률 0.123%, 종료 종가 3725.000, 종료 수익률 14.792%. 구간 관측률 0.950.

| t0 상대 분 | KST | 확정 종가 | t0 대비 % |
|---|---|---|---|
| -120 | 08-21 18:35 | 3324.000 | 2.435 |
| -60 | 08-21 19:35 | 3305.000 | 1.849 |
| -30 | 08-21 20:05 | 3316.000 | 2.188 |
| -15 | 08-21 20:20 | NULL | NULL |
| -5 | 08-21 20:30 | 3285.000 | 1.233 |
| 0 | 08-21 20:35 | 3245.000 | 0.000 |
| 5 | 08-21 20:40 | 3262.000 | 0.524 |
| 15 | 08-21 20:50 | 3291.000 | 1.418 |
| 30 | 08-21 21:05 | NULL | NULL |
| 60 | 08-21 21:35 | 3345.000 | 3.082 |
| 목표 도달 봉 고가 | 08-22 01:39 | 3929.000 | 21.079 |

가격 흐름과 중복 event 목록:

| 유형 | t0 | 기준 가격 | 목표 도달 | 평가 종료 | 최대 상승 % |
|---|---|---|---|---|---|
| B | 08-21 20:35 | 3245.000 | 08-22 01:39 | 08-22 02:35 | 24.037 |
| A | 08-22 01:03 | 3560.000 | 08-22 01:39 | 08-22 02:03 | 13.062 |

사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):

| 분 전 | return_5m_pct | return_15m_pct | return_30m_pct | return_60m_pct | trade_value_ratio | trade_value_acceleration | ma5 | ma20 | range_30m_pct | distance_to_prior_high_pct | alt_relative_60m_pct | MA5>MA20 | 돌파 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | 1.341 | 1.095 | -0.746 | -0.539 | NULL | NULL | NULL | NULL | NULL | NULL | -0.345 | NULL | NULL |
| 60 | -0.030 | -1.812 | 1.318 | -0.572 | NULL | NULL | 3302.600 | NULL | NULL | NULL | -1.082 | NULL | NULL |
| 30 | NULL | -0.030 | 0.333 | 1.655 | NULL | NULL | NULL | NULL | NULL | NULL | 0.884 | NULL | NULL |
| 15 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 5 | 0.922 | -0.755 | NULL | -0.635 | NULL | NULL | 3284.000 | NULL | NULL | NULL | -0.821 | NULL | NULL |

- 120분 전 NULL: trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 57/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 57/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 19/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 19/20 candles; ma20_slope_5m_pct: 20..0m: 19/20 candles; 25..5m: 19/20 candles; range_30m_pct: 30..0m: 28/30 candles; range_change_pct: 30..0m: 28/30 candles; 60..30m: 29/30 candles; distance_to_prior_high_pct: 61..1m: 57/60 candles

- 60분 전 NULL: prior_mean_trade_value_5m: 65..5m: 55/60 candles; trade_value_ratio: 65..5m: 55/60 candles; trade_value_change_pct: 10..5m: 4/5 candles; trade_value_acceleration: 10..5m: 4/5 candles; 15..10m: 4/5 candles; ma20: 20..0m: 18/20 candles; ma5_ma20_ratio: 20..0m: 18/20 candles; ma20_slope_5m_pct: 20..0m: 18/20 candles; 25..5m: 17/20 candles; range_30m_pct: 30..0m: 27/30 candles; range_change_pct: 30..0m: 27/30 candles; 60..30m: 29/30 candles; distance_to_prior_high_pct: 61..1m: 56/60 candles

- 30분 전 NULL: return_5m_pct: missing exact close: 2026-08-21T11:00:00+00:00; trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 53/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 53/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; 10..5m: 3/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; 10..5m: 3/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 16/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 16/20 candles; ma20_slope_5m_pct: 20..0m: 16/20 candles; 25..5m: 16/20 candles; range_30m_pct: 30..0m: 25/30 candles; range_change_pct: 30..0m: 25/30 candles; 60..30m: 27/30 candles; distance_to_prior_high_pct: 61..1m: 52/60 candles

- 15분 전 NULL: return_5m_pct: missing exact close: 2026-08-21T11:20:00+00:00; return_15m_pct: missing exact close: 2026-08-21T11:20:00+00:00; return_30m_pct: missing exact close: 2026-08-21T11:20:00+00:00; return_60m_pct: missing exact close: 2026-08-21T11:20:00+00:00; trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 52/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 52/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; 10..5m: 4/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; 10..5m: 4/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 17/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 17/20 candles; ma20_slope_5m_pct: 20..0m: 17/20 candles; 25..5m: 16/20 candles; range_30m_pct: 30..0m: 25/30 candles; range_change_pct: 30..0m: 25/30 candles; 60..30m: 26/30 candles; distance_to_prior_high_pct: 61..1m: 52/60 candles; missing current close; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

- 5분 전 NULL: return_30m_pct: missing exact close: 2026-08-21T11:00:00+00:00; prior_mean_trade_value_5m: 65..5m: 52/60 candles; trade_value_ratio: 65..5m: 52/60 candles; trade_value_acceleration: 15..10m: 4/5 candles; ma20: 20..0m: 18/20 candles; ma5_ma20_ratio: 20..0m: 18/20 candles; ma20_slope_5m_pct: 20..0m: 18/20 candles; 25..5m: 18/20 candles; range_30m_pct: 30..0m: 27/30 candles; range_change_pct: 30..0m: 27/30 candles; 60..30m: 26/30 candles; distance_to_prior_high_pct: 61..1m: 53/60 candles

### 6. KRW-PUMP / A / 77fbd0d139ac6c95463c

t0 08-22 14:11, 가격 4.94; 목표 08-22 14:12, 고가 5.52; 최대 상승 21.660%; 도달 1.0~2.0분.
직전 120분 관측 최저가 5.74, 최저 종가 5.74, t0 1분 전 종가 5.74.

t0 이후 평가 창 최저가 수익률 -0.607%, 종료 종가 5.930, 종료 수익률 20.040%. 구간 관측률 1.000.

| t0 상대 분 | KST | 확정 종가 | t0 대비 % |
|---|---|---|---|
| -120 | 08-22 12:11 | 5.790 | 17.206 |
| -60 | 08-22 13:11 | 5.820 | 17.814 |
| -30 | 08-22 13:41 | 6.000 | 21.457 |
| -15 | 08-22 13:56 | 6.100 | 23.482 |
| -5 | 08-22 14:06 | 5.930 | 20.040 |
| 0 | 08-22 14:11 | 4.940 | 0.000 |
| 5 | 08-22 14:16 | 5.630 | 13.968 |
| 15 | 08-22 14:26 | 5.720 | 15.789 |
| 30 | 08-22 14:41 | 5.810 | 17.611 |
| 60 | 08-22 15:11 | 5.930 | 20.040 |
| 목표 도달 봉 고가 | 08-22 14:12 | 5.520 | 11.741 |

가격 흐름과 중복 event 목록:

| 유형 | t0 | 기준 가격 | 목표 도달 | 평가 종료 | 최대 상승 % |
|---|---|---|---|---|---|
| A | 08-22 14:11 | 4.940 | 08-22 14:12 | 08-22 15:11 | 21.660 |
| B | 08-22 14:11 | 4.940 | 08-22 14:29 | 08-22 20:11 | 32.389 |

사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):

| 분 전 | return_5m_pct | return_15m_pct | return_30m_pct | return_60m_pct | trade_value_ratio | trade_value_acceleration | ma5 | ma20 | range_30m_pct | distance_to_prior_high_pct | alt_relative_60m_pct | MA5>MA20 | 돌파 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | -1.195 | -1.026 | -0.344 | -1.363 | NULL | NULL | NULL | NULL | NULL | NULL | -3.652 | NULL | NULL |
| 60 | NULL | -2.676 | -1.188 | 0.518 | NULL | NULL | NULL | NULL | NULL | NULL | 0.080 | NULL | NULL |
| 30 | 1.523 | NULL | 3.093 | 1.868 | NULL | 0.883 | 5.964 | NULL | NULL | NULL | 1.409 | NULL | NULL |
| 15 | 0.826 | 1.667 | NULL | 2.007 | NULL | 11.691 | 6.064 | 6.017 | 4.811 | NULL | 1.244 | True | NULL |
| 5 | NULL | -1.983 | 0.338 | NULL | NULL | NULL | 5.942 | NULL | NULL | NULL | NULL | NULL | NULL |

- 120분 전 NULL: trade_value_5m: 5..0m: 3/5 candles; prior_mean_trade_value_5m: 65..5m: 54/60 candles; trade_value_ratio: 5..0m: 3/5 candles; 65..5m: 54/60 candles; trade_value_change_pct: 5..0m: 3/5 candles; 10..5m: 4/5 candles; trade_value_acceleration: 5..0m: 3/5 candles; 10..5m: 4/5 candles; 15..10m: 4/5 candles; ma5: 5..0m: 3/5 candles; ma20: 20..0m: 16/20 candles; ma5_ma20_ratio: 5..0m: 3/5 candles; 20..0m: 16/20 candles; ma20_slope_5m_pct: 20..0m: 16/20 candles; 25..5m: 17/20 candles; range_30m_pct: 30..0m: 25/30 candles; range_change_pct: 30..0m: 25/30 candles; 60..30m: 27/30 candles; distance_to_prior_high_pct: 61..1m: 52/60 candles

- 60분 전 NULL: return_5m_pct: missing exact close: 2026-08-22T04:06:00+00:00; trade_value_5m: 5..0m: 3/5 candles; prior_mean_trade_value_5m: 65..5m: 55/60 candles; trade_value_ratio: 5..0m: 3/5 candles; 65..5m: 55/60 candles; trade_value_change_pct: 5..0m: 3/5 candles; 10..5m: 4/5 candles; trade_value_acceleration: 5..0m: 3/5 candles; 10..5m: 4/5 candles; ma5: 5..0m: 3/5 candles; ma20: 20..0m: 17/20 candles; ma5_ma20_ratio: 5..0m: 3/5 candles; 20..0m: 17/20 candles; ma20_slope_5m_pct: 20..0m: 17/20 candles; 25..5m: 19/20 candles; range_30m_pct: 30..0m: 27/30 candles; range_change_pct: 30..0m: 27/30 candles; 60..30m: 28/30 candles; distance_to_prior_high_pct: 61..1m: 55/60 candles

- 30분 전 NULL: return_15m_pct: missing exact close: 2026-08-22T04:26:00+00:00; prior_mean_trade_value_5m: 65..5m: 50/60 candles; trade_value_ratio: 65..5m: 50/60 candles; ma20: 20..0m: 17/20 candles; ma5_ma20_ratio: 20..0m: 17/20 candles; ma20_slope_5m_pct: 20..0m: 17/20 candles; 25..5m: 15/20 candles; range_30m_pct: 30..0m: 23/30 candles; range_change_pct: 30..0m: 23/30 candles; 60..30m: 27/30 candles; distance_to_prior_high_pct: 61..1m: 50/60 candles

- 15분 전 NULL: return_30m_pct: missing exact close: 2026-08-22T04:26:00+00:00; prior_mean_trade_value_5m: 65..5m: 50/60 candles; trade_value_ratio: 65..5m: 50/60 candles; range_change_pct: 60..30m: 20/30 candles; distance_to_prior_high_pct: 61..1m: 50/60 candles

- 5분 전 NULL: return_5m_pct: missing exact close: 2026-08-22T05:01:00+00:00; return_60m_pct: missing exact close: 2026-08-22T04:06:00+00:00; prior_mean_trade_value_5m: 65..5m: 49/60 candles; trade_value_ratio: 65..5m: 49/60 candles; trade_value_change_pct: 10..5m: 4/5 candles; trade_value_acceleration: 10..5m: 4/5 candles; ma20: 20..0m: 19/20 candles; ma5_ma20_ratio: 20..0m: 19/20 candles; ma20_slope_5m_pct: 20..0m: 19/20 candles; 25..5m: 19/20 candles; range_30m_pct: 30..0m: 29/30 candles; range_change_pct: 30..0m: 29/30 candles; 60..30m: 21/30 candles; distance_to_prior_high_pct: 61..1m: 49/60 candles; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

### 7. KRW-ARX / B / 23f6410fb085fee372e7

t0 08-22 14:12, 가격 162.0; 목표 08-22 17:12, 고가 195.0; 최대 상승 20.370%; 도달 180.0~181.0분.
직전 120분 관측 최저가 164.0, 최저 종가 164.0, t0 1분 전 종가 164.0.

t0 이후 평가 창 최저가 수익률 0.617%, 종료 종가 NULL, 종료 수익률 NULL%. 구간 관측률 0.814.

| t0 상대 분 | KST | 확정 종가 | t0 대비 % |
|---|---|---|---|
| -120 | 08-22 12:12 | NULL | NULL |
| -60 | 08-22 13:12 | 179.000 | 10.494 |
| -30 | 08-22 13:42 | NULL | NULL |
| -15 | 08-22 13:57 | 184.000 | 13.580 |
| -5 | 08-22 14:07 | 189.000 | 16.667 |
| 0 | 08-22 14:12 | 162.000 | 0.000 |
| 5 | 08-22 14:17 | 170.000 | 4.938 |
| 15 | 08-22 14:27 | 176.000 | 8.642 |
| 30 | 08-22 14:42 | 172.000 | 6.173 |
| 60 | 08-22 15:12 | NULL | NULL |
| 목표 도달 봉 고가 | 08-22 17:12 | 195.000 | 20.370 |

가격 흐름과 중복 event 목록:

| 유형 | t0 | 기준 가격 | 목표 도달 | 평가 종료 | 최대 상승 % |
|---|---|---|---|---|---|
| B | 08-22 14:12 | 162.000 | 08-22 17:12 | 08-22 20:12 | 20.370 |

사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):

| 분 전 | return_5m_pct | return_15m_pct | return_30m_pct | return_60m_pct | trade_value_ratio | trade_value_acceleration | ma5 | ma20 | range_30m_pct | distance_to_prior_high_pct | alt_relative_60m_pct | MA5>MA20 | 돌파 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 60 | NULL | NULL | NULL | NULL | NULL | NULL | 180.000 | NULL | NULL | NULL | NULL | NULL | NULL |
| 30 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 15 | 0.546 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 5 | 2.717 | 3.279 | 5.000 | NULL | NULL | NULL | 187.800 | NULL | NULL | NULL | NULL | NULL | NULL |

- 120분 전 NULL: return_5m_pct: missing exact close: 2026-08-22T03:12:00+00:00; return_15m_pct: missing exact close: 2026-08-22T03:12:00+00:00,2026-08-22T02:57:00+00:00; return_30m_pct: missing exact close: 2026-08-22T03:12:00+00:00; return_60m_pct: missing exact close: 2026-08-22T03:12:00+00:00,2026-08-22T02:12:00+00:00; trade_value_5m: 5..0m: 3/5 candles; prior_mean_trade_value_5m: 65..5m: 37/60 candles; trade_value_ratio: 5..0m: 3/5 candles; 65..5m: 37/60 candles; trade_value_change_pct: 5..0m: 3/5 candles; 10..5m: 3/5 candles; trade_value_acceleration: 5..0m: 3/5 candles; 10..5m: 3/5 candles; ma5: 5..0m: 3/5 candles; ma20: 20..0m: 13/20 candles; ma5_ma20_ratio: 5..0m: 3/5 candles; 20..0m: 13/20 candles; ma20_slope_5m_pct: 20..0m: 13/20 candles; 25..5m: 11/20 candles; range_30m_pct: 30..0m: 19/30 candles; range_change_pct: 30..0m: 19/30 candles; 60..30m: 18/30 candles; distance_to_prior_high_pct: 61..1m: 37/60 candles; missing current close; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

- 60분 전 NULL: return_5m_pct: missing exact close: 2026-08-22T04:07:00+00:00; return_15m_pct: missing exact close: 2026-08-22T03:57:00+00:00; return_30m_pct: missing exact close: 2026-08-22T03:42:00+00:00; return_60m_pct: missing exact close: 2026-08-22T03:12:00+00:00; prior_mean_trade_value_5m: 65..5m: 43/60 candles; trade_value_ratio: 65..5m: 43/60 candles; trade_value_change_pct: 10..5m: 4/5 candles; trade_value_acceleration: 10..5m: 4/5 candles; ma20: 20..0m: 16/20 candles; ma5_ma20_ratio: 20..0m: 16/20 candles; ma20_slope_5m_pct: 20..0m: 16/20 candles; 25..5m: 15/20 candles; range_30m_pct: 30..0m: 24/30 candles; range_change_pct: 30..0m: 24/30 candles; 60..30m: 21/30 candles; distance_to_prior_high_pct: 61..1m: 44/60 candles; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

- 30분 전 NULL: return_5m_pct: missing exact close: 2026-08-22T04:42:00+00:00; return_15m_pct: missing exact close: 2026-08-22T04:42:00+00:00,2026-08-22T04:27:00+00:00; return_30m_pct: missing exact close: 2026-08-22T04:42:00+00:00; return_60m_pct: missing exact close: 2026-08-22T04:42:00+00:00,2026-08-22T03:42:00+00:00; trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 43/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 43/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; 10..5m: 2/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; 10..5m: 2/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 14/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 14/20 candles; ma20_slope_5m_pct: 20..0m: 14/20 candles; 25..5m: 12/20 candles; range_30m_pct: 30..0m: 21/30 candles; range_change_pct: 30..0m: 21/30 candles; 60..30m: 24/30 candles; distance_to_prior_high_pct: 61..1m: 45/60 candles; missing current close; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

- 15분 전 NULL: return_15m_pct: missing exact close: 2026-08-22T04:42:00+00:00; return_30m_pct: missing exact close: 2026-08-22T04:27:00+00:00; return_60m_pct: missing exact close: 2026-08-22T03:57:00+00:00; trade_value_5m: 5..0m: 3/5 candles; prior_mean_trade_value_5m: 65..5m: 46/60 candles; trade_value_ratio: 5..0m: 3/5 candles; 65..5m: 46/60 candles; trade_value_change_pct: 5..0m: 3/5 candles; 10..5m: 4/5 candles; trade_value_acceleration: 5..0m: 3/5 candles; 10..5m: 4/5 candles; ma5: 5..0m: 3/5 candles; ma20: 20..0m: 16/20 candles; ma5_ma20_ratio: 5..0m: 3/5 candles; 20..0m: 16/20 candles; ma20_slope_5m_pct: 20..0m: 16/20 candles; 25..5m: 15/20 candles; range_30m_pct: 30..0m: 23/30 candles; range_change_pct: 30..0m: 23/30 candles; 60..30m: 24/30 candles; distance_to_prior_high_pct: 61..1m: 46/60 candles; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

- 5분 전 NULL: return_60m_pct: missing exact close: 2026-08-22T04:07:00+00:00; prior_mean_trade_value_5m: 65..5m: 47/60 candles; trade_value_ratio: 65..5m: 47/60 candles; trade_value_acceleration: 15..10m: 3/5 candles; ma20: 20..0m: 17/20 candles; ma5_ma20_ratio: 20..0m: 17/20 candles; ma20_slope_5m_pct: 20..0m: 17/20 candles; 25..5m: 17/20 candles; range_30m_pct: 30..0m: 26/30 candles; range_change_pct: 30..0m: 26/30 candles; 60..30m: 22/30 candles; distance_to_prior_high_pct: 61..1m: 47/60 candles; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

### 8. KRW-CHIP / A / e98639d4528fde707fe5

t0 08-20 19:53, 가격 38.5; 목표 08-20 20:45, 고가 42.4; 최대 상승 10.909%; 도달 52.0~53.0분.
직전 120분 관측 최저가 38.2, 최저 종가 38.3, t0 1분 전 종가 None.

t0 이후 평가 창 최저가 수익률 0.000%, 종료 종가 42.700, 종료 수익률 10.909%. 구간 관측률 0.933.

| t0 상대 분 | KST | 확정 종가 | t0 대비 % |
|---|---|---|---|
| -120 | 08-20 17:53 | 39.200 | 1.818 |
| -60 | 08-20 18:53 | 39.100 | 1.558 |
| -30 | 08-20 19:23 | 38.400 | -0.260 |
| -15 | 08-20 19:38 | NULL | NULL |
| -5 | 08-20 19:48 | 38.500 | 0.000 |
| 0 | 08-20 19:53 | 38.500 | 0.000 |
| 5 | 08-20 19:58 | 39.400 | 2.338 |
| 15 | 08-20 20:08 | 40.800 | 5.974 |
| 30 | 08-20 20:23 | NULL | NULL |
| 60 | 08-20 20:53 | 42.700 | 10.909 |
| 목표 도달 봉 고가 | 08-20 20:45 | 42.400 | 10.130 |

가격 흐름과 중복 event 목록:

| 유형 | t0 | 기준 가격 | 목표 도달 | 평가 종료 | 최대 상승 % |
|---|---|---|---|---|---|
| A | 08-20 19:53 | 38.500 | 08-20 20:45 | 08-20 20:53 | 10.909 |

사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):

| 분 전 | return_5m_pct | return_15m_pct | return_30m_pct | return_60m_pct | trade_value_ratio | trade_value_acceleration | ma5 | ma20 | range_30m_pct | distance_to_prior_high_pct | alt_relative_60m_pct | MA5>MA20 | 돌파 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | -0.759 | -2.730 | -2.488 | -1.754 | NULL | NULL | 39.300 | NULL | NULL | NULL | -2.859 | NULL | NULL |
| 60 | -1.263 | -0.761 | -1.263 | -0.255 | NULL | NULL | NULL | NULL | NULL | NULL | -0.094 | NULL | NULL |
| 30 | NULL | 0.261 | -1.790 | -3.030 | NULL | NULL | NULL | NULL | NULL | NULL | -3.154 | NULL | NULL |
| 15 | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL | NULL |
| 5 | 0.000 | NULL | NULL | -2.778 | NULL | NULL | NULL | NULL | NULL | NULL | -2.890 | NULL | NULL |

- 120분 전 NULL: prior_mean_trade_value_5m: 65..5m: 52/60 candles; trade_value_ratio: 65..5m: 52/60 candles; trade_value_acceleration: 15..10m: 4/5 candles; ma20: 20..0m: 19/20 candles; ma5_ma20_ratio: 20..0m: 19/20 candles; ma20_slope_5m_pct: 20..0m: 19/20 candles; 25..5m: 17/20 candles; range_30m_pct: 30..0m: 27/30 candles; range_change_pct: 30..0m: 27/30 candles; 60..30m: 25/30 candles; distance_to_prior_high_pct: 61..1m: 52/60 candles

- 60분 전 NULL: trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 51/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 51/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; 10..5m: 4/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; 10..5m: 4/5 candles; 15..10m: 4/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 17/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 17/20 candles; ma20_slope_5m_pct: 20..0m: 17/20 candles; 25..5m: 15/20 candles; range_30m_pct: 30..0m: 23/30 candles; range_change_pct: 30..0m: 23/30 candles; 60..30m: 27/30 candles; distance_to_prior_high_pct: 61..1m: 50/60 candles

- 30분 전 NULL: return_5m_pct: missing exact close: 2026-08-20T10:18:00+00:00; trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 49/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 49/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; 10..5m: 3/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; 10..5m: 3/5 candles; 15..10m: 3/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 15/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 15/20 candles; ma20_slope_5m_pct: 20..0m: 15/20 candles; 25..5m: 16/20 candles; range_30m_pct: 30..0m: 25/30 candles; range_change_pct: 30..0m: 25/30 candles; 60..30m: 23/30 candles; distance_to_prior_high_pct: 61..1m: 48/60 candles

- 15분 전 NULL: return_5m_pct: missing exact close: 2026-08-20T10:38:00+00:00,2026-08-20T10:33:00+00:00; return_15m_pct: missing exact close: 2026-08-20T10:38:00+00:00; return_30m_pct: missing exact close: 2026-08-20T10:38:00+00:00; return_60m_pct: missing exact close: 2026-08-20T10:38:00+00:00; trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 47/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 47/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; 10..5m: 3/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; 10..5m: 3/5 candles; 15..10m: 2/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 13/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 13/20 candles; ma20_slope_5m_pct: 20..0m: 13/20 candles; 25..5m: 12/20 candles; range_30m_pct: 30..0m: 19/30 candles; range_change_pct: 30..0m: 19/30 candles; 60..30m: 27/30 candles; distance_to_prior_high_pct: 61..1m: 47/60 candles; missing current close; alt_relative_60m_pct: own 60m return missing; btc_relative_60m_pct: own 60m return missing

- 5분 전 NULL: return_15m_pct: missing exact close: 2026-08-20T10:33:00+00:00; return_30m_pct: missing exact close: 2026-08-20T10:18:00+00:00; trade_value_5m: 5..0m: 3/5 candles; prior_mean_trade_value_5m: 65..5m: 44/60 candles; trade_value_ratio: 5..0m: 3/5 candles; 65..5m: 44/60 candles; trade_value_change_pct: 5..0m: 3/5 candles; 10..5m: 2/5 candles; trade_value_acceleration: 5..0m: 3/5 candles; 10..5m: 2/5 candles; 15..10m: 4/5 candles; ma5: 5..0m: 3/5 candles; ma20: 20..0m: 12/20 candles; ma5_ma20_ratio: 5..0m: 3/5 candles; 20..0m: 12/20 candles; ma20_slope_5m_pct: 20..0m: 12/20 candles; 25..5m: 11/20 candles; range_30m_pct: 30..0m: 18/30 candles; range_change_pct: 30..0m: 18/30 candles; 60..30m: 25/30 candles; distance_to_prior_high_pct: 61..1m: 43/60 candles

### 9. KRW-CAP / A / f4f3f9bdc8c088a41a16

t0 08-21 17:46, 가격 91.8; 목표 08-21 18:40, 고가 101.0; 최대 상승 10.022%; 도달 54.0~55.0분.
직전 120분 관측 최저가 91.2, 최저 종가 91.3, t0 1분 전 종가 92.0.

t0 이후 평가 창 최저가 수익률 0.218%, 종료 종가 98.100, 종료 수익률 6.863%. 구간 관측률 1.000.

| t0 상대 분 | KST | 확정 종가 | t0 대비 % |
|---|---|---|---|
| -120 | 08-21 15:46 | 91.900 | 0.109 |
| -60 | 08-21 16:46 | 91.600 | -0.218 |
| -30 | 08-21 17:16 | 92.200 | 0.436 |
| -15 | 08-21 17:31 | 92.500 | 0.763 |
| -5 | 08-21 17:41 | 92.200 | 0.436 |
| 0 | 08-21 17:46 | 91.800 | 0.000 |
| 5 | 08-21 17:51 | 94.300 | 2.723 |
| 15 | 08-21 18:01 | 95.000 | 3.486 |
| 30 | 08-21 18:16 | 95.800 | 4.357 |
| 60 | 08-21 18:46 | 98.100 | 6.863 |
| 목표 도달 봉 고가 | 08-21 18:40 | 101.000 | 10.022 |

가격 흐름과 중복 event 목록:

| 유형 | t0 | 기준 가격 | 목표 도달 | 평가 종료 | 최대 상승 % |
|---|---|---|---|---|---|
| A | 08-21 17:46 | 91.800 | 08-21 18:40 | 08-21 18:46 | 10.022 |

사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):

| 분 전 | return_5m_pct | return_15m_pct | return_30m_pct | return_60m_pct | trade_value_ratio | trade_value_acceleration | ma5 | ma20 | range_30m_pct | distance_to_prior_high_pct | alt_relative_60m_pct | MA5>MA20 | 돌파 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | 0.657 | 0.768 | 1.659 | 1.659 | NULL | NULL | 91.560 | NULL | NULL | NULL | 1.330 | NULL | NULL |
| 60 | -0.326 | 0.109 | -0.218 | -0.326 | NULL | NULL | NULL | NULL | NULL | NULL | -2.272 | NULL | NULL |
| 30 | -0.753 | -0.860 | 0.655 | 0.436 | NULL | NULL | NULL | NULL | NULL | NULL | -0.552 | NULL | NULL |
| 15 | -0.108 | 0.325 | -0.538 | 1.093 | NULL | 3.852 | 92.560 | NULL | NULL | NULL | -0.178 | NULL | NULL |
| 5 | -0.432 | -0.432 | -0.753 | 0.326 | NULL | 5.026 | 92.460 | 92.585 | NULL | NULL | -0.893 | False | NULL |

- 120분 전 NULL: prior_mean_trade_value_5m: 65..5m: 57/60 candles; trade_value_ratio: 65..5m: 57/60 candles; trade_value_acceleration: 15..10m: 4/5 candles; ma20: 20..0m: 19/20 candles; ma5_ma20_ratio: 20..0m: 19/20 candles; ma20_slope_5m_pct: 20..0m: 19/20 candles; 25..5m: 19/20 candles; range_30m_pct: 30..0m: 29/30 candles; range_change_pct: 30..0m: 29/30 candles; 60..30m: 28/30 candles; distance_to_prior_high_pct: 61..1m: 57/60 candles

- 60분 전 NULL: trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 54/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 54/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 18/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 18/20 candles; ma20_slope_5m_pct: 20..0m: 18/20 candles; 25..5m: 19/20 candles; range_30m_pct: 30..0m: 28/30 candles; range_change_pct: 30..0m: 28/30 candles; 60..30m: 25/30 candles; distance_to_prior_high_pct: 61..1m: 53/60 candles

- 30분 전 NULL: trade_value_5m: 5..0m: 4/5 candles; prior_mean_trade_value_5m: 65..5m: 58/60 candles; trade_value_ratio: 5..0m: 4/5 candles; 65..5m: 58/60 candles; trade_value_change_pct: 5..0m: 4/5 candles; trade_value_acceleration: 5..0m: 4/5 candles; ma5: 5..0m: 4/5 candles; ma20: 20..0m: 19/20 candles; ma5_ma20_ratio: 5..0m: 4/5 candles; 20..0m: 19/20 candles; ma20_slope_5m_pct: 20..0m: 19/20 candles; range_30m_pct: 30..0m: 29/30 candles; range_change_pct: 30..0m: 29/30 candles; 60..30m: 28/30 candles; distance_to_prior_high_pct: 61..1m: 57/60 candles

- 15분 전 NULL: prior_mean_trade_value_5m: 65..5m: 57/60 candles; trade_value_ratio: 65..5m: 57/60 candles; ma20: 20..0m: 19/20 candles; ma5_ma20_ratio: 20..0m: 19/20 candles; ma20_slope_5m_pct: 20..0m: 19/20 candles; 25..5m: 19/20 candles; range_30m_pct: 30..0m: 29/30 candles; range_change_pct: 30..0m: 29/30 candles; 60..30m: 29/30 candles; distance_to_prior_high_pct: 61..1m: 58/60 candles

- 5분 전 NULL: prior_mean_trade_value_5m: 65..5m: 58/60 candles; trade_value_ratio: 65..5m: 58/60 candles; range_30m_pct: 30..0m: 29/30 candles; range_change_pct: 30..0m: 29/30 candles; 60..30m: 29/30 candles; distance_to_prior_high_pct: 61..1m: 58/60 candles

### 10. KRW-DOS / A / 4739ce7ec3b0425aaf63

t0 08-22 14:11, 가격 290.0; 목표 08-22 14:11, 고가 322.0; 최대 상승 12.759%; 도달 0.0~1.0분.
직전 120분 관측 최저가 325.0, 최저 종가 326.0, t0 1분 전 종가 326.0.

t0 이후 평가 창 최저가 수익률 -1.034%, 종료 종가 320.000, 종료 수익률 10.345%. 구간 관측률 1.000.

| t0 상대 분 | KST | 확정 종가 | t0 대비 % |
|---|---|---|---|
| -120 | 08-22 12:11 | 360.000 | 24.138 |
| -60 | 08-22 13:11 | 359.000 | 23.793 |
| -30 | 08-22 13:41 | 351.000 | 21.034 |
| -15 | 08-22 13:56 | 353.000 | 21.724 |
| -5 | 08-22 14:06 | 350.000 | 20.690 |
| 0 | 08-22 14:11 | 290.000 | 0.000 |
| 5 | 08-22 14:16 | 322.000 | 11.034 |
| 15 | 08-22 14:26 | 324.000 | 11.724 |
| 30 | 08-22 14:41 | 320.000 | 10.345 |
| 60 | 08-22 15:11 | 320.000 | 10.345 |
| 목표 도달 봉 고가 | 08-22 14:11 | 322.000 | 11.034 |

가격 흐름과 중복 event 목록:

| 유형 | t0 | 기준 가격 | 목표 도달 | 평가 종료 | 최대 상승 % |
|---|---|---|---|---|---|
| A | 08-22 14:11 | 290.000 | 08-22 14:11 | 08-22 15:11 | 12.759 |

사전 특징 (가격 수익률과 변동폭은 %, 상대강도는 %p):

| 분 전 | return_5m_pct | return_15m_pct | return_30m_pct | return_60m_pct | trade_value_ratio | trade_value_acceleration | ma5 | ma20 | range_30m_pct | distance_to_prior_high_pct | alt_relative_60m_pct | MA5>MA20 | 돌파 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 120 | 0.840 | 0.840 | 0.559 | 3.746 | NULL | 1.034 | 358.200 | 358.400 | 1.695 | NULL | 1.701 | False | NULL |
| 60 | 0.000 | -0.278 | 0.560 | -0.278 | NULL | 0.139 | 359.400 | 360.500 | 1.966 | NULL | -0.796 | False | NULL |
| 30 | -1.127 | -0.847 | -2.228 | -1.681 | 1.503 | 0.512 | 353.000 | 354.200 | 3.143 | 3.419 | -2.188 | False | False |
| 15 | 0.284 | 0.570 | -0.282 | -1.944 | 0.891 | 2.932 | 352.600 | 351.900 | 1.714 | 2.833 | -2.766 | True | False |
| 5 | -0.850 | -0.568 | -1.408 | -2.507 | 2.064 | 1.174 | 350.200 | 351.650 | 2.305 | 3.143 | -3.388 | False | False |

- 120분 전 NULL: prior_mean_trade_value_5m: 65..5m: 59/60 candles; trade_value_ratio: 65..5m: 59/60 candles; range_change_pct: 60..30m: 29/30 candles; distance_to_prior_high_pct: 61..1m: 59/60 candles

- 60분 전 NULL: prior_mean_trade_value_5m: 65..5m: 59/60 candles; trade_value_ratio: 65..5m: 59/60 candles; range_change_pct: 60..30m: 29/30 candles; distance_to_prior_high_pct: 61..1m: 59/60 candles

## t0 정의 불일치 목록

새 episode를 시작할 때 과거 저점 큐를 비우는 동작은 이전 episode 저점을 재사용하지 않게 하지만, 전체 과거 H분의 최저 종가라는 설명과 달라질 수 있습니다. 아래는 조건을 바꾸지 않고 측정한 차이입니다.

| 종목 | event_id | 현재 t0 | 전체 창 최저 종가 시각 | 현재 가격 | 전체 창 최저 종가 |
|---|---|---|---|---|---|
| KRW-ONG | cc5e67ecc357ab6997ed | 08-20 22:35 | 08-20 22:06 | 96.700 | 82.700 |

## 특징별 NULL 수 (대표 10개 × 5시점)

| 특징 | NULL | 전체 |
|---|---|---|
| return_5m_pct | 13 | 50 |
| return_15m_pct | 14 | 50 |
| return_30m_pct | 15 | 50 |
| return_60m_pct | 13 | 50 |
| trade_value_5m | 20 | 50 |
| prior_mean_trade_value_5m | 37 | 50 |
| trade_value_ratio | 37 | 50 |
| trade_value_change_pct | 24 | 50 |
| trade_value_acceleration | 29 | 50 |
| ma5 | 20 | 50 |
| ma20 | 32 | 50 |
| ma5_ma20_ratio | 32 | 50 |
| ma20_slope_5m_pct | 33 | 50 |
| range_30m_pct | 34 | 50 |
| range_change_pct | 37 | 50 |
| distance_to_prior_high_pct | 37 | 50 |
| alt_relative_60m_pct | 13 | 50 |
| btc_relative_60m_pct | 13 | 50 |

## 통계 단위

원본 event 기준 단일 특징 통계는 같은 이름의 research JSON/Markdown에 있습니다. audit JSON의 episode_statistics는 episode·유형별 첫 event 하나만 남긴 별도 집계이며 원래 대조군을 유지합니다. 매칭 유무에 따라 대표를 바꾸지 않습니다. A/B 유형 합산 확률이나 독립 표본 추론은 하지 않습니다.
## 판단

현재 전체 실행을 연구 결론 산출용으로 권하지 않습니다. 결측으로 인한 표본·대조군 선택 편향, t0의 episode 경계 예외, 전이적 episode 병합과 통계 단위를 먼저 확정해야 합니다. 매칭률을 올리려고 이번 작업에서 조건을 완화하지 않았습니다.
