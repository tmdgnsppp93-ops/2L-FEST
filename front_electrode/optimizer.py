# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Optimizer — 전면전극 grid search.

풀-M10 FEM은 1조합 ≈17분이라 무제한 grid search가 불가능하다. 두 갈래를 제공한다.

  optimize_fingers (Stage 1, 작은 대표 셀 예 39mm): finger width × pitch 만 스윕.
     버스바는 대표값 하나로 고정. 프랙셔널 손실은 pitch 지배 → 최적 finger
     설계가 셀 크기에 거의 불변. 대표 셀은 버스바 간격의 3배 이상을 담아야
     finger 저항이 실제 M10과 맞는다(사용자 지시).
  optimize_grid: finger width × pitch × busbar 수 × busbar 폭 × ρ_L × ρ_c 전 축
     Cartesian 스윕. GUI preview와 CLI `--stage grid`가 쓴다.

풀 M10의 버스바 스윕(옛 Stage 2)은 조합당 비용 때문에 **병렬 드라이버**
`scripts/optimize_m10.py:run_busbars`가 담당한다 — 워커마다 독립 엔진을 띄우고
adapter를 직접 호출한다. 같은 일을 하던 순차 함수 optimize_busbars는 호출처가
없어 v28.49에서 제거했다(optimize_grid가 같은 공간을 덮는다).

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


# ── 물성 시나리오 ────────────────────────────────────────────────────
# 헤드라인: 본 연구 실측 전극 비저항 (저온 가압소결 90°C/30min/5MPa).
SCENARIO_MEASURED = {
    "label": "pressed (rho=4.22 uohm.cm, KIST low-T sinter 90C/30min/5MPa)",
    "rho_bulk_uohm_cm": 4.22,
}
# 가압 효과의 **대조군** (v28.48에서 교체): 무가압 경화 실측 9 uohm.cm.
#   · 측정 조건: 90°C / 30min, 무가압, 4-probe Kelvin sensing.
#   · SCENARIO_MEASURED(4.22)와 **온도·시간이 동일하고 가압만 다르다** → 두 값의 차이가
#     경화 효과가 상쇄된 **순수 가압 효과**다. 이것이 대조군으로 옳은 이유.
#   · 이전에 쓰던 13.22는 as-printed(경화 전)라 경화 효과와 가압 효과가 섞여 있어
#     "가압의 기여"를 과대평가했다. 히스토리는 docs/front_electrode_model_scope.md §9.
SCENARIO_AS_CURED = {
    "label": "as-cured (rho=9 uohm.cm, 90C/30min, no pressure)",
    "rho_bulk_uohm_cm": 9.0,
}
# 엔진 GridDesign 기본값을 그대로 쓰는 시나리오(rho=None). 엔진 기본은 as-printed
# 13.22 uohm.cm이며 Compare 탭(before/after hot pressing)의 BEFORE 상태와 연동된다 —
# **가압 효과 비교의 대조군이 아니다**. 대조군은 SCENARIO_AS_CURED를 쓸 것.
SCENARIO_ENGINE_DEFAULT = {
    "label": "engine default (as-printed, GridDesign rho_bulk)",
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
                     edge_margin_mm=0.0,
                     scenario=None, recovery_factor=0.0, mode="tandem", npts=14,
                     axis_segments_override=None, target_nodes=None,
                     objective="total_loss", progress=None):
    """Stage 1 — 소셀에서 finger width × pitch 스윕 (버스바 대표값 고정).

    edge_margin_mm(v28.46): 엣지 실버-프리 마진을 Stage 1에도 전달한다. 기본 0.0
    이면 기존과 비트 동일. GUI 기본값(1.0mm)과 CLI를 같은 조건으로 맞출 때 쓴다.

    n_probe 가드(v28.43): 다중 busbar를 n_probe_points=0(legacy 단일-busbar 수집)으로
    풀면 전류 미수집으로 FF가 붕괴해 **에러 없이 그럴듯한 틀린 값**을 낸다(preview
    8.85% 버그, 메쉬 아님). 가드는 모든 호출 경로를 덮도록 **초크포인트인
    adapter.evaluate_existing_simulation**에 있다(여기선 실제 사용된 값을 결과 meta
    에서 취합해 노출만 한다)."""
    grid_list = []
    for wf_um, pitch_mm in itertools.product(finger_widths_um, finger_pitches_mm):
        grid_list.append(dict(
            cell_w_mm=cell_mm, cell_h_mm=cell_mm,
            finger_spacing_mm=pitch_mm, w_finger_um=wf_um,
            n_busbars=busbar_number, w_busbar_mm=busbar_width_mm,
            n_probe_points=n_probe_points, edge_margin_mm=edge_margin_mm))
    out = _sweep(fest, grid_list, scenario=scenario, recovery_factor=recovery_factor,
                 mode=mode, npts=npts, axis_segments_override=axis_segments_override,
                 target_nodes=target_nodes, objective=objective, progress=progress,
                 stage="fingers")
    metas = [r["meta"] for r in out["results"] if r]
    out["n_probe_points"] = metas[0].get("n_probe_points", n_probe_points) if metas else n_probe_points
    out["n_probe_auto_bumped"] = any(m.get("n_probe_auto_bumped") for m in metas)
    return out


