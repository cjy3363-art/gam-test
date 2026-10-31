# -*- coding: utf-8 -*-
"""원달러 환율 26년 — FRED DEXKOUS 일별 원·달러 환율 (2000~2024).

build_topics.py 가 불러서 다른 주제와 함께 만든다. 목록에서는 '우리는 얼마나
일하나'(working-hours) 칸을 지우고 그 자리에 들어간다. 이 파일만 따로 돌려
topics/korea-exchange-rate.json 하나만 만들 수도 있다.

**모든 숫자는 raw/ 의 FRED 원본 CSV에서 계산합니다.** 값이 빈 칸이거나 숫자가
아닌 날(휴장일 · 결측)은 빼고 세며, 0 으로 채우거나 앞뒤 값으로 메우지 않습니다.
환율은 1달러를 사는 데 드는 원화이므로, 환율이 오르면 원화 가치는 내려간 것입니다.

실행 (저장소 최상위에서):
    python tools/korea_exchange_rate.py
"""
from __future__ import annotations

import csv
import io
import json
import random
import sys
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from statistics import mean

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent          # tools/
APP = HERE.parent
RAW = APP / "data" / "raw"
OUT = APP / "topics"

START, END = 2000, 2024
TID = "korea-exchange-rate"
REPLACES = "working-hours"                       # 목록에서 이 칸을 지우고 그 자리에 넣는다
FILE = "usd-krw-exchange-rate.csv"
COL = "DEXKOUS"


def daily(raw: Path) -> dict[str, float]:
    """날짜 → 환율. 숫자로 읽히지 않는 값('.' · 빈 칸)은 관측치로 치지 않는다."""
    out = {}
    for r in csv.DictReader(io.open(raw / FILE, encoding="utf-8")):
        if not START <= int(r["observation_date"][:4]) <= END:
            continue
        try:
            out[r["observation_date"]] = float(r[COL])
        except ValueError:
            pass
    return out


def only(s: dict, pick, what: str):
    """최솟값 · 최댓값이 나온 키. 같은 값이 여럿이면 하나를 고르지 않고 멈춘다."""
    best = pick(s.values())
    hits = sorted(k for k, v in s.items() if v == best)
    if len(hits) > 1:
        raise ValueError(f"판정 불가: {what}이 {', '.join(map(str, hits))}에서 같은 값({best})입니다")
    return hits[0]


def half_up(x: float, nd: int) -> float:
    """사사오입. round() 는 0.5 를 짝수 쪽으로 보내므로 쓰지 않는다."""
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-nd), ROUND_HALF_UP))


