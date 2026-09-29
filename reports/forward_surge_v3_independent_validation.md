# V3 고정 4% 정책: 독립 기간 validation

무결성: True; 상태 {'COMPLETE': 51}; 분봉 724,694; 중복 0; 오류 {}
51시장 평균 본 기간 coverage: 68.299%

{'research': {'start_utc': '2026-09-14T15:00:00+00:00', 'end_exclusive_utc': '2026-09-28T15:00:00+00:00', 'start_kst': '2026-09-15T00:00:00+09:00', 'end_exclusive_kst': '2026-09-29T00:00:00+09:00'}, 'before_buffer': {'start_utc': '2026-09-14T09:00:00+00:00', 'end_exclusive_utc': '2026-09-14T15:00:00+00:00', 'start_kst': '2026-09-14T18:00:00+09:00', 'end_exclusive_kst': '2026-09-15T00:00:00+09:00'}, 'after_buffer': {'start_utc': '2026-09-28T15:00:00+00:00', 'end_exclusive_utc': '2026-09-28T21:00:00+00:00', 'start_kst': '2026-09-29T00:00:00+09:00', 'end_exclusive_kst': '2026-09-29T06:00:00+09:00'}}

## 결론: PARTIAL

첫 6시간 제외 판정: PARTIAL. 판정은 사전에 동결한 수치 기준을 그대로 사용한다.
REPLICATED에는 L1/L2 각각 성공 20건 이상이 필요하다. lift가 높아도 표본 기준에 못 미치면 완전 재현으로 판정하지 않는다.
절대 성공률과 lift는 별개다. validation baseline이 낮아져 lift가 커져도 절대 성공률이 discovery보다 높아졌다는 뜻은 아니다.

## Discovery와 validation 비교

|지표|Discovery|Validation 전체|첫 6시간 제외|
|---|---|---|---|
| range 유효 observation | 30305 | 43170 | 42810 |
| 4% signal observation | 3624 | 2340 | 2281 |
| signal cluster | 522 | 455 | 446 |
| L1 baseline % | 3.221 | 0.938 | 0.946 |
| L1 valid cluster | 434 | 373 | 367 |
| L1 success | 44 | 29 | 29 |
| L1 success % | 10.138 | 7.775 | 7.902 |
| L1 baseline lift | 3.148 | 8.285 | 8.357 |
| L2 baseline % | 1.588 | 0.384 | 0.387 |
| L2 valid cluster | 357 | 313 | 312 |
| L2 success | 27 | 13 | 13 |
| L2 success % | 7.563 | 4.153 | 4.167 |
| L2 baseline lift | 4.762 | 10.823 | 10.778 |

## full: PARTIAL

Signal 시장 44; 최대 시장 KRW-CPOOL (10.110%); 시장별 신호 {'KRW-CPOOL': 46, 'KRW-NEAR': 44, 'KRW-FLOCK': 37, 'KRW-ENA': 32, 'KRW-MANTRA': 26, 'KRW-ONDO': 20, 'KRW-UNI': 19, 'KRW-LA': 17, 'KRW-WLD': 16, 'KRW-BCH': 16, 'KRW-SUI': 14, 'KRW-CHIP': 10, 'KRW-PUMP': 10, 'KRW-PEPE': 10, 'KRW-DATA': 10, 'KRW-ENS': 9, 'KRW-TREE': 9, 'KRW-ONG': 8, 'KRW-STX': 8, 'KRW-0G': 8, 'KRW-SAND': 7, 'KRW-RVN': 7, 'KRW-DOGE': 6, 'KRW-SKR': 6, 'KRW-ETC': 6, 'KRW-ICX': 6, 'KRW-TRUMP': 5, 'KRW-MIRA': 5, 'KRW-ZKC': 4, 'KRW-XLM': 4, 'KRW-SLX': 4, 'KRW-SHIB': 4, 'KRW-ZK': 4, 'KRW-XRP': 3, 'KRW-ADA': 2, 'KRW-RE': 2, 'KRW-LINK': 2, 'KRW-KAITO': 2, 'KRW-PRL': 2, 'KRW-SOL': 1, 'KRW-AUCTION': 1, 'KRW-ZORA': 1, 'KRW-ERA': 1, 'KRW-POL': 1}

