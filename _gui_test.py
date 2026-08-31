# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Headless-driven GUI smoke test: instantiates the REAL GEDOSApp, patches all
blocking dialogs/messageboxes, and invokes each user-facing handler
programmatically (input parsing, tab rendering, file save/load) — catching
exceptions and verifying outputs. Never enters mainloop.
"""
import importlib.util, os, tempfile, traceback

spec = importlib.util.spec_from_file_location('gedos', 'GEDOS.py')
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
except SystemExit:
    pass

TMP = tempfile.gettempdir()
NEXT = {'save': None, 'open': None}

# --- patch all blocking dialogs/messageboxes ---
m.filedialog.asksaveasfilename = lambda **k: NEXT['save']
m.filedialog.askopenfilename   = lambda **k: NEXT['open']
m.messagebox.showinfo    = lambda *a, **k: None
m.messagebox.showerror   = lambda *a, **k: None
m.messagebox.showwarning = lambda *a, **k: None
m.messagebox.askyesno    = lambda *a, **k: True
try: m.plt.show = lambda *a, **k: None
except Exception: pass

results = []
def record(name, fn):
    try:
        d = fn()
        results.append((name, "PASS", d or ""))
    except Exception:
        tb = traceback.format_exc().strip().splitlines()
        results.append((name, "FAIL", tb[-1][:170]))

# --- build the app ---
app = None
try:
    app = m.GEDOSApp()
    app.update_idletasks(); app.update()
    print("APP_BUILT")
except Exception:
    print("APP BUILD FAILED:\n" + traceback.format_exc())
    raise SystemExit(1)

def pump(n=3):
    for _ in range(n):
        try: app.update_idletasks(); app.update()
        except Exception: pass

# 1) input parsing / apply
record("apply_grid_design", lambda: ("ok" if app._apply_grid_design() else (_ for _ in ()).throw(AssertionError("returned False"))))
record("apply_diode_params", lambda: ("ok" if app._apply_diode_params() else (_ for _ in ()).throw(AssertionError("returned False"))))
pump()

# 2) Compare tab (runs the real simulation, populates cache)
def t_compare():
    app._tab_compare(); pump()
    assert 'iv_b' in app._cache, "cache not populated"
    iv = app._cache['iv_b']
    return f"Eff={iv['Eff']:.2f} Jsc={iv['Jsc']:.2f}"
record("TAB compare (run sim)", t_compare)

# 3) Save CSV  -> verify non-zero file (the bug we fixed)
def t_csv():
    NEXT['save'] = os.path.join(TMP, "gui_test_out.csv")
    if os.path.exists(NEXT['save']): os.remove(NEXT['save'])
    app._save_csv(); pump()
    sz = os.path.getsize(NEXT['save']) if os.path.exists(NEXT['save']) else 0
    assert sz > 0, f"CSV is {sz} bytes"
    # sanity: openable as utf-8
    with open(NEXT['save'], encoding='utf-8-sig') as f:
        head = f.readline().strip()
    return f"{sz} bytes, opens OK, head='{head[:30]}'"
record("SAVE csv (non-zero file)", t_csv)

# 4) Save PNG -> verify file
def t_png():
    NEXT['save'] = os.path.join(TMP, "gui_test_out.png")
    if os.path.exists(NEXT['save']): os.remove(NEXT['save'])
    app._save_png(); pump()
    sz = os.path.getsize(NEXT['save']) if os.path.exists(NEXT['save']) else 0
    assert sz > 0, f"PNG is {sz} bytes"
    return f"{sz} bytes"
record("SAVE png", t_png)

# 5) Other analysis tabs
for tabname in ('_tab_current','_tab_waterfall','_tab_design','_tab_model','_tab_sweep','_tab_contour'):
    def mk(tn):
        def _():
            getattr(app, tn)(); pump()
            return "rendered"
        return _
    record(f"TAB {tabname}", mk(tabname))

# 6) Load experimental I-V CSV
def t_loadexp():
    p = os.path.join(TMP, "gui_test_exp.csv")
    with open(p, 'w', encoding='utf-8') as f:
        f.write("V,J\n0.0,19.5\n0.5,19.0\n1.0,17.0\n1.5,12.0\n1.9,0.0\n")
    NEXT['open'] = p
    app._load_exp(); pump()
    ok = bool(app._exp_data) and ('V_exp' in app._exp_data or len(app._exp_data) > 0)
    os.remove(p)
    assert ok, "exp data not loaded"
    return f"exp keys={list(app._exp_data)[:4]}"
record("LOAD experimental CSV", t_loadexp)

# 7) Load DXF
def t_loaddxf():
    try:
        import ezdxf
    except ImportError:
        return "SKIP (no ezdxf)"
    p = os.path.join(TMP, "gui_test_grid.dxf")
    doc = ezdxf.new(); msp = doc.modelspace()
    def rect(layer,x,y,w,h):
        msp.add_lwpolyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],
                           dxfattribs={'layer':layer}, close=True)
    rect('CELL',0,0,9,9); rect('BUSBAR',4.4,0,0.2,9)
    for yy in (2,4,6): rect('FINGER',0,yy,9,0.05)
    doc.saveas(p)
    NEXT['open'] = p
    app._load_dxf(); pump()
    os.remove(p)
    return f"dxf_loaded={getattr(app,'_dxf_loaded',None)}"
record("LOAD dxf", t_loaddxf)

# 8) Report window build
def t_report():
    app._gen_report(); pump()
    # close any Toplevel report windows it created
    for w in list(app.winfo_children()):
        if isinstance(w, m.ctk.CTkToplevel) or w.winfo_class() == 'Toplevel':
            try: w.destroy()
            except Exception: pass
    return "report window built"
record("REPORT window (_gen_report)", t_report)

# --- teardown ---
try: app.destroy()
except Exception: pass

print("\n" + "="*78)
n_pass = sum(1 for _,s,_ in results if s=="PASS")
for name,status,detail in results:
    print(f"  [{'OK ' if status=='PASS' else 'XX '}] {name:34} {detail}")
print("="*78)
print(f"  GUI TOTAL: {n_pass} PASS / {len(results)-n_pass} FAIL  (of {len(results)})")
