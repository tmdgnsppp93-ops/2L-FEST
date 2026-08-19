"""Mesh convergence probe: same design point, varying node budget.

Does NOT modify the repo or the solver. Imports the existing driver and
overrides only MESH_NODE_BUDGET, then re-evaluates the identical point.

Reference already measured at budget 82000 -> 98433 nodes, 1429.8 s:
    eff 30.734126%  Voc 1.9179160 V  FF 82.475709%  Jsc 19.429661 mA/cm2
"""
import importlib.util, json, os, sys, time

ROOT = r"C:\Users\A\Desktop\2L-FEST"
DRIVER = os.path.join(ROOT, "analysis", "unist_rhoc", "run_unist_rhoc.py")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

os.chdir(ROOT)
spec = importlib.util.spec_from_file_location("run_unist_rhoc", DRIVER)
mod = importlib.util.module_from_spec(spec)
sys.modules["run_unist_rhoc"] = mod
spec.loader.exec_module(mod)

W_F, PITCH = 45.0, 1.40           # identical to the --probe point (Run B centre)
REF = dict(nodes=98433, eff=30.734126256223647, Voc=1.9179160259560426,
           FF=82.47570887036262, Jsc=19.42966112022392, seconds=1429.8)

rows = []
for budget in (20000, 40000):
    mod.MESH_NODE_BUDGET = budget
    t0 = time.time()
    r = mod.evaluate(W_F, PITCH, mod.RUNS["B"]["rsheet"],
                     mod.RUNS["B"]["rho_c_mohm"], npts=8)
    wall = time.time() - t0
    row = dict(budget=budget, nodes=r["nodes"], seconds=round(wall, 1),
               eff=r["efficiency_pct"], Voc=r["Voc_V"], FF=r["FF_pct"],
               Jsc=r["Jsc_mA_cm2"],
               d_eff_abs_pp=r["efficiency_pct"] - REF["eff"],
               speedup=round(REF["seconds"] / wall, 2))
    rows.append(row)
    print(json.dumps(row, indent=2), flush=True)

print("\n=== MESH CONVERGENCE (design point 45 um / 1.40 mm, Run B) ===",
      flush=True)
print(f"{'budget':>8} {'nodes':>8} {'sec':>8} {'eff %':>10} {'d_eff pp':>10} "
      f"{'Voc V':>9} {'FF %':>8} {'speedup':>8}", flush=True)
for r in rows:
    print(f"{r['budget']:>8} {r['nodes']:>8} {r['seconds']:>8.1f} "
          f"{r['eff']:>10.4f} {r['d_eff_abs_pp']:>+10.4f} {r['Voc']:>9.4f} "
          f"{r['FF']:>8.4f} {r['speedup']:>8.2f}x", flush=True)
print(f"{REF['nodes']:>8} {REF['nodes']:>8} {REF['seconds']:>8.1f} "
      f"{REF['eff']:>10.4f} {0.0:>+10.4f} {REF['Voc']:>9.4f} "
      f"{REF['FF']:>8.4f} {1.0:>8.2f}x   <- reference (budget 82000)",
      flush=True)

with open(os.path.join(os.environ["CLAUDE_JOB_DIR"], "tmp",
                       "mesh_conv.json"), "w", encoding="utf-8") as fh:
    json.dump(dict(design_point=dict(w_f_um=W_F, pitch_mm=PITCH, run="B"),
                   reference=REF, rows=rows), fh, indent=2)
