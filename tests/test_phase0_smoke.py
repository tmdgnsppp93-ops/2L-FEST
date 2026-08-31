# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Phase 0 smoke test: verify the headless import + fixtures work.

Not a physics test — just proves the test infrastructure (conftest) can load
the app without a display and build both a monofacial and a bifacial solver.
"""


def test_gedos_imports(gedos):
    assert hasattr(gedos, "GEDOSSolver")
    assert hasattr(gedos, "generate_mesh")
    assert hasattr(gedos, "classify_nodes")
    assert hasattr(gedos, "CellGeometry")
    assert hasattr(gedos, "GridDesign")
    assert hasattr(gedos, "DiodeParams")


def test_mono_fixture(mono):
    n = len(mono.pts)
    # spec target ~3.8k nodes for 2x2mm / 8F+1BB / axis_segments_override=36
    assert 2500 < n < 5500, f"unexpected mono node count: {n}"
    assert mono.S is not None
    assert mono.geo.rear_mode == "full_area"


def test_bifacial_fixture(bifacial):
    n = len(bifacial.pts)
    assert 2500 < n < 6500, f"unexpected bifacial node count: {n}"
    assert bifacial.S is not None
    assert bifacial.geo.rear_mode == "bifacial"
    assert bifacial.isrm is not None and bifacial.isrp is not None
