"""front_electrode UI — 최적화 창 (기존 GUI에 버튼 하나로 연결, 최소 침습).

지시서 §3b. 새 페이지를 만들지 않고, 기존 결과화면의 "Optimize Electrode" 버튼이
이 창을 연다. 기존 CustomTkinter 스타일(색·위젯)을 따르고 새 시각화 라이브러리를
추가하지 않는다(matplotlib 그대로).

이 모듈은 **GUI에서만** import된다(headless 테스트는 import하지 않음). optimizer/
adapter/preset를 호출만 하며 새 물리/효율식을 만들지 않는다.

주의: M10 풀-FEM은 1조합 ≈17분이라 GUI 인터랙티브에 부적합 → 이 창은 **작은 대표
셀 빠른 미리보기**(설계공간 스캔)를 제공한다. 정밀 M10 최종 최적화는 headless CLI
(scripts/optimize_m10.py)로 수행한다(창에 안내 표시).

i18n(v28.47): 표시 문자열은 전부 `i18n.py`의 dict에 있고 여기서는 `T("key")`로만
참조한다. 사이드바 상단 세그먼트 버튼으로 KO/EN을 즉시 전환하며, 전환 시 위젯
텍스트를 다시 입히고 **이미 계산된 결과가 있으면 텍스트·그래프도 재렌더**한다
(FEM 재계산은 하지 않는다 — 언어는 표시에만 영향, 결과는 비트 동일).
"""
import threading

from . import optimizer as _opt
from . import presets as _presets
from . import adapter as _adapter
from .i18n import T, set_language, get_language, LANGUAGES, label_for

# 사이드바 폭 [px]. 영문 안내가 한글보다 길어 v28.47에서 300 → 340으로 넓혔다.
# 라벨 폭/wraplength가 여기서 파생되므로 한 곳에서만 바꾼다.
SIDEBAR_W = 340
_LABEL_W = 150          # 입력 라벨 고정 폭 — 모든 행의 입력칸 x 위치를 맞춘다
_WRAP = SIDEBAR_W - 46  # 안내 문구 줄바꿈 폭(스크롤바·패딩 제외)
# 입력칸 폭 [px]. range 행은 min/max/steps 3칸이라 한 칸이 좁아지기 쉬운데,
# 확정 결과값(pitch 1.767 / 2.193)이 **잘리면 안 된다** — 실측 텍스트폭 33~34px에
# CTkEntry 내부 여백 약 10px를 더해 44px가 하한이다(tests/test_gui_layout.py가 검증).
#   실측(2026-08-10, macOS/CTk 5.2.2): "2.600"=36px, "100.0"=35px, "1.767"=33px
#   → 필요 칸폭 46px. 행 프레임 폭 302px 예산 안에서 48/48/34 + padx 6 + 라벨 150
#   = 286px라 여유 16px. 라벨 폭을 줄이지 않고도 들어가므로 정렬을 유지한다.
_ENTRY_W = 110          # 단일 입력 행
_ENTRY_W_RANGE = 48     # range 행의 min / max (소수 3자리까지)
_ENTRY_W_STEPS = 34     # range 행의 steps (정수 1~2자리)


_HANGUL_FONT_OK = {"checked": False, "ok": False}


