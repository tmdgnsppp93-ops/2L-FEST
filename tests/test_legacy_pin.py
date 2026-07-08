"""Pin test: LEGACY (Phase A local current matching) path bit-preservation.

FEST_LEGACY_LOCAL_MATCH=1 + dp.Rs_junction=0 -> _K_junc is None -> tandem uses
the legacy Phase-A local-node current-matching path. This pin guards that path
from silent numerical drift as later phases change surrounding code.

Pinned on Python 3.14.3 / numpy 2.4.3 / scipy 1.17.1 (see commit message).
Fresh solver each run so values are order-independent.
"""

PARAMS = dict(rm=3e-6, hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)
PINS = [18.678777559153552, 18.276331778124046, 11.835353257148611]
RTOL = 1e-8


def test_legacy_pin(fest, make_mono, monkeypatch):
    monkeypatch.setenv("FEST_LEGACY_LOCAL_MATCH", "1")
    S = make_mono().S
    dp = fest.DiodeParams()
    dp.Rs_junction = 0.0  # Phase-A trigger (allowed only under the legacy flag)
    Voc0 = dp.expected_voc()[2]
    vbs = [0.0, 0.85 * Voc0, 0.95 * Voc0]
    for Vb, pin in zip(vbs, PINS):
        res = S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                      PARAMS["Rs"], Vb, PARAMS["cf"], dp, "tandem")
        assert S._K_junc is None, "legacy flag + Rs_j=0 must NOT build the interlayer"
        J = float(S.cell_current(res, dp))
        assert abs(J - pin) <= RTOL * abs(pin), f"Vb={Vb}: {J!r} vs pinned {pin!r}"
