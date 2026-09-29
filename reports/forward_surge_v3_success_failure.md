# 30분 range ≥4%: cluster 최초 시점의 성공·실패 비교

판정: **WEAK**

총 cluster 522; 최대 signal 시장 KRW-FLOCK; 시장 분포 {'KRW-FLOCK': 109, 'KRW-SKR': 59, 'KRW-LA': 49, 'KRW-CHIP': 46, 'KRW-0G': 22, 'KRW-ONG': 21, 'KRW-ZORA': 17, 'KRW-ICX': 16, 'KRW-NEAR': 14, 'KRW-TREE': 13, 'KRW-MIRA': 12, 'KRW-MANTRA': 11, 'KRW-ENA': 10, 'KRW-ZKC': 10, 'KRW-UNI': 10, 'KRW-TRUMP': 9, 'KRW-WLD': 9, 'KRW-RVN': 7, 'KRW-ZK': 7, 'KRW-DOGE': 5, 'KRW-ZKP': 5, 'KRW-ADA': 5, 'KRW-PUMP': 5, 'KRW-ENS': 5, 'KRW-SAND': 4, 'KRW-PRL': 4, 'KRW-CPOOL': 4, 'KRW-SUI': 3, 'KRW-LINK': 3, 'KRW-BCH': 3, 'KRW-ETC': 3, 'KRW-PEPE': 3, 'KRW-DATA': 3, 'KRW-XRP': 2, 'KRW-ONDO': 2, 'KRW-XLM': 2, 'KRW-STX': 2, 'KRW-RE': 2, 'KRW-ETH': 1, 'KRW-SOL': 1, 'KRW-SHIB': 1, 'KRW-AUCTION': 1, 'KRW-ERA': 1, 'KRW-KAITO': 1}

|label|signal|success|failure|unknown|성공률 %|
|---|---|---|---|---|---|
|L1|522|44|390|88|10.1382|
|L2|522|27|330|165|7.5630|

## 해석 및 분류

성공률 분모는 success+failure이며 UNKNOWN은 제외한다. 1차 필터 이후의 추가 분리력을 조사한다.
방향만 반복된 잠정 후보: ['return_60m_pct', 'range_15m_pct', 'range_30m_pct', 'drawdown30_pct', 'alt_relative_60m_pct', 'btc_relative_60m_pct']
각 민감도 분석에서 성공·실패 각각 20건 이상을 요구했다. 방향이 유지돼도 이 표본 조건을 충족하지 못하면 약한 후보로 남긴다.
기준을 모두 통과한 공통 후보: []
보조 조건 비교: 엄격한 공통 후보가 없어 2단계 조건을 만들지 않았다.

|feature|분류|L1/L2 방향 일치|모든 sensitivity 방향 일치|
|---|---|---|---|
|return_5m_pct|차이가 거의 없음|False|False|
|return_15m_pct|차이가 거의 없음|True|True|
|return_30m_pct|차이가 거의 없음|False|False|
|return_60m_pct|약한 차이|True|True|
|return_120m_pct|차이가 거의 없음|False|False|
|range_15m_pct|약한 차이|True|True|
|range_30m_pct|약한 차이|True|True|
|range_60m_pct|약한 차이|True|False|
|drawdown_from_high_60m_pct|차이가 거의 없음|True|False|
|drawdown30_pct|약한 차이|True|True|
|position30|차이가 거의 없음|True|False|
|trade_value_ratio|차이가 거의 없음|True|False|
|trade_value_acceleration|차이가 거의 없음|False|False|
|ma5_ma20_ratio|차이가 거의 없음|True|False|
|ma20_slope_5m_pct|차이가 거의 없음|True|False|
|prior_high_breakout|차이가 거의 없음|True|True|
|alt_relative_60m_pct|약한 차이|True|True|
|btc_relative_60m_pct|약한 차이|True|True|
|exploratory_value5_prior25_ratio|차이가 거의 없음|True|True|
|exploratory_value15_prior15_ratio|차이가 거의 없음|True|False|

## 사람이 읽는 주요 비교

최근 15/30분 고저폭과 60분 상대강도는 서로 독립적인 후보가 아니다. 고저폭은 동일한 변동성 상태를, 상대강도는 60분 수익률을 일부 공유한다.
5/15/30분 수익률, MA 관계, 거래대금 배율·가속의 분리력은 전반적으로 작거나 sensitivity에서 방향이 바뀐다. 거래대금 탐색 feature는 원래 feature와 구분하여 표에 표시했다.
drawdown30은 음수 값이 더 작을수록 고점에서 더 많이 내려온 상태다. 성공군이 고점에 더 가까웠다는 해석은 하지 않는다. position30 자체의 차이는 작다.
최대 signal 시장이 FLOCK이므로 FLOCK 제외와 최대 시장 제외는 동일한 분석이며 두 독립 검증으로 세지 않는다.

|feature|label|success 중앙값|failure 중앙값|success/failure N|
|---|---|---|---|---|
|range_15m_pct|L1|4.6411|3.8439|44/390|
|range_15m_pct|L2|5.0517|4.0000|27/330|
|range_30m_pct|L1|5.4711|4.7512|44/390|
|range_30m_pct|L2|5.6106|4.7003|27/330|
|alt_relative_60m_pct|L1|1.9448|0.9722|43/368|
|alt_relative_60m_pct|L2|3.8095|1.3120|27/314|
|drawdown30_pct|L1|-2.2799|-1.7158|44/390|
|drawdown30_pct|L2|-2.7618|-1.4912|27/330|
|position30|L1|0.6410|0.6612|44/390|
|position30|L2|0.6757|0.6900|27/330|