def hangul_renderable(force_recheck=False):
    """현재 matplotlib 폰트로 한글을 그릴 수 있는지 (결과 캐시).

    엔진이 기동 시 rcParams['font.family']를 한글 폰트로 잡지만, 탐지 실패 시
    최후 폴백이 'Helvetica'라 한글 글리프가 없을 수 있다. 그 상태로 한글을 그리면
    조용히 두부(□)가 찍힌다 — v28.47에서 µ로 이미 한 번 겪은 실패 유형이라
    사전에 확인하고 안 되면 영문으로 떨어뜨린다.
    """
    if _HANGUL_FONT_OK["checked"] and not force_recheck:
        return _HANGUL_FONT_OK["ok"]
    ok = False
    try:
        import matplotlib
        from matplotlib import font_manager
        from matplotlib.ft2font import FT2Font
        fam = matplotlib.rcParams.get("font.family") or ["sans-serif"]
        path = font_manager.findfont(font_manager.FontProperties(family=fam),
                                     fallback_to_default=True)
        # 프로브 문자는 U+B2E8(한글 '단'). 리터럴 대신 코드포인트로 쓴다 —
        # ui.py에 하드코딩 한글이 없어야 한다는 규칙(test_ui_module_uses_no_
        # hardcoded_korean)을 지키기 위함이며, 이 문자는 표시용이 아니라 검사용이다.
        ok = 0xB2E8 in FT2Font(path).get_charmap()
    except Exception:
        ok = False        # 확인 자체가 실패하면 안전한 쪽(영문)으로.
    _HANGUL_FONT_OK.update(checked=True, ok=ok)
    return ok


