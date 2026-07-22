"""M10 전면전극 2단계 최적화 — headless 드라이버 (GUI 불필요).

Stage 1 (39mm 대표 소셀): finger width × pitch 스윕 → 최적 finger 설계 확정.
Stage 2 (풀 M10 182mm): 위 finger 고정 + busbar number × width 스윕.
물성 시나리오 2종 병행: measured(rho=4.22, KIST 실측) / engine default(13.22).

  python scripts/optimize_m10.py --stage fingers            # 빠름(39mm, 수 분)
  python scripts/optimize_m10.py --stage fingers --quick    # 아주 빠름(격자 축소)
  python scripts/optimize_m10.py --stage busbars --wf 25 --pitch 1.6   # 느림(M10, ~시간)

엔진은 conftest 하네스로 headless 로드(mock tkinter + Agg). 새 물리/효율식 없음.
"""
import os
import sys
import csv
import time
import itertools
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "tests"))
sys.path.insert(0, _ROOT)
import conftest  # noqa: E402
from front_electrode import (  # noqa: E402
    optimize_fingers, roundtrip_check, export_csv,
    evaluate_existing_simulation,
    SCENARIO_MEASURED, SCENARIO_ENGINE_DEFAULT,
)

fest = conftest._load_fest()

# ITRPV 15/16판 기반 초기 탐색범위 (Phase 3 preset와 일치 예정 — 사용자 조정 가능)
FINGER_WIDTHS_UM = [15.0, 20.0, 25.0, 30.0]
FINGER_PITCHES_MM = [1.0, 1.4, 1.8, 2.2]
BUSBAR_NUMBERS = [12, 16, 18, 20]
BUSBAR_WIDTHS_MM = [0.20, 0.30]


def _progress(prefix):
    t0 = [time.time()]

    def cb(i, n, out):
        dt = time.time() - t0[0]
        t0[0] = time.time()
        p = out["parameters"]
        print(f"  [{prefix} {i}/{n}] {dt:5.1f}s  "
              f"wf={p['finger_width_um']:.0f}um pitch={p['finger_pitch_mm']:.2f}mm "
              f"nf={p['n_fingers']} nbb={p['busbar_number']} wbb={p['busbar_width_mm']:.2f}mm "
              f"| total_loss={out['results']['total_loss']:.4f} eff={out['results']['efficiency']:.3f}"
              f" nodes={out['meta']['nodes']}", flush=True)
    return cb


def _print_best(tag, opt):
    b = opt["best"]["parameters"]
    r = opt["best"]["results"]
    print(f"\n>>> BEST [{tag}] ({opt['scenario_label']})")
    print(f"    finger: w={b['finger_width_um']:.0f}um pitch={b['finger_pitch_mm']:.2f}mm nf={b['n_fingers']}")
    print(f"    busbar: n={b['busbar_number']} w={b['busbar_width_mm']:.2f}mm")
    print(f"    total_loss={r['total_loss']:.4f} mW/cm2  efficiency={r['efficiency']:.3f}%  "
          f"(optical={r['optical_loss']:.4f} electrical={r['electrical_loss']:.4f})")


def run_fingers(scenario, quick, recovery, ax):
    widths = [20.0, 30.0] if quick else FINGER_WIDTHS_UM
    pitches = [1.4, 2.0] if quick else FINGER_PITCHES_MM
    print(f"\n=== Stage 1 (fingers, 39mm) — {scenario['label']} ===")
    print(f"    widths={widths}um  pitches={pitches}mm  = {len(widths)*len(pitches)} combos")
    t0 = time.time()
    opt = optimize_fingers(
        fest, cell_mm=39.0, finger_widths_um=widths, finger_pitches_mm=pitches,
        busbar_number=3, busbar_width_mm=0.3, scenario=scenario,
        recovery_factor=recovery, axis_segments_override=ax, npts=8,
        progress=_progress("fingers"))
    print(f"    stage1 total {time.time()-t0:.0f}s")
    _print_best("fingers", opt)
    ok, _, _ = roundtrip_check(fest, opt["best"], scenario=scenario,
                               recovery_factor=recovery, axis_segments_override=ax, npts=8)
    print(f"    round-trip: {'OK (동일)' if ok else 'FAIL (불일치)'}")
    out_csv = os.path.join(_HERE, f"opt_fingers_{'quick' if quick else 'full'}.csv")
    export_csv(opt, out_csv)
    print(f"    CSV: {out_csv}")
    return opt


def _csv_key(n_bb, w_bb):
    return (int(n_bb), round(float(w_bb), 4))


