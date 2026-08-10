# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Bifacial diagnostic: is the 2T tandem top- or bottom-limited, and where does
rear illumination actually start to help?

Builds a *bifacial* solver (rear GridDesign present -> rear_mode='bifacial') and
sweeps dp.bifacial_gain = 0 -> 0.30 for both tandem and single-cell modes.
Also decomposes the area-weighted effective top/bottom photocurrents so we can
see the current-matching clamp directly.
"""
import importlib.util, numpy as np

spec = importlib.util.spec_from_file_location('fest', '2L_FEST_v28_18_wf_wired.py')
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
except SystemExit:
    pass

GridDesign   = m.GridDesign
CellGeometry = m.CellGeometry
FESTSolver   = m.FESTSolver

# --- Build a bifacial geometry: front H-pattern + rear H-pattern ---
front = GridDesign(n_fingers=2, n_busbars=1, w_finger=50e-4, w_busbar=50e-4)
rear  = GridDesign(n_fingers=2, n_busbars=1, w_finger=50e-4, w_busbar=50e-4)
GEO = CellGeometry(front=front, rear=rear)          # rear != None -> 'bifacial'
print(f"rear_mode = {GEO.rear_mode}")

pts, tri = m.generate_mesh(GEO, pass_density=2)
isf, isb, isp, ism, isrm, isrp = m.classify_nodes(pts, GEO)
S = FESTSolver(pts, tri, isf, isb, isp, ism, GEO, isrm, isrp)
print(f"mesh: {len(pts)} nodes, {len(tri.simplices)} tri")

# realistic-R operating point (same as _validate_tandem 'realistic')
P = dict(rm=1.6e-6, hf=10e-4, wf=40e-4, rc=1e-3, Rs=100.0, cf=1.0)

def run(mode, gains):
    dp = m.DiodeParams()
    rows = []
    for g in gains:
        dp.bifacial_gain = g
        Vs, Js, iv = S.calc_iv(P['rm'], P['hf'], P['wf'], P['rc'], P['Rs'],
                               P['cf'], dp, mode=mode, npts=12)
        rows.append((g, iv['Voc'], iv['Jsc'], iv['FF'], iv['Eff']))
    return dp, rows

# Area weights / illum fractions (populated after a solve)
def frac(arr):
    na = S._na
    return float(np.sum(na * arr) / np.sum(na))

gains = [0.0, 0.05, 0.10, 0.20, 0.30]

print("\n=== TANDEM (2T series) ===")
dp, rows = run('tandem', gains)
ilf  = frac(1.0 - S.metal_frac)            # front illuminated fraction (area-wt)
rilf = frac(S.rear_illum_frac)             # rear illuminated fraction (area-wt)
print(f"front illum frac (area-wt) = {ilf:.4f}   rear illum frac = {rilf:.4f}")
print(f"Jph_top = {dp.Jph_top*1e3:.3f}   Jph_bot = {dp.Jph_bot*1e3:.3f}  mA/cm2 (base)")
print(f"{'gain':>6} {'Jph_top_eff':>12} {'Jph_bot_eff':>12} {'limiter':>9} | "
      f"{'Voc':>7} {'Jsc':>7} {'FF':>6} {'Eff':>7}")
for (g, voc, jsc, ff, eff) in rows:
    jt = ilf * dp.Jph_top * 1e3
    jb = (ilf + g * rilf) * dp.Jph_bot * 1e3
    lim = 'TOP' if jt <= jb else 'BOT'
    print(f"{g:>6.2f} {jt:>12.3f} {jb:>12.3f} {lim:>9} | "
          f"{voc:>7.4f} {jsc:>7.3f} {ff:>6.2f} {eff:>7.3f}")

print("\n=== SINGLE-CELL (bifacial contrast) ===")
dp2, rows2 = run('single', gains)
print(f"{'gain':>6} | {'Voc':>7} {'Jsc':>7} {'FF':>6} {'Eff':>7}")
for (g, voc, jsc, ff, eff) in rows2:
    print(f"{g:>6.2f} | {voc:>7.4f} {jsc:>7.3f} {ff:>6.2f} {eff:>7.3f}")

# Summary deltas
e0 = rows[0][4]; e30 = rows[-1][4]
se0 = rows2[0][4]; se30 = rows2[-1][4]
print(f"\nTandem  dEff (gain 0 -> 0.30): {e30 - e0:+.3f} %abs  "
      f"({(e30/e0-1)*100:+.1f}% rel)")
print(f"Single  dEff (gain 0 -> 0.30): {se30 - se0:+.3f} %abs  "
      f"({(se30/se0-1)*100:+.1f}% rel)")
