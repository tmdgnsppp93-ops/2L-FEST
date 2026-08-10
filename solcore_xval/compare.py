"""Step (3b): 2L-FEST (FEM) vs Solcore Quasi-3D (SPICE) on the SAME single cell.

Drives the real 2L-FEST single-cell solver, rasterizes its exact metal grid into
a Solcore injection/contacts mask, maps the resistance/diode parameters, runs the
Solcore Quasi-3D SPICE solver, and reports an IV/Eff/FF/Pmax comparison + overlay.

    <solcore venv>/bin/python compare.py [pixel_um]
"""
import os, sys, importlib.util, warnings
warnings.filterwarnings("ignore")
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from xval_common import run_quasi3d, iv_metrics

PIX_UM = float(sys.argv[1]) if len(sys.argv) > 1 else 50.0   # pixel size (um)
VSTEP = float(sys.argv[2]) if len(sys.argv) > 2 else 0.005    # bias step (V)
NFING = int(sys.argv[3]) if len(sys.argv) > 3 else 0          # 0 = keep default
WFING = float(sys.argv[4]) if len(sys.argv) > 4 else 0        # finger/busbar width [um]; 0=default
RSVAL = float(sys.argv[5]) if len(sys.argv) > 5 else 0        # front TCO sheet R override [Ohm/sq]; 0=default(55)
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- 2L-FEST side
FEST = os.path.join(os.path.dirname(HERE), "2L_FEST_v28_18_wf_wired.py")
spec = importlib.util.spec_from_file_location("fest", FEST)
m = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(m)
except SystemExit: pass
m.messagebox.showinfo = m.messagebox.showerror = m.messagebox.showwarning = lambda *a, **k: None

app = m.FESTProApp(); app.update_idletasks(); app.update()
app._mode_var.set("single")
if NFING > 0:                                   # realistic multi-finger grid
    app._grid_input_mode_var.set("n_fingers")
    app.tb_hpat[0].delete(0, "end"); app.tb_hpat[0].insert(0, str(NFING))
if WFING > 0:                                   # finger=pixel test: tb_b[2]=finger w, [3]=busbar w (um)
    for _i in (2, 3):
        app.tb_b[_i].delete(0, "end"); app.tb_b[_i].insert(0, f"{WFING:.0f}")
if RSVAL > 0:                                   # diagnostic: override front TCO sheet R (both solvers)
    app._tco_front_entry.delete(0, "end"); app._tco_front_entry.insert(0, f"{RSVAL:g}")
app._apply_grid_design(); app._apply_diode_params()
bp, ap = app._get_params()
rm, hf, wf, wb, cf, rc, rs = bp
S, DP, GEO = m.S, m.DP, m.GEO

Vf, Jf, ivf = S.calc_iv(rm, hf, wf, rc, rs, cf, DP, mode="single", wb=wb)
Vf = np.asarray(Vf); Jf = np.asarray(Jf)
mf = dict(Jsc=ivf["Jsc"], Voc=ivf["Voc"], Pmax=ivf["Pmpp"], FF=ivf["FF"]/100.0)

rects = GEO.metal_rects_front()    # (x,y,w,h) in cm
W, H = GEO.W, GEO.H
print(f"2L-FEST cell {W*10:.1f}x{H*10:.1f} mm, n_f={GEO.n_f}, n_b={GEO.n_b}, "
      f"w_f={GEO.w_f*1e4:.0f}um, w_b={GEO.w_b*1e4:.0f}um, {len(rects)} metal rects")

# ---------------------------------------------------------------- build mask
Lcm = PIX_UM * 1e-4                 # pixel size in cm
nx = int(round(W / Lcm)); ny = int(round(H / Lcm))

# Anti-aliased mask: accumulate exact metal AREA fraction per pixel so optical
# shading is correct regardless of pixel size (binary stamping at 100um turns a
# 50um finger into a full 100um pixel -> 2x over-shading -> ~5% Jsc error).
metal_frac = np.zeros((nx, ny))     # for optical shading (injection)
contacts = np.zeros((nx, ny))       # electrical node type (binary): 150 finger, 255 bus
for (x, y, w, h) in rects:
    is_busbar = w < h                              # busbars are vertical strips
    val = 255 if is_busbar else 150
    i0 = max(0, int(np.floor(x / Lcm))); i1 = min(nx, int(np.ceil((x + w) / Lcm)))
    j0 = max(0, int(np.floor(y / Lcm))); j1 = min(ny, int(np.ceil((y + h) / Lcm)))
    for i in range(i0, i1):
        ox = max(0.0, min((i + 1) * Lcm, x + w) - max(i * Lcm, x))
        for j in range(j0, j1):
            oy = max(0.0, min((j + 1) * Lcm, y + h) - max(j * Lcm, y))
            f = ox * oy / (Lcm * Lcm)
            if f <= 0:
                continue
            metal_frac[i, j] = min(1.0, metal_frac[i, j] + f)
            if f > 0.25:                            # substantial metal -> a node
                contacts[i, j] = max(contacts[i, j], val)
