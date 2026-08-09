"""실제 GUI로 i18n 전수 확인 (개발 도구 — pytest 아님, 디스플레이 필요).

`_gui_test.py`와 같은 성격의 수동 스모크 도구다. 진짜 customtkinter 위젯으로
전면전극 최적화 창을 조립해서:

  1. KO / EN 각각에서 **실제로 렌더된 모든 위젯 텍스트**를 수집해 해당 언어인지 확인
  2. 언어 전환이 창 재생성 없이 그 자리에서 반영되는지 확인
  3. 사이드바 **레이아웃 넘침**을 확인 (영문이 한글보다 길어 폭을 넘길 수 있다)

pytest 스위트(tests/test_i18n_ui.py)는 가짜 위젯으로 같은 내용을 검사하므로 CI에
디스플레이가 없어도 돌아간다. 이 스크립트는 실제 폰트·실제 배치까지 보는 용도다.

    python _gui_i18n_check.py
"""
import importlib.util
import sys

SIDEBAR_W = 330      # ui.open_optimizer_window의 left 프레임 폭과 맞출 것


def _load_engine():
    spec = importlib.util.spec_from_file_location("fest", "2L_FEST_v28_18_wf_wired.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fest"] = mod
    try:
        spec.loader.exec_module(mod)
    except SystemExit:
        pass
    return mod


def _walk(widget, out=None):
    out = [] if out is None else out
    out.append(widget)
    for child in widget.winfo_children():
        _walk(child, out)
    return out


def _texts(win):
    """창 안의 모든 위젯에서 표시 문자열을 긁어온다(라벨/버튼/텍스트박스)."""
    found = []
    for w in _walk(win):
        try:
            t = w.cget("text")
        except Exception:
            t = None
        if isinstance(t, str) and t.strip():
            found.append((w, t))
    return found


def _overflow(win):
    """사이드바 폭을 넘기는 위젯 목록 [(텍스트, 요구폭)]."""
    win.update_idletasks()
    bad = []
    for w in _walk(win):
        try:
            req = w.winfo_reqwidth()
            t = w.cget("text")
        except Exception:
            continue
        if isinstance(t, str) and t.strip() and req > SIDEBAR_W:
            # 우측 결과 패널 위젯은 사이드바 제약을 받지 않으므로 좌측만 본다.
            master = getattr(w, "master", None)
            root_side = None
            probe = w
            for _ in range(6):
                probe = getattr(probe, "master", None)
                if probe is None:
                    break
                root_side = probe
            if master is not None:
                bad.append((t[:60].replace("\n", " / "), req))
    return bad


def main():
    from front_electrode import i18n
    from front_electrode import ui as fe_ui
    import customtkinter as ctk

    fest = _load_engine()
    root = ctk.CTk()
    root.withdraw()          # 메인 창은 숨김 — 최적화 창만 확인

    # 이 도구는 실제 전환 경로(설정 저장 포함)를 타므로 사용자의 언어 선택을
    # 덮어쓴다. 원래 상태를 기억해 두고 끝날 때 되돌린다.
    _saved_settings = i18n.load_settings()
    _existed = bool(_saved_settings)

    failures = []

    for lang in ("en", "ko"):
        i18n.set_language(lang, persist=False)
        win = fe_ui.open_optimizer_window(fest, root)
        win.withdraw()
        win.update_idletasks()

        allowed = {v for v in i18n.STRINGS[lang].values() if "{" not in v}
        allowed |= {i18n.label_for(c) for c in i18n.LANGUAGES}
        allowed |= set(__import__("front_electrode").MAINSTREAM_PRESETS)

        leftovers = [t for _w, t in _texts(win) if t not in allowed]
        print(f"[{lang}] 위젯 텍스트 {len(_texts(win))}개 — "
              f"언어 테이블 밖: {len(leftovers)}")
        for t in leftovers:
            print(f"    ! {t!r}")
        if leftovers:
            failures.append(f"{lang}: 번역 누락 {len(leftovers)}건")

        over = _overflow(win)
        print(f"[{lang}] 사이드바({SIDEBAR_W}px) 초과 위젯: {len(over)}")
        for t, req in over:
            print(f"    ! {req}px  {t!r}")

        win.destroy()

    # 언어 전환이 창 재생성 없이 반영되는지
    i18n.set_language("en", persist=False)
    win = fe_ui.open_optimizer_window(fest, root)
    win.withdraw()
    before_ids = {id(w) for w in _walk(win)}
    win._fe_internals["switch_language"](i18n.label_for("ko"))
    win.update_idletasks()
    after_ids = {id(w) for w in _walk(win)}
    same_widgets = before_ids == after_ids
    ko_hit = any(t == i18n.STRINGS["ko"]["note.range_fields"] for _w, t in _texts(win))
    print(f"[switch] 위젯 재사용: {same_widgets} | KO 문구 반영: {ko_hit}")
    if not (same_widgets and ko_hit):
        failures.append("switch: 즉시 반영 실패")
    win.destroy()
    root.destroy()

    # 사용자 설정 원복 — 없던 파일이면 지운다.
    import os as _os
    if _existed:
        i18n.save_settings(_saved_settings)
    else:
        try:
            _os.remove(i18n.SETTINGS_PATH)
        except OSError:
            pass
    i18n.reset_language_cache()

    print()
    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("OK — KO/EN 전수 일치, 레이아웃 넘침 없음, 즉시 전환 동작")
    return 0


if __name__ == "__main__":
    sys.exit(main())
