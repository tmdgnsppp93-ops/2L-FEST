# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""과도(capacitive) 해석 — 선형 시스템 레이아웃 특성화 (구 우선순위 3 단위 0).

**2026-08-20: 과도 해석은 드롭 확정됐다** — 매뉴얼 §1.2 등가회로에 용량 소자가
없고(따라갈 대상 부재), 실리콘에서 그 효과가 무시할 수준이라는 박사님 판단이다.
근거 2건은 `docs/WORKLOG.md` §3-제외에 있다.

**그래도 이 파일은 유지한다.** 여기서 고정하는 것은 과도 항이 아니라 **선형
시스템의 모양 자체**(미지 벡터 레이아웃 · 희소성 패턴 · 대각 슬롯의 구조적 존재)
이고, 시간 항의 유무와 무관하게 성립한다. 구조를 건드리는 어떤 작업이든 이 파일이
먼저 깨진다. 아래 "왜 이것부터 하는가"는 작성 당시의 동기 기록이다.

이 파일은 **새 기능을 정의하지 않는다.** 과도 항은 없다(프로덕션 0줄).
여기서 고정하는 것은 **v28.61 시점에 각 분기가 푸는 선형 시스템의 모양**뿐이다 —
미지 벡터 길이와 희소성 패턴.

왜 이것부터 하는가
------------------
계획서 §2의 판정이 이렇다:

    후향 오일러(음함수)로 이산화하면 용량 항이 ``C/dt * (V - V_prev)``가 되고,
    잔차에 상수항 하나, **야코비안 대각에 ``+C/dt``** 가 붙는다.
    → 새 평면도 새 미지수도 없다. 미지 벡터 레이아웃·희소성 패턴이 불변이다.

**그 판정은 조건부다.** 대각에 값을 더하는 것이 희소성을 바꾸지 않으려면
**대각 자리가 이미 구조적으로 존재해야 한다.** 하나라도 비어 있으면 시간 항이
``nnz``를 늘리고, "패턴 불변"이라는 근거가 무너진다. 그 조건을 실측으로 확인하는
것이 이 파일의 핵심이다(`test_every_diagonal_entry_is_structurally_present`).

계획서가 이 판정을 글로만 남기지 말라고 못 박은 이유도 같다 — 우선순위 0의 단위
0은 **계획서 전제 네 개가 틀렸다는 것**을 실측으로 찾아냈다. 여기서도 먼저 재본다.

측정 방법
--------
`test_base_lateral.py`가 확립한 방식을 그대로 쓴다. 야코비안은 각 솔버 메서드의
**지역 변수**라 밖에서 읽을 수 없으므로, 뉴턴 루프가 매 반복 부르는
``spsolve(J, -F)``를 가로채 ``J`` 자체를 관측한다. 프로덕션에 디버그 훅을 남기지
않는다.

주의: ``gedos.spsolve`` **하나만** 패치하면 안 된다 — 탠덤 접합 솔버 3종은 메서드
안에서 다시 import 하므로 모듈 전역 패치가 무시된다. 원본
``scipy.sparse.linalg.spsolve``도 함께 패치해야 6개 경로가 전부 잡힌다.
(`test_base_lateral._probe`의 주석과 같은 함정이다.)

분기 표는 **import 한다**
-------------------------
`BRANCH_CASES`를 복제하지 않는다. 복제하면 두 벌이 되어 갈리고, 그것이 우선순위 0
결함의 발생 구조였다(*"한 곳만 고치면 경로에 따라 결과가 갈린다"*).
v28.61 시점 그 표는 ``_solve_single_bifacial``까지 포함해 **6분기 전부**를 덮는다.

희소성 서명이란
--------------
``(row, col)`` 쌍의 집합을 사전식으로 정렬해 sha256을 뜬 것이다. ``indptr``을
그대로 쓰지 않는 이유는 **저장 포맷(CSR/CSC)에 따라 값이 달라지기** 때문이다.
좌표 집합은 포맷과 무관하다.

``nnz``는 **명시적 0을 포함한 저장 슬롯 수**다. 그것이 곧 "희소성 패턴"이며,
실제로 이 코드는 대각을
``J += csr_matrix((diag, (arange(Ns), arange(Ns))))``로 통째로 더하므로 값이 0인
대각도 구조적으로 존재한다(`GEDOS.py:5211-5213` 등).

