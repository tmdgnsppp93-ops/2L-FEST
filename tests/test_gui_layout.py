"""GUI 레이아웃 회귀 테스트 — 실제 Tk 위젯 좌표로 판정 (v28.47).

왜 필요한가: v28.47 첫 판에서 영문 안내가 2줄로 늘어나며 사이드바 하단이 창 밖으로
밀려 **Run/Save 버튼이 보이지 않았다**(툴 사용 불가). 당시 검사가 가로 폭만 봐서
놓쳤다. 여기서 세로 넘침과 버튼 가시성을 좌표로 확인해 회귀를 막는다.

스크린샷을 쓰지 않는 이유
------------------------
캡처는 사람 눈에 의존하고, macOS에서 Tk를 띄운 뒤 같은 프로세스에서 scipy sparse
solve를 돌리면 GIL 오류로 죽는다(실측). 이 테스트는 **엔진 스텁**을 넘겨
(ui는 fest를 Run 콜백에서만 쓴다) scipy를 아예 로드하지 않으므로 그 조합이
성립하지 않는다. 물리 수치 검증은 반대로 Tk 없이 다른 테스트가 담당한다.

CI 등 디스플레이가 없는 환경에서는 통째로 skip한다(사유 명시).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _gui_i18n_check as gui_check      # noqa: E402
from front_electrode import i18n         # noqa: E402

# conftest는 엔진을 헤드리스로 로드하면서 sys.modules의 customtkinter와
# matplotlib.backends.backend_tkagg를 **가짜로 교체**한다. 이 파일은 진짜 위젯
# 좌표를 재야 하므로, 아직 교체되지 않은 수집(collection) 시점에 진짜 모듈을
# 붙잡아 두고 테스트 동안 되돌려 쓴다.
try:
    import customtkinter as _REAL_CTK
    import matplotlib.backends.backend_tkagg as _REAL_TKAGG
    import tkinter as _REAL_TK
    import tkinter.font as _REAL_TKFONT
except Exception:                        # pragma: no cover - 디스플레이 없는 환경
    _REAL_CTK = _REAL_TKAGG = _REAL_TK = _REAL_TKFONT = None

pytestmark = pytest.mark.skipif(
    not gui_check.display_available(),
    reason="실제 Tk 창을 만들 수 없는 환경(헤드리스 CI 등) — "
           "레이아웃은 좌표 측정이 필요해 대체 불가. "
           "가짜 위젯 기반 i18n 검사는 test_i18n_ui.py가 담당한다.")


@pytest.fixture(autouse=True)
def _real_gui_modules(monkeypatch):
    """conftest가 끼워 넣은 가짜 GUI 모듈을 이 테스트 동안 진짜로 되돌린다."""
    for name, mod in (("customtkinter", _REAL_CTK),
                      ("matplotlib.backends.backend_tkagg", _REAL_TKAGG),
                      # tkinter/tkinter.font도 mock 대상이다 — 폰트 측정
                      # (tkfont.Font.measure)이 MagicMock이면 비교가 TypeError.
                      ("tkinter", _REAL_TK),
                      ("tkinter.font", _REAL_TKFONT)):
        if mod is not None:
            monkeypatch.setitem(sys.modules, name, mod)
    yield


@pytest.fixture(scope="module")
def tk_root():
    root = _REAL_CTK.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


# 엔진이 기동 시 하는 것과 같은 한글 폰트 설정(2L_FEST...py의 후보 목록과 동일).
_KR_FONT_CANDIDATES = ("AppleGothic", "Apple SD Gothic Neo", "Malgun Gothic",
                       "NanumGothic", "Noto Sans CJK KR")


@pytest.fixture
def hangul_font():
    """matplotlib에 한글 폰트를 물린다. 없으면 None(테스트가 폴백 경로로 분기)."""
    import matplotlib
    from matplotlib import font_manager
    from front_electrode import ui
    available = {f.name for f in font_manager.fontManager.ttflist}
    picked = next((c for c in _KR_FONT_CANDIDATES if c in available), None)
    old = matplotlib.rcParams["font.family"]
    if picked:
        matplotlib.rcParams["font.family"] = picked
    ui.hangul_renderable(force_recheck=True)
    yield picked if ui.hangul_renderable() else None
    matplotlib.rcParams["font.family"] = old
    ui.hangul_renderable(force_recheck=True)


@pytest.fixture(autouse=True)
def _restore_language():
    before = i18n.get_language()
    yield
    i18n.set_language(before, persist=False)


@pytest.fixture
def window(tk_root, request):
    lang = getattr(request, "param", "en")
    win = gui_check.build_window(lang, tk_root)
    yield win
    try:
        win.destroy()
    except Exception:
        pass


@pytest.mark.parametrize("window", ["en", "ko"], indirect=True)
@pytest.mark.parametrize("geo", [gui_check.DEFAULT_GEO, gui_check.MIN_GEO])
def test_no_overflow_and_buttons_visible(window, geo):
    """세로·가로 넘침이 없고 Run/Save가 창 안에 있어야 한다(양 언어 × 두 크기)."""
    r = gui_check.layout_report(window, geo)
    assert not r["overflow_v"], f"{geo} 세로 넘침: {r['overflow_v']}"
    assert not r["overflow_h"], f"{geo} 가로 넘침: {r['overflow_h']}"
    for key in ("run_btn", "save_btn"):
        b = r["buttons"][key]
        assert b["in_window"], (
            f"{geo} {key}가 창 밖: x={b['x']} y={b['y']} w={b['w']} h={b['h']} "
            f"(창 {b['win_w']}x{b['win_h']})")


@pytest.mark.parametrize("window", ["en", "ko"], indirect=True)
def test_all_widget_text_matches_language(window, request):
    """실제 렌더된 위젯 문자열이 전부 선택 언어 테이블 값인지."""
    lang = request.node.callspec.params["window"]
    rep = gui_check.i18n_report(window, lang)
    assert rep["n_texts"] > 20, "위젯 텍스트가 너무 적다 — 창이 제대로 안 만들어졌다"
    assert not rep["leftovers"], f"[{lang}] 언어 테이블 밖 문자열: {rep['leftovers']}"


def test_engine_is_not_touched(tk_root):
    """레이아웃 검사가 계산 경로를 타지 않는지 — 엔진 스텁이 접근되면 즉시 실패."""
    win = gui_check.build_window("en", tk_root)   # _EngineStub이 __getattr__에서 raise
    try:
        assert win._fe_internals["sweep"]["results"] is None
    finally:
        win.destroy()


def _fake_results():
    """표시 검증용 결과 6건 (ρL 2종 — ρ_L 비교 블록이 렌더되도록)."""
    out = []
    for pitch, nbb, eff, rho_l in ((1.8, 6, 21.0, 4.22), (1.8, 8, 21.2, 4.22),
                                   (2.2, 6, 21.1, 4.22), (2.2, 8, 21.3, 4.22),
                                   (1.8, 6, 20.5, 9.0), (2.2, 8, 20.8, 9.0)):
        out.append({
            "parameters": {
                "cell_w_mm": 20.0, "cell_h_mm": 20.0, "n_fingers": 10,
                "finger_width_um": 20.0, "finger_pitch_mm": pitch,
                "busbar_number": nbb, "busbar_width_mm": 0.2,
                "n_probe_points": 10, "busbar_recovery_factor": 0.0,
                "rho_bulk_uohm_cm": rho_l, "rho_contact_mohm_cm2": 10.0,
                "edge_margin_mm": 1.0,
            },
            "results": {
                "efficiency": eff, "total_loss": 1.0, "optical_loss": 0.6,
                "electrical_loss": 0.4, "raw_busbar_shading": 0.01,
                "effective_busbar_shading": 0.01, "recovered_busbar_light": 0.0,
                "finger_shading_loss": 0.02,
            },
            "engine_raw": {
                "Eff": eff, "Pmpp": eff, "Jmpp": 19.0, "Vmpp": 1.6,
                "P_shade": 0.6, "Pe": 0.1, "Pf_finger": 0.1,
                "Pf_busbar": 0.1, "Pc": 0.1,
            },
            "meta": {"nodes": 40000, "mode": "tandem"},
        })
    return out


def _capture(st):
    """현재 렌더 상태 스냅샷 — 결과 텍스트 / 그래프 문자열 / efficiency 값."""
    fig = st["figure"]
    plot = {
        "titles": [ax.get_title() for ax in fig.axes],
        "xlabels": [ax.get_xlabel() for ax in fig.axes],
        "ylabels": [ax.get_ylabel() for ax in fig.axes],
        "legend": [t.get_text() for ax in fig.axes
                   if ax.get_legend() for t in ax.get_legend().get_texts()],
        "suptitle": fig._suptitle.get_text() if fig._suptitle else "",
    }
    return {
        "text": st["result_textbox"].get("1.0", "end"),
        "prog": st["progress_label"].cget("text"),
        "plot": plot,
        "effs": [r["results"]["efficiency"] for r in st["sweep"]["results"]],
    }


def test_language_switch_preserves_results_bit_identical(tk_root, hangul_font):
    """KO ↔ EN 2회 왕복 — 표시는 바뀌고 efficiency는 비트 동일해야 한다."""
    win = gui_check.build_window("en", tk_root)
    try:
        st = win._fe_internals
        st["sweep"].update({
            "results": _fake_results(), "cell": 20.0, "total": 6, "edge": 1.0,
            "model": (10, True, 40000, 42000),
        })
        st["render_results"](0.25)
        en1 = _capture(st)

        st["switch_language"](i18n.label_for("ko"))
        win.update_idletasks()
        ko = _capture(st)

        st["switch_language"](i18n.label_for("en"))
        win.update_idletasks()
        en2 = _capture(st)

        # (a) 결과 텍스트 3블록이 언어를 따라간다
        assert "BEST (eff @" in en1["text"] and "BEST (eff @" in ko["text"]
        assert i18n.STRINGS["en"]["result.top10_header"].strip() in en1["text"]
        assert "comparison (best efficiency" in en1["text"], "EN ρ_L 블록 없음"
        assert "비교 (각 ρL" in ko["text"], "KO ρ_L 블록으로 안 바뀜"
        assert "comparison (best efficiency" not in ko["text"], "KO에 EN 문구 잔존"
        assert "비교 (각 ρL" not in en2["text"], "EN 복귀 후 KO 문구 잔존"
        # 진행 문구도 언어를 따른다
        assert en1["prog"].startswith("Done") and ko["prog"].startswith("완료")

        # (b) 그래프: subtitle은 언어를 따르고, 제목·축·범례는 **의도적으로** 동일
        #     (기술 용어는 번역하지 않는다는 원칙 — busbar/pitch/efficiency).
        assert "slice" in en1["plot"]["suptitle"]
        if hangul_font:
            assert en1["plot"]["suptitle"] != ko["plot"]["suptitle"], "subtitle 미변경"
            assert "단면" in ko["plot"]["suptitle"]
        else:
            # 한글 폰트가 없는 환경 → PT()가 영문으로 폴백하는 것이 정상(두부 방지).
            assert ko["plot"]["suptitle"] == en1["plot"]["suptitle"], \
                "폰트 없을 때 영문 폴백이 동작하지 않았다"
        assert en1["plot"]["titles"] == ko["plot"]["titles"]
        assert en1["plot"]["xlabels"] == ko["plot"]["xlabels"]
        assert en1["plot"]["ylabels"] == ko["plot"]["ylabels"]
        assert en1["plot"]["legend"] == ko["plot"]["legend"]
        assert en2["plot"]["suptitle"] == en1["plot"]["suptitle"], "EN 복귀 불일치"

        # (c) efficiency 비트 동일 — 재렌더 중 recovery 재적용으로 값이 흐르면 안 된다
        assert en1["effs"] == ko["effs"] == en2["effs"], (
            f"언어 전환으로 efficiency가 변했다: "
            f"EN={en1['effs']} KO={ko['effs']} EN2={en2['effs']}")
    finally:
        win.destroy()


# 창에 실제로 입력될 값들 — 확정 결과(pitch 1.767 / 2.193)와 기본 preset 값.
# "13.22"는 물리 기준값이 아니라 **폰트 폭 프로브**다(5자 소수 = 이 창에서 가장 넓은
# 실입력 문자열). 기준 ρ_L이 9로 바뀐 뒤에도 폭 검사 강도를 유지하려고 남겨둔다.
_MUST_FIT = ["1.767", "2.193", "2.600", "13.22", "9.00", "4.22", "0.20", "100.0", "20"]


def test_entry_widths_fit_real_values(tk_root):
    """입력칸이 실제 값을 자르지 않는지 — 특히 range 행(min/max/steps).

    v28.47에서 라벨 폭을 넓히며 range 칸을 44→36px로 줄였더니 확정 결과값
    pitch 1.767(텍스트폭 33px)·2.193(34px)이 잘렸다. 폭을 다시 만지면 여기서 걸린다.
    """
    import tkinter.font as tkfont
    win = gui_check.build_window("en", tk_root)
    try:
        sb = win._fe_internals["sidebar"]
        entries = [w for w in gui_check._walk(sb)
                   if w.__class__.__name__ == "CTkEntry"]
        assert entries, "입력칸을 못 찾았다"
        clipped = []
        for e in entries:
            width = e.winfo_width()
            font = tkfont.Font(font=e._entry.cget("font"))
            avail = width - 10          # CTkEntry 내부 테두리+패딩 실측 여유
            # steps 칸(가장 좁음)은 정수만 들어가므로 소수 3자리는 요구하지 않는다.
            wanted = ["1", "12"] if width <= 34 else _MUST_FIT
            for text in wanted:
                need = font.measure(text)
                if need > avail:
                    clipped.append((width, text, need, avail))
        assert not clipped, (
            "입력칸에서 값이 잘린다 (칸폭, 값, 텍스트폭, 가용폭): " + str(clipped))
    finally:
        win.destroy()


def test_minsize_matches_check_constant(tk_root):
    """창 minsize와 검사 스크립트의 MIN_GEO가 어긋나면 검사가 무의미해진다."""
    win = gui_check.build_window("en", tk_root)
    try:
        win.update_idletasks()
        # CTkToplevel.minsize()는 getter를 지원하지 않는다(인자 없이 부르면 TypeError)
        # → customtkinter가 보관하는 값을 읽는다.
        mw, mh = win._min_width, win._min_height
        w, h = (int(x) for x in gui_check.MIN_GEO.split("x"))
        assert (mw, mh) == (w, h), (
            f"ui.minsize({mw},{mh}) != _gui_i18n_check.MIN_GEO({w},{h}) — "
            "둘 중 하나를 고치면 다른 쪽도 맞출 것")
    finally:
        win.destroy()
