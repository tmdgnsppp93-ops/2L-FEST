# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""UNIST M10 before/after rho_c — first-pass sweep driver (TASK_FAST, cut scope).

**Solver is READ-ONLY.** This module only *calls* the engine; it adds no physics
and patches nothing. Everything new for this study lives under
``analysis/unist_rhoc/``.

Runs (26 evaluations total)
---------------------------
  B  after   rho_c = 15.32 mOhm.cm2, R_sheet = 147.1 Ohm/sq   12-point sweep
             (run first — cheap pipeline validation)
  A  before  rho_c = 1716  mOhm.cm2, R_sheet = 128   Ohm/sq   12-point sweep
  C  decomp  rho_c = 15.32 mOhm.cm2, R_sheet = 128   Ohm/sq   single evaluation
             at the Run B optimum — NOT re-optimized
  D  sens.   Run B optimum re-evaluated at Rs_junction = 5000 Ohm/sq

Maximum-density re-runs are **dropped** this round. Every evaluation uses an
82,000-node budget and **mesh convergence is pending**.

Usage
-----
    python analysis/unist_rhoc/run_unist_rhoc.py
    python analysis/unist_rhoc/run_unist_rhoc.py --probe      # time one point

Framing: **first pass, coarse grid, 82k-node mesh, for feedback.** Not final.
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, os.path.join(_ROOT, "tests"))
sys.path.insert(0, _ROOT)

import conftest                      # noqa: E402  (headless engine harness)

fest = conftest._load_fest()

OUT_DIR = os.path.join(_HERE, "out")


# ---------------------------------------------------------------------------
# Fixed geometry / optical inputs
# ---------------------------------------------------------------------------
CELL_MM = 182.0
N_BUSBARS = 16
W_BUSBAR_MM = 0.20          # optical shading width, NOT the printed 0.036 mm
EDGE_MARGIN_MM = 1.0
RHO_L_UOHM_CM = 4.22
JPH_TOP = 20.36e-3          # A/cm2  MEASURED (collaborator EQE, SP Ag)
JPH_BOT = 20.45e-3          # A/cm2  MEASURED
N_PROBE_POINTS = 10         # multi-busbar current collection (v28.43 guard)

# Node budget for every evaluation. 82,000 is what scripts/optimize_m10.py
# uses for full-M10 sweeps; the engine's reference ("Max") budget is 138,000.
MESH_NODE_BUDGET = 82000


# ---------------------------------------------------------------------------
# Diode parameters — Jeon et al., Solar Energy 292 (2025) 113426, Table 1
# "Fitted value of each parameter of high-efficiency Si/perovskite tandem solar
#  cell at small area."   Used VERBATIM, not the engine's re-anchored defaults.
#
# The engine docstring warned that these Table 1 values had never been checked
# against the paper. They have now been checked against the paper.
#
# *** UNIT CORRECTION — Is1 / Is2 are A/cm2, not the printed mA/cm2. ***
# The printed table gives mA/cm2. That is a typographical error. Three
# independent checks, all agreeing:
#   1. As A/cm2  -> tandem Voc = 1.935 V, matching the collaborator's measured
#      ~1.94 V almost exactly.
#   2. As mA/cm2 -> tandem Voc = 2.29 V, physically impossible.
#   3. Zeng et al., J. Semicond. 44, 082702 (2023) Table 1 gives a perovskite
#      subcell I01 of 1e-21 A/cm2 — the same order of magnitude as 8.8e-23.
# Ingested as A/cm2. NOT silently converted in either direction: the digits
# below are the printed digits; only the unit reading differs.
#
# Zeng 2023 is NOT used as a parameter source. It served only as check 3.
#
# Table 1 also labels Rsh "top" twice; the second entry (12 kOhm.cm2) is Rsh
# bottom. Read as such — an obvious typo in the paper.
# ---------------------------------------------------------------------------
JEON = dict(
    J01_top=8.8e-23,        # A/cm2  (printed "mA/cm2" — see unit correction)
    J02_top=2.62e-13,       # A/cm2
    n1_top=1.0, n2_top=2.0,
    Rs_vert_top=2.0,        # Ohm.cm2   (Table 1 "Rs top")
    Rsh_top=5550.0,         # Ohm.cm2   (5.55 kOhm.cm2)

    J01_bot=1.3339e-14,     # A/cm2
    J02_bot=6.5674e-19,     # A/cm2
    n1_bot=1.0, n2_bot=2.0,
    Rs_vert_bot=0.2,        # Ohm.cm2   (Table 1 "Rs bot")
    Rsh_bot=12000.0,        # Ohm.cm2   (12 kOhm.cm2 — the mislabelled entry)

    R_ito_sheet=55.0,       # Ohm/sq  — NOT used: per-run measured R_sheet wins
    R_inter_sheet=200.0,    # Ohm/sq  -> Rs_junction
    Iph=19.65e-3,           # A/cm2   — the paper's own photocurrent, both cells
)