def korea_exchange_rate(raw: Path = RAW) -> dict:
    day = daily(raw)
    by = defaultdict(dict)                           # 연도 → {날짜: 환율}
    for d, v in day.items():
        by[int(d[:4])][d] = v
    empty = [y for y in range(START, END + 1) if not by[y]]
    if empty:
        raise ValueError(f"계산 불가: {', '.join(map(str, empty))}년에 유효 관측값이 없습니다")

    avg = {y: mean(by[y].values()) for y in range(START, END + 1)}
    hi = {y: max(by[y].values()) for y in avg}
    lo = {y: min(by[y].values()) for y in avg}
    rng = {y: hi[y] - lo[y] for y in avg}
    # 연중 최고 · 최저가 나온 날짜는 설명에 쓰는 해만 하나로 정한다 (동률이면 멈춘다).
    # 2000년 최저처럼 같은 값이 두 날 나온 해도 있어, 모든 해에 미리 정하지 않는다
    hi_day = lambda y: only(by[y], max, f"{y}년 최고 환율")
    lo_day = lambda y: only(by[y], min, f"{y}년 최저 환율")

    # 반올림은 마지막 결과에만 한다
    change = half_up(avg[END] - avg[START], 0)       # 1번 · 정수
    top_avg_y = only(avg, max, "연평균 환율 최댓값")
    top_d = only(day, max, "일별 환율 최댓값")
    wide_y = only(rng, max, "연중 변동 폭 최댓값")
    last_rng = half_up(rng[END], 0)                  # 5번 · 정수

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    # 수치 문항의 오답은 정답에서 일정 간격씩 떨어진 값 중에서 뽑는다 (0원은 빼고)
    x1_opts = with_decoys("x1", change, [half_up(change + 100 * k, 0) for k in range(-3, 4)
                                         if half_up(change + 100 * k, 0) != 0])
    x2_opts = with_decoys("x2", top_avg_y, avg)
    # 날짜 오답은 다른 해의 연중 최고 환율 날짜 — 모두 원본에 값이 있는 날이다
    x3_opts = with_decoys("x3", top_d, [d for y in avg for d, v in by[y].items() if v == hi[y]])
    x4_opts = with_decoys("x4", wide_y, rng)
    x5_opts = with_decoys("x5", last_rng, [half_up(last_rng + 75 * k, 0) for k in range(-3, 4)
                                           if last_rng + 75 * k > 0])

    def choice(qid, text, options, answer, basis, why):
        assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
        assert len(set(options)) == 4, f"{qid}: 보기가 4개가 아니거나 겹칩니다"
        return {"id": qid, "type": "choice", "text": text, "options": options,
                "answer": answer, "basis": basis, "why": why}

    updown = lambda v: f"{abs(v):,.0f}원 {'상승' if v > 0 else '하락'}"
    won = lambda v: f"{v:,.0f}원"
    yr = lambda v: f"{v}년"
    n = lambda y: len(by[y])
    BASE = f"FRED DEXKOUS(뉴욕 정오 매입환율, 1달러당 원화) {START}~{END}년 유효 일별 관측값 기준으로"

    questions = [
        choice("x1", f"{START}년 대비 {END}년 대한민국의 연평균 원·달러 환율은 몇 원 상승하거나 "
               "하락했을까요? (단위: 원/달러, 정수)",
               [updown(v) for v in x1_opts], updown(change),
               f"{BASE} {END}년 연평균({n(END)}일 산술평균) − {START}년 연평균({n(START)}일 산술평균)"
               f" = {avg[END]:,.4f} − {avg[START]:,.4f}의 차이를 계산해 소수 첫째 자리에서 반올림해 정수로 나타내고, "
               "양수면 상승 · 음수면 하락으로 표시했다.",
               f"연평균 환율은 {START}년 {avg[START]:,.2f}원, {END}년 {avg[END]:,.2f}원으로 "
               f"{updown(change)}했습니다. 1달러를 사는 데 드는 원화가 "
               + ("늘었으므로 원화 가치는 달러 대비 낮아졌습니다." if change > 0 else
                  "줄었으므로 원화 가치는 달러 대비 높아졌습니다.")),
        choice("x2", f"{START}~{END}년 중 연평균 원·달러 환율이 가장 높았던 해는 언제일까요? "
               "(단위: 연도)",
               [yr(v) for v in x2_opts], yr(top_avg_y),
               f"{BASE} 연도별 일별 환율의 산술평균을 구해 {len(avg)}개 연도 중 "
               f"최댓값({avg[top_avg_y]:,.2f}원)에 해당하는 해를 찾았다.",
               f"{top_avg_y}년 연평균 환율 {avg[top_avg_y]:,.2f}원이 {len(avg)}개 연도 중 "
               f"가장 높았습니다. 연말 환율이나 특정 날짜 환율이 아니라 그해 {n(top_avg_y)}일의 "
               "평균입니다."),
        choice("x3", f"{START}~{END}년 중 일별 원·달러 환율이 가장 높았던 날짜는 언제일까요? "
               "(단위: YYYY-MM-DD)",
               x3_opts, top_d,
               f"{BASE} 유효 관측값 {len(day):,}개 중 최댓값({day[top_d]:,.2f}원)이 기록된 날짜를 "
               "찾았다.",
               f"{top_d}의 {day[top_d]:,.2f}원이 {START}~{END}년 {len(day):,}개 관측값 중 가장 "
               f"높았습니다. {END}년 최고치는 {hi_day(END)}의 {hi[END]:,.2f}원이었습니다."),
        choice("x4", f"{START}~{END}년 중 연중 원·달러 환율 변동 폭이 가장 컸던 해는 언제일까요? "
               "(단위: 연도)",
               [yr(v) for v in x4_opts], yr(wide_y),
               f"{BASE} 연도별 '일별 최고 환율 − 일별 최저 환율'을 구해 {len(rng)}개 연도 중 "
               "최댓값에 해당하는 해를 찾았다.",
               f"{wide_y}년은 최저 {lo[wide_y]:,.2f}원({lo_day(wide_y)})에서 최고 "
               f"{hi[wide_y]:,.2f}원({hi_day(wide_y)})까지 {rng[wide_y]:,.2f}원 움직여, "
               f"{len(rng)}개 연도 중 변동 폭이 가장 컸습니다."),
        choice("x5", f"{END}년 원·달러 환율의 연중 최고와 최저 차이는 몇 원이었을까요? "
               "(단위: 원/달러, 정수)",
               [won(v) for v in x5_opts], won(last_rng),
               f"{BASE} {END}년 유효 관측값 {n(END)}개의 최고 환율 − 최저 환율"
               f" = {hi[END]:,.2f} − {lo[END]:,.2f}의 차이를 계산해 소수 첫째 자리에서 반올림해 정수로 나타냈다.",
               f"{END}년 환율은 최저 {lo[END]:,.2f}원({lo_day(END)}), 최고 {hi[END]:,.2f}원"
               f"({hi_day(END)})으로 차이는 {won(last_rng)}입니다."),
    ]

    caveat = (
        "미국 연방준비제도가 뉴욕 정오 무렵 매입환율로 기록한 값입니다. 한국 외환시장 종가나 "
        "한국은행 기준환율과는 시각 · 기준이 달라 숫자가 조금씩 다를 수 있습니다. 미국 공휴일 등 "
        "값이 비어 있는 날과 주말은 계산에서 뺐습니다. 환율이 오르면 1달러를 사는 데 원화가 더 "
        "드는 것이므로 원화 가치는 내려간 것입니다.")

    return {"id": TID, "emoji": "💵", "title": "원달러 환율 26년",
            "blurb": f"{START}년부터 {END}년 일별 원·달러 환율",
            "source": "FRED (DEXKOUS)", "source_url": "https://fred.stlouisfed.org/series/DEXKOUS",
            "caveat": caveat,
            "questions": questions}


def main() -> None:
    """이 주제 하나만 만든다. 다른 주제 파일은 건드리지 않는다."""
    t = korea_exchange_rate()
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
        print(f"    [{q['type'][:6]:<6}] {q['answer']:<14} {q['basis']}")


if __name__ == "__main__":
    main()
