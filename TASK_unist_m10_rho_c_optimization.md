# TASK: UNIST TCO Paper — M10 Large-Area Grid Optimization (before/after ρ_c)

**Repo:** `~/dev/2L-FEST` (branch: create `feat/unist-rhoc-runs` from `main`)
**Deliverable:** two optimized M10 efficiencies (before / after TCO modification), plus decomposition and sensitivity runs.
**Execution mode:** run to completion without stopping for confirmation, EXCEPT where a HALT condition below is triggered.

**Data status:** the collaborator has confirmed that parameters they did not supply may be taken from literature or set to reasonable approximate values. This is not a blocked task — missing inputs are handled by documented assumption plus sensitivity analysis, not by waiting.

---

## 0. Hard constraints — read before doing anything

### C1. Solver source is READ-ONLY
The repository is under code freeze for CROS software copyright registration.

- **Do NOT modify** any existing solver, GUI, or physics module.
- All new code goes in a **new file** under `analysis/unist_rhoc/` (create the directory).
- If a solver bug appears to block the task, **HALT and report**. Do not patch it.

### C2. No parameter tuning to make results look good
If a result looks wrong, **report it** — do not adjust inputs until the number improves. The one exception is the Voc anchor in §2, which has an explicit, bounded procedure.

### C3. Provenance tags are mandatory
Every parameter is one of: `MEASURED` (from collaborator), `MEASURED_OURS`, `LITERATURE` (with citation), `ASSUMED`, `DERIVED`. These appear in the results CSV and in the summary's Limitations section.

This matters more here, not less, because most inputs are now literature or assumed. The corresponding author's standard is that measured, assumed, and inferred values are never blended without labels.

---

## 1. Phase 0 — Preflight (do this first, report before proceeding)

1. Confirm branch created from `main`, record `git rev-parse HEAD`.
2. Run the existing test suite. Record pass/xfail counts. If any previously-passing test now fails → **HALT**.
3. **Verify busbar optical handling.** Read the shading / metal-fraction code path and answer explicitly:
   - Are `metal_frac_physical` (J01 weighting, contact area) and `metal_frac_optical` (shading, Jsc) separate quantities?
   - Is metal optical transparency applied to **fingers only**?
   - Can busbars carry an optical shading width (0.20 mm) different from their printed width (0.036 mm)?

   If the code would compute a busbar transparency of `T = 1 − 0.20/0.036 = −4.56`, or forces one width for both roles → **HALT and report**. Do not work around it silently.
4. **Confirm the known silent-wrong bugs are off the optimization path.** Two are on record: `extraction_method` (dead parameter) and `taper` (geometry not wired to resistance/shading). Grep the optimizer call path and report the grep evidence, not just a conclusion.
5. **Time a single M10 run** at the intended mesh density. Report seconds/run and projected wall time for §3. If the projection exceeds 6 hours, thin the Stage-1 grid and report the revised plan.

---

## 2. Inputs

### Fixed across all runs

| Parameter | Value | Tag |
|---|---|---|
| Cell format | M10, 182 × 182 mm | `ASSUMED` (industry standard) |
| Configuration | Monofacial, 2-terminal tandem | `MEASURED` |
| Busbar count | 16 | `ASSUMED` (ITRPV / commercial M10) |
| Busbar printed width | 0.036 mm | `ASSUMED` (commercial datasheet) |
| Busbar optical shading width | 0.20 mm (Cu wire) | `ASSUMED` (ITRPV) |
| Edge margin | 1.0 mm | `ASSUMED` (our prior result) |
| ρ_L (finger + busbar) | 4.22 µΩ·cm | `MEASURED_OURS` |
| Rs_junction | 5000 Ω/sq | `ASSUMED` (Griddler PRO equivalent default) |
| Jph top | 20.36 mA/cm² | `MEASURED` (collaborator EQE, SP Ag) |
| Jph bottom | 20.45 mA/cm² | `MEASURED` (collaborator EQE, SP Ag) |
| Temperature | 25 °C | `ASSUMED` |

**Jph must be byte-identical across Runs A, B, C.** Varying it between conditions would mix optical and contact-resistance effects and invalidate the comparison. Assert this in code.

The tandem is **top-limited** (20.36 < 20.45). Record this in the summary — it affects how sensitive the optimum is to resistive loss.

### Per-run

| Run | ρ_c (mΩ·cm²) | TCO sheet R (Ω/sq) | Purpose |
|---|---|---|---|
| **A** | 1716 | 128 | before TCO modification |
| **B** | 15.32 | 147.1 | after TCO modification |
| **C** | 15.32 | **128** | decomposition |

ρ_c and sheet R are both `MEASURED`.

Run C exists because sheet resistance **increased** after modification (128 → 147.1), so part of the ρ_c gain is cancelled by higher lateral loss. Report the split:

- ρ_c effect alone = η(C) − η(A)
- sheet-R penalty = η(B) − η(C)
- net gain = η(B) − η(A)

### Diode parameters — literature, chosen and cited

Priority order:

1. **Jeon et al., *Solar Energy* 292 (2025)** — the corresponding author's own M10 tandem model. Preferred: easiest to defend in this paper, and already used as a validation reference for this solver.
2. **Zeng et al., *J. Semicond.* 44, 082702 (2023)** — validated two-diode parameter set already present in the repo.

Use (1) if a complete set is available in the repo or the PDF in project files; otherwise (2). **Report which was used and why.** Tag `LITERATURE` with the full citation.

**Voc anchor (the one experimental constraint available):** the collaborator's measured tandem Voc is ≈ **1.94 V** — tag `DERIVED`, since it was read from a figure rather than a numerical table, so tolerance is deliberately loose.

