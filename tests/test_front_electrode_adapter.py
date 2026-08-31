# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Phase 1 — front_electrode adapter + busbar recovery 테스트.

절대 원칙 검증: recovery OFF일 때 adapter 결과가 기존 엔진 직접 호출과 완전히
동일(구버전==신버전). recovery는 busbar shading line-item에만 적용되고 다른
손실·효율에는 영향이 없어야 한다.

Pinned: Python 3.14.3 / numpy 2.4.3 / scipy 1.17.1.
"""
import sys
import os

# repo 루트를 path에 추가(front_electrode 패키지 import)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from front_electrode import (  # noqa: E402
    evaluate_existing_simulation,
    busbar_shading_breakdown,
    DEFAULT_BUSBAR_RECOVERY_FACTOR,
)

# 작고 빠른 지오메트리 (mono 픽스처와 동일: 20mm, 8F/1BB, ~3.8k nodes)
GRID = dict(cell_w_mm=20.0, cell_h_mm=20.0, n_fingers=8, n_busbars=1,
            w_finger_um=50.0, w_busbar_mm=0.6, n_probe_points=0)
AX = 36        # axis_segments_override — 픽스처와 동일
TEST_NPTS = 8  # 테스트 속도용(회귀 등식은 adapter/direct가 같은 npts만 쓰면 무관)


def _direct_engine(gedos, grid, mode="tandem", npts=TEST_NPTS):
    """adapter를 거치지 않고 엔진을 직접 실행 — '구버전' 기준값."""
    front = gedos.GridDesign(
        input_mode="n_fingers", n_fingers=grid["n_fingers"],
        n_busbars=grid["n_busbars"], w_finger=grid["w_finger_um"] * 1e-4,
        w_busbar=grid["w_busbar_mm"] / 10.0,
        n_probe_points=grid.get("n_probe_points", 0))
    geo = gedos.CellGeometry(cell_w=grid["cell_w_mm"] / 10.0,
                            cell_h=grid["cell_h_mm"] / 10.0, front=front)
    pts, tri = gedos.generate_mesh(geo, axis_segments_override=AX)
    isf, isb, isp, ism, isrm, isrp = gedos.classify_nodes(pts, geo)
    S = gedos.GEDOSSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)
    g = geo.front
    dp = gedos.DiodeParams()
    Vs, Js, iv = S.calc_iv(g.rho_bulk, g.finger_h, g.w_f, g.rho_contact,
                           g.Rs_sheet, g.shape_cf, dp, mode=mode, npts=npts)
    vb = iv.get("Vmpp_internal", iv["Vmpp"])
    r = iv.get("_mpp_result") or S.solve(g.rho_bulk, g.finger_h, g.w_f,
                                         g.rho_contact, g.Rs_sheet, vb, g.shape_cf, dp, mode)
    L = S.losses(r, g.rho_bulk, g.finger_h, g.w_f, g.rho_contact, g.Rs_sheet,
                 g.shape_cf, dp, Vmpp=iv["Vmpp"], Jmpp=iv["Jmpp"])
    return iv, L, geo


def test_regression_recovery_off(gedos, monkeypatch):
    """recovery OFF → adapter 결과가 엔진 직접 호출과 비트 동일(구버전==신버전)."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    iv, L, _ = _direct_engine(gedos, GRID)
    out = evaluate_existing_simulation(gedos, GRID, busbar_recovery_factor=0.0,
                                       axis_segments_override=AX, npts=TEST_NPTS)
    # optical_loss / efficiency 가 엔진 값과 정확히 일치
    assert out["results"]["optical_loss"] == L["P_shade"]
    assert out["results"]["efficiency"] == iv["Eff"]
    # 원본 엔진 값도 비트 동일
    assert out["engine_raw"]["P_shade"] == L["P_shade"]
    assert out["engine_raw"]["Eff"] == iv["Eff"]
    assert out["engine_raw"]["Pf_busbar"] == L["Pf_busbar"]
    assert out["results"]["recovered_busbar_light"] == 0.0


def test_recovery_arithmetic():
    """순수 회수 산술: raw 2.0% + factor 0.25 → recovered 0.5%, effective 1.5%."""
    raw = 0.02
    f = 0.25
    recovered = raw * f
    effective = raw * (1.0 - f)
    assert abs(recovered - 0.005) < 1e-12
    assert abs(effective - 0.015) < 1e-12
    assert abs((recovered + effective) - raw) < 1e-12
    assert DEFAULT_BUSBAR_RECOVERY_FACTOR == 0.25


