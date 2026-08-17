# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""SpatialMap 특성화 테스트 (공간 분포 입력 계획 단위 0).

이 파일은 **새 기능을 정의하지 않는다.** `SpatialMap`(2L_FEST.py:3248)과
`_spatial_mult`(2L_FEST.py:3838)는 이미 구현되어 있으나 테스트가 하나도 없었다.
파일 로더·GUI를 붙이기 전에 **현재 동작을 먼저 고정**해서, 이후 단위에서 무엇이
회귀인지 판정할 기준을 만든다.

여기서 고정하는 규약 중 교차검증에 직결되는 두 가지:

  1. **꼭짓점 정렬(vertex-aligned)** — `linspace(0,H,ny)`이므로 `matrix[0]`은
     `y=0` 경계에, `matrix[-1]`은 `y=H` 경계에 놓인다. 픽셀 중심이 아니다.
  2. **행 방향** — `matrix[0]`이 `y=0`이다. 텍스트 파일의 첫 줄을 사람은 보통
     위쪽으로 읽으므로, Griddler와 대조할 때 상하 반전 위험이 여기서 나온다.

두 규약이 Griddler와 같은지는 **단위 3에서 판정**한다. 이 파일은 "우리 쪽이
무엇인지"만 못 박는다. 판정 결과 보정이 필요하면 보정은 로더 안에서 하고
`evaluate()`는 건드리지 않는다 — 그러면 이 테스트들이 그대로 회귀 감시로 남는다.

계획: docs/superpowers/plans/2026-08-17-spatial-map-io.md
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 핀 테스트와 같은 solve 인자 (tests/test_default_pin.py:19)
PARAMS = dict(rm=3e-6, hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)

W = 2.0   # cm — conftest._mono_geo의 cell_w/cell_h와 같은 값
H = 2.0


def _pts(*xy):
    """[(x,y), ...] -> (N,2) float array."""
    return np.asarray(xy, dtype=float)


# =============================================================================
# 1. 레지스트리·기본값
# =============================================================================

def test_spatial_targets_registry(fest):
    """대상 물성 4종 확정 (계획 §대상 물성, 2026-08-17 박사님 확정)."""
    assert fest.SPATIAL_TARGETS == ("j01", "j02", "gen", "rc")


def test_diode_params_default_none(fest):
    """맵 미지정이 기본. 이 None이 비트 동일 근거 (1)의 출발점이다."""
    dp = fest.DiodeParams()
    for which in fest.SPATIAL_TARGETS:
        assert getattr(dp, f"spatial_{which}") is None


def test_make_uniform_helper(fest):
    arr = fest.make_uniform(5)
    assert arr.shape == (5,)
    assert np.all(arr == 1.0)


# =============================================================================
# 2. evaluate() — 모드별 (FEM 없음)
# =============================================================================

def test_uniform_mode(fest):
    sm = fest.SpatialMap(mode="uniform", background=1.3)
    out = sm.evaluate(_pts((0.0, 0.0), (W, H), (0.5, 1.5)), W, H)
    assert out.shape == (3,)
    assert np.all(out == 1.3)


def test_rectangle_mode_inside_outside(fest):
    sm = fest.SpatialMap(mode="rectangle", background=1.0, feature=2.0,
                         x_min=0.5, x_max=1.5, y_min=0.5, y_max=1.5)
    out = sm.evaluate(_pts((1.0, 1.0),      # 내부
                           (0.1, 0.1),      # 외부
                           (0.5, 0.5),      # 경계 — 포함(>=, <=)
                           (1.5, 1.5)), W, H)
    assert out[0] == 2.0
    assert out[1] == 1.0
    assert out[2] == 2.0
    assert out[3] == 2.0


def test_gaussian_mode_peak_and_tail(fest):
    sm = fest.SpatialMap(mode="gaussian", background=1.0, feature=3.0,
                         cx=1.0, cy=1.0, sigma_x=0.1, sigma_y=0.1)
    out = sm.evaluate(_pts((1.0, 1.0), (1.0, 2.0)), W, H)
    assert out[0] == pytest.approx(3.0)          # 중심 = feature
    assert out[1] == pytest.approx(1.0, abs=1e-9)  # 멀리 = background


