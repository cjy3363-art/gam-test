# -*- coding: utf-8 -*-
"""공개 데이터 내려받기 — 10주제의 원본을 raw/ 에 저장한다.

**전부 키도 로그인도 필요 없습니다.** 수업 중에 20명이 동시에 받아도 막히지
않는 곳만 골랐습니다.

한 번 받으면 raw/ 에 남으므로 다시 돌려도 새로 받지 않습니다.
(--force 를 주면 다시 받습니다)

실행 (저장소 최상위에서):
    python tools/fetch_all.py
    python tools/fetch_all.py --force
"""
from __future__ import annotations

import http.client
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 윈도우 콘솔(cp949)은 한글 · 기호를 못 찍고 멈출 때가 있다. 출력만 UTF-8 로 맞춘다
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
# HTTP 헤더는 latin-1 만 담는다. 한글을 넣으면 UnicodeEncodeError 가 난다
UA = {"User-Agent": "gam-test-class/1.0 (data analysis class)"}
TIMEOUT = 90

SEOUL = (37.5665, 126.9780)

# 날씨는 **모델을 ERA5로 못 박는다** (&models=era5).
# 모델을 적지 않으면 Open-Meteo가 그때그때 '가장 알맞은 모델'(best_match)을 골라 섞어 준다.
# 그 구성이 바뀌면 같은 주소로 받아도 지난 값이 달라진다 — 2026-10에 실제로 2024년 서울
# 열대야가 15일에서 12일로 바뀌었다. 출처에 모델까지 적어야 다시 받아도 같은 값이 나온다.
ERA5 = "&models=era5"

