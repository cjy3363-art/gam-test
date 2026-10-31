# -*- coding: utf-8 -*-
"""한국인은 얼마나 일할까? — 대한민국 연간 근로시간 변화.

build_topics.py 가 불러서 다른 주제와 함께 만든다. 목록에서는 '비는 언제, 얼마나'
(seoul-rain) 칸을 지우고 그 자리에 들어간다. 이 파일만 따로 돌려
topics/korea-working-hours.json 하나만 만들 수도 있다.

**모든 숫자는 raw/ 의 OWID 원본 CSV에서 계산합니다.** 빈 값은 빼고 세며,
필요한 나라 · 연도가 비어 있으면 다른 값으로 대신하지 않고 '계산 불가'로 멈춥니다.

실행 (저장소 최상위에서):
    python tools/korea_working_hours.py
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

START, END = 1990, 2023
TID = "korea-working-hours"
REPLACES = "seoul-rain"                          # 목록에서 이 칸을 지우고 그 자리에 넣는다
FILE = "korea-working-hours.csv"
COL = "Working hours per worker"
NAMES = {"KOR": "대한민국", "JPN": "일본", "USA": "미국", "DEU": "독일", "FRA": "프랑스"}


def series(raw: Path) -> dict[str, dict[int, float]]:
    """국가코드 · 연도 · 근로시간만 쓴다. 값이 빈 칸인 해는 관측치로 치지 않는다."""
    rows = csv.DictReader(io.open(raw / FILE, encoding="utf-8"))
    out: dict[str, dict[int, float]] = {c: {} for c in NAMES}
    for r in rows:
        if r["Code"] in out and r[COL] != "" and START <= int(r["Year"]) <= END:
            out[r["Code"]][int(r["Year"])] = float(r[COL])
    return out


def need(s: dict[int, float], year: int, what: str) -> float:
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


def half_up(x: float, nd: int) -> float:
    """사사오입. round() 는 0.5 를 짝수 쪽으로 보내므로 쓰지 않는다."""
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-nd), ROUND_HALF_UP))


def korea_working_hours(raw: Path = RAW) -> dict:
    s = series(raw)
    kor = s["KOR"]

    k0, k1 = need(kor, START, "대한민국"), need(kor, END, "대한민국")
    j1 = need(s["JPN"], END, "일본")
    last = {c: need(s[c], END, NAMES[c]) for c in NAMES}

    drop = half_up(k0 - k1, 0)                       # 1번 · 정수
    top_y = only(kor, max, "대한민국 근로시간 최댓값")
    gap = half_up(abs(k1 - j1), 0)                   # 3번 · 절댓값, 정수
    # 4번은 전년과 그해 값이 모두 있는 해만 비교한다
    diff = {y: round(kor[y] - kor[y - 1], 10) for y in sorted(kor) if y - 1 in kor}
    cut_y = only(diff, min, "대한민국 전년 대비 변화량 최솟값")
    short = only(last, min, f"{END}년 5개국 근로시간 최솟값")
    skipped = [y for y in range(START + 1, END + 1) if y not in diff]

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    # 수치 문항의 오답은 정답에서 일정 간격씩 떨어진 값 중에서 뽑는다
    w1_opts = with_decoys("w1", drop, [half_up(drop + 150 * k, 0) for k in range(-3, 4)
                                       if drop + 150 * k > 0])
    w2_opts = with_decoys("w2", top_y, kor)
    w3_opts = with_decoys("w3", gap, [half_up(gap + 100 * k, 0) for k in range(-3, 4)
                                      if gap + 100 * k > 0])
    w4_opts = with_decoys("w4", cut_y, diff)
    w5_opts = with_decoys("w5", short, NAMES)        # 5개국 중 정답 포함 4개국

    def choice(qid, text, options, answer, basis, why):
        assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
        assert len(set(options)) == 4, f"{qid}: 보기가 4개가 아니거나 겹칩니다"
        return {"id": qid, "type": "choice", "text": text, "options": options,
                "answer": answer, "basis": basis, "why": why}

    hr = lambda v: f"{v:,.0f}시간"
    yr = lambda v: f"{v}년"
    rank = sorted(last, key=last.get)

    questions = [
        choice("w1", f"{START}년 대비 {END}년 대한민국의 연간 평균 근로시간은 몇 시간 감소했을까요? "
               "(단위: 시간, 정수)",
               [hr(v) for v in w1_opts], hr(drop),
               f"OWID 취업자 1인당 연간 근로시간 기준으로 대한민국의 {START}년 값 − {END}년 값"
               f" = {k0:,.2f} − {k1:,.2f}을 계산해 소수 첫째 자리에서 반올림해 정수로 나타냈다.",
               f"대한민국의 연간 근로시간은 {START}년 {k0:,.2f}시간에서 {END}년 {k1:,.2f}시간으로 "
               f"{hr(drop)} 줄었습니다."),
        choice("w2", f"{START}~{END}년 중 대한민국의 연간 평균 근로시간이 가장 길었던 해는 언제일까요? "
               "(단위: 연도)",
               [yr(v) for v in w2_opts], yr(top_y),
               f"OWID 취업자 1인당 연간 근로시간 기준으로 {START}~{END}년 대한민국 값이 있는 "
               f"{len(kor)}개 연도에서 최댓값({kor[top_y]:,.2f}시간)에 해당하는 해를 찾았다.",
               f"{top_y}년 {kor[top_y]:,.2f}시간이 {len(kor)}개 연도 중 가장 길었고, "
               f"{END}년은 {k1:,.2f}시간이었습니다."),
        choice("w3", f"{END}년 대한민국과 일본의 연간 평균 근로시간 차이는 몇 시간일까요? "
               "(단위: 시간, 절댓값, 정수)",
               [hr(v) for v in w3_opts], hr(gap),
               f"OWID 취업자 1인당 연간 근로시간 기준으로 {END}년 |대한민국 값 − 일본 값|"
               f" = |{k1:,.2f} − {j1:,.2f}|을 계산해 소수 첫째 자리에서 반올림해 정수로 나타냈다.",
               f"{END}년 연간 근로시간은 대한민국 {k1:,.2f}시간, 일본 {j1:,.2f}시간으로 "
               f"대한민국이 {hr(gap)} 더 깁니다." if k1 >= j1 else
               f"{END}년 연간 근로시간은 대한민국 {k1:,.2f}시간, 일본 {j1:,.2f}시간으로 "
               f"일본이 {hr(gap)} 더 깁니다."),
        choice("w4", f"{START + 1}~{END}년 중 대한민국의 연간 평균 근로시간이 전년 대비 가장 크게 "
               "감소한 해는 언제일까요? (단위: 연도)",
               [yr(v) for v in w4_opts], yr(cut_y),
               f"OWID 취업자 1인당 연간 근로시간 기준으로 {START + 1}~{END}년 대한민국의 "
               f"'그해 값 − 전년 값'을 전년과 그해 값이 모두 있는 {len(diff)}개 연도"
               + (f"(결측으로 {', '.join(map(str, skipped))}년 제외)" if skipped else "")
               + "에서 계산해 최솟값에 해당하는 해를 찾았다.",
               f"{cut_y}년 연간 근로시간은 전년 {kor[cut_y - 1]:,.2f}시간에서 "
               f"{kor[cut_y]:,.2f}시간으로 {-diff[cut_y]:,.2f}시간 줄어, 비교한 {len(diff)}개 "
               f"연도 중 감소량이 가장 컸습니다."),
        choice("w5", f"{END}년 대한민국·일본·미국·독일·프랑스 중 연간 평균 근로시간이 가장 짧은 "
               "국가는 어디일까요? (단위: 국가)",
               [NAMES[c] for c in w5_opts], NAMES[short],
               f"OWID 취업자 1인당 연간 근로시간 기준으로 {END}년 5개국 값을 비교해 "
               f"최솟값에 해당하는 국가를 찾았다.",
               f"{END}년 연간 근로시간은 "
               + ", ".join(f"{NAMES[c]} {last[c]:,.2f}시간" for c in rank)
               + f" 순으로 {NAMES[short]}이 가장 짧습니다."),
    ]

    caveat = (
        "Our World in Data가 여러 연구 · 통계(Penn World Table 등)를 모아 정리한 값입니다. "
        "나라마다 근로시간을 조사하는 방법이 달라, OECD나 고용노동부 발표 숫자와 다를 수 있으며 "
        "나라 사이 비교는 대략적인 차이로 보는 것이 안전합니다.")

    return {"id": TID, "emoji": "⏰", "title": "한국인은 얼마나 일할까?",
            "blurb": f"{START}년부터 {END}년 근로시간 변화",
            "source": "Our World in Data",
            "source_url": "https://ourworldindata.org/grapher/annual-working-hours-per-worker",
            "caveat": caveat,
            "questions": questions}


def main() -> None:
    """이 주제 하나만 만든다. 다른 주제 파일은 건드리지 않는다."""
    t = korea_working_hours()
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
