"""M10 front-grid resistive loss before/after hot pressing — report figure.

High-mesh 2L-FEST result (mesh-converged; matches Rehman 2023 analytical and
the rho-linear scaling). Conference-ready bar chart + table.
"""
import os
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.gridspec import GridSpec

for cand in ("AppleGothic", "Apple SD Gothic Neo", "NanumGothic"):
    if any(cand == f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = cand; break
plt.rcParams["axes.unicode_minus"] = False
HERE = os.path.dirname(os.path.abspath(__file__))

# High-mesh results [mW/cm^2]
before = {"Finger": 0.0073, "Busbar": 0.0018, "합계": 0.0091}
after  = {"Finger": 0.0040, "Busbar": 0.0011, "합계": 0.0050}
labels = list(before.keys())
b = np.array([before[k] for k in labels]); a = np.array([after[k] for k in labels])
# exact reductions from the full-precision High-mesh run (not from rounded values)
red = np.array([46.0, 39.1, 44.6])
RED = {"Finger": 46.0, "Busbar": 39.1, "합계": 44.6}

C_B, C_A = "#C0392B", "#2E86C1"
fig = plt.figure(figsize=(13, 6.8), facecolor="white")
gs = GridSpec(1, 2, figure=fig, width_ratios=[1, 1.12], left=0.07, right=0.975,
              top=0.84, bottom=0.11, wspace=0.22)
fig.suptitle("M10 탠덤 셀 — Hot Pressing 전/후 앞면 그리드 저항손실",
             fontsize=15, fontweight="bold", y=0.965)
fig.text(0.5, 0.90, "182×182 mm · 132 finger + 16 busbar · 프로브 12/BB · 동작전류 ~17.3 mA/cm² · "
         "High mesh (2L-FEST FEM)", ha="center", fontsize=9.5, color="#555")

# (A) grouped bar chart
axA = fig.add_subplot(gs[0, 0])
x = np.arange(len(labels)); w = 0.38
axA.bar(x - w/2, b*1e3, w, color=C_B, label="Before (ρ=8 µΩ·cm)")
axA.bar(x + w/2, a*1e3, w, color=C_A, label="After (ρ=4.22)")
for i in range(len(labels)):
    axA.text(x[i], max(b[i], a[i])*1e3 + 0.25, f"−{red[i]:.0f}%", ha="center",
             fontsize=11, fontweight="bold", color="#117A65")
axA.set_xticks(x); axA.set_xticklabels(labels, fontsize=11)
axA.set_ylabel("저항손실 [µW/cm²]", fontsize=11)
axA.set_title("(A) 손실 비교 (Before vs After)", fontsize=11.5, fontweight="bold")
axA.set_ylim(0, max(b)*1e3*1.30); axA.grid(axis="y", alpha=0.3); axA.legend(fontsize=9.5, loc="upper right")

# (B) table + conditions + conclusion
axB = fig.add_subplot(gs[0, 1]); axB.axis("off")
axB.set_title("(B) 수치 및 조건", fontsize=11.5, fontweight="bold", y=1.0)
cells = [["손실 [mW/cm²]", "Before", "After", "감소율"]]
for k in labels:
    cells.append([k, f"{before[k]:.4f}", f"{after[k]:.4f}", f"−{RED[k]:.1f}%"])
colors = [["#1F2937"]*4] + [["#F1F5F9", "#FDEDEC", "#EBF5FB", "#D1F2EB"] for _ in labels]
t = axB.table(cellText=cells, cellColours=colors, loc="center", cellLoc="center",
              bbox=[0.0, 0.60, 1.0, 0.32])
t.auto_set_font_size(False); t.set_fontsize(10.5); t.scale(1, 1.6)
for c in range(4): t[(0, c)].set_text_props(color="white", fontweight="bold")
for r in range(1, len(cells)): t[(r, 0)].set_text_props(fontweight="bold")
t[(len(labels), 0)].set_text_props(fontweight="bold")  # 합계 row label

axB.text(0.0, 0.50,
    "■ 조건\n"
    "   · 웨이퍼: M10 182×182 mm, 132 finger / 16 busbar, busbar 폭 600 µm\n"
    "   · Before: bulk ρ 8 µΩ·cm, finger 높이 11 µm, 폭 55 µm\n"
    "   · After : bulk ρ 4.22 µΩ·cm, finger 높이 9.5 µm, 폭 65 µm\n"
    "   · 페로브스카이트/Si 탠덤 동작전류 ~17.3 mA/cm²",
    transform=axB.transAxes, va="top", fontsize=9.2, color="#1E293B", linespacing=1.45)
axB.text(0.0, 0.20,
    "■ 결론\n"
    "   Hot pressing으로 앞면 그리드 저항손실 0.0091 → 0.0050 mW/cm²,\n"
    "   약 45% 감소 (finger −46%, busbar −39%). 주 기여는 bulk ρ 감소.",
    transform=axB.transAxes, va="top", fontsize=9.6, color="#117A65", fontweight="bold", linespacing=1.45)
axB.add_patch(plt.Rectangle((-0.02, -0.02), 1.04, 1.02, transform=axB.transAxes,
              fill=False, ec="#cbd5e1", lw=1.0, clip_on=False))

out = f"{HERE}/M10_gridloss_hotpressing.png"
fig.savefig(out, dpi=160); print("saved", out); print("FIG_DONE")