def test_checkerboard_mode_alternates(fest):
    sm = fest.SpatialMap(mode="checkerboard", background=1.0, feature=2.0,
                         cells_x=2, cells_y=2)
    # 셀 크기 1.0 x 1.0. (ix+iy)%2==0 -> feature
    out = sm.evaluate(_pts((0.5, 0.5),   # ix=0, iy=0 -> feature
                           (1.5, 0.5),   # ix=1, iy=0 -> background
                           (0.5, 1.5),   # ix=0, iy=1 -> background
                           (1.5, 1.5)), W, H)  # ix=1, iy=1 -> feature
    assert out[0] == 2.0
    assert out[1] == 1.0
    assert out[2] == 1.0
    assert out[3] == 2.0


def test_checkerboard_clamps_upper_edge(fest):
    """x=W 노드가 nx로 넘어가 IndexError가 되지 않고 마지막 셀에 들어간다."""
    sm = fest.SpatialMap(mode="checkerboard", background=1.0, feature=2.0,
                         cells_x=2, cells_y=2)
    out = sm.evaluate(_pts((W, H)), W, H)
    assert out[0] == 2.0   # ix=1, iy=1


# =============================================================================
# 3. csv 모드 — 격자 정렬·행 방향·보간 (교차검증 직결)
# =============================================================================

def test_csv_corners_are_vertex_aligned(fest):
    """꼭짓점 정렬: 행렬 네 값이 셀 네 모서리에 **정확히** 놓인다.

    픽셀 중심(cell-centered) 규약이면 이 값들이 모서리에 오지 않는다.
    """
    M = np.array([[1.0, 2.0],
                  [3.0, 4.0]])
    sm = fest.SpatialMap(mode="csv", matrix=M)
    out = sm.evaluate(_pts((0.0, 0.0),   # matrix[0][0]
                           (W, 0.0),     # matrix[0][1]
                           (0.0, H),     # matrix[1][0]
                           (W, H)), W, H)  # matrix[1][1]
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(2.0)
    assert out[2] == pytest.approx(3.0)
    assert out[3] == pytest.approx(4.0)


def test_csv_row_zero_is_y_zero(fest):
    """행 방향 고정: matrix[0]이 y=0이다.

    텍스트 파일의 첫 줄을 사람은 보통 '위쪽'으로 읽는다. Griddler가 첫 줄을
    y=H로 해석하면 맵이 상하 반전된다 — 단위 3의 판정 대상.
    시험 행렬을 **비대칭**으로 두어야 이 오류가 드러난다.
    """
    M = np.array([[1.0, 1.0],
                  [2.0, 2.0]])
    sm = fest.SpatialMap(mode="csv", matrix=M)
    out = sm.evaluate(_pts((0.5, 0.0), (0.5, H)), W, H)
    assert out[0] == pytest.approx(1.0)   # y=0  -> 첫 행
    assert out[1] == pytest.approx(2.0)   # y=H  -> 마지막 행


def test_csv_bilinear_midpoint(fest):
    """쌍선형 보간 — 중앙은 네 값의 평균."""
    M = np.array([[1.0, 2.0],
                  [3.0, 4.0]])
    sm = fest.SpatialMap(mode="csv", matrix=M)
    out = sm.evaluate(_pts((W / 2, H / 2)), W, H)
    assert out[0] == pytest.approx(2.5)


def test_csv_clips_outside_points_no_extrapolation(fest):
    """셀 밖 좌표는 clip되어 경계값을 받는다 — fill_value=None이지만 외삽 없음."""
    M = np.array([[1.0, 2.0],
                  [3.0, 4.0]])
    sm = fest.SpatialMap(mode="csv", matrix=M)
    out = sm.evaluate(_pts((-5.0, -5.0), (W + 5.0, H + 5.0)), W, H)
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(4.0)


def test_csv_non_square_matrix(fest):
    """행/열 수가 달라도 (ny, nx) 순서로 해석된다."""
    M = np.array([[1.0, 2.0, 3.0],
                  [4.0, 5.0, 6.0]])   # ny=2, nx=3
    sm = fest.SpatialMap(mode="csv", matrix=M)
    out = sm.evaluate(_pts((0.0, 0.0), (W, 0.0), (W, H)), W, H)
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(3.0)
    assert out[2] == pytest.approx(6.0)


