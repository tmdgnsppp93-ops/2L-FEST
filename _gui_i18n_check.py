# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""GUI 레이아웃 · i18n 검사 (수치 기반, 스크린샷 불필요).

왜 스크린샷을 안 쓰나
--------------------
캡처 방식은 (a) 사람이 눈으로 확인해야 하고 (b) macOS에서 Tk를 띄운 뒤 같은
프로세스에서 scipy sparse solve를 돌리면 GIL 오류로 죽는다(실측: Tk → screencapture
→ optimize_grid 순서에서 `PyEval_RestoreThread ... GIL released`; 순서를 뒤집으면
정상). 그래서 여기서는 **위젯 좌표를 직접 읽어 수치로 판정**한다.

크래시 회피 근거: `ui.open_optimizer_window(fest, parent)`는 `fest`를 Run 버튼
콜백 안에서만 쓴다(ui.py의 optimize_grid 호출 1곳). 따라서 **엔진을 스텁으로 넘기면
scipy가 이 프로세스에 아예 로드되지 않아** 위 조합이 성립할 수 없다. 수치 검증
(효율 비트 동일 등)은 반대로 Tk 없이 pytest에서 돈다 — 둘을 섞지 않는다.

검사 항목
--------
  1. 세로 넘침 — 사이드바 고정 영역(스크롤 밖) 위젯이 사이드바 높이를 넘는지
  2. 가로 넘침 — 사이드바 폭을 넘는 위젯
  3. Run / Save 가시성 — 기본 크기와 minsize 양쪽에서 창 영역 안에 있는지
  4. 1~3을 KO / EN 각각에서
  5. i18n 키 집합 일치 (KO/EN)

같은 로직을 tests/test_gui_layout.py가 import해서 pytest 회귀로 돌린다
(디스플레이가 없으면 skip). 이 스크립트는 사람이 표로 보려고 실행한다.

    python _gui_i18n_check.py
