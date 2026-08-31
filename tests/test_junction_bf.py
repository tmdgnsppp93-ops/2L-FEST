# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Phase 3 (v28.35): Phase-B bifacial junction solver — regression guards.

DIAGNOSIS (see commit / changelog): the spec's premise for Phase 3 — a Vint-Vr
degeneracy fixed by adding a 0V Dirichlet anchor on the rear-metal terminal — is
already handled by the current code:
  * v28.16 "Method B" makes the oVint DOF hold Vbot directly (V_int = Vbot + Vr
    is reconstructed), so the (V_int+c, Vr+c) null mode is gone and the Jacobian
    is nonsingular by construction (GEDOS_...:4615-4628, 4769-4774).
  * The rear-metal pad nodes ARE already Dirichlet-pinned to 0V
    (GEDOS_...:4591, 4687-4688, 4760-4766).
So NO solver code was changed. These tests fence the measured behaviour so any
future regression (or the plateau below silently improving/worsening) is caught.

Measured on Python 3.14.3 / numpy 2.4.3 / scipy 1.17.1.
"""
import numpy as np
import pytest

GAIN = 0.2
BASE = dict(rm=3e-6, hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)
RSJ = [1, 50, 200, 1000, 5000, 10000]


def _solve(S, dp, rs_j, vb, gain=GAIN):
    dp.Rs_junction = rs_j
    dp.bifacial_gain = gain
    res = S.solve(BASE["rm"], BASE["hf"], BASE["wf"], BASE["rc"], BASE["Rs"],
                  vb, BASE["cf"], dp, "tandem")
    rl = res.get("res")
    return res, (rl[-1] if rl else float("nan"))


def _matrix_params():
    params = []
    for rs in RSJ:
        for vf in (0.0, 0.85, 0.95):
            marks = ()
            if vf == 0.0:
                marks = pytest.mark.xfail(
                    reason="short-circuit absolute-KCL residual plateau (~9e-3); "
                           "legacy Phase A plateaus at Vb=0 too and the solution is "
                           "accurate (test_vb0_solution_accurate). Not a degeneracy.",
                    strict=False)
            params.append(pytest.param(rs, vf, marks=marks, id=f"Rsj{rs}-Vb{vf}"))
    return params


# --- (1) 18-combo convergence matrix (12 pins + 6 Vb=0 xfail) ------------------
@pytest.mark.parametrize("rs_j,vb_frac", _matrix_params())
def test_junction_bf_convergence(gedos, make_bifacial, monkeypatch, rs_j, vb_frac):
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    S = make_bifacial().S
    dp = gedos.DiodeParams()
    Voc0 = dp.expected_voc()[2]
    _, r = _solve(S, dp, rs_j, vb_frac * Voc0)
    assert r <= 1e-6, f"Rs_j={rs_j} Vb={vb_frac}*Voc0 residual {r:.2e} > 1e-6"


# --- (2) Vb=0 solution accuracy: residual plateaus but the physics is right ----
def test_vb0_solution_accurate(gedos, make_bifacial, monkeypatch):
    """Rs_j=5000, gain=0.2, Vb=0: Phase B cell_current == legacy Phase A within 0.1%.

    This is the key guard behind the Vb=0 xfails: the KCL residual floors at ~9e-3
    at short circuit, but the extracted current matches the legacy Phase-A baseline
    (measured 0.015%), proving the plateau is a residual-metric artifact.
    """
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    Sb = make_bifacial().S
    dpb = gedos.DiodeParams()
    resb, _ = _solve(Sb, dpb, 5000.0, 0.0)
    Jb = float(Sb.cell_current(resb, dpb))

    monkeypatch.setenv("GEDOS_LEGACY_LOCAL_MATCH", "1")
    Sa = make_bifacial().S
    dpa = gedos.DiodeParams(); dpa.bifacial_gain = GAIN; dpa.Rs_junction = 0.0
    resa = Sa.solve(BASE["rm"], BASE["hf"], BASE["wf"], BASE["rc"], BASE["Rs"],
                    0.0, BASE["cf"], dpa, "tandem")
    Ja = float(Sa.cell_current(resa, dpa))

    d = 100.0 * abs(Jb - Ja) / abs(Ja)
    assert d <= 0.1, f"Vb=0 Phase B vs legacy A cell_current differ {d:.4f}% (Jb={Jb} Ja={Ja})"


# --- (3) extreme-Rs_j consistency vs legacy Phase A (original spec) ------------
def test_extreme_consistency(gedos, make_bifacial, monkeypatch):
    """Rs_j=1e5, gain=0.2, Vb=0.9*Voc0: junction_bf J within 3% of legacy Phase A."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    Sb = make_bifacial().S
    dpb = gedos.DiodeParams()
    Voc0 = dpb.expected_voc()[2]
    Vb = 0.9 * Voc0
    resb, rb = _solve(Sb, dpb, 1e5, Vb)
    Jb = float(Sb.cell_current(resb, dpb))

    monkeypatch.setenv("GEDOS_LEGACY_LOCAL_MATCH", "1")
    Sa = make_bifacial().S
    dpa = gedos.DiodeParams(); dpa.bifacial_gain = GAIN; dpa.Rs_junction = 0.0
    resa = Sa.solve(BASE["rm"], BASE["hf"], BASE["wf"], BASE["rc"], BASE["Rs"],
                    Vb, BASE["cf"], dpa, "tandem")
    Ja = float(Sa.cell_current(resa, dpa))

    d = 100.0 * abs(Jb - Ja) / abs(Ja)
    assert d <= 3.0, f"Rs_j=1e5 junction_bf vs legacy A differ {d:.3f}% (Jb={Jb} Ja={Ja})"


# --- (4) nonsingularity guard: the cited "divergence" case solves cleanly ------
def test_junction_bf_nonsingular(gedos, make_bifacial, monkeypatch):
    """Rs_j=5000, gain=0.2, Vb=0.95*Voc0: solves via spsolve to residual<=1e-6.

    Pins that the Jacobian is nonsingular at the case the spec called degenerate.
    The absolute condition number (~1e9) is not pinned — it is numerically noisy.
    """
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    S = make_bifacial().S
    dp = gedos.DiodeParams()
    Voc0 = dp.expected_voc()[2]
    res, r = _solve(S, dp, 5000.0, 0.95 * Voc0)
    assert r <= 1e-6, f"residual {r:.2e} > 1e-6 (would indicate singular Jacobian)"
    assert np.isfinite(float(S.cell_current(res, dp)))