### 시간 분리의 유효 표본

- L1 first7d: {'signals': 347, 'success': 31, 'failure': 254, 'unknown': 62, 'rate_pct': 10.87719298245614}
- L1 last7d: {'signals': 175, 'success': 12, 'failure': 134, 'unknown': 29, 'rate_pct': 8.219178082191782}
- L2 first7d: {'signals': 347, 'success': 14, 'failure': 223, 'unknown': 110, 'rate_pct': 5.9071729957805905}
- L2 last7d: {'signals': 175, 'success': 12, 'failure': 104, 'unknown': 59, 'rate_pct': 10.344827586206897}

## 계산·해석 정책

- 4% fixed; 5-minute grid; first cluster observation only. Warm-up pre-buffer; NULL range does not reset, observed <4% resets.
- All incomplete future windows are UNKNOWN, including observed partial hits. First signal is never replaced.
- Features use candle close <=t, no fill. Range=(high/low-1)*100; position=(close-low)/(high-low).
- New exploratory trade-value ratios: last5/(preceding25/5), last15/preceding15; complete respective windows, zero denominator => NULL.
- Market-balanced: equal total weight per market separately within each feature-valid success/failure group. Different class market composition remains a confounder.
- First7d outcomes crossing split excluded; trailing buffer allowed. Time split is retrospective, not independent holdout.
- Descriptive Cliff delta measures rank separation; abs<0.147 is classified near-zero, not a significance test. No p-value or trading cutoff search.
- Repeated candidate requires same rank-effect sign in both labels/all six views, >=20 valid in each class and >=3 markets/class in every view. Median ties are reported, not invented as directional differences.
- Absolute MA prices excluded from cross-market comparison. Labels and features overlap; cluster observations can still be temporally dependent.

## L1 / all

{'signals': 522, 'success': 44, 'failure': 390, 'unknown': 88, 'rate_pct': 10.138248847926267}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|44|390|0.0000|0.1961|-0.1961|0.9005|0.3051|0.0198|OK|
|return_15m_pct|44|390|0.8755|1.1761|-0.3006|1.4021|0.5948|0.0268|OK|
|return_30m_pct|41|367|1.9108|1.9380|-0.0272|1.3558|0.8519|0.0457|OK|
|return_60m_pct|43|368|2.4931|1.4618|1.0313|2.5921|0.8760|0.1588|OK|
|return_120m_pct|39|362|2.4648|2.1128|0.3520|2.4174|1.4325|0.0883|OK|
|range_15m_pct|44|390|4.6411|3.8439|0.7972|5.8533|4.1250|0.3700|OK|
|range_30m_pct|44|390|5.4711|4.7512|0.7200|6.9963|5.3987|0.2875|OK|
|range_60m_pct|23|253|5.7047|5.8252|-0.1205|7.1465|6.4420|0.0878|OK|
|drawdown_from_high_60m_pct|23|253|-2.8571|-2.0630|-0.7942|-3.6648|-2.8998|-0.1303|OK|
|drawdown30_pct|44|390|-2.2799|-1.7158|-0.5641|-2.6963|-2.2388|-0.1519|OK|
|position30|44|390|0.6410|0.6612|-0.0202|0.5229|0.5601|-0.0813|OK|
|trade_value_ratio|22|246|2.7375|2.0517|0.6858|3.4840|3.3423|0.1264|OK|
|trade_value_acceleration|44|390|1.8264|1.6429|0.1835|6.9876|6.6754|0.0640|OK|
|ma5_ma20_ratio|44|390|1.0050|1.0066|-0.0016|1.0078|1.0027|0.0160|OK|
|ma20_slope_5m_pct|44|390|0.2948|0.3625|-0.0677|0.3759|0.1522|0.0020|OK|
|prior_high_breakout|23|251|0.0000|0.0000|0.0000|0.1739|0.1116|0.0624|OK|
|alt_relative_60m_pct|43|368|1.9448|0.9722|0.9727|2.6532|0.7439|0.1863|OK|
|btc_relative_60m_pct|43|368|2.6053|1.3187|1.2866|2.5731|0.7852|0.1672|OK|
|exploratory_value5_prior25_ratio|44|390|2.6593|2.1234|0.5359|5.8493|3.4859|0.1217|OK|
|exploratory_value15_prior15_ratio|44|390|2.0164|1.7654|0.2510|4.9206|2.9033|0.0949|OK|

## L1 / market_balanced