DIODE_SET_NOTE = (
    "Jeon et al., Solar Energy 292 (2025) 113426, Table 1, used verbatim. "
    "Is1/Is2 ingested as A/cm2, correcting the printed mA/cm2 (typographical "
    "error; the three-way justification is recorded in the driver source). "
    "Rsh 'top' is printed twice - the second entry, 12 kOhm.cm2, is read as "
    "Rsh bottom. Zeng et al., J. Semicond. 44, 082702 (2023) is NOT a "
    "parameter source here; it served only as an order-of-magnitude "
    "cross-check on the unit correction."
)

# Rs_junction. Jeon Table 1 gives R_inter sheet = 200 Ohm/sq for the same M10
# tandem model, from the corresponding author's own paper — a stronger basis
# than the generic Griddler-equivalent 5000 Ohm/sq the task file carried.
# Run D re-evaluates the Run B optimum at 5000 as a sensitivity check.
RS_JUNCTION = JEON["R_inter_sheet"]
RS_JUNCTION_SENSITIVITY = 5000.0

# Tags: MEASURED | MEASURED_OURS | LITERATURE | ASSUMED | DERIVED
PARAM_TABLE = [
    ("Cell format",            "M10, 182 x 182 mm",     "ASSUMED"),
    ("Configuration",          "Monofacial, 2T tandem", "MEASURED"),
    ("Busbar count",           "16",                    "ASSUMED (ITRPV / commercial M10)"),
    ("Busbar optical shading width", "0.20 mm",         "ASSUMED (Cu wire; printed width 0.036 mm NOT used)"),
    ("Metal optical transparency",   "OFF (T=0)",       "ASSUMED (simplification)"),
    ("Edge margin",            "1.0 mm",                "ASSUMED (our prior result)"),
    ("rho_L (metal bulk)",     "4.22 uOhm.cm",          "MEASURED_OURS"),
    ("Rs_junction",            "200 Ohm/sq",            "LITERATURE (Jeon Table 1 R_inter sheet; 5000 checked in Run D)"),
    ("Jph top",                "20.36 mA/cm2",          "MEASURED (collaborator EQE, SP Ag)"),
    ("Jph bottom",             "20.45 mA/cm2",          "MEASURED (collaborator EQE, SP Ag)"),
    ("Temperature",            "25 degC",               "ASSUMED (engine VT at 298.15 K)"),
    ("Finger height",          "10 um (engine default)", "ASSUMED"),
    ("Finger shape factor",    "0.785 (round)",         "ASSUMED (engine default)"),
    ("Diode parameter set",    "Jeon 2025 Table 1 verbatim", "LITERATURE (units corrected mA->A, justified in source)"),
    ("Metallized-area J0 split", "none (pass = metal)", "LITERATURE (Table 1 gives no split)"),
    ("Rc_junction",            "engine default 0.1 Ohm.cm2", "ASSUMED (Table 1 has no interlayer vertical contact)"),
    ("Mesh node budget",       "82,000 nodes/evaluation", "ASSUMED (= scripts/optimize_m10.py full-M10 default; engine reference budget is 138,000)"),
]

RUNS = {
    "A": dict(rho_c_mohm=1716.0, rsheet=128.0,  label="before (as-deposited TCO)"),
    "B": dict(rho_c_mohm=15.32,  rsheet=147.1,  label="after (modified TCO)"),
    "C": dict(rho_c_mohm=15.32,  rsheet=128.0,  label="decomposition (rho_c of B, R_sheet of A)"),
    "D": dict(rho_c_mohm=15.32,  rsheet=147.1,  label="sensitivity (Rs_junction = 5000)"),
}

# Grids — cut for tonight, 12 points each. Run A keeps the deliberate low-pitch
# range: hand estimation puts its optimum near metal coverage f = w_f/p ~ 0.14,
# which the standard 0.8-3.0 mm range cannot reach.
GRID_A = dict(w_f_um=[20.0, 45.0, 80.0], pitch_mm=[0.35, 0.60, 1.00, 1.60])
GRID_B = dict(w_f_um=[20.0, 45.0, 80.0], pitch_mm=[0.90, 1.40, 2.10, 3.00])

