# -*- coding: utf-8 -*-
"""한국에서 아이는 얼마나 태어날까? — 대한민국 출산율 · 인구 변화 (11번째 주제).

build_topics.py 가 불러서 다른 주제와 함께 만든다. 다른 주제의 원본이 아직
없을 때는 이 파일만 따로 돌려 topics/korea-population.json 하나만 만들 수 있다.

**모든 숫자는 raw/ 의 World Bank 원본에서 계산합니다.** null 은 빼고 세며,
필요한 연도가 비어 있으면 다른 해로 대신하지 않고 '계산 불가'로 멈춥니다.

실행 (저장소 최상위에서):
    python tools/korea_population.py
"""
from __future__ import annotations

import io
import json
import random
from decimal import ROUND_HALF_UP, Decimal
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent          # tools/
APP = HERE.parent
RAW = APP / "data" / "raw"
OUT = APP / "topics"

# 원본을 2000~2024년으로 받았다 (fetch_all.py 의 korea_*_2000_2024.json)
START, END = 2000, 2024
TID = "korea-population"
FILES = {
    "fert": "korea_fertility_2000_2024.json",           # 합계출산율 SP.DYN.TFRT.IN
    "cbr": "korea_birth_rate_2000_2024.json",           # 조출생률 SP.DYN.CBRT.IN
    "pop": "korea_population_2000_2024.json",           # 총인구 SP.POP.TOTL
    "grow": "korea_population_growth_2000_2024.json",   # 인구증가율 SP.POP.GROW
}


def series(raw: Path, name: str) -> dict[int, float]:
    """원본의 date · value 만 쓴다. value 가 있는 해만 유효한 관측치로 친다."""
    rows = json.load(io.open(raw / name, encoding="utf-8"))[1]
    return {int(r["date"]): r["value"] for r in rows
            if r["value"] is not None and START <= int(r["date"]) <= END}


def fetched(raw: Path, name: str) -> tuple[str, list[int]]:
    """언제 기준인가 — World Bank 갱신일과, 원본에서 값이 비어 있는 해."""
    meta, rows = json.load(io.open(raw / name, encoding="utf-8"))
    return meta["lastupdated"], sorted(int(r["date"]) for r in rows if r["value"] is None)


def need(s: dict[int, float], year: int, what: str) -> float:
    if year not in s:
        raise ValueError(f"계산 불가: {what} {year}년 값이 원본에 없습니다")
    return s[year]


def only(s: dict[int, float], pick, what: str) -> int:
    """최솟값 · 최댓값이 나온 해. 같은 값이 여러 해면 하나를 고르지 않고 멈춘다."""
    best = pick(s.values())
    hits = sorted(y for y, v in s.items() if v == best)
    if len(hits) > 1:
        raise ValueError(f"판정 불가: {what}이 {', '.join(map(str, hits))}년에 같은 값({best})입니다")
    return hits[0]


def half_up(x: float, nd: int) -> float:
    """사사오입. round() 는 0.5 를 짝수 쪽으로 보내므로 쓰지 않는다."""
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-nd), ROUND_HALF_UP))


