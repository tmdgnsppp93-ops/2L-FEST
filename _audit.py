# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Headless audit of 2L-FEST computation surface across all modes/paths.
Exercises geometry variants, solver modes, analysis methods, 0D models,
spatial maps, mesh metrics, and report-page rendering. Reports PASS/FAIL.
"""
import importlib.util, numpy as np, traceback
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

spec = importlib.util.spec_from_file_location('fest', '2L_FEST.py')
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
except SystemExit:
    pass

GridDesign=m.GridDesign; CellGeometry=m.CellGeometry; DiodeParams=m.DiodeParams
FESTSolver=m.FESTSolver; SpatialMap=m.SpatialMap

results = []
def record(name, fn):
    try:
        detail = fn()
        results.append((name, "PASS", detail or ""))
    except Exception:
        tb = traceback.format_exc().strip().splitlines()
        results.append((name, "FAIL", tb[-1][:160]))

# small/fast mesh
def make_solver(geo):
    pts, tri = m.generate_mesh(geo, mesh_tangent="Low", mesh_perp="Low")
    isf,isb,isp,ism,isrm,isrp = m.classify_nodes(pts, geo)
    return FESTSolver(pts,tri,isf,isb,isp,ism,geo,isrm,isrp), pts, tri

P = dict(rm=1.6e-6, hf=10e-4, wf=40e-4, wb=50e-4, cf=0.785, rc=1e-3, Rs=55.0)
def quick_iv(S, dp, mode, npts=6):
    Vs,Js,iv = S.calc_iv(P['rm'],P['hf'],P['wf'],P['rc'],P['Rs'],P['cf'],dp,mode=mode,npts=npts,wb=P['wb'])
    assert np.isfinite(iv['Eff']) and iv['Eff']>0, f"bad Eff={iv.get('Eff')}"
    assert iv['Jsc']>0 and iv['Voc']>0, f"bad Jsc={iv['Jsc']} Voc={iv['Voc']}"
    return f"Eff={iv['Eff']:.2f} Jsc={iv['Jsc']:.2f} Voc={iv['Voc']:.3f} FF={iv['FF']:.1f}"

# ---------- A. GEOMETRY / MESH VARIANTS ----------
def geom_case(**kw):
    def _():
        front = kw.get('front') or GridDesign(n_fingers=kw.get('nf',3), n_busbars=kw.get('nb',2))
        rear  = kw.get('rear')
        geo = CellGeometry(cell_w=kw.get('w',0.9),cell_h=kw.get('h',0.9),front=front,rear=rear,
                           wafer_shape=kw.get('shape','square'),chamfer_mm=kw.get('ch',0.0))
        S,pts,tri = make_solver(geo)
        return f"{len(pts)} nodes; " + quick_iv(S, DiodeParams(), 'tandem')
    return _

record("GEOM square 3F+2BB",            geom_case(nf=3,nb=2))
record("GEOM pseudo_square chamfer2mm",  geom_case(shape='pseudo_square',ch=2.0))
record("GEOM circular",                  geom_case(shape='circular'))
record("GEOM finger_spacing mode",
       lambda: (lambda S: quick_iv(S,DiodeParams(),'tandem'))(make_solver(
           CellGeometry(front=GridDesign(input_mode='finger_spacing',finger_spacing_mm=2.0,n_busbars=2)))[0]))
record("GEOM shingled pattern",
       lambda: (lambda S: quick_iv(S,DiodeParams(),'tandem'))(make_solver(
           CellGeometry(front=GridDesign(pattern_style='shingled',n_fingers=4)))[0]))
record("GEOM tapered_h pattern",
       lambda: (lambda S: quick_iv(S,DiodeParams(),'tandem'))(make_solver(
           CellGeometry(front=GridDesign(pattern_style='tapered_h',n_fingers=3,n_busbars=2)))[0]))
record("GEOM bifacial (rear grid)",
       geom_case(rear=GridDesign(n_fingers=3,n_busbars=2)))

# ---------- B. SOLVER MODES (use default global solver S where possible) ----------
S0 = m.S  # default full_area tandem solver
record("MODE tandem full_area",   lambda: quick_iv(S0, DiodeParams(), 'tandem'))
record("MODE single full_area",   lambda: quick_iv(S0, DiodeParams(), 'single'))

def bifacial_solver():
    geo = CellGeometry(front=GridDesign(n_fingers=3,n_busbars=2),
                       rear=GridDesign(n_fingers=3,n_busbars=2))
    return make_solver(geo)[0]
Sb = None
def get_Sb():
    global Sb
    if Sb is None: Sb = bifacial_solver()
    return Sb
record("MODE tandem bifacial",    lambda: quick_iv(get_Sb(), DiodeParams(), 'tandem'))
record("MODE single bifacial",    lambda: quick_iv(get_Sb(), DiodeParams(), 'single'))

def phaseB():
    dp = DiodeParams(); dp.Rs_junction = 200.0   # enable Phase B interlayer
    return quick_iv(S0, dp, 'tandem')
record("MODE Phase B (Rs_junction=200)", phaseB)

def rc_junction():
    dp = DiodeParams(); dp.Rc_junction = 0.2
    return quick_iv(S0, dp, 'tandem')
record("MODE Rc_junction=0.2", rc_junction)

def bifacial_gain_case():
    dp = DiodeParams(); dp.bifacial_gain = 0.2
    return quick_iv(get_Sb(), dp, 'tandem')
record("MODE bifacial_gain=0.2", bifacial_gain_case)

# ---------- C. ANALYSIS METHODS ----------
def analysis():
    dp = DiodeParams()
    Vs,Js,iv = S0.calc_iv(P['rm'],P['hf'],P['wf'],P['rc'],P['Rs'],P['cf'],dp,mode='tandem',npts=6,wb=P['wb'])
    vmpp = iv.get('Vmpp_internal', iv['Vmpp'])
    res = iv.get('_mpp_result') or S0.solve(P['rm'],P['hf'],P['wf'],P['rc'],P['Rs'],vmpp,P['cf'],dp,mode='tandem',wb=P['wb'])
    loss = S0.losses(res,P['rm'],P['hf'],P['wf'],P['rc'],P['Rs'],P['cf'],dp,Vmpp=iv['Vmpp'],Jmpp=iv['Jmpp'],wb=P['wb'])
    rc = S0.recomb_currents(res, dp)
    cm = S0.current_matching_diagnostics(res, dp)
    rs_ext, gsh = FESTSolver.extract_rs_gsh(Vs, Js)
    h = m._iv_health(iv)
    assert all(np.isfinite(v) for v in [loss['Pe'],loss['Pc'],loss['P_shade'],loss['P_recomb']])
    assert all(np.isfinite(v) for v in rc.values())
    return f"loss keys={len(loss)} cm.limiting={cm.get('limiting','?')} Rs_ext={rs_ext:.4f} health={h['status']}"
record("ANALYSIS losses/recomb/cm/rs_gsh/health", analysis)

# ---------- D. 0D MODELS ----------
def zerod():
    dp = DiodeParams()
    Vt,Jt,iv1 = m.solve_0d_tandem_iv(dp, npts=120)
    Vt2,Jt2,iv2 = m.solve_0d_tandem_iv(dp, npts=120, shading_frac=0.05, metal_frac=0.05, j_match=True)
    j = m.solve_0d_subcell_current(0.5, dp, cell='top')
    assert iv1['Eff']>0 and iv2['Eff']>0 and np.isfinite(j)
    return f"0D ideal Eff={iv1['Eff']:.2f} matched Eff={iv2['Eff']:.2f}"
record("0D tandem + subcell", zerod)

# ---------- E. SPATIAL MAPS (all 5 modes) ----------
def spatial(mode):
    def _():
        dp = DiodeParams()
        if mode=='csv':
            sm = SpatialMap(mode='csv', matrix=np.array([[1.0,1.2],[0.8,1.0]]))
        elif mode=='rectangle':
            sm = SpatialMap(mode='rectangle', background=1.0, feature=1.5,
                            x_min=0.2,x_max=0.7,y_min=0.2,y_max=0.7)
        elif mode=='gaussian':
            sm = SpatialMap(mode='gaussian', background=1.0, feature=2.0,
                            cx=0.45,cy=0.45,sigma_x=0.2,sigma_y=0.2)
        elif mode=='checkerboard':
            sm = SpatialMap(mode='checkerboard', background=1.0, feature=1.3, cells_x=4, cells_y=4)
        else:
            sm = SpatialMap(mode='uniform')
        dp.spatial_j01 = sm
        return quick_iv(S0, dp, 'tandem')
    return _
for mode in ('uniform','rectangle','gaussian','checkerboard','csv'):
    record(f"SPATIALMAP {mode} (on J01)", spatial(mode))

# ---------- F. MESH METRICS ----------
def mesh_metrics():
    q = m.mesh_quality_metrics(m.pts, m.tri)
    d = m.mesh_distribution_metrics(m.pts, m.GEO)
    return f"quality keys={list(q)[:3]} dist keys={list(d)[:3]}"
record("MESH quality + distribution metrics", mesh_metrics)

# ---------- G. REPORT PAGES (render all 8 to Agg) ----------
def build_full_cache():
    dp = DiodeParams(); S = S0
    rm,hf,wf,wb,cf,rc,rs = P['rm'],P['hf'],P['wf'],P['wb'],P['cf'],P['rc'],P['Rs']
    bp = (rm,hf,wf,wb,cf,rc,rs); ap = bp
    Vs,Js,iv = S.calc_iv(rm,hf,wf,rc,rs,cf,dp,mode='tandem',npts=6,wb=wb)
    vmpp = iv.get('Vmpp_internal', iv['Vmpp'])
    res = iv.get('_mpp_result') or S.solve(rm,hf,wf,rc,rs,vmpp,cf,dp,mode='tandem',wb=wb)
    loss = S.losses(res,rm,hf,wf,rc,rs,cf,dp,Vmpp=iv['Vmpp'],Jmpp=iv['Jmpp'],wb=wb)
    Rc = S.recomb_currents(res, dp); cm = S.current_matching_diagnostics(res, dp)
    rs_ext, gsh = FESTSolver.extract_rs_gsh(Vs, Js); health = m._iv_health(iv)
    Pff=loss['Pf_finger']; Pfb=loss['Pf_busbar']
    base = dict(bp=bp,ap=ap,mode='tandem',Vs_b=Vs,Js_b=Js,iv_b=iv,Vs_a=Vs,Js_a=Js,iv_a=iv,
        Ve_b=res['Ve'],Vm_b=res['Vm'],Vt_b=res.get('Vtop'),Ve_a=res['Ve'],Vm_a=res['Vm'],Vt_a=res.get('Vtop'),
        Vr_b=res['Vr'],Vr_a=res['Vr'],Vint_b=res.get('Vint'),Vint_a=res.get('Vint'),
        Pe_b=loss['Pe'],Pf_b=Pff+Pfb,Pc_b=loss['Pc'],Ps_b=loss['P_shade'],Psh_b=loss['P_shunt'],
        Prec_b=loss['P_recomb'],Pj_b=loss.get('P_Rc_junction',0.0),
        Pe_a=loss['Pe'],Pf_a=Pff+Pfb,Pc_a=loss['Pc'],Ps_a=loss['P_shade'],Psh_a=loss['P_shunt'],
        Prec_a=loss['P_recomb'],Pj_a=loss.get('P_Rc_junction',0.0),
        Pff_b=Pff,Pfb_b=Pfb,Pff_a=Pff,Pfb_a=Pfb,Rc_b=Rc,Rc_a=Rc,
        Rs_ext_b=rs_ext,Rs_ext_a=rs_ext,Gsh_b=gsh,Gsh_a=gsh,cm_b=cm,cm_a=cm,
        health_b=health,health_a=health)
    return base

_cache_d = None
def render_page(i):
    def _():
        global _cache_d
        if _cache_d is None: _cache_d = build_full_cache()
        fig = Figure(figsize=(11,8.5)); FigureCanvasAgg(fig)
        m._RPT_PAGES[i](fig, _cache_d)
        fig.canvas.draw()
        return f"page {i+1} rendered"
    return _
for i in range(len(m._RPT_PAGES)):
    record(f"REPORT page {i+1}", render_page(i))

# ---------- H. DXF IMPORT (module-level, needs ezdxf) ----------
def dxf_roundtrip():
    import os, tempfile
    try:
        import ezdxf
    except ImportError:
        return "SKIP (ezdxf not installed)"
    path = os.path.join(tempfile.gettempdir(), 'audit_grid.dxf')
    doc = ezdxf.new(); msp = doc.modelspace()
    def rect(layer,x,y,w,h):
        msp.add_lwpolyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],
                           dxfattribs={'layer':layer}, close=True)
    rect('CELL',0,0,9,9); rect('BUSBAR',4.4,0,0.2,9)
    for yy in (2,4,6): rect('FINGER',0,yy,9,0.05)
    doc.saveas(path)
    try:
        g = m.load_dxf_grid(path)
        assert len(g.finger_rects) >= 1 and len(g.busbar_rects) >= 1, "no rects parsed"
        geo = m.CellGeometry()
        m.attach_dxf_to_geometry(geo, g)
        return f"fingers={len(g.finger_rects)} busbars={len(g.busbar_rects)} attach OK"
    finally:
        try: os.remove(path)
        except OSError: pass
record("DXF load + attach_to_geometry", dxf_roundtrip)

# ---------- SUMMARY ----------
print("\n" + "="*78)
n_pass = sum(1 for _,s,_ in results if s=="PASS")
n_fail = len(results)-n_pass
for name,status,detail in results:
    mark = "OK " if status=="PASS" else "XX "
    print(f"  [{mark}] {name:42} {detail}")
print("="*78)
print(f"  TOTAL: {n_pass} PASS / {n_fail} FAIL  (of {len(results)})")
