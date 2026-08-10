# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Phase 3 §3a — preset 데이터 + UI 모듈 import 안전성 테스트."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from front_electrode import PRESETS, MAINSTREAM_PRESETS, get_preset  # noqa: E402


def test_presets_structure():
    assert set(PRESETS) >= {"M10_MBB_2025", "M10_SMBB_2025", "M10_Custom", "M10_0BB_future"}
    for name, p in PRESETS.items():
        assert "finger_width_um" in p, f"{name}: finger_width_um 누락"
        assert "finger_pitch_mm" in p, f"{name}: finger_pitch_mm 누락"
        assert "busbar_number" in p, f"{name}: busbar_number 누락"
        assert p["cell_size_mm"] == (182.0, 182.0), f"{name}: M10 규격 아님"


def test_0bb_separated_from_mainstream():
    # 0BB는 mainstream preset과 섞지 말 것
    assert "M10_0BB_future" not in MAINSTREAM_PRESETS
    assert "M10_MBB_2025" in MAINSTREAM_PRESETS
    assert "M10_SMBB_2025" in MAINSTREAM_PRESETS
    assert PRESETS["M10_0BB_future"]["busbar_number"] == [0]


def test_engineering_vs_sourced_labeled():
    # 근거 못 찾은 값은 kind="engineering"으로 명시돼야 함
    mbb = PRESETS["M10_MBB_2025"]
    assert mbb["busbar_width_mm"]["kind"] == "engineering"   # 인쇄 MBB 폭 ITRPV 미제공
    assert mbb["finger_pitch_mm"]["kind"] == "engineering"   # pitch ITRPV 미제공
    smbb = PRESETS["M10_SMBB_2025"]
    assert smbb["busbar_width_mm"]["kind"] == "sourced"      # SMBB wire 유효폭 출처 있음
    assert "src" in smbb["finger_width_um"]


def test_get_preset_deepcopy():
    a = get_preset("M10_SMBB_2025")
    b = get_preset("M10_SMBB_2025")
    a["busbar_number"].append(999)
    assert 999 not in b["busbar_number"], "get_preset가 깊은 복사가 아님"


def test_ui_module_imports():
    # ui.py는 GUI에서만 쓰지만 top-level import는 안전해야 함(ctk는 함수 내 지연 import)
    import front_electrode.ui as ui
    assert hasattr(ui, "open_optimizer_window")
