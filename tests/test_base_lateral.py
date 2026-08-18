# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""벌크 횡전도(base lateral transport) — 잔차 분기 특성화 테스트 (계획 단위 0).

이 파일은 **새 기능을 정의하지 않는다.** 벌크 평면은 아직 없다. 여기서 고정하는
것은 **지금 코드가 어떤 설정에서 어느 잔차 지점으로 가고, 그때 미지 벡터가 몇
개인가**뿐이다.

왜 이것부터 하는가
------------------
`docs/WORKLOG.md` §3이 경고한다 — *"Phase B tandem 잔차가 3개 분기로 갈라져
있어서 세 곳 다 손봐야 한다. 한 곳만 고치면 경로에 따라 결과가 갈린다."*

**착수 전 재조사 결과 그 경고는 옳지만 숫자가 과소평가되어 있다.** WORKLOG가 센
3개는 `_K_junc`를 쓰는 분기이고, 미지 벡터 레이아웃을 **독립적으로 조립하는**
잔차 지점은 7곳이다. 벌크 평면(+N 자유도)은 그 7곳 각각의 오프셋 식·잔차·
야코비안·BC를 건드린다.

그런데 **지금은 어느 설정이 어느 분기로 가는지 확인하는 테스트가 하나도 없다.**
그 상태로 평면을 넣으면, 손대지 않은 분기에서 `Rs_base`가 조용히 무시되는 것을
알아챌 방법이 없다 — 오류도 경고도 없이 "켰는데 결과가 안 변한다"로 나타난다.

이 파일이 그 판정 기준이다. 계획 단위 3~5는 여기 고정된 표를 기준으로
"어디를 고쳤고 어디를 거부했는지"를 말한다.

측정 방법
--------
`Ns`(미지 벡터 길이)는 각 솔버 메서드의 **지역 변수**라 밖에서 읽을 수 없고,
`solve()`가 돌려주는 dict에도 없다(`Vrm`은 반환되지 않는다 — `2L_FEST.py:6512`
부근의 반환 dict 참조). 그래서 **뉴턴 루프가 매 반복 부르는 `spsolve(J, -F)`를
가로채 `J.shape[0]`을 읽는다.** 그것이 곧 `Ns`이고, 프로덕션 코드에 디버그 훅을
남기지 않는다.

⚠ `fest.spsolve` **하나만** 패치하면 안 된다. `_solve_tandem_junction`
(`2L_FEST.py:5041`) · `_solve_tandem_junction_bf`(`:5392`) ·
`_solve_tandem_junction_bf_v29`(`:5733`)는 **메서드 안에서 다시 import** 하므로
모듈 전역 패치가 무시된다. 원본 `scipy.sparse.linalg.spsolve`도 함께 패치해야
6개 경로가 전부 잡힌다.

