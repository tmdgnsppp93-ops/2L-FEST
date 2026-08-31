# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Phase 2 (v28.34): rear metal wiring + unit fix.

The rear metal stiffness (_Krm) must now use the rear metal sheet R
(Rs_rear_metal_auto), decoupled from the front rm/hf, so front-only hot pressing
leaves the rear at its baseline.

(a) fixed rear sheet R (0.01322) != front-coupled fallback (<=0)  -> wiring live.
(b) fixed mode: changing front rm leaves _Krm bit-identical              -> decoupled.
(b-ctrl) fallback mode: _Krm DOES track front rm (legacy bit-identical)  -> control.
(c) full_area monofacial is unaffected by Rs_rear_metal_sheet (no rear grid).

Bifacial tests use the legacy Phase-A bifacial path (GEDOS_LEGACY_LOCAL_MATCH=1 +
Rs_junction=0) for a simple, deterministic solve. Pinned on Python 3.14.3 /
numpy 2.4.3 / scipy 1.17.1.
"""
import numpy as np

BIF = dict(hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)


def _solve_bif(S, dp, rm):
    dp.Rs_junction = 0.0  # legacy Phase-A bifacial (flag set by the test)
    Voc0 = dp.expected_voc()[2]
    return S.solve(rm, BIF["hf"], BIF["wf"], BIF["rc"], BIF["Rs"],
                   0.85 * Voc0, BIF["cf"], dp, "tandem")


def test_rear_wiring_live(gedos, make_bifacial, monkeypatch):
    """(a) fixed rear sheet R != front-coupled fallback -> Rs_rear is wired in."""
    monkeypatch.setenv("GEDOS_LEGACY_LOCAL_MATCH", "1")
    S1 = make_bifacial().S
    dp1 = gedos.DiodeParams(); dp1.Rs_rear_metal_sheet = 0.01322
    J_fixed = float(S1.cell_current(_solve_bif(S1, dp1, 3e-6), dp1))
    S2 = make_bifacial().S
    dp2 = gedos.DiodeParams(); dp2.Rs_rear_metal_sheet = 0.0  # fallback -> rm/hf
    J_fallback = float(S2.cell_current(_solve_bif(S2, dp2, 3e-6), dp2))
    rel = abs(J_fixed - J_fallback) / abs(J_fallback)
    assert rel > 1e-5, f"fixed vs fallback nearly identical ({rel:.2e}) -> wiring dead"


def test_rear_decoupled_from_front_rm(gedos, make_bifacial, monkeypatch):
    """(b) fixed mode: front rm change leaves rear _Krm bit-identical."""
    monkeypatch.setenv("GEDOS_LEGACY_LOCAL_MATCH", "1")
    S = make_bifacial().S
    dp = gedos.DiodeParams(); dp.Rs_rear_metal_sheet = 0.01322
    _solve_bif(S, dp, 3e-6); Krm_a = S._Krm.copy()
    _solve_bif(S, dp, 2e-6); Krm_b = S._Krm.copy()
    d = (Krm_a - Krm_b)
    maxabs = float(np.abs(d.data).max()) if d.nnz > 0 else 0.0
    assert maxabs == 0.0, f"rear _Krm changed with front rm ({maxabs:.2e}) -> still coupled"


def test_rear_fallback_still_coupled(gedos, make_bifacial, monkeypatch):
    """(b-control) fallback (Rs_rear_metal_sheet<=0) rear tracks front rm (legacy)."""
    monkeypatch.setenv("GEDOS_LEGACY_LOCAL_MATCH", "1")
    S = make_bifacial().S
    dp = gedos.DiodeParams(); dp.Rs_rear_metal_sheet = 0.0
    _solve_bif(S, dp, 3e-6); Ka = S._Krm.copy()
    _solve_bif(S, dp, 2e-6); Kb = S._Krm.copy()
    d = (Ka - Kb)
    maxabs = float(np.abs(d.data).max()) if d.nnz > 0 else 0.0
    assert maxabs > 0.0, "fallback rear should track front rm (bit-identical to legacy)"


def test_monofacial_unaffected(gedos, make_mono, monkeypatch):
    """(c) full_area monofacial has no rear metal grid -> Rs_rear_metal_sheet no-op."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    p = dict(rm=3e-6, hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)
    S1 = make_mono().S
    dp1 = gedos.DiodeParams(); dp1.Rs_rear_metal_sheet = 0.01322
    S2 = make_mono().S
    dp2 = gedos.DiodeParams(); dp2.Rs_rear_metal_sheet = 0.0
    Vb = 0.85 * dp1.expected_voc()[2]
    J1 = float(S1.cell_current(
        S1.solve(p["rm"], p["hf"], p["wf"], p["rc"], p["Rs"], Vb, p["cf"], dp1, "tandem"), dp1))
    J2 = float(S2.cell_current(
        S2.solve(p["rm"], p["hf"], p["wf"], p["rc"], p["Rs"], Vb, p["cf"], dp2, "tandem"), dp2))
    assert J1 == J2, f"monofacial affected by rear sheet R: {J1!r} vs {J2!r}"