# =============================================================================
# 4. 값 제약 — 조용히 고치지 말고 ValueError
# =============================================================================

@pytest.mark.parametrize("matrix", [
    None,
    np.array([1.0, 2.0]),               # 1D
    np.array([[1.0, 2.0]]),             # 1 x 2
    np.array([[1.0], [2.0]]),           # 2 x 1
])
def test_csv_rejects_bad_matrix_shape(fest, matrix):
    sm = fest.SpatialMap(mode="csv", matrix=matrix)
    with pytest.raises(ValueError, match="csv spatial map needs"):
        sm.evaluate(_pts((0.0, 0.0)), W, H)


@pytest.mark.parametrize("bad", [0.0, -1.0, np.nan, np.inf])
def test_rejects_non_positive_or_non_finite(fest, bad):
    """배율은 유한하고 양수여야 한다 (2L_FEST.py:3327-3328)."""
    M = np.array([[1.0, 1.0],
                  [1.0, bad]])
    sm = fest.SpatialMap(mode="csv", matrix=M)
    with pytest.raises(ValueError, match="finite and positive"):
        sm.evaluate(_pts((W, H)), W, H)


def test_rejects_non_positive_background(fest):
    sm = fest.SpatialMap(mode="uniform", background=0.0)
    with pytest.raises(ValueError, match="finite and positive"):
        sm.evaluate(_pts((0.0, 0.0)), W, H)


def test_rejects_unknown_mode(fest):
    sm = fest.SpatialMap(mode="bogus")
    with pytest.raises(ValueError, match="Unsupported spatial map mode"):
        sm.evaluate(_pts((0.0, 0.0)), W, H)


# =============================================================================
# 5. _spatial_mult — None 가드와 캐시 (비트 동일 근거 (1))
# =============================================================================

def test_spatial_mult_returns_none_when_unset(fest, make_mono):
    """맵이 없으면 배열을 만들지 않고 None을 준다 → 호출부가 곱셈을 건너뛴다.

    이것이 '맵 미지정 시 비트 동일'의 1차 근거다. all-ones 배열을 만들어
    곱하는 구조였다면 이 근거가 성립하지 않는다.
    """
    m = make_mono()
    dp = fest.DiodeParams()
    for which in fest.SPATIAL_TARGETS:
        assert m.S._spatial_mult(dp, which) is None


def test_spatial_mult_returns_node_length_array(fest, make_mono):
    m = make_mono()
    dp = fest.DiodeParams()
    dp.spatial_j01 = fest.SpatialMap(mode="uniform", background=1.7)
    arr = m.S._spatial_mult(dp, "j01")
    assert arr is not None
    assert arr.shape == (m.S.N,)
    assert np.all(arr == 1.7)


def test_spatial_mult_caches_same_object(fest, make_mono):
    """같은 spec을 다시 물으면 같은 배열 객체를 돌려준다 (노드 평가 1회)."""
    m = make_mono()
    dp = fest.DiodeParams()
    dp.spatial_gen = fest.SpatialMap(mode="uniform", background=1.1)
    a = m.S._spatial_mult(dp, "gen")
    b = m.S._spatial_mult(dp, "gen")
    assert a is b


def test_spatial_mult_evaluated_on_node_coords(fest, make_mono):
    """노드 좌표에서 평가된다 — 좌우로 갈리는 맵이 노드 x에 따라 갈린다."""
    m = make_mono()
    dp = fest.DiodeParams()
    dp.spatial_j01 = fest.SpatialMap(
        mode="rectangle", background=1.0, feature=2.0,
        x_min=0.0, x_max=m.geo.W / 2, y_min=0.0, y_max=m.geo.H)
    arr = m.S._spatial_mult(dp, "j01")
    left = m.S.pts[:, 0] <= m.geo.W / 2
    assert np.all(arr[left] == 2.0)
    assert np.all(arr[~left] == 1.0)


# =============================================================================
# 6. rc 맵의 의미 방향 — 값이 클수록 접촉이 나쁘다
# =============================================================================

