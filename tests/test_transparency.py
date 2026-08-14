# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Metal Optical Transparency 테스트.

정의(Manual v7.0 §2.7): T = 1 − optical_width/physical_width, 기본 0.
physical → contact area / 금속 저항, optical → shading.

순수 함수는 FEM 없이 즉시 검증하고, 엔진 배선만 20mm 소셀로 확인한다
(tests/test_optimizer.py:96-106의 AX/NPTS 관용구와 동일).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AX = 36
NPTS = 6


def test_optical_widths_identity_at_zero(fest):
    """T=0이면 입력 폭을 그대로 돌려준다 — 비트 동일의 근거."""
    g = fest.GridDesign()
    assert g.optical_transparency_f == 0.0
    assert g.optical_transparency_b == 0.0
    w_f, w_b = 50e-4, 200e-4
    assert g.optical_widths(w_f, w_b) == (w_f, w_b)


def test_optical_widths_scales_each_side(fest):
    """finger와 busbar에 각각 다른 T가 걸린다."""
    g = fest.GridDesign(optical_transparency_f=0.3, optical_transparency_b=0.5)
    of, ob = g.optical_widths(100e-4, 200e-4)
    assert of == pytest.approx(70e-4)
    assert ob == pytest.approx(100e-4)


def test_transparency_range_validation(fest):
    """T<0 과 T>=1 은 ValueError. T=1은 광학 폭 0이라 무의미하다."""
    with pytest.raises(ValueError, match="optical_transparency_f"):
        fest.GridDesign(optical_transparency_f=-0.1)
    with pytest.raises(ValueError, match="optical_transparency_b"):
        fest.GridDesign(optical_transparency_b=1.0)
    with pytest.raises(ValueError, match="optical_transparency_b"):
        fest.GridDesign(optical_transparency_b=1.5)
    # 경계값은 통과해야 한다
    fest.GridDesign(optical_transparency_f=0.0, optical_transparency_b=0.999)


def test_optical_shading_fraction_matches_physical_at_zero(fest):
    """T=0에서 optical_shading_fraction == shading_fraction (비트 동일)."""
    geo = fest.CellGeometry(cell_w=2.0, cell_h=2.0,
                            front=fest.GridDesign(n_fingers=4, n_busbars=2))
    assert geo.optical_shading_fraction() == geo.shading_fraction()


def test_optical_shading_fraction_less_when_transparent(fest):
    """T>0이면 광학 shading이 물리 shading보다 작다."""
    geo = fest.CellGeometry(
        cell_w=2.0, cell_h=2.0,
        front=fest.GridDesign(n_fingers=4, n_busbars=2,
                              optical_transparency_f=0.4,
                              optical_transparency_b=0.4))
    assert geo.optical_shading_fraction() < geo.shading_fraction()