SOURCES: list[tuple[str, str, str]] = [
    # (저장 파일명, 설명, URL)
    ("seoul_weather.json",
     "서울 일별 기온·강수 1950~2024 (Open-Meteo Archive · ERA5 고정)",
     "https://archive-api.open-meteo.com/v1/archive"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=1950-01-01&end_date=2024-12-31"
     "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
     "&timezone=Asia%2FSeoul" + ERA5),

    ("seoul_air.json",
     "서울 시간별 미세먼지 2023~2024 (Open-Meteo Air Quality · CAMS)",
     "https://air-quality-api.open-meteo.com/v1/air-quality"
     f"?latitude={SEOUL[0]}&longitude={SEOUL[1]}"
     "&start_date=2023-01-01&end_date=2024-12-31"
     "&hourly=pm10,pm2_5&timezone=Asia%2FSeoul"),

    ("working_hours.csv",
     "연간 노동시간 (Our World in Data)",
     "https://ourworldindata.org/grapher/annual-working-hours-per-worker.csv"
     "?csvType=full&useColumnShortNames=true"),

    ("korea-working-hours.csv",
     "연간 근로시간 전체 CSV — 한국·일본·미국·독일·프랑스 비교용 (Our World in Data)",
     "https://ourworldindata.org/grapher/annual-working-hours-per-worker.csv"
     "?v=1&csvType=full&useColumnShortNames=false"),

    ("korea-meat-supply-total.csv",
     "1인당 연간 육류 공급량 전체 CSV · kg (Our World in Data · FAO 식품수급표)",
     "https://ourworldindata.org/grapher/meat-supply-per-person.csv"
     "?v=1&csvType=full&useColumnShortNames=false"),

    ("korea-meat-supply-by-type.csv",
     "1인당 연간 육류 종류별 공급량 전체 CSV · kg (Our World in Data · FAO 식품수급표)",
     "https://ourworldindata.org/grapher/per-capita-meat-consumption-by-type-kilograms-per-year.csv"
     "?v=1&csvType=full&useColumnShortNames=false"),

    ("korea-co2-emissions.csv",
     "CO₂ 배출량 전체 CSV · 전 국가 (Our World in Data owid_co2)",
     "https://catalog.ourworldindata.org/emissions/owid_co2/owid_co2.csv"),

    ("korea-energy-use.csv",
     "에너지 사용 · 발전 전체 CSV · 전 국가 (Our World in Data owid_energy)",
     "https://catalog.ourworldindata.org/energy/owid_energy/owid_energy.csv"),

    ("life_expectancy.csv",
     "기대수명 (Our World in Data)",
     "https://ourworldindata.org/grapher/life-expectancy.csv"
     "?csvType=full&useColumnShortNames=true"),

    ("wb_fertility.json",
     "합계출산율 전세계 (World Bank SP.DYN.TFRT.IN)",
     "https://api.worldbank.org/v2/country/all/indicator/SP.DYN.TFRT.IN"
     "?format=json&per_page=20000&date=1960:2023"),

    ("wb_pop_kor.json",
     "한국 인구·고령화 (World Bank)",
     "https://api.worldbank.org/v2/country/KOR/indicator/"
     "SP.POP.TOTL;SP.POP.65UP.TO.ZS;SP.URB.TOTL.IN.ZS"
     "?format=json&per_page=2000&source=2"),

    ("korea_fertility_2000_2025.json",
     "한국 합계출산율 2000~2025 (World Bank SP.DYN.TFRT.IN)",
     "https://api.worldbank.org/v2/country/KOR/indicator/SP.DYN.TFRT.IN"
     "?format=json&date=2000%3A2025&per_page=100"),

    ("korea_life_expectancy_2000_2025.json",
     "한국 기대수명 2000~2025 (World Bank SP.DYN.LE00.IN)",
     "https://api.worldbank.org/v2/country/KOR/indicator/SP.DYN.LE00.IN"
     "?format=json&date=2000%3A2025&per_page=100"),

    *[(f"korea_{fname}_2000_2024.json",
       f"한국 {kn} 2000~2024 (World Bank {code})",
       f"https://api.worldbank.org/v2/country/KOR/indicator/{code}"
       "?format=json&date=2000%3A2024&per_page=100")
      for fname, kn, code in (
          ("fertility", "합계출산율", "SP.DYN.TFRT.IN"),
          ("birth_rate", "조출생률", "SP.DYN.CBRT.IN"),
          ("population", "총인구", "SP.POP.TOTL"),
          ("population_growth", "인구증가율", "SP.POP.GROW"),
      )],

    # 소득 · 경제성장 — 5개국 × 5개 지표를 국가별 · 지표별로 따로 받는다
    *[(f"economy_{cc}_{code}_1990_2023.json",
       f"{cn} {kn} 1990~2023 (World Bank {code})",
       f"https://api.worldbank.org/v2/country/{cc}/indicator/{code}"
       "?format=json&date=1990%3A2023&per_page=100")
      for cc, cn in (("KOR", "한국"), ("JPN", "일본"), ("USA", "미국"),
                     ("DEU", "독일"), ("FRA", "프랑스"))
      for code, kn in (("NY.GDP.PCAP.CD", "1인당 명목 GDP"),
                       ("NY.GNP.PCAP.CD", "1인당 명목 GNI"),
                       ("NY.GDP.MKTP.KD.ZG", "경제성장률"),
                       ("NY.GDP.PCAP.KD", "실질 1인당 GDP"),
                       ("NY.GNP.PCAP.KD", "실질 1인당 GNI"))],

    # 고령화 · 인구구조 — 2개국 × 3개 지표를 국가별 · 지표별로 따로 받는다
    *[(f"aging_{cc}_{code}_2000_2024.json",
       f"{cn} {kn} 2000~2024 (World Bank {code})",
       f"https://api.worldbank.org/v2/country/{cc}/indicator/{code}"
       "?format=json&date=2000:2024&per_page=100")
      for cc, cn in (("KOR", "한국"), ("JPN", "일본"))
      for code, kn in (("SP.POP.65UP.TO.ZS", "65세 이상 인구 비율"),
                       ("SP.POP.65UP.TO", "65세 이상 인구수"),
                       ("SP.POP.DPND.OL", "노년부양비"))],

    # 소비자물가 · 화폐 구매력 — 3개국 × 2개 지표를 국가별 · 지표별로 따로 받는다
    *[(f"korea-cpi_{cc}_{code}_2000_2024.json",
       f"{cn} {kn} 2000~2024 (World Bank {code})",
       f"https://api.worldbank.org/v2/country/{cc}/indicator/{code}"
       "?format=json&date=2000%3A2024&per_page=100")
      for cc, cn in (("KOR", "한국"), ("JPN", "일본"), ("USA", "미국"))
      for code, kn in (("FP.CPI.TOTL", "소비자물가지수(2010=100)"),
                       ("FP.CPI.TOTL.ZG", "연간 소비자물가 상승률"))],

    ("wb_internet.json",
     "인터넷 사용률 전세계 (World Bank IT.NET.USER.ZS)",
     "https://api.worldbank.org/v2/country/all/indicator/IT.NET.USER.ZS"
     "?format=json&per_page=20000&date=1990:2023"),

    ("usdkrw.json",
     "원달러 환율 1999~ (Frankfurter · ECB)",
     "https://api.frankfurter.dev/v1/1999-01-04..2024-12-31"
     "?base=USD&symbols=KRW"),

    ("usd-krw-exchange-rate.csv",
     "원달러 일별 환율 전체 시계열 (FRED DEXKOUS · 뉴욕 정오 매입환율)",
     "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXKOUS"),

    # 가계부채 — BIS '가계 및 가계봉사 비영리단체 총신용(Adjusted for Breaks)', 분기말
    ("korea-household-debt-total.csv",
     "한국 가계부채 잔액 · 십억 원 (FRED CRDQKRAHABIS · BIS)",
     "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CRDQKRAHABIS"),

    ("korea-household-debt-gdp.csv",
     "한국 GDP 대비 가계부채 비율 · % (FRED QKRHAM770A · BIS)",
     "https://fred.stlouisfed.org/graph/fredgraph.csv?id=QKRHAM770A"),

    ("japan-household-debt-gdp.csv",
     "일본 GDP 대비 가계부채 비율 · % (FRED QJPHAM770A · BIS, 한국과 같은 기준)",
     "https://fred.stlouisfed.org/graph/fredgraph.csv?id=QJPHAM770A"),

    # 자동차 등록대수 — 국토교통부 통계누리 '자동차등록대수현황_연도별'(hRsId=58, 양식 1244).
    # 화면의 엑셀 버튼은 브라우저 안에서 파일을 만들므로, 화면이 표를 채울 때 부르는
    # 조회 요청(columns.do · data.do)을 그대로 받는다. 한 번에 5년까지만 조회되고,
    # 2000~2014년은 형식 561, 2015년부터는 형식 562 에만 값이 있다 (열 순서가 다르다).
    # 열 이름은 columns 파일에 있다. 연도별 값은 12월 말 등록대수다
    *[(f"korea-vehicle-registrations_columns_{st}.json",
       f"자동차 등록대수 연도별 열 정의 · 형식 {st} (국토교통부 통계누리)",
       f"https://stat.molit.go.kr/portal/stat/columns.do?formId=1244&styleNum={st}")
      for st in (561, 562)],
    *[(f"korea-vehicle-registrations_{st}_{a}_{a + 4}.json",
       f"자동차 등록대수 연도별 {a}~{a + 4} · 대 (국토교통부 통계누리 · 형식 {st})",
       "https://stat.molit.go.kr/portal/stat/data.do?formId=1244"
       f"&styleNum={st}&apprYn=Y&startDate={a}&endDate={a + 4}")
      for st, a in ((561, 2000), (561, 2005), (561, 2010), (562, 2015), (562, 2020))],

    # 도로교통 — 사망률(OWID · WHO)과 사망자 수(OECD/ITF)는 출처 · 정의가 다른 별개 지표다
    ("korea-road-death-rate.csv",
     "도로교통사고 사망률 · 인구 10만 명당 전체 CSV (Our World in Data · WHO GHE)",
     "https://ourworldindata.org/grapher/death-rate-from-road-accidents-ghe.csv"
     "?v=1&csvType=full&useColumnShortNames=false"),

    ("korea-road-fatalities.csv",
     "한국 도로교통사고 사망자 수 · 명 (OECD/ITF SDMX DF_TRENDSSAFETY)",
     "https://sdmx.oecd.org/public/rest/data/OECD.ITF,DSD_TRENDS@DF_TRENDSSAFETY,1.0/"
     "KOR.A.FATALITIES....?format=csvfilewithlabels"),

    ("wb_countries.json",
     "World Bank 국가 목록 — 대륙·소득군 같은 집계치를 걸러내는 데 씁니다",
     "https://api.worldbank.org/v2/country?format=json&per_page=400"),

    *[(f"city_{cid}.json", f"{cn} 일별 기온·강수 1991~2020 (Open-Meteo Archive · ERA5 고정)",
       "https://archive-api.open-meteo.com/v1/archive"
       f"?latitude={lat}&longitude={lon}"
       "&start_date=1991-01-01&end_date=2020-12-31"
       "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
       f"&timezone=auto" + ERA5)
      for cid, cn, lat, lon in (
          ("seoul", "서울", 37.5665, 126.9780),
          ("tokyo", "도쿄", 35.6895, 139.6917),
          ("london", "런던", 51.5072, -0.1276),
          ("singapore", "싱가포르", 1.3521, 103.8198),
      )],

    ("quakes.geojson",
     "규모 5.5 이상 지진 2000~2024 (USGS) — 2만건 상한에 걸리지 않는 기준",
     "https://earthquake.usgs.gov/fdsnws/event/1/query"
     "?format=geojson&starttime=2000-01-01&endtime=2024-12-31"
     "&minmagnitude=5.5&orderby=time&limit=20000"),

    ("quakes_korea.geojson",
     "한반도 주변 지진 2000~2024 (USGS · 규모 3.0 이상)",
     "https://earthquake.usgs.gov/fdsnws/event/1/query"
     "?format=geojson&starttime=2000-01-01&endtime=2024-12-31"
     "&minmagnitude=3.0&minlatitude=33&maxlatitude=39.5"
     "&minlongitude=124&maxlongitude=132&limit=20000"),
]


