# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Rs_base sensitivity sweep — where does bulk lateral transport start to matter?

**Solver is READ-ONLY.** Script only; nothing in the engine is modified.

Purpose is *not* to predict a measured value. It is to find the range over which
``DiodeParams.Rs_base`` [Ohm/sq, lateral] changes the result at all, so we know
whether the parameter is worth measuring.

Rear mode must be **bifacial**. ``full_area`` fixes the rear at V_rear = 0
(ideal contact), so the rear plane's sheet conductance cannot change anything —
the engine rejects Rs_base there rather than accepting it and silently doing
nothing (docs/base_lateral_convention.md §3-4). This script therefore builds a
bifacial M10 and would be meaningless on a monofacial one.

    python analysis/unist_rhoc/rs_base_sensitivity.py
    python analysis/unist_rhoc/rs_base_sensitivity.py --mesh Low --npts 8
"""
import argparse
import csv
import os
import sys
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, "tests"))
sys.path.insert(0, _ROOT)

import conftest                      # noqa: E402

fest = conftest._load_fest()

OUT_DIR = os.path.join(_HERE, "out")

# M10 reference cell. Front grid is a plausible commercial design; the point is
# a fixed reference, not an optimised one - only Rs_base varies.
CELL_MM = 182.0
N_BUSBARS = 16
W_BUSBAR_MM = 0.20
W_FINGER_UM = 45.0
PITCH_MM = 1.40
EDGE_MARGIN_MM = 1.0
RHO_L_UOHM_CM = 4.22
RS_SHEET = 147.1            # front TCO, the "after" value
RHO_C_MOHM = 15.32          # the "after" value
N_PROBE_POINTS = 10

# Rear grid for the bifacial build. Rs_base parallels the REAR plane's sheet
# conductance (1/Rs_eff = 1/Rs_rear_tco + 1/Rs_base), so the rear has to be a
# real conducting plane for the parameter to have anywhere to act.
REAR_N_FINGERS_PITCH_MM = 1.60
REAR_W_FINGER_UM = 60.0

# The sweep. None = off (engine default). The decade span is deliberate: we do
# not know the range where this matters, so bracket it widely and let the
# numbers say where the knee is.
RS_BASE_VALUES = [None, 10000.0, 5000.0, 2000.0, 1000.0]


def build_geo():
    """Bifacial M10. Rear is a real conducting plane, not an ideal contact."""
    bb_frac = max(0.0, (CELL_MM - 2.0 * EDGE_MARGIN_MM) / CELL_MM)
    common = dict(
        input_mode="finger_spacing",
        n_busbars=N_BUSBARS,
        w_busbar=W_BUSBAR_MM * 0.1,
        n_probe_points=N_PROBE_POINTS,
        edge_gap=EDGE_MARGIN_MM * 0.1,
        busbar_length_frac=bb_frac,
        rho_bulk=RHO_L_UOHM_CM * 1e-6,
    )
    front = fest.GridDesign(
        finger_spacing_mm=PITCH_MM,
        w_finger=W_FINGER_UM * 1e-4,
        Rs_sheet=RS_SHEET,
        rho_contact=RHO_C_MOHM * 1e-3,
        **common)
    rear = fest.GridDesign(
        finger_spacing_mm=REAR_N_FINGERS_PITCH_MM,
        w_finger=REAR_W_FINGER_UM * 1e-4,
        **common)
    return fest.CellGeometry(cell_w=CELL_MM * 0.1, cell_h=CELL_MM * 0.1,
                             front=front, rear=rear)


def evaluate(geo, rs_base, mesh, npts):
    dp = fest.DiodeParams()
    dp.Rs_base = rs_base          # None = off

    pts, tri = fest.generate_mesh(geo, mesh_tangent=mesh, mesh_perp=mesh)
    isf, isb, isp, ism, isrm, isrp = fest.classify_nodes(pts, geo)
    S = fest.FESTSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)

    g = geo.front
    t0 = time.time()
    Vs, Js, iv = S.calc_iv(g.rho_bulk, g.finger_h, g.w_f, g.rho_contact,
                           g.Rs_sheet, g.shape_cf, dp, mode="tandem", npts=npts)
    return {
        "Rs_base_ohm_sq": ("off" if rs_base is None else f"{rs_base:g}"),
        "Rs_rear_tco_ohm_sq": dp.Rs_rear_tco,
        "Rs_eff_rear_ohm_sq": (dp.Rs_rear_tco if rs_base is None
                               else 1.0 / (1.0 / dp.Rs_rear_tco + 1.0 / rs_base)),
        "nodes": len(pts),
        "Jsc_mA_cm2": iv["Jsc"],
        "Voc_V": iv["Voc"],
        "FF_pct": iv["FF"],
        "efficiency_pct": iv["Eff"],
        "seconds": time.time() - t0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default="Med", choices=["Low", "Med", "High", "Max"])
    ap.add_argument("--npts", type=int, default=10)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)

    geo = build_geo()
    assert geo.rear_mode in ("bifacial", "patterned"), (
        f"rear_mode={geo.rear_mode!r} - Rs_base has no effect on an ideal-contact "
        f"rear and the engine rejects it there")
    print(f"M10 reference cell, rear_mode={geo.rear_mode}, "
          f"front {W_FINGER_UM:g}um / {PITCH_MM:g}mm / {N_BUSBARS} busbars, "
          f"mesh={args.mesh}, npts={args.npts}")
    print()

    rows = []
    for rb in RS_BASE_VALUES:
        r = evaluate(geo, rb, args.mesh, args.npts)
        rows.append(r)
        print(f"  Rs_base={r['Rs_base_ohm_sq']:>6}  "
              f"Rs_eff(rear)={r['Rs_eff_rear_ohm_sq']:7.3f}  "
              f"Voc={r['Voc_V']:.4f}  FF={r['FF_pct']:.3f}  "
              f"Jsc={r['Jsc_mA_cm2']:.4f}  eff={r['efficiency_pct']:.4f}%  "
              f"({r['seconds']:.1f}s)", flush=True)

    base = rows[0]                        # Rs_base off
    print()
    print("| Rs_base (Ω/sq) | Rs_eff rear (Ω/sq) | Voc (V) | FF (%) | "
          "Jsc (mA/cm²) | η (%) | Δη vs off |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        d = r["efficiency_pct"] - base["efficiency_pct"]
        print(f"| {r['Rs_base_ohm_sq']} | {r['Rs_eff_rear_ohm_sq']:.3f} | "
              f"{r['Voc_V']:.4f} | {r['FF_pct']:.3f} | {r['Jsc_mA_cm2']:.4f} | "
              f"{r['efficiency_pct']:.4f} | {d:+.4f} |")

    path = os.path.join(OUT_DIR, "rs_base_sensitivity.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("# Rs_base sensitivity - M10 reference cell, bifacial rear\n")
        fh.write(f"# generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        fh.write(f"# mesh={args.mesh} npts={args.npts} "
                 f"front={W_FINGER_UM:g}um/{PITCH_MM:g}mm/{N_BUSBARS}bb\n")
        fh.write("# purpose: locate the range where Rs_base changes the result "
                 "at all - NOT a prediction of a measured value\n")
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
