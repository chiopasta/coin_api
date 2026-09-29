# V2 수정 정책 검증

coverage 100%, 최소 유효 표본 20

t0는 사후 관측 저점입니다. target_time은 목표 고가를 확인한 봉의 마감 시각이며 t0 후보에서 그 봉을 제외합니다.
원본 event는 보존하고, 가격 흐름 episode·유형별 최초 목표 도달 event를 먼저 대표로 고른 뒤 동일 품질 정책을 적용합니다.
일부 누락이 허용된 대조군은 관측된 급등이 없다는 뜻이며, 누락 중 급등하지 않았음을 보장하지 않습니다.

고유 episode 46; 유효 표본 부족 통계행 240/240

| 유형 | raw | 품질 적격 raw | 대표 | 품질 적격 대표 | 주 매칭 | 주 % | 보조 매칭 | 보조 % |
|---|---|---|---|---|---|---|---|---|
| A | 47 | 6 | 44 | 6 | 5 | 83.333 | 6 | 100.000 |
| B | 12 | 0 | 12 | 0 | 0 | NULL | 0 | NULL |

## Episode

수익률은 시작 가격 대비 종료 종가입니다. low/high 범위 상승률과 구분합니다. t0는 episode 시작 이전일 수도 있으며 원본에 표시합니다.