계획: docs/superpowers/plans/2026-08-18-base-lateral-transport.md
"""
import os
import sys

import numpy as np
import pytest
import scipy.sparse.linalg as _sla

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 핀 테스트와 같은 solve 인자 (tests/test_default_pin.py:19,
# tests/test_spatial_map.py:34). 값이 갈리면 다른 파일과의 비교가 깨진다.
PARAMS = dict(rm=3e-6, hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)

VB = 0.5   # 바이어스 지점. 분기 판정에는 값이 중요하지 않으나 0은 피한다
           # (뉴턴 반복이 얕아 warm-start 경로가 달라질 수 있다).

# solve()가 도달할 수 있는 이름 있는 솔버 메서드 전부. 인라인 경로(solve_tandem /
# solve_single 자체)는 여기 없으므로, 아무것도 안 잡히면 인라인이라는 뜻이다.
_NAMED_SOLVERS = (
    "_solve_tandem_junction",
    "_solve_tandem_junction_bf",
    "_solve_tandem_junction_bf_v29",
    "_solve_tandem_bifacial",
)

_INLINE = "inline"   # solve_tandem / solve_single 본문이 직접 조립하는 경우


# =============================================================================
# 헬퍼 — 단위 1~7이 전부 재사용한다. 이름과 시그니처를 여기서 확정한다.
# =============================================================================

def _build_args(dp):
    """``_build(rm, hf, wf, rc, Rs_front, cf, dp)`` 호출 인자.

    ⚠ PARAMS의 키는 ``Rs``인데 `_build`의 파라미터명은 ``Rs_front``다.
    ``_build(**PARAMS, dp=dp)``는 TypeError가 난다 — 반드시 이 헬퍼를 쓸 것.
    """
    return dict(rm=PARAMS["rm"], hf=PARAMS["hf"], wf=PARAMS["wf"],
                rc=PARAMS["rc"], Rs_front=PARAMS["Rs"], cf=PARAMS["cf"], dp=dp)


def _solve(m, dp, Vb=VB, mode="tandem"):
    """solve() 한 번. 위치 인자 순서는 ``2L_FEST.py:6488``."""
    return m.S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                     PARAMS["Rs"], Vb, PARAMS["cf"], dp, mode)


def _cell_current(m, dp, Vb=VB, mode="tandem"):
    """단자 전류 [A]. 물리 비교의 단일 스칼라 지표."""
    return float(m.S.cell_current(_solve(m, dp, Vb, mode), dp))


def _probe(fest, m, dp, monkeypatch, Vb=VB, mode="tandem"):
    """한 번 풀면서 **어느 분기로 갔는지**와 **Ns**를 관측한다.

    Returns
    -------
    (target, ns_values)
        target     : `_NAMED_SOLVERS` 중 처음 불린 이름, 또는 `_INLINE`
        ns_values  : 관측된 `J.shape[0]` 집합 (정렬된 tuple)
    """
    calls = []
    for name in _NAMED_SOLVERS:
        orig = getattr(fest.FESTSolver, name)

        def _make(nm, o):
            def _wrapper(self, *a, **kw):
                calls.append(nm)
                return o(self, *a, **kw)
            return _wrapper

        monkeypatch.setattr(fest.FESTSolver, name, _make(name, orig))

    shapes = []
    orig_spsolve = _sla.spsolve

    def _spy(A, b, *a, **kw):
        shapes.append(int(A.shape[0]))
        return orig_spsolve(A, b, *a, **kw)

    # 지역 import 경로(:5041 · :5392 · :5733)와 모듈 전역 경로(:4982 · :6194 ·
    # :6344 · :6463 · :5941) 양쪽을 덮는다. 하나만 하면 절반이 새어 나간다.
    monkeypatch.setattr(_sla, "spsolve", _spy)
    monkeypatch.setattr(fest, "spsolve", _spy)

    _solve(m, dp, Vb, mode)
    return (calls[0] if calls else _INLINE), tuple(sorted(set(shapes)))


def _observed_Ns(fest, m, dp, monkeypatch, Vb=VB, mode="tandem"):
    """관측된 미지 벡터 길이. 여러 값이 나오면 실패시킨다.

    한 번의 solve에서 서로 다른 Ns가 보이면 내부에서 레이아웃이 갈렸다는 뜻이고,
    그 경우 "이 설정의 Ns"를 하나로 말할 수 없다.
    """
    _, ns = _probe(fest, m, dp, monkeypatch, Vb, mode)
    assert len(ns) == 1, f"한 solve에서 Ns가 여러 개 관측됐다: {ns}"
    return ns[0]


def _plane_sizes(m):
    """(N, Nm, Nrm) — 오프셋 식을 검산하기 위한 평면별 자유도 수."""
    N = int(m.S.N)
    Nm = int(m.S.Nm)
    rear_midx = getattr(m.S, "rear_midx", None)
    Nrm = 0 if rear_midx is None else int(len(rear_midx))
    return N, Nm, Nrm


def _dp(fest, rs_junction=None):
    dp = fest.DiodeParams()
    if rs_junction is not None:
        dp.Rs_junction = rs_junction
    return dp


# =============================================================================
# 1. 디스패치 — 어떤 설정이 어느 잔차 지점으로 가는가
# =============================================================================
#
# 아래 표가 이 작업 전체의 기준이다. 벌크 평면은 이 중 **2곳에만** 들어가고
# (계획 단위 3·4), 나머지는 명시적으로 거부한다(단위 5). 디스패치가 조용히
# 바뀌면 그 대응이 통째로 어긋나므로 여기서 먼저 못 박는다.
#
#   (라벨, 지오메트리, Rs_junction, legacy 플래그, mode,
#    기대 분기, Ns 식, 계획상 처리)

BRANCH_CASES = [
    pytest.param(
        "1. Phase A / full_area", "mono", 0.0, True, "tandem",
        _INLINE, lambda N, Nm, Nrm: 3 * N + Nm, id="phaseA_full_area"),
    pytest.param(
        "2. Phase B / full_area", "mono", 100.0, False, "tandem",
        "_solve_tandem_junction", lambda N, Nm, Nrm: 4 * N + Nm,
        id="phaseB_full_area"),
    pytest.param(
        "3. Phase B / bifacial", "bifacial", 100.0, False, "tandem",
        "_solve_tandem_junction_bf", lambda N, Nm, Nrm: 4 * N + Nm + Nrm,
        id="phaseB_bifacial"),
    pytest.param(
        "5. Phase A / bifacial", "bifacial", 0.0, True, "tandem",
        "_solve_tandem_bifacial", lambda N, Nm, Nrm: 3 * N + Nm + Nrm,
        id="phaseA_bifacial"),
    pytest.param(
        "6. 단일셀 / full_area", "mono", None, False, "single",
        _INLINE, lambda N, Nm, Nrm: 2 * N + Nm, id="single_full_area"),
    pytest.param(
        "7. 단일셀 / bifacial", "bifacial", None, False, "single",
        _INLINE, lambda N, Nm, Nrm: 2 * N + Nm + Nrm, id="single_bifacial"),
]

# 분기 4(`_solve_tandem_junction_bf_v29`)는 이 표에 없다 — solve()로 도달하지
# 않기 때문이다. 그 사실 자체를 test_v29_schur_branch_is_unreachable이 고정한다.


@pytest.fixture
def geo_factory(make_mono, make_bifacial):
    """라벨 → 새 솔버. **매번 새로 만든다.**

    session 스코프 `mono`/`bifacial`을 공유하면 이 파일이 남긴 warm-start가
    다른 파일의 값 테스트에 새어 나간다 — 특히 `_warm_V_junc_bf`가 있으면
    연속법(homotopy) 램프가 통째로 생략된다(`2L_FEST.py:4713`).
    """
    return {"mono": make_mono, "bifacial": make_bifacial}


@pytest.mark.parametrize(
    "label,geo,rs_j,legacy,mode,expected_branch,ns_fn", BRANCH_CASES)
def test_dispatch_target_is_pinned(fest, geo_factory, monkeypatch, label, geo,
                                   rs_j, legacy, mode, expected_branch, ns_fn):
    """설정 → 잔차 분기 매핑을 고정한다.

    이것이 바뀌면 벌크 평면의 "지원 2 / 거부 5" 배치가 어긋난다.
    """
    monkeypatch.setenv("FEST_LEGACY_LOCAL_MATCH", "1" if legacy else "")
    m = geo_factory[geo]()
    target, _ = _probe(fest, m, _dp(fest, rs_j), monkeypatch, mode=mode)
    assert target == expected_branch, (
        f"{label}: {expected_branch!r}로 가야 하는데 {target!r}로 갔다")


@pytest.mark.parametrize(
    "label,geo,rs_j,legacy,mode,expected_branch,ns_fn", BRANCH_CASES)
def test_unknown_vector_layout_is_pinned(fest, geo_factory, monkeypatch, label,
                                         geo, rs_j, legacy, mode,
                                         expected_branch, ns_fn):
    """미지 벡터 길이를 오프셋 식으로 고정한다.

    벌크 평면은 여기에 **+N**을 한다. 그리고 `Rs_base`가 지정되지 않았을 때는
    이 값이 **변하지 않아야 한다** — 그것이 무벌크 경로 비트 동일의 근거다
    (계획 §비트 동일 근거: "0 행렬을 더함"이 아니라 "평면을 안 만듦").
    """
    monkeypatch.setenv("FEST_LEGACY_LOCAL_MATCH", "1" if legacy else "")
    m = geo_factory[geo]()
    N, Nm, Nrm = _plane_sizes(m)
    observed = _observed_Ns(fest, m, _dp(fest, rs_j), monkeypatch, mode=mode)
    assert observed == ns_fn(N, Nm, Nrm), (
        f"{label}: Ns={observed}, 기대={ns_fn(N, Nm, Nrm)} "
        f"(N={N}, Nm={Nm}, Nrm={Nrm})")


def test_case_table_covers_every_reachable_named_solver(fest, geo_factory,
                                                        monkeypatch):
    """표가 **도달 가능한 이름 있는 솔버를 전부** 덮는지 확인한다.

    새 분기가 생겼는데 표에 없으면, 벌크 평면 작업이 그 분기를 통째로 놓친다.
    이 테스트가 그때 실패해서 표를 갱신하라고 알린다.
    """
    covered = {c.values[5] for c in BRANCH_CASES} - {_INLINE}
    reachable = set()
    for case in BRANCH_CASES:
        label, geo, rs_j, legacy, mode = case.values[:5]
        monkeypatch.setenv("FEST_LEGACY_LOCAL_MATCH", "1" if legacy else "")
        target, _ = _probe(fest, geo_factory[geo](), _dp(fest, rs_j),
                           monkeypatch, mode=mode)
        if target != _INLINE:
            reachable.add(target)
    assert reachable == covered, (
        f"표가 덮는 분기={sorted(covered)}, 실제 도달={sorted(reachable)}")


def test_v29_schur_branch_is_unreachable(fest, geo_factory, monkeypatch):
    """`_solve_tandem_junction_bf_v29`는 solve()로 도달하지 않는다.

    `solve_tandem`의 주석(`2L_FEST.py:4726` 부근)이 *"currently sub-optimal,
    kept for future"*라고 적어 둔 그대로다. 벌크 평면을 넣지 않는 이유이므로
    (죽은 경로에 검증되지 않은 물리를 넣지 않는다) 그 전제를 고정한다.

    **누군가 이 분기를 다시 배선하면 이 테스트가 실패한다** — 그때 벌크 평면
    대응(지원 또는 거부)을 함께 하라는 신호다.
    """
    for case in BRANCH_CASES:
        label, geo, rs_j, legacy, mode = case.values[:5]
        monkeypatch.setenv("FEST_LEGACY_LOCAL_MATCH", "1" if legacy else "")
        target, _ = _probe(fest, geo_factory[geo](), _dp(fest, rs_j),
                           monkeypatch, mode=mode)
        assert target != "_solve_tandem_junction_bf_v29", (
            f"{label}에서 v29 Schur 분기에 도달했다 — 계획의 '거부' 판단을 "
            f"재검토할 것")


# =============================================================================
# 2. 분기를 가르는 스위치 — 무엇이 경로를 바꾸는가
# =============================================================================
#
# 위 표가 "어느 설정이 어디로 가는가"라면, 여기는 "무엇을 바꾸면 경로가
# 바뀌는가"다. 벌크 평면의 지원/거부 게이트(단위 5)가 바로 이 스위치들을 읽어
# 판정하므로, 스위치 자체가 고정되어 있어야 한다.

def test_rs_junction_switches_phase_a_to_phase_b(fest, make_mono, monkeypatch):
    """`Rs_junction`이 Phase A(3N+Nm) ↔ Phase B(4N+Nm)를 가른다.

    Phase B에서 interlayer 평면 하나가 늘면서 **Ns가 정확히 +N** 된다.
    벌크 평면이 할 일이 이것과 같은 형태다.
    """
    monkeypatch.setenv("FEST_LEGACY_LOCAL_MATCH", "1")
    m = make_mono()
    N, Nm, _ = _plane_sizes(m)

    ns_a = _observed_Ns(fest, m, _dp(fest, 0.0), monkeypatch)
    ns_b = _observed_Ns(fest, m, _dp(fest, 100.0), monkeypatch)

    assert ns_a == 3 * N + Nm
    assert ns_b == 4 * N + Nm
    assert ns_b - ns_a == N, "평면 하나 추가 = 자유도 +N"


def test_legacy_flag_is_required_to_reach_phase_a(fest, make_mono, monkeypatch):
    """플래그가 꺼져 있으면 `Rs_junction=0`이어도 Phase B로 간다.

    `RS_JUNCTION_MIN` 클램프(`2L_FEST.py:4304-4306`) 때문이다 — Phase B가
    production 모델이고 Phase A는 탈출구다. 벌크 평면을 Phase A에 넣지 않기로
    한 근거이므로(계획 §설계 결정 4) 그 전제를 고정한다.
    """
    m = make_mono()
    N, Nm, _ = _plane_sizes(m)
    monkeypatch.setenv("FEST_LEGACY_LOCAL_MATCH", "")
    target, _ = _probe(fest, m, _dp(fest, 0.0), monkeypatch)
    assert target == "_solve_tandem_junction"
    assert _observed_Ns(fest, m, _dp(fest, 0.0), monkeypatch) == 4 * N + Nm


def test_rear_mode_switches_layout_by_Nrm(fest, make_mono, make_bifacial,
                                          monkeypatch):
    """`rear_mode`가 rear metal 평면(`Nrm`)의 유무를 가른다.

    같은 Phase B인데도 `Ns` 식이 달라지는 이유다 — 그래서 계획 단위 3(full_area)과
    단위 4(bifacial)를 **복붙하면 안 되고** 오프셋 식을 각각 다시 세워야 한다.
    """
    m_fa, m_bf = make_mono(), make_bifacial()
    assert _plane_sizes(m_fa)[2] == 0, "full_area에는 rear metal 평면이 없다"
    assert _plane_sizes(m_bf)[2] > 0, "bifacial에는 rear metal 평면이 있다"

    assert _probe(fest, m_fa, _dp(fest, 100.0), monkeypatch)[0] \
        == "_solve_tandem_junction"
    assert _probe(fest, m_bf, _dp(fest, 100.0), monkeypatch)[0] \
        == "_solve_tandem_junction_bf"


def test_mode_single_never_reaches_tandem_branches(fest, geo_factory,
                                                   monkeypatch):
    """단일셀은 tandem 분기 어디에도 가지 않는다.

    계획이 단일셀을 범위 밖으로 둔 근거다 — 잔차 지점이 완전히 별개라
    tandem 쪽 작업이 여기 닿지 않는다.
    """
    for geo in ("mono", "bifacial"):
        target, _ = _probe(fest, geo_factory[geo](), _dp(fest), monkeypatch,
                           mode="single")
        assert target == _INLINE


# =============================================================================
# 3. 벌크 파라미터 도입 전 상태 — 단위 2가 뒤집을 기준선
# =============================================================================

def test_base_parameter_surface_is_exactly_one_field(fest):
    """벌크 횡전도가 추가한 입력은 **`Rs_base` 하나뿐**이다.

    단위 0에서는 이 테스트가 `not hasattr(...)`였다(아직 없다는 기준선).
    단위 2가 `Rs_base`를 신설하며 뒤집었다.

    `Gv_base`가 **없어야 한다**는 쪽이 지금 더 중요하다 — 그것은 토폴로지 α
    (새 평면 + 수직 결합)의 파라미터이고, β를 확정하면서 대상이 사라졌다.
    생기면 `Rs_vert_bot`과의 이중 계산 판정이 되살아나야 하므로
    (docs/base_lateral_convention.md §5) 여기서 감시한다.
    """
    assert fest.DiodeParams.Rs_base is None
    assert not hasattr(fest.DiodeParams, "Gv_base"), (
        "Gv_base가 생겼다 — 토폴로지가 β에서 α로 돌아갔다는 뜻이다. "
        "Rs_vert_bot 이중 계산 거부 판정을 되살릴 것 "
        "(docs/base_lateral_convention.md §5)")


def test_no_base_plane_on_solver_yet(fest, make_mono):
    """솔버에 `_K_base` 평면이 없다. 현재 횡전도 평면은 5개다."""
    m = make_mono()
    m.S._build(**_build_args(_dp(fest, 100.0)))
    assert not hasattr(m.S, "_K_base")
    for plane in ("_Ke", "_Kr", "_Km", "_K_junc"):
        assert hasattr(m.S, plane), f"{plane}가 없다 — 평면 인벤토리가 바뀌었다"


def test_rs_vert_bot_is_a_post_hoc_lumped_correction(fest, make_mono,
                                                    monkeypatch):
    """`Rs_vert_bot`은 **FEM 밖**에서 터미널 IR 강하로 적용된다.

    계획 §설계 결정 3의 전제다 — 벌크 수직 저항이 이미 여기 들어 있으므로,
    `Gv_base`(FEM 내부 수직 결합)와 동시에 켜면 **이중 계산**이 된다.
    박사님 판단(2026-08-18): 둘 다 0이 아니면 `ValueError`로 거부한다.

    여기서는 그 전제 두 가지를 고정한다:
      (a) `Rs_vert_bot`은 기본값 0이다 — 그래서 지금은 충돌이 없다
      (b) 값을 바꿔도 **미지 벡터 레이아웃이 변하지 않는다** = FEM 밖이다
    """
    m = make_mono()
    assert fest.DiodeParams.Rs_vert_bot == 0.0

    ns_zero = _observed_Ns(fest, m, _dp(fest, 100.0), monkeypatch)
    dp = _dp(fest, 100.0)
    dp.Rs_vert_bot = 0.5
    ns_set = _observed_Ns(fest, m, dp, monkeypatch)
    assert ns_zero == ns_set, (
        "Rs_vert_bot이 Ns를 바꾼다면 FEM 안에 들어와 있다는 뜻이고, "
        "계획 §설계 결정 3의 전제가 무너진다")


# =============================================================================
# 4. β 토폴로지의 전제 (계획 단위 1 — docs/base_lateral_convention.md §3)
# =============================================================================
#
# 규약 문서 §3의 숫자는 **설계의 근거**다. 벌크 횡전도를 "기존 후면 평면의
# 면전도에 병렬로 더한다"로 구현하기로 한 것이 전부 아래 성질에 기대고 있다:
#
#   ① assemble_K가 1/Rs에 선형   → 병렬 합성 = 두 평면을 더한 것
#   ② sparsity pattern이 Rs와 무관 → Ns·SuperLU 열 순열 불변 = 분기 수술 불필요
#   ③ full_area의 Vr ≡ 0          → 후면 평면을 바꿔도 결과 불변 = 거부 대상
#   ④ bifacial의 Vr에 실제 강하    → 벌크 전도가 의미를 갖는 유일한 모드
#
# 코드가 바뀌어 이 숫자가 달라지면 규약이 무효가 되는데, 문서만으로는 알 수 없다.
# 여기서 묶어 둔다.

def test_assemble_K_is_linear_in_sheet_conductance(fest, make_mono):
    """β의 수학적 근거 — 병렬 합성 = 행렬 덧셈.

    `assemble_K`의 `coeff = 1/(4·A·Rs)`(2L_FEST.py:2649)가 1/Rs에 선형이라
    성립한다. 이것이 깨지면 "유효 면저항을 한 번 계산"이 "두 평면을 더한 것"과
    달라져 규약 §1-4가 무효가 된다.

    ⚠ **비트 동일은 아니다**(실측 상대 3.5e-16). 그래서 구현은 반드시
    "유효 면저항 계산 후 assemble_K 한 번"이어야 하고, 행렬 덧셈이면 안 된다 —
    off 경로의 비트 동일이 깨진다.
    """
    m = make_mono()
    Ka, _ = fest.assemble_K(m.pts, m.S.simp, 50.0, m.S.areas, m.S.b, m.S.c)
    Kb, _ = fest.assemble_K(m.pts, m.S.simp, 500.0, m.S.areas, m.S.b, m.S.c)
    Kp, _ = fest.assemble_K(m.pts, m.S.simp, 1.0 / (1 / 50.0 + 1 / 500.0),
                            m.S.areas, m.S.b, m.S.c)
    d = abs((Ka + Kb).tocsr() - Kp)
    rel = (d.max() if d.nnz else 0.0) / abs(Kp).max()
    assert rel < 1e-14, f"선형성이 깨졌다 (상대 {rel:.3e})"


def test_assemble_K_sparsity_is_independent_of_sheet_resistance(fest, make_mono):
    """β의 구조적 근거 — 패턴이 같아야 Ns와 SuperLU 열 순열이 같다.

    면저항 값만 바꾸면 같은 메시에서 나온 행렬이므로 패턴이 같다. 이것이
    "미지 벡터 불변 → 7개 잔차 분기를 손댈 필요 없음"의 근거다.
    """
    m = make_mono()
    Ka, _ = fest.assemble_K(m.pts, m.S.simp, 50.0, m.S.areas, m.S.b, m.S.c)
    Kb, _ = fest.assemble_K(m.pts, m.S.simp, 500.0, m.S.areas, m.S.b, m.S.c)
    assert Ka.shape == Kb.shape
    assert Ka.nnz == Kb.nnz
    assert np.array_equal(Ka.indices, Kb.indices)
    assert np.array_equal(Ka.indptr, Kb.indptr)


def test_full_area_rear_plane_is_an_ideal_equipotential(fest, make_mono):
    """`full_area`를 거부하는 근거 — 후면이 완전 등전위다.

    `full_area`의 `_Kr`은 `assemble_K(Rs=0.001)` 하드코딩이고
    (2L_FEST.py:4389-4390, `dp.Rs_rear_tco`를 무시한다) 그 결과 `Vr ≡ 0`이다.
    `K_r @ 0 = 0`이므로 후면 평면의 면전도를 어떻게 바꿔도 결과가 수학적으로
    변하지 않는다.

    이 성질이 깨지면(후면을 실제 면저항으로 바꾸면) `full_area`도 지원 대상이
    되므로 규약 §3-4의 거부 판정을 다시 해야 한다.
    """
    m = make_mono()
    Vr = np.asarray(_solve(m, _dp(fest, 100.0))["Vr"])
    assert float(Vr.max() - Vr.min()) == 0.0, (
        f"full_area의 Vr에 전압강하가 생겼다 "
        f"(span={float(Vr.max() - Vr.min()):.3e} V)")


def test_full_area_result_is_insensitive_to_rear_plane(fest, make_mono):
    """위 성질의 직접 확인 — `_Kr`을 2배로 해도 전류가 **비트 동일**하다.

    `_build`는 `_cache_hash`가 같으면 조기 반환하므로, 여기서 평면을 직접 바꾸면
    다음 solve가 그 값을 그대로 쓴다. 벌크 횡전도 구현이 하려는 조작(후면 평면의
    면전도 변경)을 미리 흉내 낸 것이다.
    """
    m = make_mono()
    dp = _dp(fest, 100.0)
    j0 = _cell_current(m, dp)
    m.S._Kr = (m.S._Kr * 2.0).tocsr()      # 시트 컨덕턴스 2배 = Rs 절반
    assert _cell_current(m, dp) == j0


def test_bifacial_rear_plane_carries_a_real_lateral_drop(fest, make_bifacial):
    """`bifacial`은 반대다 — `Vr`에 실제 전압강하가 있다.

    그래서 벌크 횡전도가 의미를 갖는 유일한 모드이고, 지원 범위가
    `rear_mode ∈ {bifacial, patterned}`로 정해진다(규약 §1-5).
    """
    m = make_bifacial()
    Vr = np.asarray(_solve(m, _dp(fest, 100.0))["Vr"])
    assert float(Vr.max() - Vr.min()) > 1e-3


def test_bifacial_result_responds_to_rear_plane(fest, make_bifacial):
    """`bifacial`에서는 `_Kr` 변경이 전류를 실제로 바꾼다 — 벌크 항이 닿는 곳."""
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    j0 = _cell_current(m, dp)
    m.S._Kr = (m.S._Kr * 2.0).tocsr()
    assert _cell_current(m, dp) != j0


def test_rear_tco_feeds_only_the_rear_plane(fest, make_bifacial):
    """`Rs_rear_tco`가 **후면 평면 조립에만** 쓰이는지 확인한다.

    벌크를 이 값과 **병렬 합성**해 `assemble_K` 인자로 넣기로 한 근거다. 만약
    `Rs_rear_tco`가 다른 강성행렬에도 새어 들어간다면, 합성값을 그쪽에도 흘리게
    되므로 구현 위치를 다시 정해야 한다.

    솔브를 거치지 않고 **조립된 행렬을 직접 비교**한다 — 솔브를 태우면 연속법
    램프·warm-start가 끼어들어 무엇이 원인인지 흐려진다
    (test_hand_patched_plane_is_discarded_without_warmup 참조).
    """
    m1, m2 = make_bifacial(), make_bifacial()
    dp1 = _dp(fest, 100.0)
    dp2 = _dp(fest, 100.0)
    dp2.Rs_rear_tco = 1.0 / (1.0 / dp2.Rs_rear_tco + 1.0 / 500.0)

    m1.S._build(**_build_args(dp1))
    m2.S._build(**_build_args(dp2))

    # 후면 평면은 달라야 한다 (그래야 이 비교가 의미 있다)
    assert not np.array_equal(m1.S._Kr.toarray(), m2.S._Kr.toarray())

    # 나머지는 전부 같아야 한다 — Rs_rear_tco가 새지 않는다는 뜻
    for attr in ("_Ke", "_Krm", "_Km", "_K_junc"):
        a, b = getattr(m1.S, attr), getattr(m2.S, attr)
        assert np.array_equal(a.toarray(), b.toarray()), (
            f"{attr}가 Rs_rear_tco에 반응한다 — 벌크 합성이 그쪽에도 흘러간다")
    assert np.array_equal(m1.S._Gc, m2.S._Gc)
    assert np.array_equal(m1.S._Gc_rear, m2.S._Gc_rear)


def test_hand_patched_plane_is_discarded_without_warmup(fest, make_bifacial):
    """⚠ **평면을 손으로 갈아 끼울 때의 함정** — 연속법 램프가 재빌드한다.

    `Rs_junction > 50`이면 `solve_tandem`이 `[50, 200, 1000, 5000, target]`으로
    램프하며 **각 단계마다 `_build`를 부른다**(`2L_FEST.py:4713-4726`). 그 호출은
    `Rs_junction`이 달라 캐시 해시가 어긋나므로 **전체 재빌드**가 일어나고, 손으로
    넣은 `_Kr`이 버려진다.

    warm-start 캐시(`_warm_V_junc_bf`)가 있으면 램프를 통째로 건너뛰므로(`:4713`)
    살아남는다.

    이 파일과 이후 단위가 평면을 직접 조작하는 테스트를 쓸 때 **반드시 warm-up
    solve를 먼저** 해야 하는 이유다. 모르고 쓰면 "평면을 바꿨는데 결과가 안
    변한다"를 모델 성질로 오해하게 된다 — 실제로 이 파일을 쓰다 한 번 겪었다.
    """
    def _patch_and_solve(warmup):
        m = make_bifacial()
        dp = _dp(fest, 100.0)
        m.S._build(**_build_args(dp))
        if warmup:
            _solve(m, dp)                       # warm-start 캐시를 채운다
        before = m.S._Kr.copy()
        m.S._Kr = (m.S._Kr * 2.0).tocsr()
        _solve(m, dp)
        return not np.array_equal(m.S._Kr.toarray(), before.toarray())

    assert _patch_and_solve(warmup=False) is False, "램프가 재빌드하지 않았다"
    assert _patch_and_solve(warmup=True) is True, "warm 경로가 램프를 건너뛰지 않았다"


# =============================================================================
# 5. Rs_base 신설 + 후면 평면 병렬 합성 (계획 단위 2)
# =============================================================================
#
# 벌크 횡전도를 **기존 후면 평면(_Kr)의 면전도에 병렬로 더한다.** 새 평면도
# 새 미지수도 만들지 않는다(β) — docs/base_lateral_convention.md.
#
#     1/Rs_r_eff = 1/Rs_rear_tco + 1/Rs_base
#
# off(`Rs_base is None`)에서 **비트 동일**이어야 한다. 그 근거가 두 겹이다:
#
#   (a) assemble_K가 받는 인자가 예전과 같은 실수 → 행렬이 비트 동일
#   (b) _build 캐시 해시의 hit/miss 판정이 예전과 동일
#
# (b)가 이 절의 핵심이다. 공간 분포에서 "맵이 없으면 0으로 태그"로 푼 것과
# **같은 문제**다 — 새 슬롯이 off에서 상수가 아니면, 아무것도 안 바뀌었는데
# 재빌드가 일어나거나(느려짐) 반대로 바뀌었는데 안 일어난다(옛 결과 재사용).


def test_rs_base_defaults_to_none(fest):
    """기본값은 off. 기존 사용자는 아무 영향을 받지 않는다."""
    assert fest.DiodeParams.Rs_base is None
    assert fest.DiodeParams().Rs_base is None


# --- 5-a. 캐시 해시 — off에서 예전과 같은 거동인가 --------------------------

def test_base_none_does_not_trigger_rebuild(fest, make_bifacial):
    """`Rs_base = None`을 다시 넣어도 재빌드가 일어나지 않는다.

    off 슬롯이 상수가 아니면(예: `None`을 그대로 넣거나 매번 다른 객체를 넣으면)
    여기서 해시가 달라져 **아무것도 안 바뀌었는데 전체 재조립**이 일어난다.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    m.S._build(**_build_args(dp))
    h0 = m.S._cache_hash
    Kr0 = m.S._Kr

    dp.Rs_base = None
    m.S._build(**_build_args(dp))

    assert m.S._cache_hash == h0
    assert m.S._Kr is Kr0, "재빌드가 일어났다 — 조기 반환되지 않았다"