# Hand-calc sanity reference (NOT ground truth).
HAND_REF = {"A": dict(f=0.14, eff=25.0), "B": dict(f=0.015, eff=32.0)}
HAND_REF_RC_OHM_CM2 = 1.35
HAND_REF_TCO_OHM_CM2 = 0.38
VOC_MEASURED = 1.94             # DERIVED - collaborator, read from a figure
VOC_HAND_JEON = 1.935           # DERIVED - hand calc from Jeon Table 1


# ---------------------------------------------------------------------------
# Engine wrappers (no new physics)
# ---------------------------------------------------------------------------
def build_geo(w_f_um, pitch_mm, rsheet, rho_c_mohm):
    """M10 monofacial geometry for one design point.

    Busbar width is the **optical shading width** (0.20 mm), not the printed
    width. Metal optical transparency stays OFF (T=0), so optical width equals
    physical width and the degenerate value 1 - 0.20/0.036 = -4.56 never arises.
    """
    bb_frac = max(0.0, (CELL_MM - 2.0 * EDGE_MARGIN_MM) / CELL_MM)
    front = fest.GridDesign(
        input_mode="finger_spacing",
        finger_spacing_mm=float(pitch_mm),
        n_busbars=N_BUSBARS,
        w_finger=float(w_f_um) * 1e-4,        # um -> cm
        w_busbar=W_BUSBAR_MM * 0.1,           # mm -> cm
        n_probe_points=N_PROBE_POINTS,
        edge_gap=EDGE_MARGIN_MM * 0.1,        # mm -> cm
        busbar_length_frac=bb_frac,
        Rs_sheet=float(rsheet),
        rho_bulk=RHO_L_UOHM_CM * 1e-6,        # uOhm.cm -> Ohm.cm
        rho_contact=float(rho_c_mohm) * 1e-3,  # mOhm.cm2 -> Ohm.cm2
        optical_transparency_f=0.0,
        optical_transparency_b=0.0,
    )
    return fest.CellGeometry(cell_w=CELL_MM * 0.1, cell_h=CELL_MM * 0.1,
                             front=front)


def make_dp(rs_junction=None, jph_top=None, jph_bot=None):
    """Diode parameters — Jeon Table 1 verbatim on top of the engine object.

    Every Table 1 field is set explicitly, so nothing silently falls back to an
    engine default. The engine's own defaults are a *re-anchored derivative* of
    this same table; using them would be a different parameter set wearing the
    same citation.

    **pass == metal.** Jeon gives one J01 and one J02 per subcell, with no
    metallized-area split. Setting pass = metal is the verbatim reading. The
    consequence is real and stated in the summary: there is no under-metal
    recombination enhancement (the engine default carried ~83x for the top
    cell), which slightly favours wider metal coverage than a split model would.

    ``Rc_junction`` is left at the engine default. Jeon's per-subcell "Rc = 0"
    is the subcell contact resistance, a different quantity from the interlayer
    vertical contact; Table 1 does not give the latter.
    """
    dp = fest.DiodeParams()

    dp.Jph_top = JPH_TOP if jph_top is None else jph_top
    dp.Jph_bot = JPH_BOT if jph_bot is None else jph_bot

    dp.J01_top_pass = dp.J01_top_metal = JEON["J01_top"]
    dp.J02_top_pass = dp.J02_top_metal = JEON["J02_top"]
    dp.n1_top, dp.n2_top = JEON["n1_top"], JEON["n2_top"]
    dp.Rsh_top = JEON["Rsh_top"]
    dp.Rs_vert_top = JEON["Rs_vert_top"]

    dp.J01_bot = JEON["J01_bot"]          # property -> sets pass and metal
    dp.J02_bot = JEON["J02_bot"]
    dp.n1_bot, dp.n2_bot = JEON["n1_bot"], JEON["n2_bot"]
    dp.Rsh_bot = JEON["Rsh_bot"]
    dp.Rs_vert_bot = JEON["Rs_vert_bot"]

    dp.Rs_junction = RS_JUNCTION if rs_junction is None else rs_junction
    return dp


