# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Re-run the two tandem baselines under the v28.33 default (Phase B interlayer).

Headless (no GUI): reuses the tests/conftest.py mock harness to import the app
as module `gedos`, then drives the FEM solver directly. For each cell it runs the
SAME geometry/params under BOTH:
  * legacy Phase A  (GEDOS_LEGACY_LOCAL_MATCH=1, Rs_junction=0)  -> "이전" column
  * default Phase B (Rs_junction=5000, Rc_junction=0.1)         -> "신규" column
so the "previous (Phase A)" numbers are MEASURED here, not trusted from memory.
The hard-coded references (M10 26.113%, small 26.762%) are shown for context only.

Pure measurement — no solver/default code is modified.

CONFIG PROVENANCE
  * M10 cell    : task-specified (12BB / 132F / 40um finger / 0.6mm BB /
                  182x182mm, monofacial). 132 fingers fixed (never 80).
  * small cell  : NOT FOUND in repo or git history (grep for 26.762 / 132F /
                  M10 config returned nothing). Config below is ASSUMED — the
                  absolute small-area PCE may not equal the 26.762% reference;
                  the Phase A->B delta is still valid. FLAGGED in the output.
"""
import os
import sys
import csv
import platform

import numpy as np
import scipy

# --- load the app exactly like the test suite does -------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "tests"))
import conftest  # noqa: E402
gedos = conftest._load_gedos()


def _versions():
    print("=" * 78)
    print(f"Python {platform.python_version()} | numpy {np.__version__} | "
          f"scipy {scipy.__version__}")
    print(f"GEDOS build {gedos.__build__['version']} ({gedos.__build__['date']})")
    print("=" * 78)


# --- cell definitions -------------------------------------------------------
# cell_w/cell_h in cm (182 mm -> 18.2 cm). widths in cm (40 um = 40e-4 cm).
CELLS = {
    # M10: multi-probe (n_probe_points=10 per busbar). Diagnosed: single-probe
    # (n_probe_points=0) funnels all 12 busbars into one pad -> Pf_busbar=3.36
    # mW/cm2 dominates -> FF collapses to 31%. Mesh is converged at ~82k (Jsc
    # 14.60 identical at 83k/142k/199k), so this is a probe artifact, not mesh.
    "M10 (182x182mm, 132F/12BB, multi-probe 10/BB)": dict(
        cell_w=18.2, cell_h=18.2, n_fingers=132, n_busbars=12,
        w_finger=40e-4, w_busbar=0.06, n_probe_points=10, target_nodes=82000,
        provenance="task-specified geometry; multi-probe added (probe artifact fix)",
        ref_pce=26.113),
    # small cell config UNKNOWN (not in repo). Assumed a physically reasonable
    # low-shading lab cell: 20x20mm, 16F/2BB, 40um finger, 0.2mm busbar. The
    # original 0.6mm busbar (M10) would give ~15% shading on a 1cm cell, which
    # is unrealistic — so this is a best-effort placeholder, FLAGGED below.
    "small (ASSUMED 20x20mm, 16F/2BB, 0.2mm BB)": dict(
        cell_w=2.0, cell_h=2.0, n_fingers=16, n_busbars=2,
        w_finger=40e-4, w_busbar=0.02, n_probe_points=0, target_nodes=25000,
        provenance="UNVERIFIED (original GEO not found in repo)", ref_pce=26.762),
}


def _build_solver(spec):
    geo = gedos.CellGeometry(
        cell_w=spec["cell_w"], cell_h=spec["cell_h"],
        front=gedos.GridDesign(
            n_fingers=spec["n_fingers"], n_busbars=spec["n_busbars"],
            w_finger=spec["w_finger"], w_busbar=spec["w_busbar"],
            n_probe_points=spec.get("n_probe_points", 0)),
    )  # monofacial (no rear grid -> full_area)
    pts, tri, nfin, axfin = gedos._generate_mesh_for_target(
        geo, mesh_tangent="Med", mesh_perp="Med", target_nodes=spec["target_nodes"])
    isf, isb, isp, ism, isrm, isrp = gedos.classify_nodes(pts, geo)
    S = gedos.GEDOSSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)
    return geo, S, len(pts)


def _baseline_params(geo):
    """Before-hot-pressing baseline params, read off the front GridDesign."""
    g = geo.front
    return dict(rm=g.rho_bulk, hf=g.finger_h, wf=g.w_f, rc=g.rho_contact,
                Rs=g.Rs_sheet, cf=g.shape_cf)


def _run(S, geo, legacy):
    if legacy:
        os.environ["GEDOS_LEGACY_LOCAL_MATCH"] = "1"
    else:
        os.environ.pop("GEDOS_LEGACY_LOCAL_MATCH", None)
    dp = gedos.DiodeParams()
    if legacy:
        dp.Rs_junction = 0.0   # Phase A trigger (allowed under the flag)
    p = _baseline_params(geo)
    _, _, iv = S.calc_iv(p["rm"], p["hf"], p["wf"], p["rc"], p["Rs"], p["cf"],
                         dp, mode="tandem")
    model = gedos._phase_b_model_info(dp, "tandem")["interlayer_model"]
    shade = 100.0 * geo.shading_fraction(p["wf"], geo.w_b)
    return dict(Jsc=iv["Jsc"], Voc=iv["Voc"], FF=iv["FF"], PCE=iv["Eff"],
                shade=shade, model=model)


def main():
    _versions()
    rows = []
    for name, spec in CELLS.items():
        print(f"\n### {name}   [config: {spec['provenance']}]")
        geo, S, nnodes = _build_solver(spec)
        print(f"  mesh: {nnodes} nodes | ref_pce(hardcoded)={spec['ref_pce']}%")
        a = _run(S, geo, legacy=True)    # 이전 (Phase A)
        b = _run(S, geo, legacy=False)   # 신규 (Phase B)
        print(f"  model(이전) : {a['model']}")
        print(f"  model(신규) : {b['model']}")
        print(f"  {'metric':10}{'이전(Phase A)':>16}{'신규(Phase B)':>16}{'Δ':>12}")
        for key, unit in [("Jsc", "mA/cm2"), ("Voc", "V"), ("FF", "%"),
                          ("PCE", "%"), ("shade", "%")]:
            va, vb = a[key], b[key]
            d = vb - va
            print(f"  {key:10}{va:16.4f}{vb:16.4f}{d:+12.4f}  {unit}")
            rows.append(dict(cell=name, provenance=spec["provenance"], metric=key,
                             unit=unit, prev_phaseA=va, new_phaseB=vb, delta=d,
                             ref_hardcoded=(spec["ref_pce"] if key == "PCE" else ""),
                             model_new=b["model"]))
        # reference reconciliation note for PCE
        if abs(a["PCE"] - spec["ref_pce"]) > 0.05:
            print(f"  ⚠ 실측 legacy PCE {a['PCE']:.3f}% != hardcoded ref "
                  f"{spec['ref_pce']}% -> config/조건 불일치 가능 (양쪽 표기).")

    out_csv = os.path.join(_HERE, "rerun_baseline_result.csv")
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nCSV: {out_csv}")
    print("발표 자료엔 이 신규(Phase B) 값 + 'Interlayer: Phase B, Rs_j=5000 ohm/sq' "
          "명기 필요.")


if __name__ == "__main__":
    main()
