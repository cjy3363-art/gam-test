# -*- coding: utf-8 -*-
"""한국 물가는 얼마나 올랐을까? — 대한민국 소비자물가와 화폐 구매력 (2000~2024).

build_topics.py 가 불러서 다른 주제와 함께 만든다. 목록에서는 '원달러 환율 26년'
(usdkrw, 1999년부터의 Frankfurter 환율) 칸을 지우고 그 자리에 들어간다. 이 파일만
따로 돌려 topics/korea-inflation-purchasing-power.json 하나만 만들 수도 있다.

**모든 숫자는 raw/ 의 World Bank 원본에서 계산합니다.** null 은 빼고 세며,
필요한 연도가 비어 있으면 다른 해로 대신하지 않고 '계산 불가'로 멈춥니다.
누적 상승률은 두 해의 CPI 비율로 구하며, 연간 상승률을 더하지 않습니다.
미국 파일도 받아 두었지만 이 주제의 계산에는 쓰지 않습니다.

실행 (저장소 최상위에서):
    python tools/korea_inflation.py
"""
from __future__ import annotations

import io
import json
import random
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent          # tools/
APP = HERE.parent
RAW = APP / "data" / "raw"
OUT = APP / "topics"

START, END = 2000, 2024
TID = "korea-inflation-purchasing-power"
REPLACES = "usdkrw"                              # 목록에서 이 칸을 지우고 그 자리에 넣는다
CPI = "FP.CPI.TOTL"             # 소비자물가지수 (2010 = 100)
INF = "FP.CPI.TOTL.ZG"          # 연간 소비자물가 상승률 (%)
TEN = 10                        # 4번 · 10만 원


def name(cc: str, code: str) -> str:
    return f"korea-cpi_{cc}_{code}_{START}_{END}.json"


def series(raw: Path, cc: str, code: str) -> dict[int, Decimal]:
    """메타데이터와 관측값을 나눠 읽고, 국가 · 지표 · 연도가 맞는 값만 쓴다.
    같은 해가 두 번 나오면 하나를 고르지 않고 멈춘다."""
    meta, rows = json.load(io.open(raw / name(cc, code), encoding="utf-8"))
    out: dict[int, Decimal] = {}
    for r in rows:
        if r["countryiso3code"] != cc or r["indicator"]["id"] != code:
            continue
        y = int(r["date"])
        if r["value"] is None or not START <= y <= END:
            continue
        if y in out:
            raise ValueError(f"판정 불가: {cc} {code} {y}년 값이 원본에 두 번 있습니다")
        out[y] = Decimal(repr(r["value"]))       # 원본 소수점을 그대로 유지
    return out


def label(raw: Path, cc: str, code: str) -> str:
    """원본에 적힌 지표 이름 — CPI 기준 연도(2010 = 100)를 여기서 확인한다."""
    return json.load(io.open(raw / name(cc, code), encoding="utf-8"))[1][0]["indicator"]["value"]


def need(s: dict[int, Decimal], year: int, what: str) -> Decimal:
    if year not in s:
        raise ValueError(f"계산 불가: {what} {year}년 값이 원본에 없습니다")
    return s[year]


def only(s: dict, pick, what: str):
    """최솟값 · 최댓값이 나온 키. 같은 값이 여럿이면 하나를 고르지 않고 멈춘다."""
    best = pick(s.values())
    hits = sorted(k for k, v in s.items() if v == best)
    if len(hits) > 1:
        raise ValueError(f"판정 불가: {what}이 {', '.join(map(str, hits))}에서 같은 값({best})입니다")
    return hits[0]


def whole(x: Decimal) -> int:
    """소수 첫째 자리에서 사사오입해 정수로."""
    return int(x.quantize(Decimal(1), ROUND_HALF_UP))


def nonzero(v: int, what: str) -> int:
    if v == 0:
        raise ValueError(f"판정 불가: {what}이 반올림하면 0이 되어 문항 뜻이 흐려집니다")
    return v


