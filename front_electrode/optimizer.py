"""Optimizer — 전면전극 grid search (2단계 분리).

승인된 접근(Phase 0 실측 근거): 풀-M10 FEM은 1조합 ≈17분이라 4-파라미터
grid search 불가. 파라미터를 물리적 성격으로 나눠 각자 맞는 곳에서 최적화한다.

  Stage 1 (작은 대표 셀, 예 39mm): finger width × finger pitch 만 스윕.
     버스바는 대표값 하나로 고정. 프랙셔널 손실은 pitch 지배 → 최적 finger
     설계가 셀 크기에 거의 불변. 대표 셀은 버스바 간격의 3배 이상을 담아야
     finger 저항이 실제 M10과 맞는다(사용자 지시).
  Stage 2 (풀 M10): Stage 1의 최적 finger 설계를 고정하고 busbar number ×
     busbar width 만 스윕. 버스바 개수 이득(L_seg = W/n_bb)은 셀 크기에
     비례하는 절대 길이라 작은 셀로 재현 불가 → 반드시 풀 M10에서 확정.

이 모듈은 새 물리/새 효율식을 만들지 않는다. adapter.evaluate_existing_simulation
(기존 엔진 래퍼)을 반복 호출하고, 기존 total_loss/efficiency로 정렬만 한다.

정수 핑거 처리: 엔진 관례(finger_spacing 모드 → n_f = round(L/s)−1, 실제 pitch =
L/(n_f+1) 재계산)를 그대로 따른다. 결과에는 **실제 실현된 n_fingers와 pitch**를
기록한다. Round-trip 재입력은 실제 n_fingers(정수)로 하여 지오메트리를 정확히
재현한다.
"""
import csv
import itertools

from .adapter import evaluate_existing_simulation


# ── 물성 시나리오 (Phase 2 헤드라인 & 엔진 기본 병행) ──────────────
# 헤드라인: 본 연구 실측 전극 비저항 (저온 가압소결 90°C/30min/5MPa).
SCENARIO_MEASURED = {
    "label": "measured (rho=4.22 uohm.cm, KIST low-T sinter 90C/30min/5MPa)",
    "rho_bulk_uohm_cm": 4.22,
}
# 엔진 기본값: before-pressing Ag 페이스트 벌크 비저항 13.22 uohm.cm (rho=None → 엔진값 사용).
SCENARIO_ENGINE_DEFAULT = {
    "label": "engine default (rho=13.22 uohm.cm, before-pressing)",
    "rho_bulk_uohm_cm": None,
}


def _objective_value(result, objective):
    """정렬 기준값. total_loss는 최소화, efficiency는 최대화(부호 반전)."""
    if objective == "efficiency":
        return -result["results"]["efficiency"]
    return result["results"]["total_loss"]


def _sweep(fest, grid_list, *, scenario, recovery_factor, mode, npts,
           axis_segments_override, target_nodes, objective, progress, stage):
    """grid_list의 각 파라미터 조합을 adapter로 평가 후 objective로 정렬."""
    results = []
    n = len(grid_list)
    label = (scenario or {}).get("label", "engine_default")
    for i, grid in enumerate(grid_list):
        out = evaluate_existing_simulation(
            fest, grid, scenario=scenario, busbar_recovery_factor=recovery_factor,
            mode=mode, npts=npts, axis_segments_override=axis_segments_override,
            target_nodes=target_nodes)
        out["scenario_label"] = label
        results.append(out)
        if progress is not None:
            progress(i + 1, n, out)
    results.sort(key=lambda r: _objective_value(r, objective))
    return {
        "stage": stage,
        "objective": objective,
        "scenario_label": label,
        "results": results,
        "best": results[0] if results else None,
    }


