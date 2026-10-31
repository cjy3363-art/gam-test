# -*- coding: utf-8 -*-
"""한국의 자동차는 얼마나 늘었을까? — 자동차 등록대수(2000~2024)와 도로교통사고 사망률(2000~2021).

build_topics.py 가 불러서 다른 주제와 함께 만든다. 목록에서는 '지진은 얼마나
자주'(quakes) 칸을 지우고 그 자리에 들어간다. 이 파일만 따로 돌려
topics/korea-vehicle-road-safety.json 하나만 만들 수도 있다.

**모든 숫자는 raw/ 의 원본에서 계산합니다.**
- 자동차 등록대수: 국토교통부 통계누리 '자동차등록대수현황_연도별'(양식 1244) 조회 응답.
  2000~2014년은 형식 561, 2015년부터는 형식 562 이고 열 순서가 달라, 열 번호를 적지 않고
  columns 파일의 열 이름으로 '총계 › 계' · '승용 › 계' 열을 찾는다. 전국 값이 그대로 있어
  지역을 더하지 않는다. 연도별 값은 12월 말 등록대수다.
- 도로교통사고 사망률: OWID · WHO 세계보건추정치(인구 10만 명당). OECD/ITF 사망자 수와는
  출처 · 정의가 달라 섞지 않는다.

실행 (저장소 최상위에서):
    python tools/korea_vehicle_road_safety.py
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

START, END = 2000, 2024                          # 자동차 등록대수
R_END = 2021                                     # 사망률은 원본이 2021년까지다
TID = "korea-vehicle-road-safety"
REPLACES = "quakes"                              # 목록에서 이 칸을 지우고 그 자리에 넣는다
# (형식, 시작 연도) — 한 번에 5년씩 받은 응답 파일
CHUNKS = ((561, 2000), (561, 2005), (561, 2010), (562, 2015), (562, 2020))
TOTAL_GROUP = ("합계", "총계")                   # 형식마다 이름이 다르다
CAR_GROUP = ("승용차", "승용")
RATE_FILE = "korea-road-death-rate.csv"
RATE = "Death rate from road injury among both sexes"   # 인구 10만 명당


def column(style: int, groups: tuple[str, ...]) -> str:
    """columns 파일에서 '<그룹> › 계' 열의 번호를 찾는다. 없거나 여럿이면 멈춘다."""
    cols = json.load(io.open(RAW / f"korea-vehicle-registrations_columns_{style}.json",
                             encoding="utf-8"))["data"]
    name = {c["DATA_DIV_ID"]: c["DATA_DIV_NM"] for c in cols}
    hits = [str(c["DATA_DIV_ID"]) for c in cols
            if c["DATA_DIV"] == "M" and c["DATA_DIV_NM"] == "계"
            and name.get(c["UP_DATA_DIV_ID"]) in groups]
    if len(hits) != 1:
        raise ValueError(f"계산 불가: 형식 {style} 에서 {'/'.join(groups)} › 계 열을 하나로 정할 수 없습니다")
    return hits[0]


def registrations(raw: Path) -> tuple[dict[int, int], dict[int, int]]:
    """연도 → (전체 등록대수, 승용차 등록대수). '-' 같은 빈 값은 관측치로 치지 않는다."""
    total: dict[int, int] = {}
    cars: dict[int, int] = {}
    for style, a in CHUNKS:
        t_col, c_col = column(style, TOTAL_GROUP), column(style, CAR_GROUP)
        body = json.load(io.open(raw / f"korea-vehicle-registrations_{style}_{a}_{a + 4}.json",
                                 encoding="utf-8"))
        if body.get("result") is not True:
            raise ValueError(f"계산 불가: 형식 {style} {a}~{a + 4} 응답이 실패입니다 ({body.get('msg')})")
        for r in body["data"]:
            y = int(r["0"])
            if not START <= y <= END:
                continue
            if y in total or y in cars:
                raise ValueError(f"판정 불가: 자동차 등록대수 {y}년 행이 두 번 있습니다")
            if r.get(t_col, "-").strip().isdigit():
                total[y] = int(r[t_col])
            if r.get(c_col, "-").strip().isdigit():
                cars[y] = int(r[c_col])
    return total, cars


def death_rate(raw: Path) -> dict[int, Decimal]:
    out: dict[int, Decimal] = {}
    for r in csv.DictReader(io.open(raw / RATE_FILE, encoding="utf-8")):
        y = int(r["Year"])
        if r["Code"] != "KOR" or not START <= y <= R_END:
            continue
        if y in out:
            raise ValueError(f"판정 불가: 도로교통사고 사망률 {y}년 행이 두 번 있습니다")
        if r[RATE].strip():
            out[y] = Decimal(r[RATE])
    return out


def need(s: dict, year: int, what: str):
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
    return int(Decimal(x).quantize(Decimal(1), ROUND_HALF_UP))


def korea_vehicle_road_safety(raw: Path = RAW) -> dict:
    total, cars = registrations(raw)
    rate = death_rate(raw)
    if RATE not in next(csv.reader(io.open(raw / RATE_FILE, encoding="utf-8"))):
        raise ValueError(f"계산 불가: {RATE_FILE} 에 '{RATE}' 열이 없습니다")

    t0, t1 = need(total, START, "자동차 전체 등록대수"), need(total, END, "자동차 전체 등록대수")
    c0, c1 = need(cars, START, "승용차 등록대수"), need(cars, END, "승용차 등록대수")
    r0, r1 = need(rate, START, "도로교통사고 사망률"), need(rate, R_END, "도로교통사고 사망률")
    if r0 - r1 <= 0:
        raise ValueError(f"판정 불가: 사망률이 {START}년 {r0} → {R_END}년 {r1}로 감소하지 않았습니다")

    # 반올림은 마지막 결과에만 한다. 최댓값 비교는 원본 값 그대로 한다
    added = whole(Decimal(t1 - t0) / 10000)          # 1번 · 만 대
    share = whole(Decimal(c1) / Decimal(t1) * 100)   # 2번 · %
    top_y = only(total, max, "자동차 전체 등록대수 최댓값")
    times = whole(Decimal(c1) / Decimal(c0))         # 4번 · 배
    drop = whole(r0 - r1)                            # 5번 · 명/10만 명

    def with_decoys(qid, answer, pool):
        """오답 3개를 pool 에서 뽑아 정답과 함께 오름차순으로 놓는다.
        시드를 문항 id 로 고정해 다시 만들어도 같은 보기가 나온다.
        값 순서로 놓으므로 정답 자리는 문항마다 달라진다."""
        decoys = random.Random(f"{TID}-{qid}").sample(
            sorted(set(pool) - {answer}), 3)
        return sorted([answer, *decoys])

    near = lambda a, step, lo=0: [a + step * k for k in range(-3, 4) if a + step * k > lo]
    v1_opts = with_decoys("v1", added, near(added, 300))
    v2_opts = with_decoys("v2", share, [v for v in near(share, 6) if v < 100])
    v3_opts = with_decoys("v3", top_y, total)
    v4_opts = with_decoys("v4", times, near(times, 1, 1))
    v5_opts = with_decoys("v5", drop, near(drop, 4))

    def choice(qid, text, options, answer, basis, why):
        assert answer in options, f"{qid}: 정답이 선택지에 없습니다"
        assert len(set(options)) == 4, f"{qid}: 보기가 4개가 아니거나 겹칩니다"
        return {"id": qid, "type": "choice", "text": text, "options": options,
                "answer": answer, "basis": basis, "why": why}

    man = lambda v: f"{v:,}만 대"
    yr = lambda v: f"{v}년"
    MOLIT = "국토교통부 자동차등록대수현황_연도별(12월 말 등록대수, 대)"
    WHO = "OWID · WHO 세계보건추정치 도로교통사고 사망률(인구 10만 명당)"

    questions = [
        choice("v1", f"{START}년 대비 {END}년 대한민국의 자동차 전체 등록 대수는 약 몇 만 대 "
               "증가했을까요? (단위: 만 대, 정수)",
               [man(v) for v in v1_opts], man(added),
               f"{MOLIT} 기준으로 전국 총계(승용 · 승합 · 화물 · 특수 포함)의 ({END}년 값 − {START}년 값)"
               " ÷ 10,000을 반올림 없이 계산한 뒤 소수 첫째 자리에서 반올림했다.",
               f"전국 자동차 등록대수는 {START}년 {t0:,}대, {END}년 {t1:,}대로 차이 {t1 - t0:,}대를 "
               f"만 대로 나타내면 약 {man(added)}입니다. 등록된 차량 수이며 소유자 수나 실제 운행 차량 "
               "수가 아닙니다."),
        choice("v2", f"{END}년 대한민국의 전체 등록 자동차 중 승용차가 차지하는 비중은 약 몇 %였을까요? "
               "(단위: %, 정수)",
               [f"{v}%" for v in v2_opts], f"{share}%",
               f"{MOLIT} 기준으로 {END}년 (승용 계 ÷ 전국 총계) × 100을 반올림 없이 계산한 뒤 소수 첫째 "
               "자리에서 반올림했다.",
               f"{END}년 승용차 {c1:,}대 ÷ 전체 {t1:,}대 × 100 = 약 {share}%입니다. 등록 자동차 가운데 "
               "승용차의 비율이며, 승용차를 가진 가구의 비율이 아닙니다."),
        choice("v3", f"{START}~{END}년 중 대한민국의 자동차 전체 등록 대수가 가장 많았던 해는 "
               "언제일까요? (단위: 연도)",
               [yr(v) for v in v3_opts], yr(top_y),
               f"{MOLIT} 기준으로 {START}~{END}년 전국 총계 {len(total)}개 연도의 원본 값을 비교해 "
               "최댓값을 기록한 해를 찾았다.",
               f"{top_y}년 {total[top_y]:,}대가 {len(total)}개 연도 중 가장 많았습니다. "
               f"{START}년은 {t0:,}대였습니다."),
        choice("v4", f"{START}년 대비 {END}년 대한민국의 승용차 등록 대수는 약 몇 배가 되었을까요? "
               "(단위: 배, 정수)",
               [f"{v}배" for v in v4_opts], f"{times}배",
               f"{MOLIT} 기준으로 승용 계의 {END}년 값 ÷ {START}년 값을 반올림 없이 계산한 뒤 소수 첫째 "
               "자리에서 반올림했다.",
               f"승용차 등록대수는 {START}년 {c0:,}대에서 {END}년 {c1:,}대로, {c1:,} ÷ {c0:,}의 값을 "
               f"정수로 반올림하면 약 {times}배입니다."),
        choice("v5", f"{START}년 대비 {R_END}년 대한민국의 인구 10만 명당 도로교통사고 사망률은 약 몇 명 "
               "감소했을까요? (단위: 명/인구 10만 명, 정수)",
               [f"{v}명" for v in v5_opts], f"{drop}명",
               f"{WHO} 기준으로 대한민국(KOR)의 {START}년 값 − {R_END}년 값을 반올림 없이 계산한 뒤 "
               "소수 첫째 자리에서 반올림했다.",
               f"WHO 추정 사망률은 {START}년 인구 10만 명당 {r0}명, {R_END}년 {r1}명으로 "
               f"{r0} − {r1} = {r0 - r1}, 정수로 약 {drop}명 줄었습니다. 사망자 수가 아니라 인구 대비 "
               "비율이며, 자동차 증가와의 인과관계를 뜻하지 않습니다."),
    ]

    caveat = (
        "자동차 등록대수는 국토교통부 '자동차등록대수현황'(승인통계)의 12월 말 등록대수로, 등록된 "
        "차량 수이지 소유자 수나 실제로 굴러가는 차량 수가 아닙니다. 승용 · 승합 · 화물 · 특수 구분은 "
        "자동차관리법 시행규칙의 분류를 따릅니다. 통계누리 화면이 표를 채울 때 쓰는 조회 응답을 "
        "받은 값입니다. 도로교통사고 사망률은 WHO 세계보건추정치(OWID 가공)로 2021년까지만 있고, "
        "경찰청 · OECD가 집계한 사망자 수와는 정의가 달라 숫자가 다릅니다. 화면의 숫자는 정수로 "
        "반올림해 보여 줍니다.")

    return {"id": TID, "emoji": "🚗", "title": "한국의 자동차는 얼마나 늘었을까?",
            "blurb": f"{START}년부터 {END}년 자동차 등록과 도로교통",
            "source": "국토교통부 · OWID(WHO)",
            "source_url": "https://stat.molit.go.kr/portal/cate/statView.do?hRsId=58&hFormId=1244",
            "caveat": caveat,
            "questions": questions}


def main() -> None:
    """이 주제 하나만 만든다. 다른 주제 파일은 건드리지 않는다."""
    t = korea_vehicle_road_safety()     # 계산 · 검증이 하나라도 실패하면 여기서 멈춰 아무것도 쓰지 않는다
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
