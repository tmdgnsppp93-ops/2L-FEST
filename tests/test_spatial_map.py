# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""SpatialMap 특성화 테스트 (공간 분포 입력 계획 단위 0).

이 파일은 **새 기능을 정의하지 않는다.** `SpatialMap`(GEDOS.py:3248)과
`_spatial_mult`(GEDOS.py:3838)는 이미 구현되어 있으나 테스트가 하나도 없었다.
파일 로더·GUI를 붙이기 전에 **현재 동작을 먼저 고정**해서, 이후 단위에서 무엇이
회귀인지 판정할 기준을 만든다.

여기서 고정하는 규약 중 교차검증에 직결되는 두 가지:

  1. **꼭짓점 정렬(vertex-aligned)** — `linspace(0,H,ny)`이므로 `matrix[0]`은
     `y=0` 경계에, `matrix[-1]`은 `y=H` 경계에 놓인다. 픽셀 중심이 아니다.
  2. **행 방향** — `matrix[0]`이 `y=0`이다. 텍스트 파일의 첫 줄을 사람은 보통
     위쪽으로 읽으므로, Griddler와 대조할 때 상하 반전 위험이 여기서 나온다.

두 규약이 Griddler와 같은지는 **대조하지 못했다** — 무료판에 공간 분포 입력
기능이 없다(PRO 전용, 2026-08-18 확인). 그래서 단위 3에서 **자체 규약으로 확정
선언**했다: `docs/spatial_map_convention.md`. 이 파일은 그 규약의 회귀 감시다.

PRO를 확보해 대조한 결과가 어긋나면 **보정은 로더 안에서** 하고 `evaluate()`는
건드리지 않는다 — 그러면 이 테스트들이 그대로 회귀 감시로 남는다. §10이 대조
절차서의 기준값을 코드에 묶어 둔다.

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

def test_spatial_targets_registry(gedos):
    """대상 물성 확정 — 4종(2026-08-17 박사님 확정) + `rsh`(v28.62) + `rcj`(v28.66).

    새 대상은 **끝에 붙인다.** 순서가 GUI 행 순서이자 `active_spatial_maps()`의
    반환 순서라, 중간에 끼우면 그 순서에 기대는 것들이 조용히 어긋난다.

    ⚠ `rcj`를 `rc` 옆에 두고 싶은 유혹이 있다(이름도 의미도 이웃이다). 그렇게
    하지 않는다 — 논리적 이웃이라는 이유로 재배열하는 것이 정확히 이 규약이
    막는 행위다. `rsh`가 j01/j02의 논리적 이웃인데도 끝에 붙은 것과 같다.
    """
    assert gedos.SPATIAL_TARGETS == ("j01", "j02", "gen", "rc", "rsh", "rcj")


def test_inverted_targets_registry(gedos):
    """맵이 **저항**을 곱하는 대상 목록 — `rc` · `rsh` · `rcj` 셋이다.

    이 목록이 GUI의 앰버 강조를 결정한다. 방향이 뒤집힌다는 것은 **모델의
    사실**이지 화면의 사실이 아니므로 엔진 쪽에 둔다. 새 대상을 추가하는 사람이
    여기를 안 보면 경고 없이 반대로 쓰이게 되므로 목록을 테스트로 고정한다.
    """
    assert gedos.SPATIAL_INVERTED_TARGETS == ("rc", "rsh", "rcj")
    assert set(gedos.SPATIAL_INVERTED_TARGETS) <= set(gedos.SPATIAL_TARGETS)


def test_diode_params_default_none(gedos):
    """맵 미지정이 기본. 이 None이 비트 동일 근거 (1)의 출발점이다."""
    dp = gedos.DiodeParams()
    for which in gedos.SPATIAL_TARGETS:
        assert getattr(dp, f"spatial_{which}") is None


def test_make_uniform_helper(gedos):
    arr = gedos.make_uniform(5)
    assert arr.shape == (5,)
    assert np.all(arr == 1.0)


# =============================================================================
# 2. evaluate() — 모드별 (FEM 없음)
# =============================================================================

def test_uniform_mode(gedos):
    sm = gedos.SpatialMap(mode="uniform", background=1.3)
    out = sm.evaluate(_pts((0.0, 0.0), (W, H), (0.5, 1.5)), W, H)
    assert out.shape == (3,)
    assert np.all(out == 1.3)


def test_rectangle_mode_inside_outside(gedos):
    sm = gedos.SpatialMap(mode="rectangle", background=1.0, feature=2.0,
                         x_min=0.5, x_max=1.5, y_min=0.5, y_max=1.5)
    out = sm.evaluate(_pts((1.0, 1.0),      # 내부
                           (0.1, 0.1),      # 외부
                           (0.5, 0.5),      # 경계 — 포함(>=, <=)
                           (1.5, 1.5)), W, H)
    assert out[0] == 2.0
    assert out[1] == 1.0
    assert out[2] == 2.0
    assert out[3] == 2.0


def test_gaussian_mode_peak_and_tail(gedos):
    sm = gedos.SpatialMap(mode="gaussian", background=1.0, feature=3.0,
                         cx=1.0, cy=1.0, sigma_x=0.1, sigma_y=0.1)
    out = sm.evaluate(_pts((1.0, 1.0), (1.0, 2.0)), W, H)
    assert out[0] == pytest.approx(3.0)          # 중심 = feature
    assert out[1] == pytest.approx(1.0, abs=1e-9)  # 멀리 = background