1. With the fixed inputs above, compute tandem Voc at the Run B optimum.
2. If |Voc − 1.94| ≤ 0.05 V → proceed, record the residual.
3. If outside tolerance → adjust **J01_top only**. Do not touch J02, ideality factors, or Rsh; a single Voc value cannot constrain them.
4. Record pre- and post-adjustment J01_top and tag the result `DERIVED (Voc-anchored)`.

---

## 3. Sweep plan

Sweep axes are **finger width** and **finger pitch only**. Busbar count and width are fixed (supervisor directive). CAD import is not applicable — this is a parametric H-pattern.

### Stage 1 — coarse

| Run | finger width (µm) | pitch (mm) |
|---|---|---|
| A | 20, 35, 50, 65, 80 | 0.30, 0.45, 0.60, 0.90, 1.20, 1.80, 2.40, 3.00 |
| B, C | 20, 35, 50, 65, 80 | 0.80, 1.20, 1.60, 2.00, 2.40, 3.00 |

Run A uses an extended pitch range deliberately. Hand estimation puts its optimum near metal coverage fraction `f = w_f/p ≈ 0.14`, which the standard 0.8–3.0 mm range cannot reach (max `f = 0.10` there).

### Stage 2 — refine

Around the Stage-1 argmax, sweep a finer local grid (roughly one coarse step either side, ~5×5). Report both coarse and refined optima.

### Stage 3 — Jph shading sensitivity

The collaborator's EQE may or may not include grid shading from their small-area cell, and the small-cell geometry is not available. If it does include shading, using Jph directly double-counts shading once the M10 grid is applied.

Handle this as a documented sensitivity rather than a blocker:

- **Case α:** Jph as given (assumes EQE was shading-free, e.g. measured between fingers)
- **Case β:** Jph scaled by `1/(1 − 0.05)` → top 21.43, bottom 21.53 mA/cm², assuming 5% shading on a typical lab-scale tandem grid — tag `ASSUMED`

Re-evaluate the three optima under Case β. Then re-run **one coarse sweep for Run B only** under Case β to confirm the optimum location barely moves.

**The expected finding — verify and report it explicitly:** absolute efficiencies shift under Case β, but **Δη(B − A) is nearly unchanged**, because both conditions share the same Jph. This is the argument that the conclusion is robust to the unavailable data. Report Δη for both cases side by side.

### ASSERTIONS — these gate the result

- **A1 (boundary check, critical).** The argmax must not lie on any edge of the swept grid, in either stage. If it does, the result is a boundary value, not an optimum. Automatically extend the offending axis and re-run. Still on a boundary after two extensions → **HALT and report**.
- **A2 (Jph identity).** Assert Jph is identical across A, B, C within a case.
- **A3 (ordering sanity).** Expect η(B) > η(C) > η(A). If this breaks, do not "fix" it — report it with the loss breakdown, since a real physical explanation may exist.
- **A4 (contact-loss dominance).** At the Run B optimum, report contact resistance and TCO lateral resistance referred to cell area. Hand reference: contact ≈ 1.35 Ω·cm², TCO lateral ≈ 0.38 Ω·cm².
- **A5 (loss closure).** Loss breakdown terms sum to total loss within numerical tolerance.
- **A6 (Δη robustness).** |Δη(Case α) − Δη(Case β)| should be small. If it is not, that is a real finding and must be reported prominently, since it would mean the conclusion depends on data we do not have.

### Execution order

Run **B first** — narrower range, physically well-behaved optimum, so it validates the pipeline cheaply. Then A, then C, then Stage 3.

---

## 4. Sanity reference (hand calculation — NOT ground truth)

A linearized series-resistance estimate, each condition at its own optimum:

| Run | approx. optimal `f` | approx. η |
|---|---|---|
| A (before) | ~0.14 | ~25% |
| B (after) | ~0.015 | ~32% |

Order-of-magnitude checks only — they omit diode non-linearity, metallized-area recombination, busbar shading, and edge margin. **If the solver disagrees by more than a few percentage points, the solver is probably right, but say so explicitly rather than silently accepting it.**

---

## 5. Outputs

Write to `analysis/unist_rhoc/out/`.

1. **`sweep_results.csv`** — one row per grid point: run_id, case (α/β), finger_width, pitch, metal_fraction, Jsc, Voc, FF, efficiency, each loss term. Header block records git SHA, timestamp, and the full parameter table with provenance tags.
2. **`summary.md`** — the deliverable:

   | Condition | ρ_c (mΩ·cm²) | R_sheet (Ω/sq) | Optimal finger width | Optimal pitch | Busbars | η |
   |---|---|---|---|---|---|---|

   Plus:
   - Δη decomposition (ρ_c effect / sheet-R penalty / net)
   - Δη for Case α and Case β side by side, with the robustness statement
   - Top-limited note and Voc anchor residual
   - **Limitations** — every `LITERATURE`, `ASSUMED`, and `DERIVED` input, stated plainly, with which conclusions depend on it and which do not
3. **`loss_breakdown.png`** — loss terms at the three optima, side by side.
4. **`heatmap_A.png`, `heatmap_B.png`** — efficiency over the (finger width × pitch) grid, argmax marked, swept boundary drawn so boundary-adjacency is visually checkable.

### Report format when done

In this order: (1) the three efficiencies and the Δη decomposition, (2) the Case α vs β comparison and whether A6 held, (3) assertion pass/fail with any failures named, (4) which literature source was used for diode parameters and the Voc anchor residual.

Recommended framing for the paper, to be stated in `summary.md`: **Δη is the robust quantity; absolute efficiencies carry the literature and shading assumptions.** Lead with Δη.
