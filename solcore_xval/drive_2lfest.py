# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Step (3a): drive 2L-FEST single-cell solver headlessly, dump IV + geometry.

Goal: get (V, J) curve + metrics from the REAL 2L-FEST FEM solver for the
default single cell, and discover the exact geometry attributes we need to
build a matching Solcore mask in step (3b).

    <solcore venv>/bin/python drive_2lfest.py
"""
import os, importlib.util, warnings, json
warnings.filterwarnings("ignore")
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FEST = os.path.join(os.path.dirname(HERE), "2L_FEST_v28_18_wf_wired.py")
spec = importlib.util.spec_from_file_location("fest", FEST)
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
except SystemExit:
    pass

# silence dialogs in case anything pops
m.messagebox.showinfo = lambda *a, **k: None
m.messagebox.showerror = lambda *a, **k: None
m.messagebox.showwarning = lambda *a, **k: None

app = m.FESTProApp()
app.update_idletasks(); app.update()
print("APP_BUILT", m.__build__["version"])

# --- single-cell mode ---
app._mode_var.set("single")
ok1 = app._apply_grid_design()
ok2 = app._apply_diode_params()
print("apply_grid_design:", ok1, " apply_diode_params:", ok2)

bp, ap = app._get_params()
print("base params (rm,hf,wf,wb,cf,rc,rs):", bp)
rm, hf, wf, wb, cf, rc, rs = bp

S = m.S; DP = m.DP
Vs, Js, iv = S.calc_iv(rm, hf, wf, rc, rs, cf, DP, mode="single", wb=wb)
Vs = np.asarray(Vs); Js = np.asarray(Js)

print("\n=== 2L-FEST single-cell IV metrics ===")
for k in ("Jsc", "Voc", "Vmpp", "Jmpp", "Pmpp", "FF", "Eff"):
    print(f"  {k:6} = {iv.get(k)}")
print(f"  IV curve pts: {len(Vs)}  V[0..-1]={Vs.min():.3f}..{Vs.max():.3f}")

# --- geometry discovery: probe S and module globals for the grid layout ---
print("\n=== geometry probe ===")
GEO = getattr(m, "GEO", None)
print("  module GEO:", type(GEO).__name__ if GEO is not None else None)
for obj_name, obj in [("GEO", GEO), ("S", S)]:
    if obj is None:
        continue
    attrs = {}
    for a in ("W", "H", "n_fingers", "n_busbars", "N_fingers", "N_busbars",
              "w_finger", "w_busbar", "wf", "wb", "finger_spacing", "pad",
              "pad_cx", "pad_cy", "cell_w", "cell_h"):
        if hasattr(obj, a):
            try:
                v = getattr(obj, a)
                if isinstance(v, (int, float, str)):
                    attrs[a] = v
            except Exception:
                pass
    print(f"  {obj_name} attrs:", attrs)

# dump IV curve to npz for step 3b
np.savez(os.path.join(HERE, "fest_single.npz"),
         V=Vs, J=Js, **{k: float(iv[k]) for k in ("Jsc","Voc","Vmpp","Jmpp","Pmpp","FF","Eff") if k in iv})
print("\nsaved fest_single.npz")
print("DRIVE_DONE")
