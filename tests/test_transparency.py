# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Metal Optical Transparency 테스트.

정의(Manual v7.0 §2.7): T = 1 − optical_width/physical_width, 기본 0.
physical → contact area / 금속 저항, optical → shading.

순수 함수는 FEM 없이 즉시 검증하고, 엔진 배선만 20mm 소셀로 확인한다
(tests/test_optimizer.py:96-106의 AX/NPTS 관용구와 동일).
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AX = 36
NPTS = 6


def test_optical_widths_identity_at_zero(gedos):
    """T=0이면 입력 폭을 그대로 돌려준다 — 비트 동일의 근거."""
    g = gedos.GridDesign()
    assert g.optical_transparency_f == 0.0
    assert g.optical_transparency_b == 0.0
    w_f, w_b = 50e-4, 200e-4
    assert g.optical_widths(w_f, w_b) == (w_f, w_b)


def test_optical_widths_scales_each_side(gedos):
    """finger와 busbar에 각각 다른 T가 걸린다."""
    g = gedos.GridDesign(optical_transparency_f=0.3, optical_transparency_b=0.5)
    of, ob = g.optical_widths(100e-4, 200e-4)
    assert of == pytest.approx(70e-4)
    assert ob == pytest.approx(100e-4)


def test_transparency_range_validation(gedos):
    """T<0 과 T>=1 은 ValueError. T=1은 광학 폭 0이라 무의미하다."""
    with pytest.raises(ValueError, match="optical_transparency_f"):
        gedos.GridDesign(optical_transparency_f=-0.1)
    with pytest.raises(ValueError, match="optical_transparency_b"):
        gedos.GridDesign(optical_transparency_b=1.0)
    with pytest.raises(ValueError, match="optical_transparency_b"):
        gedos.GridDesign(optical_transparency_b=1.5)
    # 경계값은 통과해야 한다
    gedos.GridDesign(optical_transparency_f=0.0, optical_transparency_b=0.999)


def test_optical_shading_fraction_matches_physical_at_zero(gedos):
    """T=0에서 optical_shading_fraction == shading_fraction (비트 동일)."""
    geo = gedos.CellGeometry(cell_w=2.0, cell_h=2.0,
                            front=gedos.GridDesign(n_fingers=4, n_busbars=2))
    assert geo.optical_shading_fraction() == geo.shading_fraction()


def test_optical_shading_fraction_less_when_transparent(gedos):
    """T>0이면 광학 shading이 물리 shading보다 작다."""
    geo = gedos.CellGeometry(
        cell_w=2.0, cell_h=2.0,
        front=gedos.GridDesign(n_fingers=4, n_busbars=2,
                              optical_transparency_f=0.4,
                              optical_transparency_b=0.4))
    assert geo.optical_shading_fraction() < geo.shading_fraction()


# ---------------------------------------------------------------------------
# 엔진 배선 (FEM, 20mm 소셀)
# ---------------------------------------------------------------------------
def _build_case(gedos, t_f=0.0, t_b=0.0):
    """20mm 소셀 + coarse 메시로 solver/geo/dp 한 세트를 만든다."""
    front = gedos.GridDesign(n_fingers=4, n_busbars=2,
                            w_finger=100e-4, w_busbar=200e-4,
                            n_probe_points=10,
                            optical_transparency_f=t_f,
                            optical_transparency_b=t_b)
    geo = gedos.CellGeometry(cell_w=2.0, cell_h=2.0, front=front)
    pts, tri = gedos.generate_mesh(geo, axis_segments_override=AX)
    isf, isb, isp, ism, isrm, isrp = gedos.classify_nodes(pts, geo)
    S = gedos.GEDOSSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)
    return S, geo, gedos.DiodeParams()


def _built_solver(gedos, t_f=0.0, t_b=0.0):
    """_build()까지만 돌린 solver — 폭에서 유도되는 모델을 직접 비교할 때 쓴다."""
    S, geo, dp = _build_case(gedos, t_f, t_b)
    g = geo.front
    S._build(g.rho_bulk, g.finger_h, g.w_f, g.rho_contact, g.Rs_sheet,
             g.shape_cf, dp)
    return S