def optimize_grid(fest, *, cell_mm, finger_widths_um, finger_pitches_mm,
                  n_busbars_list, busbar_widths_mm, rho_bulk_list=(None,),
                  rho_contact_list=(None,), edge_margin_mm=0.0,
                  edge_margins_mm=None, n_probe_points=0,
                  scenario=None, recovery_factor=0.0, mode="tandem", npts=14,
                  axis_segments_override=None, target_nodes=None,
                  objective="efficiency", progress=None):
    """전 축 Cartesian 스윕 (v28.45, 2026.08.06 랩미팅).

    축: finger_width × finger_pitch × busbar_number × busbar_width ×
        rho_bulk × rho_contact (× edge_margin). 각 축은 리스트.
        rho_bulk_list/rho_contact_list의 None 항목은 override 없음(scenario/엔진
        기본값) → 기본 상태 비트 동일.
    물성(rho_bulk/rho_contact)과 edge_margin은 grid dict로 넘겨 adapter 초크포인트가
    조합별로 적용한다. 반환은 _sweep과 동일 구조 + n_combos.

    edge_margin 스윕(v28.50): `edge_margins_mm`에 리스트를 주면 마진도 축이 된다.
    미지정이면 스칼라 `edge_margin_mm` 하나만 쓴다(기존과 비트 동일).

    ⚠ **마진은 설계 자유도가 아니라 공정 제약이다.** 실측상 마진이 커질수록 효율이
    단조 감소하므로(금속·접촉 면적이 줄어든다), 마진을 최적화 축으로 보고 전체
    argmax를 취하면 **항상 가장 작은 마진**이 뽑혀 무의미하다. 그래서 마진을 여러 개
    준 경우 `best`(전역 최적) 대신 **`best_by_edge`(마진별 최적)** 를 보라. 답해야 할
    질문은 "어떤 마진을 고를까"가 아니라 "이 마진의 대가가 얼마인가"다.
    """
    edges = list(edge_margins_mm) if edge_margins_mm else [edge_margin_mm]
    grid_list = []
    for wf, pitch, nbb, wbb, rho_l, rho_c, edge in itertools.product(
            finger_widths_um, finger_pitches_mm, n_busbars_list,
            busbar_widths_mm, rho_bulk_list, rho_contact_list, edges):
        d = dict(cell_w_mm=cell_mm, cell_h_mm=cell_mm,
                 finger_spacing_mm=pitch, w_finger_um=wf,
                 n_busbars=nbb, w_busbar_mm=wbb,
                 n_probe_points=n_probe_points, edge_margin_mm=edge)
        if rho_l is not None:
            d["rho_bulk_uohm_cm"] = rho_l
        if rho_c is not None:
            d["rho_contact_mohm_cm2"] = rho_c
        grid_list.append(d)
    out = _sweep(fest, grid_list, scenario=scenario, recovery_factor=recovery_factor,
                 mode=mode, npts=npts, axis_segments_override=axis_segments_override,
                 target_nodes=target_nodes, objective=objective, progress=progress,
                 stage="grid")
    metas = [r["meta"] for r in out["results"] if r]
    out["n_probe_points"] = metas[0].get("n_probe_points", n_probe_points) if metas else n_probe_points
    out["n_probe_auto_bumped"] = any(m.get("n_probe_auto_bumped") for m in metas)
    out["n_combos"] = len(grid_list)
    # 마진을 여러 개 스윕했다면 마진별 최적을 따로 제공한다 — 전역 best는 항상
    # 최소 마진이 되어 오해를 부른다(docstring 참조).
    if len(edges) > 1:
        by_edge = {}
        for r in out["results"]:
            e = round(float(r["parameters"].get("edge_margin_mm", 0.0)), 6)
            if e not in by_edge or (r["results"]["efficiency"]
                                    > by_edge[e]["results"]["efficiency"]):
                by_edge[e] = r
        out["best_by_edge"] = dict(sorted(by_edge.items()))
    return out


def roundtrip_check(fest, best, *, scenario=None, recovery_factor=0.0, mode="tandem",
                    npts=14, axis_segments_override=None, target_nodes=None):
    """최적 조건을 엔진에 '직접 재입력'했을 때 동일한 손실·효율이 나오는지 확인.

    실제 실현된 n_fingers(정수)로 재입력해 지오메트리를 정확히 재현한다.

    재입력은 **스윕에 쓰인 전 축**을 복원해야 한다(v28.46 fix). v28.45에서
    edge_margin / rho_bulk / rho_contact가 조합별 스윕 축이 되었는데 여기서 복원하지
    않으면 재평가가 **다른 설계**(마진 없음·엔진 기본 물성)를 풀게 된다 → 멀쩡한
    최적해를 "round-trip FAIL(불일치)"로 오보고한다. 값 자체가 조용히 틀리는 게
    아니라 검증기가 가짜 경보를 내는 쪽이지만, 진짜 지오메트리 불일치와 구분이
    안 돼 위험하다. edge_margin=0·물성 override 없음(기본 상태)에서는 복원할 것이
    없어 기존 동작과 비트 동일하다.

    물성은 ``parameters``(실제 사용된 값, µΩ·cm로 역환산됨)가 아니라
    ``meta['grid_overrides']``(**원본 입력 그대로**)에서 복원한다. parameters를 쓰면
    ρ[Ω·cm]→µΩ·cm→Ω·cm 왕복에서 부동소수 오차가 끼어 "비트 동일" 판정이 깨질 수
    있기 때문이다.

    Returns (ok, reeval_result, best_result).
    """
    p = best["parameters"]
    grid = dict(
        cell_w_mm=p["cell_w_mm"], cell_h_mm=p["cell_h_mm"],
        n_fingers=int(p["n_fingers"]), w_finger_um=p["finger_width_um"],
        n_busbars=int(p["busbar_number"]), w_busbar_mm=p["busbar_width_mm"],
        n_probe_points=int(p["n_probe_points"]))
    # 조합별 override(edge_margin/rho_bulk/rho_contact)를 원본 입력 그대로 복원.
    grid.update(best.get("meta", {}).get("grid_overrides", {}))
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