def evaluate(w_f_um, pitch_mm, rsheet, rho_c_mohm, mesh="Med", npts=10,
             rs_junction=None, jph_top=None, jph_bot=None):
    """One design point. Returns a flat dict of inputs + results + loss terms."""
    dp = make_dp(rs_junction=rs_junction, jph_top=jph_top, jph_bot=jph_bot)
    # --- Check A2: Jph identity across all runs. Asserted at *every* evaluation,
    #     not once at startup, so a stray mutation cannot slip through. The
    #     single Jeon-Iph anchor point deliberately overrides it and says so.
    if jph_top is None and jph_bot is None:
        assert dp.Jph_top == JPH_TOP, f"Jph_top drifted: {dp.Jph_top}"
        assert dp.Jph_bot == JPH_BOT, f"Jph_bot drifted: {dp.Jph_bot}"

    geo = build_geo(w_f_um, pitch_mm, rsheet, rho_c_mohm)
    # Mesh by **node budget**, not by the per-mm density preset.
    #
    # Measured, not assumed: mesh_tangent/perp="Med" on this M10 geometry
    # (182 mm, 129 fingers, 16 busbars) produces **304,899 nodes** - 2.2x the
    # engine's own "Max"/reference budget of 138,000, and 3.7x the 82,000 that
    # scripts/optimize_m10.py uses for full-M10 sweeps. The presets are a
    # per-millimetre density, so on a large cell "Med" is not medium at all.
    # A ~300k-node nonlinear tandem FEM with a 10-point I-V sweep runs for tens
    # of minutes per design point; the first attempt at this study did not
    # finish one point in 22 minutes.
    #
    # So the node budget is the control, matching what the repository's own M10
    # driver already does. MESH_NODE_BUDGET is reported in the summary in place
    # of a density label - "Med" would have been a misleading thing to print.
    pts, tri, *_ = fest._generate_mesh_for_target(
        geo, target_nodes=int(MESH_NODE_BUDGET))
    isf, isb, isp, ism, isrm, isrp = fest.classify_nodes(pts, geo)
    S = fest.FESTSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)

    g = geo.front
    rm, hf, wf, cf = g.rho_bulk, g.finger_h, g.w_f, g.shape_cf
    rc, Rs = g.rho_contact, g.Rs_sheet

    t0 = time.time()
    Vs, Js, iv = S.calc_iv(rm, hf, wf, rc, Rs, cf, dp, mode="tandem", npts=npts)
    vmpp_bias = iv.get("Vmpp_internal", iv["Vmpp"])
    res = iv.get("_mpp_result") or S.solve(rm, hf, wf, rc, Rs, vmpp_bias, cf,
                                           dp, "tandem")
    L = S.losses(res, rm, hf, wf, rc, Rs, cf, dp,
                 Vmpp=iv["Vmpp"], Jmpp=iv["Jmpp"])
    dt = time.time() - t0

    return {
        "rho_c_mohm_cm2": rho_c_mohm,
        "rsheet_ohm_sq": rsheet,
        "rs_junction_ohm_sq": dp.Rs_junction,
        "jph_top_mA_cm2": dp.Jph_top * 1e3,
        "jph_bot_mA_cm2": dp.Jph_bot * 1e3,
        "mesh_density": f"{len(pts)} nodes (budget {MESH_NODE_BUDGET})",
        "nodes": len(pts),
        "finger_width_um": w_f_um,
        "pitch_mm_requested": pitch_mm,
        "pitch_mm_actual": g.get_finger_pitch_mm(geo.W, geo.H),
        "n_fingers": geo.n_f,
        "metal_fraction": geo.shading_fraction(wf, geo.w_b),
        "Jsc_mA_cm2": iv["Jsc"],
        "Voc_V": iv["Voc"],
        "FF_pct": iv["FF"],
        "efficiency_pct": iv["Eff"],
        "Pmpp_mW_cm2": iv["Pmpp"],
        "P_shade_mW_cm2": L["P_shade"],
        "Pe_emitter_mW_cm2": L["Pe"],
        "Pf_finger_mW_cm2": L["Pf_finger"],
        "Pf_busbar_mW_cm2": L["Pf_busbar"],
        "Pc_contact_mW_cm2": L["Pc"],
        "P_shunt_mW_cm2": L.get("P_shunt", 0.0),
        "P_recomb_mW_cm2": L.get("P_recomb", 0.0),
        "P_Rc_junction_mW_cm2": L.get("P_Rc_junction", 0.0),
        "seconds": dt,
    }


