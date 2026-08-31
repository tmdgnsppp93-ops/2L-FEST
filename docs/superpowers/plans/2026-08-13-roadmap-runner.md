# Roadmap 러너 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 시나리오 JSON에 적힌 baseline 설계에서 파라미터를 순차 누적 변경하며 각 케이스의 I-V를 재실행하고, 결과를 CSV에 누적한 뒤 Jsc/Voc/FF/Eff 4-panel PNG로 출력하는 CLI 러너를 만든다.

**Architecture:** 엔진(`GEDOS.py`)과 `front_electrode/adapter.py`를 **한 줄도 수정하지 않는다.** 신규 모듈이 기존 `evaluate_existing_simulation()`을 그대로 호출하므로 기존 스윕·최적화 경로가 새 코드에 도달할 수 없고, "기존 결과 비트 불변"이 구조적으로 성립한다. 순수 함수(로드·검증·누적전개)와 부작용(FEM 실행·CSV·플롯)을 파일 단위로 분리해, 로직 대부분을 FEM 없이 밀리초 단위로 테스트한다.

**Tech Stack:** Python ≥3.10, 표준 라이브러리 `json`·`csv`·`hashlib`·`subprocess`, numpy/matplotlib(이미 의존성), pytest.

**Spec:** `docs/superpowers/specs/2026-08-13-roadmap-runner-design.md` (커밋 `8dc0ded`)

## Global Constraints

- **엔진 `GEDOS.py`와 `front_electrode/adapter.py`는 수정 금지.** 유일하게 수정하는 기존 파일은 `front_electrode/__init__.py`이며 export 추가(가산적)만 한다.
- **PyYAML 금지.** 시나리오는 stdlib `json`. (PyInstaller 번들 앱이라 런타임 의존성 추가에 비용이 있다.)
- 모든 신규 `.py` 파일은 저장소 SPDX 헤더로 시작한다:
  ```python
  # SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
  #   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
  # SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
  ```
- CSV 인코딩은 `utf-8-sig` (기존 `export_csv`·`optimize_m10.py` 규약).
- 잘못된 입력은 **조용히 무시하지 말고 `ValueError`를 던진다.** 이 저장소의 반복 사고(v28.43 `n_probe_points=0`, `extraction_method` 죽은 파라미터)가 전부 "조용히 무시되고 그럴듯한 틀린 값"이었다.
- FEM이 필요한 테스트는 `cell_mm=20.0` + `AX=36` / `NPTS=6` (기존 `tests/test_optimizer.py` 관용구)를 쓴다. M10은 `slow` 마커 대상이며 이 계획에 포함하지 않는다.
- 각 태스크 종료 시 `pytest -m "not slow" tests/test_roadmap.py -v`가 초록이어야 한다. 전체 베이스라인은 **94 passed / 2 deselected / 6 xfailed** (2026-08-13 실측).
- 커밋 메시지 말미에 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

## File Structure

| 파일 | 책임 |
|---|---|
| `front_electrode/roadmap.py` | 시나리오 로드·검증·누적전개(순수) + provenance 수집 + CSV 행 조립 + 실행 루프 |
| `front_electrode/roadmap_plot.py` | CSV → 4-panel PNG. FEM 재실행 없이 그림만 다시 그릴 수 있어야 하므로 분리 |
| `scripts/run_roadmap.py` | argparse CLI. 엔진 로드(conftest 하네스) + 두 모듈 연결 |
| `scripts/scenarios/unist_tco.json` | 최소 동작 예시 시나리오 |
| `tests/test_roadmap.py` | 단위·회귀 테스트 |
| `front_electrode/__init__.py` | export 추가 (유일한 기존 파일 수정) |

---

### Task 1: 시나리오 스키마 — 로드·검증·누적 전개

순수 함수만 다룬다. FEM도 파일 I/O도(테스트의 tmp 파일 제외) 없다.

**Files:**
- Create: `front_electrode/roadmap.py`
- Create: `tests/test_roadmap.py`
- Modify: `front_electrode/__init__.py` (import 블록과 `__all__`에 추가)

**Interfaces:**
- Consumes: `front_electrode.optimizer.SCENARIO_MEASURED`, `SCENARIO_AS_CURED`, `SCENARIO_ENGINE_DEFAULT` (이미 존재)
- Produces:
  - `SCHEMA_ID: str = "gedos.roadmap/1"`
  - `PROV_TAGS: tuple = ("measured", "assumed", "derived")`
  - `SCENARIO_MAP: dict[str, dict]` — 문자열 → 시나리오 상수
  - `validate_scenario(sc: dict) -> None` — 위반 시 `ValueError`
  - `load_scenario(path: str) -> dict` — 검증 통과한 dict. `sc["_meta"] = {"file": str, "sha256": str}` 주입
  - `expand_cases(sc: dict) -> list[dict]` — 각 원소 `{"case_index": int, "label": str, "note": str, "grid_params": dict}`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_roadmap.py` 신규 생성:

```python
# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""roadmap 러너 테스트.

순수 함수(로드·검증·누적전개·행 조립)는 FEM 없이 즉시 검증한다.
엔진이 필요한 회귀 테스트만 20mm 소셀 + coarse 메시로 돌린다
(tests/test_optimizer.py의 AX/NPTS 관용구와 동일).
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from front_electrode import (  # noqa: E402
    SCHEMA_ID,
    expand_cases,
    load_scenario,
    validate_scenario,
)

AX = 36
NPTS = 6


def _min_scenario():
    """검증을 통과하는 최소 시나리오 (baseline + 1 case)."""
    return {
        "schema": SCHEMA_ID,
        "name": "unit test",
        "engine": {"mode": "tandem", "npts": NPTS, "scenario": "measured"},
        "baseline": {
            "label": "base",
            "cell_w_mm": 20.0, "cell_h_mm": 20.0,
            "finger_spacing_mm": 1.8, "w_finger_um": 50.0,
            "n_busbars": 2, "w_busbar_mm": 0.2,
            "n_probe_points": 10,
            "rho_contact_mohm_cm2": 10.0,
        },
        "cases": [
            {"label": "lower rc", "note": "test",
             "set": {"rho_contact_mohm_cm2": 2.0}},
        ],
        "provenance": {
            "rho_contact_mohm_cm2": {"tag": "assumed", "note": "test"},
        },
    }