def test_rc_map_multiplies_resistance_not_conductance(fest, make_mono):
    """rc 맵은 **접촉저항 R**을 곱한다 → 컨덕턴스 Gc는 나뉜다.

    예: 0.5 = 접촉저항 절반(잘 눌린 영역) → Gc 2배
        2.0 = 접촉저항 두 배(덜 눌린 영역) → Gc 절반

    4종 중 rc만 의미가 반대라 GUI 라벨에서 오해가 나기 쉽다(단위 4).
    """
    base = make_mono()
    dp0 = fest.DiodeParams()
    base.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                  PARAMS["Rs"], PARAMS["cf"], dp0)
    Gc0 = base.S._Gc.copy()

    worse = make_mono()
    dp2 = fest.DiodeParams()
    dp2.spatial_rc = fest.SpatialMap(mode="uniform", background=2.0)
    worse.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                   PARAMS["Rs"], PARAMS["cf"], dp2)
    Gc2 = worse.S._Gc

    ism = base.S.ism
    assert np.any(ism), "접촉 노드가 있어야 의미 있는 비교다"
    # 배율 2.0 -> 접촉저항 2배 -> 컨덕턴스 절반
    assert np.allclose(Gc2[ism], Gc0[ism] / 2.0, rtol=0, atol=0)
    # 접촉 노드 밖은 건드리지 않는다
    assert np.array_equal(Gc2[~ism], Gc0[~ism])


# =============================================================================
# 7. 맵 미지정 비트 동일 — 해제 경로 회귀 가드
# =============================================================================

def _solve_current(fest, m, dp, Vb):
    res = m.S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                    PARAMS["Rs"], Vb, PARAMS["cf"], dp, "tandem")
    return float(m.S.cell_current(res, dp))


def test_clearing_map_to_none_restores_bit_identical_result(fest, make_mono):
    """맵을 걸었다 **None으로 해제**하면 원래 결과로 비트 단위 복귀한다.

    GUI의 Clear 경로가 의존하는 성질이다(계획 단위 4). 해제를
    `SpatialMap(mode='uniform')`으로 구현하면 값은 같더라도 None 가드를
    우회하므로, 해제는 반드시 None이어야 한다.
    """
    m = make_mono()
    dp = fest.DiodeParams()
    Vb = 0.85 * dp.expected_voc()[2]

    J0 = _solve_current(fest, m, dp, Vb)

    dp.spatial_j01 = fest.SpatialMap(mode="uniform", background=2.0)
    J_mapped = _solve_current(fest, m, dp, Vb)

    dp.spatial_j01 = None
    J_restored = _solve_current(fest, m, dp, Vb)

    assert J_mapped != J0, "맵이 실제로 결과를 바꿔야 이 테스트가 의미 있다"
    assert J_restored == J0   # 비트 동일


def test_j01_map_raises_recombination_and_lowers_current(fest, make_mono):
    """물리 방향 확인: J01 배율↑ = 재결합↑ = 전류↓ (바이어스 하에서)."""
    m = make_mono()
    dp = fest.DiodeParams()
    Vb = 0.85 * dp.expected_voc()[2]

    J0 = _solve_current(fest, m, dp, Vb)
    dp.spatial_j01 = fest.SpatialMap(mode="uniform", background=10.0)
    J_hi = _solve_current(fest, m, dp, Vb)

    assert J_hi < J0


# =============================================================================
# 8. 캐시 무효화 — 내용 기반이어야 한다 (계획 단위 1)
# =============================================================================
#
# `_build`의 캐시 태그 `_sm_tag`(2L_FEST.py:3897-3901)는 원래 맵의 **id()**로
# 변경을 감지했다. 앱이 맵을 생성·소멸시킨 적이 없어 지금까지 드러나지 않았으나,
# 파일 로더·GUI가 생기면 두 경로로 깨진다:
#
#   (a) 같은 맵 객체를 **제자리 수정** — id 불변 → 태그 불변 → _Gc 재빌드 안 됨.
#       GUI가 target당 맵 하나를 두고 필드만 갱신하면 **100 % 발생**한다.
#   (b) 맵 A 해제 후 B 생성 — CPython이 A의 주소를 B에 재사용하면 역시 태그 불변.
#
# `_sm_tag`는 `_build` 안의 지역 변수라 직접 못 읽는다. 그래서 태그의 재료인
# `SpatialMap.content_key()` 계약을 결정론적으로 검사하고(§8-1), 결과에 미치는
# 영향은 `_Gc`로 확인한다(§8-2).