"""
import sys

DEFAULT_GEO = "1010x660"
MIN_GEO = "760x420"          # ui.open_optimizer_window의 minsize와 맞출 것


class _EngineStub:
    """엔진 자리 표시자 — Run을 누르지 않는 한 접근되지 않는다.

    실수로 계산 경로가 타면 조용히 틀린 결과를 내는 대신 즉시 터지게 한다.
    """

    def __getattr__(self, name):
        raise AssertionError(
            f"레이아웃 검사에서 엔진이 호출됐다(fest.{name}) — "
            "이 검사는 계산 없이 위젯 배치만 봐야 한다")


def display_available():
    """실제 Tk 창을 만들 수 있는 환경인지(헤드리스 CI면 False)."""
    try:
        import customtkinter as ctk
    except Exception:
        return False
    try:
        r = ctk.CTk()
        r.withdraw()
        r.destroy()
        return True
    except Exception:
        return False


def build_window(lang, root):
    """지정 언어로 최적화 창을 만든다(엔진 없이)."""
    from front_electrode import i18n
    from front_electrode import ui as fe_ui
    i18n.set_language(lang, persist=False)
    win = fe_ui.open_optimizer_window(_EngineStub(), root)
    win.deiconify()          # ismapped를 보려면 창이 떠 있어야 한다
    win.update_idletasks()
    win.update()
    return win


def _walk(widget, out=None):
    out = [] if out is None else out
    out.append(widget)
    for child in widget.winfo_children():
        _walk(child, out)
    return out


def _inside(widget, ancestor):
    probe = widget
    for _ in range(20):
        if probe is ancestor:
            return True
        probe = getattr(probe, "master", None)
        if probe is None:
            return False
    return False


def _label(w):
    try:
        t = w.cget("text")
    except Exception:
        t = None
    if isinstance(t, str) and t.strip():
        return t.replace("\n", " / ")[:52]
    return w.__class__.__name__


def layout_report(win, geo):
    """창을 geo 크기로 만든 뒤 넘침·버튼 좌표를 수치로 반환한다."""
    from front_electrode.ui import SIDEBAR_W
    st = win._fe_internals
    sidebar, body = st["sidebar"], st["scroll_body"]

    win.geometry(geo)
    win.update_idletasks()
    win.update()

    sx, sy = sidebar.winfo_rootx(), sidebar.winfo_rooty()
    sw, sh = sidebar.winfo_width(), sidebar.winfo_height()
    wx, wy = win.winfo_rootx(), win.winfo_rooty()
    ww, wh = win.winfo_width(), win.winfo_height()

    over_v, over_h = [], []
    for w in _walk(sidebar):
        if w is sidebar:
            continue
        # 스크롤 영역은 세로 검사에서 제외한다 — 안쪽 위젯은 물론이고
        # CTkScrollableFrame 자신도 **뷰포트가 아니라 내용 높이**를 보고하므로
        # 사이드바보다 큰 것이 정상이다(그게 스크롤의 목적). 검사 대상은 스크롤
        # 바깥, 즉 하단 고정 액션 영역과 스크롤 컨테이너의 외곽 프레임이다.
        in_scroll = _inside(w, body)
        top = w.winfo_rooty() - sy
        bottom = top + w.winfo_height()
        left_ = w.winfo_rootx() - sx
        right = left_ + w.winfo_width()
        if not in_scroll and bottom > sh + 1:
            over_v.append((_label(w), f"bottom={bottom} > 사이드바 {sh}"))
        if right > sw + 1:
            over_h.append((_label(w), f"right={right} > 사이드바 {sw}"))

    buttons = {}
    for key in ("run_btn", "save_btn"):
        b = st[key]
        bx, by = b.winfo_rootx() - wx, b.winfo_rooty() - wy
        bw, bh = b.winfo_width(), b.winfo_height()
        ok = (b.winfo_ismapped() and by >= 0 and bx >= 0
              and by + bh <= wh and bx + bw <= ww)
        buttons[key] = {"x": bx, "y": by, "w": bw, "h": bh,
                        "in_window": bool(ok), "win_w": ww, "win_h": wh}
    return {"geo": geo, "win": (ww, wh), "sidebar": (sw, sh),
            "sidebar_w_const": SIDEBAR_W,
            "overflow_v": over_v, "overflow_h": over_h, "buttons": buttons}


def i18n_report(win, lang):
    """표시 문자열이 전부 해당 언어 테이블 값인지."""
    from front_electrode import i18n
    import front_electrode
    allowed = {v for v in i18n.STRINGS[lang].values() if "{" not in v}
    allowed |= {i18n.label_for(c) for c in i18n.LANGUAGES}
    allowed |= set(front_electrode.MAINSTREAM_PRESETS)
    texts = []
    for w in _walk(win):
        try:
            t = w.cget("text")
        except Exception:
            continue
        if isinstance(t, str) and t.strip():
            texts.append(t)
    return {"n_texts": len(texts), "leftovers": [t for t in texts if t not in allowed]}


def run_all():
    """KO/EN × (기본, minsize) 전수 측정 → (표 문자열, 실패목록)."""
    from front_electrode import i18n
    import customtkinter as ctk

    saved = i18n.load_settings()
    before = i18n.get_language()
    lines, failures = [], []

    gaps = i18n.missing_keys()
    lines.append(f"[i18n] KO/EN 키 집합 일치: {'OK' if not gaps else gaps}")
    if gaps:
        failures.append(f"i18n 키 누락: {gaps}")

    root = ctk.CTk()
    root.withdraw()
    lines.append("")
    lines.append(f"{'lang':<5} {'size':<10} {'넘침(가로)':<12} {'넘침(세로)':<12} "
                 f"{'Run (x,y,w,h)':<24} {'in':<4} {'Save (x,y,w,h)':<24} {'in':<4}")
    lines.append("-" * 104)
    for lang in ("en", "ko"):
        win = build_window(lang, root)
        rep_i18n = i18n_report(win, lang)
        if rep_i18n["leftovers"]:
            failures.append(f"{lang}: 번역 누락 {rep_i18n['leftovers']}")
        for geo in (DEFAULT_GEO, MIN_GEO):
            r = layout_report(win, geo)
            rb, sb = r["buttons"]["run_btn"], r["buttons"]["save_btn"]
            lines.append(
                f"{lang:<5} {geo:<10} "
                f"{(str(len(r['overflow_h'])) + '건') if r['overflow_h'] else '없음':<12} "
                f"{(str(len(r['overflow_v'])) + '건') if r['overflow_v'] else '없음':<12} "
                f"{f'({rb[chr(120)]},{rb[chr(121)]},{rb[chr(119)]},{rb[chr(104)]})':<24} "
                f"{'OK' if rb['in_window'] else 'NG':<4} "
                f"{f'({sb[chr(120)]},{sb[chr(121)]},{sb[chr(119)]},{sb[chr(104)]})':<24} "
                f"{'OK' if sb['in_window'] else 'NG':<4}")
            for lbl, why in r["overflow_h"]:
                lines.append(f"      ! 가로 {lbl!r} — {why}")
                failures.append(f"{lang}@{geo}: 가로 넘침 {lbl!r}")
            for lbl, why in r["overflow_v"]:
                lines.append(f"      ! 세로 {lbl!r} — {why}")
                failures.append(f"{lang}@{geo}: 세로 넘침 {lbl!r}")
            if not rb["in_window"]:
                failures.append(f"{lang}@{geo}: Run 버튼 창 밖")
            if not sb["in_window"]:
                failures.append(f"{lang}@{geo}: Save 버튼 창 밖")
        lines.append(f"      [{lang}] 위젯 텍스트 {rep_i18n['n_texts']}개, "
                     f"언어 테이블 밖 {len(rep_i18n['leftovers'])}개")
        win.destroy()

    # 언어 전환이 창 재생성 없이 반영되는지
    win = build_window("en", root)
    before_ids = {id(w) for w in _walk(win)}
    win._fe_internals["switch_language"](i18n.label_for("ko"))
    win.update_idletasks()
    same = before_ids == {id(w) for w in _walk(win)}
    def _text_of(w):
        try:
            return w.cget("text")
        except Exception:      # text 옵션이 없는 위젯(Toplevel/Frame 등)
            return None

    ko_hit = any(_text_of(w) == i18n.STRINGS["ko"]["note.range_fields"]
                 for w in _walk(win))
    lines.append("")
    lines.append(f"[switch] 위젯 재사용: {same} | KO 문구 반영: {ko_hit}")
    if not (same and ko_hit):
        failures.append("switch: 즉시 반영 실패")
    win.destroy()
    root.destroy()

    # 사용자 설정 원복
    i18n.set_language(before, persist=False)
    if saved:
        i18n.save_settings(saved)
    else:
        import os
        try:
            os.remove(i18n.SETTINGS_PATH)
        except OSError:
            pass
    return "\n".join(lines), failures


def main():
    if not display_available():
        print("SKIP — 디스플레이가 없어 실제 Tk 창을 만들 수 없다(헤드리스 환경).")
        return 0
    table, failures = run_all()
    print(table)
    print()
    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        return 1
    print("OK — KO/EN 전수 일치, 가로·세로 넘침 없음, Run/Save 항상 창 안")
    return 0


if __name__ == "__main__":
    sys.exit(main())