def _run(gedos, t_f=0.0, t_b=0.0):
    """calc_iv + losses를 돌려 (iv, loss, geo) 반환."""
    S, geo, dp = _build_case(gedos, t_f, t_b)
    g = geo.front
    _, _, iv = S.calc_iv(g.rho_bulk, g.finger_h, g.w_f, g.rho_contact,
                         g.Rs_sheet, g.shape_cf, dp, mode="tandem", npts=NPTS)
    vb = iv.get("Vmpp_internal", iv["Vmpp"])
    res = iv.get("_mpp_result") or S.solve(
        g.rho_bulk, g.finger_h, g.w_f, g.rho_contact, g.Rs_sheet, vb,
        g.shape_cf, dp, "tandem")
    loss = S.losses(res, g.rho_bulk, g.finger_h, g.w_f, g.rho_contact,
                    g.Rs_sheet, g.shape_cf, dp,
                    Vmpp=iv["Vmpp"], Jmpp=iv["Jmpp"])
    return iv, loss, geo


def test_transparency_zero_bit_identical(gedos, monkeypatch):
    """★ T=0 명시 전달 == 미전달. 기존 결과 불변의 실증."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    iv_default, loss_default, _ = _run(gedos)      # 파라미터 미전달과 동일 (기본 0)
    iv_zero, loss_zero, _ = _run(gedos, t_f=0.0, t_b=0.0)
    for k in ("Jsc", "Voc", "FF", "Eff", "Pmpp"):
        assert iv_zero[k] == iv_default[k], f"{k} 비트동일 실패"
    for k in ("Pe", "Pf_finger", "Pf_busbar", "Pc", "P_shade"):
        assert loss_zero[k] == loss_default[k], f"{k} 비트동일 실패"


def test_transparency_does_not_touch_contact(gedos, monkeypatch):
    """★ 이 기능의 정의 — T는 접촉·저항 **모델**에 닿지 않는다.

    불변이어야 하는 것은 모델이지 소산 전력이 아니다.
    Pc = Σ(Ve−Vm)²·Gc 는 전력이므로, Gc가 그대로여도 T가 발전량을 늘리면
    전류가 늘어 Pc는 물리적으로 **당연히 오른다**. 소산 전력을 불변으로
    단언하면 옳은 구현이 실패한다 — 실측(20mm 소셀, T 0→0.4)에서 Pc가
    +3.32% 올랐고, 이는 발전량비 1.0164의 제곱(1.0331)과 일치한다.
    저항 소산이 전류²에 비례하기 때문이다.

    그래서 검사 대상은 **폭에서 직접 유도되는 양**이다 — 접촉 컨덕턴스 _Gc,
    금속 저항 네트워크 _Km, emitter 시트 _Ke, 금속 점유율 metal_frac.
    이들이 비트 동일하면 T가 물리 폭 경로로 새지 않았다는 뜻이며,
    소산 전력을 보는 것보다 강한 보증이다.

    결과 수준(전력·효율)의 방향과 크기는
    test_transparency_effects_stay_in_optical_path가 담당한다.
    """
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    a = _built_solver(gedos, t_f=0.0, t_b=0.0)
    b = _built_solver(gedos, t_f=0.4, t_b=0.4)

    assert np.array_equal(a._Gc, b._Gc), "T가 접촉 컨덕턴스를 건드렸다"
    assert (a._Km - b._Km).nnz == 0, "T가 금속 저항 네트워크를 건드렸다"
    assert (a._Ke - b._Ke).nnz == 0, "T가 emitter 시트 행렬을 건드렸다"
    assert np.array_equal(a.metal_frac, b.metal_frac), "T가 금속 점유율을 건드렸다"

    # 반대 방향 — 광학 경로에는 반드시 나타나야 한다
    assert b.illum_frac.sum() > a.illum_frac.sum(), "T를 줬는데 발전량이 안 늘었다"


def test_transparency_effects_stay_in_optical_path(gedos, monkeypatch):
    """T의 영향이 광학 경로에만 나타나는지 — 결과 수준의 보증.

    모델이 불변임은 위 테스트가 본다. 여기서는 실제 계산 결과가 물리적으로
    말이 되는지, 그리고 저항 소산의 증가가 **발전량 증가만으로 설명되는지**를
    본다. 설명되지 않는 증가가 있으면 T가 어딘가 다른 경로로 샌 것이다.

    상한은 느슨하게 잡는다: 저항 소산은 전류²에 준해 오르므로 발전량비의
    제곱이 자연스러운 기준이고, 여기에 여유 2배를 둔다. 정밀 회귀가 아니라
    "딴 경로로 새지 않았다"의 방어선이다.
    """
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    iv0, l0, _ = _run(gedos, t_f=0.0, t_b=0.0)
    iv1, l1, geo1 = _run(gedos, t_f=0.4, t_b=0.4)

    # 발전량 증가비 — 엔진의 _gen_s와 같은 식 (solver 내부를 보지 않고 재현)
    gen_ratio = ((1.0 - geo1.optical_shading_fraction())
                 / (1.0 - geo1.shading_fraction()))
    assert gen_ratio > 1.0, "T>0인데 발전량 증가비가 1 이하다"

    assert l1["P_shade"] < l0["P_shade"], "T를 줬는데 shading 손실이 안 줄었다"
    assert iv1["Eff"] > iv0["Eff"], "shading이 줄었는데 효율이 안 올랐다"

    upper = 1.0 + (gen_ratio ** 2 - 1.0) * 2.0
    for k in ("Pc", "Pf_finger", "Pf_busbar"):
        assert l1[k] > l0[k], f"{k}가 안 늘었다 — 전류가 안 늘었다는 뜻"
        assert l1[k] / l0[k] < upper, (
            f"{k} 증가({l1[k] / l0[k]:.4f}배)가 발전량 증가"
            f"({gen_ratio:.4f}배)로 설명되지 않는다 — T가 딴 경로로 샜다")


def test_rear_transparency_warns(gedos, monkeypatch, capsys):
    """rear T는 모델에 반영되지 않는다 — 조용한 no-op으로 두지 않고 경고한다."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    front = gedos.GridDesign(n_fingers=4, n_busbars=2, n_probe_points=10)
    rear = gedos.GridDesign(n_fingers=4, n_busbars=2, n_probe_points=10,
                           optical_transparency_f=0.3)
    geo = gedos.CellGeometry(cell_w=2.0, cell_h=2.0, front=front, rear=rear)
    pts, tri = gedos.generate_mesh(geo, axis_segments_override=AX)
    isf, isb, isp, ism, isrm, isrp = gedos.classify_nodes(pts, geo)
    S = gedos.GEDOSSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)
    g = geo.front
    S._build(g.rho_bulk, g.finger_h, g.w_f, g.rho_contact, g.Rs_sheet,
             g.shape_cf, gedos.DiodeParams())
    assert "rear optical transparency" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# adapter 경로