def korea_inflation(raw: Path = RAW) -> dict:
    base = label(raw, "KOR", CPI)
    if "2010 = 100" not in base:
        raise ValueError(f"계산 불가: CPI 기준이 2010 = 100 이 아닙니다 ({base})")
    cpi = series(raw, "KOR", CPI)
    inf = series(raw, "KOR", INF)
    inf_j = series(raw, "JPN", INF)

    c0 = need(cpi, START, "대한민국 CPI")
    c14 = need(cpi, 2014, "대한민국 CPI")
    c04 = need(cpi, 2004, "대한민국 CPI")
    c1 = need(cpi, END, "대한민국 CPI")
    k1, j1 = need(inf, END, "대한민국 물가상승률"), need(inf_j, END, "일본 물가상승률")

    # 반올림은 마지막 결과에만 한다. 최댓값 비교는 원본 값 그대로 한다
    cum = nonzero(whole((c1 / c0 - 1) * 100), "1번 누적 상승률")
    cum10 = nonzero(whole((c1 / c14 - 1) * 100), "2번 누적 상승률")
    top_y = only(inf, max, "대한민국 연간 물가상승률 최댓값")
    worth = nonzero(whole(TEN * c1 / c04), "4번 환산 금액")
    if k1 == j1:
        raise ValueError(f"판정 불가: {END}년 대한민국과 일본 물가상승률이 같습니다({k1})")
    higher = "대한민국" if k1 > j1 else "일본"
    diff = abs(k1 - j1)
    bands = ["대한민국이 1%p 이상 높았다", "대한민국이 1%p 미만 높았다",
             "일본이 1%p 미만 높았다", "일본이 1%p 이상 높았다"]
    q5 = bands[(0 if diff >= 1 else 1) if higher == "대한민국" else (2 if diff < 1 else 3)]

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다.
        값 순서로 놓으므로 정답 자리는 문항마다 달라진다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    # 수치 문항의 오답은 정답에서 일정 간격씩 떨어진 정수 중에서 뽑는다
    p1_opts = with_decoys("p1", cum, [cum + 20 * k for k in range(-3, 4) if cum + 20 * k > 0])
    p2_opts = with_decoys("p2", cum10, [cum10 + 10 * k for k in range(-3, 4) if cum10 + 10 * k > 0])
    p3_opts = with_decoys("p3", top_y, inf)
    p4_opts = with_decoys("p4", worth, [worth + 2 * k for k in range(-3, 4) if worth + 2 * k > TEN])

    def choice(qid, text, options, answer, basis, why):
        assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
        assert len(set(options)) == 4, f"{qid}: 보기가 4개가 아니거나 겹칩니다"
        return {"id": qid, "type": "choice", "text": text, "options": options,
                "answer": answer, "basis": basis, "why": why}

    pct = lambda v: f"{v}%"
    yr = lambda v: f"{v}년"
    man = lambda v: f"{v}만 원"
    WB = "World Bank WDI"

    questions = [
        choice("p1", f"{START}년부터 {END}년까지 대한민국의 소비자물가는 누적 약 몇 % 상승했을까요? "
               "(단위: %, 정수)",
               [pct(v) for v in p1_opts], pct(cum),
               f"{WB} 소비자물가지수({CPI}, 2010 = 100) 기준으로 대한민국의 ({END}년 CPI ÷ {START}년 "
               "CPI − 1) × 100을 반올림 없이 계산한 뒤 소수 첫째 자리에서 반올림했다.",
               f"{START}년과 {END}년 대한민국 소비자물가지수의 비율로 계산하면 {END}년 물가는 "
               f"{START}년보다 약 {pct(cum)} 높습니다. 해마다의 상승률을 더한 값이 아니라 두 해의 "
               "지수를 나눈 값입니다."),
        choice("p2", f"2014년부터 {END}년까지 대한민국의 소비자물가는 누적 약 몇 % 상승했을까요? "
               "(단위: %, 정수)",
               [pct(v) for v in p2_opts], pct(cum10),
               f"{WB} 소비자물가지수({CPI}, 2010 = 100) 기준으로 대한민국의 ({END}년 CPI ÷ 2014년 "
               "CPI − 1) × 100을 반올림 없이 계산한 뒤 소수 첫째 자리에서 반올림했다.",
               f"2014년과 {END}년 대한민국 소비자물가지수의 비율로 계산하면 {END}년 물가는 "
               f"2014년보다 약 {pct(cum10)} 높습니다. {START}년부터 따지면 약 {pct(cum)}입니다."),
        choice("p3", f"{START}~{END}년 중 대한민국의 연간 소비자물가 상승률이 가장 높았던 해는 "
               "언제일까요? (단위: 연도)",
               [yr(v) for v in p3_opts], yr(top_y),
               f"{WB} 연간 소비자물가 상승률({INF}, %) 기준으로 {START}~{END}년 대한민국 값이 있는 "
               f"{len(inf)}개 연도의 원본 값을 반올림 없이 비교해 최댓값을 기록한 해를 찾았다.",
               f"World Bank 연간 상승률 원본 값으로 비교하면 {top_y}년 약 {whole(inf[top_y])}%가 "
               f"{len(inf)}개 연도 중 가장 높았고, {END}년은 약 {whole(k1)}%였습니다."),
        choice("p4", f"2004년의 {TEN}만 원은 {END}년 소비자물가 기준으로 약 몇만 원에 해당할까요? "
               "(단위: 만 원, 정수)",
               [man(v) for v in p4_opts], man(worth),
               f"{WB} 소비자물가지수({CPI}, 2010 = 100) 기준으로 대한민국의 {TEN}만 원 × ({END}년 CPI "
               "÷ 2004년 CPI)를 반올림 없이 계산한 뒤 만 원 단위 정수로 반올림했다.",
               f"2004년과 {END}년 대한민국 소비자물가지수의 비율을 곱하면 2004년 {TEN}만 원과 같은 "
               f"물가 수준의 금액은 {END}년 약 {man(worth)}입니다. 물가 지수로 환산한 값이며, 특정 "
               "상품 가격이나 소득이 그만큼 늘었다는 뜻은 아닙니다."),
        choice("p5", f"{END}년 대한민국과 일본 중 연간 소비자물가 상승률이 더 높았던 나라는 어디이며, "
               "차이는 어느 정도였을까요?",
               bands, q5,
               f"{WB} 연간 소비자물가 상승률({INF}, %) 기준으로 같은 {END}년의 대한민국 값과 일본 값을 "
               "반올림 없이 비교해 더 높은 나라를 찾고, 두 값의 차이(%p)가 1%p 이상인지 판정했다.",
               f"{END}년 연간 소비자물가 상승률을 원본 값으로 비교하면 {higher}이 더 높았고, 두 나라의 "
               f"차이는 {'1%p 이상' if diff >= 1 else '1%p 미만(정수로 반올림하면 0%p)'}이었습니다."),
    ]

    upd = sorted({json.load(io.open(raw / name(cc, code), encoding="utf-8"))[0]["lastupdated"]
                  for cc, code in (("KOR", CPI), ("KOR", INF), ("JPN", INF))})
    caveat = (
        f"World Bank 공표치이며 World Bank 갱신일 {', '.join(upd)} 기준으로 받은 값입니다. "
        "소비자물가지수는 2010년을 100으로 둔 지수이고, 연간 상승률은 World Bank가 따로 낸 "
        "지표입니다. 누적 상승률과 화폐 환산은 같은 나라의 두 해 지수 비율로 계산했으며, 나라 "
        "사이에서는 지수 수준이 아니라 연간 상승률만 비교했습니다. 화면의 숫자는 정수로 반올림해 "
        "보여 줍니다. 통계청 발표와 조금 다를 수 있습니다.")

    return {"id": TID, "emoji": "📈", "title": "한국 물가는 얼마나 올랐을까?",
            "blurb": f"{START}년부터 {END}년 소비자물가와 화폐 구매력",
            "source": "World Bank Open Data · WDI", "source_url": "https://data.worldbank.org/",
            "caveat": caveat,
            "questions": questions}