{'signals': 522, 'success': 44, 'failure': 390, 'unknown': 88, 'rate_pct': 10.138248847926267}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|44|390|1.3245|0.1606|1.1639|1.4451|0.2512|0.1581|OK|
|return_15m_pct|44|390|1.7483|1.2422|0.5060|2.2948|0.8282|0.1473|OK|
|return_30m_pct|41|367|0.6920|2.8807|-2.1886|2.4561|1.5765|0.0311|OK|
|return_60m_pct|43|368|4.7244|2.9412|1.7832|4.3317|1.9136|0.2241|OK|
|return_120m_pct|39|362|2.8902|4.6667|-1.7765|3.3372|2.7389|-0.0402|OK|
|range_15m_pct|44|390|4.6512|3.3123|1.3389|6.1030|3.5109|0.5947|OK|
|range_30m_pct|44|390|5.4993|4.5649|0.9344|7.7080|5.3010|0.4206|OK|
|range_60m_pct|23|253|5.6088|5.4696|0.1392|6.5569|6.2234|0.0543|OK|
|drawdown_from_high_60m_pct|23|253|-1.3158|-0.6053|-0.7105|-2.7637|-2.0946|-0.2505|OK|
|drawdown30_pct|44|390|-1.4286|-0.9615|-0.4670|-2.3939|-1.8348|-0.1754|OK|
|position30|44|390|0.7045|0.8000|-0.0955|0.6108|0.6498|-0.0904|OK|
|trade_value_ratio|22|246|3.0044|2.1181|0.8863|3.0256|3.6502|0.1146|OK|
|trade_value_acceleration|44|390|1.8562|1.2516|0.6046|7.3954|5.4657|0.2165|OK|
|ma5_ma20_ratio|44|390|1.0077|1.0071|0.0006|1.0108|1.0039|0.0982|OK|
|ma20_slope_5m_pct|44|390|0.4275|0.5645|-0.1371|0.5942|0.3229|0.0033|OK|
|prior_high_breakout|23|251|0.0000|0.0000|0.0000|0.1790|0.1099|0.0691|OK|
|alt_relative_60m_pct|43|368|4.0333|1.4686|2.5647|4.4386|1.4187|0.3154|OK|
|btc_relative_60m_pct|43|368|4.1146|2.0612|2.0534|4.3623|1.6176|0.2709|OK|
|exploratory_value5_prior25_ratio|44|390|2.3479|1.5843|0.7636|7.6322|2.8578|0.2069|OK|
|exploratory_value15_prior15_ratio|44|390|2.0157|1.8065|0.2092|5.4101|3.1334|0.1061|OK|

## L1 / without_flock

{'signals': 413, 'success': 25, 'failure': 313, 'unknown': 75, 'rate_pct': 7.396449704142012}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|25|313|0.0000|0.1458|-0.1458|1.0909|0.1432|0.0256|OK|
|return_15m_pct|25|313|1.0676|1.1577|-0.0901|2.0712|0.5229|0.0771|OK|
|return_30m_pct|23|290|1.5924|2.1047|-0.5124|1.8046|0.8521|0.0651|OK|
|return_60m_pct|24|293|3.8073|1.7544|2.0529|3.9816|0.9493|0.3235|OK|
|return_120m_pct|20|288|2.6775|2.2226|0.4549|2.9990|1.5719|0.1384|OK|
|range_15m_pct|25|313|4.4776|3.6550|0.8226|6.1114|3.9256|0.3099|OK|
|range_30m_pct|25|313|5.4745|4.6948|0.7796|7.7901|5.2675|0.3256|OK|
|range_60m_pct|12|190|5.5731|5.8026|-0.2294|6.8872|6.3117|-0.0851|INSUFFICIENT_SAMPLE|
|drawdown_from_high_60m_pct|12|190|-2.2002|-2.0876|-0.1126|-3.4981|-2.8610|-0.0544|INSUFFICIENT_SAMPLE|
|drawdown30_pct|25|313|-1.6892|-1.5674|-0.1218|-2.6100|-2.1898|-0.1103|OK|
|position30|25|313|0.6667|0.6667|-0.0000|0.5786|0.5676|-0.0091|OK|
|trade_value_ratio|11|183|2.4691|2.0144|0.4547|2.4014|3.2457|-0.0035|INSUFFICIENT_SAMPLE|
|trade_value_acceleration|25|313|1.8562|1.6237|0.2325|5.1410|6.5431|0.0960|OK|
|ma5_ma20_ratio|25|313|1.0056|1.0064|-0.0008|1.0116|1.0024|0.0796|OK|
|ma20_slope_5m_pct|25|313|0.4123|0.4009|0.0113|0.5843|0.1682|0.0679|OK|
|prior_high_breakout|12|188|0.0000|0.0000|0.0000|0.1667|0.1170|0.0496|INSUFFICIENT_SAMPLE|
|alt_relative_60m_pct|24|293|3.9875|1.1004|2.8871|4.0975|0.7858|0.3604|OK|
|btc_relative_60m_pct|24|293|3.7524|1.4632|2.2891|3.9902|0.8425|0.3359|OK|
|exploratory_value5_prior25_ratio|25|313|2.2097|1.9891|0.2207|5.4748|3.2646|0.0088|OK|
|exploratory_value15_prior15_ratio|25|313|1.9546|1.7198|0.2348|5.7171|2.9017|-0.0121|OK|

## L1 / without_top_market

