"""M10 전면전극 2단계 최적화 — headless 드라이버 (GUI 불필요).

Stage 1 (39mm 대표 소셀): finger width × pitch 스윕 → 최적 finger 설계 확정.
Stage 2 (풀 M10 182mm): 위 finger 고정 + busbar number × width 스윕.
물성 시나리오: pressed(rho=4.22, 90°C/30min/5MPa) / as_cured(rho=9, 동일 열처리
무가압 — 가압 효과 분리용 대조군) / default(엔진 GridDesign 기본, as-printed).

Stage grid (v28.46): 2단계 분리의 커플링 한계(docs §5)를 닫기 위한 **결합 스윕** —
풀 M10에서 finger pitch/width와 busbar를 동시에 스윕한다. 조합수 = 곱이라 비싸다.

  python scripts/optimize_m10.py --stage fingers            # 빠름(39mm, 수 분)
  python scripts/optimize_m10.py --stage fingers --quick    # 아주 빠름(격자 축소)
  python scripts/optimize_m10.py --stage busbars --wf 25 --pitch 1.6   # 느림(M10, ~시간)
  python scripts/optimize_m10.py --stage grid --pitch-list 1.77,2.2,2.6 \
      --nbb 6,8,10 --wbb 0.20 --edge-margin 1.0 --workers 5   # 결합(M10, 매우 느림)

엔진은 conftest 하네스로 headless 로드(mock tkinter + Agg). 새 물리/효율식 없음.
"""
import os
import sys
import csv
import time
import itertools
import argparse
import multiprocessing as mp

# 헤드리스 로그 안전: Windows에서 stdout이 파일/파이프로 리다이렉트되면 로케일
# 인코딩(cp949)이 되어 em-dash 등 비-cp949 문자 print가 UnicodeEncodeError로
# 죽는다(장시간 stage2를 로그로 남길 때 치명적). utf-8로 재구성.
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
    optimize_fingers, roundtrip_check, export_csv,
    evaluate_existing_simulation,
    SCENARIO_MEASURED, SCENARIO_AS_CURED, SCENARIO_ENGINE_DEFAULT,
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


def run_fingers(scenario, quick, recovery, ax, edge_margin=0.0):
    widths = [20.0, 30.0] if quick else FINGER_WIDTHS_UM
    pitches = [1.4, 2.0] if quick else FINGER_PITCHES_MM
    print(f"\n=== Stage 1 (fingers, 39mm) — {scenario['label']} ===")
    print(f"    widths={widths}um  pitches={pitches}mm  = {len(widths)*len(pitches)} combos"
          f"  edge_margin={float(edge_margin or 0.0):g}mm")
    t0 = time.time()
    opt = optimize_fingers(
        fest, cell_mm=39.0, finger_widths_um=widths, finger_pitches_mm=pitches,
        busbar_number=3, busbar_width_mm=0.3, scenario=scenario,
        edge_margin_mm=edge_margin,
        recovery_factor=recovery, axis_segments_override=ax, npts=8,
        progress=_progress("fingers"))
    print(f"    stage1 total {time.time()-t0:.0f}s")
    _print_best("fingers", opt)
    ok, _, _ = roundtrip_check(fest, opt["best"], scenario=scenario,
                               recovery_factor=recovery, axis_segments_override=ax, npts=8)
    print(f"    round-trip: {'OK (동일)' if ok else 'FAIL (불일치)'}")
    suffix = "quick" if quick else "full"
    if float(edge_margin or 0.0) > 0.0:
        suffix += f"_edge{float(edge_margin):g}mm"
    out_csv = os.path.join(_HERE, f"opt_fingers_{suffix}.csv")
    export_csv(opt, out_csv)
    print(f"    CSV: {out_csv}")
    return opt


def _csv_key(n_bb, w_bb):
    return (int(n_bb), round(float(w_bb), 4))