# --- 8-1. content_key() 계약: 같은 내용 → 같은 키, 다른 내용 → 다른 키 --------

def test_content_key_equal_for_equal_content(fest):
    """서로 다른 객체라도 내용이 같으면 키가 같다.

    id() 기반 태그는 이 성질을 **결정론적으로** 위반한다 — 별개 객체는 항상
    다른 id를 갖기 때문이다. 정정 전에는 이 테스트가 실패해야 한다.
    """
    a = fest.SpatialMap(mode="uniform", background=1.5)
    b = fest.SpatialMap(mode="uniform", background=1.5)
    assert a is not b
    assert a.content_key() == b.content_key()


def test_content_key_equal_for_equal_matrix_distinct_arrays(fest):
    """행렬도 내용으로 비교한다 — 배열 객체가 달라도 값이 같으면 같은 키."""
    M1 = np.array([[1.0, 2.0], [3.0, 4.0]])
    M2 = np.array([[1.0, 2.0], [3.0, 4.0]])
    a = fest.SpatialMap(mode="csv", matrix=M1)
    b = fest.SpatialMap(mode="csv", matrix=M2)
    assert M1 is not M2
    assert a.content_key() == b.content_key()


def test_content_key_differs_on_matrix_value(fest):
    a = fest.SpatialMap(mode="csv", matrix=np.array([[1.0, 2.0], [3.0, 4.0]]))
    b = fest.SpatialMap(mode="csv", matrix=np.array([[1.0, 2.0], [3.0, 4.5]]))
    assert a.content_key() != b.content_key()


def test_content_key_differs_on_matrix_shape(fest):
    """같은 값의 나열이라도 형상이 다르면 다른 맵이다."""
    a = fest.SpatialMap(mode="csv", matrix=np.array([[1.0, 2.0], [3.0, 4.0]]))
    b = fest.SpatialMap(mode="csv",
                        matrix=np.array([[1.0, 2.0, 3.0, 4.0],
                                         [1.0, 2.0, 3.0, 4.0]]))
    assert a.content_key() != b.content_key()


@pytest.mark.parametrize("field,value", [
    ("mode", "rectangle"),
    ("background", 9.0),
    ("feature", 9.0),
    ("x_min", 9.0), ("x_max", 9.0), ("y_min", 9.0), ("y_max", 9.0),
    ("cx", 9.0), ("cy", 9.0), ("sigma_x", 9.0), ("sigma_y", 9.0),
    ("cells_x", 9), ("cells_y", 9),
])
def test_content_key_differs_on_each_field(fest, field, value):
    """어떤 필드를 바꿔도 키가 달라져야 한다 — 빠뜨린 필드가 있으면 잡힌다."""
    a = fest.SpatialMap(mode="uniform")
    b = fest.SpatialMap(mode="uniform")
    setattr(b, field, value)
    assert a.content_key() != b.content_key()


def test_content_key_is_hashable(fest):
    """`_spatial_cache`의 dict 키로 쓰이므로 해시 가능해야 한다."""
    sm = fest.SpatialMap(mode="csv", matrix=np.array([[1.0, 2.0], [3.0, 4.0]]))
    assert hash(sm.content_key()) == hash(sm.content_key())


# --- 8-2. 결과에 미치는 영향 --------------------------------------------------

def _build(m, dp):
    m.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
               PARAMS["Rs"], PARAMS["cf"], dp)
    return m.S._Gc[m.S.ism].copy()