def test_expand_cumulative():
    """케이스가 직전 상태 위에 누적되고, label/note는 grid_params에 섞이지 않는다."""
    sc = _min_scenario()
    sc["cases"].append({"label": "coarser", "set": {"finger_spacing_mm": 2.4}})
    sc["provenance"]["finger_spacing_mm"] = {"tag": "derived", "note": "test"}

    cases = expand_cases(sc)

    assert [c["case_index"] for c in cases] == [0, 1, 2]
    assert [c["label"] for c in cases] == ["base", "lower rc", "coarser"]
    # baseline
    assert cases[0]["grid_params"]["rho_contact_mohm_cm2"] == 10.0
    assert cases[0]["grid_params"]["finger_spacing_mm"] == 1.8
    # case1: rc만 바뀜
    assert cases[1]["grid_params"]["rho_contact_mohm_cm2"] == 2.0
    assert cases[1]["grid_params"]["finger_spacing_mm"] == 1.8
    # case2: rc는 누적 유지, spacing이 바뀜
    assert cases[2]["grid_params"]["rho_contact_mohm_cm2"] == 2.0
    assert cases[2]["grid_params"]["finger_spacing_mm"] == 2.4
    # label/note는 엔진에 넘어가면 안 된다
    for c in cases:
        assert "label" not in c["grid_params"]
        assert "note" not in c["grid_params"]


def test_expand_does_not_mutate_input():
    """전개가 원본 시나리오 dict를 건드리지 않는다."""
    sc = _min_scenario()
    before = json.dumps(sc, sort_keys=True)
    expand_cases(sc)
    assert json.dumps(sc, sort_keys=True) == before


def test_rejects_unknown_key():
    """set에 baseline에 없는 키 → ValueError (조용히 무시 금지)."""
    sc = _min_scenario()
    sc["cases"][0]["set"] = {"rho_contakt_mohm_cm2": 2.0}   # 오타
    sc["provenance"]["rho_contakt_mohm_cm2"] = {"tag": "assumed", "note": "x"}
    with pytest.raises(ValueError, match="rho_contakt_mohm_cm2"):
        validate_scenario(sc)


def test_requires_provenance_for_changed_key():
    """케이스가 바꾸는 키에 provenance가 없으면 ValueError."""
    sc = _min_scenario()
    sc["provenance"] = {}
    with pytest.raises(ValueError, match="provenance"):
        validate_scenario(sc)


def test_rejects_bad_provenance_tag():
    sc = _min_scenario()
    sc["provenance"]["rho_contact_mohm_cm2"]["tag"] = "guessed"
    with pytest.raises(ValueError, match="guessed"):
        validate_scenario(sc)


def test_rejects_duplicate_label():
    """--resume이 label을 키로 쓰므로 중복은 조용한 오작동을 만든다."""
    sc = _min_scenario()
    sc["cases"].append({"label": "lower rc", "set": {"w_finger_um": 40.0}})
    sc["provenance"]["w_finger_um"] = {"tag": "derived", "note": "x"}
    with pytest.raises(ValueError, match="label"):
        validate_scenario(sc)


def test_rejects_bad_schema_id():
    sc = _min_scenario()
    sc["schema"] = "gedos.roadmap/99"
    with pytest.raises(ValueError, match="schema"):
        validate_scenario(sc)


def test_rejects_unknown_engine_scenario():
    sc = _min_scenario()
    sc["engine"]["scenario"] = "hand-wavy"
    with pytest.raises(ValueError, match="hand-wavy"):
        validate_scenario(sc)


def test_rejects_empty_set():
    """아무것도 바꾸지 않는 케이스는 실수다."""
    sc = _min_scenario()
    sc["cases"][0]["set"] = {}
    with pytest.raises(ValueError, match="set"):
        validate_scenario(sc)


def test_baseline_only_scenario_is_valid():
    """cases가 비어도 유효하다 (baseline 단독 실행 = 비트동일 회귀용)."""
    sc = _min_scenario()
    sc["cases"] = []
    validate_scenario(sc)
    assert len(expand_cases(sc)) == 1


def test_load_scenario_records_file_and_hash(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps(_min_scenario()), encoding="utf-8")
    sc = load_scenario(str(p))
    assert sc["_meta"]["file"] == "s.json"
    assert len(sc["_meta"]["sha256"]) == 12
    # 내용이 바뀌면 해시도 바뀐다
    sc2 = _min_scenario()
    sc2["name"] = "changed"
    p.write_text(json.dumps(sc2), encoding="utf-8")
    assert load_scenario(str(p))["_meta"]["sha256"] != sc["_meta"]["sha256"]
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_roadmap.py -v`
Expected: 수집 단계에서 `ImportError: cannot import name 'SCHEMA_ID' from 'front_electrode'`

- [ ] **Step 3: 최소 구현 작성**

`front_electrode/roadmap.py` 신규 생성:

```python
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

엔진(GEDOS.py)과 adapter.py는 수정하지 않는다 — evaluate_existing_simulation을
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

SCHEMA_ID = "gedos.roadmap/1"

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
```

`front_electrode/__init__.py` 수정 — `from .presets import ...` 줄 **바로 위**에 import 블록을 추가한다:

```python
from .roadmap import (
    SCHEMA_ID,
    PROV_TAGS,
    SCENARIO_MAP,
    validate_scenario,
    load_scenario,
    expand_cases,
)
```

그리고 `__all__`의 `"export_csv",` 다음 줄에 추가한다:

```python
    "SCHEMA_ID",
    "PROV_TAGS",
    "SCENARIO_MAP",
    "validate_scenario",
    "load_scenario",
    "expand_cases",
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_roadmap.py -v`
Expected: 11 passed (전부 1초 이내 — FEM 없음)

- [ ] **Step 5: 커밋**

```bash
git add front_electrode/roadmap.py front_electrode/__init__.py tests/test_roadmap.py
git commit -m "feat(roadmap): 시나리오 스키마 로드·검증·누적 전개