| ID | 종목 | 시작 KST | 종료 KST | low | high | 종료 수익률 % | A | B | 대표 |
|---|---|---|---|---|---|---|---|---|---|
| 050ac345b6b83fa588a5 | KRW-ARX | 08-22 14:11 | 08-22 17:25 | 156.000 | 195.000 | 12.805 | 0 | 1 | {"B": "10907a2caa5eb7d8b6df"} |
| f8e1fb2bb40e30cf6a74 | KRW-CAP | 08-21 11:44 | 08-21 20:56 | 87.200 | 101.000 | 8.503 | 1 | 0 | {"A": "03d0008fa73dd1a49d39"} |
| 40f5bd0e0f09ee7b7669 | KRW-CFG | 08-22 14:12 | 08-22 19:04 | 176.000 | 201.000 | 4.396 | 1 | 0 | {"A": "3e6ac70420f1b360f63e"} |
| 4e6b165a5878221688bd | KRW-CHIP | 08-20 18:57 | 08-20 23:25 | 38.200 | 43.000 | 6.266 | 1 | 0 | {"A": "2891c675963dc7968ff4"} |
| 37f06bec5bccebc19cdc | KRW-DOS | 08-22 14:11 | 08-22 19:12 | 287.000 | 327.000 | 6.897 | 1 | 0 | {"A": "263879a6ff7c7deaebd3"} |
| 8868cc70586674ae1249 | KRW-ENSO | 08-22 14:12 | 08-22 19:04 | 1033.000 | 1226.000 | 9.211 | 1 | 0 | {"A": "d824bec2704f9d959a72"} |
| 64c4c05b4ce492b2205b | KRW-ETC | 08-22 14:11 | 08-22 19:03 | 10020.000 | 11450.000 | 1.589 | 1 | 0 | {"A": "3a4dcf9556e471b336df"} |
| 7bc3fd85e3494c2cece4 | KRW-EUL | 08-22 14:12 | 08-22 19:21 | 1618.000 | 1890.000 | 10.123 | 1 | 0 | {"A": "85ef6d9de6a8a1aa7075"} |
| 3088fd18767cc5d15926 | KRW-EUL | 08-22 23:33 | 08-23 09:49 | 1701.000 | 2056.000 | 6.098 | 1 | 1 | {"A": "0f9aac7ee463584a8c47", "B": "6c038f8e355656ccf572"} |
| 136080b62e45a7a54c66 | KRW-GRVT | 08-22 14:11 | 08-23 02:37 | 314.000 | 380.000 | 10.429 | 1 | 0 | {"A": "fd3bc0106d68dc0c859d"} |
| 97d21508f2b2580bb934 | KRW-HOLO | 08-22 14:12 | 08-22 19:04 | 81.500 | 93.300 | 5.861 | 1 | 0 | {"A": "a9c8536d705f38cdb0f3"} |
| da07555703ad21961683 | KRW-KAITO | 08-22 14:11 | 08-22 17:39 | 455.000 | 512.000 | 1.461 | 1 | 0 | {"A": "d7aa76026b78bde5a178"} |
| bf7b517f1233d1f3e7f9 | KRW-LA | 08-22 14:12 | 08-22 17:26 | 73.700 | 88.000 | 12.855 | 1 | 0 | {"A": "aada4b95b5583607178e"} |
| 53ba2d33dfaa38c9084d | KRW-ME | 08-22 14:11 | 08-22 19:10 | 75.000 | 94.700 | 3.691 | 1 | 0 | {"A": "6f47d23d799af066499c"} |
| 479f82981387993a6304 | KRW-MMT | 08-22 14:11 | 08-22 17:57 | 228.000 | 265.000 | 10.088 | 1 | 0 | {"A": "eace78aa32941467bb76"} |
| b4172df124e8e0288682 | KRW-NEAR | 08-22 14:12 | 08-22 19:02 | 2384.000 | 2755.000 | 9.548 | 1 | 0 | {"A": "c356c04370eda0a66833"} |
| 9450aed5402b37bcdd37 | KRW-ONDO | 08-22 14:12 | 08-22 14:17 | 475.000 | 540.000 | 7.789 | 1 | 0 | {"A": "1b8aa50ec0ec2695b84a"} |
| af7eccdd36fd447dbff6 | KRW-ONG | 08-20 20:16 | 08-20 22:35 | 81.600 | 104.000 | 15.256 | 1 | 1 | {"A": "93f1a4b2a24866baa886", "B": "1e180df96d5d06a61cba"} |
| 55c5c9ca492e308dfc90 | KRW-ONG | 08-21 08:08 | 08-21 09:53 | 99.300 | 135.000 | 27.000 | 1 | 1 | {"A": "f86045c09e2f847d66bd", "B": "5cb89d54dfd9ef6069b4"} |
| 765626b806e95bb4d588 | KRW-ONG | 08-21 09:53 | 08-21 10:57 | 124.000 | 143.000 | 6.299 | 1 | 0 | {"A": "c1c7d64c6d86f9fca329"} |
| 843b2a78b4c6ca31de92 | KRW-ONG | 08-21 11:04 | 08-21 12:37 | 127.000 | 152.000 | 11.719 | 1 | 0 | {"A": "6d0c5ca062273db91d1b"} |
| a1e39fffd26fce993c5a | KRW-ONG | 08-21 13:49 | 08-21 15:14 | 130.000 | 144.000 | 4.615 | 1 | 0 | {"A": "8c4b6c4d2d3df91a192e"} |
| bf955154ee4877364639 | KRW-ONG | 08-21 17:31 | 08-21 18:06 | 109.000 | 130.000 | 7.080 | 1 | 0 | {"A": "5450feef9b0de6d863f1"} |
| 794caa870a46c9e78bd0 | KRW-ONG | 08-22 14:11 | 08-22 14:17 | 97.300 | 116.000 | 8.000 | 1 | 0 | {"A": "d31d72ee203815fa3442"} |
| 066093c4d33f3b5aa5e5 | KRW-ONT | 08-19 00:01 | 08-21 06:01 | 52.800 | 79.200 | 37.361 | 1 | 1 | {"A": "e857afe2365aa5fd259a", "B": "c93c49e60049fbbb5ff0"} |
| 905f8e3d5482eacea99e | KRW-ONT | 08-21 08:10 | 08-21 09:44 | 64.500 | 75.300 | 8.042 | 1 | 0 | {"A": "6b4786ff8b0292718a4f"} |
| 5fba266f234d1a256bde | KRW-ONT | 08-21 11:04 | 08-21 12:37 | 70.700 | 78.800 | 3.894 | 1 | 1 | {"A": "729e79052ec6aa2eef2e", "B": "a1fed89c39ccea19750a"} |
| 971918d15c5d065b40bf | KRW-ONT | 08-22 19:15 | 08-23 13:06 | 62.700 | 77.100 | 7.087 | 1 | 1 | {"A": "ad8e9f4f8446f7c916b5", "B": "7843fe813dce88a99a5c"} |
| 3cf90f6ee6d6d93e6698 | KRW-PENGU | 08-22 14:11 | 08-22 14:17 | 10.300 | 12.000 | 5.714 | 1 | 0 | {"A": "0bcc2b8b592e441ca174"} |
| 330497e06336d9252fd1 | KRW-PIEVERSE | 08-19 23:15 | 08-21 18:01 | 1171.000 | 1522.000 | 22.704 | 1 | 0 | {"A": "e0a7770b1e794dcb392e"} |
| a493bcf8ebb6ad0ffd8b | KRW-PIEVERSE | 08-21 18:01 | 08-21 19:59 | 1406.000 | 1595.000 | 3.881 | 1 | 0 | {"A": "e1d3401af2fbe5ac4b94"} |
| 0db69bb81e3df52df69e | KRW-PIEVERSE | 08-21 20:20 | 08-22 00:52 | 1360.000 | 1656.000 | 14.348 | 1 | 1 | {"A": "43f54bed2955c4e00dbd", "B": "a12e712e6f32ddcf67ce"} |
| c45e31eabf4bc7ce28cc | KRW-PROM | 08-21 13:47 | 08-21 18:13 | 3000.000 | 3445.000 | 3.621 | 1 | 0 | {"A": "0c40b7fb897e3019fe98"} |
| 8e097601945a2636b11d | KRW-PROM | 08-22 00:54 | 08-22 01:59 | 3541.000 | 4025.000 | 0.356 | 1 | 1 | {"A": "d01e9ea419ed395147c2", "B": "1e74636279c1905b1859"} |
| 58646b1e0ba784fc91f6 | KRW-PROM | 08-22 14:11 | 08-22 15:11 | 3187.000 | 4249.000 | 17.993 | 1 | 1 | {"A": "9de85d45c8a668b7b8ec", "B": "e14d99868ff012e4673b"} |
| 5a7d5737d77f3caf2e3a | KRW-PROM | 08-23 18:53 | 08-23 22:07 | 3591.000 | 4285.000 | 6.854 | 1 | 0 | {"A": "2f36533f5647d87333b4"} |
| 4991497d1a6effd6d549 | KRW-PROM | 08-23 22:07 | 08-23 23:44 | 3882.000 | 4338.000 | 2.756 | 1 | 0 | {"A": "6492e5b29bf1bcc5ee53"} |
| 4b90b454ec30990ff306 | KRW-PUMP | 08-22 14:11 | 08-22 17:08 | 4.910 | 6.540 | 24.899 | 4 | 1 | {"A": "cc29c2eb01496df45ebf", "B": "20da6a29d5828380e52d"} |
| b48769a9870fda6f8c77 | KRW-PUMP | 08-23 13:51 | 08-23 16:47 | 6.360 | 7.430 | 10.849 | 1 | 0 | {"A": "f55f1fbdee695953e4dd"} |
| cfe27425a2455c1c61ae | KRW-RVN | 08-19 15:37 | 08-22 10:56 | 3.270 | 4.060 | 12.281 | 1 | 0 | {"A": "82fcf59310a73e2a7597"} |
| 24e87e3f9fbf16622d76 | KRW-RVN | 08-22 14:11 | 08-22 17:33 | 3.520 | 4.040 | 6.389 | 1 | 0 | {"A": "b4d81f68fb01193d1a33"} |
| 26e63ca579867d4c9c46 | KRW-RVN | 08-22 18:44 | 08-22 19:28 | 3.840 | 4.400 | 6.170 | 1 | 0 | {"A": "6e943193b18b6a9f740d"} |
| ab63a7cec2d0c05487e4 | KRW-RVN | 08-22 17:33 | 08-22 17:43 | 3.780 | 4.430 | 9.661 | 0 | 1 | {"B": "f8da5537e5dbbbd586a4"} |
| 256eefdf239619e8a3ea | KRW-SUI | 08-22 14:10 | 08-22 14:17 | 1066.000 | 1198.000 | -3.078 | 1 | 0 | {"A": "4c5c9e7aeb4e710b1f78"} |
| 0cb85bc2654866ee40e3 | KRW-UNI | 08-22 14:11 | 08-22 19:25 | 5155.000 | 5810.000 | 1.948 | 1 | 0 | {"A": "8379cd951743a8b55adb"} |
| d3536adda8ab7f39a3c8 | KRW-WLD | 08-22 14:11 | 08-22 14:23 | 479.000 | 575.000 | 5.620 | 1 | 0 | {"A": "85bbf6bffd0b653da962"} |

