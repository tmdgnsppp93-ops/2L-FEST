"""Mesh size vs design point, across the ACTUAL sweep grids. Mesh only, no solve.

Cost per evaluation is driven by node count, and node count on this geometry is
refinement-dominated (finger count), NOT the requested node budget. So map it.
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
mod = importlib.util.module_from_spec(spec); sys.modules["run_unist_rhoc"] = mod
spec.loader.exec_module(mod)

# Reference: 98,433 nodes solved in 1429.8 s at npts=8.
REF_NODES, REF_SEC = 98433, 1429.8

def probe(w_f_um, pitch_mm, cfg):
    geo = mod.build_geo(w_f_um, pitch_mm, cfg["rsheet"], cfg["rho_c_mohm"])
    t0 = time.time()
    pts, tri, n_act, axis = mod.fest._generate_mesh_for_target(
        geo, target_nodes=int(mod.MESH_NODE_BUDGET))
    return dict(w_f_um=w_f_um, pitch_mm=pitch_mm, n_fingers=geo.n_f,
                nodes=len(pts), axis=axis, mesh_s=round(time.time() - t0, 2))

rows = []
for run, grid in (("A", mod.GRID_A), ("B", mod.GRID_B)):
    for w in grid["w_f_um"]:
        for p in grid["pitch_mm"]:
            r = probe(w, p, mod.RUNS[run]); r["run"] = run
            # linear-in-nodes extrapolation from the one measured solve
            r["est_min_linear"] = round(REF_SEC * r["nodes"] / REF_NODES / 60, 1)
            rows.append(r); print(json.dumps(r), flush=True)

print("\n=== MESH COST MAP (node budget requested = %d) ===" % mod.MESH_NODE_BUDGET,
      flush=True)
print(f"{'run':>4} {'w_f um':>7} {'pitch mm':>9} {'fingers':>8} {'nodes':>8} "
      f"{'axis':>5} {'est min':>8}", flush=True)
for r in rows:
    print(f"{r['run']:>4} {r['w_f_um']:>7.0f} {r['pitch_mm']:>9.2f} "
          f"{r['n_fingers']:>8} {r['nodes']:>8} {r['axis']:>5} "
          f"{r['est_min_linear']:>8.1f}", flush=True)

tot = sum(r["est_min_linear"] for r in rows)
print(f"\n24 swept points, linear-in-nodes estimate: {tot:.0f} min "
      f"= {tot/60:.1f} h  (excludes C and D)", flush=True)
print(f"node range: {min(r['nodes'] for r in rows)} .. "
      f"{max(r['nodes'] for r in rows)}", flush=True)
with open(os.path.join(os.environ["CLAUDE_JOB_DIR"], "tmp", "mesh_cost.json"),
          "w", encoding="utf-8") as fh:
    json.dump(dict(ref=dict(nodes=REF_NODES, seconds=REF_SEC), rows=rows), fh, indent=2)
