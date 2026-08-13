# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""roadmap — 고정 설계에서 파라미터를 누적 변경하며 I-V를 재실행하는 러너.

Griddler PRO §5.1 Efficiency Improvement Diagram 상당. 설계는
docs/superpowers/specs/2026-08-13-roadmap-runner-design.md 참조.

경계(중요): 이 모듈은 **탐색하지 않는다.** 시나리오 파일에 적힌 값을 그대로
엔진에 넣고 돌릴 뿐이다. 최적 설계 탐색은 optimize_grid의 몫이며, 두 기능을
합치면 "이 막대가 파라미터 변경의 효과인가 재최적화의 효과인가"를 구분할 수
없게 된다. 최적 설계가 필요한 분석은 스펙 §2의 2단계 워크플로우를 따른다.

엔진(2L_FEST.py)과 adapter.py는 수정하지 않는다 — evaluate_existing_simulation을
그대로 호출한다.
"""
import hashlib
import json
import os

from .optimizer import (
    SCENARIO_AS_CURED,
    SCENARIO_ENGINE_DEFAULT,
    SCENARIO_MEASURED,
)

SCHEMA_ID = "2lfest.roadmap/1"

# 데이터 출처 태그. 기능 명세 §3.2가 제안한 provenance 강제를 이 범위에서 실현한다.
#   measured — 랩/협력기관 실측값
#   derived  — 다른 계산의 산출물 (optimize_grid 최적해 등)
#   assumed  — 가정값 (문헌·관행·미확보)
PROV_TAGS = ("measured", "assumed", "derived")

# engine.scenario 문자열 → optimizer의 시나리오 상수.
# as_cured는 v28.48에서 가압 효과 대조군이 as-printed → as-cured로 바뀌며
# 도입된 상수라 함께 노출한다.
SCENARIO_MAP = {
    "measured": SCENARIO_MEASURED,
    "as_cured": SCENARIO_AS_CURED,
    "default": SCENARIO_ENGINE_DEFAULT,
}

# baseline 블록에서 grid_params가 아닌 키 (엔진에 넘기면 안 된다).
_RESERVED = ("label", "note")


def _grid_keys(baseline):
    return {k for k in baseline if k not in _RESERVED}


def validate_scenario(sc):
    """시나리오 dict를 검증한다. 위반 시 ValueError.

    조용한 통과를 만들지 않는 것이 이 함수의 존재 이유다 — 오타난 키를
    무시하면 '에러 없이 그럴듯한 틀린 값'이 나온다(v28.43 전례).
    """
    if not isinstance(sc, dict):
        raise ValueError("시나리오 최상위는 object여야 한다")
    if sc.get("schema") != SCHEMA_ID:
        raise ValueError(
            f"schema 불일치: {sc.get('schema')!r} (기대 {SCHEMA_ID!r})")

    baseline = sc.get("baseline")
    if not isinstance(baseline, dict):
        raise ValueError("baseline 블록이 없거나 object가 아니다")
    if not baseline.get("label"):
        raise ValueError("baseline.label이 필요하다")

    grid_keys = _grid_keys(baseline)
    if not grid_keys:
        raise ValueError("baseline에 grid 파라미터가 하나도 없다")

    eng = sc.get("engine", {})
    if not isinstance(eng, dict):
        raise ValueError("engine 블록은 object여야 한다")
    eng_sc = eng.get("scenario", "measured")
    if eng_sc not in SCENARIO_MAP:
        raise ValueError(
            f"engine.scenario 알 수 없음: {eng_sc!r} "
            f"(허용: {sorted(SCENARIO_MAP)})")

    cases = sc.get("cases", [])
    if not isinstance(cases, list):
        raise ValueError("cases는 배열이어야 한다")

    prov = sc.get("provenance", {})
    if not isinstance(prov, dict):
        raise ValueError("provenance 블록은 object여야 한다")

    labels = [baseline["label"]]
    changed_keys = set()
    for i, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            raise ValueError(f"cases[{i - 1}]가 object가 아니다")
        label = case.get("label")
        if not label:
            raise ValueError(f"cases[{i - 1}].label이 필요하다")
        labels.append(label)

        changes = case.get("set")
        if not isinstance(changes, dict) or not changes:
            raise ValueError(
                f"cases[{i - 1}] ({label}): set이 비었다 — "
                "아무것도 바꾸지 않는 케이스는 실수다")
        unknown = sorted(set(changes) - grid_keys)
        if unknown:
            raise ValueError(
                f"cases[{i - 1}] ({label}): baseline에 없는 키 {unknown} — "
                "오타이거나 baseline에 추가해야 한다")
        changed_keys |= set(changes)

    dup = sorted({x for x in labels if labels.count(x) > 1})
    if dup:
        raise ValueError(
            f"label 중복 {dup} — --resume이 label을 키로 쓰므로 유일해야 한다")

    # 케이스가 바꾸는 키는 provenance 필수. figure의 주장이 걸린 값이다.
    missing = sorted(changed_keys - set(prov))
    if missing:
        raise ValueError(
            f"provenance 누락 {missing} — 케이스가 바꾸는 키는 "
            f"measured/assumed/derived 태그가 필수다")

    for key, entry in prov.items():
        if not isinstance(entry, dict) or entry.get("tag") not in PROV_TAGS:
            raise ValueError(
                f"provenance[{key}].tag 불량: {entry!r} "
                f"(허용: {list(PROV_TAGS)})")


def load_scenario(path):
    """JSON 시나리오를 읽고 검증한다. 반환 dict에 _meta(파일명·해시)를 주입한다."""
    with open(path, "rb") as fh:
        raw = fh.read()
    sc = json.loads(raw.decode("utf-8"))
    validate_scenario(sc)
    sc["_meta"] = {
        "file": os.path.basename(path),
        "sha256": hashlib.sha256(raw).hexdigest()[:12],
    }
    return sc


def expand_cases(sc):
    """누적 전개 — 각 케이스는 직전 상태 위에 set을 얹는다.

    순수 함수. 입력 dict를 변경하지 않는다.
    반환: [{"case_index", "label", "note", "grid_params"}, ...]
    """
    baseline = sc["baseline"]
    state = {k: v for k, v in baseline.items() if k not in _RESERVED}
    out = [{
        "case_index": 0,
        "label": baseline["label"],
        "note": baseline.get("note", ""),
        "grid_params": dict(state),
    }]
    for i, case in enumerate(sc.get("cases", []), start=1):
        state = dict(state)
        state.update(case["set"])
        out.append({
            "case_index": i,
            "label": case["label"],
            "note": case.get("note", ""),
            "grid_params": dict(state),
        })
    return out