def test_base_touches_exactly_one_hash_slot_and_off_is_a_constant(fest,
                                                                  make_bifacial):
    """**이 절의 핵심 테스트.**

    `Rs_base`가 해시 튜플에서 **정확히 한 슬롯만** 건드리고, off일 때 그 슬롯이
    **상수 0**이어야 한다. 그래야 off 경로의 hit/miss 판정이 예전 필드들만으로
    결정된다 — 즉 캐시 거동이 이전과 완전히 같다.

    공간 분포의 `_sm_tag`가 "맵 없으면 0"인 것과 같은 처리다(`2L_FEST.py:4314`
    주석). 슬롯을 여러 개 건드리면 이 논증이 성립하지 않는다.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)

    m.S._build(**_build_args(dp))
    h_off = m.S._cache_hash

    dp.Rs_base = 500.0
    m.S._build(**_build_args(dp))
    h_on = m.S._cache_hash

    assert len(h_off) == len(h_on), "슬롯 개수가 조건에 따라 달라진다"
    diff = [i for i, (a, b) in enumerate(zip(h_off, h_on)) if a != b]
    assert len(diff) == 1, f"Rs_base가 해시의 여러 슬롯을 건드린다: {diff}"

    slot = diff[0]
    assert h_off[slot] == 0, f"off 센티넬이 0이 아니다: {h_off[slot]!r}"
    assert h_on[slot] == 500.0


def test_off_hash_slot_stays_constant_across_other_parameter_changes(
        fest, make_bifacial):
    """다른 파라미터를 아무리 바꿔도 off 슬롯은 계속 0이다.

    "off일 때 상수"가 실제로 상수인지 확인한다 — 다른 값에 연동되면 상수가
    아니고, 그러면 캐시 거동이 예전과 같다는 논증이 무너진다.
    """
    m = make_bifacial()
    seen = set()
    for rs_front in (15.0, 20.0):
        for rc in (5e-3, 6e-3):
            for rs_j in (100.0, 300.0):
                dp = _dp(fest, rs_j)
                args = _build_args(dp)
                args["Rs_front"] = rs_front
                args["rc"] = rc
                m.S._build(**args)
                h = m.S._cache_hash
                seen.add(h[_base_slot(fest, make_bifacial)])
    assert seen == {0}, f"off 슬롯이 상수가 아니다: {seen}"


def _base_slot(fest, make_bifacial):
    """`Rs_base`가 차지하는 해시 슬롯 번호를 실측으로 찾는다.

    인덱스를 테스트에 하드코딩하면 나중에 해시 튜플에 필드가 추가될 때 조용히
    엉뚱한 슬롯을 보게 된다.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    m.S._build(**_build_args(dp))
    off = m.S._cache_hash
    dp.Rs_base = 777.0
    m.S._build(**_build_args(dp))
    on = m.S._cache_hash
    (slot,) = [i for i, (a, b) in enumerate(zip(off, on)) if a != b]
    return slot


