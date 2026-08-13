# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""roadmap 4-panel 플롯 — Jsc / Voc / FF / Efficiency.

계산(roadmap.py)과 분리되어 있다. 논문 figure는 스타일을 여러 번 고치므로
CSV만 있으면 FEM 재실행 없이 다시 그릴 수 있어야 한다.

축·제목은 영문 고정이다. 한글 폰트 탐색 실패 시의 깨짐을 원천 차단한다.
백엔드는 강제하지 않는다 — headless 호출자(scripts/run_roadmap.py)가 Agg를 정한다.
"""
import csv
import os

import matplotlib.pyplot as plt

# (CSV 컬럼, 축 라벨, 소수 자릿수)
PANELS = (
    ("Jsc", "Jsc [mA/cm$^2$]", 2),
    ("Voc", "Voc [V]", 3),
    ("FF", "FF [%]", 2),
    ("Eff", "Efficiency [%]", 2),
)

_LINE = "#1a237e"
_BASE = "#c0392b"


def _read_rows(csv_path):
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"빈 CSV — 그릴 케이스가 없다: {csv_path}")
    rows.sort(key=lambda r: int(r["case_index"]))
    return rows


def plot_roadmap(csv_path, png_path=None):
    """roadmap CSV → 2×2 패널 PNG. 저장 경로를 반환한다."""
    rows = _read_rows(csv_path)
    if png_path is None:
        png_path = os.path.splitext(csv_path)[0] + ".png"

    labels = [r["label"] for r in rows]
    x = range(len(rows))

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, (col, ylabel, ndigits) in zip(axes.ravel(), PANELS):
        y = [float(r[col]) for r in rows]
        base = y[0]

        ax.plot(x, y, "o-", color=_LINE, lw=2, ms=7, zorder=3)
        ax.axhline(base, ls="--", lw=1.2, color=_BASE, alpha=0.7, zorder=1)
        ax.text(len(rows) - 0.5, base, f" baseline {base:.{ndigits}f}",
                fontsize=8, color=_BASE, va="bottom", ha="right")

        for xi, yi in zip(x, y):
            ax.annotate(f"{yi:.{ndigits}f}", (xi, yi), textcoords="offset points",
                        xytext=(0, 9), ha="center", fontsize=8.5,
                        fontweight="bold", color=_LINE)
            if xi > 0:
                d = yi - base
                ax.annotate(f"{d:+.{ndigits}f}", (xi, yi),
                            textcoords="offset points", xytext=(0, -16),
                            ha="center", fontsize=8,
                            color=("#1b5e20" if d >= 0 else "#b71c1c"))

        # 세로 여백. baseline 점은 정의상 기준선 위에 놓이므로, 자동 스케일에
        # 맡기면 그 값 라벨이 파선과 겹치고 델타 라벨이 연결선에 얹힌다.
        lo, hi = min(y), max(y)
        span = (hi - lo) or (abs(hi) * 0.01 or 1.0)
        ax.set_ylim(lo - span * 0.35, hi + span * 0.30)

        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=9, rotation=12, ha="right")
        ax.set_xlim(-0.5, len(rows) - 0.5)
        ax.grid(True, alpha=0.2, axis="y")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        title = ylabel.split(" [")[0]
        if col == "Eff":
            title += f"   (total {y[-1] - base:+.{ndigits}f})"
        ax.set_title(title, fontweight="bold", fontsize=11)

    fig.suptitle("Efficiency improvement roadmap", fontweight="bold", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    return png_path