{'signals': 413, 'success': 25, 'failure': 313, 'unknown': 75, 'rate_pct': 7.396449704142012}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|25|313|0.0000|0.1458|-0.1458|1.0909|0.1432|0.0256|OK|
|return_15m_pct|25|313|1.0676|1.1577|-0.0901|2.0712|0.5229|0.0771|OK|
|return_30m_pct|23|290|1.5924|2.1047|-0.5124|1.8046|0.8521|0.0651|OK|
|return_60m_pct|24|293|3.8073|1.7544|2.0529|3.9816|0.9493|0.3235|OK|
|return_120m_pct|20|288|2.6775|2.2226|0.4549|2.9990|1.5719|0.1384|OK|
|range_15m_pct|25|313|4.4776|3.6550|0.8226|6.1114|3.9256|0.3099|OK|
|range_30m_pct|25|313|5.4745|4.6948|0.7796|7.7901|5.2675|0.3256|OK|
|range_60m_pct|12|190|5.5731|5.8026|-0.2294|6.8872|6.3117|-0.0851|INSUFFICIENT_SAMPLE|
|drawdown_from_high_60m_pct|12|190|-2.2002|-2.0876|-0.1126|-3.4981|-2.8610|-0.0544|INSUFFICIENT_SAMPLE|
|drawdown30_pct|25|313|-1.6892|-1.5674|-0.1218|-2.6100|-2.1898|-0.1103|OK|
|position30|25|313|0.6667|0.6667|-0.0000|0.5786|0.5676|-0.0091|OK|
|trade_value_ratio|11|183|2.4691|2.0144|0.4547|2.4014|3.2457|-0.0035|INSUFFICIENT_SAMPLE|
|trade_value_acceleration|25|313|1.8562|1.6237|0.2325|5.1410|6.5431|0.0960|OK|
|ma5_ma20_ratio|25|313|1.0056|1.0064|-0.0008|1.0116|1.0024|0.0796|OK|
|ma20_slope_5m_pct|25|313|0.4123|0.4009|0.0113|0.5843|0.1682|0.0679|OK|
|prior_high_breakout|12|188|0.0000|0.0000|0.0000|0.1667|0.1170|0.0496|INSUFFICIENT_SAMPLE|
|alt_relative_60m_pct|24|293|3.9875|1.1004|2.8871|4.0975|0.7858|0.3604|OK|
|btc_relative_60m_pct|24|293|3.7524|1.4632|2.2891|3.9902|0.8425|0.3359|OK|
|exploratory_value5_prior25_ratio|25|313|2.2097|1.9891|0.2207|5.4748|3.2646|0.0088|OK|
|exploratory_value15_prior15_ratio|25|313|1.9546|1.7198|0.2348|5.7171|2.9017|-0.0121|OK|

## L1 / first7d

{'signals': 347, 'success': 31, 'failure': 254, 'unknown': 62, 'rate_pct': 10.87719298245614}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|31|254|-0.3676|0.0000|-0.3676|0.7549|0.1752|-0.0157|OK|
|return_15m_pct|31|254|0.8016|0.8675|-0.0659|1.3976|0.3643|0.0085|OK|
|return_30m_pct|28|241|0.6285|1.2024|-0.5739|0.6969|0.5878|0.0009|OK|
|return_60m_pct|30|239|1.4035|1.0000|0.4035|2.2513|0.6852|0.1414|OK|
|return_120m_pct|27|236|2.0408|1.2216|0.8192|1.7905|1.0855|0.0808|OK|
|range_15m_pct|31|254|4.2339|3.9481|0.2858|5.9135|4.2052|0.2565|OK|
|range_30m_pct|31|254|5.2319|4.7651|0.4668|6.8277|5.3382|0.1811|OK|
|range_60m_pct|15|169|5.5375|6.0703|-0.5328|7.0219|6.6017|-0.0935|INSUFFICIENT_SAMPLE|
|drawdown_from_high_60m_pct|15|169|-2.9126|-2.9372|0.0246|-3.8746|-3.1137|-0.1199|INSUFFICIENT_SAMPLE|
|drawdown30_pct|31|254|-2.7618|-2.0726|-0.6892|-2.8067|-2.3507|-0.1618|OK|
|position30|31|254|0.6154|0.5774|0.0380|0.4819|0.5333|-0.1077|OK|
|trade_value_ratio|14|163|2.1359|1.9208|0.2150|3.0120|3.2458|0.0210|INSUFFICIENT_SAMPLE|
|trade_value_acceleration|31|254|2.0049|1.6823|0.3226|4.9223|6.9865|0.0597|OK|
|ma5_ma20_ratio|31|254|1.0054|1.0046|0.0009|1.0090|1.0015|0.0348|OK|
|ma20_slope_5m_pct|31|254|0.2724|0.2874|-0.0151|0.4074|0.1026|0.0198|OK|
|prior_high_breakout|15|167|0.0000|0.0000|0.0000|0.1333|0.1138|0.0196|INSUFFICIENT_SAMPLE|
|alt_relative_60m_pct|30|239|1.4846|0.8875|0.5971|2.2747|0.6753|0.1437|OK|
|btc_relative_60m_pct|30|239|1.3687|1.0444|0.3243|2.1960|0.6576|0.1395|OK|
|exploratory_value5_prior25_ratio|31|254|2.2582|2.1252|0.1330|5.8847|3.4163|0.0587|OK|
|exploratory_value15_prior15_ratio|31|254|1.9839|1.6948|0.2891|5.5539|2.7007|0.0531|OK|

## L1 / last7d