def test_base_change_invalidates_build_cache(fest, make_bifacial):
    """`Rs_base`를 바꾸면 반드시 재빌드된다.

    안 되면 **옛 `_Kr`이 조용히 재사용된다** — v28.56이 `id()` 캐시에서 겪은
    실패와 같은 형태이고, 오류도 경고도 없이 옛 결과가 나온다.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    m.S._build(**_build_args(dp))
    h0, Kr0 = m.S._cache_hash, m.S._Kr

    dp.Rs_base = 500.0
    m.S._build(**_build_args(dp))

    assert m.S._cache_hash != h0
    assert m.S._Kr is not Kr0
    assert not np.array_equal(m.S._Kr.toarray(), Kr0.toarray())


def test_base_on_then_off_restores_the_original_plane(fest, make_bifacial):
    """켰다 끄면 후면 평면이 **비트 단위로** 원래대로 돌아온다."""
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    m.S._build(**_build_args(dp))
    Kr_ref = m.S._Kr.copy()

    dp.Rs_base = 500.0
    m.S._build(**_build_args(dp))
    assert not np.array_equal(m.S._Kr.toarray(), Kr_ref.toarray())

    dp.Rs_base = None
    m.S._build(**_build_args(dp))
    assert np.array_equal(m.S._Kr.toarray(), Kr_ref.toarray())


# --- 5-b. 병렬 합성이 규약대로인가 ------------------------------------------

def test_base_off_assembles_the_legacy_rear_plane_exactly(fest, make_bifacial):
    """**off는 `assemble_K` 인자를 건드리지 않는다** — 산술적 비트 동일 근거.

    `Rs_base is None`이면 `Rs_r_eff`가 `Rs_rear_tco` 그 자체이므로 부동소수점
    연산이 하나도 추가되지 않는다(공간 분포의 "곱셈을 아예 하지 않음"과 같은
    계열). 조립된 행렬을 직접 비교해 그것을 확인한다.

    ⚠ 솔브 결과로 이걸 확인하려 하면 안 된다 — **같은 솔버로 두 번 풀면
    warm-start 때문에 두 번째 답이 미세하게 다르다.** 이 파일을 쓰다 한 번
    걸렸다. 비트 동일의 최종 확인은 `tests/test_default_pin.py` /
    `test_legacy_pin.py`(변경 전 값을 들고 있다)가 한다.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    m.S._build(**_build_args(dp))
    K_ref, _ = fest.assemble_K(m.pts, m.S.simp, dp.Rs_rear_tco, m.S.areas,
                               m.S.b, m.S.c)
    assert np.array_equal(m.S._Kr.toarray(), K_ref.toarray())