계획: docs/superpowers/plans/2026-08-19-capacitive-effects.md (§2 · §6-0 (a))
매뉴얼 근거: docs/griddler_feature_map.md §1-1 · §2.11-a
"""
import hashlib
import os
import re
import sys
from collections import namedtuple

import numpy as np
import pytest
import scipy.sparse as _sp
import scipy.sparse.linalg as _sla

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _ROOT)
sys.path.insert(0, _TESTS_DIR)

# 분기 표와 헬퍼는 **import 한다.** 복제 금지 (계획 §2 마지막 항목).
from test_base_lateral import (  # noqa: E402
    BRANCH_CASES, VB, _INLINE, _NAMED_SOLVERS, _dp, _plane_sizes, _solve,
)

SRC_PATH = os.path.join(_ROOT, "GEDOS.py")

Layout = namedtuple("Layout", "branch ns nnz ndiag digest n_solves")

_ID_BY_LABEL = {c.values[0]: c.id for c in BRANCH_CASES}


# =============================================================================
# 관측
# =============================================================================

def _signature(A):
    """(Ns, nnz, 대각 슬롯 수, 좌표 집합 sha256[:16]) — 저장 포맷 무관."""
    assert _sp.issparse(A), f"spsolve에 희소행렬이 아닌 것이 들어왔다: {type(A)}"
    coo = A.tocoo()
    order = np.lexsort((coo.col, coo.row))
    rows = coo.row[order].astype(np.int64)
    cols = coo.col[order].astype(np.int64)
    h = hashlib.sha256()
    h.update(rows.tobytes())
    h.update(cols.tobytes())
    return (int(A.shape[0]), int(A.nnz),
            int(np.count_nonzero(rows == cols)), h.hexdigest()[:16])


def _canonical_map(gedos):
    """`test_spatial_branch_coverage._canonical_map`과 같은 맵.

    노드마다 다른 배율을 다이오드 계수에 곱한다. 시간 항(``C/dt``)도 **노드마다
    다른 값을 대각에 더하는 것**이므로, 이 맵이 구조를 바꾸지 않는다는 사실이
    계획서 §2 판정의 실측 방증이 된다.
    """
    return gedos.SpatialMap(mode="gaussian", background=1.0, feature=2.0,
                           cx=1.0, cy=1.0, sigma_x=0.4, sigma_y=0.4)


def _measure(gedos, geo_factory, monkeypatch, geo, rs_j, legacy, mode,
             Vb=VB, spatial_target=None):
    """한 번 풀면서 분기와 **모든 뉴턴 반복의 희소성 서명**을 관측한다."""
    monkeypatch.setenv("GEDOS_LEGACY_LOCAL_MATCH", "1" if legacy else "")

    calls = []
    for name in _NAMED_SOLVERS:
        orig = getattr(gedos.GEDOSSolver, name)

        def _make(nm, o):
            def _wrapper(self, *a, **kw):
                calls.append(nm)
                return o(self, *a, **kw)
            return _wrapper

        monkeypatch.setattr(gedos.GEDOSSolver, name, _make(name, orig))

    sigs = []
    orig_spsolve = _sla.spsolve

    def _spy(A, b, *a, **kw):
        sigs.append(_signature(A))
        return orig_spsolve(A, b, *a, **kw)

    # 지역 import 경로와 모듈 전역 경로 양쪽. 하나만 하면 절반이 새어 나간다.
    monkeypatch.setattr(_sla, "spsolve", _spy)
    monkeypatch.setattr(gedos, "spsolve", _spy)

    m = geo_factory[geo]()          # 매번 **새 솔버** — warm-start 누수 차단
    dp = _dp(gedos, rs_j)
    if spatial_target is not None:
        gedos.set_spatial_map(dp, spatial_target, _canonical_map(gedos))
    _solve(m, dp, Vb, mode)

    assert sigs, "spsolve가 한 번도 불리지 않았다 — 관측 경로가 끊겼다"
    return (calls[0] if calls else _INLINE), sigs


_CACHE = {}


def _layout(gedos, geo_factory, monkeypatch, case_values, Vb=VB,
            spatial_target=None):
    """분기별 레이아웃. 같은 조건은 세션 안에서 한 번만 푼다.

    캐시에 담는 것은 **불변 서명**이지 솔버 객체가 아니다. 그러므로 warm-start가
    테스트 사이로 새지 않는다 — 측정은 매번 새 솔버로 한다.
    """
    label, geo, rs_j, legacy, mode = case_values[:5]
    key = (label, Vb, spatial_target)
    if key not in _CACHE:
        branch, sigs = _measure(gedos, geo_factory, monkeypatch, geo, rs_j,
                                legacy, mode, Vb=Vb,
                                spatial_target=spatial_target)
        _CACHE[key] = (branch, sorted(set(sigs)), len(sigs))
    return _CACHE[key]


def _one(gedos, geo_factory, monkeypatch, case_values, **kw):
    """서명이 하나로 수렴한 경우의 Layout. 여러 개면 실패시킨다."""
    branch, uniq, n = _layout(gedos, geo_factory, monkeypatch, case_values, **kw)
    assert len(uniq) == 1, (
        f"한 solve 안에서 희소성 패턴이 {len(uniq)}가지로 갈렸다: {uniq}. "
        "패턴이 반복마다 바뀌면 '패턴 불변'을 말할 수 없다")
    ns, nnz, ndiag, digest = uniq[0]
    return Layout(branch, ns, nnz, ndiag, digest, n)


@pytest.fixture
def geo_factory(make_mono, make_bifacial):
    """라벨 → 새 솔버 팩토리. `test_base_lateral`의 같은 이름 fixture와 동일 규약."""
    return {"mono": make_mono, "bifacial": make_bifacial}


# =============================================================================
# 핀 — v28.61 시점 실측값 (KIST PC / 핀 스택)
# =============================================================================
#
# 재캡처 절차: 이 파일의 `_signature`로 6분기를 다시 측정해 아래를 갱신한다.
# **값을 고치기 전에 왜 바뀌었는지 먼저 설명할 것.** 시간 항 추가로 여기가
# 바뀌었다면 계획서 §2의 판정이 틀린 것이므로, 핀을 고칠 게 아니라 설계를
# 다시 봐야 한다.
#
# 주의: 이 표는 **메시에 의존한다**(conftest의 axis_segments_override=36).
# 메시 생성은 Qhull(Delaunay)을 거치므로 scipy 빌드가 달라지면 삼각분할이
# 달라질 수 있다 → `bit_pin_gate`로 낮춘다. 아래 "구조 불변식" 테스트들은
# 리터럴에 의존하지 않으므로 **어느 머신에서도 strict로 돈다.**
#
#   분기 id : (Ns, nnz, 좌표집합 sha256[:16])
SPARSITY_PINS = {
    "phaseA_full_area": (12980, 51380, "a5f75dd9816dc3fd"),
    "phaseB_full_area": (16789, 83447, "ebda543dd19674c4"),
    "phaseB_bifacial": (24942, 207968, "ddfb0a76f1649dd8"),
    "phaseA_bifacial": (19483, 119644, "86ba04fb1cf559d4"),
    "single_full_area": (9171, 39953, "40ff99f5b7670ed6"),
    "single_bifacial": (14024, 97808, "ef62eaa7689dbf2b"),
}


# =============================================================================
# 1. 미지 벡터 — 시간 항이 건드리면 안 되는 기준선
# =============================================================================

@pytest.mark.parametrize(
    "label,geo,rs_j,legacy,mode,expected_branch,ns_fn", BRANCH_CASES)
def test_unknown_vector_length_is_the_transient_baseline(
        gedos, geo_factory, monkeypatch, label, geo, rs_j, legacy, mode,
        expected_branch, ns_fn):
    """관측된 Ns가 분기 표의 오프셋 식과 일치한다.

    `test_base_lateral.test_unknown_vector_layout_is_pinned`와 같은 단언이지만
    **여기 있어야 한다** — 계획서 §2가 *"C = 0에서 미지 벡터 길이가 v28.61과
    동일함을 6개 분기 전부에서 고정"* 하라고 요구한 것이 이 파일의 완료 조건이고,
    그 판정이 다른 파일에만 있으면 이 작업의 회귀 게이트가 비게 된다.
    식 자체는 import한 ``ns_fn``이므로 **표가 두 벌이 되지는 않는다.**
    """
    N, Nm, Nrm = _plane_sizes(geo_factory[geo]())
    lay = _one(gedos, geo_factory, monkeypatch,
               (label, geo, rs_j, legacy, mode))
    assert lay.ns == ns_fn(N, Nm, Nrm), (
        f"{label}: Ns={lay.ns}, 기대={ns_fn(N, Nm, Nrm)} "
        f"(N={N}, Nm={Nm}, Nrm={Nrm})")


@pytest.mark.parametrize(
    "label,geo,rs_j,legacy,mode,expected_branch,ns_fn", BRANCH_CASES)
def test_dispatch_target_agrees_with_the_branch_table(
        gedos, geo_factory, monkeypatch, label, geo, rs_j, legacy, mode,
        expected_branch, ns_fn):
    """관측 경로가 실제로 표가 말하는 분기를 지난다.

    이 파일의 모든 측정이 그 전제 위에 있다. 디스패치가 바뀌면 아래 핀들이
    "다른 분기의 값"을 지키게 되므로 여기서 먼저 잡는다.
    """
    lay = _one(gedos, geo_factory, monkeypatch,
               (label, geo, rs_j, legacy, mode))
    assert lay.branch == expected_branch, (
        f"{label}: {expected_branch!r}로 가야 하는데 {lay.branch!r}로 갔다")


# =============================================================================
# 2. 구조 불변식 — 리터럴에 의존하지 않는다 (어느 머신에서도 strict)
# =============================================================================

@pytest.mark.parametrize(
    "label,geo,rs_j,legacy,mode,expected_branch,ns_fn", BRANCH_CASES)
def test_every_diagonal_entry_is_structurally_present(
        gedos, geo_factory, monkeypatch, label, geo, rs_j, legacy, mode,
        expected_branch, ns_fn):
    """**이 파일에서 가장 중요한 단언이다.**

    후향 오일러의 시간 항은 야코비안 **대각에 ``+C/dt``** 를 더한다. 그것이
    희소성을 바꾸지 않으려면 대각 자리가 **이미 구조적으로 존재해야** 한다.
    하나라도 비어 있으면 시간 항이 ``nnz``를 늘리고, 계획서 §2의 *"패턴 불변"*
    판정이 그 분기에서 거짓이 된다.

    v28.61 실측: 6분기 모두 ``대각 슬롯 수 == Ns``다. 조립 코드가 대각을
    ``J += csr_matrix((diag, (arange(Ns), arange(Ns))))`` 형태로 **통째로** 더하기
    때문이며(`GEDOS.py:5211-5213` 등), 값이 0인 대각도 슬롯으로 남는다.

    누군가 그 조립을 "0은 빼고 넣자"로 최적화하면 이 테스트가 먼저 깨진다.
    그때 고칠 것은 이 테스트가 아니라 **계획서 §2의 판정**이다.
    """
    lay = _one(gedos, geo_factory, monkeypatch,
               (label, geo, rs_j, legacy, mode))
    assert lay.ndiag == lay.ns, (
        f"{label}: 대각 슬롯이 {lay.ndiag}/{lay.ns}개뿐이다. "
        f"{lay.ns - lay.ndiag}개 노드에서 시간 항이 희소성을 바꾼다 — "
        "계획서 §2의 '패턴 불변' 판정이 이 분기에서 성립하지 않는다")


@pytest.mark.parametrize(
    "label,geo,rs_j,legacy,mode,expected_branch,ns_fn", BRANCH_CASES)
def test_sparsity_pattern_is_constant_within_one_solve(
        gedos, geo_factory, monkeypatch, label, geo, rs_j, legacy, mode,
        expected_branch, ns_fn):
    """한 번의 solve 안에서 뉴턴 반복이 몇 번을 돌든 패턴이 하나다.

    반복마다 패턴이 달라지면 "패턴 불변"이라는 말 자체가 성립하지 않는다.
    `_one`이 이미 단언하지만, **그 사실 자체를 이름 있는 테스트로** 남긴다 —
    다른 테스트가 실패했을 때 원인이 여기인지 구분할 수 있어야 한다.
    """
    _, uniq, n_solves = _layout(gedos, geo_factory, monkeypatch,
                                (label, geo, rs_j, legacy, mode))
    assert len(uniq) == 1, f"{label}: {n_solves}회 반복에서 패턴 {len(uniq)}가지"
    assert n_solves >= 1


@pytest.mark.parametrize(
    "label,geo,rs_j,legacy,mode,expected_branch,ns_fn", BRANCH_CASES)
def test_sparsity_pattern_does_not_depend_on_bias_voltage(
        gedos, geo_factory, monkeypatch, label, geo, rs_j, legacy, mode,
        expected_branch, ns_fn):
    """``Vb``를 바꿔도 패턴이 같다.

    ``calc_iv_transient``는 시간에 따라 ``Vb``를 훑는다(계획서 §3). 그 과정에서
    패턴이 바뀐다면 시간 스텝마다 재조립·재분해가 강제되고, "대각 기여뿐"이라는
    설계 근거도 약해진다. **지금은 바뀌지 않는다**는 것을 고정한다.
    """
    base = _one(gedos, geo_factory, monkeypatch,
                (label, geo, rs_j, legacy, mode))
    other = _one(gedos, geo_factory, monkeypatch,
                 (label, geo, rs_j, legacy, mode), Vb=0.9)
    assert (base.ns, base.nnz, base.digest) == \
           (other.ns, other.nnz, other.digest), (
        f"{label}: Vb={VB}와 Vb=0.9의 희소성 패턴이 다르다 "
        f"({base.nnz} vs {other.nnz})")


@pytest.mark.parametrize(
    "label,geo,rs_j,legacy,mode,expected_branch,ns_fn", BRANCH_CASES)
def test_node_varying_diode_coefficients_do_not_change_the_pattern(
        gedos, geo_factory, monkeypatch, label, geo, rs_j, legacy, mode,
        expected_branch, ns_fn):
    """노드마다 다른 다이오드 계수(공간 분포 맵)를 걸어도 패턴이 같다.

    시간 항 ``C/dt``도 **노드마다 다른 값을 대각에 더하는 것**이다. 구조적으로
    이미 그런 항이 하나 있고(v28.61의 ``_diode_node_arrays``), 그것이 패턴을
    바꾸지 않는다는 것이 계획서 §2 판정의 **실측 방증**이다.

    (증명은 아니다 — 다이오드 항은 대각과 몇몇 off-diagonal 블록에 들어가고
    시간 항은 대각에만 들어간다. 방향이 같을 뿐이며, 결정적 근거는 위
    `test_every_diagonal_entry_is_structurally_present`다.)
    """
    base = _one(gedos, geo_factory, monkeypatch,
                (label, geo, rs_j, legacy, mode))
    mapped = _one(gedos, geo_factory, monkeypatch,
                  (label, geo, rs_j, legacy, mode), spatial_target="j01")
    assert (base.ns, base.nnz, base.digest) == \
           (mapped.ns, mapped.nnz, mapped.digest), (
        f"{label}: spatial_j01을 걸었더니 희소성 패턴이 바뀌었다 "
        f"({base.nnz} -> {mapped.nnz})")


# =============================================================================
# 3. 리터럴 핀 — 메시 의존이라 핀 스택에서만 strict
# =============================================================================

@pytest.mark.parametrize(
    "label,geo,rs_j,legacy,mode,expected_branch,ns_fn", BRANCH_CASES)
def test_sparsity_pattern_is_pinned(
        gedos, geo_factory, monkeypatch, bit_pin_gate, label, geo, rs_j,
        legacy, mode, expected_branch, ns_fn):
    """``(Ns, nnz, 좌표집합 해시)``를 v28.61 실측값으로 고정한다.

    오프셋 식(``ns_fn``)은 **평면 크기가 맞으면** 통과하므로 메시가 바뀌어도
    조용하다. 이 핀은 그 위에 좌표 집합까지 묶어, 시간 항이 들어갈 때
    *"어디에"* 들어갔는지까지 감시한다.

    스택이 다르면 Qhull 삼각분할이 달라질 수 있으므로 xfail로 낮춘다 —
    핀 스택에서는 strict라 회귀 감시가 유지된다(`conftest.stack_mismatch`).
    """
    if bit_pin_gate:
        pytest.xfail(
            f"핀 캡처 스택과 다름 ({bit_pin_gate}) — 메시(Delaunay)가 달라지면 "
            "희소성 리터럴이 성립하지 않는다(물리 회귀 아님). 구조 불변식 "
            "테스트들은 이 머신에서도 strict로 돈다")
    case_id = _ID_BY_LABEL[label]
    lay = _one(gedos, geo_factory, monkeypatch,
               (label, geo, rs_j, legacy, mode))
    assert (lay.ns, lay.nnz, lay.digest) == SPARSITY_PINS[case_id], (
        f"{label}: 관측 {(lay.ns, lay.nnz, lay.digest)} vs "
        f"핀 {SPARSITY_PINS[case_id]}. 시간 항 때문에 바뀐 것이라면 "
        "핀을 고치지 말고 계획서 §2 판정을 다시 볼 것")


# =============================================================================
# 4. 표·핀의 정합성 — 복제와 누락을 막는다
# =============================================================================

def test_branch_table_is_imported_not_copied():
    """``BRANCH_CASES``가 `test_base_lateral`의 그 객체인지 확인한다.

    이 파일이 표를 복제하면 두 벌이 되어 갈린다 — 우선순위 0 결함이 정확히 그
    구조로 생겼다. import 여부는 눈으로 못 보므로 테스트로 못 박는다.
    """
    import test_base_lateral
    assert BRANCH_CASES is test_base_lateral.BRANCH_CASES
    assert _NAMED_SOLVERS is test_base_lateral._NAMED_SOLVERS


def test_pins_cover_every_branch_case():
    """핀 dict가 표의 모든 케이스를 덮는다.

    표에 분기가 추가되면 여기서 먼저 실패해 핀을 캡처하라고 알린다. 없으면 새
    분기가 감시 밖에서 조용히 늘어난다 — ``_NAMED_SOLVERS``에
    ``_solve_single_bifacial``이 빠져 있던 것과 같은 실패 유형이다.
    """
    assert set(SPARSITY_PINS) == {c.id for c in BRANCH_CASES}, (
        f"핀 {sorted(SPARSITY_PINS)} vs "
        f"표 {sorted(c.id for c in BRANCH_CASES)}")


def test_branch_table_covers_all_six_branches():
    """표가 6분기(인라인 2 + 이름 있는 4)를 덮는지 확인한다.

    계획서 §2가 *"6분기 전부에서 고정"* 이라고 적은 그 6이다.
    ``_solve_tandem_junction_bf_v29``는 도달 불가라 표에 없다
    (`test_base_lateral.test_v29_schur_branch_is_unreachable`이 고정한다).
    """
    assert len(BRANCH_CASES) == 6
    named = {c.values[5] for c in BRANCH_CASES} - {_INLINE}
    assert named == set(_NAMED_SOLVERS) - {"_solve_tandem_junction_bf_v29"}


# =============================================================================
# 5. 프로덕션 0줄 — 착수 전 상태의 특성화
# =============================================================================

# 과도 해석이 도입되면 나타날 이름들. 지금은 **하나도 없어야 한다.**
# 단위 2 이후 이 목록은 "없어야 할 것"에서 "있어야 할 것"으로 뒤집힌다 —
# 그때 이 테스트를 반전시킬 것(우선순위 0 단위 0의
# ``test_cell_current_delta_is_not_evidence_of_working``가 단위 1에서 반전된 선례).
_TRANSIENT_TOKENS = (
    "_transient_state",
    "calc_iv_transient",
    "sweep_rate",
    "sweeprate",
    "sweeptiming",
    "capacitance",
    "capacitive",
)


def test_engine_has_no_transient_code_yet():
    """엔진에 과도 관련 식별자가 0건임을 고정한다 — 이 단위의 "프로덕션 0줄" 근거.

    2026-08-17·08-19 두 번의 전문 검색이 0건이었다는 기록
    (`docs/pro_feature_map_2026-08-14.md` #9)을 **테스트로** 옮긴다. 사람이
    grep한 기록은 다음 판에서 다시 검증되지 않지만 테스트는 매번 돈다.
    """
    with open(SRC_PATH, encoding="utf-8") as fh:
        src = fh.read()
    hits = {t: len(re.findall(re.escape(t), src, re.I))
            for t in _TRANSIENT_TOKENS}
    found = {k: v for k, v in hits.items() if v}
    assert not found, (
        f"엔진에 과도 관련 식별자가 생겼다: {found}. "
        "과도 해석은 2026-08-20에 드롭 확정됐다(WORKLOG §3-제외) — 판정이 뒤집혀 "
        "실제로 착수한 것이 아니라면 이건 실수로 들어온 코드다")


def test_calc_iv_is_untouched_and_still_the_only_sweep_path():
    """``calc_iv``가 존재하고 ``calc_iv_transient``는 아직 없다.

    계획서 §3의 판단은 *"기존 ``calc_iv``를 고치지 말고 별도 경로를 신설한다"* 다.
    그 판단이 지켜지는지의 출발점을 여기 고정한다 — 지금은 ``calc_iv`` 하나뿐이다.
    """
    with open(SRC_PATH, encoding="utf-8") as fh:
        src = fh.read()
    assert re.search(r"\bdef calc_iv\b", src), "calc_iv가 사라졌다"
    assert not re.search(r"\bdef calc_iv_transient\b", src), (
        "calc_iv_transient가 생겼다 — 단위 4가 착수됐다면 이 테스트를 갱신할 것")
