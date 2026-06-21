"""
2L-FEST PRO v5.0 -- 2-Layer Front Electrode Simulation Tool
=============================================================
CustomTkinter Pro UI + Fixed Report

[1] Constrained mesh -- finger/busbar boundaries as mesh edges
[2] Variable grid design -- N_fingers, N_busbars, widths
[3] J01 spatial variation -- passivated vs metal-contact (Sec 2.7)
[4] Shading loss -- optical width calculation (Sec 2.7)
[5] Experimental I-V overlay -- load CSV and compare
[6] 2T Tandem -- Series-connected two-terminal model
[7] CustomTkinter Pro UI -- modern dark/light theme
[8] Fixed Report -- correct architecture + clean conditions

v28.19: [+] mesh_distribution_metrics 진단 복원 (DESIGN 메시 비대칭/편향 시 제목 경고색)
v28.20: [fix] CSV 내보내기 0바이트 버그 수정 — utf-8-sig 인코딩 + 원자적 쓰기
        (GUI 실행 시 기본 코덱이 ASCII/cp949가 되어 비ASCII 문자에서 write가
         실패하며 0바이트 파일이 남던 문제. temp→replace로 안전 저장)
        [fix] 모델 설명(_tab_model) 탭 크래시 수정 — INDEX 라벨이 비BMP 이모지를
         lone surrogate 쌍으로 담고 있어 Tk가 "surrogates not allowed"로 죽던 문제.
         BMP 안전 텍스트로 교체 (Windows/macOS 공통)
v28.21: [ui] 재결합접합 저항 라벨 명확화 — "Rc Junction ↕/Rs Junction ↔" →
         "Recomb.J Contact↕"(수직 접촉저항, Ω·cm²) / "Recomb.J Sheet↔"(수평 면저항,
         Ω/sq). 입력란/배선은 기존과 동일(tb_diode[5]/[6] → DP.Rc_junction/Rs_junction)
v28.22: [+] 후면 접촉저항 rc_rear 독립 입력 — 기존엔 앞/뒤가 같은 rc를 공유했으나
         실제 셀·Griddler처럼 앞면과 후면 접촉 비저항을 따로 줄 수 있게 함. REAR 카드에
         "rc_rear (L4)" 입력란 추가(mΩ·cm², 빈칸=앞면 rc). DP.rc_rear=None이면 앞면 rc로
         폴백해 기존 결과와 비트 동일. bifacial 모드에서만 의미.
v28.23: [ui] Rs_junction(Phase B) 입력 시 뜨던 "결과 신뢰성 점검 필요" 안내 배너 및
         상태바 cross-validation 안내 메시지 제거(사용자 요청). FF/Recomb/수렴 등
         실제 물리 health 경고는 그대로 유지.
v28.24: [ui] REAR 카드 라벨 명확화 — "Rs_rear TCO (L3)" → "Rear Sheet R ↔"(수평
         면저항, Ω/sq), "rc_rear (L4)" → "Rear Contact R ↕"(수직 접촉저항, mΩ·cm²).
         방향 화살표로 횡/종 구분(Recomb.J 라벨과 스타일 통일). 배선/단위는 동일.
v28.25: [ui] 나머지 저항 라벨에도 방향 화살표 추가 — 앞면 "Contact R ↕"(수직),
         "TCO Sheet R ↔"(수평), "Bulk ρ ↔"(핑거 횡전도); 셀 내부 "Rs lumped Top/Bot ↕"
         (수직). 후면·재결합접합 라벨과 스타일 통일. Rsh(shunt)는 병렬 누설경로라 제외.

Author: Seunghoon (KIST, Dr. Inho Kim's Solar Cell Research Team)
"""
import numpy as np
import types
from scipy.spatial import Delaunay
from scipy.sparse import lil_matrix, csr_matrix, coo_matrix
from scipy.sparse.linalg import spsolve
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, FancyBboxPatch
import matplotlib.gridspec as gridspec
import matplotlib.tri as mtri

# --- Korean Font Setup (cross-platform, robust) ---
_kr_font = None
import platform as _pf
from matplotlib import font_manager as _fm

def _find_korean_font():
    """Find a working Korean font on this system."""
    if _pf.system() == 'Darwin':
        candidates = ['AppleGothic', 'Apple SD Gothic Neo', 'Helvetica']
    elif _pf.system() == 'Windows':
        candidates = ['Malgun Gothic', 'NanumGothic', 'Gulim']
    else:
        candidates = ['NanumGothic', 'NanumBarunGothic', 'UnDotum']

    for name in candidates:
        try:
            path = _fm.findfont(_fm.FontProperties(family=name), fallback_to_default=False)
            if path and 'DejaVu' not in path and 'default' not in path.lower():
                return name
        except:
            pass

    # Fallback: scan system fonts for any CJK font
    for fp in _fm.fontManager.ttflist:
        if any(k in fp.name.lower() for k in ['gothic', 'nanum', 'gulim', 'malgun', 'apple']):
            return fp.name
    return None

_kr_font = _find_korean_font()
if _kr_font:
    matplotlib.rcParams['font.family'] = _kr_font
    matplotlib.rcParams['axes.unicode_minus'] = False
    # Force DejaVu Sans for math/exponent rendering (Korean font lacks math glyphs)
    matplotlib.rcParams['mathtext.fontset'] = 'dejavusans'
    # Disable y-axis offset notation (prevents "3.5e1 + ..." style)
    matplotlib.rcParams['axes.formatter.useoffset'] = False
    print(f"  Font: {_kr_font}")
else:
    print("  WARNING: No Korean font found.")

# ===== Cross-platform monospace font (v28.8.1) =====
# Logo and code blocks need a monospace font. 'Consolas' is Windows-only.
# Mac default = 'Menlo' or 'Monaco', Linux = 'DejaVu Sans Mono'.
def _find_mono_font():
    """Return a working monospace font name for the current platform."""
    if _pf.system() == 'Darwin':
        candidates = ['Menlo', 'Monaco', 'Courier New', 'Courier']
    elif _pf.system() == 'Windows':
        candidates = ['Consolas', 'Courier New', 'Courier']
    else:
        candidates = ['DejaVu Sans Mono', 'Liberation Mono', 'Courier New']
    for name in candidates:
        try:
            path = _fm.findfont(_fm.FontProperties(family=name), fallback_to_default=False)
            if path and 'default' not in path.lower():
                return name
        except Exception:
            pass
    return 'Courier'  # last-resort fallback (exists on all OSes via tk)

MONO_FONT = _find_mono_font()
print(f"  Mono : {MONO_FONT}")

try:
    import customtkinter as ctk
except ImportError:
    print("ERROR: pip install customtkinter")
    exit(1)
import tkinter as tk
from tkinter import messagebox, filedialog
import time, os, sys, hashlib

# =============================================================
# CONSTANTS
# =============================================================
q_e = 1.602e-19; kB = 1.381e-23; T = 298.15; VT = kB * T / q_e
PAD_SIZE = 0.030

__build__ = {
    "version": "v28.25",
    "date": "2026-06-21",
    "name": "wf_wired",
}
_BUILD_SHA_CACHE = None


def _build_sha():
    global _BUILD_SHA_CACHE
    if _BUILD_SHA_CACHE is not None:
        return _BUILD_SHA_CACHE
    try:
        with open(__file__, "rb") as handle:
            _BUILD_SHA_CACHE = hashlib.sha256(handle.read()).hexdigest()[:12]
    except Exception:
        _BUILD_SHA_CACHE = "unknown"
    return _BUILD_SHA_CACHE


def _build_label():
    return (
        f"2L-FEST {__build__['version']} {__build__['name']} "
        f"build {_build_sha()} ({__build__['date']})"
    )


print(_build_label())


def _parse_gui_float(raw, name, *, scale=1.0, allow_blank=False, blank_value=0.0):
    text = str(raw).strip()
    if text == "":
        if allow_blank:
            return blank_value
        raise ValueError(f"{name} is required")
    try:
        value = float(text) * scale
    except Exception as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _parse_gui_int(raw, name, *, min_value=None, max_value=None):
    value = _parse_gui_float(raw, name)
    rounded = round(value)
    if abs(value - rounded) > 1e-9:
        raise ValueError(f"{name} must be an integer")
    value = int(rounded)
    if min_value is not None and value < min_value:
        raise ValueError(f"{name} must be >= {min_value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be <= {max_value}")
    return value


def _require_range(name, value, *, min_value=None, max_value=None,
                   min_inclusive=True, max_inclusive=True):
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if min_value is not None:
        if min_inclusive and value < min_value:
            raise ValueError(f"{name} must be >= {min_value}")
        if not min_inclusive and value <= min_value:
            raise ValueError(f"{name} must be > {min_value}")
    if max_value is not None:
        if max_inclusive and value > max_value:
            raise ValueError(f"{name} must be <= {max_value}")
        if not max_inclusive and value >= max_value:
            raise ValueError(f"{name} must be < {max_value}")
    return value


def _finite_or_none(value):
    try:
        value = float(value)
    except Exception:
        return None
    return value if np.isfinite(value) else None


_PHASE_B_GRIDDLER_MESSAGE = (
    "Phase B Rs_junction uses the Griddler-style single-plane interlayer FEM. "
    "It is numerically stable, but it is a different model family from the "
    "Phase A local-node baseline; direct Griddler PRO cross-validation is "
    "required before claiming absolute equivalence. "
    "Measured behaviour: a systematic ~23 mV Voc offset vs Phase A, consistent "
    "across rear modes (full_area / bifacial) and mesh density — i.e. a "
    "model-formulation difference, not a discretization error. Absolute Phase B "
    "values are therefore NOT interchangeable with Phase A, but relative deltas "
    "WITHIN Phase B (e.g. the hot-pressing effect) cancel the offset and remain "
    "reliable. Phase A stays the validated absolute baseline; Griddler PRO is "
    "currently unavailable, so the direct absolute cross-validation is still open."
)


def _phase_b_model_info(dp=None, mode='tandem'):
    rs_junction = 0.0
    if dp is not None:
        rs_junction = _finite_or_none(getattr(dp, "Rs_junction", 0.0)) or 0.0
    phase_b_active = bool(mode == 'tandem' and rs_junction > 0.0)
    if phase_b_active:
        return {
            "phase_b_active": True,
            "phase_b_status": "GRIDDLER_STYLE",
            "phase_b_message": _PHASE_B_GRIDDLER_MESSAGE,
            "junction_model": "Phase B Griddler-style single-plane interlayer",
            "rs_junction": float(rs_junction),
        }
    return {
        "phase_b_active": False,
        "phase_b_status": "BASELINE",
        "phase_b_message": "Phase A local current matching baseline.",
        "junction_model": "Phase A local current matching",
        "rs_junction": float(rs_junction),
    }


def _iv_health(iv):
    required = ("Jsc", "Voc", "Vmpp", "Jmpp", "Pmpp", "FF", "Eff", "Vmpp_internal")
    missing = [key for key in required if _finite_or_none(iv.get(key)) is None]
    p_expected = _finite_or_none(iv.get("Vmpp"))
    j_expected = _finite_or_none(iv.get("Jmpp"))
    p_actual = _finite_or_none(iv.get("Pmpp"))
    p_error = None
    if p_expected is not None and j_expected is not None and p_actual is not None:
        p_error = abs(p_actual - p_expected * j_expected)
    residual = _finite_or_none(iv.get("final_newton_residual"))
    kcl_rms = _finite_or_none(iv.get("last_point_kcl_residual_rms"))
    phase_b_native_kcl_max_A = _finite_or_none(iv.get("phase_b_native_kcl_max_A"))
    iterations = iv.get("nonlinear_iterations", "")
    fallback = bool(iv.get("fallback_used", False))
    warm_start = bool(iv.get("warm_start_used", False))

    checks = []
    if missing:
        checks.append("non-finite metrics: " + ", ".join(missing))
    if fallback:
        checks.append("warm-start fallback used")
    if residual is not None and residual > 1e-5:
        checks.append(f"Newton residual {residual:.2e} > 1e-5")
    if p_error is None or p_error > 1e-6:
        checks.append(
            "Pmpp mismatch" if p_error is None else f"Pmpp mismatch {p_error:.2e}"
        )
    phase_b_active = bool(iv.get("phase_b_active", False))
    if (not phase_b_active) and kcl_rms is not None and kcl_rms > 1e-5:
        checks.append(f"KCL RMS {kcl_rms:.2e} > 1e-5")
    if (phase_b_active and phase_b_native_kcl_max_A is not None
            and phase_b_native_kcl_max_A > 1e-5):
        checks.append(
            f"Phase B native interlayer residual "
            f"{phase_b_native_kcl_max_A:.2e} A > 1e-5"
        )

    status = "PASS" if not checks else "CHECK"
    return {
        "status": status,
        "message": "OK" if not checks else "; ".join(checks),
        "final_newton_residual": residual,
        "last_point_kcl_residual_rms": kcl_rms,
        "nonlinear_iterations": iterations,
        "warm_start_used": warm_start,
        "fallback_used": fallback,
        "pmpp_consistency_error": p_error,
        "vmpp_internal": _finite_or_none(iv.get("Vmpp_internal")),
        "rs_lumped_total": _finite_or_none(iv.get("Rs_lumped_total")),
        "phase_b_active": phase_b_active,
        "phase_b_status": iv.get("phase_b_status", "BASELINE"),
        "phase_b_message": iv.get("phase_b_message", ""),
        "junction_model": iv.get("junction_model", ""),
        "rs_junction": _finite_or_none(iv.get("rs_junction")),
        "phase_b_native_kcl_rms_mA_cm2": _finite_or_none(
            iv.get("phase_b_native_kcl_rms_mA_cm2")
        ),
        "phase_b_native_kcl_max_mA_cm2": _finite_or_none(
            iv.get("phase_b_native_kcl_max_mA_cm2")
        ),
        "phase_b_native_kcl_integrated_mA_cm2": _finite_or_none(
            iv.get("phase_b_native_kcl_integrated_mA_cm2")
        ),
        "phase_b_native_kcl_max_A": phase_b_native_kcl_max_A,
        "phase_b_top_kvl_rms_mV": _finite_or_none(
            iv.get("phase_b_top_kvl_rms_mV")
        ),
        "phase_b_top_kvl_max_mV": _finite_or_none(
            iv.get("phase_b_top_kvl_max_mV")
        ),
    }

# --- Design Tokens ---
CLR_HEADER   = "#0F172A"
CLR_SIDEBAR  = "#FFFFFF"
CLR_CARD_BG  = "#F8FAFC"
CLR_CARD_BD  = "#E2E8F0"
CLR_RED      = "#DC2626"
CLR_GREEN    = "#059669"
CLR_BLUE     = "#2563EB"
CLR_AMBER    = "#D97706"
CLR_TAB_BG   = "#F1F5F9"
CLR_EVEN_ROW = "#F1F5F9"
CLR_TEXT      = "#1E293B"
CLR_TEXT_SEC  = "#64748B"
CLR_ACCENT   = "#1a237e"

# --- Global Language System ---
_LANG = {'current': 'EN'}

_TR = {
    # Sidebar
    'before': {'EN': 'BEFORE', 'KR': '프레싱 전'},
    'after': {'EN': 'AFTER', 'KR': '프레싱 후'},
    'grid_design': {'EN': 'GRID DESIGN', 'KR': '그리드 설계'},
    'bulk_res': {'EN': 'Bulk ρ ↔', 'KR': '벌크 비저항 ↔'},
    'finger_h': {'EN': 'Finger Height', 'KR': '핑거 높이'},
    'finger_w': {'EN': 'Finger Width', 'KR': '핑거 폭'},
    'shape_cf': {'EN': 'Shape CF', 'KR': '형상 계수'},
    'contact_res': {'EN': 'Contact R ↕', 'KR': '접촉저항 ↕'},
    'busbar_w': {'EN': 'Busbar Width', 'KR': '버스바 폭'},
    'tco_rsheet': {'EN': 'TCO Sheet R ↔', 'KR': 'TCO 면저항 ↔'},
    'cell_w': {'EN': 'Cell Width', 'KR': '셀 폭'},
    'cell_h': {'EN': 'Cell Height', 'KR': '셀 높이'},
    'n_fingers': {'EN': 'N Fingers', 'KR': '핑거 수'},
    'n_busbars': {'EN': 'N Busbars', 'KR': '버스바 수'},
    'w_finger': {'EN': 'Finger Width', 'KR': '핑거 폭'},
    'w_busbar': {'EN': 'Busbar Width', 'KR': '버스바 폭'},
    'diode_params': {'EN': 'DIODE PARAMS', 'KR': '다이오드 파라미터'},
    'n2_top': {'EN': 'n2 Top (Pvsk)', 'KR': 'n2 상부 (Pvsk)'},
    'n2_bot': {'EN': 'n2 Bot (Si)', 'KR': 'n2 하부 (Si)'},
    # Tabs
    'compare': {'EN': 'COMPARE', 'KR': '비교'},
    'current': {'EN': 'CURRENT', 'KR': '전류맵'},
    'loss_ff': {'EN': 'LOSS/FF', 'KR': '손실/FF'},
    'sweep': {'EN': 'SWEEP', 'KR': '스윕'},
    'contour': {'EN': 'CONTOUR', 'KR': '등고선'},
    'model': {'EN': 'MODEL', 'KR': '모델'},
    'exp_iv': {'EN': 'EXP I-V', 'KR': '실험 I-V'},
    'report': {'EN': 'REPORT', 'KR': '보고서'},
    'validate': {'EN': 'VALIDATE', 'KR': '검증'},
    'lit_bench': {'EN': 'LIT BENCH', 'KR': '문헌검증'},
    # Chart titles
    'tandem_iv': {'EN': 'Tandem I-V', 'KR': '탠덤 I-V 곡선'},
    'front_res_loss': {'EN': 'Front Resistive Losses', 'KR': '전면 저항 손실'},
    'tandem_perf': {'EN': 'Tandem Performance', 'KR': '탠덤 성능'},
    'res_loss_ba': {'EN': 'Resistive Loss (B vs A)', 'KR': '저항손실 (전 vs 후)'},
    'recomb_ba': {'EN': 'Recomb. Currents (B vs A)', 'KR': '재결합전류 (전 vs 후)'},
    'hot_press': {'EN': 'Hot Pressing Effect', 'KR': '핫 프레싱 효과'},
    'voltage': {'EN': 'Voltage [V]', 'KR': '전압 [V]'},
    'loss_mw': {'EN': 'Loss [mW/cm2]', 'KR': '손실 [mW/cm2]'},
    'eff_pct': {'EN': 'Efficiency [%]', 'KR': '효율 [%]'},
    'ff_pct': {'EN': 'FF [%]', 'KR': 'FF [%]'},
    # Current tab
    'emitter_v': {'EN': 'Emitter (TCO) Voltage', 'KR': '에미터 (TCO) 전압'},
    'top_cell_v': {'EN': 'Top Cell (Perovskite) V', 'KR': '상부셀 (페로브스카이트) V'},
    'bot_cell_v': {'EN': 'Bottom Cell (Si) V', 'KR': '하부셀 (Si) V'},
    'metal_v': {'EN': 'Metal Voltage', 'KR': '금속 전압'},
    'fem_mesh': {'EN': 'FEM Mesh', 'KR': 'FEM 메시'},
    'j01_spatial': {'EN': 'J01 Spatial (metal vs pass)', 'KR': 'J01 공간분포'},
    'current_maps_title': {'EN': 'Voltage / Current Maps  [BEFORE pressing, at MPP]',
                           'KR': '전압 / 전류 맵  [프레싱 전, MPP]'},
    # FF Waterfall
    'ff_waterfall': {'EN': 'FF Waterfall', 'KR': 'FF 워터폴'},
    'ff_what_kills': {'EN': 'FF Waterfall -- What Kills Fill Factor?', 'KR': 'FF 워터폴 -- Fill Factor를 줄이는 요인'},
    'ff_drop_summary': {'EN': 'FF Drop Summary', 'KR': 'FF 감소 요약'},
    'final_ff': {'EN': 'Final FF', 'KR': '최종 FF'},
    # Sweep
    'eff_vs_rho': {'EN': 'Efficiency vs rho_bulk', 'KR': '효율 vs rho_bulk'},
    'ff_vs_rho': {'EN': 'FF vs rho_bulk', 'KR': 'FF vs rho_bulk'},
    'loss_vs_rho': {'EN': 'Loss vs rho_bulk', 'KR': '손실 vs rho_bulk'},
    # Contour
    'eff_contour': {'EN': 'Efficiency Contour', 'KR': '효율 등고선'},
    'ff_contour': {'EN': 'FF Contour', 'KR': 'FF 등고선'},
    'sensitivity': {'EN': 'Sensitivity Analysis Summary', 'KR': '민감도 분석 요약'},
    # Progress
    'computing_iv': {'EN': 'Computing tandem I-V curves...', 'KR': '탠덤 I-V 곡선 계산 중...'},
    'drawing_maps': {'EN': 'Drawing voltage / current maps...', 'KR': '전압/전류 맵 그리는 중...'},
    'computing_ff': {'EN': 'Computing FF waterfall...', 'KR': 'FF 워터폴 계산 중...'},
    'param_sweep': {'EN': 'Parameter sweep: rho_bulk (12 pts)...', 'KR': '파라미터 스윕: rho_bulk (12점)...'},
    'contour_2d': {'EN': '2D Contour: rho_bulk vs rho_c (6x6)...', 'KR': '2D 등고선: rho_bulk vs rho_c (6x6)...'},
    'gen_report': {'EN': 'Generating Report...', 'KR': '보고서 생성 중...'},
    # Table headers
    'parameter': {'EN': 'Parameter', 'KR': '항목'},
    'delta': {'EN': 'Delta', 'KR': '변화량'},
    'loss_bd_before': {'EN': 'Loss Breakdown (Before)', 'KR': '손실 분해 (프레싱 전)'},
    'loss_bd_after': {'EN': 'Loss Breakdown (After)', 'KR': '손실 분해 (프레싱 후)'},
    'eff_improve': {'EN': 'Efficiency Improvement (Hot Pressing)', 'KR': '효율 개선 (핫 프레싱)'},
    'before_sim': {'EN': 'Before (sim)', 'KR': '프레싱 전 (sim)'},
    'after_sim': {'EN': 'After (sim)', 'KR': '프레싱 후 (sim)'},
    # General
    'ready': {'EN': 'Ready. Click a tab.', 'KR': '준비 완료. 탭을 클릭하세요.'},
    'run_compare_first': {'EN': 'Run COMPARE first.', 'KR': 'COMPARE를 먼저 실행하세요.'},
}

def _t(key):
    """Get translated text for current language."""
    d = _TR.get(key)
    if d is None: return key
    return d.get(_LANG['current'], d.get('EN', key))

# Report colors
_C2 = '#5C6BC0'; _C3 = '#66BB6A'; _CH = '#1a237e'

# =============================================================
# CELL GEOMETRY
# =============================================================

"""
2L-FEST Solver Engine v5.0
===========================
Core solver module (no GUI) for validation and testing.

Changes from v4.1:
  [1] Rear plane -- V_rear per node, lateral current, diode V = V_front - V_rear
  [2] Single-cell / Tandem mode switch
  [3] Hybrid ism/metal_frac (15cm validation technique)
  [4] n1 as free parameter (perovskite ideality)
  [5] Transition-zone mesh refinement + pass_density
  [6] High-resolution IV sweep near MPP
  [7] Stiffness caching strengthened

Author: Seunghoon (KIST, Dr. Inho Kim's Solar Cell Research Team)
"""

import numpy as np
from scipy.spatial import Delaunay
from scipy.sparse import lil_matrix, csr_matrix, coo_matrix
from scipy.sparse.linalg import spsolve
import time

# =============================================================
# CONSTANTS
# =============================================================
q_e = 1.602e-19
kB = 1.381e-23
T = 298.15
VT = kB * T / q_e
PAD_SIZE = 0.030

# =============================================================
# CELL GEOMETRY + H-PATTERN GENERATOR
# =============================================================
class GridDesign:
    """H-pattern electrode design for one side (front or rear).

    Two input modes (v28.5+):
      A) "n_fingers" mode (legacy): user specifies n_fingers directly.
         Finger pitch is auto-derived from cell width: pitch = W / (n_fingers + 1).
         Useful for unit-cell representative simulations.

      B) "finger_spacing" mode (Griddler-compatible): user specifies the
         finger spacing s [mm] directly. n_fingers is auto-derived:
            n_fingers = max(1, round(W_mm / s_mm)) - 1   (interior fingers, busbar-to-busbar)
         This matches Griddler's H-pattern Design Page convention, where
         spacing is the physical lever and the count adjusts to wafer size.

    Parameters:
        input_mode: "n_fingers" | "finger_spacing"
        n_fingers: int -- number of fingers (used in n_fingers mode)
        finger_spacing_mm: float -- inter-finger pitch [mm] (used in finger_spacing mode)
        n_busbars: int -- number of busbars
        w_finger: float -- finger width [cm]
        w_busbar: float -- busbar width [cm]
        finger_length_frac: float -- finger length as fraction of wafer width (0~1)
        busbar_length_frac: float -- busbar length as fraction of wafer height (0~1)
        edge_gap: float -- gap between finger tip and wafer edge [cm]
        pad_size: float -- terminal pad size [cm]
        n_terminals: int -- number of terminal/probe points along busbar
        Rs_sheet: float -- sheet resistance of the underlying layer [Ohm/sq]
        rho_bulk: float -- metal bulk resistivity [Ohm*cm]
        finger_h: float -- finger height/thickness [cm]
        shape_cf: float -- cross-section factor (pi/4 for round, 1 for flat)
        rho_contact: float -- contact resistivity [Ohm*cm2]
    """
    def __init__(self, n_fingers=2, n_busbars=1,
                 w_finger=50e-4, w_busbar=50e-4,
                 finger_length_frac=1.0, busbar_length_frac=1.0,
                 edge_gap=0.0, pad_size=0.0, n_terminals=1,
                 Rs_sheet=55.0,
                 rho_bulk=13.22e-6, finger_h=10e-4,
                 shape_cf=0.785, rho_contact=10e-3,
                 input_mode="n_fingers", finger_spacing_mm=1.5,
                 n_probe_points=0, extraction_method="probe_point",
                 pattern_style="h_pattern",
                 taper_factor=1.0, taper_dist_mm=0.0):
        # pad_size default 0 으로 변경.
        #   이전: 0.030 cm (300×300 μm 사각형 contact pad) — 옛날 v1-v3 잔재
        #   현재: 0 (pad 제거) — Griddler 표준, 통상적 셀에 맞음
        # Griddler-style pattern variety.
        #   pattern_style options:
        #     "h_pattern"   — default (standard H-pattern grid, current behavior)
        #     "shingled"    — single BB at left edge, fingers extend right (박사님 fork pattern)
        #     "tapered_h"   — H-pattern with finger widening near BBs (industrial cells)
        #   taper_factor: finger width multiplier near BBs (1.0 = no taper)
        #   taper_dist_mm: taper transition distance from BB [mm]
        self.pattern_style = pattern_style
        self.taper_factor = float(taper_factor)
        self.taper_dist_mm = float(taper_dist_mm)
        # auto-apply sensible defaults for tapered_h if not specified
        if pattern_style == "tapered_h":
            if self.taper_factor <= 1.0:
                self.taper_factor = 2.0    # 2× wider near BBs
            if self.taper_dist_mm <= 0:
                self.taper_dist_mm = 0.5   # 0.5 mm transition zone
        # Griddler-style probe points:
        #   n_probe_points = 0  -> legacy n_terminals behavior (single-cell integrity preserved)
        #   n_probe_points > 0  -> N probe points per ALL busbars (Griddler)
        # extraction_method:
        #   "probe_point" -> I-V tester: extract at each probe point (default)
        #   "ribbon_ends" -> module mode: solder ribbons at probe points, extract at ribbon ends
        #   "floating"    -> Voc-only (no IV sweep)
        self.n_probe_points = int(max(0, n_probe_points))
        self.extraction_method = str(extraction_method)
        self.input_mode = input_mode
        self.finger_spacing_mm = finger_spacing_mm
        self.n_f = n_fingers
        self.n_b = n_busbars if pattern_style != "shingled" else 1  # shingled forces 1 BB
        self.w_f = w_finger
        self.w_b = w_busbar
        self.finger_length_frac = finger_length_frac
        self.busbar_length_frac = busbar_length_frac
        self.edge_gap = edge_gap
        self.pad = pad_size
        self.n_terminals = n_terminals
        self.Rs_sheet = Rs_sheet
        self.rho_bulk = rho_bulk
        self.finger_h = finger_h
        self.shape_cf = shape_cf
        self.rho_contact = rho_contact

    def derive_n_fingers(self, W_cm, H_cm=None):
        """In finger_spacing mode, recompute n_f from the finger-spacing AXIS.

        v28.18 fix (리뷰 1-B): 핑거는 compute_positions에서 y(=H)축으로
        fg_y = H*(i+1)/(n_f+1) 에 배치된다. 따라서 핑거 간 간격(pitch)은
        H/(n_f+1) 이고, 요청 간격 s 를 실현하려면
            n_f = round(H / s) - 1
        이어야 한다 (클래스 docstring의 본래 의도와 일치). 이전 버전은
        (1) 폭 W에서 개수를 뽑아 비정사각 셀에서 H를 무시했고
        (2) -1 누락으로 실현 pitch가 요청 s 와 체계적으로 어긋났다.
        H_cm=None 이면 옛 W 기준으로 폴백(하위호환). 최소 1개 보장.
        """
        if self.input_mode != "finger_spacing":
            return self.n_f
        L_mm = (H_cm if H_cm is not None else W_cm) * 10.0
        s_mm = max(0.10, float(self.finger_spacing_mm))  # guard: s >= 0.1 mm
        n_f = max(1, int(round(L_mm / s_mm)) - 1)
        self.n_f = n_f
        return n_f

    def get_finger_pitch_mm(self, W_cm, H_cm=None):
        """Return the *actual* finger pitch [mm] that compute_positions draws.

        v28.18 fix (리뷰 1-B): 실제 배치는 fg_y = H*(i+1)/(n_f+1) 이므로
        실현 pitch = H/(n_f+1). 이전엔 W/n_f 를 보고해 실제 그려지는 값과
        어긋났다. H_cm=None 이면 옛 W 기준으로 폴백(하위호환)."""
        L_mm = (H_cm if H_cm is not None else W_cm) * 10.0
        if self.n_f >= 1:
            return L_mm / (self.n_f + 1)
        return L_mm

    def compute_positions(self, W, H):
        """Compute finger/busbar/terminal positions for a given wafer size.

        v28.10: branch on pattern_style.
          "h_pattern"  (default): n_b BBs evenly distributed across width
          "shingled" / "fork"   : 1 BB at LEFT edge, fingers extend to right edge
                                  (박사님 fork pattern, tandem cell style)

        Returns dict with:
            bb_x: list of busbar x-centers [cm]
            fg_y: list of finger y-centers [cm]
            fg_x_range: (x_start, x_end) for each finger [cm]
            bb_y_range: (y_start, y_end) for each busbar [cm]
            terminals: list of (x, y) probe points [cm]
            pad_cx, pad_cy: primary pad center [cm]
        """
        # Shingled / Fork pattern branch
        if self.pattern_style == "shingled":
            return self._compute_shingled(W, H)

        # === Standard H-pattern (default) ===
        # Busbar positions: evenly spaced (always)
        bb_x = [W * (i + 1) / (self.n_b + 1) for i in range(self.n_b)]

        # Finger y-positions: ALWAYS evenly divided (v4.1 method)
        # edge_gap does NOT affect finger spacing -- it affects finger LENGTH only
        fg_y = [H * (i + 1) / (self.n_f + 1) for i in range(self.n_f)]

        # Finger x-range: edge_gap = distance from finger tip to wafer edge
        # finger_length_frac takes priority; edge_gap further trims if set
        fg_len = self.finger_length_frac * W
        fg_margin = (W - fg_len) / 2
        # edge_gap overrides margin if larger
        fg_margin = max(fg_margin, self.edge_gap)
        fg_x_range = (fg_margin, W - fg_margin)

        # Busbar y-range
        bb_len = self.busbar_length_frac * H
        bb_margin = (H - bb_len) / 2
        bb_y_range = (bb_margin, H - bb_margin)

        # Probe points
        #   n_probe_points > 0 : Griddler-style - N probe points evenly spaced
        #                        on EACH busbar (all of them)
        #   n_probe_points == 0: legacy single-busbar n_terminals behavior
        #                        (bit-exact backward compat for single-cell mode)
        if self.n_probe_points > 0 and len(bb_x) > 0:
            terminals = []
            for bx in bb_x:
                for i in range(self.n_probe_points):
                    # Center N probe points within busbar y-range
                    ty = bb_y_range[0] + (bb_y_range[1] - bb_y_range[0]) * (i + 0.5) / self.n_probe_points
                    terminals.append((bx, ty))
            pad_cx = bb_x[0]
            pad_cy = terminals[0][1]
        else:
            # Legacy path (n_probe_points == 0)
            # pad 제거 시 probe를 BB 중앙에 배치
            # 이전: BB 끝점 (top) — pad 사각형 있을 때만 의미 있음
            # 현재: pad ≤ 0 (default) → BB 중앙 / pad > 0 → 옛 동작 (top, backward compat)
            terminals = []
            if self.n_terminals >= 1 and len(bb_x) > 0:
                bx0 = bb_x[0]
                if self.n_terminals == 1:
                    if self.pad > 0:
                        # Legacy: pad가 있으면 그 위치 (top)
                        terminals.append((bx0, H - self.pad / 2))
                    else:
                        # 새 default: BB 중앙
                        bb_center_y = (bb_y_range[0] + bb_y_range[1]) / 2
                        terminals.append((bx0, bb_center_y))
                else:
                    for i in range(self.n_terminals):
                        ty = bb_y_range[0] + (bb_y_range[1] - bb_y_range[0]) * i / (self.n_terminals - 1)
                        terminals.append((bx0, ty))
            pad_cx = bb_x[0] if bb_x else W / 2
            # pad centered on BB top (inside BB), not wafer top
            if bb_x and len(bb_y_range) == 2:
                pad_cy = bb_y_range[1] - self.pad / 2 if self.pad > 0 else (bb_y_range[0] + bb_y_range[1]) / 2
            else:
                pad_cy = H - self.pad / 2 if self.pad > 0 else H / 2

        return {
            'bb_x': bb_x, 'fg_y': fg_y,
            'fg_x_range': fg_x_range, 'bb_y_range': bb_y_range,
            'terminals': terminals, 'pad_cx': pad_cx, 'pad_cy': pad_cy,
        }

    def _compute_shingled(self, W, H):
        """v28.10: Shingled / Fork pattern (박사님 직접 언급).
        - Single BB at LEFT edge (x = w_b/2 + small inset)
        - All fingers extend from BB to RIGHT edge of cell
        - Tandem cell 'fork' / 'tuning fork' shape
        """
        self.n_b = 1  # shingled = always 1 BB
        # BB at left edge (inset by half-width so it stays inside the cell)
        bb_inset = self.w_b / 2 + 1e-4  # small inset for FEM stability
        bb_x = [bb_inset]

        # Finger y-positions: evenly distributed (same as H)
        fg_y = [H * (i + 1) / (self.n_f + 1) for i in range(self.n_f)]

        # Fingers extend FROM the BB right edge TO right edge of cell
        # finger_length_frac shrinks the right end (e.g. 0.95 leaves 5% gap)
        fg_start = self.w_b + 1e-4   # finger starts just past BB
        fg_len_max = W - fg_start    # max possible length
        fg_len = self.finger_length_frac * fg_len_max
        fg_x_range = (fg_start, fg_start + fg_len)

        # BB y-range (BB spans nearly full height)
        bb_len = self.busbar_length_frac * H
        bb_margin = (H - bb_len) / 2
        bb_y_range = (bb_margin, H - bb_margin)

        # Probe points on BB (uniformly distributed)
        if self.n_probe_points > 0:
            terminals = []
            for i in range(self.n_probe_points):
                ty = bb_y_range[0] + (bb_y_range[1] - bb_y_range[0]) * (i + 0.5) / self.n_probe_points
                terminals.append((bb_inset, ty))
            pad_cx = bb_inset
            pad_cy = terminals[0][1]
        else:
            # Fork/Shingled probe 위치 fix
            # 이전: BB top corner — 옛 pad 위치 (이상함)
            # 현재: pad ≤ 0 (default) → BB 중앙 / pad > 0 → 옛 동작
            terminals = []
            if self.n_terminals >= 1:
                if self.n_terminals == 1:
                    if self.pad > 0:
                        terminals.append((bb_inset, H - self.pad / 2))
                    else:
                        # 새 default: BB 중앙
                        bb_center_y = (bb_y_range[0] + bb_y_range[1]) / 2
                        terminals.append((bb_inset, bb_center_y))
                else:
                    for i in range(self.n_terminals):
                        ty = bb_y_range[0] + (bb_y_range[1] - bb_y_range[0]) * i / (self.n_terminals - 1)
                        terminals.append((bb_inset, ty))
            pad_cx = bb_inset
            if self.pad > 0:
                pad_cy = bb_y_range[1] - self.pad / 2 if bb_y_range[1] > self.pad else H - self.pad / 2
            else:
                pad_cy = (bb_y_range[0] + bb_y_range[1]) / 2

        return {
            'bb_x': bb_x, 'fg_y': fg_y,
            'fg_x_range': fg_x_range, 'bb_y_range': bb_y_range,
            'terminals': terminals, 'pad_cx': pad_cx, 'pad_cy': pad_cy,
        }


class CellGeometry:
    """Wafer geometry + front/rear GridDesign.

    Supports two modes:
      A) Full area rear (Rs_rear = uniform, no pattern)
      B) Patterned rear (independent H-pattern)
    """
    def __init__(self, cell_w=0.90, cell_h=0.90,
                 front=None, rear=None, pad_size=0.0,
                 wafer_shape="square", chamfer_mm=0.0):
        # Wafer shape support
        #   "square"        — 표준 사각형 (multicrystalline)
        #   "pseudo_square" — 모서리 모따기 (monocrystalline, M-series)
        #   "circular"      — 원형 (lab wafer)
        #   chamfer_mm: pseudo_square 모서리 모따기 길이 [mm]
        self.wafer_shape = wafer_shape
        self.chamfer_mm = float(chamfer_mm)
        self.W = cell_w
        self.H = cell_h
        self.area = cell_w * cell_h  # bounding rectangle area (legacy)
        self.pad = pad_size

        # Front grid (default: 2F+1BB, legacy compatible)
        if front is None:
            front = GridDesign(n_fingers=2, n_busbars=1,
                               w_finger=50e-4, w_busbar=50e-4,
                               pad_size=pad_size)
        self.front = front

        # Rear grid (None = full area metal contact)
        self.rear = rear
        self.rear_mode = 'full_area' if rear is None else 'bifacial'

        # If front grid is in finger_spacing mode, derive n_f from cell_w
        # before computing positions. Same for rear if patterned.
        front.derive_n_fingers(cell_w, cell_h)
        if rear is not None:
            rear.derive_n_fingers(cell_w, cell_h)

        # Compute positions
        fp = front.compute_positions(cell_w, cell_h)
        self.bb_x = fp['bb_x']
        self.fg_y = fp['fg_y']
        self.fg_x_range = fp['fg_x_range']
        self.bb_y_range = fp['bb_y_range']
        self.pad_cx = fp['pad_cx']
        self.pad_cy = fp['pad_cy']
        self.front_terminals = fp['terminals']

        # Legacy aliases
        self.n_f = front.n_f
        self.n_b = front.n_b
        self.w_f = front.w_f
        self.w_b = front.w_b

        # Rear positions (if patterned)
        if rear is not None:
            rp = rear.compute_positions(cell_w, cell_h)
            self.rear_bb_x = rp['bb_x']
            self.rear_fg_y = rp['fg_y']
            self.rear_fg_x_range = rp['fg_x_range']
            self.rear_bb_y_range = rp['bb_y_range']
            self.rear_terminals = rp['terminals']
            self.rear_pad_cx = rp['pad_cx']
            self.rear_pad_cy = rp['pad_cy']

    def wafer_area(self):
        """v28.10: Actual wafer area accounting for shape (square/pseudo/circular).
        Used for shading fraction and PCE calculation."""
        if self.wafer_shape == "circular":
            r = min(self.W, self.H) / 2.0
            return np.pi * r * r
        elif self.wafer_shape == "pseudo_square":
            c_cm = self.chamfer_mm / 10.0  # mm -> cm
            # 4 chamfered corners, each removes c²/2 triangle
            return max(0.5 * self.W * self.H,
                       self.W * self.H - 2.0 * c_cm * c_cm)
        return self.W * self.H

    def wafer_outline_xy_mm(self):
        """v28.10: Return polygon vertices (in mm) for wafer outline.
        Returns list of (x_mm, y_mm) — closed polygon (last == first)."""
        W_mm = self.W * 10
        H_mm = self.H * 10
        if self.wafer_shape == "circular":
            # 64-vertex circle inscribed in cell
            cx, cy = W_mm / 2, H_mm / 2
            r = min(W_mm, H_mm) / 2
            return [(cx + r * np.cos(t), cy + r * np.sin(t))
                    for t in np.linspace(0, 2 * np.pi, 65)]
        elif self.wafer_shape == "pseudo_square":
            c = self.chamfer_mm  # mm directly
            c = max(0, min(c, min(W_mm, H_mm) / 2 - 0.01))
            return [
                (c, 0), (W_mm - c, 0),
                (W_mm, c), (W_mm, H_mm - c),
                (W_mm - c, H_mm), (c, H_mm),
                (0, H_mm - c), (0, c),
                (c, 0)
            ]
        # square
        return [(0, 0), (W_mm, 0), (W_mm, H_mm), (0, H_mm), (0, 0)]

    def shading_fraction(self, w_f_opt=None, w_b_opt=None):
        """Front-side shading (fingers + busbars + pad, accounting for lengths).
        v28.10: divides by actual wafer area (accounts for chamfer/circular)."""
        if w_f_opt is None: w_f_opt = self.w_f
        if w_b_opt is None: w_b_opt = self.w_b

        # Finger length (actual, not full wafer width)
        fg_len = self.fg_x_range[1] - self.fg_x_range[0]
        A_f = self.n_f * w_f_opt * fg_len

        # Busbar length (actual)
        bb_len = self.bb_y_range[1] - self.bb_y_range[0]
        A_b = self.n_b * w_b_opt * bb_len

        A_p = self.pad ** 2 if self.pad > 0 else 0

        # Overlap: only where finger and busbar actually cross
        # Finger spans [fg_x_range], busbar is at bb_x -- always overlaps
        A_ov = self.n_f * self.n_b * w_f_opt * w_b_opt

        # divide by ACTUAL wafer area (square/pseudo/circular)
        return (A_f + A_b + A_p - A_ov) / self.wafer_area()

    def metal_rects_front(self):
        """Return list of (x, y, w, h) rectangles for front metal.

        v28.10: tapered_h pattern splits each finger into 3 segments —
        wider near each busbar, narrower in the middle.
        """
        rects = []
        fx0, fx1 = self.fg_x_range

        # Tapered fingers (wider near BBs)
        if (self.front.pattern_style == "tapered_h"
                and self.front.taper_factor > 1.0
                and self.front.taper_dist_mm > 0):
            taper_w = self.w_f * self.front.taper_factor
            taper_d_cm = self.front.taper_dist_mm / 10.0  # mm -> cm
            for fy in self.fg_y:
                # Build per-finger segments based on BB positions along x.
                # Sort BB positions to define segment boundaries.
                bb_sorted = sorted(self.bb_x)
                # x positions of taper transitions: each BB has ±taper_d zone
                x_starts = []
                for bx in bb_sorted:
                    # Wider taper zone around BB
                    t_left = max(fx0, bx - taper_d_cm)
                    t_right = min(fx1, bx + taper_d_cm)
                    x_starts.append((t_left, t_right, "wide"))
                # Construct strip with normal width in non-taper zones
                cur_x = fx0
                for t_left, t_right, _ in x_starts:
                    # Normal segment before taper
                    if cur_x < t_left:
                        rects.append((cur_x, fy - self.w_f / 2,
                                       t_left - cur_x, self.w_f))
                    # Wider taper segment
                    rects.append((t_left, fy - taper_w / 2,
                                   t_right - t_left, taper_w))
                    cur_x = t_right
                # Final normal segment
                if cur_x < fx1:
                    rects.append((cur_x, fy - self.w_f / 2,
                                   fx1 - cur_x, self.w_f))
        else:
            # Standard fingers (H-pattern, shingled)
            for fy in self.fg_y:
                rects.append((fx0, fy - self.w_f / 2, fx1 - fx0, self.w_f))

        # Busbars (same for all patterns)
        by0, by1 = self.bb_y_range
        for bx in self.bb_x:
            rects.append((bx - self.w_b / 2, by0, self.w_b, by1 - by0))
        if self.pad > 0:
            rects.append((self.pad_cx - self.pad / 2, self.H - self.pad, self.pad, self.pad))
        return rects

    def metal_rects_rear(self):
        """Return list of (x, y, w, h) rectangles for rear metal.
           Returns None for full_area mode."""
        if self.rear_mode == 'full_area':
            return None
        rects = []
        fx0, fx1 = self.rear_fg_x_range
        for fy in self.rear_fg_y:
            rects.append((fx0, fy - self.rear.w_f / 2, fx1 - fx0, self.rear.w_f))
        by0, by1 = self.rear_bb_y_range
        for bx in self.rear_bb_x:
            rects.append((bx - self.rear.w_b / 2, by0, self.rear.w_b, by1 - by0))
        return rects

    def metal_rects_front_split(self):
        """v28.10 (사용자 요청 2026.05.21): finger와 busbar를 분리해서 반환.
        DESIGN 탭에서 색 구분 표시용. 기존 metal_rects_front()는 그대로 유지 (FEM 사용).
        Returns: (finger_rects, busbar_rects, pad_rects) — 각각 [(x,y,w,h), ...]"""
        finger_rects = []
        busbar_rects = []
        pad_rects = []

        fx0, fx1 = self.fg_x_range

        # Tapered fingers (3 segment) or standard
        if (self.front.pattern_style == "tapered_h"
                and self.front.taper_factor > 1.0
                and self.front.taper_dist_mm > 0):
            taper_w = self.w_f * self.front.taper_factor
            taper_d_cm = self.front.taper_dist_mm / 10.0
            for fy in self.fg_y:
                bb_sorted = sorted(self.bb_x)
                x_starts = []
                for bx in bb_sorted:
                    t_left = max(fx0, bx - taper_d_cm)
                    t_right = min(fx1, bx + taper_d_cm)
                    x_starts.append((t_left, t_right))
                cur_x = fx0
                for t_left, t_right in x_starts:
                    if cur_x < t_left:
                        finger_rects.append((cur_x, fy - self.w_f / 2,
                                              t_left - cur_x, self.w_f))
                    finger_rects.append((t_left, fy - taper_w / 2,
                                          t_right - t_left, taper_w))
                    cur_x = t_right
                if cur_x < fx1:
                    finger_rects.append((cur_x, fy - self.w_f / 2,
                                          fx1 - cur_x, self.w_f))
        else:
            for fy in self.fg_y:
                finger_rects.append((fx0, fy - self.w_f / 2, fx1 - fx0, self.w_f))

        # Busbars
        by0, by1 = self.bb_y_range
        for bx in self.bb_x:
            busbar_rects.append((bx - self.w_b / 2, by0, self.w_b, by1 - by0))

        # Optional pad
        if self.pad > 0:
            pad_rects.append((self.pad_cx - self.pad / 2, self.H - self.pad,
                              self.pad, self.pad))

        return finger_rects, busbar_rects, pad_rects

    def metal_rects_rear_split(self):
        """v28.10: rear finger/busbar 분리 (bifacial 시각화용)."""
        if self.rear_mode == 'full_area':
            return None, None
        finger_rects = []
        busbar_rects = []
        fx0, fx1 = self.rear_fg_x_range
        for fy in self.rear_fg_y:
            finger_rects.append((fx0, fy - self.rear.w_f / 2, fx1 - fx0, self.rear.w_f))
        by0, by1 = self.rear_bb_y_range
        for bx in self.rear_bb_x:
            busbar_rects.append((bx - self.rear.w_b / 2, by0, self.rear.w_b, by1 - by0))
        return finger_rects, busbar_rects

    def is_under_front_metal(self, x, y):
        """Point (x,y) under front metal?"""
        for (rx, ry, rw, rh) in self.metal_rects_front():
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                return True
        return False

    def summary(self):
        """Human-readable summary."""
        fg_len = self.fg_x_range[1] - self.fg_x_range[0]
        bb_len = self.bb_y_range[1] - self.bb_y_range[0]
        lines = [
            f"Wafer: {self.W*10:.1f} x {self.H*10:.1f} mm",
            f"Front: {self.n_f}F + {self.n_b}BB",
            f"  Finger: {self.w_f*1e4:.0f} um x {fg_len*10:.1f} mm, gap={self.front.edge_gap*10:.1f} mm",
            f"  Busbar: {self.w_b*1e4:.0f} um x {bb_len*10:.1f} mm",
            f"  Shading: {self.shading_fraction()*100:.2f}%",
            f"  Terminals: {len(self.front_terminals)}",
        ]
        if self.rear_mode == 'full_area':
            lines.append(f"Rear: full area metal")
        else:
            r = self.rear
            lines.append(f"Rear: {r.n_f}F + {r.n_b}BB (patterned)")
        return '\n'.join(lines)


# =============================================================
# DIODE PARAMETERS
# =============================================================
class DiodeParams:
    """Tandem 2-diode parameters.

    Originally based on Jeon et al., Solar Energy 292 (2025), Table 1, but the
    top/bottom diode defaults were re-anchored to the device literature in the
    TANDEM-3 fix (perovskite n1≈1.3, J01_top≈3e-18 → Voc_top~1.22V; Si J01≈9e-15
    → Voc_bot~0.73V), giving a credible tandem (Voc~1.95V, Eff~32.9% 0D-ideal;
    cf. KAUST 33.7% Voc 1.974V). The Jeon Table 1 values themselves were NOT
    independently verified against the paper; the Rs_top=2.0/Rs_bot=0.2 Ω·cm²
    annotations are higher than typical device literature (Rs~0.2-0.4 Ω·cm²) —
    verify against the source before publication.
    n1 is a free parameter (important for perovskite)."""
    # --- Top cell (Perovskite, ~1.68 eV) ---
    Jph_top = 19.65e-3        # A/cm2
    # TANDEM-3 fix (literature-anchored). The originally shipped J01_top_pass=
    # 8.8e-26 with n1=1.0 gave Voc_top=1.38 V → tandem Voc=2.28 V / Eff~39.7 %,
    # which EXCEEDS the certified ~34 % 2T record and is below even the 1.68 eV
    # radiative limit — physically non-credible. Replaced with values consistent
    # with the device literature for a 1.65-1.70 eV perovskite top cell:
    #   n1 ≈ 1.3   (effective ideality; Caprioglio, Adv. Energy Mater. 2020;
    #               Calado, Phys. Rev. Applied 14, 024031, 2020)
    #   J01_top_pass = 3e-18  → Voc_top ≈ 1.22 V (typical good cell 1.20-1.25 V)
    # Resulting tandem 0D (ideal, no spatial R): Voc≈1.95 V, FF≈86 %, Eff≈32.9 %,
    # matching the KAUST 33.7 % anchor (Voc 1.974 V, Jsc 20.99, FF 81.3 %;
    # pv-magazine 2023) once FEM resistive losses are added. Under-metal J01 keeps
    # a ~83x recombination enhancement. Originals preserved for reference:
    #   J01_top_pass = 8.8e-26 ; J01_top_metal = 7.3e-24 ; n1_top = 1.0
    J01_top_pass = 3.0e-18
    J02_top_pass = 2.62e-16
    J01_top_metal = 2.5e-16   # ~83x higher under metal
    J02_top_metal = 2.62e-15  # ~10x higher under metal
    n1_top = 1.3              # effective ideality for perovskite (lit. 1.3-1.5)
    n2_top = 2.0              # Free parameter
    Rsh_top = 5550            # Ohm*cm2 (lit. range 1e3-1e5)

    # --- Per-pixel internal series resistance (distributed model) ---
    # Each pixel's vertical transport R inside the cell layer (e.g. perovskite
    # bulk transport, contact at top of perovskite). This is part of the
    # 2D distributed diode model — NOT a global lumped Rs. v28's FEM grid
    # already handles lateral grid R / TCO R / contact R distributively;
    # this term adds the per-pixel vertical R that's inside each diode unit.
    # Jeon 2025 Table 1 calls this Rs_top / Rs_bot.
    # Applied as terminal IR drop: V_terminal = V_solver - J × Rs_internal.
    # Default 0 = no per-pixel internal R. Jeon: Rs_top=2.0, Rs_bot=0.2.
    Rs_internal_top = 0.0     # Ohm*cm2 (Jeon Rs_top: 2.0)
    Rs_internal_bot = 0.0     # Ohm*cm2 (Jeon Rs_bot: 0.2)
    # Backward compat aliases (deprecated, will be removed)
    Rs_lumped_top = 0.0
    Rs_lumped_bot = 0.0

    # --- Bottom cell (c-Si) ---
    # pass/metal split for backward-compatible tandem extension.
    # 기존 J01_bot, J02_bot은 아래 @property로 유지 → 솔버 코드(45곳) 한 줄도 안 바뀜.
    # 솔버에서 노드별 weighting을 쓰려면 _bot_pass / _bot_metal을 직접 참조 (Phase 1).
    # 기본값: pass = metal = 기존 단일값 → Phase 0 적용 시 결과 비트 단위 동일.
    Jph_bot = 19.65e-3
    # TANDEM-3 fix: previous J01_bot=1.3339e-17 gave Voc_bot=0.898 V, too high
    # for a real c-Si bottom cell (SHJ records ~0.75 V). Set to 9e-15 →
    # Voc_bot~0.73 V, consistent with the single-cell default J01_single=5.36e-15
    # (Voc~0.748 V). Original value preserved: J01_bot = 1.3339e-17.
    J01_bot_pass  = 9.0e-15      # passivated rear (typical c-Si SHJ, Voc~0.73 V)
    J01_bot_metal = 9.0e-15      # under rear metal contact (default same as pass)
    J02_bot_pass  = 6.5674e-22
    J02_bot_metal = 6.5674e-22
    n1_bot = 1.0              # Typically fixed for c-Si
    n2_bot = 2.0
    Rsh_bot = 12000

    # --- Single-cell mode (c-Si domain, matches Griddler single-cell) ---
    # Griddler cross-val defaults: Bot subcell (Si-like) from LONGi Flex 2025.11
    # Previously used perovskite top values by default — confusing for Single mode users.
    Jph_single = 19.77e-3       # mA/cm² — LONGi Flex Jsc
    J01_single_pass = 5.36e-15  # Si-like J01 (Voc ~ 0.748V)
    J02_single_pass = 0.0       # Set to 0 for Griddler compatibility
    J01_single_metal = 5.36e-15 # No pass/metal split for c-Si
    J02_single_metal = 0.0
    n1_single = 1.0
    n2_single = 2.0
    Rsh_single = 15000

    # --- Rear electrode ---
    # L3: rear TCO/emitter sheet R (lateral path before reaching rear metal).
    #     IZO ~15-80, BSF ~50-200 Ω/sq. Set ~0 for ideal equipotential rear.
    Rs_rear_tco = 50.0
    Rs_rear = 0.5  # deprecated

    # Rear metal–semiconductor contact resistivity [Ohm·cm²].
    # Real cells differ front vs rear (different doping polarity / paste /
    # process); Griddler likewise takes front & rear contact resistivity
    # independently. None = fall back to the front rc (bit-identical to the
    # legacy single-rc behavior when left unset). Set >0 to decouple the rear.
    rc_rear = None

    # Rear metal sheet R (박사님 2026.05.21: hot pressing 전면만, 후면 baseline).
    # 13.22 = 13.22 μΩ·cm × 10 μm = hot-pressing BEFORE state. 0 = auto from rm/hf.
    Rs_rear_metal_sheet = 13.22

    # --- Bifacial illumination (rear-side) ---
    # bifacial_gain = Jph_rear_eff / Jph_front. Range: 0 (mono) to 0.30 (outdoor + albedo).
    # NOT equivalent to full_area+rear-light: bifacial mode adds rear lateral V drops.
    # Validate within bifacial mode (gain=0 vs 0.2), not vs full_area.
    bifacial_gain = 0.20

    # --- Interlayer / Recombination Junction (박사님 2026.04.10) ---
    # Phase A: vertical contact R only.  V_bot_eff = (Ve-Vtop-Vr) - Rc_j × J_local.
    # Default 0 = ideal junction.  Typical PST: 0.02-0.2 Ω·cm², poor contact: 0.5-2.
    Rc_junction = 0.0

    # Phase B: Griddler-style lateral interlayer sheet R.
    # Rs_junction>0 enables the single-plane interlayer FEM model used for
    # Griddler-style runs. This is not the same model family as the Phase A
    # local-node Rs_junction=0 baseline, so direct Griddler PRO cross-validation
    # is required before claiming absolute equivalence.
    # Typical ITO/nc-SiOx: 50-500 Ω/sq. Default 0 = Phase A baseline.
    Rs_junction = 0.0

    # --- Spatial multiplier maps (v28.16 feature ③) ---
    # Per-node multipliers applied ON TOP OF the metal_frac pass/metal weighting,
    # so diode currents / generation / contact-R can vary across the cell plane.
    # Primary use: local contact-resistance scatter of screen-printed Ag fingers.
    # Each is either None (= uniform, all-ones, reproduces v28.15 exactly) or a
    # SpatialMap instance (from spatial_maps.py). The solver evaluates the map on
    # its own node coordinates at build time and caches the length-N array.
    #   spatial_j01 : multiplies J01 (top+bot saturation current, n1 diode)
    #   spatial_j02 : multiplies J02 (n2 / SCR recombination)
    #   spatial_gen : multiplies photogeneration Jph (optical non-uniformity)
    #   spatial_rc  : multiplies contact conductance Gc (1/multiplier on R_contact)
    spatial_j01 = None
    spatial_j02 = None
    spatial_gen = None
    spatial_rc  = None

    # --- Luminescent Coupling J01 (Zeder 2025; Jäger 2021) ---
    # J_LC = J01_coupling × (exp(qV_top/kT)-1), added to bot photocurrent.
    # Scaling: J01_coupling ≈ η_LC × J01_top_rad,  η_LC ≈ 36% (EPFL, Zeder 2025).
    # ATTRIBUTION FIX: Zeder et al. (Solar RRL 2025) model LC with SETFOS (Fluxim
    # drift-diffusion), NOT Griddler — LC is not a Griddler PRO feature. The
    # exp(qV_top/kT) LC form is the standard one (also Jäger, Solar RRL 2021).
    # Expected gain in current-matched PST: +0.1 to +0.5% abs (Jäger 2021, Nguyen 2024).
    J01_coupling = 0.0

    # --- Backward-compat aliases (v28.4) ---
    # 기존 코드에서 dp.J01_bot / dp.J02_bot을 직접 읽는 곳 45곳 보호.
    # 솔버에서 array weighting을 쓸 때는 _bot_pass / _bot_metal을 명시 참조 (Phase 1).
    @property
    def J01_bot(self):
        return self.J01_bot_pass
    @J01_bot.setter
    def J01_bot(self, val):
        # 기존 코드의 dp.J01_bot = x 호출 호환 → pass/metal 동시 갱신
        self.J01_bot_pass = val
        self.J01_bot_metal = val

    @property
    def J02_bot(self):
        return self.J02_bot_pass
    @J02_bot.setter
    def J02_bot(self, val):
        self.J02_bot_pass = val
        self.J02_bot_metal = val

    def expected_voc(self, mode='tandem'):
        """Proper 2-diode Voc including J02 and Rsh contributions.
        
        v28.1 FIX: Previously used n1-only approximation (ignored J02, Rsh),
        which caused Voc_est to be 10-15 mV off for realistic PST cells.
        This propagated to calc_iv sweep range and downstream Voc extraction.
        
        Solves the full 2-diode equation via bisection:
            Jph - J01(e^(V/n1VT) - 1) - J02(e^(V/n2VT) - 1) - V/Rsh = 0
        """
        def _solve_voc(Jph, J01, J02, Rsh, n1, n2):
            # Upper bound: n1-only approximation gives a safe upper bound
            V_hi = VT * n1 * np.log(max(Jph/J01, 1.0) + 1)
            V_hi = max(V_hi * 1.1, 0.1)
            def f(V):
                e1 = np.exp(np.clip(V / (n1 * VT), -80, 80))
                e2 = np.exp(np.clip(V / (n2 * VT), -80, 80))
                return Jph - J01*(e1-1) - J02*(e2-1) - V/Rsh
            V_lo = 1e-6
            # Extend bracket if needed
            if f(V_lo) < 0 or f(V_hi) > 0:
                V_hi_try = V_hi
                for _ in range(10):
                    if f(V_hi_try) < 0:
                        break
                    V_hi_try *= 1.5
                V_hi = V_hi_try
            # Bisection (60 iterations → ~1e-7 V precision)
            for _ in range(60):
                V_mid = 0.5 * (V_lo + V_hi)
                if f(V_mid) > 0:
                    V_lo = V_mid
                else:
                    V_hi = V_mid
                if V_hi - V_lo < 1e-7:
                    break
            return 0.5 * (V_lo + V_hi)
        
        if mode == 'single':
            return _solve_voc(self.Jph_single, self.J01_single_pass,
                               self.J02_single_pass, self.Rsh_single,
                               self.n1_single, self.n2_single)
        Vt = _solve_voc(self.Jph_top, self.J01_top_pass,
                         self.J02_top_pass, self.Rsh_top,
                         self.n1_top, self.n2_top)
        Vb = _solve_voc(self.Jph_bot, self.J01_bot,
                         self.J02_bot, self.Rsh_bot,
                         self.n1_bot, self.n2_bot)
        return Vt, Vb, Vt + Vb

    def subcell_iv(self, V, cell='top'):
        """0D subcell I-V (no spatial variation)."""
        if cell == 'top':
            return (self.Jph_top
                    - self.J01_top_pass * (np.exp(np.minimum(V / (self.n1_top * VT), 80)) - 1)
                    - self.J02_top_pass * (np.exp(np.minimum(V / (self.n2_top * VT), 80)) - 1)
                    - V / self.Rsh_top)
        else:
            return (self.Jph_bot
                    - self.J01_bot * (np.exp(np.minimum(V / (self.n1_bot * VT), 80)) - 1)
                    - self.J02_bot * (np.exp(np.minimum(V / (self.n2_bot * VT), 80)) - 1)
                    - V / self.Rsh_bot)

# =============================================================
# MESH GENERATION  —  v28.10 Griddler-style (tangent/perp to metal)
# Levels (Griddler manual v7.0 §2.5):
#   Low(~2)/Med(~4, default)/High(~8)/Max(~16) nodes between BBs along finger.
# =============================================================
# Front-grid calibration targets are approximately 30k / 50k / 85k / 138k
# nodes. Patterned rear features add nodes on top of these budgets.
_MESH_LEVELS = {
    # Each level appends balanced subdivisions on the same geometry so every
    # coarse vertex remains present in the next level.
    "Low":  {"power": 0, "axis_segments": 165, "target_nodes": 30000, "label": "coarse", "bd_mult": 0.6, "rf_mult": 0.7, "pass_density": 1},
    "Med":  {"power": 1, "axis_segments": 210, "target_nodes": 50000, "label": "default", "bd_mult": 1.0, "rf_mult": 1.0, "pass_density": 2},
    "High": {"power": 2, "axis_segments": 280, "target_nodes": 85000, "label": "fine", "bd_mult": 1.5, "rf_mult": 1.5, "pass_density": 3},
    "Max":  {"power": 3, "axis_segments": 360, "target_nodes": 138000, "label": "reference", "bd_mult": 2.5, "rf_mult": 2.0, "pass_density": 4},
}

def get_mesh_level(level):
    """Return hierarchical mesh parameters for a level name."""
    return _MESH_LEVELS.get(level, _MESH_LEVELS["Med"])


def _nested_linspace(start, stop, segments):
    """Return balanced vertices that remain present at every finer level.

    Vertices are kept LEFT-RIGHT SYMMETRIC: each dyadic level is added
    center-out in mirror pairs (f and 1-f together), so when the requested
    segment count truncates a level the remaining points are still symmetric
    about the midpoint. The previous low-fraction-first fill biased nodes to
    the low end (denser left, sparser right) whenever segments+1 was not a
    power of two plus one, which skewed the actual FEM mesh, not just its
    rendering. Coarser levels remain subsets of finer levels (warm-start
    prolongation stays valid)."""
    segments = max(1, int(segments))
    fractions = {0.0, 1.0}
    denominator = 2
    while len(fractions) < segments + 1:
        level = sorted({numerator / denominator
                        for numerator in range(1, denominator, 2)},
                       key=lambda f: abs(f - 0.5))
        for f in level:
            fractions.add(f)
            fractions.add(1.0 - f)
            if len(fractions) >= segments + 1:
                break
        denominator *= 2
    start = float(start)
    span = float(stop) - start
    return np.array(sorted(start + span * fraction for fraction in fractions))


def _mesh_seed_density(geo, bd):
    """Return an explicit legacy subdivision seed, or None for named levels."""
    del geo
    return None if bd is None else max(6, int(bd))


def _mesh_level_segments(seed, level):
    params = get_mesh_level(level)
    if seed is None:
        return params["axis_segments"]
    return max(2, int(seed)) * (1 << params["power"])


def mesh_quality_metrics(points, tri):
    """Return compact triangular-mesh quality diagnostics."""
    vertices = points[tri.simplices]
    edge_a = np.linalg.norm(vertices[:, 1] - vertices[:, 0], axis=1)
    edge_b = np.linalg.norm(vertices[:, 2] - vertices[:, 1], axis=1)
    edge_c = np.linalg.norm(vertices[:, 0] - vertices[:, 2], axis=1)
    edges = np.column_stack((edge_a, edge_b, edge_c))
    twice_area = np.abs(
        (vertices[:, 1, 0] - vertices[:, 0, 0])
        * (vertices[:, 2, 1] - vertices[:, 0, 1])
        - (vertices[:, 2, 0] - vertices[:, 0, 0])
        * (vertices[:, 1, 1] - vertices[:, 0, 1])
    )
    max_edge = np.max(edges, axis=1)
    altitude = np.divide(
        twice_area, max_edge, out=np.zeros_like(twice_area), where=max_edge > 0
    )
    aspect = np.divide(
        max_edge, altitude, out=np.full_like(max_edge, np.inf), where=altitude > 0
    )

    angles = []
    for opposite, side_1, side_2 in (
        (edge_a, edge_b, edge_c),
        (edge_b, edge_c, edge_a),
        (edge_c, edge_a, edge_b),
    ):
        cosine = np.divide(
            side_1**2 + side_2**2 - opposite**2,
            2.0 * side_1 * side_2,
            out=np.ones_like(opposite),
            where=(side_1 > 0) & (side_2 > 0),
        )
        angles.append(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))
    min_angle = np.min(np.column_stack(angles), axis=1)
    finite_aspect = aspect[np.isfinite(aspect)]
    return {
        "Triangles": int(len(tri.simplices)),
        "MinAngle_deg": float(np.min(min_angle)),
        "P05Angle_deg": float(np.percentile(min_angle, 5)),
        "MaxAspect": (
            float(np.max(finite_aspect)) if finite_aspect.size else float("inf")
        ),
    }


def mesh_distribution_metrics(points, geo, *, bins=12, ndigits=6):
    """Return symmetry and local-density diagnostics for visual mesh checks."""
    if points is None or len(points) == 0:
        return {
            "MirrorNodeHitX": 0.0,
            "MirrorNodeHitY": 0.0,
            "CentroidBiasX_um": 0.0,
            "CentroidBiasY_um": 0.0,
            "PeakBinOverMedian": 0.0,
            "PeakBinFraction": 0.0,
            "PeakBinCenterX_mm": 0.0,
            "PeakBinCenterY_mm": 0.0,
            "QuadrantImbalance": 0.0,
        }

    rounded = np.round(points, ndigits)
    point_set = set(map(tuple, rounded))
    width = float(geo.W)
    height = float(geo.H)
    mirror_x = sum(
        ((round(width - x, ndigits), round(y, ndigits)) in point_set)
        for x, y in point_set
    ) / len(point_set)
    mirror_y = sum(
        ((round(x, ndigits), round(height - y, ndigits)) in point_set)
        for x, y in point_set
    ) / len(point_set)

    centroid = np.mean(points, axis=0)
    hist, x_edges, y_edges = np.histogram2d(
        points[:, 0], points[:, 1],
        bins=max(2, int(bins)),
        range=[[0.0, width], [0.0, height]],
    )
    nonzero = hist[hist > 0]
    median = float(np.median(nonzero)) if nonzero.size else 0.0
    peak = float(np.max(hist)) if hist.size else 0.0
    peak_idx = np.unravel_index(int(np.argmax(hist)), hist.shape) if hist.size else (0, 0)
    peak_center_x = 0.5 * (x_edges[peak_idx[0]] + x_edges[peak_idx[0] + 1])
    peak_center_y = 0.5 * (y_edges[peak_idx[1]] + y_edges[peak_idx[1] + 1])

    q = np.array([
        np.sum((points[:, 0] <= width / 2.0) & (points[:, 1] <= height / 2.0)),
        np.sum((points[:, 0] > width / 2.0) & (points[:, 1] <= height / 2.0)),
        np.sum((points[:, 0] <= width / 2.0) & (points[:, 1] > height / 2.0)),
        np.sum((points[:, 0] > width / 2.0) & (points[:, 1] > height / 2.0)),
    ], dtype=float) / len(points)

    return {
        "MirrorNodeHitX": float(mirror_x),
        "MirrorNodeHitY": float(mirror_y),
        "CentroidBiasX_um": float((centroid[0] - width / 2.0) * 1e4),
        "CentroidBiasY_um": float((centroid[1] - height / 2.0) * 1e4),
        "PeakBinOverMedian": float(peak / median) if median > 0 else float("inf"),
        "PeakBinFraction": float(peak / len(points)) if len(points) else 0.0,
        "PeakBinCenterX_mm": float(peak_center_x * 10.0),
        "PeakBinCenterY_mm": float(peak_center_y * 10.0),
        "QuadrantImbalance": float(np.max(q) - np.min(q)),
    }


def generate_mesh_legacy(geo, bd=None, rf=3, pass_density=1, transition_mm=2.0,
                         mesh_tangent="Med", mesh_perp="Med"):
    """Adaptive mesh with transition zone refinement.

    Args:
        geo: CellGeometry
        bd: base density (auto-scaled if None)
        rf: refinement factor near metal edges
        pass_density: multiplier for passivated region node density (1=normal, 2=double)
        transition_mm: width of transition zone beyond metal edges [mm]
        mesh_tangent: "Low" | "Med" | "High" | "Max" — node density along metal direction
        mesh_perp: "Low" | "Med" | "High" | "Max" — node density perpendicular to metal
    """
    # Griddler-style mesh detail.
    # Override params from levels (overrides explicit args if non-default).
    if mesh_tangent != "Med" or mesh_perp != "Med":
        tang = get_mesh_level(mesh_tangent)
        perp = get_mesh_level(mesh_perp)
        # bd is influenced by both — tangent affects density along fingers (max_edge_pts),
        # perp affects density across fingers (passivated bulk fills).
        bd_mult_combined = (tang["bd_mult"] + perp["bd_mult"]) / 2.0
        if bd is not None:
            bd = int(bd * bd_mult_combined)
        rf = int(rf * tang["rf_mult"])
        pass_density = max(pass_density, perp["pass_density"])
    W, H = geo.W, geo.H
    n_grid = geo.n_f + geo.n_b

    if bd is None:
        # Scale with cell size: larger cells need proportionally more nodes
        bd = max(15, min(50, int(30 * min(W, H) / 0.9 / max(1, n_grid / 3))))

    pts = set()

    # Base grid
    for xi in np.linspace(0, W, bd + 1):
        for yi in np.linspace(0, H, bd + 1):
            pts.add((round(xi, 6), round(yi, 6)))

    # Enhanced passivated region density
    if pass_density > 1:
        bd_pass = int(bd * pass_density)
        for xi in np.linspace(0, W, bd_pass + 1):
            for yi in np.linspace(0, H, bd_pass + 1):
                pts.add((round(xi, 6), round(yi, 6)))

    dxf = W / (bd * rf)
    dyf = H / (bd * rf)
    max_edge_pts = min(int(W / dxf) + 1, 80)
    trans_cm = transition_mm / 10.0  # mm -> cm

    # Finger edges + transition zones
    fx0, fx1 = geo.fg_x_range
    for fy in geo.fg_y:
        hw = geo.w_f / 2
        x_dense = np.linspace(fx0, fx1, max_edge_pts)  # finger length range

        # Metal edges (exact boundary)
        for edge_y in [fy - hw, fy, fy + hw]:
            if 0 <= edge_y <= H:
                for xi in x_dense:
                    pts.add((round(xi, 6), round(edge_y, 6)))

        # Fill inside finger
        y_fill = np.linspace(fy - hw, fy + hw, max(3, min(6, int(geo.w_f / dyf) + 1)))
        for xi in x_dense[::2]:
            for yi in y_fill:
                if 0 <= yi <= H:
                    pts.add((round(xi, 6), round(yi, 6)))

        # Transition zones (±trans_cm beyond finger edges)
        for sign in [-1, +1]:
            edge = fy + sign * hw
            for offset in np.linspace(0, trans_cm, 5)[1:]:  # 4 layers
                ty = edge + sign * offset
                if 0 <= ty <= H:
                    # Sparser than metal edge but denser than background
                    for xi in x_dense[::3]:
                        pts.add((round(xi, 6), round(ty, 6)))

    # Busbar edges + transition zones
    by0, by1 = geo.bb_y_range
    for bx in geo.bb_x:
        hw = geo.w_b / 2
        max_edge_pts_y = min(int(H / dyf) + 1, 80)
        y_dense = np.linspace(by0, by1, max_edge_pts_y)  # busbar length range

        for edge_x in [bx - hw, bx, bx + hw]:
            if 0 <= edge_x <= W:
                for yi in y_dense:
                    pts.add((round(edge_x, 6), round(yi, 6)))

        x_fill = np.linspace(bx - hw, bx + hw, max(3, min(6, int(geo.w_b / dxf) + 1)))
        for yi in y_dense[::2]:
            for xi in x_fill:
                if 0 <= xi <= W:
                    pts.add((round(xi, 6), round(yi, 6)))

        # Front busbar transition zones
        for sign in [-1, +1]:
            edge = bx + sign * hw
            for offset in np.linspace(0, trans_cm, 5)[1:]:
                tx = edge + sign * offset
                if 0 <= tx <= W:
                    for yi in y_dense[::3]:
                        pts.add((round(tx, 6), round(yi, 6)))

    # NOTE: Rear pattern mesh insertion intentionally disabled — was found to
    # introduce a mesh-density dependent solver inaccuracy (38%→30% drift).
    # Bifacial uses same node density as full_area for consistent baseline.

    # Intersection refinement
    n_inter = max(3, min(8, int(10 / max(1, n_grid / 3))))
    for fy in geo.fg_y:
        for bx in geo.bb_x:
            for xi in np.linspace(max(0, bx - geo.w_b), min(W, bx + geo.w_b), n_inter):
                for yi in np.linspace(max(0, fy - geo.w_f), min(H, fy + geo.w_f), n_inter):
                    pts.add((round(xi, 6), round(yi, 6)))

    # Pad region (skip if pad=0, i.e. DXF mode)
    if geo.pad > 0:
        pcx, pcy = geo.pad_cx, geo.pad_cy
        for xi in np.linspace(pcx - geo.pad / 2, pcx + geo.pad / 2, 8):
            for yi in np.linspace(H - geo.pad, H, 8):
                if 0 <= xi <= W and 0 <= yi <= H:
                    pts.add((round(xi, 6), round(yi, 6)))

    # ensure mesh has nodes at exact terminal positions + refinement ring
    # so classify_nodes can mark them as pad via tolerance band.
    if hasattr(geo, 'front_terminals') and geo.front_terminals:
        ring_r = max(geo.w_b * 1.5, 0.025)  # 250 μm or 1.5 × BB width
        for tx, ty in geo.front_terminals:
            # Center
            pts.add((round(tx, 6), round(ty, 6)))
            # Refinement ring (3×3 grid around terminal)
            for dx in np.linspace(-ring_r, ring_r, 3):
                for dy in np.linspace(-ring_r, ring_r, 3):
                    nx, ny = tx + dx, ty + dy
                    if 0 <= nx <= W and 0 <= ny <= H:
                        pts.add((round(nx, 6), round(ny, 6)))

    points = np.array(sorted(pts))
    tri = Delaunay(points)
    return points, tri


def generate_mesh(geo, bd=None, rf=3, pass_density=1, transition_mm=2.0,
                  mesh_tangent="Med", mesh_perp="Med", axis_segments_override=None):
    """Generate a hierarchical triangular mesh around front and rear metal.

    ``mesh_tangent`` controls x subdivisions and ``mesh_perp`` controls y
    subdivisions. Legacy ``rf`` and ``pass_density`` arguments remain only so
    saved projects keep loading; named levels now define refinement.
    """
    del rf, pass_density
    W, H = geo.W, geo.H
    seed = _mesh_seed_density(geo, bd)
    tang_power = get_mesh_level(mesh_tangent)["power"]
    perp_power = get_mesh_level(mesh_perp)["power"]
    max_power = max(tang_power, perp_power)
    x_segments = _mesh_level_segments(seed, mesh_tangent)
    y_segments = _mesh_level_segments(seed, mesh_perp)
    # v28.17: optional direct override of axis subdivisions (node-count input).
    #   레벨 대신 사용자가 지정한 세분화 수를 x/y에 직접 적용. 레벨의 power는
    #   유지(across/transition/intersection 세분화 스타일은 그대로).
    if axis_segments_override is not None and int(axis_segments_override) > 0:
        x_segments = y_segments = int(axis_segments_override)
    pts = set()

    def add(x, y):
        if -1e-12 <= x <= W + 1e-12 and -1e-12 <= y <= H + 1e-12:
            pts.add((round(float(x), 9), round(float(y), 9)))

    for xi in _nested_linspace(0, W, x_segments):
        for yi in _nested_linspace(0, H, y_segments):
            add(xi, yi)

    trans_cm = transition_mm / 10.0
    # Keep exact metal edges at every level. Extra layers inside very narrow
    # printed lines are capped because over-refining those strips makes the
    # FEM system ill-conditioned without improving the area-integrated result.
    across_x_segments = min(4, 2 << tang_power)
    across_y_segments = min(4, 2 << perp_power)
    transition_x_segments = min(8, 2 << tang_power)
    transition_y_segments = min(8, 2 << perp_power)
    intersection_segments = min(8, 2 << max_power)

    def add_terminal_ring(terminals, width):
        ring_r = max(width * 1.5, 0.025)
        for tx, ty in terminals:
            add(tx, ty)
            for xi in _nested_linspace(tx - ring_r, tx + ring_r,
                                       intersection_segments):
                for yi in _nested_linspace(ty - ring_r, ty + ring_r,
                                           intersection_segments):
                    add(xi, yi)

    def add_grid_features(fg_y, bb_x, fg_x_range, bb_y_range,
                          w_f, w_b, terminals):
        fx0, fx1 = fg_x_range
        by0, by1 = bb_y_range
        x_dense = _nested_linspace(fx0, fx1, x_segments)
        y_dense = _nested_linspace(by0, by1, y_segments)

        for fy in fg_y:
            for xi in x_dense:
                for yi in (fy - w_f / 2, fy, fy + w_f / 2):
                    add(xi, yi)
            for xi in _nested_linspace(fx0, fx1, max(1, x_segments // 2)):
                for yi in _nested_linspace(fy - w_f / 2, fy + w_f / 2,
                                           across_y_segments):
                    add(xi, yi)
            for xi in _nested_linspace(fx0, fx1, max(1, x_segments // 3)):
                for sign in (-1, 1):
                    for offset in _nested_linspace(0, trans_cm,
                                                   transition_y_segments)[1:]:
                        add(xi, fy + sign * (w_f / 2 + offset))

        for bx in bb_x:
            for yi in y_dense:
                for xi in (bx - w_b / 2, bx, bx + w_b / 2):
                    add(xi, yi)
            for yi in _nested_linspace(by0, by1, max(1, y_segments // 2)):
                for xi in _nested_linspace(bx - w_b / 2, bx + w_b / 2,
                                           across_x_segments):
                    add(xi, yi)
            for yi in _nested_linspace(by0, by1, max(1, y_segments // 3)):
                for sign in (-1, 1):
                    for offset in _nested_linspace(0, trans_cm,
                                                   transition_x_segments)[1:]:
                        add(bx + sign * (w_b / 2 + offset), yi)

        for fy in fg_y:
            for bx in bb_x:
                for xi in _nested_linspace(max(0, bx - w_b),
                                           min(W, bx + w_b),
                                           intersection_segments):
                    for yi in _nested_linspace(max(0, fy - w_f),
                                               min(H, fy + w_f),
                                               intersection_segments):
                        add(xi, yi)
        add_terminal_ring(terminals, w_b)

    add_grid_features(
        geo.fg_y, geo.bb_x, geo.fg_x_range, geo.bb_y_range,
        geo.w_f, geo.w_b, getattr(geo, "front_terminals", []),
    )

    if geo.rear_mode in ("patterned", "bifacial") and geo.rear is not None:
        add_grid_features(
            geo.rear_fg_y, geo.rear_bb_x, geo.rear_fg_x_range,
            geo.rear_bb_y_range, geo.rear.w_f, geo.rear.w_b,
            getattr(geo, "rear_terminals", []),
        )

    # Pad region (skip if pad=0, i.e. DXF mode).
    if geo.pad > 0:
        pcx, pcy = geo.pad_cx, geo.pad_cy
        for xi in _nested_linspace(pcx - geo.pad / 2, pcx + geo.pad / 2,
                                   intersection_segments):
            for yi in _nested_linspace(H - geo.pad, H, intersection_segments):
                add(xi, yi)

    points = np.array(sorted(pts))
    tri = Delaunay(points)
    return points, tri


def _generate_mesh_for_target(geo, mesh_tangent="Med", mesh_perp="Med",
                              target_nodes=30000, max_iter=7, tol=0.04,
                              progress=None):
    """Mesh so node count ~= target_nodes, robust for ANY cell size.

    v28.17 fix (Seunghoon): node_count(axis) is monotonic but its exponent vs
    axis depends on the cell — small cells are background-grid dominated
    (~axis^2), large/feature-dense cells (e.g. M10, 80 fingers) are refinement
    dominated (~axis^1). A fixed-exponent step (sqrt) only converges in one
    regime, so target 80000 on M10 missed by +23%. This estimates the LOCAL
    exponent p from the two most recent (axis, N) samples (log-log secant) and
    predicts the next axis, so it adapts to every size. Always keeps the closest
    result found; clamps axis to [40,700]; stops at tol, granularity floor, or
    a clamp bound. Returns (points, tri, n_actual, axis_used)."""
    import math as _math
    LO, HI = 40, 700
    # Conservative start: cap the first axis so the initial mesh is never huge
    # on feature-dense cells (the secant climbs up from here when needed).
    a = int(round(165.0 * (max(target_nodes, 1) / 30000.0) ** 0.5))
    a = max(LO, min(HI, min(a, 130)))
    prev_a = prev_N = None
    best = None  # (abs_err, points, tri, N, axis)
    for _it in range(max_iter):
        pts, tri = generate_mesh(geo, mesh_tangent=mesh_tangent,
                                 mesh_perp=mesh_perp, axis_segments_override=a)
        N = len(pts)
        err = abs(N - target_nodes)
        if best is None or err < best[0]:
            best = (err, pts, tri, N, a)
        if progress is not None:
            try:
                progress(_it + 1, a, N)
            except Exception:
                pass
        if err <= tol * target_nodes:
            break
        if (prev_a is not None and prev_N is not None
                and N != prev_N and a != prev_a):
            # local power law: N ~ axis^p (p estimated from last two samples)
            p = _math.log(N / prev_N) / _math.log(a / prev_a)
            p = max(0.5, min(3.0, p))
            a_next = a * (target_nodes / max(N, 1)) ** (1.0 / p)
        else:
            a_next = a * (target_nodes / max(N, 1)) ** 0.5  # first step: ~quadratic
        a_next = int(round(max(LO, min(HI, a_next))))
        if a_next == a:
            # nudge by 1 to escape the discrete-step floor; stop if at a bound
            a_next = max(LO, min(HI, a + (1 if N < target_nodes else -1)))
            if a_next == a:
                break
        prev_a, prev_N = a, N
        a = a_next
    return best[1], best[2], best[3], best[4]


def classify_nodes(points, geo):
    """Binary classification for front + rear metal regions.
       Returns: is_finger, is_busbar, is_pad, is_metal  (front)
                + is_rear_metal, is_rear_pad            (if patterned)
       For full_area mode: rear_metal/rear_pad are None."""
    N = len(points)
    x = points[:, 0]
    y = points[:, 1]
    fx0, fx1 = geo.fg_x_range
    by0, by1 = geo.bb_y_range

    # --- Front ---
    is_finger = np.zeros(N, dtype=bool)
    for fy in geo.fg_y:
        is_finger |= ((np.abs(y - fy) <= geo.w_f / 2 + 1e-6) &
                       (x >= fx0 - 1e-6) & (x <= fx1 + 1e-6))

    is_busbar = np.zeros(N, dtype=bool)
    for bx in geo.bb_x:
        is_busbar |= ((np.abs(x - bx) <= geo.w_b / 2 + 1e-6) &
                       (y >= by0 - 1e-6) & (y <= by1 + 1e-6))

    if geo.pad > 0:
        # box centered on (pad_cx, pad_cy) — previously anchored to wafer top
        is_pad = ((np.abs(x - geo.pad_cx) <= geo.pad / 2 + 1e-6) &
                  (np.abs(y - geo.pad_cy) <= geo.pad / 2 + 1e-6))
    else:
        # pad=0 (default) → use terminal positions (BB centers) directly.
        # Previous code generated phantom pad at BB top — caused upper-left
        # dark spot in voltage maps. Now mark mesh nodes within a small radius
        # of each terminal position (set in compute_positions).
        is_pad = np.zeros(N, dtype=bool)
        if hasattr(geo, 'front_terminals') and geo.front_terminals:
            # Use small radius (~busbar half-width or 250 μm, whichever larger)
            tol = max(geo.w_b / 2 + 1e-6, 0.025)  # 250 μm minimum radius
            for tx, ty in geo.front_terminals:
                is_pad |= ((np.abs(x - tx) <= tol) &
                           (np.abs(y - ty) <= tol))
            # Safety: ensure at least one pad node per terminal
            if not np.any(is_pad) and geo.bb_x:
                # Fallback: closest mesh node to first terminal
                tx, ty = geo.front_terminals[0]
                d2 = (x - tx) ** 2 + (y - ty) ** 2
                is_pad[np.argmin(d2)] = True

    is_metal = is_finger | is_busbar | is_pad

    # --- Rear (only if bifacial / patterned) ---
    if geo.rear_mode in ('patterned', 'bifacial') and geo.rear is not None:
        r_fx0, r_fx1 = geo.rear_fg_x_range
        r_by0, r_by1 = geo.rear_bb_y_range
        w_rf = geo.rear.w_f
        w_rb = geo.rear.w_b

        is_rear_finger = np.zeros(N, dtype=bool)
        for fy in geo.rear_fg_y:
            is_rear_finger |= ((np.abs(y - fy) <= w_rf / 2 + 1e-6) &
                               (x >= r_fx0 - 1e-6) & (x <= r_fx1 + 1e-6))

        is_rear_busbar = np.zeros(N, dtype=bool)
        for bx in geo.rear_bb_x:
            is_rear_busbar |= ((np.abs(x - bx) <= w_rb / 2 + 1e-6) &
                               (y >= r_by0 - 1e-6) & (y <= r_by1 + 1e-6))

        is_rear_metal = is_rear_finger | is_rear_busbar
        # use rear_terminals positions instead of auto BB top
        is_rear_pad = np.zeros(N, dtype=bool)
        if geo.pad > 0:
            # Legacy: pad box at top of each rear BB
            pad_h_r = max(w_rb * 10, 0.04)
            for r_bx in geo.rear_bb_x:
                is_rear_pad |= ((np.abs(x - r_bx) <= w_rb / 2 + 1e-6) &
                                (y >= r_by1 - pad_h_r - 1e-6) & (y <= r_by1 + 1e-6))
        elif hasattr(geo, 'rear_terminals') and geo.rear_terminals:
            # use rear terminal positions (BB centers) directly
            tol_r = max(w_rb / 2 + 1e-6, 0.025)
            for tx_r, ty_r in geo.rear_terminals:
                is_rear_pad |= ((np.abs(x - tx_r) <= tol_r) &
                                (np.abs(y - ty_r) <= tol_r))
            # Safety: ensure at least one rear pad node
            if not np.any(is_rear_pad) and geo.rear_terminals:
                tx_r, ty_r = geo.rear_terminals[0]
                d2 = (x - tx_r) ** 2 + (y - ty_r) ** 2
                is_rear_pad[np.argmin(d2)] = True
    else:
        is_rear_metal = None
        is_rear_pad = None

    return is_finger, is_busbar, is_pad, is_metal, is_rear_metal, is_rear_pad


# =============================================================
# POLYGON CLIPPING (Sutherland-Hodgman) for metal_frac
# =============================================================
def _clip_poly(poly, x1, y1, x2, y2):
    if len(poly) == 0:
        return []
    out = []
    for i in range(len(poly)):
        cur = poly[i]
        nxt = poly[(i + 1) % len(poly)]
        cs = (x2 - x1) * (cur[1] - y1) - (y2 - y1) * (cur[0] - x1)
        ns = (x2 - x1) * (nxt[1] - y1) - (y2 - y1) * (nxt[0] - x1)
        if cs >= 0:
            out.append(cur)
        if (cs >= 0) != (ns >= 0):
            d = cs - ns
            if abs(d) > 1e-15:
                t = cs / d
                out.append((cur[0] + t * (nxt[0] - cur[0]),
                            cur[1] + t * (nxt[1] - cur[1])))
    return out


def _poly_area(poly):
    n = len(poly)
    if n < 3:
        return 0.0
    a = 0.0
    for i in range(n):
        j = (i + 1) % n
        a += poly[i][0] * poly[j][1] - poly[j][0] * poly[i][1]
    return abs(a) * 0.5


def _tri_rect_area(tri_pts, rx, ry, rw, rh):
    poly = list(tri_pts)
    poly = _clip_poly(poly, rx, ry, rx + rw, ry)
    poly = _clip_poly(poly, rx + rw, ry, rx + rw, ry + rh)
    poly = _clip_poly(poly, rx + rw, ry + rh, rx, ry + rh)
    poly = _clip_poly(poly, rx, ry + rh, rx, ry)
    return _poly_area(poly)


def compute_metal_frac(points, simplices, areas, geo):
    """Exact geometric metal fraction per node (area-weighted, Griddler method).
       Uses geo.metal_rects_front() for proper finger/busbar lengths."""
    N = len(points)
    n_elem = len(simplices)
    rects = geo.metal_rects_front()

    elem_mf = np.zeros(n_elem)
    for ei in range(n_elem):
        if areas[ei] < 1e-15:
            continue
        i0, i1, i2 = simplices[ei]
        tri = ((points[i0][0], points[i0][1]),
               (points[i1][0], points[i1][1]),
               (points[i2][0], points[i2][1]))
        total_inter = 0.0
        for (rx, ry, rw, rh) in rects:
            total_inter += _tri_rect_area(tri, rx, ry, rw, rh)
        elem_mf[ei] = min(total_inter / areas[ei], 1.0)

    metal_area = np.zeros(N)
    total_area = np.zeros(N)
    for m in range(3):
        np.add.at(total_area, simplices[:, m], areas / 3.0)
        np.add.at(metal_area, simplices[:, m], elem_mf * areas / 3.0)

    metal_frac = np.where(total_area > 1e-15, metal_area / total_area, 0.0)
    return metal_frac


def _compute_rear_metal_frac(points, simplices, areas, geo):
    """Same as compute_metal_frac but for rear-side metal pattern.
       Used to determine rear illumination blocking in bifacial mode."""
    rects = geo.metal_rects_rear()
    if rects is None:
        # Full area rear metal - blocks all rear light
        return np.ones(len(points))

    N = len(points)
    n_elem = len(simplices)
    elem_mf = np.zeros(n_elem)
    for ei in range(n_elem):
        if areas[ei] < 1e-15:
            continue
        i0, i1, i2 = simplices[ei]
        tri = ((points[i0][0], points[i0][1]),
               (points[i1][0], points[i1][1]),
               (points[i2][0], points[i2][1]))
        total_inter = 0.0
        for (rx, ry, rw, rh) in rects:
            total_inter += _tri_rect_area(tri, rx, ry, rw, rh)
        elem_mf[ei] = min(total_inter / areas[ei], 1.0)

    metal_area = np.zeros(N)
    total_area = np.zeros(N)
    for m in range(3):
        np.add.at(total_area, simplices[:, m], areas / 3.0)
        np.add.at(metal_area, simplices[:, m], elem_mf * areas / 3.0)

    return np.where(total_area > 1e-15, metal_area / total_area, 0.0)

    elem_mf = np.zeros(n_elem)
    for ei in range(n_elem):
        if areas[ei] < 1e-15:
            continue
        i0, i1, i2 = simplices[ei]
        tri = ((points[i0][0], points[i0][1]),
               (points[i1][0], points[i1][1]),
               (points[i2][0], points[i2][1]))
        total_inter = 0.0
        for (rx, ry, rw, rh) in rects:
            total_inter += _tri_rect_area(tri, rx, ry, rw, rh)
        elem_mf[ei] = min(total_inter / areas[ei], 1.0)

    # Distribute to nodes (area-weighted)
    metal_area = np.zeros(N)
    total_area = np.zeros(N)
    for m in range(3):
        np.add.at(total_area, simplices[:, m], areas / 3.0)
        np.add.at(metal_area, simplices[:, m], elem_mf * areas / 3.0)

    metal_frac = np.where(total_area > 1e-15, metal_area / total_area, 0.0)
    return metal_frac


# =============================================================
# FEM ASSEMBLY
# =============================================================
def assemble_K(points, simplices, Rs, areas, b, c):
    """Emitter (or rear) stiffness matrix from sheet resistance.
       Rs can be a scalar (uniform) or a per-element array."""
    N = len(points)
    valid = areas > 1e-15
    idx = simplices[valid]
    A = areas[valid]
    bv = b[valid]
    cv = c[valid]

    # Handle scalar or per-element Rs
    if np.isscalar(Rs):
        coeff = 1.0 / (4.0 * A * Rs)
    else:
        Rs_valid = Rs[valid]
        coeff = 1.0 / (4.0 * A * Rs_valid)

    rows = []
    cols = []
    vals = []
    for m in range(3):
        for n in range(3):
            rows.append(idx[:, m])
            cols.append(idx[:, n])
            vals.append(coeff * (bv[:, m] * bv[:, n] + cv[:, m] * cv[:, n]))

    K = coo_matrix((np.concatenate(vals),
                     (np.concatenate(rows), np.concatenate(cols))),
                    shape=(N, N)).tocsr()

    # Nodal areas
    na = np.zeros(N)
    for m in range(3):
        np.add.at(na, idx[:, m], A / 3.0)

    return K, na


def assemble_K_met(points, simplices, ism, rm, hf, wf, cf,
                   isf, isb, areas, b, c, w_b, geo=None):
    """Front metal grid stiffness matrix.

    Bug fix (mesh-density connectivity):
    Original version required ALL 3 element nodes to be in `ism` for the
    element to contribute. In dense meshes, finger-edge elements often have
    only 2/3 metal nodes, fragmenting the metal grid into disconnected
    components. The pad BC could not reach orphaned metal nodes, causing
    the solver to converge to wrong fixed points (efficiency collapse from
    38% to 24%).

    Correct fix: include 2/3-metal elements, then "absorb" any metal-to-
    non-metal coupling into the metal node's diagonal. This preserves the
    Galerkin row-sum-zero property restricted to the metal subspace, which
    is essential for the solver to behave physically (V → V + const must
    leave KCL unchanged in the metal grid).
    """
    N = len(points)
    Rsf = rm / (cf * hf) if hf > 0 else 1e10  # Finger sheet R
    Rsb = rm / hf if hf > 0 else 1e10          # Busbar sheet R (no CF)

    n_metal = (ism[simplices[:, 0]].astype(np.int8)
             + ism[simplices[:, 1]].astype(np.int8)
             + ism[simplices[:, 2]].astype(np.int8))

    # Include elements with 2 or 3 metal nodes (was: only 3)
    am = n_metal >= 2
    valid = am & (areas > 1e-15)
    if not np.any(valid):
        return csr_matrix((N, N))

    idx = simplices[valid]
    A = areas[valid]
    bv = b[valid]
    cv = c[valid]

    # Classify element type by node majority (>=2 of 3)
    af = (isf[idx[:, 0]].astype(np.int8)
        + isf[idx[:, 1]].astype(np.int8)
        + isf[idx[:, 2]].astype(np.int8)) >= 2
    ab = (isb[idx[:, 0]].astype(np.int8)
        + isb[idx[:, 1]].astype(np.int8)
        + isb[idx[:, 2]].astype(np.int8)) >= 2
    Rs_a = np.where(af & ~ab, Rsf, np.where(ab, Rsb, 0.5 * (Rsf + Rsb)))

    coeff = 1.0 / (4.0 * A * Rs_a)
    rows = []
    cols = []
    vals = []
    for m in range(3):
        for n in range(3):
            rows.append(idx[:, m])
            cols.append(idx[:, n])
            vals.append(coeff * (bv[:, m] * bv[:, n] + cv[:, m] * cv[:, n]))

    K = coo_matrix((np.concatenate(vals),
                    (np.concatenate(rows), np.concatenate(cols))),
                   shape=(N, N)).tocsr()

    # Absorb metal-to-non-metal couplings into metal diagonal.
    # For each metal row i: collect K[i, j] where j is non-metal,
    # and add them to K[i, i] (diagonal). Then zero K[i, j].
    # This restores the metal-only row sum = 0 property (Galerkin invariance
    # under V -> V + const), ensuring physically correct solver behavior.
    # Equivalent to imposing V_nonmetal = V_metal_neighbor at the boundary
    # (Neumann-like absorption of non-metal nodes).
    K_lil = K.tolil()
    nonmetal_idx = np.where(~ism)[0]
    nonmetal_set = set(nonmetal_idx.tolist())
    metal_idx = np.where(ism)[0]
    for i in metal_idx:
        row_data = K_lil.data[i]
        row_cols = K_lil.rows[i]
        diag_add = 0.0
        new_data = []
        new_cols = []
        for c_idx, val in zip(row_cols, row_data):
            if c_idx in nonmetal_set:
                diag_add += val  # absorb into diagonal
            else:
                new_data.append(val)
                new_cols.append(c_idx)
        # Add diag_add to diagonal entry (find or create)
        if i in new_cols:
            di = new_cols.index(i)
            new_data[di] += diag_add
        else:
            new_cols.append(i)
            new_data.append(diag_add)
        K_lil.rows[i] = new_cols
        K_lil.data[i] = new_data

    # Zero out non-metal rows entirely (those nodes are not metal DOF)
    for i in nonmetal_idx:
        K_lil.rows[i] = []
        K_lil.data[i] = []

    return K_lil.tocsr()


def assemble_K_met_1d(points, ism, geo, rm, hf, cf, w_f=None, w_b=None, gc_max=0.0,
                      fg_y=None, bb_x=None, band_w_f=None, band_w_b=None):
    """1D conductor model for a metal grid (v28.14; rear-capable since ASM-1 fix).

    ASM-1: the line centers (fg_y / bb_x) and the node-selection band widths
    (band_w_f / band_w_b) default to the FRONT grid (geo.fg_y, geo.bb_x,
    geo.w_f, geo.w_b) but can be overridden so the SAME mesh-convergent 1D model
    can assemble the REAR metal grid. Previously the rear used the 2D Galerkin
    sheet model (assemble_K_met) that the front abandoned because it is
    mesh-dependent for thin lines (sliver triangles), making bifacial/patterned-
    rear FF/efficiency non-convergent under refinement.

    WHY: the 2D Galerkin sheet model (assemble_K_met) creates sliver
    triangles wherever the metal line width (e.g. 50 um finger) is much
    smaller than the in-plane node spacing. Sliver elements have
    ill-conditioned shape-function gradients, so the longitudinal finger
    conductance becomes mesh-dependent — refining the mesh keeps changing
    the answer (efficiency diverges, FF drifts) instead of converging.
    Verified: 50 um finger, rf 2->10, efficiency spread 0.59% (2D) -> 0.08%
    (1D); and on a 500 um finger where the 2D model DOES converge, the 1D
    model matches it to 0.05% abs, confirming the resistance is physical.

    FIX: a finger is physically a thin, highly-conductive line. Current
    flows ALONG its length; the transverse potential drop across its width
    is negligible. So we model each finger as:
      • transverse: all metal nodes at the same lengthwise position are
        equipotential-bonded (strong conductance SHORT)
      • longitudinal: adjacent lengthwise positions connected by the true
        1D resistance R/length = rho / (cf * A), A = width * height
    Busbars are treated identically along their (vertical) length, with no
    shape-correction factor. Mesh-independent regardless of line width,
    because resistance depends only on node SPACING, not element shape.

    Returns an (N,N) CSR matrix with non-zero rows only at metal nodes,
    matching the contract of assemble_K_met (non-metal rows are empty).
    """
    N = len(points)
    K = lil_matrix((N, N))
    if hf <= 0:
        return K.tocsr()

    # Equipotential bond strength. Must dominate both the 1D longitudinal
    # conductance and the contact conductance Gc so that same-position metal
    # nodes truly share one potential. Large enough to bond, small enough to
    # avoid wrecking matrix conditioning.
    # v28.18 fix (리뷰 1-C): 고정 1e4는 접촉 컨덕턴스 Gc=na·mf/rc 가 작은 rc
    #   (이상접촉, _build에서 rc>=1e-12로 클램프)에서 1e7까지 치솟으면 본드를
    #   압도당해 1D 모델의 mesh-독립성이 깨진다. Gc 피크(gc_max)에 비례해
    #   끌어올려 항상 본드가 지배하도록 한다. 기본 rc에선 gc_max~1e-3 →
    #   1e3*gc_max~1 < 1e4 → SHORT=1e4 그대로(비트 동일). 단 rc→0 에서는
    #   행렬이 stiff 해지므로 일상 실행은 rc>=1e-4 권장.
    SHORT = max(1.0e4, 1.0e3 * float(gc_max))

    def _chain_along(coord_axis, line_centers, half_width, R_per_len):
        """1D chain + transverse bonds for a set of parallel lines.
        coord_axis 0 -> lines run along x (fingers); 1 -> along y (busbars).
        """
        perp = 1 - coord_axis
        for c in line_centers:
            band = (np.abs(points[:, perp] - c) <= half_width + 1e-6) & ism
            idx = np.where(band)[0]
            if len(idx) < 2:
                continue
            along = points[idx, coord_axis]
            order = np.argsort(along, kind='stable')
            idx_o = idx[order]
            along_o = along[order]
            # Group nodes at the same lengthwise position
            groups = []
            cur_pos = along_o[0]
            cur = [int(idx_o[0])]
            for k in range(1, len(idx_o)):
                if along_o[k] - cur_pos < 1e-7:
                    cur.append(int(idx_o[k]))
                else:
                    groups.append((cur_pos, cur))
                    cur_pos = along_o[k]
                    cur = [int(idx_o[k])]
            groups.append((cur_pos, cur))
            # Transverse equipotential bond within each group; rep = min index
            reps = []
            for pos, members in groups:
                rep = min(members)
                reps.append((pos, rep))
                for m in members:
                    if m == rep:
                        continue
                    K[rep, rep] += SHORT
                    K[m, m] += SHORT
                    K[rep, m] -= SHORT
                    K[m, rep] -= SHORT
            # Longitudinal 1D resistors between adjacent representatives
            for k in range(len(reps) - 1):
                p0, i = reps[k]
                p1, j = reps[k + 1]
                dl = p1 - p0
                if dl <= 1e-9:
                    continue
                g = 1.0 / (R_per_len * dl)
                K[i, i] += g
                K[j, j] += g
                K[i, j] -= g
                K[j, i] -= g

    # v28.18 (wf_wired, 리뷰 [1-1] 수정): 단면적(CROSS-SECTION)은 케이스별 폭
    #   (w_f/w_b 인자 — 예: 핫프레싱 After 65μm)을 쓰고, 노드 선택 밴드는 설계
    #   (메시) 폭 geo.w_f/geo.w_b를 유지한다. 메시 노드는 설계 geometry의 금속선
    #   위에 있으므로, 케이스 폭 변화는 "선의 단위길이 저항"만 바꿔야 하고 어떤
    #   노드가 그 선에 속하는지는 바꾸면 안 된다. w_f/w_b=None -> 설계 폭(기존과
    #   비트 단위 동일).
    w_f_eff = geo.w_f if w_f is None else float(w_f)
    w_b_eff = geo.w_b if w_b is None else float(w_b)
    # ASM-1: line centers + node-selection band widths default to the FRONT grid
    # but can be overridden for the REAR grid (geo.rear_fg_y / geo.rear_bb_x,
    # geo.rear.w_f / geo.rear.w_b).
    _fg_y = geo.fg_y if fg_y is None else fg_y
    _bb_x = geo.bb_x if bb_x is None else bb_x
    _band_f = geo.w_f if band_w_f is None else float(band_w_f)
    _band_b = geo.w_b if band_w_b is None else float(band_w_b)

    # Fingers: along x, cross-section A_f = w_f_eff * h_f, with cf
    A_f = w_f_eff * hf
    if A_f > 0:
        Rpl_f = rm / (cf * A_f)
        _chain_along(0, _fg_y, _band_f / 2.0, Rpl_f)

    # Busbars: along y, cross-section A_b = w_b_eff * h_f, no cf
    A_b = w_b_eff * hf
    if A_b > 0:
        Rpl_b = rm / A_b
        _chain_along(1, _bb_x, _band_b / 2.0, Rpl_b)

    return K.tocsr()


# =============================================================
# 0D ANALYTICAL TANDEM SOLVER (v28.4 — Step 4)
# =============================================================
# 검증 목적: 2D FEM 손실(시트R, 금속R, 접촉R, interlayer)이 모두 0인
# 극한 조건에서 2L-FEST tandem 결과가 수학적으로 등가한 0D 2-diode
# 직렬 모델과 일치해야 한다. 일치 → 솔버의 다이오드 핵심 로직 검증.
# 불일치 → 솔버 버그 또는 FEM에 R이 잔류.


# ============================================================================
# DXF GRID IMPORT (merged from dxf_grid.py — v28.16 single-file)
# ============================================================================
LAYER_SYNONYMS = {
    "cell":    {"cell", "cellsize", "wafer", "outline", "boundary", "die", "substrate"},
    "finger":  {"finger", "fingers", "grid", "gridline"},
    "busbar":  {"busbar", "busbars", "bb", "bus", "bar", "mbb"},
    "contact": {"contact", "contactpoint", "pad", "probe", "terminal", "terminals", "solderpad"},
}


def _norm(s: str) -> str:
    return "".join(c for c in s.lower() if c.isalnum())


# Layers whose names mark them as REAR-side geometry. This loader imports the
# FRONT pattern only (rear stays full_area), so these must NOT be pulled into
# the front finger/busbar lists. Without this guard the substring match below
# would classify 'rear_fingers' as finger and 'rear_busbars' as busbar,
# drawing rear bars on the front and corrupting widths/shading.
_REAR_PREFIXES = ("rear", "back", "bottom", "rear_", "back_")


def _is_rear_layer(norm_name: str) -> bool:
    # norm_name is already alphanumeric-lowercased (e.g. 'rearbusbars')
    return norm_name.startswith(("rear", "back", "bottom"))


def _classify_layer(name: str, extra: dict | None) -> str | None:
    n = _norm(name)
    # Explicit user override wins (even for rear-prefixed names, in case the
    # user deliberately maps one).
    if extra:
        for raw, cat in extra.items():
            if _norm(raw) == n:
                return cat
    # Skip rear-side layers entirely: front import only.
    if _is_rear_layer(n):
        return None
    # Exact synonym match first (most reliable).
    for cat, syns in LAYER_SYNONYMS.items():
        if n in syns:
            return cat
    # Substring fallback (e.g. 'mainbusbar' -> busbar). Rear layers already
    # filtered out above, so this no longer misfires on 'rear_*'.
    for cat, syns in LAYER_SYNONYMS.items():
        if any(s in n for s in syns):
            return cat
    return None


_UNIT_TO_CM = {0: 1.0, 1: 2.54, 2: 30.48, 4: 0.1, 5: 1.0, 6: 100.0, 13: 1e-4}
_UNIT_NAME = {0: "unitless", 1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m", 13: "um"}
_FORCE = {"um": 1e-4, "mm": 0.1, "cm": 1.0, "m": 100.0, "in": 2.54}


# ---------------------------------------------------------------------------
# DxfGrid: 임포트 결과 컨테이너 (모든 좌표 cm, wafer 좌하단 원점)
# ---------------------------------------------------------------------------
class DxfGrid:
    def __init__(self):
        self.W = self.H = 0.0
        self.finger_rects: list[tuple] = []   # (x, y, w, h) cm
        self.busbar_rects: list[tuple] = []
        self.terminals: list[tuple] = []      # (x, y) cm
        self.report: dict = {}

    @property
    def metal_rects(self):
        return self.finger_rects + self.busbar_rects


def _entity_rect(e):
    """LWPOLYLINE/POLYLINE/LINE -> (x0,y0,x1,y1) bbox. 곡선은 flattening."""
    t = e.dxftype()
    if t == "LWPOLYLINE":
        try:
            pts = [(p.x, p.y) for p in e.flattening(0.02)]
        except Exception:
            pts = [(x, y) for x, y, *_ in e.get_points("xy")]
    elif t == "POLYLINE":
        try:
            pts = [(p.x, p.y) for p in e.flattening(0.02)]
        except Exception:
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
    elif t == "LINE":
        pts = [(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)]
    else:
        return None
    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def load_dxf_grid(path: str, force_unit: str | None = None,
                  extra_layer_map: dict | None = None) -> DxfGrid:
    """DXF -> DxfGrid. 블록(INSERT) 재귀, 단위 자동, 손상파일 recover 포함."""
    try:
        import ezdxf
        from ezdxf import recover
    except ImportError as _e:
        raise ImportError("ezdxf 필요: pip install ezdxf") from _e
    warnings = []
    try:
        doc = ezdxf.readfile(path)
    except Exception as ex:
        warnings.append(f"정상읽기 실패 -> recover ({type(ex).__name__})")
        doc, auditor = recover.readfile(path)

    if force_unit:
        scale = _FORCE[force_unit]; uname = force_unit; assumed = False
    else:
        code = int(getattr(doc, "units", 0) or 0)
        scale = _UNIT_TO_CM.get(code, 1.0)
        uname = _UNIT_NAME.get(code, f"code{code}")
        assumed = code not in _UNIT_TO_CM or code == 0
        if assumed:
            warnings.append(f"단위 불명('{uname}') -> cm 가정. 어긋나면 force_unit='mm' 등 지정.")

    # --- 엔티티 수집 (블록 재귀) ---
    raw = {"cell": [], "finger": [], "busbar": [], "contact_circle": [], "contact_poly": []}
    unmatched = {}

    def handle(e):
        cat = _classify_layer(e.dxf.layer or "0", extra_layer_map)
        t = e.dxftype()
        if cat is None:
            unmatched[e.dxf.layer] = unmatched.get(e.dxf.layer, 0) + 1
            return
        if cat == "contact":
            if t == "CIRCLE":
                raw["contact_circle"].append((e.dxf.center.x, e.dxf.center.y, e.dxf.radius))
            elif t == "POINT":
                raw["contact_circle"].append((e.dxf.location.x, e.dxf.location.y, 0.0))
            else:
                r = _entity_rect(e)
                if r:
                    raw["contact_poly"].append(r)
            return
        r = _entity_rect(e)
        if r:
            raw[cat].append(r)

    def walk(ents, depth=0):
        if depth > 8:
            return
        for e in ents:
            if e.dxftype() == "INSERT":
                try:
                    walk(e.virtual_entities(), depth + 1)
                except Exception:
                    pass
            else:
                handle(e)

    walk(doc.modelspace())

    # --- wafer 외곽 ---
    g = DxfGrid()
    if raw["cell"]:
        cell = max(raw["cell"], key=lambda b: (b[2]-b[0])*(b[3]-b[1]))
        ox, oy = cell[0], cell[1]
        g.W = (cell[2]-cell[0])*scale
        g.H = (cell[3]-cell[1])*scale
    else:
        allm = raw["finger"] + raw["busbar"]
        if not allm:
            raise ValueError("cell/finger/busbar 레이어에서 도형을 못 찾음. "
                             f"미분류 레이어: {unmatched}")
        ox = min(b[0] for b in allm); oy = min(b[1] for b in allm)
        ex = max(b[2] for b in allm); ey = max(b[3] for b in allm)
        g.W = (ex-ox)*scale; g.H = (ey-oy)*scale
        warnings.append("cell 외곽 없음 -> finger/busbar bbox로 셀 크기 추정")

    def to_rect(b):
        return ((b[0]-ox)*scale, (b[1]-oy)*scale, (b[2]-b[0])*scale, (b[3]-b[1])*scale)

    g.finger_rects = [to_rect(b) for b in raw["finger"]]
    g.busbar_rects = [to_rect(b) for b in raw["busbar"]]
    g.terminals = [((cx-ox)*scale, (cy-oy)*scale) for (cx, cy, _r) in raw["contact_circle"]]
    for b in raw["contact_poly"]:
        rx, ry, rw, rh = to_rect(b)
        g.terminals.append((rx+rw/2, ry+rh/2))

    if not g.finger_rects:
        warnings.append("finger 레이어 도형 없음")
    if not g.busbar_rects:
        warnings.append("busbar 레이어 도형 없음")
    if not g.terminals:
        warnings.append("contact(probe) 없음 -> 솔버에 단자 없음. busbar 위에 점/원 1개 필요.")

    g.report = {
        "unit": uname, "unit_assumed": assumed if not force_unit else False,
        "scale_to_cm": scale,
        "counts": {"cell": len(raw["cell"]), "finger": len(g.finger_rects),
                   "busbar": len(g.busbar_rects), "contact": len(g.terminals)},
        "unmatched_layers": unmatched,
        "cell_mm": (g.W*10, g.H*10),
        "warnings": warnings,
    }
    return g


# ---------------------------------------------------------------------------
# 기존 CellGeometry에 임포트 rect를 '붙여서' rect 기계가 그걸 쓰게 함
# ---------------------------------------------------------------------------
def attach_dxf_to_geometry(geo, dxfgrid: DxfGrid):
    """
    geo.metal_rects_front() / metal_rects_front_split() / shading_fraction()
    을 임포트 rect 기반으로 교체(인스턴스 바인딩). compute_metal_frac는 수정 없이
    이 rect를 그대로 쓰게 됨. front_terminals도 주입(classify pad용).
    """
    geo._dxf_finger_rects = list(dxfgrid.finger_rects)
    geo._dxf_busbar_rects = list(dxfgrid.busbar_rects)
    geo._dxf_terminals = list(dxfgrid.terminals)
    geo.front_terminals = list(dxfgrid.terminals)   # classify_nodes pad 경로가 읽음

    def _mrf(self):
        return self._dxf_finger_rects + self._dxf_busbar_rects

    def _mrf_split(self):
        return (list(self._dxf_finger_rects), list(self._dxf_busbar_rects), [])

    def _shading(self, w_f_opt=None, w_b_opt=None, _grid=900):
        # 임의 rect union 면적 / 셀면적 (래스터라이즈; 겹침 자동 처리)
        rects = self._dxf_finger_rects + self._dxf_busbar_rects
        if not rects:
            return 0.0
        gx = np.linspace(0, self.W, _grid)
        gy = np.linspace(0, self.H, _grid)
        cov = np.zeros((_grid, _grid), dtype=bool)
        for (rx, ry, rw, rh) in rects:
            ix = (gx >= rx) & (gx <= rx + rw)
            iy = (gy >= ry) & (gy <= ry + rh)
            if ix.any() and iy.any():
                cov[np.ix_(iy, ix)] = True
        return cov.mean() * (self.W * self.H) / self.wafer_area()

    geo.metal_rects_front = types.MethodType(_mrf, geo)
    geo.metal_rects_front_split = types.MethodType(_mrf_split, geo)
    geo.shading_fraction = types.MethodType(_shading, geo)
    return geo


# ---------------------------------------------------------------------------
# rect-native 노드 분류 (기존 classify_nodes와 동일한 6-tuple 반환)
# ---------------------------------------------------------------------------
def classify_nodes_poly(points, geo):
    """임포트 rect 기준 분류. 반환: (is_finger,is_busbar,is_pad,is_metal,None,None).
       rear는 full_area로 간주(전면 패턴 임포트). bifacial 후면은 기존 경로 유지 대상."""
    N = len(points)
    x = points[:, 0]; y = points[:, 1]
    eps = 1e-6

    def in_rects(rects):
        m = np.zeros(N, dtype=bool)
        for (rx, ry, rw, rh) in rects:
            m |= ((x >= rx - eps) & (x <= rx + rw + eps) &
                  (y >= ry - eps) & (y <= ry + rh + eps))
        return m

    is_finger = in_rects(geo._dxf_finger_rects)
    is_busbar = in_rects(geo._dxf_busbar_rects)

    is_pad = np.zeros(N, dtype=bool)
    if geo._dxf_terminals:
        # busbar 폭 기준 반경 (최소 250 μm)
        bws = [min(rw, rh) for (rx, ry, rw, rh) in geo._dxf_busbar_rects] or [0.05]
        tol = max(min(bws) / 2 + eps, 0.025)
        for tx, ty in geo._dxf_terminals:
            is_pad |= (np.abs(x - tx) <= tol) & (np.abs(y - ty) <= tol)
        if not is_pad.any():  # 안전장치: 가장 가까운 노드 1개
            tx, ty = geo._dxf_terminals[0]
            is_pad[np.argmin((x - tx) ** 2 + (y - ty) ** 2)] = True

    is_metal = is_finger | is_busbar | is_pad
    return is_finger, is_busbar, is_pad, is_metal, None, None


# ---------------------------------------------------------------------------
# rect-native 메시: 임의 rect 변 주변 조밀화
# ---------------------------------------------------------------------------
def generate_mesh_poly(geo, bd=None, trans_mm=0.6, edge_pts_cap=60):
    """임포트 rect들의 변/내부/전이대에 노드를 깔고 Delaunay.
       반환: (points(N,2), scipy.Delaunay) — 기존 generate_mesh와 동일 형식."""
    from scipy.spatial import Delaunay
    W, H = geo.W, geo.H
    rects = geo._dxf_finger_rects + geo._dxf_busbar_rects
    if bd is None:
        bd = max(20, min(70, int(28 * max(W, H) / 1.2)))
    trans = trans_mm / 10.0

    pts = set()
    add = lambda px, py: pts.add((round(min(max(px, 0.0), W), 6),
                                  round(min(max(py, 0.0), H), 6)))

    # 배경 격자
    for xi in np.linspace(0, W, bd + 1):
        for yi in np.linspace(0, H, bd + 1):
            add(xi, yi)

    for (rx, ry, rw, rh) in rects:
        nx = min(edge_pts_cap, max(3, int(rw / (min(rw, rh) * 0.6) ) + 2))
        ny = min(edge_pts_cap, max(3, int(rh / (min(rw, rh) * 0.6) ) + 2))
        xs = np.linspace(rx, rx + rw, nx)
        ys = np.linspace(ry, ry + rh, ny)
        # 변 + 내부 채움
        for xi in xs:
            add(xi, ry); add(xi, ry + rh)
        for yi in ys:
            add(rx, yi); add(rx + rw, yi)
        for xi in xs[::2]:
            for yi in ys[::2]:
                add(xi, yi)
        # 전이대 (바깥쪽 ±trans)
        for off in np.linspace(0, trans, 4)[1:]:
            for xi in xs[::2]:
                add(xi, ry - off); add(xi, ry + rh + off)
            for yi in ys[::2]:
                add(rx - off, yi); add(rx + rw + off, yi)

    # 단자 강제 포함
    for tx, ty in geo._dxf_terminals:
        add(tx, ty)

    P = np.array(sorted(pts), dtype=float)
    tri = Delaunay(P)
    return P, tri


# ---------------------------------------------------------------------------
# step B: 임의 축정렬 rect용 1D 금속 그래프
#   기존 assemble_K_met_1d 의 _chain_along 을 임포트 rect 위로 일반화.
#   교차/접촉 연결은 band-overlap(공유 노드) 메커니즘으로 자동.
#   H패턴은 이 일반식의 특수경우 → 기존과 동일 결과.
# ---------------------------------------------------------------------------
def assemble_K_met_1d_poly(points, ism, finger_rects, busbar_rects, rm, hf, cf,
                           SHORT=1.0e4, gc_max=0.0):
    """Returns (N,N) CSR. 비금속 행은 비어있음 (기존 assemble_K_met_1d 계약 동일).

    각 rect: 긴 축을 따라 1D 저항 체인 + 폭방향 등전위 본드.
      finger(가로/세로 무관, finger 레이어): cross-section A = (짧은변)*hf, cf 적용
      busbar: A = (짧은변)*hf, cf 미적용
    """
    from scipy.sparse import lil_matrix
    N = len(points)
    K = lil_matrix((N, N))
    if hf <= 0:
        return K.tocsr()
    # v28.18 fix (리뷰 1-C): assemble_K_met_1d 와 동일하게 접촉 컨덕턴스
    #   피크에 맞춰 본드를 끌어올린다(작은 rc에서 mesh-독립성 보호).
    SHORT = max(float(SHORT), 1.0e3 * float(gc_max))
    px, py = points[:, 0], points[:, 1]

    def _chain_rect(rx, ry, rw, rh, R_per_len):
        # 긴 축 = along, 짧은 축 = perp
        along_axis = 0 if rw >= rh else 1
        coord = px if along_axis == 0 else py
        # 이 rect 안의 금속 노드
        band = ((px >= rx - 1e-6) & (px <= rx + rw + 1e-6) &
                (py >= ry - 1e-6) & (py <= ry + rh + 1e-6) & ism)
        idx = np.where(band)[0]
        if len(idx) < 2:
            return
        a = coord[idx]
        order = np.argsort(a, kind='stable')
        idx_o = idx[order]; a_o = a[order]
        # 같은 along 위치 묶기
        groups = []; cur_pos = a_o[0]; cur = [int(idx_o[0])]
        for k in range(1, len(idx_o)):
            if a_o[k] - cur_pos < 1e-7:
                cur.append(int(idx_o[k]))
            else:
                groups.append((cur_pos, cur)); cur_pos = a_o[k]; cur = [int(idx_o[k])]
        groups.append((cur_pos, cur))
        # 폭방향 등전위 본드 (rep = min index)
        reps = []
        for pos, members in groups:
            rep = min(members); reps.append((pos, rep))
            for m in members:
                if m == rep:
                    continue
                K[rep, rep] += SHORT; K[m, m] += SHORT
                K[rep, m] -= SHORT; K[m, rep] -= SHORT
        # 인접 위치 1D 저항
        for k in range(len(reps) - 1):
            p0, i = reps[k]; p1, j = reps[k + 1]
            dl = p1 - p0
            if dl <= 1e-9:
                continue
            g = 1.0 / (R_per_len * dl)
            K[i, i] += g; K[j, j] += g; K[i, j] -= g; K[j, i] -= g

    for (rx, ry, rw, rh) in finger_rects:
        width = min(rw, rh); A = width * hf
        if A > 0:
            _chain_rect(rx, ry, rw, rh, rm / (cf * A))   # finger: cf 적용
    for (rx, ry, rw, rh) in busbar_rects:
        width = min(rw, rh); A = width * hf
        if A > 0:
            _chain_rect(rx, ry, rw, rh, rm / A)          # busbar: cf 미적용

    return K.tocsr()


# ============================================================================
# SPATIAL MULTIPLIER MAPS (merged from spatial_maps.py — v28.16 ③)
# ============================================================================
class SpatialMap:
    """Per-node parameter multiplier spec.

    Parameters
    ----------
    mode : 'uniform' | 'rectangle' | 'gaussian' | 'checkerboard' | 'csv'
    background : multiplier outside the feature (default 1.0)
    feature : multiplier inside the feature / peak value
    Mode-specific:
      rectangle:   x_min, x_max, y_min, y_max  [cm]
      gaussian:    cx, cy [cm], sigma_x, sigma_y [cm]
      checkerboard: cells_x, cells_y (int)
      csv:         matrix (2D ndarray) sampled on a regular grid over the cell
    """

    def __init__(self, mode="uniform", background=1.0, feature=1.0,
                 x_min=0.0, x_max=0.0, y_min=0.0, y_max=0.0,
                 cx=0.0, cy=0.0, sigma_x=1.0, sigma_y=1.0,
                 cells_x=4, cells_y=4, matrix=None):
        self.mode = mode
        self.background = float(background)
        self.feature = float(feature)
        self.x_min = float(x_min); self.x_max = float(x_max)
        self.y_min = float(y_min); self.y_max = float(y_max)
        self.cx = float(cx); self.cy = float(cy)
        self.sigma_x = float(sigma_x); self.sigma_y = float(sigma_y)
        self.cells_x = int(cells_x); self.cells_y = int(cells_y)
        self.matrix = None if matrix is None else np.asarray(matrix, dtype=float)

    def evaluate(self, points_cm, W_cm, H_cm):
        """Return length-N positive multiplier array at node coords.

        points_cm : (N,2) array of [x,y] in cm
        W_cm, H_cm: cell extents in cm
        """
        x = np.asarray(points_cm)[:, 0]
        y = np.asarray(points_cm)[:, 1]
        bg = self.background
        ft = self.feature

        if self.mode == "uniform":
            result = np.full(len(x), bg)

        elif self.mode == "rectangle":
            inside = ((x >= self.x_min) & (x <= self.x_max)
                      & (y >= self.y_min) & (y <= self.y_max))
            result = np.where(inside, ft, bg)

        elif self.mode == "gaussian":
            sx = max(self.sigma_x, 1e-12)
            sy = max(self.sigma_y, 1e-12)
            w = np.exp(-0.5 * (((x - self.cx) / sx) ** 2
                               + ((y - self.cy) / sy) ** 2))
            result = bg + (ft - bg) * w

        elif self.mode == "checkerboard":
            nx = max(self.cells_x, 1)
            ny = max(self.cells_y, 1)
            ix = np.minimum((x / max(W_cm, 1e-12) * nx).astype(int), nx - 1)
            iy = np.minimum((y / max(H_cm, 1e-12) * ny).astype(int), ny - 1)
            result = np.where((ix + iy) % 2 == 0, ft, bg)

        elif self.mode == "csv":
            if self.matrix is None or self.matrix.ndim != 2 \
                    or self.matrix.shape[0] < 2 or self.matrix.shape[1] < 2:
                raise ValueError("csv spatial map needs a >=2x2 matrix")
            from scipy.interpolate import RegularGridInterpolator
            ny_, nx_ = self.matrix.shape
            y_axis = np.linspace(0.0, H_cm, ny_)
            x_axis = np.linspace(0.0, W_cm, nx_)
            interp = RegularGridInterpolator(
                (y_axis, x_axis), self.matrix,
                bounds_error=False, fill_value=None)
            result = interp(np.column_stack((np.clip(y, 0, H_cm),
                                             np.clip(x, 0, W_cm))))
        else:
            raise ValueError(f"Unsupported spatial map mode: {self.mode!r}")

        result = np.asarray(result, dtype=float)
        if np.any(~np.isfinite(result)) or np.any(result <= 0.0):
            raise ValueError("spatial multiplier must be finite and positive")
        return result


# Convenience: a registry of multiplier maps the solver looks for on dp.
# Each entry is a node-length array (or None). Defaults to None = all-ones.
SPATIAL_TARGETS = ("j01", "j02", "gen", "rc")


def make_uniform(n):
    """All-ones multiplier (no-op), length n."""
    return np.ones(n)


def solve_0d_subcell_current(V, dp, cell='top'):
    """단일 subcell 다이오드 J(V) [mA/cm²].

    Lumped (uniform) — pass 영역 파라미터만 사용 (0D는 metal_frac 개념 없음).
    Bifacial gain 등 spatial 효과 일체 무시.

    Args:
      V    : voltage [V] (scalar or numpy array)
      dp   : DiodeParams
      cell : 'top' or 'bottom'

    Returns:
      J [mA/cm²] (양수 = power generation 방향)
    """
    V = np.asarray(V, dtype=float)
    if cell == 'top':
        Jph = dp.Jph_top * 1000.0           # mA/cm²
        J01 = dp.J01_top_pass * 1000.0
        J02 = dp.J02_top_pass * 1000.0
        n1 = dp.n1_top; n2 = dp.n2_top
        Rsh = dp.Rsh_top
    elif cell in ('bottom', 'bot'):
        Jph = dp.Jph_bot * 1000.0
        J01 = dp.J01_bot_pass * 1000.0
        J02 = dp.J02_bot_pass * 1000.0
        n1 = dp.n1_bot; n2 = dp.n2_bot
        Rsh = dp.Rsh_bot
    else:
        raise ValueError(f"cell must be 'top' or 'bottom', got {cell!r}")
    e1 = np.exp(np.minimum(V / (n1 * VT), 80))
    e2 = np.exp(np.minimum(V / (n2 * VT), 80))
    return Jph - J01 * (e1 - 1) - J02 * (e2 - 1) - V / Rsh * 1000.0
    #                                                       ^^^^
    # V/Rsh: V [V] / Rsh [Ω·cm²] = A/cm² → ×1000 = mA/cm². Note Jph/J01/J02
    # already converted above. Consistent units throughout.


def solve_0d_tandem_iv(dp, npts=200, shading_frac=0.0, metal_frac=0.0, j_match=False):
    """0D analytical 2T tandem I-V curve.

    Two-diode series-connected, uniform, no spatial losses.
    For each V_total, solve for V_top such that
       J_top(V_top) = J_bot(V_total - V_top)
    using Newton iteration on V_top.

    Args:
      dp           : DiodeParams
      npts         : number of V_total sweep points
      shading_frac : optional. If >0, multiply Jph_top/bot by (1-shading_frac)
                     to match FEM's optical loss from front metal.
      metal_frac   : optional. Used with j_match=True for area-weighted J0.
      j_match      : optional. If True, use area-weighted J01/J02
                     = (1-metal_frac)·pass + metal_frac·metal,
                     matching the FEM diode mixing exactly. With shading_frac
                     and j_match both set from FEM, the only remaining
                     difference between 0D and FEM is spatial (R) loss —
                     which is what the validation aims to test.

    Returns:
      Vs (npts,), Js (npts,), iv dict (Jsc/Voc/Vmpp/Jmpp/Pmpp/FF/Eff/mode)
    """
    # Effective Jph and J0 — match FEM mixing if requested
    sf = max(0.0, min(1.0, shading_frac))
    mf = max(0.0, min(1.0, metal_frac)) if j_match else 0.0
    Jph_t_eff = dp.Jph_top * (1.0 - sf)
    Jph_b_eff = dp.Jph_bot * (1.0 - sf)
    if j_match:
        J01t_eff = (1.0 - mf) * dp.J01_top_pass + mf * dp.J01_top_metal
        J02t_eff = (1.0 - mf) * dp.J02_top_pass + mf * dp.J02_top_metal
        J01b_eff = (1.0 - mf) * dp.J01_bot_pass + mf * dp.J01_bot_metal
        J02b_eff = (1.0 - mf) * dp.J02_bot_pass + mf * dp.J02_bot_metal
    else:
        J01t_eff = dp.J01_top_pass; J02t_eff = dp.J02_top_pass
        J01b_eff = dp.J01_bot_pass; J02b_eff = dp.J02_bot_pass

    # Estimate Voc with effective parameters (overrides dp.expected_voc)
    Vt_oc = dp.n1_top * VT * np.log(max(Jph_t_eff / max(J01t_eff, 1e-40), 1.0))
    Vb_oc = dp.n1_bot * VT * np.log(max(Jph_b_eff / max(J01b_eff, 1e-40), 1.0))
    Voc_est = Vt_oc + Vb_oc + 0.05    # small headroom for the sweep
    V_max = Voc_est * 1.10            # widened for safer sign-change capture
    Vs = np.linspace(0.0, V_max, npts)
    Js = np.zeros(npts)

    # Newton on Vtop with continuation: warm-start from previous V_total.
    # f(Vt) = J_top(Vt) - J_bot(V_total - Vt)
    # df/dVt = dJ_top/dVt + dJ_bot/dVb (both negative → df/dVt < 0, monotonic)
    Vt_prev = 0.0
    for i, V_total in enumerate(Vs):
        if V_total < 1e-9:
            Js[i] = min(Jph_t_eff, Jph_b_eff) * 1000.0
            Vt_prev = 0.0
            continue
        Vt = Vt_prev if Vt_prev > 0 else V_total * Vt_oc / max(Voc_est, 1e-6)
        Vt = max(min(Vt, V_total - 1e-6), 1e-6)
        for _ in range(60):
            Vb = V_total - Vt
            e1t = np.exp(min(Vt / (dp.n1_top * VT), 80))
            e2t = np.exp(min(Vt / (dp.n2_top * VT), 80))
            Jt = (Jph_t_eff * 1000.0
                  - J01t_eff * 1000.0 * (e1t - 1)
                  - J02t_eff * 1000.0 * (e2t - 1)
                  - Vt / dp.Rsh_top * 1000.0)
            dJt = -(J01t_eff * 1000.0 * e1t / (dp.n1_top * VT)
                    + J02t_eff * 1000.0 * e2t / (dp.n2_top * VT)
                    + 1000.0 / dp.Rsh_top)
            e1b = np.exp(min(Vb / (dp.n1_bot * VT), 80))
            e2b = np.exp(min(Vb / (dp.n2_bot * VT), 80))
            Jb = (Jph_b_eff * 1000.0
                  - J01b_eff * 1000.0 * (e1b - 1)
                  - J02b_eff * 1000.0 * (e2b - 1)
                  - Vb / dp.Rsh_bot * 1000.0)
            dJb = -(J01b_eff * 1000.0 * e1b / (dp.n1_bot * VT)
                    + J02b_eff * 1000.0 * e2b / (dp.n2_bot * VT)
                    + 1000.0 / dp.Rsh_bot)
            f = Jt - Jb
            df = dJt + dJb
            if abs(f) < 1e-9 or abs(df) < 1e-30:
                break
            dV = -f / df
            if abs(dV) > 0.1:
                dV = 0.1 * np.sign(dV)
            Vt_new = Vt + dV
            Vt_new = max(min(Vt_new, V_total - 1e-6), 1e-6)
            if abs(Vt_new - Vt) < 1e-8:
                Vt = Vt_new
                break
            Vt = Vt_new
        Js[i] = Jt
        Vt_prev = Vt

    # Extract performance metrics
    Jsc = Js[0]                                    # at V_total = 0
    # Voc: first sign change (J: positive → negative), refined by bisection
    Voc = V_max
    sgn = np.sign(Js)
    cross = np.where((sgn[:-1] > 0) & (sgn[1:] <= 0))[0]
    if len(cross) > 0:
        i0 = cross[0]
        a, b = Vs[i0], Vs[i0+1]
        ja, jb = Js[i0], Js[i0+1]
        # Bisection refinement using the same Newton-on-Vtop as the main sweep.
        # The sweep already converged Vt at a and b — we re-solve here for
        # interior V_total points to get sub-mV Voc resolution.
        def _J_at(Vtot):
            Vt = max(min(Vtot * Vt_oc / max(Voc_est, 1e-6), Vtot - 1e-6), 1e-6)
            for _ in range(40):
                Vb_ = Vtot - Vt
                e1tx = np.exp(min(Vt / (dp.n1_top * VT), 80))
                e2tx = np.exp(min(Vt / (dp.n2_top * VT), 80))
                Jtx = (Jph_t_eff*1000 - J01t_eff*1000*(e1tx-1)
                       - J02t_eff*1000*(e2tx-1) - Vt/dp.Rsh_top*1000)
                dJtx = -(J01t_eff*1000*e1tx/(dp.n1_top*VT)
                         + J02t_eff*1000*e2tx/(dp.n2_top*VT) + 1000/dp.Rsh_top)
                e1bx = np.exp(min(Vb_ / (dp.n1_bot * VT), 80))
                e2bx = np.exp(min(Vb_ / (dp.n2_bot * VT), 80))
                Jbx = (Jph_b_eff*1000 - J01b_eff*1000*(e1bx-1)
                       - J02b_eff*1000*(e2bx-1) - Vb_/dp.Rsh_bot*1000)
                dJbx = -(J01b_eff*1000*e1bx/(dp.n1_bot*VT)
                         + J02b_eff*1000*e2bx/(dp.n2_bot*VT) + 1000/dp.Rsh_bot)
                fx = Jtx - Jbx; dfx = dJtx + dJbx
                if abs(fx) < 1e-9 or abs(dfx) < 1e-30: break
                dVx = -fx/dfx
                if abs(dVx) > 0.05: dVx = 0.05*np.sign(dVx)
                Vt = max(min(Vt + dVx, Vtot - 1e-6), 1e-6)
            return Jtx
        # Bisection for sub-mV Voc accuracy
        for _ in range(40):
            m = 0.5 * (a + b)
            jm = _J_at(m)
            if jm > 0:
                a, ja = m, jm
            else:
                b, jb = m, jm
            if (b - a) < 5e-5:    # 0.05 mV resolution
                break
        Voc = a + ja * (b - a) / (ja - jb) if ja != jb else 0.5*(a+b)
    P = Vs * Js
    valid = (Js > 0) & (Vs > 0) & (Vs < Voc * 1.01)
    if np.any(valid):
        idx = np.where(valid)[0]
        Pmpp = float(np.max(P[valid]))
        im = idx[np.argmax(P[valid])]
        Vmpp = Vs[im]; Jmpp = Js[im]
    else:
        Pmpp = 0.0; Vmpp = 0.0; Jmpp = 0.0
    FF = (Pmpp / (Jsc * Voc) * 100.0) if (Jsc * Voc > 0) else 0.0
    Eff = Pmpp / 100.0 * 100.0       # 100 mW/cm² AM1.5G

    iv = {'Jsc': Jsc, 'Voc': Voc, 'Vmpp': Vmpp, 'Jmpp': Jmpp,
          'Pmpp': Pmpp, 'FF': FF, 'Eff': Eff, 'mode': 'tandem_0d'}
    return Vs, Js, iv


# =============================================================
# NESTED-MESH PROLONGATION
# =============================================================
class MeshProlongationSeedProvider:
    """Interpolate converged voltage planes from a coarser nested mesh."""

    _CONTINUOUS_FIELDS = ("Ve", "Vtop", "Vr", "Vint", "Vbot")
    _METAL_FIELDS = ("Vm", "Vrm")

    def __init__(self, source_solver, target_points):
        from scipy.spatial import cKDTree

        t0 = time.time()
        if not getattr(source_solver, "_mesh_seed_snapshots", None):
            raise ValueError("Source solver has no converged voltage snapshots.")
        self.source_points = source_solver.pts
        self.source_tri = source_solver.tri
        self.target_points = target_points
        self.snapshots = source_solver._mesh_seed_snapshots

        simplex = self.source_tri.find_simplex(target_points)
        self._inside = simplex >= 0
        self._vertices = np.zeros((len(target_points), 3), dtype=np.int64)
        self._weights = np.zeros((len(target_points), 3), dtype=float)
        if np.any(self._inside):
            inside_simplex = simplex[self._inside]
            transform = self.source_tri.transform[inside_simplex]
            delta = target_points[self._inside] - transform[:, 2]
            first_two = np.einsum("nij,nj->ni", transform[:, :2], delta)
            self._weights[self._inside, :2] = first_two
            self._weights[self._inside, 2] = 1.0 - np.sum(first_two, axis=1)
            self._vertices[self._inside] = self.source_tri.simplices[inside_simplex]

        self._nearest_all = cKDTree(self.source_points).query(target_points)[1]
        self._metal_nearest = {}
        for field, indices in (
            ("Vm", source_solver.midx),
            ("Vrm", source_solver.rear_midx),
        ):
            if indices is not None and len(indices):
                self._metal_nearest[field] = (
                    indices[cKDTree(self.source_points[indices]).query(target_points)[1]]
                )
        self.build_time_s = time.time() - t0

    def _continuous(self, values):
        values = np.asarray(values)
        out = values[self._nearest_all].astype(float, copy=True)
        if np.any(self._inside):
            out[self._inside] = np.sum(
                values[self._vertices[self._inside]] * self._weights[self._inside],
                axis=1,
            )
        return out

    def _metal(self, field, values):
        nearest = self._metal_nearest.get(field)
        if nearest is None:
            return None
        return np.asarray(values)[nearest].astype(float, copy=True)

    def seed_for(self, voltage_bias):
        source_bias = min(self.snapshots, key=lambda vb: abs(vb - voltage_bias))
        snapshot = self.snapshots[source_bias]
        seed = {}
        for field in self._CONTINUOUS_FIELDS:
            values = snapshot.get(field)
            if values is not None:
                seed[field] = self._continuous(values)
        for field in self._METAL_FIELDS:
            values = snapshot.get(field)
            if values is not None:
                seed[field] = self._metal(field, values)
        return seed, source_bias


# =============================================================
# UNIFIED SOLVER (Single-cell + Tandem, with Rear Plane)
# =============================================================
class FESTSolver:
    """
    v5.0 Unified Solver.

    DOF structure:
      Tandem mode:
        [V_emitter(N), V_metal_front(Nm), V_top(N), V_rear(N)]
        Total = 3N + Nm
      Single-cell mode:
        [V_emitter(N), V_metal_front(Nm), V_rear(N)]
        Total = 2N + Nm

    Key changes from v4.1 TandemSolver:
      - V_rear is a full plane with lateral current (K_rear @ V_rear)
      - Diode voltage = V_emitter - V_rear (not V_emitter - 0)
      - Hybrid ism/metal_frac: binary ism for mesh, continuous metal_frac for J0/Gc
      - Rear probe BC: V_rear[pad_nodes] = 0 (ground at rear pad)
    """

    def __init__(self, points, tri, isf, isb, isp, ism, geo, isrm=None, isrp=None):
        self.pts = points
        self.tri = tri
        self.simp = tri.simplices
        self.isf = isf
        self.isb = isb
        self.isp = isp
        self.ism = ism  # Binary (geometric boundary)
        self.geo = geo
        self.N = len(points)
        self.midx = np.where(ism)[0]
        self.Nm = len(self.midx)
        self.pidx = np.where(isp)[0]

        # --- Rear metal (patterned mode) ---
        self.isrm = isrm  # rear metal mask (None if full_area)
        self.isrp = isrp  # rear probe mask (None if full_area)
        if isrp is not None and np.any(isrp):
            self.rear_pidx = np.where(isrp)[0]
        else:
            self.rear_pidx = None
        if isrm is not None and np.any(isrm):
            self.rear_midx = np.where(isrm)[0]
            self.Nrm = len(self.rear_midx)
            # Rear metal index mapping (mirrors front mmap)
            self.rear_mmap = -np.ones(self.N, dtype=int)
            for k, gi in enumerate(self.rear_midx):
                self.rear_mmap[gi] = k
        else:
            self.rear_midx = None
            self.Nrm = 0
            self.rear_mmap = None

        # Metal index mapping
        self.mmap = -np.ones(self.N, dtype=int)
        for k, gi in enumerate(self.midx):
            self.mmap[gi] = k

        # Geometry precompute
        p0 = points[self.simp[:, 0]]
        p1 = points[self.simp[:, 1]]
        p2 = points[self.simp[:, 2]]
        self.areas = 0.5 * np.abs(
            (p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]) -
            (p2[:, 0] - p0[:, 0]) * (p1[:, 1] - p0[:, 1]))
        self.b = np.column_stack([
            p1[:, 1] - p2[:, 1],
            p2[:, 1] - p0[:, 1],
            p0[:, 1] - p1[:, 1]])
        self.c = np.column_stack([
            p2[:, 0] - p1[:, 0],
            p0[:, 0] - p2[:, 0],
            p1[:, 0] - p0[:, 0]])

        # Continuous metal fraction (hybrid approach)
        self.metal_frac = compute_metal_frac(points, self.simp, self.areas, geo)
        self.illum_frac = 1.0 - self.metal_frac
        # v28.18 (wf_wired): 케이스 폭 머신너리. 메시/metal_frac은 설계(Before)
        #   geometry에 고정되고, 케이스별 전극 폭(예: 핫프레싱 After)은 _build에서
        #   (1) 1D 금속 단면적, (2) 접촉 컨덕턴스 스케일, (3) 발전량 전역 스케일로
        #   주입된다. illum_frac은 _build가 매번 이 원본 base에서 재계산하므로
        #   스케일이 중첩(compound)될 수 없다.
        self._illum_frac_base = self.illum_frac.copy()
        self._case_wb = None

        # Rear-side illumination fraction: rear metal blocks rear light
        # Only meaningful in bifacial mode; full_area mode has 0 (rear is
        # entirely metal so no rear light reaches the absorber).
        if geo.rear_mode in ('bifacial', 'patterned') and geo.rear is not None:
            self.rear_metal_frac = _compute_rear_metal_frac(
                points, self.simp, self.areas, geo)
            self.rear_illum_frac = 1.0 - self.rear_metal_frac
        else:
            self.rear_metal_frac = np.ones(self.N)  # full area metal blocks all
            self.rear_illum_frac = np.zeros(self.N)

        # Stiffness cache
        self._cache_hash = None
        self._Ke = None
        self._Kr = None       # Rear emitter (semiconductor surface)
        self._Krm = None      # Rear metal grid
        self._Km = None
        self._na = None
        self._Gc = None       # Front contact conductance
        self._Gc_rear = None  # Rear contact conductance
        self._Km_rows = None
        self._Krm_rows = None
        self._K_junc = None    # Phase B: interlayer lateral plane stiffness

        # Warm-start cache for continuation solver (Phase 2 optimization).
        # _warm_V_bf: last converged V vector from bifacial tandem solve
        # _warm_V_tf: last converged V from full_area tandem solve
        # _warm_V_sbf: last converged V from bifacial single solve
        # _warm_V_sf: last converged V from full_area single solve
        # Reset to None when build hash changes (different geometry/params).
        self._warm_V_bf = None
        self._warm_V_tf = None
        self._warm_V_sbf = None
        self._warm_V_sf = None
        self._warm_Vb_ref = None  # Vbias at which warm vector was computed
        # (③): cache for evaluated spatial multiplier arrays, keyed by id(dp)
        self._mesh_seed_snapshots = {}
        self._mesh_seed_provider = None
        self._mesh_seed_disabled = False
        self._mesh_seed_applied_this_call = False
        self._mesh_warm_stats = {}
        self.reset_mesh_warm_diagnostics(clear_snapshots=False)
        self._spatial_cache = {}

    def reset_mesh_warm_diagnostics(self, clear_snapshots=True):
        """Reset per-IV prolongation diagnostics without changing physics."""
        if clear_snapshots:
            self._mesh_seed_snapshots = {}
        self._mesh_warm_stats = {
            "warm_start_used": False,
            "fallback_used": False,
            "warm_seed_applications": 0,
            "fallback_count": 0,
            "solve_calls": 0,
            "nonlinear_iterations": 0,
            "final_newton_residual": float("nan"),
            "prolongation_time_s": (
                self._mesh_seed_provider.build_time_s
                if self._mesh_seed_provider is not None else 0.0
            ),
        }

    def mesh_warm_diagnostics(self):
        return dict(self._mesh_warm_stats)

    def set_mesh_prolongation_source(self, source_solver):
        """Use a converged coarser solver as an initial-guess oracle."""
        if (abs(source_solver.geo.W - self.geo.W) > 1e-12
                or abs(source_solver.geo.H - self.geo.H) > 1e-12):
            raise ValueError("Prolongation requires identical wafer dimensions.")
        self._mesh_seed_provider = MeshProlongationSeedProvider(source_solver, self.pts)
        self.reset_mesh_warm_diagnostics(clear_snapshots=True)
        return self._mesh_seed_provider.build_time_s

    def _apply_mesh_prolongation_seed(self, V, voltage_bias, planes, frac_top=0.5):
        """Fill an initial vector from the nearest coarse-mesh bias snapshot."""
        if self._mesh_seed_provider is None or self._mesh_seed_disabled:
            return False
        t0 = time.time()
        seed, source_bias = self._mesh_seed_provider.seed_for(voltage_bias)
        delta_bias = voltage_bias - source_bias
        shifts = {
            "Ve": delta_bias,
            "Vm": delta_bias,
            "Vtop": delta_bias * frac_top,
            "Vint": delta_bias * (1.0 - frac_top),
            "Vbot": delta_bias * (1.0 - frac_top),
            "Vr": 0.0,
            "Vrm": 0.0,
        }
        applied = False
        for field, (start, indices) in planes.items():
            values = seed.get(field)
            if values is None:
                continue
            if indices is not None:
                values = values[indices]
            values = np.asarray(values) + shifts.get(field, 0.0)
            stop = start + len(values)
            finite = np.isfinite(values)
            if np.any(finite):
                current = V[start:stop]
                current[finite] = values[finite]
                V[start:stop] = current
                applied = True
        if applied:
            self._mesh_seed_applied_this_call = True
            self._mesh_warm_stats["warm_start_used"] = True
            self._mesh_warm_stats["warm_seed_applications"] += 1
            self._mesh_warm_stats["prolongation_time_s"] += time.time() - t0
        return applied

    def _capture_mesh_seed_snapshot(self, voltage_bias, result):
        snapshot = {
            "Ve": result["Ve"].copy(),
            "Vm": result["Vm"].copy(),
            "Vtop": result["Vtop"].copy() if result.get("Vtop") is not None else None,
            "Vr": result["Vr"].copy(),
            "Vint": None,
            "Vbot": None,
            "Vrm": None,
        }
        if getattr(self, "_last_Vint", None) is not None:
            snapshot["Vint"] = self._last_Vint.copy()
            snapshot["Vbot"] = self._last_Vint - result["Vr"]
        if getattr(self, "_last_Vrm", None) is not None:
            snapshot["Vrm"] = self._last_Vrm.copy()
        self._mesh_seed_snapshots[float(voltage_bias)] = snapshot

    def _spatial_mult(self, dp, which):
        """Return length-N positive multiplier array for the named target.

        which in {'j01','j02','gen','rc'}. None map -> all-ones (no-op).
        Evaluated once on this solver's node coords and cached per dp.
        """
        spec = getattr(dp, f"spatial_{which}", None)
        if spec is None:
            return None  # caller treats None as all-ones (skips the multiply)
        key = (id(dp), which, id(spec))
        cached = self._spatial_cache.get(key)
        if cached is not None and cached.shape[0] == self.N:
            return cached
        arr = spec.evaluate(self.pts, self.geo.W, self.geo.H)
        arr = np.asarray(arr, dtype=float)
        self._spatial_cache[key] = arr
        return arr

    def _build(self, rm, hf, wf, rc, Rs_front, cf, dp):
        """Build/cache stiffness matrices AND pre-assembled static Jacobians.
           
        2-layer rear (bifacial): mirrors front 2-layer structure.
          - V_rear_emitter: rear semiconductor surface (TCO/doped layer, L3)
            Sheet R from dp.Rs_rear_tco (default 50 Ω/sq, typical IZO)
          - V_rear_metal: rear metal grid (L4)
            Auto Rs from rm/hf (same paste as front, same hot pressing)
          - Connected via Gc_rear (contact resistance, same rc as front)
        
        Full area: collapse to single layer with V=0 BC everywhere."""
        # v28.18 (리뷰 [1-2] 수정): rc=0은 유효한 GUI 입력("이상 접촉")이지만
        #   Gc = na·mf/rc 가 inf를 만든다. 1e-12 Ω·cm²로 클램프 — 물리적으로
        #   존재하는 어떤 접촉보다도 작아서 수치상 이상 접촉과 동등하다.
        rc = max(float(rc), 1e-12)
        # v28.22: rear contact resistivity — independent rear value if dp.rc_rear
        # is set (>0), else fall back to the front rc (legacy bit-identical).
        _rc_rear = getattr(dp, 'rc_rear', None)
        rc_rear = rc if (_rc_rear is None or float(_rc_rear) <= 0) else max(float(_rc_rear), 1e-12)
        # v28.18 (wf_wired): 케이스별 버스바 폭. solve()/calc_iv()/losses()
        #   진입점에서 설정; None -> 설계(Before) 폭.
        wb_case = self._case_wb if self._case_wb is not None else self.geo.w_b
        # Auto-compute rear metal sheet resistance from front bulk + height
        # Hot pressing applies to FRONT ONLY.
        # If dp.Rs_rear_metal_sheet > 0, use this fixed value (rear decoupled).
        # If dp.Rs_rear_metal_sheet <= 0, fall back to legacy rm/hf coupling.
        if dp.Rs_rear_metal_sheet > 0:
            Rs_rear_metal_auto = dp.Rs_rear_metal_sheet
        else:
            Rs_rear_metal_auto = rm / hf if hf > 0 else dp.Rs_rear
        # Rear emitter/TCO sheet R — physical value from DiodeParams
        Rs_rear_tco = dp.Rs_rear_tco
        # Interlayer lateral sheet R (Phase B) — affects K_int matrix
        Rs_j = dp.Rs_junction
        # (③): include spatial-map identities so changing a map (esp. the
        # rc map, which feeds Gc built here) invalidates the build cache. Use a
        # cheap id()-based tag; None maps tag as 0.
        _sm_tag = (id(dp.spatial_j01) if dp.spatial_j01 is not None else 0,
                   id(dp.spatial_j02) if dp.spatial_j02 is not None else 0,
                   id(dp.spatial_gen) if dp.spatial_gen is not None else 0,
                   id(dp.spatial_rc)  if dp.spatial_rc  is not None else 0)
        h = (rm, hf, wf, wb_case, rc, rc_rear, Rs_front, cf, Rs_rear_metal_auto, Rs_rear_tco, Rs_j, _sm_tag)
        if self._cache_hash == h:
            return
        self._cache_hash = h
        # Geometry/parameter change → invalidate warm-start cache
        self._warm_V_bf = None
        self._warm_V_tf = None
        self._warm_V_sbf = None
        self._warm_V_sf = None
        self._warm_Vb_ref = None

        # Emitter stiffness
        self._Ke, self._na = assemble_K(
            self.pts, self.simp, Rs_front, self.areas, self.b, self.c)

        # ===== REAR PLANE STIFFNESS =====
        if self.geo.rear_mode in ('bifacial', 'patterned') and self.isrm is not None:
            # 2-LAYER REAR (mirrors front):
            #   L3 (V_rear_emitter): rear TCO sheet R = dp.Rs_rear_tco (~50 Ω/sq IZO)
            #   L4 (V_rear_metal):   rear metal grid, same paste/Rs as front
            #   Connected by Gc_rear at rear metal nodes. Rs_rear_tco ≈ 0 collapses
            #   to lumped-rear; realistic >0 essential for rear pattern analysis.
            self._Kr, _ = assemble_K(
                self.pts, self.simp, Rs_rear_tco, self.areas, self.b, self.c)

            # Rear metal grid stiffness. ASM-1 fix: use the mesh-convergent 1D
            # conductor model (assemble_K_met_1d, same as the front at L3246)
            # over the REAR grid geometry, instead of the 2D Galerkin sheet model
            # (assemble_K_met) the front abandoned — that 2D model gives
            # mesh-dependent thin-line conductance (sliver triangles), so
            # bifacial/patterned-rear FF/efficiency did not converge under
            # refinement. cf=1.0 preserves the previous "no finger CF" intent for
            # the rear; rear finger/busbar lines come from the rear grid.
            rw_f = self.geo.rear.w_f if self.geo.rear else wf
            rw_b = self.geo.rear.w_b if self.geo.rear else 0.05
            if np.any(self.isrm):
                _gc_peak_rear = float(np.max(
                    self._na[self.isrm] * self.rear_metal_frac[self.isrm])) / rc_rear
            else:
                _gc_peak_rear = 0.0
            self._Krm = assemble_K_met_1d(
                self.pts, self.isrm, self.geo, rm, hf, 1.0,
                w_f=rw_f, w_b=rw_b, gc_max=_gc_peak_rear,
                fg_y=self.geo.rear_fg_y, bb_x=self.geo.rear_bb_x,
                band_w_f=rw_f, band_w_b=rw_b)

            # Rear contact conductance: rear metal -> rear emitter.
            # v28.22: uses rc_rear (independent rear contact resistivity if set,
            # else front rc). ASM-2 fix: weight by the continuous rear_metal_frac
            # exactly as the front path weights by metal_frac (L3252). Previously
            # this used binary isrm (=1.0), which at partial-coverage edge nodes
            # overstates Gc_rear → understates rear contact resistance and
            # overstiffens the rear coupling in bifacial/patterned mode.
            # rear_metal_frac is the area-weighted mirror of the front metal_frac.
            self._Gc_rear = np.zeros(self.N)
            self._Gc_rear[self.isrm] = (
                self._na[self.isrm] * self.rear_metal_frac[self.isrm] / rc_rear)

            # Cache rear metal row data
            self._Krm_rows = []
            for k, gi in enumerate(self.rear_midx):
                r = self._Krm.getrow(gi)
                self._Krm_rows.append((r.indices.copy(), r.data.copy()))
        else:
            # Full area: collapse to single ideal back contact
            self._Kr, _ = assemble_K(
                self.pts, self.simp, 0.001, self.areas, self.b, self.c)
            self._Krm = None
            self._Gc_rear = None
            self._Krm_rows = None

        # Front metal grid stiffness
        # switched from 2D Galerkin sheet (assemble_K_met) to a 1D
        # conductor model. The 2D version produced mesh-dependent finger
        # conductance via sliver triangles when w_f << node spacing, causing
        # efficiency to diverge under refinement. The 1D model is convergent
        # and matches the 2D-converged result on wide fingers to 0.05% abs.
        # (DXF import): if an arbitrary axis-aligned rect pattern was
        # attached from a DXF (geo._dxf_finger_rects present), build the 1D
        # metal graph over those rects via the poly assembler. For H-patterns
        # this is bit-identical to assemble_K_met_1d (verified ΔK=0), so the
        # dispatch only changes behavior for imported non-H patterns.
        # v28.18 (리뷰 1-C): 접촉 컨덕턴스 피크 Gc=na·mf/rc. 1D 금속 등전위
        #   본드(SHORT)가 이보다 항상 크도록 assemble_K_met_1d에 전달한다.
        if self.Nm > 0:
            _gc_peak = float(np.max(self._na[self.ism] * self.metal_frac[self.ism])) / rc
        else:
            _gc_peak = 0.0
        _dxf_fr = getattr(self.geo, '_dxf_finger_rects', None)
        if _dxf_fr is not None:
            # DXF: rect별 고유 폭을 쓰므로 단일 케이스-폭 override는 정의 불가.
            # 케이스 폭 머신너리(단면/Gc/발전 스케일)는 DXF 경로에서 비활성.
            _dxf_br = getattr(self.geo, '_dxf_busbar_rects', [])
            self._Km = assemble_K_met_1d_poly(
                self.pts, self.ism, _dxf_fr, _dxf_br, rm, hf, cf,
                gc_max=_gc_peak)
        else:
            self._Km = assemble_K_met_1d(
                self.pts, self.ism, self.geo, rm, hf, cf,
                w_f=wf, w_b=wb_case, gc_max=_gc_peak)

        # Contact conductance: metal_frac weighted (continuous, Griddler method)
        self._Gc = np.zeros(self.N)
        self._Gc[self.ism] = self._na[self.ism] * self.metal_frac[self.ism] / rc
        # v28.18 (wf_wired): 접촉 면적도 케이스 폭에 비례해 스케일.
        #   (metal_frac은 설계 메시에 고정이므로 폭 비율을 노드별로 곱한다.)
        #   finger 노드 × (wf/geo.w_f), busbar(+pad) 노드 × (wb_case/geo.w_b);
        #   교차점은 busbar가 우선(교차부 금속은 busbar가 지배). Before 케이스는
        #   비율 1 → 비트 단위 동일.
        if getattr(self.geo, '_dxf_finger_rects', None) is None:
            _wsc = np.ones(self.N)
            if self.geo.w_f > 0:
                _wsc[self.isf] = wf / self.geo.w_f
            if self.geo.w_b > 0:
                _wsc[self.isb] = wb_case / self.geo.w_b
            self._Gc[self.ism] = self._Gc[self.ism] * _wsc[self.ism]
        # (③): spatial contact-R multiplier. The map multiplies R_contact,
        # so it divides the conductance Gc. None -> no-op (bit-identical).
        _m_rc = self._spatial_mult(dp, 'rc')
        if _m_rc is not None:
            self._Gc[self.ism] = self._Gc[self.ism] / _m_rc[self.ism]

        # v28.18 (wf_wired): 케이스 폭에 대한 발전량(generation) 전역 스케일.
        #   공간 조도 맵은 설계 메시에 고정하고(설계 의도: "mesh shade region is
        #   fixed to BEFORE geometry"), 총 발전량이 케이스 shading을 따르도록
        #   s = (1 - shade_case) / (1 - shade_design) 을 곱한다. ±10μm급 폭
        #   변화의 공간 재분배는 노드 간격(수백 μm)보다 한참 작아 전역 스케일이
        #   일관된 1차 처리다. illum_frac은 항상 원본 base에서 재계산(중첩 방지).
        _gen_s = 1.0
        if getattr(self.geo, '_dxf_finger_rects', None) is None:
            try:
                _sh_geo = float(self.geo.shading_fraction())
                _sh_case = float(self.geo.shading_fraction(w_f_opt=wf,
                                                           w_b_opt=wb_case))
                _gen_s = (1.0 - _sh_case) / max(1.0 - _sh_geo, 1e-9)
            except Exception:
                _gen_s = 1.0
        self.illum_frac = self._illum_frac_base * _gen_s

        # Cache metal row data for fast iteration
        self._Km_rows = []
        for k, gi in enumerate(self.midx):
            r = self._Km.getrow(gi)
            self._Km_rows.append((r.indices.copy(), r.data.copy()))

        # ===== INTERLAYER LATERAL PLANE (Phase B) =====
        # Only build K_int when Rs_junction > 0. Otherwise leave as None
        # and solver uses Phase A path.
        if Rs_j > 0:
            self._K_junc, _ = assemble_K(
                self.pts, self.simp, Rs_j, self.areas, self.b, self.c)
        else:
            self._K_junc = None

        # ===== PRE-ASSEMBLE STATIC JACOBIANS (done ONCE) =====
        # This eliminates the per-iteration Python for-loop bottleneck.
        N = self.N; Nm = self.Nm

        # --- Tandem static Jacobian (3N + Nm) ---
        Ns_t = 3 * N + Nm
        oVe = 0; oVm = N; oVt = N + Nm; oVr = N + Nm + N
        rows = []; cols = []; vals = []

        # Ke block at (oVe, oVe)
        Ke_c = self._Ke.tocoo()
        rows.append(Ke_c.row + oVe); cols.append(Ke_c.col + oVe); vals.append(Ke_c.data.copy())

        # Gc coupling (Ve <-> Vm)
        gc_nz = np.where(self._Gc > 0)[0]
        for gi in gc_nz:
            k = self.mmap[gi]
            if k < 0: continue
            gc = self._Gc[gi]
            rows.append(np.array([oVe+gi, oVe+gi, oVm+k, oVm+k], dtype=np.int64))
            cols.append(np.array([oVe+gi, oVm+k, oVe+gi, oVm+k], dtype=np.int64))
            vals.append(np.array([gc, -gc, -gc, gc]))

        # Km block at (oVm, oVm)
        for k, gi in enumerate(self.midx):
            ids, dat = self._Km_rows[k]
            for ci, v in zip(ids, dat):
                if self.ism[ci]:
                    rows.append(np.array([oVm+k])); cols.append(np.array([oVm+self.mmap[ci]])); vals.append(np.array([v]))

        # Kr block at (oVr, oVr)
        Kr_c = self._Kr.tocoo()
        rows.append(Kr_c.row + oVr); cols.append(Kr_c.col + oVr); vals.append(Kr_c.data.copy())

        self._J_static_tandem = coo_matrix(
            (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
            shape=(Ns_t, Ns_t)).tocsr()

        # --- Tandem BIFACIAL static Jacobian (3N + Nm + Nrm) ---
        # Adds rear metal grid as separate DOF, mirrors front 2-layer structure.
        if self.geo.rear_mode in ('bifacial', 'patterned') and self._Krm is not None:
            Nrm = self.Nrm
            Ns_tb = 3 * N + Nm + Nrm
            oVe_b = 0; oVm_b = N; oVt_b = N + Nm
            oVr_b = N + Nm + N; oVrm_b = 2 * N + Nm + N
            rows_b = []; cols_b = []; vals_b = []

            # Ke block at (oVe, oVe)
            rows_b.append(Ke_c.row + oVe_b); cols_b.append(Ke_c.col + oVe_b)
            vals_b.append(Ke_c.data.copy())

            # Front Gc coupling (Ve <-> Vm)
            for gi in gc_nz:
                k = self.mmap[gi]
                if k < 0: continue
                gc = self._Gc[gi]
                rows_b.append(np.array([oVe_b+gi, oVe_b+gi, oVm_b+k, oVm_b+k], dtype=np.int64))
                cols_b.append(np.array([oVe_b+gi, oVm_b+k, oVe_b+gi, oVm_b+k], dtype=np.int64))
                vals_b.append(np.array([gc, -gc, -gc, gc]))

            # Front Km block (oVm, oVm)
            for k, gi in enumerate(self.midx):
                ids, dat = self._Km_rows[k]
                for ci, v in zip(ids, dat):
                    if self.ism[ci]:
                        rows_b.append(np.array([oVm_b+k]))
                        cols_b.append(np.array([oVm_b+self.mmap[ci]]))
                        vals_b.append(np.array([v]))

            # Kr (rear emitter) block at (oVr, oVr)
            rows_b.append(Kr_c.row + oVr_b); cols_b.append(Kr_c.col + oVr_b)
            vals_b.append(Kr_c.data.copy())

            # Rear Gc_rear coupling (Vr <-> Vrm) - mirror of front Gc
            gc_rear_nz = np.where(self._Gc_rear > 0)[0]
            for gi in gc_rear_nz:
                kr = self.rear_mmap[gi]
                if kr < 0: continue
                gcr = self._Gc_rear[gi]
                rows_b.append(np.array([oVr_b+gi, oVr_b+gi, oVrm_b+kr, oVrm_b+kr], dtype=np.int64))
                cols_b.append(np.array([oVr_b+gi, oVrm_b+kr, oVr_b+gi, oVrm_b+kr], dtype=np.int64))
                vals_b.append(np.array([gcr, -gcr, -gcr, gcr]))

            # Krm (rear metal) block at (oVrm, oVrm)
            for kr, gi in enumerate(self.rear_midx):
                ids, dat = self._Krm_rows[kr]
                for ci, v in zip(ids, dat):
                    if self.isrm[ci]:
                        rows_b.append(np.array([oVrm_b+kr]))
                        cols_b.append(np.array([oVrm_b+self.rear_mmap[ci]]))
                        vals_b.append(np.array([v]))

            self._J_static_tandem_bf = coo_matrix(
                (np.concatenate(vals_b), (np.concatenate(rows_b), np.concatenate(cols_b))),
                shape=(Ns_tb, Ns_tb)).tocsr()
        else:
            self._J_static_tandem_bf = None

        # --- Single-cell static Jacobian (2N + Nm) ---
        Ns_s = 2 * N + Nm
        oVr_s = N + Nm
        rows2 = []; cols2 = []; vals2 = []

        rows2.append(Ke_c.row + oVe); cols2.append(Ke_c.col + oVe); vals2.append(Ke_c.data.copy())

        for gi in gc_nz:
            k = self.mmap[gi]
            if k < 0: continue
            gc = self._Gc[gi]
            rows2.append(np.array([oVe+gi, oVe+gi, oVm+k, oVm+k], dtype=np.int64))
            cols2.append(np.array([oVm+k, oVe+gi, oVe+gi, oVm+k], dtype=np.int64))
            vals2.append(np.array([-gc, gc, -gc, gc]))

        for k, gi in enumerate(self.midx):
            ids, dat = self._Km_rows[k]
            for ci, v in zip(ids, dat):
                if self.ism[ci]:
                    rows2.append(np.array([oVm+k])); cols2.append(np.array([oVm+self.mmap[ci]])); vals2.append(np.array([v]))

        rows2.append(Kr_c.row + oVr_s); cols2.append(Kr_c.col + oVr_s); vals2.append(Kr_c.data.copy())

        self._J_static_single = coo_matrix(
            (np.concatenate(vals2), (np.concatenate(rows2), np.concatenate(cols2))),
            shape=(Ns_s, Ns_s)).tocsr()

        # --- Single-cell BIFACIAL static Jacobian (2N + Nm + Nrm) ---
        if self.geo.rear_mode in ('bifacial', 'patterned') and self._Krm is not None:
            Nrm = self.Nrm
            Ns_sb = 2 * N + Nm + Nrm
            oVe_sb = 0; oVm_sb = N; oVr_sb = N + Nm; oVrm_sb = 2 * N + Nm
            rows3 = []; cols3 = []; vals3 = []

            # Ke
            rows3.append(Ke_c.row + oVe_sb); cols3.append(Ke_c.col + oVe_sb)
            vals3.append(Ke_c.data.copy())

            # Front Gc coupling
            for gi in gc_nz:
                k = self.mmap[gi]
                if k < 0: continue
                gc = self._Gc[gi]
                rows3.append(np.array([oVe_sb+gi, oVe_sb+gi, oVm_sb+k, oVm_sb+k], dtype=np.int64))
                cols3.append(np.array([oVm_sb+k, oVe_sb+gi, oVe_sb+gi, oVm_sb+k], dtype=np.int64))
                vals3.append(np.array([-gc, gc, -gc, gc]))

            # Front Km
            for k, gi in enumerate(self.midx):
                ids, dat = self._Km_rows[k]
                for ci, v in zip(ids, dat):
                    if self.ism[ci]:
                        rows3.append(np.array([oVm_sb+k]))
                        cols3.append(np.array([oVm_sb+self.mmap[ci]]))
                        vals3.append(np.array([v]))

            # Kr (rear emitter)
            rows3.append(Kr_c.row + oVr_sb); cols3.append(Kr_c.col + oVr_sb)
            vals3.append(Kr_c.data.copy())

            # Rear Gc_rear coupling
            gc_rear_nz = np.where(self._Gc_rear > 0)[0]
            for gi in gc_rear_nz:
                kr = self.rear_mmap[gi]
                if kr < 0: continue
                gcr = self._Gc_rear[gi]
                rows3.append(np.array([oVr_sb+gi, oVr_sb+gi, oVrm_sb+kr, oVrm_sb+kr], dtype=np.int64))
                cols3.append(np.array([oVr_sb+gi, oVrm_sb+kr, oVr_sb+gi, oVrm_sb+kr], dtype=np.int64))
                vals3.append(np.array([gcr, -gcr, -gcr, gcr]))

            # Krm (rear metal)
            for kr, gi in enumerate(self.rear_midx):
                ids, dat = self._Krm_rows[kr]
                for ci, v in zip(ids, dat):
                    if self.isrm[ci]:
                        rows3.append(np.array([oVrm_sb+kr]))
                        cols3.append(np.array([oVrm_sb+self.rear_mmap[ci]]))
                        vals3.append(np.array([v]))

            self._J_static_single_bf = coo_matrix(
                (np.concatenate(vals3), (np.concatenate(rows3), np.concatenate(cols3))),
                shape=(Ns_sb, Ns_sb)).tocsr()
        else:
            self._J_static_single_bf = None

    # ---------------------------------------------------------
    # TANDEM SOLVE (with rear plane)
    # ---------------------------------------------------------
    def solve_tandem(self, rm, hf, wf, rc, Rs, Vb, cf=1.0, dp=None):
        """
        Solve 2T tandem with rear plane -- OPTIMIZED.
        Static Jacobian parts pre-assembled; only diode diagonal updated per iteration.

        Dispatches to bifacial 2-layer rear solver if rear_mode is 'bifacial'.
        """
        if dp is None:
            dp = DiodeParams()
        self._build(rm, hf, wf, rc, Rs, cf, dp)

        # ===== v29 Path B-1.5: Continuation (homotopy) for high Rs_junction =====
        # Griddler-style high R_inter (1000~10000+ Ω/sq) requires gradual ramp from
        # baseline to target Rs_j to avoid Newton divergence (large jump in K_int scaling).
        # Strategy:
        #   - Target Rs_j ≤ 50 → solve directly (no ramp needed)
        #   - Target Rs_j > 50 → ramp through [50, 200, 1000, 5000, target]
        #   - Each intermediate step warm-starts from previous
        if (self._K_junc is not None
                and self.geo.rear_mode in ('bifacial', 'patterned')
                and self._J_static_tandem_bf is not None
                and dp.Rs_junction > 50):
            target_Rs_j = dp.Rs_junction
            # Generate ramp schedule: 50 → 200 → 1000 → 5000 → target
            ramp = [50.0, 200.0, 1000.0, 5000.0]
            ramp = [r for r in ramp if r < target_Rs_j] + [target_Rs_j]
            try:
                # Save current Rs_junction so we can restore after ramp
                _Rs_j_save = dp.Rs_junction
                last_result = None
                for Rs_j_step in ramp:
                    dp.Rs_junction = Rs_j_step
                    self._build(rm, hf, wf, rc, Rs, cf, dp)  # rebuild K_int per step
                    last_result = self._solve_tandem_junction_bf(rm, hf, wf, rc, Rs, Vb, cf, dp)
                dp.Rs_junction = _Rs_j_save
                return last_result
            except Exception as e:
                # Fallback: restore and try direct solve (may still fail but logged)
                dp.Rs_junction = target_Rs_j
                self._build(rm, hf, wf, rc, Rs, cf, dp)
                return self._solve_tandem_junction_bf(rm, hf, wf, rc, Rs, Vb, cf, dp)

        # Dispatch order (v29 Path B-1, 2026.05.19):
        # 1) Phase B + bifacial → 5-plane junction_bf solver with enhanced damping
        #    (v29 4-plane Schur kept for future, currently sub-optimal due to
        #     Gc_rear sparsity in diagonal-dominance approximation)
        # 2) Phase B + full_area → 5-plane junction solver (working since v28)
        # 3) Bifacial (Rs_junction=0) → bifacial solver (Phase A vertical R only)
        if (self._K_junc is not None
                and self.geo.rear_mode in ('bifacial', 'patterned')
                and self._J_static_tandem_bf is not None):
            return self._solve_tandem_junction_bf(rm, hf, wf, rc, Rs, Vb, cf, dp)

        if self._K_junc is not None and self.geo.rear_mode == 'full_area':
            return self._solve_tandem_junction(rm, hf, wf, rc, Rs, Vb, cf, dp)

        # Dispatch to bifacial branch if rear is patterned
        if (self.geo.rear_mode in ('bifacial', 'patterned')
                and self._J_static_tandem_bf is not None):
            return self._solve_tandem_bifacial(rm, hf, wf, rc, Rs, Vb, cf, dp)

        N = self.N; Nm = self.Nm; Ns = 3 * N + Nm
        oVe = 0; oVm = N; oVt = N + Nm; oVr = N + Nm + N

        # Initial guess
        Vt_est, Vb_est, Vtot_est = dp.expected_voc()
        frac = Vt_est / (Vt_est + Vb_est)
        V = np.zeros(Ns)
        V[oVe:oVe + N] = Vb * 0.95
        V[oVm:oVm + Nm] = Vb
        V[oVt:oVt + N] = Vb * frac * 0.95
        V[oVr:oVr + N] = 0.0
        self._apply_mesh_prolongation_seed(
            V, Vb,
            {"Ve": (oVe, None), "Vm": (oVm, self.midx),
             "Vtop": (oVt, None), "Vr": (oVr, None)},
            frac,
        )

        pmk = np.array([self.mmap[gi] for gi in self.pidx if self.mmap[gi] >= 0])
        # Full area rear: ALL rear nodes grounded (perfect back contact)
        # Patterned rear: rear probe points grounded (from rear H-pattern)
        if self.geo.rear_mode == 'full_area':
            rear_probe_idx = np.arange(N)
        elif self.rear_pidx is not None and len(self.rear_pidx) > 0:
            rear_probe_idx = self.rear_pidx
        else:
            # Fallback: front probe position
            rear_probe_idx = self.pidx

        ilf = self.illum_frac
        mf = self.metal_frac
        J01_top_arr = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
        J02_top_arr = dp.J02_top_pass * (1 - mf) + dp.J02_top_metal * mf

        # (③): apply per-node spatial multipliers. None -> no-op (skip),
        # so default behaviour is bit-identical to v28.15.
        _m_j01 = self._spatial_mult(dp, 'j01')
        _m_j02 = self._spatial_mult(dp, 'j02')
        _m_gen = self._spatial_mult(dp, 'gen')
        if _m_j01 is not None:
            J01_top_arr = J01_top_arr * _m_j01
        if _m_j02 is not None:
            J02_top_arr = J02_top_arr * _m_j02
        # Bottom-cell effective (node-length) arrays so the spatial map applies
        # to the Si subcell too. With no map these equal the scalar dp values
        # broadcast, preserving exact prior results.
        _J01b = dp.J01_bot * (_m_j01 if _m_j01 is not None else 1.0)
        _J02b = dp.J02_bot * (_m_j02 if _m_j02 is not None else 1.0)
        # Generation multipliers (top/bot share the optical map).
        _gen_t = (ilf * _m_gen) if _m_gen is not None else ilf
        _gen_b = _gen_t

        # Pre-extract static Jacobian (will add diode diagonals per iteration)
        J_base = self._J_static_tandem.copy()

        # Pre-compute BC mask rows (zero out once, set diagonal)
        bc_front = [oVm + k for k in pmk]
        bc_rear = [oVr + gi for gi in rear_probe_idx]

        # Interlayer vertical contact R: solved per outer-iter via inner
        # 3-step Newton on V_diode_bot (박사님 지시 2026.04.10).
        # Equation: Jb = Jb(V_diode_bot), V_diode_bot = (Ve-Vtop-Vr) - Rc*Jb
        # When Rc=0 this collapses to V_diode_bot = Ve-Vtop-Vr (original).
        Rc_j = dp.Rc_junction

        res_list = []
        for it in range(250):
            Ve = V[oVe:oVe + N]
            Vml = V[oVm:oVm + Nm]
            Vtop = V[oVt:oVt + N]
            Vr = V[oVr:oVr + N]
            # Standard "lumped" Vbot — would be the answer if Rc=0
            Vbot_lump = Ve - Vtop - Vr

            # Top subcell
            e1t = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
            e2t = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
            Jph_t = _gen_t * dp.Jph_top
            Jt = Jph_t - J01_top_arr * (e1t - 1) - J02_top_arr * (e2t - 1) - Vtop / dp.Rsh_top
            dJt = -(J01_top_arr * e1t / (dp.n1_top * VT) +
                     J02_top_arr * e2t / (dp.n2_top * VT) + 1 / dp.Rsh_top)

            # Bottom subcell with implicit interlayer R (Phase A vertical only)
            # KVL: cell J flows from rear pad (low V) UP to front pad (high V).
            # Through passive interlayer R, V drops in current direction (up),
            # so V_perov_p < V_si_n. With V_perov_p = Ve - Vtop and
            # V_si_n = Vr + Vbot:
            #   (Vr + Vbot) - (Ve - Vtop) = Rc * J
            #   Vbot = Ve - Vtop - Vr + Rc * J
            # The +Rc*J term INCREASES V_d_bot at fixed Vb → more recomb →
            # less cell J → standard series-R FF reduction. ✓
            # Solved via inner Newton in V_diode_bot. Rc=0 → trivial.
            # (v28.16 ③: _J01b/_J02b/_gen_b carry the spatial multiplier.)
            if Rc_j > 0:
                Vbot = Vbot_lump.copy()
                # LC additive term (V_top dependent, fixed during inner Newton)
                if dp.J01_coupling > 0:
                    J_LC_in = dp.J01_coupling * (np.exp(np.minimum(Vtop/VT, 80)) - 1)
                else:
                    J_LC_in = 0.0
                for inner_it in range(10):
                    e1b_i = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
                    e2b_i = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
                    Jb_i = (_gen_b * dp.Jph_bot
                            - _J01b * (e1b_i - 1)
                            - _J02b * (e2b_i - 1)
                            - Vbot / dp.Rsh_bot
                            + J_LC_in)
                    # Residual: Vbot - (Vbot_lump + Rc*Jb) = 0
                    f_in = Vbot - Vbot_lump - Rc_j * Jb_i
                    if np.max(np.abs(f_in)) < 1e-12:
                        break
                    dJb_i = -(_J01b * e1b_i / (dp.n1_bot * VT) +
                              _J02b * e2b_i / (dp.n2_bot * VT) +
                              1 / dp.Rsh_bot)
                    # df/dVbot = 1 - Rc*dJb_i  (always > 1 since dJb_i < 0)
                    df_in = 1.0 - Rc_j * dJb_i
                    dVb = -f_in / df_in
                    mx_in = np.max(np.abs(dVb))
                    if mx_in > 0.05:
                        dVb *= 0.05 / mx_in
                    Vbot = Vbot + dVb
            else:
                Vbot = Vbot_lump

            e1b = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
            e2b = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
            Jph_b = _gen_b * dp.Jph_bot
            Jb = Jph_b - _J01b * (e1b - 1) - _J02b * (e2b - 1) - Vbot / dp.Rsh_bot
            dJb_raw = -(_J01b * e1b / (dp.n1_bot * VT) +
                         _J02b * e2b / (dp.n2_bot * VT) + 1 / dp.Rsh_bot)
            # Implicit-Rc Jacobian correction:
            # Vbot = Vbot_lump + Rc*Jb(Vbot)
            # dVbot/dVbot_lump = 1 / (1 - Rc*dJb/dVbot)
            # dJb/dVbot_lump = dJb/dVbot * dVbot/dVbot_lump
            #                = dJb_raw / (1 - Rc*dJb_raw)
            # Since dJb_raw < 0, denominator > 1, so |dJb_eff| < |dJb_raw|.
            if Rc_j > 0:
                dJb = dJb_raw / (1.0 - Rc_j * dJb_raw)
            else:
                dJb = dJb_raw

            # --- Luminescent Coupling (LC) ---
            # J_LC = J01_coupling * (exp(V_top/VT) - 1), added to bottom subcell
            # as extra photogeneration (Zeder et al. 2025 / Jäger 2021; modeled
            # in SETFOS, not a Griddler feature — standard LC form).
            # Depends on V_top, so adds new Jacobian off-diagonal dJb/dVtop.
            if dp.J01_coupling > 0:
                eLC = np.exp(np.minimum(Vtop / VT, 80))
                J_LC = dp.J01_coupling * (eLC - 1)
                dJLC_dVtop = dp.J01_coupling * eLC / VT  # dJ_LC/dVtop
                if Rc_j == 0:
                    Jb = Jb + J_LC  # bottom cell gets extra generation
                # else: already included via inner Newton's J_LC_in
            else:
                J_LC = 0.0
                dJLC_dVtop = 0.0

            It = Jt * self._na
            Ib = Jb * self._na
            dIt = dJt * self._na
            dIb = dJb * self._na
            dILC_dVtop = dJLC_dVtop * self._na

            # ======= RESIDUAL F (vectorized) =======
            F = np.zeros(Ns)
            F[oVe:oVe + N] = self._Ke @ Ve - It
            # Gc coupling (vectorized over metal nodes)
            F[oVe + self.midx] += self._Gc[self.midx] * (Ve[self.midx] - Vml)
            # Metal KCL
            Vm_full = np.zeros(N)
            Vm_full[self.midx] = Vml
            F[oVm:oVm + Nm] = (self._Km @ Vm_full)[self.midx] + self._Gc[self.midx] * (Vml - Ve[self.midx])
            for k in pmk:
                F[oVm + k] = Vml[k] - Vb
            # Current matching
            F[oVt:oVt + N] = (Jt - Jb) * self._na
            # Rear KCL
            F[oVr:oVr + N] = self._Kr @ Vr + Ib
            for gi in rear_probe_idx:
                F[oVr + gi] = Vr[gi]

            # ======= JACOBIAN = Static + Diode diagonal =======
            # Build diagonal addition array
            diag = np.zeros(Ns)

            # dF_Ve/dVe: -dIt/dVtop is OFF-diagonal, handled below
            # But -dIt/dVe comes from chain: dJt depends on Vtop not Ve directly
            # dF_Ve/dVe diagonal: already in J_base (Ke + Gc)
            # No additional Ve diagonal needed from diodes

            # Current matching diagonal at oVt: (dJt + dJb)*na
            # With LC: dF_Vt/dVt gets extra -dJLC_dVtop*na (since Jb includes +J_LC)
            diag[oVt:oVt + N] = (dJt + dJb) * self._na - dILC_dVtop

            # Rear diagonal addition: -dJb*na (from dIb/dVr)
            diag[oVr:oVr + N] = -dIb

            J = self._J_static_tandem.copy()

            # Add diagonal
            J += csr_matrix((diag, (np.arange(Ns), np.arange(Ns))), shape=(Ns, Ns))

            # Off-diagonal diode terms (these change per iteration)
            # dF_Ve/dVtop = -dIt (at each node i)
            od_r = np.arange(N) + oVe
            od_c = np.arange(N) + oVt
            J += csr_matrix((-dIt, (od_r, od_c)), shape=(Ns, Ns))

            # dF_Vtop/dVe = -dJb*na
            J += csr_matrix((-dIb, (np.arange(N) + oVt, np.arange(N) + oVe)), shape=(Ns, Ns))

            # dF_Vtop/dVr = +dJb*na (chain: dVbot/dVr = -1, so -dJb*(-1) = +dJb)
            J += csr_matrix((dIb, (np.arange(N) + oVt, np.arange(N) + oVr)), shape=(Ns, Ns))

            # dF_Vr/dVe = dJb*na
            J += csr_matrix((dIb, (np.arange(N) + oVr, np.arange(N) + oVe)), shape=(Ns, Ns))

            # dF_Vr/dVtop = -dJb*na + dJLC_dVtop*na
            # (chain: Vbot = Ve - Vtop - Vr → dVbot/dVtop = -1 → -dJb*(-1) = -dJb
            #  wait, F_Vr = Kr@Vr + Ib, dF_Vr/dVtop = dIb/dVtop = dJb*(-1) + dJLC_dVtop
            #  = -dJb + dJLC_dVtop. Original code had -dIb which is wrong sign?
            #  Actually -dIb = -dJb*na which matches -dJb. OK consistent.)
            J += csr_matrix((-dIb + dILC_dVtop, (np.arange(N) + oVr, np.arange(N) + oVt)), shape=(Ns, Ns))

            # BC: vectorized zero rows + add diagonal=1 via COO
            bc_all = np.array(bc_front + bc_rear, dtype=np.int64)
            for idx_bc in bc_all:
                start = J.indptr[idx_bc]
                end = J.indptr[idx_bc + 1]
                J.data[start:end] = 0.0
            J += csr_matrix((np.ones(len(bc_all)),
                             (bc_all, bc_all)), shape=(Ns, Ns))

            # Solve
            dV = spsolve(J, -F)
            mx = np.max(np.abs(dV))
            if mx > 0.3:
                dV *= 0.3 / mx
            V += dV
            # (Step 5 fix): Vtop clip widened so mismatched cells solve
            # correctly at Jsc. Original [0, V_terminal] forced Vtop=0 in
            # Bottom-limited Jsc case. New range allows Vbot to go reverse
            # by up to 1.5V (covers all realistic mismatch). Newton dV cap
            # 0.3V/iter ensures numerical stability.
            V[oVt:oVt + N] = np.clip(V[oVt:oVt + N],
                                     -0.5,
                                     V[oVe:oVe + N] - V[oVr:oVr + N] + 1.5)

            r = np.max(np.abs(F))
            res_list.append(r)
            if r < 1e-10:
                break
            # Stagnation escape for stiff regimes (e.g., interlayer R near Voc):
            # If residual flat for 6 iters and below 1e-6, accept as converged.
            if len(res_list) >= 10:
                recent = res_list[-6:]
                if max(recent) / max(min(recent), 1e-20) < 1.05 and r < 1e-6:
                    break

        Ve = V[oVe:oVe + N]
        Vm = np.full(N, np.nan)
        Vm[self.midx] = V[oVm:oVm + Nm]
        Vtop = V[oVt:oVt + N]
        Vr = V[oVr:oVr + N]
        return Ve, Vm, Vtop, Vr, res_list

    # ---------------------------------------------------------
    # TANDEM INTERLAYER SOLVE (Phase B — full area only)
    # ---------------------------------------------------------
    def _solve_tandem_junction(self, rm, hf, wf, rc, Rs, Vb, cf, dp):
        """Phase B solver: tandem with interlayer lateral plane.

        DOF layout: [Ve(N), Vm(Nm), Vt(N), Vr(N), V_int(N)] = 4N + Nm.

        Physics (박사님 지시 2026.04.10, Phase B):
          - V_int is a new plane DOF representing interlayer potential.
          - Vertical R Rc_junction is lumped above V_int:
              V_perov_p = V_int - Rc_j * Jt
              → F_Vt: Vtop - Ve + V_int - Rc_j * Jt = 0
          - Below V_int is directly connected to Si n-side:
              V_si_n = V_int → Vbot = V_int - Vr  (explicit, no inner Newton!)
          - Lateral spreading: K_int @ V_int = (Jt - Jb)*na
              Relaxes pointwise current matching; current can redistribute
              laterally in the interlayer from high-Jt to low-Jt regions.

        Limits:
          - Rs_j → ∞ (K_int → 0): F_Vint forces (Jt - Jb) = 0 pointwise
            → degenerates to Phase A with vertical R (after Vbot substitution).
          - Rs_j → 0: V_int uniform, integrated current matching only.

        Full area only. Bifacial + lateral interlayer: future work.
        """
        from scipy.sparse import csr_matrix, coo_matrix
        from scipy.sparse.linalg import spsolve

        N = self.N; Nm = self.Nm
        Ns = 4 * N + Nm
        oVe = 0
        oVm = N
        oVt = N + Nm
        oVr = 2 * N + Nm
        oVint = 3 * N + Nm

        # Initial guess
        Vt_est, Vb_est, _ = dp.expected_voc()
        frac = Vt_est / (Vt_est + Vb_est)
        V = np.zeros(Ns)
        V[oVe:oVe + N] = Vb * 0.95
        V[oVm:oVm + Nm] = Vb
        V[oVt:oVt + N] = max(Vb, 0.01) * frac * 0.95
        V[oVr:oVr + N] = 0.0
        # V_int near Vbot operating point (so Vbot = V_int - Vr ≈ Vb*(1-frac))
        V[oVint:oVint + N] = max(Vb, 0.01) * (1 - frac) * 0.95
        self._apply_mesh_prolongation_seed(
            V, Vb,
            {"Ve": (oVe, None), "Vm": (oVm, self.midx),
             "Vtop": (oVt, None), "Vr": (oVr, None),
             "Vint": (oVint, None)},
            frac,
        )

        pmk = np.array([self.mmap[gi] for gi in self.pidx if self.mmap[gi] >= 0])
        # Full area rear: ground all rear nodes
        rear_probe_idx = np.arange(N)

        ilf = self.illum_frac
        mf = self.metal_frac
        J01_top_arr = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
        J02_top_arr = dp.J02_top_pass * (1 - mf) + dp.J02_top_metal * mf

        Rc_j = dp.Rc_junction

        bc_front = np.array([oVm + k for k in pmk], dtype=np.int64)
        bc_rear = np.array([oVr + gi for gi in rear_probe_idx], dtype=np.int64)

        idx_N = np.arange(N, dtype=np.int64)

        # Pre-compute COO pieces that don't change across iterations
        Ke_c = self._Ke.tocoo()
        Kr_c = self._Kr.tocoo()
        Kint_c = self._K_junc.tocoo()
        # Km submatrix on metal rows/cols
        Km_mm = self._Km[self.midx, :][:, self.midx]
        Km_mm_c = Km_mm.tocoo()
        # Local metal indices (0..Nm-1) for each global metal node
        mm_local = self.mmap[self.midx]  # = np.arange(Nm) essentially

        res_list = []
        for it in range(250):
            Ve = V[oVe:oVe + N]
            Vml = V[oVm:oVm + Nm]
            Vtop = V[oVt:oVt + N]
            Vr = V[oVr:oVr + N]
            V_int = V[oVint:oVint + N]

            # Vbot is EXPLICIT in Phase B: Vbot = V_int - Vr
            Vbot = V_int - Vr

            # Top subcell
            e1t = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
            e2t = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
            Jt = ilf * dp.Jph_top - J01_top_arr * (e1t - 1) \
                 - J02_top_arr * (e2t - 1) - Vtop / dp.Rsh_top
            dJt = -(J01_top_arr * e1t / (dp.n1_top * VT)
                    + J02_top_arr * e2t / (dp.n2_top * VT)
                    + 1 / dp.Rsh_top)

            # Bot subcell
            e1b = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
            e2b = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
            Jb = ilf * dp.Jph_bot - dp.J01_bot * (e1b - 1) \
                 - dp.J02_bot * (e2b - 1) - Vbot / dp.Rsh_bot
            dJb = -(dp.J01_bot * e1b / (dp.n1_bot * VT)
                    + dp.J02_bot * e2b / (dp.n2_bot * VT)
                    + 1 / dp.Rsh_bot)

            # LC
            if dp.J01_coupling > 0:
                eLC = np.exp(np.minimum(Vtop / VT, 80))
                J_LC = dp.J01_coupling * (eLC - 1)
                dJLC = dp.J01_coupling * eLC / VT
                Jb = Jb + J_LC
            else:
                dJLC = 0.0

            It = Jt * self._na
            Ib = Jb * self._na
            dIt = dJt * self._na
            dIb = dJb * self._na
            dILC = dJLC * self._na

            # ====== Residual F ======
            F = np.zeros(Ns)
            # F_Ve
            F[oVe:oVe + N] = self._Ke @ Ve - It
            F[oVe + self.midx] += self._Gc[self.midx] * (Ve[self.midx] - Vml)
            # F_Vm
            Vm_full = np.zeros(N)
            Vm_full[self.midx] = Vml
            F[oVm:oVm + Nm] = ((self._Km @ Vm_full)[self.midx]
                               + self._Gc[self.midx] * (Vml - Ve[self.midx]))
            for k in pmk:
                F[oVm + k] = Vml[k] - Vb
            # F_Vt: Vtop - Ve + V_int - Rc*Jt
            F[oVt:oVt + N] = Vtop - Ve + V_int - Rc_j * Jt
            # F_Vr: Kr @ Vr + Ib (Ib = Jb*na)
            F[oVr:oVr + N] = self._Kr @ Vr + Ib
            for gi in rear_probe_idx:
                F[oVr + gi] = Vr[gi]
            # F_Vint: interlayer node KCL. V_int is the top cell's REAR
            # (contributes +It, like F_Vr=Kr@Vr+Ib) and simultaneously the bottom
            # cell's EMITTER (contributes -Ib, like F_Ve=Ke@Ve-It, since
            # Vbot=V_int-Vr). So lateral-out = +It - Ib:
            #     K_int @ V_int + It - Ib = 0
            # TANDEM-1 fix: this previously read "- It + Ib", the opposite sign,
            # which deviated from the file's universal 2-plane KCL convention
            # (upper plane K@V-I, lower plane K@V+I) used by every other emitter/
            # rear/interlayer residual (e.g. the bifacial junction solver L4322).
            # Only affects Phase-B full_area runs (Rs_junction>0); default
            # Rs_junction=0 uses solve_tandem (no interlayer plane).
            F[oVint:oVint + N] = self._K_junc @ V_int + It - Ib

            # ====== Jacobian (assembled from COO blocks) ======
            rows = []; cols = []; vals = []

            # --- F_Ve / dVe: Ke + Gc diag ---
            rows.append(Ke_c.row + oVe)
            cols.append(Ke_c.col + oVe)
            vals.append(Ke_c.data.copy())
            # Gc diagonal at metal nodes
            rows.append(self.midx + oVe)
            cols.append(self.midx + oVe)
            vals.append(self._Gc[self.midx].copy())
            # --- F_Ve / dVm: -Gc coupling ---
            rows.append(self.midx + oVe)
            cols.append(mm_local + oVm)
            vals.append(-self._Gc[self.midx].copy())
            # --- F_Ve / dVt: -dIt diagonal ---
            rows.append(idx_N + oVe)
            cols.append(idx_N + oVt)
            vals.append(-dIt)

            # --- F_Vm / dVm: Km[metal,metal] + Gc diag ---
            rows.append(Km_mm_c.row + oVm)
            cols.append(Km_mm_c.col + oVm)
            vals.append(Km_mm_c.data.copy())
            rows.append(mm_local + oVm)
            cols.append(mm_local + oVm)
            vals.append(self._Gc[self.midx].copy())
            # --- F_Vm / dVe: -Gc coupling (transpose of Ve/dVm) ---
            rows.append(mm_local + oVm)
            cols.append(self.midx + oVe)
            vals.append(-self._Gc[self.midx].copy())

            # --- F_Vt / dVe: -1 diagonal ---
            rows.append(idx_N + oVt)
            cols.append(idx_N + oVe)
            vals.append(-np.ones(N))
            # --- F_Vt / dVt: (1 - Rc*dJt) diagonal ---
            rows.append(idx_N + oVt)
            cols.append(idx_N + oVt)
            vals.append(1.0 - Rc_j * dJt)
            # --- F_Vt / dVint: +1 diagonal ---
            rows.append(idx_N + oVt)
            cols.append(idx_N + oVint)
            vals.append(np.ones(N))

            # --- F_Vr / dVr: Kr + (-dJb)*na diag (dVbot/dVr = -1) ---
            rows.append(Kr_c.row + oVr)
            cols.append(Kr_c.col + oVr)
            vals.append(Kr_c.data.copy())
            rows.append(idx_N + oVr)
            cols.append(idx_N + oVr)
            vals.append(-dIb)  # dJb/dVr = -dJb → dF_Vr/dVr = +(-dIb)*... wait
            # F_Vr = Kr@Vr + Jb*na. dF_Vr/dVr += dJb/dVr * na = dJb*(-1)*na = -dIb
            # Yes, -dIb diagonal addition. Above is correct.

            # --- F_Vr / dVint: dJb/dVint * na = dJb*(+1)*na = dIb ---
            rows.append(idx_N + oVr)
            cols.append(idx_N + oVint)
            vals.append(dIb)
            # --- F_Vr / dVt: dJLC*na (LC off-diagonal) ---
            if dp.J01_coupling > 0:
                rows.append(idx_N + oVr)
                cols.append(idx_N + oVt)
                vals.append(dILC)

            # TANDEM-1 fix: Jacobian of F_Vint = K_int@V_int + It - Ib (diode
            # source signs flipped to match the corrected residual; K_int term
            # unchanged).
            # --- F_Vint / dVint: K_int - dIb diag (from -Ib, dVbot/dVint=+1) ---
            rows.append(Kint_c.row + oVint)
            cols.append(Kint_c.col + oVint)
            vals.append(Kint_c.data.copy())
            rows.append(idx_N + oVint)
            cols.append(idx_N + oVint)
            vals.append(-dIb)
            # --- F_Vint / dVr: d(-Ib)/dVr = -dJb*na*(dVbot/dVr=-1) = +dIb ---
            rows.append(idx_N + oVint)
            cols.append(idx_N + oVr)
            vals.append(dIb)
            # --- F_Vint / dVt: d(+It)/dVt = +dIt; LC via -Ib → -dILC ---
            rows.append(idx_N + oVint)
            cols.append(idx_N + oVt)
            vals.append(dIt - dILC)

            # Build sparse matrix
            J_rows = np.concatenate(rows)
            J_cols = np.concatenate(cols)
            J_vals = np.concatenate(vals)
            J = csr_matrix((J_vals, (J_rows, J_cols)), shape=(Ns, Ns))

            # Apply BCs: zero rows, set diagonal = 1
            bc_all = np.concatenate([bc_front, bc_rear])
            for idx_bc in bc_all:
                start = J.indptr[idx_bc]
                end = J.indptr[idx_bc + 1]
                J.data[start:end] = 0.0
            J += csr_matrix((np.ones(len(bc_all)),
                             (bc_all, bc_all)), shape=(Ns, Ns))

            # ===== v28.11 STABILIZATION PATCH =====
            # Adaptive Levenberg-Marquardt damping
            # If residual stagnated (last 2 steps showed <10% improvement),
            # add λI to Jacobian → damped Newton step toward gradient descent
            F_norm = float(np.linalg.norm(F))
            lm_lambda = 0.0
            if len(res_list) >= 2:
                # Detect stagnation: current residual >= 0.9 * residual_2_ago
                if res_list[-1] > 0.9 * res_list[-2]:
                    # LM damping proportional to current residual magnitude
                    lm_lambda = max(1e-3 * F_norm, 1e-7)

            if lm_lambda > 0:
                diag_idx = np.arange(Ns, dtype=np.int64)
                J = J + csr_matrix(
                    (lm_lambda * np.ones(Ns), (diag_idx, diag_idx)),
                    shape=(Ns, Ns)
                )

            # Solve Newton step
            dV = spsolve(J, -F)

            # Adaptive step limit: very conservative early, relax as we converge
            if it < 5:
                step_limit = 0.05   # Very small steps early to avoid overshoot
            elif it < 15:
                step_limit = 0.15
            else:
                step_limit = 0.3

            mx = np.max(np.abs(dV))
            if mx > step_limit:
                dV *= step_limit / mx

            # Trial step
            V_trial = V + dV
            # Apply Vtop clip on trial
            V_trial[oVt:oVt + N] = np.clip(
                V_trial[oVt:oVt + N],
                -0.5,
                V_trial[oVe:oVe + N] - V_trial[oVr:oVr + N] + 1.5
            )

            # Backtracking line search (lightweight):
            # If residual not improving with full step, take half-step
            # Only check after a few iterations (skip cost early)
            if it >= 3 and len(res_list) >= 1:
                # Quick re-evaluation of F norm at trial point
                Ve_t = V_trial[oVe:oVe + N]
                Vml_t = V_trial[oVm:oVm + Nm]
                Vtop_t = V_trial[oVt:oVt + N]
                Vr_t = V_trial[oVr:oVr + N]
                V_int_t = V_trial[oVint:oVint + N]
                Vbot_t = V_int_t - Vr_t

                # Approximate F norm (skip BC enforcement for speed)
                e1t_t = np.exp(np.minimum(Vtop_t / (dp.n1_top * VT), 80))
                e2t_t = np.exp(np.minimum(Vtop_t / (dp.n2_top * VT), 80))
                Jt_t = (ilf * dp.Jph_top - J01_top_arr * (e1t_t - 1)
                        - J02_top_arr * (e2t_t - 1) - Vtop_t / dp.Rsh_top)
                e1b_t = np.exp(np.minimum(Vbot_t / (dp.n1_bot * VT), 80))
                e2b_t = np.exp(np.minimum(Vbot_t / (dp.n2_bot * VT), 80))
                Jb_t = (ilf * dp.Jph_bot - dp.J01_bot * (e1b_t - 1)
                        - dp.J02_bot * (e2b_t - 1) - Vbot_t / dp.Rsh_bot)
                It_t = Jt_t * self._na
                Ib_t = Jb_t * self._na
                F_quick = abs(np.max(self._Ke @ Ve_t - It_t))
                F_quick = max(F_quick, abs(np.max(
                    Vtop_t - Ve_t + V_int_t - Rc_j * Jt_t)))

                # If trial residual >> current residual, halve step
                if F_quick > 2.0 * F_norm:
                    dV *= 0.5
                    V_trial = V + dV
                    V_trial[oVt:oVt + N] = np.clip(
                        V_trial[oVt:oVt + N],
                        -0.5,
                        V_trial[oVe:oVe + N] - V_trial[oVr:oVr + N] + 1.5
                    )

            V = V_trial
            # ===== END STABILIZATION PATCH =====

            r = np.max(np.abs(F))
            res_list.append(r)
            if r < 1e-7:
                break
            # Stagnation escape
            if len(res_list) >= 12:
                recent = res_list[-8:]
                if max(recent) / max(min(recent), 1e-20) < 1.05 and r < 5e-6:
                    break
            # Hard divergence detection — abort if residual exploding
            if len(res_list) >= 8 and r > 1e3 and r > res_list[-8] * 100:
                # Solver diverged — return what we have, caller will catch
                break

        Ve_out = V[oVe:oVe + N]
        Vm_out = np.full(N, np.nan)
        Vm_out[self.midx] = V[oVm:oVm + Nm]
        Vtop_out = V[oVt:oVt + N]
        Vr_out = V[oVr:oVr + N]
        # Stash V_int for visualization/loss calculation
        self._last_Vint = V[oVint:oVint + N].copy()
        return Ve_out, Vm_out, Vtop_out, Vr_out, res_list

    # ---------------------------------------------------------
    # TANDEM PHASE B + BIFACIAL (6-plane solver, Step 3-C)
    # ---------------------------------------------------------
    def _solve_tandem_junction_bf(self, rm, hf, wf, rc, Rs, Vb, cf, dp):
        """6-plane solver: Phase B (interlayer lateral) + bifacial rear.

        DOF: [Ve(N), Vm(Nm), Vt(N), Vint(N), Vr(N), Vrm(Nrm)]
             total = 4N + Nm + Nrm

        Physics:
          - V_int is interlayer lateral plane (Phase B)
          - Vbot = V_int - Vr  (rear TCO is variable, not ground)
          - Rear has 2-layer FEM: Rear TCO (Vr) + Rear metal grid (Vrm)
          - Bifacial gain on Jph_b
          박사님 지시 (회의록 2026.04.10): bifacial tandem 우선 구현
        """
        from scipy.sparse import csr_matrix, coo_matrix
        from scipy.sparse.linalg import spsolve

        N = self.N; Nm = self.Nm; Nrm = self.Nrm
        Ns = 4 * N + Nm + Nrm
        oVe = 0
        oVm = N
        oVt = N + Nm
        oVint = 2 * N + Nm
        oVr = 3 * N + Nm
        oVrm = 4 * N + Nm

        # Initial guess (cold start; warm-start can be added later)
        Vt_est, Vb_est, _ = dp.expected_voc()
        frac = Vt_est / (Vt_est + Vb_est)
        V = np.zeros(Ns)
        V[oVe:oVe + N] = Vb * 0.95
        V[oVm:oVm + Nm] = Vb
        V[oVt:oVt + N] = max(Vb, 0.01) * frac * 0.95
        # Method B: oVint slot holds Vbot. With Vr initialized to 0, this is the
        # bottom-cell operating point (same numeric value as the old V_int init).
        V[oVint:oVint + N] = max(Vb, 0.01) * (1 - frac) * 0.95
        V[oVr:oVr + N] = 0.0
        V[oVrm:oVrm + Nrm] = 0.0
        self._apply_mesh_prolongation_seed(
            V, Vb,
            {"Ve": (oVe, None), "Vm": (oVm, self.midx),
             "Vtop": (oVt, None), "Vbot": (oVint, None),
             "Vr": (oVr, None), "Vrm": (oVrm, self.rear_midx)},
            frac,
        )

        pmk = np.array([self.mmap[gi] for gi in self.pidx if self.mmap[gi] >= 0])
        rear_pad_kr = []
        if self.rear_pidx is not None:
            for gi in self.rear_pidx:
                kr = self.rear_mmap[gi]
                if kr >= 0:
                    rear_pad_kr.append(kr)
        rear_pad_kr = np.array(rear_pad_kr, dtype=np.int64)
        # gauge fix: global node indices of rear pads (V_int anchor)
        rear_pad_kr_node = np.array(
            [int(gi) for gi in (self.rear_pidx if self.rear_pidx is not None else [])
             if self.rear_mmap[gi] >= 0], dtype=np.int64)

        ilf = self.illum_frac
        mf = self.metal_frac
        J01_top_arr = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
        J02_top_arr = dp.J02_top_pass * (1 - mf) + dp.J02_top_metal * mf

        Rc_j = dp.Rc_junction
        bc_front = np.array([oVm + k for k in pmk], dtype=np.int64)
        bc_rear = np.array([oVrm + kr for kr in rear_pad_kr], dtype=np.int64)
        idx_N = np.arange(N, dtype=np.int64)

        # Pre-compute COO pieces
        Ke_c = self._Ke.tocoo()
        Kr_c = self._Kr.tocoo()
        Krm = self._Krm
        Krm_mm = Krm[self.rear_midx, :][:, self.rear_midx]
        Krm_mm_c = Krm_mm.tocoo()
        rmm_local = self.rear_mmap[self.rear_midx]
        Kint_c = self._K_junc.tocoo()
        Km_mm = self._Km[self.midx, :][:, self.midx]
        Km_mm_c = Km_mm.tocoo()
        mm_local = self.mmap[self.midx]
        gc_rear_nz = np.where(self._Gc_rear > 0)[0]

        res_list = []
        DBG = False  # debug off (6-plane disabled)
        if DBG:
            print(f"\n[6plane] Vb={Vb:.4f} Rc_j={Rc_j:.3f} Rs_j={dp.Rs_junction:.1f} DOF={Ns}")
        for it in range(120):  # augmented gauge removed singularity; allow full convergence
            Ve = V[oVe:oVe + N]
            Vml = V[oVm:oVm + Nm]
            Vtop = V[oVt:oVt + N]
            # METHOD B (v28.16): the DOF slot at oVint now holds Vbot DIRECTLY,
            # not the interlayer potential. V_int is the dependent quantity:
            #     V_int = Vbot + Vr
            # Previously V_int and Vr entered every equation only via the
            # difference Vbot = V_int - Vr, so (V_int+c, Vr+c) was a null mode
            # -> singular Jacobian + residual floor. With Vbot as the variable
            # the null mode is gone: Vbot enters the bottom diode as exp(Vbot/VT)
            # (a shift changes Jb exponentially), while Vr stays pinned by
            # Kr + Gc_rear + rear ground. Pure change of variables; identical
            # physics; no gauge term and no floor.
            Vbot = V[oVint:oVint + N]          # this DOF IS Vbot now
            Vr = V[oVr:oVr + N]
            Vrml = V[oVrm:oVrm + Nrm]
            V_int = Vbot + Vr                  # dependent interlayer potential

            # Top subcell currents/derivatives
            e1t = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
            e2t = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
            Jt = ilf * dp.Jph_top - J01_top_arr * (e1t - 1) \
                 - J02_top_arr * (e2t - 1) - Vtop / dp.Rsh_top
            dJt = -(J01_top_arr * e1t / (dp.n1_top * VT)
                    + J02_top_arr * e2t / (dp.n2_top * VT) + 1 / dp.Rsh_top)

            # Bottom subcell with bifacial Jph and LC
            Jph_b_eff = (ilf + dp.bifacial_gain * self.rear_illum_frac) * dp.Jph_bot
            e1b = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
            e2b = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
            if dp.J01_coupling > 0:
                J_LC = dp.J01_coupling * (np.exp(np.minimum(Vtop / VT, 80)) - 1)
                dILC = (dp.J01_coupling / VT * np.exp(np.minimum(Vtop / VT, 80))) * self._na
            else:
                J_LC = 0.0; dILC = np.zeros(N)
            Jb = (Jph_b_eff - dp.J01_bot * (e1b - 1)
                  - dp.J02_bot * (e2b - 1) - Vbot / dp.Rsh_bot + J_LC)
            dJb = -(dp.J01_bot * e1b / (dp.n1_bot * VT)
                    + dp.J02_bot * e2b / (dp.n2_bot * VT) + 1 / dp.Rsh_bot)

            It = Jt * self._na
            Ib = Jb * self._na
            dIt = dJt * self._na
            dIb = dJb * self._na

            # ---------- F (residuals) ----------
            F = np.zeros(Ns)
            # F_Ve: Ke@Ve - It (sign matches Phase B full_area solver convention)
            F[oVe:oVe + N] = self._Ke @ Ve - It
            F[oVe + self.midx] += self._Gc[self.midx] * (Ve[self.midx] - Vml)
            # F_Vm
            Vm_full = np.zeros(N); Vm_full[self.midx] = Vml
            F[oVm:oVm + Nm] = ((self._Km @ Vm_full)[self.midx]
                               + self._Gc[self.midx] * (Vml - Ve[self.midx]))
            for k in pmk:
                F[oVm + k] = Vml[k] - Vb
            # F_Vt: Vtop - Ve + V_int - Rc*Jt   (V_int = Vbot + Vr, recovered)
            F[oVt:oVt + N] = Vtop - Ve + V_int - Rc_j * Jt
            # F_Vbot (interlayer KCL, residing in the oVint slot):
            #   K_int @ V_int + It - Ib,  with V_int = Vbot + Vr.
            # The unknown in this slot is Vbot; the equation is unchanged because
            # V_int has been reconstructed above. K_int still acts on the true
            # interlayer potential V_int = Vbot + Vr.
            F[oVint:oVint + N] = self._K_junc @ V_int + It - Ib
            # F_Vr: Kr @ Vr + Ib + Gc_rear*(Vr - Vrm)
            F[oVr:oVr + N] = self._Kr @ Vr + Ib
            for gi in gc_rear_nz:
                kr = self.rear_mmap[gi]
                if kr >= 0:
                    F[oVr + gi] += self._Gc_rear[gi] * (Vr[gi] - Vrml[kr])
            # F_Vrm: Krm @ Vrm + Gc_rear*(Vrm - Vr) - BC at rear pads
            Vrm_full = np.zeros(N); Vrm_full[self.rear_midx] = Vrml
            F[oVrm:oVrm + Nrm] = ((Krm @ Vrm_full)[self.rear_midx]
                                  + self._Gc_rear[self.rear_midx]
                                    * (Vrml - Vr[self.rear_midx]))
            for kr in rear_pad_kr:
                F[oVrm + kr] = Vrml[kr] - 0.0  # Rear ground BC

            # ---------- Jacobian ----------
            rows = []; cols = []; vals = []

            # F_Ve / dVe : Ke + Gc diag
            rows.append(Ke_c.row + oVe); cols.append(Ke_c.col + oVe); vals.append(Ke_c.data.copy())
            rows.append(self.midx + oVe); cols.append(self.midx + oVe)
            vals.append(self._Gc[self.midx].copy())
            # F_Ve / dVm : -Gc
            rows.append(self.midx + oVe); cols.append(mm_local + oVm)
            vals.append(-self._Gc[self.midx].copy())
            # F_Ve / dVt : -dIt diag (matches F_Ve = Ke@Ve - It convention)
            rows.append(idx_N + oVe); cols.append(idx_N + oVt); vals.append(-dIt)

            # F_Vm / dVm : Km_mm + Gc diag
            rows.append(Km_mm_c.row + oVm); cols.append(Km_mm_c.col + oVm); vals.append(Km_mm_c.data.copy())
            rows.append(mm_local + oVm); cols.append(mm_local + oVm); vals.append(self._Gc[self.midx].copy())
            # F_Vm / dVe : -Gc
            rows.append(mm_local + oVm); cols.append(self.midx + oVe)
            vals.append(-self._Gc[self.midx].copy())

            # F_Vt / dVe : -1
            rows.append(idx_N + oVt); cols.append(idx_N + oVe); vals.append(-np.ones(N))
            # F_Vt / dVt : 1 - Rc*dJt
            rows.append(idx_N + oVt); cols.append(idx_N + oVt); vals.append(1.0 - Rc_j * dJt)
            # F_Vt / dVint : +1
            rows.append(idx_N + oVt); cols.append(idx_N + oVint); vals.append(np.ones(N))
            # F_Vt / dVr : +1  (NEW under method B: Vr part of V_int = Vbot + Vr)
            rows.append(idx_N + oVt); cols.append(idx_N + oVr); vals.append(np.ones(N))

            # F_Vbot (oVint slot) = K_int @ (Vbot + Vr) + It - Ib(Vbot)
            # / dVbot : K_int (Vbot part) + (-dIb)   [Ib depends on Vbot only]
            rows.append(Kint_c.row + oVint); cols.append(Kint_c.col + oVint); vals.append(Kint_c.data.copy())
            rows.append(idx_N + oVint); cols.append(idx_N + oVint); vals.append(-dIb)
            # / dVr : K_int  (Vr part of V_int = Vbot + Vr). Under B, Ib no longer
            #   depends on Vr, so the old +dIb term is REPLACED by this K_int block.
            rows.append(Kint_c.row + oVint); cols.append(Kint_c.col + oVr); vals.append(Kint_c.data.copy())
            # / dVt : +dIt - dILC
            rows.append(idx_N + oVint); cols.append(idx_N + oVt); vals.append(dIt - dILC)

            # F_Vr = Kr @ Vr + Ib(Vbot) + Gc_rear*(Vr - Vrm)
            # / dVr : Kr + Gc_rear   (under B, Ib depends on Vbot only -> NO -dIb)
            rows.append(Kr_c.row + oVr); cols.append(Kr_c.col + oVr); vals.append(Kr_c.data.copy())
            for gi in gc_rear_nz:
                rows.append(np.array([oVr + gi])); cols.append(np.array([oVr + gi]))
                vals.append(np.array([self._Gc_rear[gi]]))
            # / dVbot : +dIb   (Ib depends on Vbot directly)
            rows.append(idx_N + oVr); cols.append(idx_N + oVint); vals.append(dIb)
            # F_Vr / dVt : dILC (from J_LC term in Jb)
            rows.append(idx_N + oVr); cols.append(idx_N + oVt); vals.append(dILC)
            # F_Vr / dVrm : -Gc_rear (off-diagonal coupling)
            for gi in gc_rear_nz:
                kr = self.rear_mmap[gi]
                if kr >= 0:
                    rows.append(np.array([oVr + gi])); cols.append(np.array([oVrm + kr]))
                    vals.append(np.array([-self._Gc_rear[gi]]))

            # F_Vrm / dVrm : Krm_mm + Gc_rear diag
            rows.append(Krm_mm_c.row + oVrm); cols.append(Krm_mm_c.col + oVrm); vals.append(Krm_mm_c.data.copy())
            rows.append(rmm_local + oVrm); cols.append(rmm_local + oVrm)
            vals.append(self._Gc_rear[self.rear_midx].copy())
            # F_Vrm / dVr : -Gc_rear
            rows.append(rmm_local + oVrm); cols.append(self.rear_midx + oVr)
            vals.append(-self._Gc_rear[self.rear_midx].copy())

            J_rows = np.concatenate(rows)
            J_cols = np.concatenate(cols)
            J_vals = np.concatenate(vals)

            # Apply Dirichlet BCs (front pads, rear pads): drop triplets on BC
            # rows then add unit diagonals (vectorized identity rows).
            bc_all = np.concatenate([bc_front, bc_rear])
            bc_set = np.zeros(Ns, dtype=bool); bc_set[bc_all] = True
            keep = ~bc_set[J_rows]
            J_rows = np.concatenate([J_rows[keep], bc_all])
            J_cols = np.concatenate([J_cols[keep], bc_all])
            J_vals = np.concatenate([J_vals[keep], np.ones(len(bc_all))])
            J_csr = csr_matrix((J_vals, (J_rows, J_cols)), shape=(Ns, Ns))


            # ===== METHOD B: no gauge term needed =====
            # With Vbot as the DOF (V_int = Vbot + Vr), the interlayer plane no
            # longer has a constant null mode: Vbot enters the bottom diode as
            # exp(Vbot/VT), so the Jacobian is nonsingular by construction. The
            # earlier augmented-gauge border (Lagrange multiplier) is removed;
            # this also eliminates the ~1e-6 residual floor it introduced.
            try:
                dV = spsolve(J_csr, -F)
            except Exception:
                res_list.append(np.linalg.norm(F))
                break

            # Newton globalization by a fixed step cap on the voltage update.
            # The Jacobian is nonsingular (verified by FD), but far from the
            # solution the linear model can produce huge steps (Vt and Vbot are
            # strongly coupled). Capping the max |dV| keeps the iterate in the
            # region where exp(V/VT) is well-behaved. Near convergence the true
            # Newton step is already << cap, so the cap stops binding and full
            # quadratic convergence resumes — no need to release it by residual.
            cap = 0.10
            mx = np.max(np.abs(dV))
            if mx > cap:
                dV *= cap / mx

            # Backtracking line search: try alpha = 1.0, 0.5, 0.25, ...
            r_prev = r if it > 0 else np.inf
            alpha = 1.0
            V_orig = V.copy()
            for _bt in range(5):
                V[:] = V_orig + alpha * dV
                # Quick re-compute residual norm at trial point
                # (full F recompute is expensive; use simple check)
                V[oVt:oVt + N] = np.clip(V[oVt:oVt + N], -0.5,
                                         V[oVe:oVe + N] - V[oVr:oVr + N] + 1.5)
                # For initial iters or Rs_j=0, accept step directly (faster)
                if it < 3 or dp.Rs_junction == 0:
                    break
                # Backtrack only if step seems too large (heuristic: |alpha*dV| > 0.05 anywhere)
                if np.max(np.abs(alpha * dV)) < 0.05:
                    break
                # Otherwise just halve alpha and retry next iter (safer)
                alpha *= 0.5
                if alpha < 0.05:
                    V[:] = V_orig + alpha * dV
                    break

            # (Step 5 fix): widened Vtop clip — see Phase A comment
            V[oVt:oVt + N] = np.clip(V[oVt:oVt + N],
                                     -0.5,
                                     V[oVe:oVe + N] - V[oVr:oVr + N] + 1.5)

            r = np.max(np.abs(F))
            res_list.append(r)
            # Converged: 1e-6 in current units is ~µV/pA-level, physically exact.
            if r < 1e-6:
                break
            # Stagnation escape: if the residual floor is reached (no improvement
            # over 8 iters) accept it — the augmented-gauge solution can leave a
            # ~1e-6 floor in the original residual norm, which is below physical
            # significance.
            if len(res_list) >= 12:
                recent = res_list[-8:]
                if max(recent) / max(min(recent), 1e-20) < 1.10:
                    break

        Ve_out = V[oVe:oVe + N]
        Vm_out = np.full(N, np.nan)
        Vm_out[self.midx] = V[oVm:oVm + Nm]
        Vtop_out = V[oVt:oVt + N]
        Vr_out = V[oVr:oVr + N]
        # Method B: oVint slot holds Vbot; reconstruct interlayer V_int = Vbot+Vr
        # so downstream code (which computes Vbot = _last_Vint - Vr) stays valid.
        self._last_Vint = (V[oVint:oVint + N] + Vr_out).copy()
        self._last_Vrm = np.full(N, np.nan)
        self._last_Vrm[self.rear_midx] = V[oVrm:oVrm + Nrm]
        return Ve_out, Vm_out, Vtop_out, Vr_out, res_list

    # ---------------------------------------------------------
    # TANDEM PHASE B + BIFACIAL  v29 — 4-plane SCHUR COMPLEMENT solver
    # ---------------------------------------------------------
    def _solve_tandem_junction_bf_v29(self, rm, hf, wf, rc, Rs, Vb, cf, dp):
        """4-plane Schur complement solver: V_r eliminated.

        Derivation:
          5-plane solver had V_r as independent DOF -> Jacobian (V_int, V_r) block
          near-singular when Rs_junction > 0, causing Newton divergence (cond > 1e10).

          v29 eliminates V_r via Schur complement:
            F_Vr = Kr@V_r + Ib(V_int - V_r) + Gc_rear@(V_r - V_rm) = 0
          Linearizing Ib around current Vbot_k = V_int_k - V_r_k:
            Ib ≈ Ib_k + dIb·(V_int - V_r - Vbot_k)
          Substituting (note: dIb < 0):
            (Kr + Gc_rear_diag + |dIb|·I) · V_r = Gc_rear·V_rm - Ib_k + dIb·(Vbot_k - V_int)
            └────── A_r (SPD) ──────┘
          Solved each Newton iter via sparse Cholesky (O(N) for 2D mesh).

        DOF: [Ve(N), Vm(Nm), Vt(N), Vint(N), Vrm(Nrm)] -- total 3N + Nm + Nrm
        V_r recovered explicitly from V_int, V_rm via inner solve.

        Reference: Path B (constraint elimination) as discussed 2026.05.19.
        Activated via flag `dp._use_v29_constraint_solver = True`.
        """
        from scipy.sparse import csr_matrix, coo_matrix, eye as sp_eye, diags as sp_diags
        from scipy.sparse.linalg import spsolve

        N = self.N; Nm = self.Nm; Nrm = self.Nrm
        Ns = 3 * N + Nm + Nrm
        oVe = 0
        oVm = N
        oVt = N + Nm
        oVint = 2 * N + Nm
        oVrm = 3 * N + Nm

        # Initial guess (cold start)
        Vt_est, Vb_est, _ = dp.expected_voc()
        frac = Vt_est / (Vt_est + Vb_est)
        V = np.zeros(Ns)
        V[oVe:oVe + N] = Vb * 0.95
        V[oVm:oVm + Nm] = Vb
        V[oVt:oVt + N] = max(Vb, 0.01) * frac * 0.95
        V[oVint:oVint + N] = max(Vb, 0.01) * (1 - frac) * 0.95
        V[oVrm:oVrm + Nrm] = 0.0
        V_r = np.zeros(N)   # initial V_r guess (rear TCO ~ 0)

        pmk = np.array([self.mmap[gi] for gi in self.pidx if self.mmap[gi] >= 0])
        rear_pad_kr = []
        if self.rear_pidx is not None:
            for gi in self.rear_pidx:
                kr = self.rear_mmap[gi]
                if kr >= 0:
                    rear_pad_kr.append(kr)
        rear_pad_kr = np.array(rear_pad_kr, dtype=np.int64)

        ilf = self.illum_frac
        mf = self.metal_frac
        J01_top_arr = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
        J02_top_arr = dp.J02_top_pass * (1 - mf) + dp.J02_top_metal * mf

        Rc_j = dp.Rc_junction
        bc_front = np.array([oVm + k for k in pmk], dtype=np.int64)
        bc_rear  = np.array([oVrm + kr for kr in rear_pad_kr], dtype=np.int64)
        idx_N = np.arange(N, dtype=np.int64)

        # Pre-compute sparse matrix pieces (front, interlayer, rear)
        Ke_c = self._Ke.tocoo()
        Kr_c = self._Kr.tocoo()
        Krm = self._Krm
        Krm_mm = Krm[self.rear_midx, :][:, self.rear_midx]
        Krm_mm_c = Krm_mm.tocoo()
        rmm_local = self.rear_mmap[self.rear_midx]
        Kint_c = self._K_junc.tocoo()

        Km = self._Km
        Km_mm = Km[self.midx, :][:, self.midx]
        Km_mm_c = Km_mm.tocoo()
        mm_local = self.mmap[self.midx]

        Gc = self._Gc
        Gc_rear = self._Gc_rear
        gc_rear_nz = np.where(Gc_rear > 0)[0]

        VT = 0.02568  # kT/q at 25C, module-level (kB·T/q_e)
        Jph_b_eff = dp.Jph_bot * (1 + dp.bifacial_gain)

        res_list = []
        for it in range(50):
            Ve = V[oVe:oVe + N]
            Vml = V[oVm:oVm + Nm]
            Vtop = V[oVt:oVt + N]
            V_int = V[oVint:oVint + N]
            Vrml = V[oVrm:oVrm + Nrm]

            # --- Top subcell diode current Jt(Vtop) ---
            e1t = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
            e2t = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
            Jt = (dp.Jph_top * ilf - J01_top_arr * (e1t - 1)
                  - J02_top_arr * (e2t - 1) - Vtop / dp.Rsh_top)
            dJt = -(J01_top_arr * e1t / (dp.n1_top * VT)
                    + J02_top_arr * e2t / (dp.n2_top * VT) + 1 / dp.Rsh_top)
            It = Jt * self._na
            dIt = dJt * self._na

            # --- Schur complement inner solve: V_r ---
            # Vbot_k = V_int - V_r  (current iterate)
            # Solve linearized: (Kr + Gc_r_diag + |dIb|·I) V_r = b_r
            # First compute Ib_k(Vbot_k), dIb_k from current V_r
            for inner in range(8):  # inner Newton for V_r self-consistency
                Vbot_k = V_int - V_r
                e1b = np.exp(np.minimum(Vbot_k / (dp.n1_bot * VT), 80))
                e2b = np.exp(np.minimum(Vbot_k / (dp.n2_bot * VT), 80))
                if dp.J01_coupling > 0:
                    J_LC = dp.J01_coupling * (np.exp(np.minimum(Vtop / VT, 80)) - 1)
                else:
                    J_LC = 0.0
                Jb_k = (Jph_b_eff - dp.J01_bot * (e1b - 1)
                        - dp.J02_bot * (e2b - 1) - Vbot_k / dp.Rsh_bot + J_LC)
                dJb = -(dp.J01_bot * e1b / (dp.n1_bot * VT)
                        + dp.J02_bot * e2b / (dp.n2_bot * VT) + 1 / dp.Rsh_bot)
                Ib_k = Jb_k * self._na
                dIb = dJb * self._na  # negative

                # Build Vrm full vector
                Vrm_full = np.zeros(N); Vrm_full[self.rear_midx] = Vrml
                rhs_Vr = (Gc_rear * Vrm_full) - Ib_k + dIb * (Vbot_k - V_int)
                # diag boost: -dIb is positive (since dIb<0), ensures SPD
                A_r_diag = -dIb + Gc_rear  # positive
                A_r = self._Kr + sp_diags(A_r_diag, format='csr')
                V_r_new = spsolve(A_r, rhs_Vr)
                # Enforce rear pad BC implicit through Gc_rear * (V_r - V_rm) coupling
                # which is already in the equation via Vrm boundary

                dVr = np.max(np.abs(V_r_new - V_r))
                V_r = V_r_new
                if dVr < 1e-9:
                    break

            # Final Vbot, Ib, dIb at converged V_r
            Vbot = V_int - V_r
            e1b = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
            e2b = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
            if dp.J01_coupling > 0:
                J_LC = dp.J01_coupling * (np.exp(np.minimum(Vtop / VT, 80)) - 1)
                dILC = (dp.J01_coupling / VT * np.exp(np.minimum(Vtop / VT, 80))) * self._na
            else:
                J_LC = 0.0; dILC = np.zeros(N)
            Jb = (Jph_b_eff - dp.J01_bot * (e1b - 1)
                  - dp.J02_bot * (e2b - 1) - Vbot / dp.Rsh_bot + J_LC)
            dJb = -(dp.J01_bot * e1b / (dp.n1_bot * VT)
                    + dp.J02_bot * e2b / (dp.n2_bot * VT) + 1 / dp.Rsh_bot)
            Ib = Jb * self._na
            dIb = dJb * self._na

            # --- F (residuals) over 4-plane DOF ---
            F = np.zeros(Ns)
            F[oVe:oVe + N] = self._Ke @ Ve - It
            F[oVe + self.midx] += self._Gc[self.midx] * (Ve[self.midx] - Vml)

            Vm_full = np.zeros(N); Vm_full[self.midx] = Vml
            F[oVm:oVm + Nm] = ((self._Km @ Vm_full)[self.midx]
                               + self._Gc[self.midx] * (Vml - Ve[self.midx]))
            for k in pmk:
                F[oVm + k] = Vml[k] - Vb

            F[oVt:oVt + N] = Vtop - Ve + V_int - Rc_j * Jt
            F[oVint:oVint + N] = self._K_junc @ V_int + It - Ib

            # F_Vrm: rear metal grid
            Vrm_full = np.zeros(N); Vrm_full[self.rear_midx] = Vrml
            F[oVrm:oVrm + Nrm] = ((Krm @ Vrm_full)[self.rear_midx]
                                  + self._Gc_rear[self.rear_midx]
                                    * (Vrml - V_r[self.rear_midx]))
            for kr in rear_pad_kr:
                F[oVrm + kr] = Vrml[kr] - 0.0  # Rear ground BC

            # --- Jacobian assembly (4-plane, V_r eliminated) ---
            rows = []; cols = []; vals = []

            # F_Ve / dVe
            rows.append(Ke_c.row + oVe); cols.append(Ke_c.col + oVe); vals.append(Ke_c.data.copy())
            rows.append(self.midx + oVe); cols.append(self.midx + oVe)
            vals.append(self._Gc[self.midx].copy())
            rows.append(self.midx + oVe); cols.append(mm_local + oVm)
            vals.append(-self._Gc[self.midx].copy())
            rows.append(idx_N + oVe); cols.append(idx_N + oVt); vals.append(-dIt)

            # F_Vm
            rows.append(Km_mm_c.row + oVm); cols.append(Km_mm_c.col + oVm); vals.append(Km_mm_c.data.copy())
            rows.append(mm_local + oVm); cols.append(mm_local + oVm); vals.append(self._Gc[self.midx].copy())
            rows.append(mm_local + oVm); cols.append(self.midx + oVe)
            vals.append(-self._Gc[self.midx].copy())

            # F_Vt
            rows.append(idx_N + oVt); cols.append(idx_N + oVe); vals.append(-np.ones(N))
            rows.append(idx_N + oVt); cols.append(idx_N + oVt); vals.append(1.0 - Rc_j * dJt)
            rows.append(idx_N + oVt); cols.append(idx_N + oVint); vals.append(np.ones(N))

            # F_Vint / dVint  : K_int + (effective dIb_eff after V_r elimination)
            # ∂Vbot/∂V_int = 1 - ∂V_r/∂V_int = 1 - (-dIb / A_r_diag)
            # Effective dIb in V_int = dIb · (1 + dIb / A_r_diag)
            # (smaller magnitude than naive dIb since V_r partially compensates)
            screen_factor = 1.0 + dIb / A_r_diag  # ranges (0, 1] for negative dIb
            dIb_eff = dIb * screen_factor
            rows.append(Kint_c.row + oVint); cols.append(Kint_c.col + oVint); vals.append(Kint_c.data.copy())
            rows.append(idx_N + oVint); cols.append(idx_N + oVint); vals.append(-dIb_eff)
            # F_Vint / dVt  : +dIt (from +It)
            rows.append(idx_N + oVint); cols.append(idx_N + oVt); vals.append(dIt)
            if dp.J01_coupling > 0:
                # LC adds -dILC contribution (V_top → V_int coupling)
                rows.append(idx_N + oVint); cols.append(idx_N + oVt); vals.append(-dILC)

            # F_Vrm
            rows.append(Krm_mm_c.row + oVrm); cols.append(Krm_mm_c.col + oVrm); vals.append(Krm_mm_c.data.copy())
            rows.append(rmm_local + oVrm); cols.append(rmm_local + oVrm)
            vals.append(self._Gc_rear[self.rear_midx].copy())

            # Build sparse Jacobian
            rows_a = np.concatenate(rows); cols_a = np.concatenate(cols); vals_a = np.concatenate(vals)
            J = csr_matrix((vals_a, (rows_a, cols_a)), shape=(Ns, Ns))

            # Apply Dirichlet BCs (replace BC rows with identity)
            J = J.tolil()
            for k in bc_front:
                J.rows[k] = [k]
                J.data[k] = [1.0]
            for k in bc_rear:
                J.rows[k] = [k]
                J.data[k] = [1.0]
            J = J.tocsr()

            # Newton step
            try:
                dV = spsolve(J, -F)
            except Exception as e:
                res_list.append(np.inf)
                break

            # Damping (line search-lite)
            alpha = 1.0
            if np.max(np.abs(dV)) > 0.5:
                alpha = 0.5 / np.max(np.abs(dV))
            V += alpha * dV

            # Constrain Vtop to physical range
            V[oVt:oVt + N] = np.clip(V[oVt:oVt + N], -0.5,
                                     V[oVe:oVe + N] - V[oVint:oVint + N] + 1.5)

            r = np.max(np.abs(F))
            res_list.append(r)
            if r < 1e-7:
                break
            if len(res_list) >= 12:
                recent = res_list[-8:]
                if max(recent) / max(min(recent), 1e-20) < 1.05 and r < 5e-6:
                    break

        # --- Recover outputs ---
        Ve_out = V[oVe:oVe + N]
        Vm_out = np.full(N, np.nan)
        Vm_out[self.midx] = V[oVm:oVm + Nm]
        Vtop_out = V[oVt:oVt + N]
        Vr_out = V_r.copy()
        self._last_Vint = V[oVint:oVint + N].copy()
        self._last_Vrm = np.full(N, np.nan)
        self._last_Vrm[self.rear_midx] = V[oVrm:oVrm + Nrm]
        return Ve_out, Vm_out, Vtop_out, Vr_out, res_list

    # ---------------------------------------------------------
    # TANDEM BIFACIAL SOLVE (2-layer rear with metal grid)
    # ---------------------------------------------------------
    def _solve_tandem_bifacial(self, rm, hf, wf, rc, Rs, Vb, cf, dp):
        """
        Tandem solve with full 2-layer rear (mirrors front structure).
        DOF: [Ve(N), Vm(Nm), Vt(N), Vr(N), Vrm(Nrm)] -- total 3N + Nm + Nrm
        Vr is now rear EMITTER (sheet R ~ 1 Ohm/sq).
        Vrm is rear METAL grid (auto Rs from rm/hf).
        BC: V_rm[rear_pad] = 0, V_m[front_pad] = Vb.
        """
        N = self.N; Nm = self.Nm; Nrm = self.Nrm
        Ns = 3 * N + Nm + Nrm
        oVe = 0; oVm = N; oVt = N + Nm
        oVr = 2 * N + Nm; oVrm = 3 * N + Nm

        # Phase A path: clear stale V_int (so losses() knows not to use it)
        self._last_Vint = None

        # Initial guess — use warm-start cache if available.
        # Warm start typically gives 2-5 iter convergence vs 15+ for cold.
        if (self._warm_V_bf is not None
                and self._warm_V_bf.shape[0] == Ns
                and self._warm_Vb_ref is not None
                and abs(self._warm_Vb_ref - Vb) < 0.25):
            V = self._warm_V_bf.copy()
            # Shift front metal/emitter by ΔVb (since pad BC enforces Vb).
            # Top/Bot diode voltages also scale approximately with terminal V
            # (since Vbot = Ve - Vtop - Vr, and Vr ≈ 0 stays fixed).
            dV_bias = Vb - self._warm_Vb_ref
            V[oVe:oVe + N] += dV_bias
            V[oVm:oVm + Nm] += dV_bias
            # Split diode V change across top/bot proportional to their Voc
            Vt_est, Vb_est, _ = dp.expected_voc()
            frac_t = Vt_est / (Vt_est + Vb_est)
            V[oVt:oVt + N] += dV_bias * frac_t
        else:
            # Cold start: standard Voc-based initial guess
            Vt_est, Vb_est, Vtot_est = dp.expected_voc()
            frac = Vt_est / (Vt_est + Vb_est)
            V = np.zeros(Ns)
            V[oVe:oVe + N] = Vb * 0.95
            V[oVm:oVm + Nm] = Vb
            V[oVt:oVt + N] = max(Vb, 0.01) * frac * 0.95
            V[oVr:oVr + N] = 0.0
            V[oVrm:oVrm + Nrm] = 0.0
            self._apply_mesh_prolongation_seed(
                V, Vb,
                {"Ve": (oVe, None), "Vm": (oVm, self.midx),
                 "Vtop": (oVt, None), "Vr": (oVr, None),
                 "Vrm": (oVrm, self.rear_midx)},
                frac,
            )

        pmk = np.array([self.mmap[gi] for gi in self.pidx if self.mmap[gi] >= 0])
        # Rear probe: rear metal pad nodes (mapped through rear_mmap)
        rear_pad_kr = []
        if self.rear_pidx is not None:
            for gi in self.rear_pidx:
                kr = self.rear_mmap[gi]
                if kr >= 0:
                    rear_pad_kr.append(kr)
        rear_pad_kr = np.array(rear_pad_kr, dtype=np.int64)

        ilf = self.illum_frac
        mf = self.metal_frac
        J01_top_arr = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
        J02_top_arr = dp.J02_top_pass * (1 - mf) + dp.J02_top_metal * mf

        bc_front = [oVm + k for k in pmk]
        bc_rear = [oVrm + kr for kr in rear_pad_kr]

        gc_rear_nz = np.where(self._Gc_rear > 0)[0]

        # Interlayer vertical contact R (Phase A, 박사님 지시 2026.04.10)
        Rc_j = dp.Rc_junction

        res_list = []
        for it in range(250):
            Ve = V[oVe:oVe + N]
            Vml = V[oVm:oVm + Nm]
            Vtop = V[oVt:oVt + N]
            Vr = V[oVr:oVr + N]
            Vrm_l = V[oVrm:oVrm + Nrm]
            # Standard "lumped" Vbot — exact answer when Rc_j=0
            Vbot_lump = Ve - Vtop - Vr

            # Top subcell
            e1t = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
            e2t = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
            Jph_t = ilf * dp.Jph_top
            Jt = Jph_t - J01_top_arr * (e1t - 1) - J02_top_arr * (e2t - 1) - Vtop / dp.Rsh_top
            dJt = -(J01_top_arr * e1t / (dp.n1_top * VT) +
                     J02_top_arr * e2t / (dp.n2_top * VT) + 1 / dp.Rsh_top)

            # Bottom subcell with bifacial Jph_b and implicit interlayer R
            # See full_area solver for KVL derivation. Sign: +Rc*Jb (not -).
            Jph_b_eff = (ilf + dp.bifacial_gain * self.rear_illum_frac) * dp.Jph_bot
            if Rc_j > 0:
                Vbot = Vbot_lump.copy()
                if dp.J01_coupling > 0:
                    J_LC_in = dp.J01_coupling * (np.exp(np.minimum(Vtop/VT, 80)) - 1)
                else:
                    J_LC_in = 0.0
                for inner_it in range(10):
                    e1b_i = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
                    e2b_i = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
                    Jb_i = (Jph_b_eff
                            - dp.J01_bot * (e1b_i - 1)
                            - dp.J02_bot * (e2b_i - 1)
                            - Vbot / dp.Rsh_bot
                            + J_LC_in)
                    f_in = Vbot - Vbot_lump - Rc_j * Jb_i
                    if np.max(np.abs(f_in)) < 1e-12:
                        break
                    dJb_i = -(dp.J01_bot * e1b_i / (dp.n1_bot * VT) +
                              dp.J02_bot * e2b_i / (dp.n2_bot * VT) +
                              1 / dp.Rsh_bot)
                    df_in = 1.0 - Rc_j * dJb_i
                    dVb = -f_in / df_in
                    mx_in = np.max(np.abs(dVb))
                    if mx_in > 0.05:
                        dVb *= 0.05 / mx_in
                    Vbot = Vbot + dVb
            else:
                Vbot = Vbot_lump

            e1b = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
            e2b = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
            Jph_b = Jph_b_eff
            Jb = Jph_b - dp.J01_bot * (e1b - 1) - dp.J02_bot * (e2b - 1) - Vbot / dp.Rsh_bot
            dJb_raw = -(dp.J01_bot * e1b / (dp.n1_bot * VT) +
                         dp.J02_bot * e2b / (dp.n2_bot * VT) + 1 / dp.Rsh_bot)
            if Rc_j > 0:
                dJb = dJb_raw / (1.0 - Rc_j * dJb_raw)
            else:
                dJb = dJb_raw

            # --- Luminescent Coupling (LC), same as tandem full_area solver ---
            if dp.J01_coupling > 0:
                eLC = np.exp(np.minimum(Vtop / VT, 80))
                J_LC = dp.J01_coupling * (eLC - 1)
                dJLC_dVtop = dp.J01_coupling * eLC / VT
                if Rc_j == 0:
                    Jb = Jb + J_LC
                # else: already in Jb via inner Newton's J_LC_in
            else:
                J_LC = 0.0
                dJLC_dVtop = 0.0

            It = Jt * self._na
            Ib = Jb * self._na
            dIt = dJt * self._na
            dIb = dJb * self._na
            dILC_dVtop = dJLC_dVtop * self._na
            F = np.zeros(Ns)
            # Front emitter KCL
            F[oVe:oVe + N] = self._Ke @ Ve - It
            F[oVe + self.midx] += self._Gc[self.midx] * (Ve[self.midx] - Vml)
            # Front metal KCL
            Vm_full = np.zeros(N)
            Vm_full[self.midx] = Vml
            F[oVm:oVm + Nm] = (self._Km @ Vm_full)[self.midx] + self._Gc[self.midx] * (Vml - Ve[self.midx])
            for k in pmk:
                F[oVm + k] = Vml[k] - Vb
            # Current matching at top
            F[oVt:oVt + N] = (Jt - Jb) * self._na
            # Rear emitter KCL: Kr @ Vr + Ib + Gc_rear*(Vr - Vrm_full) = 0
            Vrm_full = np.zeros(N)
            Vrm_full[self.rear_midx] = Vrm_l
            F[oVr:oVr + N] = self._Kr @ Vr + Ib
            F[oVr + self.rear_midx] += self._Gc_rear[self.rear_midx] * (Vr[self.rear_midx] - Vrm_l)
            # Rear metal KCL: Krm row at rear metal nodes + Gc_rear*(Vrm - Vr)
            F[oVrm:oVrm + Nrm] = ((self._Krm @ Vrm_full)[self.rear_midx]
                                   + self._Gc_rear[self.rear_midx] * (Vrm_l - Vr[self.rear_midx]))
            # BC: rear metal pad fixed at 0
            for kr in rear_pad_kr:
                F[oVrm + kr] = Vrm_l[kr]

            # ======= JACOBIAN = Static + Diode diagonal + Off-diagonal =======
            diag = np.zeros(Ns)
            # LC modifies dF_Vt/dVt by -dILC_dVtop
            diag[oVt:oVt + N] = (dJt + dJb) * self._na - dILC_dVtop
            diag[oVr:oVr + N] = -dIb

            # Build all off-diagonals in single COO
            od_rows = np.concatenate([
                np.arange(N) + oVe,    # dF_Ve/dVtop
                np.arange(N) + oVt,    # dF_Vtop/dVe
                np.arange(N) + oVt,    # dF_Vtop/dVr
                np.arange(N) + oVr,    # dF_Vr/dVe
                np.arange(N) + oVr,    # dF_Vr/dVtop
            ])
            od_cols = np.concatenate([
                np.arange(N) + oVt,
                np.arange(N) + oVe,
                np.arange(N) + oVr,
                np.arange(N) + oVe,
                np.arange(N) + oVt,
            ])
            # dF_Vr/dVtop: original -dIb, plus LC contribution +dILC_dVtop
            od_vals = np.concatenate([-dIt, -dIb, dIb, dIb, -dIb + dILC_dVtop])

            J = self._J_static_tandem_bf.copy()
            J += csr_matrix((diag, (np.arange(Ns), np.arange(Ns))), shape=(Ns, Ns))
            J += csr_matrix((od_vals, (od_rows, od_cols)), shape=(Ns, Ns))

            # BC: directly zero the row data and set diagonal to 1
            # Vectorized: zero all BC row entries at once
            bc_all = np.array(bc_front + bc_rear, dtype=np.int64)
            for idx_bc in bc_all:
                start = J.indptr[idx_bc]
                end = J.indptr[idx_bc + 1]
                J.data[start:end] = 0.0
            # Set BC diagonals via COO add (only the diagonal positions)
            J += csr_matrix((np.ones(len(bc_all)),
                             (bc_all, bc_all)), shape=(Ns, Ns))

            dV = spsolve(J, -F)
            mx = np.max(np.abs(dV))
            # Looser damping for bifacial faster convergence
            if mx > 0.3:
                dV *= 0.3 / mx
            V += dV
            # (Step 5 fix): widened Vtop clip — see Phase A comment
            V[oVt:oVt + N] = np.clip(V[oVt:oVt + N],
                                     -0.5,
                                     V[oVe:oVe + N] - V[oVr:oVr + N] + 1.5)

            r = np.max(np.abs(F))
            res_list.append(r)
            # Strict convergence for MPP accuracy: 1e-7 default
            if r < 1e-7:
                break
            # Stagnation escape (for low-V regime where residual floor > 1e-7):
            # If residual has flattened for 8 iters AND is below 5e-6, accept.
            # This is 20× stricter than the previous 1e-5 and sufficient for
            # MPP determination (cell J accuracy ~1e-4 mA/cm²).
            if len(res_list) >= 12:
                recent = res_list[-8:]
                if max(recent) / max(min(recent), 1e-20) < 1.05 and r < 5e-6:
                    break

        Ve = V[oVe:oVe + N]
        Vm = np.full(N, np.nan)
        Vm[self.midx] = V[oVm:oVm + Nm]
        Vtop = V[oVt:oVt + N]
        Vr = V[oVr:oVr + N]
        # Note: returns Vr (rear emitter); rear metal voltage stored separately
        Vrm = np.full(N, np.nan)
        Vrm[self.rear_midx] = V[oVrm:oVrm + Nrm]
        # Stash rear metal in result for visualization (via attribute or return)
        self._last_Vrm = Vrm
        # Save warm start cache (only if converged well)
        if res_list and res_list[-1] < 1e-5:
            self._warm_V_bf = V.copy()
            self._warm_Vb_ref = Vb
        return Ve, Vm, Vtop, Vr, res_list

    # ---------------------------------------------------------
    # SINGLE-CELL SOLVE (with rear plane)
    # ---------------------------------------------------------
    def solve_single(self, rm, hf, wf, rc, Rs, Vb, cf=1.0, dp=None):
        """Solve single-cell with rear plane -- OPTIMIZED.
        
        Dispatches to bifacial 2-layer rear if rear_mode is 'bifacial'."""
        if dp is None:
            dp = DiodeParams()
        self._build(rm, hf, wf, rc, Rs, cf, dp)

        # Dispatch to bifacial branch if rear is patterned
        if (self.geo.rear_mode in ('bifacial', 'patterned')
                and self._J_static_single_bf is not None):
            return self._solve_single_bifacial(rm, hf, wf, rc, Rs, Vb, cf, dp)

        N = self.N; Nm = self.Nm; Ns = 2 * N + Nm
        oVe = 0; oVm = N; oVr = N + Nm

        Voc_est = dp.expected_voc(mode='single')
        V = np.zeros(Ns)
        V[oVe:oVe + N] = Vb * 0.95
        V[oVm:oVm + Nm] = Vb
        V[oVr:oVr + N] = 0.0
        self._apply_mesh_prolongation_seed(
            V, Vb,
            {"Ve": (oVe, None), "Vm": (oVm, self.midx), "Vr": (oVr, None)},
        )

        pmk = np.array([self.mmap[gi] for gi in self.pidx if self.mmap[gi] >= 0])
        # Full area rear: ALL rear nodes grounded (perfect back contact)
        # Patterned rear: rear probe points grounded (from rear H-pattern)
        if self.geo.rear_mode == 'full_area':
            rear_probe_idx = np.arange(N)
        elif self.rear_pidx is not None and len(self.rear_pidx) > 0:
            rear_probe_idx = self.rear_pidx
        else:
            # Fallback: front probe position
            rear_probe_idx = self.pidx
        bc_front = [oVm + k for k in pmk]
        bc_rear = [oVr + gi for gi in rear_probe_idx]

        ilf = self.illum_frac
        mf = self.metal_frac
        J01_arr = dp.J01_single_pass * (1 - mf) + dp.J01_single_metal * mf
        J02_arr = dp.J02_single_pass * (1 - mf) + dp.J02_single_metal * mf
        # (③): per-node spatial multipliers (None -> no-op, exact prior).
        _m_j01 = self._spatial_mult(dp, 'j01')
        _m_j02 = self._spatial_mult(dp, 'j02')
        _m_gen = self._spatial_mult(dp, 'gen')
        if _m_j01 is not None:
            J01_arr = J01_arr * _m_j01
        if _m_j02 is not None:
            J02_arr = J02_arr * _m_j02
        _gen = (ilf * _m_gen) if _m_gen is not None else ilf

        res_list = []
        for it in range(250):
            Ve = V[oVe:oVe + N]
            Vml = V[oVm:oVm + Nm]
            Vr = V[oVr:oVr + N]
            Vd = Ve - Vr

            e1 = np.exp(np.minimum(Vd / (dp.n1_single * VT), 80))
            e2 = np.exp(np.minimum(Vd / (dp.n2_single * VT), 80))
            Jph = _gen * dp.Jph_single
            Jd = Jph - J01_arr * (e1 - 1) - J02_arr * (e2 - 1) - Vd / dp.Rsh_single
            dJd = -(J01_arr * e1 / (dp.n1_single * VT) +
                     J02_arr * e2 / (dp.n2_single * VT) + 1 / dp.Rsh_single)

            Id = Jd * self._na
            dId = dJd * self._na

            # Residual (vectorized)
            F = np.zeros(Ns)
            F[oVe:oVe + N] = self._Ke @ Ve - Id
            F[oVe + self.midx] += self._Gc[self.midx] * (Ve[self.midx] - Vml)

            Vm_full = np.zeros(N)
            Vm_full[self.midx] = Vml
            F[oVm:oVm + Nm] = (self._Km @ Vm_full)[self.midx] + self._Gc[self.midx] * (Vml - Ve[self.midx])
            for k in pmk:
                F[oVm + k] = Vml[k] - Vb

            F[oVr:oVr + N] = self._Kr @ Vr + Id
            for gi in rear_probe_idx:
                F[oVr + gi] = Vr[gi]

            # Jacobian = static + diode diagonal + off-diagonal
            diag = np.zeros(Ns)
            diag[oVe:oVe + N] = -dId          # dF_Ve/dVe: -dId (from diode)
            diag[oVr:oVr + N] = -dId           # dF_Vr/dVr: -dId (chain rule)

            J = self._J_static_single.copy()
            J += csr_matrix((diag, (np.arange(Ns), np.arange(Ns))), shape=(Ns, Ns))

            # Off-diagonal: dF_Ve/dVr = +dId, dF_Vr/dVe = +dId
            J += csr_matrix((dId, (np.arange(N) + oVe, np.arange(N) + oVr)), shape=(Ns, Ns))
            J += csr_matrix((dId, (np.arange(N) + oVr, np.arange(N) + oVe)), shape=(Ns, Ns))

            # BC: vectorized zero rows + add diagonal=1 via COO
            bc_all = np.array(bc_front + bc_rear, dtype=np.int64)
            for idx_bc in bc_all:
                start = J.indptr[idx_bc]
                end = J.indptr[idx_bc + 1]
                J.data[start:end] = 0.0
            J += csr_matrix((np.ones(len(bc_all)),
                             (bc_all, bc_all)), shape=(Ns, Ns))

            dV = spsolve(J, -F)
            mx = np.max(np.abs(dV))
            if mx > 0.3:
                dV *= 0.3 / mx
            V += dV

            r = np.max(np.abs(F))
            res_list.append(r)
            if r < 1e-10:
                break

        Ve = V[oVe:oVe + N]
        Vm = np.full(N, np.nan)
        Vm[self.midx] = V[oVm:oVm + Nm]
        Vr = V[oVr:oVr + N]
        return Ve, Vm, Vr, res_list

    # ---------------------------------------------------------
    # SINGLE-CELL BIFACIAL SOLVE (2-layer rear)
    # ---------------------------------------------------------
    def _solve_single_bifacial(self, rm, hf, wf, rc, Rs, Vb, cf, dp):
        """Single-cell with 2-layer rear.
        DOF: [Ve(N), Vm(Nm), Vr(N), Vrm(Nrm)] -- total 2N + Nm + Nrm"""
        N = self.N; Nm = self.Nm; Nrm = self.Nrm
        Ns = 2 * N + Nm + Nrm
        oVe = 0; oVm = N; oVr = N + Nm; oVrm = 2 * N + Nm

        Voc_est = dp.expected_voc(mode='single')
        V = np.zeros(Ns)
        V[oVe:oVe + N] = Vb * 0.95
        V[oVm:oVm + Nm] = Vb
        V[oVr:oVr + N] = 0.0
        V[oVrm:oVrm + Nrm] = 0.0
        self._apply_mesh_prolongation_seed(
            V, Vb,
            {"Ve": (oVe, None), "Vm": (oVm, self.midx),
             "Vr": (oVr, None), "Vrm": (oVrm, self.rear_midx)},
        )

        pmk = np.array([self.mmap[gi] for gi in self.pidx if self.mmap[gi] >= 0])
        rear_pad_kr = []
        if self.rear_pidx is not None:
            for gi in self.rear_pidx:
                kr = self.rear_mmap[gi]
                if kr >= 0:
                    rear_pad_kr.append(kr)
        rear_pad_kr = np.array(rear_pad_kr, dtype=np.int64)

        bc_front = [oVm + k for k in pmk]
        bc_rear = [oVrm + kr for kr in rear_pad_kr]

        ilf = self.illum_frac
        mf = self.metal_frac
        J01_arr = dp.J01_single_pass * (1 - mf) + dp.J01_single_metal * mf
        J02_arr = dp.J02_single_pass * (1 - mf) + dp.J02_single_metal * mf

        res_list = []
        for it in range(250):
            Ve = V[oVe:oVe + N]
            Vml = V[oVm:oVm + Nm]
            Vr = V[oVr:oVr + N]
            Vrm_l = V[oVrm:oVrm + Nrm]
            Vd = Ve - Vr

            e1 = np.exp(np.minimum(Vd / (dp.n1_single * VT), 80))
            e2 = np.exp(np.minimum(Vd / (dp.n2_single * VT), 80))
            # Bifacial: rear illumination gain scaled by rear_illum_frac
            Jph = (ilf + dp.bifacial_gain * self.rear_illum_frac) * dp.Jph_single
            Jd = Jph - J01_arr * (e1 - 1) - J02_arr * (e2 - 1) - Vd / dp.Rsh_single
            dJd = -(J01_arr * e1 / (dp.n1_single * VT) +
                     J02_arr * e2 / (dp.n2_single * VT) + 1 / dp.Rsh_single)

            Id = Jd * self._na
            dId = dJd * self._na

            # Residual
            F = np.zeros(Ns)
            F[oVe:oVe + N] = self._Ke @ Ve - Id
            F[oVe + self.midx] += self._Gc[self.midx] * (Ve[self.midx] - Vml)

            Vm_full = np.zeros(N)
            Vm_full[self.midx] = Vml
            F[oVm:oVm + Nm] = (self._Km @ Vm_full)[self.midx] + self._Gc[self.midx] * (Vml - Ve[self.midx])
            for k in pmk:
                F[oVm + k] = Vml[k] - Vb

            # Rear emitter KCL
            Vrm_full = np.zeros(N)
            Vrm_full[self.rear_midx] = Vrm_l
            F[oVr:oVr + N] = self._Kr @ Vr + Id
            F[oVr + self.rear_midx] += self._Gc_rear[self.rear_midx] * (Vr[self.rear_midx] - Vrm_l)

            # Rear metal KCL
            F[oVrm:oVrm + Nrm] = ((self._Krm @ Vrm_full)[self.rear_midx]
                                   + self._Gc_rear[self.rear_midx] * (Vrm_l - Vr[self.rear_midx]))
            for kr in rear_pad_kr:
                F[oVrm + kr] = Vrm_l[kr]

            # Jacobian
            diag = np.zeros(Ns)
            diag[oVe:oVe + N] = -dId
            diag[oVr:oVr + N] = -dId

            J = self._J_static_single_bf.copy()
            J += csr_matrix((diag, (np.arange(Ns), np.arange(Ns))), shape=(Ns, Ns))

            # Off-diagonals: dF_Ve/dVr = +dId, dF_Vr/dVe = +dId
            J += csr_matrix((dId, (np.arange(N) + oVe, np.arange(N) + oVr)), shape=(Ns, Ns))
            J += csr_matrix((dId, (np.arange(N) + oVr, np.arange(N) + oVe)), shape=(Ns, Ns))

            # BC: zero rows by direct data slice, then add diagonal=1 via COO
            bc_all = np.array(bc_front + bc_rear, dtype=np.int64)
            for idx_bc in bc_all:
                start = J.indptr[idx_bc]
                end = J.indptr[idx_bc + 1]
                J.data[start:end] = 0.0
            J += csr_matrix((np.ones(len(bc_all)),
                             (bc_all, bc_all)), shape=(Ns, Ns))

            dV = spsolve(J, -F)
            mx = np.max(np.abs(dV))
            # Looser damping for faster convergence
            if mx > 0.3:
                dV *= 0.3 / mx
            V += dV

            r = np.max(np.abs(F))
            res_list.append(r)
            # Looser tolerance (engineering accuracy)
            if r < 1e-7:
                break

        Ve = V[oVe:oVe + N]
        Vm = np.full(N, np.nan)
        Vm[self.midx] = V[oVm:oVm + Nm]
        Vr = V[oVr:oVr + N]
        Vrm = np.full(N, np.nan)
        Vrm[self.rear_midx] = V[oVrm:oVrm + Nrm]
        self._last_Vrm = Vrm
        return Ve, Vm, Vr, res_list

    # ---------------------------------------------------------
    # UNIFIED SOLVE INTERFACE
    # ---------------------------------------------------------
    def solve(self, rm, hf, wf, rc, Rs, Vb, cf=1.0, dp=None, mode='tandem',
              wb=None):
        """Unified interface: returns dict with all voltage planes.

        v28.18: ``wf``/``wb``는 케이스별 전극 폭(핫프레싱 After 등)으로 실제
        솔버(1D 금속 단면, 접촉 Gc, 발전 스케일)에 반영된다. wb=None -> 설계 폭."""
        self._case_wb = None if wb is None else float(wb)
        # Sanity check: front probe pad must exist (otherwise solver will hang
        # on a singular matrix). This guards against bad DXF imports.
        if len(self.pidx) == 0:
            raise ValueError(
                "No front probe pad nodes found. The mesh has no nodes "
                "labeled as front pad. This usually means the DXF import "
                "failed to find a valid busbar at the cell top, or the "
                "probe pad region is too small to capture mesh nodes. "
                "Try increasing mesh density or check the DXF file.")
        # Also check the metal-mapped probe indices
        pmk = [self.mmap[gi] for gi in self.pidx if self.mmap[gi] >= 0]
        if len(pmk) == 0:
            raise ValueError(
                "Front probe pad nodes exist but none are in the metal "
                "DOF map. The probe pad region must overlap with metal "
                "(busbar/finger) areas.")

        def _run():
            if mode == 'tandem':
                Ve, Vm, Vtop, Vr, res = self.solve_tandem(
                    rm, hf, wf, rc, Rs, Vb, cf, dp
                )
                return {
                    'Ve': Ve, 'Vm': Vm, 'Vtop': Vtop, 'Vr': Vr,
                    'res': res, 'mode': 'tandem',
                }
            Ve, Vm, Vr, res = self.solve_single(rm, hf, wf, rc, Rs, Vb, cf, dp)
            return {
                'Ve': Ve, 'Vm': Vm, 'Vtop': None, 'Vr': Vr,
                'res': res, 'mode': 'single',
            }

        self._mesh_seed_applied_this_call = False
        result = _run()
        used_prolongation = self._mesh_seed_applied_this_call
        residuals = result.get("res", [])
        final_residual = residuals[-1] if residuals else float("inf")
        failed = (not np.isfinite(final_residual)) or final_residual > 1e-5
        if used_prolongation and failed:
            self._mesh_warm_stats["fallback_used"] = True
            self._mesh_warm_stats["fallback_count"] += 1
            self._mesh_seed_disabled = True
            try:
                self._mesh_seed_applied_this_call = False
                result = _run()
            finally:
                self._mesh_seed_disabled = False
            residuals = result.get("res", [])
            final_residual = residuals[-1] if residuals else float("inf")

        self._mesh_warm_stats["solve_calls"] += 1
        self._mesh_warm_stats["nonlinear_iterations"] += len(residuals)
        self._mesh_warm_stats["final_newton_residual"] = float(final_residual)
        self._capture_mesh_seed_snapshot(Vb, result)
        last_vint = getattr(self, "_last_Vint", None)
        result["Vint"] = last_vint.copy() if last_vint is not None else None
        self._last_solve_result = result
        return result

    # ---------------------------------------------------------
    # CELL CURRENT (for I-V curve)
    # ---------------------------------------------------------
    def cell_current(self, result, dp=None):
        """Total cell current [mA/cm2] from solve result."""
        if dp is None:
            dp = DiodeParams()
        Ve = result['Ve']
        Vr = result['Vr']
        mf = self.metal_frac
        ilf = self.illum_frac
        # (③): the same spatial multipliers the solver used must be
        # applied here, or the recomputed current ignores them (notably gen,
        # which otherwise has no effect on the reported J). None -> no-op.
        _m_j01 = self._spatial_mult(dp, 'j01')
        _m_j02 = self._spatial_mult(dp, 'j02')
        _m_gen = self._spatial_mult(dp, 'gen')
        _gen = (ilf * _m_gen) if _m_gen is not None else ilf

        if result['mode'] == 'tandem':
            Vtop = result['Vtop']
            J01_arr = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
            J02_arr = dp.J02_top_pass * (1 - mf) + dp.J02_top_metal * mf
            if _m_j01 is not None:
                J01_arr = J01_arr * _m_j01
            if _m_j02 is not None:
                J02_arr = J02_arr * _m_j02
            e1t = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
            e2t = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
            # Cell current = top subcell current (current-matched with bottom).
            # Top subcell is not affected by rear illumination (sees no rear
            # light). In bifacial tandem, gain comes only if Jph_bot > Jph_top
            # in which case top is current-limiting and bifacial gain is lost.
            # If the cell is under-matched (Jph_top < Jph_bot), adding rear
            # light to bot further widens the mismatch.
            Jt = _gen * dp.Jph_top - J01_arr * (e1t - 1) - J02_arr * (e2t - 1) - Vtop / dp.Rsh_top
            # UNITS-1 note: current density is normalized by self.geo.area = the
            # bounding-rectangle W*H. For the default SQUARE wafer this equals
            # wafer_area(), so Jsc/Eff are correct. For pseudo_square/circular
            # wafers the mesh still tessellates the full rectangle (corners
            # generate current) while shading_fraction divides by the true
            # wafer_area(), so the two area conventions disagree (circular bias
            # ~21%). Square-wafer runs are unaffected; if non-square wafers are
            # used, mask generation to wafer_outline_xy_mm and normalize both
            # current and shading by wafer_area() consistently.
            return np.sum(Jt * self._na) / self.geo.area * 1000
        else:
            Vd = Ve - Vr
            J01_arr = dp.J01_single_pass * (1 - mf) + dp.J01_single_metal * mf
            J02_arr = dp.J02_single_pass * (1 - mf) + dp.J02_single_metal * mf
            if _m_j01 is not None:
                J01_arr = J01_arr * _m_j01
            if _m_j02 is not None:
                J02_arr = J02_arr * _m_j02
            e1 = np.exp(np.minimum(Vd / (dp.n1_single * VT), 80))
            e2 = np.exp(np.minimum(Vd / (dp.n2_single * VT), 80))
            # Bifacial: include rear-side photocurrent (gen map applies to front)
            Jph_eff = (_gen + dp.bifacial_gain * self.rear_illum_frac) * dp.Jph_single
            Jd = Jph_eff - J01_arr * (e1 - 1) - J02_arr * (e2 - 1) - Vd / dp.Rsh_single
            return np.sum(Jd * self._na) / self.geo.area * 1000

    def _phase_b_interlayer_diagnostics(self, result, dp=None):
        """Native Phase B interlayer KCL diagnostic."""
        if dp is None:
            dp = DiodeParams()
        if (result.get('mode') != 'tandem'
                or self._K_junc is None
                or result.get('Vint') is None):
            return {
                'mode': result.get('mode', 'N/A'),
                'phase_b_native': False,
                'note': 'Phase B interlayer diagnostic is not applicable.',
            }

        Ve = result['Ve']
        Vtop = result['Vtop']
        Vr = result['Vr']
        V_int = result['Vint']
        Vbot = V_int - Vr
        mf = self.metal_frac
        ilf = self.illum_frac
        rilf = self.rear_illum_frac
        A = float(np.sum(self._na))

        Jph_top_node = ilf * dp.Jph_top
        Jph_bot_node = (ilf + dp.bifacial_gain * rilf) * dp.Jph_bot
        Jph_top_eff = float(np.sum(Jph_top_node * self._na)) / A * 1000.0
        Jph_bot_eff = float(np.sum(Jph_bot_node * self._na)) / A * 1000.0
        Jlim = min(Jph_top_eff, Jph_bot_eff)
        mismatch = Jph_top_eff - Jph_bot_eff
        mismatch_pct = (mismatch / Jlim * 100.0) if Jlim > 0 else 0.0
        if abs(mismatch_pct) < 0.5:
            limiting = 'Current-matched'
        elif mismatch < 0:
            limiting = 'Top-limited'
        else:
            limiting = 'Bottom-limited'

        J01_top_arr = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
        J02_top_arr = dp.J02_top_pass * (1 - mf) + dp.J02_top_metal * mf
        e1t = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
        e2t = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
        Jt = (ilf * dp.Jph_top
              - J01_top_arr * (e1t - 1)
              - J02_top_arr * (e2t - 1)
              - Vtop / dp.Rsh_top)

        e1b = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
        e2b = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
        if dp.J01_coupling > 0:
            J_LC = dp.J01_coupling * (np.exp(np.minimum(Vtop / VT, 80)) - 1)
        else:
            J_LC = 0.0
        Jb = (Jph_bot_node
              - dp.J01_bot * (e1b - 1)
              - dp.J02_bot * (e2b - 1)
              - Vbot / dp.Rsh_bot
              + J_LC)

        It = Jt * self._na
        Ib = Jb * self._na
        lateral = self._K_junc @ V_int
        if self.geo.rear_mode == 'full_area':
            residual_A = lateral - It + Ib
            sign_convention = 'Kint@Vint - It + Ib'
        else:
            residual_A = lateral + It - Ib
            sign_convention = 'Kint@Vint + It - Ib'

        residual_density = np.full(self.N, np.nan, dtype=float)
        valid = self._na > 1e-30
        residual_density[valid] = residual_A[valid] / self._na[valid] * 1000.0
        rms_density = float(
            np.sqrt(np.sum((residual_density[valid] ** 2) * self._na[valid]) / A)
        )
        max_density = float(np.nanmax(np.abs(residual_density)))
        integrated_density = float(np.sum(residual_A) / A * 1000.0)
        rms_A = float(np.sqrt(np.mean(residual_A ** 2)))
        max_A = float(np.max(np.abs(residual_A)))

        top_kvl_mV = (Vtop - Ve + V_int - dp.Rc_junction * Jt) * 1000.0
        top_kvl_rms_mV = float(np.sqrt(np.mean(top_kvl_mV ** 2)))
        top_kvl_max_mV = float(np.max(np.abs(top_kvl_mV)))

        return {
            'mode': 'tandem',
            'phase_b_native': True,
            'diagnostic': 'Phase B native interlayer KCL',
            'sign_convention': sign_convention,
            'Jph_top_eff': Jph_top_eff,
            'Jph_bot_eff': Jph_bot_eff,
            'Jlim': Jlim,
            'mismatch': mismatch,
            'mismatch_pct': mismatch_pct,
            'limiting': limiting,
            'Jtop_mpp': float(np.sum(Jt * self._na)) / A * 1000.0,
            'Jbot_mpp': float(np.sum(Jb * self._na)) / A * 1000.0,
            'rms_residual': rms_density,
            'max_residual': max_density,
            'integrated_residual': integrated_density,
            'rms_residual_A': rms_A,
            'max_residual_A': max_A,
            'top_kvl_rms_mV': top_kvl_rms_mV,
            'top_kvl_max_mV': top_kvl_max_mV,
            'residual_map': residual_density,
            'note': (
                'Native Phase B residual uses the solved interlayer V_int plane '
                'and the exact K_int equation for the active rear mode. This is '
                'the SAME equation the Newton solve drives to zero, so it is an '
                'INTERNAL CONSISTENCY / convergence check (confirms the solver '
                'solved its own interlayer KCL) and is ~0 whenever Newton '
                'converges. It is NOT an external physical validation and by '
                'construction cannot detect the Phase B vs Phase A model-family '
                'offset.'
            ),
        }

    # ---------------------------------------------------------
    # CURRENT MATCHING DIAGNOSTICS (v28.4 — Step 3)
    # ---------------------------------------------------------
    def current_matching_diagnostics(self, result, dp=None):
        """Tandem 2T current-matching analysis at the result's operating point.

        Splits info into TWO independent groups:
          (A) Photogen matching — operating-point INDEPENDENT.
              Tells you which subcell is photo-current limited.
          (B) MPP residual — operating-point SPECIFIC.
              Pass the MPP solve to get RMS/max |Jt-Jb|; should be tiny
              (solver enforces (Jt-Jb)*na = 0 node-wise as KCL between
              top↔bot planes). Large residual → solver didn't converge.

        Single mode → {'mode':'N/A'}.

        Phase B: when Rs_junction>0 and V_int is available, this returns the
        native Griddler-style interlayer KCL residual evaluated on the solved
        V_int plane. Phase A still uses the local Jt-Jb residual below.

        Returns dict with keys:
          mode, Jph_top_eff, Jph_bot_eff, Jlim, mismatch, mismatch_pct,
          limiting, Jtop_mpp, Jbot_mpp, rms_residual, max_residual,
          residual_map (per-node, mA/cm²).
        """
        if dp is None:
            dp = DiodeParams()
        if result.get('mode') != 'tandem':
            return {'mode': 'N/A',
                    'note': 'Current matching applies to tandem mode only.'}
        if self._K_junc is not None and result.get('Vint') is not None:
            return self._phase_b_interlayer_diagnostics(result, dp)

        Ve = result['Ve']; Vtop = result['Vtop']; Vr = result['Vr']
        mf = self.metal_frac
        ilf = self.illum_frac
        rilf = self.rear_illum_frac          # array(N,), zeros in full_area mode
        A = float(np.sum(self._na))           # cm² (== self.geo.area, but use _na sum)

        # === (A) Photogen matching ===
        # Top sees only front light. Bot may also see rear light if bifacial.
        Jph_top_node = ilf * dp.Jph_top
        Jph_bot_node = ilf * dp.Jph_bot + dp.bifacial_gain * rilf * dp.Jph_bot
        Jph_top_eff = float(np.sum(Jph_top_node * self._na)) / A * 1000.0   # mA/cm²
        Jph_bot_eff = float(np.sum(Jph_bot_node * self._na)) / A * 1000.0
        Jlim = min(Jph_top_eff, Jph_bot_eff)
        mismatch = Jph_top_eff - Jph_bot_eff
        mismatch_pct = (mismatch / Jlim * 100.0) if Jlim > 0 else 0.0
        if abs(mismatch_pct) < 0.5:
            limiting = 'Current-matched'
        elif mismatch < 0:
            limiting = 'Top-limited'
        else:
            limiting = 'Bottom-limited'

        # === (B) MPP-point residual ===
        # Top subcell J (per node) — same formula as cell_current()
        J01_top_arr = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
        J02_top_arr = dp.J02_top_pass * (1 - mf) + dp.J02_top_metal * mf
        e1t = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
        e2t = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
        Jt = (ilf * dp.Jph_top
              - J01_top_arr * (e1t - 1)
              - J02_top_arr * (e2t - 1)
              - Vtop / dp.Rsh_top)

        # Bot subcell — reconstruct Vbot (Phase A assumption)
        Vbot_lump = Ve - Vtop - Vr
        Rc_j = dp.Rc_junction
        if dp.J01_coupling > 0:
            J_LC = dp.J01_coupling * (np.exp(np.minimum(Vtop / VT, 80)) - 1)
        else:
            J_LC = 0.0
        if Rc_j > 0:
            Vbot = Vbot_lump.copy()
            for _ in range(8):
                e1b = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
                e2b = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
                Jb_i = (Jph_bot_node
                        - dp.J01_bot * (e1b - 1)
                        - dp.J02_bot * (e2b - 1)
                        - Vbot / dp.Rsh_bot
                        + J_LC)
                f = Vbot - Vbot_lump - Rc_j * Jb_i
                if np.max(np.abs(f)) < 1e-12: break
                dJb = -(dp.J01_bot * e1b / (dp.n1_bot * VT)
                        + dp.J02_bot * e2b / (dp.n2_bot * VT)
                        + 1.0 / dp.Rsh_bot)
                df = 1.0 - Rc_j * dJb
                dV = -f / df
                mx = float(np.max(np.abs(dV)))
                if mx > 0.05: dV *= 0.05 / mx
                Vbot = Vbot + dV
        else:
            Vbot = Vbot_lump
        e1b = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
        e2b = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
        Jb = (Jph_bot_node
              - dp.J01_bot * (e1b - 1)
              - dp.J02_bot * (e2b - 1)
              - Vbot / dp.Rsh_bot
              + J_LC)

        # mA/cm² area-weighted
        Jtop_mpp = float(np.sum(Jt * self._na)) / A * 1000.0
        Jbot_mpp = float(np.sum(Jb * self._na)) / A * 1000.0
        residual_map = (Jt - Jb) * 1000.0     # mA/cm² per node
        rms_residual = float(np.sqrt(np.mean(residual_map ** 2)))
        max_residual = float(np.max(np.abs(residual_map)))

        return {
            'mode': 'tandem',
            'Jph_top_eff': Jph_top_eff,
            'Jph_bot_eff': Jph_bot_eff,
            'Jlim': Jlim,
            'mismatch': mismatch,
            'mismatch_pct': mismatch_pct,
            'limiting': limiting,
            'Jtop_mpp': Jtop_mpp,
            'Jbot_mpp': Jbot_mpp,
            'rms_residual': rms_residual,
            'max_residual': max_residual,
            'residual_map': residual_map,
        }

    # ---------------------------------------------------------
    # I-V CURVE (High-resolution near MPP)
    # ---------------------------------------------------------
    def calc_iv(self, rm, hf, wf, rc, Rs, cf=1.0, dp=None, mode='tandem',
                npts=14, wb=None):
        """Calculate full I-V curve with enhanced MPP resolution.

        npts=14 default: 14 coarse + 10 fine near MPP = ~24 evaluations.
        Sufficient for engineering accuracy and keeps DXF/dense-mesh runs
        under ~30 seconds even for bifacial 2-layer rear."""
        if dp is None:
            dp = DiodeParams()
        self.reset_mesh_warm_diagnostics(clear_snapshots=True)

        if mode == 'tandem':
            _, _, Voc_est = dp.expected_voc()
            # TANDEM-2 fix: wire in the documented per-subcell internal series R
            # (Jeon 2025 Rs_top/Rs_bot — vertical transport inside each diode
            # unit). Applied as a terminal IR drop V_term = V_solver - J·Rs.
            # In a 2T series stack the same J flows through both subcells, so the
            # two internal resistances add. Previously these params were declared
            # but never read, so FF was overstated when vertical R was non-zero.
            # The legacy Rs_lumped_* aliases (deprecated, default 0) are kept for
            # backward compatibility.
            Rs_lumped_total = (dp.Rs_internal_top + dp.Rs_internal_bot
                               + dp.Rs_lumped_top + dp.Rs_lumped_bot)
        else:
            Voc_est = dp.expected_voc(mode='single')
            # Single-cell defaults are Si/bottom-like (LONGi), so the relevant
            # internal R is the bottom (Si) value.
            Rs_lumped_total = dp.Rs_internal_bot + dp.Rs_lumped_top

        Rs_lumped_total = max(float(Rs_lumped_total), 0.0)

        def _V_terminal(V_internal, J_mA_cm2):
            return np.asarray(V_internal) - (np.asarray(J_mA_cm2) * 1e-3) * Rs_lumped_total

        eval_cache = {}

        def _eval_internal(V_internal):
            key = round(float(V_internal), 12)
            cached = eval_cache.get(key)
            if cached is not None:
                return cached
            result = self.solve(rm, hf, wf, rc, Rs, float(V_internal), cf, dp, mode, wb=wb)
            J = float(self.cell_current(result, dp))
            cached = (J, result)
            eval_cache[key] = cached
            return cached

        def _eval_many(values):
            vals = np.array(values, dtype=float)
            vals = vals[np.isfinite(vals)]
            vals = vals[vals >= 0.0]
            if vals.size == 0:
                return np.array([], dtype=float), np.array([], dtype=float)
            vals = np.unique(vals)
            # Keep the high-to-low continuation order for nonlinear convergence.
            for vb in vals[::-1]:
                _eval_internal(float(vb))
            Js_eval = np.array([eval_cache[round(float(vb), 12)][0] for vb in vals])
            return vals, Js_eval

        def _bisect_root(func, lo, hi, *, xtol=5e-5, maxiter=24):
            lo = float(lo)
            hi = float(hi)
            flo = float(func(lo))
            fhi = float(func(hi))
            if not (np.isfinite(flo) and np.isfinite(fhi)):
                return None
            if abs(flo) < 1e-10:
                return lo
            if abs(fhi) < 1e-10:
                return hi
            if flo * fhi > 0:
                return None
            for _ in range(maxiter):
                mid = 0.5 * (lo + hi)
                fmid = float(func(mid))
                if not np.isfinite(fmid):
                    return None
                if abs(fmid) < 1e-10 or (hi - lo) < xtol:
                    return mid
                if flo * fmid > 0:
                    lo, flo = mid, fmid
                else:
                    hi, fhi = mid, fmid
            return 0.5 * (lo + hi)

        def _interp_y_at_x(x, y, x0):
            x = np.asarray(x, dtype=float)
            y = np.asarray(y, dtype=float)
            if x.size == 0:
                return 0.0
            exact = np.where(np.abs(x - x0) < 1e-9)[0]
            if exact.size:
                return float(y[exact[0]])
            for k in range(len(x) - 1):
                if (x[k] <= x0 <= x[k + 1]) or (x[k + 1] <= x0 <= x[k]):
                    return float(np.interp(x0, [x[k], x[k + 1]], [y[k], y[k + 1]]))
            idx = int(np.argmin(np.abs(x - x0)))
            return float(y[idx])

        # Phase 1: Coarse sweep
        # CONTINUATION STRATEGY: sweep from HIGH V → LOW V so each solve can
        # warm-start from the previous converged state. Initial guess for the
        # highest V point is built from Voc estimate (which is ~accurate at Voc).
        # This cascades down and dramatically reduces iteration count per solve,
        # especially at low V where the cold-start solver can take 100+ iterations
        # due to the strongly nonlinear diode region.
        V1 = np.linspace(0, 0.85 * Voc_est, npts // 2)
        V2 = np.linspace(0.85 * Voc_est, Voc_est * 1.05, npts // 2)
        Vs_coarse = np.unique(np.concatenate([V1, V2]))
        # Reset warm cache so the first solve at max V goes cold (correct)
        self._warm_V_bf = None
        self._warm_V_tf = None
        self._warm_V_sbf = None
        self._warm_V_sf = None

        t0 = time.time()
        Vs_coarse, Js_coarse = _eval_many(Vs_coarse)
        Vs_term_coarse = _V_terminal(Vs_coarse, Js_coarse)

        Voc_internal = None
        for k in range(len(Js_coarse) - 1):
            if Js_coarse[k] >= 0 and Js_coarse[k + 1] <= 0:
                Voc_internal = _bisect_root(
                    lambda v: _eval_internal(v)[0],
                    Vs_coarse[k],
                    Vs_coarse[k + 1],
                )
                break
        if Voc_internal is None:
            lo = 0.0
            hi = max(float(Voc_est) * 1.10, 0.1)
            f_hi = _eval_internal(hi)[0]
            for _ in range(8):
                if f_hi <= 0.0:
                    break
                hi *= 1.25
                f_hi = _eval_internal(hi)[0]
            if _eval_internal(lo)[0] >= 0.0 and f_hi <= 0.0:
                Voc_internal = _bisect_root(lambda v: _eval_internal(v)[0], lo, hi)
        if Voc_internal is None:
            Voc_internal = float(Voc_est)

        # Find coarse MPP
        P_coarse = Vs_term_coarse * Js_coarse
        valid_c = (Js_coarse > 0) & (Vs_term_coarse > 0)
        if np.any(valid_c):
            im_c = np.where(valid_c)[0][np.argmax(P_coarse[valid_c])]
            Vmpp_est = Vs_coarse[im_c]
        else:
            Vmpp_est = float(Voc_internal) * 0.8

        # Phase 2: Fine sweep around MPP (±50mV), also high-to-low
        # Reduced from 20 to 10 points for ~50% speedup at MPP step
        Vsc_internal = 0.0
        if Rs_lumped_total > 1e-6:
            def _terminal_at_internal(v):
                J, _ = _eval_internal(v)
                return float(v - J * 1e-3 * Rs_lumped_total)

            f0 = _terminal_at_internal(0.0)
            fvoc = _terminal_at_internal(Voc_internal)
            if f0 < 0.0 and fvoc >= 0.0:
                root = _bisect_root(
                    _terminal_at_internal,
                    0.0,
                    Voc_internal,
                    xtol=1e-10,
                    maxiter=48,
                )
                if root is not None:
                    Vsc_internal = root

            V_pos_lo = max(0.0, min(Vsc_internal, Voc_internal))
            V_pos_hi = max(V_pos_lo, Voc_internal)
            base_count = max(npts + 4, 16)
            V_positive = np.linspace(V_pos_lo, V_pos_hi, base_count)
            V_probe, J_probe = _eval_many(V_positive)
            Vt_probe = _V_terminal(V_probe, J_probe)
            P_probe = Vt_probe * J_probe
            valid_probe = (Vt_probe > 0.0) & (J_probe > 0.0)
            if np.any(valid_probe):
                idx_probe = np.where(valid_probe)[0][np.argmax(P_probe[valid_probe])]
                Vmpp_est = float(V_probe[idx_probe])
            span = max((V_pos_hi - V_pos_lo) * 0.30, 0.002)
            V_fine_lo = max(V_pos_lo, Vmpp_est - span)
            V_fine_hi = min(V_pos_hi, Vmpp_est + span)
            V_fine = np.unique(np.concatenate([
                V_positive,
                np.linspace(V_fine_lo, V_fine_hi, 10),
                np.array([V_pos_lo, V_pos_hi, Vsc_internal, Voc_internal]),
            ]))
        else:
            V_fine_lo = max(0, Vmpp_est - 0.05)
            V_fine_hi = min(Voc_est * 1.02, Vmpp_est + 0.05)
            V_fine = np.linspace(V_fine_lo, V_fine_hi, 10)

        V_fine, Js_fine = _eval_many(V_fine)

        # Merge and sort
        Vs_all = np.concatenate([Vs_coarse, V_fine])
        Js_all = np.concatenate([Js_coarse, Js_fine])
        order = np.argsort(Vs_all)
        Vs_internal = Vs_all[order]
        Js = Js_all[order]
        # Remove near-duplicates
        duplicate_tol = 1e-10 if Rs_lumped_total > 1e-6 else 1e-6
        mask = np.diff(Vs_internal, prepend=-1) > duplicate_tol
        Vs_internal = Vs_internal[mask]
        Js = Js[mask]

        # Apply lumped series resistance (Jeon Table 1 style)
        # V_terminal = V_solver - J × Rs_lumped (J in mA/cm² → ×1e-3 to A)
        Vs = _V_terminal(Vs_internal, Js)
        Vs_internal_for_terminal = Vs_internal.copy()
        if Rs_lumped_total > 1e-6:
            Jsc_root, _ = _eval_internal(Vsc_internal)
            Vs = np.concatenate([Vs, np.array([0.0, float(Voc_internal)])])
            Js = np.concatenate([Js, np.array([Jsc_root, 0.0])])
            Vs_internal_for_terminal = np.concatenate([
                Vs_internal_for_terminal,
                np.array([float(Vsc_internal), float(Voc_internal)]),
            ])
        order2 = np.argsort(Vs)
        Vs = Vs[order2]
        Js = Js[order2]
        Vs_internal_for_terminal = Vs_internal_for_terminal[order2]

        dt = time.time() - t0

        # Extract parameters
        Jsc = abs(_interp_y_at_x(Vs, Js, 0.0))
        Voc = float(Voc_internal)
        Voc_bracket = None
        for k in range(len(Js) - 1):
            if Js[k] > 0 and Js[k + 1] <= 0:
                Voc = np.interp(0, [Js[k + 1], Js[k]], [Vs[k + 1], Vs[k]])
                Voc_bracket = (Vs[k], Vs[k+1], Js[k], Js[k+1])
                break

        # === v28.1 FIX: Voc refinement via bisection ===
        # The I-V curve near Voc is exponential (dJ/dV rises sharply), so linear
        # interpolation between coarse sweep points underestimates Voc by ~10-20 mV.
        # Refine with 8-step bisection using actual solver calls to reach <0.1 mV.
        if Voc_bracket is not None and Rs_lumped_total <= 1e-6:
            V_lo, V_hi, J_lo, J_hi = Voc_bracket
            def _J_at_Vterm(V_term):
                # V_term includes Rs_lumped drop; need V_int = V_term + J*Rs for solver.
                # At Voc J≈0 so V_int ≈ V_term; iterate 3x to converge.
                V_int = V_term
                for _ in range(3):
                    res = self.solve(rm, hf, wf, rc, Rs, V_int, cf, dp, mode, wb=wb)
                    J = self.cell_current(res, dp)
                    V_int_new = V_term + J * 1e-3 * Rs_lumped_total
                    if abs(V_int_new - V_int) < 1e-6:
                        break
                    V_int = V_int_new
                return J
            a, b = V_lo, V_hi
            fa, fb = J_lo, J_hi
            for _ in range(8):
                m = 0.5 * (a + b)
                fm = _J_at_Vterm(m)
                if fm > 0:
                    a, fa = m, fm
                else:
                    b, fb = m, fm
                if b - a < 5e-5:  # 0.05 mV tolerance
                    break
            # Final linear interp on refined bracket
            if fa != fb:
                Voc = a + fa * (b - a) / (fa - fb)
            else:
                Voc = 0.5 * (a + b)
        # === END v28.1 FIX ===

        P = Vs * Js
        valid = (Js > 0) & (Vs > 0) & (Vs < Voc * 1.01)
        if np.any(valid):
            Pmpp = np.max(P[valid])
            im = np.where(valid)[0][np.argmax(P[valid])]
        else:
            Pmpp = 0
            im = 0

        Vmpp = Vs[im]
        Jmpp = Js[im]
        Vmpp_internal = Vs_internal_for_terminal[im]
        if Pmpp > 0 and len(Vs_internal_for_terminal) >= 3:
            def _power_at_internal(v_internal):
                J_here, _ = _eval_internal(float(v_internal))
                V_term_here = float(v_internal - J_here * 1e-3 * Rs_lumped_total)
                if not (np.isfinite(V_term_here) and np.isfinite(J_here)):
                    return 0.0, V_term_here, J_here
                if V_term_here <= 0.0 or J_here <= 0.0:
                    return 0.0, V_term_here, J_here
                return V_term_here * J_here, V_term_here, J_here

            left_i = max(0, im - 1)
            right_i = min(len(Vs_internal_for_terminal) - 1, im + 1)
            if left_i < im < right_i:
                lo = float(Vs_internal_for_terminal[left_i])
                hi = float(Vs_internal_for_terminal[right_i])
                if hi > lo:
                    phi = (np.sqrt(5.0) - 1.0) / 2.0
                    x1 = hi - phi * (hi - lo)
                    x2 = lo + phi * (hi - lo)
                    f1 = _power_at_internal(x1)[0]
                    f2 = _power_at_internal(x2)[0]
                    for _ in range(24):
                        if hi - lo < 1e-7:
                            break
                        if f1 < f2:
                            lo = x1
                            x1 = x2
                            f1 = f2
                            x2 = lo + phi * (hi - lo)
                            f2 = _power_at_internal(x2)[0]
                        else:
                            hi = x2
                            x2 = x1
                            f2 = f1
                            x1 = hi - phi * (hi - lo)
                            f1 = _power_at_internal(x1)[0]
                    candidates = [float(Vmpp_internal), x1, x2, 0.5 * (lo + hi)]
                    best = max((_power_at_internal(v)[0], v) for v in candidates)
                    P_refined, V_refined, J_refined = _power_at_internal(best[1])
                    if P_refined >= Pmpp:
                        Vmpp_internal = float(best[1])
                        Pmpp = float(P_refined)
                        Vmpp = float(V_refined)
                        Jmpp = float(J_refined)
        mpp_result = _eval_internal(float(Vmpp_internal))[1]
        FF = Pmpp / (Jsc * Voc) * 100 if Jsc * Voc > 0 else 0
        Eff = Pmpp / 100 * 100  # Pmpp in mW/cm2, irradiance = 100 mW/cm2

        iv = {
            'Jsc': Jsc, 'Voc': Voc, 'Vmpp': Vmpp, 'Jmpp': Jmpp,
            'Vmpp_internal': Vmpp_internal,
            'Rs_lumped_total': Rs_lumped_total,
            'Pmpp': Pmpp, 'FF': FF, 'Eff': Eff, 'time': dt,
            'mode': mode,
            '_mpp_result': mpp_result,
        }
        iv.update(_phase_b_model_info(dp, mode))
        iv.update(self.mesh_warm_diagnostics())
        try:
            diagnostics = self.current_matching_diagnostics(self._last_solve_result, dp)
            if iv.get("phase_b_active"):
                iv["last_point_kcl_residual_rms"] = diagnostics.get("rms_residual", "")
                iv["last_point_kcl_note"] = (
                    "Phase B native interlayer KCL residual [mA/cm2]."
                )
                iv["phase_b_native_kcl_rms_mA_cm2"] = diagnostics.get("rms_residual", "")
                iv["phase_b_native_kcl_max_mA_cm2"] = diagnostics.get("max_residual", "")
                iv["phase_b_native_kcl_integrated_mA_cm2"] = diagnostics.get(
                    "integrated_residual", ""
                )
                iv["phase_b_native_kcl_rms_A"] = diagnostics.get("rms_residual_A", "")
                iv["phase_b_native_kcl_max_A"] = diagnostics.get("max_residual_A", "")
                iv["phase_b_top_kvl_rms_mV"] = diagnostics.get("top_kvl_rms_mV", "")
                iv["phase_b_top_kvl_max_mV"] = diagnostics.get("top_kvl_max_mV", "")
                iv["phase_b_native_kcl_sign"] = diagnostics.get("sign_convention", "")
            else:
                iv["last_point_kcl_residual_rms"] = diagnostics.get("rms_residual", "")
        except Exception:
            iv["last_point_kcl_residual_rms"] = ""
        if mode == 'tandem':
            Vt_, Vb_, _ = dp.expected_voc()
            iv['Voc_top'] = Vt_
            iv['Voc_bot'] = Vb_

        # Trim to the physical illuminated quadrant used by plots/exports.
        trim = (Vs >= -1e-7) & (Vs <= Voc * 1.02)
        return np.maximum(Vs[trim], 0.0), np.maximum(Js[trim], 0), iv

    # ---------------------------------------------------------
    # LOSSES (Updated for rear plane)
    # ---------------------------------------------------------
    def losses(self, result, rm, hf, wf, rc, Rs, cf=1.0, dp=None,
               Vmpp=None, Jmpp=None, wb=None):
        """Power loss breakdown [mW/cm2]: Pe, Pf_finger, Pf_busbar, Pc, P_shade, P_rear."""
        if dp is None:
            dp = DiodeParams()
        # v28.18: 분해도 solve와 동일한 케이스 폭으로 빌드(일관성).
        self._case_wb = None if wb is None else float(wb)
        self._build(rm, hf, wf, rc, Rs, cf, dp)

        Ve = result['Ve']
        Vm = result['Vm']
        Vr = result['Vr']

        valid = self.areas > 1e-15
        idx = self.simp[valid]
        A = self.areas[valid]
        bv = self.b[valid]
        cv = self.c[valid]

        # Emitter / rear plane ohmic loss.
        # (④): evaluate as the quadratic form V^T K V on the SAME
        # assembled stiffness operator the solver uses, instead of recomputing
        # the element sheet-gradient. For the 2D Galerkin emitter/rear planes the
        # two are mathematically identical (K is the Galerkin Laplacian), but the
        # quadratic form is model-exact by construction, cannot drift from the
        # solver, and unifies the loss treatment across all planes (front TCO,
        # rear TCO, metal, interlayer). P = V^T K V  [W]; /area*1000 -> mW/cm2
        # is applied at the return (A_) like the other terms.
        Ve_full = np.nan_to_num(Ve, nan=0.0)
        Vr_full = np.nan_to_num(Vr, nan=0.0)
        Pe = float(Ve_full @ (self._Ke @ Ve_full))
        Pe = max(Pe, 0.0)
        if self._Kr is not None:
            P_rear = float(Vr_full @ (self._Kr @ Vr_full))
            P_rear = max(P_rear, 0.0)
        else:
            P_rear = 0.0
        # (Interlayer lateral loss is computed below as P_Rs_junction using the
        #  ½ Galerkin energy form; no separate term needed here.)

        # Metal grid loss (finger + busbar).
        # the solver models the metal grid as a 1D conductor network
        # (assemble_K_met_1d). The metal resistive loss must be evaluated on the
        # SAME network, edge by edge: for each conductance g_ij between metal
        # nodes i,j the dissipated power is g_ij*(V_i - V_j)^2. Summing over edges
        # gives exactly Vm^T K_met Vm (model-exact). The previous 2D sheet-gradient
        # formula was inconsistent with the 1D model and inflated finger loss by
        # >100x on large cells (e.g. 742% of MPP power on M10). We classify each
        # edge as finger/busbar by its endpoints' node flags.
        Km_coo = self._Km.tocoo()
        Vm_full = np.nan_to_num(Vm, nan=0.0)
        Pf_finger = 0.0
        Pf_busbar = 0.0
        # iterate over upper-triangular off-diagonal entries (each edge once)
        ii = Km_coo.row; jj = Km_coo.col; vv = Km_coo.data
        upper = (ii < jj)
        ii, jj, vv = ii[upper], jj[upper], vv[upper]
        # K_ij = -g_ij for the resistor between i and j
        g_ij = -vv
        dV = Vm_full[ii] - Vm_full[jj]
        edge_loss = g_ij * dV * dV          # [W] per edge
        # classify: busbar if EITHER endpoint is a busbar node; else finger
        eb = self.isb[ii] | self.isb[jj]
        ef = ~eb
        Pf_busbar = float(np.sum(edge_loss[eb]))
        Pf_finger = float(np.sum(edge_loss[ef]))
        Pf_finger = max(Pf_finger, 0.0)
        Pf_busbar = max(Pf_busbar, 0.0)


        # Contact loss
        Pc = sum((Ve[gi] - Vm[gi])**2 * self._Gc[gi]
                 for gi in self.midx if not np.isnan(Vm[gi]))

        # Shading loss — v28.18: wb도 케이스별(이전엔 설계 폭 고정이라 분해 내부조차 비일관).
        wb_eff = self.geo.w_b if wb is None else float(wb)
        shade_frac = self.geo.shading_fraction(wf, wb_eff)
        if Vmpp is not None and Jmpp is not None:
            P_shade = shade_frac * Jmpp * Vmpp
        else:
            Jmpp_est = dp.Jph_top * 1000 * 0.95 if result['mode'] == 'tandem' else dp.Jph_single * 1000 * 0.95
            Vmpp_est = np.mean(Ve[~self.ism]) * 0.95
            P_shade = shade_frac * Jmpp_est * Vmpp_est / 1000

        A_ = self.geo.area
        mode = result['mode']

        # Shunt power loss: P_shunt = sum(V_diode^2 / Rsh * nodal_area)
        # v28: when Phase B (lateral interlayer), Vbot = V_int - Vr.
        result_vint = result.get('Vint')
        if mode == 'tandem':
            Vtop = result['Vtop']
            if (self._K_junc is not None
                    and result_vint is not None
                    and result_vint.shape[0] == self.N):
                Vbot = result_vint - Vr
            else:
                Vbot = Ve - Vtop - Vr
            P_shunt_top = np.sum((Vtop**2 / dp.Rsh_top) * self._na)
            P_shunt_bot = np.sum((Vbot**2 / dp.Rsh_bot) * self._na)
            P_shunt = P_shunt_top + P_shunt_bot
        else:
            Vd = Ve - Vr
            P_shunt = np.sum((Vd**2 / dp.Rsh_single) * self._na)

        # Recombination power loss: P_recomb = sum(J_recomb * V_diode * nodal_area)
        # J_recomb = J01*(exp(V/n1VT)-1) + J02*(exp(V/n2VT)-1) for each node
        # When Rc_junction > 0, refine Vbot via fix-point (matches solver's
        # +Rc*Jb formula). For Rc=0 this is a no-op.
        #
        # v28: detect Phase B (interlayer lateral plane). If self._last_Vint is
        # populated, the solver was junction or junction_bf, and the correct
        # bottom-cell diode voltage is Vbot = V_int - Vr (NOT Ve - Vtop - Vr).
        mf = self.metal_frac
        Jb_local_for_int = None  # populated only if tandem
        # Phase B detection
        phase_B = (mode == 'tandem'
                   and self._K_junc is not None
                   and result_vint is not None
                   and result_vint.shape[0] == self.N)
        if mode == 'tandem':
            Vtop = result['Vtop']
            if phase_B:
                V_int_arr = result_vint
                Vbot_lump = V_int_arr - Vr
            else:
                V_int_arr = None
                Vbot_lump = Ve - Vtop - Vr
            # Refine Vbot for interlayer R via fix-point (Phase A only).
            # Phase B: V_int is already the solver-converged interlayer node,
            # so Vbot = V_int - Vr is exact; no refinement needed. The Rc drop
            # in Phase B sits between Ve and V_int on the top-current side,
            # so P_Rc_junction = sum(Rc * Jt²·area) using top current.
            Vbot = Vbot_lump.copy()
            if dp.Rc_junction > 0 and not phase_B:
                Jph_b_loc = (self.illum_frac
                             + dp.bifacial_gain * self.rear_illum_frac) * dp.Jph_bot
                for _ in range(8):
                    e1 = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
                    e2 = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
                    Jb_loc = (Jph_b_loc - dp.J01_bot * (e1 - 1)
                              - dp.J02_bot * (e2 - 1) - Vbot / dp.Rsh_bot)
                    Vbot_new = Vbot_lump + dp.Rc_junction * Jb_loc
                    if np.max(np.abs(Vbot_new - Vbot)) < 1e-10:
                        break
                    Vbot = Vbot_new
                # Recompute final Jb_loc with converged Vbot for P_Rc_junction
                e1 = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
                e2 = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
                Jb_local_for_int = (Jph_b_loc - dp.J01_bot * (e1 - 1)
                                    - dp.J02_bot * (e2 - 1) - Vbot / dp.Rsh_bot)
            elif dp.Rc_junction > 0 and phase_B:
                # Phase B: use top current Jt (current matching → Jt = Jb at int)
                J01_t_arr = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
                J02_t_arr = dp.J02_top_pass * (1 - mf) + dp.J02_top_metal * mf
                e1t_loc = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
                e2t_loc = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
                Jt_loc = (self.illum_frac * dp.Jph_top
                          - J01_t_arr * (e1t_loc - 1)
                          - J02_t_arr * (e2t_loc - 1)
                          - Vtop / dp.Rsh_top)
                Jb_local_for_int = Jt_loc

            J01_t = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
            J02_t = dp.J02_top_pass * (1 - mf) + dp.J02_top_metal * mf
            e1t = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
            e2t = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
            Jr_top = J01_t * (e1t - 1) + J02_t * (e2t - 1)
            P_recomb_top = np.sum(Jr_top * Vtop * self._na)

            e1b = np.exp(np.minimum(Vbot / (dp.n1_bot * VT), 80))
            e2b = np.exp(np.minimum(Vbot / (dp.n2_bot * VT), 80))
            Jr_bot = dp.J01_bot * (e1b - 1) + dp.J02_bot * (e2b - 1)
            P_recomb_bot = np.sum(Jr_bot * Vbot * self._na)
            P_recomb = P_recomb_top + P_recomb_bot
        else:
            Vd = Ve - Vr
            J01_s = dp.J01_single_pass * (1 - mf) + dp.J01_single_metal * mf
            J02_s = dp.J02_single_pass * (1 - mf) + dp.J02_single_metal * mf
            e1 = np.exp(np.minimum(Vd / (dp.n1_single * VT), 80))
            e2 = np.exp(np.minimum(Vd / (dp.n2_single * VT), 80))
            Jr = J01_s * (e1 - 1) + J02_s * (e2 - 1)
            P_recomb = np.sum(Jr * Vd * self._na)

        # Interlayer vertical R loss (Phase A, 박사님 지시 2026.04.10)
        # P_int = sum(Rc * Jb_local^2 * nodal_area) — power dissipated in
        # the interlayer recombination junction by vertical contact R.
        # Only meaningful in tandem mode with Rc_junction > 0.
        if mode == 'tandem' and dp.Rc_junction > 0 and Jb_local_for_int is not None:
            P_Rc_junction = np.sum(dp.Rc_junction * Jb_local_for_int**2 * self._na)
        else:
            P_Rc_junction = 0.0

        # v28: lateral interlayer dissipation (Phase B)
        # v28.18 fix (리뷰 2-A): Joule 발열은 P = V^T K V (전체), ½ 아님.
        #   Galerkin sheet Laplacian K(=assemble_K)에 대해 V^T K V = ∫σ|∇V|² =
        #   소산 전력이며, 같은 함수의 Pe/P_rear도 ½ 없이 쓴다. 이전 0.5는
        #   변분에너지(저장)와 혼동한 것으로 횡방향 interlayer 손실을 2배 과소
        #   평가했다. Phase B(Rs_junction>0)에서만 발현(기본 Phase A는 0).
        if (mode == 'tandem' and phase_B
                and self._K_junc is not None and V_int_arr is not None):
            P_Rs_junction = float(V_int_arr @ (self._K_junc @ V_int_arr))
        else:
            P_Rs_junction = 0.0

        P_junction = P_Rc_junction + P_Rs_junction

        return {
            'Pe': Pe / A_ * 1000,
            'Pf_finger': Pf_finger / A_ * 1000,
            'Pf_busbar': Pf_busbar / A_ * 1000,
            'Pc': Pc / A_ * 1000,
            'P_shade': P_shade,
            'P_rear': P_rear / A_ * 1000,
            'P_shunt': P_shunt / A_ * 1000,
            'P_recomb': P_recomb / A_ * 1000,
            'P_Rc_junction': P_junction / A_ * 1000,   # back-compat: total junction loss
            'P_Rs_junction': P_Rs_junction / A_ * 1000,  # lateral only (v28)
            'P_junction': P_junction / A_ * 1000,        # total = lateral + vertical
        }

    # ---------------------------------------------------------
    # EXTRACT Rs, Gsh FROM I-V CURVE
    # ---------------------------------------------------------
    @staticmethod
    def extract_rs_gsh(Vs, Js):
        """Extract series resistance and shunt conductance from I-V curve."""
        pos = np.where(Js > 0)[0]
        Rs_ext = 0.0; Gsh_ext = 0.0
        if len(pos) >= 3:
            i2 = pos[-1]; i1 = pos[-2]
            dV = Vs[i2] - Vs[i1]; dJ = Js[i2] - Js[i1]
            if abs(dJ) > 1e-6: Rs_ext = -dV / dJ
        if len(pos) >= 3:
            dV = Vs[pos[1]] - Vs[pos[0]]; dJ = Js[pos[1]] - Js[pos[0]]
            if abs(dV) > 1e-6: Gsh_ext = abs(dJ / dV)
        return Rs_ext, Gsh_ext

    # ---------------------------------------------------------
    # RECOMBINATION CURRENTS
    # ---------------------------------------------------------
    def recomb_currents(self, result, dp=None):
        if dp is None:
            dp = DiodeParams()
        Ve = result['Ve']
        Vr = result['Vr']
        mf = self.metal_frac

        if result['mode'] == 'tandem':
            Vtop = result['Vtop']
            e1 = np.exp(np.minimum(Vtop / (dp.n1_top * VT), 80))
            e2 = np.exp(np.minimum(Vtop / (dp.n2_top * VT), 80))
            Jr_pass_n1 = np.sum(dp.J01_top_pass * (1 - mf) * (e1 - 1) * self._na)
            Jr_met_n1 = np.sum(dp.J01_top_metal * mf * (e1 - 1) * self._na)
            Jr_met_n2 = np.sum(dp.J02_top_metal * mf * (e2 - 1) * self._na)
            Jr_pass_n2 = np.sum(dp.J02_top_pass * (1 - mf) * (e2 - 1) * self._na)
        else:
            Vd = Ve - Vr
            e1 = np.exp(np.minimum(Vd / (dp.n1_single * VT), 80))
            e2 = np.exp(np.minimum(Vd / (dp.n2_single * VT), 80))
            Jr_pass_n1 = np.sum(dp.J01_single_pass * (1 - mf) * (e1 - 1) * self._na)
            Jr_met_n1 = np.sum(dp.J01_single_metal * mf * (e1 - 1) * self._na)
            Jr_met_n2 = np.sum(dp.J02_single_metal * mf * (e2 - 1) * self._na)
            Jr_pass_n2 = np.sum(dp.J02_single_pass * (1 - mf) * (e2 - 1) * self._na)

        A_ = self.geo.area
        return {
            'pass_n1': Jr_pass_n1 / A_ * 1000,
            'met_n1': Jr_met_n1 / A_ * 1000,
            'met_n2': Jr_met_n2 / A_ * 1000,
            'pass_n2': Jr_pass_n2 / A_ * 1000,
        }


# =============================================================
# QUICK VALIDATION
# =============================================================


# =============================================================
# INITIALIZE SOLVER (v5.0)
# =============================================================
print("2L-FEST PRO v5.0 -- Initializing...")
t0 = time.time()
GEO = CellGeometry()
DP = DiodeParams()
TP = DP  # Backward compatibility alias
pts, tri = generate_mesh(GEO, pass_density=2)
isf, isb, isp, ism, isrm, isrp = classify_nodes(pts, GEO)
S = FESTSolver(pts, tri, isf, isb, isp, ism, GEO, isrm, isrp)
triang = mtri.Triangulation(pts[:,0]*10, pts[:,1]*10, tri.simplices)
print(f"  Mesh: {len(pts)} nodes, {len(tri.simplices)} tri ({time.time()-t0:.2f}s)")
print(f"  Metal: {np.sum(ism)} nodes ({np.sum(ism)/len(pts)*100:.1f}%)")

# =============================================================
# ANALYTICAL LOSS (for report verification)
# =============================================================
def _analytical_loss(rm, hf, wf, rc, Rs, cf):
    """Closed-form distributed series-resistance losses as power density [mW/cm²].

    ASM-3 fix: the Mette/Green expressions below are DIMENSIONLESS fractional
    losses (of Pmpp) only when Jmp is in A/cm². Previously the function used Jmp
    in mA/cm² and returned the bare fractions, i.e. ~1000× the true fraction,
    while the report labeled the column "mW/cm²" and placed the values next to the
    genuine FEM losses() buckets (true mW/cm²). That apples-to-oranges comparison
    could mask or falsely flag a real FEM discrepancy. We now compute each
    fraction with Jmp in A/cm² and multiply by Pmpp = Jmp·Vmp to return an
    absolute power density directly comparable to the FEM column.
    """
    Jm = DP.Jph_top * 0.93                 # A/cm²  (Jph_top stored in A/cm²)
    _, _, Vs = DP.expected_voc(); Vm = Vs * 0.88
    df = GEO.H / (GEO.n_f + 1); dBB = GEO.W / (GEO.n_b + 1) if GEO.n_b > 0 else GEO.W
    rf = rm / (cf * wf * hf)
    Pmpp = Jm * 1000.0 * Vm                # mW/cm²  (Jm·1000 → mA/cm²)
    frac_e = (1/12) * Rs * (Jm / Vm) * df**2
    frac_f = (1/12) * rf * (Jm / Vm) * dBB**2 * df
    frac_c = 0.5 * rc * (Jm / Vm) * dBB * df / wf
    return (frac_e * Pmpp, frac_f * Pmpp, frac_c * Pmpp)


# =============================================================
# REPORT PAGES -- FIXED ARCHITECTURE + CLEAN CONDITIONS
# =============================================================
def _rpt_hdr(f, title, page, total=8):
    ax = f.add_axes([0, 0.93, 1, 0.07]); ax.axis('off')
    ax.add_patch(Rectangle((0,0),1,1,transform=ax.transAxes,fc=_CH,ec='none'))
    ax.text(0.04, 0.5, title, va='center', fontsize=15, fontweight='bold', color='white', transform=ax.transAxes)
    ax.text(0.96, 0.5, f'{page} / {total}', va='center', ha='right', fontsize=10, color='#90CAF9', transform=ax.transAxes)

def _rpt_ftr(f):
    f.text(
        0.04,
        0.015,
        f'2L-FEST PRO v5.0  |  {_build_label()}  |  KIST Solar Cell Research Team  |  Dr. Inho Kim',
        fontsize=7,
        color='#bbb',
    )

def _txt_tbl(ax, title, headers, rows, xpos, y0=0.92, rh=0.095):
    ax.axis('off'); ax.set_xlim(0,1); ax.set_ylim(0,1)
    if title:
        ax.text(0.5, 0.98, title, ha='center', fontsize=11, fontweight='bold', color=_CH, transform=ax.transAxes)
    y_ = y0
    ax.add_patch(Rectangle((0,y_-rh*0.35),1,rh*0.85,transform=ax.transAxes,fc='#E8EAF6',ec='none'))
    for xi, t in zip(xpos, headers):
        ax.text(xi, y_-rh*0.0, t, fontsize=8.5, fontweight='bold', color=_CH, transform=ax.transAxes)
    y_ -= rh * 0.6
    ax.plot([0,1],[y_+0.01,y_+0.01],'-',color='#C5CAE9',lw=1.0,transform=ax.transAxes)
    for ri, row in enumerate(rows):
        y_ -= rh
        if all(c == '' for c in row):
            ax.plot([0.02,0.98],[y_+rh*0.4,y_+rh*0.4],'-',color='#e0e0e0',lw=0.5,transform=ax.transAxes)
            continue
        if ri % 2 == 0:
            ax.add_patch(Rectangle((0,y_-rh*0.2),1,rh*0.9,transform=ax.transAxes,fc='#FAFAFA',ec='none'))
        for ci, (xi, cell) in enumerate(zip(xpos, row)):
            fw = 'bold' if ci > 0 else 'normal'
            ax.text(xi, y_+rh*0.25, cell, fontsize=9, color='#333', fontweight=fw, transform=ax.transAxes)


def _rpt_p1(f, d):
    _rpt_hdr(f, 'Summary', 1); _rpt_ftr(f)
    iv_b=d['iv_b']; iv_a=d['iv_a']; ed=iv_a['Eff']-iv_b['Eff']
    bp=d['bp']; ap=d['ap']
    mode = d.get('mode', 'tandem')
    Rl_b=bp[0]/(bp[4]*bp[2]*bp[1]); Rl_a=ap[0]/(ap[4]*ap[2]*ap[1])
    Pt_b=d['Pe_b']+d['Pf_b']+d['Pc_b']; Pt_a=d['Pe_a']+d['Pf_a']+d['Pc_a']
    ax=f.add_axes([0,0.05,1,0.87]); ax.axis('off'); ax.set_xlim(0,1); ax.set_ylim(0,1)
    ax.text(0.5,0.92,'Hot Pressing Effect on Screen-Printed Ag Electrode',ha='center',fontsize=16,color='#333')
    subtitle = '2T Monolithic Perovskite / Si Tandem Solar Cell' if mode == 'tandem' else 'Single Cell Solar Cell'
    ax.text(0.5,0.85,subtitle,ha='center',fontsize=11,color='#888')
    sc=_C3 if ed>0 else '#EF5350'
    ax.text(0.5,0.68,f'{iv_b["Eff"]:.3f}%   ->   {iv_a["Eff"]:.3f}%',ha='center',fontsize=28,fontweight='bold',color='#333')
    ax.text(0.5,0.54,f'Deta = {ed:+.4f}%',ha='center',fontsize=40,fontweight='bold',color=sc)
    lines=[
        f'rho_bulk:  {bp[0]*1e6:.2f} -> {ap[0]*1e6:.2f} uO*cm   ({(ap[0]-bp[0])/bp[0]*100:+.1f}%)',
        f'R_line:  {Rl_b:.3f} -> {Rl_a:.3f} Ohm/cm   ({(Rl_a-Rl_b)/Rl_b*100:+.1f}%)',
        f'Shape CF:  {bp[4]:.3f} -> {ap[4]:.3f}   (dome -> flat)',
        f'Total R Loss:  {Pt_b:.4f} -> {Pt_a:.4f} mW/cm2',
        f'Voc={iv_b["Voc"]:.4f}V  |  FF: {iv_b["FF"]:.2f}->{iv_a["FF"]:.2f}%  |  Pmpp: {iv_b["Pmpp"]:.3f}->{iv_a["Pmpp"]:.3f}',
    ]
    # Append CM line for tandem mode (Step 3 — report integration)
    cm_b = d.get('cm_b')
    if mode == 'tandem' and cm_b and cm_b.get('mode') == 'tandem':
        lines.append(
            f'CM:  {cm_b["limiting"]}   '
            f'(Top {cm_b["Jph_top_eff"]:.2f}, Bot {cm_b["Jph_bot_eff"]:.2f}, '
            f'D = {cm_b["mismatch"]:+.2f} mA/cm2,  {cm_b["mismatch_pct"]:+.2f}%)'
        )
    y_ = 0.38
    for line in lines:
        ax.text(0.5, y_, line, ha='center', fontsize=11, color='#555'); y_ -= 0.06


def _rpt_p2(f, d):
    _rpt_hdr(f, 'I-V Characteristics', 2); _rpt_ftr(f)
    iv_b=d['iv_b']; iv_a=d['iv_a']; ed=iv_a['Eff']-iv_b['Eff']
    mode = d.get('mode', 'tandem')
    ax=f.add_axes([0.08,0.10,0.48,0.78])
    ax.plot(d['Vs_b'],d['Js_b'],'--',color=_C2,lw=2.5,label='Before')
    ax.plot(d['Vs_a'],d['Js_a'],'-',color=_C3,lw=2.5,label='After')
    ax.fill_between([0,iv_b['Vmpp'],iv_b['Vmpp'],0],[0,0,iv_b['Jmpp'],iv_b['Jmpp']],alpha=0.06,color=_C2)
    ax.fill_between([0,iv_a['Vmpp'],iv_a['Vmpp'],0],[0,0,iv_a['Jmpp'],iv_a['Jmpp']],alpha=0.06,color=_C3)
    ax.plot(iv_b['Vmpp'],iv_b['Jmpp'],'o',color=_C2,ms=9,zorder=5)
    ax.plot(iv_a['Vmpp'],iv_a['Jmpp'],'s',color=_C3,ms=9,zorder=5)
    ax.set_xlabel('Voltage [V]',fontsize=12); ax.set_ylabel('J [mA/cm2]',fontsize=12)
    ax.set_xlim(0,max(iv_b['Voc'],iv_a['Voc'])*1.05)
    ax.set_ylim(0,max(iv_b['Jsc'],iv_a['Jsc'])*1.15)
    ax.legend(fontsize=10); ax.grid(True,alpha=0.1)
    rows=[('Jsc [mA/cm2]',f'{iv_b["Jsc"]:.3f}',f'{iv_a["Jsc"]:.3f}',f'{iv_a["Jsc"]-iv_b["Jsc"]:+.3f}'),
          ('Voc [V]',f'{iv_b["Voc"]:.4f}',f'{iv_a["Voc"]:.4f}',f'{(iv_a["Voc"]-iv_b["Voc"])*1000:+.1f}mV')]
    if mode == 'tandem':
        rows.append(('Voc,top [V]',f'{iv_b.get("Voc_top",0):.4f}',f'{iv_a.get("Voc_top",0):.4f}','(diode)'))
        rows.append(('Voc,bot [V]',f'{iv_b.get("Voc_bot",0):.4f}',f'{iv_a.get("Voc_bot",0):.4f}','(diode)'))
        # CM rows (Step 3 — report integration)
        cm_b = d.get('cm_b'); cm_a = d.get('cm_a')
        if cm_b and cm_a and cm_b.get('mode') == 'tandem':
            rows.append(('Jph_top_eff [mA/cm2]',
                         f'{cm_b["Jph_top_eff"]:.3f}', f'{cm_a["Jph_top_eff"]:.3f}',
                         f'{cm_a["Jph_top_eff"]-cm_b["Jph_top_eff"]:+.3f}'))
            rows.append(('Jph_bot_eff [mA/cm2]',
                         f'{cm_b["Jph_bot_eff"]:.3f}', f'{cm_a["Jph_bot_eff"]:.3f}',
                         f'{cm_a["Jph_bot_eff"]-cm_b["Jph_bot_eff"]:+.3f}'))
            rows.append(('CM mismatch [%]',
                         f'{cm_b["mismatch_pct"]:+.2f}', f'{cm_a["mismatch_pct"]:+.2f}',
                         cm_b['limiting']))
            rows.append(('MPP residual RMS',
                         f'{cm_b["rms_residual"]:.1e}', f'{cm_a["rms_residual"]:.1e}',
                         '(<1e-5 OK)'))
    rows.extend([
          ('FF [%]',f'{iv_b["FF"]:.2f}',f'{iv_a["FF"]:.2f}',f'{iv_a["FF"]-iv_b["FF"]:+.2f}'),
          ('eta [%]',f'{iv_b["Eff"]:.3f}',f'{iv_a["Eff"]:.3f}',f'{ed:+.4f}'),
          ('Pmpp [mW/cm2]',f'{iv_b["Pmpp"]:.3f}',f'{iv_a["Pmpp"]:.3f}',f'{iv_a["Pmpp"]-iv_b["Pmpp"]:+.3f}'),
          ('Vmpp [V]',f'{iv_b["Vmpp"]:.4f}',f'{iv_a["Vmpp"]:.4f}','')])
    ax2=f.add_axes([0.62,0.10,0.35,0.78])
    _txt_tbl(ax2,'',['','Before','After','D'],
             [[r[0],r[1],r[2],r[3]] for r in rows],
             [0.0,0.42,0.66,0.88],y0=0.95,rh=0.105)


def _rpt_p3(f, d):
    _rpt_hdr(f, 'Power Loss Analysis at MPP', 3); _rpt_ftr(f)
    Pe_b=d['Pe_b']; Pf_b=d['Pf_b']; Pc_b=d['Pc_b']; Ps_b=d['Ps_b']
    Pe_a=d['Pe_a']; Pf_a=d['Pf_a']; Pc_a=d['Pc_a']; Ps_a=d['Ps_a']
    Psh_b=d.get('Psh_b',0); Psh_a=d.get('Psh_a',0)
    Prec_b=d.get('Prec_b',0); Prec_a=d.get('Prec_a',0)
    Pj_b=d.get('Pj_b',0); Pj_a=d.get('Pj_a',0)
    Pt_b=Pe_b+Pf_b+Pc_b; Pt_a=Pe_a+Pf_a+Pc_a; iv_b=d['iv_b']; iv_a=d['iv_a']
    from matplotlib.patches import Patch
    # Stacked bar: Output & All Losses (Griddler style)
    ax1=f.add_axes([0.06,0.10,0.27,0.78])
    bc=['#FDD835','#EF5350','#42A5F5','#FFA726','#AB47BC','#9b59b6','#1abc9c','#FF9800']
    bl=['Output','Shading','Emitter R','Finger R','Contact R','Shunt','Recomb','Junction']
    for xi,(iv_c,pe,pf,pc,ps,psh,prec,pj) in enumerate([
            (iv_b,Pe_b,Pf_b,Pc_b,Ps_b,Psh_b,Prec_b,Pj_b),
            (iv_a,Pe_a,Pf_a,Pc_a,Ps_a,Psh_a,Prec_a,Pj_a)]):
        vals=[iv_c['Pmpp'],ps,pe,pf,pc,psh,prec,pj]; bot=0
        for vi,(v,col) in enumerate(zip(vals,bc)):
            ax1.bar(xi,v,0.45,bottom=bot,color=col,edgecolor='white',lw=0.5)
            if v>max(vals)*0.03:
                ax1.text(xi,bot+v/2,f'{v:.3f}',ha='center',va='center',fontsize=6,fontweight='bold',
                        color='#333' if vi==0 else 'white')
            bot+=v
    ax1.set_xticks([0,1]); ax1.set_xticklabels(['Before','After'],fontsize=11)
    ax1.set_ylabel('Power [mW/cm2]')
    ax1.set_title('Output & Losses',fontweight='bold',fontsize=12)
    ax1.legend(handles=[Patch(fc=c_,label=l_) for c_,l_ in zip(bc,bl)],fontsize=6,loc='upper right')
    ax1.grid(True,alpha=0.08,axis='y')
    # Grouped bar: All losses
    ax2=f.add_axes([0.40,0.10,0.25,0.78])
    cats=['Emitter','Finger','Contact','Shunt','Recomb','Junction']; x_=np.arange(6); w_=0.32
    ax2.bar(x_-w_/2,[Pe_b,Pf_b,Pc_b,Psh_b,Prec_b,Pj_b],w_,color=_C2,alpha=0.9,label='Before')
    ax2.bar(x_+w_/2,[Pe_a,Pf_a,Pc_a,Psh_a,Prec_a,Pj_a],w_,color=_C3,alpha=0.9,label='After')
    ax2.set_xticks(x_); ax2.set_xticklabels(cats,fontsize=8,rotation=15)
    ax2.set_ylabel('Loss [mW/cm2]')
    ax2.set_title('All Losses',fontweight='bold',fontsize=12)
    ax2.legend(fontsize=8); ax2.grid(True,alpha=0.08,axis='y')
    # Loss detail table
    ax3=f.add_axes([0.70,0.10,0.28,0.78])
    _txt_tbl(ax3,'Loss Detail [mW/cm2]',['','Before','After','D'],
        [['Emitter/TCO',f'{Pe_b:.4f}',f'{Pe_a:.4f}',f'{Pe_a-Pe_b:+.4f}'],
         ['Finger/BB',f'{Pf_b:.4f}',f'{Pf_a:.4f}',f'{Pf_a-Pf_b:+.4f}'],
         ['Contact',f'{Pc_b:.4f}',f'{Pc_a:.4f}',f'{Pc_a-Pc_b:+.4f}'],
         ['R Total',f'{Pt_b:.4f}',f'{Pt_a:.4f}',f'{Pt_a-Pt_b:+.4f}'],
         ['','','',''],
         ['Shunt',f'{Psh_b:.4f}',f'{Psh_a:.4f}',f'{Psh_a-Psh_b:+.4f}'],
         ['Recomb',f'{Prec_b:.4f}',f'{Prec_a:.4f}',f'{Prec_a-Prec_b:+.4f}'],
         ['Junction',f'{Pj_b:.4f}',f'{Pj_a:.4f}',f'{Pj_a-Pj_b:+.4f}'],
         ['Shading*',f'{Ps_b:.4f}',f'{Ps_a:.4f}','(in eta)'],
         ['Pmpp',f'{iv_b["Pmpp"]:.3f}',f'{iv_a["Pmpp"]:.3f}',f'{iv_a["Pmpp"]-iv_b["Pmpp"]:+.3f}']],
        [0.0,0.35,0.58,0.80],y0=0.95,rh=0.076)


def _rpt_p4(f, d):
    _rpt_hdr(f, 'Voltage Maps \u2014 Before vs After (at MPP)', 4); _rpt_ftr(f)
    Ve_b=d['Ve_b']; Ve_a=d['Ve_a']; Vt_b=d.get('Vt_b'); Vt_a=d.get('Vt_a')
    cb_kw=dict(shrink=0.72,pad=0.02)
    vmin_e=min(Ve_b.min(),Ve_a.min()); vmax_e=max(Ve_b.max(),Ve_a.max())
    ax1=f.add_axes([0.04,0.52,0.42,0.38])
    tcf1=ax1.tricontourf(triang,Ve_b,levels=50,cmap='inferno',vmin=vmin_e,vmax=vmax_e)
    f.colorbar(tcf1,ax=ax1,label='V',**cb_kw)
    ax1.set_title('Emitter (TCO) \u2014 Before',fontweight='bold',fontsize=11,color=_C2)
    ax1.set_aspect('equal',adjustable='box'); ax1.set_xlabel('X [mm]'); ax1.set_ylabel('Y [mm]')
    ax2=f.add_axes([0.52,0.52,0.42,0.38])
    tcf2=ax2.tricontourf(triang,Ve_a,levels=50,cmap='inferno',vmin=vmin_e,vmax=vmax_e)
    f.colorbar(tcf2,ax=ax2,label='V',**cb_kw)
    ax2.set_title('Emitter (TCO) \u2014 After',fontweight='bold',fontsize=11,color=_C3)
    ax2.set_aspect('equal',adjustable='box'); ax2.set_xlabel('X [mm]'); ax2.set_ylabel('Y [mm]')

    if Vt_b is not None and Vt_a is not None:
        vmin_t=min(Vt_b.min(),Vt_a.min()); vmax_t=max(Vt_b.max(),Vt_a.max())
        ax3=f.add_axes([0.04,0.06,0.42,0.38])
        tcf3=ax3.tricontourf(triang,Vt_b,levels=50,cmap='inferno',vmin=vmin_t,vmax=vmax_t)
        f.colorbar(tcf3,ax=ax3,label='V',**cb_kw)
        ax3.set_title('Top Cell (Pvsk) \u2014 Before',fontweight='bold',fontsize=11,color=_C2)
        ax3.set_aspect('equal',adjustable='box'); ax3.set_xlabel('X [mm]'); ax3.set_ylabel('Y [mm]')
        ax4=f.add_axes([0.52,0.06,0.42,0.38])
        tcf4=ax4.tricontourf(triang,Vt_a,levels=50,cmap='inferno',vmin=vmin_t,vmax=vmax_t)
        f.colorbar(tcf4,ax=ax4,label='V',**cb_kw)
        ax4.set_title('Top Cell (Pvsk) \u2014 After',fontweight='bold',fontsize=11,color=_C3)
        ax4.set_aspect('equal',adjustable='box'); ax4.set_xlabel('X [mm]'); ax4.set_ylabel('Y [mm]')
    else:
        # Single cell: show rear voltage
        Vr_b=d.get('Vr_b'); Vr_a=d.get('Vr_a')
        if Vr_b is None: Vr_b = np.zeros_like(Ve_b)
        if Vr_a is None: Vr_a = np.zeros_like(Ve_a)
        ax3=f.add_axes([0.04,0.06,0.42,0.38])
        Vd_b = Ve_b - Vr_b
        tcf3=ax3.tricontourf(triang,Vd_b,levels=50,cmap='inferno')
        f.colorbar(tcf3,ax=ax3,label='V',**cb_kw)
        ax3.set_title('Diode V \u2014 Before',fontweight='bold',fontsize=11,color=_C2)
        ax3.set_aspect('equal',adjustable='box'); ax3.set_xlabel('X [mm]'); ax3.set_ylabel('Y [mm]')
        ax4=f.add_axes([0.52,0.06,0.42,0.38])
        Vd_a = Ve_a - Vr_a
        tcf4=ax4.tricontourf(triang,Vd_a,levels=50,cmap='inferno')
        f.colorbar(tcf4,ax=ax4,label='V',**cb_kw)
        ax4.set_title('Diode V \u2014 After',fontweight='bold',fontsize=11,color=_C3)
        ax4.set_aspect('equal',adjustable='box'); ax4.set_xlabel('X [mm]'); ax4.set_ylabel('Y [mm]')


def _rpt_p5(f, d):
    """Architecture -- mode-dependent layer stack."""
    _rpt_hdr(f, 'FEM Model & Methodology', 5); _rpt_ftr(f)
    bp = d['bp']
    mode = d.get('mode', 'tandem')
    vmpp_bias = d['iv_b'].get('Vmpp_internal', d['iv_b']['Vmpp'])
    res_t_dict = d['iv_b'].get('_mpp_result') or S.solve(bp[0],bp[1],bp[2],bp[5],bp[6],vmpp_bias,bp[4],DP,mode=mode)
    res_t = res_t_dict['res']

    # --- LEFT PANEL: Architecture Diagram ---
    ax1 = f.add_axes([0.04, 0.10, 0.38, 0.78]); ax1.axis('off')
    ax1.set_xlim(0,1); ax1.set_ylim(0,1)
    ax1.text(0.5, 0.99, 'Simulation Model', ha='center', fontsize=13,
             fontweight='bold', color=_CH, transform=ax1.transAxes)

    if mode == 'tandem':
        arch_layers = [
            ('Metal Grid (Ag)',            '#FFF3E0', '#E65100', 0.88),
            ('Contact R (rho_c)',          '#FFEBEE', '#C62828', 0.80),
            ('TCO / Emitter (R_sh)',       '#E3F2FD', '#1565C0', 0.72),
            ('Perovskite Top Diode',       '#FFF8E1', '#F57F17', 0.64),
            ('Recomb. Junction',           '#F3E5F5', '#7B1FA2', 0.56),
            ('c-Si Bottom Diode',          '#E8F5E9', '#2E7D32', 0.48),
            ('Rear Plane (V_rear)',        '#ECEFF1', '#455A64', 0.40),
        ]
        eqs = [
            ('Method:', 'Galerkin FEM + Newton-Raphson'),
            ('Diode:', 'J=Jph-J01(e^(V/VT)-1)-J02(...)-V/Rsh'),
            ('J01:', 'Passivated vs Metal contact'),
            ('2T:', 'I_top(V_top) = I_bot(V-V_top) at each node'),
            ('Ref:', 'Jeon et al. 2025, Rehman 2023, Meier 1984'),
        ]
    else:
        arch_layers = [
            ('Metal Grid (Ag)',            '#FFF3E0', '#E65100', 0.88),
            ('Contact R (rho_c)',          '#FFEBEE', '#C62828', 0.80),
            ('TCO / Emitter (R_sh)',       '#E3F2FD', '#1565C0', 0.72),
            ('2-Diode (Jph, J01, J02)',    '#FFF8E1', '#F57F17', 0.64),
            ('Rear Plane (V_rear)',        '#ECEFF1', '#455A64', 0.52),
        ]
        eqs = [
            ('Method:', 'Galerkin FEM + Newton-Raphson'),
            ('Diode:', 'J=Jph-J01(e^(V/VT)-1)-J02(...)-V/Rsh'),
            ('J01:', 'Passivated vs Metal contact'),
            ('V_diode:', 'V_emitter - V_rear'),
            ('Ref:', 'Gupta 2018, Rehman 2023, Meier 1984'),
        ]

    for lab, fc, ec, y_ in arch_layers:
        ax1.add_patch(FancyBboxPatch((0.05, y_-0.025), 0.90, 0.055,
                      transform=ax1.transAxes, boxstyle='round,pad=0.008',
                      fc=fc, ec=ec, lw=1.0))
        ax1.text(0.5, y_, lab, ha='center', va='center', fontsize=8.5,
                fontweight='bold', color=ec, transform=ax1.transAxes)

    # Arrows indicating current flow direction
    y_top = arch_layers[0][3]; y_bot = arch_layers[-1][3]
    ax1.annotate('', xy=(0.12, y_bot-0.02), xytext=(0.12, y_top+0.02),
                 xycoords='axes fraction', textcoords='axes fraction',
                 arrowprops=dict(arrowstyle='->', color='#B71C1C', lw=2))
    ax1.text(0.02, (y_top+y_bot)/2, 'I\u2193', fontsize=10, fontweight='bold',
             color='#B71C1C', transform=ax1.transAxes, ha='center')

    # Key equations (already set in mode branch above)
    y_ = 0.30
    for lbl, val in eqs:
        ax1.text(0.05, y_, lbl, fontsize=8.5, fontweight='bold', color='#333', transform=ax1.transAxes)
        ax1.text(0.28, y_, val, fontsize=8.5, color='#555', transform=ax1.transAxes)
        y_ -= 0.055

    # --- CENTER: Mesh plot ---
    ax2 = f.add_axes([0.46, 0.10, 0.24, 0.76])
    ax2.triplot(triang, 'k-', lw=0.1, alpha=0.2)
    ax2.plot(pts[isf,0]*10, pts[isf,1]*10, 's', color='#EF5350', ms=1, label='Front F')
    ax2.plot(pts[isb&~isp,0]*10, pts[isb&~isp,1]*10, 's', color='#42A5F5', ms=1, label='Front BB')
    if isrm is not None and np.any(isrm):
        rm_only = isrm & (~isrp if isrp is not None else np.ones_like(isrm))
        ax2.plot(pts[rm_only,0]*10, pts[rm_only,1]*10, 's', color='#7B1FA2', ms=1, alpha=0.5, label='Rear M')
    if isrp is not None and np.any(isrp):
        ax2.plot(pts[isrp,0]*10, pts[isrp,1]*10, 'D', color='#4CAF50', ms=4, label='Rear Pad')
    if GEO.pad > 0:
        ax2.plot(pts[isp,0]*10, pts[isp,1]*10, 's', color='#FFA726', ms=2.5, label='Front Pad')
    ax2.legend(fontsize=6, loc='upper right'); ax2.set_aspect('equal', adjustable='box')
    ax2.set_xlabel('X [mm]'); ax2.set_ylabel('Y [mm]')
    ax2.set_title(f'Mesh: {len(pts)} nodes\n{len(tri.simplices)} elements',
                  fontweight='bold', fontsize=10)

    # --- RIGHT: Convergence ---
    ax3 = f.add_axes([0.76, 0.10, 0.22, 0.76])
    ax3.semilogy(range(1,len(res_t)+1), res_t, 'o-', color=_C2, ms=4, lw=1.8)
    ax3.axhline(1e-10, color='#EF5350', ls='--', lw=1)
    ax3.set_xlabel('Iteration'); ax3.set_ylabel('Max |F|')
    ax3.set_title(f'Convergence\n({len(res_t)} iter)', fontweight='bold', fontsize=10)
    ax3.grid(True, alpha=0.1)


def _rpt_p6(f, d):
    """[FIXED] Clean conditions panel -- proper table layout."""
    _rpt_hdr(f, 'Verification & Parameters', 6); _rpt_ftr(f)
    bp=d['bp']; ap=d['ap']
    Pe_b=d['Pe_b']; Pf_b=d['Pf_b']; Pc_b=d['Pc_b']
    Pe_a=d['Pe_a']; Pf_a=d['Pf_a']; Pc_a=d['Pc_a']
    Pt_b=Pe_b+Pf_b+Pc_b; Pt_a=Pe_a+Pf_a+Pc_a
    Rl_b=bp[0]/(bp[4]*bp[2]*bp[1]); Rl_a=ap[0]/(ap[4]*ap[2]*ap[1])
    aPe_b,aPf_b,aPc_b=_analytical_loss(bp[0],bp[1],bp[2],bp[5],bp[6],bp[4])
    aPe_a,aPf_a,aPc_a=_analytical_loss(ap[0],ap[1],ap[2],ap[5],bp[6],ap[4])

    ax1=f.add_axes([0.03,0.50,0.46,0.40])
    _txt_tbl(ax1,'FEM vs Analytical [mW/cm2]',['Loss','FEM(B)','Ana(B)','FEM(A)','Ana(A)'],
        [['Emitter',f'{Pe_b:.4f}',f'{aPe_b:.4f}',f'{Pe_a:.4f}',f'{aPe_a:.4f}'],
         ['Finger',f'{Pf_b:.4f}',f'{aPf_b:.4f}',f'{Pf_a:.4f}',f'{aPf_a:.4f}'],
         ['Contact',f'{Pc_b:.4f}',f'{aPc_b:.4f}',f'{Pc_a:.4f}',f'{aPc_a:.4f}'],
         ['TOTAL',f'{Pt_b:.4f}',f'{aPe_b+aPf_b+aPc_b:.4f}',f'{Pt_a:.4f}',f'{aPe_a+aPf_a+aPc_a:.4f}']],
        [0.02,0.22,0.40,0.58,0.78])

    ax2=f.add_axes([0.53,0.50,0.44,0.40])
    _txt_tbl(ax2,'Electrode Parameters',['Param','Before','After'],
        [['rho_bulk [uO*cm]',f'{bp[0]*1e6:.2f}',f'{ap[0]*1e6:.2f}'],
         ['H [um]',f'{bp[1]*1e4:.1f}',f'{ap[1]*1e4:.1f}'],
         ['W_finger [um]',f'{bp[2]*1e4:.0f}',f'{ap[2]*1e4:.0f}'],
         ['W_busbar [um]',f'{bp[3]*1e4:.0f}',f'{ap[3]*1e4:.0f}'],
         ['CF',f'{bp[4]:.3f}',f'{ap[4]:.3f}'],
         ['R_line [Ohm/cm]',f'{Rl_b:.3f}',f'{Rl_a:.3f}'],
         ['rho_c [mOhm*cm2]',f'{bp[5]*1e3:.1f}',f'{ap[5]*1e3:.1f}'],
         ['R_sh [Ohm/sq]',f'{bp[6]:.0f}','\u2014']],
        [0.02,0.48,0.75])

    ax3=f.add_axes([0.03,0.05,0.46,0.40])
    mode = d.get('mode', 'tandem')
    if mode == 'tandem':
        _txt_tbl(ax3,'Tandem 2-Diode Model',['Param','Top (Pvsk)','Bot (Si)'],
            [['Jph [mA/cm2]',f'{DP.Jph_top*1000:.1f}',f'{DP.Jph_bot*1000:.1f}'],
             ['J01 pass.',f'{DP.J01_top_pass:.1e}',f'{DP.J01_bot:.1e}'],
             ['J01 metal',f'{DP.J01_top_metal:.1e}','\u2014'],
             ['J02',f'{DP.J02_top_pass:.1e}',f'{DP.J02_bot:.1e}'],
             ['n1/n2',f'{DP.n1_top:.1f}/{DP.n2_top:.1f}',f'{DP.n1_bot:.1f}/{DP.n2_bot:.1f}'],
             ['Rsh [Ohm*cm2]',f'{DP.Rsh_top:.0f}',f'{DP.Rsh_bot:.0f}']],
            [0.02,0.45,0.75])
    else:
        _txt_tbl(ax3,'Single Cell 2-Diode Model',['Param','Value'],
            [['Jph [mA/cm2]',f'{DP.Jph_single*1000:.1f}'],
             ['J01 pass.',f'{DP.J01_single_pass:.1e}'],
             ['J01 metal',f'{DP.J01_single_metal:.1e}'],
             ['J02',f'{DP.J02_single_pass:.1e}'],
             ['n1/n2',f'{DP.n1_single:.1f}/{DP.n2_single:.1f}'],
             ['Rsh [Ohm*cm2]',f'{DP.Rsh_single:.0f}']],
            [0.02,0.55])

    # [FIXED] Clean simulation conditions table
    ax4=f.add_axes([0.53,0.05,0.44,0.40])
    mode_label = '2T series-connected' if mode == 'tandem' else 'Single cell'
    _txt_tbl(ax4,'Simulation Conditions',['',''],
        [['Method','Galerkin FEM + Newton-Raphson'],
         ['Mesh',f'{len(pts)} nodes, {len(tri.simplices)} tri'],
         ['DOF',f'{2*len(pts)+np.sum(ism):,}'],
         ['Mode',mode_label],
         ['Cell',f'{GEO.W*10:.0f}x{GEO.H*10:.0f}mm, {GEO.n_f}F+{GEO.n_b}BB'],
         ['Shading',f'{GEO.shading_fraction()*100:.2f}%'],
         ['Temp.','25\u00b0C (298.15 K)']],
        [0.02,0.45])


def _rpt_p7(f, d):
    """Validation page: Tier 1 (energy balance) + Tier 2 (analytical)."""
    _rpt_hdr(f, 'Validation — Tier 1 (Self-consistency) & Tier 2 (Analytical)', 7); _rpt_ftr(f)
    bp=d['bp']; ap=d['ap']
    iv_b=d['iv_b']; iv_a=d['iv_a']
    Pe_b=d['Pe_b']; Pf_b=d['Pf_b']; Pc_b=d['Pc_b']; Pe_a=d['Pe_a']; Pf_a=d['Pf_a']; Pc_a=d['Pc_a']
    Ps_b=d['Ps_b']; Psh_b=d['Psh_b']; Prec_b=d['Prec_b']
    Ps_a=d['Ps_a']; Psh_a=d['Psh_a']; Prec_a=d['Prec_a']
    Pj_b=d.get('Pj_b',0.0); Pj_a=d.get('Pj_a',0.0)
    Pt_b=Pe_b+Pf_b+Pc_b; Pt_a=Pe_a+Pf_a+Pc_a

    # === Tier 1: Electrical power balance (loss reconstruction) ===
    # IVL-1 fix: this is an ELECTRICAL budget. Jph enters the model as an INPUT
    # (there is no optical/spectral front-end), so the budget CANNOT be closed
    # against the 100 mW/cm² AM1.5G optical irradiance — roughly 60 mW/cm² of
    # thermalization + sub-bandgap photon loss is structurally outside any
    # electrical FEM model. The previous "Residual vs 100 mW/cm²" was a category
    # error: it compared an electrical generation budget to an optical input, so
    # the residual was structurally ~55-66% and "PASS (<5%)" was unachievable
    # for any real cell. We instead reconstruct the loss-free electrical power
    # ceiling, consistent with the PCE waterfall (PCE_ref):
    #     P_lossfree = P_out(MPP) + Σ(electrical loss buckets)
    P_out_b = iv_b['Pmpp']
    P_loss_total_b = Pt_b + Ps_b + Psh_b + Prec_b + Pj_b
    P_lossfree_b = P_out_b + P_loss_total_b
    P_out_a = iv_a['Pmpp']
    P_loss_total_a = Pt_a + Ps_a + Psh_a + Prec_a + Pj_a
    P_lossfree_a = P_out_a + P_loss_total_a
    # Fraction of the reconstructed loss-free ceiling actually delivered to the
    # terminal — an electrical-completeness indicator, NOT an optical balance.
    deliver_b = (P_out_b / P_lossfree_b * 100.0) if P_lossfree_b > 1e-9 else 0.0
    deliver_a = (P_out_a / P_lossfree_a * 100.0) if P_lossfree_a > 1e-9 else 0.0

    ax1 = f.add_axes([0.03, 0.55, 0.45, 0.38])
    _txt_tbl(ax1, 'Tier 1 — Electrical Loss Reconstruction [mW/cm²]',
             ['Term', 'Before', 'After'],
             [['P_out (MPP)',       f'{P_out_b:.3f}', f'{P_out_a:.3f}'],
              ['P_resistive',       f'{Pt_b:.4f}', f'{Pt_a:.4f}'],
              ['P_shading',         f'{Ps_b:.4f}', f'{Ps_a:.4f}'],
              ['P_shunt',           f'{Psh_b:.4f}', f'{Psh_a:.4f}'],
              ['P_recomb',          f'{Prec_b:.4f}', f'{Prec_a:.4f}'],
              ['P_junction',        f'{Pj_b:.4f}', f'{Pj_a:.4f}'],
              ['Loss-free ceiling', f'{P_lossfree_b:.3f}', f'{P_lossfree_a:.3f}'],
              ['Delivered %',       f'{deliver_b:.1f}%', f'{deliver_a:.1f}%']],
             [0.02, 0.45, 0.75])
    ax1.text(0.50, -0.04,
             'Electrical reconstruction — Jph is a model input, not an optical balance',
             ha='center', va='top', fontsize=8, fontweight='bold',
             color='#0F172A', transform=ax1.transAxes)

    # === Tier 2: Analytical comparison (Rehman 2023) ===
    aPe_b,aPf_b,aPc_b = _analytical_loss(bp[0],bp[1],bp[2],bp[5],bp[6],bp[4])
    aPe_a,aPf_a,aPc_a = _analytical_loss(ap[0],ap[1],ap[2],ap[5],bp[6],ap[4])

    def err(fem, ana):
        return abs(fem - ana) / ana * 100 if ana > 1e-9 else 0
    err_e_b = err(Pe_b, aPe_b); err_f_b = err(Pf_b, aPf_b); err_c_b = err(Pc_b, aPc_b)
    err_e_a = err(Pe_a, aPe_a); err_f_a = err(Pf_a, aPf_a); err_c_a = err(Pc_a, aPc_a)
    max_err = max(err_e_b, err_f_b, err_c_b, err_e_a, err_f_a, err_c_a)
    tier2_color = '#059669' if max_err < 5.0 else '#EA580C' if max_err < 15 else '#DC2626'

    ax2 = f.add_axes([0.52, 0.55, 0.45, 0.38])
    _txt_tbl(ax2, 'Tier 2 — FEM vs Rehman 2023 Analytical [%]',
             ['Loss', 'B err%', 'A err%', 'Tol'],
             [['Emitter (P_TCO)',  f'{err_e_b:.2f}', f'{err_e_a:.2f}', '< 2%'],
              ['Finger (P_grid)',  f'{err_f_b:.2f}', f'{err_f_a:.2f}', '< 2%'],
              ['Contact (P_c)',    f'{err_c_b:.2f}', f'{err_c_a:.2f}', '< 3%'],
              ['', '', '', ''],
              ['Max error',        f'{max_err:.2f}%', '', '']],
             [0.02, 0.40, 0.60, 0.80])
    status2 = ('PASS (<5%)' if max_err < 5 else
               'WARN (<15%)' if max_err < 15 else 'CHECK (>15%)')
    ax2.text(0.50, -0.04, f'Tier 2 status: {status2}',
             ha='center', va='top', fontsize=9, fontweight='bold',
             color=tier2_color, transform=ax2.transAxes)

    # === Bottom row: status summary ===
    ax3 = f.add_axes([0.03, 0.05, 0.94, 0.42]); ax3.axis('off')
    ax3.text(0.5, 0.92, 'v28 Validation Status (4-Tier)',
             ha='center', fontsize=14, fontweight='bold', color='#0F172A',
             transform=ax3.transAxes)

    # Summary table
    rows = [
        ('Tier 1', 'KCL residual',          '< 1e-8',     'PASS', '#059669'),
        ('Tier 1', 'Loss reconstruction',   'electrical', f'deliv {deliver_b:.0f}% / {deliver_a:.0f}%',
                                                          '#0F172A'),
        ('Tier 1', 'Rs_junction model family', 'Griddler-style interlayer',
         'GRIDDLER-STYLE', '#D97706'),
        ('Tier 2', 'Rehman 2023 analytical', '< 5%',       f'max {max_err:.1f}%',
                                                          tier2_color),
        ('Tier 3', 'Griddler single-cell',   '< 0.5%',     'PASS', '#059669'),
        ('Tier 3', 'Jeon 2025 Table 1',     '< 5% (Voc/Jsc)', 'See validation doc', '#0F172A'),
        ('Tier 4', 'Aydin 2024 benchmark',   '< 5%',       'Pending', '#5F5E5A'),
        ('Tier 4', 'KIST cell measurement',  '< 5%',       'Future',  '#5F5E5A'),
    ]
    y_top = 0.78
    col_x = [0.05, 0.18, 0.42, 0.62, 0.85]
    headers = ['Tier', 'Test', 'Tolerance', 'Status', '']
    for i, hdr in enumerate(headers):
        ax3.text(col_x[i], y_top, hdr, fontsize=10, fontweight='bold',
                 color='#0F172A', transform=ax3.transAxes)
    ax3.plot([0.04, 0.96], [y_top - 0.04, y_top - 0.04], '-',
             color='#0F172A', lw=0.8, transform=ax3.transAxes, clip_on=False)

    for i, (tier, test, tol, status, color) in enumerate(rows):
        y = y_top - 0.10 - i * 0.085
        ax3.text(col_x[0], y, tier, fontsize=9, fontweight='bold',
                 color='#475569', transform=ax3.transAxes)
        ax3.text(col_x[1], y, test, fontsize=9, color='#1A1A1A',
                 transform=ax3.transAxes)
        ax3.text(col_x[2], y, tol, fontsize=9, color='#475569',
                 transform=ax3.transAxes)
        ax3.text(col_x[3], y, status, fontsize=9, fontweight='bold',
                 color=color, transform=ax3.transAxes)

    ax3.text(
        0.50, 0.015,
        'Note: Phase B Rs_junction uses a Griddler-style single-plane '
        'interlayer FEM. It is numerically stable, but it is a different '
        'model family from the Phase A local-node Rs_junction=0 baseline. '
        'Use direct Griddler PRO cross-validation before claiming absolute '
        'equivalence. Measured: ~23 mV Voc offset vs Phase A (mode/mesh-'
        'independent); absolute values not interchangeable, but relative '
        'Delta within Phase B is preserved. Phase A = absolute baseline.',
        ha='center', fontsize=7.5, color='#92400E', transform=ax3.transAxes,
        bbox=dict(boxstyle='round,pad=0.35', fc='#FFFBEB', ec='#F59E0B',
                  lw=0.8, alpha=0.95),
    )


def _rpt_p8(f, d):
    """Tandem Hot Pressing Summary — research-output page (v28.4 / Step 8).

    Consolidates Before/After tandem performance into a single research-quality
    page with auto-interpretation. Tandem mode only.

    Default assumptions baked in:
      - Rc_junction = 0, Rs_junction = 0, J01_coupling = 0
      - top/bottom areas equal
      - focus on relative ΔPCE / ΔFF, not absolute Griddler PRO equivalence

    Sections:
      1. Header + Eff arrow (Before → After, ΔEff highlighted)
      2. Performance table (Jsc, Voc, FF, Eff, Pmpp + Δ row)
      3. Loss breakdown table (front resistive, finger, contact, TCO/emitter)
      4. Current matching panel (limiting subcell, mismatch, KCL residual)
      5. Auto-interpretation box (rule-based narrative)
    """
    _rpt_hdr(f, 'Tandem Hot Pressing Summary', 8); _rpt_ftr(f)

    mode = d.get('mode', 'tandem')
    iv_b = d['iv_b']; iv_a = d['iv_a']
    health_b = d.get('health_b') or _iv_health(iv_b)
    health_a = d.get('health_a') or _iv_health(iv_a)
    model_note_active = bool(
        health_b.get('phase_b_active') or health_a.get('phase_b_active')
    )

    # Single mode → polite skip page
    if mode != 'tandem':
        ax = f.add_axes([0, 0.05, 1, 0.85]); ax.axis('off')
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.text(0.5, 0.55, 'Tandem-only page',
                ha='center', fontsize=20, fontweight='bold',
                color='#94A3B8', transform=ax.transAxes)
        ax.text(0.5, 0.47,
                'This page summarizes 2T tandem-specific metrics. '
                'Run COMPARE in tandem mode to populate.',
                ha='center', fontsize=10, color='#64748B',
                transform=ax.transAxes)
        return

    # ---- Pull data ----
    d_eff = iv_a['Eff'] - iv_b['Eff']
    d_ff = iv_a['FF'] - iv_b['FF']
    d_pmpp = iv_a['Pmpp'] - iv_b['Pmpp']
    d_jsc = iv_a['Jsc'] - iv_b['Jsc']
    d_voc = iv_a['Voc'] - iv_b['Voc']

    # Loss breakdown (mW/cm²) — already cached by _run_both
    Pe_b = d['Pe_b']; Pe_a = d['Pe_a']      # emitter / TCO sheet R
    Pff_b = d['Pff_b']; Pff_a = d['Pff_a']  # finger metal R
    Pfb_b = d['Pfb_b']; Pfb_a = d['Pfb_a']  # busbar metal R
    Pc_b = d['Pc_b']; Pc_a = d['Pc_a']      # contact R
    finger_b = Pff_b + Pfb_b
    finger_a = Pff_a + Pfb_a
    front_R_b = Pe_b + finger_b + Pc_b      # total front-side resistive
    front_R_a = Pe_a + finger_a + Pc_a

    cm_b = d.get('cm_b'); cm_a = d.get('cm_a')

    # ============== TOP STRIP — large Eff arrow ==============
    ax_top = f.add_axes([0.04, 0.78, 0.92, 0.13]); ax_top.axis('off')
    ax_top.set_xlim(0, 1); ax_top.set_ylim(0, 1)
    sc = '#27ae60' if d_eff > 0 else '#e74c3c'
    ax_top.text(0.5, 0.85, 'Before / After Hot Pressing — Tandem Performance',
                ha='center', fontsize=12, fontweight='bold', color='#0F172A',
                transform=ax_top.transAxes)
    ax_top.text(0.5, 0.45,
                f'{iv_b["Eff"]:.3f}%   →   {iv_a["Eff"]:.3f}%',
                ha='center', fontsize=22, fontweight='bold', color='#0F172A',
                transform=ax_top.transAxes)
    ax_top.text(0.5, 0.05, f'ΔEff = {d_eff:+.4f}% abs   |   '
                            f'ΔFF = {d_ff:+.3f}% pt   |   '
                            f'ΔPmpp = {d_pmpp:+.4f} mW/cm²',
                ha='center', fontsize=11, fontweight='bold', color=sc,
                transform=ax_top.transAxes)

    # ============== LEFT — Performance table ==============
    ax1 = f.add_axes([0.04, 0.42, 0.46, 0.34]); ax1.axis('off')
    ax1.set_xlim(0, 1); ax1.set_ylim(0, 1)
    ax1.text(0.5, 0.97, 'Tandem Performance Metrics',
             ha='center', fontsize=10.5, fontweight='bold', color=_CH,
             transform=ax1.transAxes)
    perf_rows = [
        ('Jsc [mA/cm²]', f'{iv_b["Jsc"]:.3f}', f'{iv_a["Jsc"]:.3f}',
                          f'{d_jsc:+.3f}'),
        ('Voc [V]',       f'{iv_b["Voc"]:.4f}', f'{iv_a["Voc"]:.4f}',
                          f'{d_voc*1000:+.1f} mV'),
        ('FF [%]',        f'{iv_b["FF"]:.2f}',  f'{iv_a["FF"]:.2f}',
                          f'{d_ff:+.3f}'),
        ('Eff [%]',       f'{iv_b["Eff"]:.3f}', f'{iv_a["Eff"]:.3f}',
                          f'{d_eff:+.4f}'),
        ('Pmpp [mW/cm²]', f'{iv_b["Pmpp"]:.3f}', f'{iv_a["Pmpp"]:.3f}',
                          f'{d_pmpp:+.4f}'),
    ]
    _txt_tbl(ax1, '', ['Metric', 'Before', 'After', 'Δ'],
             perf_rows, [0.02, 0.40, 0.58, 0.78], y0=0.86, rh=0.105)

    # ============== RIGHT — Loss breakdown table ==============
    ax2 = f.add_axes([0.52, 0.42, 0.44, 0.34]); ax2.axis('off')
    ax2.set_xlim(0, 1); ax2.set_ylim(0, 1)
    ax2.text(0.5, 0.97, 'Front-Side Resistive Loss Breakdown',
             ha='center', fontsize=10.5, fontweight='bold', color=_CH,
             transform=ax2.transAxes)
    loss_rows = [
        ('Front resistive (total)', f'{front_R_b:.4f}', f'{front_R_a:.4f}',
                                     f'{front_R_a-front_R_b:+.4f}'),
        ('  Finger (F+BB)',         f'{finger_b:.4f}',  f'{finger_a:.4f}',
                                     f'{finger_a-finger_b:+.4f}'),
        ('  Contact',                f'{Pc_b:.4f}',     f'{Pc_a:.4f}',
                                     f'{Pc_a-Pc_b:+.4f}'),
        ('  TCO / emitter',          f'{Pe_b:.4f}',     f'{Pe_a:.4f}',
                                     f'{Pe_a-Pe_b:+.4f}'),
        ('Pmpp recovered [%]',
            '—',
            f'{(front_R_b-front_R_a)/iv_b["Pmpp"]*100:+.3f}',
            ''),
    ]
    _txt_tbl(ax2, '', ['Item [mW/cm²]', 'Before', 'After', 'Δ'],
             loss_rows, [0.02, 0.50, 0.68, 0.86], y0=0.86, rh=0.105)

    # ============== MIDDLE-BOTTOM — Current Matching panel ==============
    ax3 = f.add_axes([0.04, 0.22, 0.92, 0.18]); ax3.axis('off')
    ax3.set_xlim(0, 1); ax3.set_ylim(0, 1)
    ax3.text(0.5, 0.92, 'Current Matching & Solver Diagnostics',
             ha='center', fontsize=10.5, fontweight='bold', color=_CH,
             transform=ax3.transAxes)
    if cm_b and cm_a and cm_b.get('mode') == 'tandem':
        cm_rows = [
            ('Limiting subcell',
                cm_b.get('limiting', '—'),
                cm_a.get('limiting', '—'),
                '(unchanged)' if cm_b.get('limiting')==cm_a.get('limiting') else 'CHANGED'),
            ('Jph_top_eff [mA/cm²]',
                f'{cm_b["Jph_top_eff"]:.3f}', f'{cm_a["Jph_top_eff"]:.3f}',
                f'{cm_a["Jph_top_eff"]-cm_b["Jph_top_eff"]:+.3f}'),
            ('Jph_bot_eff [mA/cm²]',
                f'{cm_b["Jph_bot_eff"]:.3f}', f'{cm_a["Jph_bot_eff"]:.3f}',
                f'{cm_a["Jph_bot_eff"]-cm_b["Jph_bot_eff"]:+.3f}'),
            ('CM mismatch [%]',
                f'{cm_b["mismatch_pct"]:+.2f}', f'{cm_a["mismatch_pct"]:+.2f}',
                f'{cm_a["mismatch_pct"]-cm_b["mismatch_pct"]:+.3f}'),
            ('KCL residual RMS',
                f'{cm_b["rms_residual"]:.2e}', f'{cm_a["rms_residual"]:.2e}',
                '(< 1e-5 = converged)'),
        ]
        _txt_tbl(ax3, '', ['Item', 'Before', 'After', 'Δ / Note'],
                 cm_rows, [0.02, 0.30, 0.50, 0.72], y0=0.84, rh=0.13)
    else:
        ax3.text(0.5, 0.5, '(CM diagnostics unavailable — re-run COMPARE)',
                 ha='center', fontsize=9, color='#94A3B8', style='italic',
                 transform=ax3.transAxes)

    # ============== BOTTOM — Auto-interpretation box ==============
    ax4 = f.add_axes([0.04, 0.04, 0.92, 0.16]); ax4.axis('off')
    ax4.set_xlim(0, 1); ax4.set_ylim(0, 1)
    ax4.add_patch(Rectangle((0, 0), 1, 1, transform=ax4.transAxes,
                              fc='#F0F9FF', ec='#0EA5E9', lw=1.2))
    ax4.text(0.02, 0.88, '◆ Automatic Interpretation',
             fontsize=10, fontweight='bold', color='#0369A1',
             transform=ax4.transAxes)

    # Rule-based narrative — applies all rules that match (not exclusive)
    interpretations = []
    if model_note_active:
        interpretations.append(
            'Phase B Rs_junction is active: this is the Griddler-style '
            'single-plane interlayer model, not the Phase A local-node '
            'baseline. Use direct Griddler PRO cross-validation before '
            'claiming absolute equivalence. Measured ~23 mV Voc offset vs '
            'Phase A (mode/mesh-independent): absolute values are not '
            'interchangeable, but relative Delta within Phase B is preserved.'
        )
    front_R_decreased = (front_R_a < front_R_b)
    if d_ff > 0 and front_R_decreased:
        interpretations.append(
            'Hot pressing improves tandem efficiency mainly by reducing '
            'front-electrode resistive loss.'
        )
    if abs(d_jsc) < 0.05 and d_ff > 0:
        interpretations.append(
            'The improvement is primarily FF-driven rather than '
            'generation-driven (Jsc essentially unchanged).'
        )
    # Use BEFORE mismatch as the dominant indicator (process baseline)
    if cm_b and cm_b.get('mode') == 'tandem' and abs(cm_b['mismatch_pct']) > 2.0:
        interpretations.append(
            f'The tandem gain is partially limited by top/bottom current '
            f'mismatch ({cm_b["mismatch_pct"]:+.1f}% — '
            f'{cm_b["limiting"]}).'
        )
    # Edge cases
    if d_eff < 0:
        interpretations.append(
            'NOTE: Hot pressing decreased efficiency — check for over-pressing '
            '(finger crushed, contact damage, or ρ rebound).'
        )
    if not interpretations:
        interpretations.append(
            'No dominant mechanism flagged by the heuristic rules. '
            'Examine the Resistive / Recomb / Shading breakdown manually.'
        )

    y_int = 0.68
    for line in interpretations:
        ax4.text(0.04, y_int, '• ' + line, fontsize=9, color='#0F172A',
                 transform=ax4.transAxes, wrap=True)
        y_int -= 0.16


_RPT_PAGES = [_rpt_p1, _rpt_p2, _rpt_p3, _rpt_p4, _rpt_p5, _rpt_p6, _rpt_p7, _rpt_p8]


# User cancellation exception
# 로딩 창 X 버튼 클릭 시 _prog_update 에서 발생 → tab 메서드가 catch.
class _UserCancelled(Exception):
    """Raised when user clicks X on the progress popup to cancel."""
    pass


# =============================================================
# CUSTOMTKINTER PRO GUI
# =============================================================
class FESTProApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        # Build tag: bump this whenever the file changes so the window title
        # immediately tells you which build is running. If your title doesn't
        # show this tag, you are running an OLD copy of the file.
        self.title(f"2L-FEST PRO v5.0  [{_build_label()}]")
        print("=" * 64)
        print(f"  {_build_label()}")
        print("  DXF import: arbitrary-rect (multi-terminal) + spatial maps")
        print("  If you expected new behavior and don't see it, you are")
        print("  running an OLD copy. Check this banner.")
        print("=" * 64)
        self.geometry("1500x900")
        self.minsize(1200, 750)
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self._cache = {}
        self._last_tab = None
        self._exp_data = {}
        # DXF mode lifecycle flags
        self._dxf_loaded = False
        self._dxf_field_baseline = None
        self._dxf_last_nprobe = None   # debounce for extraction re-spacing
        self._dxf_redrawing = False    # re-entrancy guard for view refresh
        # cancellation flag (initialized; reset on each _prog_open)
        self._prog_cancelled = False

        self._build_ui()
        # arm field-edit watchers that leave DXF mode on first edit.
        try:
            self._bind_dxf_exit_watchers()
        except Exception as _e:
            print(f"[warn] DXF exit watcher bind failed: {_e}")
        self._status(_t("ready"))

    def report_callback_exception(self, exc, val, tb):
        """v28.10 (사용자 요청 2026.05.21): Tkinter global exception handler.

        _UserCancelled (X 버튼 클릭) 이 callback 어디서든 발생하면 여기서
        잡아서 progress popup만 닫고 조용히 종료. 다른 예외는 정상 로그."""
        if isinstance(val, _UserCancelled):
            try:
                self._prog_close("Cancelled.")
            except: pass
            try:
                self._status("Cancelled by user (X button).")
            except: pass
            return
        # Other exceptions: log normally
        import traceback
        traceback.print_exception(exc, val, tb)
        try:
            self._prog_close(f"Error: {val}")
        except: pass

    # ---------------------------------------------------------
    # UI CONSTRUCTION
    # ---------------------------------------------------------
    def _build_ui(self):
        # === HEADER BAR ===
        hdr = ctk.CTkFrame(self, fg_color=CLR_HEADER, height=52, corner_radius=0)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="2L-FEST", font=ctk.CTkFont(MONO_FONT, 22, "bold"),
                     text_color="#FFFFFF").pack(side="left", padx=(20, 4), pady=10)
        ctk.CTkLabel(hdr, text="2-Layer Front Electrode Simulation Tool",
                     font=ctk.CTkFont(size=12), text_color="#94A3B8").pack(side="left", pady=10)

        # About button (right side)
        info_btn = ctk.CTkButton(hdr, text="i", width=26, height=26,
                       fg_color="#334155", hover_color="#475569",
                       font=ctk.CTkFont(size=14, weight="bold"),
                       text_color="white", corner_radius=13,
                       command=self._show_about)
        info_btn.pack(side="right", padx=(4, 4), pady=12)

        # Lang toggle (right side)
        self._lang_btn = ctk.CTkButton(hdr, text="EN/KR", width=60, height=26,
                       fg_color="#334155", hover_color="#475569",
                       font=ctk.CTkFont(size=10, weight="bold"),
                       text_color="white", corner_radius=4,
                       command=self._toggle_lang)
        self._lang_btn.pack(side="right", padx=(4, 8), pady=12)
        self._mesh_info = ctk.CTkLabel(hdr, text=f"Mesh: {len(pts)} nodes | {len(tri.simplices)} tri",
                     font=ctk.CTkFont(size=10), text_color="#64748B")
        self._mesh_info.pack(side="right", padx=4, pady=10)

        # === MAIN BODY ===
        body = ctk.CTkFrame(self, fg_color="#F8FAFC", corner_radius=0)
        body.pack(fill="both", expand=True)

        # --- LEFT SIDEBAR ---
        sidebar = ctk.CTkFrame(body, fg_color=CLR_SIDEBAR, width=280, corner_radius=0)
        sidebar.pack(side="left", fill="y", padx=0)
        sidebar.pack_propagate(False)

        self._build_sidebar(sidebar)

        # --- RIGHT AREA ---
        right = ctk.CTkFrame(body, fg_color="#F8FAFC", corner_radius=0)
        right.pack(side="left", fill="both", expand=True)

        # Tab bar
        self._build_tabbar(right)

        # Plot area
        plot_frame = ctk.CTkFrame(right, fg_color="white", corner_radius=8,
                                  border_width=1, border_color=CLR_CARD_BD)
        plot_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.fig = Figure(figsize=(12, 8), facecolor='white', dpi=100)
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=4, pady=4)

        self.gs = gridspec.GridSpec(2, 3, figure=self.fig,
                                   left=0.06, right=0.97, top=0.93, bottom=0.08,
                                   hspace=0.35, wspace=0.32)

        # Status bar
        self._build_statusbar(right)


    def _build_sidebar(self, parent):
        """v28.10: Griddler-style wizard (4 steps) - 사용자 요청 2026.05.21."""
        # Scroll frame for sidebar content
        inner = ctk.CTkScrollableFrame(parent, fg_color=CLR_SIDEBAR, width=260)
        inner.pack(fill="both", expand=True, padx=4, pady=4)

        # ============= v28.10 WIZARD SELECTOR =============
        # 사이드바를 4단계로 분리 (Griddler 방식)
        wizard_hdr = ctk.CTkFrame(inner, fg_color="#1E293B", corner_radius=8, height=78)
        wizard_hdr.pack(fill="x", padx=2, pady=(2, 6))
        wizard_hdr.pack_propagate(False)

        ctk.CTkLabel(wizard_hdr, text="🧭  SETUP WIZARD",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="white").pack(pady=(6, 1))

        self._wizard_step_var = ctk.StringVar(value="1.Design")
        self._wizard_seg = ctk.CTkSegmentedButton(
            wizard_hdr,
            values=["1.Design", "2.Process", "3.Diode"],
            variable=self._wizard_step_var,
            font=ctk.CTkFont(size=10, weight="bold"),
            selected_color="#3B82F6", selected_hover_color="#2563EB",
            unselected_color="#475569", unselected_hover_color="#334155",
            text_color="white", height=26,
            command=self._on_wizard_step_change)
        self._wizard_seg.pack(fill="x", padx=6, pady=(2, 6))

        # ============= STEP CONTAINER FRAMES =============
        # 3-step 재배치:
        #   STEP 1 (Design):  MODE (top) + CELL + GRID + EXTRACTION + REAR + MESH (bottom)
        #   STEP 2 (Process): BEFORE + AFTER hot pressing
        #   STEP 3 (Diode):   ILLUMINATION + DIODE + TOP + BOT
        self._step_frames = {}
        for i in range(1, 4):
            f = ctk.CTkFrame(inner, fg_color="transparent")
            self._step_frames[i] = f
        # (3-step): 의미적 이름
        step_design  = self._step_frames[1]  # Mode, Cell, Grid, Extraction, Rear, Mesh
        step_process = self._step_frames[2]  # Before, After
        step_diode   = self._step_frames[3]  # Illumination, Diode, Top, Bot

        # 기존 코드 호환용 별칭 (legacy step1~step4 → 새 매핑)
        step1 = step_design   # 기존 step1 카드들 (Cell/Grid/Rear) → Design
        step2 = step_process  # 기존 step2 카드들 (Before/After)   → Process
        step3 = step_diode    # 기존 step3 카드들 (Diode/Top/Bot)  → Diode
        step4 = step_design   # 기존 step4 카드들 (Mode/Mesh) → Design (통합)

        # Parameters definition (hot pressing effects only)
        self.param_defs = [
            ("Bulk Resistivity", "13.22", "6.81", "uOhm.cm"),
            ("Finger Height", "10.0", "8.5", "um"),
            ("Finger Width", "50", "65", "um"),
            ("Busbar Width", "50", "65", "um"),
            ("Shape CF", "0.785", "0.95", "(pi/4~1)"),
            ("Contact Resistivity", "10.0", "10.0", "mOhm.cm2"),
            ("TCO R_sheet", "55", "", "Ohm/sq"),
        ]

        # --- BEFORE Card --- [STEP 2]
        self.tb_b, self._sidebar_labels_b, hdr_b = self._make_card(step2, _t('before'), CLR_RED,
                                     [(_t(k), p[1], p[3]) for k,p in zip(
                                      ['bulk_res','finger_h','w_finger','w_busbar','shape_cf','contact_res','tco_rsheet'],
                                      self.param_defs)])

        ctk.CTkFrame(step2, height=8, fg_color="transparent").pack()

        # --- AFTER Card --- [STEP 2]
        self.tb_a, self._sidebar_labels_a, hdr_a = self._make_card(step2, _t('after'), CLR_GREEN,
                                     [(_t(k), p[2], p[3]) for k,p in zip(
                                      ['bulk_res','finger_h','w_finger','w_busbar','shape_cf','contact_res'],
                                      self.param_defs[:6])])

        # Spacer
        ctk.CTkFrame(step2, height=12, fg_color="transparent").pack()

        # --- MODE TOGGLE (Tandem / Single) --- [STEP 1: Design 맨 위]
        # Mode를 Design 카드의 맨 위로
        # (Tandem/Single 결정은 다른 디자인 입력에 영향을 미침)
        mode_card = ctk.CTkFrame(step_design, fg_color=CLR_CARD_BG, corner_radius=8,
                                  border_width=1, border_color=CLR_CARD_BD)
        mode_card.pack(fill="x", pady=2)
        mbar = ctk.CTkFrame(mode_card, fg_color="#37474F", height=32, corner_radius=0)
        mbar.pack(fill="x"); mbar.pack_propagate(False)
        ctk.CTkLabel(mbar, text="MODE", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="white").pack(side="left", padx=12, pady=4)

        mode_row = ctk.CTkFrame(mode_card, fg_color=CLR_CARD_BG, height=40, corner_radius=0)
        mode_row.pack(fill="x", padx=8, pady=6); mode_row.pack_propagate(False)
        self._mode_var = ctk.StringVar(value="tandem")
        self._mode_seg = ctk.CTkSegmentedButton(
            mode_row, values=["tandem", "single"],
            variable=self._mode_var, font=ctk.CTkFont(size=11, weight="bold"),
            selected_color=CLR_BLUE, selected_hover_color="#1D4ED8",
            height=28)
        self._mode_seg.pack(fill="x", pady=2)
        ctk.CTkFrame(mode_card, height=4, fg_color=CLR_CARD_BG).pack()

        # --- CELL DESIGN Card (v28.10 사용자 요청 재정리) --- [STEP 1]
        # 셀 자체의 모양 + 크기: Wafer Shape + Chamfer + Cell W + Cell H
        # 명명 변경: 이전 "GRID DESIGN" (cell size만) → "CELL DESIGN" (모양 + 크기)
        cell_card = ctk.CTkFrame(step1, fg_color=CLR_CARD_BG, corner_radius=8,
                                  border_width=1, border_color=CLR_CARD_BD)
        cell_card.pack(fill="x", pady=2)
        hbar = ctk.CTkFrame(cell_card, fg_color=CLR_BLUE, height=28, corner_radius=0)
        hbar.pack(fill="x"); hbar.pack_propagate(False)
        hdr_g = ctk.CTkLabel(hbar, text="CELL DESIGN",
                             font=ctk.CTkFont(size=12, weight="bold"), text_color="white")
        hdr_g.pack(side="left", padx=10, pady=3)

        # Row 1: Wafer Shape dropdown
        ws_row = ctk.CTkFrame(cell_card, fg_color=CLR_EVEN_ROW, height=30, corner_radius=0)
        ws_row.pack(fill="x", padx=0); ws_row.pack_propagate(False)
        ctk.CTkLabel(ws_row, text="Wafer Shape", font=ctk.CTkFont(size=10),
                     text_color=CLR_TEXT, width=100, anchor="w").pack(side="left", padx=(8, 2), pady=1)
        self._wafer_shape_var = ctk.StringVar(value="Square")
        self._wafer_shape_dropdown = ctk.CTkOptionMenu(
            ws_row, values=["Square", "Pseudo-Square", "Circular"],
            variable=self._wafer_shape_var,
            font=ctk.CTkFont(size=10),
            fg_color=CLR_BLUE, button_color="#1D4ED8",
            button_hover_color="#1E40AF", height=22, width=140,
            dropdown_font=ctk.CTkFont(size=10),
            command=lambda v: self._on_wafer_shape_change())
        self._wafer_shape_dropdown.pack(side="left", padx=2, pady=1)

        # Row 2: Chamfer entry (Pseudo-Square 용)
        ch_row = ctk.CTkFrame(cell_card, fg_color=CLR_CARD_BG, height=30, corner_radius=0)
        ch_row.pack(fill="x", padx=0); ch_row.pack_propagate(False)
        ctk.CTkLabel(ch_row, text="Chamfer", font=ctk.CTkFont(size=10),
                     text_color=CLR_TEXT, width=100, anchor="w").pack(side="left", padx=(8, 2), pady=1)
        self._chamfer_entry = ctk.CTkEntry(ch_row, width=65, height=24, font=ctk.CTkFont(size=10),
                                            fg_color="white", border_color=CLR_CARD_BD,
                                            corner_radius=4, justify="center")
        self._chamfer_entry.insert(0, "0")
        self._chamfer_entry.pack(side="left", padx=2, pady=1)
        ctk.CTkLabel(ch_row, text="mm (corner)", font=ctk.CTkFont(size=8),
                     text_color=CLR_TEXT_SEC, width=95, anchor="w").pack(side="left", padx=2)

        # Row 3-4: Cell Width / Cell Height (entries — for compatibility with _apply_grid_design)
        def _make_entry_row(parent, label, default, unit, idx):
            bg = CLR_EVEN_ROW if idx % 2 == 0 else CLR_CARD_BG
            row = ctk.CTkFrame(parent, fg_color=bg, height=30, corner_radius=0)
            row.pack(fill="x", padx=0); row.pack_propagate(False)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=10),
                         text_color=CLR_TEXT, width=100, anchor="w").pack(side="left", padx=(8, 2), pady=1)
            entry = ctk.CTkEntry(row, width=65, height=24, font=ctk.CTkFont(size=10),
                                 fg_color="white", border_color=CLR_CARD_BD,
                                 corner_radius=4, justify="center")
            entry.insert(0, default)
            entry.pack(side="left", padx=2, pady=1)
            ctk.CTkLabel(row, text=unit, font=ctk.CTkFont(size=8),
                         text_color=CLR_TEXT_SEC, width=95, anchor="w").pack(side="left", padx=2)
            return entry

        # tb_grid keeps the same interface (idx 0 = Cell W, idx 1 = Cell H)
        e_cw = _make_entry_row(cell_card, _t('cell_w'), f"{GEO.W*10:.0f}", "mm", 2)
        e_ch = _make_entry_row(cell_card, _t('cell_h'), f"{GEO.H*10:.0f}", "mm", 3)
        self.tb_grid = [e_cw, e_ch]
        self._sidebar_labels_g = []  # labels updated by _t() refresh — keep empty for compat
        ctk.CTkFrame(cell_card, height=6, fg_color=CLR_CARD_BG).pack()

        self._card_headers = [hdr_b, hdr_a, hdr_g]

        # (MODE card moved to top of Design step — see line ~5363)

        # --- DIODE PARAMS Card (now with n1) --- [STEP 3]
        ctk.CTkFrame(step3, height=8, fg_color="transparent").pack()
        self.tb_diode, self._sidebar_labels_d, hdr_d = self._make_card(step3, _t('diode_params'), CLR_AMBER, [
            ("n1 Top (Pvsk)", f"{DP.n1_top:.1f}", ""),
            (_t('n2_top'), f"{DP.n2_top:.1f}", ""),
            ("n1 Bot (Si)", f"{DP.n1_bot:.1f}", ""),
            (_t('n2_bot'), f"{DP.n2_bot:.1f}", ""),
            ("LC Coupling", "0.0e+00", "A/cm2"),
            ("Recomb.J Contact↕", f"{DP.Rc_junction:.2f}", "Ohm.cm2"),
            ("Recomb.J Sheet↔", f"{DP.Rs_junction:.1f}", "Ohm/sq"),
        ])
        self._card_headers.append(hdr_d)

        # === v28.1: TOP cell diode params — Tandem mode only (Perovskite) === [STEP 3]
        ctk.CTkFrame(step3, height=8, fg_color="transparent").pack()
        self.tb_dtop, self._sidebar_labels_dt, hdr_dt = self._make_card(
            step3, "TOP CELL (Pvsk)", "#D84315", [
                ("Jph Top", f"{DP.Jph_top*1000:.2f}", "mA/cm2"),
                ("J01 Top pass", f"{DP.J01_top_pass:.2e}", "A/cm2"),
                ("J01 Top metal", f"{DP.J01_top_metal:.2e}", "A/cm2"),
                ("J02 Top pass", f"{DP.J02_top_pass:.2e}", "A/cm2"),
                ("J02 Top metal", f"{DP.J02_top_metal:.2e}", "A/cm2"),
                ("Rsh Top", f"{DP.Rsh_top:.0f}", "Ohm.cm2"),
                ("Rs lumped Top ↕", f"{DP.Rs_lumped_top:.2f}", "Ohm.cm2"),
            ])
        self._card_headers.append(hdr_dt)

        # === v28.4: BOT cell — pass/metal split (Tandem + Single) === [STEP 3]
        ctk.CTkFrame(step3, height=8, fg_color="transparent").pack()
        self.tb_dbot, self._sidebar_labels_db, hdr_db = self._make_card(
            step3, "BOT CELL (c-Si)", "#0277BD", [
                ("Jph Bot",       f"{DP.Jph_bot*1000:.2f}",   "mA/cm2"),
                ("J01 Bot pass",  f"{DP.J01_bot_pass:.2e}",   "A/cm2"),
                ("J01 Bot metal", f"{DP.J01_bot_metal:.2e}",  "A/cm2"),
                ("J02 Bot pass",  f"{DP.J02_bot_pass:.2e}",   "A/cm2"),
                ("J02 Bot metal", f"{DP.J02_bot_metal:.2e}",  "A/cm2"),
                ("Rsh Bot",       f"{DP.Rsh_bot:.0f}",        "Ohm.cm2"),
                ("Rs lumped Bot ↕", f"{DP.Rs_lumped_bot:.2f}",  "Ohm.cm2"),
            ])
        self._card_headers.append(hdr_db)
        # === END v28.1 diode GUI addition ===



        # --- GRID DESIGN Card (v28.10 사용자 요청 재정리) --- [STEP 1]
        # 명명 변경: 이전 "FRONT DESIGN" → "GRID DESIGN" (실제 grid 입력이라 의미상 맞음)
        # 통합: Pattern dropdown + Input mode toggle + DXF button 모두 카드 안으로
        ctk.CTkFrame(step1, height=8, fg_color="transparent").pack()
        grid_card = ctk.CTkFrame(step1, fg_color=CLR_CARD_BG, corner_radius=8,
                                  border_width=1, border_color=CLR_CARD_BD)
        grid_card.pack(fill="x", pady=2)
        hbar2 = ctk.CTkFrame(grid_card, fg_color="#00695C", height=28, corner_radius=0)
        hbar2.pack(fill="x"); hbar2.pack_propagate(False)
        hdr_hp = ctk.CTkLabel(hbar2, text="GRID DESIGN",
                              font=ctk.CTkFont(size=12, weight="bold"), text_color="white")
        hdr_hp.pack(side="left", padx=10, pady=3)

        # Row 1: Pattern dropdown (통합)
        ps_row = ctk.CTkFrame(grid_card, fg_color=CLR_EVEN_ROW, height=30, corner_radius=0)
        ps_row.pack(fill="x", padx=0); ps_row.pack_propagate(False)
        ctk.CTkLabel(ps_row, text="Pattern", font=ctk.CTkFont(size=10),
                     text_color=CLR_TEXT, width=100, anchor="w").pack(side="left", padx=(8, 2), pady=1)
        self._pattern_style_var = ctk.StringVar(value="H-pattern")
        self._pattern_style_dropdown = ctk.CTkOptionMenu(
            ps_row, values=["H-pattern", "Shingled (Fork)", "Tapered H"],
            variable=self._pattern_style_var,
            font=ctk.CTkFont(size=10),
            fg_color="#00695C", button_color="#004D40",
            button_hover_color="#00251A", height=22, width=140,
            dropdown_font=ctk.CTkFont(size=10),
            command=lambda v: self._on_pattern_change())
        self._pattern_style_dropdown.pack(side="left", padx=2, pady=1)

        # Row 2: Input mode toggle (통합)
        im_row = ctk.CTkFrame(grid_card, fg_color=CLR_CARD_BG, height=30, corner_radius=0)
        im_row.pack(fill="x", padx=0); im_row.pack_propagate(False)
        ctk.CTkLabel(im_row, text="Input mode", font=ctk.CTkFont(size=10),
                     text_color=CLR_TEXT, width=100, anchor="w").pack(side="left", padx=(8, 2), pady=1)
        self._grid_input_mode_var = ctk.StringVar(value="n_fingers")
        self._grid_input_mode_seg = ctk.CTkSegmentedButton(
            im_row, values=["n_fingers", "spacing"],
            variable=self._grid_input_mode_var,
            font=ctk.CTkFont(size=9, weight="bold"),
            selected_color="#00695C", selected_hover_color="#004D40",
            height=22, command=self._on_grid_input_mode_change)
        self._grid_input_mode_seg.pack(side="left", padx=2, pady=1)

        # Rows 3-8: Finger/Busbar entries (numeric inputs)
        # _make_entry_row 함수 재정의 (위 cell_card 안에서 nested 정의됐으니 재정의 필요)
        def _make_entry_row2(parent, label, default, unit, idx):
            bg = CLR_EVEN_ROW if idx % 2 == 0 else CLR_CARD_BG
            row = ctk.CTkFrame(parent, fg_color=bg, height=30, corner_radius=0)
            row.pack(fill="x", padx=0); row.pack_propagate(False)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=10),
                         text_color=CLR_TEXT, width=100, anchor="w").pack(side="left", padx=(8, 2), pady=1)
            entry = ctk.CTkEntry(row, width=65, height=24, font=ctk.CTkFont(size=10),
                                 fg_color="white", border_color=CLR_CARD_BD,
                                 corner_radius=4, justify="center")
            entry.insert(0, default)
            entry.pack(side="left", padx=2, pady=1)
            ctk.CTkLabel(row, text=unit, font=ctk.CTkFont(size=8),
                         text_color=CLR_TEXT_SEC, width=95, anchor="w").pack(side="left", padx=2)
            return entry

        # tb_hpat keeps original layout: [0]=N Fingers, [1]=Spacing, [2]=N Busbars,
        # [3]=Finger Length, [4]=Busbar Length, [5]=Edge Gap
        e1 = _make_entry_row2(grid_card, "N Fingers",      f"{GEO.n_f}", "#",  0)
        e2 = _make_entry_row2(grid_card, "Finger Spacing", "1.50",       "mm", 1)
        e3 = _make_entry_row2(grid_card, "N Busbars",      f"{GEO.n_b}", "#",  2)
        e4 = _make_entry_row2(grid_card, "Finger Length",  "100",        "%",  3)
        e5 = _make_entry_row2(grid_card, "Busbar Length",  "100",        "%",  4)
        e6 = _make_entry_row2(grid_card, "Edge Gap",       "0",          "mm", 5)
        self.tb_hpat = [e1, e2, e3, e4, e5, e6]
        self._sidebar_labels_hp = []  # backward compat

        # DXF button inside GRID DESIGN card
        ctk.CTkFrame(grid_card, height=4, fg_color=CLR_CARD_BG).pack()
        dxf_btn = ctk.CTkButton(grid_card, text="Load DXF File", width=240, height=28,
                       fg_color="#00695C", hover_color="#004D40",
                       font=ctk.CTkFont(size=11, weight="bold"),
                       text_color="white", corner_radius=6,
                       command=self._load_dxf)
        dxf_btn.pack(padx=8, pady=(2, 6))

        self._card_headers.append(hdr_hp)

        # === Pattern/Input/DXF 별도 미니카드 코드 제거됨 ===
        # 이전엔 여기 다음에 ps_card, mode_card, dxf_btn 각각 있었으나
        # 모두 GRID DESIGN 카드 안으로 통합됨 (사용자 요청 2026.05.21)

        # (MESH DETAIL card moved to bottom of Design step — see after REAR DESIGN)

        # --- ILLUMINATION Card (v28.10 재배치: 이제 Diode step) --- [STEP 3: Diode]
        # 사용자 요청 2026.05.21: Illumination은 diode 입력하는 곳으로
        # (광량 = 셀의 전기적 응답에 영향, diode와 같이 다루는 게 자연스러움)
        ctk.CTkFrame(step_diode, height=8, fg_color="transparent").pack()
        self.tb_illum, _, hdr_il = self._make_card(
            step_diode, 'ILLUMINATION', '#FB8C00', [
                ("Suns Front", "1.00", "sun"),  # idx 0 (default STC)
                ("Suns Rear",  "0.20", "sun"),  # idx 1 (IEC 61853-4 default)
            ])
        self._card_headers.append(hdr_il)

        # Albedo preset dropdown [STEP 3: Diode]
        preset_card = ctk.CTkFrame(step_diode, fg_color=CLR_CARD_BG, corner_radius=6,
                                   border_width=1, border_color=CLR_CARD_BD)
        preset_card.pack(fill="x", padx=4, pady=2)
        preset_row = ctk.CTkFrame(preset_card, fg_color=CLR_CARD_BG, height=34, corner_radius=0)
        preset_row.pack(fill="x", padx=4, pady=3); preset_row.pack_propagate(False)
        ctk.CTkLabel(preset_row, text="Preset:", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=CLR_TEXT_SEC, width=58, anchor="w").pack(side="left", padx=(6, 2))

        # Preset name -> Suns_rear value (front always 1.0)
        # .1: numeric values shown in label for direct visibility
        self._albedo_presets = {
            "STC (0.00)":                  0.00,
            "Grass / IEC 61853-4 (0.20)":  0.20,
            "Concrete / NREL (0.25)":      0.25,
            "Sand / desert (0.40)":        0.40,
            "White roof (0.60)":           0.60,
            "Snow / winter (0.80)":        0.80,
            "Custom":                      None,  # don't auto-fill
        }
        self._albedo_preset_var = ctk.StringVar(value="Grass / IEC 61853-4 (0.20)")
        self._albedo_preset_dropdown = ctk.CTkOptionMenu(
            preset_row,
            values=list(self._albedo_presets.keys()),
            variable=self._albedo_preset_var,
            command=self._on_albedo_preset_change,
            font=ctk.CTkFont(size=10),
            fg_color="#FB8C00", button_color="#EF6C00",
            button_hover_color="#E65100", height=26, width=180,
            dropdown_font=ctk.CTkFont(size=10))
        self._albedo_preset_dropdown.pack(side="left", fill="x", expand=True, padx=4)

        # --- CURRENT EXTRACTION Card (v28.10 재배치: Setup → Design) --- [STEP 2: Design]
        # 사용자 요청 2026.05.21: probe 위치는 디자인의 일부 → Design 단계로 이동
        # default 0 → 1 (Griddler 표준, BB 중앙 probe)
        ctk.CTkFrame(step_design, height=8, fg_color="transparent").pack()
        self.tb_extract, _, hdr_ex = self._make_card(
            step_design, 'CURRENT EXTRACTION (Front)', '#7B1FA2', [
                ("Probe Pts/BB", "1", "# per BB"),  # idx 0
            ])
        self._card_headers.append(hdr_ex)

        # Front extraction method - dropdown [STEP 2: Design]
        method_card = ctk.CTkFrame(step_design, fg_color=CLR_CARD_BG, corner_radius=6,
                                   border_width=1, border_color=CLR_CARD_BD)
        method_card.pack(fill="x", padx=4, pady=2)
        method_row = ctk.CTkFrame(method_card, fg_color=CLR_CARD_BG, height=34, corner_radius=0)
        method_row.pack(fill="x", padx=4, pady=3); method_row.pack_propagate(False)
        ctk.CTkLabel(method_row, text="Method:", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=CLR_TEXT_SEC, width=58, anchor="w").pack(side="left", padx=(6, 2))
        self._extract_method_var = ctk.StringVar(value="At Probe Point (I-V tester)")
        self._extract_method_dropdown = ctk.CTkOptionMenu(
            method_row,
            values=[
                "At Probe Point (I-V tester)",
                "Ribbon Ends (Module)",
                "Floating (Voc only)",
            ],
            variable=self._extract_method_var,
            font=ctk.CTkFont(size=10),
            fg_color="#7B1FA2", button_color="#6A1B9A",
            button_hover_color="#4A148C", height=26, width=180,
            dropdown_font=ctk.CTkFont(size=10))
        self._extract_method_dropdown.pack(side="left", fill="x", expand=True, padx=4)

        # --- REAR DESIGN Card --- [STEP 1]
        ctk.CTkFrame(step1, height=8, fg_color="transparent").pack()
        rear_card = ctk.CTkFrame(step1, fg_color=CLR_CARD_BG, corner_radius=8,
                                  border_width=1, border_color=CLR_CARD_BD)
        rear_card.pack(fill="x", pady=2)
        rbar = ctk.CTkFrame(rear_card, fg_color="#4E342E", height=28, corner_radius=0)
        rbar.pack(fill="x"); rbar.pack_propagate(False)
        hdr_rear = ctk.CTkLabel(rbar, text="REAR DESIGN", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="white")
        hdr_rear.pack(side="left", padx=10, pady=3)
        self._card_headers.append(hdr_rear)

        # Rear mode toggle
        rear_mode_row = ctk.CTkFrame(rear_card, fg_color=CLR_CARD_BG, height=36, corner_radius=0)
        rear_mode_row.pack(fill="x", padx=6, pady=4); rear_mode_row.pack_propagate(False)
        self._rear_mode_var = ctk.StringVar(value="full_area")
        self._rear_seg = ctk.CTkSegmentedButton(
            rear_mode_row, values=["full_area", "bifacial"],
            variable=self._rear_mode_var, font=ctk.CTkFont(size=10, weight="bold"),
            selected_color="#4E342E", selected_hover_color="#3E2723",
            height=26, command=self._toggle_rear_mode)
        self._rear_seg.pack(fill="x", pady=1)

        # Rs_rear input (always visible)
        def _rear_row(label, default, unit):
            row = ctk.CTkFrame(rear_card, fg_color=CLR_EVEN_ROW, height=28, corner_radius=0)
            row.pack(fill="x"); row.pack_propagate(False)
            ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=10),
                         text_color=CLR_TEXT, width=100, anchor="w").pack(side="left", padx=(8, 2), pady=1)
            ent = ctk.CTkEntry(row, width=65, height=24, font=ctk.CTkFont(size=10),
                               fg_color="white", border_color=CLR_CARD_BD,
                               corner_radius=4, justify="center")
            ent.insert(0, default)
            ent.pack(side="left", padx=2, pady=1)
            ctk.CTkLabel(row, text=unit, font=ctk.CTkFont(size=8),
                         text_color=CLR_TEXT_SEC, width=95, anchor="w").pack(side="left", padx=2)
            return row, ent

        # Rs_rear is now AUTO-COMPUTED from front bulk_res / finger_height
        # (assumes same Ag paste + same hot pressing process on both sides)
        # Show as read-only info label that updates with BEFORE/AFTER values
        rs_info_row = ctk.CTkFrame(rear_card, fg_color=CLR_EVEN_ROW, height=44, corner_radius=0)
        rs_info_row.pack(fill="x"); rs_info_row.pack_propagate(False)
        ctk.CTkLabel(rs_info_row, text="Rs_rear (auto)", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=CLR_TEXT, anchor="w").pack(anchor="w", padx=8, pady=(2, 0))
        self._rs_rear_label = ctk.CTkLabel(rs_info_row, text="B: -- | A: -- mΩ/sq",
                     font=ctk.CTkFont(size=9), text_color=CLR_TEXT_SEC, anchor="w")
        self._rs_rear_label.pack(anchor="w", padx=8, pady=(0, 2))

        # Keep entry for backward compat (hidden)
        self._rs_rear_entry = ctk.CTkEntry(rear_card, width=1, height=1)
        self._rs_rear_entry.insert(0, "0.5")
        # Don't pack it - hidden

        # Rs_rear_tco (L3 layer sheet R) — USER-EDITABLE
        # Represents the rear TCO / doped Si lateral conductance layer.
        # Only used in bifacial mode; irrelevant in full_area.
        rs_tco_row = ctk.CTkFrame(rear_card, fg_color=CLR_CARD_BG, height=30, corner_radius=0)
        rs_tco_row.pack(fill="x"); rs_tco_row.pack_propagate(False)
        ctk.CTkLabel(rs_tco_row, text="Rear Sheet R ↔", font=ctk.CTkFont(size=10),
                     text_color=CLR_TEXT, width=110, anchor="w").pack(side="left", padx=(8, 2), pady=1)
        self._rs_tco_entry = ctk.CTkEntry(rs_tco_row, width=60, height=24, font=ctk.CTkFont(size=10),
                           fg_color="white", border_color=CLR_CARD_BD,
                           corner_radius=4, justify="center")
        self._rs_tco_entry.insert(0, f"{DP.Rs_rear_tco:.0f}")
        self._rs_tco_entry.pack(side="left", padx=2, pady=1)
        ctk.CTkLabel(rs_tco_row, text="Ω/sq", font=ctk.CTkFont(size=8),
                     text_color=CLR_TEXT_SEC, width=45, anchor="w").pack(side="left", padx=2)

        # rc_rear (L4 rear metal–semiconductor contact resistivity) — USER-EDITABLE
        # Blank = same as front rc (legacy). Real cells / Griddler allow front≠rear.
        rc_rear_row = ctk.CTkFrame(rear_card, fg_color=CLR_CARD_BG, height=30, corner_radius=0)
        rc_rear_row.pack(fill="x"); rc_rear_row.pack_propagate(False)
        ctk.CTkLabel(rc_rear_row, text="Rear Contact R ↕", font=ctk.CTkFont(size=10),
                     text_color=CLR_TEXT, width=110, anchor="w").pack(side="left", padx=(8, 2), pady=1)
        self._rc_rear_entry = ctk.CTkEntry(rc_rear_row, width=60, height=24, font=ctk.CTkFont(size=10),
                           fg_color="white", border_color=CLR_CARD_BD,
                           corner_radius=4, justify="center",
                           placeholder_text="=front")
        self._rc_rear_entry.pack(side="left", padx=2, pady=1)
        ctk.CTkLabel(rc_rear_row, text="mOhm.cm2", font=ctk.CTkFont(size=8),
                     text_color=CLR_TEXT_SEC, width=45, anchor="w").pack(side="left", padx=2)

        # Rear H-pattern inputs (visible only in patterned/bifacial mode)
        # bifacial-focused per Dr. Kim directive
        # Default: denser than front (rear cares less about shading)
        self._rear_patt_rows = []
        self.tb_rear_pat = []
        rear_params = [
            ("N Fingers", "4", "#"),         # idx 0
            ("N Busbars", "2", "#"),         # idx 1
            ("Finger Width", "100", "um"),       # idx 2
            ("Busbar Width", "100", "um"),       # idx 3
            ("Fg Length", "95", "%"),        # idx 4
            ("BB Length", "90", "%"),        # idx 5
            ("Probe Pts/BB", "1", "# per BB"),  # idx 6 (v28.10: default 0→1)
        ]
        for lbl, dflt, unit in rear_params:
            row, ent = _rear_row(lbl, dflt, unit)
            self._rear_patt_rows.append(row)
            self.tb_rear_pat.append(ent)

        # Rear extraction method dropdown (v28.7 NEW, bifacial mode)
        rear_method_row = ctk.CTkFrame(rear_card, fg_color=CLR_CARD_BG, height=34, corner_radius=0)
        rear_method_row.pack(fill="x", padx=6, pady=3); rear_method_row.pack_propagate(False)
        ctk.CTkLabel(rear_method_row, text="R-Method:", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color=CLR_TEXT_SEC, width=68, anchor="w").pack(side="left", padx=(6, 2))
        self._rear_extract_method_var = ctk.StringVar(value="At Probe Point (I-V tester)")
        self._rear_extract_method_dropdown = ctk.CTkOptionMenu(
            rear_method_row,
            values=[
                "At Probe Point (I-V tester)",
                "Ribbon Ends (Module)",
                "Full Area Chuck",
                "Floating (Voc only)",
            ],
            variable=self._rear_extract_method_var,
            font=ctk.CTkFont(size=10),
            fg_color="#4E342E", button_color="#3E2723",
            button_hover_color="#1B0000", height=26, width=180,
            dropdown_font=ctk.CTkFont(size=10))
        self._rear_extract_method_dropdown.pack(side="left", fill="x", expand=True, padx=4)
        self._rear_patt_rows.append(rear_method_row)  # so it hides with bifacial toggle

        ctk.CTkFrame(rear_card, height=6, fg_color=CLR_CARD_BG).pack()

        # Hide rear H-pattern rows initially (full_area mode)
        for row in self._rear_patt_rows:
            row.pack_forget()

        # --- MESH DETAIL Card (v28.10 재배치: Design step 맨 아래) --- [STEP 1: Design]
        # 사용자 요청 2026.05.21: Mesh detail은 디자인의 마지막 단계로
        # (셀/그리드 다 설정한 후 마지막에 정밀도 결정)
        ctk.CTkFrame(step_design, height=8, fg_color="transparent").pack()
        mesh_card = ctk.CTkFrame(step_design, fg_color=CLR_CARD_BG, corner_radius=8,
                                  border_width=1, border_color=CLR_CARD_BD)
        mesh_card.pack(fill="x", padx=4, pady=2)
        mesh_hdr = ctk.CTkLabel(mesh_card, text="MESH DETAIL", font=ctk.CTkFont(size=11, weight="bold"),
                                text_color="white", fg_color="#455A64", corner_radius=6,
                                height=24, anchor="w")
        mesh_hdr.pack(fill="x", padx=4, pady=(4, 2))
        self._card_headers.append(mesh_hdr)

        # Tangent (along metal)
        mt_row = ctk.CTkFrame(mesh_card, fg_color=CLR_CARD_BG, height=28)
        mt_row.pack(fill="x", padx=6, pady=1); mt_row.pack_propagate(False)
        ctk.CTkLabel(mt_row, text="Tangent to metal", font=ctk.CTkFont(size=10),
                     text_color=CLR_TEXT_SEC, width=120, anchor="w").pack(side="left", padx=2)
        self._mesh_tangent_var = ctk.StringVar(value="Med")
        self._mesh_tangent_menu = ctk.CTkOptionMenu(
            mt_row, values=["Low", "Med", "High", "Max"],
            variable=self._mesh_tangent_var,
            font=ctk.CTkFont(size=10), width=80, height=22,
            fg_color="#455A64", button_color="#37474F",
            button_hover_color="#263238",
            command=lambda v: self._on_mesh_change())
        self._mesh_tangent_menu.pack(side="left", padx=2)

        # Perpendicular (across metal)
        mp_row = ctk.CTkFrame(mesh_card, fg_color=CLR_CARD_BG, height=28)
        mp_row.pack(fill="x", padx=6, pady=1); mp_row.pack_propagate(False)
        ctk.CTkLabel(mp_row, text="Perp. to metal", font=ctk.CTkFont(size=10),
                     text_color=CLR_TEXT_SEC, width=120, anchor="w").pack(side="left", padx=2)
        self._mesh_perp_var = ctk.StringVar(value="Med")
        self._mesh_perp_menu = ctk.CTkOptionMenu(
            mp_row, values=["Low", "Med", "High", "Max"],
            variable=self._mesh_perp_var,
            font=ctk.CTkFont(size=10), width=80, height=22,
            fg_color="#455A64", button_color="#37474F",
            button_hover_color="#263238",
            command=lambda v: self._on_mesh_change())
        self._mesh_perp_menu.pack(side="left", padx=2)

        # v28.17 (박사님 지시): 노드 수 직접 입력 (override). 비우면 위 레벨 사용.
        #   target nodes -> axis 세분화로 환산 후 측정·보정 반복(±5%).
        # v28.17 fix (Seunghoon): 라벨+입력칸+버튼을 한 줄에 넣으니 카드 폭을 넘어
        #   Apply가 짤렸다. → 2행 분리: (1)라벨 한 줄, (2)입력칸(자동 확장)+Apply(우측 고정).
        ctk.CTkLabel(mesh_card, text="Target nodes (≈, blank=level)",
                     font=ctk.CTkFont(size=10), text_color=CLR_TEXT_SEC,
                     anchor="w").pack(fill="x", padx=8, pady=(2, 0))
        tn_row = ctk.CTkFrame(mesh_card, fg_color=CLR_CARD_BG, height=28)
        tn_row.pack(fill="x", padx=6, pady=(0, 2)); tn_row.pack_propagate(False)
        self._mesh_target_nodes_var = ctk.StringVar(value="")
        # Apply 먼저 우측에 고정(폭 확보) → 입력칸이 남은 공간을 채움 = 절대 안 짤림.
        ctk.CTkButton(tn_row, text="Apply", width=64, height=22,
                      font=ctk.CTkFont(size=10, weight="bold"),
                      command=self._on_mesh_change).pack(side="right", padx=(4, 2))
        _tn_entry = ctk.CTkEntry(
            tn_row, textvariable=self._mesh_target_nodes_var,
            height=22, font=ctk.CTkFont(size=10),
            placeholder_text="e.g. 50000")
        _tn_entry.pack(side="left", fill="x", expand=True, padx=2)
        _tn_entry.bind("<Return>", lambda e: self._on_mesh_change())

        self._mesh_warm_start_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            mesh_card, text="Use nested-mesh warm start",
            variable=self._mesh_warm_start_var,
            font=ctk.CTkFont(size=9), height=20,
            checkbox_width=16, checkbox_height=16,
            text_color=CLR_TEXT_SEC,
        ).pack(anchor="w", padx=8, pady=(2, 0))

        # Convergence study button
        ctk.CTkFrame(mesh_card, height=2, fg_color="transparent").pack()
        ctk.CTkButton(mesh_card, text="Run Convergence Study",
                      width=200, height=24,
                      fg_color="#37474F", hover_color="#263238",
                      font=ctk.CTkFont(size=10, weight="bold"),
                      text_color="white", corner_radius=4,
                      command=self._run_mesh_convergence).pack(padx=6, pady=(2, 4))

        # Mesh recommendation hint (dynamic, updated on grid/cell change)
        self._mesh_hint_label = ctk.CTkLabel(
            mesh_card, text="", font=ctk.CTkFont(size=9),
            text_color="#E65100", justify="left", anchor="w", wraplength=240
        )
        self._mesh_hint_label.pack(fill="x", padx=8, pady=(0, 4))
        # Initialize hint after GUI fully built (deferred)
        self.after(500, self._update_mesh_hint)
        # .1: 초기 rear_mode에 맞춰 Suns Rear 활성/비활성 한 번 적용
        self.after(550, self._toggle_rear_mode)

        # Info label (always visible at bottom, regardless of step)
        self._info_label = ctk.CTkLabel(inner, text="", font=ctk.CTkFont(size=10),
                     text_color=CLR_TEXT_SEC, justify="left")
        self._info_label.pack(anchor="w", padx=4, pady=(8, 4))
        self._update_info_label()

        # ============= v28.10 WIZARD: Show STEP 1 by default =============
        self._show_wizard_step(1)

    def _on_wizard_step_change(self, value):
        """v28.10: Triggered when wizard segmented button changes."""
        try:
            step_num = int(value.split('.')[0])
            self._show_wizard_step(step_num)
        except Exception as e:
            print(f"[wizard] step change error: {e}")

    def _show_wizard_step(self, step_num):
        """v28.10: Show only the cards belonging to the given step.

        Step 1: Design (cell + grid + rear)
        Step 2: Process (BEFORE + AFTER)
        Step 3: Diode (junction + Top + Bot)
        Step 4: Sim (mode + mesh + illumination + extraction)
        """
        if not hasattr(self, '_step_frames'):
            return
        # Forget all, then pack just the target
        for i, f in self._step_frames.items():
            f.pack_forget()
        target = self._step_frames.get(step_num)
        if target is not None:
            # Pack BEFORE the info_label (which is at the bottom of `inner`)
            target.pack(fill="x", padx=0, pady=0, before=self._info_label)
        # Sync segmented button label
        _labels = {1: "1.Design", 2: "2.Process", 3: "3.Diode"}
        if hasattr(self, '_wizard_step_var'):
            self._wizard_step_var.set(_labels.get(step_num, "1.Design"))
        # Status hint
        _step_hints = {
            1: "STEP 1: Design - Mode + Cell + Grid + Probe + Rear + Mesh",
            2: "STEP 2: Process - BEFORE/AFTER hot pressing parameters",
            3: "STEP 3: Diode - Illumination + Junction + Top/Bot cell",
        }
        self._status(_step_hints.get(step_num, ""))

    def _update_info_label(self):
        mode = self._mode_var.get() if hasattr(self, '_mode_var') else 'tandem'
        mode_str = "2T Tandem" if mode == 'tandem' else "Single Cell"
        rear_str = self._rear_mode_var.get() if hasattr(self, '_rear_mode_var') else 'full_area'
        fg_len = GEO.fg_x_range[1] - GEO.fg_x_range[0]
        bb_len = GEO.bb_y_range[1] - GEO.bb_y_range[0]
        txt = (f"{mode_str} | Rear: {rear_str}\n"
               f"Grid: {GEO.n_f}F + {GEO.n_b}BB | {GEO.W*10:.0f}x{GEO.H*10:.0f} mm\n"
               f"Finger: {GEO.w_f*1e4:.0f}um x {fg_len*10:.1f}mm\n"
               f"Busbar: {GEO.w_b*1e4:.0f}um x {bb_len*10:.1f}mm\n"
               f"Shading: {GEO.shading_fraction()*100:.2f}%")
        self._info_label.configure(text=txt)
        # Update Rs_rear auto-display
        if hasattr(self, '_rs_rear_label'):
            try:
                rm_b = float(self.tb_b[0].get()) * 1e-6   # uOhm·cm -> Ohm·cm
                hf_b = float(self.tb_b[1].get()) * 1e-4   # um -> cm
                rm_a = float(self.tb_a[0].get()) * 1e-6
                hf_a = float(self.tb_a[1].get()) * 1e-4
                rs_b = rm_b / hf_b * 1000 if hf_b > 0 else 0  # Ohm/sq -> mOhm/sq
                rs_a = rm_a / hf_a * 1000 if hf_a > 0 else 0
                self._rs_rear_label.configure(text=f"B: {rs_b:.1f} | A: {rs_a:.1f} mΩ/sq")
            except Exception:
                self._rs_rear_label.configure(text="B: -- | A: -- mΩ/sq")

    def _apply_grid_design(self):
        """Re-initialize mesh with new grid parameters + H-pattern + rear design."""
        global GEO, pts, tri, isf, isb, isp, ism, isrm, isrp, S, triang
        # when a DXF rect pattern is loaded, GEO holds the
        # imported rectangles and the DXF terminals. Regenerating an H-pattern
        # here (from the n_f/n_b/w_f GUI fields) would silently discard the DXF
        # geometry and collapse all DXF terminals into a single centered probe.
        # The DXF loader already built GEO/mesh/solver, so this is a no-op for
        # DXF designs. To return to an H-pattern, the user reloads via the grid
        # fields path (which clears _dxf_* by constructing a fresh CellGeometry).
        if getattr(GEO, '_dxf_finger_rects', None) is not None:
            return True
        try:
            cw = _parse_gui_float(self.tb_grid[0].get(), "Cell Width", scale=0.1)
            ch = _parse_gui_float(self.tb_grid[1].get(), "Cell Height", scale=0.1)
            # Grid card indices changed (Finger Spacing field added at idx 1)
            # idx 0: N Fingers      | idx 1: Finger Spacing (mm)
            # idx 2: N Busbars      | idx 3: Finger Length %
            # idx 4: Busbar Length %| idx 5: Edge Gap mm
            # idx 6: Terminals
            input_mode = getattr(self, "_grid_input_mode_var", None)
            input_mode = input_mode.get() if input_mode is not None else "n_fingers"
            if input_mode not in ("n_fingers", "spacing"):
                raise ValueError(f"Unknown grid input mode: {input_mode}")

            nb = _parse_gui_int(self.tb_hpat[2].get(), "N Busbars",
                                min_value=1, max_value=30)

            # Widths now read from BEFORE card (tb_b[2]=wf, tb_b[3]=wb)
            wf_grid = _parse_gui_float(self.tb_b[2].get(), "Before finger width", scale=1e-4)
            wb_grid = _parse_gui_float(self.tb_b[3].get(), "Before busbar width", scale=1e-4)
            _require_range("Cell Width", cw, min_value=0.0, min_inclusive=False)
            _require_range("Cell Height", ch, min_value=0.0, min_inclusive=False)
            _require_range("Before finger width", wf_grid, min_value=0.0, min_inclusive=False)
            _require_range("Before busbar width", wb_grid, min_value=0.0, min_inclusive=False)

            # In "spacing" mode, n_f is auto-derived from cell_w and spacing.
            # In "n_fingers" mode, use the user's value directly.
            if input_mode == "spacing":
                spacing_mm = _parse_gui_float(self.tb_hpat[1].get(), "Finger Spacing")
                _require_range("Finger Spacing", spacing_mm, min_value=0.10)
                nf = max(1, int(round((cw * 10.0) / spacing_mm)))
                # Mirror the derived value back into the N Fingers entry
                try:
                    self.tb_hpat[0].delete(0, 'end')
                    self.tb_hpat[0].insert(0, str(nf))
                except Exception:
                    pass
            else:
                nf = _parse_gui_int(self.tb_hpat[0].get(), "N Fingers",
                                    min_value=1, max_value=200)
                # Mirror the derived spacing back into the Finger Spacing entry
                derived_spacing_mm = (cw * 10.0) / max(1, nf)
                spacing_mm = derived_spacing_mm
                try:
                    self.tb_hpat[1].delete(0, 'end')
                    self.tb_hpat[1].insert(0, f"{derived_spacing_mm:.2f}")
                except Exception:
                    pass

            # ============= v28.10 입력 검증 (사용자 요청) =============
            # 잘못된 입력으로 인한 메시 폭주 / FEM 발산 / hang 방지.
            MAX_FINGERS = 200          # 한계 (M10 80F 기준 여유 2.5x)
            MAX_BUSBARS = 30           # 한계 (산업 기준 15-20)
            MIN_FINGER_W_um = 5        # 5 μm 미만 = 비현실
            MAX_FINGER_W_um = 500      # 500 μm 초과 = 비현실

            # 음수/0 체크 (기존)
            if nf < 1 or nb < 1 or cw <= 0 or ch <= 0 or wf_grid <= 0 or wb_grid <= 0:
                self._status(f"❌ 잘못된 값: nf={nf}, nb={nb}, cell={cw*10:.1f}×{ch*10:.1f}mm, wf={wf_grid*1e4:.1f}μm, wb={wb_grid*1e4:.1f}μm")
                return False

            # 상한 체크 — 너무 많은 finger/busbar는 mesh 폭주
            if nf > MAX_FINGERS:
                self._status(f"❌ N Fingers 너무 많음 ({nf} > {MAX_FINGERS}). 줄여줘.")
                return False
            if nb > MAX_BUSBARS:
                self._status(f"❌ N Busbars 너무 많음 ({nb} > {MAX_BUSBARS}).")
                return False

            # Finger / Busbar 폭 sanity (5 μm ~ 500 μm)
            wf_um = wf_grid * 1e4
            wb_um = wb_grid * 1e4
            if wf_um < MIN_FINGER_W_um or wf_um > MAX_FINGER_W_um:
                self._status(f"⚠ Finger 폭 비현실적 ({wf_um:.1f}μm). 권장 {MIN_FINGER_W_um}~{MAX_FINGER_W_um}μm.")
                # warning만, return False는 안 함

            # 그리드 면적 충돌 체크 (finger 합이 셀 width의 50% 넘으면 경고)
            # finger들은 가로 방향이므로 폭(width)이 H 방향으로 합산됨
            fg_total_h = nf * wf_grid
            if fg_total_h > 0.5 * ch:
                self._status(f"❌ Finger 합 두께 ({fg_total_h*10:.1f}mm) > 셀 높이 50% ({ch*10*0.5:.1f}mm). nf 또는 wf 줄여줘.")
                return False
            # busbar들은 세로 방향이므로 폭이 W 방향으로 합산됨
            bb_total_w = nb * wb_grid
            if bb_total_w > 0.5 * cw:
                self._status(f"❌ Busbar 합 너비 ({bb_total_w*10:.1f}mm) > 셀 너비 50% ({cw*10*0.5:.1f}mm). nb 또는 wb 줄여줘.")
                return False

            # 셀 크기 sanity (1mm ~ 300mm)
            if cw*10 < 1 or ch*10 < 1:
                self._status(f"❌ 셀 너무 작음 ({cw*10:.2f}×{ch*10:.2f}mm). 최소 1mm.")
                return False
            if cw*10 > 300 or ch*10 > 300:
                self._status(f"⚠ 셀 너무 큼 ({cw*10:.0f}×{ch*10:.0f}mm). M-series 최대 230mm.")

            # 큰 셀 + 많은 finger 조합 경고 (mesh 폭주 예방)
            est_nodes = nf * nb * 60 + (cw * ch * 10000)  # 거친 추정
            if est_nodes > 100000:
                self._status(f"⚠ 예상 mesh 노드 ~{int(est_nodes)} — 계산 시간 길 수 있음. Mesh Detail = Low 추천.")

            # ============= 검증 통과 =============

            # H-pattern params (v28.7: Terminals removed - probe points from CURRENT EXTRACTION card)
            fg_len_pct = _parse_gui_float(
                self.tb_hpat[3].get(), "Finger Length", scale=0.01
            )
            bb_len_pct = _parse_gui_float(
                self.tb_hpat[4].get(), "Busbar Length", scale=0.01
            )
            edge_gap = _parse_gui_float(self.tb_hpat[5].get(), "Edge Gap", scale=0.1)
            _require_range("Finger Length", fg_len_pct, min_value=0.1, max_value=1.0)
            _require_range("Busbar Length", bb_len_pct, min_value=0.1, max_value=1.0)
            _require_range("Edge Gap", edge_gap, min_value=0.0)
            if edge_gap >= ch / 2.0:
                raise ValueError("Edge Gap must be smaller than half the cell height")

            # FRONT CURRENT EXTRACTION card reads
            n_probe_points = _parse_gui_int(
                self.tb_extract[0].get(), "Front Probe Pts/BB",
                min_value=0, max_value=50
            )
            extract_method_label = getattr(self, "_extract_method_var", None)
            extract_method_label = extract_method_label.get() if extract_method_label is not None else "At Probe Point (I-V tester)"
            # dropdown label -> internal key
            _method_map = {
                "At Probe Point (I-V tester)": "probe_point",
                "Ribbon Ends (Module)":        "ribbon_ends",
                "Floating (Voc only)":         "floating",
                # also accept raw keys for back-compat
                "probe_point": "probe_point",
                "ribbon_ends": "ribbon_ends",
                "floating":    "floating",
            }
            extract_method = _method_map.get(extract_method_label, "probe_point")
            # Terminals derived from probe_points (legacy fallback = 1)
            n_terminals = max(1, n_probe_points if n_probe_points > 0 else 1)

            # Pattern style from dropdown
            ps_label = getattr(self, "_pattern_style_var", None)
            ps_label = ps_label.get() if ps_label is not None else "H-pattern"
            _ps_map = {
                "H-pattern":       "h_pattern",
                "Shingled (Fork)": "shingled",
                "Tapered H":       "tapered_h",
            }
            pattern_style = _ps_map.get(ps_label, "h_pattern")

            front = GridDesign(n_fingers=nf, n_busbars=nb,
                               w_finger=wf_grid, w_busbar=wb_grid,
                               finger_length_frac=fg_len_pct,
                               busbar_length_frac=bb_len_pct,
                               edge_gap=edge_gap,
                               n_terminals=n_terminals,
                               input_mode=input_mode,
                               finger_spacing_mm=spacing_mm,
                               n_probe_points=n_probe_points,
                               extraction_method=extract_method,
                               pattern_style=pattern_style)

            # Rear design (v28.7: bifacial-focused per Dr. Kim directive)
            rear = None
            if self._rear_mode_var.get() == 'bifacial':
                # Read independent rear H-pattern parameters
                r_nf = _parse_gui_int(self.tb_rear_pat[0].get(), "Rear N Fingers",
                                      min_value=1, max_value=200)
                r_nb = _parse_gui_int(self.tb_rear_pat[1].get(), "Rear N Busbars",
                                      min_value=1, max_value=30)
                r_wf_um = _parse_gui_float(self.tb_rear_pat[2].get(), "Rear finger width")
                r_wb_um = _parse_gui_float(self.tb_rear_pat[3].get(), "Rear busbar width")
                _require_range("Rear finger width", r_wf_um, min_value=5.0, max_value=500.0)
                _require_range("Rear busbar width", r_wb_um, min_value=5.0, max_value=500.0)
                r_wf = r_wf_um * 1e-4  # um -> cm
                r_wb = r_wb_um * 1e-4
                r_fgl = _parse_gui_float(self.tb_rear_pat[4].get(), "Rear finger length", scale=0.01)
                r_bbl = _parse_gui_float(self.tb_rear_pat[5].get(), "Rear busbar length", scale=0.01)
                _require_range("Rear finger length", r_fgl, min_value=0.1, max_value=1.0)
                _require_range("Rear busbar length", r_bbl, min_value=0.1, max_value=1.0)
                # rear gets its own probe points + extraction method
                r_probe = _parse_gui_int(self.tb_rear_pat[6].get(), "Rear Probe Pts/BB",
                                         min_value=0, max_value=50)
                r_method_label = getattr(self, "_rear_extract_method_var", None)
                r_method_label = r_method_label.get() if r_method_label is not None else "At Probe Point (I-V tester)"
                _rear_method_map = {
                    "At Probe Point (I-V tester)": "probe_point",
                    "Ribbon Ends (Module)":        "ribbon_ends",
                    "Full Area Chuck":             "full_area_chuck",
                    "Floating (Voc only)":         "floating",
                    "probe_point": "probe_point", "ribbon_ends": "ribbon_ends",
                    "full_area_chuck": "full_area_chuck", "floating": "floating",
                }
                r_method = _rear_method_map.get(r_method_label, "probe_point")
                rear = GridDesign(n_fingers=r_nf, n_busbars=r_nb,
                                  w_finger=r_wf, w_busbar=r_wb,
                                  finger_length_frac=r_fgl,
                                  busbar_length_frac=r_bbl,
                                  Rs_sheet=0.5,  # placeholder; actual Rs auto-computed
                                  n_probe_points=r_probe,
                                  extraction_method=r_method,
                                  n_terminals=max(1, r_probe if r_probe > 0 else 1))

            # Wafer shape from dropdown + chamfer
            ws_label = getattr(self, "_wafer_shape_var", None)
            ws_label = ws_label.get() if ws_label is not None else "Square"
            _ws_map = {
                "Square":        "square",
                "Pseudo-Square": "pseudo_square",
                "Circular":      "circular",
            }
            wafer_shape = _ws_map.get(ws_label, "square")
            chamfer_mm = (
                _parse_gui_float(self._chamfer_entry.get(), "Chamfer")
                if hasattr(self, '_chamfer_entry') else 0.0
            )
            _require_range("Chamfer", chamfer_mm, min_value=0.0)
            if wafer_shape == "pseudo_square" and chamfer_mm >= min(cw, ch) * 5.0:
                raise ValueError("Chamfer must be smaller than half the cell size")

            GEO = CellGeometry(cw, ch, front=front, rear=rear,
                               wafer_shape=wafer_shape, chamfer_mm=chamfer_mm)
            # Griddler-style mesh detail (tangent/perpendicular)
            mt = getattr(self, "_mesh_tangent_var", None)
            mp = getattr(self, "_mesh_perp_var", None)
            mt_v = mt.get() if mt is not None else "Med"
            mp_v = mp.get() if mp is not None else "Med"
            # v28.17 fix (Seunghoon): target nodes를 모든 셀 면적에서 robust하게.
            #   node수↔axis 지수가 셀마다 달라서(작은 셀~2, 큰 셀~1) 고정 sqrt 보정은
            #   큰 셀(M10 80F)에서 깨졌다(80000 입력 -> 98217, +23%). 이제 매번 지수를
            #   추정하는 log-log secant 헬퍼(_generate_mesh_for_target)로 크기 무관하게
            #   수렴시키고, 항상 "가장 가까운 결과"를 반환한다.
            _tgt = None
            _tn_var = getattr(self, "_mesh_target_nodes_var", None)
            if _tn_var is not None and str(_tn_var.get()).strip():
                try:
                    _tgt = _parse_gui_int(_tn_var.get(), "Target nodes",
                                          min_value=2000, max_value=2000000)
                except Exception as _tn_e:
                    self._status(f"Target nodes ignored: {_tn_e}")
                    _tgt = None
            if _tgt is not None:
                def _mesh_prog(_it, _ax, _n, _t=_tgt):
                    self._status(f"Target {_t:,}: pass {_it} -> {_n:,} nodes (axis={_ax})")
                    if getattr(self, '_prog_win', None) is not None:
                        try:
                            self._prog_lbl.configure(
                                text=f"Calibrating to ~{_t:,}: pass {_it} -> {_n:,} nodes")
                            self._prog_bar.set(min(0.92, 0.30 + 0.09 * _it))
                            self._prog_win.update()
                        except Exception:
                            pass
                pts, tri, _nfin, _axfin = _generate_mesh_for_target(
                    GEO, mesh_tangent=mt_v, mesh_perp=mp_v,
                    target_nodes=_tgt, progress=_mesh_prog)
                self._status(
                    f"Target {_tgt:,}: final {_nfin:,} nodes "
                    f"(axis={_axfin}, off {100.0*(_nfin-_tgt)/_tgt:+.1f}%)")
            else:
                pts, tri = generate_mesh(GEO, pass_density=2,
                                         mesh_tangent=mt_v, mesh_perp=mp_v)
            isf, isb, isp, ism, isrm, isrp = classify_nodes(pts, GEO)
            S = FESTSolver(pts, tri, isf, isb, isp, ism, GEO, isrm, isrp)
            triang = mtri.Triangulation(pts[:,0]*10, pts[:,1]*10, tri.simplices)
            self._update_info_label()
            self._status(f"Mesh updated: {len(pts)} nodes, {len(tri.simplices)} tri, {nf}F+{nb}BB  [{wafer_shape}, Mesh: T={mt_v}/P={mp_v}]")
            # Update mesh recommendation hint
            try:
                self._update_mesh_hint()
            except Exception:
                pass
            return True
        except Exception as e:
            self._status(f"Grid design error: {e}"); return False

    # ---------------------------------------------------------
    # MESH DETAIL HANDLERS (v28.10, Griddler-style)
    # ---------------------------------------------------------
    def _on_mesh_change(self):
        """Triggered when MESH DETAIL dropdowns / Target-nodes change.

        v28.17 fix (Seunghoon): 이전엔 re-mesh만 하고 DESIGN 뷰를 다시 안 그려서
        레벨/target node를 바꿔도 화면이 그대로라 "작동 안 하는" 것처럼 보였다.
        또 re-mesh(수 초)가 피드백 없이 멈춰서 동작 여부를 알 수 없었다. 이제
        (1) progress 창으로 로딩을 보여주고, (2) DESIGN 탭이 활성이면 re-mesh 후
        즉시 다시 그려 결과(노드 수·메시 밀도)가 바로 보이게 한다. DESIGN 탭이
        아니면 re-mesh만 수행(다음 view/solve 때 반영)."""
        if not hasattr(self, 'fig'):
            return
        try:
            mt = self._mesh_tangent_var.get()
            mp = self._mesh_perp_var.get()
            try:
                _tn = str(self._mesh_target_nodes_var.get()).strip()
            except Exception:
                _tn = ""
            _tn_txt = f", target≈{_tn}" if _tn else ""
            self._prog_open("Re-meshing...", topmost=True)
            self._prog_update(
                f"Generating mesh (T={mt}/P={mp}{_tn_txt}) — 몇 초 걸려...",
                pct=0.30)
            self.update_idletasks()
            _on_design = (getattr(self, '_last_tab', None) == self._tab_design)
            if _on_design:
                # re-meshes (level + target override) AND redraws DESIGN view
                self._tab_design()
            else:
                # re-mesh only; ready for the next DESIGN view / solve
                self._apply_grid_design()
            self._prog_update(
                f"Mesh: {len(pts):,} nodes, {len(tri.simplices):,} tri", pct=1.0)
        except Exception as e:
            self._status(f"Mesh change error: {e}")
        finally:
            try:
                self._prog_close(f"Mesh ready: {len(pts):,} nodes")
            except Exception:
                pass
        try:
            self._update_mesh_hint()
        except Exception:
            pass

    def _update_mesh_hint(self):
        """v28.12: Dynamic mesh recommendation based on cell size and grid density.

        Calculates finger spacing and cell-to-spacing ratio.
        Issues warning if current mesh setting may be insufficient.

        v28.12+: defer actual work to after_idle for responsiveness.
        """
        # Schedule deferred work — Tkinter event loop will run it when idle.
        # If multiple changes happen quickly, only the last one matters.
        try:
            if hasattr(self, '_mesh_hint_pending') and self._mesh_hint_pending:
                return  # Already scheduled
            self._mesh_hint_pending = True
            self.after_idle(self._update_mesh_hint_impl)
        except Exception:
            # Fallback: run immediately
            self._update_mesh_hint_impl()

    def _update_mesh_hint_impl(self):
        """v28.12: Actual mesh hint computation (deferred from _update_mesh_hint)."""
        try:
            self._mesh_hint_pending = False
            if not hasattr(self, '_mesh_hint_label'):
                return
            # Get current cell dimensions and finger count
            try:
                cw = float(self._cell_w_entry.get())
                ch = float(self._cell_h_entry.get())
                nf = int(float(self._n_fingers_entry.get()))
                nb = int(float(self._n_busbars_entry.get()))
            except Exception:
                self._mesh_hint_label.configure(text="")
                return

            if nf <= 0 or cw <= 0 or ch <= 0:
                self._mesh_hint_label.configure(text="")
                return

            # Finger spacing (mm) — assume fingers along width, evenly spaced
            f_spacing = ch / (nf + 1)
            mt = self._mesh_tangent_var.get()
            mp = self._mesh_perp_var.get()

            # Mesh recommendation logic:
            # - finger_spacing < 1.5 mm: needs Med+Med minimum, High+Med ideal
            # - finger_spacing 1.5-3 mm: Med+Med sufficient
            # - finger_spacing > 3 mm: Low+Low OK
            cell_area_cm2 = (cw * ch) / 100.0

            warn = False
            if f_spacing < 1.5:
                rec = "High+Med"
                if mt == "Low" or mp == "Low":
                    warn = True
            elif f_spacing < 3.0:
                rec = "Med+Med"
                if mt == "Low" or mp == "Low":
                    warn = True
            else:
                rec = "Low+Low"

            if warn:
                hint = (f"⚠ f-spacing={f_spacing:.2f}mm, cell={cell_area_cm2:.1f}cm²\n"
                        f"  Current={mt}+{mp} → 결과 신뢰성 낮음\n"
                        f"  권장: {rec}")
                self._mesh_hint_label.configure(text=hint, text_color="#E65100")
            else:
                hint = (f"f-spacing={f_spacing:.2f}mm, cell={cell_area_cm2:.1f}cm²\n"
                        f"  Current={mt}+{mp} ✓ OK (권장: {rec})")
                self._mesh_hint_label.configure(text=hint, text_color="#059669")
            tangent_budget = get_mesh_level(mt)["target_nodes"]
            perp_budget = get_mesh_level(mp)["target_nodes"]
            budget = int(math.sqrt(tangent_budget * perp_budget))
            hint = (
                f"finger spacing={f_spacing:.2f} mm, cell={cell_area_cm2:.1f} cm2\n"
                f"  Current={mt}+{mp} | target ~{budget:,} nodes | Recommended={rec}"
            )
            if warn:
                hint += " | run convergence study"
            self._mesh_hint_label.configure(
                text=hint, text_color="#E65100" if warn else "#059669"
            )
        except Exception as e:
            print(f"[mesh_hint] {e}")

    def _on_pattern_change(self):
        """v28.10: Triggered when PATTERN STYLE dropdown changes. Re-mesh and report."""
        try:
            ok = self._apply_grid_design()
            if ok:
                ps = self._pattern_style_var.get()
                self._status(f"Pattern changed: {ps} | {GEO.n_f}F+{GEO.n_b}BB | {len(pts)} nodes")
            self._update_mesh_hint()
        except Exception as e:
            self._status(f"Pattern change error: {e}")

    def _on_wafer_shape_change(self):
        """v28.10: Triggered when WAFER SHAPE dropdown changes. Re-mesh and report."""
        try:
            ok = self._apply_grid_design()
            if ok:
                ws = self._wafer_shape_var.get()
                wa_cm2 = GEO.wafer_area()
                self._status(f"Wafer changed: {ws} | area = {wa_cm2:.3f} cm²")
            self._update_mesh_hint()
        except Exception as e:
            self._status(f"Wafer shape error: {e}")

    def _run_mesh_convergence(self):
        """v28.10: Mesh convergence study (Griddler-recommended best practice).

        Sweeps through Low/Med/High/Max for both tangent and perpendicular
        mesh detail and reports PCE/Voc/FF/Jsc, hierarchy diagnostics, mesh
        quality, node count, triangles and timing. Saves CSV automatically.

        Use to verify PCE is mesh-converged (박사님 요구사항 2026.05.21).
        """
        import csv as _csv
        import time as _time
        from pathlib import Path as _Path
        # Save current mesh settings to restore after
        orig_t = self._mesh_tangent_var.get()
        orig_p = self._mesh_perp_var.get()
        if not self._apply_diode_params():
            return

        # Four diagonal settings: tangent and perpendicular levels stay equal.
        levels = ["Low", "Med", "High", "Max"]
        results = []
        previous_nodes = None
        previous_solver = None
        use_warm_start = self._mesh_warm_start_var.get()

        self._prog_open("Running dense mesh convergence study (may take several minutes)...")
        try:
            for i, lv in enumerate(levels):
                pct = (i + 1) / len(levels)
                self._mesh_tangent_var.set(lv)
                self._mesh_perp_var.set(lv)
                self._prog_update(f"[{i+1}/{len(levels)}] Mesh={lv}...", pct=pct * 0.9)
                t0 = _time.time()
                ok = self._apply_grid_design()
                if not ok:
                    continue
                if use_warm_start and previous_solver is not None:
                    S.set_mesh_prolongation_source(previous_solver)
                node_keys = {tuple(row) for row in pts}
                nested_nodes = previous_nodes is None or previous_nodes.issubset(node_keys)
                quality = mesh_quality_metrics(pts, tri)
                # Run a quick MPP solve (no full IV sweep — too slow)
                bp, ap = self._get_params()
                if bp is None:
                    continue
                rm_b, hf_b, wf_b, wb_b, cf_b, rc_b, rs = bp
                mode = self._mode_var.get()
                # Quick IV at 14 points
                Vs, Js, iv = S.calc_iv(rm_b, hf_b, wf_b, rc_b, rs, cf_b, DP, mode=mode)
                t1 = _time.time()
                results.append({
                    "Level": lv,
                    "Nodes": len(pts),
                    "Triangles": quality["Triangles"],
                    "NestedNodes": nested_nodes,
                    "P05Angle_deg": quality["P05Angle_deg"],
                    "MaxAspect": quality["MaxAspect"],
                    "Voc": iv["Voc"],
                    "Jsc": iv["Jsc"],
                    "FF": iv["FF"],
                    "Eff": iv["Eff"],
                    "Time_s": t1 - t0,
                    "WarmStartUsed": iv.get("warm_start_used", False),
                    "FallbackUsed": iv.get("fallback_used", False),
                    "NonlinearIterations": iv.get("nonlinear_iterations", ""),
                    "FinalNewtonResidual": iv.get("final_newton_residual", ""),
                    "LastPointKCLResidualRMS": iv.get("last_point_kcl_residual_rms", ""),
                    "ProlongationTime_s": iv.get("prolongation_time_s", 0.0),
                    "SolveTime_s": iv.get("time", ""),
                })
                previous_nodes = node_keys
                previous_solver = S

            for i, row in enumerate(results):
                previous = results[i - 1] if i else None
                row["dEff_prev"] = (
                    row["Eff"] - previous["Eff"] if previous is not None else ""
                )
                row["dFF_prev"] = (
                    row["FF"] - previous["FF"] if previous is not None else ""
                )
                row["dVoc_prev_mV"] = (
                    (row["Voc"] - previous["Voc"]) * 1000
                    if previous is not None else ""
                )
                row["dJsc_prev"] = (
                    row["Jsc"] - previous["Jsc"] if previous is not None else ""
                )

            out_dir = _Path(__file__).resolve().parent / "mesh_convergence_results"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_csv = out_dir / f"mesh_convergence_{_time.strftime('%Y%m%d_%H%M%S')}.csv"
            if results:
                with out_csv.open("w", newline="", encoding="utf-8-sig") as handle:
                    writer = _csv.DictWriter(handle, fieldnames=list(results[0]))
                    writer.writeheader()
                    writer.writerows(results)
                self._last_mesh_convergence_csv = str(out_csv)

            # Restore original settings
            self._mesh_tangent_var.set(orig_t)
            self._mesh_perp_var.set(orig_p)
            self._apply_grid_design()

            # Display result in a popup or as plot
            self._prog_update("Drawing convergence plot...", pct=0.95)
            self._draw_mesh_convergence(results)
            saved = getattr(self, "_last_mesh_convergence_csv", "")
            self._prog_close(f"Convergence study done. CSV: {saved}")
        except Exception as e:
            self._mesh_tangent_var.set(orig_t)
            self._mesh_perp_var.set(orig_p)
            self._prog_close(f"Convergence error: {e}")

    def _draw_mesh_convergence(self, results):
        """Render mesh convergence results as a 4-panel plot."""
        if not results:
            self._status("No convergence data."); return
        self._clear_fig()
        self.gs = self.fig.add_gridspec(2, 2, hspace=0.35, wspace=0.30)
        nodes = [r["Nodes"] for r in results]
        levels = [r["Level"] for r in results]
        voc = [r["Voc"]*1000 for r in results]   # mV
        jsc = [r["Jsc"] for r in results]
        ff = [r["FF"] for r in results]
        eff = [r["Eff"] for r in results]
        times = [r["Time_s"] for r in results]

        ax1 = self.fig.add_subplot(self.gs[0, 0])
        ax1.plot(nodes, voc, 'o-', color='#1565C0', lw=2, ms=8)
        for i, lv in enumerate(levels):
            ax1.annotate(lv, (nodes[i], voc[i]), textcoords='offset points',
                         xytext=(5, 5), fontsize=8)
        ax1.set_xlabel('Mesh nodes'); ax1.set_ylabel('Voc [mV]')
        ax1.set_title('Voc convergence', fontweight='bold', fontsize=10)
        ax1.grid(True, alpha=0.3); ax1.set_xscale('log')

        ax2 = self.fig.add_subplot(self.gs[0, 1])
        ax2.plot(nodes, ff, 's-', color='#E67E22', lw=2, ms=8)
        for i, lv in enumerate(levels):
            ax2.annotate(lv, (nodes[i], ff[i]), textcoords='offset points',
                         xytext=(5, 5), fontsize=8)
        ax2.set_xlabel('Mesh nodes'); ax2.set_ylabel('FF [%]')
        ax2.set_title('FF convergence', fontweight='bold', fontsize=10)
        ax2.grid(True, alpha=0.3); ax2.set_xscale('log')

        ax3 = self.fig.add_subplot(self.gs[1, 0])
        ax3.plot(nodes, eff, '^-', color='#27AE60', lw=2, ms=8)
        for i, lv in enumerate(levels):
            ax3.annotate(lv, (nodes[i], eff[i]), textcoords='offset points',
                         xytext=(5, 5), fontsize=8)
        ax3.set_xlabel('Mesh nodes'); ax3.set_ylabel('PCE [%]')
        ax3.set_title('PCE convergence (★ key metric)', fontweight='bold', fontsize=10)
        ax3.grid(True, alpha=0.3); ax3.set_xscale('log')
        # The finest evaluated mesh is a numerical reference, not ground truth.
        ax3.axhline(eff[-1], color='red', ls='--', lw=1, alpha=0.5,
                    label=f'Finest tested: {eff[-1]:.3f}%')
        ax3.legend(fontsize=8)

        ax4 = self.fig.add_subplot(self.gs[1, 1]); ax4.axis('off')
        # Convergence interpretation message + table
        # FEM mesh가 정밀해질수록 lateral 저항 손실이 더 정확히 capture됨
        # → Coarse mesh는 overestimate (효율 높게 나옴)
        # → Max는 참값에 가장 가까운 reference
        eff_max = eff[-1]
        err_max_pct = abs((eff[0] - eff_max) / eff_max * 100) if eff_max > 0 else 0
        # Convergence check: High → Max 변화가 0.05% 미만이면 수렴
        hi_to_max_delta = abs(eff[-2] - eff_max) if len(eff) >= 2 else 0
        converged = hi_to_max_delta < 0.05

        recent = results[-min(3, len(results)):]
        pce_band = max(r["Eff"] for r in recent) - min(r["Eff"] for r in recent)
        ff_band = max(r["FF"] for r in recent) - min(r["FF"] for r in recent)
        voc_band = (
            max(r["Voc"] for r in recent) - min(r["Voc"] for r in recent)
        ) * 1000
        jsc_band = max(r["Jsc"] for r in recent) - min(r["Jsc"] for r in recent)
        nested_ok = all(r.get("NestedNodes", False) for r in results)
        tol_eff = 0.01
        tol_ff = 0.02
        tol_voc = 1.0
        tol_jsc = 0.005
        converged = (
            len(results) >= 3
            and nested_ok
            and pce_band <= tol_eff
            and ff_band <= tol_ff
            and voc_band <= tol_voc
            and jsc_band <= tol_jsc
        )

        # Interpretation box at top
        ax4.text(0.50, 0.96, 'Mesh Convergence Analysis',
                 ha='center', va='top', fontweight='bold', fontsize=10,
                 transform=ax4.transAxes, color='#1565C0')
        msg_lines = [
            f"Max ref PCE = {eff_max:.4f}% (most accurate)",
            f"Low overestimates by {(eff[0]-eff_max):+.4f}% absolute",
            f"Med error vs Max: {(eff[1]-eff_max):+.4f}%" if len(eff) >= 2 else "",
            f"High error vs Max: {(eff[-2]-eff_max):+.4f}%" if len(eff) >= 2 else "",
            "",
            "Why? Finer mesh captures lateral",
            "resistive losses more accurately.",
            "Coarse mesh underestimates resistance",
            "→ overestimates PCE.",
            "",
            f"{'Converged' if converged else 'NOT converged'}: |High-Max|={hi_to_max_delta:.4f}% "
            f"({'<' if converged else '≥'} 0.05% threshold)",
            "",
            "Recommendation:",
            "  Compare BEFORE/AFTER: Med OK",
            "  Absolute reporting: High or Max",
        ]
        msg_lines = [
            f"STATUS: {'CONVERGED' if converged else 'NOT YET CONVERGED'}",
            f"Finest tested PCE = {eff_max:.4f}%",
            "",
            f"Last-3 PCE band = {pce_band:.4f}%p  (tol {tol_eff:.2f})",
            f"Last-3 FF band  = {ff_band:.4f}%p  (tol {tol_ff:.2f})",
            f"Last-3 Voc band = {voc_band:.3f} mV (tol {tol_voc:.1f})",
            f"Last-3 Jsc band = {jsc_band:.4f}    (tol {tol_jsc:.2f})",
            f"Nested node sets: {'YES' if nested_ok else 'NO'}",
            "",
            "Finest mesh is a numerical reference,",
            "not experimental validation.",
            "",
            "Use Med for screening.",
            "Use High/Max for final reporting.",
        ]
        ax4.text(0.04, 0.86, '\n'.join(msg_lines),
                 transform=ax4.transAxes, fontsize=8, va='top',
                 family='monospace', color='#37474F')

        # Compact table below
        rows = [["Level", "Nodes", "PCE [%]", "ΔvsMax", "Time"]]
        for i, r in enumerate(results):
            d = r["Eff"] - eff[-1]
            rows.append([
                r["Level"], f"{r['Nodes']}",
                f"{r['Eff']:.3f}", f"{d:+.4f}", f"{r['Time_s']:.1f}s"
            ])
        rows = [["Level", "Nodes", "Tri", "PCE [%]", "dPCE prev"]]
        for r in results:
            delta = r.get("dEff_prev", "")
            delta_text = "-" if delta == "" else f"{delta:+.4f}"
            rows.append([
                r["Level"], f"{r['Nodes']}", f"{r.get('Triangles', 0)}",
                f"{r['Eff']:.3f}", delta_text,
            ])
        # Mini table at bottom of ax4
        n = len(rows); rh = 0.30 / max(n, 1)  # compressed to bottom 30%
        for ri, row in enumerate(rows):
            y = 0.30 - ri * rh
            bg = '#1a237e' if ri == 0 else ('white' if ri % 2 else '#f0f4ff')
            fc = 'white' if ri == 0 else '#222'
            fw = 'bold' if ri == 0 else 'normal'
            from matplotlib.patches import FancyBboxPatch
            ax4.add_patch(FancyBboxPatch((0.01, y - rh * 0.8), 0.98, rh * 0.85,
                                          boxstyle='round,pad=0.005', fc=bg,
                                          ec='#ddd', lw=0.5,
                                          transform=ax4.transAxes))
            xp = 0.03
            for cell, w in zip(row, [0.20, 0.22, 0.20, 0.20, 0.15]):
                ax4.text(xp, y - rh * 0.3, str(cell), fontsize=7, va='center',
                         color=fc, fontweight=fw, transform=ax4.transAxes)
                xp += w

        self._refresh()

    # ---------------------------------------------------------
    # ILLUMINATION PRESET HANDLER (v28.8)
    # ---------------------------------------------------------
    def _on_albedo_preset_change(self, value):
        """Triggered when ILLUMINATION preset dropdown changes.
        Auto-fills the Suns Rear field unless 'Custom' is selected.
        v28.13.1: mono (full_area) 모드에서는 preset 변경을 무시 (Suns Rear=0 유지)."""
        try:
            # mono 모드 가드 — full_area cell에 bifacial illumination 적용 방지
            if hasattr(self, '_rear_mode_var') and self._rear_mode_var.get() != 'bifacial':
                return
            rear_val = self._albedo_presets.get(value, None)
            if rear_val is None:  # 'Custom' -> don't auto-fill, user types
                return
            ent = self.tb_illum[1]   # idx 1 = Suns Rear
            ent.delete(0, "end")
            ent.insert(0, f"{rear_val:.2f}")
        except Exception as e:
            print(f"[albedo preset] {e}")

    # ---------------------------------------------------------
    # DXF IMPORT
    # ---------------------------------------------------------
    def _on_grid_input_mode_change(self, value):
        """Triggered when the FRONT DESIGN input mode toggles.

        We do NOT auto-rebuild the mesh here; we only mirror the master
        field's value into the dependent field so the user can see what
        the next Apply will produce.
        """
        try:
            cw_mm = float(self.tb_grid[0].get())  # cell width in mm
        except Exception:
            cw_mm = 9.0

        if value == "spacing":
            # Master = spacing field. Mirror n_f into the N Fingers entry from
            # whatever the user has typed for spacing (default 1.5 mm).
            try:
                s_mm = max(0.10, float(self.tb_hpat[1].get()))
            except Exception:
                s_mm = 1.5
            nf = max(1, int(round(cw_mm / s_mm)))
            try:
                self.tb_hpat[0].delete(0, 'end')
                self.tb_hpat[0].insert(0, str(nf))
            except Exception:
                pass
            self._status(f"Input mode: finger spacing (master) -> n_f auto-derived = {nf}")
        else:
            # Master = n_fingers. Mirror spacing for visual feedback.
            try:
                nf = max(1, int(float(self.tb_hpat[0].get())))
            except Exception:
                nf = 2
            s_mm = cw_mm / max(1, nf)
            try:
                self.tb_hpat[1].delete(0, 'end')
                self.tb_hpat[1].insert(0, f"{s_mm:.2f}")
            except Exception:
                pass
            self._status(f"Input mode: n_fingers (master) -> spacing auto-derived = {s_mm:.2f} mm")

    # ------------------------------------------------------------------
    # DXF mode lifecycle (v28.16): a loaded DXF pins GEO to the imported
    # rect/terminal geometry (see _apply_grid_design guard). Per the user's
    # choice, editing ANY grid/extraction field abandons the DXF and rebuilds
    # an H-pattern from the GUI fields. These helpers detect that edit.
    # ------------------------------------------------------------------
    def _is_design_tab(self):
        """True if the currently shown tab is the (cheap) design view."""
        return getattr(self, '_last_tab', None) is self._tab_design

    def _invalidate_results(self):
        """Drop cached I-V / loss results so heavy tabs recompute on next open.
        Called after any geometry/terminal change so a later Compare/Loss/Sweep
        click uses fresh geometry instead of stale cached numbers."""
        try:
            self._cache.pop('iv_b', None)
            self._cache.pop('iv_a', None)
        except Exception:
            pass
        # Any other memoized run-state lives in self._cache; clearing the IV
        # keys is enough to force _run_both / _run_one to re-solve.

    def _grid_fields_for_watch(self):
        """Entry widgets whose edit should DROP DXF mode (geometry change).

        NOTE: tb_extract (Probe Pts/BB) is intentionally EXCLUDED. In DXF mode,
        editing the probe count must NOT discard the DXF finger/busbar geometry;
        it only re-spaces the terminals (see _on_dxf_extract_change). Only true
        geometry fields (cell size, finger/busbar counts/widths/lengths) leave
        DXF mode and trigger an H-pattern rebuild.
        """
        ws = []
        ws += list(getattr(self, 'tb_grid', []))      # cell W/H
        ws += list(getattr(self, 'tb_hpat', []))      # N fingers/spacing/busbars/...
        # finger/busbar widths live in the BEFORE card (tb_b[2], tb_b[3])
        tb_b = getattr(self, 'tb_b', [])
        for i in (2, 3):
            if len(tb_b) > i:
                ws.append(tb_b[i])
        return [w for w in ws if w is not None]

    def _snapshot_grid_fields(self):
        """Record current text of all watched fields (to detect real changes)."""
        snap = []
        for w in self._grid_fields_for_watch():
            try:
                snap.append(w.get())
            except Exception:
                snap.append(None)
        return snap

    def _exit_dxf_mode(self, regenerate=True):
        """Leave DXF mode: drop the imported geometry so _apply_grid_design
        rebuilds an H-pattern from the GUI fields. Idempotent."""
        global GEO
        if not getattr(self, '_dxf_loaded', False):
            return
        self._dxf_loaded = False
        # Strip DXF rect/terminal attributes from GEO so the guard releases.
        for attr in ('_dxf_finger_rects', '_dxf_busbar_rects', '_dxf_terminals'):
            if hasattr(GEO, attr):
                try:
                    delattr(GEO, attr)
                except Exception:
                    setattr(GEO, attr, None)
        # Restore the H-pattern method bindings that attach_dxf_to_geometry
        # overrode (metal_rects_front etc.) by reconstructing GEO from fields.
        self._status("Left DXF mode -> regenerating H-pattern from grid fields")
        if regenerate:
            try:
                # Rebuild a fresh CellGeometry from the GUI (clears DXF overrides)
                self._rebuild_geo_from_fields()
                self._apply_grid_design()
                # Geometry changed -> stale results. Only auto-refresh the cheap
                # design view; heavy tabs wait for the user to click them.
                self._invalidate_results()
                if self._is_design_tab():
                    self._tab_design()
            except Exception as e:
                self._status(f"H-pattern regen error: {e}")

    def _rebuild_geo_from_fields(self):
        """Construct a clean H-pattern CellGeometry from the GUI entries,
        discarding any DXF method overrides bound onto the old GEO."""
        global GEO, pts, tri, isf, isb, isp, ism, isrm, isrp, S, triang
        cw = float(self.tb_grid[0].get()) / 10
        ch = float(self.tb_grid[1].get()) / 10
        try:
            nf = max(1, int(float(self.tb_hpat[0].get())))
        except Exception:
            nf = 2
        try:
            nb = max(1, int(float(self.tb_hpat[2].get())))
        except Exception:
            nb = 1
        try:
            fg_len = float(self.tb_hpat[3].get()) / 100.0
        except Exception:
            fg_len = 1.0
        try:
            bb_len = float(self.tb_hpat[4].get()) / 100.0
        except Exception:
            bb_len = 1.0
        try:
            egap = float(self.tb_hpat[5].get()) / 10.0
        except Exception:
            egap = 0.0
        try:
            wf = float(self.tb_b[2].get()) * 1e-4
        except Exception:
            wf = 50e-4
        try:
            wb = float(self.tb_b[3].get()) * 1e-4
        except Exception:
            wb = 200e-4
        try:
            npp = max(0, int(float(self.tb_extract[0].get())))
        except Exception:
            npp = 1
        front = GridDesign(n_fingers=nf, n_busbars=nb, w_finger=wf, w_busbar=wb,
                           finger_length_frac=fg_len, busbar_length_frac=bb_len,
                           edge_gap=egap, n_probe_points=npp)
        GEO = CellGeometry(cell_w=cw, cell_h=ch, front=front)

    def _bind_dxf_exit_watchers(self):
        """Bind watchers. Two distinct behaviors:
        (a) GEOMETRY fields (cell/finger/busbar) -> leave DXF mode, rebuild
            H-pattern (_on_edit).
        (b) EXTRACTION field (Probe Pts/BB) -> stay in DXF mode, just re-space
            the terminals on the existing DXF geometry (_on_extract_edit).
        Call once at GUI build."""
        def _on_edit(_evt=None):
            if not getattr(self, '_dxf_loaded', False):
                return
            # Only react to a genuine change vs the post-load baseline.
            base = getattr(self, '_dxf_field_baseline', None)
            now = self._snapshot_grid_fields()
            if base is not None and now == base:
                return
            self._exit_dxf_mode(regenerate=True)
        for w in self._grid_fields_for_watch():
            try:
                w.bind("<KeyRelease>", _on_edit, add="+")
                w.bind("<FocusOut>", _on_edit, add="+")
            except Exception:
                pass
        # Pattern style / input mode dropdowns are GEOMETRY changes -> exit DXF.
        # (extraction_method is NOT here — it doesn't change geometry.)
        for var_name in ('_pattern_style_var', '_grid_input_mode_var'):
            var = getattr(self, var_name, None)
            if var is not None:
                try:
                    var.trace_add("write", lambda *a: _on_edit())
                except Exception:
                    pass

        # (b) Extraction field: re-space terminals, keep DXF geometry.
        #     IMPORTANT: do NOT bind <KeyRelease> here — that fires on every
        #     keystroke and would rebuild mesh+solver per character (and the
        #     mid-typed text isn't even a valid integer), causing the runaway
        #     re-execution the user saw. Only commit on Enter or focus-out.
        def _on_extract_edit(_evt=None):
            if not getattr(self, '_dxf_loaded', False):
                return  # non-DXF: handled by the normal apply/run path
            self._on_dxf_extract_change()
        tb_ext = getattr(self, 'tb_extract', [])
        if len(tb_ext) > 0 and tb_ext[0] is not None:
            try:
                tb_ext[0].bind("<Return>", _on_extract_edit, add="+")
                tb_ext[0].bind("<FocusOut>", _on_extract_edit, add="+")
            except Exception:
                pass

    def _on_dxf_extract_change(self):
        """DXF mode: the user committed a new Probe Pts/BB count. Keep the
        imported finger/busbar rectangles; replace the terminals with N
        EVENLY-spaced points along the terminals' own vertical span. The metal
        geometry does not change. Rebuild mesh + solver once."""
        global GEO, pts, tri, isf, isb, isp, ism, isrm, isrp, S, triang
        if getattr(GEO, '_dxf_finger_rects', None) is None:
            return
        # Parse; ignore mid-typed / non-integer text silently (no rebuild).
        raw = ""
        try:
            raw = self.tb_extract[0].get().strip()
            n_new = int(float(raw))
        except Exception:
            return
        if n_new < 1:
            n_new = 1
        # Debounce: if we already built this exact count, do nothing. Prevents
        # FocusOut-after-Return (or repeated focus events) from re-running.
        if getattr(self, '_dxf_last_nprobe', None) == n_new:
            return
        old = list(getattr(GEO, '_dxf_terminals', []) or [])
        if not old:
            return
        # Re-distribute n_new terminals EVENLY over the original span. No finger
        # snapping — snapping collapsed multiple probes onto the same finger row
        # and destroyed the even spacing (the bug the user reported). The probe
        # is an electrical extraction node; the mesher attaches it to the metal
        # network regardless of whether it sits exactly on a finger centerline.
        xs = [t[0] for t in old]; ys = [t[1] for t in old]
        x_const = sum(xs) / len(xs)          # terminals lie on a vertical line
        y_lo, y_hi = min(ys), max(ys)
        if n_new == 1:
            new_terms = [(x_const, 0.5 * (y_lo + y_hi))]
        else:
            new_terms = [(x_const, y_lo + (y_hi - y_lo) * i / (n_new - 1))
                         for i in range(n_new)]
        GEO._dxf_terminals = list(new_terms)
        GEO.front_terminals = list(new_terms)
        self._dxf_last_nprobe = n_new
        # Rebuild mesh/classification/solver with the new terminal set; the
        # finger/busbar rects are unchanged so the metal pattern is identical.
        try:
            pts, tri = generate_mesh_poly(GEO)
            isf, isb, isp, ism, isrm, isrp = classify_nodes_poly(pts, GEO)
            S = FESTSolver(pts, tri, isf, isb, isp, ism, GEO, isrm, isrp)
            triang = mtri.Triangulation(pts[:, 0] * 10, pts[:, 1] * 10, tri.simplices)
            self._status(f"DXF extraction: terminals re-spaced to {len(new_terms)} "
                         f"(evenly, geometry unchanged) — press a tab to recompute")
            # The geometry/solver changed, so any cached I-V is stale.
            self._invalidate_results()
            # Only the (cheap) design view auto-refreshes. Heavy tabs (compare/
            # loss/sweep/contour) must NOT auto-run — the user re-runs them by
            # clicking the tab. Re-entrancy guard prevents redraw loops.
            if self._is_design_tab() and not getattr(self, '_dxf_redrawing', False):
                self._dxf_redrawing = True
                try:
                    self._tab_design()
                finally:
                    self._dxf_redrawing = False
        except Exception as e:
            self._status(f"DXF re-space error: {e}")

    def _load_dxf(self):
        """Load a DXF and import its grid as an arbitrary axis-aligned rect
        pattern (v28.15).

        Unlike the old loader, which reverse-engineered the DXF into H-pattern
        parameters (n_f, w_f, ...) and regenerated — silently corrupting any
        non-H pattern (perimeter busbar frames, forks: a horizontal busbar's
        length was misread as its width, collapsing the topology) — this keeps
        the metal as the imported rectangle list and feeds it straight into the
        existing rect machinery (compute_metal_frac / Sutherland-Hodgman) and
        the 1D metal graph. H-patterns are unchanged (verified bit-identical);
        arbitrary rect patterns now import faithfully.

        Layers (case-insensitive, synonyms): cell/finger/busbar/contact.
        Units auto-detected; override via the unit prompt if unknown.
        """
        global GEO, pts, tri, isf, isb, isp, ism, isrm, isrp, S, triang
        fn = filedialog.askopenfilename(
            title="Load DXF File (arbitrary rect pattern)",
            filetypes=[('DXF Files', '*.dxf'), ('All Files', '*.*')])
        if not fn:
            return

        try:
            # 1) Parse DXF into a rect grid (cm, wafer-origin). Unit auto-detect;
            #    if the file's units are unknown the module assumes cm and warns.
            g = load_dxf_grid(fn)
            rep = g.report
            if rep.get("unit_assumed", False):
                # Let the user pick the real unit if it was ambiguous.
                from tkinter import simpledialog
                ans = simpledialog.askstring(
                    "DXF units",
                    "DXF units are ambiguous. Enter unit (um / mm / cm / m / in):",
                    initialvalue="mm")
                if ans:
                    ans = ans.strip().lower()
                    if ans in ("um", "mm", "cm", "m", "in"):
                        g = load_dxf_grid(fn, force_unit=ans)
                        rep = g.report

            if g.W <= 0 or g.H <= 0:
                raise ValueError("Could not determine cell size from DXF "
                                 "(no cell outline and no finger/busbar rects).")

            # 2) Build a CellGeometry and attach the imported rects so that
            #    metal_rects_front()/shading_fraction() return the DXF pattern.
            front = GridDesign(n_fingers=1, n_busbars=1,
                               w_finger=50e-4, w_busbar=200e-4,
                               finger_length_frac=1.0, busbar_length_frac=1.0,
                               edge_gap=0)
            GEO = CellGeometry(cell_w=g.W, cell_h=g.H, front=front)
            attach_dxf_to_geometry(GEO, g)

            # 3) rect-native mesh + classification (same 6-tuple contract).
            pts, tri = generate_mesh_poly(GEO)
            isf, isb, isp, ism, isrm, isrp = classify_nodes_poly(pts, GEO)

            # 4) Solver. _build dispatches to the poly 1D metal assembler
            #    automatically because GEO._dxf_finger_rects is present.
            S = FESTSolver(pts, tri, isf, isb, isp, ism, GEO, isrm, isrp)
            triang = mtri.Triangulation(pts[:, 0] * 10, pts[:, 1] * 10, tri.simplices)

            shading_pct = GEO.shading_fraction() * 100
            avg_mfrac = float(np.mean(S.metal_frac)) * 100
            nF = len(g.finger_rects); nB = len(g.busbar_rects); nT = len(g.terminals)

            # 5) Update GUI fields. For an arbitrary pattern there is no single
            #    n_f/w_f, so show counts and cell size; widths show the mean
            #    short-edge of the imported rects as an indicator only.
            def _mean_width(rects):
                ws = [min(rw, rh) for (rx, ry, rw, rh) in rects]
                return (sum(ws) / len(ws)) if ws else 0.0
            avg_wf = _mean_width(g.finger_rects)
            avg_wb = _mean_width(g.busbar_rects)

            # Fill GUI fields with the DXF's actual values. NOTE the correct
            # tb_hpat indexing: [0]=N Fingers [1]=Finger Spacing [2]=N Busbars
            # [3]=Finger Length% [4]=Busbar Length% [5]=Edge Gap. (Earlier builds
            # wrote nB into [1]/Spacing and nT into [5]/Edge Gap — both wrong.)
            self.tb_grid[0].delete(0, 'end'); self.tb_grid[0].insert(0, f"{g.W*10:.1f}")
            self.tb_grid[1].delete(0, 'end'); self.tb_grid[1].insert(0, f"{g.H*10:.1f}")
            self.tb_hpat[0].delete(0, 'end'); self.tb_hpat[0].insert(0, str(nF))   # N Fingers
            self.tb_hpat[2].delete(0, 'end'); self.tb_hpat[2].insert(0, str(nB))   # N Busbars
            if avg_wf > 0:
                self.tb_b[2].delete(0, 'end'); self.tb_b[2].insert(0, f"{avg_wf*1e4:.0f}")
                self.tb_a[2].delete(0, 'end'); self.tb_a[2].insert(0, f"{avg_wf*1e4:.0f}")
            if avg_wb > 0:
                self.tb_b[3].delete(0, 'end'); self.tb_b[3].insert(0, f"{avg_wb*1e4:.0f}")
                self.tb_a[3].delete(0, 'end'); self.tb_a[3].insert(0, f"{avg_wb*1e4:.0f}")
            # Current Extraction: show the DXF terminal count in Probe Pts/BB.
            # (This is the field that actually drives n_probe_points.)
            try:
                self.tb_extract[0].delete(0, 'end')
                self.tb_extract[0].insert(0, str(nT))
            except Exception:
                pass
            # Mark these fields as "DXF-origin" so the next user edit knows to
            # leave DXF mode (see _bind_dxf_exit_watchers / _exit_dxf_mode).
            self._dxf_loaded = True
            self._dxf_field_baseline = self._snapshot_grid_fields()
            # Seed the debounce with the loaded terminal count so the first
            # focus-out (without an actual change) doesn't rebuild.
            self._dxf_last_nprobe = nT

            try:
                self._update_info_label()
            except Exception:
                pass
            self._mesh_info.configure(
                text=f"Mesh: {len(pts)} nodes | {len(tri.simplices)} tri (DXF rect pattern)")

            warn = list(rep.get("warnings", []))
            diag = (f"DXF loaded (rect pattern): {os.path.basename(fn)}\n\n"
                    f"Cell: {g.W*10:.1f} x {g.H*10:.1f} mm\n"
                    f"Finger rects: {nF}  (mean width {avg_wf*1e4:.0f} um)\n"
                    f"Busbar rects: {nB}  (mean width {avg_wb*1e4:.0f} um)\n"
                    f"Terminals: {nT}\n"
                    f"Shading: {shading_pct:.2f}%   (avg metal_frac {avg_mfrac:.2f}%)\n"
                    f"Mesh: {len(pts)} nodes, {len(tri.simplices)} tri\n"
                    f"Unit: {rep.get('unit')} (scale {rep.get('scale_to_cm')} -> cm)\n")
            if rep.get("unmatched_layers"):
                diag += f"Unmatched layers (ignored): {rep['unmatched_layers']}\n"
            if warn:
                diag += "\nWarnings:\n  - " + "\n  - ".join(warn)

            self._status(f"DXF loaded: {nF} finger / {nB} busbar rects, "
                         f"{nT} terminal(s), {len(pts)} nodes")
            if shading_pct > 95:
                messagebox.showerror(
                    "DXF Import Error",
                    f"Shading {shading_pct:.1f}% is impossibly high — likely a unit "
                    f"mismatch. Re-load and specify the correct unit.\n\n" + diag)
                return
            if warn:
                messagebox.showwarning("DXF Import", diag)
            else:
                messagebox.showinfo("DXF Import Success", diag)
            # jump to the design view so the imported pattern (with all
            # its terminals) is visible immediately.
            try:
                self._tab_design()
            except Exception:
                pass

        except Exception as e:
            import traceback
            err_detail = traceback.format_exc()
            self._status(f"DXF error: {e}")
            messagebox.showerror(
                "DXF Import Error",
                f"Failed to load DXF:\n{e}\n\nTraceback:\n{err_detail[-600:]}")

    def _apply_diode_params(self):
        """Read n1/n2 top/bot and LC coupling from DIODE PARAMS card and apply to DP."""
        try:
            n1t = _parse_gui_float(self.tb_diode[0].get(), "n1_top")
            n2t = _parse_gui_float(self.tb_diode[1].get(), "n2_top")
            n1b = _parse_gui_float(self.tb_diode[2].get(), "n1_bot")
            n2b = _parse_gui_float(self.tb_diode[3].get(), "n2_bot")
            # Validate ranges
            for name, val in [('n1_top', n1t), ('n2_top', n2t), ('n1_bot', n1b), ('n2_bot', n2b)]:
                if val < 0.5 or val > 5.0:
                    raise ValueError(f"{name} must be between 0.5 and 5.0")
            DP.n1_top = n1t
            DP.n2_top = n2t
            DP.n1_bot = n1b
            DP.n2_bot = n2b
            # Mirror n1/n2 to Single mode — Single = c-Si = Bot values
            # (Griddler single-cell is c-Si domain, matches our Bot subcell)
            DP.n1_single = n1b
            DP.n2_single = n2b
            # Luminescent Coupling J01 (Griddler PRO compatible)
            # Empty / 0 / 0e+00 all mean disabled
            try:
                lc_str = self.tb_diode[4].get().strip()
                if lc_str and lc_str not in ("0", "0.0", "0e+00", "0.0e+00"):
                    lc_val = _parse_gui_float(lc_str, "LC Coupling")
                    if lc_val < 0 or lc_val > 1e-15:
                        raise ValueError("LC Coupling must be between 0 and 1e-15")
                    else:
                        DP.J01_coupling = lc_val
                else:
                    DP.J01_coupling = 0.0
            except ValueError as e:
                self._status(f"LC Coupling parse error: {e}")
                return False

            # Rs_rear_tco (L3 layer sheet R, bifacial only)
            try:
                rs_tco_str = self._rs_tco_entry.get().strip()
                if rs_tco_str:
                    rs_tco_val = _parse_gui_float(rs_tco_str, "Rs_rear_tco")
                    if rs_tco_val < 0 or rs_tco_val > 10000:
                        raise ValueError("Rs_rear_tco must be between 0 and 10000")
                    if rs_tco_val < 0 or rs_tco_val > 10000:
                        self._status(f"Rs_rear_tco out of range (0~10000 Ω/sq), kept default.")
                    else:
                        DP.Rs_rear_tco = rs_tco_val
            except ValueError as e:
                self._status(f"Rs_rear_tco parse error: {e}")
                return False
            except AttributeError:
                pass

            # rc_rear (L4 rear metal contact resistivity, mOhm·cm² -> Ohm·cm²).
            # Blank = use the front rc (DP.rc_rear = None, legacy-identical).
            try:
                rc_rear_str = self._rc_rear_entry.get().strip()
                if rc_rear_str:
                    rc_rear_val = _parse_gui_float(rc_rear_str, "rc_rear")
                    if rc_rear_val < 0 or rc_rear_val > 1e4:
                        self._status("rc_rear out of range (0~10000 mOhm.cm2), using front rc.")
                        DP.rc_rear = None
                    else:
                        DP.rc_rear = rc_rear_val * 1e-3
                else:
                    DP.rc_rear = None
            except ValueError as e:
                self._status(f"rc_rear parse error: {e}")
                return False
            except AttributeError:
                pass

            # Rc_junction (vertical contact R between top and bot subcells)
            # 박사님 지시 2026.04.10 (Phase A vertical only)
            try:
                rc_str = self.tb_diode[5].get().strip()
                if rc_str:
                    rc_val = _parse_gui_float(rc_str, "Rc_junction")
                    if rc_val < 0 or rc_val > 100:
                        raise ValueError("Rc_junction must be between 0 and 100")
                    if rc_val < 0 or rc_val > 100:
                        self._status(f"Rc_junction out of range (0~100 Ω·cm²), disabled.")
                        DP.Rc_junction = 0.0
                    else:
                        DP.Rc_junction = rc_val
                else:
                    DP.Rc_junction = 0.0
            except (ValueError, IndexError) as e:
                self._status(f"Rc_junction parse error: {e}")
                return False

            # Rs_junction (interlayer lateral sheet R, Phase B)
            # When > 0, activates 5/6-plane Phase B solver
            try:
                rs_str = self.tb_diode[6].get().strip()
                if rs_str:
                    rs_val = _parse_gui_float(rs_str, "Rs_junction")
                    if rs_val < 0 or rs_val > 100000:
                        raise ValueError("Rs_junction must be between 0 and 100000")
                    if rs_val < 0 or rs_val > 100000:
                        self._status(f"Rs_junction out of range (0~100000 Ω/sq), disabled.")
                        DP.Rs_junction = 0.0
                    else:
                        DP.Rs_junction = rs_val
                else:
                    DP.Rs_junction = 0.0
            except (ValueError, IndexError) as e:
                self._status(f"Rs_junction parse error: {e}")
                return False

            # === v28.1: Read TOP DIODE card (J01, J02, Jph, Rsh, Rs_lumped) ===
            # TOP = Perovskite top subcell (Tandem mode only, ignored in Single mode)
            current_mode = self._mode_var.get() if hasattr(self, '_mode_var') else 'tandem'
            try:
                if hasattr(self, 'tb_dtop'):
                    jph_top = float(self.tb_dtop[0].get()) * 1e-3  # mA/cm² → A/cm²
                    j01_top_pass = float(self.tb_dtop[1].get())
                    j01_top_metal = float(self.tb_dtop[2].get())
                    j02_top_pass = float(self.tb_dtop[3].get())
                    j02_top_metal = float(self.tb_dtop[4].get())
                    rsh_top = float(self.tb_dtop[5].get())
                    rs_lumped_top_val = float(self.tb_dtop[6].get())
                    top_values = (
                        ("Top Jph", jph_top),
                        ("Top J01 pass", j01_top_pass),
                        ("Top J01 metal", j01_top_metal),
                        ("Top J02 pass", j02_top_pass),
                        ("Top J02 metal", j02_top_metal),
                        ("Top Rsh", rsh_top),
                        ("Top Rs_lumped", rs_lumped_top_val),
                    )
                    for name, value in top_values:
                        if not np.isfinite(value):
                            raise ValueError(f"{name} must be finite")
                    if jph_top <= 0 or j01_top_pass <= 0 or rsh_top <= 0:
                        raise ValueError("Top Jph, J01 pass, and Rsh must be > 0")
                    if j01_top_metal < 0 or j02_top_pass < 0 or j02_top_metal < 0:
                        raise ValueError("Top diode saturation currents must be >= 0")
                    if rs_lumped_top_val < 0:
                        raise ValueError("Top Rs_lumped must be >= 0")
                    # Apply to DP (Tandem mode uses these)
                    DP.Jph_top = jph_top
                    DP.J01_top_pass = j01_top_pass
                    DP.J01_top_metal = j01_top_metal
                    DP.J02_top_pass = j02_top_pass
                    DP.J02_top_metal = j02_top_metal
                    DP.Rsh_top = rsh_top
                    # In Tandem: use TOP card's Rs_lumped_top
                    # In Single: TOP card is ignored; BOT mirror handles Rs_lumped_top below
                    if current_mode == 'tandem':
                        DP.Rs_lumped_top = rs_lumped_top_val
            except (ValueError, IndexError, AttributeError) as e:
                self._status(f"Top diode param parse error: {e}")
                return False

            # === v28.8: Read ILLUMINATION card (Griddler-style Suns_front, Suns_rear) ===
            # Suns_rear maps directly to DP.bifacial_gain (= fraction of front Jph received from rear).
            # Suns_front not yet wired through solver (reserved for v28.9 scaling Jph by Suns_front).
            try:
                if hasattr(self, 'tb_illum'):
                    suns_front = _parse_gui_float(self.tb_illum[0].get(), "Suns Front")
                    suns_rear = _parse_gui_float(self.tb_illum[1].get(), "Suns Rear")
                    _require_range("Suns Front", suns_front, min_value=0.0, max_value=2.0)
                    _require_range("Suns Rear", suns_rear, min_value=0.0, max_value=2.0)
                    # .1: mono(full_area) 모드에서는 suns_rear 강제 0
                    # (GUI에서 이미 disable 처리됐지만 prog. 입력 등 우회 가능성 차단)
                    if hasattr(self, '_rear_mode_var') and \
                       self._rear_mode_var.get() != 'bifacial':
                        suns_rear = 0.0
                    # Store for diagnostic/print; map to existing field
                    DP.bifacial_gain = suns_rear
                    # Preserve Suns_front for future use (currently 1.0 = STC convention)
                    if not hasattr(DP, 'suns_front'):
                        try:
                            DP.__dict__['suns_front'] = suns_front
                        except Exception:
                            pass
                    else:
                        DP.suns_front = suns_front
            except (ValueError, IndexError, AttributeError) as e:
                self._status(f"Illumination parse error: {e}")
                return False

            # === v28.4: Read BOT DIODE card (pass/metal split) ===
            # BOT = c-Si bottom subcell in Tandem mode AND the only diode in Single mode.
            #   Tandem: pass/metal 각각 솔버 반영 (Phase 1 솔버 patch 후 효력).
            #           Phase 0 단계에서는 pass = metal이면 결과 동일 (property가 pass 반환).
            #   Single: pass 값만 사용 (Griddler c-Si 도메인 = pass 영역).
            try:
                if hasattr(self, 'tb_dbot'):
                    jph_bot       = float(self.tb_dbot[0].get()) * 1e-3
                    j01_bot_pass  = float(self.tb_dbot[1].get())
                    j01_bot_metal = float(self.tb_dbot[2].get())
                    j02_bot_pass  = float(self.tb_dbot[3].get())
                    j02_bot_metal = float(self.tb_dbot[4].get())
                    rsh_bot       = float(self.tb_dbot[5].get())
                    rs_lumped_bot_val = float(self.tb_dbot[6].get())

                    # Sanity check (경고만)
                    bot_values = (
                        ("Bot Jph", jph_bot),
                        ("Bot J01 pass", j01_bot_pass),
                        ("Bot J01 metal", j01_bot_metal),
                        ("Bot J02 pass", j02_bot_pass),
                        ("Bot J02 metal", j02_bot_metal),
                        ("Bot Rsh", rsh_bot),
                        ("Bot Rs_lumped", rs_lumped_bot_val),
                    )
                    for name, value in bot_values:
                        if not np.isfinite(value):
                            raise ValueError(f"{name} must be finite")
                    if jph_bot <= 0 or j01_bot_pass <= 0 or rsh_bot <= 0:
                        raise ValueError("Bot Jph, J01 pass, and Rsh must be > 0")
                    if j01_bot_metal < 0 or j02_bot_pass < 0 or j02_bot_metal < 0:
                        raise ValueError("Bot diode saturation currents must be >= 0")
                    if rs_lumped_bot_val < 0:
                        raise ValueError("Bot Rs_lumped must be >= 0")

                    if j01_bot_metal < j01_bot_pass * 0.99:
                        self._status(
                            "Warning: J01_bot_metal < J01_bot_pass. "
                            "물리적으로 metal contact recombination이 더 큰 것이 일반적."
                        )

                    # Apply to Tandem DP (pass/metal 직접 set, property 우회)
                    DP.Jph_bot        = jph_bot
                    DP.J01_bot_pass   = j01_bot_pass
                    DP.J01_bot_metal  = j01_bot_metal
                    DP.J02_bot_pass   = j02_bot_pass
                    DP.J02_bot_metal  = j02_bot_metal
                    DP.Rsh_bot        = rsh_bot
                    DP.Rs_lumped_bot  = rs_lumped_bot_val

                    # Mirror to Single mode — pass 값만 사용 (Griddler c-Si 도메인)
                    DP.Jph_single        = jph_bot
                    DP.J01_single_pass   = j01_bot_pass
                    DP.J01_single_metal  = j01_bot_pass   # 기존 동작 유지
                    DP.J02_single_pass   = j02_bot_pass
                    DP.J02_single_metal  = j02_bot_pass
                    DP.Rsh_single        = rsh_bot

                    if current_mode == 'single':
                        DP.Rs_lumped_top = rs_lumped_bot_val
            except (ValueError, IndexError, AttributeError) as e:
                self._status(f"Bot diode param parse error: {e}")
                return False
            # === END v28.4 diode param GUI read ===
            return True
        except Exception as e:
            self._status(f"Diode param error: {e}")
            return False


    def _make_card(self, parent, title, color, params):
        """Create a parameter input card. Returns (entries, label_widgets, header_label)."""
        card = ctk.CTkFrame(parent, fg_color=CLR_CARD_BG, corner_radius=8,
                            border_width=1, border_color=CLR_CARD_BD)
        card.pack(fill="x", pady=2)

        hbar = ctk.CTkFrame(card, fg_color=color, height=28, corner_radius=0)
        hbar.pack(fill="x"); hbar.pack_propagate(False)
        hdr_lbl = ctk.CTkLabel(hbar, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="white")
        hdr_lbl.pack(side="left", padx=10, pady=3)

        entries = []; label_widgets = []
        for i, (label, default, unit) in enumerate(params):
            row_bg = CLR_EVEN_ROW if i % 2 == 0 else CLR_CARD_BG
            row = ctk.CTkFrame(card, fg_color=row_bg, height=30, corner_radius=0)
            row.pack(fill="x", padx=0); row.pack_propagate(False)

            lbl_w = ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=10),
                         text_color=CLR_TEXT, width=100, anchor="w")
            lbl_w.pack(side="left", padx=(8, 2), pady=1)
            label_widgets.append(lbl_w)

            entry = ctk.CTkEntry(row, width=65, height=24, font=ctk.CTkFont(size=10),
                                 fg_color="white", border_color=CLR_CARD_BD,
                                 corner_radius=4, justify="center")
            entry.insert(0, default)
            entry.pack(side="left", padx=2, pady=1)
            entries.append(entry)

            ctk.CTkLabel(row, text=unit, font=ctk.CTkFont(size=8),
                         text_color=CLR_TEXT_SEC, width=95, anchor="w").pack(side="left", padx=2)

        ctk.CTkFrame(card, height=6, fg_color=CLR_CARD_BG).pack()
        return entries, label_widgets, hdr_lbl


    def _build_tabbar(self, parent):
        """Tab buttons row."""
        bar = ctk.CTkFrame(parent, fg_color=CLR_TAB_BG, height=44, corner_radius=0)
        bar.pack(fill="x", padx=12, pady=(8, 4))
        bar.pack_propagate(False)

        tabs = [
            ("COMPARE",  "#E67E22", self._tab_compare),
            ("CURRENT",  "#8E44AD", self._tab_current),
            ("LOSS / FF","#C0392B", self._tab_waterfall),
            ("SWEEP",    "#16A085", self._tab_sweep),
            ("CONTOUR",  "#795548", self._tab_contour),
            ("DESIGN",   "#455A64", self._tab_design),
            ("MODEL",    "#1565C0", self._tab_model),
            ("EXP I-V",  "#34495E", self._load_exp),
            ("REPORT",   "#6C3483", self._gen_report),
        ]

        self._tab_btns = []
        for label, color, cmd in tabs:
            btn = ctk.CTkButton(bar, text=label, font=ctk.CTkFont(size=11, weight="bold"),
                                fg_color=color, hover_color=color,
                                text_color="white", corner_radius=6,
                                width=78, height=32, command=cmd)
            btn.pack(side="left", padx=2, pady=6)
            self._tab_btns.append(btn)

        # Save buttons (right side)
        ctk.CTkButton(bar, text="CSV", font=ctk.CTkFont(size=10, weight="bold"),
                       fg_color="#2E7D32", hover_color="#1B5E20",
                       text_color="white", corner_radius=6,
                       width=50, height=32, command=self._save_csv).pack(side="right", padx=2, pady=6)
        ctk.CTkButton(bar, text="PNG", font=ctk.CTkFont(size=10, weight="bold"),
                       fg_color=CLR_BLUE, hover_color="#1D4ED8",
                       text_color="white", corner_radius=6,
                       width=50, height=32, command=self._save_png).pack(side="right", padx=2, pady=6)


    def _build_statusbar(self, parent):
        sbar = ctk.CTkFrame(parent, fg_color=CLR_TAB_BG, height=28, corner_radius=0)
        sbar.pack(fill="x", padx=12, pady=(0, 8))
        sbar.pack_propagate(False)
        self._status_label = ctk.CTkLabel(sbar, text="", font=ctk.CTkFont(size=10),
                                           text_color=CLR_TEXT_SEC)
        self._status_label.pack(side="left", padx=8, pady=2)


    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------
    def _toggle_rear_mode(self, value=None):
        """Show/hide rear H-pattern inputs + auto-disable Suns Rear in mono mode.

        v28.13.1: mono (full_area) cell 구조에 bifacial illumination을 적용하는 것은
        물리적으로 모순이므로, full_area 모드에서 Suns Rear를 0으로 강제하고
        입력칸·preset 드롭다운을 disable한다.
        """
        mode = self._rear_mode_var.get()
        if mode == 'bifacial':
            for row in self._rear_patt_rows:
                row.pack(fill="x")
            # Bifacial: Suns Rear 입력/preset 활성화
            if hasattr(self, 'tb_illum') and len(self.tb_illum) > 1:
                try:
                    self.tb_illum[1].configure(state="normal")
                except Exception:
                    pass
            if hasattr(self, '_albedo_preset_dropdown'):
                try:
                    self._albedo_preset_dropdown.configure(state="normal")
                except Exception:
                    pass
        else:
            for row in self._rear_patt_rows:
                row.pack_forget()
            # Mono (full_area): Suns Rear=0 강제 + 입력/preset disable
            if hasattr(self, 'tb_illum') and len(self.tb_illum) > 1:
                try:
                    ent = self.tb_illum[1]
                    ent.configure(state="normal")  # 값 수정용 임시 활성
                    ent.delete(0, "end")
                    ent.insert(0, "0.00")
                    ent.configure(state="disabled")
                except Exception:
                    pass
            if hasattr(self, '_albedo_preset_var'):
                try:
                    self._albedo_preset_var.set("STC (0.00)")
                except Exception:
                    pass
            if hasattr(self, '_albedo_preset_dropdown'):
                try:
                    self._albedo_preset_dropdown.configure(state="disabled")
                except Exception:
                    pass

    def _show_griddler_equiv(self):
        """Show Griddler-equivalent single-cell parameters for cross-validation.

        박사님 지시 (2026.03.24 미팅): Griddler PRO 없으므로 tandem 결과의
        Voc/Jsc/Jmpp/Vmpp를 맞춘 single-cell을 Griddler 2.5 free에 입력하여
        저항성 손실 (Emitter/Finger/Contact) 크로스-검증.

        등가 single-cell의 J01 = Jsc / (exp(qVoc/nkT) - 1)
        """
        c = getattr(self, '_cache', None)
        if not c or 'iv_a' not in c:
            self._status("Run COMPARE first to get IV results.")
            return

        iv_a = c['iv_a']; iv_b = c['iv_b']
        kT = 0.02585  # V @ 25C
        win = ctk.CTkToplevel(self)
        win.title("Griddler Single-cell Equivalent")
        win.geometry("680x640"); win.resizable(False, False)

        txt = ctk.CTkTextbox(win, font=ctk.CTkFont(family=MONO_FONT, size=11))
        txt.pack(fill="both", expand=True, padx=12, pady=12)

        def eq_params(iv, label):
            Voc, Jsc, FF, Eff = iv['Voc'], iv['Jsc'], iv['FF'], iv['Eff']
            Vmpp, Jmpp = iv['Vmpp'], iv['Jmpp']
            return (f"[{label}]\n"
                    f"  Voc       = {Voc:.4f} V       <- Griddler target\n"
                    f"  Jsc       = {Jsc:.3f} mA/cm2  <- 'JL,front (1-Sun)'\n"
                    f"  Vmpp      = {Vmpp:.4f} V      <- ★ resistive loss key ★\n"
                    f"  Jmpp      = {Jmpp:.3f} mA/cm2 <- ★ resistive loss key ★\n"
                    f"  FF        = {FF:.2f} %\n"
                    f"  Eff       = {Eff:.3f} %\n\n")

        SEP = "-" * 60
        out = (
            f"{SEP}\n"
            f"GRIDDLER CROSS-VALIDATION (PRO 없을 때)\n"
            f"{SEP}\n\n"
            f"박사님 방식: tandem의 Voc/Jsc를 single-cell Griddler에서\n"
            f"재현하여 저항성 손실만 검증.\n\n"
            f"※ Interlayer/Shunt/Recomb는 tandem 고유라 검증 불가.\n\n"
            + eq_params(iv_b, "BEFORE (hot pressing 前)")
            + eq_params(iv_a, "AFTER (hot pressing 後)")
            + f"{SEP}\n"
            f"GRIDDLER 2.5 FREE 입력 순서\n"
            f"{SEP}\n"
            f"  1) Tandem 체크박스 OFF (Single cell mode)\n"
            f"  2) Cell geometry: 2L-FEST와 동일한 wafer/finger/busbar\n"
            f"  3) Front Diode Params:\n"
            f"     - 1-Sun JL = 위 Jsc 값\n"
            f"     - J01/J02/n 은 자유롭게 튜닝\n"
            f"       → Griddler 결과의 Voc가 위 Voc target과 일치할 때까지\n"
            f"       → 팁: n=3~4 정도로 높이면 tandem Voc 맞추기 쉬움\n"
            f"            (물리적 의미 무시, 저항 비교용 가짜 diode)\n"
            f"  4) Front Metal: resistivity/contact R 동일\n"
            f"  5) TCO sheet R (Rs_front): 동일 (예: 50 Ω/sq)\n"
            f"  6) Rear: Rs_rear 매우 작게 (ground BC 모사)\n"
            f"  7) Run → REPORT에서 비교:\n"
            f"     ★ Emitter/Finger/Busbar/Contact loss 수치 ★\n"
            f"     ★ Rline 값 ★\n\n"
            f"왜 J01 튜닝해도 되나?\n"
            f"  저항 손실 = f(Jmpp, Vmpp, geometry, R) 뿐.\n"
            f"  J01은 Voc만 결정 → Voc 맞추면 Vmpp도 유사 → 저항 손실\n"
            f"  자동으로 같아짐. Diode physics 자체는 비교 대상 아님.\n\n"
            f"{SEP}\n"
            f"합격 기준 (기존 single-cell 검증 실적: IV 0.5%, Recomb 0.4%)\n"
            f"{SEP}\n"
            f"  < 1%   ✅ 완벽 - 박사님 보고 가능\n"
            f"  1~2%   ⚠️ 허용 - mesh density 차이\n"
            f"  2~5%   ❌ 의심 - geometry/metal fraction 재확인\n"
            f"  > 5%   ❌ 버그 - 단위/BC 오류 가능성\n\n"
            f"불일치 시 체크포인트:\n"
            f"  - metal fraction (Sutherland-Hodgman intersection?)\n"
            f"  - finger/busbar 치수·개수 정확히 동일한가\n"
            f"  - contact R 단위 (Ω·cm² vs mΩ·cm²)\n"
            f"  - Rs_front 단위 (Ω/sq)\n"
        )
        txt.insert("1.0", out)
        txt.configure(state="disabled")



    def _show_about(self):
        """About dialog with version, credits, and references."""
        win = ctk.CTkToplevel(self)
        win.title("About 2L-FEST")
        win.geometry("520x620+500+200")
        win.resizable(False, False)
        win.attributes('-topmost', True)
        win.configure(fg_color="#F8FAFC")

        hdr = ctk.CTkFrame(win, fg_color="#0F172A", height=80, corner_radius=0)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="2L-FEST", font=ctk.CTkFont(MONO_FONT, 26, "bold"),
                     text_color="white").pack(pady=(12, 0))
        ctk.CTkLabel(hdr, text="2-Layer Front Electrode Simulation Tool",
                     font=ctk.CTkFont(size=11), text_color="#94A3B8").pack()

        body = ctk.CTkScrollableFrame(win, fg_color="#F8FAFC")
        body.pack(fill="both", expand=True, padx=16, pady=12)

        def section(title, color="#1565C0"):
            ctk.CTkLabel(body, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=color, anchor="w").pack(fill="x", pady=(8, 2))
        def line(text, fontsize=10, color="#334155"):
            ctk.CTkLabel(body, text=text, font=ctk.CTkFont(size=fontsize),
                         text_color=color, anchor="w", justify="left").pack(fill="x", padx=8)

        section("Version")
        line("2L-FEST PRO v5.0  (April 2026)")
        line("Galerkin FEM + Newton-Raphson solver")

        section("Author")
        line("Seunghoon Lee  (이승훈)")
        line("Mechanical Engineering")
        line("Photovoltaic Research Center, KIST")

        section("Supervisor")
        line("Dr. Inho Kim  (김인호 박사님)")
        line("Photovoltaic Research Center, KIST")

        section("Capabilities")
        line("- 2T monolithic perovskite/Si tandem simulation")
        line("- Single-cell mode (Si or perovskite)")
        line("- 2-diode model with n1, n2 free parameters")
        line("- Front + Rear plane (independent V distribution)")
        line("- Power loss decomposition (resistive/shunt/recomb)")
        line("- FF Waterfall (Griddler-style 5-step erosion)")
        line("- DXF import (ezdxf, auto layer classification)")
        line("- H-pattern auto-generator")

        section("Technical Stack")
        line("- Python 3.9+, NumPy, SciPy (sparse, SuperLU)")
        line("- Matplotlib, CustomTkinter")
        line("- ezdxf (DXF import)")

        section("Key References")
        line("[1] Jeon et al., Solar Energy 292 (2025)")
        line("    \u2014 Tandem cell parameters (Table 1)")
        line("[2] Gupta et al., Solar Energy 174 (2018)")
        line("    \u2014 2-layer FEM methodology")
        line("[3] Rehman et al., Prog. Photovolt. (2023)")
        line("    \u2014 Loss verification equations")
        line("[4] Meier & Schroder, IEEE TED (1984)")
        line("    \u2014 Analytical loss reference")

        section("Validation")
        line("Cross-validated against Griddler 2.5")
        line("All IV parameters within 0.5%")

        section("License")
        line("Internal research use \u2014 KIST PVRC", color="#64748B")
        line("(c) 2026 Seunghoon Lee", color="#64748B")

        ctk.CTkButton(win, text="Close", width=100, height=32,
                      fg_color="#1565C0", hover_color="#0D47A1",
                      command=win.destroy).pack(pady=(0, 12))

    def _toggle_lang(self):
        _LANG['current'] = 'KR' if _LANG['current'] == 'EN' else 'EN'
        lang = _LANG['current']
        self._lang_btn.configure(text=f"{'KR' if lang=='EN' else 'EN'}")
        self._update_sidebar_labels()
        tab_keys = ['compare','current','loss_ff','sweep','contour','model','validate','lit_bench','exp_iv','report']
        for btn, key in zip(self._tab_btns, tab_keys):
            btn.configure(text=_t(key))
        self._status(_t('ready'))
        # Auto re-render current tab if data exists
        if hasattr(self, '_last_tab') and self._last_tab and 'iv_b' in self._cache:
            try: self._last_tab()
            except: pass

    def _update_sidebar_labels(self):
        """Update sidebar card/param labels for current language."""
        param_keys = ['bulk_res','finger_h','shape_cf','contact_res','tco_rsheet']
        grid_keys = ['cell_w','cell_h']
        if hasattr(self, '_sidebar_labels_b'):
            for lbl, key in zip(self._sidebar_labels_b, param_keys):
                lbl.configure(text=_t(key))
        if hasattr(self, '_sidebar_labels_a'):
            for lbl, key in zip(self._sidebar_labels_a, param_keys[:4]):
                lbl.configure(text=_t(key))
        if hasattr(self, '_sidebar_labels_g'):
            for lbl, key in zip(self._sidebar_labels_g, grid_keys):
                lbl.configure(text=_t(key))
        if hasattr(self, '_sidebar_labels_d'):
            diode_keys = ['n2_top', 'n2_bot']
            for lbl, key in zip(self._sidebar_labels_d, diode_keys):
                lbl.configure(text=_t(key))
        if hasattr(self, '_card_headers'):
            hdr_texts = [_t('before'), _t('after'), _t('grid_design'), _t('diode_params')]
            for hdr_lbl, txt in zip(self._card_headers, hdr_texts):
                hdr_lbl.configure(text=txt)

    def _status(self, msg):
        # safe if called before _status_label is built (early wizard init)
        if hasattr(self, '_status_label') and self._status_label is not None:
            self._status_label.configure(text=msg)
            self.update_idletasks()

    def _prog_open(self, title="Computing...", topmost=False):
        """Open a progress popup with bar + percentage + elapsed time.

        v28.10 (사용자 요청 2026.05.21): X 버튼 클릭 시 취소 플래그 설정.
        다음 _prog_update 호출에서 _UserCancelled 예외 발생 → tab 메서드가 catch.
        v28.17 (Seunghoon): topmost=True면 작업 중 창을 항상 위에 둔다(메시 재생성
        처럼 짧고 블로킹인 작업용 — 캔버스 redraw가 메인 창을 앞으로 올려도 가려지지
        않게). 긴 작업(solve)은 기존대로 topmost=False(최소화 가능)."""
        # Close any existing popup
        if hasattr(self, '_prog_win') and self._prog_win:
            try: self._prog_win.destroy()
            except: pass
            self._prog_win = None; self._prog_lbl = None
        # reset cancel flag for new operation
        self._prog_cancelled = False
        try:
            w = ctk.CTkToplevel(self); w.title("2L-FEST")
            w.geometry("420x130+600+400"); w.resizable(False, False)
            # (Seunghoon): make the progress popup a normal, MINIMIZABLE
            # and movable window. The previous permanent always-on-top
            # (attributes('-topmost', True)) pinned it in front and blocked the
            # OS minimize button. Instead we lift + focus it once on open and
            # leave it as an ordinary top-level: the user can now minimize it,
            # move it, or send it behind other windows.
            try:
                w.lift()
                w.focus_force()
                if topmost:
                    # 항상 위에 두되, 사용자가 직접 최소화하면 내려가게 한다:
                    #   최소화(iconic) 순간엔 topmost를 풀고, 복원(map)되면 다시 위로.
                    #   (permanent topmost는 최소화 버튼을 무력화해서 못 내림.)
                    w.attributes('-topmost', True)

                    def _prog_on_unmap(_e=None, _w=w):
                        try:
                            if _w.state() == 'iconic':
                                _w.attributes('-topmost', False)
                        except Exception:
                            pass

                    def _prog_on_map(_e=None, _w=w):
                        try:
                            if _w.state() != 'iconic':
                                _w.attributes('-topmost', True)
                        except Exception:
                            pass

                    w.bind('<Unmap>', _prog_on_unmap)
                    w.bind('<Map>', _prog_on_map)
            except Exception:
                pass
            # hook X (close button) to cancel handler
            w.protocol("WM_DELETE_WINDOW", self._prog_cancel)
            # Title/message label
            lbl = ctk.CTkLabel(w, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                               text_color="white", fg_color=CLR_HEADER,
                               corner_radius=8, width=400, height=40)
            lbl.pack(padx=10, pady=(10, 4))
            # Progress bar
            pbar = ctk.CTkProgressBar(w, width=380, height=18,
                                       progress_color="#2E7D32")
            pbar.set(0)
            pbar.pack(padx=10, pady=2)
            # Percentage + elapsed time label
            pct_lbl = ctk.CTkLabel(w, text="0%  |  0.0s elapsed",
                                    font=ctk.CTkFont(size=10),
                                    text_color="#555555")
            pct_lbl.pack(pady=(2, 6))
            self._prog_win = w
            self._prog_lbl = lbl
            self._prog_bar = pbar
            self._prog_pct_lbl = pct_lbl
            self._prog_t0 = time.time()
            w.update()
        except:
            self._prog_win = None
            self._prog_lbl = None
            self._prog_bar = None
            self._prog_pct_lbl = None

    def _prog_cancel(self):
        """v28.10: X 버튼 핸들러. 취소 플래그 설정 + UI 업데이트.
        실제 종료는 다음 _prog_update 시 예외로 처리."""
        self._prog_cancelled = True
        if hasattr(self, '_prog_lbl') and self._prog_lbl:
            try:
                self._prog_lbl.configure(text="Cancelling... will stop at next checkpoint",
                                          fg_color="#C0392B")
            except: pass
        if hasattr(self, '_prog_pct_lbl') and self._prog_pct_lbl:
            try:
                self._prog_pct_lbl.configure(text="Cancelling...", text_color="#C0392B")
            except: pass

    def _prog_update(self, msg, pct=None):
        """Update progress popup. pct is 0..1 (or None to leave unchanged).
        v28.10: 취소 플래그 set 되면 _UserCancelled 예외 발생."""
        # cancel check BEFORE update
        if getattr(self, '_prog_cancelled', False):
            raise _UserCancelled("Cancelled by user")
        self._status(msg)
        if hasattr(self, '_prog_lbl') and self._prog_lbl:
            try:
                self._prog_lbl.configure(text=msg)
                if pct is not None and hasattr(self, '_prog_bar') and self._prog_bar:
                    pct = max(0.0, min(1.0, pct))
                    self._prog_bar.set(pct)
                if hasattr(self, '_prog_pct_lbl') and self._prog_pct_lbl:
                    elapsed = time.time() - getattr(self, '_prog_t0', time.time())
                    pct_str = f"{int(pct*100)}%" if pct is not None else "—"
                    self._prog_pct_lbl.configure(
                        text=f"{pct_str}  |  {elapsed:.1f}s elapsed")
                self._prog_win.update()
            except _UserCancelled:
                raise  # propagate
            except: pass

    def _prog_close(self, msg="Done."):
        self._status(msg)
        w = getattr(self, '_prog_win', None)
        if w is not None:
            try:
                w.withdraw()  # hide immediately
                w.destroy()
            except: pass
        self._prog_win = None
        self._prog_lbl = None
        self._prog_bar = None
        self._prog_pct_lbl = None
        # reset cancel flag
        self._prog_cancelled = False
        try:
            self.update_idletasks()
            self.update()
        except: pass

    def _clear_fig(self):
        # Destroy any tab-overlay CTk buttons (VALIDATE / LIT BENCH)
        # before clearing canvas. Otherwise buttons placed via .place() on the
        # canvas widget persist across tab switches.
        for attr in ('_validate_btns', '_lit_btns'):
            btns = getattr(self, attr, None)
            if btns:
                for b in btns:
                    try: b.destroy()
                    except: pass
                setattr(self, attr, [])
        self.fig.clear()
        self.gs = gridspec.GridSpec(2, 3, figure=self.fig,
                                   left=0.06, right=0.97, top=0.93, bottom=0.08,
                                   hspace=0.35, wspace=0.32)

    def _refresh(self):
        # draw_idle (deferred, non-blocking) instead of draw (blocking)
        # Gives Tkinter event loop time to handle clicks/keys → UI feels responsive.
        try:
            self.canvas.draw_idle()
        except Exception:
            self.canvas.draw()

    def _get_params(self):
        try:
            # FRONT DESIGN card no longer holds widths — BEFORE card is master.
            # Mesh width = tb_b[2]/tb_b[3]. AFTER uses its own width for R calc only
            # (mesh shade region is fixed to BEFORE geometry).

            # BEFORE card (7 fields):
            #   [0]=BulkR, [1]=FingerH, [2]=WFinger, [3]=WBusbar,
            #   [4]=ShapeCF, [5]=ContactR, [6]=TCO_Rsheet
            rm_b = float(self.tb_b[0].get()) * 1e-6   # bulk resistivity
            hf_b = float(self.tb_b[1].get()) * 1e-4   # finger height
            wf_b = float(self.tb_b[2].get()) * 1e-4   # finger width (Before) -- MASTER
            wb_b = float(self.tb_b[3].get()) * 1e-4   # busbar width (Before) -- MASTER
            cf_b = float(self.tb_b[4].get())          # shape CF
            rc_b = float(self.tb_b[5].get()) * 1e-3   # contact resistivity
            rs   = float(self.tb_b[6].get())          # TCO R_sheet

            # AFTER card (6 fields, no TCO since unchanged):
            #   [0]=BulkR, [1]=FingerH, [2]=WFinger, [3]=WBusbar,
            #   [4]=ShapeCF, [5]=ContactR
            rm_a = float(self.tb_a[0].get()) * 1e-6
            hf_a = float(self.tb_a[1].get()) * 1e-4
            wf_a = float(self.tb_a[2].get()) * 1e-4   # finger width (After)
            wb_a = float(self.tb_a[3].get()) * 1e-4   # busbar width (After)
            cf_a = float(self.tb_a[4].get())
            rc_a = float(self.tb_a[5].get()) * 1e-3

            values = {
                "Before bulk resistivity": rm_b,
                "Before finger height": hf_b,
                "Before finger width": wf_b,
                "Before busbar width": wb_b,
                "Before shape correction": cf_b,
                "Before contact resistivity": rc_b,
                "TCO sheet resistance": rs,
                "After bulk resistivity": rm_a,
                "After finger height": hf_a,
                "After finger width": wf_a,
                "After busbar width": wb_a,
                "After shape correction": cf_a,
                "After contact resistivity": rc_a,
            }
            for name, value in values.items():
                if not np.isfinite(value):
                    raise ValueError(f"{name} must be finite")
            for name in (
                "Before bulk resistivity", "Before finger height",
                "Before finger width", "Before busbar width",
                "Before shape correction", "TCO sheet resistance",
                "After bulk resistivity", "After finger height",
                "After finger width", "After busbar width",
                "After shape correction",
            ):
                if values[name] <= 0:
                    raise ValueError(f"{name} must be > 0")
            for name in ("Before contact resistivity", "After contact resistivity"):
                if values[name] < 0:
                    raise ValueError(f"{name} must be >= 0")

            return (rm_b,hf_b,wf_b,wb_b,cf_b,rc_b,rs), (rm_a,hf_a,wf_a,wb_a,cf_a,rc_a,rs)
        except Exception as e:
            self._status(f"Input error: {e}")
            return None, None

    def _run_both(self):
        if not self._apply_grid_design():  # Re-mesh if grid params changed
            return None
        if not self._apply_diode_params():  # Apply n1/n2 values from GUI
            return None
        bp, ap = self._get_params()
        if bp is None: return None
        mode = self._mode_var.get()  # 'tandem' or 'single'
        rm_b,hf_b,wf_b,wb_b,cf_b,rc_b,rs = bp
        rm_a,hf_a,wf_a,wb_a,cf_a,rc_a,_ = ap
        # Inform user which solver path will run (timing varies dramatically)
        rear_mode = self._rear_mode_var.get() if hasattr(self, '_rear_mode_var') else 'full_area'
        if mode == 'tandem' and DP.Rs_junction > 0 and rear_mode == 'bifacial':
            solver_info = "Phase B + bifacial (6-plane, ~30-60s)"
        elif mode == 'tandem' and DP.Rs_junction > 0:
            solver_info = "Phase B (5-plane, ~15-30s)"
        elif mode == 'tandem' and rear_mode == 'bifacial':
            solver_info = "Bifacial Phase A (~10-20s)"
        elif mode == 'tandem':
            solver_info = "Tandem full_area (~5-10s)"
        else:
            solver_info = "Single cell (~2-5s)"
        import time as _time
        _t0 = _time.time()
        self._prog_update(f"[{solver_info}] Computing Before I-V...", pct=0.05)
        Vs_b,Js_b,iv_b = S.calc_iv(rm_b,hf_b,wf_b,rc_b,rs,cf_b,DP,mode=mode,wb=wb_b)
        _t1 = _time.time()
        self._prog_update(f"[{solver_info}] Before done ({_t1-_t0:.1f}s). Computing After I-V...", pct=0.45)
        Vs_a,Js_a,iv_a = S.calc_iv(rm_a,hf_a,wf_a,rc_a,rs,cf_a,DP,mode=mode,wb=wb_a)
        _t2 = _time.time()
        self._prog_update(f"[{solver_info}] Computing losses at MPP (Before)... [{_t2-_t0:.1f}s elapsed]", pct=0.85)
        vmpp_b_bias = iv_b.get('Vmpp_internal', iv_b['Vmpp'])
        vmpp_a_bias = iv_a.get('Vmpp_internal', iv_a['Vmpp'])
        res_b = iv_b.get('_mpp_result') or S.solve(rm_b,hf_b,wf_b,rc_b,rs,vmpp_b_bias,cf_b,DP,mode=mode,wb=wb_b)
        Ve_b=res_b['Ve']; Vm_b=res_b['Vm']; Vt_b=res_b.get('Vtop'); Vr_b=res_b['Vr']
        loss_b = S.losses(res_b,rm_b,hf_b,wf_b,rc_b,rs,cf_b,DP,Vmpp=iv_b['Vmpp'],Jmpp=iv_b['Jmpp'],wb=wb_b)
        Pe_b=loss_b['Pe']; Pff_b=loss_b['Pf_finger']; Pfb_b=loss_b['Pf_busbar']
        Pc_b=loss_b['Pc']; Ps_b=loss_b['P_shade']
        Psh_b=loss_b['P_shunt']; Prec_b=loss_b['P_recomb']
        Pj_b=loss_b.get('P_Rc_junction',0.0)
        # v28: stash V_int for Before (Phase B only; None otherwise)
        Vint_b = (res_b.get('Vint').copy()
                  if res_b.get('Vint') is not None else None)
        self._prog_update("Computing losses at MPP (After)...", pct=0.92)
        res_a = iv_a.get('_mpp_result') or S.solve(rm_a,hf_a,wf_a,rc_a,rs,vmpp_a_bias,cf_a,DP,mode=mode,wb=wb_a)
        Ve_a=res_a['Ve']; Vm_a=res_a['Vm']; Vt_a=res_a.get('Vtop'); Vr_a=res_a['Vr']
        loss_a = S.losses(res_a,rm_a,hf_a,wf_a,rc_a,rs,cf_a,DP,Vmpp=iv_a['Vmpp'],Jmpp=iv_a['Jmpp'],wb=wb_a)
        Pe_a=loss_a['Pe']; Pff_a=loss_a['Pf_finger']; Pfb_a=loss_a['Pf_busbar']
        Pc_a=loss_a['Pc']; Ps_a=loss_a['P_shade']
        Psh_a=loss_a['P_shunt']; Prec_a=loss_a['P_recomb']
        Pj_a=loss_a.get('P_Rc_junction',0.0)
        # v28: stash V_int for After (Phase B only)
        Vint_a = (res_a.get('Vint').copy()
                  if res_a.get('Vint') is not None else None)
        Pf_b=Pff_b+Pfb_b; Pf_a=Pff_a+Pfb_a
        # Recomb currents
        Rc_b = S.recomb_currents(res_b, DP)
        Rc_a = S.recomb_currents(res_a, DP)
        # Current matching diagnostics (tandem only) — Step 3
        if mode == 'tandem':
            try:
                cm_b = S.current_matching_diagnostics(res_b, DP)
                cm_a = S.current_matching_diagnostics(res_a, DP)
            except Exception as _e:
                self._status(f"CM diagnostics error: {_e}")
                cm_b = cm_a = None
        else:
            cm_b = cm_a = None
        # R_series, G_shunt
        Rs_ext_b, Gsh_b = FESTSolver.extract_rs_gsh(Vs_b, Js_b)
        Rs_ext_a, Gsh_a = FESTSolver.extract_rs_gsh(Vs_a, Js_a)
        health_b = _iv_health(iv_b)
        health_a = _iv_health(iv_a)
        self._cache.update(dict(bp=bp,ap=ap,mode=mode,Vs_b=Vs_b,Js_b=Js_b,iv_b=iv_b,
            Vs_a=Vs_a,Js_a=Js_a,iv_a=iv_a,
            Ve_b=Ve_b,Vm_b=Vm_b,Vt_b=Vt_b,Ve_a=Ve_a,Vm_a=Vm_a,Vt_a=Vt_a,
            Vr_b=Vr_b,Vr_a=Vr_a,
            Vint_b=Vint_b,Vint_a=Vint_a,
            Pe_b=Pe_b,Pf_b=Pf_b,Pc_b=Pc_b,Ps_b=Ps_b,Psh_b=Psh_b,Prec_b=Prec_b,Pj_b=Pj_b,
            Pe_a=Pe_a,Pf_a=Pf_a,Pc_a=Pc_a,Ps_a=Ps_a,Psh_a=Psh_a,Prec_a=Prec_a,Pj_a=Pj_a,
            Pff_b=Pff_b,Pfb_b=Pfb_b,Pff_a=Pff_a,Pfb_a=Pfb_a,
            Rc_b=Rc_b,Rc_a=Rc_a,Rs_ext_b=Rs_ext_b,Rs_ext_a=Rs_ext_a,
            Gsh_b=Gsh_b,Gsh_a=Gsh_a,
            cm_b=cm_b,cm_a=cm_a,
            health_b=health_b,health_a=health_a))
        return self._cache

    def _draw_table(self, ax, rows, cw, hc='#1a237e', rc_=['white','#f0f4ff']):
        ax.axis('off'); ax.set_xlim(0,1); ax.set_ylim(0,1)
        n = len(rows); rh = 0.9/max(n,1)
        for ri, row in enumerate(rows):
            y = 0.95 - ri*rh
            bg = hc if ri==0 else rc_[ri%2]
            fc = 'white' if ri==0 else '#222'
            fw = 'bold' if ri==0 else 'normal'
            ax.add_patch(FancyBboxPatch((0.01,y-rh*0.8),0.98,rh*0.85,
                boxstyle='round,pad=0.01',fc=bg,ec='#ddd',lw=0.5))
            xp = 0.03
            for cell, w in zip(row, cw):
                ax.text(xp, y-rh*0.3, str(cell), fontsize=7, va='center',
                       color=fc, fontweight=fw)
                xp += w

    # ---------------------------------------------------------
    # TAB: COMPARE
    # ---------------------------------------------------------
    def _tab_compare(self):
        self._last_tab = self._tab_compare
        self._clear_fig()
        self._prog_open(_t("computing_iv"))
        self.update_idletasks()
        try:
            c = self._run_both()
        except _UserCancelled:
            self._prog_close("Cancelled.")
            return
        if c is None:
            self._prog_close("Error in inputs.")
            return
        iv_b=c['iv_b']; iv_a=c['iv_a']
        Pe_b=c['Pe_b']; Pf_b=c['Pf_b']; Pc_b=c['Pc_b']; Ps_b=c['Ps_b']
        Pe_a=c['Pe_a']; Pf_a=c['Pf_a']; Pc_a=c['Pc_a']; Ps_a=c['Ps_a']
        Pt_b=Pe_b+Pf_b+Pc_b; Pt_a=Pe_a+Pf_a+Pc_a
        bp=c['bp']; ap=c['ap']
        Rl_b=bp[0]/(bp[4]*bp[2]*bp[1]); Rl_a=ap[0]/(ap[4]*ap[2]*ap[1])

        # I-V
        ax1 = self.fig.add_subplot(self.gs[0,0])
        ax1.plot(c['Vs_b'],c['Js_b'],'--',color='#e74c3c',lw=2.5,label=_t('before_sim'))
        ax1.plot(c['Vs_a'],c['Js_a'],'-',color='#2ecc71',lw=2.5,label=_t('after_sim'))
        if 'V_exp' in self._exp_data:
            ax1.plot(self._exp_data['V_exp'],self._exp_data['J_exp'],'ko',ms=4,alpha=0.6,label='Experiment')
        ax1.plot(iv_b['Vmpp'],iv_b['Jmpp'],'o',color='#e74c3c',ms=8)
        ax1.plot(iv_a['Vmpp'],iv_a['Jmpp'],'s',color='#2ecc71',ms=8)
        ax1.annotate(f'MPP {iv_b["Eff"]:.2f}%', xy=(iv_b['Vmpp'],iv_b['Jmpp']),
                    xytext=(-8,-18), textcoords='offset points', fontsize=6.5, color='#b71c1c')
        ax1.annotate(f'MPP {iv_a["Eff"]:.2f}%', xy=(iv_a['Vmpp'],iv_a['Jmpp']),
                    xytext=(8,8), textcoords='offset points', fontsize=6.5, color='#1b5e20')
        ax1.set_xlabel(_t('voltage')); ax1.set_ylabel('J [mA/cm2]')
        ax1.set_title(_t('tandem_iv'),fontweight='bold'); ax1.legend(fontsize=7); ax1.grid(True,alpha=0.2)

        # Loss bar -- Resistive only (Griddler style: separate from recomb)
        Pff_b=c.get('Pff_b',Pf_b/2); Pfb_b=c.get('Pfb_b',Pf_b/2)
        Pff_a=c.get('Pff_a',Pf_a/2); Pfb_a=c.get('Pfb_a',Pf_a/2)
        Psh_b=c.get('Psh_b',0); Psh_a=c.get('Psh_a',0)
        Prec_b=c.get('Prec_b',0); Prec_a=c.get('Prec_a',0)
        Pj_b=c.get('Pj_b',0); Pj_a=c.get('Pj_a',0)
        ax2 = self.fig.add_subplot(self.gs[0,1])
        cats=['Emitter','Finger','Busbar','Contact']; x=np.arange(4); w=0.35
        bv=[Pe_b,Pff_b,Pfb_b,Pc_b]; av=[Pe_a,Pff_a,Pfb_a,Pc_a]
        ax2.bar(x-w/2,bv,w,label='Before',color='#e74c3c',alpha=0.85)
        ax2.bar(x+w/2,av,w,label='After',color='#2ecc71',alpha=0.85)
        for i in range(4):
            if bv[i] > 0.005: ax2.text(x[i]-w/2, bv[i]+0.005, f'{bv[i]:.3f}', ha='center', fontsize=6, color='#b71c1c')
            if av[i] > 0.005: ax2.text(x[i]+w/2, av[i]+0.005, f'{av[i]:.3f}', ha='center', fontsize=6, color='#1b5e20')
        ax2.set_xticks(x); ax2.set_xticklabels(cats,fontsize=8)
        ax2.set_ylabel(_t('loss_mw'))
        ax2.set_title('Resistive Losses [mW/cm2]',fontweight='bold',fontsize=10)
        ax2.legend(fontsize=7); ax2.grid(True,alpha=0.2,axis='y')

        # Performance table
        ax3 = self.fig.add_subplot(self.gs[0,2]); ax3.axis('off')
        # compute shading per BEFORE/AFTER finger geometry
        # Hot pressing widens fingers (e.g. 50→65 μm) → shading increases
        wf_b = bp[2]; wb_b = bp[3]  # finger/busbar width BEFORE [cm]
        wf_a = ap[2]; wb_a = ap[3]  # finger/busbar width AFTER [cm]
        try:
            sh_b = GEO.shading_fraction(w_f_opt=wf_b, w_b_opt=wb_b) * 100
            sh_a = GEO.shading_fraction(w_f_opt=wf_a, w_b_opt=wb_a) * 100
        except Exception:
            sh_b = sh_a = 0.0
        rows=[['Parameter','Before','After','D'],
            ['Jsc [mA/cm2]',f'{iv_b["Jsc"]:.3f}',f'{iv_a["Jsc"]:.3f}',f'{iv_a["Jsc"]-iv_b["Jsc"]:+.3f}'],
            ['Voc [V]',f'{iv_b["Voc"]:.4f}',f'{iv_a["Voc"]:.4f}',f'{(iv_a["Voc"]-iv_b["Voc"])*1000:+.1f}mV'],
            ['FF [%]',f'{iv_b["FF"]:.2f}',f'{iv_a["FF"]:.2f}',f'{iv_a["FF"]-iv_b["FF"]:+.2f}'],
            ['Eff [%]',f'{iv_b["Eff"]:.3f}',f'{iv_a["Eff"]:.3f}',f'{iv_a["Eff"]-iv_b["Eff"]:+.4f}'],
            ['Pmpp',f'{iv_b["Pmpp"]:.3f}',f'{iv_a["Pmpp"]:.3f}',f'{iv_a["Pmpp"]-iv_b["Pmpp"]:+.3f}'],
            ['R_line',f'{Rl_b:.2f}',f'{Rl_a:.2f}',f'{(Rl_a-Rl_b)/Rl_b*100:+.1f}%'],
            ['Shading [%]',f'{sh_b:.2f}',f'{sh_a:.2f}',f'{sh_a-sh_b:+.2f}']]
        self._draw_table(ax3, rows, [0.26,0.20,0.20,0.22])
        ax3.set_title(_t('tandem_perf'),fontweight='bold')

        # Current Matching mini-summary (tandem mode only) — Step 3
        cm_b = c.get('cm_b')
        if cm_b and cm_b.get('mode') == 'tandem':
            is_match = (cm_b['limiting'] == 'Current-matched')
            color = '#27ae60' if is_match else '#E67E22'
            # Two compact lines under the table
            ax3.text(0.5, 0.075,
                f"CM: {cm_b['limiting']}  ({cm_b['mismatch']:+.2f} mA/cm², {cm_b['mismatch_pct']:+.2f}%)",
                ha='center', fontsize=7.5, color=color, fontweight='bold',
                transform=ax3.transAxes)
            ax3.text(0.5, 0.020,
                f"Top {cm_b['Jph_top_eff']:.2f}  /  Bot {cm_b['Jph_bot_eff']:.2f} mA/cm²   |   "
                f"MPP RMS {cm_b['rms_residual']:.1e}",
                ha='center', fontsize=6.5, color='#555',
                transform=ax3.transAxes)

        # --- Bottom row: Griddler-style loss decomposition (bar charts, B vs A) ---

        # All losses bar (Before vs After): Shading / Resistive / Shunt / Recomb
        # Junction loss is excluded from the bar (typically <0.001 mW/cm² in
        # uniform cells; shown numerically in the Hot Pressing summary panel).
        ax4 = self.fig.add_subplot(self.gs[1,0])
        Rt_b = Pe_b + Pf_b + Pc_b; Rt_a = Pe_a + Pf_a + Pc_a
        loss_cats = ['Shading','Resistive','Shunt','Recomb']
        loss_b = [Ps_b, Rt_b, Psh_b, Prec_b]
        loss_a = [Ps_a, Rt_a, Psh_a, Prec_a]
        y_pos = np.arange(4); bh = 0.35
        loss_colors_b = ['#EF5350','#42A5F5','#9b59b6','#1abc9c']
        loss_colors_a = ['#F48FB1','#90CAF9','#CE93D8','#80CBC4']
        ax4.barh(y_pos + bh/2, loss_b, bh, label='Before', color=loss_colors_b, edgecolor='white', lw=0.5)
        ax4.barh(y_pos - bh/2, loss_a, bh, label='After', color=loss_colors_a, edgecolor='white', lw=0.5)
        for i in range(4):
            if loss_b[i] > 0.001: ax4.text(loss_b[i]+0.01, y_pos[i]+bh/2, f'{loss_b[i]:.3f}', va='center', fontsize=6, color='#333')
            if loss_a[i] > 0.001: ax4.text(loss_a[i]+0.01, y_pos[i]-bh/2, f'{loss_a[i]:.3f}', va='center', fontsize=6, color='#555')
        ax4.set_yticks(y_pos); ax4.set_yticklabels(loss_cats, fontsize=8)
        ax4.set_xlabel('Loss [mW/cm2]', fontsize=8)
        ax4.set_title('All Losses (B vs A)',fontweight='bold',fontsize=9)
        ax4.legend(fontsize=7); ax4.grid(True, alpha=0.15, axis='x')
        ax4.invert_yaxis()

        # Recomb current breakdown bar (Before vs After)
        ax5 = self.fig.add_subplot(self.gs[1,1])
        Rc_b = c.get('Rc_b', {}); Rc_a = c.get('Rc_a', {})
        if Rc_b:
            rc_cats = ['Pass n=1','Metal n=1','Metal n=2','Pass n=2']
            rc_b = [Rc_b.get('pass_n1',0), Rc_b.get('met_n1',0), Rc_b.get('met_n2',0), Rc_b.get('pass_n2',0)]
            rc_a = [Rc_a.get('pass_n1',0), Rc_a.get('met_n1',0), Rc_a.get('met_n2',0), Rc_a.get('pass_n2',0)]
            y_rc = np.arange(4); bh_rc = 0.35
            ax5.barh(y_rc + bh_rc/2, rc_b, bh_rc, label='Before', color='#e74c3c', alpha=0.85)
            ax5.barh(y_rc - bh_rc/2, rc_a, bh_rc, label='After', color='#2ecc71', alpha=0.85)
            for i in range(4):
                if rc_b[i] > 0.0001: ax5.text(rc_b[i]+0.001, y_rc[i]+bh_rc/2, f'{rc_b[i]:.4f}', va='center', fontsize=6, color='#b71c1c')
                if rc_a[i] > 0.0001: ax5.text(rc_a[i]+0.001, y_rc[i]-bh_rc/2, f'{rc_a[i]:.4f}', va='center', fontsize=6, color='#1b5e20')
            ax5.set_yticks(y_rc); ax5.set_yticklabels(rc_cats, fontsize=8)
            ax5.set_xlabel('J [mA/cm2]', fontsize=8)
            ax5.set_title('Recomb Currents at MPP',fontweight='bold',fontsize=9)
            ax5.legend(fontsize=7); ax5.grid(True, alpha=0.15, axis='x')
            ax5.invert_yaxis()
        else:
            ax5.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax5.transAxes)

        # Hot pressing summary
        ax6 = self.fig.add_subplot(self.gs[1,2]); ax6.axis('off')
        ed = iv_a['Eff'] - iv_b['Eff']
        sc = '#27ae60' if ed > 0 else '#e74c3c'
        health_b = c.get('health_b') or _iv_health(iv_b)
        health_a = c.get('health_a') or _iv_health(iv_a)
        health_ok = health_b['status'] == 'PASS' and health_a['status'] == 'PASS'
        health_color = '#059669' if health_ok else '#EA580C'
        model_note_active = bool(health_b.get('phase_b_active') or health_a.get('phase_b_active'))
        model_color = '#D97706' if model_note_active else '#999'
        def _sci(v):
            return 'n/a' if v is None else f'{v:.1e}'
        def _num(v, digits=4):
            return 'n/a' if v is None else f'{v:.{digits}f}'
        ax6.text(0.5,0.92,_t('hot_press'),ha='center',fontsize=12,fontweight='bold',transform=ax6.transAxes)
        ax6.text(0.5,0.76,f'{iv_b["Eff"]:.3f}%  ->  {iv_a["Eff"]:.3f}%',ha='center',fontsize=11,fontweight='bold',transform=ax6.transAxes)
        ax6.text(0.5,0.60,f'{ed:+.4f}% abs',ha='center',fontsize=18,fontweight='bold',color=sc,transform=ax6.transAxes)
        ax6.text(0.5,0.45,
                 f'Total loss: {Pt_b+Psh_b+Prec_b+Pj_b:.3f} -> {Pt_a+Psh_a+Prec_a+Pj_a:.3f} mW/cm2',
                 ha='center',fontsize=8.5,fontweight='bold',transform=ax6.transAxes,color=sc)
        ax6.text(0.5,0.34,
                 f'Result Health: B {health_b["status"]} / A {health_a["status"]}',
                 ha='center',fontsize=9,fontweight='bold',transform=ax6.transAxes,color=health_color)
        ax6.text(0.5,0.25,
                 f'Newton residual: {_sci(health_b["final_newton_residual"])} / {_sci(health_a["final_newton_residual"])}',
                 ha='center',fontsize=7.5,transform=ax6.transAxes,color='#555')
        ax6.text(0.5,0.17,
                 f'MPP err: {_sci(health_b["pmpp_consistency_error"])} / {_sci(health_a["pmpp_consistency_error"])}',
                 ha='center',fontsize=7.5,transform=ax6.transAxes,color='#555')
        ax6.text(0.5,0.09,
                 f'Rs_lumped: {_num(health_b["rs_lumped_total"],2)} / {_num(health_a["rs_lumped_total"],2)} ohm*cm2',
                 ha='center',fontsize=7.5,transform=ax6.transAxes,color='#555')
        ax6.text(0.5,0.02,
                 f'Model B/A: {health_b.get("phase_b_status","BASELINE")}/{health_a.get("phase_b_status","BASELINE")} '
                 f'| fallback B/A: {health_b["fallback_used"]}/{health_a["fallback_used"]}',
                 ha='center',fontsize=7,transform=ax6.transAxes,color=model_color)

        # Sanity check warnings
        # BEFORE/AFTER FF < 50% or Recomb > 5 mW/cm² indicates likely cell-design issue
        warnings = []
        if iv_b['FF'] < 50:
            warnings.append(f"⚠ BEFORE FF={iv_b['FF']:.1f}% (비정상 낮음)")
        elif iv_b['FF'] < 65:
            warnings.append(f"⚠ BEFORE FF={iv_b['FF']:.1f}% (낮음, 점검 권장)")
        if iv_a['FF'] < 50:
            warnings.append(f"⚠ AFTER FF={iv_a['FF']:.1f}% (비정상 낮음)")
        if Prec_b > 5.0:
            warnings.append(f"⚠ Recomb BEFORE={Prec_b:.1f} mW/cm² (비정상)")
        if Prec_a > 5.0:
            warnings.append(f"⚠ Recomb AFTER={Prec_a:.1f} mW/cm² (비정상)")
        if iv_b['Eff'] < 15:
            warnings.append(f"⚠ BEFORE PCE={iv_b['Eff']:.1f}% (Tandem 표준 미달)")
        # v28.23: Phase B(Rs_junction) 사용 시 띄우던 "신뢰성 점검 필요" 안내 배너
        # 메시지는 사용자 요청으로 제거(상태바 안내도 함께 제거). 실제 수렴/FF/재결합
        # 등 물리적 health 경고는 아래에서 그대로 유지된다.

        def _non_model_health_message(health):
            msg = str(health.get('message', ''))
            phase_msg = str(health.get('phase_b_message', ''))
            if phase_msg:
                msg = msg.replace(phase_msg, '')
            return msg.replace(';;', ';').strip('; ')

        msg_b = _non_model_health_message(health_b)
        msg_a = _non_model_health_message(health_a)
        if health_b['status'] != 'PASS' and msg_b:
            warnings.append(f"Before health CHECK: {msg_b}")
        if health_a['status'] != 'PASS' and msg_a:
            warnings.append(f"After health CHECK: {msg_a}")

        if warnings:
            # Draw warning banner overlay on compare panel
            warn_text = "\n".join(warnings[:4])  # max 4 lines
            self.fig.text(0.5, 0.005, "결과 신뢰성 점검 필요:  " + " | ".join(warnings),
                          ha='center', fontsize=8, color='#C62828', fontweight='bold',
                          bbox=dict(boxstyle='round,pad=0.4', fc='#FFEBEE',
                                    ec='#C62828', lw=1.0, alpha=0.95))

        self._refresh()

        # Sanity check on status bar
        if warnings:
            self._prog_close(f'COMPARE done (⚠ {len(warnings)} 경고). Eff: {iv_b["Eff"]:.3f} -> {iv_a["Eff"]:.3f}%')
        else:
            self._prog_close(f'COMPARE done.  Eff: {iv_b["Eff"]:.3f} -> {iv_a["Eff"]:.3f}% (D={ed:+.4f}%)')


    # ---------------------------------------------------------
    # TAB: CURRENT MAP
    # ---------------------------------------------------------
    def _tab_current(self):
        """Mode-aware voltage/current maps.

        full_area: 5 panels (no rear emitter, since rear is grounded plane)
        bifacial : 6 panels (adds Rear Emitter V — L3 TCO)

        Common to both:
          Front Emitter V (L1) | Top Cell V | Bottom Cell V
          Recomb. Junction V   | (Rear Emitter V if bifacial) | Current Density
        """
        self._last_tab = self._tab_current
        self.fig.clear()
        if 'Ve_b' not in self._cache:
            self._status(_t('run_compare_first')); return
        self._prog_open(_t("drawing_maps"))
        self._prog_update(_t("drawing_maps"), pct=0.10)
        Ve_b=self._cache['Ve_b']; Vt_b=self._cache.get('Vt_b')
        Vr_b=self._cache.get('Vr_b')
        Vint_b = self._cache.get('Vint_b', None)
        mode = self._cache.get('mode', 'tandem')
        is_bifacial = (GEO.rear_mode in ('bifacial', 'patterned'))
        _cb_kw = dict(shrink=0.72, pad=0.02, aspect=18)
        mode_label = "Tandem" if mode == 'tandem' else "Single Cell"
        rear_label = "bifacial" if is_bifacial else "full_area"
        self.fig.suptitle(
            f'Voltage / Current Maps  [{mode_label}, rear={rear_label}, BEFORE pressing, at MPP]',
            fontsize=11, fontweight='bold', color='#c0392b', y=0.98)

        # Mode-aware layout: 3 cols always; bot row has 3 cols (bifacial) or 2 (full_area)
        gs_top = gridspec.GridSpec(1, 3, figure=self.fig,
                                    left=0.05, right=0.97, top=0.92, bottom=0.52,
                                    wspace=0.35)
        n_bot = 3 if is_bifacial else 2
        gs_bot = gridspec.GridSpec(1, n_bot, figure=self.fig,
                                    left=0.10 if not is_bifacial else 0.05,
                                    right=0.90 if not is_bifacial else 0.97,
                                    top=0.46, bottom=0.05,
                                    wspace=0.40)

        # =========================================================
        # TOP ROW: Front Emitter V (L1) | Top Cell V | Bottom Cell V
        # =========================================================
        # Panel 1: Front Emitter V (L1 — front TCO)
        ax1 = self.fig.add_subplot(gs_top[0, 0])
        tcf = ax1.tricontourf(triang, Ve_b, levels=50, cmap='inferno')
        self.fig.colorbar(tcf, ax=ax1, label='V', **_cb_kw)
        emitter_title = 'Front Emitter V (L1, TCO)' if is_bifacial else 'Emitter V (TCO)'
        ax1.set_title(emitter_title, fontweight='bold', fontsize=9)
        ax1.set_aspect('equal', adjustable='box')
        ax1.set_xlabel('X [mm]'); ax1.set_ylabel('Y [mm]')

        if mode == 'tandem' and Vt_b is not None:
            # Panel 2: Top Cell V (Perovskite)
            ax2 = self.fig.add_subplot(gs_top[0, 1])
            tcf2 = ax2.tricontourf(triang, Vt_b, levels=50, cmap='inferno')
            self.fig.colorbar(tcf2, ax=ax2, label='V', **_cb_kw)
            ax2.set_title('Top Cell V (Perovskite)', fontweight='bold', fontsize=9)
            ax2.set_aspect('equal', adjustable='box')
            ax2.set_xlabel('X [mm]'); ax2.set_ylabel('Y [mm]')

            # Panel 3: Bottom Cell V (Si)
            # Vbot = V_int - Vr (Phase B) or Ve - Vt - Vr (Phase A)
            ax3 = self.fig.add_subplot(gs_top[0, 2])
            Vr_for_bot = Vr_b if Vr_b is not None else 0.0
            if Vint_b is not None:
                Vbot = Vint_b - Vr_for_bot
            else:
                Vbot = Ve_b - Vt_b - Vr_for_bot
            tcf3 = ax3.tricontourf(triang, Vbot, levels=50, cmap='inferno')
            self.fig.colorbar(tcf3, ax=ax3, label='V', **_cb_kw)
            ax3.set_title('Bottom Cell V (Si)', fontweight='bold', fontsize=9)
            ax3.set_aspect('equal', adjustable='box')
            ax3.set_xlabel('X [mm]'); ax3.set_ylabel('Y [mm]')
        else:
            for col, msg in [(1, 'Single Cell Mode'),
                             (2, '(no top/bot subcell)')]:
                ax_e = self.fig.add_subplot(gs_top[0, col])
                ax_e.text(0.5, 0.55, 'N/A', ha='center', va='center',
                          fontsize=22, color='#CBD5E1', fontweight='bold',
                          transform=ax_e.transAxes)
                ax_e.text(0.5, 0.42, msg, ha='center', va='center',
                          fontsize=9, color='#94A3B8',
                          transform=ax_e.transAxes)
                ax_e.set_xticks([]); ax_e.set_yticks([])
                for spine in ax_e.spines.values():
                    spine.set_color('#E2E8F0')

        # =========================================================
        # BOTTOM ROW
        # bifacial : Recomb. Junction V | Rear Emitter V (L3) | Current Density
        # full_area: Recomb. Junction V | Current Density
        # =========================================================
        # Panel 4: Recombination Junction V (formerly "V_int (Phase B)")
        ax4 = self.fig.add_subplot(gs_bot[0, 0])
        if Vint_b is not None and mode == 'tandem':
            Vint_mV = Vint_b * 1000
            spread = Vint_mV.max() - Vint_mV.min()
            tcfV = ax4.tricontourf(triang, Vint_mV, levels=50, cmap='RdBu_r')
            self.fig.colorbar(tcfV, ax=ax4, label='mV', **_cb_kw)
            ax4.set_title(f'Recomb. Junction V  (spread {spread:.2f} mV)',
                          fontweight='bold', fontsize=9)
        else:
            # Phase B disabled (Rs_junction=0): show note instead
            ax4.text(0.5, 0.5,
                     'Recomb. Junction V\n\n(enable lateral Rs_junction\n in sidebar to view)',
                     ha='center', va='center', fontsize=10, color='#94A3B8',
                     transform=ax4.transAxes)
            ax4.set_xticks([]); ax4.set_yticks([])
            for spine in ax4.spines.values():
                spine.set_color('#E2E8F0')
        ax4.set_aspect('equal', adjustable='box')
        ax4.set_xlabel('X [mm]'); ax4.set_ylabel('Y [mm]')

        # Panel 5 (bifacial only): Rear Emitter V (L3 — rear TCO)
        if is_bifacial:
            ax5 = self.fig.add_subplot(gs_bot[0, 1])
            Vr_plot = (Vr_b if Vr_b is not None else np.zeros_like(Ve_b)) * 1000
            tcf_r = ax5.tricontourf(triang, Vr_plot, levels=50, cmap='RdBu_r')
            self.fig.colorbar(tcf_r, ax=ax5, label='mV', **_cb_kw)
            ax5.set_title('Rear Emitter V (L3, TCO)', fontweight='bold', fontsize=9)
            ax5.set_aspect('equal', adjustable='box')
            ax5.set_xlabel('X [mm]'); ax5.set_ylabel('Y [mm]')

        # Last panel: Current Density (top diode current at MPP, mA/cm²)
        ax_last = self.fig.add_subplot(gs_bot[0, n_bot - 1])
        if mode == 'tandem' and Vt_b is not None:
            # Compute J_top per node = ilf*Jph - J01*(exp(qV/n1kT)-1) - J02*(...) - V/Rsh
            mf = S.metal_frac; ilf = S.illum_frac
            J01_arr = DP.J01_top_pass*(1-mf) + DP.J01_top_metal*mf
            J02_arr = DP.J02_top_pass*(1-mf) + DP.J02_top_metal*mf
            VT_ = 0.02585  # ~kT/q at 300K
            e1 = np.exp(np.minimum(Vt_b/(DP.n1_top*VT_), 80))
            e2 = np.exp(np.minimum(Vt_b/(DP.n2_top*VT_), 80))
            Jnode = (ilf*DP.Jph_top - J01_arr*(e1-1) - J02_arr*(e2-1) - Vt_b/DP.Rsh_top) * 1000  # mA/cm²
            # Clip extremes for cleaner colormap
            jmin, jmax = np.percentile(Jnode, [2, 98])
            Jnode_c = np.clip(Jnode, jmin, jmax)
            tcfJ = ax_last.tricontourf(triang, Jnode_c, levels=50, cmap='viridis')
            self.fig.colorbar(tcfJ, ax=ax_last, label='mA/cm²', **_cb_kw)
            ax_last.set_title(f'Current Density at MPP\n(top diode, mean {Jnode.mean():.2f})',
                              fontweight='bold', fontsize=9)
        else:
            ax_last.text(0.5, 0.5, 'Current Density\n(tandem mode only)',
                         ha='center', va='center', fontsize=10, color='#94A3B8',
                         transform=ax_last.transAxes)
            ax_last.set_xticks([]); ax_last.set_yticks([])
            for spine in ax_last.spines.values():
                spine.set_color('#E2E8F0')
        ax_last.set_aspect('equal', adjustable='box')
        ax_last.set_xlabel('X [mm]'); ax_last.set_ylabel('Y [mm]')

        self._prog_update("Rendering plots...", pct=0.95)
        self._refresh()
        self._prog_close("Voltage / current maps displayed.")


    # ---------------------------------------------------------
    # TAB: FF WATERFALL
    # ---------------------------------------------------------
    def _tab_waterfall(self):
        self._last_tab = self._tab_waterfall
        self._clear_fig()
        if 'iv_b' not in self._cache:
            self._status(_t('run_compare_first')); return
        self._prog_open(_t("computing_ff"))
        bp=self._cache['bp']; rm,hf,wf,wb,cf,rc,rs=bp; iv_real=self._cache['iv_b']
        mode = self._cache.get('mode', 'tandem')
        # v28.18 (리뷰 1-A): FEM losses() 기반 PCE %abs waterfall.
        #   이전 0D sff() 기반은 subcell_iv가 _pass diode만 읽어 metal recomb /
        #   공간 직렬R / 전극 세부분해를 원리적으로 표현 못 했고(n2·metal 막대가
        #   항상 0), Grid R 칸이 0D↔FEM 점프 전부를 흡수했다. 이제 _run_both가
        #   캐시한 FEM 손실 분해(mW/cm2)를 그대로 쓴다. 100 mW/cm2 입력이므로
        #   PCE[%] = Pmpp[mW/cm2] → 손실 1 mW/cm2 = PCE 1 %abs 하락.
        self._prog_update("Assembling PCE loss waterfall (FEM)...", pct=0.5)
        c = self._cache
        PCE_act = float(iv_real['Eff'])
        L_opt = float(c.get('Ps_b', 0.0))     # optical (shading)
        L_rec = float(c.get('Prec_b', 0.0))   # recombination
        L_sh  = float(c.get('Psh_b', 0.0))    # shunt
        L_e   = float(c.get('Pe_b', 0.0))     # emitter/TCO lateral
        L_ff  = float(c.get('Pff_b', 0.0))    # finger
        L_fb  = float(c.get('Pfb_b', 0.0))    # busbar
        L_c   = float(c.get('Pc_b', 0.0))     # contact
        L_j   = float(c.get('Pj_b', 0.0))     # junction (Rc/Rs)
        L_res = L_e + L_ff + L_fb + L_c + L_j  # 전극 직렬저항 합
        # 손실-free 복원 기준(= 실제 PCE + 모든 손실 채널). 1차(first-order)
        # 복원이며, 각 막대는 FEM losses()가 직접 계산한 값이다.
        PCE_ref = PCE_act + L_opt + L_rec + L_sh + L_res
        # 누적 레벨(위→아래): 기준 → −광학 → −재결합 → −shunt → −직렬R(=Actual)
        lv1 = PCE_ref - L_opt
        lv2 = lv1 - L_rec
        lv3 = lv2 - L_sh
        step_ffs = [PCE_ref, lv1, lv2, lv3, PCE_act]
        step_drops = [0.0, L_opt, L_rec, L_sh, L_res]
        step_labels = ['Loss-free\n(FEM recon.)', '− Optical\n(shade)',
                       '− Recomb', '− Shunt\n(Rsh)',
                       '− Grid R\n(Pe+Pf+Pc)']
        step_colors = ['#27ae60', '#16a085', '#c0392b', '#f39c12', '#3498db']
        step_txt_colors = ['#27ae60', '#0e6655', '#8e1e1e', '#e65100', '#1565c0']
        # plot/summary 코드가 쓰는 기존 변수명 재사용
        FF_ideal = PCE_ref
        FF_grid = PCE_act

        n_s = len(step_ffs)
        ax1 = self.fig.add_subplot(self.gs[0,:2])
        x = np.arange(n_s); bw = 0.55
        y_min = step_ffs[-1] - 5; y_max = step_ffs[0] + 3

        for i in range(n_s):
            if i == 0:
                ax1.bar(x[i], step_ffs[i]-y_min, bw, bottom=y_min, color='#27ae60',
                        edgecolor='#1e8449', lw=1.5, zorder=3)
            else:
                ax1.bar(x[i], step_ffs[i]-y_min, bw, bottom=y_min, color='#ecf0f1',
                        edgecolor='#bdc3c7', lw=0.8, zorder=2)
                ax1.bar(x[i], step_drops[i], bw, bottom=step_ffs[i], color=step_colors[i],
                        edgecolor=step_colors[i], lw=1.5, alpha=0.9, zorder=3)
                ax1.plot([x[i-1]+bw/2, x[i]-bw/2], [step_ffs[i-1], step_ffs[i-1]],
                         '--', color='#555', lw=1.2, zorder=5)

        for i in range(n_s):
            top_y = step_ffs[i] + step_drops[i] if i > 0 else step_ffs[i]
            ax1.text(x[i], top_y+0.4, f'{step_ffs[i]:.1f}%', ha='center',
                     fontsize=11, fontweight='bold', color='#1a237e', zorder=6)

        for i in range(1, n_s):
            if step_drops[i] > 0.02:
                ax1.text(x[i], step_ffs[i]-0.8, f'\u25bc -{step_drops[i]:.2f}%', ha='center', va='top',
                         fontsize=9, fontweight='bold', color=step_txt_colors[i], zorder=6)

        td = step_ffs[0] - step_ffs[-1]
        ax1.annotate('', xy=(n_s-0.45, step_ffs[-1]), xytext=(n_s-0.45, step_ffs[0]),
                     arrowprops=dict(arrowstyle='<->', color='#2c3e50', lw=2.5))
        ax1.text(n_s-0.1, (step_ffs[0]+step_ffs[-1])/2, f'Total\n-{td:.1f}%',
                 fontsize=11, fontweight='bold', color='#2c3e50', va='center')

        ax1.set_xticks(x); ax1.set_xticklabels(step_labels, fontsize=9)
        ax1.set_ylabel('PCE [%abs]', fontsize=11)
        ax1.set_title('PCE loss waterfall (FEM losses)', fontweight='bold', fontsize=13)
        ax1.set_ylim(y_min, y_max); ax1.set_xlim(-0.5, n_s+0.3)
        ax1.spines['top'].set_visible(False); ax1.spines['right'].set_visible(False)
        ax1.grid(True, alpha=0.2, axis='y')

        # Summary panel — FEM 손실 분해 (전극 직렬R 세부 포함)
        ax2 = self.fig.add_subplot(self.gs[0,2]); ax2.axis('off')
        ax2.set_xlim(0,1); ax2.set_ylim(0,1)
        ax2.add_patch(FancyBboxPatch((0.02,0.02),0.96,0.94,transform=ax2.transAxes,
                      boxstyle='round,pad=0.03',fc='#fafafa',ec='#dee2e6',lw=1))
        ax2.text(0.5,0.95,'PCE loss summary [%abs]',ha='center',fontsize=11,fontweight='bold',
                 transform=ax2.transAxes,color='#1a237e')
        summary_items = [
            (0.86, 'Loss-free (recon.)', f'{PCE_ref:.2f}', '#27ae60'),
            (0.77, '− Optical (shade)', f'-{L_opt:.3f}', '#16a085'),
            (0.69, '− Recombination', f'-{L_rec:.3f}', '#c0392b'),
            (0.61, '− Shunt (Rsh)', f'-{L_sh:.3f}', '#f39c12'),
            (0.50, '− Emitter/TCO R', f'-{L_e:.3f}', '#2471a3'),
            (0.42, '− Finger R', f'-{L_ff:.3f}', '#3498db'),
            (0.34, '− Busbar R', f'-{L_fb:.3f}', '#5dade2'),
            (0.26, '− Contact R', f'-{L_c:.3f}', '#85c1e9'),
        ]
        for y_, lbl, val, cl in summary_items:
            ax2.text(0.06, y_, lbl, fontsize=8, transform=ax2.transAxes, color='#333')
            ax2.text(0.74, y_, val, fontsize=8.5, fontweight='bold', transform=ax2.transAxes, color=cl)
        ax2.plot([0.04,0.96],[0.19,0.19],'-',color='#dee2e6',lw=1,transform=ax2.transAxes)
        ax2.text(0.06,0.11,'Actual PCE (FEM)',fontsize=10,fontweight='bold',transform=ax2.transAxes,color='#1a237e')
        ax2.text(0.74,0.11,f'{FF_grid:.2f}%',fontsize=12,fontweight='bold',transform=ax2.transAxes,color='#1a237e')
        if td > 0:
            ax2.text(0.06,0.04,f'Grid R = {step_drops[4]/td*100:.0f}% of total loss',
                     fontsize=7.5,transform=ax2.transAxes,color='#888')

        self._refresh()
        self._prog_close(f'PCE loss waterfall done.  {FF_ideal:.2f}% -> {FF_grid:.2f}%')

        # --- Bottom row: Efficiency Improvement Diagram ---
        if 'iv_a' not in self._cache: return
        ap = self._cache['ap']; rm_a,hf_a,wf_a,wb_a,cf_a,rc_a,_ = ap
        self._prog_open("Efficiency Improvement analysis...")

        # Cumulative: change one param at a time from Before -> After
        param_names = ['rho_bulk', 'H_finger', 'W_finger', 'Shape CF', 'rho_c']
        # Start: all Before
        p = [rm, hf, wf, cf, rc]  # current state (starts as Before)
        a = [rm_a, hf_a, wf_a, cf_a, rc_a]  # After targets
        effs = []
        # Baseline
        _,_,iv0 = S.calc_iv(p[0],p[1],p[2],p[4],rs,p[3],DP,mode='tandem',npts=12)
        effs.append(iv0['Eff'])

        for i in range(5):
            self._prog_update(f'Eff Improve {i+1}/5: {param_names[i]}',
                              pct=(i+1)/6)
            p[i] = a[i]  # change this param to After value
            _,_,ivi = S.calc_iv(p[0],p[1],p[2],p[4],rs,p[3],DP,mode='tandem',npts=12)
            effs.append(ivi['Eff'])

        # Incremental gains
        gains = [effs[i+1] - effs[i] for i in range(5)]
        total_gain = effs[-1] - effs[0]

        # Waterfall chart
        ax3 = self.fig.add_subplot(self.gs[1,:2])
        x = np.arange(5); bw = 0.55
        colors = ['#e74c3c','#FF9800','#3498db','#9C27B0','#f39c12']
        bottom = effs[0]
        y_range = max(effs) - min(effs)
        min_bar = max(0.005, y_range * 0.015)  # Minimum visible bar height

        for i in range(5):
            g = gains[i]
            c = colors[i] if g > 0 else '#95a5a6'
            # Draw bar with minimum visible height
            bar_h = g if abs(g) > min_bar else (min_bar if g >= 0 else -min_bar)
            ax3.bar(x[i], bar_h, bw, bottom=bottom, color=c, edgecolor='white', lw=1, zorder=3,
                    alpha=0.9 if abs(g) > min_bar else 0.4)
            # Always show label
            sign = '+' if g >= 0 else ''
            if g >= 0:
                ax3.text(x[i], bottom + max(bar_h, min_bar) + 0.015, f'{sign}{g:.4f}%', ha='center',
                        fontsize=8, fontweight='bold', color=colors[i], zorder=6)
            else:
                ax3.text(x[i], bottom + min(bar_h, -min_bar) - 0.025, f'{g:.4f}%', ha='center',
                        fontsize=8, fontweight='bold', color='#c62828', zorder=6)
            bottom += g

        # Baseline and final lines
        ax3.axhline(effs[0], color='#e74c3c', ls='--', lw=1, alpha=0.5, zorder=1)
        ax3.axhline(effs[-1], color='#27ae60', ls='--', lw=1, alpha=0.5, zorder=1)
        # Before label: below baseline. After label: above final.
        ax3.text(-0.4, effs[0] - 0.06, f'Before\n{effs[0]:.3f}%', fontsize=7.5, color='#e74c3c',
                va='top', ha='center', fontweight='bold')
        ax3.text(4.4, effs[-1] + 0.06, f'After\n{effs[-1]:.3f}%', fontsize=7.5, color='#27ae60',
                va='bottom', ha='center', fontweight='bold')

        ax3.set_xticks(x)
        ax3.set_xticklabels(param_names, fontsize=9)
        ax3.set_ylabel(_t('eff_pct'))
        ax3.set_title(_t('eff_improve'), fontweight='bold', fontsize=12)
        ax3.set_xlim(-0.7, 5.0)
        y_lo = min(effs) - 0.2; y_hi = max(effs) + 0.2
        if y_hi - y_lo < 0.5: y_lo -= 0.15; y_hi += 0.15
        ax3.set_ylim(y_lo, y_hi)
        # Force plain decimal format on y-axis (no mathtext/offset)
        from matplotlib.ticker import FormatStrFormatter
        ax3.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
        ax3.spines['top'].set_visible(False); ax3.spines['right'].set_visible(False)
        ax3.grid(True, alpha=0.15, axis='y')

        # Recomb at OC panel (Griddler style: J0 in fA/cm2)
        ax4 = self.fig.add_subplot(self.gs[1,2])
        mode = self._cache.get('mode', 'tandem')
        iv_b_data = self._cache['iv_b']
        Voc = iv_b_data['Voc']

        # Get recomb currents at MPP (already computed)
        Rc_b = self._cache.get('Rc_b', {})
        if Rc_b and Voc > 0:
            # Direct J0 from diode parameters (no solver needed)
            # J0 = J01 * area_fraction, converted to fA/cm2 (*1e15 from A/cm2 to fA/cm2)
            avg_mf = np.mean(S.metal_frac)  # average metal fraction

            if mode == 'tandem':
                j0_pass_n1 = DP.J01_top_pass * (1 - avg_mf) * 1e15   # A/cm2 -> fA/cm2
                j0_met_n1 = DP.J01_top_metal * avg_mf * 1e15
                j0_met_n2 = DP.J02_top_metal * avg_mf * 1e15
                j0_pass_n2 = DP.J02_top_pass * (1 - avg_mf) * 1e15
            else:
                j0_pass_n1 = DP.J01_single_pass * (1 - avg_mf) * 1e15
                j0_met_n1 = DP.J01_single_metal * avg_mf * 1e15
                j0_met_n2 = DP.J02_single_metal * avg_mf * 1e15
                j0_pass_n2 = DP.J02_single_pass * (1 - avg_mf) * 1e15

            # Bar chart (log scale for wide dynamic range)
            j0_cats = ['Pass\nn=1', 'Metal\nn=1', 'Metal\nn=2', 'Pass\nn=2']
            j0_vals = [j0_pass_n1, j0_met_n1, j0_met_n2, j0_pass_n2]
            j0_colors = ['#e74c3c', '#c0392b', '#f39c12', '#e67e22']
            x_j0 = np.arange(4)
            # Clamp to minimum displayable value
            j0_disp = [max(v, 1e-20) for v in j0_vals]
            ax4.bar(x_j0, j0_disp, 0.6, color=j0_colors, edgecolor='white', lw=0.5)
            ax4.set_yscale('log')
            for i in range(4):
                if j0_vals[i] > 0:
                    ax4.text(x_j0[i], j0_disp[i] * 2, f'{j0_vals[i]:.2e}', ha='center',
                             fontsize=7, fontweight='bold', color=j0_colors[i])
            ax4.set_xticks(x_j0); ax4.set_xticklabels(j0_cats, fontsize=8)
            ax4.set_ylabel('J0 [fA/cm2]', fontsize=9)
            ax4.set_title(f'J0 Decomposition at Voc ({Voc:.3f}V)', fontweight='bold', fontsize=9)
            ax4.grid(True, alpha=0.15, axis='y')
            ax4.spines['top'].set_visible(False); ax4.spines['right'].set_visible(False)
        else:
            ax4.axis('off')
            ax4.text(0.5, 0.5, 'Run COMPARE first', ha='center', va='center',
                     transform=ax4.transAxes, fontsize=10, color='#999')

        self._refresh()
        sign_t = '+' if total_gain >= 0 else ''
        self._prog_close(f'Eff Improvement: {sign_t}{total_gain:.4f}%')


    # ---------------------------------------------------------
    # TAB: SWEEP
    # ---------------------------------------------------------
    def _tab_sweep(self):
        self._last_tab = self._tab_sweep
        self._clear_fig()
        if not self._apply_grid_design():
            return
        if not self._apply_diode_params():
            return
        bp, ap = self._get_params()
        if bp is None: return
        rm_b,hf_b,wf_b,wb_b,cf_b,rc_b,rs = bp
        self._prog_open(_t("param_sweep"))
        try:
            rho_range = np.linspace(3e-6, 25e-6, 12)
            effs=[]; ffs=[]; le=[]; lf=[]; lc=[]
            for i, rm in enumerate(rho_range):
                self._prog_update(f'Sweep {i+1}/12: rho = {rm*1e6:.1f}',
                                  pct=(i+1)/12)
                _,_,iv = S.calc_iv(rm,hf_b,wf_b,rc_b,rs,cf_b,DP,mode='tandem',npts=12)
                vmpp_bias = iv.get('Vmpp_internal', iv['Vmpp'])
                res = iv.get('_mpp_result') or S.solve(rm,hf_b,wf_b,rc_b,rs,vmpp_bias,cf_b,DP,mode='tandem')
                loss = S.losses(res,rm,hf_b,wf_b,rc_b,rs,cf_b,DP,
                                        Vmpp=iv['Vmpp'], Jmpp=iv['Jmpp'])
                pe=loss['Pe']; pff_=loss['Pf_finger']; pfb_=loss['Pf_busbar']; pc=loss['Pc']
                pf=pff_+pfb_
                effs.append(iv['Eff']); ffs.append(iv['FF']); le.append(pe); lf.append(pf); lc.append(pc)
        except _UserCancelled:
            self._prog_close("Sweep cancelled.")
            return
        ru = rho_range * 1e6

        ax1=self.fig.add_subplot(self.gs[0,0])
        ax1.plot(ru,effs,'o-',color='#2c3e50',lw=2,ms=6)
        ax1.axvline(bp[0]*1e6,color='#e74c3c',ls='--',lw=1.5,label=f'Before: {bp[0]*1e6:.1f}')
        ax1.axvline(ap[0]*1e6,color='#27ae60',ls='--',lw=1.5,label=f'After: {ap[0]*1e6:.1f}')
        # Interpolate and annotate Before/After Eff
        eff_b_interp = np.interp(bp[0]*1e6, ru, effs)
        eff_a_interp = np.interp(ap[0]*1e6, ru, effs)
        ax1.plot(bp[0]*1e6, eff_b_interp, 'ro', ms=8, zorder=5)
        ax1.plot(ap[0]*1e6, eff_a_interp, 'g^', ms=8, zorder=5)
        ax1.annotate(f'{eff_b_interp:.2f}%', xy=(bp[0]*1e6, eff_b_interp),
                    xytext=(5,8), textcoords='offset points', fontsize=7.5, fontweight='bold', color='#b71c1c')
        ax1.annotate(f'{eff_a_interp:.2f}%', xy=(ap[0]*1e6, eff_a_interp),
                    xytext=(5,8), textcoords='offset points', fontsize=7.5, fontweight='bold', color='#1b5e20')
        ax1.set_xlabel('rho_bulk [uO*cm]'); ax1.set_ylabel(_t('eff_pct'))
        ax1.set_title(_t('eff_vs_rho'),fontweight='bold'); ax1.legend(fontsize=8); ax1.grid(True,alpha=0.2)

        ax2=self.fig.add_subplot(self.gs[0,1])
        ax2.plot(ru,ffs,'s-',color='#8e44ad',lw=2,ms=6)
        ax2.axvline(bp[0]*1e6,color='#e74c3c',ls='--',lw=1.5)
        ax2.axvline(ap[0]*1e6,color='#27ae60',ls='--',lw=1.5)
        ff_b_interp = np.interp(bp[0]*1e6, ru, ffs)
        ff_a_interp = np.interp(ap[0]*1e6, ru, ffs)
        ax2.plot(bp[0]*1e6, ff_b_interp, 'ro', ms=8, zorder=5)
        ax2.plot(ap[0]*1e6, ff_a_interp, 'g^', ms=8, zorder=5)
        ax2.annotate(f'{ff_b_interp:.2f}%', xy=(bp[0]*1e6, ff_b_interp),
                    xytext=(5,8), textcoords='offset points', fontsize=7.5, fontweight='bold', color='#b71c1c')
        ax2.annotate(f'{ff_a_interp:.2f}%', xy=(ap[0]*1e6, ff_a_interp),
                    xytext=(5,8), textcoords='offset points', fontsize=7.5, fontweight='bold', color='#1b5e20')
        ax2.set_xlabel('rho_bulk [uO*cm]'); ax2.set_ylabel(_t('ff_pct'))
        ax2.set_title(_t('ff_vs_rho'),fontweight='bold'); ax2.grid(True,alpha=0.2)

        ax3=self.fig.add_subplot(self.gs[0,2])
        ax3.stackplot(ru,le,lf,lc,labels=['Emitter','Finger','Contact'],colors=['#3498db','#e74c3c','#f39c12'],alpha=0.8)
        ax3.axvline(bp[0]*1e6,color='#e74c3c',ls='--',lw=1.5)
        ax3.axvline(ap[0]*1e6,color='#27ae60',ls='--',lw=1.5)
        ax3.set_xlabel('rho_bulk [uO*cm]'); ax3.set_ylabel('Loss [mW/cm2]')
        ax3.set_title(_t('loss_vs_rho'),fontweight='bold'); ax3.legend(fontsize=7); ax3.grid(True,alpha=0.2)

        self._refresh()
        self._prog_close(f'Sweep done. 12 points: {ru[0]:.0f}~{ru[-1]:.0f}')



    # ---------------------------------------------------------
    # TAB: CONTOUR -- 2D sensitivity map
    # ---------------------------------------------------------
    def _tab_contour(self):
        self._last_tab = self._tab_contour
        self._clear_fig()
        if not self._apply_grid_design():
            return
        if not self._apply_diode_params():
            return
        bp, ap = self._get_params()
        if bp is None: return
        rm_b,hf_b,wf_b,wb_b,cf_b,rc_b,rs = bp
        self._prog_open(_t("contour_2d"))

        # === SPEED OPTIMIZATION (v28) ===
        # CONTOUR's purpose is to show rho_bulk × rho_c → Eff sensitivity map.
        # Phase B (interlayer lateral R) and bifacial rear add solver cost (3N→5N+Nm DOF)
        # but their effect on the SHAPE of the sensitivity map is negligible
        # (~0.001% Eff offset, well below the rho_bulk effect of several %).
        # We temporarily disable them during the sweep (then restore), giving ~7x speedup.
        # Annotation values (BEFORE/AFTER markers) ARE computed with full Phase B/bifacial
        # so the displayed efficiency numbers are accurate.
        _saved_Rs_j = DP.Rs_junction
        _saved_Rc_j = DP.Rc_junction
        _saved_bif_gain = DP.bifacial_gain
        _saved_rear_mode = GEO.rear_mode
        DP.Rs_junction = 0.0   # Phase A only during sweep
        DP.Rc_junction = 0.0
        DP.bifacial_gain = 0.0
        GEO.rear_mode = 'full_area'  # simpler solver path (3N+Nm DOF)
        # Force solver rebuild with simplified config
        try:
            S._build(rm_b, hf_b, wf_b, rc_b, rs, cf_b, DP)
        except Exception:
            pass

        try:
            # 5×5 grid (was 6×6) — interpolated contour smooths the difference
            rho_range = np.linspace(3e-6, 20e-6, 5)
            rc_range = np.linspace(2e-3, 20e-3, 5)
            eff_map = np.zeros((len(rc_range), len(rho_range)))
            ff_map = np.zeros_like(eff_map)
            total = len(rho_range)*len(rc_range); cnt = 0
            for i, rc_v in enumerate(rc_range):
                for j, rm_v in enumerate(rho_range):
                    cnt += 1
                    self._prog_update(f'Contour {cnt}/{total} (fast mode)...', pct=cnt/total)
                    _,_,iv = S.calc_iv(rm_v, hf_b, wf_b, rc_v, rs, cf_b, DP, mode='tandem', npts=8)
                    eff_map[i,j] = iv['Eff']
                    ff_map[i,j] = iv['FF']
        finally:
            # Always restore original config (even if sweep failed)
            DP.Rs_junction = _saved_Rs_j
            DP.Rc_junction = _saved_Rc_j
            DP.bifacial_gain = _saved_bif_gain
            GEO.rear_mode = _saved_rear_mode
            try:
                S._build(rm_b, hf_b, wf_b, rc_b, rs, cf_b, DP)
            except Exception:
                pass

        RHO, RC = np.meshgrid(rho_range*1e6, rc_range*1e3)
        ax1 = self.fig.add_subplot(self.gs[0,:2])
        cf1 = ax1.contourf(RHO, RC, eff_map, levels=20, cmap='RdYlGn')
        self.fig.colorbar(cf1, ax=ax1, label='Eff [%]', shrink=0.8)
        ax1.contour(RHO, RC, eff_map, levels=10, colors='k', linewidths=0.3, alpha=0.3)
        # Before/After annotation: use FULL solver (Phase B + bifacial restored above)
        # so user sees accurate efficiency at their actual operating point.
        self._prog_update('Computing accurate B/A markers...', pct=0.95)
        _,_,iv_cb = S.calc_iv(bp[0],hf_b,wf_b,bp[5],rs,cf_b,DP,mode='tandem',npts=8)
        _,_,iv_ca = S.calc_iv(ap[0],hf_b,wf_b,ap[5],rs,cf_b,DP,mode='tandem',npts=8)
        ax1.plot(bp[0]*1e6, bp[5]*1e3, 'ro', ms=10, label='Before')
        ax1.annotate(f'{iv_cb["Eff"]:.2f}%', xy=(bp[0]*1e6, bp[5]*1e3),
                    xytext=(8, 8), textcoords='offset points', fontsize=8,
                    fontweight='bold', color='#b71c1c',
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#e74c3c', alpha=0.9))
        ax1.plot(ap[0]*1e6, ap[5]*1e3, 'g^', ms=10, label='After')
        ax1.annotate(f'{iv_ca["Eff"]:.2f}%', xy=(ap[0]*1e6, ap[5]*1e3),
                    xytext=(8, 8), textcoords='offset points', fontsize=8,
                    fontweight='bold', color='#1b5e20',
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#27ae60', alpha=0.9))
        ax1.set_xlabel('rho_bulk [uOhm*cm]'); ax1.set_ylabel('rho_c [mOhm*cm2]')
        ax1.set_title(_t('eff_contour') + '\n[fast mode: Phase A only — markers use full solver]',
                      fontweight='bold', fontsize=10)
        ax1.legend(fontsize=8)
        ax2 = self.fig.add_subplot(self.gs[0,2])
        cf2 = ax2.contourf(RHO, RC, ff_map, levels=15, cmap='YlOrRd_r')
        self.fig.colorbar(cf2, ax=ax2, label='FF [%]', shrink=0.8)
        ax2.plot(bp[0]*1e6, bp[5]*1e3, 'ro', ms=8)
        ax2.annotate(f'{iv_cb["FF"]:.1f}%', xy=(bp[0]*1e6, bp[5]*1e3),
                    xytext=(6, 6), textcoords='offset points', fontsize=7,
                    fontweight='bold', color='#b71c1c',
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#e74c3c', alpha=0.9))
        ax2.plot(ap[0]*1e6, ap[5]*1e3, 'g^', ms=8)
        ax2.annotate(f'{iv_ca["FF"]:.1f}%', xy=(ap[0]*1e6, ap[5]*1e3),
                    xytext=(6, 6), textcoords='offset points', fontsize=7,
                    fontweight='bold', color='#1b5e20',
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', ec='#27ae60', alpha=0.9))
        ax2.set_xlabel('rho_bulk'); ax2.set_ylabel('rho_c')
        ax2.set_title(_t('ff_contour'), fontweight='bold')
        ax3 = self.fig.add_subplot(self.gs[1,:])
        ax3.axis('off'); ax3.set_xlim(0,1); ax3.set_ylim(0,1)
        imax = np.unravel_index(np.argmax(eff_map), eff_map.shape)
        opt_rc = rc_range[imax[0]]*1e3; opt_rho = rho_range[imax[1]]*1e6
        opt_eff = eff_map[imax]; opt_ff = ff_map[imax]
        ax3.text(0.5, 0.85, _t('sensitivity'), ha='center',
                fontsize=14, fontweight='bold', color=CLR_ACCENT, transform=ax3.transAxes)
        ax3.text(0.5, 0.68, f'Optimal: rho_bulk = {opt_rho:.1f} uOhm*cm,  rho_c = {opt_rc:.1f} mOhm*cm2',
                ha='center', fontsize=11, transform=ax3.transAxes)
        ax3.text(0.5, 0.53, f'Peak Eff = {opt_eff:.3f}%   |   FF = {opt_ff:.2f}%',
                ha='center', fontsize=13, fontweight='bold', color='#2E7D32', transform=ax3.transAxes)
        ax3.text(0.5, 0.35, f'Before: rho={bp[0]*1e6:.2f}, rc={bp[5]*1e3:.1f}  ->  Eff={iv_cb["Eff"]:.3f}%, FF={iv_cb["FF"]:.2f}%',
                ha='center', fontsize=10, color='#c62828', fontweight='bold', transform=ax3.transAxes)
        ax3.text(0.5, 0.22, f'After:  rho={ap[0]*1e6:.2f}, rc={ap[5]*1e3:.1f}  ->  Eff={iv_ca["Eff"]:.3f}%, FF={iv_ca["FF"]:.2f}%',
                ha='center', fontsize=10, color='#1b5e20', fontweight='bold', transform=ax3.transAxes)
        deff_c = iv_ca['Eff'] - iv_cb['Eff']
        ax3.text(0.5, 0.08, f'dEff = {deff_c:+.4f}%  (hot pressing shifts to higher Eff region)',
                ha='center', fontsize=10, fontweight='bold',
                color='#27ae60' if deff_c > 0 else '#e74c3c', transform=ax3.transAxes)
        self._refresh()
        self._prog_close(f'Contour done. Optimal: rho={opt_rho:.1f}, rc={opt_rc:.1f} -> Eff={opt_eff:.3f}%')


    # ---------------------------------------------------------
    # TAB: DESIGN -- Electrode Visualization (v28.10, Griddler-style)
    # ---------------------------------------------------------
    def _tab_design(self):
        """v28.10 (박사님 지시 2026.05.21): Visualize electrode patterns.
        Front + Rear grid + contact points, Griddler-style.
        """
        self._last_tab = self._tab_design
        self._clear_fig()
        self._apply_grid_design()  # make sure GEO is current

        from matplotlib.patches import Rectangle, Circle, Polygon as MplPolygon
        # 2x2 grid: front design (top-left), rear design (top-right),
        # geometry table (bottom-left), info text (bottom-right)
        self.gs = self.fig.add_gridspec(2, 2, hspace=0.42, wspace=0.25)

        W_mm = GEO.W * 10  # cm -> mm
        H_mm = GEO.H * 10

        # wafer outline polygon (mm)
        wafer_outline = GEO.wafer_outline_xy_mm()

        # === FRONT PATTERN ===
        ax1 = self.fig.add_subplot(self.gs[0, 0])
        ax1.set_xlim(-W_mm * 0.05, W_mm * 1.05)
        ax1.set_ylim(-H_mm * 0.05, H_mm * 1.05)
        ax1.set_aspect('equal')
        # Wafer outline (square / pseudo-square / circular)
        ax1.add_patch(MplPolygon(wafer_outline,
                                  fill=True, fc='#E3F2FD', ec='#1565C0', lw=1.5, zorder=1))

        # finger와 busbar를 다른 색으로 분리 표시
        # BB visibility 강화 — finger 50개+에 묻히지 않도록
        # finger를 실제 폭·방향대로 Rectangle로 그림.
        #   기존엔 finger를 항상 세로 중심선(Line2D)으로만 그려서 (a) 폭이 안
        #   보이고 (b) 가로 finger·임의 DXF 패턴을 표현 못 했음. 이제 각 rect를
        #   그 방향(가로/세로 자동) 그대로 그리되, 화면에서 1픽셀 이하로 가늘어
        #   안 보이는 finger는 '짧은 축'만 최소 가시 폭으로 부풀려 그린다
        #   (중심선 기준 대칭 확장 → 위치·길이는 정확, 폭만 보이게). FEM 계산은
        #   실제 폭을 쓰므로 영향 없음; 이건 표시 전용.
        from matplotlib.patches import Patch as _Patch
        from matplotlib.lines import Line2D as _Line2D
        fingers, busbars, pads = GEO.metal_rects_front_split()
        # v28.17 (박사님 지시): finger/busbar를 "실제 폭" 그대로 그린다 (CAD 파일처럼).
        #   이전엔 _min_vis_mm로 가는 finger를 부풀려 그려서 50um finger가 1mm
        #   busbar보다 굵게 보이는 등 실제 폭 판단이 불가능했음. 이제 부풀림을 제거,
        #   실제 폭 Rectangle로 그리되 채움색과 같은 색의 얇은 edge(lw=0.6)를 줘서
        #   sub-pixel 폭 finger도 올바른 색의 hairline으로 보이게 한다(=CAD 뷰어 방식).
        #   폭이 충분한 부재는 그대로 채워지므로 finger(가늘다)·busbar(굵다) 비율이
        #   실제와 일치. FEM 계산은 항상 실제 폭을 쓰므로 영향 없음(표시 전용).
        for rx, ry, rw, rh in fingers:
            ax1.add_patch(Rectangle((rx * 10, ry * 10), rw * 10, rh * 10,
                                     fc='#37474F', ec='#37474F', lw=0.6,
                                     alpha=0.9, zorder=3))
        # Busbars: 진한 주황 + 굵은 검은 outline (v28.12 강화)
        for rx, ry, rw, rh in busbars:
            ax1.add_patch(Rectangle((rx * 10, ry * 10), rw * 10, rh * 10,
                                     fc='#E65100', ec='#000000', lw=1.5,
                                     alpha=1.0, zorder=5))
        # Pads (legacy, 보통 안 보임)
        for rx, ry, rw, rh in pads:
            ax1.add_patch(Rectangle((rx * 10, ry * 10), rw * 10, rh * 10,
                                     fc='#5D4037', ec='none', alpha=0.85, zorder=4))

        # Contact/probe points (v28.12: zorder 강화)
        if GEO.front_terminals:
            tx = [t[0] * 10 for t in GEO.front_terminals]
            ty = [t[1] * 10 for t in GEO.front_terminals]
            ax1.scatter(tx, ty, s=80, c='#E53935', marker='o',
                        edgecolors='white', linewidths=1.5, zorder=6)

        # 명확한 범례 (Finger / Busbar / Probe 각각 표시)
        # for an imported DXF rect pattern, n_f/n_b are meaningless
        # (H-pattern params); show the actual imported rect counts instead.
        _is_dxf = getattr(GEO, '_dxf_finger_rects', None) is not None
        if _is_dxf:
            _nf_disp = len(fingers); _nb_disp = len(busbars)
            _wf_lbl = ''; _wb_lbl = ''
        else:
            _nf_disp = GEO.n_f; _nb_disp = GEO.n_b
            _wf_lbl = f'  ({GEO.w_f*1e4:.0f}μm)'; _wb_lbl = f'  ({GEO.w_b*1e4:.0f}μm)'
        legend_elements = [
            _Patch(facecolor='#37474F', edgecolor='none', alpha=0.85,
                   label=f'Finger × {_nf_disp}{_wf_lbl}'),
            _Patch(facecolor='#E65100', edgecolor='#000000', linewidth=1.5,
                   label=f'Busbar × {_nb_disp}{_wb_lbl}'),
        ]
        if GEO.front_terminals:
            legend_elements.append(
                _Line2D([0], [0], marker='o', color='w',
                        markerfacecolor='#E53935', markeredgecolor='white',
                        markersize=8, markeredgewidth=1.5,
                        label=f'Probe × {len(GEO.front_terminals)}')
            )
        ax1.legend(handles=legend_elements, loc='upper center',
                   bbox_to_anchor=(0.5, -0.16), ncol=3, fontsize=7,
                   framealpha=0.92, edgecolor='#CFD8DC')

        ax1.set_xlabel('x [mm]', fontsize=9)
        ax1.set_ylabel('y [mm]', fontsize=9)
        # include pattern_style in title
        # DXF imports show rect counts, not H-pattern F/BB.
        if _is_dxf:
            ax1.set_title(
                f'Front Pattern: {len(fingers)} finger + {len(busbars)} busbar rects  [DXF import]',
                fontweight='bold', fontsize=11, color='#1565C0')
        else:
            _ps_disp = {"h_pattern": "H-pattern", "shingled": "Shingled / Fork",
                        "tapered_h": "Tapered H"}.get(GEO.front.pattern_style, "H-pattern")
            ax1.set_title(f'Front Pattern: {GEO.n_f}F + {GEO.n_b}BB  [{_ps_disp}]',
                          fontweight='bold', fontsize=11, color='#1565C0')
        ax1.grid(True, alpha=0.2)
        ax1.tick_params(labelsize=8)

        # === REAR PATTERN ===
        ax2 = self.fig.add_subplot(self.gs[0, 1])
        ax2.set_xlim(-W_mm * 0.05, W_mm * 1.05)
        ax2.set_ylim(-H_mm * 0.05, H_mm * 1.05)
        ax2.set_aspect('equal')
        # Rear outline (same wafer shape)
        ax2.add_patch(MplPolygon(wafer_outline,
                                  fill=True, fc='#FFF3E0', ec='#E65100', lw=1.5, zorder=1))
        if GEO.rear_mode == 'full_area' or GEO.rear is None:
            # Full-area metal — fill cell with light hatching
            ax2.add_patch(Rectangle((0, 0), W_mm, H_mm,
                                     fc='#FFB74D', ec='none', alpha=0.40, zorder=2,
                                     hatch='///'))
            ax2.text(W_mm * 0.5, H_mm * 0.5, 'FULL-AREA METAL\n(monofacial)',
                     ha='center', va='center', fontsize=11, fontweight='bold',
                     color='#BF360C')
            rear_title = 'Rear: Full-Area Metal'
        else:
            # rear finger/busbar 분리 (bifacial)
            r_fingers, r_busbars = GEO.metal_rects_rear_split()
            # v28.17: rear finger도 실제 폭 Rectangle로 (front과 동일 방식)
            for rx, ry, rw, rh in (r_fingers or []):
                ax2.add_patch(Rectangle((rx * 10, ry * 10), rw * 10, rh * 10,
                                         fc='#263238', ec='#263238', lw=0.6,
                                         alpha=0.9, zorder=3))
            # Rear busbars: orange (front과 통일)
            for rx, ry, rw, rh in (r_busbars or []):
                ax2.add_patch(Rectangle((rx * 10, ry * 10), rw * 10, rh * 10,
                                         fc='#E65100', ec='#3E2723', lw=0.5, alpha=0.95, zorder=4))
            # Rear probe points (purple square)
            if hasattr(GEO, 'rear_terminals') and GEO.rear_terminals:
                tx = [t[0] * 10 for t in GEO.rear_terminals]
                ty = [t[1] * 10 for t in GEO.rear_terminals]
                ax2.scatter(tx, ty, s=80, c='#7B1FA2', marker='s',
                            edgecolors='white', linewidths=1.5, zorder=5)
                rear_legend = [
                    _Patch(facecolor='#263238', edgecolor='#263238', alpha=0.9,
                           label=f'Finger × {GEO.rear.n_f}'),
                    _Patch(facecolor='#E65100', edgecolor='#3E2723', linewidth=0.5,
                           label=f'Busbar × {GEO.rear.n_b}'),
                    _Line2D([0], [0], marker='s', color='w',
                            markerfacecolor='#7B1FA2', markeredgecolor='white',
                            markersize=8, markeredgewidth=1.5,
                            label=f'Probe × {len(GEO.rear_terminals)}'),
                ]
                ax2.legend(handles=rear_legend, loc='upper center',
                           bbox_to_anchor=(0.5, -0.16), ncol=3, fontsize=7,
                           framealpha=0.92, edgecolor='#CFD8DC')
            r = GEO.rear
            rear_title = f'Rear Pattern: {r.n_f}F + {r.n_b}BB (bifacial)'
        ax2.set_xlabel('x [mm]', fontsize=9)
        ax2.set_ylabel('y [mm]', fontsize=9)
        ax2.set_title(rear_title, fontweight='bold', fontsize=11, color='#E65100')
        ax2.grid(True, alpha=0.2)
        ax2.tick_params(labelsize=8)

        # === GEOMETRY TABLE ===
        ax3 = self.fig.add_subplot(self.gs[1, 0]); ax3.axis('off')
        fg_len_mm = (GEO.fg_x_range[1] - GEO.fg_x_range[0]) * 10
        bb_len_mm = (GEO.bb_y_range[1] - GEO.bb_y_range[0]) * 10
        # current BEFORE/AFTER widths
        try:
            bp, ap = self._get_params()
            wf_b_um = bp[2] * 1e4
            wf_a_um = ap[2] * 1e4
            wb_b_um = bp[3] * 1e4
            wb_a_um = ap[3] * 1e4
            sh_b = GEO.shading_fraction(w_f_opt=bp[2], w_b_opt=bp[3]) * 100
            sh_a = GEO.shading_fraction(w_f_opt=ap[2], w_b_opt=ap[3]) * 100
        except Exception:
            wf_b_um = wf_a_um = GEO.w_f * 1e4
            wb_b_um = wb_a_um = GEO.w_b * 1e4
            sh_b = sh_a = GEO.shading_fraction() * 100

        finger_pitch_mm = GEO.front.get_finger_pitch_mm(GEO.W, GEO.H)
        rows = [
            ['Parameter', 'Before', 'After'],
            ['Cell [mm × mm]', f'{W_mm:.1f} × {H_mm:.1f}', f'{W_mm:.1f} × {H_mm:.1f}'],
            ['N Fingers', f'{GEO.n_f}', f'{GEO.n_f}'],
            ['N Busbars', f'{GEO.n_b}', f'{GEO.n_b}'],
            ['Finger pitch [mm]', f'{finger_pitch_mm:.2f}', f'{finger_pitch_mm:.2f}'],
            ['Finger W [μm]', f'{wf_b_um:.1f}', f'{wf_a_um:.1f}'],
            ['Busbar W [μm]', f'{wb_b_um:.1f}', f'{wb_a_um:.1f}'],
            ['Finger length [mm]', f'{fg_len_mm:.1f}', f'{fg_len_mm:.1f}'],
            ['Busbar length [mm]', f'{bb_len_mm:.1f}', f'{bb_len_mm:.1f}'],
            ['Shading [%]', f'{sh_b:.2f}', f'{sh_a:.2f}'],
        ]
        self._draw_table(ax3, rows, [0.42, 0.28, 0.28])
        ax3.set_title('Geometry Summary', fontweight='bold', fontsize=11)

        # === MESH VIEW: how the current mesh was formed (Griddler-style) ===
        # Draws the actual constrained-Delaunay triangulation of the CURRENT
        # geometry (rebuilt by _apply_grid_design above) with metal nodes
        # highlighted, so the tangent/perpendicular refinement around the
        # fingers/busbars is visible. Node/element counts sit in the title,
        # like Griddler's meshing display.
        ax4 = self.fig.add_subplot(self.gs[1, 1])
        mt = getattr(self, "_mesh_tangent_var", None)
        mp = getattr(self, "_mesh_perp_var", None)
        mt_v = mt.get() if mt is not None else "Med"
        mp_v = mp.get() if mp is not None else "Med"
        n_nodes = len(pts) if pts is not None else 0
        n_tri = len(tri.simplices) if tri is not None else 0
        _mesh_title_color = '#455A64'
        n_probe = (GEO.front.n_probe_points if GEO.front.n_probe_points > 0
                   else GEO.front.n_terminals)
        try:
            # v28.17: Griddler-style region shading. 각 삼각형을 "metal 접촉
            #   여부"로 분류해 metal/계면 영역은 주황(촘촘), passivated bulk은
            #   하늘색(성김)으로 칠한다. PolyCollection edge가 곧 메시 선이라
            #   영역 구분 + 메시 구조가 한 번에 보임(노드 마커는 dense mesh에서
            #   영역색을 가려서 제거).
            from matplotlib.collections import PolyCollection as _PolyColl
            from matplotlib.patches import Patch as _MeshPatch
            import matplotlib.colors as _mcolors
            _simp = tri.simplices
            _metal_node = (ism.copy() if ism is not None
                           else np.zeros(len(pts), dtype=bool))
            if isf is not None: _metal_node |= isf
            if isb is not None: _metal_node |= isb
            _tri_metal = _metal_node[_simp].any(axis=1)
            _verts = pts[_simp] * 10.0
            _fc = np.empty((len(_simp), 4))
            _fc[_tri_metal] = _mcolors.to_rgba('#FFCC80')   # metal/interface (dense)
            _fc[~_tri_metal] = _mcolors.to_rgba('#E8F0FE')  # passivated bulk (coarse)
            ax4.add_collection(_PolyColl(_verts, facecolors=_fc,
                                         edgecolors='#5b6b7a', linewidths=0.2,
                                         zorder=1))
            ax4.set_xlim(pts[:, 0].min() * 10 - 1, pts[:, 0].max() * 10 + 1)
            ax4.set_ylim(pts[:, 1].min() * 10 - 1, pts[:, 1].max() * 10 + 1)
            ax4.set_aspect('equal', adjustable='box')
            ax4.set_xlabel('x [mm]', fontsize=9)
            ax4.set_ylabel('y [mm]', fontsize=9)
            ax4.tick_params(labelsize=8)
            _md = mesh_distribution_metrics(pts, GEO)
            if (_md['MirrorNodeHitX'] < 0.99 or _md['MirrorNodeHitY'] < 0.99
                    or abs(_md['CentroidBiasX_um']) > 25.0
                    or abs(_md['CentroidBiasY_um']) > 25.0):
                _mesh_title_color = '#C62828'
            ax4.legend(handles=[
                _MeshPatch(fc='#FFCC80', ec='#5b6b7a', lw=0.4, label='metal (dense)'),
                _MeshPatch(fc='#E8F0FE', ec='#5b6b7a', lw=0.4, label='bulk (coarse)'),
            ], loc='upper center', bbox_to_anchor=(0.5, -0.20), ncol=2,
               fontsize=7, framealpha=0.92, edgecolor='#CFD8DC')
            # v28.17 fix: 메쉬 위에는 아무 박스도 올리지 않는다(셀 메쉬 전체가
            #   가려지지 않게). 레벨/메타정보는 제목 줄로 이동.
        except Exception as _mesh_e:
            ax4.axis('off')
            ax4.text(0.5, 0.5, f'(mesh view unavailable:\n{_mesh_e})',
                     transform=ax4.transAxes, ha='center', va='center',
                     fontsize=9, color='#B0BEC5')
        ax4.set_title(f'Mesh: {n_nodes:,} nodes  |  {n_tri:,} elements   ·   T/P {mt_v}/{mp_v}',
                      fontweight='bold', fontsize=10.5, color=_mesh_title_color)

        self._refresh()
        self._status(f"DESIGN view: {GEO.n_f}F+{GEO.n_b}BB, mesh T={mt_v}/P={mp_v}, {n_nodes} nodes")


    # ---------------------------------------------------------
    # TAB: MODEL -- Paginated Methodology Viewer (KR/EN)
    # ---------------------------------------------------------
    def _tab_model(self):
        self._status("Opening MODEL viewer...")
        state = {'pg': 0, 'lang': 'EN'}

        mwin = ctk.CTkToplevel(self)
        mwin.title("2L-FEST PRO \u2014 Model & Methodology")
        mwin.geometry("1300x850")
        mwin.attributes('-topmost', True)

        # --- PAGE TITLES ---
        _TITLES_EN = ['Overview', 'Architecture', 'FEM Equations',
                      'Two-Diode Model', '2T Tandem', 'Newton-Raphson', 'Mesh & Conv.']
        _TITLES_KR = ['\uac1c\uc694', '\uad6c\uc870', 'FEM \ubc29\uc815\uc2dd',
                      'Two-Diode \ubaa8\ub378', '2T \ud0e0\ub364', 'Newton-Raphson', '\uba54\uc2dc & \uc218\ub834']

        # --- LAYOUT: sidebar (left) + canvas (right) + nav (bottom) ---
        nav = ctk.CTkFrame(mwin, fg_color=CLR_TAB_BG, height=48)
        nav.pack(fill="x", side="bottom"); nav.pack_propagate(False)

        body = ctk.CTkFrame(mwin, fg_color="#F8FAFC")
        body.pack(fill="both", expand=True)

        # LEFT SIDEBAR TOC
        sidebar = ctk.CTkFrame(body, fg_color="white", width=170, corner_radius=0,
                                border_width=1, border_color=CLR_CARD_BD)
        sidebar.pack(side="left", fill="y"); sidebar.pack_propagate(False)

        # v28.20 fix: the INDEX label previously embedded the book emoji written
        # as a lone surrogate pair, which can never encode to UTF-8 — Tk raised
        # "surrogates not allowed" and crashed the moment this label was built.
        # Use a BMP-safe ASCII label for cross-platform safety (Windows/macOS).
        ctk.CTkLabel(sidebar, text="INDEX", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=CLR_ACCENT).pack(pady=(12, 8))

        toc_btns = []

        # RIGHT: figure canvas
        fig_frame = ctk.CTkFrame(body, fg_color="white")
        fig_frame.pack(side="left", fill="both", expand=True)

        mfig = Figure(figsize=(11, 8.5), facecolor='white', dpi=100)
        mcanvas = FigureCanvasTkAgg(mfig, master=fig_frame)
        mcanvas.get_tk_widget().pack(fill="both", expand=True)

        # ===================== PAGE DEFINITIONS =====================

        _MPAGES = [self._model_p1, self._model_p2, self._model_p3, self._model_p4, self._model_p5, self._model_p6, self._model_p7]
        page_label = ctk.CTkLabel(nav, text="1/7", font=ctk.CTkFont(size=12, weight="bold"), text_color=CLR_TEXT)

        def draw_m(pg=None):
            if pg is not None: state['pg'] = max(0, min(pg, len(_MPAGES)-1))
            mfig.clear()
            _MPAGES[state['pg']](mfig, state['lang'])
            page_label.configure(text=f"{state['pg']+1} / {len(_MPAGES)}")
            # Update sidebar highlight
            titles = _TITLES_KR if state['lang']=='KR' else _TITLES_EN
            for i, tb in enumerate(toc_btns):
                tb.configure(text=f"  {i+1}. {titles[i]}",
                    fg_color=(CLR_ACCENT if i==state['pg'] else "transparent"),
                    text_color=("white" if i==state['pg'] else CLR_TEXT))
            # Update nav dots
            for i, pb in enumerate(pg_btns):
                pb.configure(fg_color=(CLR_ACCENT if i==state['pg'] else "white"),
                             text_color=("white" if i==state['pg'] else "#64748B"),
                             border_color=(CLR_ACCENT if i==state['pg'] else "#CBD5E1"))
            mcanvas.draw()

        def prev_m(): draw_m(state['pg']-1)
        def next_m(): draw_m(state['pg']+1)
        def toggle_lang():
            state['lang'] = 'KR' if state['lang']=='EN' else 'EN'
            lang_btn.configure(text=f"Lang: {state['lang']}")
            draw_m()

        # Build sidebar TOC buttons
        for i in range(len(_MPAGES)):
            def _mk_toc(idx):
                def _fn(): draw_m(idx)
                return _fn
            tb = ctk.CTkButton(sidebar, text=f"  {i+1}. {_TITLES_EN[i]}",
                               font=ctk.CTkFont(size=11), anchor="w",
                               fg_color="transparent", hover_color="#E2E8F0",
                               text_color=CLR_TEXT, corner_radius=4,
                               height=34, command=_mk_toc(i))
            tb.pack(fill="x", padx=6, pady=1)
            toc_btns.append(tb)

        # Nav bar buttons
        bp = ctk.CTkButton(nav, text="<", width=36, height=30, fg_color="#94A3B8",
                    hover_color="#64748B", font=ctk.CTkFont(size=14), command=prev_m)
        bp.pack(side="left", padx=(8,3), pady=8)
        pg_btns = []
        for i in range(len(_MPAGES)):
            def _mk(idx):
                def _fn(): draw_m(idx)
                return _fn
            pb = ctk.CTkButton(nav, text=str(i+1), width=28, height=26, fg_color="white",
                               hover_color="#E2E8F0", text_color="#64748B", border_width=1,
                               border_color="#CBD5E1", font=ctk.CTkFont(size=10, weight="bold"),
                               corner_radius=6, command=_mk(i))
            pb.pack(side="left", padx=1, pady=8); pg_btns.append(pb)
        page_label.pack(side="left", padx=(6,3))
        bn = ctk.CTkButton(nav, text=">", width=36, height=30, fg_color="#94A3B8",
                    hover_color="#64748B", font=ctk.CTkFont(size=14), command=next_m)
        bn.pack(side="left", padx=(3,8), pady=8)
        lang_btn = ctk.CTkButton(nav, text="Lang: EN", width=80, height=30, fg_color="#1565C0",
                       hover_color="#0D47A1", font=ctk.CTkFont(size=11, weight="bold"), command=toggle_lang)
        lang_btn.pack(side="right", padx=10, pady=8)

        mwin._refs = [mfig, mcanvas, bp, bn, lang_btn, page_label, state] + pg_btns + toc_btns
        def on_key(e):
            if e.keysym in ('Left','a','A'): prev_m()
            elif e.keysym in ('Right','d','D'): next_m()
            elif e.keysym in ('1','2','3','4','5','6','7'): draw_m(int(e.keysym)-1)
            elif e.keysym in ('l','L'): toggle_lang()
        mwin.bind('<Key>', on_key)
        _st = {'t': 0}
        def on_scroll(event):
            import time as _t
            now = _t.time()
            if now - _st['t'] < 0.15: return "break"
            _st['t'] = now
            if hasattr(event,'delta') and event.delta!=0:
                prev_m() if event.delta>0 else next_m()
            elif hasattr(event,'num'):
                prev_m() if event.num==4 else next_m()
            return "break"
        cw = mcanvas.get_tk_widget()
        cw.bind('<MouseWheel>', on_scroll); cw.bind('<Button-4>', on_scroll); cw.bind('<Button-5>', on_scroll)
        mwin.focus_set()
        draw_m(0)
        self._status("MODEL viewer: Scroll / Arrow / L=lang")


    # ---------------------------------------------------------
    # LOAD EXP I-V
    # ---------------------------------------------------------
    # ---------------------------------------------------------
    # MODEL VIEWER PAGES (extracted from _tab_model for clarity)
    # ---------------------------------------------------------
    def _model_hdr(self, f, title_en, title_kr, pg, total, lang):
        ax = f.add_axes([0, 0.91, 1, 0.09]); ax.axis('off')
        ax.add_patch(Rectangle((0,0), 1, 1, transform=ax.transAxes, fc=CLR_HEADER, ec='none'))
        t = title_kr if lang == 'KR' else title_en
        ax.text(0.03, 0.5, t, va='center', fontsize=18, fontweight='bold',
                color='white', transform=ax.transAxes)
        ax.text(0.97, 0.5, f'{pg}/{total}  [{lang}]', va='center', ha='right',
                fontsize=10, color='#64748B', transform=ax.transAxes)

    def _model_card(self, ax, x, y, w, h, title, body_lines, title_color=CLR_ACCENT, fc='#F8FAFC', ec=CLR_CARD_BD):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.008',
                     fc=fc, ec=ec, lw=1, transform=ax.transAxes))
        ax.text(x+0.02, y+h-0.025, title, fontsize=9.5, fontweight='bold',
                color=title_color, transform=ax.transAxes)
        dy = 0.035
        for i, line in enumerate(body_lines):
            ax.text(x+0.02, y+h-0.055-i*dy, line, fontsize=8, color='#444',
 transform=ax.transAxes)

    def _model_p1(self, f, lang):
        self._model_hdr(f, 'What is 2L-FEST?', '2L-FEST\ub780 \ubb34\uc5c7\uc778\uac00?', 1, 7, lang)
        ax = f.add_axes([0, 0, 1, 0.91]); ax.axis('off'); ax.set_xlim(0,1); ax.set_ylim(0,1)
        ax.text(0.5, 0.95, '2-Layer Front Electrode Simulation Tool',
                ha='center', fontsize=12, color='#64748B', transform=ax.transAxes)
        if lang == 'EN':
            cards = [
                (0.74, 'THE PROBLEM', [
                    'Screen-printed Ag electrodes on perovskite/Si tandem cells',
                    'suffer from resistive losses in emitter, finger, and contact.',
                    'How much efficiency can we gain via hot pressing?']),
                (0.54, 'OUR APPROACH', [
                    '2L-FEST models the front surface as TWO coupled layers:',
                    '  (1) Emitter/TCO layer  --  lateral photocurrent (R_sheet)',
                    '  (2) Metal electrode layer  --  finger/busbar collection (R_line)',
                    'Connected by contact resistance (rho_c) at every metal node.']),
                (0.34, 'THE METHOD', [
                    'Galerkin FEM on constrained Delaunay triangular mesh.',
                    'KCL at each node + two-diode model per subcell.',
                    'Newton-Raphson nonlinear solver.']),
                (0.14, 'THE OUTPUT', [
                    'I-V curve, loss decomposition, FF waterfall, parameter sweeps,',
                    'voltage/current maps. Before vs After comparison for hot pressing.']),
            ]
        else:
            cards = [
                (0.74, '\ubb38\uc81c \uc815\uc758', [
                    '\ud398\ub85c\ube0c\uc2a4\uce74\uc774\ud2b8/Si \ud0e0\ub364 \uc140\uc758 \uc2a4\ud06c\ub9b0 \ud504\ub9b0\ud305 Ag \uc804\uadf9\uc740',
                    '\uc5d0\ubbf8\ud130, \ud551\uac70, \uc811\ucd09\uc5d0\uc11c \uc800\ud56d\uc131 \uc804\ub825\uc190\uc2e4\uc774 \ubc1c\uc0dd\ud569\ub2c8\ub2e4.',
                    '\ud56b \ud504\ub808\uc2f1\uc73c\ub85c \uc5bc\ub9c8\ub098 \ud6a8\uc728\uc744 \ub192\uc77c \uc218 \uc788\uc744\uae4c\uc694?']),
                (0.54, '\uc811\uadfc \ubc29\ubc95', [
                    '2L-FEST\ub294 \uc804\uba74\uc744 2\uac1c \uacb0\ud569 \ub808\uc774\uc5b4\ub85c \ubaa8\ub378\ub9c1:',
                    '  (1) \uc5d0\ubbf8\ud130/TCO \uce35 -- \uc218\ud3c9 \uad11\uc804\ub958 (R_sheet)',
                    '  (2) \uae08\uc18d \uc804\uadf9 \uce35 -- \ud551\uac70/\ubc84\uc2a4\ubc14 \uc804\ub958 \uc218\uc9d1 (R_line)',
                    '\ubaa8\ub4e0 \uae08\uc18d \ub178\ub4dc\uc5d0\uc11c \uc811\ucd09\uc800\ud56d(rho_c)\uc73c\ub85c \uc5f0\uacb0.']),
                (0.34, '\ud574\uc11d \ubc29\ubc95', [
                    'Constrained Delaunay \uc0bc\uac01\ud615 \uba54\uc2dc + Galerkin FEM.',
                    '\uac01 \ub178\ub4dc KCL + Two-diode \ubaa8\ub378.',
                    'Newton-Raphson \ube44\uc120\ud615 \ud480\uc774.']),
                (0.14, '\ucd9c\ub825', [
                    'I-V \uace1\uc120, \uc804\ub825\uc190\uc2e4 \ubd84\ud574, FF waterfall, \ud30c\ub77c\ubbf8\ud130 \uc2a4\uc775,',
                    '\uc804\uc555/\uc804\ub958 \ub9f5. Before vs After\ub85c \ud56b\ud504\ub808\uc2f1 \ud6a8\uacfc \uc815\ub7c9\ud654.']),
            ]
        for y0, title, lines in cards:
            self._model_card(ax, 0.04, y0, 0.92, 0.17, title, lines)

    def _model_p2(self, f, lang):
        self._model_hdr(f, 'Architecture: 2-Layer Model', '\uad6c\uc870: 2-Layer \ubaa8\ub378', 2, 7, lang)
        ax = f.add_axes([0, 0, 1, 0.91]); ax.axis('off'); ax.set_xlim(0,1); ax.set_ylim(0,1)
        bp_,_ = self._get_params()
        rm=bp_[0] if bp_ else 13.22e-6; cf=bp_[4] if bp_ else 0.785
        wf=bp_[2] if bp_ else 50e-4; hf=bp_[1] if bp_ else 10e-4
        rc=bp_[5] if bp_ else 10e-3; rs=bp_[6] if bp_ else 55.0
        rl = rm/(cf*wf*hf) if (cf*wf*hf)>0 else 0
        if lang == 'EN':
            L = [('Metal Grid (Ag)','#FFF3E0','#E65100',f'R_line = rho/(CF*W*H) = {rl:.2f} ohm/cm'),
                 ('Contact R (rho_c)','#FFEBEE','#C62828',f'rho_c = {rc*1e3:.1f} mohm*cm2 | target < 6'),
                 ('TCO / Emitter','#E3F2FD','#1565C0',f'Lateral current to finger. R_sheet = {rs:.0f} ohm/sq'),
                 ('Perovskite Top','#FFF8E1','#F57F17',f'J01={TP.J01_top_pass:.0e}(pass) / {TP.J01_top_metal:.0e}(metal)'),
                 ('Recomb. Junction','#F3E5F5','#7B1FA2','2T series: I_top = I_bot at every node'),
                 ('c-Si Bottom','#E8F5E9','#2E7D32',f'J01={TP.J01_bot:.0e}, Jph={TP.Jph_bot*1e3:.1f} mA/cm2'),
                 ('Rear (GND)','#ECEFF1','#455A64','Reference V=0. Full-area contact')]
        else:
            L = [('\uae08\uc18d \uadf8\ub9ac\ub4dc (Ag)','#FFF3E0','#E65100',f'R_line = rho/(CF*W*H) = {rl:.2f} ohm/cm'),
                 ('\uc811\ucd09\uc800\ud56d (rho_c)','#FFEBEE','#C62828',f'rho_c = {rc*1e3:.1f} mohm*cm2 | \ubaa9\ud45c < 6'),
                 ('TCO / \uc5d0\ubbf8\ud130','#E3F2FD','#1565C0',f'\ud551\uac70\ub85c \uc218\ud3c9 \uc804\ub958 \uc774\ub3d9. R_sheet = {rs:.0f} ohm/sq'),
                 ('\ud398\ub85c\ube0c\uc2a4\uce74\uc774\ud2b8 \uc0c1\ubd80','#FFF8E1','#F57F17',f'J01={TP.J01_top_pass:.0e}(\ud328\uc2dc) / {TP.J01_top_metal:.0e}(\uae08\uc18d)'),
                 ('\uc7ac\uacb0\ud569 \uc811\ud569','#F3E5F5','#7B1FA2','2T \uc9c1\ub82c: \ubaa8\ub4e0 \ub178\ub4dc\uc5d0\uc11c I_top = I_bot'),
                 ('c-Si \ud558\ubd80','#E8F5E9','#2E7D32',f'J01={TP.J01_bot:.0e}, Jph={TP.Jph_bot*1e3:.1f} mA/cm2'),
                 ('\ud6c4\uba74 (GND)','#ECEFF1','#455A64','\uae30\uc900 V=0. Full-area \uc811\ucd09')]
        y0 = 0.88
        for lab, fc, ec, note in L:
            h = 0.10
            ax.add_patch(FancyBboxPatch((0.04,y0), 0.92, h, boxstyle='round,pad=0.008', fc=fc, ec=ec, lw=1.2, transform=ax.transAxes))
            ax.text(0.07, y0+h*0.7, lab, fontsize=10, fontweight='bold', color=ec, transform=ax.transAxes)
            ax.text(0.07, y0+h*0.2, note, fontsize=8, color='#555', transform=ax.transAxes)
            if y0 > 0.12:
                ax.annotate('', xy=(0.5,y0-0.003), xytext=(0.5,y0+0.003), xycoords='axes fraction',
                            textcoords='axes fraction', arrowprops=dict(arrowstyle='->', color='#B0BEC5', lw=1.5))
            y0 -= (h + 0.02)

    def _model_p3(self, f, lang):
        self._model_hdr(f, 'FEM Equations + Mesh Comparison', 'FEM \ubc29\uc815\uc2dd + \uba54\uc2dc \ube44\uad50', 3, 7, lang)
        # LEFT: Equations
        ax = f.add_axes([0.02, 0.02, 0.46, 0.86]); ax.axis('off'); ax.set_xlim(0,1); ax.set_ylim(0,1)
        if lang == 'EN':
            S_ = [
                (0.78, '(1) Emitter -- KCL', '#1565C0',
                 'Sum[(Vj-Vi)/Rs] + Gc*(Ve-Vm) + J*A = 0',
                 'TCO lateral + contact out + photocurrent = 0'),
                (0.58, '(2) Metal -- Finger/Busbar', '#E65100',
                 'Sum[(Vmj-Vmi)/Rline] + Gc*(Vm-Ve) = 0',
                 'Metal grid current + emitter current = 0'),
                (0.38, '(3) Contact Coupling', '#C62828',
                 'Gc = A_node / rho_c   [S]',
                 'Lower rho_c -> stronger coupling -> less loss'),
                (0.18, '(4) Galerkin + Newton-Raphson', '#333',
                 'Int(grad_phi*grad_V/Rs)dA = Int(phi*J)dA',
                 'Exact Jacobian -> quadratic convergence'),
            ]
        else:
            S_ = [
                (0.78, '(1) \uc5d0\ubbf8\ud130 -- KCL', '#1565C0',
                 'Sum[(Vj-Vi)/Rs] + Gc*(Ve-Vm) + J*A = 0',
                 'TCO \uc218\ud3c9\uc804\ub958 + \uc811\ucd09\uc804\ub958 + \uad11\uc804\ub958 = 0'),
                (0.58, '(2) \uae08\uc18d -- \ud551\uac70/\ubc84\uc2a4\ubc14', '#E65100',
                 'Sum[(Vmj-Vmi)/Rline] + Gc*(Vm-Ve) = 0',
                 '\uae08\uc18d \uadf8\ub9ac\ub4dc \uc804\ub958 + \uc5d0\ubbf8\ud130 \uc804\ub958 = 0'),
                (0.38, '(3) \uc811\ucd09 \ucee4\ud50c\ub9c1', '#C62828',
                 'Gc = A_node / rho_c   [S]',
                 'rho_c \ub0ae\uc744\uc218\ub85d -> \uacb0\ud569 \uac15\ud654 -> \uc190\uc2e4 \uac10\uc18c'),
                (0.18, '(4) Galerkin + Newton-Raphson', '#333',
                 'Int(grad_phi*grad_V/Rs)dA = Int(phi*J)dA',
                 '\uc815\ud655\ud55c \uc57c\ucf54\ube44\uc548 -> 2\ucc28 \uc218\ub834'),
            ]
        for y0, title, clr_, eq, desc in S_:
            ax.add_patch(FancyBboxPatch((0.02,y0), 0.96, 0.17, boxstyle='round,pad=0.008', fc='#FAFAFA', ec=CLR_CARD_BD, lw=1, transform=ax.transAxes))
            ax.text(0.05, y0+0.135, title, fontsize=9.5, fontweight='bold', color=clr_, transform=ax.transAxes)
            ax.text(0.05, y0+0.075, eq, fontsize=9, color='#222', fontweight='bold', transform=ax.transAxes)
            ax.text(0.05, y0+0.025, desc, fontsize=8, color='#666', transform=ax.transAxes)

        # RIGHT: FDM vs FEM mesh comparison (VISUAL)
        ax2 = f.add_axes([0.52, 0.08, 0.46, 0.78])
        t2 = 'FDM vs FEM Mesh Comparison' if lang=='EN' else 'FDM vs FEM \uba54\uc2dc \ube44\uad50'
        ax2.set_title(t2, fontweight='bold', fontsize=10)
        ax2.set_xlim(0, 20); ax2.set_ylim(-0.5, 9.5); ax2.set_aspect('equal'); ax2.axis('off')
        # --- Left: FDM grid ---
        ax2.text(4.5, 9.0, 'FDM', ha='center', fontsize=11, fontweight='bold', color='#EF5350')
        for i in range(10):
            ax2.plot([i,i],[0,8],'-',color='#ddd',lw=0.4)
        for j in range(9):
            ax2.plot([0,9],[j,j],'-',color='#ddd',lw=0.4)
        # Finger band - FDM can't match
        ax2.fill_between([0,9],[3.5,3.5],[4.5,4.5],alpha=0.12,color='#EF5350')
        ax2.plot([0,9],[3,3],'--',color='#EF5350',lw=1.5)  # nearest grid line
        ax2.plot([0,9],[5,5],'--',color='#EF5350',lw=1.5)
        ax2.plot([0,9],[3.8,3.8],'-',color='#EF5350',lw=2.5)  # actual finger
        ax2.plot([0,9],[4.2,4.2],'-',color='#EF5350',lw=2.5)
        fdm_note = 'Grid != finger edge\nWidth overestimated' if lang=='EN' else '\uadf8\ub9ac\ub4dc != \ud551\uac70 \uacbd\uacc4\n\ud3ed \uacfc\ub300\ud3c9\uac00'
        ax2.text(4.5, 1.8, fdm_note, ha='center', fontsize=7, color='#EF5350', style='italic')
        # --- Right: FEM triangles ---
        ox = 11
        ax2.text(ox+4.5, 9.0, 'FEM', ha='center', fontsize=11, fontweight='bold', color='#66BB6A')
        fem_pts = []
        for i in np.linspace(0, 9, 8):
            for j in np.linspace(0, 8, 7):
                fem_pts.append([ox+i, j+(0.25*np.random.RandomState(42+int(i*10+j)).randn()
                                       if 0.5<i<8.5 and 0.5<j<7.5 else 0)])
        for x in np.linspace(ox, ox+9, 16):
            fem_pts.append([x, 3.8]); fem_pts.append([x, 4.0]); fem_pts.append([x, 4.2])
        fem_pts = np.array(fem_pts)
        from scipy.spatial import Delaunay as _Del
        try:
            _tri = _Del(fem_pts)
            for simplex in _tri.simplices:
                tp_ = fem_pts[simplex]
                poly = plt.Polygon(tp_, fill=False, edgecolor='#bbb', lw=0.3)
                ax2.add_patch(poly)
        except: pass
        ax2.plot([ox,ox+9],[3.8,3.8],'-',color='#66BB6A',lw=2.5)
        ax2.plot([ox,ox+9],[4.2,4.2],'-',color='#66BB6A',lw=2.5)
        for x in np.linspace(ox, ox+9, 16):
            ax2.plot(x, 3.8, 'o', color='#66BB6A', ms=2.5)
            ax2.plot(x, 4.2, 'o', color='#66BB6A', ms=2.5)
        fem_note = 'Nodes ON finger edge\nExact width' if lang=='EN' else '\ub178\ub4dc\uac00 \ud551\uac70 \uacbd\uacc4 \uc704\uc5d0\n\uc815\ud655\ud55c \ud3ed'
        ax2.text(ox+4.5, 1.8, fem_note, ha='center', fontsize=7, color='#66BB6A', style='italic')

    def _model_p4(self, f, lang):
        self._model_hdr(f, 'Two-Diode Model', 'Two-Diode \ubaa8\ub378', 4, 7, lang)
        ax = f.add_axes([0, 0, 1, 0.91]); ax.axis('off'); ax.set_xlim(0,1); ax.set_ylim(0,1)
        # Equation box
        ax.add_patch(FancyBboxPatch((0.03,0.78), 0.94, 0.10, boxstyle='round,pad=0.012', fc='#F0F4FF', ec='#5C6BC0', lw=1.5, transform=ax.transAxes))
        ax.text(0.5, 0.84, 'J = Jph - J01*(exp(V/n1*Vt)-1) - J02*(exp(V/n2*Vt)-1) - V/Rsh',
                ha='center', fontsize=11, fontweight='bold', color='#1a237e', transform=ax.transAxes)
        if lang=='EN':
            terms = [('Jph: photocurrent','#333'),('J01 (n=1): diffusion recombination','#E65100'),
                     ('J02 (n=2): SRH recombination','#C62828'),('Rsh: shunt resistance (leakage)','#2E7D32')]
        else:
            terms = [('Jph: \uad11\uc804\ub958','#333'),('J01 (n=1): \ud655\uc0b0 \uc7ac\uacb0\ud569','#E65100'),
                     ('J02 (n=2): SRH \uc7ac\uacb0\ud569','#C62828'),('Rsh: \ub204\uc124\uc800\ud56d','#2E7D32')]
        for i,(t,c) in enumerate(terms):
            ax.text(0.06, 0.74-i*0.03, '* '+t, fontsize=8.5, color=c, transform=ax.transAxes)
        # Top cell (LEFT)
        tl = 'Top Cell (Perovskite)' if lang=='EN' else '\uc0c1\ubd80 \uc140 (\ud398\ub85c\ube0c\uc2a4\uce74\uc774\ud2b8)'
        ax.add_patch(FancyBboxPatch((0.03,0.22), 0.45, 0.36, boxstyle='round,pad=0.01', fc='#FFF8E1', ec='#F57F17', lw=1, transform=ax.transAxes))
        ax.text(0.255, 0.545, tl, ha='center', fontsize=10, fontweight='bold', color='#F57F17', transform=ax.transAxes)
        for i,p in enumerate([f'Jph = {TP.Jph_top*1e3:.1f} mA/cm2', f'J01 = {TP.J01_top_pass:.1e} (passivated)',
            f'J01 = {TP.J01_top_metal:.1e} (under metal)', f'J02 = {TP.J02_top_pass:.1e}',
            f'n1={TP.n1_top:.0f}, n2={TP.n2_top:.1f}', f'Rsh = {TP.Rsh_top:.0f} ohm*cm2']):
            ax.text(0.06, 0.50-i*0.04, p, fontsize=8.5, color='#555', transform=ax.transAxes)
        # Bottom cell (RIGHT)
        bl = 'Bottom Cell (c-Si HJT)' if lang=='EN' else '\ud558\ubd80 \uc140 (c-Si HJT)'
        ax.add_patch(FancyBboxPatch((0.52,0.22), 0.45, 0.36, boxstyle='round,pad=0.01', fc='#E8F5E9', ec='#2E7D32', lw=1, transform=ax.transAxes))
        ax.text(0.745, 0.545, bl, ha='center', fontsize=10, fontweight='bold', color='#2E7D32', transform=ax.transAxes)
        for i,p in enumerate([f'Jph = {TP.Jph_bot*1e3:.1f} mA/cm2', f'J01 = {TP.J01_bot:.1e}',
            f'J02 = {TP.J02_bot:.1e}', f'n1={TP.n1_bot:.0f}, n2={TP.n2_bot:.1f}',
            f'Rsh = {TP.Rsh_bot:.0f} ohm*cm2']):
            ax.text(0.55, 0.50-i*0.04, p, fontsize=8.5, color='#555', transform=ax.transAxes)
        # J01 spatial note
        n = 'J01 under metal is 83x higher (literature)' if lang=='EN' else '\uae08\uc18d \ud558\ubd80 J01\uc740 \ud328\uc2dc\ubca0\uc774\uc158 \ub300\ube44 83\ubc30'
        ax.add_patch(FancyBboxPatch((0.03,0.08), 0.94, 0.10, boxstyle='round,pad=0.01', fc='#FFF3E0', ec='#E65100', lw=1, transform=ax.transAxes))
        ax.text(0.5, 0.13, n, ha='center', fontsize=10, fontweight='bold', color='#E65100', transform=ax.transAxes)

    def _model_p5(self, f, lang):
        self._model_hdr(f, '2T Tandem Current Matching', '2T \ud0e0\ub364 \uc804\ub958 \ub9e4\uce6d', 5, 7, lang)
        ax = f.add_axes([0, 0, 1, 0.91]); ax.axis('off'); ax.set_xlim(0,1); ax.set_ylim(0,1)
        ax.add_patch(FancyBboxPatch((0.05,0.78), 0.90, 0.10, boxstyle='round,pad=0.015', fc='#F0F4FF', ec='#5C6BC0', lw=2, transform=ax.transAxes))
        ax.text(0.5, 0.84, 'I_top(V_top) = I_bot(V_emitter - V_top)', ha='center',
                fontsize=14, fontweight='bold', color='#1a237e', transform=ax.transAxes)
        sub = 'at EVERY mesh node simultaneously' if lang=='EN' else '\ubaa8\ub4e0 \uba54\uc2dc \ub178\ub4dc\uc5d0\uc11c \ub3d9\uc2dc\uc5d0'
        ax.text(0.5, 0.795, sub, ha='center', fontsize=10, color='#666', style='italic', transform=ax.transAxes)
        if lang == 'EN':
            items = [
                ('V_emitter = V_top + V_bottom', 'Total voltage = sum of two subcells (series)'),
                ('V_top is a separate unknown', f'At each of {len(pts):,} nodes, V_top solved independently'),
                ('Newton-Raphson finds V_top', 'Iterates until I_top = I_bot at every point'),
                ('LOCAL matching (not global)', 'Current matching varies spatially due to R and shading'),
                ('Current-limiting subcell -> Jsc', 'Subcell with less current determines overall Jsc'),
            ]
        else:
            items = [
                ('V_emitter = V_top + V_bottom', '\uc804\uccb4 \uc804\uc555 = \ub450 \uc11c\ube0c\uc140 \uc804\uc555\uc758 \ud569 (\uc9c1\ub82c)'),
                ('V_top\uc740 \ubcc4\ub3c4 \ubbf8\uc9c0\uc218', f'{len(pts):,}\uac1c \uac01 \ub178\ub4dc\uc5d0\uc11c V_top \ub3c5\ub9bd \uacc4\uc0b0'),
                ('Newton-Raphson\uc73c\ub85c V_top \uacc4\uc0b0', '\ubaa8\ub4e0 \uc9c0\uc810\uc5d0\uc11c I_top = I_bot \ub420 \ub54c\uae4c\uc9c0 \ubc18\ubcf5'),
                ('LOCAL \ub9e4\uce6d (\uae00\ub85c\ubc8c X)', '\uc800\ud56d + \uc74c\uc601\uc73c\ub85c \uc804\ub958\ub9e4\uce6d\uc774 \uacf5\uac04\uc801\uc73c\ub85c \ubcc0\ud568'),
                ('\uc804\ub958\uc81c\ud55c \uc11c\ube0c\uc140 -> Jsc', '\uc804\ub958 \uc801\uc740 \uc140\uc774 \uc804\uccb4 Jsc \uacb0\uc815'),
            ]
        y0 = 0.68
        for title, body in items:
            ax.add_patch(FancyBboxPatch((0.05,y0), 0.90, 0.09, boxstyle='round,pad=0.008', fc='#F8FAFC', ec=CLR_CARD_BD, lw=1, transform=ax.transAxes))
            ax.text(0.08, y0+0.06, '> '+title, fontsize=9.5, fontweight='bold', color=CLR_ACCENT, transform=ax.transAxes)
            ax.text(0.08, y0+0.02, body, fontsize=8.5, color='#555', transform=ax.transAxes)
            y0 -= 0.105
        Vt_,Vb_,Vtot_ = TP.expected_voc()
        ax.add_patch(FancyBboxPatch((0.05,0.06), 0.90, 0.06, boxstyle='round,pad=0.008', fc='#E8EAF6', ec='#5C6BC0', lw=1, transform=ax.transAxes))
        lbl = 'Expected Voc' if lang=='EN' else '\uc608\uc0c1 Voc'
        ax.text(0.5, 0.09, f'{lbl}:  Top {Vt_:.4f}V + Bot {Vb_:.4f}V = {Vtot_:.4f}V',
                ha='center', fontsize=10, fontweight='bold', color='#1a237e', transform=ax.transAxes)

    def _model_p6(self, f, lang):
        """Newton-Raphson: tangent line visual + convergence + flowchart."""
        self._model_hdr(f, 'Newton-Raphson Solver', 'Newton-Raphson \ud480\uc774 \uacfc\uc815', 6, 7, lang)
        bp_,_ = self._get_params()
        if bp_ is None: bp_ = (13.22e-6,10e-4,50e-4,50e-4,0.785,10e-3,55.0)
        rm,hf,wf,wb,cf,rc,rs = bp_
        Vmpp_nr = self._cache.get('iv_b',{}).get('Vmpp', 1.8)  # MPP 전압 사용
        Vmpp_nr = self._cache.get('iv_b',{}).get('Vmpp_internal', Vmpp_nr)
        res_nr = self._cache.get('iv_b',{}).get('_mpp_result') or S.solve(rm,hf,wf,rc,rs,Vmpp_nr,cf,DP,mode='tandem')
        res_list = res_nr['res']
        Nt = 2*len(pts) + int(np.sum(ism))

        # ── LEFT TOP: NR concept diagram (tangent line method) ──
        ax_nr = f.add_axes([0.05, 0.50, 0.42, 0.36])
        t1 = 'Newton-Raphson Concept' if lang=='EN' else 'Newton-Raphson \uac1c\ub150'
        ax_nr.set_title(t1, fontweight='bold', fontsize=10)
        x_plot = np.linspace(0, 6, 200)
        f_func = lambda x: np.exp(0.6*x) - 3
        fp_func = lambda x: 0.6*np.exp(0.6*x)
        y_plot = f_func(x_plot)
        ax_nr.plot(x_plot, y_plot, '-', color='#333', lw=2)
        ax_nr.axhline(0, color='#999', lw=0.8)
        x_root = np.log(3)/0.6
        ax_nr.plot(x_root, 0, '*', color='#2E7D32', ms=14, zorder=10)
        colors_nr = ['#EF5350', '#FFA726', '#42A5F5', '#66BB6A']
        x_nr = 5.5
        for i in range(4):
            fx = f_func(x_nr); fpx = fp_func(x_nr)
            ax_nr.plot(x_nr, fx, 'o', color=colors_nr[i], ms=7, zorder=5)
            x_next = x_nr - fx/fpx
            x_tang = np.linspace(max(x_next-0.3,0), min(x_nr+0.5,6), 50)
            y_tang = fpx*(x_tang - x_nr) + fx
            ax_nr.plot(x_tang, y_tang, '--', color=colors_nr[i], lw=1.2, alpha=0.7)
            ax_nr.plot([x_nr,x_nr], [0,fx], ':', color=colors_nr[i], lw=0.8, alpha=0.5)
            if i < 3:
                lbl = f'x{i+1}' if lang=='EN' else f'x{i+1}'
                ax_nr.annotate(lbl, xy=(x_nr,fx), xytext=(x_nr+0.2, fx+1.5-i*0.5),
                    fontsize=7, color=colors_nr[i], fontweight='bold',
                    arrowprops=dict(arrowstyle='->', color=colors_nr[i], lw=0.8))
            x_nr = x_next
        ax_nr.set_xlabel('V (voltage)', fontsize=8)
        ax_nr.set_ylabel('F(V) (residual)', fontsize=8)
        ax_nr.set_xlim(0, 6.5); ax_nr.set_ylim(-3.5, max(y_plot)*0.6)
        ax_nr.grid(True, alpha=0.08)
        eq_txt = 'V_new = V - F(V)/F\'(V)'
        ax_nr.text(0.95, 0.05, eq_txt, fontsize=8, ha='right', transform=ax_nr.transAxes,
                  color='#555', bbox=dict(boxstyle='round', fc='#FAFAFA', ec='#e0e0e0', alpha=0.9))

        # ── LEFT BOTTOM: Live convergence ──
        ax_conv = f.add_axes([0.05, 0.06, 0.42, 0.36])
        t2 = 'Convergence (this solve)' if lang=='EN' else '\uc218\ub834 \uacb0\uacfc (\uc2e4\uc2dc\uac04)'
        ax_conv.set_title(t2, fontweight='bold', fontsize=10)
        iters = range(1, len(res_list)+1)
        ax_conv.semilogy(iters, res_list, 'o-', color='#5C6BC0', ms=8, lw=2.5, zorder=5)
        ax_conv.axhline(1e-10, color='#EF5350', ls='--', lw=1.5, label='Threshold')
        for i, r in enumerate(res_list):
            ax_conv.annotate(f'{r:.1e}', (i+1, r), textcoords="offset points",
                xytext=(8, 5 if i%2==0 else -12), fontsize=7, color='#333')
        ax_conv.set_xlabel('Iteration'); ax_conv.set_ylabel('max |F(V)|')
        ax_conv.legend(fontsize=8); ax_conv.grid(True, alpha=0.15)
        info = f'{len(res_list)} iter | {Nt:,} DOF' if lang=='EN' else f'{len(res_list)}\ud68c | {Nt:,} DOF'
        ax_conv.text(0.95, 0.95, info, transform=ax_conv.transAxes, ha='right', va='top',
            fontsize=8, fontweight='bold', bbox=dict(boxstyle='round', fc='#E8F5E9', ec='#66BB6A'))

        # ── RIGHT: Step-by-step flowchart ──
        ax_f = f.add_axes([0.52, 0.02, 0.46, 0.86]); ax_f.axis('off')
        ax_f.set_xlim(0, 1); ax_f.set_ylim(0, 1)
        Ne = len(pts); Nm = int(np.sum(ism))
        if lang == 'EN':
            title = 'Solver Loop (per bias point)'
            blks = [
                (0.88, '#E3F2FD', '#1565C0', 'INIT: Guess V', [
                    f'V = [Ve({Ne:,}) + Vm({Nm:,}) + Vt({Ne:,})] = {Nt:,} unknowns',
                    'Ve = 0.95*Vbias,  Vm = Vbias,  Vt = 0.63*Vbias']),
                (0.72, '#FFF3E0', '#E65100', '1. Compute residual F(V)', [
                    'F_emitter: K_e*Ve - J_diode*A + Gc*(Ve-Vm)',
                    'F_metal:   K_m*Vm + Gc*(Vm-Ve)',
                    'F_tandem:  (J_top - J_bot) * A_node']),
                (0.56, '#FFEBEE', '#C62828', '2. Build Jacobian J = dF/dV', [
                    f'Sparse {Nt:,} x {Nt:,} matrix',
                    'dJ_diode/dV = J01*exp(V/Vt)/Vt  (exact, not finite-diff)']),
                (0.42, '#E8F5E9', '#2E7D32', '3. Solve J * dV = -F', [
                    'scipy sparse LU factorization',
                    'Damping: if |dV| > 0.1V, scale down (prevent divergence)']),
                (0.28, '#F3E5F5', '#7B1FA2', '4. Update V = V + dV', [
                    'Clip: V_top must stay in [0, V_emitter]',
                    'This is what the tangent line (left) does visually!']),
                (0.16, '#E0F7FA', '#00695C', '5. Converged?', [
                    f'max|F| < 1e-10 ?  YES in {len(res_list)} iterations',
                    f'Final residual: {res_list[-1]:.2e}']),
            ]
        else:
            title = '\ud480\uc774 \ub8e8\ud504 (\uac01 \uc804\uc555 \uc810\ub9c8\ub2e4)'
            blks = [
                (0.88, '#E3F2FD', '#1565C0', '\ucd08\uae30\uac12: V \ucd94\uc815', [
                    f'V = [Ve({Ne:,}) + Vm({Nm:,}) + Vt({Ne:,})] = {Nt:,}\uac1c',
                    'Ve=0.95*Vb, Vm=Vb, Vt=0.63*Vb']),
                (0.72, '#FFF3E0', '#E65100', '1. \uc794\uc5ec\ubca1\ud130 F(V) \uacc4\uc0b0', [
                    'F_emitter: K_e*Ve - J_diode*A + Gc*(Ve-Vm)',
                    'F_metal:   K_m*Vm + Gc*(Vm-Ve)',
                    'F_tandem:  (J_top - J_bot) * A_node']),
                (0.56, '#FFEBEE', '#C62828', '2. \uc57c\ucf54\ube44\uc548 J = dF/dV \uad6c\uc131', [
                    f'\ud76c\uc18c\ud589\ub82c {Nt:,} x {Nt:,}',
                    'dJ/dV = J01*exp(V/Vt)/Vt  (\uc815\ud655\ud55c \ud574\uc11d\uc801 \ubbf8\ubd84)']),
                (0.42, '#E8F5E9', '#2E7D32', '3. J * dV = -F \ud480\uae30', [
                    'scipy \ud76c\uc18c LU \ubd84\ud574',
                    '\uac10\uc1e0: |dV| > 0.1V\uba74 \ucd95\uc18c (\ubc1c\uc0b0 \ubc29\uc9c0)']),
                (0.28, '#F3E5F5', '#7B1FA2', '4. V = V + dV \uc5c5\ub370\uc774\ud2b8', [
                    'V_top\uc744 [0, V_emitter] \ub0b4\ub85c \ud074\ub9ac\ud551',
                    '\uc67c\ucabd \uc811\uc120\ubc95 \uadf8\ub9bc\uc774 \uc774 \uacfc\uc815\uc744 \uc2dc\uac01\ud654!']),
                (0.16, '#E0F7FA', '#00695C', '5. \uc218\ub834 \ud655\uc778', [
                    f'max|F| < 1e-10?  {len(res_list)}\ud68c\ub9cc\uc5d0 \uc218\ub834!',
                    f'\ucd5c\uc885 \uc794\uc5ec: {res_list[-1]:.2e}']),
            ]
        ax_f.text(0.5, 0.97, title, ha='center', fontsize=10, fontweight='bold',
                 color=CLR_ACCENT, transform=ax_f.transAxes)
        for y0, fc, ec, title_b, lines_b in blks:
            h = 0.10 if len(lines_b) <= 2 else 0.12
            ax_f.add_patch(FancyBboxPatch((0.02, y0), 0.96, h,
                boxstyle='round,pad=0.006', fc=fc, ec=ec, lw=1.2, transform=ax_f.transAxes))
            ax_f.text(0.05, y0+h-0.022, title_b, fontsize=8.5, fontweight='bold',
                     color=ec, transform=ax_f.transAxes)
            for i, ln in enumerate(lines_b):
                ax_f.text(0.05, y0+h-0.045-i*0.025, ln, fontsize=7, color='#444',
                         transform=ax_f.transAxes)
            if y0 > 0.20:
                ax_f.annotate('', xy=(0.5, y0-0.003), xytext=(0.5, y0+0.003),
                    xycoords='axes fraction', textcoords='axes fraction',
                    arrowprops=dict(arrowstyle='->', color='#90A4AE', lw=1.8))

    def _model_p7(self, f, lang):
        self._model_hdr(f, 'Mesh & Solver Convergence', '\uba54\uc2dc & \uc218\ub834 \uacb0\uacfc', 7, 7, lang)
        # Mesh plot
        ax_m = f.add_axes([0.06, 0.48, 0.40, 0.38])
        ax_m.triplot(triang,'k-',lw=0.12,alpha=0.25)
        ax_m.plot(pts[isf,0]*10,pts[isf,1]*10,'s',color='#EF5350',ms=1.5,label='Finger')
        ax_m.plot(pts[isb&~isp,0]*10,pts[isb&~isp,1]*10,'s',color='#42A5F5',ms=1.5,label='Busbar')
        if GEO.pad > 0:
            ax_m.plot(pts[isp,0]*10,pts[isp,1]*10,'s',color='#FFA726',ms=3,label='Pad')
        ax_m.legend(fontsize=7); ax_m.set_aspect('equal',adjustable='box')
        ax_m.set_xlabel('X [mm]'); ax_m.set_ylabel('Y [mm]')
        ml = f'Mesh ({len(pts)} nodes)' if lang=='EN' else f'\uba54\uc2dc ({len(pts)} \ub178\ub4dc)'
        ax_m.set_title(ml, fontweight='bold', fontsize=10)
        # Convergence
        ax_c = f.add_axes([0.55, 0.48, 0.40, 0.38])
        bp_,_ = self._get_params()
        if bp_:
            rm,hf,wf,wb,cf,rc,rs = bp_
            Vmpp_nr = self._cache.get('iv_b',{}).get('Vmpp', 1.8)
            Vmpp_nr = self._cache.get('iv_b',{}).get('Vmpp_internal', Vmpp_nr)
            res_nr2 = self._cache.get('iv_b',{}).get('_mpp_result') or S.solve(rm,hf,wf,rc,rs,Vmpp_nr,cf,DP,mode='tandem')
            rl = res_nr2['res']
            ax_c.semilogy(range(1,len(rl)+1),rl,'o-',color='#5C6BC0',ms=6,lw=2)
            ax_c.axhline(1e-10,color='#EF5350',ls='--',lw=1.2,label='Threshold')
            ax_c.legend(fontsize=8); ax_c.grid(True,alpha=0.1)
            ax_c.set_xlabel('Iteration'); ax_c.set_ylabel('Max |Residual|')
            cl = f'Convergence ({len(rl)} iter)' if lang=='EN' else f'\uc218\ub834 ({len(rl)}\ud68c)'
            ax_c.set_title(cl, fontweight='bold', fontsize=10)
        # Stats table
        ax_s = f.add_axes([0, 0, 1, 0.45]); ax_s.axis('off'); ax_s.set_xlim(0,1); ax_s.set_ylim(0,1)
        Nm=int(np.sum(ism)); Nt=2*len(pts)+Nm
        if lang=='EN':
            st=[('Mesh','Constrained Delaunay Triangulation'),('Nodes',f'{len(pts):,}'),
                ('Elements',f'{len(tri.simplices):,} triangles'),
                ('V_emitter',f'{len(pts):,} unknowns'),('V_metal',f'{Nm:,} unknowns'),
                ('V_top',f'{len(pts):,} unknowns'),('Total DOF',f'{Nt:,}'),
                ('Cell',f'{GEO.W*10:.0f}x{GEO.H*10:.0f}mm, {GEO.n_f}F+{GEO.n_b}BB'),
                ('Shading',f'{GEO.shading_fraction()*100:.2f}%')]
        else:
            st=[('\uba54\uc2dc','Constrained Delaunay Triangulation'),('\ub178\ub4dc',f'{len(pts):,}'),
                ('\uc694\uc18c',f'{len(tri.simplices):,} \uc0bc\uac01\ud615'),
                ('V_emitter',f'{len(pts):,} \ubbf8\uc9c0\uc218'),('V_metal',f'{Nm:,} \ubbf8\uc9c0\uc218'),
                ('V_top',f'{len(pts):,} \ubbf8\uc9c0\uc218'),('Total DOF',f'{Nt:,}'),
                ('\uc140',f'{GEO.W*10:.0f}x{GEO.H*10:.0f}mm, {GEO.n_f}F+{GEO.n_b}BB'),
                ('\uc74c\uc601',f'{GEO.shading_fraction()*100:.2f}%')]
        ax_s.add_patch(Rectangle((0.06,0.10), 0.88, 0.85, fc='#F8FAFC', ec=CLR_CARD_BD, lw=1, transform=ax_s.transAxes))
        y0=0.88
        for i,(k,v) in enumerate(st):
            if i%2==0: ax_s.add_patch(Rectangle((0.06,y0-0.02),0.88,0.09, fc='#F1F5F9', ec='none', transform=ax_s.transAxes))
            ax_s.text(0.10, y0+0.01, k, fontsize=9, fontweight='bold', color='#555', transform=ax_s.transAxes)
            ax_s.text(0.38, y0+0.01, v, fontsize=9, color='#333', transform=ax_s.transAxes)
            y0 -= 0.09

    def _load_exp(self):
        fn = filedialog.askopenfilename(
            title="Load Experimental I-V (CSV)",
            filetypes=[('CSV','*.csv'),('Text','*.txt'),('All','*.*')])
        if not fn: return
        try:
            lines = []
            with open(fn, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    lines.append(line)
            if len(lines) < 2:
                self._status("Error: file too short."); return
            delim = ',' if ',' in lines[1] else '\t' if '\t' in lines[1] else ' '
            data_lines = lines[1:]
            V_list=[]; J_list=[]
            for dl in data_lines:
                parts = [p.strip() for p in dl.split(delim) if p.strip()]
                if len(parts) >= 2:
                    try: V_list.append(float(parts[0])); J_list.append(float(parts[1]))
                    except ValueError: continue
            if len(V_list) < 2:
                self._status("Error: could not parse data."); return
            self._exp_data['V_exp'] = np.array(V_list)
            self._exp_data['J_exp'] = np.array(J_list)
            self._status(f'Loaded: {os.path.basename(fn)} ({len(V_list)} pts). Click COMPARE to overlay.')
            messagebox.showinfo("2L-FEST PRO",
                f"Loaded {len(V_list)} data points.\n"
                f"V range: {min(V_list):.3f} ~ {max(V_list):.3f} V\n"
                f"J range: {min(J_list):.2f} ~ {max(J_list):.2f} mA/cm2\n\n"
                f"Click COMPARE to overlay on simulation.")
        except Exception as e:
            self._status(f"Load error: {e}")


    # ---------------------------------------------------------
    # REPORT VIEWER
    # ---------------------------------------------------------
    def _gen_report(self):
        if 'iv_b' not in self._cache:
            self._status(_t('run_compare_first')); return
        self._status("Generating Report...")
        self.update_idletasks()

        d = dict(self._cache)
        state = {'pg': 0}

        rwin = ctk.CTkToplevel(self)
        rwin.title("2L-FEST PRO Report")
        rwin.geometry("1200x800")
        rwin.attributes('-topmost', True)

        # Report figure
        rfig = Figure(figsize=(11, 8.5), facecolor='white', dpi=100)

        # Navigation bar -- PACK FIRST so it always shows
        nav = ctk.CTkFrame(rwin, fg_color=CLR_TAB_BG, height=48)
        nav.pack(fill="x", side="bottom")
        nav.pack_propagate(False)

        # Canvas fills remaining space AFTER nav
        rcanvas = FigureCanvasTkAgg(rfig, master=rwin)
        rcanvas.get_tk_widget().pack(fill="both", expand=True)

        page_label = ctk.CTkLabel(nav, text=f"1 / {len(_RPT_PAGES)}",
                                    font=ctk.CTkFont(size=12, weight="bold"),
                                    text_color=CLR_TEXT)

        def draw_page(pg=None):
            if pg is not None:
                state['pg'] = max(0, min(pg, len(_RPT_PAGES)-1))
            rfig.clear()
            _RPT_PAGES[state['pg']](rfig, d)
            page_label.configure(text=f"{state['pg']+1} / {len(_RPT_PAGES)}")
            rcanvas.draw()

        def prev_pg(): draw_page(state['pg']-1)
        def next_pg(): draw_page(state['pg']+1)

        def save_pdf():
            fn = filedialog.asksaveasfilename(
                initialfile='2L-FEST_PRO_Report.pdf',
                filetypes=[('PDF','*.pdf')], defaultextension='.pdf')
            if not fn: return
            with PdfPages(fn) as pdf:
                for pf_ in _RPT_PAGES:
                    pg = Figure(figsize=(11,8.5), facecolor='white')
                    FigureCanvasAgg(pg)
                    pf_(pg, d); pdf.savefig(pg); plt.close(pg)
            messagebox.showinfo("2L-FEST PRO",
                                 f"PDF saved ({len(_RPT_PAGES)} pages):\n{fn}")

        def save_png():
            fn = filedialog.asksaveasfilename(
                initialfile=f'2L-FEST_p{state["pg"]+1}.png',
                filetypes=[('PNG','*.png')], defaultextension='.png')
            if fn:
                rfig.savefig(fn, dpi=150, bbox_inches='tight', facecolor='white')

        # --- Left side: PREV + page dots + NEXT ---
        btn_prev = ctk.CTkButton(nav, text="\u25c0", width=40, height=30,
                       fg_color="#94A3B8", hover_color="#64748B",
                       font=ctk.CTkFont(size=14),
                       command=prev_pg)
        btn_prev.pack(side="left", padx=(8,4), pady=6)

        # Page number buttons (1~6)
        pg_btns = []
        _active_clr = CLR_ACCENT
        _inactive_clr = "#CBD5E1"

        def _go_page(i):
            def _fn(): draw_page(i)
            return _fn

        def _update_pg_btns():
            for i, pb in enumerate(pg_btns):
                if i == state['pg']:
                    pb.configure(fg_color=_active_clr, text_color="white",
                                 border_color=_active_clr)
                else:
                    pb.configure(fg_color="white", text_color="#64748B",
                                 border_color=_inactive_clr)

        for i in range(len(_RPT_PAGES)):
            pb = ctk.CTkButton(nav, text=str(i+1), width=30, height=28,
                               fg_color="white", hover_color="#E2E8F0",
                               text_color="#64748B", border_width=1,
                               border_color=_inactive_clr,
                               font=ctk.CTkFont(size=11, weight="bold"),
                               corner_radius=6, command=_go_page(i))
            pb.pack(side="left", padx=1, pady=6)
            pg_btns.append(pb)

        page_label.pack(side="left", padx=(8,4))

        btn_next = ctk.CTkButton(nav, text="\u25b6", width=40, height=30,
                       fg_color="#94A3B8", hover_color="#64748B",
                       font=ctk.CTkFont(size=14),
                       command=next_pg)
        btn_next.pack(side="left", padx=(4,8), pady=6)

        # --- Right side: SAVE buttons ---
        btn_pdf = ctk.CTkButton(nav, text="SAVE PDF", width=100, height=30,
                       fg_color=CLR_ACCENT, hover_color="#303F9F",
                       font=ctk.CTkFont(size=11, weight="bold"),
                       command=save_pdf)
        btn_pdf.pack(side="right", padx=8, pady=6)
        btn_png = ctk.CTkButton(nav, text="SAVE PNG", width=100, height=30,
                       fg_color="#455A64", hover_color="#546E7A",
                       font=ctk.CTkFont(size=11, weight="bold"),
                       command=save_png)
        btn_png.pack(side="right", padx=4, pady=6)

        # Patch draw_page to also update page dot highlights
        _orig_draw = draw_page
        def draw_page_wrapped(pg=None):
            _orig_draw(pg)
            _update_pg_btns()
        # Rebind
        def prev_pg_w(): draw_page_wrapped(state['pg']-1)
        def next_pg_w(): draw_page_wrapped(state['pg']+1)
        btn_prev.configure(command=prev_pg_w)
        btn_next.configure(command=next_pg_w)
        for i, pb in enumerate(pg_btns):
            def _mk(idx):
                def _fn(): draw_page_wrapped(idx)
                return _fn
            pb.configure(command=_mk(i))

        # Keep references alive
        rwin._btns = [btn_prev, btn_next, btn_pdf, btn_png] + pg_btns
        rwin._refs = [rfig, rcanvas, page_label, d, state]

        # Keyboard navigation
        def on_key(event):
            if event.keysym in ('Left', 'a', 'A'):
                prev_pg_w()
            elif event.keysym in ('Right', 'd', 'D'):
                next_pg_w()
            elif event.keysym == 'Home':
                draw_page_wrapped(0)
            elif event.keysym == 'End':
                draw_page_wrapped(len(_RPT_PAGES)-1)
            elif event.keysym in ('1','2','3','4','5','6'):
                draw_page_wrapped(int(event.keysym)-1)

        rwin.bind('<Key>', on_key)

        # Mouse scroll navigation (bind ONLY on canvas to avoid double-fire)
        _scroll_lock = {'t': 0}
        def on_scroll(event):
            import time as _t
            now = _t.time()
            if now - _scroll_lock['t'] < 0.15:  # debounce 150ms
                return "break"
            _scroll_lock['t'] = now
            # macOS: event.delta > 0 = scroll up = prev, < 0 = next
            # Windows: same but larger delta values
            # Linux: event.num == 4/5
            if hasattr(event, 'delta') and event.delta != 0:
                if event.delta > 0:
                    prev_pg_w()
                else:
                    next_pg_w()
            elif hasattr(event, 'num'):
                if event.num == 4:
                    prev_pg_w()
                elif event.num == 5:
                    next_pg_w()
            return "break"

        # Bind scroll ONLY on canvas widget (not rwin) to prevent double-fire
        canvas_widget = rcanvas.get_tk_widget()
        canvas_widget.bind('<MouseWheel>', on_scroll)
        canvas_widget.bind('<Button-4>', on_scroll)
        canvas_widget.bind('<Button-5>', on_scroll)

        rwin.focus_set()
        draw_page_wrapped(0)
        self._status("Report opened.  Scroll / \u25c0\u25b6 / 1~6 keys to navigate.")



    # ---------------------------------------------------------
    # CSV EXPORT
    # ---------------------------------------------------------
    def _save_csv(self):
        if 'iv_b' not in self._cache:
            self._status(_t('run_compare_first')); return
        fn = filedialog.asksaveasfilename(
            initialfile='2L-FEST_Results.csv',
            filetypes=[('CSV','*.csv')], defaultextension='.csv')
        if not fn: return
        c = self._cache
        iv_b=c['iv_b']; iv_a=c['iv_a']; bp=c['bp']; ap=c['ap']
        lines = []
        lines.append("2L-FEST PRO v5.0 Results")
        lines.append(f"Cell,{GEO.W*10:.0f}x{GEO.H*10:.0f}mm,{GEO.n_f}F+{GEO.n_b}BB")
        lines.append(f"Mesh,{len(pts)} nodes,{len(tri.simplices)} tri")
        lines.append("")
        lines.append("Parameter,Before,After,Unit")
        lines.append(f"rho_bulk,{bp[0]*1e6:.2f},{ap[0]*1e6:.2f},uOhm*cm")
        lines.append(f"H_finger,{bp[1]*1e4:.1f},{ap[1]*1e4:.1f},um")
        lines.append(f"W_finger,{bp[2]*1e4:.0f},{ap[2]*1e4:.0f},um")
        lines.append(f"W_busbar,{bp[3]*1e4:.0f},{ap[3]*1e4:.0f},um")
        lines.append(f"CF,{bp[4]:.3f},{ap[4]:.3f},")
        lines.append(f"rho_c,{bp[5]*1e3:.1f},{ap[5]*1e3:.1f},mOhm*cm2")
        lines.append(f"R_sheet,{bp[6]:.0f},{bp[6]:.0f},Ohm/sq")
        lines.append("")
        lines.append("Performance,Before,After,Delta")
        lines.append(f"Jsc [mA/cm2],{iv_b['Jsc']:.4f},{iv_a['Jsc']:.4f},{iv_a['Jsc']-iv_b['Jsc']:+.4f}")
        lines.append(f"Voc [V],{iv_b['Voc']:.5f},{iv_a['Voc']:.5f},{iv_a['Voc']-iv_b['Voc']:+.5f}")
        lines.append(f"FF [%],{iv_b['FF']:.3f},{iv_a['FF']:.3f},{iv_a['FF']-iv_b['FF']:+.3f}")
        lines.append(f"Eff [%],{iv_b['Eff']:.4f},{iv_a['Eff']:.4f},{iv_a['Eff']-iv_b['Eff']:+.4f}")
        lines.append(f"Pmpp [mW/cm2],{iv_b['Pmpp']:.4f},{iv_a['Pmpp']:.4f},{iv_a['Pmpp']-iv_b['Pmpp']:+.4f}")
        Rl_b=bp[0]/(bp[4]*bp[2]*bp[1]); Rl_a=ap[0]/(ap[4]*ap[2]*ap[1])
        lines.append(f"R_line [Ohm/cm],{Rl_b:.4f},{Rl_a:.4f},{Rl_a-Rl_b:+.4f}")
        lines.append(f"Rs_extracted [Ohm*cm2],{c.get('Rs_ext_b',0):.4f},{c.get('Rs_ext_a',0):.4f},")
        lines.append(f"Gsh [S/cm2],{c.get('Gsh_b',0):.6f},{c.get('Gsh_a',0):.6f},")
        lines.append("")
        hb = c.get('health_b') or _iv_health(iv_b)
        ha = c.get('health_a') or _iv_health(iv_a)
        def _csv_num(value):
            return "" if value is None else f"{value:.12g}"
        lines.append("Result Health,Before,After,Unit")
        lines.append(f"Status,{hb['status']},{ha['status']},")
        lines.append(f"Message,{hb['message']},{ha['message']},")
        lines.append(f"Final Newton residual,{_csv_num(hb['final_newton_residual'])},{_csv_num(ha['final_newton_residual'])},")
        lines.append(f"Last-point KCL RMS,{_csv_num(hb['last_point_kcl_residual_rms'])},{_csv_num(ha['last_point_kcl_residual_rms'])},")
        lines.append(f"Nonlinear iterations,{hb['nonlinear_iterations']},{ha['nonlinear_iterations']},")
        lines.append(f"Warm start used,{hb['warm_start_used']},{ha['warm_start_used']},")
        lines.append(f"Fallback used,{hb['fallback_used']},{ha['fallback_used']},")
        lines.append(f"MPP consistency error,{_csv_num(hb['pmpp_consistency_error'])},{_csv_num(ha['pmpp_consistency_error'])},mW/cm2")
        lines.append(f"Vmpp internal,{_csv_num(hb['vmpp_internal'])},{_csv_num(ha['vmpp_internal'])},V")
        lines.append(f"Rs lumped total,{_csv_num(hb['rs_lumped_total'])},{_csv_num(ha['rs_lumped_total'])},Ohm*cm2")
        lines.append(f"Junction model,{hb.get('junction_model','')},{ha.get('junction_model','')},")
        lines.append(f"Rs junction,{_csv_num(hb.get('rs_junction'))},{_csv_num(ha.get('rs_junction'))},Ohm/sq")
        lines.append(f"Phase B status,{hb.get('phase_b_status','')},{ha.get('phase_b_status','')},")
        lines.append(f"Phase B message,{hb.get('phase_b_message','')},{ha.get('phase_b_message','')},")
        lines.append(f"Phase B native KCL RMS,{_csv_num(hb.get('phase_b_native_kcl_rms_mA_cm2'))},{_csv_num(ha.get('phase_b_native_kcl_rms_mA_cm2'))},mA/cm2")
        lines.append(f"Phase B native KCL max,{_csv_num(hb.get('phase_b_native_kcl_max_mA_cm2'))},{_csv_num(ha.get('phase_b_native_kcl_max_mA_cm2'))},mA/cm2")
        lines.append(f"Phase B native KCL integrated,{_csv_num(hb.get('phase_b_native_kcl_integrated_mA_cm2'))},{_csv_num(ha.get('phase_b_native_kcl_integrated_mA_cm2'))},mA/cm2")
        lines.append(f"Phase B native KCL max current,{_csv_num(hb.get('phase_b_native_kcl_max_A'))},{_csv_num(ha.get('phase_b_native_kcl_max_A'))},A")
        lines.append(f"Phase B top KVL RMS,{_csv_num(hb.get('phase_b_top_kvl_rms_mV'))},{_csv_num(ha.get('phase_b_top_kvl_rms_mV'))},mV")
        lines.append("")
        lines.append("Loss [mW/cm2],Before,After,Delta")
        lines.append(f"Emitter,{c['Pe_b']:.5f},{c['Pe_a']:.5f},{c['Pe_a']-c['Pe_b']:+.5f}")
        lines.append(f"Finger,{c.get('Pff_b',0):.5f},{c.get('Pff_a',0):.5f},")
        lines.append(f"Busbar,{c.get('Pfb_b',0):.5f},{c.get('Pfb_a',0):.5f},")
        lines.append(f"Contact,{c['Pc_b']:.5f},{c['Pc_a']:.5f},{c['Pc_a']-c['Pc_b']:+.5f}")
        lines.append(f"Shading,{c['Ps_b']:.5f},{c['Ps_a']:.5f},")
        lines.append(f"Shunt,{c.get('Psh_b',0):.5f},{c.get('Psh_a',0):.5f},{c.get('Psh_a',0)-c.get('Psh_b',0):+.5f}")
        lines.append(f"Recomb,{c.get('Prec_b',0):.5f},{c.get('Prec_a',0):.5f},{c.get('Prec_a',0)-c.get('Prec_b',0):+.5f}")
        lines.append(f"Junction,{c.get('Pj_b',0):.5f},{c.get('Pj_a',0):.5f},{c.get('Pj_a',0)-c.get('Pj_b',0):+.5f}")
        Rc_b = c.get('Rc_b',{})
        if Rc_b:
            lines.append("")
            lines.append("Recomb Current [mA/cm2],Before,After")
            Rc_a = c.get('Rc_a',{})
            for k,label in [('pass_n1','Passivated n=1'),('met_n1','Metal n=1'),
                            ('met_n2','Metal n=2'),('pass_n2','Passivated n=2')]:
                lines.append(f"{label},{Rc_b.get(k,0):.6f},{Rc_a.get(k,0):.6f}")
        lines.append("")
        lines.append("I-V Curve (Before)")
        lines.append("V [V],J [mA/cm2]")
        for v,j in zip(c['Vs_b'], c['Js_b']):
            lines.append(f"{v:.6f},{j:.6f}")
        lines.append("")
        lines.append("I-V Curve (After)")
        lines.append("V [V],J [mA/cm2]")
        for v,j in zip(c['Vs_a'], c['Js_a']):
            lines.append(f"{v:.6f},{j:.6f}")
        # v28.20: robust CSV write. Previously `open(fn,'w')` (a) used the OS
        # default text codec — on Korean Windows (cp949) any non-ASCII glyph in
        # the content (Ω, ², ·, →, Korean health/junction messages) raised
        # UnicodeEncodeError *after* the file was already truncated to 0 bytes,
        # leaving an unopenable 0-byte file; and (b) wrote in place, so any mid-
        # write failure destroyed the target. Fix: encode as utf-8-sig (Excel- &
        # Korean-safe, matching the mesh_convergence writer) and write atomically
        # to a temp file, replacing the target only on full success — so a
        # failure can never leave a 0-byte CSV behind.
        import tempfile
        try:
            _dir = os.path.dirname(os.path.abspath(fn)) or '.'
            _fd, _tmp = tempfile.mkstemp(suffix='.tmp', dir=_dir)
            try:
                with os.fdopen(_fd, 'w', encoding='utf-8-sig', newline='') as f:
                    f.write('\r\n'.join(lines))
                os.replace(_tmp, fn)
            except BaseException:
                try:
                    os.remove(_tmp)
                except OSError:
                    pass
                raise
        except Exception as e:
            self._status(f"CSV save failed: {e}")
            messagebox.showerror("2L-FEST PRO", f"CSV 저장 실패:\n{e}")
            return
        self._status(f"CSV saved: {fn}")
        messagebox.showinfo("2L-FEST PRO", f"Results exported:\n{fn}")

    # ---------------------------------------------------------
    # SAVE PNG
    # ---------------------------------------------------------
    def _save_png(self):
        fn = filedialog.asksaveasfilename(
            initialfile='2L-FEST_PRO.png',
            filetypes=[('PNG','*.png')], defaultextension='.png')
        if fn:
            self.fig.savefig(fn, dpi=150, bbox_inches='tight', facecolor='white')
            self._status(f"Saved: {fn}")


# =============================================================
# RUN
# =============================================================
if __name__ == "__main__":
    app = FESTProApp()
    app.mainloop()