def korea_population(raw: Path = RAW) -> dict:
    fert = series(raw, FILES["fert"])
    cbr = series(raw, FILES["cbr"])
    pop = series(raw, FILES["pop"])
    grow = series(raw, FILES["grow"])

    f0, f1 = need(fert, START, "합계출산율"), need(fert, END, "합계출산율")
    b0, b1 = need(cbr, START, "조출생률"), need(cbr, END, "조출생률")

    drop = half_up((f0 - f1) / f0 * 100, 0)          # 1번 · 정수
    gap = half_up(b0 - b1, 0)                        # 3번 · 정수
    low_y = only(fert, min, "합계출산율 최솟값")
    top_y = only(pop, max, "총인구 최댓값")
    neg = sorted(y for y, v in grow.items() if v < 0)

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    # 수치 문항의 오답은 정답에서 일정 간격씩 떨어진 값 중에서 뽑는다
    k2_opts = with_decoys("k2", low_y, fert)
    k3_opts = with_decoys("k3", gap, [half_up(gap + 2 * k, 0) for k in range(-3, 4)
                                      if gap + 2 * k > 0])
    k4_opts = with_decoys("k4", top_y, pop)
    k5_opts = with_decoys("k5", len(neg), range(0, len(grow) + 1))

    def choice(qid, text, options, answer, basis, why):
        assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
        assert len(set(options)) == 4, f"{qid}: 보기가 4개가 아니거나 겹칩니다"
        return {"id": qid, "type": "choice", "text": text, "options": options,
                "answer": answer, "basis": basis, "why": why}

    def slider(qid, text, answer, unit, lo, hi, basis, why):
        """숫자를 직접 맞히는 문항. 시작 위치는 범위의 맨 왼쪽 — 가운데에 두면 정답 근처에서 시작할 수 있다"""
        assert lo <= answer <= hi, f"{qid}: 정답 {answer}이(가) 슬라이더 범위 {lo}~{hi} 밖입니다"
        return {"id": qid, "type": "slider", "text": text, "unit": unit, "min": lo, "max": hi,
                "step": 1, "start": lo, "answer": answer, "basis": basis, "why": why}

    pct = lambda v: f"{v:.0f}%"
    per = lambda v: f"{v:.0f}명"
    yr = lambda v: f"{v}년"
    p_below = pop[top_y] - pop[END]

    questions = [
        slider("k1", f"{START}년 대비 {END}년 대한민국의 합계출산율은 몇 % 감소했을까요? "
               "(단위: %, 정수)",
               int(drop), "%", 0, 100,
               f"{START}·{END}년 대한민국 합계출산율로 ({START}년 값 − {END}년 값) ÷ {START}년 값 × 100"
               f" = ({f0:.3f} − {f1:.3f}) ÷ {f0:.3f} × 100을 계산해 소수 첫째 자리에서 반올림해 정수로 나타냈다.",
               f"합계출산율은 {START}년 {f0:.3f}명에서 {END}년 {f1:.3f}명으로 "
               f"{f0 - f1:.3f}명 줄어 {pct(drop)} 감소했습니다."),
        choice("k2", f"{START}~{END}년 중 대한민국의 합계출산율이 가장 낮았던 해는 언제일까요? "
               "(단위: 연도)",
               [yr(v) for v in k2_opts], yr(low_y),
               f"{START}~{END}년 대한민국 합계출산율 중 값이 있는 {len(fert)}개 연도에서 "
               f"최솟값({fert[low_y]:.3f}명)에 해당하는 해를 찾았다.",
               f"{low_y}년 합계출산율 {fert[low_y]:.3f}명이 {len(fert)}개 연도 중 가장 낮았고, "
               f"{END}년은 {fert[END]:.3f}명이었습니다."),
        choice("k3", f"{START}년과 {END}년 대한민국의 조출생률은 얼마나 차이 날까요? "
               "(단위: 인구 1,000명당 출생아 수, 정수)",
               [per(v) for v in k3_opts], per(gap),
               f"{START}·{END}년 대한민국 조출생률(인구 1,000명당 출생아 수)로 {START}년 값 − {END}년 값"
               f" = {b0:.2f} − {b1:.2f}의 차이를 계산해 소수 첫째 자리에서 반올림해 정수로 나타냈다.",
               f"조출생률은 {START}년 인구 1,000명당 {b0:.2f}명, {END}년 {b1:.2f}명으로 "
               f"{per(gap)} 차이 납니다."),
        choice("k4", f"{START}~{END}년 중 대한민국의 총인구가 가장 많았던 해는 언제일까요? "
               "(단위: 연도)",
               [yr(v) for v in k4_opts], yr(top_y),
               f"{START}~{END}년 대한민국 총인구 중 값이 있는 {len(pop)}개 연도에서 "
               f"최댓값({pop[top_y]:,.0f}명)에 해당하는 해를 찾았다.",
               f"{top_y}년 총인구 {pop[top_y]:,.0f}명이 {len(pop)}개 연도 중 가장 많았고, "
               f"{END}년은 {pop[END]:,.0f}명으로 그보다 {p_below:,.0f}명 적습니다."),
        choice("k5", f"{START}~{END}년 중 대한민국의 연간 인구증가율이 0% 미만이었던 해는 "
               "총 몇 년일까요? (단위: 년)",
               [f"{n}년" for n in k5_opts], f"{len(neg)}년",
               f"{START}~{END}년 대한민국 연간 인구증가율 중 값이 있는 {len(grow)}개 연도에서 "
               f"0% 미만(0%는 제외)인 해의 개수를 셌다.",
               f"{START}~{END}년 중 인구증가율이 0% 미만인 해는 "
               + (f"{', '.join(f'{y}년({grow[y]:.3f}%)' for y in neg)}으로 " if neg else "없어 ")
               + f"총 {len(neg)}년입니다."),
    ]

    # 한계 문장의 날짜 · 숫자도 손으로 적지 않는다 — 원본 메타에서 가져온다
    meta = {k: fetched(raw, f) for k, f in FILES.items()}
    upds = sorted({u for u, _ in meta.values()})
    nulls = sorted({y for _, ns in meta.values() for y in ns})
    caveat = (
        f"World Bank 공표치이며 World Bank 갱신일 {', '.join(upds)} 기준으로 받은 값입니다. "
        + (f"원본에서 {', '.join(map(str, nulls))}년 값은 비어 있어(null) 계산에서 뺐습니다. "
           if nulls else "")
        + "출산율·조출생률은 연도마다 UN 세계인구전망 추정치인지 통계청 공표치인지 원본에 "
        "표시되지 않으며, 최근 연도 값은 나중에 고쳐질 수 있습니다. 그래서 통계청 발표나 "
        "다른 곳에서 본 숫자와 다를 수 있습니다.")

    return {"id": TID, "emoji": "👶", "title": "한국에서 아이는 얼마나 태어날까?",
            "blurb": f"{START}년부터 {END}년 출산율과 인구변화",
            "source": "World Bank Open Data · WDI", "source_url": "https://data.worldbank.org/",
            "caveat": caveat,
            "questions": questions}


