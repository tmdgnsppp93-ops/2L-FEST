# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Adapter — 기존 GEDOS 엔진 호출 래퍼 + busbar 반사광 회수(recovery).

    기존 엔진(gedos 모듈)
         ↓  evaluate_existing_simulation(gedos, grid_params, ...)
    results dict  →  (Phase 2) optimizer

이 모듈은 **새 물리식을 계산하지 않는다.** GridDesign/CellGeometry/GEDOSSolver
등 기존 엔진 객체에 파라미터를 넣고, 기존 calc_iv/losses 결과를 받아온다.
엔진 코드는 전혀 수정하지 않는다(의존성 주입: gedos 모듈을 인자로 받음 →
테스트는 mock된 gedos, CLI는 실제 gedos를 넘긴다).

── busbar 반사광 회수(박사님 지시) ──────────────────────────────────
busbar가 가린 빛의 일부는 반사되어 셀로 재입사한다. 이를 **busbar shading
항목에만** 적용하는 사후 line-item 보정으로 더한다:

    effective_busbar_shading = raw_busbar_shading × (1 − recovery_factor)
    recovered_busbar_light   = raw_busbar_shading × recovery_factor
    optical_loss(보정)       = 엔진 P_shade − recovered_busbar_light × Jmpp × Vmpp

적용 범위(엄수):
  · finger shading / TCO / contact / finger·busbar 전기저항에는 적용 안 함
  · 전체 optical loss에 일괄 계수를 곱하지 않음
  · finger–busbar 겹침(A_ov)을 이중계산하지 않음 (raw_busbar = (A_b − A_ov)/area)

Phase 0 분석 결과 shading은 (a) 사후 line-item(P_shade)과 (b) 생성전류
스케일(_gen_s) 두 경로로 엔진에 들어간다. 회수는 **(a) line-item 경로에만**
적용한다 — (b)에 넣으면 case/design 비율에서 상쇄되거나 FEM 재작성이
필요하기 때문. 따라서 **회수광은 FEM 전류 재계산에 피드백되지 않는 근사**다
(엔진 무수정, FEM 재풀이 없음).

회수의 회계(double-entry, 대칭):
  · 손실 원장:  optical_loss = P_shade − recovered_power           [mW/cm²]
  · 전력 원장:  efficiency   = iv['Eff'] + recovered_power/Pin×100 [%]
  회수광은 MPP에서 recovered_power[mW/cm²]만큼 delivered power를 늘리므로
  (1차 근사 ΔPmpp ≈ recovered·Jmpp·Vmpp) efficiency에도 반영하는 것이 옳다.
  두 원장은 회수량 기준으로 대칭이라 (efficiency + total_loss/Pin×100)은 회수에
  불변 → 이중계산이 없다. f=0이면 recovered_power=0 → efficiency == iv['Eff']
  (비트 동일). engine_raw['Eff']는 **순수 엔진값**으로 보존한다(핀/회귀 기준값).

  단위 주의: efficiency[%]와 total_loss[mW/cm²]의 수치가 같아지는 것은
  **Pin=100 mW/cm²(1-sun AM1.5G)에서만** 성립한다. 그래서 efficiency에는
  Pin 정규화(recovered_power/Pin×100)를 명시한다. Pin은 하드코딩하지 않고
  엔진 출력에서 역산한다: 엔진 Eff=Pmpp/Pin×100 → Pin=Pmpp/Eff×100.

  근사 한계(2-fix-c): recovered_power는 회수 전류의 추가 저항 손실(I²R)을
  무시한 무손실 delivered power다 → efficiency를 항상 미세하게 **과대평가**
  (상한)하는 방향이다.