def optimize_fingers(fest, *, cell_mm=39.0, finger_widths_um, finger_pitches_mm,
                     busbar_number=3, busbar_width_mm=0.3, n_probe_points=0,
                     scenario=None, recovery_factor=0.0, mode="tandem", npts=14,
                     axis_segments_override=None, target_nodes=None,
                     objective="total_loss", progress=None):
    """Stage 1 — 소셀에서 finger width × pitch 스윕 (버스바 대표값 고정)."""
    grid_list = []
    for wf_um, pitch_mm in itertools.product(finger_widths_um, finger_pitches_mm):
        grid_list.append(dict(
            cell_w_mm=cell_mm, cell_h_mm=cell_mm,
            finger_spacing_mm=pitch_mm, w_finger_um=wf_um,
            n_busbars=busbar_number, w_busbar_mm=busbar_width_mm,
            n_probe_points=n_probe_points))
    return _sweep(fest, grid_list, scenario=scenario, recovery_factor=recovery_factor,
                  mode=mode, npts=npts, axis_segments_override=axis_segments_override,
                  target_nodes=target_nodes, objective=objective, progress=progress,
                  stage="fingers")


def optimize_busbars(fest, *, cell_mm=182.0, finger_width_um, finger_pitch_mm,
                     n_busbars_list, busbar_widths_mm, n_probe_points=10,
                     scenario=None, recovery_factor=0.0, mode="tandem", npts=14,
                     axis_segments_override=None, target_nodes=None,
                     objective="total_loss", progress=None):
    """Stage 2 — 풀 M10에서 finger 고정 + busbar number × width 스윕."""
    grid_list = []
    for n_bb, w_bb in itertools.product(n_busbars_list, busbar_widths_mm):
        grid_list.append(dict(
            cell_w_mm=cell_mm, cell_h_mm=cell_mm,
            finger_spacing_mm=finger_pitch_mm, w_finger_um=finger_width_um,
            n_busbars=n_bb, w_busbar_mm=w_bb, n_probe_points=n_probe_points))
    return _sweep(fest, grid_list, scenario=scenario, recovery_factor=recovery_factor,
                  mode=mode, npts=npts, axis_segments_override=axis_segments_override,
                  target_nodes=target_nodes, objective=objective, progress=progress,
                  stage="busbars")


def roundtrip_check(fest, best, *, scenario=None, recovery_factor=0.0, mode="tandem",
                    npts=14, axis_segments_override=None, target_nodes=None):
    """최적 조건을 엔진에 '직접 재입력'했을 때 동일한 손실·효율이 나오는지 확인.

    실제 실현된 n_fingers(정수)로 재입력해 지오메트리를 정확히 재현한다.
    Returns (ok, reeval_result, best_result).
    """
    p = best["parameters"]
    grid = dict(
        cell_w_mm=p["cell_w_mm"], cell_h_mm=p["cell_h_mm"],
        n_fingers=int(p["n_fingers"]), w_finger_um=p["finger_width_um"],
        n_busbars=int(p["busbar_number"]), w_busbar_mm=p["busbar_width_mm"],
        n_probe_points=int(p["n_probe_points"]))
    re = evaluate_existing_simulation(
        fest, grid, scenario=scenario, busbar_recovery_factor=recovery_factor,
        mode=mode, npts=npts, axis_segments_override=axis_segments_override,
        target_nodes=target_nodes)
    ok = (re["results"]["total_loss"] == best["results"]["total_loss"]
          and re["results"]["efficiency"] == best["results"]["efficiency"])
    return ok, re, best


def export_csv(opt_result, path):
    """스윕 전체 결과를 CSV로 저장 (Griddler 수동 교차검증용 — 각 조합의 전체
    입력 파라미터가 명확히 export된다)."""
    rows = []
    for r in opt_result["results"]:
        row = dict(r["parameters"])
        row.update(r["results"])
        row["scenario_label"] = r.get("scenario_label", "")
        row["nodes"] = r["meta"]["nodes"]
        row["mode"] = r["meta"]["mode"]
        rows.append(row)
    if not rows:
        raise ValueError("빈 결과 — export할 조합이 없음")
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return path
