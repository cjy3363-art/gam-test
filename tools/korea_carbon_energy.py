# -*- coding: utf-8 -*-
"""한국은 탄소를 얼마나 배출할까? — 대한민국 CO₂ 배출량과 재생에너지 발전 (2000~2024).

build_topics.py 가 불러서 다른 주제와 함께 만든다. 목록에서는 '얼마나 오래 사나'
(life) 칸을 지우고 그 자리에 들어간다. 이 파일만 따로 돌려
topics/korea-carbon-energy.json 하나만 만들 수도 있다.

**모든 숫자는 raw/ 의 OWID 원본 CSV에서 계산합니다.** 빈 값은 빼고 세며,
필요한 나라 · 연도가 비어 있으면 다른 해로 대신하지 않고 '계산 불가'로 멈춥니다.
- co2 : 토지이용 변화를 뺀 화석연료 · 산업 공정 CO₂, 백만 톤(Mt). 전체 온실가스가 아니다.
- co2_per_capita : 1인당 CO₂, 톤/인.
- renewables_electricity_share_pct : 전체 발전량 중 재생에너지 비율(%). 이미 % 라 100을
  곱하지 않는다. 1차 에너지 비율 · 저탄소(원자력 포함) 비율로 대신하지 않는다.
(단위 · 정의는 OWID 공식 코드북 기준. 에너지 코드북은 같은 지표를 renewables_share_elec 로 적는다)

실행 (저장소 최상위에서):
    python tools/korea_carbon_energy.py
"""
from __future__ import annotations

import csv
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
TID = "korea-carbon-energy"
REPLACES = "life"                                # 목록에서 이 칸을 지우고 그 자리에 넣는다
CO2_FILE = "korea-co2-emissions.csv"
ENERGY_FILE = "korea-energy-use.csv"
CO2 = "co2"
PER = "co2_per_capita"
RENEW = "renewables_electricity_share_pct"


def series(fname: str, cc: str, col: str, raw: Path = RAW) -> dict[int, Decimal]:
    """iso_code 가 cc 인 행에서 연도 → 값. 열이 없으면 지표를 추측하지 않고 멈추고,
    같은 해가 두 번 나오면 하나를 고르지 않고 멈춘다. 빈 값은 관측치로 치지 않는다."""
    reader = csv.DictReader(io.open(raw / fname, encoding="utf-8"))
    missing = [c for c in ("country", "iso_code", "year", col) if c not in reader.fieldnames]
    if missing:
        raise ValueError(f"계산 불가: {fname} 에 {', '.join(missing)} 열이 없습니다")
    out: dict[int, Decimal] = {}
    seen = set()
    for r in reader:
        y = int(r["year"])
        if r["iso_code"] != cc or not START <= y <= END:
            continue
        if y in seen:
            raise ValueError(f"판정 불가: {fname} {cc} {y}년 행이 두 번 있습니다")
        seen.add(y)
        if r[col].strip():
            out[y] = Decimal(r[col])             # 원본 소수점을 그대로 유지
    return out


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
    """소수 첫째 자리에서 사사오입해 정수로 (음수는 절댓값 기준으로 반올림)."""
    return int(x.quantize(Decimal(1), ROUND_HALF_UP))