def main() -> None:
    """이 주제 하나만 만든다. 다른 주제 파일은 건드리지 않는다."""
    t = korea_population()
    pack = {k: t[k] for k in ("id", "emoji", "title", "blurb",
                              "source", "source_url", "caveat")}
    pack["questions"] = t["questions"]
    OUT.mkdir(parents=True, exist_ok=True)
    io.open(OUT / f"{TID}.json", "w", encoding="utf-8").write(
        json.dumps(pack, ensure_ascii=False, indent=2))

    # 주제 목록에는 이 주제 한 줄만 넣거나 바꾼다. 나머지는 그대로 둔다
    index = json.load(io.open(APP / "topics.json", encoding="utf-8"))
    entry = {k: t[k] for k in ("id", "emoji", "title", "blurb", "source")}
    ids = [x["id"] for x in index["topics"]]
    if TID in ids:
        index["topics"][ids.index(TID)] = entry
    else:
        index["topics"].append(entry)
    io.open(APP / "topics.json", "w", encoding="utf-8").write(
        json.dumps(index, ensure_ascii=False, indent=2))

    print(f"{t['emoji']} {t['title']}  → {OUT / f'{TID}.json'}")
    for q in t["questions"]:
        a = f"{q['answer']}{q.get('unit', '')}" if q["type"] == "slider" else q["answer"]
        print(f"    [{q['type'][:6]:<6}] {a:<8} {q['basis']}")


if __name__ == "__main__":
    main()
