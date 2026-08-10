# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""M10 (182x182 mm) front-grid resistive loss — finger + busbar — before/after
hot pressing. FAST path: single-cell mode driven at the TANDEM operating current
(grid loss is an I^2R of the front grid -> same whether tandem or single below it),
so we skip the slow tandem Phase-B solve. Reports only Pf_finger / Pf_busbar.

    <solcore venv>/bin/python grid_loss_M10.py [mesh]
"""
import os, sys, importlib.util, warnings, time
warnings.filterwarnings("ignore")
import numpy as np

MESH = sys.argv[1] if len(sys.argv) > 1 else "High"
JPH_TANDEM = 19.65e-3   # A/cm^2 — perovskite/Si tandem operating current (Jph_top)

HERE = os.path.dirname(os.path.abspath(__file__))
FEST = os.path.join(os.path.dirname(HERE), "2L_FEST_v28_18_wf_wired.py")
spec = importlib.util.spec_from_file_location("fest", FEST)
m = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(m)
except SystemExit: pass
m.messagebox.showinfo = m.messagebox.showerror = m.messagebox.showwarning = lambda *a, **k: None

app = m.FESTProApp(); app.update_idletasks(); app.update()
app._mode_var.set("single")
app._mesh_tangent_var.set(MESH); app._mesh_perp_var.set(MESH)
# cell 182x182 mm, 132 fingers, 16 busbars
app.tb_grid[0].delete(0, "end"); app.tb_grid[0].insert(0, "182")
app.tb_grid[1].delete(0, "end"); app.tb_grid[1].insert(0, "182")
app._grid_input_mode_var.set("n_fingers")
app.tb_hpat[0].delete(0, "end"); app.tb_hpat[0].insert(0, "132")
app.tb_hpat[2].delete(0, "end"); app.tb_hpat[2].insert(0, "16")
# probe points per busbar = 12 (current extraction points; affects busbar loss)
app.tb_extract[0].delete(0, "end"); app.tb_extract[0].insert(0, "12")

S = m.S

def set_card(rho_uohmcm, h_um, wf_um, wb_um):
    # tb_b: [0]=bulk rho(uOhm.cm), [1]=finger h(um), [2]=finger w(um), [3]=busbar w(um)
    vals = {0: rho_uohmcm, 1: h_um, 2: wf_um, 3: wb_um}
    for i, v in vals.items():
        app.tb_b[i].delete(0, "end"); app.tb_b[i].insert(0, str(v))

def run_case(name, rho, h, wf, wb):
    set_card(rho, h, wf, wb)
    t0 = time.time()
    ok = app._apply_grid_design()           # builds mesh at MESH level
    app._apply_diode_params()
    m.DP.Jph_single = JPH_TANDEM             # tandem operating current
    nnodes = len(S.pts) if hasattr(S, "pts") else -1
    bp, ap = app._get_params()
    rm, hf, wfc, wbc, cf, rc, rs = bp
    t_mesh = time.time() - t0
    # locate MPP + loss breakdown (single-cell)
    Vs, Js, iv = S.calc_iv(rm, hf, wfc, rc, rs, cf, m.DP, mode="single", wb=wbc, npts=10)
    vmpp = iv.get("Vmpp_internal", iv["Vmpp"])
    res = iv.get("_mpp_result") or S.solve(rm, hf, wfc, rc, rs, vmpp, cf, m.DP, mode="single", wb=wbc)
    loss = S.losses(res, rm, hf, wfc, rc, rs, cf, m.DP, wb=wbc)
    dt = time.time() - t0
    print(f"[{name}] mesh={MESH} nodes={nnodes} (mesh {t_mesh:.0f}s, total {dt:.0f}s)")
    print(f"   rho={rho} uOhmcm, h={h}um, wf={wf}um, wb={wb}um | Jmpp~{iv['Jmpp']:.1f} mA/cm2")
    return dict(Pf=loss["Pf_finger"], Pb=loss["Pf_busbar"])

print(f">>> M10 182x182mm, 132F + 16BB, mesh={MESH}, Jph(tandem)={JPH_TANDEM*1e3:.1f} mA/cm2")
b = run_case("BEFORE", 8.0, 11.0, 55.0, 600.0)
a = run_case("AFTER", 4.22, 9.5, 65.0, 600.0)

print("\n========  M10 front-grid RESISTIVE loss [mW/cm2]  ========")
print(f"{'':10}{'BEFORE':>10}{'AFTER':>10}{'Δ':>10}{'reduction':>12}")
for k, lab in [("Pf", "Finger"), ("Pb", "Busbar")]:
    bb, aa = b[k], a[k]; red = 100*(bb-aa)/bb if bb else 0
    print(f"{lab:10}{bb:10.4f}{aa:10.4f}{aa-bb:+10.4f}{red:11.1f}%")
gb, ga = b["Pf"]+b["Pb"], a["Pf"]+a["Pb"]
print(f"{'TOTAL':10}{gb:10.4f}{ga:10.4f}{ga-gb:+10.4f}{100*(gb-ga)/gb:11.1f}%")
print("GRIDLOSS_DONE")