# ---------------------------------------------------------------------------
from front_electrode import (  # noqa: E402
    SCENARIO_MEASURED,
    evaluate_existing_simulation,
)


def _grid(**over):
    g = dict(cell_w_mm=20.0, cell_h_mm=20.0, finger_spacing_mm=1.8,
             w_finger_um=50.0, n_busbars=2, w_busbar_mm=0.2,
             n_probe_points=10)
    g.update(over)
    return g


def test_adapter_transparency_zero_bit_identical(gedos, monkeypatch):
    """T=0 키를 넘긴 것과 안 넘긴 것이 비트 동일."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    kw = dict(scenario=SCENARIO_MEASURED, busbar_recovery_factor=0.0,
              mode="tandem", npts=NPTS, axis_segments_override=AX)
    base = evaluate_existing_simulation(gedos, _grid(), **kw)
    zero = evaluate_existing_simulation(
        gedos, _grid(optical_transparency_finger=0.0,
                    optical_transparency_busbar=0.0), **kw)
    for k in ("Jsc", "Voc", "FF", "Eff", "Pmpp", "Pc", "Pf_finger"):
        assert zero["engine_raw"][k] == base["engine_raw"][k], f"{k} 비트동일 실패"


def test_shading_columns_physical_and_optical(gedos, monkeypatch):
    """T=0이면 두 컬럼이 같고, T>0이면 optical < physical."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    kw = dict(scenario=SCENARIO_MEASURED, busbar_recovery_factor=0.0,
              mode="tandem", npts=NPTS, axis_segments_override=AX)
    zero = evaluate_existing_simulation(gedos, _grid(), **kw)["results"]
    assert zero["shading_physical"] == zero["shading_optical"]

    tr = evaluate_existing_simulation(
        gedos, _grid(optical_transparency_finger=0.4,
                    optical_transparency_busbar=0.4), **kw)["results"]
    assert tr["shading_optical"] < tr["shading_physical"]
    # 물리 shading은 T와 무관하다 (금속이 덮은 면적은 그대로)
    assert tr["shading_physical"] == pytest.approx(zero["shading_physical"])


def test_transparency_conflicts_with_recovery(gedos):
    """같은 물리를 두 번 계산하는 조합은 막는다. 메시지에 해결책 양쪽이 있어야 한다."""
    with pytest.raises(ValueError) as ei:
        evaluate_existing_simulation(
            gedos, _grid(optical_transparency_busbar=0.3),
            scenario=SCENARIO_MEASURED, busbar_recovery_factor=0.25,
            mode="tandem", npts=NPTS, axis_segments_override=AX)
    msg = str(ei.value)
    assert "optical_transparency_busbar=0" in msg
    assert "busbar_recovery_factor=0" in msg


