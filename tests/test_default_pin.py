"""Pin test: DEFAULT (Phase B) path bit-preservation (v28.33).

Default DiodeParams (Rs_junction=5000, Rc_junction=0.1), FEST_LEGACY_LOCAL_MATCH
unset -> tandem dispatches to the Phase B interlayer solver. Full-area mono cell.

Pinned on Python 3.14.3 / numpy 2.4.3 / scipy 1.17.1 (see commit message).
Fresh solver each run (no warm-start history) so values are order-independent.
"""

PARAMS = dict(rm=3e-6, hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)
PINS = [18.678777562124054, 18.215245612864987, 11.388031779177389]
RTOL = 1e-8


def test_default_pin(fest, make_mono, monkeypatch):
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    S = make_mono().S
    dp = fest.DiodeParams()  # defaults: Rs_junction=5000, Rc_junction=0.1
    Voc0 = dp.expected_voc()[2]
    vbs = [0.0, 0.85 * Voc0, 0.95 * Voc0]
    for Vb, pin in zip(vbs, PINS):
        res = S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                      PARAMS["Rs"], Vb, PARAMS["cf"], dp, "tandem")
        assert S._K_junc is not None, "default must build the Phase B interlayer"
        J = float(S.cell_current(res, dp))
        assert abs(J - pin) <= RTOL * abs(pin), f"Vb={Vb}: {J!r} vs pinned {pin!r}"
