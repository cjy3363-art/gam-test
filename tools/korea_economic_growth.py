# -*- coding: utf-8 -*-
"""한국인은 얼마나 벌까? — 대한민국 소득 수준과 경제 성장.

build_topics.py 가 불러서 다른 주제와 함께 만든다. 목록에서는 '미세먼지, 언제
나쁜가'(seoul-air) 칸을 지우고 그 자리에 들어간다. 이 파일만 따로 돌려
topics/korea-economic-growth.json 하나만 만들 수도 있다.

**모든 숫자는 raw/ 의 World Bank 원본에서 계산합니다.** null 은 빼고 세며,
1990년 · 2023년 값이 비어 있으면 다른 해로 대신하지 않고 '계산 불가'로 멈춥니다.
GDP · GNI 는 나라 경제 전체를 인구로 나눈 값이지, 한 사람이 받는 월급이 아닙니다.

실행 (저장소 최상위에서):
    python tools/korea_economic_growth.py
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

START, END = 1990, 2023
TID = "korea-economic-growth"
REPLACES = "seoul-air"                           # 목록에서 이 칸을 지우고 그 자리에 넣는다
GDP = "NY.GDP.PCAP.CD"          # 1인당 명목 GDP (현재 US$)
GNI = "NY.GNP.PCAP.CD"          # 1인당 명목 GNI (현재 US$)
GROW = "NY.GDP.MKTP.KD.ZG"      # 경제성장률 (실질 GDP 증가율, %)
REAL = "NY.GDP.PCAP.KD"         # 실질 1인당 GDP (불변가격 US$)


def name(cc: str, code: str) -> str:
    return f"economy_{cc}_{code}_{START}_{END}.json"


def series(raw: Path, cc: str, code: str) -> dict[int, float]:
    """원본의 date · value 만 쓴다. value 가 있는 해만 유효한 관측치로 친다."""
    rows = json.load(io.open(raw / name(cc, code), encoding="utf-8"))[1]
    return {int(r["date"]): r["value"] for r in rows
            if r["value"] is not None and START <= int(r["date"]) <= END}


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


def korea_economic_growth(raw: Path = RAW) -> dict:
    gdp = series(raw, "KOR", GDP)
    grow = series(raw, "KOR", GROW)
    real = series(raw, "KOR", REAL)
    gni_k = series(raw, "KOR", GNI)
    gni_j = series(raw, "JPN", GNI)

    g0, g1 = need(gdp, START, "대한민국 1인당 명목 GDP"), need(gdp, END, "대한민국 1인당 명목 GDP")
    r0, r1 = need(real, START, "대한민국 실질 1인당 GDP"), need(real, END, "대한민국 실질 1인당 GDP")
    nk = need(gni_k, END, "대한민국 1인당 명목 GNI")
    nj = need(gni_j, END, "일본 1인당 명목 GNI")

    # 반올림은 마지막 결과에만 한다
    times = half_up(g1 / g0, 0)                      # 1번 · 정수
    top_y = only(grow, max, "대한민국 경제성장률 최댓값")
    rise = half_up((r1 - r0) / r0 * 100, 0)          # 3번 · 정수
    gap = half_up(abs(nk - nj), 0)                   # 4번 · 절댓값, 정수
    neg = sorted(y for y, v in grow.items() if v < 0)

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    # 수치 문항의 오답은 정답에서 일정 간격씩 떨어진 값 중에서 뽑는다
    e1_opts = with_decoys("e1", times, [half_up(times + k, 0) for k in range(-3, 4)
                                        if times + k > 1])
    e2_opts = with_decoys("e2", top_y, grow)         # 1990~2023 중 값이 있는 해
    e3_opts = with_decoys("e3", rise, [half_up(rise + 75 * k, 0) for k in range(-3, 4)
                                       if rise + 75 * k > 0])
    e4_opts = with_decoys("e4", gap, [half_up(gap + 2000 * k, 0) for k in range(-3, 4)
                                      if gap + 2000 * k > 0])
    e5_opts = with_decoys("e5", len(neg), range(0, 8))

    def choice(qid, text, options, answer, basis, why):
        assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
        assert len(set(options)) == 4, f"{qid}: 보기가 4개가 아니거나 겹칩니다"
        return {"id": qid, "type": "choice", "text": text, "options": options,
                "answer": answer, "basis": basis, "why": why}

    bae = lambda v: f"{v:.0f}배"
    pct = lambda v: f"{v:,.0f}%"
    usd = lambda v: f"{v:,.0f}달러"
    yr = lambda v: f"{v}년"
    more = "대한민국" if nk > nj else "일본"

    questions = [
        choice("e1", f"{START}년 대비 {END}년 대한민국의 1인당 명목 GDP는 몇 배가 되었을까요? "
               "(단위: 배, 정수)",
               [bae(v) for v in e1_opts], bae(times),
               f"World Bank 1인당 명목 GDP(현재 US$) 기준으로 대한민국의 {END}년 값 ÷ {START}년 값"
               f" = {g1:,.2f} ÷ {g0:,.2f}을 계산해 소수 첫째 자리에서 반올림해 정수로 나타냈다.",
               f"대한민국의 1인당 명목 GDP는 {START}년 {g0:,.2f}달러에서 {END}년 {g1:,.2f}달러로 "
               f"{bae(times)}가 되었습니다. 나라 전체 GDP를 인구로 나눈 값입니다."),
        choice("e2", f"{START}~{END}년 중 대한민국의 경제성장률이 가장 높았던 해는 언제일까요? "
               "(단위: 연도)",
               [yr(v) for v in e2_opts], yr(top_y),
               f"World Bank 실질 GDP 증가율(%) 기준으로 {START}~{END}년 대한민국 값이 있는 "
               f"{len(grow)}개 연도에서 최댓값({grow[top_y]:.2f}%)에 해당하는 해를 찾았다.",
               f"{top_y}년 경제성장률 {grow[top_y]:.2f}%가 {len(grow)}개 연도 중 가장 높았고, "
               f"{END}년은 {grow[END]:.2f}%였습니다."),
        choice("e3", f"{START}년 대비 {END}년 대한민국의 실질 1인당 GDP는 몇 % 증가했을까요? "
               "(단위: %, 정수)",
               [pct(v) for v in e3_opts], pct(rise),
               f"World Bank 실질 1인당 GDP(불변가격 US$) 기준으로 대한민국의 ({END}년 값 − {START}년 값)"
               f" ÷ {START}년 값 × 100 = ({r1:,.2f} − {r0:,.2f}) ÷ {r0:,.2f} × 100을 계산해 "
               f"소수 첫째 자리에서 반올림해 정수로 나타냈다.",
               f"물가 변동을 뺀 실질 1인당 GDP는 {START}년 {r0:,.2f}달러에서 {END}년 {r1:,.2f}달러로 "
               f"{pct(rise)} 늘었습니다. 같은 기간 명목 값은 {bae(times)}가 되었습니다."),
        choice("e4", f"{END}년 대한민국과 일본의 1인당 명목 GNI 차이는 얼마일까요? "
               "(단위: 미국 달러, 절댓값, 정수)",
               [usd(v) for v in e4_opts], usd(gap),
               f"World Bank 1인당 명목 GNI(현재 US$) 기준으로 {END}년 |대한민국 값 − 일본 값|"
               f" = |{nk:,.0f} − {nj:,.0f}|을 계산해 소수 첫째 자리에서 반올림해 정수로 나타냈다.",
               f"{END}년 1인당 명목 GNI는 대한민국 {nk:,.0f}달러, 일본 {nj:,.0f}달러로 "
               f"{more}이 {usd(gap)} 많습니다. 나라 전체 국민총소득을 인구로 나눈 값입니다."),
        choice("e5", f"{START}~{END}년 중 대한민국의 경제성장률이 마이너스였던 해는 총 몇 년일까요? "
               "(단위: 년)",
               [f"{n}년" for n in e5_opts], f"{len(neg)}년",
               f"World Bank 실질 GDP 증가율(%) 기준으로 {START}~{END}년 대한민국 값이 있는 "
               f"{len(grow)}개 연도에서 0% 미만(0%는 제외)인 해의 개수를 셌다.",
               f"{START}~{END}년 중 경제성장률이 0% 미만인 해는 "
               + (f"{', '.join(f'{y}년({grow[y]:.2f}%)' for y in neg)}으로 " if neg else "없어 ")
               + f"총 {len(neg)}년입니다."),
    ]

    upd = sorted({json.load(io.open(raw / name(cc, code), encoding="utf-8"))[0]["lastupdated"]
                  for cc, code in (("KOR", GDP), ("KOR", GNI), ("KOR", GROW),
                                   ("KOR", REAL), ("JPN", GNI))})
    caveat = (
        f"World Bank 공표치이며 World Bank 갱신일 {', '.join(upd)} 기준으로 받은 값입니다. "
        "1인당 GDP · GNI는 나라 경제 전체를 인구로 나눈 값으로, 한 사람이 실제로 받는 월급이나 "
        "소득이 아닙니다. 명목 값은 그해 환율로 달러로 바꾼 값이라 환율이 움직이면 함께 바뀌고, "
        "1인당 GNI는 World Bank Atlas 방식으로 계산한 값입니다. 최근 연도 값은 나중에 "
        "고쳐질 수 있어 한국은행 발표와 다를 수 있습니다.")

    return {"id": TID, "emoji": "💰", "title": "한국인은 얼마나 벌까?",
            "blurb": f"{START}년부터 {END}년 소득 수준과 경제 성장",
            "source": "World Bank Open Data · WDI", "source_url": "https://data.worldbank.org/",
            "caveat": caveat,
            "questions": questions}


def main() -> None:
    """이 주제 하나만 만든다. 다른 주제 파일은 건드리지 않는다."""
    t = korea_economic_growth()
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
        print(f"    [{q['type'][:6]:<6}] {q['answer']:<12} {q['basis']}")


if __name__ == "__main__":
    main()
