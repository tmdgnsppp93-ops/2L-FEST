# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Phase 2 — optimizer 테스트 (작은 config로 headless 검증).

실제 M10 stage-2는 1조합 ≈17분이라 pytest에서 못 돌린다. optimizer 함수는
config 주도라 테스트는 작은 셀·소수 조합·coarse 메시로 수 초 내 검증한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from front_electrode import (  # noqa: E402
    optimize_fingers,
    optimize_grid,
    roundtrip_check,
    export_csv,
    SCENARIO_MEASURED,
    SCENARIO_AS_CURED,
    SCENARIO_ENGINE_DEFAULT,
)

AX = 36
NPTS = 6


def test_optimize_fingers_sorted_and_best(gedos, monkeypatch):
    """finger 스윕이 total_loss 오름차순 정렬 + best가 실제 최소인지."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_fingers(
        gedos, cell_mm=20.0, finger_widths_um=[40.0, 80.0],
        finger_pitches_mm=[1.5, 2.5], busbar_number=2, busbar_width_mm=0.2,
        scenario=SCENARIO_MEASURED, axis_segments_override=AX, npts=NPTS)
    rs = opt["results"]
    assert len(rs) == 4
    losses = [r["results"]["total_loss"] for r in rs]
    assert losses == sorted(losses), "total_loss 오름차순 정렬이어야 함"
    assert opt["best"] is rs[0]
    assert opt["best"]["results"]["total_loss"] == min(losses)
    # 실제 실현된 정수 n_fingers / pitch가 기록됨
    for r in rs:
        assert isinstance(r["parameters"]["n_fingers"], int)
        assert r["parameters"]["finger_pitch_mm"] > 0
    # 시나리오 라벨 부착 — 문구가 아니라 **어떤 시나리오였는지**를 검사한다.
    # (v28.48에서 라벨이 "measured ..." → "pressed ..."로 바뀌며 문자열 결합이 깨졌다.)
    assert opt["best"]["scenario_label"] == SCENARIO_MEASURED["label"]
    assert abs(opt["best"]["parameters"]["rho_bulk_uohm_cm"]
               - SCENARIO_MEASURED["rho_bulk_uohm_cm"]) < 1e-9


def test_roundtrip(gedos, monkeypatch):
    """최적 조건을 직접 재입력 → 동일한 손실·효율(비트 동일)."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_fingers(
        gedos, cell_mm=20.0, finger_widths_um=[50.0, 90.0],
        finger_pitches_mm=[1.8], busbar_number=2, busbar_width_mm=0.2,
        scenario=SCENARIO_MEASURED, axis_segments_override=AX, npts=NPTS)
    ok, re, best = roundtrip_check(
        gedos, opt["best"], scenario=SCENARIO_MEASURED,
        axis_segments_override=AX, npts=NPTS)
    assert ok, "round-trip 재입력 결과가 최적 조합과 불일치"
    assert re["results"]["total_loss"] == best["results"]["total_loss"]
    assert re["results"]["efficiency"] == best["results"]["efficiency"]


def test_roundtrip_restores_grid_overrides(gedos, monkeypatch):
    """v28.46 회귀 — round-trip이 edge_margin/물성 override까지 재입력하는지.

    v28.45에서 edge_margin·rho_bulk·rho_contact가 조합별 스윕 축이 됐는데
    roundtrip_check가 이를 복원하지 않아, 최적 조합을 **다른 설계로**(마진 없음·
    엔진 기본 물성) 재평가하고 'FAIL(불일치)'로 오보고했다 — 엔진이 아니라 검증기
    쪽 결함이라 진짜 지오메트리 불일치와 구분되지 않는다.
    """
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_grid(
        gedos, cell_mm=20.0, finger_widths_um=[50.0], finger_pitches_mm=[1.8],
        n_busbars_list=[2], busbar_widths_mm=[0.2],
        rho_bulk_list=[3.0], rho_contact_list=[7.0],
        edge_margin_mm=0.5, n_probe_points=10,
        scenario=SCENARIO_MEASURED, axis_segments_override=AX, npts=NPTS)
    best = opt["best"]
    # override가 실제로 적용됐는지 먼저 확인(테스트가 무의미해지지 않도록)
    assert best["parameters"]["edge_margin_mm"] == 0.5
    assert abs(best["parameters"]["rho_bulk_uohm_cm"] - 3.0) < 1e-9
    assert abs(best["parameters"]["rho_contact_mohm_cm2"] - 7.0) < 1e-9
    assert best["meta"]["grid_overrides"] == {
        "edge_margin_mm": 0.5, "rho_bulk_uohm_cm": 3.0, "rho_contact_mohm_cm2": 7.0}

    ok, re, _ = roundtrip_check(gedos, best, scenario=SCENARIO_MEASURED,
                                axis_segments_override=AX, npts=NPTS)
    assert ok, "override 조합의 round-trip 재입력이 불일치"
    assert re["parameters"]["edge_margin_mm"] == 0.5
    assert re["results"]["efficiency"] == best["results"]["efficiency"]