def test_finger_transparency_does_not_conflict(gedos, monkeypatch):
    """finger에는 recovery 모델이 없으므로 충돌하지 않는다."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    out = evaluate_existing_simulation(
        gedos, _grid(optical_transparency_finger=0.3),
        scenario=SCENARIO_MEASURED, busbar_recovery_factor=0.25,
        mode="tandem", npts=NPTS, axis_segments_override=AX)
    assert out["results"]["shading_optical"] < out["results"]["shading_physical"]


# ---------------------------------------------------------------------------
# 스윕 축
# ---------------------------------------------------------------------------
from front_electrode import (  # noqa: E402
    COMBO_CONFIRM_THRESHOLD,
    optimize_grid,
)

_SWEEP_BASE = dict(cell_mm=20.0, finger_widths_um=[50.0],
                   finger_pitches_mm=[1.8], n_busbars_list=[2],
                   busbar_widths_mm=[0.2], scenario=SCENARIO_MEASURED,
                   axis_segments_override=AX, npts=NPTS)


def test_transparency_sweep_axis(gedos, monkeypatch):
    """T가 축이 되면 조합 수가 늘고 각 조합에 값이 실린다."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_grid(gedos, transparency_finger_list=[0.0, 0.4],
                        **_SWEEP_BASE)
    assert opt["n_combos"] == 2
    sh = [r["results"]["shading_optical"] for r in opt["results"]]
    assert max(sh) > min(sh), "T를 바꿨는데 광학 shading이 그대로다"


def test_sweep_axis_order_is_preserved(gedos, monkeypatch):
    """★ itertools.product 언패킹 순서 대조 — 7축이 9축이 되며 자리가 밀리면
    조용히 잘못된 조합이 만들어진다.

    transparency 2축은 **맨 뒤에** 붙이므로 기존 7개 자리는 그대로여야 한다.
    여러 축에 서로 구별되는 값을 주고, 각 값이 원래 자리에 도착했는지 본다.
    자리가 밀리면 예컨대 T가 edge_margin에 들어가 아래 단언이 깨진다.
    """
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_grid(
        gedos, cell_mm=20.0,
        finger_widths_um=[50.0], finger_pitches_mm=[1.8],
        n_busbars_list=[2], busbar_widths_mm=[0.2],
        rho_contact_list=[10.0], edge_margins_mm=[0.0],
        transparency_finger_list=[0.0, 0.4],
        scenario=SCENARIO_MEASURED, axis_segments_override=AX, npts=NPTS)

    assert opt["n_combos"] == 2
    for r in opt["results"]:
        p = r["parameters"]
        assert p["finger_width_um"] == pytest.approx(50.0), "finger 폭 자리 밀림"
        assert p["busbar_number"] == 2, "busbar 개수 자리 밀림"
        assert p["busbar_width_mm"] == pytest.approx(0.2), "busbar 폭 자리 밀림"
        assert p["rho_contact_mohm_cm2"] == pytest.approx(10.0), "접촉저항 자리 밀림"
        assert p["edge_margin_mm"] == pytest.approx(0.0), "edge margin 자리 밀림"


def test_combo_confirm_threshold_value():
    """임계 50 — M10 1조합 약 17분이므로 50조합이면 약 14시간이다."""
    assert COMBO_CONFIRM_THRESHOLD == 50


def test_combo_confirm_can_cancel(gedos, monkeypatch):
    """임계를 넘고 confirm이 False를 주면 FEM을 돌리기 전에 취소된다.

    confirm=None(기본)이면 이 경로에 들어가지 않는다 — 라이브러리 안에서
    input()을 부르면 pytest와 백그라운드 실행이 멈추기 때문이다.
    """
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    monkeypatch.setattr("front_electrode.optimizer.COMBO_CONFIRM_THRESHOLD", 1)
    calls = []

    def _deny(n):
        calls.append(n)
        return False

    with pytest.raises(RuntimeError, match="취소"):
        optimize_grid(gedos, cell_mm=20.0, finger_widths_um=[50.0, 60.0],
                      finger_pitches_mm=[1.8], n_busbars_list=[2],
                      busbar_widths_mm=[0.2], scenario=SCENARIO_MEASURED,
                      axis_segments_override=AX, npts=NPTS, confirm=_deny)
    assert calls == [2], "confirm이 조합 수와 함께 정확히 한 번 불려야 한다"


def test_combo_confirm_not_called_below_threshold(gedos, monkeypatch):
    """임계 이하면 confirm을 주더라도 부르지 않는다."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    calls = []
    opt = optimize_grid(gedos, confirm=lambda n: calls.append(n) or True,
                        **_SWEEP_BASE)
    assert calls == [], "임계 이하인데 확인을 물었다"
    assert opt["n_combos"] == 1