def PT(key, **kwargs):
    """그래프용 문자열 조회 — 한글 폰트가 없으면 영문으로 폴백한다.

    UI 위젯은 Tk가 자체 폰트를 쓰므로 T()를 그대로 쓰고, **matplotlib에 들어가는
    문자열만** 이 함수를 거친다.
    """
    if get_language() == "ko" and not hangul_renderable():
        from .i18n import STRINGS, DEFAULT_LANGUAGE
        s = STRINGS[DEFAULT_LANGUAGE].get(key)
        if s is not None:
            return s.format(**kwargs) if kwargs else s
    return T(key, **kwargs)


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

    문자열은 **PT()**로 조회한다(T()가 아니라). 축 라벨·제목·범례는 기술 용어라 두
    언어에서 동일한 영문이고, 산문형 안내(격자 부족)와 subtitle만 언어를 따른다.
    PT()는 한글 폰트가 없는 환경에서 영문으로 폴백해 두부(□)를 막는다.
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
                     color=color, lw=1.8, markersize=4,
                     label=PT("plot.legend_bb", nb=nb), zorder=3)
    # (2) 최적점 강조: 별표 + offset 주석
    ax1.plot([best_pitch], [best_eff], marker="*", markersize=15,
             color="#d81b60", markeredgecolor="black", markeredgewidth=0.7, zorder=6)
    _mid = (min(ps) + max(ps)) / 2 if len(ps) > 1 else best_pitch
    _dx = -10 if best_pitch > _mid else 10
    ax1.annotate(PT("plot.annot_best", nb=best_nb, pitch=best_pitch, eff=best_eff),
                 xy=(best_pitch, best_eff), textcoords="offset points",
                 xytext=(_dx, 12), ha=("right" if _dx < 0 else "left"),
                 fontsize=8, color="#d81b60",
                 arrowprops=dict(arrowstyle="->", color="#d81b60", lw=0.7))
    ax1.set_xlabel(PT("plot.xlabel_pitch")); ax1.set_ylabel(PT("plot.ylabel_eff"))
    ax1.set_title(PT("plot.title_eff_vs_pitch"))
    ax1.margins(y=0.18)   # (4) 실제 스케일 유지, 여백만 확보(차이 과장 아님)
    ax1.legend(loc="best", fontsize=8, framealpha=0.7)
    if subtitle:   # 다축 스윕: pitch×busbar 단면이고 나머지 축은 BEST값 고정임을 명시
        fig.suptitle(subtitle, fontsize=8, color="#555555")

    # 그래프 2: pitch × busbar heatmap (efficiency)
    if len(ps) < 2 or len(nbs) < 2:
        ax2.axis("off")
        ax2.text(0.5, 0.5,
                 PT("plot.grid_insufficient", n_pitch=len(ps), n_bb=len(nbs)),
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
        ax2.set_xlabel(PT("plot.xlabel_pitch")); ax2.set_ylabel(PT("plot.ylabel_busbar"))
        ax2.set_title(PT("plot.title_heatmap"))
        plot_state["cbar"] = fig.colorbar(im, ax=ax2)   # (3-1) 핸들 보관
    return fig


def open_optimizer_window(fest, parent):
    """Optimize Electrode 창을 연다. fest=엔진 모듈, parent=메인 앱(CTk)."""
    import customtkinter as ctk
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    win = ctk.CTkToplevel(parent)
    win.title(T("window.title"))
    # i18n: 영문 문구가 한글보다 길어 2줄로 늘어나므로 가로·세로 모두 여유를 준다.
    # 세로 660은 1440x900 노트북에서도 잘리지 않는 범위(메뉴바·독 제외 ~800 가용).
    win.geometry("1010x660")
    win.minsize(760, 420)      # 이보다 줄여도 Run/Save는 하단 고정이라 계속 보인다

    left = ctk.CTkFrame(win, width=SIDEBAR_W)
    left.pack(side="left", fill="y", padx=6, pady=6)
    left.pack_propagate(False)   # 자식 요구폭에 눌려 좁아지지 않도록 폭 고정
    right = ctk.CTkFrame(win)
    right.pack(side="left", fill="both", expand=True, padx=6, pady=6)

    # ── 사이드바 구조: 하단 고정 액션 영역 + 스크롤 가능한 입력 영역 ────────
    # 지시(레이아웃 수정): 어떤 언어·어떤 창 크기에서도 Run/Save가 보여야 한다.
    #   · actions를 **먼저** side="bottom"으로 pack → Tk가 남은 공간을 body에 주므로
    #     입력이 아무리 길어져도 버튼이 밀려나지 않는다(항상 최하단 고정).
    #   · body는 CTkScrollableFrame → 창을 세로로 줄이면 입력부만 스크롤된다.
    # 둘을 함께 쓴 이유: 하단 고정만으로는 창이 아주 작을 때 입력 필드에 접근할 수
    # 없고, 스크롤만으로는 버튼이 스크롤 안쪽에 숨는다.
    actions = ctk.CTkFrame(left, fg_color="transparent")
    actions.pack(side="bottom", fill="x", padx=6, pady=(2, 6))
    body = ctk.CTkScrollableFrame(left, fg_color="transparent",
                                  width=SIDEBAR_W - 34)
    body.pack(side="top", fill="both", expand=True, padx=2, pady=(4, 0))

    # ── i18n 재번역 레지스트리 ──────────────────────────────────────────
    # (위젯, 키) 쌍을 모아두고 언어 변경 시 한 번에 다시 입힌다. 위젯을 새로 만들지
    # 않으므로 입력값·스크롤 위치·계산 결과가 그대로 유지된다.
    _i18n_widgets = []      # [(widget, key), ...] — configure(text=T(key))
    _retranslators = []     # [callable, ...] — 텍스트 외 갱신(창 제목 등)

    def _reg(widget, key):
        _i18n_widgets.append((widget, key))
        widget.configure(text=T(key))
        return widget

    # 라벨은 전 행 같은 고정 폭(_LABEL_W)을 쓴다 — 입력칸 x 위치가 어긋나지 않도록.
    # 라벨 문구가 그 폭을 넘으면 입력칸이 밀리므로, 긴 설명은 라벨이 아니라 _note로
    # 내린다(예: edge margin의 "= Griddler Edge Gap").
    def _row(parent_, key, default):
        fr = ctk.CTkFrame(parent_, fg_color="transparent")
        fr.pack(fill="x", pady=2)
        lbl = ctk.CTkLabel(fr, width=_LABEL_W, anchor="w")
        _reg(lbl, key)
        lbl.pack(side="left")
        e = ctk.CTkEntry(fr, width=_ENTRY_W)
        e.insert(0, str(default))
        e.pack(side="left")
        return e

    def _range_row(parent_, key, dmin, dmax, dn):
        # (Phase 2) min / max / steps 3칸을 한 줄에. 기본 steps=1이면 단일값.
        fr = ctk.CTkFrame(parent_, fg_color="transparent")
        fr.pack(fill="x", pady=2)
        lbl = ctk.CTkLabel(fr, width=_LABEL_W, anchor="w")
        _reg(lbl, key)
        lbl.pack(side="left")
        # min/max 칸은 확정 결과값(pitch 1.767 / 2.193 등 소수 3자리)이 잘리지 않아야
        # 한다 — 실측 텍스트폭 33~34px + CTkEntry 내부 여백 ≈10px → 44px 필요.
        # steps는 정수 1~2자리라 34px면 충분하다. (_ENTRY_W_* 참조)
        emin = ctk.CTkEntry(fr, width=_ENTRY_W_RANGE)
        emin.insert(0, str(dmin)); emin.pack(side="left", padx=1)
        emax = ctk.CTkEntry(fr, width=_ENTRY_W_RANGE)
        emax.insert(0, str(dmax)); emax.pack(side="left", padx=1)
        en = ctk.CTkEntry(fr, width=_ENTRY_W_STEPS)
        en.insert(0, str(dn)); en.pack(side="left", padx=1)
        return emin, emax, en

    def _note(parent_, key):
        lbl = ctk.CTkLabel(parent_, font=ctk.CTkFont(size=9), text_color="gray",
                           anchor="w", justify="left", wraplength=_WRAP)
        _reg(lbl, key)
        lbl.pack(fill="x")
        return lbl

    # ── 언어 선택 (사이드바 최상단) ─────────────────────────────────────
    # 라벨을 세그먼트 버튼 **위쪽 줄**로 올린다 — 같은 줄에 두면 영문("Language")
    # 폭 때문에 버튼이 오른쪽 경계에 붙어 잘렸다. 좌우 패딩도 함께 준다.
    lang_lbl = ctk.CTkLabel(body, anchor="w", font=ctk.CTkFont(size=11))
    _reg(lang_lbl, "ui.language")
    lang_lbl.pack(fill="x", padx=6, pady=(2, 0))
    lang_row = ctk.CTkFrame(body, fg_color="transparent")
    lang_row.pack(fill="x", padx=6, pady=(0, 4))
    lang_var = ctk.StringVar(value=label_for(get_language()))
    _label_to_code = {label_for(c): c for c in LANGUAGES}

    title_lbl = ctk.CTkLabel(body, font=ctk.CTkFont(size=13, weight="bold"))
    _reg(title_lbl, "header.title")
    title_lbl.pack(pady=(2, 6))

    # preset (mainstream만 드롭다운; 0BB는 별도 안내)
    preset_lbl = ctk.CTkLabel(body, anchor="w")
    _reg(preset_lbl, "input.preset")
    preset_lbl.pack(fill="x")
    preset_var = ctk.StringVar(value="M10_SMBB_2025")
    ctk.CTkOptionMenu(body, variable=preset_var,
                      values=list(_presets.MAINSTREAM_PRESETS)).pack(fill="x", pady=2)
    _note(body, "note.preset_0bb")

    e_cell = _row(body, "input.preview_cell", 20.0)
    _note(body, "note.range_fields")
    e_wfmin, e_wfmax, e_wfn = _range_row(body, "input.finger_width", 20, 20, 1)
    e_pmin, e_pmax, e_pn = _range_row(body, "input.finger_pitch", 1.2, 2.4, 4)
    e_nbb = _row(body, "input.busbar_numbers", "6,8,10,12")
    _note(body, "note.busbar_numbers_format")
    e_wbmin, e_wbmax, e_wbn = _range_row(body, "input.busbar_width", 0.2, 0.2, 1)
    # (Phase 2) 물성 스윕 — 쉼표 구분 다중값. 기본=현재값 → 비트 동일.
    e_rhol = _row(body, "input.rho_l", "4.22")
    _note(body, "note.rho_l_compare")
    e_rhoc = _row(body, "input.rho_c", "10")
    # (Phase 1) 엣지 실버-프리 마진 (Griddler "Edge Gap" 동일 개념). 기본 1.0 mm.
    # 라벨은 짧게 두고 "= Griddler Edge Gap" 설명은 아래 note로 내렸다 — 라벨이
    # _LABEL_W를 넘으면 입력칸이 밀려 다른 행과 정렬이 어긋나기 때문.
    e_edge = _row(body, "input.edge_margin", 1.0)
    _note(body, "note.edge_margin")

    # busbar 광학 회수 f — 슬라이더(라이브) + 수치칸(양방향 동기).
    # recovery는 Route 2(adapter.RECOVERY_IS_POST_PROCESS)에서 순수 post-process라
    # 슬라이더 이동 시 FEM 재계산 없이 efficiency/loss만 즉시 재산출한다
    # (adapter.apply_recovery — 직접 호출과 비트동일).
    rec_lbl = ctk.CTkLabel(body, anchor="w", font=ctk.CTkFont(size=11, weight="bold"))
    _reg(rec_lbl, "input.recovery")
    rec_lbl.pack(fill="x", pady=(6, 0))
    rec_row = ctk.CTkFrame(body, fg_color="transparent")
    rec_row.pack(fill="x")
    rec_slider = ctk.CTkSlider(rec_row, from_=0.0, to=0.60, number_of_steps=60)
    rec_slider.set(0.25)
    rec_slider.pack(side="left", fill="x", expand=True, padx=(0, 6))
    e_rec = ctk.CTkEntry(rec_row, width=56)
    e_rec.insert(0, "0.25")
    e_rec.pack(side="left")
    # recovery 해석대 안내 — 값에 따라 문구가 바뀌므로 레지스트리 대신 재렌더로 갱신.
    rec_note_lbl = ctk.CTkLabel(body, text="", anchor="w", justify="left",
                                wraplength=_WRAP, font=ctk.CTkFont(size=9))
    rec_note_lbl.pack(fill="x")
    rec_assum_lbl = ctk.CTkLabel(body, font=ctk.CTkFont(size=9), text_color="#c0392b",
                                 anchor="w", justify="left", wraplength=_WRAP)
    _reg(rec_assum_lbl, "note.recovery_assumption")
    rec_assum_lbl.pack(fill="x")

    obj_lbl = ctk.CTkLabel(body, font=ctk.CTkFont(size=9), text_color="gray",
                           justify="left", anchor="w", wraplength=_WRAP)
    _reg(obj_lbl, "note.objective")
    obj_lbl.pack(fill="x", pady=(6, 2))

    # ── 하단 고정 액션 영역 (스크롤 밖) ──────────────────────────────────
    # Run/Save는 여기 들어가므로 입력이 아무리 길어져도, 창을 세로로 줄여도
    # 항상 보인다. 진행 표시줄도 함께 둔다(계산 중 상태가 스크롤에 숨으면 안 됨).
    prog = ctk.CTkLabel(actions, text="", anchor="w", justify="left",
                        wraplength=_WRAP, font=ctk.CTkFont(size=10))
    prog.pack(fill="x", pady=(2, 2))
    run_btn = ctk.CTkButton(actions)
    _reg(run_btn, "btn.run")
    run_btn.pack(fill="x", pady=2)
    save_btn = ctk.CTkButton(actions, fg_color="#2E7D32", hover_color="#1B5E20")
    _reg(save_btn, "btn.save_csv")
    save_btn.pack(fill="x", pady=(0, 2))

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
            return T("rec.specular", f=f), "#555555"
        if f < 0.31:
            return T("rec.lambertian_typical", f=f), "#00695C"
        if f < 0.43:
            return T("rec.lambertian_smooth", f=f), "#00695C"
        return T("rec.round_wire", f=f), "#c0392b"

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
            txt.insert("end", T("warn.n_probe_bumped", n=m0[0]))
        edge = _sweep.get("edge", 0.0)
        txt.insert("end", T("result.best_line", f=f, edge=edge,
                            wf=b["finger_width_um"], pitch=b["finger_pitch_mm"],
                            nbb=b["busbar_number"], wbb=b["busbar_width_mm"],
                            rho_l=b["rho_bulk_uohm_cm"], rho_c=b["rho_contact_mohm_cm2"]))
        txt.insert("end", T("result.best_metrics", eff=br["efficiency"],
                            loss=br["total_loss"]))
        txt.insert("end", T("result.top10_header"))
        for i, r in enumerate(sorted(results, key=lambda r: -r["results"]["efficiency"])[:10], 1):
            p = r["parameters"]; rr = r["results"]
            txt.insert("end", f"  {i:>2} {p['finger_width_um']:>3.0f} {p['finger_pitch_mm']:>4.2f} "
                              f"{p['busbar_number']:>3} {p['busbar_width_mm']:>4.2f} "
                              f"{p['rho_bulk_uohm_cm']:>5.2f} {p['rho_contact_mohm_cm2']:>4.1f} "
                              f"{p.get('edge_margin_mm', 0.0):>4.1f} {rr['efficiency']:>6.3f}\n")
        # ρ_L 비교(예: 9 as-cured vs 4.22 가압) — 각 ρL의 최고 eff 차이(%p).
        # 온도·시간이 같고 가압만 다른 쌍이라 차이가 곧 순수 가압 효과다.
        rho_ls = sorted(set(round(r["parameters"]["rho_bulk_uohm_cm"], 3) for r in results))
        if len(rho_ls) >= 2:
            txt.insert("end", T("result.rho_compare_header"))
            bestper = {}
            for r in results:
                rl = round(r["parameters"]["rho_bulk_uohm_cm"], 3)
                e = r["results"]["efficiency"]
                if rl not in bestper or e > bestper[rl]:
                    bestper[rl] = e
            hi_rl = max(rho_ls); lo_rl = min(rho_ls)
            for rl in rho_ls:
                txt.insert("end", T("result.rho_compare_row", rho=rl, eff=bestper[rl]))
            txt.insert("end", T("result.rho_compare_delta", hi=hi_rl, lo=lo_rl,
                                delta=bestper[lo_rl] - bestper[hi_rl]))

        sub = PT("plot.subtitle_fixed", wf=b["finger_width_um"],
                wbb=b["busbar_width_mm"], rho_l=b["rho_bulk_uohm_cm"],
                rho_c=b["rho_contact_mohm_cm2"], edge=edge)
        render_preview_plots(fig, slice_grid, _plot_state, subtitle=sub)
        canvas.draw()
        m = _sweep.get("model")
        model_txt = ""
        if m:
            npv, bumped, nmin, nmax = m
            model_txt = T("prog.model_info",
                          mode=T("prog.n_probe_bumped_short") if bumped
                          else T("prog.n_probe_eq"),
                          npv=npv, nmin=nmin // 1000, nmax=nmax // 1000)
        prog.configure(text=T("prog.done", total=_sweep["total"],
                              cell=_sweep["cell"], f=f, model=model_txt))

    # ── 언어 전환 ────────────────────────────────────────────────────────
    def _current_f():
        try:
            return max(0.0, min(0.60, float(e_rec.get())))
        except (ValueError, TypeError):
            return 0.25

    def _on_language(choice):
        """세그먼트 버튼 콜백 — 즉시 반영 + 설정 저장 + 결과 재렌더."""
        code = _label_to_code.get(choice, choice)
        if code == get_language():
            return
        set_language(code)                       # 설정 파일에 저장(다음 실행 유지)
        # 세그먼트 버튼의 선택 표시를 실제 언어와 동기화한다. 사용자가 버튼을 누른
        # 경우엔 위젯이 알아서 갱신하지만, 프로그램에서 호출하면(설정 복원·테스트)
        # 표시만 이전 언어에 남아 "KO인데 English가 눌린" 상태가 된다.
        lang_var.set(label_for(code))
        win.title(T("window.title"))
        for widget, key in _i18n_widgets:
            widget.configure(text=T(key))
        for fn in _retranslators:
            fn()
        # 이미 결과가 있으면 텍스트·그래프까지 새 언어로 다시 그린다(FEM 재계산 없음).
        if _sweep.get("results"):
            _render_results(_current_f())
        else:
            prog.configure(text="")
            rec_note_lbl.configure(text="")

    lang_seg = ctk.CTkSegmentedButton(
        lang_row, values=[label_for(c) for c in LANGUAGES],
        variable=lang_var, command=_on_language)
    lang_seg.pack(fill="x", expand=True)   # 자체 줄을 차지 → 오른쪽 경계 잘림 없음

    def _retranslate_route1_guard():
        # Route 1 가드 문구는 조건부라 레지스트리에 넣지 않고 별도로 갱신한다.
        if not _adapter.RECOVERY_IS_POST_PROCESS:
            rec_note_lbl.configure(text=T("warn.recovery_route1"), text_color="#c0392b")

    _retranslators.append(_retranslate_route1_guard)

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
        _retranslate_route1_guard()

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
                per = T("warn.per_combo_full") if cell >= 80.0 else T("warn.per_combo_small")
                _set_prog(T("warn.combo_explosion", total=total, per=per))
            else:
                _set_prog(T("prog.start", total=total))

            done = {"n": 0}

            def _prog(i, n, o):
                done["n"] += 1
                _set_prog(T("prog.running_n", done=done["n"], total=total))

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
            f0 = _current_f()
            parent.after(0, lambda: (_render_results(f0),
                                     run_btn.configure(state="normal")))
        except Exception as e:  # GUI가 죽지 않도록
            parent.after(0, lambda: (prog.configure(text=T("prog.error", msg=e)),
                                     run_btn.configure(state="normal")))

    def _on_run():
        run_btn.configure(state="disabled")
        prog.configure(text=T("prog.running"))
        threading.Thread(target=_do_run, daemon=True).start()

    def _save_csv():
        """스윕 전 조합을 모든 축 컬럼과 함께 CSV로 저장(cwd)."""
        import csv as _csv
        import os as _os
        results = _sweep.get("results")
        if not results:
            prog.configure(text=T("warn.no_results"))
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
        prog.configure(text=T("prog.csv_saved", path=path, n=len(results)))

    run_btn.configure(command=_on_run)
    save_btn.configure(command=_save_csv)

    # 테스트용 내부 핸들(비공개). 스윕 상태와 렌더/전환 함수가 클로저에 갇혀 있어
    # 헤드리스 검증(tests/test_i18n_ui.py)에서 "결과가 있는 상태의 언어 전환"을
    # 확인할 방법이 없다. GUI 동작에는 영향이 없다.
    win._fe_internals = {
        "sweep": _sweep,
        "render_results": _render_results,
        "switch_language": _on_language,
        "i18n_widgets": _i18n_widgets,
        # 레이아웃 검사용 프레임 핸들 — 스크롤 영역 안의 위젯은 부모 높이를 넘어도
        # 정상(스크롤됨)이라, 넘침 판정을 하려면 어느 위젯이 스크롤 안쪽인지
        # 구분해야 한다. tests/test_gui_layout.py가 이걸로 구분한다.
        "sidebar": left,
        "scroll_body": body,
        "actions": actions,
        "run_btn": run_btn,
        "save_btn": save_btn,
        # 언어 전환 후 결과·그래프가 실제로 다시 그려졌는지 검사하기 위한 핸들.
        "result_textbox": txt,
        "figure": fig,
        "progress_label": prog,
    }
    return win