def test_edge_margin_zero_is_bit_identical(gedos, monkeypatch):
    """edge_margin=0 전달이 미전달과 비트 동일 — 기존 결과 불변 보장."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    kw = dict(cell_mm=20.0, finger_widths_um=[50.0], finger_pitches_mm=[1.8],
              busbar_number=2, busbar_width_mm=0.2, scenario=SCENARIO_MEASURED,
              axis_segments_override=AX, npts=NPTS)
    legacy = optimize_fingers(gedos, **kw)
    margin0 = optimize_fingers(gedos, edge_margin_mm=0.0, **kw)
    for key in ("total_loss", "efficiency", "optical_loss", "electrical_loss"):
        assert (legacy["best"]["results"][key]
                == margin0["best"]["results"][key]), f"{key} 비트동일 실패"


def test_edge_margin_shortens_metal(gedos, monkeypatch):
    """edge_margin>0이 실제로 금속을 엣지에서 떼는지 — shading 감소로 확인."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    kw = dict(cell_mm=20.0, finger_widths_um=[50.0], finger_pitches_mm=[1.8],
              busbar_number=2, busbar_width_mm=0.2, scenario=SCENARIO_MEASURED,
              axis_segments_override=AX, npts=NPTS)
    m0 = optimize_fingers(gedos, edge_margin_mm=0.0, **kw)["best"]
    m1 = optimize_fingers(gedos, edge_margin_mm=1.0, **kw)["best"]
    assert (m1["engine_raw"]["total_shading"]
            < m0["engine_raw"]["total_shading"]), "마진을 줬는데 금속 면적이 안 줄었다"


def test_export_csv(gedos, tmp_path, monkeypatch):
    """CSV export — 각 조합의 전체 입력 파라미터가 기록되는지."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_fingers(
        gedos, cell_mm=20.0, finger_widths_um=[50.0], finger_pitches_mm=[1.5, 2.0],
        busbar_number=2, busbar_width_mm=0.2, scenario=SCENARIO_MEASURED,
        axis_segments_override=AX, npts=NPTS)
    path = os.path.join(str(tmp_path), "opt.csv")
    export_csv(opt, path)
    assert os.path.exists(path)
    with open(path, encoding="utf-8-sig") as fh:
        header = fh.readline()
    # 최적점을 Griddler로 재현할 수 있게 핵심 입력이 전부 있어야 함
    for col in ("n_fingers", "finger_pitch_mm", "finger_width_um",
                "busbar_number", "busbar_width_mm", "total_loss", "efficiency",
                "scenario_label"):
        assert col in header, f"CSV에 {col} 누락"


def test_scenarios_encode_pressing_comparison():
    """가압 비교의 두 축이 올바른 값·조건을 담고 있는지 (v28.48).

    9(as-cured)와 4.22(pressed)는 **온도·시간이 같고 가압만 다른** 쌍이라 차이가
    순수 가압 효과다. 엔진 기본(as-printed)은 대조군이 아니므로 rho를 지정하지 않는다
    — 이 구분이 깨지면 보고되는 "가압 기여"가 경화 효과까지 포함해 과대평가된다.
    """
    assert SCENARIO_AS_CURED["rho_bulk_uohm_cm"] == 9.0
    assert SCENARIO_MEASURED["rho_bulk_uohm_cm"] == 4.22
    assert SCENARIO_ENGINE_DEFAULT["rho_bulk_uohm_cm"] is None
    # 라벨에 측정 조건이 드러나야 한다(조건 없이 숫자만 있으면 오해를 부른다)
    assert "no pressure" in SCENARIO_AS_CURED["label"]
    assert "90C/30min" in SCENARIO_AS_CURED["label"]
    assert "5MPa" in SCENARIO_MEASURED["label"]
    assert "as-printed" in SCENARIO_ENGINE_DEFAULT["label"]


def test_edge_margin_sweep_axis(gedos, monkeypatch):
    """edge_margin을 축으로 스윕하면 마진별 최적이 따로 나와야 한다 (v28.50).

    마진은 설계 자유도가 아니라 공정 제약이라 효율이 마진에 단조 감소한다. 전역
    argmax를 쓰면 **항상 최소 마진**이 뽑혀 무의미하므로 best_by_edge를 제공한다.
    """
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_grid(
        gedos, cell_mm=20.0, finger_widths_um=[50.0], finger_pitches_mm=[1.8],
        n_busbars_list=[2], busbar_widths_mm=[0.2],
        edge_margins_mm=[0.0, 0.5], n_probe_points=10,
        scenario=SCENARIO_MEASURED, axis_segments_override=AX, npts=NPTS)
    assert opt["n_combos"] == 2
    margins = sorted(round(r["parameters"]["edge_margin_mm"], 6)
                     for r in opt["results"])
    assert margins == [0.0, 0.5], "마진이 조합별로 적용되지 않았다"

    by = opt["best_by_edge"]
    assert set(by) == {0.0, 0.5}, "마진별 최적이 없다"
    # 마진이 커지면 금속·접촉 면적이 줄어 효율이 낮아진다(단조 감소)
    assert by[0.5]["results"]["efficiency"] < by[0.0]["results"]["efficiency"]
    # 전역 best는 항상 최소 마진 → 이것만 보면 안 된다는 사실 자체를 고정
    assert opt["best"]["parameters"]["edge_margin_mm"] == 0.0


def test_edge_margin_scalar_path_unchanged(gedos, monkeypatch):
    """edge_margins_mm 미지정 시 기존 스칼라 경로와 비트 동일 + best_by_edge 없음."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    kw = dict(cell_mm=20.0, finger_widths_um=[50.0], finger_pitches_mm=[1.8],
              n_busbars_list=[2], busbar_widths_mm=[0.2], n_probe_points=10,
              scenario=SCENARIO_MEASURED, axis_segments_override=AX, npts=NPTS)
    a = optimize_grid(gedos, edge_margin_mm=0.5, **kw)
    b = optimize_grid(gedos, edge_margin_mm=0.5, edge_margins_mm=None, **kw)
    assert "best_by_edge" not in a, "단일 마진인데 마진별 최적이 생겼다"
    assert (a["best"]["results"]["efficiency"]
            == b["best"]["results"]["efficiency"]), "스칼라 경로가 비트 동일하지 않다"
