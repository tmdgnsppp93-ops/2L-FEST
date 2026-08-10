# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Single-cell FEM vs 0D analytic cross-validation (Griddler-style).

Validation principle (built into the tool): when spatial resistance -> 0, the
distributed FEM single-cell result must converge to the 0D analytic 2-diode
solution using the same diode parameters. Any residual gap at realistic R is the
spatial resistive loss -- the quantity a Griddler-style tool exists to compute.
"""
import importlib.util, numpy as np

spec = importlib.util.spec_from_file_location('fest', '2L_FEST_v28_18_wf_wired.py')
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
except SystemExit:
    pass

S = m.S
dp = m.DiodeParams()
VT = m.VT

# --- 0D single-cell analytic reference (Griddler-compat defaults, no R/shade) ---
Jph = dp.Jph_single; J01 = dp.J01_single_pass; J02 = dp.J02_single_pass
n1 = dp.n1_single; n2 = dp.n2_single; Rsh = dp.Rsh_single
V = np.linspace(0, 0.85, 4000)
J = (Jph
     - J01 * (np.exp(np.minimum(V / (n1 * VT), 80)) - 1)
     - J02 * (np.exp(np.minimum(V / (n2 * VT), 80)) - 1)
     - V / Rsh) * 1000.0  # mA/cm2
pos = np.where(J > 0)[0]
Voc0 = V[pos[-1]]
P = V * J
i = np.argmax(np.where(J > 0, P, -1))
Jsc0, FF0, Eff0 = J[0], P[i] / (J[0] * Voc0) * 100, P[i]
print("=== Griddler-style single-cell validation ===")
print("0D analytic (no spatial R, no shade): "
      f"Jsc={Jsc0:.3f}  Voc={Voc0:.4f}  FF={FF0:.2f}  Eff={Eff0:.3f}")
print()

cases = {
    "FEM near-ideal R": dict(rm=1.6e-6, hf=200e-4, wf=200e-4, rc=1e-5, Rs=1.0, cf=1.0),
    "FEM realistic  R": dict(rm=1.6e-6, hf=10e-4, wf=40e-4, rc=1e-3, Rs=100.0, cf=1.0),
}
for tag, p in cases.items():
    Vs, Js, iv = S.calc_iv(p['rm'], p['hf'], p['wf'], p['rc'], p['Rs'],
                           p['cf'], dp, 'single', npts=12)
    dEff = iv['Eff'] - Eff0
    print(f"{tag}: Jsc={iv['Jsc']:.3f}  Voc={iv['Voc']:.4f}  "
          f"FF={iv['FF']:.2f}  Eff={iv['Eff']:.3f}  (dEff vs 0D = {dEff:+.3f} %abs)")

print()
print("Expected: near-ideal R -> dEff ~ 0 (FEM core validated);")
print("          realistic R  -> dEff < 0 = spatial resistive+shading loss.")