# ---------------------------------------------------------------------------
# Derived reporting quantities (hand-reference comparisons)
# ---------------------------------------------------------------------------
def contact_r_referred(rho_c_mohm, metal_fraction):
    """Contact R referred to CELL area [Ohm.cm2] = rho_c / f_metal."""
    if metal_fraction <= 0:
        return float("nan")
    return (rho_c_mohm * 1e-3) / metal_fraction


def tco_lateral_r_referred(rsheet, pitch_mm):
    """TCO lateral R referred to cell area [Ohm.cm2] = R_sheet * p^2 / 12."""
    p_cm = float(pitch_mm) * 0.1
    return float(rsheet) * p_cm * p_cm / 12.0


# ---------------------------------------------------------------------------
# Sweep + boundary check
# ---------------------------------------------------------------------------
# Sweep, incremental output, wall-clock guard
# ---------------------------------------------------------------------------
CSV_FIELDS = ["run_id", "mesh_density", "nodes", "finger_width_um",
              "pitch_mm_requested", "pitch_mm_actual", "n_fingers",
              "metal_fraction", "rho_c_mohm_cm2", "rsheet_ohm_sq",
              "rs_junction_ohm_sq", "jph_top_mA_cm2", "jph_bot_mA_cm2",
              "Jsc_mA_cm2", "Voc_V", "FF_pct", "efficiency_pct",
              "Pmpp_mW_cm2", "P_shade_mW_cm2", "Pe_emitter_mW_cm2",
              "Pf_finger_mW_cm2", "Pf_busbar_mW_cm2", "Pc_contact_mW_cm2",
              "P_shunt_mW_cm2", "P_recomb_mW_cm2", "P_Rc_junction_mW_cm2",
              "seconds"]

# Nominal evaluation count: 12 (B) + 12 (A) + C + D + V. Boundary extensions
# add up to CAP_EXTRA_POINTS per swept run on top of this.
NOMINAL_EVALS = 12 + 12 + 3
CAP_EXTRA_POINTS = 3          # per run, one extension only (check A1)
WALL_BUDGET_MIN = 100.0       # projected total; over this we stop, not continue


class BudgetExceeded(RuntimeError):
    """Projected wall time over budget. Carries the numbers for the report."""

    def __init__(self, done, elapsed_s, projected_min):
        self.done = done
        self.elapsed_s = elapsed_s
        self.projected_min = projected_min
        super().__init__(
            f"projected {projected_min:.0f} min > {WALL_BUDGET_MIN:.0f} min "
            f"budget after {done} evaluations ({elapsed_s / done:.1f}s each)")


class Recorder:
    """Writes every evaluation to disk **as it returns**, and guards wall time.

    Incremental on purpose: if the process dies at point 20 of 27, the first 19
    must survive. Writing once at the end means a crash costs the whole run —
    which is exactly what happened on the first attempt at this study.

    The wall-clock guard extrapolates from the first ``GUARD_AFTER``
    evaluations. It **stops** rather than continuing quietly, because a job
    that silently overruns its window is worse than one that reports it can't
    fit: the second leaves time to cut scope.
    """

    GUARD_AFTER = 3

    def __init__(self, out_dir, npts):
        self.rows = []
        self.t0 = time.time()
        self.tripped = False
        os.makedirs(out_dir, exist_ok=True)
        self.csv_path = os.path.join(out_dir, "sweep_results.csv")
        self.log_path = os.path.join(out_dir, "progress.log")

        self._fh = open(self.csv_path, "w", encoding="utf-8-sig", newline="")
        self._fh.write("# 2L-FEST UNIST M10 rho_c study - FIRST PASS\n")
        self._fh.write(f"# git: {git_sha()}\n")
        self._fh.write(f"# started: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self._fh.write(f"# calc_iv npts: {npts}   "
                       f"mesh node budget: {MESH_NODE_BUDGET}\n")
        self._fh.write(f"# diode set: {DIODE_SET_NOTE}\n")
        self._fh.write("# run_id: A=before  B=after  C=decomposition  "
                       "D=Rs_junction sensitivity  V=Voc anchor (Jeon Iph)\n")
        self._fh.write("# rows are appended as each evaluation returns - a "
                       "truncated file is a partial run, not a corrupt one\n")
        self._fh.write("# tagged parameters:\n")
        for name, val, tag in PARAM_TABLE:
            self._fh.write(f"#   {name} = {val}  [{tag}]\n")
        self._fh.write("#\n")
        self._w = csv.DictWriter(self._fh, fieldnames=CSV_FIELDS,
                                 extrasaction="ignore")
        self._w.writeheader()
        self._fh.flush()

        self._log = open(self.log_path, "w", encoding="utf-8", newline="")

    def log(self, msg):
        print(msg, flush=True)
        self._log.write(msg + "\n")
        self._log.flush()

    def emit(self, row):
        self.rows.append(row)
        self._w.writerow(row)
        self._fh.flush()
        return row

    def check_budget(self, planned_total=NOMINAL_EVALS):
        """Raise once the projection exceeds the budget. Checked after each eval."""
        n = len(self.rows)
        if self.tripped or n < self.GUARD_AFTER:
            return
        elapsed = time.time() - self.t0
        projected_min = (elapsed / n) * planned_total / 60.0
        if projected_min > WALL_BUDGET_MIN:
            self.tripped = True
            raise BudgetExceeded(n, elapsed, projected_min)
        if n == self.GUARD_AFTER:
            self.log(f"  [budget] {elapsed / n:.1f}s/point -> projected "
                     f"{projected_min:.0f} min for {planned_total} points "
                     f"(budget {WALL_BUDGET_MIN:.0f}) - continuing")

    def close(self):
        try:
            self._fh.close()
            self._log.close()
        except Exception:
            pass