def test_checkerboard_mode_alternates(gedos):
    sm = gedos.SpatialMap(mode="checkerboard", background=1.0, feature=2.0,
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


def test_checkerboard_clamps_upper_edge(gedos):
    """x=W 노드가 nx로 넘어가 IndexError가 되지 않고 마지막 셀에 들어간다."""
    sm = gedos.SpatialMap(mode="checkerboard", background=1.0, feature=2.0,
                         cells_x=2, cells_y=2)
    out = sm.evaluate(_pts((W, H)), W, H)
    assert out[0] == 2.0   # ix=1, iy=1


# =============================================================================
# 3. csv 모드 — 격자 정렬·행 방향·보간 (교차검증 직결)
# =============================================================================

def test_csv_corners_are_vertex_aligned(gedos):
    """꼭짓점 정렬: 행렬 네 값이 셀 네 모서리에 **정확히** 놓인다.

    픽셀 중심(cell-centered) 규약이면 이 값들이 모서리에 오지 않는다.
    """
    M = np.array([[1.0, 2.0],
                  [3.0, 4.0]])
    sm = gedos.SpatialMap(mode="csv", matrix=M)
    out = sm.evaluate(_pts((0.0, 0.0),   # matrix[0][0]
                           (W, 0.0),     # matrix[0][1]
                           (0.0, H),     # matrix[1][0]
                           (W, H)), W, H)  # matrix[1][1]
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(2.0)
    assert out[2] == pytest.approx(3.0)
    assert out[3] == pytest.approx(4.0)


def test_csv_row_zero_is_y_zero(gedos):
    """행 방향 고정: matrix[0]이 y=0이다.

    텍스트 파일의 첫 줄을 사람은 보통 '위쪽'으로 읽는다. Griddler가 첫 줄을
    y=H로 해석하면 맵이 상하 반전된다 — 단위 3의 판정 대상.
    시험 행렬을 **비대칭**으로 두어야 이 오류가 드러난다.
    """
    M = np.array([[1.0, 1.0],
                  [2.0, 2.0]])
    sm = gedos.SpatialMap(mode="csv", matrix=M)
    out = sm.evaluate(_pts((0.5, 0.0), (0.5, H)), W, H)
    assert out[0] == pytest.approx(1.0)   # y=0  -> 첫 행
    assert out[1] == pytest.approx(2.0)   # y=H  -> 마지막 행


def test_csv_bilinear_midpoint(gedos):
    """쌍선형 보간 — 중앙은 네 값의 평균."""
    M = np.array([[1.0, 2.0],
                  [3.0, 4.0]])
    sm = gedos.SpatialMap(mode="csv", matrix=M)
    out = sm.evaluate(_pts((W / 2, H / 2)), W, H)
    assert out[0] == pytest.approx(2.5)


def test_csv_clips_outside_points_no_extrapolation(gedos):
    """셀 밖 좌표는 clip되어 경계값을 받는다 — fill_value=None이지만 외삽 없음."""
    M = np.array([[1.0, 2.0],
                  [3.0, 4.0]])
    sm = gedos.SpatialMap(mode="csv", matrix=M)
    out = sm.evaluate(_pts((-5.0, -5.0), (W + 5.0, H + 5.0)), W, H)
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(4.0)


def test_csv_non_square_matrix(gedos):
    """행/열 수가 달라도 (ny, nx) 순서로 해석된다."""
    M = np.array([[1.0, 2.0, 3.0],
                  [4.0, 5.0, 6.0]])   # ny=2, nx=3
    sm = gedos.SpatialMap(mode="csv", matrix=M)
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
def test_csv_rejects_bad_matrix_shape(gedos, matrix):
    sm = gedos.SpatialMap(mode="csv", matrix=matrix)
    with pytest.raises(ValueError, match="csv spatial map needs"):
        sm.evaluate(_pts((0.0, 0.0)), W, H)


@pytest.mark.parametrize("bad", [0.0, -1.0, np.nan, np.inf])
def test_rejects_non_positive_or_non_finite(gedos, bad):
    """배율은 유한하고 양수여야 한다 (GEDOS.py:3327-3328)."""
    M = np.array([[1.0, 1.0],
                  [1.0, bad]])
    sm = gedos.SpatialMap(mode="csv", matrix=M)
    with pytest.raises(ValueError, match="finite and positive"):
        sm.evaluate(_pts((W, H)), W, H)


def test_rejects_non_positive_background(gedos):
    sm = gedos.SpatialMap(mode="uniform", background=0.0)
    with pytest.raises(ValueError, match="finite and positive"):
        sm.evaluate(_pts((0.0, 0.0)), W, H)


def test_rejects_unknown_mode(gedos):
    sm = gedos.SpatialMap(mode="bogus")
    with pytest.raises(ValueError, match="Unsupported spatial map mode"):
        sm.evaluate(_pts((0.0, 0.0)), W, H)


# =============================================================================
# 5. _spatial_mult — None 가드와 캐시 (비트 동일 근거 (1))
# =============================================================================

def test_spatial_mult_returns_none_when_unset(gedos, make_mono):
    """맵이 없으면 배열을 만들지 않고 None을 준다 → 호출부가 곱셈을 건너뛴다.

    이것이 '맵 미지정 시 비트 동일'의 1차 근거다. all-ones 배열을 만들어
    곱하는 구조였다면 이 근거가 성립하지 않는다.
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    for which in gedos.SPATIAL_TARGETS:
        assert m.S._spatial_mult(dp, which) is None


def test_spatial_mult_returns_node_length_array(gedos, make_mono):
    m = make_mono()
    dp = gedos.DiodeParams()
    dp.spatial_j01 = gedos.SpatialMap(mode="uniform", background=1.7)
    arr = m.S._spatial_mult(dp, "j01")
    assert arr is not None
    assert arr.shape == (m.S.N,)
    assert np.all(arr == 1.7)


def test_spatial_mult_caches_same_object(gedos, make_mono):
    """같은 spec을 다시 물으면 같은 배열 객체를 돌려준다 (노드 평가 1회)."""
    m = make_mono()
    dp = gedos.DiodeParams()
    dp.spatial_gen = gedos.SpatialMap(mode="uniform", background=1.1)
    a = m.S._spatial_mult(dp, "gen")
    b = m.S._spatial_mult(dp, "gen")
    assert a is b


def test_spatial_mult_evaluated_on_node_coords(gedos, make_mono):
    """노드 좌표에서 평가된다 — 좌우로 갈리는 맵이 노드 x에 따라 갈린다."""
    m = make_mono()
    dp = gedos.DiodeParams()
    dp.spatial_j01 = gedos.SpatialMap(
        mode="rectangle", background=1.0, feature=2.0,
        x_min=0.0, x_max=m.geo.W / 2, y_min=0.0, y_max=m.geo.H)
    arr = m.S._spatial_mult(dp, "j01")
    left = m.S.pts[:, 0] <= m.geo.W / 2
    assert np.all(arr[left] == 2.0)
    assert np.all(arr[~left] == 1.0)


# =============================================================================
# 6. rc 맵의 의미 방향 — 값이 클수록 접촉이 나쁘다
# =============================================================================

def test_rc_map_multiplies_resistance_not_conductance(gedos, make_mono):
    """rc 맵은 **접촉저항 R**을 곱한다 → 컨덕턴스 Gc는 나뉜다.

    예: 0.5 = 접촉저항 절반(잘 눌린 영역) → Gc 2배
        2.0 = 접촉저항 두 배(덜 눌린 영역) → Gc 절반

    4종 중 rc만 의미가 반대라 GUI 라벨에서 오해가 나기 쉽다(단위 4).
    """
    base = make_mono()
    dp0 = gedos.DiodeParams()
    base.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                  PARAMS["Rs"], PARAMS["cf"], dp0)
    Gc0 = base.S._Gc.copy()

    worse = make_mono()
    dp2 = gedos.DiodeParams()
    dp2.spatial_rc = gedos.SpatialMap(mode="uniform", background=2.0)
    worse.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                   PARAMS["Rs"], PARAMS["cf"], dp2)
    Gc2 = worse.S._Gc

    ism = base.S.ism
    assert np.any(ism), "접촉 노드가 있어야 의미 있는 비교다"
    # 배율 2.0 -> 접촉저항 2배 -> 컨덕턴스 절반
    assert np.allclose(Gc2[ism], Gc0[ism] / 2.0, rtol=0, atol=0)
    # 접촉 노드 밖은 건드리지 않는다
    assert np.array_equal(Gc2[~ism], Gc0[~ism])


def test_rsh_map_multiplies_resistance_not_conductance(gedos, make_mono):
    """rsh 맵은 **션트 저항 Rsh**를 곱한다 → 누설 컨덕턴스 1/Rsh는 나뉜다.

    예: 0.5 = Rsh 절반(누설이 심한 자리) → 누설 전류 2배
        2.0 = Rsh 두 배(깨끗한 자리)     → 누설 전류 절반

    `rc`와 같은 함정이다(§6). 그리고 **Griddler와 방향이 반대**다 — 그쪽은
    shunt를 컨덕턴스 G_shunt [S/cm²]로 두고 우리는 저항 Rsh [Ω·cm²]로 둔다.
    같은 파일을 그대로 가져오면 역효과가 난다
    (`docs/spatial_map_convention.md` §7).

    판정은 헬퍼가 돌려주는 노드 배열로 한다 — `_Gc`처럼 밖에서 볼 수 있는
    행렬이 아니라 잔차 안에서만 쓰이는 값이기 때문이다.
    """
    m = make_mono()
    dp0 = gedos.DiodeParams()
    base = m.S._diode_node_arrays(dp0, mode="tandem")

    dp2 = gedos.DiodeParams()
    dp2.spatial_rsh = gedos.SpatialMap(mode="uniform", background=2.0)
    got = m.S._diode_node_arrays(dp2, mode="tandem")

    assert np.allclose(got.Rsh, dp0.Rsh_top * 2.0, rtol=0, atol=0)
    assert np.allclose(got.Rshb, dp0.Rsh_bot * 2.0, rtol=0, atol=0)
    # 누설 컨덕턴스는 절반이 된다 — 이것이 "값이 크면 좋다"의 실체다
    assert np.allclose(1.0 / got.Rsh, (1.0 / dp0.Rsh_top) / 2.0)


def test_rsh_no_map_returns_the_scalar_itself(gedos, make_mono):
    """맵이 없으면 헬퍼가 `dp.Rsh_*` **스칼라 그 객체**를 돌려준다.

    이것이 무맵 비트 동일의 근거다. 소비 지점이 전부 `V / Rsh`(나눗셈)이므로,
    스칼라를 그대로 돌려주면 식이 v28.61과 **문자 그대로 같다.**

    ⚠ 컨덕턴스 `1/Rsh`를 돌려주고 `V * Gsh`로 바꾸면 안 된다 —
    `V / R`과 `V * (1/R)`은 IEEE754에서 마지막 비트가 다르다.
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    t = m.S._diode_node_arrays(dp, mode="tandem")
    assert t.Rsh is dp.Rsh_top
    assert t.Rshb is dp.Rsh_bot
    sgl = m.S._diode_node_arrays(dp, mode="single")
    assert sgl.Rsh is dp.Rsh_single


def test_rsh_map_is_in_the_build_cache_hash(gedos, make_mono):
    """rsh 맵을 바꾸면 `_build` 캐시가 무효화된다.

    Rsh는 `_build`가 만드는 강성행렬에 들어가지 않지만, **warm-start 벡터**는
    이전 문제의 해다. 다른 맵 4종과 같은 처리를 해서 슬롯이 빠지는 일이 없게
    한다 — 맵이 없으면 상수 0이라 무맵 경로의 캐시 거동은 그대로다.
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    m.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
               PARAMS["Rs"], PARAMS["cf"], dp)
    h0 = m.S._cache_hash
    dp.spatial_rsh = gedos.SpatialMap(mode="uniform", background=2.0)
    m.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
               PARAMS["Rs"], PARAMS["cf"], dp)
    assert m.S._cache_hash != h0, "rsh 맵이 캐시 해시에 없다"
    gedos.clear_spatial_map(dp, "rsh")
    m.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
               PARAMS["Rs"], PARAMS["cf"], dp)
    assert m.S._cache_hash == h0, "맵을 떼면 해시가 원래대로 돌아와야 한다"


def test_rcj_map_multiplies_the_junction_contact_resistivity(gedos, make_mono):
    """rcj 맵은 **서브셀 사이 수직 접촉 비저항 Rc_junction**을 곱한다 (v28.66).

    `rc`(전극↔반도체, B 계층)와 **다른 물성**이다 — 단위가 둘 다 Ω·cm²라
    바꿔 걸어도 오류가 안 나므로, 여기서 "어느 값이 움직이는가"로 구분한다.
    """
    m = make_mono()
    dp0 = gedos.DiodeParams()
    base = m.S._diode_node_arrays(dp0, mode="tandem")

    dp2 = gedos.DiodeParams()
    dp2.spatial_rcj = gedos.SpatialMap(mode="uniform", background=2.0)
    got = m.S._diode_node_arrays(dp2, mode="tandem")

    assert np.allclose(got.Rc_j, dp0.Rc_junction * 2.0, rtol=0, atol=0)
    # rcj는 다이오드 포화전류·션트를 건드리지 않는다 — 계층은 같아도 물성이 다르다
    assert np.array_equal(np.atleast_1d(got.Rsh), np.atleast_1d(base.Rsh))
    assert np.array_equal(np.atleast_1d(got.J01), np.atleast_1d(base.J01))


def test_rcj_no_map_returns_the_scalar_itself(gedos, make_mono):
    """맵이 없으면 `dp.Rc_junction` **스칼라 그 객체**다 — 무맵 비트 동일 근거.

    소비 지점이 전부 `Rc_j * Jb` / `1.0 - Rc_j * dJb` 형태이므로, 스칼라를
    그대로 넘기면 식이 v28.65와 문자 그대로 같다(`rsh`의 근거 (5)와 같다).
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    t = m.S._diode_node_arrays(dp, mode="tandem")
    assert t.Rc_j is dp.Rc_junction


def test_rcj_map_does_not_break_the_on_off_gate(gedos, make_mono):
    """`Rc_junction > 0` 게이트는 **스칼라**로 판정한다 — 맵이 붙어도 살아 있다.

    이것이 이 배선에서 가장 깨지기 쉬운 자리다. 소비 지점 여섯 곳이
    `if Rc_j > 0:`로 켜짐을 판정하고 있었는데, `Rc_j`가 배열이 되면 파이썬이
    "truth value of an array is ambiguous" ValueError를 던진다. **조용한
    오답이 아니라 즉시 예외**라 발견은 쉽지만, 맵을 붙인 사용자에게만 터진다.

    v28.66은 게이트를 `dp.Rc_junction`(스칼라)로 남겼다. 배율은 항상 양수이므로
    (`SpatialMap.evaluate`가 강제한다) 켜짐 여부는 스칼라만으로 정해진다 —
    즉 판정을 스칼라로 두는 것은 편의가 아니라 **옳다.**
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    dp.spatial_rcj = gedos.SpatialMap(mode="gaussian", background=1.0,
                                     feature=3.0, cx=1.0, cy=1.0,
                                     sigma_x=0.4, sigma_y=0.4)
    got = m.S._diode_node_arrays(dp, mode="tandem")
    assert np.ndim(got.Rc_j) == 1, "맵을 붙였는데 배열이 아니다"
    assert np.all(got.Rc_j > 0), "배율이 양수인데 Rc_j에 0/음수가 생겼다"

    # 실제 solve가 게이트에서 터지지 않는지 — 여기서 ValueError가 나면 배선이
    # 게이트를 배열로 판정하고 있다는 뜻이다.
    m.S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
              PARAMS["Rs"], 0.5, PARAMS["cf"], dp, "tandem")


def test_rcj_map_is_in_the_build_cache_hash(gedos, make_mono):
    """rcj 맵을 바꾸면 `_build` 캐시가 무효화된다.

    `_build`는 이 맵을 **쓰지 않는다**(A 계층). 그래도 슬롯을 둔다 — 대상마다
    슬롯 하나라는 규약이 깨지면 나중에 어느 맵이 B 계층으로 옮겨질 때 캐시가
    조용히 낡는다. 비용은 rcj만 바뀔 때의 재빌드 한 번이다.
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    m.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
               PARAMS["Rs"], PARAMS["cf"], dp)
    h0 = m.S._cache_hash
    dp.spatial_rcj = gedos.SpatialMap(mode="uniform", background=2.0)
    m.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
               PARAMS["Rs"], PARAMS["cf"], dp)
    assert m.S._cache_hash != h0, "rcj 맵이 캐시 해시에 없다"
    gedos.clear_spatial_map(dp, "rcj")
    m.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
               PARAMS["Rs"], PARAMS["cf"], dp)
    assert m.S._cache_hash == h0, "맵을 떼면 해시가 원래대로 돌아와야 한다"


def test_rcj_is_distinct_from_rc(gedos, make_mono):
    """`rc`와 `rcj`가 **서로 다른 것을 움직인다.**

    이름·단위가 겹쳐 바꿔 거는 사고가 가장 그럴듯한 자리다. 오류가 나지 않으므로
    (둘 다 양수 배율) 값으로 구분해 둔다.
      - rc  → `_Gc`(강성 조립, 금속 노드 컨덕턴스)를 바꾸고 `Rc_j`는 그대로
      - rcj → `Rc_j`를 바꾸고 `_Gc`는 그대로
    """
    sm = gedos.SpatialMap(mode="uniform", background=2.0)

    m1 = make_mono()
    dp1 = gedos.DiodeParams()
    dp1.spatial_rc = sm
    m1.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                PARAMS["Rs"], PARAMS["cf"], dp1)
    assert m1.S._diode_node_arrays(dp1, mode="tandem").Rc_j is dp1.Rc_junction, (
        "rc 맵이 Rc_junction까지 건드렸다 — 계층을 넘었다")

    m2 = make_mono()
    dp2 = gedos.DiodeParams()
    dp2.spatial_rcj = sm
    m2.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                PARAMS["Rs"], PARAMS["cf"], dp2)
    dp0 = gedos.DiodeParams()
    m3 = make_mono()
    m3.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                PARAMS["Rs"], PARAMS["cf"], dp0)
    assert np.array_equal(m2.S._Gc, m3.S._Gc), (
        "rcj 맵이 접촉 컨덕턴스 _Gc까지 건드렸다 — rc의 자리를 침범했다")


def test_rcj_example_file_loads_and_targets_rcj(gedos):
    """배포 예제가 실제로 로드되고 `rcj`에 붙는다.

    예제 파일이 문서에만 있고 로더를 통과하지 못하면 처음 쓰는 사람이 그
    파일로 막힌다 — 안내와 구현이 갈리는 전형적인 자리다.
    """
    import os
    path = os.path.join(gedos.spatial_examples_dir(), "edge_delam_rcj.txt")
    assert os.path.exists(path), f"예제 파일이 없다: {path}"
    sm = gedos.load_spatial_map_txt(path)
    dp = gedos.DiodeParams()
    gedos.set_spatial_map(dp, "rcj", sm)
    assert gedos.active_spatial_maps(dp) == ("rcj",)
    # 가장자리가 중앙보다 나쁘다(값이 크다) — 파일 주석이 말하는 방향
    assert sm.matrix[0][0] > sm.matrix[len(sm.matrix) // 2][len(sm.matrix) // 2]


# =============================================================================
# 7. 맵 미지정 비트 동일 — 해제 경로 회귀 가드
# =============================================================================

def _solve_current(gedos, m, dp, Vb):
    res = m.S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                    PARAMS["Rs"], Vb, PARAMS["cf"], dp, "tandem")
    return float(m.S.cell_current(res, dp))