def _eval_combo(task):
    """워커 진입점 — 모듈 레벨 함수여야 multiprocessing(spawn) picklable.

    각 워커는 spawn으로 이 모듈을 재import → 최상단 ``fest = conftest._load_fest()``
    가 실행되어 **프로세스마다 독립 엔진**을 로드한다(상태 공유·warm-start 누수 없음).
    한 조합(busbar 개수×폭)을 평가해 CSV 1행 dict를 반환. 엔진/효율식 무수정.

    task: dict(n_bb, w_bb, wf, pitch, scenario, target_nodes, npts, edge_margin)
    """
    n_bb = int(task["n_bb"])
    w_bb = float(task["w_bb"])
    grid = dict(cell_w_mm=182.0, cell_h_mm=182.0, finger_spacing_mm=task["pitch"],
                w_finger_um=task["wf"], n_busbars=n_bb, w_busbar_mm=w_bb,
                n_probe_points=10,
                edge_margin_mm=float(task.get("edge_margin", 0.0) or 0.0))
    if task.get("rho_bulk") is not None:      # ρ_L 조합별 override(as-cured vs 가압)
        grid["rho_bulk_uohm_cm"] = float(task["rho_bulk"])
    t0 = time.time()
    out = evaluate_existing_simulation(
        fest, grid, scenario=task["scenario"], busbar_recovery_factor=0.0,
        mode="tandem", npts=int(task["npts"]), target_nodes=int(task["target_nodes"]))
    dt = time.time() - t0
    # recovery 25%(KIST 가정) 반영 total_loss 병기 — 순차 버전과 동일 산식.
    rec = 0.25
    raw_bb = out["results"]["raw_busbar_shading"]
    jmpp = out["engine_raw"]["Jmpp"]
    vmpp = out["engine_raw"]["Vmpp"]
    recovered_power = raw_bb * rec * jmpp * vmpp
    row = dict(out["parameters"])
    row.update(out["results"])                  # total_loss = recovery OFF(base)
    row["recovered_busbar_light_25"] = raw_bb * rec
    row["effective_busbar_shading_25"] = raw_bb * (1.0 - rec)
    row["optical_loss_rec25"] = out["results"]["optical_loss"] - recovered_power
    row["total_loss_rec25"] = out["results"]["total_loss"] - recovered_power
    # recovery 반영 efficiency — adapter와 동일 산식(Pin은 엔진 출력에서 역산).
    _pin = (out["engine_raw"]["Pmpp"] / out["engine_raw"]["Eff"] * 100.0
            ) if out["engine_raw"].get("Eff") else 100.0
    row["efficiency_rec25"] = out["engine_raw"]["Eff"] + recovered_power / _pin * 100.0
    # 엔진 손실 분해(engine_raw) — 원본은 print만 했으나 CSV 컬럼으로 병기(유용).
    er = out["engine_raw"]
    row["Pe"] = er["Pe"]
    row["Pf_finger"] = er["Pf_finger"]
    row["Pf_busbar"] = er["Pf_busbar"]
    row["Pc"] = er["Pc"]
    row["P_shade"] = er["P_shade"]
    row["FF"] = er["FF"]            # 보고서에 FF가 필요 — v28.48에서 CSV에 추가
    row["Jsc"] = er["Jsc"]
    row["Voc"] = er["Voc"]
    row["scenario_label"] = task["scenario"]["label"]
    row["nodes"] = out["meta"]["nodes"]
    row["mode"] = out["meta"]["mode"]
    row["elapsed_s"] = round(dt, 1)             # 비결정(워커 스케줄) — 비교 시 제외
    row["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")  # 비결정 — 비교 시 제외
    # sweep_key: grid stage 전용 재개(resume) 키. **입력값** 그대로를 문자열로 박아
    # 둔다 — CSV의 finger_pitch_mm은 정수 핑거 반올림 후 재계산된 *실현* pitch라
    # (입력 1.77 → 실현 1.767) 입력값 매칭에 쓸 수 없기 때문이다.
    # busbars stage는 이 키를 넣지 않는다(기존 CSV 헤더 불변 → append/resume 호환).
    if task.get("sweep_key"):
        row["sweep_key"] = task["sweep_key"]
    return row