injection = 255.0 * (1.0 - metal_frac)             # fractional (correct areal shading)

shade = float(metal_frac.mean())
term = int((contacts > 200).sum())
print(f"mask {nx}x{ny} px ({PIX_UM:.0f}um), shading(areal)={shade*100:.2f}%, terminal px={term}")

# ---------------------------------------------------------------- Solcore side
# resistance mapping: metal sheet R = bulk resistivity / finger height.
# /cf accounts for 2L-FEST's finger cross-section shape factor (area = w*h*cf),
# so the per-square metal resistance matches between the two solvers.
Rline = rm / (hf * cf)                              # Ohm/sq
Vmax = float(max(Vf.max(), mf["Voc"]) * 1.02)
Vs, Js = run_quasi3d(
    injection, contacts,
    jsc=DP.Jph_single, j01=DP.J01_single_pass, j02=DP.J02_single_pass,
    n1=DP.n1_single, n2=DP.n2_single, Eg=1.12, Rshunt=DP.Rsh_single,
    RsTop=rs, RsBot=1e-3, Rline=Rline, Rcontact=rc,
    Lx=Lcm * 1e-2, Ly=Lcm * 1e-2, vini=0.0, vfin=Vmax, step=VSTEP)
ms = iv_metrics(Vs, Js)

# ---------------------------------------------------------------- report
# unit notes: 2L-FEST iv -> Jsc [mA/cm2], FF [%], Pmpp [mW/cm2].
#             Solcore iv_metrics -> Jsc [A/cm2], FF [frac], Pmax [W/cm2].
print("\n================  2L-FEST (FEM)  vs  Solcore Quasi-3D (SPICE)  ================")
print(f"{'metric':12}{'2L-FEST':>12}{'Solcore':>12}{'diff':>12}{'rel %':>10}")
rows = [("Jsc [mA/cm2]", mf["Jsc"],     ms["Jsc"]*1e3),
        ("Voc [V]",      mf["Voc"],     ms["Voc"]),
        ("FF  [%]",      mf["FF"]*1e2,  ms["FF"]*1e2),
        ("Pmax[mW/cm2]", mf["Pmax"],    ms["Pmax"]*1e3),
        ("Eff [%]",      mf["Pmax"],    ms["Pmax"]*1e3)]
for name, a, b in rows:
    d = b - a; r = 100*d/a if a else float("nan")
    print(f"{name:10}{a:12.3f}{b:12.3f}{d:12.3f}{r:10.2f}")

# overlay plot
plt.figure(figsize=(7,5))
plt.plot(Vf, Jf, "o-", label="2L-FEST (FEM)", color="#C0392B", ms=4)   # Jf already mA/cm2
plt.plot(Vs, Js*1e3, "s--", label="Solcore Quasi-3D (SPICE)", color="#2563EB", ms=3)
plt.xlabel("Voltage [V]"); plt.ylabel("J [mA/cm2]")
plt.title(f"Single cell {W*10:.0f}x{H*10:.0f}mm  |  FEM vs SPICE quasi-3D")
plt.grid(alpha=0.3); plt.legend(); plt.xlim(0, mf["Voc"]*1.05); plt.ylim(0, mf["Jsc"]*1.15*1e3)
plt.tight_layout(); plt.savefig(f"{HERE}/compare_iv.png", dpi=120)
print(f"\nsaved compare_iv.png")

# dump everything needed for the presentation figure
np.savez(f"{HERE}/compare_result.npz",
         Vf=Vf, Jf=Jf, Vs=Vs, Js=Js, contacts=contacts,
         W=W, H=H, n_f=GEO.n_f, n_b=GEO.n_b, w_f=GEO.w_f, w_b=GEO.w_b,
         pix_um=PIX_UM, shade=shade,
         mf_Jsc=mf["Jsc"], mf_Voc=mf["Voc"], mf_FF=mf["FF"], mf_Pmax=mf["Pmax"],
         ms_Jsc=ms["Jsc"], ms_Voc=ms["Voc"], ms_FF=ms["FF"], ms_Pmax=ms["Pmax"],
         rm=rm, hf=hf, wf=wf, rc=rc, rs=rs, Rline=Rline)
print("saved compare_result.npz")
print("COMPARE_DONE")