def run_busbars(scenario, wf, pitch, recovery, resume=False, csv_path=None):
    """Stage 2 — 풀 M10 busbar 스윕 (장시간 실행 안전장치 포함).

    안전장치(드라이버 전용 — optimizer/adapter는 무수정):
      (a) 조합 1개 끝날 때마다 CSV에 즉시 append + flush → 중간 크래시에도 보존
      (b) --resume: 기존 CSV의 완료 조합(n_bb, w_bb)을 건너뜀
      (c) 조합별 timestamp + 소요초 기록
    """
    if csv_path is None:
        # 시나리오별 CSV 분리 — 양 시나리오가 한 파일에 섞이거나 --resume 키가
        # 시나리오를 넘나들며 잘못 skip되는 것을 방지.
        tag = "measured" if "measured" in scenario["label"] else "default"
        csv_path = os.path.join(_HERE, f"opt_busbars_m10_{tag}.csv")
    print(f"\n=== Stage 2 (busbars, M10 182mm) — {scenario['label']} ===")
    print(f"    finger fixed: w={wf}um pitch={pitch}mm | nbb={BUSBAR_NUMBERS} wbb={BUSBAR_WIDTHS_MM}")
    print("    finger 채택 근거: 효율 최적은 wf15um/pitch1.39mm이나 인쇄 현실성(ITRPV상 "
          "15um는 2035 목표, 현 양산 ~30um대) 고려해 wf20um/pitch1.77mm 채택 — 효율차 ~0.003%abs.")
    print(f"    ⚠ 풀 M10: 1조합 ≈17분. CSV(append): {csv_path}")
    print("    목적함수=efficiency. total_loss는 recovery OFF와 25% 반영본을 별도 컬럼 병기.")

    combos = list(itertools.product(BUSBAR_NUMBERS, BUSBAR_WIDTHS_MM))
    done = set()
    if resume and os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
        with open(csv_path, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                done.add(_csv_key(float(row["busbar_number"]), row["busbar_width_mm"]))
        print(f"    resume: 완료 {len(done)}개 조합 건너뜀")

    header_written = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    for n_bb, w_bb in combos:
        if _csv_key(n_bb, w_bb) in done:
            print(f"    skip {n_bb}BB {w_bb}mm (완료됨)", flush=True)
            continue
        grid = dict(cell_w_mm=182.0, cell_h_mm=182.0, finger_spacing_mm=pitch,
                    w_finger_um=wf, n_busbars=n_bb, w_busbar_mm=w_bb, n_probe_points=10)
        t0 = time.time()
        # efficiency 목적: 엔진은 recovery=0(base)로 실행(효율은 recovery 무관).
        out = evaluate_existing_simulation(
            fest, grid, scenario=scenario, busbar_recovery_factor=0.0,
            mode="tandem", npts=14, target_nodes=82000)
        dt = time.time() - t0
        # recovery 25%(KIST 가정) 반영 total_loss를 별도 컬럼으로 병기 —
        # 25% 복원이 busbar 개수 선택에 주는 영향을 보기 위함. 회수는 busbar
        # shading line-item에만 적용(회수광 = raw_busbar × 0.25 × Jmpp × Vmpp).
        rec = 0.25
        raw_bb = out["results"]["raw_busbar_shading"]
        jmpp = out["engine_raw"]["Jmpp"]
        vmpp = out["engine_raw"]["Vmpp"]
        recovered_power = raw_bb * rec * jmpp * vmpp
        row = dict(out["parameters"])
        row.update(out["results"])              # total_loss = recovery OFF(base)
        row["recovered_busbar_light_25"] = raw_bb * rec
        row["effective_busbar_shading_25"] = raw_bb * (1.0 - rec)
        row["optical_loss_rec25"] = out["results"]["optical_loss"] - recovered_power
        row["total_loss_rec25"] = out["results"]["total_loss"] - recovered_power
        row["scenario_label"] = scenario["label"]
        row["nodes"] = out["meta"]["nodes"]
        row["mode"] = out["meta"]["mode"]
        row["elapsed_s"] = round(dt, 1)
        row["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(csv_path, "a", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if not header_written:
                w.writeheader()
                header_written = True
            w.writerow(row)
            fh.flush()
        print(f"    [busbars {n_bb}BB {w_bb}mm] {dt:.0f}s "
              f"total_loss={out['results']['total_loss']:.4f} "
              f"eff={out['results']['efficiency']:.3f} → CSV append", flush=True)

    # 요약: CSV 재읽기 → efficiency 최대 조합 보고
    best = None
    with open(csv_path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            e = float(row["efficiency"])
            if best is None or e > best[0]:
                best = (e, row)
    if best is not None:
        r = best[1]
        print(f"\n>>> BEST [busbars, by efficiency] nbb={r['busbar_number']} "
              f"wbb={r['busbar_width_mm']}mm eff={r['efficiency']}")
        print(f"    total_loss(recovery OFF)={r['total_loss']}  "
              f"total_loss(recovery 25%)={r.get('total_loss_rec25','-')}")
    return csv_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["fingers", "busbars", "both"], default="fingers")
    ap.add_argument("--quick", action="store_true", help="격자 축소(빠른 데모)")
    ap.add_argument("--recovery", type=float, default=0.0, help="busbar recovery factor")
    ap.add_argument("--ax", type=int, default=110, help="39mm 소셀 axis_segments_override")
    ap.add_argument("--scenario", choices=["measured", "default", "both"], default="measured")
    ap.add_argument("--wf", type=float, default=25.0, help="stage2 고정 finger width [um]")
    ap.add_argument("--pitch", type=float, default=1.6, help="stage2 고정 finger pitch [mm]")
    ap.add_argument("--resume", action="store_true",
                    help="stage2: 기존 CSV의 완료 조합을 건너뜀(장시간 실행 재개)")
    args = ap.parse_args()

    scenarios = {"measured": [SCENARIO_MEASURED], "default": [SCENARIO_ENGINE_DEFAULT],
                 "both": [SCENARIO_MEASURED, SCENARIO_ENGINE_DEFAULT]}[args.scenario]

    print(f"2L-FEST build {fest.__build__['version']} | scenarios={[s['label'] for s in scenarios]}")
    for sc in scenarios:
        if args.stage in ("fingers", "both"):
            run_fingers(sc, args.quick, args.recovery, args.ax)
        if args.stage in ("busbars", "both"):
            run_busbars(sc, args.wf, args.pitch, args.recovery, resume=args.resume)


if __name__ == "__main__":
    main()
