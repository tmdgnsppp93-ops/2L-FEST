# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""M10 속도개선 회귀 핀 — measured 8BB/0.20mm/finger 20µm·1.77mm.

Phase B 속도 최적화(엔진 수정)가 결과를 바꾸지 않음을 보장하는 authoritative 핀.
느리다(M10 풀-FEM ≈17분) → @pytest.mark.slow. 빠른 반복은 `-m "not slow"`로 제외,
핀만 실행은 `pytest tests/test_speed_pin.py`.

A등급 변경: 상대 1e-6 이내(비트 사실상 동일).  B등급 변경: 1e-4 %abs 이내.
값 캡처: Python 3.14.3 / numpy 2.4.3 / scipy 1.17.1, 현재 엔진(v28.38) 기준.
"""
import pytest

PIN = dict(
    n_fingers=102,
    Jsc=19.257406483632003,
    Voc=1.9259666999965743,
    FF=84.41037602092787,
    Eff=31.30706870694106,
    total_loss=1.0693288448616638,
)
RTOL_A = 1e-6        # A등급(결과 불변): 상대오차
ATOL_B_ABS = 1e-4    # B등급(샘플링 변경): Eff/Voc 등 %abs·V 절대오차


def _run(gedos):
    from front_electrode import evaluate_existing_simulation, SCENARIO_MEASURED
    grid = dict(cell_w_mm=182.0, cell_h_mm=182.0, finger_spacing_mm=1.77,
                w_finger_um=20.0, n_busbars=8, w_busbar_mm=0.20, n_probe_points=10)
    return evaluate_existing_simulation(
        gedos, grid, scenario=SCENARIO_MEASURED, busbar_recovery_factor=0.0,
        mode="tandem", npts=14, target_nodes=82000)


@pytest.mark.slow
def test_m10_8bb_pin_Agrade(gedos, monkeypatch):
    """A등급: 상대 1e-6 이내(행렬·솔버 재사용 등 결과 불변 변경용)."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    out = _run(gedos)
    er = out["engine_raw"]
    assert out["parameters"]["n_fingers"] == PIN["n_fingers"]
    for k, v in (("Jsc", er["Jsc"]), ("Voc", er["Voc"]), ("FF", er["FF"]),
                 ("Eff", er["Eff"])):
        assert abs(v - PIN[k]) <= RTOL_A * abs(PIN[k]), f"{k}: {v!r} vs pin {PIN[k]!r}"
    tl = out["results"]["total_loss"]
    assert abs(tl - PIN["total_loss"]) <= RTOL_A * abs(PIN["total_loss"]), \
        f"total_loss: {tl!r} vs pin {PIN['total_loss']!r}"


@pytest.mark.slow
@pytest.mark.bgrade
def test_m10_8bb_pin_Bgrade(gedos, monkeypatch):
    """B등급: Eff/Voc는 1e-4 %abs·V 이내, Jsc/n_f는 불변(샘플링 변경 무관)."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    out = _run(gedos)
    er = out["engine_raw"]
    assert out["parameters"]["n_fingers"] == PIN["n_fingers"]
    # Jsc는 Vb=0 해라 샘플링과 무관 → A등급 유지
    assert abs(er["Jsc"] - PIN["Jsc"]) <= RTOL_A * abs(PIN["Jsc"])
    # Eff/Voc는 MPP/Voc 탐색 방식 변경 시 1e-4 %abs·V 이내
    assert abs(er["Eff"] - PIN["Eff"]) <= ATOL_B_ABS, f"Eff {er['Eff']!r}"
    assert abs(er["Voc"] - PIN["Voc"]) <= ATOL_B_ABS, f"Voc {er['Voc']!r}"