def test_clearing_map_to_none_restores_bit_identical_result(gedos, make_mono):
    """맵을 걸었다 **None으로 해제**하면 원래 결과로 비트 단위 복귀한다.

    GUI의 Clear 경로가 의존하는 성질이다(계획 단위 4). 해제를
    `SpatialMap(mode='uniform')`으로 구현하면 값은 같더라도 None 가드를
    우회하므로, 해제는 반드시 None이어야 한다.
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    Vb = 0.85 * dp.expected_voc()[2]

    J0 = _solve_current(gedos, m, dp, Vb)

    dp.spatial_j01 = gedos.SpatialMap(mode="uniform", background=2.0)
    J_mapped = _solve_current(gedos, m, dp, Vb)

    dp.spatial_j01 = None
    J_restored = _solve_current(gedos, m, dp, Vb)

    assert J_mapped != J0, "맵이 실제로 결과를 바꿔야 이 테스트가 의미 있다"
    assert J_restored == J0   # 비트 동일


def test_j01_map_raises_recombination_and_lowers_current(gedos, make_mono):
    """물리 방향 확인: J01 배율↑ = 재결합↑ = 전류↓ (바이어스 하에서)."""
    m = make_mono()
    dp = gedos.DiodeParams()
    Vb = 0.85 * dp.expected_voc()[2]

    J0 = _solve_current(gedos, m, dp, Vb)
    dp.spatial_j01 = gedos.SpatialMap(mode="uniform", background=10.0)
    J_hi = _solve_current(gedos, m, dp, Vb)

    assert J_hi < J0


# =============================================================================
# 8. 캐시 무효화 — 내용 기반이어야 한다 (계획 단위 1)
# =============================================================================
#
# `_build`의 캐시 태그 `_sm_tag`(GEDOS.py:3897-3901)는 원래 맵의 **id()**로
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

def test_content_key_equal_for_equal_content(gedos):
    """서로 다른 객체라도 내용이 같으면 키가 같다.

    id() 기반 태그는 이 성질을 **결정론적으로** 위반한다 — 별개 객체는 항상
    다른 id를 갖기 때문이다. 정정 전에는 이 테스트가 실패해야 한다.
    """
    a = gedos.SpatialMap(mode="uniform", background=1.5)
    b = gedos.SpatialMap(mode="uniform", background=1.5)
    assert a is not b
    assert a.content_key() == b.content_key()


def test_content_key_equal_for_equal_matrix_distinct_arrays(gedos):
    """행렬도 내용으로 비교한다 — 배열 객체가 달라도 값이 같으면 같은 키."""
    M1 = np.array([[1.0, 2.0], [3.0, 4.0]])
    M2 = np.array([[1.0, 2.0], [3.0, 4.0]])
    a = gedos.SpatialMap(mode="csv", matrix=M1)
    b = gedos.SpatialMap(mode="csv", matrix=M2)
    assert M1 is not M2
    assert a.content_key() == b.content_key()


def test_content_key_differs_on_matrix_value(gedos):
    a = gedos.SpatialMap(mode="csv", matrix=np.array([[1.0, 2.0], [3.0, 4.0]]))
    b = gedos.SpatialMap(mode="csv", matrix=np.array([[1.0, 2.0], [3.0, 4.5]]))
    assert a.content_key() != b.content_key()


def test_content_key_differs_on_matrix_shape(gedos):
    """같은 값의 나열이라도 형상이 다르면 다른 맵이다."""
    a = gedos.SpatialMap(mode="csv", matrix=np.array([[1.0, 2.0], [3.0, 4.0]]))
    b = gedos.SpatialMap(mode="csv",
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
def test_content_key_differs_on_each_field(gedos, field, value):
    """어떤 필드를 바꿔도 키가 달라져야 한다 — 빠뜨린 필드가 있으면 잡힌다."""
    a = gedos.SpatialMap(mode="uniform")
    b = gedos.SpatialMap(mode="uniform")
    setattr(b, field, value)
    assert a.content_key() != b.content_key()


def test_content_key_is_hashable(gedos):
    """`_spatial_cache`의 dict 키로 쓰이므로 해시 가능해야 한다."""
    sm = gedos.SpatialMap(mode="csv", matrix=np.array([[1.0, 2.0], [3.0, 4.0]]))
    assert hash(sm.content_key()) == hash(sm.content_key())


# --- 8-2. 결과에 미치는 영향 --------------------------------------------------

def _build(m, dp):
    m.S._build(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
               PARAMS["Rs"], PARAMS["cf"], dp)
    return m.S._Gc[m.S.ism].copy()


def test_inplace_map_edit_invalidates_build_cache(gedos, make_mono):
    """맵을 **제자리 수정**하면 _Gc가 재빌드되어야 한다.

    id() 태그에서는 결정론적으로 실패한다(id가 안 변하므로 캐시 적중).
    GUI가 target당 맵 하나를 두고 필드만 갱신하는 구조면 항상 이 경로다.
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    sm = gedos.SpatialMap(mode="uniform", background=1.0)
    dp.spatial_rc = sm

    g1 = _build(m, dp)
    sm.background = 2.0            # 제자리 수정 — id 불변
    g2 = _build(m, dp)

    # rc 배율 2배 -> 접촉저항 2배 -> Gc 절반
    assert np.allclose(g2, g1 / 2.0, rtol=0, atol=0)


def test_matrix_inplace_edit_invalidates_build_cache(gedos, make_mono):
    """행렬 내용만 바꿔치기해도 재빌드되어야 한다 (파일 재로드 경로)."""
    m = make_mono()
    dp = gedos.DiodeParams()
    sm = gedos.SpatialMap(mode="csv", matrix=np.ones((2, 2)))
    dp.spatial_rc = sm

    g1 = _build(m, dp)
    sm.matrix = np.full((2, 2), 2.0)
    g2 = _build(m, dp)

    assert np.allclose(g2, g1 / 2.0, rtol=0, atol=0)


def test_map_replacement_after_free_invalidates_cache(gedos, make_mono):
    """맵 A 해제 → B 생성. A의 주소가 재사용돼도 B가 반영되어야 한다.

    주소 재사용은 CPython 구현에 의존하므로 이 테스트만으로는 정정 전 실패가
    보장되지 않는다(재사용이 안 일어나면 그냥 통과한다). 결정론적 재현은
    위의 제자리 수정 테스트와 content_key 계약이 담당하고, 이 테스트는
    GUI 실사용 시나리오에 대한 회귀 가드다.
    """
    m = make_mono()
    dp = gedos.DiodeParams()

    A = gedos.SpatialMap(mode="uniform", background=1.0)
    dp.spatial_rc = A
    g1 = _build(m, dp)

    dp.spatial_rc = None
    del A
    B = gedos.SpatialMap(mode="uniform", background=2.0)
    dp.spatial_rc = B
    g2 = _build(m, dp)

    assert np.allclose(g2, g1 / 2.0, rtol=0, atol=0)


def test_spatial_mult_cache_follows_content(gedos, make_mono):
    """`_spatial_mult`의 배열 캐시도 내용을 따라야 한다.

    이 캐시는 `(id(dp), which, id(spec))`을 키로 썼다 — 같은 결함이다.
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    sm = gedos.SpatialMap(mode="uniform", background=1.0)
    dp.spatial_j01 = sm

    a = m.S._spatial_mult(dp, "j01")
    assert np.all(a == 1.0)

    sm.background = 3.0
    b = m.S._spatial_mult(dp, "j01")
    assert np.all(b == 3.0)


def test_unchanged_build_still_short_circuits(gedos, make_mono):
    """바뀐 게 없으면 여전히 캐시로 빠져나가야 한다 (성능 회귀 방지).

    `_build`는 재빌드 시 `self._Gc = np.zeros(N)`으로 **새 객체**를 만든다.
    따라서 같은 객체가 유지되면 조기 반환이 일어났다는 뜻이다.
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    dp.spatial_rc = gedos.SpatialMap(mode="uniform", background=1.5)

    _build(m, dp)
    first = m.S._Gc
    _build(m, dp)
    assert m.S._Gc is first


def test_no_map_build_still_short_circuits(gedos, make_mono):
    """맵이 없을 때도 캐시 거동이 그대로여야 한다 (비트 동일 경로 불변)."""
    m = make_mono()
    dp = gedos.DiodeParams()

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