def test_base_off_explicit_none_matches_unset(fest, make_bifacial):
    """`Rs_base = None`을 명시해도 미지정과 같은 결과다 (별개 솔버 비교)."""
    m1, m2 = make_bifacial(), make_bifacial()
    dp1 = _dp(fest, 100.0)                      # 미지정
    dp2 = _dp(fest, 100.0); dp2.Rs_base = None  # 명시적 None
    assert _cell_current(m1, dp1) == _cell_current(m2, dp2)


def test_base_plane_equals_parallel_sheet_resistance(fest, make_bifacial):
    """벌크를 켠 후면 평면 == 병렬 합성 면저항으로 조립한 평면 (비트 동일).

    규약 §1-4(병렬 합)를 행렬 수준에서 직접 고정한다. 솔브를 태우지 않으므로
    연속법 램프·warm-start가 끼어들지 않는다.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    dp.Rs_base = 500.0
    m.S._build(**_build_args(dp))

    eff = 1.0 / (1.0 / dp.Rs_rear_tco + 1.0 / 500.0)
    K_ref, _ = fest.assemble_K(m.pts, m.S.simp, eff, m.S.areas, m.S.b, m.S.c)
    assert np.array_equal(m.S._Kr.toarray(), K_ref.toarray())


def test_base_does_not_mutate_user_rear_tco(fest, make_bifacial):
    """`dp.Rs_rear_tco`는 사용자 입력 그대로 남는다.

    병렬 합성은 `assemble_K` **호출 인자**에서만 한다. `dp`를 제자리 수정하면
    GUI 표시와 캐시 해시가 사용자 입력과 어긋난다.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    dp.Rs_base = 500.0
    before = dp.Rs_rear_tco
    m.S._build(**_build_args(dp))
    _solve(m, dp)
    assert dp.Rs_rear_tco == before