def get(url: str, dest: Path, tries: int = 4) -> int:
    """받는다. 잠깐의 실패면 기다렸다가 다시 시도한다.

    공개 API 는 대부분 호출 제한이 있고(429), 큰 파일은 받다가 끊기기도 한다
    (IncompleteRead · 시간 초과). 한 번 실패했다고 포기하지 말고, 간격을 늘려 가며
    다시 부른다. 주소가 틀린 것(404 같은)은 다시 불러도 소용없으니 바로 알린다.
    """
    wait = 5
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = r.read()
            dest.write_bytes(data)
            return len(data)
        except urllib.error.HTTPError as e:
            if (e.code != 429 and e.code < 500) or i == tries - 1:
                raise
            why = str(e.code)
        except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if i == tries - 1:
                raise
            why = type(e).__name__
        print(f"          {why} — {wait}초 뒤 다시 시도합니다 ({i+1}/{tries-1})")
        time.sleep(wait)
        wait *= 2
    raise RuntimeError("도달 불가")


def main() -> int:
    force = "--force" in sys.argv
    RAW.mkdir(parents=True, exist_ok=True)
    fail = 0
    for name, desc, url in SOURCES:
        dest = RAW / name
        if dest.exists() and not force:
            print(f"  건너뜀  {name:<22} 이미 있음 ({dest.stat().st_size/1024:,.0f}KB)")
            continue
        t0 = time.time()
        try:
            n = get(url, dest)
            print(f"  받음    {name:<22} {n/1024:>7,.0f}KB  {time.time()-t0:.1f}s  {desc}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as e:
            print(f"  실패    {name:<22} {e}")
            fail += 1
        time.sleep(0.4)          # 상대 서버에 예의를 지킨다

    print()
    print(f"총 {len(SOURCES)}건 / 실패 {fail}건 · 저장 위치 {RAW}")
    if fail:
        print("실패한 것은 잠시 뒤 다시 실행하면 대개 받아집니다.")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