{'signals': 175, 'success': 12, 'failure': 134, 'unknown': 29, 'rate_pct': 8.219178082191782}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|12|134|1.5336|0.3615|1.1721|1.6242|0.5174|0.2525|INSUFFICIENT_SAMPLE|
|return_15m_pct|12|134|3.4636|1.4182|2.0454|1.8485|0.9886|0.2090|INSUFFICIENT_SAMPLE|
|return_30m_pct|12|124|3.8357|2.5202|1.3155|3.4308|1.3151|0.2903|INSUFFICIENT_SAMPLE|
|return_60m_pct|12|127|4.7307|2.4561|2.2745|4.1626|1.1612|0.3668|INSUFFICIENT_SAMPLE|
|return_120m_pct|11|124|6.6667|3.0472|3.6195|4.8444|1.9940|0.3123|INSUFFICIENT_SAMPLE|
|range_15m_pct|12|134|5.3099|3.6735|1.6363|5.6889|3.9594|0.6007|INSUFFICIENT_SAMPLE|
|range_30m_pct|12|134|5.6676|4.6915|0.9761|7.5186|5.5047|0.5236|INSUFFICIENT_SAMPLE|
|range_60m_pct|7|83|5.7572|5.3237|0.4335|7.4165|6.1364|0.3528|INSUFFICIENT_SAMPLE|
|drawdown_from_high_60m_pct|7|83|-1.8519|-1.3351|-0.5167|-2.8040|-2.4918|-0.0017|INSUFFICIENT_SAMPLE|
|drawdown30_pct|12|134|-1.4240|-1.2580|-0.1660|-2.1763|-2.0480|-0.0137|INSUFFICIENT_SAMPLE|
|position30|12|134|0.8080|0.7500|0.0580|0.6708|0.6066|0.1070|INSUFFICIENT_SAMPLE|
|trade_value_ratio|7|82|4.3946|2.3885|2.0061|4.1535|3.5410|0.2613|INSUFFICIENT_SAMPLE|
|trade_value_acceleration|12|134|1.2282|1.4856|-0.2574|12.7117|6.1218|0.0659|INSUFFICIENT_SAMPLE|
|ma5_ma20_ratio|12|134|1.0067|1.0076|-0.0010|1.0067|1.0048|0.0983|INSUFFICIENT_SAMPLE|
|ma20_slope_5m_pct|12|134|0.4693|0.4594|0.0100|0.3909|0.2375|0.0883|INSUFFICIENT_SAMPLE|
|prior_high_breakout|7|83|0.0000|0.0000|0.0000|0.2857|0.1084|0.1773|INSUFFICIENT_SAMPLE|
|alt_relative_60m_pct|12|127|5.1518|1.1674|3.9843|4.2672|0.7921|0.4029|INSUFFICIENT_SAMPLE|
|btc_relative_60m_pct|12|127|4.8266|1.6409|3.1857|4.2013|0.9479|0.3753|INSUFFICIENT_SAMPLE|
|exploratory_value5_prior25_ratio|12|134|4.5591|2.1082|2.4509|5.9122|3.6191|0.2326|INSUFFICIENT_SAMPLE|
|exploratory_value15_prior15_ratio|12|134|2.2542|2.0029|0.2513|3.4780|3.2988|0.1592|INSUFFICIENT_SAMPLE|

## L2 / all

{'signals': 522, 'success': 27, 'failure': 330, 'unknown': 165, 'rate_pct': 7.563025210084033}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|27|330|0.0000|0.3990|-0.3990|1.1288|0.4481|-0.0109|OK|
|return_15m_pct|27|330|1.2024|1.4021|-0.1997|1.7615|0.7666|0.0282|OK|
|return_30m_pct|24|316|2.0688|2.1047|-0.0359|1.1859|1.0766|-0.0193|OK|
|return_60m_pct|27|314|3.7081|1.5791|2.1291|2.9457|1.0443|0.1907|OK|
|return_120m_pct|24|304|1.2260|2.3057|-1.0797|1.3390|1.7627|-0.0611|OK|
|range_15m_pct|27|330|5.0517|4.0000|1.0517|6.3786|4.2656|0.3414|OK|
|range_30m_pct|27|330|5.6106|4.7003|0.9103|7.7229|5.4049|0.3712|OK|
|range_60m_pct|17|233|6.5831|5.8072|0.7759|7.5592|6.5180|0.1926|INSUFFICIENT_SAMPLE|
|drawdown_from_high_60m_pct|17|233|-2.0000|-1.9751|-0.0249|-3.5632|-2.8543|-0.0800|INSUFFICIENT_SAMPLE|
|drawdown30_pct|27|330|-2.7618|-1.4912|-1.2706|-2.8338|-2.1122|-0.1714|OK|
|position30|27|330|0.6757|0.6900|-0.0144|0.5384|0.5803|-0.0799|OK|
|trade_value_ratio|17|226|2.3534|2.0682|0.2852|3.9148|3.4311|0.1379|INSUFFICIENT_SAMPLE|
|trade_value_acceleration|27|330|1.5585|1.7086|-0.1501|5.1660|6.9955|-0.0110|OK|
|ma5_ma20_ratio|27|330|1.0054|1.0076|-0.0021|1.0101|1.0035|0.0207|OK|
|ma20_slope_5m_pct|27|330|0.3888|0.3973|-0.0085|0.4832|0.1840|0.0705|OK|
|prior_high_breakout|17|231|0.0000|0.0000|0.0000|0.2353|0.1169|0.1184|INSUFFICIENT_SAMPLE|
|alt_relative_60m_pct|27|314|3.8095|1.3120|2.4975|3.0702|0.9569|0.2109|OK|
|btc_relative_60m_pct|27|314|3.5400|1.4521|2.0878|2.9319|0.9858|0.1965|OK|
|exploratory_value5_prior25_ratio|27|330|2.3479|2.3982|-0.0503|6.6936|3.9288|0.1062|OK|
|exploratory_value15_prior15_ratio|27|330|2.4172|1.8159|0.6013|6.0720|3.1364|0.1080|OK|

## L2 / market_balanced

