# -*- coding: utf-8 -*-
"""한국인은 빚을 얼마나 질까? — 대한민국 가계부채 (BIS · FRED, 2000~2024).

build_topics.py 가 불러서 다른 주제와 함께 만든다. 목록에서는 '인터넷과 연결'
(internet) 칸을 지우고 그 자리에 들어간다. 이 파일만 따로 돌려
topics/korea-household-debt.json 하나만 만들 수도 있다.

**모든 숫자는 raw/ 의 FRED 원본 CSV에서 계산합니다.** 연도별 대표값은 4분기 말
잔액 하나이며, 분기 값을 더하거나 평균 내지 않습니다. 값이 없는 해는 다른 분기로
대신하지 않고 '계산 불가'로 멈춥니다.

값은 CSV에 적힌 십진수 그대로(Decimal) 계산한다. float 로 빼면 89.6 − 62.1 이
27.4999… 가 되어 반올림 결과가 달라진다.

실행 (저장소 최상위에서):
    python tools/korea_household_debt.py
"""
from __future__ import annotations

import csv
import io
import json
import random
import sys
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
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
TID = "korea-household-debt"
REPLACES = "internet"                            # 목록에서 이 칸을 지우고 그 자리에 넣는다
# (파일, FRED 지표 코드) — 셋 다 BIS 'Total Credit to Households and NPISHs,
# Adjusted for Breaks', 분기말(Quarterly, End of Quarter) 기준
TOTAL = ("korea-household-debt-total.csv", "CRDQKRAHABIS")   # 십억 원
KOR = ("korea-household-debt-gdp.csv", "QKRHAM770A")         # GDP 대비 %
JPN = ("japan-household-debt-gdp.csv", "QJPHAM770A")         # GDP 대비 %
# FRED 는 분기를 그 분기의 첫날로 적는다. 10월 1일 행이 4분기(말) 값이다
Q4 = "-10-01"


def year_end(raw: Path, src: tuple[str, str]) -> dict[int, Decimal]:
    """연도 → 4분기 말 값. 숫자가 아닌 값('.' · 빈 칸)은 관측치로 치지 않는다."""
    fname, col = src
    out = {}
    for r in csv.DictReader(io.open(raw / fname, encoding="utf-8")):
        d = r["observation_date"]
        if not (d.endswith(Q4) and START <= int(d[:4]) <= END):
            continue
        try:
            out[int(d[:4])] = Decimal(r[col])
        except InvalidOperation:
            pass
    return out


def need(s: dict[int, Decimal], year: int, what: str) -> Decimal:
    if year not in s:
        raise ValueError(f"계산 불가: {what} {year}년 4분기 값이 원본에 없습니다")
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


