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

from .roadmap import DEFAULT_FLAT_THRESHOLDS

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


def _thresholds_from_rows(rows):
    """CSV의 flat_thresh_* 컬럼에서 임계값을 읽는다. 없으면 기본값."""
    out = dict(DEFAULT_FLAT_THRESHOLDS)
    for key in out:
        raw = rows[0].get("flat_thresh_" + key)
        if raw not in (None, ""):
            out[key] = float(raw)
    return out


def _record_applied(csv_path, rows, applied):
    """조건 2 (2/2): 임계 적용 여부를 CSV에 덧쓴다 (원자적 재작성).

    적용 여부는 전 케이스의 총 변화를 봐야 정해지므로 append 시점에는 알 수
    없다. 실행이 끝난 뒤 한 번 다시 쓰는 것은 optimize_m10.py의 _sort_csv와
    같은 패턴이며, append+flush의 크래시 안전성을 해치지 않는다.
    """
    for row in rows:
        for key, is_flat in applied.items():
            row["flat_applied_" + key] = is_flat
    tmp = csv_path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        fh.flush()
    os.replace(tmp, csv_path)


def plot_roadmap(csv_path, png_path=None):
    """roadmap CSV → 2×2 패널 PNG. 저장 경로를 반환한다.

    총 변화가 패널별 임계(flat_thresh_*) 미만이면 y축을 baseline ± 임계로
    고정해 **실제로 평평하게** 그린다. 자동 스케일에 맡기면 +0.0008 같은
    무의미한 변화가 화면을 가득 채워 독자를 오도한다.

    부작용: 임계 적용 여부를 flat_applied_* 컬럼으로 CSV에 덧쓴다.
    """
    rows = _read_rows(csv_path)
    thresholds = _thresholds_from_rows(rows)
    applied = {}
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

        # 임계 미만이면 y축을 baseline ± 임계로 고정 → 실제로 평평하게 보인다.
        thr = thresholds[col]
        is_flat = (max(y) - min(y)) < thr
        applied[col] = is_flat
        if is_flat:
            lo, hi = base - thr, base + thr
        else:
            lo, hi = min(y), max(y)

        # 세로 여백. baseline 점은 정의상 기준선 위에 놓이므로, 자동 스케일에
        # 맡기면 그 값 라벨이 파선과 겹치고 델타 라벨이 연결선에 얹힌다.
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
        if is_flat:
            # 축이 데이터가 아니라 임계로 정해졌음을 밝힌다. 숨기면 독자가
            # "왜 이 축만 이렇게 넓지"를 알 수 없다.
            title += f"   [flat: |Δ| < {thr:g}]"
        ax.set_title(title, fontweight="bold", fontsize=11)

    fig.suptitle("Efficiency improvement roadmap", fontweight="bold", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(png_path, dpi=150)
    plt.close(fig)

    _record_applied(csv_path, rows, applied)
    return png_path