# elapsed_s/timestamp는 워커 스케줄·벽시계에 의존 → 병렬==순차 대조 시 제외.
NONDETERMINISTIC_COLS = ("elapsed_s", "timestamp")


def _sort_csv(csv_path):
    """CSV를 (busbar_number, busbar_width_mm) 오름차순으로 재작성(원자적).

    imap_unordered는 완료 순서대로 행을 append하므로 파일 순서가 워커 스케줄에
    의존한다. 실행 종료 후 한 번 정렬해 **스케줄링과 무관하게 재현 가능한** 순서로
    고정한다(값 자체는 엔진 결정성으로 이미 동일)."""
    if not (os.path.exists(csv_path) and os.path.getsize(csv_path) > 0):
        return
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not rows:
        return
    rows.sort(key=lambda r: _csv_key(float(r["busbar_number"]), r["busbar_width_mm"]))
    tmp = csv_path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
        fh.flush()
    os.replace(tmp, csv_path)


def run_busbars(scenario, wf, pitch, recovery, resume=False, csv_path=None,
                nbb_list=None, wbb_list=None, workers=1,
                target_nodes=82000, npts=14, edge_margin=0.0):
    """Stage 2 — 풀 M10 busbar 스윕 (장시간 실행 안전장치 + 병렬 실행).

    안전장치(드라이버 전용 — optimizer/adapter는 무수정):
      (a) 조합 1개 끝날 때마다 CSV에 즉시 append + flush → 중간 크래시에도 보존
      (b) --resume: 기존 CSV의 완료 조합(n_bb, w_bb)을 건너뜀
      (c) 조합별 timestamp + 소요초 기록

    병렬(workers>1): 조합을 multiprocessing spawn 풀에 분배. 각 워커는 독립
    프로세스로 엔진을 로드(상태 공유 없음). **CSV 기록은 부모 프로세스만** 수행
    (imap_unordered로 완료분을 받아 append) → 동시 쓰기 충돌 없음. 완료 후
    _sort_csv로 (n_bb,w_bb) 정렬해 스케줄링과 무관하게 재현 가능한 파일로 고정.
    엔진 결정성 덕에 병렬 결과 == 순차 결과(elapsed_s/timestamp 제외).
    """
    if csv_path is None:
        # 시나리오별 CSV 분리 — 양 시나리오가 한 파일에 섞이거나 --resume 키가
        # 시나리오를 넘나들며 잘못 skip되는 것을 방지.
        # edge_margin도 같은 이유로 파일명에 넣는다: resume 키는 (n_bb, w_bb)뿐이라
        # 마진이 다른 실행이 같은 파일을 쓰면 **다른 설계의 결과를 완료로 착각해
        # 건너뛴다**(silent-wrong). margin=0은 기존 파일명 유지(하위호환).
        tag = "measured" if "measured" in scenario["label"] else "default"
        if float(edge_margin or 0.0) > 0.0:
            tag += f"_edge{float(edge_margin):g}mm"
        csv_path = os.path.join(_HERE, f"opt_busbars_m10_{tag}.csv")
    nbb_list = nbb_list if nbb_list is not None else BUSBAR_NUMBERS
    wbb_list = wbb_list if wbb_list is not None else BUSBAR_WIDTHS_MM
    print(f"\n=== Stage 2 (busbars, M10 182mm) — {scenario['label']} ===")
    print(f"    finger fixed: w={wf}um pitch={pitch}mm | nbb={nbb_list} wbb={wbb_list}"
          f" | edge_margin={float(edge_margin or 0.0):g}mm")
    print("    finger 채택 근거: 효율 최적은 wf15um/pitch1.39mm이나 인쇄 현실성(ITRPV상 "
          "15um는 2035 목표, 현 양산 ~30um대) 고려해 wf20um/pitch1.77mm 채택 — 효율차 ~0.003%abs.")
    print(f"    ⚠ 풀 M10: 1조합 ≈17분. CSV(append): {csv_path}")
    print("    목적함수=efficiency. total_loss는 recovery OFF와 25% 반영본을 별도 컬럼 병기.")

    combos = list(itertools.product(nbb_list, wbb_list))
    done = set()
    if resume and os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
        with open(csv_path, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                done.add(_csv_key(float(row["busbar_number"]), row["busbar_width_mm"]))
        print(f"    resume: 완료 {len(done)}개 조합 건너뜀")

    header_written = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0

    # 실행할 조합만 task로 (resume 완료분 제외). 순서는 combos(정렬) 유지.
    pending = []
    for n_bb, w_bb in combos:
        if _csv_key(n_bb, w_bb) in done:
            print(f"    skip {n_bb}BB {w_bb}mm (완료됨)", flush=True)
            continue
        pending.append(dict(n_bb=n_bb, w_bb=w_bb, wf=wf, pitch=pitch,
                            scenario=scenario, target_nodes=target_nodes, npts=npts,
                            edge_margin=edge_margin))

    # CSV 기록은 항상 부모 프로세스에서만 (동시 쓰기 충돌 원천 차단).
    def _append_row(row):
        nonlocal header_written
        with open(csv_path, "a", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if not header_written:
                w.writeheader()
                header_written = True
            w.writerow(row)
            fh.flush()
        print(f"    [busbars {int(row['busbar_number'])}BB {float(row['busbar_width_mm'])}mm] "
              f"{row['elapsed_s']}s total_loss={float(row['total_loss']):.4f} "
              f"eff={float(row['efficiency']):.3f} "
              f"| Pf_busbar={float(row['Pf_busbar']):.4f} Pf_finger={float(row['Pf_finger']):.4f} "
              f"P_shade={float(row['P_shade']):.4f} → CSV append", flush=True)

    n_workers = max(1, int(workers))
    if n_workers <= 1 or len(pending) <= 1:
        if pending:
            print(f"    실행: 순차(workers=1), {len(pending)}조합", flush=True)
        for task in pending:
            _append_row(_eval_combo(task))
    else:
        n_workers = min(n_workers, len(pending))
        print(f"    실행: 병렬 spawn 풀 workers={n_workers}, {len(pending)}조합 "
              f"(각 워커 독립 엔진 로드; CSV는 부모만 기록)", flush=True)
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=n_workers) as pool:
            # imap_unordered: 먼저 끝난 조합부터 부모가 즉시 append+flush(크래시 안전).
            for row in pool.imap_unordered(_eval_combo, pending):
                _append_row(row)

    # 스케줄링과 무관한 재현성 위해 (n_bb, w_bb)로 정렬 고정.
    _sort_csv(csv_path)

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


def _grid_sweep_key(wf, pitch, n_bb, w_bb, edge, rho=None):
    """grid stage resume 키 — 입력값(반올림 전) 기준 문자열."""
    k = (f"wf{float(wf):g}|p{float(pitch):g}|nbb{int(n_bb)}"
         f"|wbb{float(w_bb):g}|e{float(edge):g}")
    if rho is not None:
        k += f"|rho{float(rho):g}"
    return k


def run_grid(scenario, wf_list, pitch_list, nbb_list, wbb_list, edge_margin,
             resume=False, csv_path=None, workers=1, target_nodes=82000, npts=14,
             rho_list=None):
    """결합 스윕 — 풀 M10에서 finger pitch/width와 busbar를 **동시에** 스윕.

    필요성(docs §5): 기존 2단계 분리는 Stage 1(39mm 소셀, 3BB)에서 정한 finger
    최적(wf20/pitch1.77)을 Stage 2에서 고정했다. 그러나 M10 다중 busbar에서는
    finger 세그먼트 길이가 W/n_bb로 짧아져 최적 pitch가 넓은 쪽으로 이동할 수
    있다(v28.43/44 GUI preview에서 pitch~2.2~2.4 관측). 이 드라이버는 그 커플링을
    풀 M10에서 직접 확인한다.

    run_busbars와 동일한 안전장치(조합별 즉시 append+flush, --resume, 병렬 spawn)를
    쓰되, resume 키만 sweep_key(입력값 문자열)로 바꾼다 — 축이 늘어 (n_bb,w_bb)로는
    조합을 구분할 수 없기 때문이다.
    """
    if csv_path is None:
        tag = "measured" if "measured" in scenario["label"] else "default"
        if float(edge_margin or 0.0) > 0.0:
            tag += f"_edge{float(edge_margin):g}mm"
        csv_path = os.path.join(_HERE, f"opt_grid_m10_{tag}.csv")
    rhos = list(rho_list) if rho_list else [None]
    combos = list(itertools.product(wf_list, pitch_list, nbb_list, wbb_list, rhos))
    print(f"\n=== Grid stage (coupled finger×busbar, M10 182mm) — {scenario['label']} ===")
    print(f"    wf={wf_list}um  pitch={pitch_list}mm  nbb={nbb_list}  wbb={wbb_list}mm"
          f"  edge_margin={float(edge_margin or 0.0):g}mm"
          f"  rho_L={rhos if rho_list else '(scenario 기본)'}")
    print(f"    조합 {len(combos)}개 × 풀 M10(1조합 ≈17분). CSV(append): {csv_path}")

    done = set()
    if resume and os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
        with open(csv_path, encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                if row.get("sweep_key"):
                    done.add(row["sweep_key"])
        print(f"    resume: 완료 {len(done)}개 조합 건너뜀")

    header_written = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0
    pending = []
    for wf, pitch, n_bb, w_bb, rho in combos:
        key = _grid_sweep_key(wf, pitch, n_bb, w_bb, edge_margin, rho)
        if key in done:
            print(f"    skip {key} (완료됨)", flush=True)
            continue
        pending.append(dict(n_bb=n_bb, w_bb=w_bb, wf=wf, pitch=pitch,
                            scenario=scenario, target_nodes=target_nodes, npts=npts,
                            edge_margin=edge_margin, sweep_key=key, rho_bulk=rho))

    def _append_row(row):
        nonlocal header_written
        with open(csv_path, "a", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(row.keys()))
            if not header_written:
                w.writeheader()
                header_written = True
            w.writerow(row)
            fh.flush()
        print(f"    [{row['sweep_key']}] {row['elapsed_s']}s "
              f"nf={int(float(row['n_fingers']))} pitch_real={float(row['finger_pitch_mm']):.3f} "
              f"eff={float(row['efficiency']):.4f} "
              f"| Pf_finger={float(row['Pf_finger']):.4f} Pf_busbar={float(row['Pf_busbar']):.4f} "
              f"P_shade={float(row['P_shade']):.4f} → CSV append", flush=True)

    n_workers = max(1, int(workers))
    if n_workers <= 1 or len(pending) <= 1:
        for task in pending:
            _append_row(_eval_combo(task))
    else:
        n_workers = min(n_workers, len(pending))
        print(f"    실행: 병렬 spawn 풀 workers={n_workers}, {len(pending)}조합", flush=True)
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=n_workers) as pool:
            for row in pool.imap_unordered(_eval_combo, pending):
                _append_row(row)

    best = None
    with open(csv_path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            e = float(row["efficiency"])
            if best is None or e > best[0]:
                best = (e, row)
    if best is not None:
        r = best[1]
        print(f"\n>>> BEST [grid, by efficiency] {r.get('sweep_key','')} "
              f"eff={float(r['efficiency']):.4f}%  "
              f"(nf={int(float(r['n_fingers']))} pitch_real={float(r['finger_pitch_mm']):.3f}mm)")
    return csv_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["fingers", "busbars", "grid", "both"],
                    default="fingers")
    ap.add_argument("--quick", action="store_true", help="격자 축소(빠른 데모)")
    ap.add_argument("--recovery", type=float, default=0.0, help="busbar recovery factor")
    ap.add_argument("--ax", type=int, default=110, help="39mm 소셀 axis_segments_override")
    ap.add_argument("--scenario", choices=["measured", "as_cured", "default", "both"],
                    default="measured")
    ap.add_argument("--wf", type=float, default=25.0, help="stage2 고정 finger width [um]")
    ap.add_argument("--pitch", type=float, default=1.6, help="stage2 고정 finger pitch [mm]")
    ap.add_argument("--resume", action="store_true",
                    help="stage2: 기존 CSV의 완료 조합을 건너뜀(장시간 실행 재개)")
    ap.add_argument("--nbb", type=str, default=None,
                    help="stage2 busbar 개수 override, 쉼표구분 (예: 4,6,8,10)")
    ap.add_argument("--wbb", type=str, default=None,
                    help="stage2 busbar 폭[mm] override, 쉼표구분 (예: 0.20)")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                    help="stage2 병렬 워커 수(각 독립 프로세스로 엔진 로드). "
                         "기본=코어수-1. 1이면 순차.")
    ap.add_argument("--target-nodes", dest="target_nodes", type=int, default=82000,
                    help="stage2 M10 메시 목표 노드수(작게 주면 빠른 검증/미리보기).")
    ap.add_argument("--npts", type=int, default=14, help="stage2 calc_iv 스윕 점수")
    ap.add_argument("--csv", dest="csv_path", type=str, default=None,
                    help="결과 CSV 경로 override (기본: scripts/ 아래 시나리오·마진 태그 자동)")
    ap.add_argument("--wf-list", dest="wf_list", type=str, default=None,
                    help="grid stage finger width[um] 목록, 쉼표구분 (기본: --wf 값 1개)")
    ap.add_argument("--pitch-list", dest="pitch_list", type=str, default=None,
                    help="grid stage finger pitch[mm] 목록, 쉼표구분 (기본: --pitch 값 1개)")
    ap.add_argument("--rho-list", dest="rho_list", type=str, default=None,
                    help="grid stage ρ_L[µΩ·cm] 목록, 쉼표구분 (예: 9,4.22 = as-cured vs "
                         "가압소결). 미지정이면 scenario의 물성을 쓴다.")
    ap.add_argument("--edge-margin", dest="edge_margin", type=float, default=0.0,
                    help="엣지 실버-프리 마진[mm] (v28.45 랩미팅 지시; GUI 기본 1.0). "
                         "0=기존 결과와 비트 동일. >0이면 CSV 파일명에 태그가 붙어 "
                         "마진이 다른 실행끼리 --resume이 섞이지 않는다.")
    args = ap.parse_args()
    nbb_list = [int(x) for x in args.nbb.split(",")] if args.nbb else None
    wbb_list = [float(x) for x in args.wbb.split(",")] if args.wbb else None

    scenarios = {"measured": [SCENARIO_MEASURED], "as_cured": [SCENARIO_AS_CURED],
                 "default": [SCENARIO_ENGINE_DEFAULT],
                 "both": [SCENARIO_MEASURED, SCENARIO_AS_CURED]}[args.scenario]

    print(f"2L-FEST build {fest.__build__['version']} | scenarios={[s['label'] for s in scenarios]}")
    for sc in scenarios:
        if args.stage in ("fingers", "both"):
            run_fingers(sc, args.quick, args.recovery, args.ax,
                        edge_margin=args.edge_margin)
        if args.stage in ("busbars", "both"):
            run_busbars(sc, args.wf, args.pitch, args.recovery, resume=args.resume,
                        nbb_list=nbb_list, wbb_list=wbb_list, workers=args.workers,
                        target_nodes=args.target_nodes, npts=args.npts,
                        edge_margin=args.edge_margin, csv_path=args.csv_path)
        if args.stage == "grid":
            run_grid(sc,
                     wf_list=[float(x) for x in args.wf_list.split(",")] if args.wf_list else [args.wf],
                     pitch_list=[float(x) for x in args.pitch_list.split(",")] if args.pitch_list else [args.pitch],
                     nbb_list=nbb_list if nbb_list is not None else BUSBAR_NUMBERS,
                     wbb_list=wbb_list if wbb_list is not None else BUSBAR_WIDTHS_MM,
                     edge_margin=args.edge_margin, resume=args.resume,
                     workers=args.workers, target_nodes=args.target_nodes,
                     npts=args.npts, csv_path=args.csv_path,
                     rho_list=([float(x) for x in args.rho_list.split(",")]
                               if args.rho_list else None))


if __name__ == "__main__":
    main()
