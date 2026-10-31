# -*- coding: utf-8 -*-
"""한국인은 얼마나 늙어갈까? — 대한민국 고령화와 인구구조 변화 (2000~2024).

build_topics.py 가 불러서 다른 주제와 함께 만든다. 목록에서는 '인구와 출산'
(population) 칸을 지우고 그 자리에 들어간다. 이 파일만 따로 돌려
topics/korea-aging-population.json 하나만 만들 수도 있다.

**모든 숫자는 raw/ 의 World Bank 원본에서 계산합니다.** null 은 빼고 세며,
필요한 연도가 비어 있으면 다른 해로 대신하지 않고 '계산 불가'로 멈춥니다.
계산 중간에는 반올림하지 않고, 화면에 보이는 숫자만 정수로 반올림합니다.

실행 (저장소 최상위에서):
    python tools/korea_aging_population.py
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
TID = "korea-aging-population"
REPLACES = "population"                          # 목록에서 이 칸을 지우고 그 자리에 넣는다
SHARE = "SP.POP.65UP.TO.ZS"     # 65세 이상 인구 비율 (전체 인구 대비 %)
COUNT = "SP.POP.65UP.TO"        # 65세 이상 인구수 (명)
OLD = "SP.POP.DPND.OL"          # 노년부양비 (15~64세 100명당 65세 이상 인구 수)


def name(cc: str, code: str) -> str:
    return f"aging_{cc}_{code}_{START}_{END}.json"


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


def whole(x: float) -> int:
    """소수 첫째 자리에서 사사오입해 정수로. round() 는 0.5 를 짝수 쪽으로 보내므로 쓰지 않는다."""
    return int(Decimal(repr(x)).quantize(Decimal(1), ROUND_HALF_UP))


def korea_aging_population(raw: Path = RAW) -> dict:
    share = series(raw, "KOR", SHARE)
    count = series(raw, "KOR", COUNT)
    old = series(raw, "KOR", OLD)
    share_j = series(raw, "JPN", SHARE)

    s0, s1 = need(share, START, "대한민국 65세 이상 인구 비율"), need(share, END, "대한민국 65세 이상 인구 비율")
    c0, c1 = need(count, START, "대한민국 65세 이상 인구수"), need(count, END, "대한민국 65세 이상 인구수")
    j1 = need(share_j, END, "일본 65세 이상 인구 비율")

    # 반올림은 마지막 결과에만 한다. 최댓값 · 증가 폭 비교는 원본 값 그대로 한다
    rise = whole(s1 - s0)                            # 1번 · %p
    times = whole(c1 / c0)                           # 2번 · 배
    top_y = only(old, max, "대한민국 노년부양비 최댓값")
    gap = whole(abs(s1 - j1))                        # 4번 · %p (같은 해끼리)
    step = {y: share[y] - share[y - 1] for y in sorted(share)
            if y - 1 in share and y > START}         # 전년과 그해 값이 모두 있을 때만
    jump_y = only(step, max, "대한민국 65세 이상 인구 비율 전년 대비 증가 폭 최댓값")
    skipped = [y for y in range(START + 1, END + 1) if y not in step]

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    # 수치 문항의 오답은 정답에서 일정 간격씩 떨어진 정수 중에서 뽑는다
    a1_opts = with_decoys("a1", rise, [rise + 3 * k for k in range(-3, 4) if rise + 3 * k > 0])
    a2_opts = with_decoys("a2", times, [times + k for k in range(-3, 4) if times + k > 0])
    a3_opts = with_decoys("a3", top_y, old)
    a4_opts = with_decoys("a4", gap, [gap + 4 * k for k in range(-3, 4) if gap + 4 * k > 0])
    a5_opts = with_decoys("a5", jump_y, step)

    def choice(qid, text, options, answer, basis, why):
        assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
        assert len(set(options)) == 4, f"{qid}: 보기가 4개가 아니거나 겹칩니다"
        return {"id": qid, "type": "choice", "text": text, "options": options,
                "answer": answer, "basis": basis, "why": why}

    pp = lambda v: f"{v}%p"
    yr = lambda v: f"{v}년"
    more = "일본" if j1 > s1 else "대한민국"
    WB = "World Bank WDI"

    questions = [
        choice("a1", f"{START}년 대비 {END}년 대한민국의 65세 이상 인구 비율은 약 몇 %p 증가했을까요? "
               "(단위: %p, 정수)",
               [pp(v) for v in a1_opts], pp(rise),
               f"{WB} 65세 이상 인구 비율({SHARE}, 전체 인구 대비 %) 기준으로 대한민국의 "
               f"{END}년 값 − {START}년 값을 반올림 없이 계산한 뒤 소수 첫째 자리에서 반올림해 "
               "정수 %p로 나타냈다.",
               f"대한민국의 65세 이상 인구 비율은 {START}년 약 {whole(s0)}%에서 {END}년 약 "
               f"{whole(s1)}%로 약 {pp(rise)} 높아졌습니다."),
        choice("a2", f"{START}년 대비 {END}년 대한민국의 65세 이상 인구수는 약 몇 배가 되었을까요? "
               "(단위: 배, 정수)",
               [f"{v}배" for v in a2_opts], f"{times}배",
               f"{WB} 65세 이상 인구수({COUNT}, 명) 기준으로 대한민국의 {END}년 값 ÷ {START}년 값을 "
               "반올림 없이 계산한 뒤 소수 첫째 자리에서 반올림해 정수 배로 나타냈다.",
               f"대한민국의 65세 이상 인구는 {START}년 {whole(c0):,}명에서 {END}년 {whole(c1):,}명으로 "
               f"약 {times}배가 되었습니다."),
        choice("a3", f"{START}~{END}년 중 대한민국의 노년부양비가 가장 높았던 해는 언제일까요? "
               "(단위: 연도)",
               [yr(v) for v in a3_opts], yr(top_y),
               f"{WB} 노년부양비({OLD}, 15~64세 인구 100명당 65세 이상 인구 수) 기준으로 "
               f"{START}~{END}년 대한민국 값이 있는 {len(old)}개 연도의 원본 값을 비교해 "
               "최댓값을 기록한 해를 찾았다.",
               f"{top_y}년 노년부양비는 15~64세 인구 100명당 65세 이상 약 {whole(old[top_y])}명으로 "
               f"{len(old)}개 연도 중 가장 높았고, {START}년은 약 {whole(old[START])}명이었습니다."),
        choice("a4", f"{END}년 대한민국과 일본의 65세 이상 인구 비율 차이는 약 몇 %p일까요? "
               "(단위: %p, 정수)",
               [pp(v) for v in a4_opts], pp(gap),
               f"{WB} 65세 이상 인구 비율({SHARE}) 기준으로 같은 {END}년의 |대한민국 값 − 일본 값|을 "
               "반올림 없이 계산한 뒤 소수 첫째 자리에서 반올림해 정수 %p로 나타냈다.",
               f"{END}년 65세 이상 인구 비율은 대한민국 약 {whole(s1)}%, 일본 약 {whole(j1)}%로 "
               f"{more}이 약 {pp(gap)} 높습니다."),
        choice("a5", f"{START + 1}~{END}년 중 대한민국의 65세 이상 인구 비율이 전년 대비 가장 크게 "
               "증가한 해는 언제일까요? (단위: 연도)",
               [yr(v) for v in a5_opts], yr(jump_y),
               f"{WB} 65세 이상 인구 비율({SHARE}) 기준으로 {START + 1}~{END}년 대한민국의 "
               f"'그해 값 − 전년 값'을 전년과 그해 값이 모두 있는 {len(step)}개 연도"
               + (f"(결측으로 {', '.join(map(str, skipped))}년 제외)" if skipped else "")
               + "에서 반올림 없이 계산해 증가 폭이 가장 큰 해를 찾았다.",
               f"반올림하지 않은 원본 값으로 비교하면 {jump_y}년의 전년 대비 증가 폭이 "
               f"{len(step)}개 연도 중 가장 컸습니다. 정수로 나타내면 {jump_y - 1}년 약 "
               f"{whole(share[jump_y - 1])}%에서 {jump_y}년 약 {whole(share[jump_y])}%입니다."),
    ]

    upd = sorted({json.load(io.open(raw / name(cc, code), encoding="utf-8"))[0]["lastupdated"]
                  for cc, code in (("KOR", SHARE), ("KOR", COUNT), ("KOR", OLD), ("JPN", SHARE))})
    caveat = (
        f"World Bank 공표치이며 World Bank 갱신일 {', '.join(upd)} 기준으로 받은 값입니다. "
        "65세 이상 인구 비율은 전체 인구 대비 %이고, 노년부양비는 일하는 나이(15~64세) 인구 "
        "100명당 65세 이상 인구 수라 서로 다른 숫자입니다. 화면의 숫자는 정수로 반올림해 "
        "보여 주므로 두 값을 빼 보면 정답과 1 정도 어긋날 수 있습니다. 최근 연도 값은 "
        "나중에 고쳐질 수 있어 통계청 발표와 다를 수 있습니다.")

    return {"id": TID, "emoji": "👵", "title": "한국인은 얼마나 늙어갈까?",
            "blurb": f"{START}년부터 {END}년 고령화와 인구구조 변화",
            "source": "World Bank Open Data · WDI", "source_url": "https://data.worldbank.org/",
            "caveat": caveat,
            "questions": questions}


def main() -> None:
    """이 주제 하나만 만든다. 다른 주제 파일은 건드리지 않는다."""
    t = korea_aging_population()
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
