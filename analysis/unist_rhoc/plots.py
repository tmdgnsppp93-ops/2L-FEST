# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Figures for the UNIST M10 rho_c first-pass study. These are the slides.

Design rule for the heatmaps: the **grid boundary is drawn explicitly** so that
boundary-adjacency of the argmax is visible at a glance. A boundary-limited
argmax is not an optimum, and a heatmap that hides the edge invites exactly that
misreading.
"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt        # noqa: E402
import numpy as np                     # noqa: E402


_BG = "#FFFFFF"
_ACCENT = "#B45309"


def _grid_matrix(rows):
    """rows -> (widths, pitches, Z[pitch, width]) with NaN for missing points."""
    ws = sorted({r["finger_width_um"] for r in rows})
    ps = sorted({r["pitch_mm_requested"] for r in rows})
    Z = np.full((len(ps), len(ws)), np.nan)
    for r in rows:
        i = ps.index(r["pitch_mm_requested"])
        j = ws.index(r["finger_width_um"])
        Z[i, j] = r["efficiency_pct"]
    return ws, ps, Z


def heatmap(rows, best, boundary, boundary_axes, title, path):
    ws, ps, Z = _grid_matrix(rows)
    fig, ax = plt.subplots(figsize=(7.2, 5.4), dpi=160, facecolor=_BG)

    im = ax.imshow(Z, origin="lower", aspect="auto", cmap="viridis",
                   interpolation="nearest")
    cb = fig.colorbar(im, ax=ax)
    cb.set_label("Efficiency (%)", fontsize=10)

    ax.set_xticks(range(len(ws)))
    ax.set_xticklabels([f"{w:g}" for w in ws])
    ax.set_yticks(range(len(ps)))
    ax.set_yticklabels([f"{p:g}" for p in ps])
    ax.set_xlabel("Finger width (µm)", fontsize=11)
    ax.set_ylabel("Finger pitch (mm)", fontsize=11)

    # cell annotations
    for i in range(len(ps)):
        for j in range(len(ws)):
            if np.isnan(Z[i, j]):
                continue
            v = Z[i, j]
            rel = (v - np.nanmin(Z)) / max(np.nanmax(Z) - np.nanmin(Z), 1e-9)
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7.5,
                    color="white" if rel < 0.55 else "#111111")

    # argmax marker
    bi = ps.index(best["pitch_mm_requested"])
    bj = ws.index(best["finger_width_um"])
    ax.plot(bj, bi, marker="o", markersize=17, markerfacecolor="none",
            markeredgecolor=_ACCENT, markeredgewidth=2.6, zorder=5)

    # explicit grid boundary — the whole point of check A1
    ax.plot([-0.5, len(ws) - 0.5, len(ws) - 0.5, -0.5, -0.5],
            [-0.5, -0.5, len(ps) - 0.5, len(ps) - 0.5, -0.5],
            color="#DC2626", lw=2.4, ls="--", zorder=6,
            label="grid boundary")
    ax.set_xlim(-0.5, len(ws) - 0.5)
    ax.set_ylim(-0.5, len(ps) - 0.5)

    sub = (f"argmax  w_f={best['finger_width_um']:g} µm, "
           f"pitch={best['pitch_mm_requested']:g} mm  →  "
           f"{best['efficiency_pct']:.3f} %   "
           f"(f_metal={best['metal_fraction']:.4f})")
    if boundary:
        sub += "\n⚠ BOUNDARY-LIMITED — not an optimum: " + "; ".join(boundary_axes)
    ax.set_title(title + "\n" + sub, fontsize=10.5, fontweight="bold",
                 color="#B91C1C" if boundary else "#111111")
    ax.legend(loc="upper right", fontsize=8, framealpha=0.85)

    fig.tight_layout()
    fig.savefig(path, facecolor=_BG)
    plt.close(fig)
    print(f"wrote {path}")


_LOSS_KEYS = [
    ("P_shade_mW_cm2", "Shading"),
    ("Pe_emitter_mW_cm2", "Emitter / TCO lateral"),
    ("Pf_finger_mW_cm2", "Finger"),
    ("Pf_busbar_mW_cm2", "Busbar"),
    ("Pc_contact_mW_cm2", "Contact"),
    ("P_recomb_mW_cm2", "Recombination"),
    ("P_shunt_mW_cm2", "Shunt"),
    ("P_Rc_junction_mW_cm2", "Recomb. junction"),
]


def loss_breakdown(rowA, rowB, path):
    labels = [lbl for _, lbl in _LOSS_KEYS]
    va = [rowA.get(k, 0.0) or 0.0 for k, _ in _LOSS_KEYS]
    vb = [rowB.get(k, 0.0) or 0.0 for k, _ in _LOSS_KEYS]

    x = np.arange(len(labels))
    w = 0.38
    fig, ax = plt.subplots(figsize=(9.0, 5.0), dpi=160, facecolor=_BG)
    ax.bar(x - w / 2, va, w, label=f"A — before (η={rowA['efficiency_pct']:.2f}%)",
           color="#94A3B8", edgecolor="white")
    ax.bar(x + w / 2, vb, w, label=f"B — after (η={rowB['efficiency_pct']:.2f}%)",
           color="#0EA5E9", edgecolor="white")

    for xi, v in zip(x - w / 2, va):
        if v > 0:
            ax.text(xi, v, f"{v:.2f}", ha="center", va="bottom", fontsize=7.5)
    for xi, v in zip(x + w / 2, vb):
        if v > 0:
            ax.text(xi, v, f"{v:.2f}", ha="center", va="bottom", fontsize=7.5)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9, rotation=18, ha="right")
    ax.set_ylabel("Loss (mW/cm²)", fontsize=11)
    ax.set_title("Loss breakdown at the A and B optima  (first pass)",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", alpha=0.18)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(path, facecolor=_BG)
    plt.close(fig)
    print(f"wrote {path}")


def make_all(state, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    titles = {
        "A": "Run A - before  (rho_c = 1716 mOhm.cm2, R_sheet = 128 Ohm/sq)",
        "B": "Run B - after  (rho_c = 15.32 mOhm.cm2, R_sheet = 147.1 Ohm/sq)",
    }
    for rid in ("A", "B"):
        st = state[rid]
        heatmap(st["rows"], st["best"], st["boundary"], st["boundary_axes"],
                titles[rid], os.path.join(out_dir, "heatmap_%s.png" % rid))
    # Medium density at both optima - the max-density re-runs were dropped.
    loss_breakdown(state["A"]["best"], state["B"]["best"],
                   os.path.join(out_dir, "loss_breakdown.png"))
