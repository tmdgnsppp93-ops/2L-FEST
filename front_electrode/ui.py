"""front_electrode UI — 최적화 창 (기존 GUI에 버튼 하나로 연결, 최소 침습).

지시서 §3b. 새 페이지를 만들지 않고, 기존 결과화면의 "Optimize Electrode" 버튼이
이 창을 연다. 기존 CustomTkinter 스타일(색·위젯)을 따르고 새 시각화 라이브러리를
추가하지 않는다(matplotlib 그대로).

이 모듈은 **GUI에서만** import된다(headless 테스트는 import하지 않음). optimizer/
adapter/preset를 호출만 하며 새 물리/효율식을 만들지 않는다.

주의: M10 풀-FEM은 1조합 ≈17분이라 GUI 인터랙티브에 부적합 → 이 창은 **작은 대표
셀 빠른 미리보기**(설계공간 스캔)를 제공한다. 정밀 M10 최종 최적화는 headless CLI
(scripts/optimize_m10.py)로 수행한다(창에 안내 표시).
"""
import threading

from . import optimizer as _opt
from . import presets as _presets
from . import adapter as _adapter


def render_preview_plots(fig, grid, plot_state, subtitle=None):
    """optimizer preview 결과를 fig에 그린다(GUI canvas/txt와 분리한 순수 함수).

    grid: {(pitch_mm, n_busbar): result_dict} — BEST의 비-(pitch,nbb) 축을 고정한
          slice(다축 스윕 시). plot_state: colorbar 핸들 보관.
    subtitle: 고정 축 값 표시(다축 스윕 시 pitch×busbar 단면임을 명시).

    (3-1) colorbar 누적 방지: ax.clear()는 colorbar가 만든 별도 axes를 남기므로
          fig.clf()로 전부 제거 후 subplot을 재생성한다.
    (3-2) heatmap busbar축은 이산 tick 명시. (3-3) 격자<2면 안내.
    (3-5) 축은 efficiency로 통일 — total_loss는 pitch↑ 경계 runaway(핑거 저항↓·
          차광↓)로 단조 감소해 내부 최적점이 사라져 최적점 판단에 부적합하고,
          efficiency만 interior optimum(생성·저항·차광 trade-off 균형점)을 보인다.
    """
    import numpy as np
    from matplotlib import colormaps
    fig.clf()
    plot_state["cbar"] = None
    ax1 = fig.add_subplot(1, 2, 1)
    ax2 = fig.add_subplot(1, 2, 2)
    ps = sorted(set(p for (p, nb) in grid))
    nbs = sorted(set(nb for (p, nb) in grid))

    # 전역 BEST(최적 디자인) — 좌측 그래프에서 강조.
    best_key = max(grid, key=lambda k: grid[k]["results"]["efficiency"])
    best_pitch, best_nb = best_key
    best_eff = grid[best_key]["results"]["efficiency"]

    # === 좌: busbar 계열별 efficiency vs pitch (viridis 단조색) ===
    # 우측 히트맵이 2D를 보이므로 좌측은 'busbar 비교축'으로 쓴다(전 계열 겹쳐 그림).
    # 계열 多(>8): 범례 대신 BEST/min/max만 강조하고 나머지는 옅은 회색 —
    #   좌측에 2번째 colorbar를 두면 우측 히트맵 colorbar와 의미가 섞여 읽기 나쁘므로
    #   grey-highlight를 채택(가독성 우선). ≤8이면 viridis 색 + 범례.
    single_pitch = len(ps) < 2   # (5) pitch 1점이면 라인 대신 마커만
    many = len(nbs) > 8
    cmap = colormaps["viridis"]
    denom = max(1, len(nbs) - 1)
    for i, nb in enumerate(nbs):
        xs = sorted(p for (p, x) in grid if x == nb)
        ys = [grid[(p, nb)]["results"]["efficiency"] for p in xs]
        color = cmap(i / denom)
        if many and nb not in (nbs[0], nbs[-1], best_nb):
            ax1.plot(xs, ys, "o" if single_pitch else "-",
                     color="#cfcfcf", lw=1.0, markersize=3, zorder=1)
        else:
            ax1.plot(xs, ys, "o" if single_pitch else "o-",
                     color=color, lw=1.8, markersize=4, label=f"{nb} BB", zorder=3)
    # (2) 최적점 강조: 별표 + offset 주석
    ax1.plot([best_pitch], [best_eff], marker="*", markersize=15,
             color="#d81b60", markeredgecolor="black", markeredgewidth=0.7, zorder=6)
    _mid = (min(ps) + max(ps)) / 2 if len(ps) > 1 else best_pitch
    _dx = -10 if best_pitch > _mid else 10
    ax1.annotate(f"{best_nb}BB, {best_pitch:.2f}mm, {best_eff:.3f}%",
                 xy=(best_pitch, best_eff), textcoords="offset points",
                 xytext=(_dx, 12), ha=("right" if _dx < 0 else "left"),
                 fontsize=8, color="#d81b60",
                 arrowprops=dict(arrowstyle="->", color="#d81b60", lw=0.7))
    ax1.set_xlabel("finger pitch [mm]"); ax1.set_ylabel("efficiency [%]")
    ax1.set_title("efficiency vs pitch")
    ax1.margins(y=0.18)   # (4) 실제 스케일 유지, 여백만 확보(차이 과장 아님)
    ax1.legend(loc="best", fontsize=8, framealpha=0.7)
    if subtitle:   # 다축 스윕: pitch×busbar 단면이고 나머지 축은 BEST값 고정임을 명시
        fig.suptitle(subtitle, fontsize=8, color="#555555")

    # 그래프 2: pitch × busbar heatmap (efficiency)
    if len(ps) < 2 or len(nbs) < 2:
        ax2.axis("off")
        ax2.text(0.5, 0.5,
                 "격자 부족\n\nheatmap을 그리려면 pitch·busbar\n각각 2개 이상 필요합니다.\n"
                 f"(현재 pitch {len(ps)}개 × busbar {len(nbs)}개)",
                 ha="center", va="center", fontsize=10, color="#555555")
    else:
        Z = np.full((len(nbs), len(ps)), np.nan)
        for (p, nb), r in grid.items():
            Z[nbs.index(nb), ps.index(p)] = r["results"]["efficiency"]
        # busbar(y)는 이산값 → index 격자 + 실제값 tick. pitch(x)는 extent 매핑 후 값 tick.
        im = ax2.imshow(Z, aspect="auto", origin="lower", interpolation="nearest",
                        extent=[min(ps), max(ps), -0.5, len(nbs) - 0.5])
        ax2.set_yticks(range(len(nbs)))
        ax2.set_yticklabels([str(nb) for nb in nbs])
        ax2.set_xticks(ps)
        ax2.set_xticklabels([f"{p:.2f}" for p in ps], rotation=45, fontsize=8)
        ax2.set_xlabel("finger pitch [mm]"); ax2.set_ylabel("busbar number")
        ax2.set_title("efficiency heatmap [%]")
        plot_state["cbar"] = fig.colorbar(im, ax=ax2)   # (3-1) 핸들 보관
    return fig