def test_base_only_changes_the_rear_plane(fest, make_bifacial):
    """벌크는 후면 평면에만 들어간다 — 다른 강성행렬은 불변이다.

    특히 `_Ke`(전면 TCO)에 새어 들어가면 안 된다. 그것은 페로브스카이트
    상부셀의 전극이라 실리콘 벌크와 무관하다(규약 §3-5).
    """
    m1, m2 = make_bifacial(), make_bifacial()
    dp1 = _dp(fest, 100.0)
    dp2 = _dp(fest, 100.0)
    dp2.Rs_base = 500.0

    m1.S._build(**_build_args(dp1))
    m2.S._build(**_build_args(dp2))

    assert not np.array_equal(m1.S._Kr.toarray(), m2.S._Kr.toarray())
    for attr in ("_Ke", "_Krm", "_Km", "_K_junc"):
        a, b = getattr(m1.S, attr), getattr(m2.S, attr)
        assert np.array_equal(a.toarray(), b.toarray()), (
            f"{attr}가 Rs_base에 반응한다 — 벌크가 후면 평면 밖으로 샜다")
    assert np.array_equal(m1.S._Gc, m2.S._Gc)
    assert np.array_equal(m1.S._Gc_rear, m2.S._Gc_rear)


def test_unknown_layout_unchanged_by_base(fest, make_bifacial, monkeypatch):
    """**β의 핵심** — 벌크를 켜도 미지 벡터가 변하지 않는다.

    이것이 성립해야 잔차 분기 7곳을 손대지 않아도 된다.
    """
    m = make_bifacial()
    N, Nm, Nrm = _plane_sizes(m)
    dp = _dp(fest, 100.0)
    assert _observed_Ns(fest, m, dp, monkeypatch) == 4 * N + Nm + Nrm
    dp.Rs_base = 500.0
    assert _observed_Ns(fest, m, dp, monkeypatch) == 4 * N + Nm + Nrm