"""

DEFAULT_BUSBAR_RECOVERY_FACTOR = 0.25  # KIST 프로젝트 조정 가능 가정값 (보편 물성 아님)

# ── recovery 모델 플래그 (GUI 슬라이더 가드) ──────────────────────────
# True  = 현재 모델(Route 2): recovery는 순수 사후 post-process다. FEM 해(iv)는
#         recovery와 완전히 무관하므로, 저장된 result에서 apply_recovery()로 f만
#         바꿔 efficiency/loss를 FEM 재계산 없이 즉시 재산출할 수 있다. GUI 슬라이더는
#         이 플래그가 True일 때만 활성화한다(비트동일 재현: recovery 대조군 |Δ|=0.0).
# False = 향후 recovery를 Jsc 보정(Route 1)으로 바꾸면 recovery가 FEM 광생성에
#         피드백되므로 이 즉시 재산출은 무효다. 그때 이 값을 False로 두면 슬라이더는
#         비활성화되고 UI가 "재계산 필요"를 안내해야 한다.
RECOVERY_IS_POST_PROCESS = True


def apply_recovery(result, recovery_factor):
    """저장된 result에서 recovery_factor만 바꿔 f-의존 필드를 FEM 재계산 없이 재산출.

    Route 2(RECOVERY_IS_POST_PROCESS=True) 전용. evaluate_existing_simulation과 **동일
    공식**을 engine_raw(모두 recovery 무관: Eff/Pmpp/Jmpp/Vmpp/P_shade/Pe/Pf_*/Pc)와
    raw_busbar_shading으로부터 재현한다 → 직접 호출과 비트동일.

    반환: {efficiency, optical_loss, total_loss, recovered_busbar_light,
           effective_busbar_shading} (results에 merge해 쓰면 됨).
    """
    if not RECOVERY_IS_POST_PROCESS:
        raise RuntimeError(
            "recovery가 post-process가 아님(Route 1) — FEM 재계산이 필요하다.")
    er = result["engine_raw"]
    raw_bb = result["results"]["raw_busbar_shading"]
    f = float(recovery_factor)
    recovered = raw_bb * f
    effective_bb = raw_bb * (1.0 - f)
    recovered_power = recovered * er["Jmpp"] * er["Vmpp"]        # [mW/cm²]
    optical_loss = er["P_shade"] - recovered_power
    electrical = er["Pe"] + er["Pf_finger"] + er["Pf_busbar"] + er["Pc"]
    total_loss = optical_loss + electrical
    pin = (er["Pmpp"] / er["Eff"] * 100.0) if er.get("Eff") else 100.0
    efficiency = er["Eff"] + recovered_power / pin * 100.0
    return dict(efficiency=efficiency, optical_loss=optical_loss, total_loss=total_loss,
                recovered_busbar_light=recovered, effective_busbar_shading=effective_bb)


# ── 단위 변환 헬퍼 (사용자 친화 단위 → 엔진 내부 단위 cm) ──────────
def _mm_to_cm(x):
    return float(x) / 10.0


def _um_to_cm(x):
    return float(x) * 1e-4


def _uohm_cm_to_ohm_cm(x):
    return float(x) * 1e-6


def busbar_shading_breakdown(geo, w_f_cm, w_b_cm):
    """geo의 공개 속성만으로 finger/busbar shading을 분리 계산한다.

    기존 CellGeometry.shading_fraction()과 **동일한 식**을 재현한다(엔진 무수정):
        A_f = n_f·w_f·fg_len,  A_b = n_b·w_b·bb_len,  A_ov = n_f·n_b·w_f·w_b
        total = (A_f + A_b + A_p − A_ov)/wafer_area
    busbar의 순(net) 성분은 (A_b − A_ov)/area 로 정의해 finger와의 겹침을
    이중계산하지 않는다(total = finger + net_busbar + pad 로 정확히 분해).
    """
    fg_len = geo.fg_x_range[1] - geo.fg_x_range[0]
    bb_len = geo.bb_y_range[1] - geo.bb_y_range[0]
    A_f = geo.n_f * w_f_cm * fg_len
    A_b = geo.n_b * w_b_cm * bb_len
    A_ov = geo.n_f * geo.n_b * w_f_cm * w_b_cm
    A_p = geo.pad ** 2 if geo.pad > 0 else 0.0
    area = geo.wafer_area()
    finger_shading = A_f / area
    net_busbar_shading = (A_b - A_ov) / area
    pad_shading = A_p / area
    total = (A_f + A_b + A_p - A_ov) / area
    return {
        "finger_shading": finger_shading,
        "raw_busbar_shading": net_busbar_shading,   # net (겹침 제거)
        "pad_shading": pad_shading,
        "total_shading": total,                     # == geo.shading_fraction()
    }


def _build_geometry(gedos, grid_params):
    """grid_params(사용자 단위) → CellGeometry (monofacial, full_area).

    edge_margin(v28.45, 2026.08.06 랩미팅): 웨이퍼 엣지의 실버-프리 마진.
    엔진의 edge_gap(핑거 x-길이 트림)에 더해 busbar_length_frac로 버스바 y-길이도
    함께 축소해 **금속(핑거·버스바)이 엣지에 닿지 않도록** 한다. 엣지 영역은
    활성으로 유지(광생성·TCO 횡전도 그대로), 효율 분모 면적은 W×H 고정(불변).
    edge_margin=0이면 edge_gap=0·busbar_length_frac=1.0 → 기존과 비트 동일.
    """
    gp = grid_params
    n_probe = int(gp.get("n_probe_points", 0))
    # Metal optical transparency (Manual v7.0 §2.7). 0이면 광학폭 == 물리폭이라
    # 기존 경로와 비트 동일하다. 엔진 내부 인자명은 _f/_b, 사용자 단위 키는
    # _finger/_busbar — 기존 w_finger_um → w_finger 규약과 같은 패턴이다.
    t_f = float(gp.get("optical_transparency_finger", 0.0) or 0.0)
    t_b = float(gp.get("optical_transparency_busbar", 0.0) or 0.0)
    edge_margin_cm = _mm_to_cm(gp.get("edge_margin_mm", 0.0) or 0.0)
    cell_h_cm = _mm_to_cm(gp["cell_h_mm"])
    # 버스바 y-길이 축소분(핑거 x는 edge_gap이 담당). margin=0이면 1.0(불변).
    bb_frac = 1.0
    if edge_margin_cm > 0.0 and cell_h_cm > 0.0:
        bb_frac = max(0.0, (cell_h_cm - 2.0 * edge_margin_cm) / cell_h_cm)
    if gp.get("finger_spacing_mm") is not None:
        front = gedos.GridDesign(
            input_mode="finger_spacing",
            finger_spacing_mm=float(gp["finger_spacing_mm"]),
            n_busbars=int(gp["n_busbars"]),
            w_finger=_um_to_cm(gp["w_finger_um"]),
            w_busbar=_mm_to_cm(gp["w_busbar_mm"]),
            n_probe_points=n_probe,
            edge_gap=edge_margin_cm, busbar_length_frac=bb_frac,
            optical_transparency_f=t_f, optical_transparency_b=t_b,
        )
    else:
        front = gedos.GridDesign(
            input_mode="n_fingers",
            n_fingers=int(gp["n_fingers"]),
            n_busbars=int(gp["n_busbars"]),
            w_finger=_um_to_cm(gp["w_finger_um"]),
            w_busbar=_mm_to_cm(gp["w_busbar_mm"]),
            n_probe_points=n_probe,
            edge_gap=edge_margin_cm, busbar_length_frac=bb_frac,
            optical_transparency_f=t_f, optical_transparency_b=t_b,
        )
    geo = gedos.CellGeometry(
        cell_w=_mm_to_cm(gp["cell_w_mm"]),
        cell_h=cell_h_cm,
        front=front,
    )  # rear=None → full_area (monofacial)
    return geo


def evaluate_existing_simulation(
    gedos,
    grid_params,
    scenario=None,
    busbar_recovery_factor=0.0,
    mode="tandem",
    npts=14,
    axis_segments_override=None,
    target_nodes=None,
):
    """기존 엔진을 1회 실행하고 결과 dict를 반환한다(순수 래퍼).

    Args:
      gedos: 로드된 엔진 모듈 (CellGeometry/GridDesign/GEDOSSolver/DiodeParams/
            generate_mesh/classify_nodes 보유).
      grid_params: dict — cell_w_mm, cell_h_mm, (n_fingers | finger_spacing_mm),
            w_finger_um, n_busbars, w_busbar_mm, [n_probe_points].
      scenario: dict|None — 물성 고정 입력. rho_bulk_uohm_cm/finger_h_um/shape_cf
            override(없으면 엔진 GridDesign 기본값). 전기 파라미터(면저항·접촉저항
            등)는 엔진 기본값 유지 — 변경하지 않는다.
      busbar_recovery_factor: 0.0 = OFF(엔진과 완전히 동일), >0 = busbar shading에만 회수.
      mode: 'tandem'|'single'.  npts: calc_iv 스윕 점수.
      axis_segments_override / target_nodes: 메시 밀도 제어(둘 중 하나; 없으면 Med).

    Returns: results dict (parameters / results / engine_raw / meta).
    """
    # ── n_probe 가드(v28.43, 초크포인트) — 모든 front_electrode 경로 보호 ──
    # 다중 busbar를 n_probe_points=0(엔진 legacy 단일-busbar n_terminals 수집)으로
    # 풀면 대부분 busbar에서 전류가 수집되지 않아 직렬저항 폭증·FF 붕괴 →
    # **에러 없이 그럴듯한 틀린 값**(M10 preview eff 8.85% vs 정상 31.3%; 실측
    # 확인: n_probe 0→10에서 FF 30.9→84.2). 메쉬 해상도 문제가 아니라 전류추출
    # 모델 문제다(43k·81k 노드 모두 8.85%). busbar_number>1인데 n_probe==0이면
    # Griddler식 수집(=10, CLI Stage-2/핀과 동일)으로 자동 상향하고 meta에 기록한다.
    _n_bb = int(grid_params.get("n_busbars", 1) or 1)
    _n_probe_in = int(grid_params.get("n_probe_points", 0) or 0)
    _n_probe_auto = (_n_bb > 1 and _n_probe_in == 0)
    if _n_probe_auto:
        grid_params = dict(grid_params, n_probe_points=10)

    # 조합별 override 축(v28.45 스윕 확장)의 **원본 입력**을 그대로 보존한다.
    # roundtrip_check가 최적 조합을 재입력할 때 이걸 되돌린다 — parameters에 기록된
    # 값(단위 역환산됨)을 쓰면 부동소수 왕복 오차로 비트 동일이 깨질 수 있다.
    _grid_overrides = {k: grid_params[k] for k in
                       ("edge_margin_mm", "rho_bulk_uohm_cm", "rho_contact_mohm_cm2",
                        "optical_transparency_finger", "optical_transparency_busbar")
                       if grid_params.get(k) is not None}

    # busbar recovery factor와 optical transparency는 같은 물리(busbar 반사광
    # 회수)를 서로 다른 계층에서 모델링한다 — 둘 다 켜면 이중계산이다.
    # recovery는 사후 line-item이라 FEM에 피드백되지 않고(위 모듈 docstring),
    # T는 엔진 입력이라 발전량에 실제로 들어간다. 조용히 둘 다 적용되는 것이
    # 최악이므로 막는다. finger는 recovery 모델이 없어 충돌하지 않는다.
    _t_b_in = float(grid_params.get("optical_transparency_busbar", 0.0) or 0.0)
    if float(busbar_recovery_factor) > 0.0 and _t_b_in > 0.0:
        raise ValueError(
            f"busbar_recovery_factor(={busbar_recovery_factor})와 "
            f"optical_transparency_busbar(={_t_b_in})를 동시에 쓸 수 없다 — "
            "같은 물리(busbar 반사광 회수)를 두 번 계산한다.\n"
            "  · 기존 방식 유지: optical_transparency_busbar=0 으로 둘 것 "
            "(권장 — 현재 기본)\n"
            "  · 광학 폭으로 전환: busbar_recovery_factor=0 으로 둘 것 "
            "(T 값의 문헌/측정 근거가 있을 때만)")

    geo = _build_geometry(gedos, grid_params)

    # 메시
    if axis_segments_override is not None:
        pts, tri = gedos.generate_mesh(geo, axis_segments_override=int(axis_segments_override))
    elif target_nodes is not None:
        pts, tri, *_ = gedos._generate_mesh_for_target(geo, target_nodes=int(target_nodes))
    else:
        pts, tri = gedos.generate_mesh(geo, mesh_tangent="Med", mesh_perp="Med")
    isf, isb, isp, ism, isrm, isrp = gedos.classify_nodes(pts, geo)
    S = gedos.GEDOSSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)

    # 물성(전극) — 우선순위: grid_params(per-combo 스윕) > scenario > 엔진 기본값.
    # (v28.45 Phase 2) rho_bulk/rho_contact를 조합별로 스윕할 수 있게 grid_params에서
    # 직접 받는다. 값이 없으면 기존 경로(scenario/엔진 기본값) → 비트 동일.
    g = geo.front
    sc = scenario or {}
    gp = grid_params
    if gp.get("rho_bulk_uohm_cm") is not None:
        rm = _uohm_cm_to_ohm_cm(gp["rho_bulk_uohm_cm"])
    elif sc.get("rho_bulk_uohm_cm") is not None:
        rm = _uohm_cm_to_ohm_cm(sc["rho_bulk_uohm_cm"])
    else:
        rm = g.rho_bulk
    hf = (_um_to_cm(sc["finger_h_um"]) if sc.get("finger_h_um") is not None else g.finger_h)
    cf = float(sc["shape_cf"]) if sc.get("shape_cf") is not None else g.shape_cf
    wf = g.w_f
    if gp.get("rho_contact_mohm_cm2") is not None:
        rc = float(gp["rho_contact_mohm_cm2"]) * 1e-3   # mΩ·cm² → Ω·cm²
    else:
        rc = g.rho_contact     # 엔진 기본값(10 mΩ·cm²)
    Rs = g.Rs_sheet

    dp = gedos.DiodeParams()

    # 기존 엔진 실행 (새 물리 없음)
    Vs, Js, iv = S.calc_iv(rm, hf, wf, rc, Rs, cf, dp, mode=mode, npts=npts)
    vmpp_bias = iv.get("Vmpp_internal", iv["Vmpp"])
    res = iv.get("_mpp_result") or S.solve(rm, hf, wf, rc, Rs, vmpp_bias, cf, dp, mode)
    L = S.losses(res, rm, hf, wf, rc, Rs, cf, dp, Vmpp=iv["Vmpp"], Jmpp=iv["Jmpp"])

    # busbar 반사광 회수 (line-item, busbar shading에만)
    bd = busbar_shading_breakdown(geo, wf, geo.w_b)
    f = float(busbar_recovery_factor)
    raw_bb = bd["raw_busbar_shading"]
    recovered = raw_bb * f
    effective_bb = raw_bb * (1.0 - f)
    # 회수광의 전력 환산 — 엔진 P_shade와 동일한 Jmpp·Vmpp 기준 [mW/cm²]
    recovered_power = recovered * iv["Jmpp"] * iv["Vmpp"]

    p_shade = L["P_shade"]
    optical_loss = p_shade - recovered_power          # f=0 → 엔진 P_shade와 정확히 동일
    electrical_loss = L["Pe"] + L["Pf_finger"] + L["Pf_busbar"] + L["Pc"]
    total_loss = optical_loss + electrical_loss

    # busbar 반사광 회수를 efficiency에도 반영(double-entry).
    # 회수광은 MPP에서 recovered_power[mW/cm²]만큼 delivered power를 늘린다.
    # 1차 근사로 ΔPmpp ≈ recovered·Jmpp·Vmpp = recovered_power 이므로
    # "유효 Jsc↑ → efficiency↑"를 FEM 재풀이 없이 line-item으로 구현한다.
    # 손실 원장(optical_loss −= recovered_power)과 전력 원장(efficiency += Δeff)이
    # 대칭이라 (efficiency + total_loss)는 회수에 불변 → 이중계산 없음.
    # f=0 → recovered_power=0 → efficiency == iv["Eff"] (비트 동일, 회귀 안전).
    # engine_raw["Eff"]는 순수 엔진값으로 보존(핀/회귀 기준).
    #
    # [2-fix-a] 단위 정규화: efficiency[%]와 recovered_power[mW/cm²]를 직접 더하지
    # 않는다. Δeff[%] = recovered_power[mW/cm²] / Pin[mW/cm²] × 100. Pin은
    # 하드코딩하지 않고 엔진 출력에서 역산한다 — 엔진 Eff=Pmpp/Pin×100 이므로
    # Pin = Pmpp/Eff×100 (엔진이 Pin을 바꾸면 자동 추종; 현재 Pin=100 mW/cm² AM1.5G).
    # Pin=100에서는 Δeff가 recovered_power와 수치가 같다(검증값 재현).
    #
    # [2-fix-c] 근사 한계: recovered_power는 회수 전류가 유발하는 추가 저항 손실
    # (I²R)을 무시한 무손실 delivered power다. 따라서 실제보다 항상 크며,
    # efficiency를 미세하게 **과대평가(overestimate)**하는 방향의 상한 근사다.
    #
    # [2-fix-d] 랭킹 영향: recovery는 busbar의 유효 광학 비용을 (1−f)배로 줄이므로
    # 최적 busbar 수를 **위로** 밀어올린다(경계 runaway 심화). Phase 3 sweep의
    # nbb 범위를 6,8,10,12,16,20으로 확장해 interior optimum이 잡히는지 확인할 것.
    pin_mw_cm2 = (iv["Pmpp"] / iv["Eff"] * 100.0) if iv.get("Eff") else 100.0
    efficiency = iv["Eff"] + recovered_power / pin_mw_cm2 * 100.0

    actual_pitch = geo.front.get_finger_pitch_mm(geo.W, geo.H)

    return {
        "parameters": {
            "cell_w_mm": grid_params["cell_w_mm"],
            "cell_h_mm": grid_params["cell_h_mm"],
            "n_fingers": geo.n_f,
            "finger_pitch_mm": actual_pitch,          # 실제 실현 pitch (round 후 재계산)
            "finger_width_um": geo.w_f * 1e4,
            "busbar_number": geo.n_b,
            "busbar_width_mm": geo.w_b * 10.0,
            "n_probe_points": int(grid_params.get("n_probe_points", 0)),
            "busbar_recovery_factor": f,
            "rho_bulk_uohm_cm": rm * 1e6,
            "rho_contact_mohm_cm2": rc * 1e3,
            "edge_margin_mm": float(grid_params.get("edge_margin_mm", 0.0) or 0.0),
        },
        "results": {
            "finger_shading_loss": bd["finger_shading"],       # fraction
            "raw_busbar_shading": raw_bb,                       # fraction (net)
            "effective_busbar_shading": effective_bb,          # fraction
            "recovered_busbar_light": recovered,               # fraction
            "optical_loss": optical_loss,                      # mW/cm² (회수 반영)
            "electrical_loss": electrical_loss,                # mW/cm²
            "total_loss": total_loss,                          # mW/cm²
            # % — 회수 반영. = iv["Eff"] + recovered_power/Pin×100 (f=0이면 iv["Eff"]).
            # Pin 정규화를 빼먹지 말 것(v28.42 [2-fix-a]) — 아래 계산부와 같은 식이다.
            "efficiency": efficiency,
            # 금속이 덮은 면적(물리) vs 빛을 잃은 면적(광학). T=0이면 같은 값이다.
            # 논문에서 두 값을 구분해 설명해야 하므로 항상 둘 다 남긴다.
            "shading_physical": geo.shading_fraction(wf, geo.w_b),
            "shading_optical": geo.optical_shading_fraction(wf, geo.w_b),
        },
        # 회귀/round-trip 검증용 원본 엔진 값(무보정)
        "engine_raw": {
            "Jsc": iv["Jsc"], "Voc": iv["Voc"], "FF": iv["FF"],
            "Pmpp": iv["Pmpp"], "Eff": iv["Eff"],
            "Vmpp": iv["Vmpp"], "Jmpp": iv["Jmpp"],
            "P_shade": p_shade,
            "Pe": L["Pe"], "Pf_finger": L["Pf_finger"],
            "Pf_busbar": L["Pf_busbar"], "Pc": L["Pc"],
            "total_shading": bd["total_shading"],
        },
        "meta": {
            "nodes": len(pts),
            "mode": mode,
            "rho_bulk_uohm_cm": rm * 1e6,
            "finger_h_um": hf * 1e4,
            "shape_cf": cf,
            "n_probe_points": int(grid_params.get("n_probe_points", 0)),
            "n_probe_auto_bumped": _n_probe_auto,
            # round-trip 재입력용 원본 override 입력(없으면 빈 dict → 기존과 동일).
            "grid_overrides": _grid_overrides,
        },
    }