def korea_carbon_energy(raw: Path = RAW) -> dict:
    co2 = series(CO2_FILE, "KOR", CO2, raw)
    per = series(CO2_FILE, "KOR", PER, raw)
    per_j = series(CO2_FILE, "JPN", PER, raw)
    renew = series(ENERGY_FILE, "KOR", RENEW, raw)
    gaps = [y for y in range(START, END + 1) if y not in co2]
    if gaps:
        raise ValueError(f"계산 불가: 대한민국 CO₂ 배출량 {', '.join(map(str, gaps))}년 값이 없습니다")

    e0, e1 = co2[START], co2[END]
    if e0 == 0:
        raise ValueError(f"계산 불가: {START}년 CO₂ 배출량이 0입니다")
    p1 = need(per, END, "대한민국 1인당 CO₂")
    pj = need(per_j, END, "일본 1인당 CO₂")
    r1 = need(renew, END, "대한민국 재생에너지 발전 비율")

    # 반올림은 마지막 결과에만 한다. 최댓값 비교는 원본 값 그대로 한다
    change = whole((e1 - e0) / e0 * 100)             # 1번 · % (감소면 음수)
    per_n = whole(p1)                                # 2번 · 톤/인
    top_y = only(co2, max, "대한민국 CO₂ 배출량 최댓값")
    renew_n = whole(r1)                              # 4번 · %
    gap = whole(abs(p1 - pj))                        # 5번 · 톤/인 (같은 2024년끼리)

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다.
        값 순서로 놓으므로 정답 자리는 문항마다 달라진다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    near = lambda a, step, lo=0: [a + step * k for k in range(-3, 4) if a + step * k > lo]
    c1_opts = with_decoys("c1", change, [change + 15 * k for k in range(-3, 4)])   # 음수 허용
    c2_opts = with_decoys("c2", per_n, near(per_n, 3))
    c3_opts = with_decoys("c3", top_y, co2)
    c4_opts = with_decoys("c4", renew_n, [v for v in near(renew_n, 7) if v < 100])
    c5_opts = with_decoys("c5", gap, near(gap, 2, -1))

    def choice(qid, text, options, answer, basis, why):
        assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
        assert len(set(options)) == 4, f"{qid}: 보기가 4개가 아니거나 겹칩니다"
        return {"id": qid, "type": "choice", "text": text, "options": options,
                "answer": answer, "basis": basis, "why": why}

    signed = lambda v: f"{v:+d}%" if v else "0%"
    ton = lambda v: f"{v}톤"
    yr = lambda v: f"{v}년"
    OWID = "Our World in Data"

    questions = [
        choice("c1", f"{START}년 대비 {END}년 대한민국의 연간 CO₂ 배출량은 약 몇 % 변했을까요? "
               "(단위: %, 정수, 화석연료 및 산업 공정에서 발생한 영토 기준 CO₂ 배출량)",
               [signed(v) for v in c1_opts], signed(change),
               f"{OWID} CO₂ 데이터의 '{CO2}'(토지이용 변화 제외 CO₂, 백만 톤) 기준으로 대한민국(KOR)의 "
               f"(({END}년 값 − {START}년 값) ÷ {START}년 값) × 100을 반올림 없이 계산한 뒤 소수 첫째 "
               "자리에서 반올림하고, 증가는 +, 감소는 −로 표시했다.",
               f"대한민국 CO₂ 배출량은 {START}년 {e0}백만 톤, {END}년 {e1}백만 톤으로 "
               f"({e1} − {e0}) ÷ {e0} × 100 = {(e1 - e0) / e0 * 100:.2f}%, 정수로 {signed(change)}입니다. "
               "전체 온실가스가 아니라 CO₂만의 배출량입니다."),
        choice("c2", f"{END}년 대한민국의 1인당 연간 CO₂ 배출량은 약 몇 톤이었을까요? (단위: 톤/인, 정수)",
               [ton(v) for v in c2_opts], ton(per_n),
               f"{OWID} CO₂ 데이터의 '{PER}'(톤/인) 열에서 대한민국(KOR) {END}년 값을 그대로 읽어 소수 "
               "첫째 자리에서 반올림했다.",
               f"원본에 적힌 {END}년 대한민국 1인당 CO₂ 배출량은 {p1}톤으로, 정수로 반올림하면 약 "
               f"{ton(per_n)}입니다. 나라 전체 배출량을 인구로 나눈 값입니다."),
        choice("c3", f"{START}~{END}년 중 대한민국의 연간 CO₂ 배출량이 가장 많았던 해는 언제일까요? "
               "(단위: 연도)",
               [yr(v) for v in c3_opts], yr(top_y),
               f"{OWID} CO₂ 데이터의 '{CO2}'(백만 톤) 기준으로 {START}~{END}년 대한민국(KOR) {len(co2)}개 "
               "연도의 원본 값을 반올림 없이 비교해 최댓값을 기록한 해를 찾았다.",
               f"{top_y}년 {co2[top_y]}백만 톤이 {len(co2)}개 연도 중 가장 많았고, {END}년은 "
               f"{e1}백만 톤이었습니다."),
        choice("c4", f"{END}년 대한민국의 전체 전력 생산량 중 재생에너지 발전 비율은 약 몇 %였을까요? "
               "(단위: %, 정수)",
               [f"{v}%" for v in c4_opts], f"{renew_n}%",
               f"{OWID} 에너지 데이터의 '{RENEW}'(전체 발전량 중 재생에너지 발전 비율, %) 열에서 "
               f"대한민국(KOR) {END}년 값을 그대로 읽어 소수 첫째 자리에서 반올림했다.",
               f"원본에 적힌 {END}년 대한민국의 재생에너지 발전 비율은 {r1}%로, 정수로 반올림하면 약 "
               f"{renew_n}%입니다. 전체 전력 생산량을 분모로 한 비율이며, 1차 에너지 전체 중 비율이나 "
               "원자력을 포함한 저탄소 전력 비율과는 다릅니다."),
        choice("c5", f"{END}년 대한민국과 일본의 1인당 연간 CO₂ 배출량 차이는 약 몇 톤이었을까요? "
               "(단위: 톤/인, 정수)",
               [ton(v) for v in c5_opts], ton(gap),
               f"{OWID} CO₂ 데이터의 '{PER}'(톤/인) 기준으로 같은 {END}년의 |대한민국 값 − 일본 값|을 "
               "반올림 없이 계산한 뒤 소수 첫째 자리에서 반올림했다.",
               f"{END}년 1인당 CO₂ 배출량은 대한민국 {p1}톤, 일본 {pj}톤으로 |{p1} − {pj}| = "
               f"{abs(p1 - pj)}, 정수로 약 {ton(gap)}입니다. "
               + ("대한민국이 더 많습니다." if p1 > pj else "일본이 더 많습니다.")),
    ]

    caveat = (
        "Our World in Data가 정리한 값입니다. CO₂ 배출량은 화석연료 연소와 시멘트 등 산업 공정에서 "
        "나온 CO₂(토지이용 변화 제외, 영토 기준)로, 메탄 등을 합친 전체 온실가스와는 다릅니다. "
        "재생에너지 발전 비율은 Ember · Energy Institute 자료를 바탕으로 전체 발전량 중 비율이며, "
        "원자력은 들어가지 않습니다. 최근 연도 값은 나중에 고쳐질 수 있어 정부 발표 통계와 다를 수 "
        "있습니다. 화면의 숫자는 정수로 반올림해 보여 줍니다.")

    return {"id": TID, "emoji": "🌱", "title": "한국은 탄소를 얼마나 배출할까?",
            "blurb": f"{START}년부터 {END}년 CO₂ 배출과 재생에너지 발전",
            "source": "Our World in Data",
            "source_url": "https://ourworldindata.org/co2-and-greenhouse-gas-emissions",
            "caveat": caveat,
            "questions": questions}


def main() -> None:
    """이 주제 하나만 만든다. 다른 주제 파일은 건드리지 않는다."""
    t = korea_carbon_energy()           # 계산 · 검증이 하나라도 실패하면 여기서 멈춰 아무것도 쓰지 않는다
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
        print(f"    [{q['type'][:6]:<6}] {q['answer']:<8} {q['basis']}")


if __name__ == "__main__":
    main()