Griddler PRO §5.1 상당 러너의 순수 함수 계층. 오타난 키/누락된
provenance/중복 label을 전부 ValueError로 막는다 — 조용히 통과시키면
'에러 없이 그럴듯한 틀린 값'이 나온다(v28.43 전례).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: provenance 수집과 CSV 행 조립

FEM 없이 검증 가능한 부작용 계층. 가짜 `out` dict로 테스트한다.

**Files:**
- Modify: `front_electrode/roadmap.py` (append)
- Modify: `tests/test_roadmap.py` (append)
- Modify: `front_electrode/__init__.py` (export 추가)

**Interfaces:**
- Consumes: Task 1의 `expand_cases`
- Produces:
  - `ENGINE_RAW_KEYS: tuple` — CSV로 옮길 `engine_raw` 필드
  - `NONDETERMINISTIC_COLS: tuple = ("elapsed_s", "timestamp")`
  - `provenance_env(gedos, sc: dict) -> dict` — 5개 환경 필드
  - `build_row(case: dict, out: dict, sc: dict, env: dict, elapsed_s: float) -> dict`
  - `append_row(csv_path: str, row: dict, header_written: bool) -> bool` — 갱신된 header_written 반환
  - `completed_labels(csv_path: str) -> set[str]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_roadmap.py` 끝에 append:

```python
from front_electrode import (  # noqa: E402
    ENGINE_RAW_KEYS,
    append_row,
    build_row,
    completed_labels,
    provenance_env,
)


class _FakeGedos:
    """provenance_env가 읽는 두 심볼만 흉내낸다."""
    __build__ = {"version": "v28.53", "date": "2026-08-12"}

    @staticmethod
    def _build_sha():
        return "abcdef123456"


def _fake_out(eff=31.0):
    """evaluate_existing_simulation 반환 구조의 최소 모형."""
    return {
        "parameters": {
            "cell_w_mm": 20.0, "cell_h_mm": 20.0, "n_fingers": 10,
            "finger_pitch_mm": 1.8, "finger_width_um": 50.0,
            "busbar_number": 2, "busbar_width_mm": 0.2,
            "n_probe_points": 10, "busbar_recovery_factor": 0.0,
            "rho_bulk_uohm_cm": 4.22, "rho_contact_mohm_cm2": 10.0,
            "edge_margin_mm": 0.0,
        },
        "results": {"total_loss": 1.07, "efficiency": eff},
        "engine_raw": {
            "Jsc": 39.42, "Voc": 1.951, "FF": 78.31, "Eff": eff,
            "Pmpp": eff, "Vmpp": 1.62, "Jmpp": 19.1,
            "P_shade": 0.55, "Pe": 0.085, "Pf_finger": 0.104,
            "Pf_busbar": 0.046, "Pc": 0.319, "total_shading": 0.017,
        },
        "meta": {"nodes": 8123, "mode": "tandem",
                 "n_probe_points": 10, "n_probe_auto_bumped": False},
    }


def test_provenance_env_fields():
    sc = _min_scenario()
    sc["_meta"] = {"file": "s.json", "sha256": "0123456789ab"}
    env = provenance_env(_FakeGedos, sc)
    assert set(env) == {"git_commit", "engine_version", "engine_sha",
                        "scenario_file", "scenario_sha256"}
    assert env["engine_version"] == "v28.53"
    assert env["engine_sha"] == "abcdef123456"
    assert env["scenario_file"] == "s.json"
    assert env["scenario_sha256"] == "0123456789ab"
    assert env["git_commit"]          # 실패해도 "unknown", 빈 문자열은 금지


def test_build_row_carries_engine_raw_and_provenance():
    sc = _min_scenario()
    sc["_meta"] = {"file": "s.json", "sha256": "0123456789ab"}
    case = expand_cases(sc)[1]
    env = provenance_env(_FakeGedos, sc)
    row = build_row(case, _fake_out(), sc, env, elapsed_s=12.34)

    assert row["case_index"] == 1
    assert row["label"] == "lower rc"
    for k in ENGINE_RAW_KEYS:
        assert k in row, f"{k}가 CSV 행에 없다"
    assert row["Jsc"] == 39.42
    assert row["FF"] == 78.31
    # provenance 태그: 선언된 키는 태그, 나머지는 unspecified
    assert row["prov_rho_contact_mohm_cm2"] == "assumed"
    assert row["prov_w_finger_um"] == "unspecified"
    assert row["engine_sha"] == "abcdef123456"
    assert row["elapsed_s"] == 12.3


def test_build_row_uses_engine_raw_not_recovered_efficiency():
    """4-panel 값은 recovery 사후보정이 섞인 results.efficiency가 아니라
    engine_raw에서 와야 한다."""
    sc = _min_scenario()
    sc["_meta"] = {"file": "s.json", "sha256": "0123456789ab"}
    case = expand_cases(sc)[0]
    out = _fake_out()
    out["results"]["efficiency"] = 99.9        # 오염된 값
    out["engine_raw"]["Eff"] = 31.33           # 순수 엔진값
    row = build_row(case, out, sc, provenance_env(_FakeGedos, sc), 1.0)
    assert row["Eff"] == 31.33


def test_append_row_and_completed_labels(tmp_path):
    sc = _min_scenario()
    sc["_meta"] = {"file": "s.json", "sha256": "0123456789ab"}
    env = provenance_env(_FakeGedos, sc)
    cases = expand_cases(sc)
    csv_path = str(tmp_path / "r.csv")

    written = False
    for c in cases:
        row = build_row(c, _fake_out(), sc, env, 1.0)
        written = append_row(csv_path, row, written)

    assert completed_labels(csv_path) == {"base", "lower rc"}

    import csv as _csv
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(_csv.DictReader(fh))
    assert len(rows) == 2, "헤더가 매 행마다 다시 쓰이면 안 된다"
    assert [r["case_index"] for r in rows] == ["0", "1"]


def test_completed_labels_on_missing_file(tmp_path):
    assert completed_labels(str(tmp_path / "nope.csv")) == set()
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_roadmap.py -v`
Expected: `ImportError: cannot import name 'ENGINE_RAW_KEYS' from 'front_electrode'`