|label|baseline 성공/유효|cluster 성공/실패/UNKNOWN|성공 시장|FLOCK 제외 성공/유효|FLOCK 제외 % / lift|시장 동일가중 % / baseline % / lift|
|---|---|---|---|---|---|---|
|L1|323/34419|29/344/82|16|24/342|7.018 / 9.523|6.836 / 2.579 / 2.651|
|L2|115/29966|13/300/142|6|8/292|2.740 / 10.737|4.535 / 1.898 / 2.389|

성공의 시장 집중도 (신호 발생 비중과 구분):

- L1: 시장별 성공 [('KRW-CPOOL', 6), ('KRW-FLOCK', 5), ('KRW-MANTRA', 2), ('KRW-NEAR', 2), ('KRW-TREE', 2), ('KRW-UNI', 2), ('KRW-BCH', 1), ('KRW-DATA', 1), ('KRW-ENA', 1), ('KRW-ETC', 1), ('KRW-ICX', 1), ('KRW-MIRA', 1), ('KRW-ONDO', 1), ('KRW-ONG', 1), ('KRW-PEPE', 1), ('KRW-SAND', 1)]; 상위 2시장 성공 비중 37.931%. 시장 동일가중도 소수 관측 시장의 불안정한 성공률 영향을 받을 수 있다.
- L2: 시장별 성공 [('KRW-FLOCK', 5), ('KRW-CPOOL', 4), ('KRW-DATA', 1), ('KRW-ICX', 1), ('KRW-MANTRA', 1), ('KRW-NEAR', 1)]; 상위 2시장 성공 비중 69.231%. 시장 동일가중도 소수 관측 시장의 불안정한 성공률 영향을 받을 수 있다.

### 동결된 2차 후보 (조건 아님)

|label|feature|success N|failure N|success 중앙값|failure 중앙값|차이|rank effect|상태|
|---|---|---|---|---|---|---|---|---|
| L1 | range_15m_pct | 29 | 344 | 4.899 | 3.574 | 1.324 | 0.526 | OK |
| L1 | range_30m_pct | 29 | 344 | 5.714 | 4.611 | 1.104 | 0.533 | OK |
| L1 | alt_relative_60m_pct | 28 | 325 | 3.277 | 1.723 | 1.554 | 0.318 | OK |
| L2 | range_15m_pct | 13 | 300 | 5.479 | 3.682 | 1.797 | 0.431 | INSUFFICIENT_SAMPLE |
| L2 | range_30m_pct | 13 | 300 | 5.763 | 4.635 | 1.128 | 0.508 | INSUFFICIENT_SAMPLE |
| L2 | alt_relative_60m_pct | 13 | 286 | 2.596 | 1.963 | 0.634 | 0.195 | INSUFFICIENT_SAMPLE |

## exclude_first6h: PARTIAL

Signal 시장 44; 최대 시장 KRW-NEAR (9.641%); 시장별 신호 {'KRW-NEAR': 43, 'KRW-CPOOL': 42, 'KRW-FLOCK': 35, 'KRW-ENA': 32, 'KRW-MANTRA': 26, 'KRW-ONDO': 20, 'KRW-UNI': 19, 'KRW-WLD': 16, 'KRW-BCH': 16, 'KRW-LA': 15, 'KRW-SUI': 14, 'KRW-CHIP': 10, 'KRW-PUMP': 10, 'KRW-PEPE': 10, 'KRW-DATA': 10, 'KRW-ENS': 9, 'KRW-TREE': 9, 'KRW-ONG': 8, 'KRW-STX': 8, 'KRW-0G': 8, 'KRW-SAND': 7, 'KRW-RVN': 7, 'KRW-DOGE': 6, 'KRW-SKR': 6, 'KRW-ETC': 6, 'KRW-ICX': 6, 'KRW-TRUMP': 5, 'KRW-MIRA': 5, 'KRW-ZKC': 4, 'KRW-XLM': 4, 'KRW-SLX': 4, 'KRW-SHIB': 4, 'KRW-ZK': 4, 'KRW-XRP': 3, 'KRW-ADA': 2, 'KRW-RE': 2, 'KRW-LINK': 2, 'KRW-KAITO': 2, 'KRW-PRL': 2, 'KRW-SOL': 1, 'KRW-AUCTION': 1, 'KRW-ZORA': 1, 'KRW-ERA': 1, 'KRW-POL': 1}

