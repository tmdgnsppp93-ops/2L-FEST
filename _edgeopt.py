import os, sys
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
import matplotlib; matplotlib.use("Agg", force=True); matplotlib.use=lambda *a,**k:None
_H=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,os.path.join(_H,"tests")); sys.path.insert(0,_H)
import conftest; gedos=conftest._load_gedos()
from front_electrode import optimize_grid, apply_recovery, SCENARIO_MEASURED
import csv
pitches=[1.8,2.2,2.6]; nbbs=[6,8,10]; REC=0.25
rows=[]
print("### edge_margin 0 vs 1.0mm 최적점 이동 (cell182 wf20 wbb0.20 rec0.25, pitch1.8~2.6×nbb6/8/10) ###", flush=True)
print(f"  {'edge':>5} {'opt_nbb':>8} {'opt_pitch':>10} {'eff[%]':>8}", flush=True)
for edge in (0.0, 1.0):
    opt=optimize_grid(gedos, cell_mm=182.0, finger_widths_um=[20.0], finger_pitches_mm=pitches,
        n_busbars_list=nbbs, busbar_widths_mm=[0.20], edge_margin_mm=edge,
        scenario=SCENARIO_MEASURED, recovery_factor=0.0, objective="efficiency",
        axis_segments_override=40, npts=6)
    # recovery 0.25 사후 반영
    for r in opt["results"]:
        r["results"].update(apply_recovery(r, REC))
    best=max(opt["results"], key=lambda r:r["results"]["efficiency"])
    bp=best["parameters"]
    print(f"  {edge:>5.1f} {bp['busbar_number']:>8} {bp['finger_pitch_mm']:>10.2f} {best['results']['efficiency']:>8.3f}", flush=True)
    for r in opt["results"]:
        p=r["parameters"]
        rows.append(dict(edge_margin_mm=edge, busbar_number=p['busbar_number'],
            finger_pitch_mm=round(p['finger_pitch_mm'],3), n_fingers=p['n_fingers'],
            efficiency=round(r['results']['efficiency'],4)))
# 상세 그리드
print("\n  nbb별 최고 eff:", flush=True)
for edge in (0.0,1.0):
    line=f"  edge={edge}: "
    for nb in nbbs:
        sub=[x for x in rows if x['edge_margin_mm']==edge and x['busbar_number']==nb]
        b=max(sub,key=lambda x:x['efficiency'])
        line+=f"nbb{nb}({b['finger_pitch_mm']:.2f}):{b['efficiency']:.3f}  "
    print(line, flush=True)
with open("_edgeopt_results.csv","w",newline="",encoding="utf-8-sig") as fh:
    w=csv.DictWriter(fh,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("\n  CSV: _edgeopt_results.csv", flush=True)
