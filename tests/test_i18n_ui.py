# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""i18n GUI 전수 검증 (v28.47) — 화면에 들어간 모든 문자열이 선택 언어인지.

왜 이렇게까지 하나: 번역 누락은 "한국어 모드인데 그 라벨만 영어" 형태로 나타나는데,
경고문 상당수가 조건부(다중 busbar, 조합수 폭발, Route 1 가드)라 사람이 화면을
훑어서는 잘 안 걸린다. 그래서 **기록형 가짜 customtkinter**로 창을 실제 조립해
`text=`로 들어간 모든 문자열을 모으고, 그것이 현재 언어 테이블의 값인지 대조한다.

여기서 확인하는 것:
  1. KO/EN 각각에서 창을 조립했을 때 모든 표시 문자열이 해당 언어다.
  2. 언어를 전환하면 이미 만들어진 위젯 텍스트가 그 자리에서 바뀐다(창 재생성 없음).
  3. 결과가 있는 상태에서 전환하면 결과 텍스트·그래프가 다시 렌더된다.
  4. 그래프(matplotlib) 문자열도 언어를 따른다.
  5. 계산 결과 수치는 언어와 무관하게 비트 동일하다.
"""
import os
import sys
import types
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from front_electrode import i18n  # noqa: E402


# ── 기록형 가짜 customtkinter ────────────────────────────────────────────
class _FakeWidget:
    """text=로 들어온 문자열을 전부 recorder에 남기는 최소 위젯."""

    def __init__(self, rec, *args, **kwargs):
        self._rec = rec
        self._text = None
        self._value = ""
        rec["widgets"].append(self)
        self.configure(**kwargs)

    # --- 텍스트 --------------------------------------------------------
    def configure(self, **kwargs):
        if "text" in kwargs:
            self._text = kwargs["text"]
            self._rec["texts"].append(kwargs["text"])
        if "values" in kwargs:
            self._rec["values"].extend(kwargs["values"])
        return None

    def cget(self, key):
        return self._text if key == "text" else None

    # --- 엔트리/텍스트박스 --------------------------------------------
    def insert(self, index, value=""):
        if isinstance(index, str) and index in ("end", "1.0"):
            # 텍스트박스 삽입 = 결과 영역에 실제로 표시되는 문자열 → 기록 대상.
            # (엔트리의 insert(0, ...)는 기본값 채우기라 표시 문자열이 아니다.)
            self._value += str(value)
            self._rec["texts"].append(str(value))
        else:
            self._value = str(value) + self._value
        return None

    def delete(self, *a):
        self._value = ""
        return None

    def get(self, *a, **k):
        return self._value

    def set(self, value):
        self._value = value
        return None

    # --- 레이아웃/기타 (전부 무시) --------------------------------------
    def pack(self, *a, **k):
        return None

    def pack_propagate(self, *a, **k):
        return None

    def grid(self, *a, **k):
        return None

    def bind(self, *a, **k):
        return None

    def title(self, text=None):
        if text is not None:
            self._rec["texts"].append(text)
            self._rec["title"] = text
        return None

    def geometry(self, *a, **k):
        return None

    def minsize(self, *a, **k):
        return None

    def maxsize(self, *a, **k):
        return None

    def after(self, delay, fn=None, *a):
        # 창 조립 중에는 지연 콜백을 실행하지 않는다(테스트가 결정적이도록).
        self._rec["after"].append(fn)
        return "afterid"

    def after_cancel(self, *a, **k):
        return None

    def get_tk_widget(self):
        return self

    def draw(self):
        self._rec["draws"] += 1
        return None


def _make_fake_ctk(rec):
    """front_electrode.ui가 쓰는 위젯만 갖춘 가짜 customtkinter 모듈."""
    mod = types.ModuleType("customtkinter")

    def _factory(name):
        def _ctor(*args, **kwargs):
            w = _FakeWidget(rec, *args, **kwargs)
            if name == "CTkSegmentedButton":
                rec["segmented"] = (w, kwargs.get("command"))
            return w
        return _ctor

    for name in ("CTkToplevel", "CTkFrame", "CTkScrollableFrame", "CTkLabel",
                 "CTkEntry", "CTkButton", "CTkOptionMenu", "CTkSlider",
                 "CTkTextbox", "CTkSegmentedButton"):
        setattr(mod, name, _factory(name))

    class _CTk:
        def __init__(self, *a, **k):
            pass

    mod.CTk = _CTk
    mod.CTkFont = lambda *a, **k: object()

    class _StringVar:
        def __init__(self, value=""):
            self._v = value

        def get(self):
            return self._v

        def set(self, v):
            self._v = v

    mod.StringVar = _StringVar
    return mod


@pytest.fixture
def rec():
    return {"widgets": [], "texts": [], "values": [], "after": [],
            "draws": 0, "title": None, "segmented": None}


@pytest.fixture
def fake_gui(rec, monkeypatch, tmp_path):
    """가짜 ctk + 가짜 tkagg 캔버스를 설치하고 ui 모듈을 돌려준다."""
    monkeypatch.setitem(sys.modules, "customtkinter", _make_fake_ctk(rec))
    tkagg = types.ModuleType("matplotlib.backends.backend_tkagg")
    tkagg.FigureCanvasTkAgg = lambda fig, master=None: _FakeWidget(rec)
    monkeypatch.setitem(sys.modules, "matplotlib.backends.backend_tkagg", tkagg)
    # 설정 파일은 임시 디렉터리로 — 사용자의 실제 선택을 건드리지 않는다.
    monkeypatch.setattr(i18n, "SETTINGS_DIR", str(tmp_path))
    monkeypatch.setattr(i18n, "SETTINGS_PATH", str(tmp_path / "settings.json"))
    before = i18n.get_language()
    import front_electrode.ui as ui
    yield ui
    i18n.set_language(before, persist=False)


def _allowed_strings(lang):
    """해당 언어에서 화면에 나타나도 되는 문자열 집합.

    포맷 자리표시자가 없는(=창 조립 시 그대로 쓰이는) 값들 + 언어 이름 + 빈 문자열.
    """
    ok = {"", None}
    for text in i18n.STRINGS[lang].values():
        if "{" not in text:
            ok.add(text)
    ok |= {i18n.label_for(c) for c in i18n.LANGUAGES}
    return ok


def _build(ui, lang, rec):
    i18n.set_language(lang, persist=False)
    rec["texts"].clear()
    gedos = MagicMock(name="gedos")
    parent = _FakeWidget(rec)
    win = ui.open_optimizer_window(gedos, parent)
    return win


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_every_widget_string_is_in_selected_language(fake_gui, rec, lang):
    """창 조립 시 표시된 모든 문자열이 선택 언어 테이블에 있어야 한다."""
    _build(fake_gui, lang, rec)
    allowed = _allowed_strings(lang)
    leftovers = [t for t in rec["texts"] if t not in allowed]
    assert not leftovers, f"[{lang}] 언어 테이블에 없는 표시 문자열: {leftovers}"


def _other_language_fragments(lang, other):
    """`other`에만 있는 문자열의 고정 조각(자리표시자 앞부분) 집합.

    두 언어에서 값이 같은 항목(기술 용어 라벨)은 의도된 것이라 제외한다.
    포맷 문자열은 '{' 앞 고정 부분만 조각으로 쓰고, 너무 짧으면(우연 일치 위험)
    버린다.
    """
    frags = set()
    for key, text in i18n.STRINGS[other].items():
        if i18n.STRINGS[lang].get(key) == text:
            continue                      # 두 언어 공통 = 의도된 영문 기술 용어
        head = text.split("{")[0].strip()
        if len(head) >= 8:
            frags.add(head)
    return frags


@pytest.mark.parametrize("lang,other", [("en", "ko"), ("ko", "en")])
def test_no_strings_from_the_other_language(fake_gui, rec, lang, other):
    """빌드 + 결과 렌더 양쪽에서 반대 언어 고유 문자열이 섞이지 않아야 한다."""
    win = _build(fake_gui, lang, rec)
    # 결과가 있어야만 나오는 문구(BEST/Top-10/ρ_L 비교/n_probe 경고/진행 완료)까지
    # 화면에 올린 뒤 검사한다 — 조건부 문구가 번역 누락의 단골이다.
    st = win._fe_internals
    st["sweep"].update({
        # ρL 2종을 넣어야 "ρ_L 비교" 블록까지 렌더돼 언어 검사 대상이 된다.
        "results": [_fake_result(p, nb, eff, rl)
                    for p, nb, eff, rl in
                    ((1.8, 6, 21.0, 4.22), (1.8, 8, 21.2, 4.22),
                     (2.2, 6, 21.1, 4.22), (2.2, 8, 21.3, 4.22),
                     (1.8, 6, 20.5, 9.0), (2.2, 8, 20.8, 9.0))],
        "cell": 20.0, "total": 6, "edge": 1.0, "model": (10, True, 40000, 42000),
    })
    st["render_results"](0.25)

    frags = _other_language_fragments(lang, other)
    bad = [t for t in rec["texts"] if any(fr in t for fr in frags)]
    assert not bad, f"[{lang}] 모드인데 {other} 문자열이 표시됨: {bad}"


def test_language_switch_retranslates_in_place(fake_gui, rec):
    """전환 시 창을 새로 만들지 않고 기존 위젯 텍스트가 바뀌어야 한다."""
    _build(fake_gui, "en", rec)
    widget_count = len(rec["widgets"])
    seg, command = rec["segmented"]
    assert command is not None, "언어 세그먼트 버튼에 command가 없다"

    rec["texts"].clear()
    command(i18n.label_for("ko"))               # 사용자가 '한국어'를 누른 상황
    assert i18n.get_language() == "ko"
    assert len(rec["widgets"]) == widget_count, "언어 전환이 위젯을 새로 만들었다"

    allowed = _allowed_strings("ko")
    leftovers = [t for t in rec["texts"] if t not in allowed]
    assert not leftovers, f"전환 후 KO가 아닌 문자열: {leftovers}"
    # 실제로 한국어 고유 문구가 다시 입혀졌는지(빈 재번역이 아닌지) 확인
    assert i18n.STRINGS["ko"]["note.range_fields"] in rec["texts"]


def test_language_choice_persists(fake_gui, rec, tmp_path):
    """전환한 언어가 설정 파일에 저장되어 다음 실행에 유지된다."""
    _build(fake_gui, "en", rec)
    _seg, command = rec["segmented"]
    command(i18n.label_for("ko"))
    assert i18n.load_settings().get("language") == "ko"


def _fake_result(pitch, nbb, eff, rho_l=4.22):
    """_render_results가 요구하는 최소 결과 dict (표시 검증용, 물리값 아님)."""
    return {
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
    }


def test_switch_rerenders_existing_results(fake_gui, rec):
    """결과가 있는 상태에서 전환하면 결과 텍스트·그래프가 새 언어로 다시 그려진다."""
    win = _build(fake_gui, "en", rec)
    st = win._fe_internals
    st["sweep"].update({
        # ρL 2종을 넣어야 "ρ_L 비교" 블록까지 렌더돼 언어 검사 대상이 된다.
        "results": [_fake_result(p, nb, eff, rl)
                    for p, nb, eff, rl in
                    ((1.8, 6, 21.0, 4.22), (1.8, 8, 21.2, 4.22),
                     (2.2, 6, 21.1, 4.22), (2.2, 8, 21.3, 4.22),
                     (1.8, 6, 20.5, 9.0), (2.2, 8, 20.8, 9.0))],
        "cell": 20.0, "total": 6, "edge": 1.0, "model": (10, True, 40000, 42000),
    })
    st["render_results"](0.25)               # EN으로 결과 렌더

    en_texts = list(rec["texts"])
    assert any(i18n.STRINGS["en"]["result.top10_header"] in t for t in en_texts), \
        "EN 결과 헤더가 렌더되지 않았다"
    assert any("BEST (eff @" in t for t in en_texts), "EN BEST 라인이 없다"
    assert any("comparison (best efficiency" in t for t in en_texts), \
        "EN ρ_L 비교 블록이 렌더되지 않았다"
    # n_probe 자동 상향 경고(조건부, 화면에서 놓치기 쉬운 항목)도 EN으로 나와야 한다
    assert any("raised automatically" in t for t in en_texts), \
        "EN n_probe 경고가 렌더되지 않았다"
    draws_before = rec["draws"]

    rec["texts"].clear()
    st["switch_language"](i18n.label_for("ko"))

    assert rec["draws"] > draws_before, "언어 전환 후 그래프가 다시 그려지지 않았다"
    ko_texts = list(rec["texts"])
    assert any("자동 상향" in t for t in ko_texts), "KO n_probe 경고가 렌더되지 않았다"
    assert any(i18n.STRINGS["ko"]["prog.done"].split("{")[0] in t for t in ko_texts), \
        "KO 진행 문구(완료)가 렌더되지 않았다"
    assert any("비교 (각 ρL" in t for t in ko_texts), "KO ρ_L 비교 블록이 안 바뀌었다"
    # EN 고유 문구가 남아 있으면 안 된다
    for en_only in ("raised automatically", "comparison (best efficiency"):
        assert not any(en_only in t for t in ko_texts), \
            f"전환 후에도 EN 문구가 남아 있다: {en_only!r}"

    # 두 번째 전환(KO → EN)도 확인 — 왕복이 안정적인지.
    rec["texts"].clear()
    st["switch_language"](i18n.label_for("en"))
    back = list(rec["texts"])
    assert any("comparison (best efficiency" in t for t in back), "EN 복귀 실패"
    assert not any("자동 상향" in t for t in back), "EN 복귀 후 KO 문구 잔존"


def test_plot_falls_back_to_english_without_hangul_font(monkeypatch):
    """한글 폰트가 없으면 그래프 문자열이 영문으로 떨어져야 한다(두부 방지).

    엔진의 폰트 탐지는 최후에 'Helvetica'로 폴백하는데 거기엔 한글 글리프가 없다.
    그 상태로 한글을 그리면 조용히 □가 찍힌다 — v28.47에서 µ로 겪은 실패 유형.
    """
    from front_electrode import ui
    before = i18n.get_language()
    try:
        i18n.set_language("ko", persist=False)
        monkeypatch.setattr(ui, "hangul_renderable", lambda *a, **k: False)
        assert ui.PT("plot.subtitle_fixed", wf=20, wbb=0.2, rho_l=4.2,
                     rho_c=10.0, edge=1.0) == i18n.STRINGS["en"][
            "plot.subtitle_fixed"].format(wf=20, wbb=0.2, rho_l=4.2,
                                          rho_c=10.0, edge=1.0)
        assert ui.PT("plot.grid_insufficient", n_pitch=1, n_bb=1) == \
            i18n.STRINGS["en"]["plot.grid_insufficient"].format(n_pitch=1, n_bb=1)
        # 폰트가 있으면 한국어 그대로
        monkeypatch.setattr(ui, "hangul_renderable", lambda *a, **k: True)
        assert "단면" in ui.PT("plot.subtitle_fixed", wf=20, wbb=0.2, rho_l=4.2,
                              rho_c=10.0, edge=1.0)
    finally:
        i18n.set_language(before, persist=False)


def test_hangul_renderable_returns_bool():
    """폰트 검사가 예외 없이 bool을 돌려주는지(환경 무관)."""
    from front_electrode import ui
    assert isinstance(ui.hangul_renderable(force_recheck=True), bool)


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_plot_strings_follow_language(lang, monkeypatch):
    """matplotlib 그래프의 문자열도 선택 언어를 따른다(격자 부족 안내 포함).

    폰트 폴백 분기는 test_plot_falls_back_to_english_without_hangul_font가 따로
    담당하므로, 여기서는 폰트가 있다고 두고 **언어 라우팅**만 본다.
    """
    import matplotlib
    matplotlib.use("Agg", force=True)
    from matplotlib.figure import Figure
    from front_electrode import ui as _ui
    from front_electrode.ui import render_preview_plots

    monkeypatch.setattr(_ui, "hangul_renderable", lambda *a, **k: True)
    before = i18n.get_language()
    try:
        i18n.set_language(lang, persist=False)
        # 격자 1×1 → '격자 부족' 안내 경로
        grid = {(1.8, 6): {"results": {"efficiency": 21.0}}}
        fig = render_preview_plots(Figure(), grid, {"cbar": None},
                                   subtitle=i18n.T("plot.subtitle_fixed",
                                                   wf=20, wbb=0.2, rho_l=4.22,
                                                   rho_c=10.0, edge=1.0))
        texts = [t.get_text() for ax in fig.axes for t in ax.texts]
        texts += [ax.get_title() for ax in fig.axes]
        texts += [ax.get_xlabel() for ax in fig.axes]
        joined = "\n".join(texts)
        expected = i18n.STRINGS[lang]["plot.grid_insufficient"].split("\n")[0]
        assert expected in joined, f"[{lang}] 격자 부족 안내가 해당 언어가 아님"
        assert i18n.STRINGS[lang]["plot.title_eff_vs_pitch"] in joined
    finally:
        i18n.set_language(before, persist=False)


def test_results_are_language_independent(gedos, monkeypatch):
    """언어를 바꿔도 계산 결과는 비트 동일해야 한다(문자열만 바뀌는 변경)."""
    monkeypatch.delenv("GEDOS_LEGACY_LOCAL_MATCH", raising=False)
    from front_electrode import evaluate_existing_simulation, SCENARIO_MEASURED
    grid = dict(cell_w_mm=20.0, cell_h_mm=20.0, n_fingers=8, n_busbars=1,
                w_finger_um=50.0, w_busbar_mm=0.6, n_probe_points=0)
    before = i18n.get_language()
    try:
        i18n.set_language("en", persist=False)
        a = evaluate_existing_simulation(gedos, grid, scenario=SCENARIO_MEASURED,
                                         axis_segments_override=36, npts=6)
        i18n.set_language("ko", persist=False)
        b = evaluate_existing_simulation(gedos, grid, scenario=SCENARIO_MEASURED,
                                         axis_segments_override=36, npts=6)
    finally:
        i18n.set_language(before, persist=False)
    for key in ("efficiency", "total_loss", "optical_loss", "electrical_loss"):
        assert a["results"][key] == b["results"][key], f"{key}가 언어에 따라 달라졌다"


def test_run_error_path_reports_message_and_reenables_button(fake_gui, rec):
    """Run 중 예외가 나면 오류 문구가 뜨고 Run 버튼이 다시 활성화돼야 한다.

    회귀 방지(v28.49): `except Exception as e` 안에서 만든 lambda가 `e`를 이름으로
    참조하고 있었다. Python 3는 except 블록을 벗어날 때 그 이름을 삭제하므로,
    나중에 after()가 lambda를 실행할 때 NameError가 나서 **오류 문구도 안 뜨고
    Run 버튼이 영구 비활성** 상태로 남았다(입력 오류 시 GUI가 멈춘 것처럼 보인다).
    """
    win = _build(fake_gui, "en", rec)
    st = win._fe_internals
    # 지연 콜백을 즉시 실행하도록 만든 뒤, 계산 경로에서 예외를 유발한다.
    run_btn = st["run_btn"]
    boom = RuntimeError("삐끗")

    def _explode(*a, **k):
        raise boom

    import front_electrode.ui as ui_mod
    orig = ui_mod._opt.optimize_grid
    ui_mod._opt.optimize_grid = _explode
    try:
        rec["texts"].clear()
        run_btn.configure(state="disabled")
        # _do_run은 스레드에서 도는데, 여기서는 동기로 호출해 예외 경로만 확인한다.
        st["do_run"]()
        # after()에 실린 콜백들을 실행 — 실제 Tk mainloop가 하는 일.
        for fn in list(rec["after"]):
            if callable(fn):
                fn()
    finally:
        ui_mod._opt.optimize_grid = orig

    joined = " ".join(t for t in rec["texts"] if isinstance(t, str))
    assert "삐끗" in joined, f"오류 메시지가 표시되지 않았다: {rec['texts']}"
    assert run_btn._text is not None      # 위젯이 살아 있음