# --- 5-c. 값 제약 ------------------------------------------------------------

@pytest.mark.parametrize("bad", [0.0, -1.0, -500.0,
                                 float("nan"), float("inf"), float("-inf")])
def test_base_rejects_non_positive_or_non_finite(fest, make_bifacial, bad):
    """면저항은 유한하고 양수여야 한다.

    0은 무한 컨덕턴스라 물리적으로 성립하지 않고, `assemble_K`의
    `coeff = 1/(4·A·Rs)`가 0으로 나눈다(`2L_FEST.py:2649`). 조용히 고치지 않고
    거부한다(v28.43·v28.54·v28.57 전례).
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    dp.Rs_base = bad
    with pytest.raises(ValueError) as exc:
        m.S._build(**_build_args(dp))
    msg = str(exc.value)
    assert "Rs_base" in msg
    assert "None" in msg          # 끄는 방법을 알려준다


def test_base_rejects_non_numeric(fest, make_bifacial):
    """숫자가 아니면 거부한다 — np.isfinite가 TypeError로 터지기 전에 잡는다.

    숫자 문자열("500")은 float()이 받으므로 거부 대상이 아니다 —
    `_parse_gui_float`가 GUI 입력을 문자열로 받는 것과 같은 관용이다.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    for bad in ("abc", [500.0], {"Rs": 500}, object()):
        dp.Rs_base = bad
        with pytest.raises(ValueError) as exc:
            m.S._build(**_build_args(dp))
        assert "Rs_base" in str(exc.value)