|label|baseline 성공/유효|cluster 성공/실패/UNKNOWN|성공 시장|FLOCK 제외 성공/유효|FLOCK 제외 % / lift|시장 동일가중 % / baseline % / lift|
|---|---|---|---|---|---|---|
|L1|323/34160|29/338/79|16|24/337|7.122 / 9.593|6.895 / 2.604 / 2.648|
|L2|115/29748|13/299/134|6|8/291|2.749 / 10.694|4.535 / 1.908 / 2.377|

성공의 시장 집중도 (신호 발생 비중과 구분):

- L1: 시장별 성공 [('KRW-CPOOL', 6), ('KRW-FLOCK', 5), ('KRW-MANTRA', 2), ('KRW-NEAR', 2), ('KRW-TREE', 2), ('KRW-UNI', 2), ('KRW-BCH', 1), ('KRW-DATA', 1), ('KRW-ENA', 1), ('KRW-ETC', 1), ('KRW-ICX', 1), ('KRW-MIRA', 1), ('KRW-ONDO', 1), ('KRW-ONG', 1), ('KRW-PEPE', 1), ('KRW-SAND', 1)]; 상위 2시장 성공 비중 37.931%. 시장 동일가중도 소수 관측 시장의 불안정한 성공률 영향을 받을 수 있다.
- L2: 시장별 성공 [('KRW-FLOCK', 5), ('KRW-CPOOL', 4), ('KRW-DATA', 1), ('KRW-ICX', 1), ('KRW-MANTRA', 1), ('KRW-NEAR', 1)]; 상위 2시장 성공 비중 69.231%. 시장 동일가중도 소수 관측 시장의 불안정한 성공률 영향을 받을 수 있다.

### 동결된 2차 후보 (조건 아님)

|label|feature|success N|failure N|success 중앙값|failure 중앙값|차이|rank effect|상태|
|---|---|---|---|---|---|---|---|---|
| L1 | range_15m_pct | 29 | 338 | 4.899 | 3.553 | 1.345 | 0.528 | OK |
| L1 | range_30m_pct | 29 | 338 | 5.714 | 4.620 | 1.094 | 0.529 | OK |
| L1 | alt_relative_60m_pct | 28 | 319 | 3.277 | 1.743 | 1.534 | 0.314 | OK |
| L2 | range_15m_pct | 13 | 299 | 5.479 | 3.700 | 1.780 | 0.430 | INSUFFICIENT_SAMPLE |
| L2 | range_30m_pct | 13 | 299 | 5.763 | 4.638 | 1.126 | 0.507 | INSUFFICIENT_SAMPLE |
| L2 | alt_relative_60m_pct | 13 | 285 | 2.596 | 1.993 | 0.603 | 0.194 | INSUFFICIENT_SAMPLE |

## 동결 판정 기준

- note: Operational descriptive gates fixed now, not significance claims. Discovery rates are references, never pass thresholds.
- REPLICATED: Both labels: >=20 successes, >=20 failures, >=3 success markets, cluster rate / same-population observation baseline >=1.5, and FLOCK-excluded lift >1 with >=3 success markets.
- PARTIAL: Not REPLICATED or concentrated FAILED: at least one label lift >1 with >=3 success markets and FLOCK-excluded lift >1. Insufficient sample explicitly flagged.
- FAILED: Neither label has such support, or both labels depend on <3 success markets or lose lift after FLOCK exclusion.
- no_valid_data: Do not assign performance verdict; DATA_INSUFFICIENT.

## 한계와 보존

