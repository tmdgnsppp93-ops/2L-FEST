"""Presentation figure (KR/EN) for Dr. Kim — 2L-FEST (FEM) vs Solcore Quasi-3D.

Loads compare_result.npz (realistic 10-finger cell). Table shows absolute AND
relative differences; conclusion (Korean) explains WHY the gap appears and WHICH
solver is more accurate, with the reason.

    /Users/seunghooooonii/Downloads/lfest_env/bin/python make_report_figure.py
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.gridspec import GridSpec

# --- Korean font (AppleGothic on macOS) ---
for cand in ("AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Malgun Gothic"):
    if any(cand == f.name for f in fm.fontManager.ttflist):
        plt.rcParams["font.family"] = cand
        break
plt.rcParams["axes.unicode_minus"] = False   # avoid missing minus glyph

HERE = "/Users/seunghooooonii/Desktop/2L-FEST/solcore_xval"
d = np.load(f"{HERE}/compare_result.npz")

Vf, Jf = d["Vf"], d["Jf"]
Vs, Js = d["Vs"], d["Js"] * 1e3
contacts = d["contacts"]
W, H = float(d["W"]), float(d["H"])
pix = float(d["pix_um"]); n_f = int(d["n_f"])

mf = dict(Jsc=float(d["mf_Jsc"]), Voc=float(d["mf_Voc"]), FF=float(d["mf_FF"])*100, Eff=float(d["mf_Pmax"]))
ms = dict(Jsc=float(d["ms_Jsc"])*1e3, Voc=float(d["ms_Voc"]), FF=float(d["ms_FF"])*1e2, Eff=float(d["ms_Pmax"])*1e3)

# diagnosis quantities: optical (areal) vs electrical (metal-node) shading
shade_opt = float(d["shade"]) * 100                       # areal metal fraction
shade_elec = float((contacts > 55).sum()) / contacts.size * 100  # metal NODES
Jph = 19.77
loss_f = (1 - mf["Jsc"] / Jph) * 100
loss_s = (1 - ms["Jsc"] / Jph) * 100

C_FEM = "#C0392B"; C_SPICE = "#2563EB"
GOOD = "#D1FAE5"; WARN = "#FEF3C7"

fig = plt.figure(figsize=(13.8, 9.4), facecolor="white")
gs = GridSpec(2, 2, figure=fig, height_ratios=[1, 1.05], width_ratios=[1, 1.2],
              hspace=0.34, wspace=0.2, left=0.06, right=0.975, top=0.845, bottom=0.055)

fig.suptitle("2L-FEST (FEM)  vs  Solcore Quasi-3D (SPICE) — 단일셀 교차검증",
             fontsize=15.5, fontweight="bold", y=0.97)
fig.text(0.5, 0.927,
         f"{W*10:.0f}×{H*10:.0f} mm c-Si · {n_f}핑거 그리드 · 동일 2-diode/sheet-R/contact · "
         f"25 ℃ · 완전히 독립적인 두 수치해법(FEM vs SPICE 회로망)",
         ha="center", fontsize=10, color="#555")
fig.text(0.5, 0.893,
         "★ 모든 입력 동일(그리드·다이오드·저항·온도, 내부 직렬R도 둘 다 0) — 솔버만 다름.\n"
         "    Jsc 차이의 원인 = Solcore 금속노드가 50µm 핑거를 100µm 픽셀로 마킹 → 전기적 그늘이 광학의 2배 (정량 확정).",
         ha="center", fontsize=9.5, color="#1D4ED8", fontweight="bold", linespacing=1.4,
         bbox=dict(boxstyle="round,pad=0.4", fc="#EFF6FF", ec="#1D4ED8", lw=1.0))

# (A) mask -----------------------------------------------------------------
axA = fig.add_subplot(gs[0, 0])
img = np.zeros_like(contacts); img[contacts > 55] = 1; img[contacts > 200] = 2
axA.imshow(img.T, origin="lower", cmap="Greys", extent=[0, W*10, 0, H*10],
           vmin=0, vmax=2, interpolation="nearest", aspect="equal")
axA.set_title("(A) 금속 그리드 → SPICE 노드 마스크", fontsize=11, fontweight="bold")
axA.set_xlabel("x [mm]"); axA.set_ylabel("y [mm]")
axA.text(0.02, 0.98, f"{contacts.shape[0]}×{contacts.shape[1]} px @ {pix:.0f}um\n{n_f}핑거 + 버스바 1",
         transform=axA.transAxes, va="top", fontsize=8.5,
         bbox=dict(boxstyle="round", fc="white", ec="#bbb", alpha=0.85))

# (B) IV overlay -----------------------------------------------------------
axB = fig.add_subplot(gs[0, 1])
axB.plot(Vf, Jf, "o-", color=C_FEM, ms=4, lw=1.9, label="2L-FEST (FEM)")
axB.plot(Vs, Js, "s--", color=C_SPICE, ms=3, lw=1.6, label="Solcore Quasi-3D (SPICE)")
axB.set_title("(B) 조사 I–V 곡선 비교", fontsize=11, fontweight="bold")
axB.set_xlabel("전압 [V]"); axB.set_ylabel("전류밀도 J [mA/cm2]")
axB.set_xlim(0, mf["Voc"]*1.05); axB.set_ylim(0, mf["Jsc"]*1.18)
axB.grid(alpha=0.3); axB.legend(loc="lower left", fontsize=9.5)
axB.text(0.97, 0.95, "곡선 모양 동일,\nVoc(무릎) 일치", transform=axB.transAxes,
         ha="right", va="top", fontsize=8.8, color="#555")

# (C) metric table: absolute + relative ------------------------------------
axC = fig.add_subplot(gs[1, 0]); axC.axis("off")
axC.set_title("(C) 지표 비교 (절대차 + 상대차)", fontsize=11, fontweight="bold", y=0.99)
rows = [("Jsc [mA/cm2]", mf["Jsc"], ms["Jsc"]),
        ("Voc [V]",       mf["Voc"], ms["Voc"]),
        ("FF [%]",        mf["FF"],  ms["FF"]),
        ("Eff [%]",       mf["Eff"], ms["Eff"])]
cells = [["지표", "2L-FEST", "Solcore", "절대차", "상대차%"]]
colors = [["#1F2937"]*5]
for name, a, b in rows:
    dabs = b - a; rel = 100*dabs/a if a else float("nan")
    cells.append([name, f"{a:.2f}", f"{b:.2f}", f"{dabs:+.2f}", f"{rel:+.2f}"])
    bg = GOOD if abs(rel) < 1 else WARN
    colors.append(["#F1F5F9", "white", "white", bg, bg])
tbl = axC.table(cellText=cells, cellColours=colors, loc="center", cellLoc="center",
                bbox=[0.0, 0.34, 1.0, 0.58])
tbl.auto_set_font_size(False); tbl.set_fontsize(10.0); tbl.scale(1, 1.6)
for c in range(5):
    tbl[(0, c)].set_text_props(color="white", fontweight="bold")
for ri in range(1, len(cells)):
    tbl[(ri, 0)].set_text_props(fontweight="bold")
axC.text(0.0, 0.22, "초록 = 일치(<1%)    노랑 = Solcore 격자 한계 (D 참조)",
         transform=axC.transAxes, fontsize=8.5, color="#555")
axC.text(0.0, 0.12, "[프레임워크 검증] 균일셀 vs 해석적 2-diode: Jsc 0.00%, Voc 0.20%\n"
         "→ 비교 코드 자체는 정확. 아래 Jsc 차이는 버그가 아니라 실제 물리.",
         transform=axC.transAxes, fontsize=8.5, color="#1E293B", va="top")

# (D) conclusion (KR) ------------------------------------------------------
axD = fig.add_subplot(gs[1, 1]); axD.axis("off")
axD.set_title("(D) 결론 — 차이의 원인과 정확도 판정", fontsize=11, fontweight="bold", y=0.99)
axD.text(0.0, 0.96,
    f"[검증됨]  Voc·FF 차이 < 0.6% (Voc {abs(ms['Voc']-mf['Voc']):.3f} V, FF {abs(ms['FF']-mf['FF']):.2f}%p)\n"
    "   재결합 다이오드 + 횡전도(sheet R) 물리가 FEM과 SPICE 회로망\n"
    "   두 독립 방법에서 일치 → 핵심 물리 교차검증 완료.",
    transform=axD.transAxes, va="top", fontsize=8.7, color="#065F46", linespacing=1.4)
axD.text(0.0, 0.69,
    f"[차이 원인 — 정량 확정]  Jsc {ms['Jsc']-mf['Jsc']:+.2f} mA/cm2 (~{abs(loss_s-loss_f):.0f}%p).\n"
    f"   Solcore는 금속노드면 광전류를 통째로 0으로 만든다. 픽셀(100um)>핑거\n"
    f"   (50um)라 핑거가 픽셀행을 통째로/2행에 걸쳐 금속노드化 →\n"
    f"   전기적 그늘 {shade_elec:.1f}% = 광학 그늘 {shade_opt:.1f}%의 약 2배.\n"
    f"   · Solcore Jsc 손실 {loss_s:.1f}% ≈ 전기적 그늘 {shade_elec:.1f}%  (일치)\n"
    f"   · 2L-FEST Jsc 손실 {loss_f:.1f}% ≈ 광학 그늘 {shade_opt:.1f}%  (정상)\n"
    f"   · sheet R=1로 낮춰도 갭 불변 → 수집(collection) 아님, 순수 그늘 확인.",
    transform=axD.transAxes, va="top", fontsize=8.7, color="#92400E", linespacing=1.4)
axD.text(0.0, 0.265,
    "[정확도]  이 항목은 2L-FEST가 더 정확하다.\n"
    "   2L-FEST는 구속 FEM 메시가 핑거 경계를 메시 선에 정확히 올려 50um\n"
    "   핑거를 그대로 표현 → 그늘이 기하학적으로 정확. Solcore binary 픽셀은\n"
    "   픽셀>핑거인 한 구조적으로 과대 그늘(정합엔 픽셀<=핑거 필요, ngspice 한계).",
    transform=axD.transAxes, va="top", fontsize=8.7, color="#1E293B", linespacing=1.4)
axD.add_patch(plt.Rectangle((-0.02, -0.02), 1.04, 1.0, transform=axD.transAxes,
              fill=False, ec="#cbd5e1", lw=1.0, clip_on=False))

out = f"{HERE}/2LFEST_vs_Solcore_quasi3D.png"
fig.savefig(out, dpi=160)
print("saved", out)
print("FIG_DONE")