- [ ] **Step 3: 최소 구현 작성**

`front_electrode/roadmap.py` 끝에 append (`import` 블록 맨 위에 `import csv`, `import subprocess`, `import time` 추가):

```python
# engine_raw에서 CSV로 옮길 필드. 4-panel(Jsc/Voc/FF/Eff)의 데이터 소스이며
# busbar recovery 사후보정이 섞이지 않은 순수 엔진값이다(adapter.py 336-344).
ENGINE_RAW_KEYS = (
    "Jsc", "Voc", "FF", "Eff", "Pmpp", "Vmpp", "Jmpp",
    "P_shade", "Pe", "Pf_finger", "Pf_busbar", "Pc",
)

# 워커 스케줄·벽시계 의존 → 회귀 대조 시 제외 (optimize_m10.py와 같은 규약).
NONDETERMINISTIC_COLS = ("elapsed_s", "timestamp")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git_commit():
    """짧은 SHA(+dirty). git이 없거나 실패하면 'unknown' — 치명적이지 않다."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=_REPO_ROOT)
        if head.returncode != 0:
            return "unknown"
        sha = head.stdout.strip() or "unknown"
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5, cwd=_REPO_ROOT)
        if status.returncode == 0 and status.stdout.strip():
            sha += "-dirty"
        return sha
    except Exception:
        return "unknown"


def provenance_env(gedos, sc):
    """실행 환경 provenance.

    engine_sha가 git_commit보다 강한 앵커다 — 커밋하지 않고 엔진을 고친 채
    돌린 결과를 구분해 낸다.
    """
    meta = sc.get("_meta", {})
    return {
        "git_commit": _git_commit(),
        "engine_version": gedos.__build__["version"],
        "engine_sha": gedos._build_sha(),
        "scenario_file": meta.get("file", "unknown"),
        "scenario_sha256": meta.get("sha256", "unknown"),
    }


def build_row(case, out, sc, env, elapsed_s):
    """한 케이스의 결과를 CSV 행 dict로 조립한다."""
    row = {
        "case_index": case["case_index"],
        "label": case["label"],
        "note": case["note"],
    }
    row.update(out["parameters"])
    er = out["engine_raw"]
    for key in ENGINE_RAW_KEYS:
        row[key] = er[key]
    row["total_loss"] = out["results"]["total_loss"]

    prov = sc.get("provenance", {})
    for key in sorted(case["grid_params"]):
        row["prov_" + key] = prov.get(key, {}).get("tag", "unspecified")

    row.update(env)
    meta = out["meta"]
    row["nodes"] = meta["nodes"]
    row["mode"] = meta["mode"]
    row["n_probe_auto_bumped"] = meta.get("n_probe_auto_bumped", False)
    row["elapsed_s"] = round(float(elapsed_s), 1)
    row["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return row


def append_row(csv_path, row, header_written):
    """한 행을 즉시 append + flush. 중간 크래시에도 완료분이 보존된다."""
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
        if not header_written:
            writer.writeheader()
        writer.writerow(row)
        fh.flush()
    return True


def completed_labels(csv_path):
    """--resume용. 기존 CSV에 기록된 label 집합. 파일이 없으면 빈 집합."""
    if not (os.path.exists(csv_path) and os.path.getsize(csv_path) > 0):
        return set()
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        return {r["label"] for r in csv.DictReader(fh) if r.get("label")}
```

`front_electrode/__init__.py`의 roadmap import 블록과 `__all__`에 6개를 추가한다: `ENGINE_RAW_KEYS`, `NONDETERMINISTIC_COLS`, `provenance_env`, `build_row`, `append_row`, `completed_labels`.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_roadmap.py -v`
Expected: 16 passed

- [ ] **Step 5: 커밋**

```bash
git add front_electrode/roadmap.py front_electrode/__init__.py tests/test_roadmap.py
git commit -m "feat(roadmap): provenance 수집 + CSV 행 조립

git_commit / engine_version / engine_sha / scenario_file /
scenario_sha256 5개 환경 필드와 파라미터별 measured|assumed|derived
태그를 행에 싣는다. engine_sha는 커밋되지 않은 엔진 수정까지 잡는다.
4-panel 값은 results.efficiency가 아니라 engine_raw에서 뽑는다
(recovery 사후보정 미오염).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 실행 루프 + 비트 동일 회귀 테스트

여기서 처음 엔진을 호출한다. **요구사항 "기존 결과 비트 불변"의 실증이 이 태스크에 있다.**

**Files:**
- Modify: `front_electrode/roadmap.py` (append)
- Modify: `tests/test_roadmap.py` (append)
- Modify: `front_electrode/__init__.py` (export 추가)

**Interfaces:**
- Consumes: Task 1의 `expand_cases`·`SCENARIO_MAP`, Task 2의 `provenance_env`/`build_row`/`append_row`/`completed_labels`, `adapter.evaluate_existing_simulation`
- Produces: `run_roadmap(gedos, sc, csv_path, *, resume=False, axis_segments_override=None, progress=None) -> list[dict]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_roadmap.py` 끝에 append:

```python
from front_electrode import (  # noqa: E402
    SCENARIO_MEASURED,
    evaluate_existing_simulation,
    run_roadmap,
)


def _write_scenario(tmp_path, sc):
    p = tmp_path / "s.json"
    p.write_text(json.dumps(sc), encoding="utf-8")
    return str(p)


def test_baseline_bit_identical(gedos, monkeypatch, tmp_path):
    """★ roadmap의 baseline 케이스가 evaluate_existing_simulation 직접 호출과
    비트 동일. 기존 결과 불변의 실증.

    tests/test_optimizer.py:96-106 test_edge_margin_zero_is_bit_identical의
    관용구를 그대로 따른다 (cell 20mm + AX/NPTS + == 비교).
    """
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    sc = _min_scenario()
    sc["cases"] = []                      # baseline 단독
    grid = {k: v for k, v in sc["baseline"].items() if k != "label"}

    direct = evaluate_existing_simulation(
        gedos, grid, scenario=SCENARIO_MEASURED, busbar_recovery_factor=0.0,
        mode="tandem", npts=NPTS, axis_segments_override=AX)

    rows = run_roadmap(gedos, load_scenario(_write_scenario(tmp_path, sc)),
                       str(tmp_path / "r.csv"), axis_segments_override=AX)

    assert len(rows) == 1
    for key in ENGINE_RAW_KEYS:
        assert rows[0][key] == direct["engine_raw"][key], f"{key} 비트동일 실패"
    assert rows[0]["total_loss"] == direct["results"]["total_loss"]


def test_case_changes_result(gedos, monkeypatch, tmp_path):
    """rho_c를 낮추면 접촉 손실이 줄고 효율이 오른다 — 케이스가 실제로 먹는지."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    sc = _min_scenario()
    rows = run_roadmap(gedos, load_scenario(_write_scenario(tmp_path, sc)),
                       str(tmp_path / "r.csv"), axis_segments_override=AX)
    assert len(rows) == 2
    assert rows[1]["Pc"] < rows[0]["Pc"], "rho_c를 5배 낮췄는데 접촉 손실이 안 줄었다"
    assert rows[1]["Eff"] > rows[0]["Eff"]


def test_resume_skips_completed(gedos, monkeypatch, tmp_path):
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    sc_path = _write_scenario(tmp_path, _min_scenario())
    csv_path = str(tmp_path / "r.csv")
    first = run_roadmap(gedos, load_scenario(sc_path), csv_path,
                        axis_segments_override=AX)
    assert len(first) == 2
    again = run_roadmap(gedos, load_scenario(sc_path), csv_path, resume=True,
                        axis_segments_override=AX)
    assert again == [], "resume인데 완료 케이스를 다시 돌렸다"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_roadmap.py -v`
Expected: `ImportError: cannot import name 'run_roadmap' from 'front_electrode'`

- [ ] **Step 3: 최소 구현 작성**

`front_electrode/roadmap.py` 끝에 append (`import` 블록에 `from .adapter import evaluate_existing_simulation` 추가):

```python
def run_roadmap(gedos, sc, csv_path, *, resume=False,
                axis_segments_override=None, progress=None):
    """시나리오의 각 케이스를 순차 실행하고 CSV에 누적한다.

    busbar_recovery_factor는 0.0으로 고정한다 — roadmap의 4-panel은 순수
    엔진값을 써야 하고, 회수 보정이 섞이면 논문 figure의 근거가 흐려진다.
    회수를 보고 싶으면 CSV를 adapter.apply_recovery로 사후 재산출하라.

    반환: 이번 호출에서 실제로 실행한 행들 (resume으로 건너뛴 것은 제외).
    """
    cases = expand_cases(sc)
    eng = sc.get("engine", {})
    scenario_const = SCENARIO_MAP[eng.get("scenario", "measured")]
    mode = eng.get("mode", "tandem")
    npts = int(eng.get("npts", 14))
    # axis_segments_override(테스트·빠른 미리보기)가 target_nodes보다 우선한다.
    target_nodes = None if axis_segments_override is not None else eng.get("target_nodes")

    env = provenance_env(gedos, sc)
    done = completed_labels(csv_path) if resume else set()
    header_written = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0

    rows = []
    for case in cases:
        if case["label"] in done:
            continue
        t0 = time.time()
        out = evaluate_existing_simulation(
            gedos, case["grid_params"],
            scenario=scenario_const,
            busbar_recovery_factor=0.0,
            mode=mode,
            npts=npts,
            axis_segments_override=axis_segments_override,
            target_nodes=target_nodes,
        )
        row = build_row(case, out, sc, env, time.time() - t0)
        header_written = append_row(csv_path, row, header_written)
        rows.append(row)
        if progress is not None:
            progress(case["case_index"], len(cases), row)
    return rows
```

`front_electrode/__init__.py`에 `run_roadmap`을 추가한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_roadmap.py -v`
Expected: 19 passed. FEM 3개는 각각 수 초.

- [ ] **Step 5: 전체 스위트 회귀 확인**

Run: `python -m pytest -q -m "not slow"`
Expected: `97 passed, 2 deselected, 6 xfailed` — **기존 94개가 하나도 안 깨져야 한다.**

- [ ] **Step 6: 커밋**

```bash
git add front_electrode/roadmap.py front_electrode/__init__.py tests/test_roadmap.py
git commit -m "feat(roadmap): 실행 루프 + resume + 비트 동일 회귀 테스트

run_roadmap이 evaluate_existing_simulation을 그대로 호출한다.
test_baseline_bit_identical이 baseline 케이스 == 직접 호출임을 12개
engine_raw 필드에서 == 로 못박는다 (기존 결과 불변의 실증).
recovery는 0.0 고정 — 4-panel은 순수 엔진값이어야 한다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 4-panel 플롯

**Files:**
- Create: `front_electrode/roadmap_plot.py`
- Modify: `tests/test_roadmap.py` (append)
- Modify: `front_electrode/__init__.py` (export 추가)

**Interfaces:**
- Consumes: Task 2가 쓴 CSV (컬럼 `case_index`, `label`, `Jsc`, `Voc`, `FF`, `Eff`)
- Produces: `plot_roadmap(csv_path: str, png_path: str | None = None) -> str` — 저장한 PNG 경로 반환

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_roadmap.py` 끝에 append:

```python
from front_electrode import plot_roadmap  # noqa: E402