## 단일 특징 통계

발생률은 양쪽 값이 있는 매칭 쌍 기준입니다. 그룹별 유효 수·비율도 별도 표시하며 최소 유효 쌍 수에도 동일 기준을 적용합니다. 부족한 차이는 JSON에 참고 수치만 남깁니다.

### A / primary

| 특징 | 분 전 | 전체 사건 | 유효 사건 | 유효율 | 전체 대조 | 유효 대조 | 유효율 | 유효 쌍 | 사건 % | 대조 % | 차이 %p / 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5분 수익률 > 0 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 0.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 20.000 | 20.000 | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 20.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 80.000 | 80.000 | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 20.000 | 40.000 | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 20.000 | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 20.000 | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 0.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 5 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 20.000 | 20.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 20.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 40.000 | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 0.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 15 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 80.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 0.000 | 20.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 80.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 80.000 | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 20.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 30 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 20.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 20.000 | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 20.000 | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 20.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 60 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 100.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 80.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 80.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 20.000 | 20.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 40.000 | 40.000 | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 100.000 | 60.000 | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 80.000 | 80.000 | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 60.000 | 60.000 | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 0.000 | 20.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 120 | 6 | 6 | 1.000 | 5 | 5 | 1.000 | 5 | 80.000 | 20.000 | INSUFFICIENT_SAMPLE |

