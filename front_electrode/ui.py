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
    e_nbb = _row(left, "Busbar numbers", "2,3,4")
    e_wbb = _row(left, "Busbar width [mm]", 0.2)

    rec_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(left, text="Enable busbar optical recovery", variable=rec_var).pack(fill="x", pady=(6, 0))
    e_rec = _row(left, "Recovery factor", _opt.SCENARIO_MEASURED and 0.25)
    ctk.CTkLabel(left, text="※ Adjustable KIST project assumption (보편 물성값 아님)",
                 font=ctk.CTkFont(size=9), text_color="#c0392b").pack(fill="x")

    ctk.CTkLabel(left, text="목적함수 = efficiency. 그래프는 total loss.\n"
                            "정밀 M10 최적화는 CLI: scripts/optimize_m10.py",
                 font=ctk.CTkFont(size=9), text_color="gray", justify="left").pack(fill="x", pady=(6, 2))

    prog = ctk.CTkLabel(left, text="", anchor="w")
    prog.pack(fill="x", pady=2)
    run_btn = ctk.CTkButton(left, text="Run optimization")
    run_btn.pack(fill="x", pady=4)

    # 결과 영역: 텍스트 + 그래프 2개
    txt = ctk.CTkTextbox(right, height=150)
    txt.pack(fill="x", padx=4, pady=4)
    fig = Figure(figsize=(8.5, 3.2))
    ax1 = fig.add_subplot(1, 2, 1)
    ax2 = fig.add_subplot(1, 2, 2)
    canvas = FigureCanvasTkAgg(fig, master=right)
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

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
                # 그래프 1: pitch vs total loss (첫 busbar)
                ax1.clear(); ax2.clear()
                nb0 = nbbs[0]
                xs = sorted(p for (p, nb) in grid if nb == nb0)
                ys = [grid[(p, nb0)]["results"]["total_loss"] for p in xs]
                ax1.plot(xs, ys, "o-")
                ax1.set_xlabel("finger pitch [mm]"); ax1.set_ylabel("total loss [mW/cm²]")
                ax1.set_title(f"total loss vs pitch ({nb0}BB)")
                # 그래프 2: pitch × busbar heatmap (total loss)
                import numpy as np
                ps = sorted(set(p for (p, nb) in grid))
                nbs = sorted(set(nb for (p, nb) in grid))
                Z = np.full((len(nbs), len(ps)), np.nan)
                for (p, nb), r in grid.items():
                    Z[nbs.index(nb), ps.index(p)] = r["results"]["total_loss"]
                im = ax2.imshow(Z, aspect="auto", origin="lower",
                                extent=[min(ps), max(ps), min(nbs), max(nbs)])
                ax2.set_xlabel("finger pitch [mm]"); ax2.set_ylabel("busbar number")
                ax2.set_title("total loss heatmap")
                fig.colorbar(im, ax=ax2)
                fig.tight_layout()
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
