"""front_electrode i18n — 한국어 / English 문자열 중앙 저장소 (v28.47).

배경: 외국인 연구원이 이 툴을 쓰게 되면서 GUI 문자열의 한국어 하드코딩을 걷어낸다.
저작권 등록 준비도 겸한다.

사용법
------
    from .i18n import T, set_language
    label = T("input.finger_width")                  # 단순 조회
    msg   = T("prog.running_n", done=3, total=12)    # str.format 인자 전달

새 문자열을 추가할 때는 **이 파일만** 고치면 된다 — `STRINGS["en"]`과
`STRINGS["ko"]` 양쪽에 같은 키를 넣는다. 한쪽만 넣으면
`tests/test_i18n.py::test_key_sets_identical`이 잡는다.

번역 원칙 (지시)
--------------
· **기술 용어는 번역하지 않는다** — busbar, pitch, finger, recovery factor,
  edge margin, FEM, efficiency 등은 한국어 모드에서도 영문 그대로 둔다. 이 앱이
  원래 쓰던 영문 병기 관례를 유지하는 것이며, 그래서 입력 라벨 다수는 두 언어에서
  값이 동일하다(중복이 아니라 의도된 것).
· 기호·단위·수식(ρ_L, mΩ·cm², %p, µm)은 언어와 무관하게 동일.
· 물리적 경고문(n_probe 자동 상향, recovery 해석대, 조합수 폭발)은 **사용자가
  잘못된 결과를 그대로 쓰는 것을 막는 안전장치**다. 축약하지 말고 의미를 정확히
  옮긴다.

계산 결과는 언어에 영향받지 않는다 — 이 모듈은 표시 문자열만 다룬다.
"""
import json
import os

DEFAULT_LANGUAGE = "en"          # 외국인 사용자가 처음 열었을 때 읽을 수 있어야 한다
LANGUAGES = ("en", "ko")
LANGUAGE_LABELS = {"en": "English", "ko": "한국어"}

# 설정 파일 — 언어 선택을 실행 간 유지한다. 엔진에 기존 저장 메커니즘이 없어
# 여기서 최소한으로 만든다(홈 디렉터리 JSON). 읽기/쓰기 실패는 조용히 무시하고
# 기본값으로 동작한다(읽기 전용 FS·권한 문제로 GUI가 죽으면 안 되므로).
SETTINGS_DIR = os.path.join(os.path.expanduser("~"), ".2l-fest")
SETTINGS_PATH = os.path.join(SETTINGS_DIR, "settings.json")

_current = {"lang": None}        # 지연 초기화(첫 조회 시 설정 파일 읽음)