{'signals': 522, 'success': 27, 'failure': 330, 'unknown': 165, 'rate_pct': 7.563025210084033}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|27|330|0.3448|0.2247|0.1201|1.7113|0.3582|0.0853|OK|
|return_15m_pct|27|330|2.6731|1.3193|1.3539|2.8053|0.9778|0.1473|OK|
|return_30m_pct|24|316|2.2267|2.9508|-0.7241|1.9858|1.8231|-0.0243|OK|
|return_60m_pct|27|314|5.6106|3.0854|2.5252|4.7146|1.8990|0.3562|OK|
|return_120m_pct|24|304|1.3937|4.7458|-3.3520|2.2701|2.7889|-0.1739|OK|
|range_15m_pct|27|330|5.4678|3.5088|1.9590|6.8587|3.6531|0.5666|OK|
|range_30m_pct|27|330|5.8201|4.5190|1.3012|8.4814|5.3069|0.5805|OK|
|range_60m_pct|17|233|8.0247|5.4187|2.6060|7.8329|6.1947|0.3772|INSUFFICIENT_SAMPLE|
|drawdown_from_high_60m_pct|17|233|-1.0204|-0.5848|-0.4356|-2.9653|-1.9598|-0.2277|INSUFFICIENT_SAMPLE|
|drawdown30_pct|27|330|-2.0000|-0.8333|-1.1667|-2.5289|-1.7239|-0.1780|OK|
|position30|27|330|0.7200|0.8095|-0.0895|0.6307|0.6679|-0.0708|OK|
|trade_value_ratio|17|226|1.9663|2.1852|-0.2189|3.3680|3.6663|-0.0230|INSUFFICIENT_SAMPLE|
|trade_value_acceleration|27|330|1.5531|1.5011|0.0520|7.7064|6.9281|0.0383|OK|
|ma5_ma20_ratio|27|330|1.0091|1.0076|0.0014|1.0158|1.0047|0.1707|OK|
|ma20_slope_5m_pct|27|330|0.4870|0.5645|-0.0775|0.7802|0.3463|0.1825|OK|
|prior_high_breakout|17|231|0.0000|0.0000|0.0000|0.3889|0.1070|0.2819|INSUFFICIENT_SAMPLE|
|alt_relative_60m_pct|27|314|6.1154|1.5784|4.5370|4.7397|1.5893|0.3939|OK|
|btc_relative_60m_pct|27|314|5.9036|2.2411|3.6625|4.6348|1.7449|0.3698|OK|
|exploratory_value5_prior25_ratio|27|330|2.0112|1.9822|0.0290|9.8173|3.3398|0.1527|OK|
|exploratory_value15_prior15_ratio|27|330|2.6258|1.9318|0.6940|7.5412|3.4489|0.1230|OK|

## L2 / without_flock

{'signals': 413, 'success': 16, 'failure': 254, 'unknown': 143, 'rate_pct': 5.925925925925926}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|16|254|0.1724|0.3069|-0.1345|1.7925|0.2142|0.0711|INSUFFICIENT_SAMPLE|
|return_15m_pct|16|254|1.5734|1.3108|0.2627|2.8338|0.6297|0.1115|INSUFFICIENT_SAMPLE|
|return_30m_pct|13|241|1.9108|2.1488|-0.2379|2.1479|0.9669|0.1021|INSUFFICIENT_SAMPLE|
|return_60m_pct|16|239|5.5831|1.7544|3.8287|4.9700|1.0286|0.4448|INSUFFICIENT_SAMPLE|
|return_120m_pct|13|230|3.6789|2.4030|1.2760|2.7153|1.7324|0.0849|INSUFFICIENT_SAMPLE|
|range_15m_pct|16|254|4.9278|3.7559|1.1719|7.3326|3.9955|0.3999|INSUFFICIENT_SAMPLE|
|range_30m_pct|16|254|5.8086|4.6027|1.2059|9.2669|5.2272|0.5706|INSUFFICIENT_SAMPLE|
|range_60m_pct|8|172|6.8176|5.7502|1.0674|8.2705|6.3494|0.1962|INSUFFICIENT_SAMPLE|
|drawdown_from_high_60m_pct|8|172|-1.5102|-1.9499|0.4397|-3.5474|-2.8009|0.0480|INSUFFICIENT_SAMPLE|
|drawdown30_pct|16|254|-2.3809|-1.3586|-1.0223|-2.9056|-2.0625|-0.1506|INSUFFICIENT_SAMPLE|
|position30|16|254|0.6978|0.6962|0.0017|0.5986|0.5877|0.0194|INSUFFICIENT_SAMPLE|
|trade_value_ratio|8|165|1.7672|2.0516|-0.2844|3.0900|3.3104|0.0182|INSUFFICIENT_SAMPLE|
|trade_value_acceleration|16|254|1.7649|1.6767|0.0881|6.5800|6.5864|0.0423|INSUFFICIENT_SAMPLE|
|ma5_ma20_ratio|16|254|1.0082|1.0073|0.0009|1.0179|1.0028|0.1983|INSUFFICIENT_SAMPLE|
|ma20_slope_5m_pct|16|254|0.4775|0.4194|0.0581|0.8411|0.1834|0.2569|INSUFFICIENT_SAMPLE|
|prior_high_breakout|8|170|0.0000|0.0000|0.0000|0.3750|0.1176|0.2574|INSUFFICIENT_SAMPLE|
|alt_relative_60m_pct|16|239|5.8459|1.3269|4.5190|5.0530|0.9223|0.4550|INSUFFICIENT_SAMPLE|
|btc_relative_60m_pct|16|239|5.6807|1.5254|4.1552|4.8621|0.9646|0.4320|INSUFFICIENT_SAMPLE|
|exploratory_value5_prior25_ratio|16|254|2.1105|2.2109|-0.1005|7.5881|3.6019|0.0295|INSUFFICIENT_SAMPLE|
|exploratory_value15_prior15_ratio|16|254|1.9825|1.8070|0.1755|7.9536|3.1137|0.0162|INSUFFICIENT_SAMPLE|

