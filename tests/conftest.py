# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Headless test infrastructure for GEDO (Phase 0).

Loads the single-file GUI application ``2L_FEST.py`` as a
plain module named ``fest`` WITHOUT a display or a real Tk/CustomTkinter
install, so the physics core (CellGeometry / generate_mesh / classify_nodes /
FESTSolver) can be unit-tested.

Strategy (order matters, all done before importing the app):
  1. Force matplotlib to the Agg backend and neuter ``matplotlib.use`` so the
     app's own ``matplotlib.use('TkAgg')`` at import becomes a no-op.
  2. Inject mock modules for tkinter (+ filedialog/messagebox), customtkinter,
     and matplotlib.backends.backend_tkagg. Only ``customtkinter.CTk`` needs to
     be a *real* subclassable class (``class FESTProApp(ctk.CTk)`` runs at
     import); everything else is a permissive MagicMock.
  3. importlib-load the app file as ``fest`` (this builds the default 9x9mm
     mesh once, ~5 s — expected).

Fixtures build small solvers (monofacial ~3.8k nodes, bifacial) for fast tests.
"""
import os
import sys
import types
import importlib.util
from unittest.mock import MagicMock

import pytest

# --- 1. matplotlib: Agg + no-op use() ---------------------------------------
import matplotlib
matplotlib.use("Agg", force=True)
matplotlib.use = lambda *a, **k: None  # app's matplotlib.use('TkAgg') -> no-op


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: 느린 M10 핀(약 17분)")
    config.addinivalue_line("markers", "bgrade: B등급(샘플링 변경) 허용오차 핀")


# --- 비트-핀 스택 게이트 (v28.46) --------------------------------------------
# RTOL=1e-8짜리 비트 보존 핀(test_default_pin / test_legacy_pin)은 값이 **캡처된
# 인터프리터·BLAS·희소솔버 조합**에서만 성립한다. 다른 스택에서는 SuperLU/BLAS
# 차이만으로 상대 ~1e-6이 떠서 항상 빨간불이 되고, 그러면 **진짜 물리 회귀와
# 환경 차이를 구분할 수 없다** — 이 저장소가 계속 경계해 온 실패 유형이다.
#
# 그래서 스택이 다르면 xfail(strict=False)로 낮추되 **이유를 명시**한다.
# 핀 스택에서는 그대로 strict fail이므로 회귀 감시 능력은 유지된다.
# 새 스택으로 옮겨 값을 다시 캡처했다면 PINNED_STACK을 갱신할 것.
#
# ⚠ **아래 3종은 비트 재현의 필요조건이지 충분조건이 아니다.** (2026-08-17 실증)
#   맥북(aarch64/darwin)에서 python·numpy·scipy를 아래 값과 완전히 일치시킨 venv를
#   만들어 게이트를 통과시켰는데도 핀 2건이 값 불일치로 실패했다.
#     test_default_pin PINS[1]  상대 1.70e-7      (PINS[0] Vb=0은 통과)
#     test_legacy_pin  PINS[1]  상대 9.75e-7      (PINS[0] Vb=0은 통과)
#   원인은 **이 dict가 기록하지 않는 두 축**이었다 (2026-08-18 규명):
#     · 아키텍처   원 캡처 x86-64(AMD64)  vs  맥북 aarch64  — 벡터화·FMA가 다름
#     · numpy BLAS 원 캡처 scipy-openblas 0.3.31.dev  vs  맥북 Apple Accelerate
#   둘 다 부동소수점 누적 순서를 바꾸므로 상대 1e-7~1e-6이 뜨는 것이 정상이다.
#
#   원 캡처 머신 전체 환경과 맥북 대조표는 docs/WORKLOG.md §1-1-a에 있다.
#   **핀을 재캡처할 때는 OS·아키텍처·numpy/scipy BLAS 백엔드까지 함께 기록할 것.**
#   버전 3종만 적으면 다음 사람이 같은 실험을 반복하게 된다(실제로 반복됐다).
PINNED_STACK = {"python": "3.14.3", "numpy": "2.4.3", "scipy": "1.17.1"}


def _current_stack():
    import numpy
    import scipy
    return {
        "python": "%d.%d.%d" % sys.version_info[:3],
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
    }


def stack_mismatch():
    """핀 캡처 스택과 다르면 '무엇이 다른지' 문자열, 같으면 None."""
    cur = _current_stack()
    diff = [f"{k} {PINNED_STACK[k]}→{cur[k]}" for k in PINNED_STACK
            if cur[k] != PINNED_STACK[k]]
    return ", ".join(diff) if diff else None


@pytest.fixture(scope="session")
def bit_pin_gate():
    """비트 핀 테스트가 스택 불일치 시 xfail로 낮추도록 하는 게이트."""
    return stack_mismatch()


# --- 2. mock GUI modules -----------------------------------------------------
class _DummyCTk:
    """Real, subclassable stand-in for customtkinter.CTk.

    ``class FESTProApp(ctk.CTk)`` executes at import time and needs a genuine
    base class; the app is never instantiated in headless tests so __init__ is
    a no-op.
    """

    def __init__(self, *args, **kwargs):
        pass


def _install_gui_mocks():
    ctk = MagicMock(name="customtkinter")
    ctk.CTk = _DummyCTk
    sys.modules["customtkinter"] = ctk

    tk = MagicMock(name="tkinter")
    filedialog = MagicMock(name="tkinter.filedialog")
    messagebox = MagicMock(name="tkinter.messagebox")
    tk.filedialog = filedialog
    tk.messagebox = messagebox
    sys.modules["tkinter"] = tk
    sys.modules["tkinter.filedialog"] = filedialog
    sys.modules["tkinter.messagebox"] = messagebox

    tkagg = MagicMock(name="matplotlib.backends.backend_tkagg")
    sys.modules["matplotlib.backends.backend_tkagg"] = tkagg


# --- 3. load the app as `fest` ----------------------------------------------
_APP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "2L_FEST.py",
)


def _load_fest():
    _install_gui_mocks()
    spec = importlib.util.spec_from_file_location("fest", _APP_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["fest"] = module
    try:
        spec.loader.exec_module(module)
    except SystemExit:
        # app calls exit(1) only if customtkinter import fails; mocked here so
        # this should not trigger, but guard anyway.
        pass
    return module


@pytest.fixture(scope="session")
def fest():
    """The GEDO application loaded headlessly as a module."""
    return _load_fest()


def _build_solver(fest, geo):
    pts, tri = fest.generate_mesh(geo, axis_segments_override=36)
    isf, isb, isp, ism, isrm, isrp = fest.classify_nodes(pts, geo)
    S = fest.FESTSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)
    return types.SimpleNamespace(
        geo=geo, pts=pts, tri=tri,
        isf=isf, isb=isb, isp=isp, ism=ism, isrm=isrm, isrp=isrp,
        S=S,
    )


def _mono_geo(fest):
    return fest.CellGeometry(
        cell_w=2.0, cell_h=2.0,
        front=fest.GridDesign(n_fingers=8, n_busbars=1,
                              w_finger=50e-4, w_busbar=600e-4),
    )


def _bifacial_geo(fest):
    return fest.CellGeometry(
        cell_w=2.0, cell_h=2.0,
        front=fest.GridDesign(n_fingers=8, n_busbars=1,
                              w_finger=50e-4, w_busbar=600e-4),
        rear=fest.GridDesign(n_fingers=6, n_busbars=1,
                             w_finger=80e-4, w_busbar=600e-4),
    )


@pytest.fixture(scope="session")
def mono(fest):
    """Small full-area (monofacial) cell: 2x2mm, 8F+1BB, ~3.8k nodes."""
    return _build_solver(fest, _mono_geo(fest))


@pytest.fixture(scope="session")
def bifacial(fest):
    """Small bifacial cell: same front + patterned rear (6F+1BB)."""
    return _build_solver(fest, _bifacial_geo(fest))


@pytest.fixture
def make_mono(fest):
    """Factory: build a FRESH monofacial solver (no warm-start history).

    Pin tests need a clean solver so results are independent of test order.
    """
    return lambda: _build_solver(fest, _mono_geo(fest))


@pytest.fixture
def make_bifacial(fest):
    """Factory: build a FRESH bifacial solver (no warm-start history)."""
    return lambda: _build_solver(fest, _bifacial_geo(fest))