def test_plot_roadmap_creates_png(tmp_path):
    """FEM 없이 CSV만으로 그림을 다시 그릴 수 있어야 한다."""
    sc = _min_scenario()
    sc["_meta"] = {"file": "s.json", "sha256": "0123456789ab"}
    env = provenance_env(_FakeGedos, sc)
    csv_path = str(tmp_path / "r.csv")
    written = False
    for i, c in enumerate(expand_cases(sc)):
        row = build_row(c, _fake_out(eff=31.0 + 0.5 * i), sc, env, 1.0)
        written = append_row(csv_path, row, written)

    png = plot_roadmap(csv_path)

    assert png == str(tmp_path / "r.png")
    assert os.path.getsize(png) > 5000, "PNG가 비었거나 너무 작다"


def test_plot_roadmap_explicit_path(tmp_path):
    sc = _min_scenario()
    sc["_meta"] = {"file": "s.json", "sha256": "0123456789ab"}
    env = provenance_env(_FakeGedos, sc)
    csv_path = str(tmp_path / "r.csv")
    written = False
    for c in expand_cases(sc):
        written = append_row(csv_path, build_row(c, _fake_out(), sc, env, 1.0),
                             written)
    out_png = str(tmp_path / "custom.png")
    assert plot_roadmap(csv_path, out_png) == out_png
    assert os.path.exists(out_png)


def test_plot_roadmap_rejects_empty_csv(tmp_path):
    p = tmp_path / "empty.csv"
    p.write_text("", encoding="utf-8-sig")
    with pytest.raises(ValueError, match="빈"):
        plot_roadmap(str(p))
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_roadmap.py -v -k plot`
Expected: `ImportError: cannot import name 'plot_roadmap' from 'front_electrode'`

- [ ] **Step 3: 최소 구현 작성**

`front_electrode/roadmap_plot.py` 신규 생성:

```python
# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""roadmap 4-panel 플롯 — Jsc / Voc / FF / Efficiency.

계산(roadmap.py)과 분리되어 있다. 논문 figure는 스타일을 여러 번 고치므로
CSV만 있으면 FEM 재실행 없이 다시 그릴 수 있어야 한다.