def korea_household_debt(raw: Path = RAW) -> dict:
    total = year_end(raw, TOTAL)
    kor = year_end(raw, KOR)
    jpn = year_end(raw, JPN)

    t0, t1 = need(total, START, "대한민국 가계부채 총액"), need(total, END, "대한민국 가계부채 총액")
    k0, k1 = need(kor, START, "대한민국 GDP 대비 가계부채 비율"), need(kor, END, "대한민국 GDP 대비 가계부채 비율")
    j1 = need(jpn, END, "일본 GDP 대비 가계부채 비율")

    # 반올림은 마지막 결과에만 한다. 최댓값 비교는 원본 값 그대로 한다
    times = whole(t1 / t0)                           # 1번 · 배
    added = whole((t1 - t0) / 1000)                  # 2번 · 십억 원 → 조 원
    top_y = only(kor, max, "대한민국 GDP 대비 가계부채 비율 최댓값")
    gap = whole(abs(k1 - j1))                        # 4번 · %p (같은 2024년 4분기끼리)
    move = k1 - k0
    move_n = whole(abs(move))                        # 5번 · %p, 부호는 상승 · 하락으로
    signed = move_n if move > 0 else -move_n

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    # 수치 문항의 오답은 정답에서 일정 간격씩 떨어진 정수 중에서 뽑는다
    d1_opts = with_decoys("d1", times, [times + 2 * k for k in range(-3, 4) if times + 2 * k > 1])
    d2_opts = with_decoys("d2", added, [added + 300 * k for k in range(-3, 4) if added + 300 * k > 0])
    d3_opts = with_decoys("d3", top_y, kor)
    d4_opts = with_decoys("d4", gap, [gap + 5 * k for k in range(-3, 4) if gap + 5 * k > 0])
    d5_opts = with_decoys("d5", signed, [signed + 10 * k for k in range(-5, 4) if signed + 10 * k != 0])

    def choice(qid, text, options, answer, basis, why):
        assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
        assert len(set(options)) == 4, f"{qid}: 보기가 4개가 아니거나 겹칩니다"
        return {"id": qid, "type": "choice", "text": text, "options": options,
                "answer": answer, "basis": basis, "why": why}

    jo = lambda v: f"{v:,}조 원"
    pp = lambda v: f"{v}%p"
    updown = lambda v: f"{abs(v)}%p {'상승' if v > 0 else '하락'}"
    yr = lambda v: f"{v}년"
    BIS = "BIS 가계 및 가계봉사 비영리단체 총신용"
    more = "대한민국" if k1 > j1 else "일본"

    questions = [
        choice("d1", f"{START}년 대비 {END}년 대한민국의 가계부채 총액은 약 몇 배가 되었을까요? "
               "(단위: 배, 정수)",
               [f"{v}배" for v in d1_opts], f"{times}배",
               f"FRED {TOTAL[1]}({BIS}, 십억 원) 기준으로 대한민국의 {END}년 4분기 말 잔액 ÷ "
               f"{START}년 4분기 말 잔액을 반올림 없이 계산한 뒤 소수 첫째 자리에서 반올림해 정수 배로 "
               "나타냈다.",
               f"대한민국 가계부채 잔액은 {START}년 4분기 말 약 {whole(t0 / 1000):,}조 원에서 {END}년 "
               f"4분기 말 약 {whole(t1 / 1000):,}조 원으로 약 {times}배가 되었습니다. 1인당 빚이 아니라 "
               "가계 전체의 부채 잔액입니다."),
        choice("d2", f"{START}년 대비 {END}년 대한민국의 가계부채 총액은 약 몇 조 원 증가했을까요? "
               "(단위: 조 원, 정수)",
               [jo(v) for v in d2_opts], jo(added),
               f"FRED {TOTAL[1]}({BIS}, 십억 원) 기준으로 대한민국의 {END}년 4분기 말 잔액 − "
               f"{START}년 4분기 말 잔액을 계산하고 1,000으로 나눠 조 원으로 바꾼 뒤 소수 첫째 자리에서 "
               "반올림했다.",
               f"{START}년 4분기 말 약 {whole(t0 / 1000):,}조 원이던 가계부채 잔액이 {END}년 4분기 말 "
               f"약 {whole(t1 / 1000):,}조 원이 되어 약 {jo(added)} 늘었습니다."),
        choice("d3", f"{START}~{END}년 중 대한민국의 GDP 대비 가계부채 비율이 가장 높았던 해는 "
               "언제일까요? (단위: 연도)",
               [yr(v) for v in d3_opts], yr(top_y),
               f"FRED {KOR[1]}({BIS}, GDP 대비 %) 기준으로 {START}~{END}년 대한민국 각 연도의 "
               f"4분기 말 값({len(kor)}개)을 반올림 없이 비교해 최댓값을 기록한 해를 찾았다.",
               f"{top_y}년 4분기 말 GDP 대비 가계부채 비율 약 {whole(kor[top_y])}%가 {len(kor)}개 연도 "
               f"중 가장 높았고, {END}년 4분기 말은 약 {whole(k1)}%였습니다."),
        choice("d4", f"{END}년 대한민국과 일본의 GDP 대비 가계부채 비율은 약 몇 %p 차이가 났을까요? "
               "(단위: %p, 정수)",
               [pp(v) for v in d4_opts], pp(gap),
               f"FRED {KOR[1]} · {JPN[1]}(같은 {BIS} 기준, GDP 대비 %)로 같은 {END}년 4분기 말의 "
               "|대한민국 값 − 일본 값|을 반올림 없이 계산한 뒤 소수 첫째 자리에서 반올림해 정수 %p로 "
               "나타냈다.",
               f"{END}년 4분기 말 GDP 대비 가계부채 비율은 대한민국 약 {whole(k1)}%, 일본 약 "
               f"{whole(j1)}%로 {more}이 약 {pp(gap)} 높았습니다."),
        choice("d5", f"{START}년 대비 {END}년 대한민국의 GDP 대비 가계부채 비율은 약 몇 %p 상승하거나 "
               "하락했을까요? (단위: %p, 정수)",
               [updown(v) for v in d5_opts], updown(signed),
               f"FRED {KOR[1]}({BIS}, GDP 대비 %) 기준으로 대한민국의 {END}년 4분기 말 값 − "
               f"{START}년 4분기 말 값을 계산해 양수면 상승 · 음수면 하락으로 표시하고, 차이의 절댓값을 "
               "소수 첫째 자리에서 반올림했다.",
               f"대한민국의 GDP 대비 가계부채 비율은 {START}년 4분기 말 약 {whole(k0)}%에서 {END}년 "
               f"4분기 말 약 {whole(k1)}%로 약 {updown(signed)}했습니다."),
    ]

    caveat = (
        "국제결제은행(BIS)이 집계한 가계 및 가계봉사 비영리단체 총신용(Adjusted for Breaks)을 "
        "FRED에서 받은 값이며, 각 연도는 4분기 말 잔액 하나로 나타냈습니다. 가계부채 총액은 가계 "
        "전체의 잔액이지 1인당 빚이 아니고, 비율은 가처분소득이 아니라 GDP 대비입니다. 한국은행 "
        "가계신용 통계와는 집계 범위가 달라 숫자가 다를 수 있습니다. 화면의 숫자는 정수로 반올림해 "
        "보여 주므로 두 값을 빼 보면 정답과 1 정도 어긋날 수 있습니다.")

    return {"id": TID, "emoji": "💳", "title": "한국인은 빚을 얼마나 질까?",
            "blurb": f"{START}년부터 {END}년 가계부채와 대출 규모 변화",
            "source": "FRED · BIS", "source_url": "https://fred.stlouisfed.org/series/QKRHAM770A",
            "caveat": caveat,
            "questions": questions}


def main() -> None:
    """이 주제 하나만 만든다. 다른 주제 파일은 건드리지 않는다."""
    t = korea_household_debt()          # 계산 · 검증이 하나라도 실패하면 여기서 멈춰 아무것도 쓰지 않는다
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
