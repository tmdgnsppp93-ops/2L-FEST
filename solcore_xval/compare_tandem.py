"""Tandem (2T) cross-validation: 2L-FEST (FEM) vs Solcore Quasi-3D (SPICE/FDM).

Phase-A recombination junction (vertical Rc) — the representation both solvers
share; Solcore's series-junction model has no DOF for Phase-B lateral interlayer.

    /Users/seunghooooonii/Downloads/lfest_env/bin/python compare_tandem.py [pix_um] [vstep] [nfing]
"""
import os, sys, importlib.util, warnings
warnings.filterwarnings("ignore")
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from xval_common import run_quasi3d_tandem, iv_metrics

PIX_UM = float(sys.argv[1]) if len(sys.argv) > 1 else 100.0
VSTEP = float(sys.argv[2]) if len(sys.argv) > 2 else 0.005
NFING = int(sys.argv[3]) if len(sys.argv) > 3 else 10
HERE = os.path.dirname(os.path.abspath(__file__))
EG_TOP, EG_BOT = 1.68, 1.12   # perovskite / Si bandgaps (Solcore ngspice diode; neutral at T=Tnom)

# ---- 2L-FEST tandem (Phase A) ----
FEST = os.path.join(os.path.dirname(HERE), "2L_FEST_v28_18_wf_wired.py")
spec = importlib.util.spec_from_file_location("fest", FEST)
m = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(m)
except SystemExit: pass
m.messagebox.showinfo = m.messagebox.showerror = m.messagebox.showwarning = lambda *a, **k: None

app = m.FESTProApp(); app.update_idletasks(); app.update()
app._mode_var.set("tandem")
app._grid_input_mode_var.set("n_fingers")
app.tb_hpat[0].delete(0, "end"); app.tb_hpat[0].insert(0, str(NFING))
app._apply_grid_design(); app._apply_diode_params()
S, DP, GEO = m.S, m.DP, m.GEO
DP.Rs_junction = 0.0; DP.Rc_junction = 0.0   # force ideal Phase-A vertical junction
bp, ap = app._get_params()
rm, hf, wf, wb, cf, rc, rs = bp

Vf, Jf, ivf = S.calc_iv(rm, hf, wf, rc, rs, cf, DP, mode="tandem", wb=wb)
Vf = np.asarray(Vf); Jf = np.asarray(Jf)
mf = dict(Jsc=ivf["Jsc"], Voc=ivf["Voc"], FF=ivf["FF"]/100.0, Pmax=ivf["Pmpp"])
print(f"2L-FEST tandem: Jsc={mf['Jsc']:.2f} Voc={mf['Voc']:.3f} FF={mf['FF']*100:.1f} Eff={mf['Pmax']:.2f}")

rects = GEO.metal_rects_front(); W, H = GEO.W, GEO.H
print(f"cell {W*10:.0f}x{H*10:.0f}mm n_f={GEO.n_f} w_f={GEO.w_f*1e4:.0f}um")

# ---- mask (same as single-cell harness: anti-aliased injection, binary contacts) ----
Lcm = PIX_UM * 1e-4
nx = int(round(W / Lcm)); ny = int(round(H / Lcm))
metal_frac = np.zeros((nx, ny)); contacts = np.zeros((nx, ny))
for (x, y, w, h) in rects:
    val = 255 if w < h else 150
    i0 = max(0, int(np.floor(x/Lcm))); i1 = min(nx, int(np.ceil((x+w)/Lcm)))
    j0 = max(0, int(np.floor(y/Lcm))); j1 = min(ny, int(np.ceil((y+h)/Lcm)))
    for i in range(i0, i1):
        ox = max(0.0, min((i+1)*Lcm, x+w) - max(i*Lcm, x))
        for j in range(j0, j1):
            oy = max(0.0, min((j+1)*Lcm, y+h) - max(j*Lcm, y))
            f = ox*oy/(Lcm*Lcm)
            if f <= 0: continue
            metal_frac[i, j] = min(1.0, metal_frac[i, j] + f)
            if f > 0.25: contacts[i, j] = max(contacts[i, j], val)
injection = 255.0 * (1.0 - metal_frac)

top = dict(jsc=DP.Jph_top, j01=DP.J01_top_pass, j02=DP.J02_top_pass,
           n1=DP.n1_top, n2=DP.n2_top, Eg=EG_TOP, Rshunt=DP.Rsh_top)
bot = dict(jsc=DP.Jph_bot, j01=DP.J01_bot_pass, j02=DP.J02_bot_pass,
           n1=DP.n1_bot, n2=DP.n2_bot, Eg=EG_BOT, Rshunt=DP.Rsh_bot)
Rline = rm / (hf * cf)
Vmax = float(max(Vf.max(), mf["Voc"]) * 1.03)
Vs, Js = run_quasi3d_tandem(injection, contacts, top=top, bot=bot, Rc_junction=0.0,
                            RsTop_front=rs, RsBot_rear=1e-3, Rline=Rline, Rcontact=rc,
                            Lx=Lcm*1e-2, Ly=Lcm*1e-2, vini=0.0, vfin=Vmax, step=VSTEP)
ms = iv_metrics(Vs, Js)

print("\n========  TANDEM (Phase A):  2L-FEST (FEM)  vs  Solcore Quasi-3D (SPICE/FDM)  ========")
print(f"{'metric':14}{'2L-FEST':>12}{'Solcore':>12}{'abs':>12}{'rel %':>10}")
for name, a, b in [("Jsc [mA/cm2]", mf["Jsc"], ms["Jsc"]*1e3), ("Voc [V]", mf["Voc"], ms["Voc"]),
                   ("FF [%]", mf["FF"]*1e2, ms["FF"]*1e2), ("Eff [%]", mf["Pmax"], ms["Pmax"]*1e3)]:
    print(f"{name:14}{a:12.3f}{b:12.3f}{b-a:12.3f}{100*(b-a)/a if a else 0:10.2f}")

np.savez(f"{HERE}/compare_tandem_result.npz", Vf=Vf, Jf=Jf, Vs=Vs, Js=Js, contacts=contacts,
         W=W, H=H, n_f=GEO.n_f, pix_um=PIX_UM, shade=float(metal_frac.mean()),
         mf_Jsc=mf["Jsc"], mf_Voc=mf["Voc"], mf_FF=mf["FF"], mf_Pmax=mf["Pmax"],
         ms_Jsc=ms["Jsc"], ms_Voc=ms["Voc"], ms_FF=ms["FF"], ms_Pmax=ms["Pmax"])
print("saved compare_tandem_result.npz")
print("TANDEM_DONE")