# ── 문자열 테이블 ────────────────────────────────────────────────────────
STRINGS = {
    "en": {
        # --- window / header -------------------------------------------------
        "window.title": "Front Electrode Optimization (fast preview)",
        "header.title": "Front Electrode Optimization",
        "ui.language": "Language",

        # --- input labels (기술 용어 — 두 언어 공통) --------------------------
        "input.preset": "Technology preset",
        "input.preview_cell": "Preview cell [mm]",
        "input.finger_width": "Finger width [µm]",
        "input.finger_pitch": "Finger pitch [mm]",
        "input.busbar_numbers": "Busbar numbers",
        "input.busbar_width": "Busbar width [mm]",
        "input.rho_l": "ρ_L bulk [µΩ·cm]",
        "input.rho_c": "ρ_c contact [mΩ·cm²]",
        "input.edge_margin": "Edge margin [mm]",
        "input.recovery": "Busbar optical recovery  f",

        # --- field notes -----------------------------------------------------
        "note.preset_0bb": "(0BB is M10_0BB_future — kept separate from mainstream, "
                           "future technology only)",
        "note.range_fields": "Range fields below: min / max / steps "
                             "(steps=1 means a single value)",
        "note.busbar_numbers_format": "Format: comma-separated integers "
                                      "(e.g. 6,8,10,12,16,20)",
        "note.rho_l_compare": "To isolate the pressing effect, enter 9,4.22 — "
                              "as-cured (90 °C/30 min, no pressure) vs pressed "
                              "(same heat + 5 MPa).",
        "note.edge_margin": "Silver-free margin at the wafer edge "
                            "(= Griddler \"Edge Gap\"). GUI default 1.0 mm.",
        "note.recovery_assumption": "※ Adjustable KIST project assumption "
                                    "(not a universal material constant)",
        "note.objective": "Objective = efficiency (plots show efficiency too).\n"
                          "Moving the recovery slider updates results instantly, "
                          "with no FEM re-run.\n"
                          "For the full M10 optimization use the CLI: "
                          "scripts/optimize_m10.py",

        # --- buttons ---------------------------------------------------------
        "btn.run": "Run optimization",
        "btn.save_csv": "Save CSV",

        # --- recovery interpretation bands (물리 해석) -------------------------
        "rec.specular": "f={f:.2f} — flat specular surface (no total internal reflection)",
        "rec.lambertian_typical": "f={f:.2f} — printed Ag, Lambertian: typical",
        "rec.lambertian_smooth": "f={f:.2f} — printed Ag, Lambertian: smooth",
        "rec.round_wire": "f={f:.2f} — round-wire regime: does NOT apply to this structure",

        # --- warnings --------------------------------------------------------
        "warn.recovery_route1": "Recovery feeds back into the FEM solution (Route 1) — "
                                "slider disabled, a re-run is required",
        "warn.n_probe_bumped": "⚠ n_probe_points raised automatically (0 → {n}, "
                               "multi-busbar collection model)\n",
        "warn.combo_explosion": "⚠ {total} combinations ({per} each). "
                                "Use the CLI for large sweeps or full M10. Starting...",
        "warn.per_combo_full": "tens of seconds to minutes per full-cell FEM",
        "warn.per_combo_small": "a few seconds per small cell",
        "warn.no_results": "No results to save — run the optimization first.",

        # --- progress --------------------------------------------------------
        "prog.start": "Starting: {total} combinations...",
        "prog.running": "Computing...",
        "prog.running_n": "Computing... {done}/{total}",
        "prog.done": "Done ({total} combinations, {cell:.0f}mm, f={f:.2f}){model}",
        "prog.model_info": " | n_probe {mode}{npv}, nodes {nmin}~{nmax}k",
        "prog.n_probe_bumped_short": "auto-raised 0→",
        "prog.n_probe_eq": "=",
        "prog.error": "Error: {msg}",
        "prog.csv_saved": "CSV saved: {path} ({n} rows)",

        # --- result text -----------------------------------------------------
        "result.best_line": "BEST (eff @ f={f:.2f}, edge {edge:.1f}mm): "
                            "wf={wf:.0f}µm pitch={pitch:.2f}mm "
                            "nbb={nbb} wbb={wbb:.2f}mm "
                            "ρL={rho_l:.2f} ρc={rho_c:.1f}\n",
        "result.best_metrics": "  efficiency={eff:.3f}%  total_loss={loss:.4f}\n\n",
        "result.top10_header": "Top-10:  rk  wf pitch nbb  wbb   ρL    ρc  edge   eff\n",
        "result.rho_compare_header": "\nρ_L comparison (best efficiency for each ρL):\n",
        "result.rho_compare_row": "  ρL={rho:.2f} µΩ·cm → {eff:.3f}%\n",
        "result.rho_compare_delta": "  gain (Δeff, {hi:.2f}→{lo:.2f}) = {delta:+.3f} %p\n",

        # --- plots -----------------------------------------------------------
        "plot.xlabel_pitch": "finger pitch [mm]",
        "plot.ylabel_eff": "efficiency [%]",
        "plot.ylabel_busbar": "busbar number",
        "plot.title_eff_vs_pitch": "efficiency vs pitch",
        "plot.title_heatmap": "efficiency heatmap [%]",
        "plot.legend_bb": "{nb} BB",
        "plot.annot_best": "{nb}BB, {pitch:.2f}mm, {eff:.3f}%",
        "plot.grid_insufficient": "Not enough grid points\n\n"
                                  "A heatmap needs at least 2 values each\n"
                                  "for pitch and busbar number.\n"
                                  "(currently {n_pitch} pitch x {n_bb} busbar)",
        # matplotlib 텍스트는 ASCII 유지(v28.31 관례) — AppleGothic에 µ(U+00B5)가
        # 없어 두부(□)로 깨지고 ρ는 폰트 폴백으로 자간이 틀어진다. um/rhoL/rhoc로 쓴다.
        "plot.subtitle_fixed": "pitch x busbar slice | fixed: wf={wf:.0f}um "
                               "wbb={wbb:.2f}mm rhoL={rho_l:.2f} rhoc={rho_c:.1f} "
                               "edge={edge:.1f}mm",

        # --- engine-side entry point ----------------------------------------
        "engine.window_opened": "Front Electrode Optimization window opened.",
        "engine.window_error": "Optimize window error: {msg}",
    },

    "ko": {
        # --- window / header -------------------------------------------------
        "window.title": "Front Electrode Optimization (빠른 미리보기)",
        "header.title": "Front Electrode Optimization",
        "ui.language": "언어",

        # --- input labels (기술 용어 — 영문 그대로 유지) ----------------------
        "input.preset": "Technology preset",
        "input.preview_cell": "Preview cell [mm]",
        "input.finger_width": "Finger width [µm]",
        "input.finger_pitch": "Finger pitch [mm]",
        "input.busbar_numbers": "Busbar numbers",
        "input.busbar_width": "Busbar width [mm]",
        "input.rho_l": "ρ_L bulk [µΩ·cm]",
        "input.rho_c": "ρ_c contact [mΩ·cm²]",
        "input.edge_margin": "Edge margin [mm]",
        "input.recovery": "Busbar optical recovery  f",

        # --- field notes -----------------------------------------------------
        "note.preset_0bb": "(0BB는 M10_0BB_future — mainstream과 분리, 미래기술 전용)",
        "note.range_fields": "아래 range 필드: min / max / steps (steps=1이면 단일값)",
        "note.busbar_numbers_format": "형식: 쉼표 구분 정수 (예: 6,8,10,12,16,20)",
        "note.rho_l_compare": "가압 효과만 보려면 9,4.22 입력 — "
                              "as-cured(90 °C/30 min, 무가압) vs 가압(동일 열처리 + 5 MPa).",
        "note.edge_margin": "웨이퍼 엣지 실버-프리 마진 "
                            "(= Griddler \"Edge Gap\"). GUI 기본 1.0 mm.",
        "note.recovery_assumption": "※ Adjustable KIST project assumption (보편 물성값 아님)",
        "note.objective": "목적함수 = efficiency (그래프도 efficiency).\n"
                          "슬라이더로 recovery를 바꾸면 FEM 재계산 없이 즉시 갱신.\n"
                          "정밀 M10 최적화는 CLI: scripts/optimize_m10.py",

        # --- buttons ---------------------------------------------------------
        "btn.run": "Run optimization",
        "btn.save_csv": "Save CSV",

        # --- recovery interpretation bands (물리 해석) -------------------------
        "rec.specular": "f={f:.2f} — 평면 경면 (전반사 없음)",
        "rec.lambertian_typical": "f={f:.2f} — 인쇄 Ag 램버시안, 전형",
        "rec.lambertian_smooth": "f={f:.2f} — 인쇄 Ag 램버시안, 평활",
        "rec.round_wire": "f={f:.2f} — 원형 와이어 영역: 본 구조에 해당하지 않음",

        # --- warnings --------------------------------------------------------
        "warn.recovery_route1": "recovery가 FEM에 반영되는 모델(Route 1) — "
                                "슬라이더 비활성, 재계산 필요",
        "warn.n_probe_bumped": "⚠ n_probe_points 자동 상향 (0 → {n}, 다중 busbar 수집 모델)\n",
        "warn.combo_explosion": "⚠ {total}조합 (조합당 {per}). "
                                "큰 스윕/풀 M10은 CLI 권장. 시작...",
        "warn.per_combo_full": "풀셀 FEM 수십초~수분",
        "warn.per_combo_small": "소셀 수초",
        "warn.no_results": "저장할 결과 없음 — 먼저 Run 하세요.",

        # --- progress --------------------------------------------------------
        "prog.start": "총 {total}조합 계산 시작...",
        "prog.running": "계산 중...",
        "prog.running_n": "계산 중... {done}/{total}",
        "prog.done": "완료 ({total}조합, {cell:.0f}mm, f={f:.2f}){model}",
        "prog.model_info": " | n_probe {mode}{npv}, nodes {nmin}~{nmax}k",
        "prog.n_probe_bumped_short": "자동상향0→",
        "prog.n_probe_eq": "=",
        "prog.error": "오류: {msg}",
        "prog.csv_saved": "CSV 저장: {path} ({n}행)",

        # --- result text -----------------------------------------------------
        "result.best_line": "BEST (eff @ f={f:.2f}, edge {edge:.1f}mm): "
                            "wf={wf:.0f}µm pitch={pitch:.2f}mm "
                            "nbb={nbb} wbb={wbb:.2f}mm "
                            "ρL={rho_l:.2f} ρc={rho_c:.1f}\n",
        "result.best_metrics": "  efficiency={eff:.3f}%  total_loss={loss:.4f}\n\n",
        "result.top10_header": "Top-10:  rk  wf pitch nbb  wbb   ρL    ρc  edge   eff\n",
        "result.rho_compare_header": "\nρ_L 비교 (각 ρL의 최고 efficiency):\n",
        "result.rho_compare_row": "  ρL={rho:.2f} µΩ·cm → {eff:.3f}%\n",
        "result.rho_compare_delta": "  개선(Δeff, {hi:.2f}→{lo:.2f}) = {delta:+.3f} %p\n",

        # --- plots -----------------------------------------------------------
        # 축 라벨·제목·범례는 기술 용어라 두 언어 공통(영문 유지). 산문형 안내만
        # 번역한다. 엔진이 matplotlib 한글 폰트를 설정하므로(app 기동 시
        # rcParams['font.family'] = AppleGothic 등) 한글 텍스트도 정상 렌더된다.
        "plot.xlabel_pitch": "finger pitch [mm]",
        "plot.ylabel_eff": "efficiency [%]",
        "plot.ylabel_busbar": "busbar number",
        "plot.title_eff_vs_pitch": "efficiency vs pitch",
        "plot.title_heatmap": "efficiency heatmap [%]",
        "plot.legend_bb": "{nb} BB",
        "plot.annot_best": "{nb}BB, {pitch:.2f}mm, {eff:.3f}%",
        "plot.grid_insufficient": "격자 부족\n\n"
                                  "heatmap을 그리려면 pitch / busbar\n"
                                  "각각 2개 이상 필요합니다.\n"
                                  "(현재 pitch {n_pitch}개 x busbar {n_bb}개)",
        # 기호는 ASCII 유지(EN과 동일 이유) — 설명어만 한국어.
        "plot.subtitle_fixed": "pitch x busbar 단면 | 고정: wf={wf:.0f}um "
                               "wbb={wbb:.2f}mm rhoL={rho_l:.2f} rhoc={rho_c:.1f} "
                               "edge={edge:.1f}mm",

        # --- engine-side entry point ----------------------------------------
        "engine.window_opened": "Front Electrode Optimization 창을 열었습니다.",
        "engine.window_error": "Optimize 창 오류: {msg}",
    },
}


