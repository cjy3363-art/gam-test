# -*- coding: utf-8 -*-
"""한국인은 고기를 얼마나 먹을까? — 대한민국 1인당 육류 공급량 (2000~2023).

build_topics.py 가 불러서 다른 주제와 함께 만든다. 목록에서는 '서울·도쿄·런던·
싱가포르'(cities) 칸을 지우고 그 자리에 들어간다. 이 파일만 따로 돌려
topics/korea-meat-supply.json 하나만 만들 수도 있다.

**모든 숫자는 raw/ 의 OWID 원본 CSV에서 계산합니다.** 빈 값은 빼고 세며,
필요한 연도가 비어 있으면 다른 해로 대신하지 않고 '계산 불가'로 멈춥니다.
전체 육류는 전체 육류 파일에서만 읽고, 종류별 값을 더해 만들지 않습니다.

원본은 FAO 식품수급표를 OWID가 1인당(kg/인/년)으로 정리한 것으로, 2009년까지는
구 방법론, 2010년부터는 신 방법론 값을 이어 붙였다 (OWID 메타데이터 기준).

실행 (저장소 최상위에서):
    python tools/korea_meat_supply.py
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

START, END = 2000, 2023
TID = "korea-meat-supply"
REPLACES = "cities"                              # 목록에서 이 칸을 지우고 그 자리에 넣는다
TOTAL_FILE = "korea-meat-supply-total.csv"
TYPE_FILE = "korea-meat-supply-by-type.csv"
# 원본 CSV 의 실제 열 이름 (가로형: 육류 종류가 열로 나뉘어 있다)
MEAT = "Per capita consumption of meat"          # 전체 육류
PIG = "Pigmeat"                                  # 돼지고기
BEEF = "Beef and buffalo"                        # 소 · 물소고기
POULTRY = "Poultry"                              # 가금육 (닭고기만이 아니다)


def table(raw: Path, fname: str, cols: list[str]) -> dict[str, dict[int, Decimal]]:
    """Code 가 KOR 인 행에서 열 → {연도: 값}. 열이 없으면 지표를 추측하지 않고 멈추고,
    같은 해가 두 번 나오면 하나를 고르지 않고 멈춘다. 빈 값은 관측치로 치지 않는다."""
    reader = csv.DictReader(io.open(raw / fname, encoding="utf-8"))
    missing = [c for c in ["Entity", "Code", "Year", *cols] if c not in reader.fieldnames]
    if missing:
        raise ValueError(f"계산 불가: {fname} 에 {', '.join(missing)} 열이 없습니다")
    out: dict[str, dict[int, Decimal]] = {c: {} for c in cols}
    seen = set()
    for r in reader:
        y = int(r["Year"])
        if r["Code"] != "KOR" or not START <= y <= END:
            continue
        if y in seen:
            raise ValueError(f"판정 불가: {fname} 대한민국 {y}년 행이 두 번 있습니다")
        seen.add(y)
        for c in cols:
            if r[c].strip() != "":
                out[c][y] = Decimal(r[c])        # 원본 소수점을 그대로 유지
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
    """소수 첫째 자리에서 사사오입해 정수로."""
    return int(x.quantize(Decimal(1), ROUND_HALF_UP))


def korea_meat_supply(raw: Path = RAW) -> dict:
    meat = table(raw, TOTAL_FILE, [MEAT])[MEAT]
    kinds = table(raw, TYPE_FILE, [PIG, BEEF, POULTRY])

    m0, m1 = need(meat, START, "전체 육류"), need(meat, END, "전체 육류")
    pig = need(kinds[PIG], END, "돼지고기")
    beef = need(kinds[BEEF], END, "소 · 물소고기")
    poultry = need(kinds[POULTRY], END, "가금육")

    # 반올림은 마지막 결과에만 한다. 최댓값 비교는 원본 값 그대로 한다
    gain = whole(m1 - m0)                            # 1번
    pig_n, beef_n, poultry_n = whole(pig), whole(beef), whole(poultry)
    top_y = only(meat, max, "대한민국 1인당 전체 육류 공급량 최댓값")
    second = max((y for y in meat if y != top_y), key=meat.get)

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다.
        값 순서로 놓으므로 정답 자리는 문항마다 달라진다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    # 수치 문항의 오답은 정답에서 일정 간격씩 떨어진 정수 중에서 뽑는다
    m5_opts = with_decoys("m5", top_y, meat)

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

    kg = lambda v: f"{v}kg"
    yr = lambda v: f"{v}년"
    OWID = "OWID · FAO 식품수급표"

    def of_year(what, col, n, qid, note=""):
        return slider(
            qid, f"{END}년 대한민국의 1인당 연간 {what} 공급량은 약 몇 kg이었을까요? "
            "(단위: kg/인/년, 정수)",
            n, "kg", 0, 80,
            f"{OWID} 종류별 육류 공급량 CSV의 '{col}' 열(kg/인/년)에서 대한민국(KOR) {END}년 "
            "값을 그대로 읽어 소수 첫째 자리에서 반올림했다.",
            f"원본에 적힌 {END}년 대한민국의 1인당 {what} 공급량을 정수로 반올림하면 약 {kg(n)}입니다. "
            f"시장에 나온 양을 인구로 나눈 공급량이며, 한 사람이 실제로 먹은 양과는 다릅니다.{note}")

    questions = [
        slider("m1", f"{START}년 대비 {END}년 대한민국의 1인당 연간 전체 육류 공급량은 약 몇 kg "
               "증가했을까요? (단위: kg/인/년, 정수)",
               gain, "kg", 0, 80,
               f"{OWID} 전체 육류 공급량 CSV의 '{MEAT}' 열(kg/인/년) 기준으로 대한민국(KOR)의 "
               f"{END}년 값 − {START}년 값을 반올림 없이 계산한 뒤 소수 첫째 자리에서 반올림했다.",
               f"대한민국의 1인당 전체 육류 공급량은 {START}년 약 {kg(whole(m0))}에서 {END}년 약 "
               f"{kg(whole(m1))}으로 약 {kg(gain)} 늘었습니다. 실제 섭취량이 아니라 공급량이며, "
               "2009년까지는 FAO 구 방법론, 2010년부터는 신 방법론 값입니다."),
        of_year("돼지고기", PIG, pig_n, "m2"),
        of_year("소·물소고기", BEEF, beef_n, "m3", " 물소고기도 포함한 값입니다."),
        of_year("가금육", POULTRY, poultry_n, "m4", " 닭고기만이 아니라 가금류 고기 전체입니다."),
        choice("m5", f"{START}~{END}년 중 대한민국의 1인당 연간 전체 육류 공급량이 가장 많았던 해는 "
               "언제일까요? (단위: 연도)",
               [yr(v) for v in m5_opts], yr(top_y),
               f"{OWID} 전체 육류 공급량 CSV의 '{MEAT}' 열(kg/인/년) 기준으로 {START}~{END}년 "
               f"대한민국(KOR) 값이 있는 {len(meat)}개 연도의 원본 값을 반올림 없이 비교해 최댓값을 "
               "기록한 해를 찾았다.",
               f"반올림하지 않은 원본 값으로 비교하면 {top_y}년 약 {kg(whole(meat[top_y]))}이 "
               f"{len(meat)}개 연도 중 가장 많았습니다. 두 번째로 많은 {second}년은 약 "
               f"{kg(whole(meat[second]))}"
               + ("으로 정수로는 같아 보이지만 원본 값은 "
                  f"{top_y}년이 더 큽니다." if whole(meat[second]) == whole(meat[top_y]) else "이었습니다.")),
    ]

    caveat = (
        "FAO 식품수급표를 Our World in Data가 1인당(kg/인/년)으로 정리한 값입니다. 시장에 공급된 "
        "고기의 양이라 버려지는 양까지 들어 있어, 한 사람이 실제로 먹은 양보다 많을 수 있습니다. "
        "2009년까지는 FAO 구 방법론, 2010년부터는 신 방법론 값을 이어 붙인 시계열이라, 2010년을 "
        "사이에 둔 비교에는 방법 차이가 섞여 있습니다. 소 · 물소고기는 물소를, 가금육은 닭 외의 "
        "가금류를 포함합니다. 화면의 숫자는 정수로 반올림해 보여 줍니다.")

    return {"id": TID, "emoji": "🥩", "title": "한국인은 고기를 얼마나 먹을까?",
            "blurb": f"{START}년부터 {END}년 1인당 육류 공급량",
            "source": "Our World in Data · FAO",
            "source_url": "https://ourworldindata.org/grapher/meat-supply-per-person",
            "caveat": caveat,
            "questions": questions}


def main() -> None:
    """이 주제 하나만 만든다. 다른 주제 파일은 건드리지 않는다."""
    t = korea_meat_supply()             # 계산 · 검증이 하나라도 실패하면 여기서 멈춰 아무것도 쓰지 않는다
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
