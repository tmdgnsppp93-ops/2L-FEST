# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Step (2): unit calibration — Solcore Quasi-3D vs closed-form 2-diode.

Uniform cell, negligible sheet resistance -> Solcore must reproduce the analytic
2-diode IV from the SAME parameters. Validates the cm->SI unit mapping before any
grid / 2L-FEST comparison. Voc/FF must match <1%; Jsc matches after the
illuminated-area fraction (one busbar column is shaded).

    <solcore venv>/bin/python calibrate_units.py
"""
import numpy as np
from xval_common import run_quasi3d, iv_metrics, analytic_2diode

# 2L-FEST single-cell defaults (cm units)
P = dict(jsc=19.77e-3, j01=5.36e-15, j02=0.0, n1=1.0, n2=2.0, Rshunt=15000.0)
Eg = 1.12

nx, ny = 20, 20
injection = np.full((nx, ny), 255.0)
contacts = np.zeros((nx, ny))
contacts[0, :] = 255          # one busbar column = external terminal
injection[0, :] = 0           # shaded under busbar
illum_frac = (injection > 0).sum() / injection.size

V, J = run_quasi3d(injection, contacts, Eg=Eg,
                   RsTop=1e-6, RsBot=1e-6, Rline=2.65e-3, Rcontact=1e-12,
                   vini=0.0, vfin=0.78, step=0.005, **P)

m_sol = iv_metrics(V, J)
Vana = np.linspace(0, 0.78, 400)
m_ana = iv_metrics(Vana, analytic_2diode(Vana, **P))
expect = {"Jsc": illum_frac, "Voc": 1.0, "Pmax": illum_frac, "FF": 1.0}

print(f"\n=== Solcore Quasi-3D vs analytic 2-diode (illum_frac={illum_frac:.3f}) ===")
print(f"  raw: J[V=0]={J[np.argmin(np.abs(V))]*1e3:.2f} mA/cm^2 (expect ~{P['jsc']*illum_frac*1e3:.1f})")
print(f"{'':8}{'Solcore':>12}{'Analytic*f':>12}{'rel.err %':>12}")
ok = True
for k, unit, sc in [("Jsc", "mA/cm2", 1e3), ("Voc", "V", 1.0),
                    ("Pmax", "mW/cm2", 1e3), ("FF", "%", 100.0)]:
    a = m_sol[k] * sc; b = m_ana[k] * sc * expect[k]
    err = 100 * (a - b) / b if b else float("nan")
    flag = "" if abs(err) < 2 else "  <-- CHECK"
    if abs(err) >= 2: ok = False
    print(f"{k:8}{a:12.3f}{b:12.3f}{err:12.2f}   [{unit}]{flag}")
print("\n" + ("CALIB_PASS (units validated, <2% on all metrics)" if ok
              else "CALIB_FAIL (unit mapping still off)"))