# ── 설정 저장/복원 ───────────────────────────────────────────────────────
def load_settings():
    """설정 파일을 읽어 dict 반환. 없거나 깨졌으면 빈 dict(예외 없음)."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data):
    """설정 dict를 저장. 실패해도 예외를 올리지 않는다(GUI가 죽으면 안 됨)."""
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        tmp = SETTINGS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.flush()
        os.replace(tmp, SETTINGS_PATH)     # 원자적 교체(중간 크래시에도 파일 보존)
        return True
    except OSError:
        return False


# ── 언어 상태 ────────────────────────────────────────────────────────────
def get_language():
    """현재 언어 코드. 첫 호출 때 설정 파일 → 기본값(en) 순으로 결정한다."""
    if _current["lang"] is None:
        saved = load_settings().get("language")
        _current["lang"] = saved if saved in LANGUAGES else DEFAULT_LANGUAGE
    return _current["lang"]


def set_language(lang, persist=True):
    """언어를 바꾼다. 알 수 없는 코드는 무시하고 현재 값을 유지한다."""
    if lang not in LANGUAGES:
        return get_language()
    _current["lang"] = lang
    if persist:
        data = load_settings()
        data["language"] = lang
        save_settings(data)
    return lang


def reset_language_cache():
    """테스트용 — 지연 초기화 상태를 되돌린다."""
    _current["lang"] = None


def label_for(lang):
    """언어 코드 → 사람이 읽는 이름 ('en' → 'English')."""
    return LANGUAGE_LABELS.get(lang, lang)


# ── 조회 ─────────────────────────────────────────────────────────────────
def T(key, **kwargs):
    """key에 해당하는 현재 언어 문자열. kwargs가 있으면 str.format 적용.

    키가 없으면 **예외를 내지 않고** 키 자체를 대괄호로 감싸 돌려준다 — GUI 한복판에서
    KeyError로 창이 죽는 것보다 `[some.missing.key]`가 눈에 띄는 편이 낫고, 키 누락은
    tests/test_i18n.py가 별도로 잡는다.
    """
    table = STRINGS.get(get_language()) or STRINGS[DEFAULT_LANGUAGE]
    s = table.get(key)
    if s is None:
        s = STRINGS[DEFAULT_LANGUAGE].get(key)
    if s is None:
        return f"[{key}]"
    if kwargs:
        try:
            return s.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            # 포맷 자리와 인자가 어긋나도 원문을 보여주는 편이 낫다.
            return s
    return s


def missing_keys():
    """언어별 누락 키를 {lang: sorted([key, ...])}로 반환. 전부 맞으면 빈 dict.

    전체 키 집합(모든 언어의 합집합) 대비 각 언어에 없는 키를 찾는다.
    """
    all_keys = set()
    for table in STRINGS.values():
        all_keys |= set(table)
    out = {}
    for lang, table in STRINGS.items():
        gap = sorted(all_keys - set(table))
        if gap:
            out[lang] = gap
    return out