def main() -> None:
    """이 주제 하나만 만든다. 다른 주제 파일은 건드리지 않는다."""
    t = korea_inflation()               # 계산 · 검증이 하나라도 실패하면 여기서 멈춰 아무것도 쓰지 않는다
    pack = {k: t[k] for k in ("id", "emoji", "title", "blurb",
                              "source", "source_url", "caveat")}
    pack["questions"] = t["questions"]
    OUT.mkdir(parents=True, exist_ok=True)
    io.open(OUT / f"{TID}.json", "w", encoding="utf-8").write(
        json.dumps(pack, ensure_ascii=False, indent=2))

    # 주제 목록에서는 REPLACES 칸을 이 주제로 바꾼다. 나머지는 그대로 둔다
    index = json.load(io.open(APP / "topics.json", encoding="utf-8"))
    entry = {k: t[k] for k in ("id", "emoji", "title", "blurb", "source")}
    ids = [x["id"] for x in index["topics"]]
    if TID in ids:
        index["topics"][ids.index(TID)] = entry
    elif REPLACES in ids:
        index["topics"][ids.index(REPLACES)] = entry
    else:
        index["topics"].append(entry)
    io.open(APP / "topics.json", "w", encoding="utf-8").write(
        json.dumps(index, ensure_ascii=False, indent=2))

    print(f"{t['emoji']} {t['title']}  → {OUT / f'{TID}.json'}")
    for q in t["questions"]:
        print(f"    [{q['type'][:6]:<6}] {q['answer']:<10} {q['basis']}")


if __name__ == "__main__":
    main()
