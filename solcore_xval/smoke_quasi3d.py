"""Smoke test: confirm Solcore Quasi-3D + ngspice pipeline runs and yields a sane IV.

Run with the lfest_env interpreter:
    <solcore venv>/bin/python smoke_quasi3d.py

Goal: NOT a quantitative match yet — just verify (a) ngspice is found,
(b) solve_quasi_3D returns a V,I curve, (c) Voc/Jsc/FF are physically sane
for a c-Si-like single junction. Unit calibration comes next.
"""
import os
# Solcore reads the ngspice path from SOLCORE_SPICE at import time — set it FIRST.
os.environ.setdefault("SOLCORE_SPICE", "/opt/homebrew/bin/ngspice")
import warnings
warnings.filterwarnings("ignore")
import numpy as np
from solcore.structure import Junction
from solcore.solar_cell import SolarCell
from solcore.spice.quasi_3D_solver import solve_quasi_3D

# ---- 2L-FEST single-cell defaults, converted to SI (A/m^2, Ohm*m^2) ----
# 2L-FEST: Jph_single=19.77 mA/cm^2, J01_single=5.36e-15 A/cm^2, n1=1,
#          J02=0, n2=2, Rsh_single=15000 Ohm*cm^2, Voc~0.748 V (c-Si like)
CM2_PER_M2 = 1e4
jsc = 19.77e-3 * CM2_PER_M2      # A/cm^2 -> A/m^2  = 197.7
j01 = 5.36e-15 * CM2_PER_M2      # A/cm^2 -> A/m^2
j02 = 1e-30                       # ~0 (avoid exactly 0); 2L-FEST single J02=0
Rsh = 15000.0 / CM2_PER_M2        # Ohm*cm^2 -> Ohm*m^2  = 1.5

jx = Junction(kind="2D", n1=1.0, n2=2.0, j01=j01, j02=j02, R_shunt=Rsh, jsc=jsc)
# attributes the quasi-3D solver reads directly:
jx.jsc = jsc
jx.j01 = j01
jx.j02 = j02
jx.Eg = 1.12              # c-Si bandgap (eV) for the SPICE diode 'eg'
jx.n1 = 1.0
jx.n2 = 2.0
jx.R_shunt = Rsh
jx.R_sheet_top = 55.0     # Ohm/sq (2L-FEST TCO default)
jx.R_sheet_bot = 1e-3     # near-ideal back

cell = SolarCell([jx])

# ---- small grid: 40x40 pixels, 10um each -> 0.4mm x 0.4mm patch ----
nx, ny = 40, 40
injection = np.ones((nx, ny))          # fully illuminated
contacts = np.zeros((nx, ny))          # electrical contact mask (metal)
# two vertical metal fingers (busbar-like) at columns 0 and 39
contacts[0, :] = 255
contacts[-1, :] = 255
# under metal -> not illuminated
injection[0, :] = 0
injection[-1, :] = 0

print(">> running solve_quasi_3D ...")
V, I, Vall, Vmet = solve_quasi_3D(
    cell, injection, contacts,
    Lx=10e-6, Ly=10e-6, h=10e-6,        # pixel 10um, finger height 10um
    R_back=1e-16, R_contact=1e-16, R_line=2.65e-8,  # Ag resistivity ~2.65e-8 Ohm*m
    bias_start=0.0, bias_end=0.75, bias_step=0.01,
)

V = np.asarray(V); I = np.asarray(I)
# I is total current over the patch area (A). Convert to density per cm^2.
area_cm2 = (nx * 10e-6) * (ny * 10e-6) * CM2_PER_M2   # m^2 -> cm^2
J = I / area_cm2                                       # A/cm^2

# IV metrics (I sign: photocurrent positive-generating; find power quadrant)
P = V * J
# take the quadrant where P is positive (generation)
idx = np.argmax(P) if np.max(P) > 0 else np.argmin(P)
Pmax = P[idx]
Voc = np.interp(0.0, J[np.argsort(J)], V[np.argsort(J)]) if (J.min() < 0 < J.max()) else float("nan")
Jsc = np.interp(0.0, V, J)
FF = abs(Pmax) / (abs(Voc) * abs(Jsc)) if Voc and Jsc else float("nan")

print(f"   V range: {V.min():.3f}..{V.max():.3f} V, {len(V)} pts")
print(f"   Jsc  ~ {Jsc*1e3:.2f} mA/cm^2  (expect ~19.8)")
print(f"   Voc  ~ {Voc:.4f} V          (expect ~0.74)")
print(f"   Pmax ~ {abs(Pmax)*1e3:.2f} mW/cm^2")
print(f"   FF   ~ {FF*100:.1f} %         (expect ~80)")
print("SMOKE_OK")