def sweep(run_id, grid, npts, rec, only=None):
    cfg = RUNS[run_id]
    pairs = only if only is not None else [
        (w, p) for w in grid["w_f_um"] for p in grid["pitch_mm"]]
    rows = []
    for i, (w, p) in enumerate(pairs, 1):
        r = evaluate(w, p, cfg["rsheet"], cfg["rho_c_mohm"], npts=npts)
        r["run_id"] = run_id
        rec.emit(r)
        rows.append(r)
        rec.log(f"  [{run_id}] {i}/{len(pairs)}  w_f={w:g}um pitch={p:g}mm "
                f"-> eff={r['efficiency_pct']:.3f}%  Voc={r['Voc_V']:.4f}V  "
                f"FF={r['FF_pct']:.2f}%  ({r['seconds']:.1f}s, "
                f"{r['nodes']} nodes)")
        rec.check_budget()
    return rows


def argmax_row(rows):
    return max(rows, key=lambda r: r["efficiency_pct"])


def boundary_check(best, grid):
    """Check A1. Returns (on_boundary: bool, which_axes: list[str])."""
    axes = []
    ws, ps = sorted(grid["w_f_um"]), sorted(grid["pitch_mm"])
    if best["finger_width_um"] in (ws[0], ws[-1]):
        axes.append(f"finger_width={best['finger_width_um']:g}um "
                    f"(grid {ws[0]:g}-{ws[-1]:g})")
    if best["pitch_mm_requested"] in (ps[0], ps[-1]):
        axes.append(f"pitch={best['pitch_mm_requested']:g}mm "
                    f"(grid {ps[0]:g}-{ps[-1]:g})")
    return bool(axes), axes


def extension_points(grid, best, cap=CAP_EXTRA_POINTS):
    """Up to ``cap`` new points extending whichever axis the argmax sits on.

    **Capped and one-shot.** On a grid this coarse an edge argmax is likely,
    and an uncapped extension turns a bounded job into an open-ended one. If
    the argmax is still on the boundary after this, that is the finding — the
    honest report is "boundary-limited, not an optimum", not a bigger grid.

    Points are generated nearest-first so the cap keeps the most informative
    ones: the step immediately outside the current edge is what decides whether
    the optimum is bracketed.
    """
    ws, ps = sorted(grid["w_f_um"]), sorted(grid["pitch_mm"])
    cand = []
    if best["finger_width_um"] == ws[0]:
        cand += [("w_f_um", round(ws[0] / (1.8 ** k), 4)) for k in (1, 2)]
    elif best["finger_width_um"] == ws[-1]:
        cand += [("w_f_um", round(ws[-1] * (1.6 ** k), 4)) for k in (1, 2)]
    if best["pitch_mm_requested"] == ps[0]:
        cand += [("pitch_mm", round(ps[0] / (1.8 ** k), 4)) for k in (1, 2)]
    elif best["pitch_mm_requested"] == ps[-1]:
        cand += [("pitch_mm", round(ps[-1] * (1.6 ** k), 4)) for k in (1, 2)]

    # Nearest-first across both axes, then cap.
    cand = sorted(cand, key=lambda kv: abs(kv[1] - (
        best["finger_width_um"] if kv[0] == "w_f_um"
        else best["pitch_mm_requested"])))[:cap]

    g = {k: list(v) for k, v in grid.items()}
    pts = []
    for axis, val in cand:
        if val in g[axis]:
            continue
        g[axis] = sorted(g[axis] + [val])
        # hold the other axis at the current best - a full outer product would
        # blow past the cap immediately
        if axis == "w_f_um":
            pts.append((val, best["pitch_mm_requested"]))
        else:
            pts.append((best["finger_width_um"], val))
    return g, pts[:cap]


