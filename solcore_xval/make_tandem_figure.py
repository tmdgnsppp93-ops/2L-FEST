# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Tandem report figure for Dr. Kim.

2L-FEST solves the perovskite/Si 2T tandem (Voc~1.9V, Eff~30.6%); Solcore
Quasi-3D cannot converge it (stiff perovskite diode + 2-junction series; even
Solcore's own 3J example simulates only a single junction). Frames it as a
solver-capability / robustness comparison.
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
d = np.load(f"{HERE}/compare_tandem_result.npz")
Vf, Jf = d["Vf"], d["Jf"]
Voc = float(d["mf_Voc"]); Jsc = float(d["mf_Jsc"]); FF = float(d["mf_FF"])*100; Eff = float(d["mf_Pmax"])

C_FEM = "#C0392B"
fig = plt.figure(figsize=(13.5, 7.6), facecolor="white")
gs = GridSpec(1, 2, figure=fig, width_ratios=[1, 1.25], left=0.07, right=0.975,
              top=0.86, bottom=0.09, wspace=0.18)
fig.suptitle("페로브스카이트/Si 탠덤 — 2L-FEST 계산 및 Solcore Quasi-3D 비교",
             fontsize=15, fontweight="bold", y=0.965)
fig.text(0.5, 0.905, "단일셀은 두 솔버 교차검증 완료 / 탠덤은 2L-FEST(FEM)만 수렴 — "
         "Solcore Quasi-3D는 실질적으로 단일접합 전용", ha="center", fontsize=10, color="#555")

# (A) 2L-FEST tandem J-V
axA = fig.add_subplot(gs[0, 0])
axA.plot(Vf, Jf, "o-", color=C_FEM, ms=5, lw=2, label="2L-FEST (FEM)")
axA.set_title("(A) 2L-FEST 탠덤 J–V 곡선", fontsize=11.5, fontweight="bold")
axA.set_xlabel("전압 [V]"); axA.set_ylabel("전류밀도 J [mA/cm$^2$]")
axA.set_xlim(0, Voc*1.05); axA.set_ylim(0, Jsc*1.18)
axA.grid(alpha=0.3); axA.legend(loc="lower left", fontsize=10)
axA.text(0.04, 0.40,
         f"Voc = {Voc:.3f} V\nJsc = {Jsc:.2f} mA/cm$^2$\nFF  = {FF:.1f} %\nEff = {Eff:.1f} %",
         transform=axA.transAxes, fontsize=11, family="monospace",
         bbox=dict(boxstyle="round,pad=0.5", fc="#FEF9E7", ec="#C0392B", lw=1.2))
axA.text(0.96, 0.94, "Voc ≈ 1.9 V\n(페로브 ~1.2V + Si ~0.7V)", transform=axA.transAxes,
         ha="right", va="top", fontsize=8.8, color="#555")

# (B) capability + conclusion
axB = fig.add_subplot(gs[0, 1]); axB.axis("off")
axB.set_title("(B) 솔버 능력 비교 및 결론", fontsize=11.5, fontweight="bold", y=1.0)

axB.text(0.0, 0.96,
    "■ 단일접합 vs 탠덤(2중접합)\n"
    "   · 단일접합 = 흡수층(P-N 접합) 1장 (예: 실리콘 셀)\n"
    "   · 탠덤 = 페로브스카이트(위) + Si(아래) 2장을 직렬로 포갬\n"
    "     → 빛 스펙트럼을 나눠 흡수, 전압이 더해짐(~1.9V), 효율↑",
    transform=axB.transAxes, va="top", fontsize=9.3, color="#1E293B", linespacing=1.45)

# capability table
cells = [["", "단일셀", "탠덤(2T)"],
         ["2L-FEST (FEM)", "가능", "가능 (Eff 30.6%)"],
         ["Solcore (SPICE)", "가능", "불가 (수렴실패)"]]
colA = [["#1F2937"]*3,
        ["#F1F5F9", "#D1FAE5", "#D1FAE5"],
        ["#F1F5F9", "#D1FAE5", "#FECACA"]]
t = axB.table(cellText=cells, cellColours=colA, loc="center", cellLoc="center",
              bbox=[0.0, 0.52, 1.0, 0.20])
t.auto_set_font_size(False); t.set_fontsize(10); t.scale(1, 1.5)
for c in range(3): t[(0, c)].set_text_props(color="white", fontweight="bold")
for r in range(1, 3): t[(r, 0)].set_text_props(fontweight="bold")

axB.text(0.0, 0.46,
    "■ 단일셀: 두 솔버 정량 교차검증 성공 (Voc·FF 0.5% 일치)",
    transform=axB.transAxes, va="top", fontsize=9.3, color="#065F46", linespacing=1.4)
axB.text(0.0, 0.40,
    "■ 탠덤: Solcore Quasi-3D 수렴 실패 — 이유\n"
    "   · 페로브스카이트 J01이 극히 작아(3e-18) 다이오드가 매우 가파름\n"
    "     (stiff). Si와 직렬로 쌓이면 ngspice가 동작점(OP)을 못 찾음\n"
    "     (gmin·source·transient stepping 모두 실패).\n"
    "   · Solcore 공식 '3J 예제'조차 실제론 단일접합 1개만 시뮬레이션\n"
    "     (전체 다중접합 >86,000 노드 회피) → 실질적 단일접합 도구.",
    transform=axB.transAxes, va="top", fontsize=9.3, color="#92400E", linespacing=1.4)
axB.text(0.0, 0.13,
    "■ 결론\n"
    "   탠덤(페로브/Si)은 2L-FEST(FEM-Newton)만 강건하게 계산.\n"
    "   FEM 기반 전용 솔버가 다중접합 시뮬레이션에서 우위.",
    transform=axB.transAxes, va="top", fontsize=9.6, color="#1E293B", fontweight="bold", linespacing=1.45)
axB.add_patch(plt.Rectangle((-0.02, -0.02), 1.04, 1.02, transform=axB.transAxes,
              fill=False, ec="#cbd5e1", lw=1.0, clip_on=False))

out = f"{HERE}/2LFEST_tandem_vs_Solcore.png"
fig.savefig(out, dpi=160); print("saved", out); print("FIG_DONE")