축·제목은 영문 고정이다. 한글 폰트 탐색 실패 시의 깨짐을 원천 차단한다.
백엔드는 강제하지 않는다 — headless 호출자(scripts/run_roadmap.py)가 Agg를 정한다.
"""
import csv
import os

import matplotlib.pyplot as plt

# (CSV 컬럼, 축 라벨, 소수 자릿수)
PANELS = (
    ("Jsc", "Jsc [mA/cm$^2$]", 2),
    ("Voc", "Voc [V]", 3),
    ("FF", "FF [%]", 2),
    ("Eff", "Efficiency [%]", 2),
)

_LINE = "#1a237e"
_BASE = "#c0392b"


def _read_rows(csv_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"빈 CSV — 그릴 케이스가 없다: {csv_path}")
    rows.sort(key=lambda r: int(r["case_index"]))
    return rows


def plot_roadmap(csv_path, png_path=None):
    """roadmap CSV → 2×2 패널 PNG. 저장 경로를 반환한다."""
    rows = _read_rows(csv_path)
    if png_path is None:
        png_path = os.path.splitext(csv_path)[0] + ".png"

    labels = [r["label"] for r in rows]
    x = range(len(rows))

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, (col, ylabel, ndigits) in zip(axes.ravel(), PANELS):
        y = [float(r[col]) for r in rows]
        base = y[0]

        ax.plot(x, y, "o-", color=_LINE, lw=2, ms=7, zorder=3)
        ax.axhline(base, ls="--", lw=1.2, color=_BASE, alpha=0.7, zorder=1)
        ax.text(len(rows) - 0.5, base, f" baseline {base:.{ndigits}f}",
                fontsize=8, color=_BASE, va="bottom", ha="right")

        for xi, yi in zip(x, y):
            ax.annotate(f"{yi:.{ndigits}f}", (xi, yi), textcoords="offset points",
                        xytext=(0, 9), ha="center", fontsize=8.5,
                        fontweight="bold", color=_LINE)
            if xi > 0:
                d = yi - base
                ax.annotate(f"{d:+.{ndigits}f}", (xi, yi),
                            textcoords="offset points", xytext=(0, -16),
                            ha="center", fontsize=8,
                            color=("#1b5e20" if d >= 0 else "#b71c1c"))

        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=9, rotation=12, ha="right")
        ax.set_xlim(-0.5, len(rows) - 0.5)
        ax.grid(True, alpha=0.2, axis="y")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        title = ylabel.split(" [")[0]
        if col == "Eff":
            title += f"   (total {y[-1] - base:+.{ndigits}f})"
        ax.set_title(title, fontweight="bold", fontsize=11)

    fig.suptitle("Efficiency improvement roadmap", fontweight="bold", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    return png_path
```

`front_electrode/__init__.py`에 추가:

```python
from .roadmap_plot import plot_roadmap
```
및 `__all__`에 `"plot_roadmap",`.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_roadmap.py -v`
Expected: 22 passed

- [ ] **Step 5: 커밋**

```bash
git add front_electrode/roadmap_plot.py front_electrode/__init__.py tests/test_roadmap.py
git commit -m "feat(roadmap): 4-panel(Jsc/Voc/FF/Eff) 플롯

각 패널에 baseline 수평 기준선 + 케이스별 절대값과 baseline 대비 델타.
계산과 분리해 CSV만으로 FEM 재실행 없이 다시 그릴 수 있다.
축·제목 영문 고정 — 한글 폰트 탐색 실패 시 깨짐 방지.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: CLI + 예시 시나리오

**Files:**
- Create: `scripts/run_roadmap.py`
- Create: `scripts/scenarios/unist_tco.json`
- Modify: `tests/test_roadmap.py` (append)

**Interfaces:**
- Consumes: Task 1–4의 `load_scenario`·`run_roadmap`·`plot_roadmap`
- Produces: CLI `python scripts/run_roadmap.py --scenario <path> [--csv <path>] [--png <path>] [--resume] [--ax N] [--no-plot]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_roadmap.py` 끝에 append:

```python
def test_shipped_example_scenario_is_valid():
    """동봉한 예시 시나리오가 실제로 로드·검증을 통과하는지.

    파일에 오타가 있으면 사용자가 처음 돌릴 때 발견된다 — 그 전에 잡는다.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "scripts", "scenarios", "unist_tco.json")
    sc = load_scenario(path)

    cases = expand_cases(sc)
    assert len(cases) == 2, "최소 동작 예시는 baseline + 1 case"
    base, modified = cases

    # 설계 파라미터는 opt_grid_m10_measured.csv 최적행과 일치해야 한다
    assert base["grid_params"]["n_busbars"] == 8
    assert base["grid_params"]["w_busbar_mm"] == 0.20
    assert base["grid_params"]["edge_margin_mm"] == 0.0
    assert abs(base["grid_params"]["finger_spacing_mm"] - 2.193) < 1e-9

    # 케이스는 rho_c만 바꾼다 (설계 고정 → TCO 개선 단독 효과)
    assert modified["grid_params"]["rho_contact_mohm_cm2"] == 2.0
    assert modified["grid_params"]["n_busbars"] == 8
    assert sc["provenance"]["rho_contact_mohm_cm2"]["tag"] == "assumed"
    assert sc["provenance"]["w_busbar_mm"]["tag"] == "derived"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_roadmap.py::test_shipped_example_scenario_is_valid -v`
Expected: `FileNotFoundError: ... scripts/scenarios/unist_tco.json`

- [ ] **Step 3: 예시 시나리오 작성**

`scripts/scenarios/unist_tco.json` 신규 생성:

```json
{
  "schema": "gedos.roadmap/1",
  "name": "UNIST TCO modification",

  "engine": {
    "mode": "tandem",
    "npts": 14,
    "target_nodes": 82000,
    "scenario": "measured"
  },

  "baseline": {
    "label": "as-is (baseline)",
    "note": "opt_grid_m10_measured.csv 최적행 (Eff 31.330%)",
    "cell_w_mm": 182.0,
    "cell_h_mm": 182.0,
    "finger_spacing_mm": 2.193,
    "w_finger_um": 20.0,
    "n_busbars": 8,
    "w_busbar_mm": 0.20,
    "n_probe_points": 10,
    "edge_margin_mm": 0.0,
    "rho_bulk_uohm_cm": 4.22,
    "rho_contact_mohm_cm2": 10.0
  },

  "cases": [
    {
      "label": "TCO modified",
      "note": "rho_c 10 -> 2 mOhm.cm2 (placeholder - 실측값 미확보)",
      "set": { "rho_contact_mohm_cm2": 2.0 }
    }
  ],

  "provenance": {
    "finger_spacing_mm":    { "tag": "derived",  "note": "optimize_grid edge0 최적 (opt_grid_m10_measured.csv, 31.330%)" },
    "n_busbars":            { "tag": "derived",  "note": "동일 스윕 최적 (8BB)" },
    "w_finger_um":          { "tag": "derived",  "note": "동일 스윕 고정축 20um (ITRPV 인쇄 현실성)" },
    "w_busbar_mm":          { "tag": "derived",  "note": "동일 스윕 고정축 0.20mm - pitch/BB 최적해와 같은 근거. 0.25는 ITRPV 16BB 계산용이며 그때는 n_busbars도 8->16이라 Stage A 재실행 필요" },
    "rho_bulk_uohm_cm":     { "tag": "measured", "note": "KIST low-T sinter 90C/30min/5MPa" },
    "rho_contact_mohm_cm2": { "tag": "assumed",  "note": "placeholder - 실측값 미확보" },
    "edge_margin_mm":       { "tag": "assumed",  "note": "공정 제약 미확정 (0 = 마진 없음 가정)" }
  }
}
```

- [ ] **Step 4: CLI 작성**

`scripts/run_roadmap.py` 신규 생성:

```python
# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""roadmap 러너 CLI — 시나리오 JSON → CSV 누적 → 4-panel PNG.

  python scripts/run_roadmap.py --scenario scripts/scenarios/unist_tco.json
  python scripts/run_roadmap.py --scenario ... --resume       # 중단 후 재개
  python scripts/run_roadmap.py --scenario ... --ax 60        # 빠른 미리보기
  python scripts/run_roadmap.py --scenario ... --plot-only    # CSV만으로 재작도

주의: 이 도구는 **탐색하지 않는다.** 최적 설계는 optimize_grid로 먼저 구해
시나리오 파일에 옮겨 적는다 (스펙 §2의 2단계 워크플로우).