def test_inplace_map_edit_invalidates_build_cache(fest, make_mono):
    """맵을 **제자리 수정**하면 _Gc가 재빌드되어야 한다.

    id() 태그에서는 결정론적으로 실패한다(id가 안 변하므로 캐시 적중).
    GUI가 target당 맵 하나를 두고 필드만 갱신하는 구조면 항상 이 경로다.
    """
    m = make_mono()
    dp = fest.DiodeParams()
    sm = fest.SpatialMap(mode="uniform", background=1.0)
    dp.spatial_rc = sm

    g1 = _build(m, dp)
    sm.background = 2.0            # 제자리 수정 — id 불변
    g2 = _build(m, dp)

    # rc 배율 2배 -> 접촉저항 2배 -> Gc 절반
    assert np.allclose(g2, g1 / 2.0, rtol=0, atol=0)


def test_matrix_inplace_edit_invalidates_build_cache(fest, make_mono):
    """행렬 내용만 바꿔치기해도 재빌드되어야 한다 (파일 재로드 경로)."""
    m = make_mono()
    dp = fest.DiodeParams()
    sm = fest.SpatialMap(mode="csv", matrix=np.ones((2, 2)))
    dp.spatial_rc = sm

    g1 = _build(m, dp)
    sm.matrix = np.full((2, 2), 2.0)
    g2 = _build(m, dp)

    assert np.allclose(g2, g1 / 2.0, rtol=0, atol=0)


def test_map_replacement_after_free_invalidates_cache(fest, make_mono):
    """맵 A 해제 → B 생성. A의 주소가 재사용돼도 B가 반영되어야 한다.

    주소 재사용은 CPython 구현에 의존하므로 이 테스트만으로는 정정 전 실패가
    보장되지 않는다(재사용이 안 일어나면 그냥 통과한다). 결정론적 재현은
    위의 제자리 수정 테스트와 content_key 계약이 담당하고, 이 테스트는
    GUI 실사용 시나리오에 대한 회귀 가드다.
    """
    m = make_mono()
    dp = fest.DiodeParams()

    A = fest.SpatialMap(mode="uniform", background=1.0)
    dp.spatial_rc = A
    g1 = _build(m, dp)

    dp.spatial_rc = None
    del A
    B = fest.SpatialMap(mode="uniform", background=2.0)
    dp.spatial_rc = B
    g2 = _build(m, dp)

    assert np.allclose(g2, g1 / 2.0, rtol=0, atol=0)


def test_spatial_mult_cache_follows_content(fest, make_mono):
    """`_spatial_mult`의 배열 캐시도 내용을 따라야 한다.

    이 캐시는 `(id(dp), which, id(spec))`을 키로 썼다 — 같은 결함이다.
    """
    m = make_mono()
    dp = fest.DiodeParams()
    sm = fest.SpatialMap(mode="uniform", background=1.0)
    dp.spatial_j01 = sm

    a = m.S._spatial_mult(dp, "j01")
    assert np.all(a == 1.0)

    sm.background = 3.0
    b = m.S._spatial_mult(dp, "j01")
    assert np.all(b == 3.0)


def test_unchanged_build_still_short_circuits(fest, make_mono):
    """바뀐 게 없으면 여전히 캐시로 빠져나가야 한다 (성능 회귀 방지).

    `_build`는 재빌드 시 `self._Gc = np.zeros(N)`으로 **새 객체**를 만든다.
    따라서 같은 객체가 유지되면 조기 반환이 일어났다는 뜻이다.
    """
    m = make_mono()
    dp = fest.DiodeParams()
    dp.spatial_rc = fest.SpatialMap(mode="uniform", background=1.5)

    _build(m, dp)
    first = m.S._Gc
    _build(m, dp)
    assert m.S._Gc is first


def test_no_map_build_still_short_circuits(fest, make_mono):
    """맵이 없을 때도 캐시 거동이 그대로여야 한다 (비트 동일 경로 불변)."""
    m = make_mono()
    dp = fest.DiodeParams()

    _build(m, dp)
    first = m.S._Gc
    _build(m, dp)
    assert m.S._Gc is first


# =============================================================================
# 9. txt/csv 로더 (계획 단위 2)
# =============================================================================
#
# 규약: **txt/csv는 절대값이다.** 읽은 수가 그대로 배율이 된다 — 정규화하지
# 않는다(이미지는 2단계에서 평균 1 정규화, 근거 매뉴얼 §3.1). 같은 파일을
# Griddler에도 넣어 교차검증할 수 있어야 하므로 여기서 값을 건드리면 안 된다.
#
# 값 제약은 **파일을 읽는 시점에** 검사한다. evaluate()가 솔버 실행 중에
# 던지면 사용자는 어느 파일의 어느 칸이 문제인지 알 수 없다.

