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

def test_no_base_lateral_parameter_exists_yet(fest):
    """아직 `Rs_base`가 없다. **단위 2에서 이 테스트를 뒤집는다.**

    기준선을 명시적으로 남겨, 단위 2가 무엇을 바꿨는지 diff로 드러나게 한다.
    """
    assert not hasattr(fest.DiodeParams, "Rs_base")
    assert not hasattr(fest.DiodeParams, "Gv_base")


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