풀 M10은 1케이스 ≈17분이다. 먼저 --ax 60으로 구조를 확인할 것.
"""
import argparse
import os
import sys
import time

import matplotlib
matplotlib.use("Agg")           # headless — GUI 없이 PNG만 만든다

# 헤드리스 로그 안전: Windows에서 stdout이 리다이렉트되면 cp949가 되어
# 비-cp949 문자 print가 UnicodeEncodeError로 죽는다 (optimize_m10.py와 동일 처리).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "tests"))
sys.path.insert(0, _ROOT)
import conftest  # noqa: E402

from front_electrode import (  # noqa: E402
    expand_cases,
    load_scenario,
    plot_roadmap,
    run_roadmap,
)


def _progress(idx, total, row):
    print(f"  [{idx + 1}/{total}] {row['label']:<24} "
          f"Jsc={row['Jsc']:.2f} Voc={row['Voc']:.4f} "
          f"FF={row['FF']:.2f} Eff={row['Eff']:.3f}  "
          f"({row['elapsed_s']}s, {row['nodes']} nodes) -> CSV append",
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, help="시나리오 JSON 경로")
    ap.add_argument("--csv", default=None,
                    help="출력 CSV (기본: 시나리오와 같은 basename의 .csv)")
    ap.add_argument("--png", default=None, help="출력 PNG (기본: CSV와 같은 basename)")
    ap.add_argument("--resume", action="store_true", help="완료 케이스 건너뜀")
    ap.add_argument("--ax", type=int, default=None,
                    help="axis_segments_override — 빠른 미리보기용 (target_nodes 무시)")
    ap.add_argument("--no-plot", action="store_true", help="PNG 생성 생략")
    ap.add_argument("--plot-only", action="store_true",
                    help="FEM 재실행 없이 기존 CSV로 그림만 다시 그린다")
    args = ap.parse_args()

    sc = load_scenario(args.scenario)
    csv_path = args.csv or (os.path.splitext(args.scenario)[0] + ".csv")

    if args.plot_only:
        print(f"plot-only: {csv_path} -> {plot_roadmap(csv_path, args.png)}")
        return

    gedos = conftest._load_gedos()
    cases = expand_cases(sc)
    print(f"GEDOS build {gedos.__build__['version']} | "
          f"scenario: {sc['name']} ({sc['_meta']['file']} "
          f"sha {sc['_meta']['sha256']})")
    print(f"  {len(cases)}개 케이스 (baseline 포함), CSV: {csv_path}")
    if args.ax is None:
        print("  ⚠ 풀 해상도 실행 — 풀 M10은 1케이스 ≈17분. "
              "구조 확인은 --ax 60을 먼저.")

    t0 = time.time()
    rows = run_roadmap(gedos, sc, csv_path, resume=args.resume,
                       axis_segments_override=args.ax, progress=_progress)
    print(f"  {len(rows)}개 실행, {time.time() - t0:.0f}s")

    if not args.no_plot:
        print(f"  PNG: {plot_roadmap(csv_path, args.png)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_roadmap.py -v`
Expected: 23 passed

- [ ] **Step 6: CLI를 실제로 한 번 돌려 확인**

Run: `python scripts/run_roadmap.py --scenario scripts/scenarios/unist_tco.json --csv scripts/scenarios/_smoke.csv --ax 60`
Expected: 2개 케이스가 각각 수십 초 내에 끝나고, `Eff`가 case 1에서 baseline보다 높다. `_smoke.csv`와 `_smoke.png`가 생긴다.

확인 후 스모크 산출물을 지운다: `rm scripts/scenarios/_smoke.csv scripts/scenarios/_smoke.png`

- [ ] **Step 7: 전체 스위트 최종 확인**

Run: `python -m pytest -q -m "not slow"`
Expected: `101 passed, 2 deselected, 6 xfailed` — 기존 94개 전원 생존.

- [ ] **Step 8: 커밋**

```bash
git add scripts/run_roadmap.py scripts/scenarios/unist_tco.json tests/test_roadmap.py
git commit -m "feat(roadmap): CLI + UNIST 예시 시나리오

--resume / --ax 미리보기 / --plot-only(FEM 없이 재작도) 지원.
예시 시나리오는 opt_grid_m10_measured.csv 최적행(8BB/0.20mm/pitch
2.193)과 근거가 일관되며, 동봉 파일이 실제로 검증을 통과하는지
테스트로 잠갔다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. 스펙 커버리지**

| 스펙 절 | 구현 태스크 |
|---|---|
| §1 목적·범위 (탐색 안 함) | Task 1 모듈 docstring, Task 5 CLI docstring |
| §2 2단계 워크플로우 | 문서로 전달 (Task 1·5 docstring). 코드 기능 아님 — 의도적 |
| §3 파일 구조 | Task 1~5 전체 |
| §4 시나리오 스키마 (JSON) | Task 1 `validate_scenario`/`load_scenario`, Task 5 예시 파일 |
| §5 provenance (2단계 강제 + 환경 5필드) | Task 2 |
| §6 실행 흐름 (순차, resume, 병렬 없음) | Task 3 |
| §7 CSV 컬럼 / PNG 4-panel | Task 2 (CSV), Task 4 (PNG) |
| §8 테스트 5종 | Task 1(3종)·2·3(비트동일)·4·5 |
| §9 비범위 | 구현 안 함 — 의도적 |

**2. 플레이스홀더 스캔** — 모든 코드 스텝에 실제 코드가 있고, TBD/TODO/"적절히 처리"류 없음.

**3. 타입 일관성**
- `expand_cases` 반환 원소 키 `{case_index, label, note, grid_params}` — Task 2 `build_row`, Task 3 `run_roadmap`에서 동일하게 사용
- `append_row(csv_path, row, header_written) -> bool` — Task 2 정의, Task 3에서 `header_written = append_row(...)`로 동일 사용
- `provenance_env(gedos, sc)` 인자 순서 — Task 2 정의와 Task 3 호출 일치
- `plot_roadmap(csv_path, png_path=None) -> str` — Task 4 정의, Task 5 CLI에서 동일 사용
- `ENGINE_RAW_KEYS` — Task 2에서 정의, Task 3 비트동일 테스트에서 순회

**4. 알려진 위험**
- Task 3 `test_case_changes_result`의 `rows[1]["Pc"] < rows[0]["Pc"]`는 물리적으로 확실하다(ρ_c 5배 감소). `Eff` 증가는 접촉 손실 감소분이 다른 채널 변화를 넘어야 하는데, 20 mm 소셀·2BB에서도 성립할 것으로 본다. 만약 실패하면 `Pc` 단조 감소만 남기고 `Eff` 단언은 제거한다 — 그 경우 이유를 커밋 메시지에 남긴다.
- Task 5 Step 6의 `--ax 60`은 M10 셀에 대해 성긴 메시다. 절대 효율값은 신뢰하지 말고 **파이프라인 동작 확인용으로만** 쓴다.