def _write(tmp_path, text, name="map.txt"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


# --- 9-1. 정상 경로 -----------------------------------------------------------

def test_loader_reads_comma_matrix(fest, tmp_path):
    path = _write(tmp_path, "1.0,2.0\n3.0,4.0\n")
    sm = fest.load_spatial_map_txt(path)
    assert isinstance(sm, fest.SpatialMap)
    assert sm.mode == "csv"
    assert np.array_equal(sm.matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_loader_reads_whitespace_matrix(fest, tmp_path):
    path = _write(tmp_path, "1.0 2.0\n3.0 4.0\n")
    sm = fest.load_spatial_map_txt(path)
    assert np.array_equal(sm.matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_loader_reads_tab_matrix(fest, tmp_path):
    path = _write(tmp_path, "1.0\t2.0\n3.0\t4.0\n")
    sm = fest.load_spatial_map_txt(path)
    assert np.array_equal(sm.matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_loader_explicit_delimiter_override(fest, tmp_path):
    path = _write(tmp_path, "1.0;2.0\n3.0;4.0\n")
    sm = fest.load_spatial_map_txt(path, delimiter=";")
    assert np.array_equal(sm.matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_loader_keeps_absolute_values_no_normalization(fest, tmp_path):
    """**절대값 규약** — 평균이 1이 아니어도 그대로 둔다.

    이미지(2단계)만 평균 1로 정규화한다. 여기서 정규화하면 같은 파일을
    Griddler에 넣었을 때와 값이 달라져 교차검증이 무의미해진다.
    """
    path = _write(tmp_path, "10,20\n30,40\n")
    sm = fest.load_spatial_map_txt(path)
    assert np.array_equal(sm.matrix, np.array([[10.0, 20.0], [30.0, 40.0]]))
    assert sm.matrix.mean() == pytest.approx(25.0)   # 1로 정규화되지 않았다


def test_loader_non_square_shape_is_ny_nx(fest, tmp_path):
    """행이 y, 열이 x — evaluate()의 (ny, nx) 해석과 일치해야 한다."""
    path = _write(tmp_path, "1,2,3\n4,5,6\n")
    sm = fest.load_spatial_map_txt(path)
    assert sm.matrix.shape == (2, 3)
    out = sm.evaluate(_pts((0.0, 0.0), (W, 0.0), (W, H)), W, H)
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(3.0)
    assert out[2] == pytest.approx(6.0)


def test_loader_first_row_is_y_zero(fest, tmp_path):
    """파일 첫 줄 = matrix[0] = y=0. 단위 3 Griddler 대조의 기준."""
    path = _write(tmp_path, "1,1\n2,2\n")
    sm = fest.load_spatial_map_txt(path)
    out = sm.evaluate(_pts((0.5, 0.0), (0.5, H)), W, H)
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(2.0)


def test_loader_tolerates_bom_blank_lines_crlf_and_comments(fest, tmp_path):
    """BOM·빈 줄·CRLF·'#' 주석은 데이터가 아니다 (v28.20 utf-8-sig 전례)."""
    p = tmp_path / "m.txt"
    p.write_bytes("# 주석\r\n1,2\r\n\r\n3,4\r\n\r\n".encode("utf-8-sig"))
    sm = fest.load_spatial_map_txt(str(p))
    assert np.array_equal(sm.matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_loader_result_equals_in_memory_map(fest, tmp_path):
    """파일로 만든 맵과 직접 만든 맵이 **내용상 같다** (content_key 일치)."""
    path = _write(tmp_path, "1,2\n3,4\n")
    a = fest.load_spatial_map_txt(path)
    b = fest.SpatialMap(mode="csv", matrix=np.array([[1.0, 2.0], [3.0, 4.0]]))
    assert a.content_key() == b.content_key()


def test_loader_report_records_provenance(fest, tmp_path):
    """DXF 로더의 report 관용구 — 무엇을 어떻게 읽었는지 남긴다."""
    path = _write(tmp_path, "1,2\n3,4\n")
    sm = fest.load_spatial_map_txt(path)
    rep = sm.load_report
    assert rep["path"] == path
    assert rep["shape"] == (2, 2)
    assert rep["delimiter"] == ","
    assert rep["warnings"] == []


def test_loader_warns_on_large_matrix_but_loads(fest, tmp_path):
    """큰 행렬은 거부하지 않고 보간 비용만 알린다."""
    n = fest.SPATIAL_MAP_LARGE_DIM + 1
    row = ",".join(["1.0"] * n)
    path = _write(tmp_path, "\n".join([row] * 2) + "\n")
    sm = fest.load_spatial_map_txt(path)
    assert sm.matrix.shape == (2, n)
    assert any("보간" in w or "large" in w.lower() for w in sm.load_report["warnings"])


# --- 9-2. 형식 오류 -----------------------------------------------------------

def test_loader_rejects_missing_file(fest, tmp_path):
    with pytest.raises(FileNotFoundError):
        fest.load_spatial_map_txt(str(tmp_path / "nope.txt"))


def test_loader_rejects_empty_file(fest, tmp_path):
    path = _write(tmp_path, "\n\n")
    with pytest.raises(ValueError, match="비어"):
        fest.load_spatial_map_txt(path)


def test_loader_rejects_ragged_rows(fest, tmp_path):
    path = _write(tmp_path, "1,2\n3,4,5\n")
    with pytest.raises(ValueError) as exc:
        fest.load_spatial_map_txt(path)
    msg = str(exc.value)
    assert "2" in msg          # 문제가 된 데이터 행
    assert "3" in msg and "2" in msg   # 열 개수 불일치(3 vs 2)


def test_loader_rejects_non_numeric_token(fest, tmp_path):
    path = _write(tmp_path, "1,2\n3,abc\n")
    with pytest.raises(ValueError) as exc:
        fest.load_spatial_map_txt(path)
    assert "abc" in str(exc.value)


@pytest.mark.parametrize("text", [
    "1.0\n",              # 1 x 1
    "1.0,2.0\n",          # 1 x 2
    "1.0\n2.0\n",         # 2 x 1
])
def test_loader_rejects_too_small(fest, tmp_path, text):
    """evaluate()가 요구하는 최소 2x2를 로드 시점에 먼저 막는다."""
    path = _write(tmp_path, text)
    with pytest.raises(ValueError, match="2x2"):
        fest.load_spatial_map_txt(path)


# --- 9-3. 값 제약 — 조용히 고치지 말고 거부 -----------------------------------

@pytest.mark.parametrize("bad,label", [
    ("0", "0"),
    ("0.0", "0"),
    ("-1.5", "-1.5"),
    ("nan", "nan"),
    ("inf", "inf"),
    ("-inf", "inf"),
])
def test_loader_rejects_non_positive_or_non_finite(fest, tmp_path, bad, label):
    """0·음수·NaN·inf는 거부한다. 클램프·치환하지 않는다."""
    path = _write(tmp_path, f"1.0,2.0\n3.0,{bad}\n")
    with pytest.raises(ValueError) as exc:
        fest.load_spatial_map_txt(path)
    msg = str(exc.value)
    assert "2" in msg              # 데이터 행 2
    assert label.lower() in msg.lower()


def test_loader_error_names_the_file(fest, tmp_path):
    """오류 메시지에 경로가 있어야 어느 파일인지 안다."""
    path = _write(tmp_path, "1,2\n3,-1\n")
    with pytest.raises(ValueError) as exc:
        fest.load_spatial_map_txt(path)
    assert os.path.basename(path) in str(exc.value)


def test_loader_rejects_before_solver_runs(fest, tmp_path, make_mono):
    """검사는 **로드 시점**에 끝난다 — 솔버에 들어가서 터지지 않는다."""
    path = _write(tmp_path, "1,2\n3,0\n")
    with pytest.raises(ValueError):
        fest.load_spatial_map_txt(path)
    # 맵이 만들어지지 않았으므로 dp는 여전히 무맵이고 솔버는 정상이다
    m = make_mono()
    dp = fest.DiodeParams()
    assert m.S._spatial_mult(dp, "rc") is None
