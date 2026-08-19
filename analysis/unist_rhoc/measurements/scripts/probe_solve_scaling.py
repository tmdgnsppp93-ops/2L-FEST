"""Solve-time scaling vs node count. Two more real Run B grid points.

We have exactly ONE measured solve (98,433 nodes, 1429.8 s). Every wall-time
projection so far assumes cost is LINEAR in nodes. That assumption decides
whether this study is feasible at all, so measure it instead of assuming it.

Both points are genuine GRID_B points (w_f=45), so the results are keepable.
"""
import importlib.util, json, math, os, sys, time

ROOT = r"C:\Users\A\Desktop\2L-FEST"
DRIVER = os.path.join(ROOT, "analysis", "unist_rhoc", "run_unist_rhoc.py")
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location("run_unist_rhoc", DRIVER)
mod = importlib.util.module_from_spec(spec); sys.modules["run_unist_rhoc"] = mod
spec.loader.exec_module(mod)

REF = dict(nodes=98433, seconds=1429.8, pitch=1.40, eff=30.734126256223647)
pts = [(45.0, 3.00), (45.0, 0.90)]      # 81,869 and 147,725 nodes
rows = [dict(w_f_um=45.0, pitch_mm=REF["pitch"], nodes=REF["nodes"],
             seconds=REF["seconds"], eff=REF["eff"], measured="earlier")]

for w, p in pts:
    t0 = time.time()
    r = mod.evaluate(w, p, mod.RUNS["B"]["rsheet"], mod.RUNS["B"]["rho_c_mohm"],
                     npts=8)
    row = dict(w_f_um=w, pitch_mm=p, nodes=r["nodes"],
               seconds=round(time.time() - t0, 1), eff=r["efficiency_pct"],
               Voc=r["Voc_V"], FF=r["FF_pct"], Jsc=r["Jsc_mA_cm2"],
               n_fingers=r["n_fingers"], metal_fraction=r["metal_fraction"],
               measured="now")
    rows.append(row); print(json.dumps(row, indent=2), flush=True)

print("\n=== SOLVE-TIME SCALING (Run B, w_f=45 um, npts=8) ===", flush=True)
print(f"{'pitch mm':>9} {'nodes':>8} {'sec':>9} {'min':>7} {'eff %':>9}", flush=True)
for r in sorted(rows, key=lambda x: x["nodes"]):
    print(f"{r['pitch_mm']:>9.2f} {r['nodes']:>8} {r['seconds']:>9.1f} "
          f"{r['seconds']/60:>7.1f} {r['eff']:>9.4f}", flush=True)

s = sorted(rows, key=lambda x: x["nodes"])
print("\nlocal exponent p in  t ~ N^p :", flush=True)
for a, b in zip(s, s[1:]):
    p_exp = math.log(b["seconds"]/a["seconds"]) / math.log(b["nodes"]/a["nodes"])
    print(f"  {a['nodes']:>7} -> {b['nodes']:>7} :  p = {p_exp:+.2f}", flush=True)
p_all = math.log(s[-1]["seconds"]/s[0]["seconds"]) / math.log(s[-1]["nodes"]/s[0]["nodes"])
print(f"  overall {s[0]['nodes']} -> {s[-1]['nodes']} :  p = {p_all:+.2f}", flush=True)
t_ref, n_ref = s[-1]["seconds"], s[-1]["nodes"]
for N in (117535, 147725, 216899, 365085):
    print(f"  extrapolated {N:>7} nodes: {t_ref*(N/n_ref)**p_all/60:>7.1f} min "
          f"(linear would say {t_ref*(N/n_ref)/60:.1f})", flush=True)
with open(os.path.join(os.environ["CLAUDE_JOB_DIR"], "tmp", "scaling.json"),
          "w", encoding="utf-8") as fh:
    json.dump(dict(rows=rows, exponent=p_all), fh, indent=2)