def test_loader_reads_comma_matrix(gedos, tmp_path):
    path = _write(tmp_path, "1.0,2.0\n3.0,4.0\n")
    sm = gedos.load_spatial_map_txt(path)
    assert isinstance(sm, gedos.SpatialMap)
    assert sm.mode == "csv"
    assert np.array_equal(sm.matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_loader_reads_whitespace_matrix(gedos, tmp_path):
    path = _write(tmp_path, "1.0 2.0\n3.0 4.0\n")
    sm = gedos.load_spatial_map_txt(path)
    assert np.array_equal(sm.matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_loader_reads_tab_matrix(gedos, tmp_path):
    path = _write(tmp_path, "1.0\t2.0\n3.0\t4.0\n")
    sm = gedos.load_spatial_map_txt(path)
    assert np.array_equal(sm.matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_loader_explicit_delimiter_override(gedos, tmp_path):
    path = _write(tmp_path, "1.0;2.0\n3.0;4.0\n")
    sm = gedos.load_spatial_map_txt(path, delimiter=";")
    assert np.array_equal(sm.matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_loader_keeps_absolute_values_no_normalization(gedos, tmp_path):
    """**절대값 규약** — 평균이 1이 아니어도 그대로 둔다.

    이미지(2단계)만 평균 1로 정규화한다. 여기서 정규화하면 같은 파일을
    Griddler에 넣었을 때와 값이 달라져 교차검증이 무의미해진다.
    """
    path = _write(tmp_path, "10,20\n30,40\n")
    sm = gedos.load_spatial_map_txt(path)
    assert np.array_equal(sm.matrix, np.array([[10.0, 20.0], [30.0, 40.0]]))
    assert sm.matrix.mean() == pytest.approx(25.0)   # 1로 정규화되지 않았다


def test_loader_non_square_shape_is_ny_nx(gedos, tmp_path):
    """행이 y, 열이 x — evaluate()의 (ny, nx) 해석과 일치해야 한다."""
    path = _write(tmp_path, "1,2,3\n4,5,6\n")
    sm = gedos.load_spatial_map_txt(path)
    assert sm.matrix.shape == (2, 3)
    out = sm.evaluate(_pts((0.0, 0.0), (W, 0.0), (W, H)), W, H)
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(3.0)
    assert out[2] == pytest.approx(6.0)


def test_loader_first_row_is_y_zero(gedos, tmp_path):
    """파일 첫 줄 = matrix[0] = y=0. 단위 3 Griddler 대조의 기준."""
    path = _write(tmp_path, "1,1\n2,2\n")
    sm = gedos.load_spatial_map_txt(path)
    out = sm.evaluate(_pts((0.5, 0.0), (0.5, H)), W, H)
    assert out[0] == pytest.approx(1.0)
    assert out[1] == pytest.approx(2.0)


def test_loader_tolerates_bom_blank_lines_crlf_and_comments(gedos, tmp_path):
    """BOM·빈 줄·CRLF·'#' 주석은 데이터가 아니다 (v28.20 utf-8-sig 전례)."""
    p = tmp_path / "m.txt"
    p.write_bytes("# 주석\r\n1,2\r\n\r\n3,4\r\n\r\n".encode("utf-8-sig"))
    sm = gedos.load_spatial_map_txt(str(p))
    assert np.array_equal(sm.matrix, np.array([[1.0, 2.0], [3.0, 4.0]]))


def test_loader_result_equals_in_memory_map(gedos, tmp_path):
    """파일로 만든 맵과 직접 만든 맵이 **내용상 같다** (content_key 일치)."""
    path = _write(tmp_path, "1,2\n3,4\n")
    a = gedos.load_spatial_map_txt(path)
    b = gedos.SpatialMap(mode="csv", matrix=np.array([[1.0, 2.0], [3.0, 4.0]]))
    assert a.content_key() == b.content_key()


def test_loader_report_records_provenance(gedos, tmp_path):
    """DXF 로더의 report 관용구 — 무엇을 어떻게 읽었는지 남긴다."""
    path = _write(tmp_path, "1,2\n3,4\n")
    sm = gedos.load_spatial_map_txt(path)
    rep = sm.load_report
    assert rep["path"] == path
    assert rep["shape"] == (2, 2)
    assert rep["delimiter"] == ","
    assert rep["warnings"] == []


def test_loader_warns_on_large_matrix_but_loads(gedos, tmp_path):
    """큰 행렬은 거부하지 않고 보간 비용만 알린다."""
    n = gedos.SPATIAL_MAP_LARGE_DIM + 1
    row = ",".join(["1.0"] * n)
    path = _write(tmp_path, "\n".join([row] * 2) + "\n")
    sm = gedos.load_spatial_map_txt(path)
    assert sm.matrix.shape == (2, n)
    assert any("보간" in w or "large" in w.lower() for w in sm.load_report["warnings"])


# --- 9-2. 형식 오류 -----------------------------------------------------------

def test_loader_rejects_missing_file(gedos, tmp_path):
    with pytest.raises(FileNotFoundError):
        gedos.load_spatial_map_txt(str(tmp_path / "nope.txt"))


def test_loader_rejects_empty_file(gedos, tmp_path):
    path = _write(tmp_path, "\n\n")
    with pytest.raises(ValueError, match="비어"):
        gedos.load_spatial_map_txt(path)


def test_loader_rejects_ragged_rows(gedos, tmp_path):
    path = _write(tmp_path, "1,2\n3,4,5\n")
    with pytest.raises(ValueError) as exc:
        gedos.load_spatial_map_txt(path)
    msg = str(exc.value)
    assert "2" in msg          # 문제가 된 데이터 행
    assert "3" in msg and "2" in msg   # 열 개수 불일치(3 vs 2)


def test_loader_rejects_non_numeric_token(gedos, tmp_path):
    path = _write(tmp_path, "1,2\n3,abc\n")
    with pytest.raises(ValueError) as exc:
        gedos.load_spatial_map_txt(path)
    assert "abc" in str(exc.value)


@pytest.mark.parametrize("text", [
    "1.0\n",              # 1 x 1
    "1.0,2.0\n",          # 1 x 2
    "1.0\n2.0\n",         # 2 x 1
])
def test_loader_rejects_too_small(gedos, tmp_path, text):
    """evaluate()가 요구하는 최소 2x2를 로드 시점에 먼저 막는다."""
    path = _write(tmp_path, text)
    with pytest.raises(ValueError, match="2x2"):
        gedos.load_spatial_map_txt(path)


# --- 9-3. 값 제약 — 조용히 고치지 말고 거부 -----------------------------------

@pytest.mark.parametrize("bad,label", [
    ("0", "0"),
    ("0.0", "0"),
    ("-1.5", "-1.5"),
    ("nan", "nan"),
    ("inf", "inf"),
    ("-inf", "inf"),
])
def test_loader_rejects_non_positive_or_non_finite(gedos, tmp_path, bad, label):
    """0·음수·NaN·inf는 거부한다. 클램프·치환하지 않는다."""
    path = _write(tmp_path, f"1.0,2.0\n3.0,{bad}\n")
    with pytest.raises(ValueError) as exc:
        gedos.load_spatial_map_txt(path)
    msg = str(exc.value)
    assert "2" in msg              # 데이터 행 2
    assert label.lower() in msg.lower()


def test_loader_error_names_the_file(gedos, tmp_path):
    """오류 메시지에 경로가 있어야 어느 파일인지 안다."""
    path = _write(tmp_path, "1,2\n3,-1\n")
    with pytest.raises(ValueError) as exc:
        gedos.load_spatial_map_txt(path)
    assert os.path.basename(path) in str(exc.value)


def test_loader_rejects_before_solver_runs(gedos, tmp_path, make_mono):
    """검사는 **로드 시점**에 끝난다 — 솔버에 들어가서 터지지 않는다."""
    path = _write(tmp_path, "1,2\n3,0\n")
    with pytest.raises(ValueError):
        gedos.load_spatial_map_txt(path)
    # 맵이 만들어지지 않았으므로 dp는 여전히 무맵이고 솔버는 정상이다
    m = make_mono()
    dp = gedos.DiodeParams()
    assert m.S._spatial_mult(dp, "rc") is None


# =============================================================================
# 10. 규약 확정 기준선 (계획 단위 3 — 대조 불가, 자체 규약 채택)
# =============================================================================
#
# Griddler 무료판에 공간 분포 입력이 없어(PRO 전용) 대조를 하지 못했다. 대신
# 규약을 **자체 규약으로 확정 선언**했다 — docs/spatial_map_convention.md.
#
#   matrix[0] = y=0   (파일의 첫 데이터 줄이 셀의 아래쪽)
#   꼭짓점 정렬        (linspace(0,H,ny) — 모서리 값이 셀 모서리에 정확히)
#
# 아래 테스트는 대조 절차서 §2의 기준값 8개를 **코드에 묶는다.** 그 표는 PRO를
# 확보해 대조할 때 우리 쪽 기준선이 되는데, 그때까지 코드가 바뀌어 문서와
# 어긋나면 대조 자체가 무의미해진다. 문서와 코드가 같이 움직이도록 한다.
#
# 시험 행렬을 임의로 바꾸면 안 된다 — 비대칭이라야 상하 반전과 반 칸 밀림이
# 둘 다 드러난다(절차서 §1).

_CROSSCHECK_TXT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "crosscheck", "spatial_4x4.txt")

# 절차서 §2 표. 셀 30 x 30 mm 기준, (x_mm, y_mm) -> 기대 배율.
_CROSSCHECK_POINTS = [
    ((0.0, 0.0), 2.0, "좌하 모서리"),
    ((10.0, 0.0), 7.0, "하변 1/3 — 스파이크"),
    ((20.0, 0.0), 1.0, "하변 2/3"),
    ((30.0, 0.0), 5.0, "우하 모서리"),
    ((10.0, 10.0), 1.0, "내부 (1/3, 1/3)"),
    ((15.0, 15.0), 1.0, "셀 중심"),
    ((0.0, 30.0), 3.0, "좌상 모서리"),
    ((30.0, 30.0), 9.0, "우상 모서리"),
]


def test_crosscheck_matrix_file_is_asymmetric(gedos):
    """시험 행렬은 **비대칭**이어야 한다 (절차서 §1).

    대칭이면 상하 반전도 반 칸 밀림도 드러나지 않아 PRO 대조가 헛돈다.
    """
    M = gedos.load_spatial_map_txt(_CROSSCHECK_TXT).matrix
    assert M.shape == (4, 4)
    # 상하 반전으로 자기 자신이 되면 행 방향을 구분할 수 없다
    assert not np.allclose(M, M[::-1]), "상하 대칭 — 행 방향을 구분할 수 없다"
    assert not np.allclose(M, M[:, ::-1]), "좌우 대칭 — 열 방향을 구분할 수 없다"
    # 네 모서리가 전부 달라야 회전·반전이 구분된다
    corners = {M[0, 0], M[0, -1], M[-1, 0], M[-1, -1]}
    assert len(corners) == 4, f"네 모서리가 서로 달라야 한다: {corners}"


def test_crosscheck_4x4_matches_documented_expectations(gedos):
    """절차서 §2 / 규약 문서의 기준값 8개를 고정한다.

    실패하면 **문서와 코드가 어긋난 것**이다. 코드를 고칠지 문서를 고칠지는
    바뀐 쪽이 정한다 — 다만 둘 중 하나는 반드시 갱신해야 한다. PRO 대조 때
    이 값들이 우리 쪽 기준선이기 때문이다.
    """
    sm = gedos.load_spatial_map_txt(_CROSSCHECK_TXT)
    W_cm = H_cm = 3.0                      # 30 mm
    pts = _pts(*[(x / 10.0, y / 10.0) for (x, y), _, _ in _CROSSCHECK_POINTS])
    got = sm.evaluate(pts, W_cm, H_cm)
    for value, (coord, expected, label) in zip(got, _CROSSCHECK_POINTS):
        assert value == pytest.approx(expected, abs=1e-9), (
            f"{label} {coord} mm: {value} != {expected} "
            f"(docs/crosscheck/2026-08-18-spatial-map-griddler.md §2)")


def test_crosscheck_distinguishes_vertex_from_cell_centered(gedos):
    """꼭짓점 정렬과 픽셀 중심이 **실제로 다른 값**을 주는지 확인한다.

    절차서 §3의 전제다 — 내부 (1/3, 1/3)에서 1.000 vs 1.861. 두 규약이 같은
    값을 주는 지점만 보고 있으면 대조가 아무것도 판정하지 못한다. 셀 중심이
    바로 그런 지점이라 §3이 "판정에 쓸 수 없다"고 못 박았다.
    """
    M = gedos.load_spatial_map_txt(_CROSSCHECK_TXT).matrix
    W_cm = H_cm = 3.0
    ny, nx = M.shape

    from scipy.interpolate import RegularGridInterpolator
    # 픽셀 중심 규약이라면 격자가 반 칸 안쪽에 놓인다.
    dy, dx = H_cm / ny, W_cm / nx
    centered = RegularGridInterpolator(
        (np.linspace(dy / 2, H_cm - dy / 2, ny),
         np.linspace(dx / 2, W_cm - dx / 2, nx)),
        M, bounds_error=False, fill_value=None)

    ours = gedos.SpatialMap(mode="csv", matrix=M)
    inner = _pts((1.0, 1.0))                       # (10, 10) mm
    v_vertex = float(ours.evaluate(inner, W_cm, H_cm)[0])
    v_center = float(centered(np.column_stack((inner[:, 1], inner[:, 0])))[0])

    assert v_vertex == pytest.approx(1.0, abs=1e-9)
    assert v_center == pytest.approx(1.8611, abs=1e-3)
    assert abs(v_vertex - v_center) > 0.5, "두 규약이 구분되지 않는 지점이다"

    # 셀 중심은 두 규약이 같다 — 판정에 쓰면 안 된다(절차서 §3의 경고).
    mid = _pts((1.5, 1.5))
    assert float(ours.evaluate(mid, W_cm, H_cm)[0]) == pytest.approx(
        float(centered(np.column_stack((mid[:, 1], mid[:, 0])))[0]), abs=1e-9)


# =============================================================================
# 11. GUI 배선 진입점 (계획 단위 4)
# =============================================================================
#
# GUI 콜백은 Tk 없이 못 돌리지만, **그 콜백이 부르는 로직은 전부 모듈 수준**에
# 있다(set_spatial_map / clear_spatial_map / draw_spatial_map_preview / ...).
# 여기서 검사하는 것이 그 로직이다. 콜백은 이들을 부르기만 하므로 얇다.
#
# 이 절이 지키는 계약 셋:
#   1. **해제는 None이다** — uniform 맵 대체 금지(§7의 비트 동일 근거).
#   2. **부착은 인스턴스에만** — 클래스에 붙이면 전역 누출.
#   3. **미리보기는 origin='lower'** — matrix[0]이 y=0이므로.

def test_spatial_target_info_covers_all_targets(gedos):
    """GUI 표시 메타데이터가 4종을 같은 순서로 덮는다."""
    keys = tuple(k for k, _, _ in gedos.SPATIAL_TARGET_INFO)
    assert keys == gedos.SPATIAL_TARGETS


def test_spatial_target_info_keys_exist_in_translation_table(gedos):
    """라벨·힌트 키가 실제로 _TR에 있어야 한다 — 없으면 GUI에 키 이름이 뜬다."""
    for target, label_key, hint_key in gedos.SPATIAL_TARGET_INFO:
        for key in (label_key, hint_key):
            assert key in gedos._TR, f"{target}: _TR에 {key!r}가 없다"


def test_set_spatial_map_attaches_to_instance(gedos):
    dp = gedos.DiodeParams()
    sm = gedos.SpatialMap(mode="uniform", background=2.0)
    assert gedos.set_spatial_map(dp, "j01", sm) is sm
    assert dp.spatial_j01 is sm
    # 다른 대상은 건드리지 않는다
    assert dp.spatial_j02 is None
    assert dp.spatial_gen is None
    assert dp.spatial_rc is None


def test_set_spatial_map_rejects_unknown_target(gedos):
    dp = gedos.DiodeParams()
    with pytest.raises(ValueError) as exc:
        gedos.set_spatial_map(dp, "rsheet", gedos.SpatialMap())
    assert "rsheet" in str(exc.value)


def test_set_spatial_map_rejects_non_map(gedos):
    dp = gedos.DiodeParams()
    with pytest.raises(TypeError):
        gedos.set_spatial_map(dp, "j01", np.ones((2, 2)))


def test_set_spatial_map_rejects_class_attachment(gedos):
    """클래스에 붙이면 **모든 인스턴스로 전역 누출**된다 — 즉시 막는다.

    solve() 안의 폴백 `dp = DiodeParams()`까지 전부 그 맵을 물려받아,
    "맵을 지웠는데 결과가 그대로"로 나타난다. 되돌리기도 어렵다.
    """
    with pytest.raises(TypeError):
        gedos.set_spatial_map(gedos.DiodeParams, "j01", gedos.SpatialMap())
    with pytest.raises(TypeError):
        gedos.clear_spatial_map(gedos.DiodeParams, "j01")
    # 클래스 기본값은 손상되지 않았다
    assert gedos.DiodeParams.spatial_j01 is None


def test_clear_spatial_map_sets_none_not_uniform(gedos):
    """**해제는 None이다.** uniform 맵으로 대체하면 안 된다.

    값은 1.0으로 같아도 `_spatial_mult`가 노드 길이 배열을 만들어 실제 곱셈이
    실행된다. 무맵 경로의 비트 동일 근거는 "1을 곱한다"가 아니라 "곱셈을 아예
    하지 않는다"이므로(소비 지점이 전부 None 가드 안), uniform 대체는 그 근거를
    없앤다. 계획 §비트 동일 근거 (1).
    """
    dp = gedos.DiodeParams()
    gedos.set_spatial_map(dp, "rc", gedos.SpatialMap(mode="uniform", background=2.0))
    gedos.clear_spatial_map(dp, "rc")
    assert dp.spatial_rc is None
    assert not isinstance(dp.spatial_rc, gedos.SpatialMap)
    assert gedos.get_spatial_map(dp, "rc") is None


def test_clear_is_idempotent_and_safe_when_unset(gedos):
    dp = gedos.DiodeParams()
    gedos.clear_spatial_map(dp, "gen")
    gedos.clear_spatial_map(dp, "gen")
    assert dp.spatial_gen is None


def test_active_spatial_maps_follows_registry_order(gedos):
    dp = gedos.DiodeParams()
    assert gedos.active_spatial_maps(dp) == ()
    gedos.set_spatial_map(dp, "rc", gedos.SpatialMap())
    gedos.set_spatial_map(dp, "j01", gedos.SpatialMap())
    # 붙인 순서가 아니라 SPATIAL_TARGETS 순서로 나온다 (GUI 표시 순서와 일치)
    assert gedos.active_spatial_maps(dp) == ("j01", "rc")
    gedos.clear_spatial_map(dp, "j01")
    assert gedos.active_spatial_maps(dp) == ("rc",)


def test_spatial_map_caption_reports_file_shape_and_range(gedos, tmp_path):
    path = _write(tmp_path, "1,2\n3,4\n", name="press.csv")
    sm = gedos.load_spatial_map_txt(path)
    cap = gedos.spatial_map_caption(sm)
    assert "press.csv" in cap
    assert "2x2" in cap
    assert "1" in cap and "4" in cap
    assert gedos.spatial_map_caption(None) == ""


def test_gui_load_clear_roundtrip_is_bit_identical(gedos, make_mono, tmp_path):
    """GUI가 하는 일(부착 → 해제)을 그대로 밟아도 원래 결과로 비트 복귀한다.

    §7은 맵을 직접 대입했다. 여기서는 **파일 로더 + 부착/해제 진입점**을 거친다
    — GUI가 실제로 타는 경로다.
    """
    m = make_mono()
    dp = gedos.DiodeParams()
    Vb = 0.85 * dp.expected_voc()[2]
    J0 = _solve_current(gedos, m, dp, Vb)

    path = _write(tmp_path, "2,2\n2,2\n")
    gedos.set_spatial_map(dp, "j01", gedos.load_spatial_map_txt(path))
    J_mapped = _solve_current(gedos, m, dp, Vb)

    gedos.clear_spatial_map(dp, "j01")
    J_restored = _solve_current(gedos, m, dp, Vb)

    assert J_mapped != J0, "맵이 실제로 결과를 바꿔야 이 테스트가 의미 있다"
    assert J_restored == J0


def test_preview_draws_with_y_up_and_cell_extent(gedos, tmp_path):
    """미리보기는 **origin='lower'** — matrix[0]이 y=0(셀의 아래쪽)이라서다.

    그대로 그리면(imshow 기본 origin='upper') 화면이 규약과 정반대가 되고,
    사용자는 파일을 거꾸로 만들게 된다.
    """
    from matplotlib.figure import Figure
    path = _write(tmp_path, "9,1\n1,1\n")     # 좌하만 9 — 위아래를 구분한다
    sm = gedos.load_spatial_map_txt(path)
    fig = Figure()
    ax = gedos.draw_spatial_map_preview(fig, sm, 3.0, 2.0, title="t")

    (im,) = ax.get_images()
    assert im.origin == "lower"
    # extent는 mm — 셀 크기 그대로여야 좌표가 맞는다
    assert tuple(im.get_extent()) == (0.0, 30.0, 0.0, 20.0)
    # 컬러바가 붙는다 (배율 값을 읽을 수 있어야 한다)
    assert len(fig.axes) == 2


def test_preview_grid_dots_sit_on_cell_boundary(gedos, tmp_path):
    """격자점 오버레이가 **셀 경계까지** 간다 — 꼭짓점 정렬의 시각 확인.

    픽셀 중심이면 점들이 반 칸 안쪽에 모인다. 그림만 봐도 규약이 보이게 한다.
    """
    from matplotlib.figure import Figure
    path = _write(tmp_path, "1,2,3\n4,5,6\n7,8,9\n")
    sm = gedos.load_spatial_map_txt(path)
    ax = gedos.draw_spatial_map_preview(Figure(), sm, 3.0, 3.0)
    (line,) = ax.get_lines()
    xs, ys = line.get_xdata(), line.get_ydata()
    assert min(xs) == 0.0 and max(xs) == 30.0
    assert min(ys) == 0.0 and max(ys) == 30.0
    assert len(xs) == 9


def test_preview_handles_matrixless_map(gedos):
    """matrix 없는 모드(rectangle 등)를 넘겨도 죽지 않는다."""
    from matplotlib.figure import Figure
    fig = Figure()
    gedos.draw_spatial_map_preview(fig, gedos.SpatialMap(mode="uniform"), 1.0, 1.0)
    assert fig.axes                      # 축은 만들어졌다


# --- 11-b. i18n --------------------------------------------------------------

def _sp_keys(gedos):
    return [k for k in gedos._TR if k.startswith("sp_")]


def test_spatial_i18n_keys_have_both_languages(gedos):
    """EN/KR 한쪽만 넣고 잊으면 그 자리만 다른 언어로 뜬다 — 기계로 잡는다."""
    keys = _sp_keys(gedos)
    assert keys, "sp_* 키가 하나도 없다"
    for key in keys:
        entry = gedos._TR[key]
        assert set(entry) == {"EN", "KR"}, f"{key}: {sorted(entry)}"
        for lang, text in entry.items():
            assert text.strip(), f"{key}[{lang}]가 비어 있다"


def test_spatial_i18n_placeholders_match(gedos):
    """포맷 자리표시자가 언어마다 같아야 한다 — 한쪽만 KeyError가 난다."""
    import re
    for key in _sp_keys(gedos):
        entry = gedos._TR[key]
        holes = {lang: set(re.findall(r"\{(\w+)\}", text))
                 for lang, text in entry.items()}
        assert holes["EN"] == holes["KR"], f"{key}: {holes}"


def test_rc_label_states_the_inverted_meaning(gedos):
    """rc는 의미가 반대다 — 맵이 접촉 저항 R을 곱한다(Gc를 나눈다).

    "1.5 = 접촉이 1.5배 좋아짐"으로 읽는 오해를 라벨에서 막아야 한다
    (계획 §대상 물성의 확정 문구). 방향 자체는
    test_rc_map_multiplies_resistance_not_conductance가 고정한다.
    """
    hint = gedos._TR["sp_rc_hint"]
    assert "WORSE" in hint["EN"].upper()
    assert "나쁨" in hint["KR"]


def test_convention_note_states_first_row_is_bottom(gedos):
    """규약 안내가 **첫 줄 = 아래쪽**을 실제로 말하는지.

    이 한 줄을 빼면 사용자가 파일을 거꾸로 만든다. 규약 문서와 화면이 같은
    말을 하도록 묶어 둔다 — docs/spatial_map_convention.md §1.
    """
    note = gedos._TR["sp_convention"]
    assert "BOTTOM" in note["EN"].upper()
    assert "y=0" in note["EN"]
    assert "아래" in note["KR"]


def test_gui_class_exposes_spatial_callbacks(gedos):
    """GUI 콜백이 실제로 존재해야 버튼 command가 살아 있다."""
    for name in ("_open_spatial_maps", "_load_spatial_map", "_clear_spatial_map",
                 "_refresh_spatial_row", "_refresh_spatial_summary",
                 "_preview_spatial_map", "_spatial_status_text",
                 "_cell_extent_cm"):
        assert callable(getattr(gedos.GEDOSApp, name, None)), f"{name} 없음"


def test_module_dp_starts_with_no_maps(gedos):
    """전역 DP는 맵 없이 시작한다 — 앱을 켜자마자 무맵 경로여야 한다."""
    assert gedos.active_spatial_maps(gedos.DP) == ()


# --- 11-c. GUI 콜백 스모크 (Tk 목으로 실제 코드 경로를 밟는다) ----------------
#
# 창 빌더와 콜백은 위 계약 테스트가 닿지 않는 표면이다 — 거기 오타(NameError)가
# 나면 버튼을 눌러야 발견된다. conftest가 customtkinter/tkinter를 목으로 갈아
# 끼워 두었으므로, __init__을 건너뛴 인스턴스에 필요한 것만 붙여 **실제 메서드
# 본문을 실행**한다. 위젯 호출은 목이 삼키고, 그 사이의 파이썬 코드는 진짜로
# 돈다.


class _Entry:
    def __init__(self, text):
        self._text = text

    def get(self):
        return self._text


def _bare_app(gedos, cell_mm=("30", "30")):
    app = object.__new__(gedos.GEDOSApp)          # __init__(Tk) 우회
    app._status_label = None                       # _status가 조용히 no-op
    app.tb_grid = [_Entry(cell_mm[0]), _Entry(cell_mm[1])]
    return app


@pytest.fixture
def clean_dp(gedos):
    """전역 DP를 건드리는 테스트용 — 끝나면 무맵으로 되돌린다."""
    yield gedos.DP
    for t in gedos.SPATIAL_TARGETS:
        gedos.clear_spatial_map(gedos.DP, t)


def test_open_spatial_maps_window_builds(gedos, clean_dp):
    """창 빌더가 끝까지 돈다 — 위젯 목이 삼켜도 파이썬 오타는 여기서 터진다."""
    app = _bare_app(gedos)
    gedos.GEDOSApp._open_spatial_maps(app)
    assert set(app._spatial_rows) == set(gedos.SPATIAL_TARGETS)


def test_gui_load_callback_attaches_to_module_dp(gedos, clean_dp, tmp_path,
                                                 monkeypatch):
    """불러오기 콜백이 **전역 DP**에 붙인다 — GUI의 calc_iv가 넘기는 그 인스턴스."""
    path = _write(tmp_path, "1,2\n3,4\n", name="gui.csv")
    monkeypatch.setattr(gedos.filedialog, "askopenfilename", lambda **kw: path)

    app = _bare_app(gedos)
    gedos.GEDOSApp._open_spatial_maps(app)
    gedos.GEDOSApp._load_spatial_map(app, "gen")

    sm = gedos.get_spatial_map(gedos.DP, "gen")
    assert isinstance(sm, gedos.SpatialMap)
    assert sm.load_report["path"] == path
    assert gedos.active_spatial_maps(gedos.DP) == ("gen",)


def test_gui_clear_callback_restores_none(gedos, clean_dp, tmp_path, monkeypatch):
    path = _write(tmp_path, "1,2\n3,4\n")
    monkeypatch.setattr(gedos.filedialog, "askopenfilename", lambda **kw: path)

    app = _bare_app(gedos)
    gedos.GEDOSApp._open_spatial_maps(app)
    gedos.GEDOSApp._load_spatial_map(app, "j02")
    assert gedos.get_spatial_map(gedos.DP, "j02") is not None

    gedos.GEDOSApp._clear_spatial_map(app, "j02")
    assert gedos.DP.spatial_j02 is None          # uniform 맵이 아니라 None
    assert gedos.active_spatial_maps(gedos.DP) == ()


def test_gui_load_cancelled_leaves_dp_untouched(gedos, clean_dp, monkeypatch):
    """파일 선택을 취소하면(빈 문자열) 아무것도 바뀌지 않는다."""
    monkeypatch.setattr(gedos.filedialog, "askopenfilename", lambda **kw: "")
    app = _bare_app(gedos)
    gedos.GEDOSApp._load_spatial_map(app, "rc")
    assert gedos.active_spatial_maps(gedos.DP) == ()


def test_gui_load_rejects_bad_file_without_attaching(gedos, clean_dp, tmp_path,
                                                     monkeypatch):
    """검증 실패 시 DP를 건드리지 않는다 — 반쯤 적용된 상태가 남으면 안 된다."""
    bad = _write(tmp_path, "1,2\n3,0\n")       # 0은 배율이 될 수 없다
    monkeypatch.setattr(gedos.filedialog, "askopenfilename", lambda **kw: bad)
    app = _bare_app(gedos)
    gedos.GEDOSApp._load_spatial_map(app, "j01")
    assert gedos.active_spatial_maps(gedos.DP) == ()


def test_cell_extent_reads_gui_fields_in_cm(gedos):
    app = _bare_app(gedos, cell_mm=("156.0", "78.0"))
    assert gedos.GEDOSApp._cell_extent_cm(app) == (15.6, 7.8)


def test_cell_extent_falls_back_to_geo_on_garbage(gedos):
    """입력란이 망가져 있어도 미리보기가 죽지 않고 현재 GEO로 그린다."""
    app = _bare_app(gedos, cell_mm=("", "abc"))
    W, H = gedos.GEDOSApp._cell_extent_cm(app)
    assert (W, H) == (float(gedos.GEO.W), float(gedos.GEO.H))


def test_status_text_counts_active_maps(gedos, clean_dp):
    """요약 라벨의 적용 개수 **와 총 개수** 둘 다 확인한다.

    총 개수를 문자열에 박으면 안 된다 — v28.62에서 대상이 4종 → 5종이 되면서
    `'{n} of 4 active'`가 **"4개 중 5개 적용"** 을 낼 수 있었다.
    `SPATIAL_INVERTED_TARGETS`로 올린 하드코딩 `target == 'rc'`와 같은 부류다.

    기존 단언(0개·1개)은 그대로 두고 총 개수 검사를 덧붙인다.
    """
    app = _bare_app(gedos)
    total = len(gedos.SPATIAL_TARGETS)
    txt0 = gedos.GEDOSApp._spatial_status_text(app)
    assert "0" in txt0
    assert str(total) in txt0, (
        f"요약 라벨에 총 개수 {total}이 없다: {txt0!r} — "
        f"len(SPATIAL_TARGETS)에서 받아야 한다")

    gedos.set_spatial_map(gedos.DP, "rc", gedos.SpatialMap())
    assert "1" in gedos.GEDOSApp._spatial_status_text(app)

    # 전부 적용하면 "n개 중 n개" — 같은 수가 두 번 나온다. 총 개수가 다른 수로
    # 박혀 있으면 여기서 갈린다.
    for t in gedos.SPATIAL_TARGETS:
        gedos.set_spatial_map(gedos.DP, t, gedos.SpatialMap())
    txt_all = gedos.GEDOSApp._spatial_status_text(app)
    assert txt_all.count(str(total)) >= 2, (
        f"전부 적용했는데 라벨이 {txt_all!r}이다 — 총 개수가 하드코딩돼 있다")


# =============================================================================
# 12. 예제 파일 (examples/spatial_maps/) — 배포물이 실제로 읽히는가
# =============================================================================
#
# `docs/spatial_map_usage.md`가 가리키는 예제 파일들이다. 사용자가 처음 만나는
# 파일이므로 **깨진 채로 배포되면 안 된다.** 예제가 로드 실패하면 사용자는 자기
# 파일이 잘못됐다고 의심하지, 예제를 의심하지 않는다.
#
# 파일 목록을 코드에 박지 않고 **glob으로 찾는다.** 목록을 박으면 새 예제를
# 추가한 사람이 여기를 안 고쳐도 초록불이 나온다 — 감시하지 않는 것이 조용히
# 늘어나는 그 실패 유형이다(`_NAMED_SOLVERS`에 `_solve_single_bifacial`이
# 빠져 있던 것과 같다). 대신 목록이 비면 통과가 무의미해지므로
# `test_examples_directory_is_not_empty`가 그것을 막는다.

_EXAMPLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "examples", "spatial_maps")


def _example_files():
    if not os.path.isdir(_EXAMPLES_DIR):
        return []
    return sorted(
        os.path.join(_EXAMPLES_DIR, n)
        for n in os.listdir(_EXAMPLES_DIR)
        if n.lower().endswith((".txt", ".csv")))


_EXAMPLE_FILES = _example_files()
_EXAMPLE_IDS = [os.path.basename(p) for p in _EXAMPLE_FILES]


def test_examples_directory_is_not_empty():
    """예제 디렉터리가 살아 있고 파일이 있다.

    아래 파라미터화는 glob 결과가 비면 **0건 수집으로 조용히 통과**한다.
    디렉터리를 옮기거나 비웠을 때 그 사실이 초록불로 덮이지 않게 여기서 막는다.
    `docs/spatial_map_usage.md` §3이 4종을 표로 안내하므로 그 수를 하한으로 둔다.
    """
    assert os.path.isdir(_EXAMPLES_DIR), f"{_EXAMPLES_DIR}가 없다"
    assert len(_EXAMPLE_FILES) >= 4, (
        f"예제 파일이 {len(_EXAMPLE_FILES)}개뿐이다 — "
        f"docs/spatial_map_usage.md §3은 4종을 안내한다: {_EXAMPLE_IDS}")


@pytest.mark.parametrize("path", _EXAMPLE_FILES, ids=_EXAMPLE_IDS)
def test_every_example_file_loads(gedos, path):
    """모든 예제 파일이 실제 로더로 읽힌다.

    로더는 0·음수·NaN·inf·2x2 미만·열 개수 불일치를 전부 거부하므로
    (§9), 이 한 줄이 통과하면 파일이 규약에 맞는다는 뜻이다.
    여기서는 그 위에 **결과가 쓸 수 있는 상태인지**까지 본다.
    """
    sm = gedos.load_spatial_map_txt(path)
    M = sm.matrix
    assert M.ndim == 2 and M.shape[0] >= 2 and M.shape[1] >= 2
    assert np.all(np.isfinite(M)) and np.all(M > 0.0)
    assert sm.load_report["path"] == path
    assert sm.load_report["shape"] == tuple(int(v) for v in M.shape)


@pytest.mark.parametrize("path", _EXAMPLE_FILES, ids=_EXAMPLE_IDS)
def test_every_example_file_explains_itself(gedos, path):
    """예제 파일 머리에 `#` 주석 설명이 있다.

    예제의 값어치는 숫자가 아니라 **무엇을 뜻하는 숫자인지**에 있다. 특히 `rc`는
    방향이 직관과 반대라(§6) 주석이 없으면 반대로 쓰기 쉽다. 로더가 `#` 줄을
    건너뛰므로 주석이 있어도 로드에는 영향이 없다 —
    `load_report['skipped_lines']`로 실제로 건너뛰었음을 확인한다.
    """
    with open(path, encoding="utf-8-sig") as fh:
        lines = [ln.strip() for ln in fh if ln.strip()]
    assert lines, f"{os.path.basename(path)}: 비어 있다"
    assert lines[0].startswith("#"), (
        f"{os.path.basename(path)}: 첫 줄이 주석이 아니다 — 예제 파일은 머리에 "
        f"용도와 값의 의미를 적는다")
    sm = gedos.load_spatial_map_txt(path)
    assert sm.load_report["skipped_lines"] >= 1


@pytest.mark.parametrize("path", _EXAMPLE_FILES, ids=_EXAMPLE_IDS)
def test_every_example_file_attaches_to_a_real_target(gedos, clean_dp, path):
    """예제를 4종 어디에 붙였다 떼도 상태가 깨끗하게 돌아온다.

    파일이 읽히는 것과 **쓸 수 있는 것**은 다르다. 사용자가 GUI에서 하는 일
    (불러오기 → 적용 → 해제)을 그대로 한 번 돌려 본다.
    """
    sm = gedos.load_spatial_map_txt(path)
    for target in gedos.SPATIAL_TARGETS:
        gedos.set_spatial_map(gedos.DP, target, sm)
        assert gedos.get_spatial_map(gedos.DP, target) is sm
        gedos.clear_spatial_map(gedos.DP, target)
        assert gedos.get_spatial_map(gedos.DP, target) is None
    assert gedos.active_spatial_maps(gedos.DP) == ()


def test_usage_doc_points_at_the_example_files():
    """`docs/spatial_map_usage.md`가 실재하는 예제 파일만 가리킨다.

    문서가 없는 파일을 안내하면 사용자는 자기 설치가 잘못된 줄 안다. 파일을
    이름 바꾸거나 지웠을 때 문서가 따라오지 않는 것을 여기서 잡는다.
    """
    doc = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docs", "spatial_map_usage.md")
    assert os.path.isfile(doc), "docs/spatial_map_usage.md가 없다"
    with open(doc, encoding="utf-8") as fh:
        text = fh.read()
    for name in _EXAMPLE_IDS:
        assert name in text, (
            f"사용 안내가 {name}을 언급하지 않는다 — 예제를 추가했으면 "
            f"docs/spatial_map_usage.md §3 표에도 넣을 것")
    # 반대 방향: 문서가 `examples/spatial_maps/<파일>` 로 가리키는 것은 실재해야
    # 한다. 경로 접두사로 좁혀서 본다 — 본문에 인용된 오류 메시지의 파일명
    # (edge.txt 등)이나 대조용 파일(spatial_4x4.txt)까지 잡으면 문서를 고칠
    # 때마다 이 테스트가 헛되이 깨진다.
    import re
    referenced = set(re.findall(r"examples/spatial_maps/([A-Za-z0-9_.-]+)", text))
    missing = {n for n in referenced if not os.path.isfile(
        os.path.join(_EXAMPLES_DIR, n))}
    assert not missing, (
        f"사용 안내가 실재하지 않는 예제 파일을 가리킨다: {sorted(missing)}")


# =============================================================================
# 13. 설정 창 개선 (v28.63) — 스크롤 · 형식 도움말 · 예제 경로 · 미리보기 통계
# =============================================================================
#
# **물리 무관한 GUI 변경이다.** 그래서 여기서 지키는 것은 계산값이 아니라
# "화면이 말하는 것과 코드가 하는 것이 같은가"다. 세 결합을 묶는다:
#
#   1. 안내 문구 ↔ 로더  — 예시 행렬이 실제로 로더를 통과하는가.
#   2. 안내 문구 ↔ 레지스트리 — 방향 주의가 SPATIAL_INVERTED_TARGETS에서
#      오는가(목록을 GUI에 다시 적으면 6종이 되는 날 안내만 5종으로 남는다).
#   3. 통계 ↔ 행렬 — 미리보기에 적히는 수가 실제 행렬의 수인가.
#
# 스크롤 자체(휠이 몇 픽셀 움직이는가)는 Tk 없이 검증할 수 없다. 대신 **바인딩
# 경로가 실제로 도는지**를 목으로 밟는다 — 거기 오타가 나면 창을 띄워 굴려 봐야
# 발견된다.


def _t_any(gedos, key, haystack):
    """어느 언어로 렌더됐든 그 키의 문구가 들어 있는지."""
    return any(v[:24] in haystack for v in gedos._TR[key].values())


# --- 13-a. 예시 행렬이 로더를 통과한다 ---------------------------------------

def test_help_sample_actually_loads(gedos, tmp_path):
    """GUI가 "복사해 쓰라"고 내주는 행렬이 **실제 로더로 읽힌다.**

    안내와 로더가 갈라지면 사용자는 안내대로 만든 파일이 거부당하고, 자기
    파일이 아니라 프로그램을 의심한다. 상수를 GUI 문자열에 묻지 않고
    `SPATIAL_HELP_SAMPLE`로 뺀 이유가 이 한 줄을 쓸 수 있게 하기 위해서다.
    """
    path = _write(tmp_path, gedos.SPATIAL_HELP_SAMPLE, name="help_sample.txt")
    sm = gedos.load_spatial_map_txt(path)
    assert sm.matrix.shape == (4, 4), "안내가 4x4라고 말한다"
    assert np.all(sm.matrix > 0.0) and np.all(np.isfinite(sm.matrix))
    # 주석 줄이 실제로 건너뛰어졌다 — "# 로 주석 가능"이라는 안내의 근거다.
    assert sm.load_report["skipped_lines"] >= 1


def test_help_sample_is_not_uniform(gedos, tmp_path):
    """예시가 전부 1.0이면 무엇을 고쳐야 하는지 안 보인다.

    "복사해서 숫자만 고치세요"라는 안내가 성립하려면 고칠 자리가 예시 안에
    보여야 한다. 균일 확인용 파일은 examples/uniform_4x4.txt가 따로 있다.
    """
    path = _write(tmp_path, gedos.SPATIAL_HELP_SAMPLE, name="help_sample.txt")
    M = gedos.load_spatial_map_txt(path).matrix
    assert M.min() < M.max(), "예시 행렬이 균일하다 — 구조가 보이지 않는다"


# --- 13-b. 예제 폴더 경로 ------------------------------------------------------

def test_examples_dir_helper_points_at_the_shipped_folder(gedos):
    """`spatial_examples_dir()`가 §12가 검사하는 그 폴더를 가리킨다.

    Load 대화상자의 시작 경로가 여기서 온다. 두 경로가 갈리면 대화상자만
    엉뚱한 곳에서 열리는데, 테스트는 전부 초록불이라 아무도 모른다.
    """
    d = gedos.spatial_examples_dir()
    assert d is not None, "저장소에는 예제 폴더가 있다"
    assert os.path.isdir(d)
    assert (os.path.normcase(os.path.abspath(d))
            == os.path.normcase(os.path.abspath(_EXAMPLES_DIR)))


def test_examples_dir_returns_none_when_missing(gedos, monkeypatch):
    """폴더가 없으면 **None**이다 — 빈 문자열도 CWD도 아니다.

    호출부가 `initialdir` 키 자체를 빼도록 하기 위해서다. Tk는 initialdir=None을
    "지정 없음"이 아니라 CWD로 해석하므로, 그대로 넘기면 폴더가 없는 배포에서만
    시작 경로가 조용히 달라진다.
    """
    monkeypatch.setattr(gedos.os.path, "isdir", lambda p: False)
    assert gedos.spatial_examples_dir() is None


def test_load_dialog_starts_in_the_examples_folder(gedos, clean_dp, tmp_path,
                                                   monkeypatch):
    """불러오기 대화상자가 예제 폴더에서 열린다 — 처음 쓰는 사람이 예제부터 본다."""
    seen = {}
    target_file = _write(tmp_path, "1,2\n3,4\n", name="dlg.csv")

    def _fake(**kw):
        seen.update(kw)
        return target_file

    monkeypatch.setattr(gedos.filedialog, "askopenfilename", _fake)
    app = _bare_app(gedos)
    gedos.GEDOSApp._load_spatial_map(app, "gen")

    assert seen.get("initialdir") == gedos.spatial_examples_dir()
    assert gedos.get_spatial_map(gedos.DP, "gen") is not None


def test_load_dialog_omits_initialdir_when_examples_missing(gedos, clean_dp,
                                                            monkeypatch):
    """예제 폴더가 없으면 initialdir을 **키째로** 넘기지 않는다."""
    seen = {}

    def _fake(**kw):
        seen.update(kw)
        return ""            # 취소 — DP는 건드리지 않는다

    monkeypatch.setattr(gedos, "spatial_examples_dir", lambda: None)
    monkeypatch.setattr(gedos.filedialog, "askopenfilename", _fake)
    app = _bare_app(gedos)
    gedos.GEDOSApp._load_spatial_map(app, "j01")

    assert "initialdir" not in seen
    assert gedos.active_spatial_maps(gedos.DP) == ()


# --- 13-c. 미리보기 통계 -------------------------------------------------------

def test_map_stats_reports_matrix_values(gedos):
    """min/max/mean/형상이 실제 행렬에서 나온다."""
    M = np.array([[1.0, 2.0], [3.0, 6.0]])
    st = gedos.spatial_map_stats(gedos.SpatialMap(mode="csv", matrix=M))
    assert (st["ny"], st["nx"]) == (2, 2)
    assert st["min"] == 1.0
    assert st["max"] == 6.0
    assert st["mean"] == pytest.approx(3.0)


def test_map_stats_none_without_matrix(gedos):
    """맵이 없거나 행렬이 없으면 None — 캡션이 통계 줄을 아예 안 붙인다."""
    assert gedos.spatial_map_stats(None) is None
    assert gedos.spatial_map_stats(gedos.SpatialMap(mode="uniform")) is None


def test_map_stats_distinguishes_uniform_levels(gedos):
    """전부 1.0인 맵과 전부 2.0인 맵을 **수치가** 구분한다.

    그림은 구분하지 못한다 — imshow가 자동 정규화하므로 둘 다 단색이다.
    통계 줄을 붙인 이유가 이것이고, 그 이유가 사라지지 않았음을 고정한다.
    """
    a = gedos.spatial_map_stats(
        gedos.SpatialMap(mode="csv", matrix=np.ones((3, 3))))
    b = gedos.spatial_map_stats(
        gedos.SpatialMap(mode="csv", matrix=np.full((3, 3), 2.0)))
    assert a["min"] == a["max"] == 1.0
    assert b["min"] == b["max"] == 2.0
    assert a != b


def test_preview_caption_carries_the_numbers(gedos, clean_dp):
    """미리보기 콜백이 캡션에 통계 문자열을 실제로 넣는다.

    `spatial_map_stats`가 맞아도 캡션에 안 붙으면 화면에서는 아무 소용이 없다.
    콜백 본문을 목으로 밟아 `configure(text=...)`에 들어간 문자열을 본다.
    """
    from matplotlib.figure import Figure

    class _Cap:
        def __init__(self):
            self.text = ""

        def configure(self, **kw):
            self.text = kw.get("text", self.text)

    class _Canvas:
        def draw(self):
            pass

    M = np.array([[1.0, 2.0], [3.0, 6.0]])
    gedos.set_spatial_map(gedos.DP, "j01", gedos.SpatialMap(mode="csv", matrix=M))
    app = _bare_app(gedos)
    cap = _Cap()
    gedos.GEDOSApp._preview_spatial_map(app, "j01", Figure(), _Canvas(), cap)

    assert "6" in cap.text and "1" in cap.text, cap.text
    # 뒤집힘 안내는 통계를 붙인 뒤에도 남아 있어야 한다 — 규약 안내가 통계에
    # 밀려 사라지면 사용자가 파일을 거꾸로 만든다.
    assert _t_any(gedos, "sp_flip_note", cap.text)


# --- 13-d. 형식 도움말 창 -------------------------------------------------------

def test_format_help_window_builds(gedos):
    """도움말 창 빌더가 끝까지 돈다 — 위젯 목이 삼켜도 파이썬 오타는 여기서 터진다."""
    app = _bare_app(gedos)
    gedos.GEDOSApp._show_spatial_format_help(app)


def test_help_button_and_callback_exist(gedos):
    """헤더 버튼이 부를 메서드가 실제로 있다."""
    for name in ("_show_spatial_format_help", "_bind_wheel_to_scrollframe"):
        assert callable(getattr(gedos.GEDOSApp, name, None)), f"{name} 없음"


def test_inverted_warning_text_comes_from_the_registry(gedos):
    """방향 주의가 `SPATIAL_INVERTED_TARGETS`를 그대로 렌더한다.

    안내에 목록을 다시 적으면 대상이 6종이 되는 날 화면만 5종으로 남는다 —
    v28.62가 고친 하드코딩 총 개수와 같은 종류의 실패다.
    """
    for lang in ("EN", "KR"):
        rendered = gedos._TR["sp_help_inverted"][lang].format(
            targets=", ".join(gedos.SPATIAL_INVERTED_TARGETS))
        for t in gedos.SPATIAL_INVERTED_TARGETS:
            assert t in rendered, f"{lang}: {t}가 안내에 없다"


def test_help_rules_state_every_rejection_the_loader_performs(gedos):
    """규칙 안내가 로더의 거부 조건을 **전부** 말한다.

    로더가 거부하는데 안내가 말하지 않으면 사용자는 이유를 모른 채 막힌다.
    문구가 아니라 **개념 단어**로 확인한다 — 번역을 다듬을 때마다 깨지면
    아무도 안 고치고 지워 버린다.
    """
    rules = gedos._TR["sp_help_rules"]
    assert "2x2" in rules["EN"] and "2x2" in rules["KR"]
    assert "NaN" in rules["EN"] and "NaN" in rules["KR"]
    assert "inf" in rules["EN"] and "inf" in rules["KR"]
    assert "#" in rules["EN"] and "#" in rules["KR"]
    for txt in rules.values():
        assert chr(10) in txt, "규칙은 여러 줄이다 — 한 줄로 뭉치면 안 읽힌다"


def test_help_rules_state_the_bottom_row_convention(gedos):
    """가장 틀리기 쉬운 규약(첫 줄 = 아래쪽)이 도움말에도 있다.

    `sp_convention`은 설정 창 헤더에만 뜬다. 도움말만 보고 파일을 만드는
    사람이 있으므로 여기서도 말해야 한다.
    """
    rules = gedos._TR["sp_help_rules"]
    assert "BOTTOM" in rules["EN"].upper() and "y=0" in rules["EN"]
    assert "아래" in rules["KR"] and "y=0" in rules["KR"]


# --- 13-e. 휠 바인딩 경로 -------------------------------------------------------

def test_wheel_binding_walks_the_subtree(gedos):
    """휠 바인딩이 스크롤 프레임 **하위 트리 전체**에 걸린다.

    카드가 하위에 있으므로 프레임에만 걸면 목록 위에서 굴려도 안 움직인다.
    (bind_all을 쓰지 않는 이유는 `_bind_wheel_to_scrollframe` 도크스트링.)
    """
    bound = []

    class _W:
        def __init__(self, children=()):
            self._children = list(children)

        def bind(self, seq, fn):
            bound.append((self, seq))

        def winfo_children(self):
            return self._children

    leaf = _W()
    card = _W([leaf])
    frame = _W([card])
    frame._parent_canvas = object()

    gedos.GEDOSApp._bind_wheel_to_scrollframe(
        object.__new__(gedos.GEDOSApp), frame)
    for w in (frame, card, leaf):
        seqs = {seq for obj, seq in bound if obj is w}
        assert seqs == {"<MouseWheel>", "<Button-4>", "<Button-5>"}, seqs


def test_wheel_binding_is_a_noop_without_a_canvas(gedos):
    """캔버스를 못 찾으면 조용히 아무것도 하지 않는다.

    CustomTkinter 내부 속성(`_parent_canvas`)에 기대는 코드다. 버전이 바뀌어
    이름이 사라지면 **창이 안 뜨는** 것이 아니라 휠만 안 되는 것이 맞다.
    """
    class _W:
        def bind(self, *a):
            raise AssertionError("바인딩을 시도하면 안 된다")

        def winfo_children(self):
            return []

    gedos.GEDOSApp._bind_wheel_to_scrollframe(
        object.__new__(gedos.GEDOSApp), _W())


def test_wheel_scroll_direction_by_platform(gedos):
    """Windows delta · macOS delta · X11 Button-4/5 셋 다 위/아래가 맞는다.

    부호만 본다(크기를 곱하지 않는다) — 곱하면 플랫폼마다 감도가 달라진다.
    """
    moved = []

    class _Canvas:
        def yview_scroll(self, n, what):
            moved.append(n)

    handlers = []

    class _W:
        def bind(self, seq, fn):
            handlers.append((seq, fn))

        def winfo_children(self):
            return []

    frame = _W()
    frame._parent_canvas = _Canvas()
    gedos.GEDOSApp._bind_wheel_to_scrollframe(
        object.__new__(gedos.GEDOSApp), frame)
    on_wheel = dict(handlers)["<MouseWheel>"]

    class _Ev:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    on_wheel(_Ev(delta=120))       # Windows 위로
    on_wheel(_Ev(delta=-120))      # Windows 아래로
    on_wheel(_Ev(delta=1))         # macOS 위로
    on_wheel(_Ev(delta=-1))        # macOS 아래로
    on_wheel(_Ev(num=4))           # X11 위로
    on_wheel(_Ev(num=5))           # X11 아래로
    assert moved == [-1, 1, -1, 1, -1, 1]


# =============================================================================
# 14. 전류 추출 방식 — 읽기 전용 상태 표시 (v28.64)
# =============================================================================
#
# 이 절은 `tests/test_spatial_map.py`의 관심사(공간 분포)가 아니라 **GUI 상태
# 표시**를 다루지만, 검사 방식이 §13과 같아서(모듈 상수 ↔ 화면 문자열의 결합)
# 여기 붙인다. 별도 파일로 떼면 `gedos` 픽스처 세션이 하나 더 뜨고 로드에만
# 5초가 더 든다.
#
# **기능은 그대로다.** 솔버는 여전히 extraction_method를 읽지 않는다. 여기서
# 고정하는 것은 "고를 수 없는 것을 선택 위젯으로 두지 않는다"와, 위젯을
# 지우면서 **GridDesign에 들어가는 값이 바뀌지 않았다**는 두 가지다.


def test_fixed_label_maps_to_probe_point(gedos):
    """고정 라벨 상수가 `_apply_grid_design`의 매핑 키와 같다.

    상수와 매핑 표가 갈리면 조용히 `probe_point` 폴백으로 떨어진다 — **같은
    값이 나오므로 아무도 눈치채지 못한다.** 그 폴백이 정답을 가려 주는 상황이라
    소스에서 직접 확인한다.
    """
    import inspect
    src = inspect.getsource(gedos.GEDOSApp._apply_grid_design)
    assert "EXTRACTION_METHOD_FIXED_LABEL: \"probe_point\"" in src, (
        "매핑 표가 상수 대신 문자열 리터럴을 쓰고 있다 — 갈려도 폴백이 덮는다")
    assert gedos.EXTRACTION_METHOD_FIXED_LABEL == "At Probe Point (I-V tester)"


def test_fixed_label_is_not_translated(gedos):
    """고정 라벨은 **번역 대상이 아니다.**

    GridDesign에 들어가는 값을 정하는 문자열이라, 언어를 바꿨다고 매핑이
    달라지면 안 된다. 화면에 뜨는 것은 `extract_probe_only`(번역됨)이고
    이것은 내부 키다 — 둘을 섞지 않는다.
    """
    assert gedos.EXTRACTION_METHOD_FIXED_LABEL not in [
        v for entry in gedos._TR.values() for v in entry.values()]


def test_extract_label_key_has_both_languages(gedos):
    """표시 라벨이 EN/KR 둘 다 있다 — 한쪽만 넣으면 그 자리만 다른 언어로 뜬다."""
    entry = gedos._TR['extract_probe_only']
    assert set(entry) == {"EN", "KR"}
    assert entry["EN"] == "Probe Point"
    assert entry["KR"] == "프로브 점 방식"


def test_no_disabled_dropdown_remains(gedos):
    """비활성 드롭다운과 "(not implemented)" 라벨이 **코드에서 사라졌다.**

    v28.64의 요지는 "고를 수 없는데 드롭다운 모양이면 곧 열릴 것처럼 보인다"
    였다. 위젯이 남아 있으면 그 요지가 무너지므로 소스에서 확인한다.
    변경 이력(파일 도크스트링)은 검사 대상이 아니다 — 거기 남는 것이 맞다.
    """
    import inspect
    src = inspect.getsource(gedos.GEDOSApp._build_sidebar)
    assert "(not implemented)" not in src
    assert "_extract_method_dropdown" not in src
    assert "_rear_extract_method_dropdown" not in src
    # 대신 라벨이 있다 — 전면·후면 두 곳.
    assert src.count("_t('extract_probe_only')") == 2, (
        "전면/후면 두 곳 모두 상태 라벨이어야 한다")


def test_state_labels_are_registered_for_language_switch(gedos):
    """언어를 바꾸면 상태 라벨도 그 자리에서 바뀐다.

    드롭다운이던 시절에는 값이 영문 고정이라 전환 대상이 아니었다. 라벨로
    바꾸면서 번역 대상이 됐고, 라벨은 자동으로 안 바뀌므로
    `_update_sidebar_labels`에 등록해야 한다. 등록을 빠뜨리면 한국어 모드에서
    이 두 자리만 영어로 남는다 — 사람 눈으로는 잘 안 걸리는 유형이다.
    """
    import inspect
    src = inspect.getsource(gedos.GEDOSApp._update_sidebar_labels)
    for name in ("_extract_method_lbl", "_rear_extract_method_lbl"):
        assert name in src, f"{name}이 언어 전환 갱신에 등록되지 않았다"
    assert "extract_probe_only" in src


def test_extraction_method_value_is_unchanged(gedos):
    """GridDesign에 들어가는 값은 여전히 `probe_point`다 — **기능 무변경.**

    위젯을 지우는 변경이 결과를 바꾸지 않았다는 축. StringVar를 남긴 이유가
    이것이다(지우면 읽기 경로가 getattr 폴백으로 갈아탄다).
    """
    g = gedos.GridDesign(n_fingers=4, n_busbars=1, w_finger=50e-4,
                        w_busbar=600e-4)
    assert g.extraction_method == "probe_point", (
        "기본값이 바뀌었다 — v28.64는 GUI만 건드린다")


# =============================================================================
# 15. 설정 창 싱글톤 (v28.65) — "한 번 눌렀는데 창이 여러 개"
# =============================================================================
#
# 보고된 증상은 "SPATIAL MAPS 버튼 한 번 눌렀는데 창이 4개"였다. 조사 결과
# **한 번의 클릭이 여러 창을 만드는 경로는 코드에 없다**(콜백 1곳, 사이드바
# 1회 생성, 휠 바인딩은 버튼 이벤트에 닿지 않음 — 아래 세 테스트가 그 셋을
# 각각 고정한다). 실제 원인이 무엇이든(클릭 중복 전달 등) 싱글톤이 증상을
# 구조적으로 없앤다.
#
# 창이 여러 개면 지저분한 것으로 끝나지 않는다. `_spatial_rows`가 딕셔너리
# 하나라 두 번째 창이 첫 번째 창의 등록을 덮어쓰고, 아무 창이나 하나 닫으면
# `_on_close`가 그것을 비워 **아직 열려 있는 창들까지 같이 죽는다.**


def _toplevel_calls(gedos):
    return gedos.ctk.CTkToplevel.call_count


# --- 15-a. 클릭 → 콜백 경로가 하나뿐이다 ---------------------------------------

def test_open_callback_is_bound_exactly_once(gedos):
    """`_open_spatial_maps`를 부르는 지점이 **정확히 한 곳**이다.

    사이드바 카드의 버튼 `command=` 하나. 두 곳이 되면 한 번의 클릭이 두 창을
    만들 수 있고, 그것이 보고된 증상의 첫 번째 가설이었다.
    """
    import ast
    import inspect
    src = inspect.getsource(gedos.GEDOSApp._build_sidebar)
    assert src.count("command=self._open_spatial_maps") == 1, (
        "사이드바에서 창 열기 콜백이 한 번만 걸려야 한다")

    # 모듈 도크스트링(=변경 이력)은 빼고 센다 — 거기서는 이 코드를 **설명**
    # 하므로 같은 문자열이 산문으로 등장한다. 이력을 고칠 때마다 깨지는
    # 테스트는 아무도 안 고치고 지워 버린다.
    whole = inspect.getsource(gedos)
    module_doc = ast.get_docstring(ast.parse(whole)) or ""
    code = whole.replace(module_doc, "", 1)
    assert code.count("command=self._open_spatial_maps") == 1
    assert code.count("def _open_spatial_maps") == 1


def test_sidebar_is_built_once(gedos):
    """사이드바를 두 번 만들면 버튼도 둘이 된다 — 호출 지점이 하나뿐이다.

    보고된 증상의 세 번째 가설(i18n 갱신·사이드바 재생성이 버튼을 여러 번
    만든다)이 성립하지 않음을 고정한다. 언어 전환은 `_update_sidebar_labels`가
    **기존 위젯의 text만** 바꾸며 위젯을 다시 만들지 않는다.
    """
    import inspect
    whole = inspect.getsource(gedos)
    assert whole.count("self._build_sidebar(") == 1

    switch = inspect.getsource(gedos.GEDOSApp._update_sidebar_labels)
    assert "_build_sidebar" not in switch, (
        "언어 전환이 사이드바를 다시 만들면 버튼이 중복된다")
    assert "CTkButton" not in switch, (
        "언어 전환은 위젯을 만들지 않고 text만 갱신해야 한다")


def test_wheel_binding_never_touches_button_events(gedos):
    """휠 바인딩이 **클릭 이벤트를 건드리지 않는다.**

    보고된 증상의 두 번째 가설(v28.63의 하위 트리 바인딩이 버튼 콜백을 중복
    등록했다)이 성립하지 않음을 고정한다. `<Button-4>`/`<Button-5>`는 X11의
    휠 위/아래이고 `<Button-1>`(클릭)과 다른 이벤트다 — 그 사실에 기대고 있으니
    누가 `<Button-1>`을 추가하면 여기서 걸려야 한다.
    """
    seqs = []

    class _W:
        def bind(self, seq, fn):
            seqs.append(seq)

        def winfo_children(self):
            return []

    frame = _W()
    frame._parent_canvas = object()
    gedos.GEDOSApp._bind_wheel_to_scrollframe(
        object.__new__(gedos.GEDOSApp), frame)

    assert set(seqs) == {"<MouseWheel>", "<Button-4>", "<Button-5>"}
    assert "<Button-1>" not in seqs, "휠 바인딩이 클릭을 가로채면 안 된다"
    assert not any("Double" in s or "ButtonRelease" in s for s in seqs)


# --- 15-b. 싱글톤 ---------------------------------------------------------------

def test_second_open_does_not_create_a_new_window(gedos, clean_dp):
    """이미 열려 있으면 **새 창을 만들지 않는다** — 앞으로 올리기만 한다."""
    app = _bare_app(gedos)
    gedos.ctk.CTkToplevel.reset_mock()

    gedos.GEDOSApp._open_spatial_maps(app)
    assert _toplevel_calls(gedos) == 1

    for _ in range(3):
        gedos.GEDOSApp._open_spatial_maps(app)
    assert _toplevel_calls(gedos) == 1, (
        f"네 번 눌렀는데 창이 {_toplevel_calls(gedos)}개 만들어졌다 — "
        f"보고된 증상 그대로다")


def test_second_open_raises_the_existing_window(gedos, clean_dp, monkeypatch):
    """두 번째 호출은 **기존 창을** 앞으로 올린다(아무 일도 안 하면 안 된다)."""
    raised = []
    monkeypatch.setattr(gedos.GEDOSApp, "_raise_once",
                        lambda self, w, **kw: raised.append(w))
    app = _bare_app(gedos)
    gedos.ctk.CTkToplevel.reset_mock()

    gedos.GEDOSApp._open_spatial_maps(app)
    first = app._spatial_win
    raised.clear()

    gedos.GEDOSApp._open_spatial_maps(app)
    assert raised == [first], "기존 창을 앞으로 올려야 한다"
    assert app._spatial_win is first


def test_closing_allows_reopening(gedos, clean_dp):
    """닫으면 등록이 풀려 **다시 열린다** — 싱글톤이 창을 영영 막으면 안 된다."""
    app = _bare_app(gedos)
    gedos.ctk.CTkToplevel.reset_mock()

    gedos.GEDOSApp._open_spatial_maps(app)
    win = app._spatial_win
    # WM_DELETE_WINDOW로 등록된 핸들러를 그대로 부른다
    handler = win.protocol.call_args[0][1]
    handler()
    assert app._spatial_win is None
    assert app._spatial_rows == {}

    gedos.GEDOSApp._open_spatial_maps(app)
    assert _toplevel_calls(gedos) == 2
    assert app._spatial_win is not None


def test_dead_window_reference_does_not_block_reopen(gedos, clean_dp):
    """창이 죽었는데 참조만 남은 경우에도 다시 열린다.

    `winfo_exists()`가 False이거나 예외를 던지는 상황 — 사용자가 창을
    강제로 닫았거나 Tk가 먼저 정리한 경우다. 여기서 막히면 버튼이 영영
    먹통이 되므로, 싱글톤 판정은 **살아 있음이 확인될 때만** 막는다.
    """
    app = _bare_app(gedos)

    class _Dead:
        def winfo_exists(self):
            return False

    app._spatial_win = _Dead()
    gedos.ctk.CTkToplevel.reset_mock()
    gedos.GEDOSApp._open_spatial_maps(app)
    assert _toplevel_calls(gedos) == 1

    class _Raises:
        def winfo_exists(self):
            raise RuntimeError("application has been destroyed")

    app._spatial_win = _Raises()
    gedos.ctk.CTkToplevel.reset_mock()
    gedos.GEDOSApp._open_spatial_maps(app)
    assert _toplevel_calls(gedos) == 1


def test_format_help_window_is_also_a_singleton(gedos):
    """도움말 창도 같은 처리 — 같은 결함이 같은 기능 안에 두 번 있었다."""
    app = _bare_app(gedos)
    gedos.ctk.CTkToplevel.reset_mock()

    gedos.GEDOSApp._show_spatial_format_help(app)
    assert _toplevel_calls(gedos) == 1

    for _ in range(3):
        gedos.GEDOSApp._show_spatial_format_help(app)
    assert _toplevel_calls(gedos) == 1


def test_help_close_button_releases_the_singleton(gedos):
    """도움말의 [닫기]가 등록을 풀어 다시 열 수 있게 한다."""
    app = _bare_app(gedos)
    gedos.GEDOSApp._show_spatial_format_help(app)
    win = app._spatial_help_win
    handler = win.protocol.call_args[0][1]
    handler()
    assert app._spatial_help_win is None

    gedos.ctk.CTkToplevel.reset_mock()
    gedos.GEDOSApp._show_spatial_format_help(app)
    assert _toplevel_calls(gedos) == 1
