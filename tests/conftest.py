"""Headless test infrastructure for 2L-FEST (Phase 0).

Loads the single-file GUI application ``2L_FEST_v28_18_wf_wired.py`` as a
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
    "2L_FEST_v28_18_wf_wired.py",
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
    """The 2L-FEST application loaded headlessly as a module."""
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