def git_sha():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, cwd=_ROOT, timeout=10)
        sha = r.stdout.strip() or "unknown"
        d = subprocess.run(["git", "status", "--porcelain"],
                           capture_output=True, text=True, cwd=_ROOT, timeout=10)
        return sha + ("-dirty" if d.stdout.strip() else "")
    except Exception:
        return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--npts", type=int, default=8,
                    help="calc_iv sweep points (default 8 - argmax search does "
                         "not need more)")
    ap.add_argument("--probe", action="store_true",
                    help="time a single evaluation and exit")
    ap.add_argument("--budget-min", type=float, default=WALL_BUDGET_MIN,
                    help="projected wall-clock budget in minutes")
    args = ap.parse_args()
    globals()["WALL_BUDGET_MIN"] = args.budget_min

    os.makedirs(OUT_DIR, exist_ok=True)

    if args.probe:
        t0 = time.time()
        r = evaluate(45.0, 1.40, RUNS["B"]["rsheet"], RUNS["B"]["rho_c_mohm"],
                     npts=args.npts)
        print(json.dumps({k: r[k] for k in
                          ("nodes", "efficiency_pct", "Voc_V", "FF_pct",
                           "Jsc_mA_cm2", "seconds")}, indent=2))
        print(f"TOTAL {time.time() - t0:.1f}s for one point (npts={args.npts}, "
              f"budget {MESH_NODE_BUDGET} nodes)")
        return 0

    rec = Recorder(OUT_DIR, args.npts)
    state = {}
    rec.log("=" * 74)
    rec.log("UNIST M10 rho_c study - FIRST PASS (coarse grid, 82k-node mesh)")
    rec.log(f"git {git_sha()}   npts={args.npts}   "
            f"Rs_junction={RS_JUNCTION:g} Ohm/sq (Jeon Table 1)   "
            f"budget {WALL_BUDGET_MIN:.0f} min")
    rec.log("=" * 74)

    try:
        # --- Deliverables first: B then A. A crash after this still leaves the
        #     two numbers the lab meeting actually needs.
        for run_id, grid in (("B", GRID_B), ("A", GRID_A)):
            cfg = RUNS[run_id]
            rec.log(f"\n### Run {run_id} - {cfg['label']} "
                    f"(rho_c={cfg['rho_c_mohm']} mOhm.cm2, "
                    f"R_sheet={cfg['rsheet']} Ohm/sq)")
            rows = sweep(run_id, grid, args.npts, rec)
            best = argmax_row(rows)
            on_b, axes = boundary_check(best, grid)
            extended = False
            if on_b:
                g2, extra = extension_points(grid, best)
                rec.log(f"  ! A1: argmax on grid boundary ({'; '.join(axes)}) "
                        f"- one extension, {len(extra)} extra points (cap "
                        f"{CAP_EXTRA_POINTS})")
                rows += sweep(run_id, g2, args.npts, rec, only=extra)
                grid, extended = g2, True
                best = argmax_row(rows)
                on_b, axes = boundary_check(best, grid)
                if on_b:
                    rec.log(f"  !! A1 STILL boundary-limited after the capped "
                            f"extension: {'; '.join(axes)} - reporting as "
                            f"boundary-limited, not extending further")
            state[run_id] = dict(rows=rows, best=best, grid=grid, boundary=on_b,
                                 boundary_axes=axes, extended=extended)
            rec.log(f"  -> best: w_f={best['finger_width_um']:g}um "
                    f"pitch={best['pitch_mm_requested']:g}mm "
                    f"eff={best['efficiency_pct']:.3f}% "
                    f"f_metal={best['metal_fraction']:.4f}")

        bB = state["B"]["best"]

        # --- Supporting runs -------------------------------------------------
        rec.log("\n### Run C - single evaluation at the Run B optimum, "
                "R_sheet=128")
        rC = evaluate(bB["finger_width_um"], bB["pitch_mm_requested"],
                      RUNS["C"]["rsheet"], RUNS["C"]["rho_c_mohm"],
                      npts=args.npts)
        rC["run_id"] = "C"
        rec.emit(rC)
        state["C"] = dict(rows=[rC], best=rC, grid=None, boundary=False,
                          boundary_axes=[], extended=False)
        rec.log(f"  -> eff={rC['efficiency_pct']:.3f}%")

        rec.log(f"\n### Run D - Rs_junction sensitivity "
                f"({RS_JUNCTION:g} -> {RS_JUNCTION_SENSITIVITY:g} Ohm/sq) "
                f"at the Run B optimum")
        rD = evaluate(bB["finger_width_um"], bB["pitch_mm_requested"],
                      RUNS["D"]["rsheet"], RUNS["D"]["rho_c_mohm"],
                      npts=args.npts, rs_junction=RS_JUNCTION_SENSITIVITY)
        rD["run_id"] = "D"
        rec.emit(rD)
        state["D"] = dict(rows=[rD], best=rD, grid=None, boundary=False,
                          boundary_axes=[], extended=False)
        rec.log(f"  -> eff={rD['efficiency_pct']:.3f}%  "
                f"(vs {bB['efficiency_pct']:.3f}% at {RS_JUNCTION:g})")

        rec.log(f"\n### Voc anchor - Jeon's own Iph "
                f"({JEON['Iph'] * 1e3:.2f} mA/cm2 both subcells) at the Run B "
                f"optimum")
        rV = evaluate(bB["finger_width_um"], bB["pitch_mm_requested"],
                      RUNS["B"]["rsheet"], RUNS["B"]["rho_c_mohm"],
                      npts=args.npts, jph_top=JEON["Iph"], jph_bot=JEON["Iph"])
        rV["run_id"] = "V"
        rec.emit(rV)
        state["V"] = dict(rows=[rV], best=rV, grid=None, boundary=False,
                          boundary_axes=[], extended=False)
        rec.log(f"  -> Voc={rV['Voc_V']:.4f}V  (hand calc "
                f"{VOC_HAND_JEON:.3f}V, measured {VOC_MEASURED:.2f}V)")

    except BudgetExceeded as exc:
        rec.log("")
        rec.log("!" * 74)
        rec.log(f"STOPPED ON WALL-CLOCK GUARD - {exc}")
        rec.log(f"  measured: {exc.elapsed_s / exc.done:.1f} s/point over "
                f"{exc.done} points")
        rec.log(f"  projected: {exc.projected_min:.0f} min for "
                f"{NOMINAL_EVALS} points (budget {WALL_BUDGET_MIN:.0f} min)")
        rec.log(f"  {len(rec.rows)} evaluations are on disk: {rec.csv_path}")
        rec.log("  nothing further was started. Cut the grid and re-run.")
        rec.log("!" * 74)
        rec.close()
        return 2

    # --- Reports ---------------------------------------------------------
    try:
        import summary
        summary.write(state, args.npts, OUT_DIR, param_table=PARAM_TABLE,
                      diode_note=DIODE_SET_NOTE, git=git_sha(), runs=RUNS,
                      hand_ref=HAND_REF, hand_rc=HAND_REF_RC_OHM_CM2,
                      hand_tco=HAND_REF_TCO_OHM_CM2,
                      voc_measured=VOC_MEASURED, voc_hand=VOC_HAND_JEON,
                      contact_fn=contact_r_referred,
                      tco_fn=tco_lateral_r_referred, jph_top=JPH_TOP,
                      jph_bot=JPH_BOT, jeon=JEON, rs_j=RS_JUNCTION,
                      rs_j_sens=RS_JUNCTION_SENSITIVITY,
                      node_budget=MESH_NODE_BUDGET)
    except Exception:
        import traceback
        traceback.print_exc()
        rec.log("! summary failed - the CSV is complete and on disk")
    try:
        import plots
        plots.make_all(state, OUT_DIR)
    except Exception:
        import traceback
        traceback.print_exc()
        rec.log("! plotting failed - CSV and summary are on disk")

    rec.log(f"\nOutputs in {OUT_DIR}")
    rec.log(f"TOTAL WALL CLOCK {(time.time() - rec.t0) / 60.0:.1f} min "
            f"({len(rec.rows)} evaluations)")
    rec.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
