# -*- coding: utf-8 -*-
"""대한민국 출산율 · 기대수명 — 11번째 주제.

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

# 2025년 값은 World Bank가 아직 공표하지 않았다(null). 그래서 기간을 2024년까지로 잡는다
START, END = 2000, 2024
TID = "korea-population"


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


def yearly_diff(s: dict[int, float]) -> dict[int, float]:
    """연속된 두 해가 모두 있을 때만 '전년 대비'를 센다. 비어 있는 해는 건너뛴다."""
    return {y: round(s[y] - s[y - 1], 10) for y in sorted(s) if y - 1 in s}


def korea_population(raw: Path = RAW) -> dict:
    fert = series(raw, "korea_fertility_2000_2025.json")
    life = series(raw, "korea_life_expectancy_2000_2025.json")

    f0, f1 = need(fert, START, "합계출산율"), need(fert, END, "합계출산율")
    l0, l1 = need(life, START, "기대수명"), need(life, END, "기대수명")

    f_ratio = f1 / f0
    f_opts = ["늘었다", "거의 같다", "조금 줄었다", "절반 아래로 줄었다"]
    f_band = ["1.1배 이상", "0.9배 이상 1.1배 미만", "0.5배 이상 0.9배 미만", "0.5배 미만"]
    f_i = 0 if f_ratio >= 1.1 else 1 if f_ratio >= 0.9 else 2 if f_ratio >= 0.5 else 3
    f_ans = f_opts[f_i]

    gain = l1 - l0
    l_opts = ["5년 이상 늘었다", "2년 이상 ~ 5년 미만 늘었다",
              "0년 이상 ~ 2년 미만 늘었다", "줄었다"]
    l_band = ["5년 이상 증가", "2년 이상 5년 미만 증가", "0년 이상 2년 미만 증가", "0년 미만"]
    l_i = 0 if gain >= 5 else 1 if gain >= 2 else 2 if gain >= 0 else 3
    l_ans = l_opts[l_i]

    # min · max 는 같은 값이면 먼저 나온 것을 고른다. 연도 순으로 넣으니 가장 이른 해가 된다
    fd = yearly_diff(fert)
    f_drop_y = min(fd, key=fd.get)
    ld = yearly_diff(life)
    l_gain_y = max(ld, key=ld.get)
    # 4번은 전년과 그해 값이 모두 있는 해만 비교한다. 결측 때문에 빠진 해는 따로 센다
    l_span = range(START + 1, END + 1)
    l_skipped = [y for y in l_span if y not in ld]
    l_compared = (f"{START + 1}~{END}년 중 전년도와 해당 연도의 기대수명 값이 모두 있는 "
                  f"연도만 비교 대상으로 집계했으며("
                  + (f"결측으로 {', '.join(map(str, l_skipped))}년 제외, "
                     if l_skipped else "결측 없음, ")
                  + f"총 {len(ld)}개 연도 비교)")

    under1 = sorted(y for y, v in fert.items() if v < 1.0)

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다.
        정렬하므로 정답 자리는 값에 따라 달라진다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    k3_years = with_decoys("k3", f_drop_y, fd)          # 전년 값이 있는 2001~2024 의 해
    k4_years = with_decoys("k4", l_gain_y, ld)
    k5_counts = with_decoys("k5", len(under1), range(0, 26))

    def choice(qid, text, options, answer, basis, why):
        assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
        return {"id": qid, "type": "choice", "text": text, "options": options,
                "answer": answer, "basis": basis, "why": why}

    questions = [
        choice("k1", f"{START}년과 비교해 {END}년 대한민국의 합계출산율은 얼마나 달라졌을까요?",
               f_opts, f_ans,
               f"{START}~{END}년 대한민국 합계출산율을 기준으로 {END}년 값을 {START}년 값으로 "
               f"나눈 비율은 {f1:.3f}명 ÷ {f0:.3f}명 = {f_ratio:.4f}배로, "
               f"1.1배 이상 '늘었다' · 0.9~1.1배 '거의 같다' · 0.5~0.9배 '조금 줄었다' · "
               f"0.5배 미만 '절반 아래로 줄었다' 기준에 따라 '{f_ans}'로 판정하였다.",
               f"합계출산율은 {START}년 {f0:.3f}명, {END}년 {f1:.3f}명으로 {END}년 값은 "
               f"{START}년의 {f_ratio:.4f}배이며, {f_band[f_i]}이므로 '{f_ans}'에 해당합니다."),
        choice("k2", f"{START}년과 비교해 {END}년 대한민국의 출생 시 기대수명은 어떻게 달라졌을까요?",
               l_opts, l_ans,
               f"{START}~{END}년 대한민국 출생 시 기대수명을 기준으로 {END}년 값에서 "
               f"{START}년 값을 뺀 차이는 {l1:.2f}세 − {l0:.2f}세 = {gain:+.2f}년으로, "
               f"5년 이상 · 2~5년 · 0~2년 증가 · 0년 미만 기준에 따라 '{l_ans}'로 판정하였다.",
               f"출생 시 기대수명은 {START}년 {l0:.2f}세, {END}년 {l1:.2f}세로 차이는 "
               f"{gain:+.2f}년이며, {l_band[l_i]}이므로 '{l_ans}'에 해당합니다."),
        choice("k3", f"{START + 1}~{END}년 중 대한민국의 합계출산율이 전년보다 가장 크게 감소한 해는 언제일까요?",
               [f"{y}년" for y in k3_years], f"{f_drop_y}년",
               f"{START + 1}~{END}년 대한민국 합계출산율의 전년 대비 차이를 비교한 결과 "
               f"{f_drop_y}년이 {fert[f_drop_y - 1]:.3f}명 → {fert[f_drop_y]:.3f}명"
               f"({fd[f_drop_y]:+.3f}명)으로 감소량이 가장 컸다.",
               f"{f_drop_y}년 합계출산율은 전년 {fert[f_drop_y - 1]:.3f}명에서 "
               f"{fert[f_drop_y]:.3f}명으로 {-fd[f_drop_y]:.3f}명 줄어, 전년 대비 비교한 "
               f"{len(fd)}개 연도 중 감소량이 가장 컸습니다."),
        choice("k4", f"{START + 1}~{END}년 중 대한민국의 출생 시 기대수명이 전년보다 가장 크게 증가한 해는 언제일까요?",
               [f"{y}년" for y in k4_years], f"{l_gain_y}년",
               f"대한민국 출생 시 기대수명의 전년 대비 차이는 {l_compared}, 그 결과 "
               f"{l_gain_y}년이 {life[l_gain_y - 1]:.2f}세 → {life[l_gain_y]:.2f}세"
               f"({ld[l_gain_y]:+.2f}년)으로 증가량이 가장 컸다.",
               f"{l_gain_y}년 출생 시 기대수명은 전년 {life[l_gain_y - 1]:.2f}세에서 "
               f"{life[l_gain_y]:.2f}세로 {ld[l_gain_y]:.2f}년 늘어, 비교한 {len(ld)}개 "
               f"연도 중 증가량이 가장 컸습니다."),
        choice("k5", f"{START}~{END}년 동안 대한민국의 합계출산율이 1.0명 미만이었던 해는 총 몇 년일까요?",
               [f"{n}년" for n in k5_counts], f"{len(under1)}년",
               f"{START}~{END}년 대한민국 합계출산율 중 값이 있는 {len(fert)}개 연도에서 "
               f"1.0명 미만(1.0명은 제외)인 해를 센 결과 "
               + (f"{', '.join(str(y) for y in under1)}년의 " if under1 else "")
               + f"총 {len(under1)}년이었다.",
               f"{START}~{END}년 중 합계출산율이 1.0명 미만인 해는 "
               + (f"{', '.join(f'{y}년({fert[y]:.3f}명)' for y in under1)}으로 "
                  if under1 else "없어 ")
               + f"총 {len(under1)}년입니다."),
    ]

    # 한계 문장의 날짜 · 숫자도 손으로 적지 않는다 — 원본 메타와 위 계산에서 가져온다
    f_upd, f_null = fetched(raw, "korea_fertility_2000_2025.json")
    l_upd, l_null = fetched(raw, "korea_life_expectancy_2000_2025.json")
    upd = f_upd if f_upd == l_upd else f"출산율 {f_upd} · 기대수명 {l_upd}"
    nulls = sorted(set(f_null) | set(l_null))
    half = f0 * 0.5      # 1번 '절반 아래' 경계에 해당하는 END 년 출산율
    # 남녀 값에서 다시 계산한 흔적 — 전년과 값이 완전히 같은 해
    same = [y for y in ld if ld[y] == 0]

    caveat = (
        f"World Bank 공표치이며 World Bank 갱신일 {upd} 기준으로 받은 값입니다. "
        + (f"원본에서 {', '.join(map(str, nulls))}년 값은 비어 있어(null) 계산에서 뺐습니다. "
           if nulls else "")
        + "출산율은 연도마다 UN 세계인구전망 추정치인지 통계청 공표치인지 원본에 표시되지 않고, "
        "기대수명은 세어서 나온 값이 아니라 남녀 기대수명에서 유도한 모형 값입니다. "
        f"최근 연도 값은 나중에 고쳐질 수 있으며, 특히 1번은 {END}년 출산율"
        f"({f1:.3f}명)이 {half:.3f}명 아래로 고쳐지면 정답이 '{f_opts[3]}'로 바뀝니다. "
        f"이 숫자가 통계청 발표나 다른 곳에서 본 숫자와 다를 수 있는 것은 World Bank가 "
        f"{upd} 갱신 때 올린 값을 받았고, 출산율은 연도마다 UN 추정치인지 통계청 "
        "공표치인지 표시가 없으며, 기대수명은 통계청이 낸 전체 값이 아니라 World Bank가 "
        "남녀 값에서 다시 계산한 값이기 때문입니다"
        + (f"(예: {', '.join(f'{y - 1}년과 {y}년' for y in same)} 기대수명이 "
           f"{life[same[0]]:.2f}세로 똑같습니다)" if same else "")
        + ".")

    return {"id": TID, "emoji": "📉", "title": "출산율과 기대수명 25년",
            "blurb": f"{START}년부터 {END}년까지, 대한민국의 출산율과 기대수명",
            "source": "World Bank Open Data", "source_url": "https://data.worldbank.org/",
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