def open_optimizer_window(fest, parent):
    """Optimize Electrode 창을 연다. fest=엔진 모듈, parent=메인 앱(CTk)."""
    import customtkinter as ctk
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    win = ctk.CTkToplevel(parent)
    win.title("Front Electrode Optimization (fast preview)")
    win.geometry("980x620")

    left = ctk.CTkFrame(win, width=300)
    left.pack(side="left", fill="y", padx=6, pady=6)
    right = ctk.CTkFrame(win)
    right.pack(side="left", fill="both", expand=True, padx=6, pady=6)

    def _row(parent_, label, default):
        fr = ctk.CTkFrame(parent_, fg_color="transparent")
        fr.pack(fill="x", pady=2)
        ctk.CTkLabel(fr, text=label, width=150, anchor="w").pack(side="left")
        e = ctk.CTkEntry(fr, width=110)
        e.insert(0, str(default))
        e.pack(side="left")
        return e

    def _range_row(parent_, label, dmin, dmax, dn):
        # (Phase 2) min / max / steps 3칸을 한 줄에. 기본 steps=1이면 단일값.
        fr = ctk.CTkFrame(parent_, fg_color="transparent")
        fr.pack(fill="x", pady=2)
        ctk.CTkLabel(fr, text=label, width=120, anchor="w").pack(side="left")
        emin = ctk.CTkEntry(fr, width=44); emin.insert(0, str(dmin)); emin.pack(side="left", padx=1)
        emax = ctk.CTkEntry(fr, width=44); emax.insert(0, str(dmax)); emax.pack(side="left", padx=1)
        en = ctk.CTkEntry(fr, width=34); en.insert(0, str(dn)); en.pack(side="left", padx=1)
        return emin, emax, en

    ctk.CTkLabel(left, text="Front Electrode Optimization",
                 font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(4, 6))

    # preset (mainstream만 드롭다운; 0BB는 별도 안내)
    ctk.CTkLabel(left, text="Technology preset", anchor="w").pack(fill="x")
    preset_var = ctk.StringVar(value="M10_SMBB_2025")
    ctk.CTkOptionMenu(left, variable=preset_var,
                      values=list(_presets.MAINSTREAM_PRESETS)).pack(fill="x", pady=2)
    ctk.CTkLabel(left, text="(0BB는 M10_0BB_future — mainstream과 분리, 미래기술 전용)",
                 font=ctk.CTkFont(size=9), text_color="gray").pack(fill="x")

    e_cell = _row(left, "Preview cell [mm]", 20.0)
    ctk.CTkLabel(left, text="아래 range 필드: min / max / steps (steps=1이면 단일값)",
                 font=ctk.CTkFont(size=9), text_color="gray", anchor="w").pack(fill="x")
    e_wfmin, e_wfmax, e_wfn = _range_row(left, "Finger width [µm]", 20, 20, 1)
    e_pmin, e_pmax, e_pn = _range_row(left, "Finger pitch [mm]", 1.2, 2.4, 4)
    e_nbb = _row(left, "Busbar numbers", "6,8,10,12")
    ctk.CTkLabel(left, text="형식: 쉼표 구분 정수 (예: 6,8,10,12,16,20)",
                 font=ctk.CTkFont(size=9), text_color="gray", anchor="w").pack(fill="x")
    e_wbmin, e_wbmax, e_wbn = _range_row(left, "Busbar width [mm]", 0.2, 0.2, 1)
    # (Phase 2) 물성 스윕 — 쉼표 구분 다중값. 기본=현재값 → 비트 동일.
    e_rhol = _row(left, "ρ_L bulk [µΩ·cm]", "4.22")
    ctk.CTkLabel(left, text="as-printed 13.22 / measured 4.22 비교: 13.22,4.22",
                 font=ctk.CTkFont(size=9), text_color="gray", anchor="w").pack(fill="x")
    e_rhoc = _row(left, "ρ_c contact [mΩ·cm²]", "10")
    # (Phase 1) 엣지 실버-프리 마진 (Griddler "Edge Gap" 동일 개념). 기본 1.0 mm.
    e_edge = _row(left, "Edge margin [mm] (=Edge Gap)", 1.0)

    # busbar 광학 회수 f — 슬라이더(라이브) + 수치칸(양방향 동기).
    # recovery는 Route 2(adapter.RECOVERY_IS_POST_PROCESS)에서 순수 post-process라
    # 슬라이더 이동 시 FEM 재계산 없이 efficiency/loss만 즉시 재산출한다
    # (adapter.apply_recovery — 직접 호출과 비트동일).
    ctk.CTkLabel(left, text="Busbar optical recovery  f", anchor="w",
                 font=ctk.CTkFont(size=11, weight="bold")).pack(fill="x", pady=(6, 0))
    rec_row = ctk.CTkFrame(left, fg_color="transparent")
    rec_row.pack(fill="x")
    rec_slider = ctk.CTkSlider(rec_row, from_=0.0, to=0.60, number_of_steps=60)
    rec_slider.set(0.25)
    rec_slider.pack(side="left", fill="x", expand=True, padx=(0, 6))
    e_rec = ctk.CTkEntry(rec_row, width=56)
    e_rec.insert(0, "0.25")
    e_rec.pack(side="left")
    rec_note_lbl = ctk.CTkLabel(left, text="", anchor="w", justify="left",
                                font=ctk.CTkFont(size=9))
    rec_note_lbl.pack(fill="x")
    ctk.CTkLabel(left, text="※ Adjustable KIST project assumption (보편 물성값 아님)",
                 font=ctk.CTkFont(size=9), text_color="#c0392b").pack(fill="x")

    ctk.CTkLabel(left, text="목적함수 = efficiency (그래프도 efficiency).\n"
                            "슬라이더로 recovery를 바꾸면 FEM 재계산 없이 즉시 갱신.\n"
                            "정밀 M10 최적화는 CLI: scripts/optimize_m10.py",
                 font=ctk.CTkFont(size=9), text_color="gray", justify="left").pack(fill="x", pady=(6, 2))

    prog = ctk.CTkLabel(left, text="", anchor="w")
    prog.pack(fill="x", pady=2)
    run_btn = ctk.CTkButton(left, text="Run optimization")
    run_btn.pack(fill="x", pady=4)
    save_btn = ctk.CTkButton(left, text="Save CSV", fg_color="#2E7D32",
                             hover_color="#1B5E20")
    save_btn.pack(fill="x", pady=(0, 4))

    # 결과 영역: 텍스트 + 그래프 2개
    txt = ctk.CTkTextbox(right, height=150)
    txt.pack(fill="x", padx=4, pady=4)
    fig = Figure(figsize=(8.6, 3.4), constrained_layout=True)
    canvas = FigureCanvasTkAgg(fig, master=right)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
    _plot_state = {"cbar": None}

    # 스윕 결과 보관(슬라이더 라이브 재산출용). results는 base(FEM) 결과 리스트.
    _sweep = {"results": None, "cell": None, "total": None}
    _syncing = {"on": False}   # 슬라이더↔수치칸 순환 갱신 방지

    def _set_prog(msg):
        parent.after(0, lambda: prog.configure(text=msg))

    def _range_vals(emin, emax, en):
        lo = float(emin.get()); hi = float(emax.get()); n = max(1, int(float(en.get())))
        if n <= 1 or hi == lo:
            return [lo]
        return [lo + (hi - lo) * i / (n - 1) for i in range(n)]

    def _list_vals(entry):
        return [float(x) for x in str(entry.get()).split(",") if x.strip()]

    def _recovery_note(f):
        # f_rec = R_m·η_TIR·τ² 의 물리적 해석대(帶).
        if f < 0.06:
            return "f=%.2f — 평면 경면 (전반사 없음)" % f, "#555555"
        if f < 0.31:
            return "f=%.2f — 인쇄 Ag 램버시안, 전형" % f, "#00695C"
        if f < 0.43:
            return "f=%.2f — 인쇄 Ag 램버시안, 평활" % f, "#00695C"
        return "f=%.2f — 원형 와이어 영역: 본 구조에 해당하지 않음" % f, "#c0392b"

    def _render_results(f):
        """저장된 결과에 recovery f를 반영해 텍스트·그래프를 갱신(FEM 재계산 없음).
        다축 스윕: BEST의 비-(pitch,nbb) 축을 고정한 단면을 그래프에 그린다."""
        results = _sweep.get("results")
        if not results:
            return
        note, col = _recovery_note(f)
        rec_note_lbl.configure(text=note, text_color=col)
        if _adapter.RECOVERY_IS_POST_PROCESS:
            for r in results:
                r["results"].update(_adapter.apply_recovery(r, f))
                r["parameters"]["busbar_recovery_factor"] = f
        best = max(results, key=lambda r: r["results"]["efficiency"])
        b = best["parameters"]; br = best["results"]

        # BEST의 비-(pitch,nbb) 축(wf/wbb/ρL/ρc)을 고정한 pitch×busbar 단면.
        def _fix(p):
            return (abs(p["finger_width_um"] - b["finger_width_um"]) < 1e-6
                    and abs(p["busbar_width_mm"] - b["busbar_width_mm"]) < 1e-9
                    and abs(p["rho_bulk_uohm_cm"] - b["rho_bulk_uohm_cm"]) < 1e-6
                    and abs(p["rho_contact_mohm_cm2"] - b["rho_contact_mohm_cm2"]) < 1e-6)
        slice_grid = {}
        for r in results:
            p = r["parameters"]
            if _fix(p):
                slice_grid[(round(p["finger_pitch_mm"], 4), p["busbar_number"])] = r

        txt.delete("1.0", "end")
        m0 = _sweep.get("model")
        if m0 and m0[1]:
            txt.insert("end", f"⚠ n_probe_points 자동 상향 (0 → {m0[0]}, 다중 busbar 수집 모델)\n")
        edge = _sweep.get("edge", 0.0)
        txt.insert("end", f"BEST (eff @ f={f:.2f}, edge {edge:.1f}mm): "
                          f"wf={b['finger_width_um']:.0f}µm pitch={b['finger_pitch_mm']:.2f}mm "
                          f"nbb={b['busbar_number']} wbb={b['busbar_width_mm']:.2f}mm "
                          f"ρL={b['rho_bulk_uohm_cm']:.2f} ρc={b['rho_contact_mohm_cm2']:.1f}\n")
        txt.insert("end", f"  efficiency={br['efficiency']:.3f}%  total_loss={br['total_loss']:.4f}\n\n")
        txt.insert("end", "Top-10:  rk  wf pitch nbb  wbb   ρL    ρc  edge   eff\n")
        for i, r in enumerate(sorted(results, key=lambda r: -r["results"]["efficiency"])[:10], 1):
            p = r["parameters"]; rr = r["results"]
            txt.insert("end", f"  {i:>2} {p['finger_width_um']:>3.0f} {p['finger_pitch_mm']:>4.2f} "
                              f"{p['busbar_number']:>3} {p['busbar_width_mm']:>4.2f} "
                              f"{p['rho_bulk_uohm_cm']:>5.2f} {p['rho_contact_mohm_cm2']:>4.1f} "
                              f"{p.get('edge_margin_mm', 0.0):>4.1f} {rr['efficiency']:>6.3f}\n")
        # ρ_L 비교(예: 13.22 as-printed vs 4.22 measured) — 각 ρL의 최고 eff 차이(%p).
        rho_ls = sorted(set(round(r["parameters"]["rho_bulk_uohm_cm"], 3) for r in results))
        if len(rho_ls) >= 2:
            txt.insert("end", "\nρ_L 비교 (각 ρL의 최고 efficiency):\n")
            bestper = {}
            for r in results:
                rl = round(r["parameters"]["rho_bulk_uohm_cm"], 3)
                e = r["results"]["efficiency"]
                if rl not in bestper or e > bestper[rl]:
                    bestper[rl] = e
            hi_rl = max(rho_ls); lo_rl = min(rho_ls)
            for rl in rho_ls:
                txt.insert("end", f"  ρL={rl:.2f} µΩ·cm → {bestper[rl]:.3f}%\n")
            txt.insert("end", f"  개선(Δeff, {hi_rl:.2f}→{lo_rl:.2f}) = "
                              f"{bestper[lo_rl] - bestper[hi_rl]:+.3f} %p\n")

        sub = (f"pitch×busbar 단면 | 고정: wf={b['finger_width_um']:.0f}µm "
               f"wbb={b['busbar_width_mm']:.2f}mm ρL={b['rho_bulk_uohm_cm']:.2f} "
               f"ρc={b['rho_contact_mohm_cm2']:.1f} edge={edge:.1f}mm")
        render_preview_plots(fig, slice_grid, _plot_state, subtitle=sub)
        canvas.draw()
        m = _sweep.get("model")
        model_txt = ""
        if m:
            npv, bumped, nmin, nmax = m
            model_txt = (f" | n_probe {'자동상향0→' if bumped else '='}{npv}, "
                         f"nodes {nmin // 1000}~{nmax // 1000}k")
        prog.configure(text=f"완료 ({_sweep['total']}조합, {_sweep['cell']:.0f}mm, "
                            f"f={f:.2f}){model_txt}")

    _debounce = {"id": None}

    def _on_slider(val):
        if _syncing["on"]:
            return
        f = float(val)
        _syncing["on"] = True
        e_rec.delete(0, "end"); e_rec.insert(0, f"{f:.2f}")
        _syncing["on"] = False
        # 디바운스: 드래그 중 연속 이벤트(최대 60틱)를 모아 마지막만 렌더 →
        # matplotlib 재그리기 폭주로 인한 버벅임 방지(50ms idle 후 1회 렌더).
        if _debounce["id"] is not None:
            try:
                win.after_cancel(_debounce["id"])
            except Exception:
                pass
        _debounce["id"] = win.after(50, lambda: _render_results(f))

    def _on_rec_entry(event=None):
        if _syncing["on"]:
            return
        try:
            f = max(0.0, min(0.60, float(e_rec.get())))
        except (ValueError, TypeError):
            return
        _syncing["on"] = True
        rec_slider.set(f)
        _syncing["on"] = False
        _render_results(f)

    rec_slider.configure(command=_on_slider)
    e_rec.bind("<Return>", _on_rec_entry)
    e_rec.bind("<FocusOut>", _on_rec_entry)
    # 가드(필수): recovery가 post-process가 아니면(Route 1) 즉시 재산출은 무효 →
    # 슬라이더 비활성 + "재계산 필요" 안내. RECOVERY_IS_POST_PROCESS로 판정.
    if not _adapter.RECOVERY_IS_POST_PROCESS:
        rec_slider.configure(state="disabled")
        e_rec.configure(state="disabled")
        rec_note_lbl.configure(
            text="recovery가 FEM에 반영되는 모델(Route 1) — 슬라이더 비활성, 재계산 필요",
            text_color="#c0392b")

    def _do_run():
        try:
            cell = float(e_cell.get())
            wfs = _range_vals(e_wfmin, e_wfmax, e_wfn)
            pitches = _range_vals(e_pmin, e_pmax, e_pn)
            if len(pitches) < 2:
                pitches = pitches * 1   # 단일 pitch 허용(그래프는 마커만)
            nbbs = [int(x) for x in str(e_nbb.get()).split(",") if x.strip()]
            wbbs = _range_vals(e_wbmin, e_wbmax, e_wbn)
            rho_l = _list_vals(e_rhol)
            rho_c = _list_vals(e_rhoc)
            edge = float(e_edge.get())

            # 조합수 = 각 축의 곱. 폭발 경고(풀셀은 조합당 수십초~수분).
            total = (len(wfs) * len(pitches) * len(nbbs) * len(wbbs)
                     * max(1, len(rho_l)) * max(1, len(rho_c)))
            big = (cell >= 80.0 and total > 12) or total > 300
            if big:
                per = "풀셀 FEM 수십초~수분" if cell >= 80.0 else "소셀 수초"
                _set_prog(f"⚠ {total}조합 (조합당 {per}). 큰 스윕/풀 M10은 CLI 권장. 시작...")
            else:
                _set_prog(f"총 {total}조합 계산 시작...")

            done = {"n": 0}

            def _prog(i, n, o):
                done["n"] += 1
                _set_prog(f"계산 중... {done['n']}/{total}")

            # recovery는 슬라이더로 사후 반영 → f=0으로 FEM 실행. n_probe는 미지정(=0)이라
            # adapter 가드가 다중 busbar에서 자동 10 상향. edge_margin·물성은 grid로 전달.
            opt = _opt.optimize_grid(
                fest, cell_mm=cell, finger_widths_um=wfs, finger_pitches_mm=pitches,
                n_busbars_list=nbbs, busbar_widths_mm=wbbs,
                rho_bulk_list=(rho_l or [None]), rho_contact_list=(rho_c or [None]),
                edge_margin_mm=edge, scenario=_opt.SCENARIO_MEASURED, recovery_factor=0.0,
                objective="efficiency", axis_segments_override=40, npts=6, progress=_prog)
            results = [r for r in opt["results"] if r]
            nodes = [r["meta"]["nodes"] for r in results]
            _sweep["results"] = results
            _sweep["cell"] = cell
            _sweep["total"] = total
            _sweep["edge"] = edge
            _sweep["model"] = (opt.get("n_probe_points", 0),
                               bool(opt.get("n_probe_auto_bumped")),
                               min(nodes) if nodes else 0, max(nodes) if nodes else 0)
            try:
                f0 = max(0.0, min(0.60, float(e_rec.get())))
            except (ValueError, TypeError):
                f0 = 0.25
            parent.after(0, lambda: (_render_results(f0),
                                     run_btn.configure(state="normal")))
        except Exception as e:  # GUI가 죽지 않도록
            parent.after(0, lambda: (prog.configure(text=f"오류: {e}"),
                                     run_btn.configure(state="normal")))

    def _on_run():
        run_btn.configure(state="disabled")
        prog.configure(text="계산 중...")
        threading.Thread(target=_do_run, daemon=True).start()

    def _save_csv():
        """스윕 전 조합을 모든 축 컬럼과 함께 CSV로 저장(cwd)."""
        import csv as _csv
        import os as _os
        results = _sweep.get("results")
        if not results:
            prog.configure(text="저장할 결과 없음 — 먼저 Run 하세요.")
            return
        cols = ["finger_width_um", "finger_pitch_mm", "n_fingers", "busbar_number",
                "busbar_width_mm", "rho_bulk_uohm_cm", "rho_contact_mohm_cm2",
                "edge_margin_mm", "busbar_recovery_factor"]
        rcols = ["efficiency", "total_loss", "optical_loss", "electrical_loss"]
        path = _os.path.join(_os.getcwd(), "front_electrode_sweep.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = _csv.writer(fh)
            w.writerow(cols + rcols + ["nodes"])
            for r in sorted(results, key=lambda x: -x["results"]["efficiency"]):
                p = r["parameters"]; rr = r["results"]
                w.writerow([p.get(c, "") for c in cols] + [rr.get(c, "") for c in rcols]
                           + [r["meta"]["nodes"]])
        prog.configure(text=f"CSV 저장: {path} ({len(results)}행)")

    run_btn.configure(command=_on_run)
    save_btn.configure(command=_save_csv)
    return win
