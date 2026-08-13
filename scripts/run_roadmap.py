# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""roadmap 러너 CLI — 시나리오 JSON → CSV 누적 → 4-panel PNG.

  python scripts/run_roadmap.py --scenario scripts/scenarios/unist_tco.json
  python scripts/run_roadmap.py --scenario ... --resume       # 중단 후 재개
  python scripts/run_roadmap.py --scenario ... --ax 60        # 빠른 미리보기
  python scripts/run_roadmap.py --scenario ... --plot-only    # CSV만으로 재작도

주의: 이 도구는 **탐색하지 않는다.** 최적 설계는 optimize_grid로 먼저 구해
시나리오 파일에 옮겨 적는다 (스펙 §2의 2단계 워크플로우).

풀 M10은 1케이스 ≈17분이다. 먼저 --ax 60으로 구조를 확인할 것.
"""
import argparse
import os
import sys
import time

import matplotlib
matplotlib.use("Agg")           # headless — GUI 없이 PNG만 만든다

# 헤드리스 로그 안전: Windows에서 stdout이 리다이렉트되면 cp949가 되어
# 비-cp949 문자 print가 UnicodeEncodeError로 죽는다 (optimize_m10.py와 동일 처리).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "tests"))
sys.path.insert(0, _ROOT)
import conftest  # noqa: E402

from front_electrode import (  # noqa: E402
    expand_cases,
    load_scenario,
    plot_roadmap,
    run_roadmap,
)


def _progress(idx, total, row):
    print(f"  [{idx + 1}/{total}] {row['label']:<24} "
          f"Jsc={row['Jsc']:.2f} Voc={row['Voc']:.4f} "
          f"FF={row['FF']:.2f} Eff={row['Eff']:.3f}  "
          f"({row['elapsed_s']}s, {row['nodes']} nodes) -> CSV append",
          flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True, help="시나리오 JSON 경로")
    ap.add_argument("--csv", default=None,
                    help="출력 CSV (기본: 시나리오와 같은 basename의 .csv)")
    ap.add_argument("--png", default=None, help="출력 PNG (기본: CSV와 같은 basename)")
    ap.add_argument("--resume", action="store_true", help="완료 케이스 건너뜀")
    ap.add_argument("--ax", type=int, default=None,
                    help="axis_segments_override — 빠른 미리보기용 (target_nodes 무시)")
    ap.add_argument("--no-plot", action="store_true", help="PNG 생성 생략")
    ap.add_argument("--plot-only", action="store_true",
                    help="FEM 재실행 없이 기존 CSV로 그림만 다시 그린다")
    args = ap.parse_args()

    sc = load_scenario(args.scenario)
    csv_path = args.csv or (os.path.splitext(args.scenario)[0] + ".csv")

    if args.plot_only:
        print(f"plot-only: {csv_path} -> {plot_roadmap(csv_path, args.png)}")
        return

    fest = conftest._load_fest()
    cases = expand_cases(sc)
    print(f"2L-FEST build {fest.__build__['version']} | "
          f"scenario: {sc['name']} ({sc['_meta']['file']} "
          f"sha {sc['_meta']['sha256']})")
    print(f"  {len(cases)}개 케이스 (baseline 포함), CSV: {csv_path}")
    if args.ax is None:
        print("  ⚠ 풀 해상도 실행 — 풀 M10은 1케이스 ≈17분. "
              "구조 확인은 --ax 60을 먼저.")

    t0 = time.time()
    rows = run_roadmap(fest, sc, csv_path, resume=args.resume,
                       axis_segments_override=args.ax, progress=_progress)
    print(f"  {len(rows)}개 실행, {time.time() - t0:.0f}s")

    if not args.no_plot:
        print(f"  PNG: {plot_roadmap(csv_path, args.png)}")


if __name__ == "__main__":
    main()