def test_recovery_applied(gedos, monkeypatch):
    """factor 0.25 적용 시 recovered/effective가 raw로부터 정확히 나온다."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    f = 0.25
    out = evaluate_existing_simulation(gedos, GRID, busbar_recovery_factor=f,
                                       axis_segments_override=AX, npts=TEST_NPTS)
    r = out["results"]
    raw = r["raw_busbar_shading"]
    assert raw > 0.0, "테스트 지오메트리의 busbar shading이 0보다 커야 함"
    assert abs(r["recovered_busbar_light"] - raw * f) < 1e-12
    assert abs(r["effective_busbar_shading"] - raw * (1.0 - f)) < 1e-12
    assert abs((r["recovered_busbar_light"] + r["effective_busbar_shading"]) - raw) < 1e-12
    # 회수로 optical_loss가 엔진 P_shade보다 작아짐
    assert r["optical_loss"] < out["engine_raw"]["P_shade"]


def test_recovery_scope(gedos, monkeypatch):
    """recovery factor를 바꿔도 finger shading/전기손실/엔진 원본값 불변 —
    busbar 관련 필드와 (회수 반영된) efficiency만 변한다.

    v28.41: recovery는 이제 efficiency에도 double-entry로 반영된다
    (efficiency = iv['Eff'] + recovered_power). 따라서 efficiency는 더 이상
    회수에 불변이 아니며, engine_raw['Eff'](순수 엔진값)만 불변이다."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    a = evaluate_existing_simulation(gedos, GRID, busbar_recovery_factor=0.0,
                                     axis_segments_override=AX, npts=TEST_NPTS)
    b = evaluate_existing_simulation(gedos, GRID, busbar_recovery_factor=0.5,
                                     axis_segments_override=AX, npts=TEST_NPTS)
    # 범위 밖 값: 완전히 동일해야 함
    assert a["results"]["finger_shading_loss"] == b["results"]["finger_shading_loss"]
    assert a["results"]["electrical_loss"] == b["results"]["electrical_loss"]
    # engine_raw는 순수 엔진값 → recovery와 무관하게 완전 동일(Eff 포함).
    for k in ("Pe", "Pf_finger", "Pf_busbar", "Pc", "P_shade", "Eff"):
        assert a["engine_raw"][k] == b["engine_raw"][k], f"{k}가 recovery로 변함(범위 위반)"
    # f=0인 a는 efficiency == 순수 엔진값.
    assert a["results"]["efficiency"] == a["engine_raw"]["Eff"]
    # recovery ON인 b는 efficiency가 Δeff = recovered_power/Pin×100 만큼 증가.
    # Pin은 엔진 출력에서 역산(Eff=Pmpp/Pin×100 → Pin=Pmpp/Eff×100), adapter와 동일.
    rec_power_b = (b["results"]["recovered_busbar_light"]
                   * b["engine_raw"]["Jmpp"] * b["engine_raw"]["Vmpp"])
    pin_b = b["engine_raw"]["Pmpp"] / b["engine_raw"]["Eff"] * 100.0
    exp_deff_b = rec_power_b / pin_b * 100.0     # Pin=100이면 == rec_power_b
    assert b["results"]["efficiency"] > a["results"]["efficiency"]
    assert abs((b["results"]["efficiency"] - a["results"]["efficiency"]) - exp_deff_b) < 1e-9
    # (efficiency + total_loss)는 회수에 불변 → 이중계산 없음.
    assert abs((a["results"]["efficiency"] + a["results"]["total_loss"])
               - (b["results"]["efficiency"] + b["results"]["total_loss"])) < 1e-9
    # busbar 관련만 변함
    assert b["results"]["recovered_busbar_light"] > a["results"]["recovered_busbar_light"]
    assert b["results"]["effective_busbar_shading"] < a["results"]["effective_busbar_shading"]


def test_shading_breakdown_no_double_count(gedos, monkeypatch):
    """busbar_shading_breakdown 합이 엔진 shading_fraction()과 정확히 일치(겹침 이중계산 없음)."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    front = gedos.GridDesign(input_mode="n_fingers", n_fingers=GRID["n_fingers"],
                            n_busbars=GRID["n_busbars"], w_finger=GRID["w_finger_um"] * 1e-4,
                            w_busbar=GRID["w_busbar_mm"] / 10.0)
    geo = gedos.CellGeometry(cell_w=2.0, cell_h=2.0, front=front)
    bd = busbar_shading_breakdown(geo, geo.w_f, geo.w_b)
    total_engine = geo.shading_fraction(geo.w_f, geo.w_b)
    # finger + net_busbar + pad == 엔진 총 shading (분해가 정확)
    recomposed = bd["finger_shading"] + bd["raw_busbar_shading"] + bd["pad_shading"]
    assert abs(recomposed - total_engine) < 1e-12
    assert abs(bd["total_shading"] - total_engine) < 1e-12
