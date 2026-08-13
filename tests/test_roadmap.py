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
    sc["schema"] = "2lfest.roadmap/99"
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
