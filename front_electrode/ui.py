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


def render_preview_plots(fig, grid, plot_state):
    """optimizer preview 결과를 fig에 그린다(GUI canvas/txt와 분리한 순수 함수).

    grid: {(pitch_mm, n_busbar): result_dict} — optimize_fingers 결과 모음.
    plot_state: {"cbar": ...} — colorbar 핸들 보관용(향후 update_normal 재사용).

    (3-1) colorbar 누적 방지: ax.clear()는 colorbar가 만든 별도 axes를 남기므로
          fig.clf()로 전부 제거 후 subplot을 재생성한다.
    (3-2) heatmap busbar축은 이산 tick 명시. (3-3) 격자<2면 안내.
    (3-5) 축은 efficiency로 통일 — total_loss는 pitch↑ 경계 runaway(핑거 저항↓·
          차광↓)로 단조 감소해 내부 최적점이 사라져 최적점 판단에 부적합하고,
          efficiency만 interior optimum(생성·저항·차광 trade-off 균형점)을 보인다.
    """
    import numpy as np
    fig.clf()
    plot_state["cbar"] = None
    ax1 = fig.add_subplot(1, 2, 1)
    ax2 = fig.add_subplot(1, 2, 2)
    ps = sorted(set(p for (p, nb) in grid))
    nbs = sorted(set(nb for (p, nb) in grid))

    # 그래프 1: pitch vs efficiency (첫 busbar 계열)
    nb0 = nbs[0]
    xs = sorted(p for (p, nb) in grid if nb == nb0)
    ys = [grid[(p, nb0)]["results"]["efficiency"] for p in xs]
    ax1.plot(xs, ys, "o-", color="#00695C")
    ax1.set_xlabel("finger pitch [mm]"); ax1.set_ylabel("efficiency [%]")
    ax1.set_title(f"efficiency vs pitch ({nb0}BB)")

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
    e_wf = _row(left, "Finger width [µm]", 20.0)
    e_pmin = _row(left, "Pitch min [mm]", 1.2)
    e_pmax = _row(left, "Pitch max [mm]", 2.4)
    e_pn = _row(left, "Pitch steps", 4)
    e_nbb = _row(left, "Busbar numbers", "6,8,10,12")
    # (3-6) busbar 입력 형식 안내 — 쉼표 구분 정수 리스트.
    ctk.CTkLabel(left, text="형식: 쉼표 구분 정수 (예: 6,8,10,12,16,20)",
                 font=ctk.CTkFont(size=9), text_color="gray", anchor="w").pack(fill="x")
    e_wbb = _row(left, "Busbar width [mm]", 0.2)

    rec_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(left, text="Enable busbar optical recovery", variable=rec_var).pack(fill="x", pady=(6, 0))
    e_rec = _row(left, "Recovery factor", _opt.SCENARIO_MEASURED and 0.25)
    ctk.CTkLabel(left, text="※ Adjustable KIST project assumption (보편 물성값 아님)",
                 font=ctk.CTkFont(size=9), text_color="#c0392b").pack(fill="x")

    ctk.CTkLabel(left, text="목적함수 = efficiency (그래프도 efficiency).\n"
                            "정밀 M10 최적화는 CLI: scripts/optimize_m10.py",
                 font=ctk.CTkFont(size=9), text_color="gray", justify="left").pack(fill="x", pady=(6, 2))

    prog = ctk.CTkLabel(left, text="", anchor="w")
    prog.pack(fill="x", pady=2)
    run_btn = ctk.CTkButton(left, text="Run optimization")
    run_btn.pack(fill="x", pady=4)

    # 결과 영역: 텍스트 + 그래프 2개
    txt = ctk.CTkTextbox(right, height=150)
    txt.pack(fill="x", padx=4, pady=4)
    # (3-4) constrained_layout: colorbar 포함 subplot spacing을 자동 정리.
    # 축은 setup에서 만들지 않고 _draw에서 fig.clf() 후 매번 재생성한다
    # (3-1: ax.clear()만으로는 colorbar가 만든 별도 axes가 남아 누적되므로).
    fig = Figure(figsize=(8.6, 3.4), constrained_layout=True)
    canvas = FigureCanvasTkAgg(fig, master=right)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)
    # colorbar 핸들 보관소 — 향후 update_normal() 재사용 전환용(3-1: 구조만 열어둠).
    _plot_state = {"cbar": None}

    def _set_prog(msg):
        parent.after(0, lambda: prog.configure(text=msg))

    def _do_run():
        try:
            cell = float(e_cell.get())
            wf = float(e_wf.get())
            pmin, pmax = float(e_pmin.get()), float(e_pmax.get())
            pn = max(2, int(float(e_pn.get())))
            pitches = [pmin + (pmax - pmin) * i / (pn - 1) for i in range(pn)]
            nbbs = [int(x) for x in str(e_nbb.get()).split(",") if x.strip()]
            wbb = float(e_wbb.get())
            rec = float(e_rec.get()) if rec_var.get() else 0.0

            # pitch × busbar 스윕 (작은 셀, 빠른 미리보기). efficiency 최대 = best.
            grid = {}  # (pitch, nbb) -> result
            total = len(pitches) * len(nbbs)
            # (3-6) 총 조합수를 시작 시 명확히 표시(pitch steps × busbar 개수).
            _set_prog(f"총 {total}조합 (pitch {len(pitches)} × busbar {len(nbbs)}) 계산 시작...")
            k = 0
            for nb in nbbs:
                opt = _opt.optimize_fingers(
                    fest, cell_mm=cell, finger_widths_um=[wf],
                    finger_pitches_mm=pitches, busbar_number=nb, busbar_width_mm=wbb,
                    scenario=_opt.SCENARIO_MEASURED, recovery_factor=rec,
                    objective="efficiency", axis_segments_override=40, npts=6,
                    progress=lambda i, n, o: (_set_prog(f"계산 중... {k + i}/{total}")))
                for r in opt["results"]:
                    grid[(round(r["parameters"]["finger_pitch_mm"], 4), nb)] = r
                k += len(pitches)

            results = list(grid.values())
            best = max(results, key=lambda r: r["results"]["efficiency"])

            def _draw():
                # 텍스트: best + top-10 (efficiency)
                txt.delete("1.0", "end")
                b = best["parameters"]
                br = best["results"]
                txt.insert("end", f"BEST (efficiency): wf={b['finger_width_um']:.0f}µm "
                                  f"pitch={b['finger_pitch_mm']:.2f}mm nbb={b['busbar_number']} "
                                  f"wbb={b['busbar_width_mm']:.2f}mm\n")
                txt.insert("end", f"  efficiency={br['efficiency']:.3f}%  total_loss={br['total_loss']:.4f}  "
                                  f"raw_bb={br['raw_busbar_shading']*100:.3f}% "
                                  f"recovered={br['recovered_busbar_light']*100:.3f}% "
                                  f"effective_bb={br['effective_busbar_shading']*100:.3f}%\n\n")
                txt.insert("end", "Top-10 (by efficiency):  rank  wf  pitch  nbb  wbb  optical  electrical  total  eff\n")
                top = sorted(results, key=lambda r: -r["results"]["efficiency"])[:10]
                for i, r in enumerate(top, 1):
                    p = r["parameters"]; rr = r["results"]
                    txt.insert("end", f"  {i:>2}  {p['finger_width_um']:.0f}  {p['finger_pitch_mm']:.2f}  "
                                      f"{p['busbar_number']}  {p['busbar_width_mm']:.2f}  "
                                      f"{rr['optical_loss']:.3f}  {rr['electrical_loss']:.3f}  "
                                      f"{rr['total_loss']:.3f}  {rr['efficiency']:.3f}\n")
                # 그래프: colorbar 누적 방지·efficiency 축·이산 tick·격자<2 안내는
                # render_preview_plots(모듈 함수)에 위임(headless 렌더 검증 가능).
                render_preview_plots(fig, grid, _plot_state)
                canvas.draw()
                prog.configure(text=f"완료 ({total}조합, 미리보기 {cell:.0f}mm)")
                run_btn.configure(state="normal")

            parent.after(0, _draw)
        except Exception as e:  # GUI가 죽지 않도록
            parent.after(0, lambda: (prog.configure(text=f"오류: {e}"),
                                     run_btn.configure(state="normal")))

    def _on_run():
        run_btn.configure(state="disabled")
        prog.configure(text="계산 중...")
        threading.Thread(target=_do_run, daemon=True).start()

    run_btn.configure(command=_on_run)
    return win
