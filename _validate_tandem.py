"""Tandem 0D <-> FEM cross-validation (built-in validation path).

Per solve_0d_tandem_iv's design: with j_match=True (area-weighted J0 mixing) and
shading_frac matched to the FEM metal coverage, the ONLY remaining difference
between the 0D analytic 2T tandem and the FEM full_area solve is the spatial
(lateral) resistive loss. So:
  - FEM near-ideal R  -> should match the matched-0D (validates the 2T diode core
                         + series coupling + J0 pass/metal mixing)
  - FEM realistic R   -> gap vs matched-0D = spatial resistive loss
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

print("=== Tandem 0D <-> FEM validation (full_area) ===")
cases = {
    "FEM near-ideal R": dict(rm=1.6e-6, hf=200e-4, wf=40e-4, rc=1e-5, Rs=1.0, cf=1.0),
    "FEM realistic  R": dict(rm=1.6e-6, hf=10e-4, wf=40e-4, rc=1e-3, Rs=100.0, cf=1.0),
}
fem = {}
for tag, p in cases.items():
    Vs, Js, iv = S.calc_iv(p['rm'], p['hf'], p['wf'], p['rc'], p['Rs'],
                           p['cf'], dp, 'tandem', npts=12)
    fem[tag] = iv

# Area-weighted front metal coverage (S._na is populated after the solve above)
mf = float(np.sum(S._na * S.metal_frac) / np.sum(S._na))
sf = mf  # optical shading = metal coverage (illum_frac = 1 - metal_frac)
print(f"FEM area-weighted metal_frac = {mf:.4f}  (shading_frac used for 0D match)")
print()

# 0D references
_, _, iv_ideal = m.solve_0d_tandem_iv(dp, npts=400)
_, _, iv_match = m.solve_0d_tandem_iv(dp, npts=400, shading_frac=sf,
                                      metal_frac=mf, j_match=True)
print(f"0D ideal  (no shade/no R, pass J0): Voc={iv_ideal['Voc']:.4f}  "
      f"Jsc={iv_ideal['Jsc']:.3f}  FF={iv_ideal['FF']:.2f}  Eff={iv_ideal['Eff']:.3f}")
print(f"0D matched(shade+J0 mix, no R)    : Voc={iv_match['Voc']:.4f}  "
      f"Jsc={iv_match['Jsc']:.3f}  FF={iv_match['FF']:.2f}  Eff={iv_match['Eff']:.3f}")
print()
for tag in cases:
    iv = fem[tag]
    d = iv['Eff'] - iv_match['Eff']
    print(f"{tag}: Voc={iv['Voc']:.4f}  Jsc={iv['Jsc']:.3f}  FF={iv['FF']:.2f}  "
          f"Eff={iv['Eff']:.3f}  (dEff vs matched-0D = {d:+.3f} %abs)")

print()
print("Expected: near-ideal R -> dEff ~ 0 (2T diode core + coupling validated);")
print("          realistic R  -> dEff < 0 = spatial resistive loss.")