## L2 / without_top_market

{'signals': 413, 'success': 16, 'failure': 254, 'unknown': 143, 'rate_pct': 5.925925925925926}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|16|254|0.1724|0.3069|-0.1345|1.7925|0.2142|0.0711|INSUFFICIENT_SAMPLE|
|return_15m_pct|16|254|1.5734|1.3108|0.2627|2.8338|0.6297|0.1115|INSUFFICIENT_SAMPLE|
|return_30m_pct|13|241|1.9108|2.1488|-0.2379|2.1479|0.9669|0.1021|INSUFFICIENT_SAMPLE|
|return_60m_pct|16|239|5.5831|1.7544|3.8287|4.9700|1.0286|0.4448|INSUFFICIENT_SAMPLE|
|return_120m_pct|13|230|3.6789|2.4030|1.2760|2.7153|1.7324|0.0849|INSUFFICIENT_SAMPLE|
|range_15m_pct|16|254|4.9278|3.7559|1.1719|7.3326|3.9955|0.3999|INSUFFICIENT_SAMPLE|
|range_30m_pct|16|254|5.8086|4.6027|1.2059|9.2669|5.2272|0.5706|INSUFFICIENT_SAMPLE|
|range_60m_pct|8|172|6.8176|5.7502|1.0674|8.2705|6.3494|0.1962|INSUFFICIENT_SAMPLE|
|drawdown_from_high_60m_pct|8|172|-1.5102|-1.9499|0.4397|-3.5474|-2.8009|0.0480|INSUFFICIENT_SAMPLE|
|drawdown30_pct|16|254|-2.3809|-1.3586|-1.0223|-2.9056|-2.0625|-0.1506|INSUFFICIENT_SAMPLE|
|position30|16|254|0.6978|0.6962|0.0017|0.5986|0.5877|0.0194|INSUFFICIENT_SAMPLE|
|trade_value_ratio|8|165|1.7672|2.0516|-0.2844|3.0900|3.3104|0.0182|INSUFFICIENT_SAMPLE|
|trade_value_acceleration|16|254|1.7649|1.6767|0.0881|6.5800|6.5864|0.0423|INSUFFICIENT_SAMPLE|
|ma5_ma20_ratio|16|254|1.0082|1.0073|0.0009|1.0179|1.0028|0.1983|INSUFFICIENT_SAMPLE|
|ma20_slope_5m_pct|16|254|0.4775|0.4194|0.0581|0.8411|0.1834|0.2569|INSUFFICIENT_SAMPLE|
|prior_high_breakout|8|170|0.0000|0.0000|0.0000|0.3750|0.1176|0.2574|INSUFFICIENT_SAMPLE|
|alt_relative_60m_pct|16|239|5.8459|1.3269|4.5190|5.0530|0.9223|0.4550|INSUFFICIENT_SAMPLE|
|btc_relative_60m_pct|16|239|5.6807|1.5254|4.1552|4.8621|0.9646|0.4320|INSUFFICIENT_SAMPLE|
|exploratory_value5_prior25_ratio|16|254|2.1105|2.2109|-0.1005|7.5881|3.6019|0.0295|INSUFFICIENT_SAMPLE|
|exploratory_value15_prior15_ratio|16|254|1.9825|1.8070|0.1755|7.9536|3.1137|0.0162|INSUFFICIENT_SAMPLE|

## L2 / first7d