def test_zero_is_rejected_so_the_off_sentinel_cannot_collide(fest,
                                                             make_bifacial):
    """off 센티넬 0이 **유효한 값과 충돌하지 않음**을 보장한다.

    0이 받아들여지면 "off"와 "Rs_base=0"이 같은 해시를 갖게 되어, 둘 사이를
    오갈 때 재빌드가 일어나지 않는다. `_sm_tag`가 0을 센티넬로 쓸 수 있는 이유와
    같다 — 유효한 content_key()는 절대 0이 아니다.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    dp.Rs_base = 0.0
    with pytest.raises(ValueError):
        m.S._build(**_build_args(dp))


def test_base_validation_runs_before_the_cache_early_return(fest,
                                                            make_bifacial):
    """잘못된 값은 **캐시 적중이어도** 거부한다.

    검증이 조기 반환 뒤에 있으면, 같은 파라미터로 두 번째 호출할 때 잘못된 값이
    그냥 통과한다. 값 제약은 v28.57 로더와 같이 **진입 시점에** 끝낸다.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    m.S._build(**_build_args(dp))          # 캐시를 채운다
    dp.Rs_base = -1.0
    with pytest.raises(ValueError):
        m.S._build(**_build_args(dp))


def test_base_accepts_int_and_normalizes(fest, make_bifacial):
    """정수 입력도 받되 해시는 float으로 정규화한다 — 500과 500.0이 같아야 한다."""
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    dp.Rs_base = 500
    m.S._build(**_build_args(dp))
    h_int = m.S._cache_hash
    dp.Rs_base = 500.0
    m.S._build(**_build_args(dp))
    assert m.S._cache_hash == h_int


# --- 5-d. 물리 방향 ----------------------------------------------------------

def test_base_lowers_effective_rear_sheet_resistance(fest, make_bifacial):
    """벌크가 병렬로 붙으면 유효 면저항이 **내려간다** (전도가 좋아진다).

    후면 평면 강성이 커지는 것으로 확인한다 — 값이 아니라 방향을 본다.
    """
    m1, m2 = make_bifacial(), make_bifacial()
    dp1 = _dp(fest, 100.0)
    dp2 = _dp(fest, 100.0)
    dp2.Rs_base = 500.0
    m1.S._build(**_build_args(dp1))
    m2.S._build(**_build_args(dp2))
    assert abs(m2.S._Kr).max() > abs(m1.S._Kr).max()


def test_base_large_sheet_r_approaches_off(fest, make_bifacial):
    """`Rs_base` → ∞ 이면 off에 수렴한다.

    비트 동일은 기대하지 않는다 — `1/(1/Rs + 1e-12)`가 `Rs`와 비트 동일하지
    않기 때문이다. 물리적 동등성 수준의 일치를 본다
    (`docs/registration_material.md` §5-1의 두 층 구분).
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    j_off = _cell_current(m, dp)
    dp.Rs_base = 1e12
    assert _cell_current(m, dp) == pytest.approx(j_off, rel=1e-9)
