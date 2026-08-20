"""Count solver calls per evaluation as a function of npts.

Option 3 (2-stage precision) assumes npts 8 -> 5 cuts cost by 5/8.
calc_iv's MPP block uses base_count = max(npts+4, 16), so that assumption
is testable WITHOUT running the real solver: stub solve() with an analytic
diode curve and count the calls. Control flow is what we measure.

Touches nothing in the repo. Solver source read-only (TASK C1).
"""
import importlib.util, math, os, sys

ROOT = r"C:\Users\A\Desktop\2L-FEST"
DRIVER = os.path.join(ROOT, "analysis", "unist_rhoc", "run_unist_rhoc.py")
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError): pass
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location("run_unist_rhoc", DRIVER)
mod = importlib.util.module_from_spec(spec); sys.modules["run_unist_rhoc"] = mod
spec.loader.exec_module(mod)
fest = mod.fest

# Analytic stand-in anchored to the one measured point (Voc 1.9179, Jsc 19.43)
VOC, JSC, NVT = 1.9179160259560426, 19.42966112022392, 0.062
J0 = JSC / (math.exp(VOC / NVT) - 1.0)
COUNT = {"n": 0}

class _R(float):
    pass

def _solve(self, rm, hf, wf, rc, Rs, V, cf=1.0, dp=None, mode='tandem', wb=None):
    COUNT["n"] += 1
    return _R(V)

def _cell_current(self, result, dp=None):
    V = float(result)
    return JSC - J0 * (math.exp(V / NVT) - 1.0)

fest.FESTSolver.solve = _solve
fest.FESTSolver.cell_current = _cell_current

# Build one real solver (mesh gen only, ~1 s) for the cheapest grid point.
cfg = mod.RUNS["B"]
geo = mod.build_geo(45.0, 3.00, cfg["rsheet"], cfg["rho_c_mohm"])
pts, tri, *_ = fest._generate_mesh_for_target(geo, target_nodes=int(mod.MESH_NODE_BUDGET))
isf, isb, isp, ism, isrm, isrp = fest.classify_nodes(pts, geo)
S = fest.FESTSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)
dp = mod.make_dp()
g = geo.front
rm, hf, wf, cf = g.rho_bulk, g.finger_h, g.w_f, g.shape_cf
rc, Rs = g.rho_contact, g.Rs_sheet
print("nodes:", len(pts), flush=True)

res = {}
for npts in (4, 5, 6, 8, 10, 12, 14):
    COUNT["n"] = 0
    err = ""
    try:
        S.calc_iv(rm, hf, wf, rc, Rs, cf, dp, mode="tandem", npts=npts)
    except Exception as e:
        err = "%s: %s" % (type(e).__name__, str(e)[:60])
    res[npts] = (COUNT["n"], err)

base = res[8][0]
print("")
print("%5s %13s %11s" % ("npts", "solve calls", "vs npts=8"))
for npts, (n, err) in res.items():
    ratio = ("%.3f" % (n / base)) if base else "-"
    print("%5d %13d %11s  %s" % (npts, n, ratio, err))
print("")
print("option 3 assumes npts 8 -> 5 costs 5/8 = 0.625 of npts=8")