{'signals': 347, 'success': 14, 'failure': 223, 'unknown': 110, 'rate_pct': 5.9071729957805905}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|14|223|-0.4108|0.1148|-0.5256|1.2659|0.2859|-0.0721|INSUFFICIENT_SAMPLE|
|return_15m_pct|14|223|0.9001|0.9934|-0.0933|2.5585|0.4994|0.0551|INSUFFICIENT_SAMPLE|
|return_30m_pct|12|213|0.6092|1.4925|-0.8834|0.4617|0.7221|-0.0556|INSUFFICIENT_SAMPLE|
|return_60m_pct|14|211|2.6600|1.1011|1.5589|2.9542|0.8101|0.1879|INSUFFICIENT_SAMPLE|
|return_120m_pct|11|207|0.6944|1.7956|-1.1011|-0.9290|1.4722|-0.2499|INSUFFICIENT_SAMPLE|
|range_15m_pct|14|223|4.2609|4.0625|0.1984|7.1752|4.3212|0.2197|INSUFFICIENT_SAMPLE|
|range_30m_pct|14|223|5.7191|4.7126|1.0064|8.3956|5.3119|0.3613|INSUFFICIENT_SAMPLE|
|range_60m_pct|7|161|6.5150|6.0143|0.5007|7.9300|6.6496|0.0470|INSUFFICIENT_SAMPLE|
|drawdown_from_high_60m_pct|7|161|-2.9126|-2.7778|-0.1348|-4.2414|-3.0818|-0.0488|INSUFFICIENT_SAMPLE|
|drawdown30_pct|14|223|-3.0767|-1.9231|-1.1536|-3.0005|-2.2367|-0.1701|INSUFFICIENT_SAMPLE|
|position30|14|223|0.5651|0.6000|-0.0349|0.5099|0.5485|-0.0647|INSUFFICIENT_SAMPLE|
|trade_value_ratio|7|154|1.8026|1.9551|-0.1525|3.1430|3.3299|0.0056|INSUFFICIENT_SAMPLE|
|trade_value_acceleration|14|223|3.1248|1.7967|1.3281|5.9577|6.6256|0.1224|INSUFFICIENT_SAMPLE|
|ma5_ma20_ratio|14|223|1.0066|1.0062|0.0004|1.0167|1.0021|0.1083|INSUFFICIENT_SAMPLE|
|ma20_slope_5m_pct|14|223|0.4255|0.3043|0.1212|0.7799|0.1269|0.1781|INSUFFICIENT_SAMPLE|
|prior_high_breakout|7|159|0.0000|0.0000|0.0000|0.2857|0.1132|0.1725|INSUFFICIENT_SAMPLE|
|alt_relative_60m_pct|14|211|2.3712|0.9443|1.4268|3.0090|0.8220|0.1842|INSUFFICIENT_SAMPLE|
|btc_relative_60m_pct|14|211|2.6285|1.0875|1.5409|2.8916|0.8025|0.1794|INSUFFICIENT_SAMPLE|
|exploratory_value5_prior25_ratio|14|223|2.1105|2.4161|-0.3056|8.5659|3.7365|0.1083|INSUFFICIENT_SAMPLE|
|exploratory_value15_prior15_ratio|14|223|1.8855|1.7293|0.1561|8.7169|2.9210|0.0634|INSUFFICIENT_SAMPLE|

## L2 / last7d

{'signals': 175, 'success': 12, 'failure': 104, 'unknown': 59, 'rate_pct': 10.344827586206897}

|feature|success N|failure N|success 중앙값|failure 중앙값|차이|success 평균|failure 평균|Cliff delta|상태|
|---|---|---|---|---|---|---|---|---|---|
|return_5m_pct|12|104|1.2017|0.6688|0.5329|1.3356|0.7515|0.1210|INSUFFICIENT_SAMPLE|
|return_15m_pct|12|104|2.2640|1.6291|0.6349|1.2964|1.2781|0.0657|INSUFFICIENT_SAMPLE|
|return_30m_pct|11|100|2.3864|2.7431|-0.3567|2.5469|1.7526|0.0836|INSUFFICIENT_SAMPLE|
|return_60m_pct|12|100|4.5629|2.4745|2.0883|3.6838|1.4060|0.3067|INSUFFICIENT_SAMPLE|
|return_120m_pct|12|94|3.9481|3.1555|0.7926|4.1421|2.2400|0.1631|INSUFFICIENT_SAMPLE|
|range_15m_pct|12|104|5.1018|3.7489|1.3529|5.4843|4.1511|0.4615|INSUFFICIENT_SAMPLE|
|range_30m_pct|12|104|5.3099|4.5889|0.7210|7.0851|5.6062|0.3966|INSUFFICIENT_SAMPLE|
|range_60m_pct|9|70|6.5831|5.3275|1.2555|7.3189|6.2549|0.3492|INSUFFICIENT_SAMPLE|
|drawdown_from_high_60m_pct|9|70|-1.8519|-1.1674|-0.6845|-2.7046|-2.4016|-0.0889|INSUFFICIENT_SAMPLE|
|drawdown30_pct|12|104|-1.7196|-1.0731|-0.6465|-2.4160|-1.8890|-0.1514|INSUFFICIENT_SAMPLE|
|position30|12|104|0.7350|0.7922|-0.0572|0.6149|0.6397|-0.0801|INSUFFICIENT_SAMPLE|
|trade_value_ratio|9|70|4.3946|2.5136|1.8810|4.3496|3.6752|0.1365|INSUFFICIENT_SAMPLE|
|trade_value_acceleration|12|104|1.1716|1.6553|-0.4837|4.4793|7.9034|-0.1538|INSUFFICIENT_SAMPLE|
|ma5_ma20_ratio|12|104|1.0051|1.0086|-0.0035|1.0048|1.0062|-0.0288|INSUFFICIENT_SAMPLE|
|ma20_slope_5m_pct|12|104|0.4199|0.4921|-0.0722|0.2426|0.2936|-0.0144|INSUFFICIENT_SAMPLE|
|prior_high_breakout|9|70|0.0000|0.0000|0.0000|0.2222|0.1286|0.0937|INSUFFICIENT_SAMPLE|
|alt_relative_60m_pct|12|100|4.8517|1.3771|3.4746|3.8439|1.0948|0.3400|INSUFFICIENT_SAMPLE|
|btc_relative_60m_pct|12|100|4.7032|1.7699|2.9333|3.6944|1.2322|0.3267|INSUFFICIENT_SAMPLE|
|exploratory_value5_prior25_ratio|12|104|3.7485|2.2239|1.5246|4.7338|4.3713|0.0609|INSUFFICIENT_SAMPLE|
|exploratory_value15_prior15_ratio|12|104|2.9678|2.2433|0.7244|3.2757|3.6295|0.0817|INSUFFICIENT_SAMPLE|