- 본 기간은 discovery와 분리됐지만 discovery buffer 첫 6시간 노출이 있다. 제외 sensitivity에서도 기존 cluster를 재시작하지 않았다.
- 동결일이 validation 시작일 이후이므로 완전한 전향 검증은 아니다. 이 기간에 대한 사후 threshold 탐색은 수행하지 않았다.
- baseline은 전체 range-valid observation, signal은 cluster 최초 시점이다. 두 분모는 다르며 lift는 기술적 비교다. 완전 관측 필터는 활발한 거래 구간에 치우친다.
- 시장 동일가중은 유효 cluster가 있는 동일 시장 집합에서 시장별 성공률과 baseline을 각각 평균한다. FLOCK 제외 baseline도 FLOCK을 제외하여 계산한다.
- 각 시장의 state/requested 범위와 buffer 품질 및 label별 시장 성공 수는 JSON에 보존했다.
- 두 DB 및 동결 정책/manifest 파일 해시: {'validation': {'before': '741e03592849630dbe7b7a2bb82ae9b31587afee66f4f351c9e8e0ed652a8248', 'after': '741e03592849630dbe7b7a2bb82ae9b31587afee66f4f351c9e8e0ed652a8248', 'unchanged': True}, 'discovery': {'before': 'ea217854758134dafc96dcf56ee86a474d1832f1eb35c65f547815d3842a1633', 'after': 'ea217854758134dafc96dcf56ee86a474d1832f1eb35c65f547815d3842a1633', 'unchanged': True}, 'policy': {'before': '6f2c99deb59eac8cc9fbb6ad55062642f165d7d99d31c2768fd29e7b37f3e7c5', 'after': '6f2c99deb59eac8cc9fbb6ad55062642f165d7d99d31c2768fd29e7b37f3e7c5', 'unchanged': True}, 'manifest': {'before': 'd78cd8d500099599b32e5a131e25ea7796bed44e256797476cf2be0f3f6d070c', 'after': 'd78cd8d500099599b32e5a131e25ea7796bed44e256797476cf2be0f3f6d070c', 'unchanged': True}}

## 시장별 본 기간과 buffer 품질

|market|본 기간 candles|coverage %|최대 gap 분|앞 buffer candles|뒤 buffer candles|
|---|---|---|---|---|---|
|KRW-0G|12827|63.626|40|226|248|
|KRW-ADA|18217|90.362|9|316|318|
|KRW-AUCTION|5873|29.132|98|79|55|
|KRW-BCH|16273|80.719|11|305|221|
|KRW-BTC|20160|100.000|0|360|360|
|KRW-CHIP|13171|65.332|22|246|115|
|KRW-CPOOL|15109|74.945|23|360|175|
|KRW-DATA|14566|72.252|22|238|175|
|KRW-DOGE|18921|93.854|7|340|309|
|KRW-ENA|18309|90.818|9|290|288|
|KRW-ENS|14944|74.127|15|241|164|
|KRW-ERA|7630|37.847|65|148|73|
|KRW-ETC|15715|77.951|22|212|235|
|KRW-ETH|20151|99.955|1|360|359|
|KRW-FLOCK|17437|86.493|19|348|250|
|KRW-ICX|7542|37.411|104|88|46|
|KRW-KAITO|10020|49.702|57|134|156|
|KRW-LA|15168|75.238|42|360|169|
|KRW-LINK|17732|87.956|9|321|360|
|KRW-MANTRA|10207|50.630|112|96|115|
|KRW-ME|8300|41.171|62|180|67|
|KRW-MIRA|11951|59.281|24|246|122|
|KRW-NEAR|19620|97.321|6|322|359|
|KRW-O|5799|28.765|76|57|109|
|KRW-ONDO|19660|97.520|7|340|360|
|KRW-ONG|11547|57.277|41|196|104|
|KRW-PEPE|13098|64.970|33|166|177|
|KRW-POL|10898|54.058|31|125|118|
|KRW-PRL|9145|45.362|55|167|121|
|KRW-PUMP|12448|61.746|40|131|282|
|KRW-RE|10614|52.649|31|190|102|
|KRW-RVN|9497|47.108|43|199|80|
|KRW-SAND|12205|60.541|36|208|157|
|KRW-SHIB|18561|92.068|7|329|298|
|KRW-SKR|9125|45.263|54|194|87|
|KRW-SLX|14720|73.016|22|325|204|
|KRW-SOL|20077|99.588|2|356|355|
|KRW-STX|14644|72.639|18|264|216|
|KRW-SUI|19440|96.429|5|348|347|
|KRW-TREE|11434|56.716|31|303|120|
|KRW-TRUMP|19173|95.104|11|355|306|
|KRW-TRX|15725|78.001|14|308|190|
|KRW-UNI|17572|87.163|8|219|283|
|KRW-WLD|18860|93.552|8|347|351|
|KRW-XLM|19177|95.124|6|353|356|
|KRW-XRP|20160|100.000|0|360|360|
|KRW-ZBT|7166|35.546|51|99|74|
|KRW-ZK|6825|33.854|63|84|73|
|KRW-ZKC|11021|54.668|43|119|138|
|KRW-ZKP|6866|34.058|59|101|76|
|KRW-ZORA|6927|34.360|52|155|70|
