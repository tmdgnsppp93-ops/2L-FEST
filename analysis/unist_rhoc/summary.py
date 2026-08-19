# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""summary.md writer for the UNIST M10 rho_c first-pass study.

Kept separate from the driver so the numbers and the prose that frames them are
edited independently. Everything here is formatting — no physics.
"""
import os
import time


def _f(x, n=3):
    try:
        return f"{float(x):.{n}f}"
    except (TypeError, ValueError):
        return "n/a"


def write(state, npts, out_dir, *, param_table, diode_note, git, runs,
          hand_ref, hand_rc, hand_tco, voc_measured, voc_hand, contact_fn,
          tco_fn, jph_top, jph_bot, jeon, rs_j, rs_j_sens, node_budget):
    bA, bB = state["A"]["best"], state["B"]["best"]
    rC, rD, rV = state["C"]["best"], state["D"]["best"], state["V"]["best"]

    etaA, etaB, etaC = bA["efficiency_pct"], bB["efficiency_pct"], rC["efficiency_pct"]
    d_rhoc = etaC - etaA
    d_sheet = etaB - etaC
    d_net = etaB - etaA

    rc_ref = contact_fn(runs["B"]["rho_c_mohm"], bB["metal_fraction"])
    tco_ref = tco_fn(runs["B"]["rsheet"], bB["pitch_mm_actual"])

    L = []
    a = L.append
    a("# UNIST M10 — before/after ρ_c, first-pass numbers")
    a("")
    a("> **FIRST PASS — coarse grid, single mesh resolution, for feedback.**")
    a("> Not final results. **Mesh convergence is pending** — the higher-density")
    a("> re-runs were dropped to fit tonight's window. Every caveat in §7 applies")
    a("> to every number here.")
    a("")
    a(f"- generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    a(f"- engine commit: `{git}`")
    a(f"- `calc_iv` sweep points: {npts}; mesh: **{node_budget:,}-node budget** "
      f"per evaluation")
    a("")
    a("> Mesh is reported as a **node count**, not a density preset name. On "
      "this M10 geometry the engine's `Med` preset yields 304,899 nodes - "
      "2.2x the engine's own reference budget (138,000) and 3.7x what "
      "`scripts/optimize_m10.py` uses for full-M10 sweeps (82,000). The "
      "presets are a per-millimetre density, so on a 182 mm cell \"Med\" is "
      "not medium. Printing a preset name here would have been misleading.")
    a("")
    a("---")
    a("")
    a("## 1. Results")
    a("")
    a("| Condition | ρ_c (mΩ·cm²) | R_sheet (Ω/sq) | Optimal w_f (µm) | "
      "Optimal pitch (mm) | Busbars | f_metal | η (%) |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|")
    for rid, r in (("A", bA), ("B", bB)):
        a(f"| **{rid}** — {runs[rid]['label']} | {runs[rid]['rho_c_mohm']:g} | "
          f"{runs[rid]['rsheet']:g} | {r['finger_width_um']:g} | "
          f"{r['pitch_mm_requested']:g} | 16 | {r['metal_fraction']:.4f} | "
          f"**{_f(r['efficiency_pct'])}** |")
    a(f"| **C** — decomposition | {runs['C']['rho_c_mohm']:g} | "
      f"{runs['C']['rsheet']:g} | {rC['finger_width_um']:g} | "
      f"{rC['pitch_mm_requested']:g} | 16 | {rC['metal_fraction']:.4f} | "
      f"{_f(etaC)} |")
    a("")
    a("Run C is a **single evaluation at the Run B optimum with only `R_sheet` "
      "changed** — it is *not* re-optimized. The decomposition below is "
      "approximate for that reason.")
    a("")
    a("### Δη decomposition")
    a("")
    a("| Term | Δη (%abs) |")
    a("|---|---:|")
    a(f"| ρ_c effect — η(C) − η(A) | {d_rhoc:+.3f} |")
    a(f"| sheet-R penalty — η(B) − η(C) | {d_sheet:+.3f} |")
    a(f"| **net — η(B) − η(A)** | **{d_net:+.3f}** |")
    a("")
    a("---")
    a("")
    a("## 2. Boundary check (A1) — CRITICAL")
    a("")
    for rid in ("A", "B"):
        st = state[rid]
        if st["boundary"]:
            a(f"- ### ⚠ Run {rid}: **BOUNDARY-LIMITED — NOT AN OPTIMUM.**")
            a(f"  argmax sits on {'; '.join(st['boundary_axes'])}"
              + (", still on the edge after the capped one-shot extension."
                 if st["extended"] else "."))
            a(f"  **This value must not be presented as an optimized "
              f"efficiency.** The true optimum lies outside the grid.")
        else:
            a(f"- Run {rid}: interior optimum"
              + (" (after one capped grid extension)." if st["extended"]
                 else ", no extension needed."))
    a("")
    a("---")
    a("")
    a("## 3. Checks")
    a("")
    a(f"- **A2 — Jph identity.** `Jph_top = {jph_top * 1e3:.2f}` and "
      f"`Jph_bot = {jph_bot * 1e3:.2f}` mA/cm² asserted at *every* evaluation "
      f"in runs A/B/C/D. Passed. (The Voc-anchor point in §4 overrides Jph "
      f"deliberately and is excluded from the assertion — it is not part of "
      f"A/B/C/D.)")
    a(f"- **Top-limited.** {jph_top * 1e3:.2f} < {jph_bot * 1e3:.2f} mA/cm² — "
      f"the tandem is limited by the **top** subcell.")
    ok = (etaB > etaC > etaA)
    a(f"- **A3 — ordering** η(B) > η(C) > η(A): "
      f"{'holds' if ok else '**VIOLATED**'} "
      f"({_f(etaB)} / {_f(etaC)} / {_f(etaA)})."
      + ("" if ok else " Reported as-is with the loss breakdown in §5; "
                       "nothing was adjusted."))
    a("")
    a("---")
    a("")
    a("## 4. Voc")
    a("")
    a("| Case | Jph top / bot (mA/cm²) | Voc (V) |")
    a("|---|---|---:|")
    a(f"| Run B optimum (our measured Jph) | {jph_top * 1e3:.2f} / "
      f"{jph_bot * 1e3:.2f} | {_f(bB['Voc_V'], 4)} |")
    a(f"| Same point, Jeon's own Iph | {jeon['Iph'] * 1e3:.2f} / "
      f"{jeon['Iph'] * 1e3:.2f} | {_f(rV['Voc_V'], 4)} |")
    a("")
    a(f"- collaborator measured tandem Voc ≈ **{voc_measured:.2f} V** "
      f"(`DERIVED` — read from a figure)")
    a(f"- hand calculation from Jeon Table 1: **{voc_hand:.3f} V** (`DERIVED`)")
    a(f"- **residual (our Jph): {bB['Voc_V'] - voc_measured:+.4f} V**")
    a(f"- **residual (Jeon Iph, directly comparable to the hand calc): "
      f"{rV['Voc_V'] - voc_hand:+.4f} V**")
    a("")
    a("`J01_top` was **not** tuned. The residuals are reported exactly as they "
      "came out.")
    a("")
    a("> Why two rows: the task fixes Jph to the collaborator's measured EQE "
      "values (20.36 / 20.45), while the ~1.935 V hand calculation uses Jeon's "
      "own 19.65 for both subcells. Comparing our-Jph Voc against a Jeon-Jph "
      "hand number would confound a photocurrent difference with a diode "
      "difference, so both are given.")
    a("")
    a("---")
    a("")
    a("## 5. Rs_junction sensitivity (Run D)")
    a("")
    a("| Rs_junction (Ω/sq) | Source | η (%) | Voc (V) | FF (%) |")
    a("|---:|---|---:|---:|---:|")
    a(f"| {rs_j:g} | Jeon Table 1 `R_inter sheet` (**used**) | "
      f"{_f(bB['efficiency_pct'])} | {_f(bB['Voc_V'], 4)} | {_f(bB['FF_pct'])} |")
    a(f"| {rs_j_sens:g} | generic Griddler-equivalent default | "
      f"{_f(rD['efficiency_pct'])} | {_f(rD['Voc_V'], 4)} | {_f(rD['FF_pct'])} |")
    a("")
    a(f"Δη = **{rD['efficiency_pct'] - bB['efficiency_pct']:+.3f} %abs** going "
      f"from {rs_j:g} to {rs_j_sens:g} Ω/sq at the Run B optimum.")
    a("")
    a("---")
    a("")
    a("## 6. Which loss dominates (at the Run B optimum)")
    a("")
    a("| Quantity | Analytic referral | Hand reference |")
    a("|---|---:|---:|")
    a(f"| Contact R referred to cell area (Ω·cm²) | {_f(rc_ref)} | {hand_rc:.2f} |")
    a(f"| TCO lateral R referred to cell area (Ω·cm²) | {_f(tco_ref)} | {hand_tco:.2f} |")
    a("")
    a("Referral formulas: contact `= ρ_c / f_metal`; TCO lateral "
      "`= R_sheet · p² / 12` (distributed-emitter result). These are analytic "
      "referrals of the *inputs* shown against the task's hand reference — they "
      "are **not** the solver's FEM loss terms. The FEM terms at the same point:")
    a("")
    a("| FEM loss term | mW/cm² |")
    a("|---|---:|")
    for key, lbl in (("Pc_contact_mW_cm2", "contact `Pc`"),
                     ("Pe_emitter_mW_cm2", "emitter / TCO lateral `Pe`"),
                     ("Pf_finger_mW_cm2", "finger `Pf_finger`"),
                     ("Pf_busbar_mW_cm2", "busbar `Pf_busbar`"),
                     ("P_shade_mW_cm2", "shading `P_shade`"),
                     ("P_recomb_mW_cm2", "recombination `P_recomb`"),
                     ("P_shunt_mW_cm2", "shunt `P_shunt`"),
                     ("P_Rc_junction_mW_cm2", "recomb. junction `P_Rc_junction`")):
        a(f"| {lbl} | {_f(bB.get(key, 0.0), 4)} |")
    a("")
    a("### Hand-calc sanity reference (NOT ground truth)")
    a("")
    a("| Run | hand f | solver f | hand η | solver η | Δη |")
    a("|---|---:|---:|---:|---:|---:|")
    for rid, b in (("A", bA), ("B", bB)):
        h = hand_ref[rid]
        a(f"| {rid} | {h['f']:.3f} | {b['metal_fraction']:.4f} | "
          f"{h['eff']:.1f} | {_f(b['efficiency_pct'])} | "
          f"{b['efficiency_pct'] - h['eff']:+.2f} |")
    a("")
    a("The hand estimate is a linearized series-resistance calculation; it omits "
      "diode non-linearity, metallized-area recombination, busbar shading and "
      "the edge margin. Where the solver disagrees the solver is probably right "
      "— but the disagreement is stated rather than absorbed.")
    a("")
    a("---")
    a("")
    a("## 7. Limitations")
    a("")
    a("### Simplifications adopted for speed")
    a("")
    a("1. **Metal optical transparency OFF.** Busbars are modeled as "
      "low-resistance collectors with a geometric optical shading width of "
      "**0.20 mm** (Cu wire), not their printed width of 0.036 mm. This avoids "
      "the degenerate transparency value `1 − 0.20/0.036 = −4.56` entirely. "
      "Same simplification already communicated to the collaborator.")
    a(f"2. **Single mesh resolution ({node_budget:,} nodes). Mesh convergence "
      f"is PENDING.** The higher-density re-runs were dropped to fit "
      f"tonight's window, so no number here has a mesh-sensitivity bound.")
    a("3. **Coarse grid only.** No local refinement pass this round.")
    a("4. **Runs C and D are single evaluations, not sweeps** — the "
      "decomposition in §1 is approximate for that reason.")
    a("5. **No metallized-area J0 enhancement.** Jeon Table 1 gives one J01 and "
      "one J02 per subcell with no pass/metal split, so `pass = metal` here. "
      "The engine's own default carried a ~83× under-metal enhancement for the "
      "top cell. Consequence: this model **under-penalises wide metal**, so the "
      "optimum sits at slightly wider coverage than a split model would give.")
    a("")
    a("### Diode parameter set")
    a("")
    a(diode_note)
    a("")
    a("| Parameter | Top (perovskite) | Bottom (Si) |")
    a("|---|---:|---:|")
    a(f"| J01 (A/cm²) | {jeon['J01_top']:.4g} | {jeon['J01_bot']:.4g} |")
    a(f"| J02 (A/cm²) | {jeon['J02_top']:.4g} | {jeon['J02_bot']:.4g} |")
    a(f"| n1 / n2 | {jeon['n1_top']:g} / {jeon['n2_top']:g} | "
      f"{jeon['n1_bot']:g} / {jeon['n2_bot']:g} |")
    a(f"| Rs vertical (Ω·cm²) | {jeon['Rs_vert_top']:g} | {jeon['Rs_vert_bot']:g} |")
    a(f"| Rsh (Ω·cm²) | {jeon['Rsh_top']:g} | {jeon['Rsh_bot']:g} |")
    a("")
    a(f"Jeon's `R_ITO sheet` = {jeon['R_ito_sheet']:g} Ω/sq is **not** used — "
      f"the per-run measured `R_sheet` (128 / 147.1 Ω/sq) is the whole point of "
      f"the study and overrides it.")
    a("")
    a("> The absolute efficiencies inherit whatever the diode set gets wrong. "
      "The **Δη decomposition is far more robust** than the absolute numbers, "
      "because the diode parameters are identical across A, B and C — they "
      "cancel to first order.")
    a("")
    a("### Every non-measured input")
    a("")
    a("| Parameter | Value | Tag |")
    a("|---|---|---|")
    for name, val, tag in param_table:
        if tag.startswith("MEASURED") and "OURS" not in tag:
            continue
        a(f"| {name} | {val} | `{tag}` |")
    a("")
    a("### Measured inputs (for contrast)")
    a("")
    a("| Parameter | Value | Tag |")
    a("|---|---|---|")
    for name, val, tag in param_table:
        if tag.startswith("MEASURED"):
            a(f"| {name} | {val} | `{tag}` |")
    a(f"| ρ_c (Run A / B) | {runs['A']['rho_c_mohm']:g} / "
      f"{runs['B']['rho_c_mohm']:g} mΩ·cm² | `MEASURED` |")
    a(f"| R_sheet (Run A / B) | {runs['A']['rsheet']:g} / "
      f"{runs['B']['rsheet']:g} Ω/sq | `MEASURED` |")
    a("")

    path = os.path.join(out_dir, "summary.md")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"wrote {path}")
    return path