### A / auxiliary

| 특징 | 분 전 | 전체 사건 | 유효 사건 | 유효율 | 전체 대조 | 유효 대조 | 유효율 | 유효 쌍 | 사건 % | 대조 % | 차이 %p / 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5분 수익률 > 0 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 16.667 | 0.000 | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 50.000 | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 66.667 | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 66.667 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 0.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 50.000 | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 83.333 | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 16.667 | 83.333 | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 83.333 | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 66.667 | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 0.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 5 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 83.333 | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 66.667 | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 66.667 | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 66.667 | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 83.333 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 16.667 | 50.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 16.667 | 50.000 | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 50.000 | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 66.667 | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 66.667 | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 33.333 | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 0.000 | 16.667 | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 15 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 83.333 | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 50.000 | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 33.333 | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 50.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 50.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 0.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 0.000 | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 0.000 | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 33.333 | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 83.333 | 16.667 | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 33.333 | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 16.667 | 0.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 30 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 50.000 | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 66.667 | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 66.667 | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 50.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 66.667 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 16.667 | 0.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 33.333 | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 33.333 | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 66.667 | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 50.000 | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 66.667 | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 16.667 | 0.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 60 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 66.667 | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 50.000 | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 100.000 | 83.333 | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 83.333 | 66.667 | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 83.333 | 50.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 33.333 | 0.000 | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 16.667 | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 50.000 | 66.667 | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 100.000 | 83.333 | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 83.333 | 83.333 | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 66.667 | 50.000 | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 16.667 | 0.000 | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 120 | 6 | 6 | 1.000 | 6 | 6 | 1.000 | 6 | 83.333 | 50.000 | INSUFFICIENT_SAMPLE |

### B / primary

| 특징 | 분 전 | 전체 사건 | 유효 사건 | 유효율 | 전체 대조 | 유효 대조 | 유효율 | 유효 쌍 | 사건 % | 대조 % | 차이 %p / 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5분 수익률 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |

### B / auxiliary

| 특징 | 분 전 | 전체 사건 | 유효 사건 | 유효율 | 전체 대조 | 유효 대조 | 유효율 | 유효 쌍 | 사건 % | 대조 % | 차이 %p / 상태 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 5분 수익률 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 5 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 15 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 30 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 60 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 5분 수익률 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 15분 수익률 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 수익률 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금이 이전 평균의 2배 이상 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 최근 5분 거래대금 증가율 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 거래대금 가속 > 1 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 1분봉 MA5 > MA20 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| MA20의 5분 변화율 > 0 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 30분 고저폭이 이전 30분보다 증가 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 종가가 직전 60분 고점 돌파 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
| 60분 수익률이 타 종목 중앙값 초과 | 120 | 0 | 0 | NULL | 0 | 0 | NULL | 0 | NULL | NULL | INSUFFICIENT_SAMPLE |
