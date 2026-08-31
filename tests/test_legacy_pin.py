# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Pin test: LEGACY (Phase A local current matching) path bit-preservation.

GEDOS_LEGACY_LOCAL_MATCH=1 + dp.Rs_junction=0 -> _K_junc is None -> tandem uses
the legacy Phase-A local-node current-matching path. This pin guards that path
from silent numerical drift as later phases change surrounding code.

Pinned on Python 3.14.3 / numpy 2.4.3 / scipy 1.17.1 (see commit message).
Fresh solver each run so values are order-independent.

스택이 다르면 RTOL=1e-8이 SuperLU/BLAS 차이만으로 깨진다 → 이유를 붙인 xfail로
낮춘다(v28.46, test_default_pin과 동일 정책). 핀 스택에서는 strict fail 유지.
"""
import pytest

PARAMS = dict(rm=3e-6, hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)
PINS = [18.678777559153552, 18.276331778124046, 11.835353257148611]
RTOL = 1e-8


def test_legacy_pin(gedos, make_mono, monkeypatch, bit_pin_gate):
    if bit_pin_gate:
        pytest.xfail(f"비트 핀 캡처 스택과 다름 ({bit_pin_gate}) — "
                     "1e-8 비트 동일은 이 스택에서 성립하지 않는다(물리 회귀 아님)")
    monkeypatch.setenv("GEDOS_LEGACY_LOCAL_MATCH", "1")
    S = make_mono().S
    dp = gedos.DiodeParams()
    dp.Rs_junction = 0.0  # Phase-A trigger (allowed only under the legacy flag)
    Voc0 = dp.expected_voc()[2]
    vbs = [0.0, 0.85 * Voc0, 0.95 * Voc0]
    for Vb, pin in zip(vbs, PINS):
        res = S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                      PARAMS["Rs"], Vb, PARAMS["cf"], dp, "tandem")
        assert S._K_junc is None, "legacy flag + Rs_j=0 must NOT build the interlayer"
        J = float(S.cell_current(res, dp))
        assert abs(J - pin) <= RTOL * abs(pin), f"Vb={Vb}: {J!r} vs pinned {pin!r}"
