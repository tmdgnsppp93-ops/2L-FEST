# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""공간 분포 맵 — 분기 커버리지 (계획 단위 0 특성화 → 단위 1 검증).

`spatial_j01`/`j02`/`gen` 세 맵이 **모든 분기에서** 잔차에 반영되는지를 실측으로
고정한다. 단위 0에서는 이 파일이 결함 12칸을 `xfail(strict=True)`로 기록했고,
**v28.61(단위 1)이 그 12칸을 전부 해소**했다 — `_diode_node_arrays` 중앙화.

| 시점 | 상태 |
|---|---|
| 단위 0 (v28.60) | 65 passed · **32 xfailed**(결함 12칸 × 2지표 + 헬퍼 부재 8) |
| 단위 1 (v28.61) | **전부 통과** — `RESIDUAL_SEES_MAP`에 `False`가 없다 |

strict였기 때문에 v28.61이 고친 순간 XPASS → 실패로 떠서 마커를 지우게 강제됐다.
`strict=False`였다면 조용히 통과해 신호가 사라졌을 것이다
(`test_no_unresolved_defect_cells_remain`이 그 장치를 유지한다).

계획: docs/superpowers/plans/2026-08-18-spatial-map-branch-coverage.md
결함: docs/spatial_map_convention.md §6 · docs/WORKLOG.md §2-6

판정 지표 — 왜 `cell_current`가 아닌가
--------------------------------------
v28.60의 `cell_current`는 맵을 **무조건** 적용했다. 잔차가 맵을 무시한 분기에서도
Δ ≠ 0이 나왔다 — 맵 없는 전압장에서 수렴시킨 뒤 맵 있는 다이오드 식으로 재계산한
**자기모순 값**이기 때문이다. 단위 0 실측:

    phaseB_full_area / gen :  전압장 Δ = 0 (비트 동일)  이지만  ΔJ = +4.426 mA/cm²

v28.61이 그 자기모순을 없앴지만(솔버와 `cell_current`가 같은 헬퍼를 거친다),
**판정 지표는 그대로 수렴 전압장이다.** `ΔJ ≠ 0`은 고치기 전에도 참이었으므로
작동 근거가 될 수 없다 — 새 물성을 추가할 때도 같은 규칙을 쓸 것.
보조로 잔차 분기 프레임의 지역 변수를 `sys.settrace`로 직접 관측한다.

⚠ 계획서 §단위0 T2의 *"`J01_top_arr`가 배열인지 스칼라인지 고정"* 은 **성립하지
않는다** (2026-08-19 실측으로 정정). `J01_top_arr = dp.J01_top_pass * (1 - mf) +
...` 의 `mf`(`metal_frac`)가 이미 **노드 길이 배열**이라, 맵을 무시하는 분기에서도
`J01_top_arr`는 `ndarray[N]`이다. dtype·shape로는 결함이 보이지 않는다.
그래서 이 파일은 **무맵 실행과 유맵 실행의 같은 지역 변수를 비트 비교**한다 —
파생값이 아니라 조작 대상 자체의 관측이고, 해석의 여지가 없다.

이 파일이 새로 찾아낸 것 (2026-08-19)
--------------------------------------
1. **`_solve_single_bifacial`(`2L_FEST.py:6513`)이 5번째 결함 분기다.**
   `docs/spatial_map_convention.md` §6은 *"단일셀(`solve_single` `:6431`)은 4종
   모두 정상이다"* 라고 적었으나, `solve_single`은 rear가 patterned/bifacial이면
   `:6396`에서 `_solve_single_bifacial`로 **빠져나간다.** 그쪽은 `_spatial_mult`
   호출이 없다(`:6546-6547`). 즉 §6의 16칸 표는 단일셀 bifacial 행이 통째로 빠져
   있고, 실제 결함 칸은 9개가 아니라 **12개**다.
2. **`BRANCH_CASES`가 그 분기를 못 보고 있었다 → 원본을 고쳤다.**
   `test_base_lateral.py`의 `_NAMED_SOLVERS`에 `_solve_single_bifacial`이 없어서
   `single_bifacial` 케이스가 `inline`으로 판정됐고, 그래서
   `test_case_table_covers_every_reachable_named_solver`도 그 분기를 세지 않고
   **통과했다**. 감시하지 않는 분기는 "도달했다"로 카운트되지 않는다.
   → `_NAMED_SOLVERS`에 추가하고 케이스 7의 기대 분기를 정정했다(2026-08-19).
   `test_named_solvers_covers_single_bifacial`과
   `test_actual_branch_agrees_with_base_lateral_table`이 되돌아가는 것을 막는다.

   **벌크 횡전도(`Rs_base`)에는 이 누락으로 인한 공백이 없었다** — `Rs_base`는
   `_build`(`:4396-4488`) 안의 강성 조립이라 디스패치보다 앞이고, 분기 정체와
   무관하게 모든 경로에 적용된다(`spatial_rc`가 무사한 것과 같은 구조적 이유).
   `test_single_mode_bifacial_supports_base`(`:1007`)와
   `test_base_gate_follows_the_rear_plane_not_the_phase`(`:1029`)가 이 분기를
   실제로 푼다. **표의 라벨만 틀렸고 기능 커버리지는 온전했다.**
3. **인라인 조립 지점은 계획서의 9곳이 아니라 13개 함수 34줄이었다.**
   계획서 §1 표에 없는 것: `_solve_single_bifacial`(잔차!) · `losses` ·
   `recomb_currents` · `_tab_current`(GUI). v28.61이 13곳 전부를 배선해
   **1개 함수 4줄**이 됐다(`INLINE_ASSEMBLY_CENSUS`).
4. **`DiodeParams.J02_single_pass/metal`의 기본값이 0.0이다.** 그래서 단일셀에서
   `j02` 맵은 무엇을 곱하든 결과가 변하지 않는다 — 결함이 아니라 **관측 불가**다.
   단일셀 케이스에 한해 `J02_SINGLE_PROBE`로 0이 아닌 값을 넣어 칸을 관측 가능하게
   만든다. 탠덤 칸은 기본값 그대로다(핀 값과의 대조를 유지하기 위해).

v28.61이 값을 건드리지 않았다는 근거
------------------------------------
Phase A / full_area는 v28.60에서 **유일하게 올바른 탠덤 경로**였다. 단위 0이
수정 전에 5조합(무맵 + 맵 4종)의 전압장 sha256과 `cell_current`를 캡처해 뒀고,
v28.61 이후 **5조합 전부 비트 동일**이다(`PHASE_A_PINS`). 리팩터가 계산을
바꾸지 않았다는 뜻이다.

⚠ 이 파일은 `sys.settrace`를 쓴다. 커버리지 도구(`pytest-cov`)와 동시에 돌리면
서로 훅을 덮어쓴다 — 커버리지 측정 시에는 이 파일을 제외할 것.
"""
import ast
import hashlib
import os
import re
import sys

import numpy as np
import pytest

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_TESTS_DIR)
sys.path.insert(0, _ROOT)
sys.path.insert(0, _TESTS_DIR)

# 분기 표는 **import 한다.** 복제하면 두 벌이 되어 갈린다(계획 §T2).
from test_base_lateral import BRANCH_CASES, PARAMS, VB, _INLINE  # noqa: E402

SRC_PATH = os.path.join(_ROOT, "2L_FEST.py")

# 단위 1이 만들 중앙 헬퍼. 이 이름이 T1의 유일한 허용 소유자다.
HELPER_NAME = "_diode_node_arrays"

# 단일셀 j02 칸을 관측 가능하게 만드는 값. 기본값 0.0이면 맵을 곱해도 0이라
# "결함"과 "영향 없음"을 구분할 수 없다(위 §4).
J02_SINGLE_PROBE = 1e-9


# =============================================================================
# 0. 관측 도구
# =============================================================================
#
# 두 가지를 본다.
#   (a) 수렴 전압장  — 잔차가 맵을 봤는가에 대한 **최종 판정**
#   (b) 분기 프레임의 지역 다이오드 배열 — 같은 사실의 **직접 관측**
# 둘은 독립적인 근거다. (a)만 두면 "왜 안 변했는가"를 말할 수 없고, (b)만 두면
# 지역 변수 이름이 바뀔 때 조용히 무력해진다.

# `_NAMED_SOLVERS`(test_base_lateral)의 상위집합. `_solve_single_bifacial`과
# 인라인 두 곳(solve_tandem / solve_single)을 더한다 — 인라인 경로도 프레임을
# 관측해야 "정상 칸"의 근거가 생긴다.
WATCHED_FRAMES = (
    "solve_tandem",
    "_solve_tandem_junction",
    "_solve_tandem_junction_bf",
    "_solve_tandem_junction_bf_v29",
    "_solve_tandem_bifacial",
    "solve_single",
    "_solve_single_bifacial",
)

# 대상 → 그 대상이 곱해져야 하는 지역 변수 후보. 분기마다 이름이 다르고, 결함
# 분기에는 **아예 없는 것도 있다**(`_gen_t`는 맵을 쓰는 경로에만 생긴다).
# 없으면 "맵을 안 봤다"로 판정한다 — 그것이 사실이다.
TARGET_LOCALS = {
    "j01": ("J01_top_arr", "_J01b", "J01_arr"),
    "j02": ("J02_top_arr", "_J02b", "J02_arr"),
    "gen": ("_gen_t", "_gen_b", "_gen"),
    # rc는 `_build` 안에서 `_Gc`를 고치는 강성 조립(B 계층)이라 다이오드 지역
    # 배열에 나타나지 않는다. 전압장 판정만 한다.
    "rc": (),
    # rsh는 j01/j02와 **같은 계층**(A, 노드 잔차)이다. 분기마다 이름이 다른
    # j01/j02와 달리 헬퍼 도입 이후 도입되므로 **모든 분기에서 같은 이름**을 쓴다.
    "rsh": ("Rsh_arr", "Rshb_arr"),
}

_ALL_LOCALS = tuple(sorted({n for v in TARGET_LOCALS.values() for n in v}))


def _canonical_map(fest):
    """모든 대상에 공통으로 쓰는 맵. 셀 중앙에 완만한 2배 피크.

    `feature=2.0`은 배율이므로 어느 대상에 붙여도 부호가 뒤집히지 않는다
    (`SpatialMap.evaluate`가 양수를 강제한다). 형상을 대상별로 바꾸면 칸끼리
    비교할 수 없으므로 **하나로 고정**한다.
    """
    return fest.SpatialMap(mode="gaussian", background=1.0, feature=2.0,
                           cx=1.0, cy=1.0, sigma_x=0.4, sigma_y=0.4)


def _voltage_field(result):
    """수렴 전압장을 하나의 1D 배열로. **비트 비교용이다.**

    `Vm`은 비금속 노드가 NaN이라(`2L_FEST.py:6368`) 그대로 두면 `==`도
    `np.array_equal`도 항상 False가 된다. NaN 위치는 메시 구조가 정하는 것이라
    두 실행에서 동일하므로 0.0으로 치환한다. `Vtop`/`Vint`는 단일셀에서 None이다.
    """
    parts = []
    for key in ("Ve", "Vm", "Vr", "Vtop", "Vint"):
        v = result.get(key)
        if v is None:
            continue
        a = np.asarray(v, dtype=float)
        parts.append(np.where(np.isnan(a), 0.0, a).ravel())
    return np.concatenate(parts)


def _make_tracer(frames_seen, locals_seen):
    """`sys.settrace` 훅 — 감시 프레임의 return 시점 지역 변수를 담는다.

    `frame.f_trace_lines = False`로 line 이벤트를 끈다. 이걸 안 하면 뉴턴 루프
    한 줄마다 훅이 불려 solve가 수십 배 느려진다. return 이벤트는 그대로 온다.
    """
    def _local(frame, event, arg):
        if event == "return":
            f_locals = frame.f_locals
            for name in _ALL_LOCALS:
                if name in f_locals:
                    key = (frame.f_code.co_name, name)
                    if key not in locals_seen:
                        locals_seen[key] = np.asarray(
                            f_locals[name], dtype=float).copy()
        return _local

    def _tracer(frame, event, arg):
        if event == "call" and frame.f_code.co_name in WATCHED_FRAMES:
            frames_seen.append(frame.f_code.co_name)
            frame.f_trace_lines = False
            return _local
        return None

    return _tracer


class Observation:
    """한 번의 solve에서 얻은 모든 관측치."""

    __slots__ = ("branch", "V", "J", "locals")

    def __init__(self, branch, V, J, locals_):
        self.branch = branch
        self.V = V
        self.J = J
        self.locals = locals_

    def digest(self):
        return hashlib.sha256(
            np.ascontiguousarray(self.V, dtype=np.float64).tobytes()).hexdigest()


def _dp(fest, rs_j, mode, target):
    dp = fest.DiodeParams()
    if rs_j is not None:
        dp.Rs_junction = rs_j
    if mode == "single":
        # 위 §4 — 기본값 0.0이면 j02 칸이 관측 불가다. 탠덤은 건드리지 않는다.
        dp.J02_single_pass = J02_SINGLE_PROBE
        dp.J02_single_metal = J02_SINGLE_PROBE
    if target is not None:
        fest.set_spatial_map(dp, target, _canonical_map(fest))
    return dp


def _observe(fest, solver_factory, rs_j, legacy, mode, target):
    """solve 한 번 = 관측 하나. **매번 새 솔버**를 쓴다.

    warm-start(`_warm_V_junc_bf` 등)가 남으면 무맵 실행의 해가 유맵 실행의
    출발점이 되어 "맵을 봤는가"의 판정이 오염된다.
    """
    prev = os.environ.get("FEST_LEGACY_LOCAL_MATCH")
    os.environ["FEST_LEGACY_LOCAL_MATCH"] = "1" if legacy else ""
    frames, loc = [], {}
    try:
        m = solver_factory()
        dp = _dp(fest, rs_j, mode, target)
        sys.settrace(_make_tracer(frames, loc))
        try:
            result = m.S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"],
                               PARAMS["rc"], PARAMS["Rs"], VB, PARAMS["cf"],
                               dp, mode)
        finally:
            sys.settrace(None)
        return Observation(frames[-1] if frames else _INLINE,
                           _voltage_field(result),
                           float(m.S.cell_current(result, dp)), loc)
    finally:
        if prev is None:
            os.environ.pop("FEST_LEGACY_LOCAL_MATCH", None)
        else:
            os.environ["FEST_LEGACY_LOCAL_MATCH"] = prev


# 관측 캐시. 24칸 x (무맵 + 유맵) = 48회 solve인데, 무맵 기준은 분기당 하나면
# 충분하므로 6 + 24 = 30회로 줄어든다. 캐시에 담는 것은 순수 배열이라 테스트
# 사이에 새어 나갈 상태가 없다.
_CACHE = {}


def _cached(fest, geo_factory, case, target):
    label, geo, rs_j, legacy, mode = case[:5]
    key = (label, target)
    if key not in _CACHE:
        _CACHE[key] = _observe(fest, geo_factory[geo], rs_j, legacy, mode,
                               target)
    return _CACHE[key]


# =============================================================================
# 1. 실측 표 — 잔차가 맵을 보는가 (2026-08-19, 이 파일이 고정하는 사실)
# =============================================================================
#
# **올바른 값은 전부 True다.** False인 칸이 결함이고, 단위 1이 고쳐야 할 목록이다.
# 단위 1의 완료 조건 = 이 dict에 False가 하나도 남지 않는 것.
#
# 도달 분기별로 묶으면:
#   solve_tandem (인라인)        rc✅ j01✅ j02✅ gen✅   유일하게 정상인 탠덤
#   _solve_tandem_junction       rc✅ j01❌ j02❌ gen❌   **기본 설정이 여기다**
#   _solve_tandem_junction_bf    rc✅ j01❌ j02❌ gen❌
#   _solve_tandem_bifacial       rc✅ j01❌ j02❌ gen❌
#   solve_single (인라인)         rc✅ j01✅ j02✅ gen✅
#   _solve_single_bifacial       rc✅ j01❌ j02❌ gen❌   ← §6 표에 없던 분기
#
# `rc`가 6/6 정상인 이유는 계층이 다르기 때문이다 — `_build` 안의 강성 조립이고
# `_build`는 디스패치보다 앞이라 모든 경로에서 반드시 실행된다.

RESIDUAL_SEES_MAP = {
    ("phaseA_full_area", "j01"): True,
    ("phaseA_full_area", "j02"): True,
    ("phaseA_full_area", "gen"): True,
    ("phaseA_full_area", "rc"): True,

    ("phaseB_full_area", "j01"): True,     # v28.61에서 해소
    ("phaseB_full_area", "j02"): True,     # v28.61에서 해소
    ("phaseB_full_area", "gen"): True,     # v28.61에서 해소
    ("phaseB_full_area", "rc"): True,

    ("phaseB_bifacial", "j01"): True,      # v28.61에서 해소
    ("phaseB_bifacial", "j02"): True,      # v28.61에서 해소
    ("phaseB_bifacial", "gen"): True,      # v28.61에서 해소
    ("phaseB_bifacial", "rc"): True,

    ("phaseA_bifacial", "j01"): True,      # v28.61에서 해소
    ("phaseA_bifacial", "j02"): True,      # v28.61에서 해소
    ("phaseA_bifacial", "gen"): True,      # v28.61에서 해소
    ("phaseA_bifacial", "rc"): True,

    ("single_full_area", "j01"): True,
    ("single_full_area", "j02"): True,     # J02_SINGLE_PROBE 필요 (§4)
    ("single_full_area", "gen"): True,
    ("single_full_area", "rc"): True,

    ("single_bifacial", "j01"): True,      # v28.61에서 해소
    ("single_bifacial", "j02"): True,      # v28.61에서 해소
    ("single_bifacial", "gen"): True,      # v28.61에서 해소
    ("single_bifacial", "rc"): True,

    # --- 5번째 대상: shunt (2026-08-19 단위 0) --------------------------------
    # 전부 False다. **결함이 아니라 미구현**이다 — `rsh`는 SPATIAL_TARGETS에
    # 아직 없어서 맵을 붙이는 것 자체가 거부된다. 구현되면 6칸이 True가 된다.
    ("phaseA_full_area", "rsh"): False,
    ("phaseB_full_area", "rsh"): False,
    ("phaseB_bifacial", "rsh"): False,
    ("phaseA_bifacial", "rsh"): False,
    ("single_full_area", "rsh"): False,
    ("single_bifacial", "rsh"): False,
}

# 실제 도달 분기. `BRANCH_CASES`의 `expected_branch`와 일치한다 — 단, 그쪽은
# 인라인 두 경로를 `_INLINE` 하나로 묶으므로 여기가 더 촘촘하다.
# (2026-08-19까지는 single_bifacial에서 어긋나 있었다. 원본을 고쳤다.)
ACTUAL_BRANCH = {
    "phaseA_full_area": "solve_tandem",
    "phaseB_full_area": "_solve_tandem_junction",
    "phaseB_bifacial": "_solve_tandem_junction_bf",
    "phaseA_bifacial": "_solve_tandem_bifacial",
    "single_full_area": "solve_single",
    "single_bifacial": "_solve_single_bifacial",
}

# 이 표가 덮으려는 대상. **`fest.SPATIAL_TARGETS`와 다를 수 있다** — 아직
# 구현되지 않은 대상을 여기 먼저 올리고 결함 칸을 `False`로 두는 것이 단위 0의
# 방식이기 때문이다(그 칸에 strict xfail이 붙어 구현되는 순간 XPASS로 뒤집힌다).
TARGETS = ("j01", "j02", "gen", "rc", "rsh")

# 단위 0 시점에 **아직 엔진에 없는** 대상. 구현되면 여기를 비운다.
#   - `set_spatial_map(dp, 'rsh', ...)`가 ValueError를 던진다(레지스트리에 없다)
#   - 그래서 아래 교차 테스트가 실패하고, strict xfail이 그것을 예상 결과로 잡는다
# 근거: Griddler 매뉴얼 §3.1이 "most cell parameters"에 shunt conductance를
# 포함하고 GUI에도 nonuniform 진입 버튼이 있는데 우리에게 빠져 있었다.
# Rsh는 이미 노드 잔차(A 계층)에 있어 j01/j02와 같은 계층이다.
NOT_YET_IMPLEMENTED = ("rsh",)

IMPLEMENTED_TARGETS = tuple(t for t in TARGETS if t not in NOT_YET_IMPLEMENTED)


@pytest.fixture
def geo_factory(make_mono, make_bifacial):
    return {"mono": make_mono, "bifacial": make_bifacial}


def _case_by_id():
    return {c.id: c.values for c in BRANCH_CASES}


def _cross(targets=TARGETS):
    """`BRANCH_CASES` x 대상. 결함 칸에는 strict xfail을 붙인다."""
    out = []
    for case in BRANCH_CASES:
        for t in targets:
            marks = ()
            if not RESIDUAL_SEES_MAP[(case.id, t)]:
                if t in NOT_YET_IMPLEMENTED:
                    why = (f"미구현 — spatial_{t}가 SPATIAL_TARGETS에 아직 없다. "
                           f"맵을 붙이는 것 자체가 거부된다")
                else:
                    why = (f"결함 — {ACTUAL_BRANCH[case.id]}가 spatial_{t}를 "
                           f"잔차에 반영하지 않는다. "
                           f"docs/spatial_map_convention.md §6")
                marks = pytest.mark.xfail(strict=True, reason=why)
            out.append(pytest.param(case.values, t, marks=marks,
                                    id=f"{case.id}-{t}"))
    return out


# =============================================================================
# 2. 표가 살아 있는가 — 전제 검사
# =============================================================================
#
# 아래 건들은 `RESIDUAL_SEES_MAP`·`ACTUAL_BRANCH`가 실제 코드와 같은 것을
# 가리키는지 확인한다. 이게 어긋나면 위 표 전체가 의미를 잃는다.

def test_cross_table_matches_branch_cases():
    """`BRANCH_CASES`가 바뀌면 이 파일의 표도 같이 바뀌어야 한다."""
    ids = {c.id for c in BRANCH_CASES}
    assert ids == set(ACTUAL_BRANCH), (
        f"BRANCH_CASES가 바뀌었다: {sorted(ids)} vs {sorted(ACTUAL_BRANCH)} — "
        f"RESIDUAL_SEES_MAP/ACTUAL_BRANCH를 함께 갱신할 것")
    assert set(RESIDUAL_SEES_MAP) == {(i, t) for i in ids for t in TARGETS}


def test_spatial_targets_registry_matches_the_table(fest):
    """엔진 레지스트리 == 이 표에서 **구현됐다고 적은** 대상.

    대상이 늘었는데 표가 안 늘면 새 대상이 감시 밖에 놓인다. 반대로 표에만
    올리고 구현이 안 됐으면 `NOT_YET_IMPLEMENTED`에 있어야 한다 — 그래야 그
    칸의 xfail이 "미구현"이라는 정확한 사유를 갖는다.

    구현이 끝나면 `NOT_YET_IMPLEMENTED`를 비우고, 그 순간 이 단언이 5종을
    요구하게 된다.
    """
    assert fest.SPATIAL_TARGETS == IMPLEMENTED_TARGETS, (
        f"레지스트리={fest.SPATIAL_TARGETS} vs 표의 구현분={IMPLEMENTED_TARGETS} — "
        f"대상을 추가했으면 TARGETS와 RESIDUAL_SEES_MAP을 함께 갱신할 것")


@pytest.mark.parametrize("target", NOT_YET_IMPLEMENTED or ["<none>"])
def test_not_yet_implemented_targets_are_actually_rejected(fest, target):
    """미구현이라고 적은 대상이 **실제로** 거부되는지 확인한다.

    이 테스트가 없으면 `NOT_YET_IMPLEMENTED`가 낡아도 아무도 모른다 — 구현이
    끝났는데 목록에 남아 있으면 위 교차 테스트 6칸이 XPASS로 뒤집혀 실패하므로
    결국 잡히지만, **여기가 먼저** 잡아서 원인을 정확히 말해 준다.

    구현이 끝나면 `NOT_YET_IMPLEMENTED = ()`가 되어 이 테스트는 수집되지 않는다
    (파라미터가 비면 `<none>` 하나가 들어와 즉시 통과한다).
    """
    if target == "<none>":
        assert not NOT_YET_IMPLEMENTED
        return
    assert target not in fest.SPATIAL_TARGETS
    assert not hasattr(fest.DiodeParams, f"spatial_{target}")
    with pytest.raises(ValueError) as exc:
        fest.set_spatial_map(fest.DiodeParams(), target, fest.SpatialMap())
    assert target in str(exc.value)


def test_no_unresolved_defect_cells_remain():
    """**결함 칸이 하나도 남아 있지 않다** (v28.61에서 12개 전부 해소).

    단위 0에서는 12칸이 `False`였고 각 칸에 `xfail(strict=True)`가 붙었다.
    strict였기 때문에 v28.61이 고친 순간 XPASS → 실패로 떠서 마커를 지우게
    강제됐다. `strict=False`였다면 조용히 통과해 "고쳐졌다"는 신호가 사라지고
    마커도 그대로 남아 다음 사람은 여전히 결함이 있다고 읽었을 것이다.

    아래 두 단언이 그 장치를 유지한다.
      (1) `False`가 다시 생기면 = 회귀 또는 새 결함 발견 → 실패
      (2) 그때 붙는 마커는 반드시 strict여야 한다

    `test_junction_bf.py:42`가 의도적으로 `strict=False`를 쓰는 것과 대비된다.
    그쪽은 "환경에 따라 갈리는 알려진 허용"이고, 이쪽은 "고쳐야 할 결함"이다.
    """
    unresolved = sorted(k for k, v in RESIDUAL_SEES_MAP.items()
                        if not v and k[1] not in NOT_YET_IMPLEMENTED)
    assert not unresolved, (
        f"잔차가 맵을 보지 않는 칸이 남아 있다: {unresolved} — "
        f"v28.61이 12칸을 해소했으므로 이것은 회귀이거나 새로 발견된 결함이다")

    # ⚠ `NOT_YET_IMPLEMENTED`는 **결함이 아니라 계획된 공백**이라 위 단언에서
    # 뺀다. 그렇다고 감시가 느슨해지지는 않는다 — 그 칸에도 strict xfail이
    # 붙으므로 구현되는 순간 XPASS로 실패해서 표를 갱신하게 만든다. 그리고
    # `test_not_yet_implemented_targets_are_actually_rejected`가 그 목록이
    # 낡았는지를 따로 본다.

    non_strict = []
    for param in _cross() + _cross(targets=_LOCAL_OBSERVED_TARGETS):
        for mark in (param.marks or ()):
            if mark.name == "xfail" and mark.kwargs.get("strict") is not True:
                non_strict.append((param.id, dict(mark.kwargs)))
    assert not non_strict, (
        f"strict=True가 아닌 결함 마커가 있다 — 고쳐도 신호가 안 뜬다: "
        f"{non_strict}")


# `solve_tandem`/`solve_single` 본문이 직접 조립하는 경로. `BRANCH_CASES`는 이
# 둘을 구분하지 않고 `_INLINE`으로 묶는다 — 이 파일은 프레임 이름까지 본다.
_INLINE_FRAMES = ("solve_tandem", "solve_single")


@pytest.mark.parametrize("case_id", sorted(ACTUAL_BRANCH))
def test_actual_branch_is_pinned(fest, geo_factory, case_id):
    """**실제** 도달 분기를 고정한다 — `_solve_single_bifacial` 포함.

    `BRANCH_CASES`는 인라인 두 경로를 `_INLINE` 하나로 묶으므로, 여기서는
    프레임 이름까지 구분해 더 촘촘하게 못 박는다.
    """
    case = _case_by_id()[case_id]
    obs = _cached(fest, geo_factory, case, None)
    assert obs.branch == ACTUAL_BRANCH[case_id], (
        f"{case[0]}: {ACTUAL_BRANCH[case_id]!r}로 가야 하는데 "
        f"{obs.branch!r}로 갔다")


@pytest.mark.parametrize("case_id", sorted(ACTUAL_BRANCH))
def test_actual_branch_agrees_with_base_lateral_table(case_id):
    """`BRANCH_CASES`의 기대 분기와 이 파일의 `ACTUAL_BRANCH`가 일치한다.

    2026-08-19에 `_NAMED_SOLVERS`가 `_solve_single_bifacial`을 빠뜨리고 있었고,
    그래서 `single_bifacial`이 `_INLINE`으로 판정됐다. **원본 표를 고쳤다** —
    이 테스트는 두 표가 다시 갈리는 것을 막는다.

    `_INLINE`인 케이스는 `BRANCH_CASES`가 인라인 경로를 구분하지 않기 때문이므로,
    이쪽이 인라인 프레임 중 하나이면 일치로 본다.
    """
    expected = _case_by_id()[case_id][5]
    actual = ACTUAL_BRANCH[case_id]
    if expected == _INLINE:
        assert actual in _INLINE_FRAMES, (
            f"{case_id}: BRANCH_CASES는 인라인이라는데 {actual!r}로 갔다 — "
            f"한쪽 표가 낡았다")
    else:
        assert actual == expected, (
            f"{case_id}: BRANCH_CASES={expected!r} vs "
            f"ACTUAL_BRANCH={actual!r} — 두 표가 갈렸다")


def test_named_solvers_covers_single_bifacial():
    """`_NAMED_SOLVERS`가 `_solve_single_bifacial`을 감시해야 한다.

    이것이 빠져 있던 것이 §2 발견의 직접 원인이다 — 감시하지 않는 분기는
    "도달했다"로 세어지지 않으므로 `BRANCH_CASES`의 커버리지 테스트가
    **통과해 버렸다.** 되돌아가지 않게 못 박는다.
    """
    from test_base_lateral import _NAMED_SOLVERS
    assert "_solve_single_bifacial" in _NAMED_SOLVERS, (
        "_NAMED_SOLVERS에서 _solve_single_bifacial이 다시 빠졌다 — "
        "docs/sessions/2026-08-19-spatial-branch-coverage-unit0.md §2")


# =============================================================================
# 3. T2 — 16칸(실은 24칸) 표를 테스트로
# =============================================================================

@pytest.mark.parametrize("case,target", _cross())
def test_residual_sees_spatial_map(fest, geo_factory, case, target):
    """**맵을 붙이면 수렴 전압장이 달라져야 한다.**

    달라지지 않으면 잔차가 맵을 보지 않은 것이다. 비교는 허용오차가 아니라
    **비트 동일 여부**로 한다 — 맵이 반영되면 반드시 어딘가는 비트가 달라지고,
    반영되지 않으면 완전히 같은 계산이라 정확히 0이다. 실측상 중간값이 없다.

    ⚠ `cell_current` 차이를 근거로 쓰지 않는다 — 파일 상단 참조.
    """
    base = _cached(fest, geo_factory, case, None)
    with_map = _cached(fest, geo_factory, case, target)
    assert base.V.shape == with_map.V.shape
    assert not np.array_equal(base.V, with_map.V), (
        f"{case[0]} / spatial_{target}: 맵을 붙였는데 수렴 전압장이 비트 동일이다 "
        f"— {base.branch}가 맵을 잔차에 반영하지 않았다. "
        f"(참고: ΔJ = {with_map.J - base.J:+.5e} mA/cm², "
        f"이 값이 0이 아닌 것은 cell_current가 맵을 무조건 적용하기 때문이며 "
        f"작동 근거가 못 된다)")


# 지역 다이오드 배열로 직접 관측할 수 있는 대상. `rc`만 빠진다 — 강성 조립
# (B 계층)이라 다이오드 배열에 나타나지 않는다. `rsh`는 j01/j02와 같은 A 계층
# 이므로 여기 들어간다.
_LOCAL_OBSERVED_TARGETS = tuple(t for t in TARGETS if TARGET_LOCALS[t])


@pytest.mark.parametrize("case,target", _cross(targets=_LOCAL_OBSERVED_TARGETS))
def test_branch_local_diode_arrays_carry_the_map(fest, geo_factory, case,
                                                 target):
    """분기 프레임의 다이오드 지역 배열이 맵을 싣고 있는가 — 직접 관측.

    전압장 판정과 같은 사실을 **파생 없이** 본다. `sys.settrace`로 잔차 분기가
    return할 때의 `J01_top_arr`/`_gen_t`/... 를 무맵 실행과 비트 비교한다.

    결함 분기에서는 해당 지역 변수가 **존재하지 않는 경우도 있다**(`_gen_t`는
    맵을 쓰는 경로에서만 만들어진다). 없는 것도 "안 실었다"이므로 같은 실패다.

    `rc`는 여기 없다 — 강성 조립(B 계층)이라 다이오드 배열에 나타나지 않는다.
    """
    base = _cached(fest, geo_factory, case, None)
    with_map = _cached(fest, geo_factory, case, target)
    names = TARGET_LOCALS[target]
    observed = [(fr, nm) for (fr, nm) in with_map.locals if nm in names]
    changed = [k for k in observed
               if k in base.locals
               and not np.array_equal(base.locals[k], with_map.locals[k])]
    assert changed, (
        f"{case[0]} / spatial_{target}: {with_map.branch} 프레임의 "
        f"{list(names)} 중 맵을 실은 것이 없다. "
        f"관측된 지역 변수={sorted(f'{a}.{b}' for a, b in observed) or '없음'}")


# =============================================================================
# 4. T1 — 우회 불가 검증 (이 작업의 핵심 산출물)
# =============================================================================
#
# 결함을 고치는 것보다 **다시 생기지 않게 하는 것**이 목적이다. 두 겹으로 둔다.
#   (1) 소스 검사  — 배열을 직접 조립하는 코드가 헬퍼 밖에 있으면 실패
#   (2) 런타임 계수 — 각 분기가 실제로 헬퍼를 부르는지 확인
# 소스 검사는 다른 문자열로 우회할 수 있고, 런타임 계수는 새 분기를 모른다.
# **둘 다 있어야** 빈틈이 없다.

# `dp.J01_top_pass * (1 - mf)` 계열. 공백 유무를 흡수한다(`_tab_current`는
# `DP.J01_top_pass*(1-mf)`로 붙여 쓴다).
INLINE_ASSEMBLY_RE = re.compile(
    r"J0\d_(?:top|single)_pass\s*\*\s*\(\s*1\s*-\s*mf\s*\)")

# census. **v28.61에서 13개 함수 34줄 → 1개 함수 4줄이 됐다.**
#
# 단위 0의 census가 남긴 기록 (v28.60 시점, 13개 함수 34줄):
#     solve_tandem 2 · _solve_tandem_junction 2 · _solve_tandem_junction_bf 2 ·
#     _solve_tandem_junction_bf_v29 2 · _solve_tandem_bifacial 2 ·
#     solve_single 2 · _solve_single_bifacial 2 · cell_current 4 ·
#     _phase_b_interlayer_diagnostics 2 · current_matching_diagnostics 2 ·
#     losses 6 · recomb_currents 4 · _tab_current 2
# 계획서 §1의 "소비 지점 7곳 + 진단 2곳"에 없던 4개(_solve_single_bifacial(잔차) ·
# losses · recomb_currents · _tab_current)를 그 census가 찾아냈고, v28.61은 13곳
# 전부를 배선했다.
#
# 헬퍼 안의 4줄은 mode별 top/single × J01/J02 조합이다. 지점이 늘면(=결함 재발
# 경로) 여기가 먼저 실패해서 갱신을 요구한다.
INLINE_ASSEMBLY_CENSUS = {
    "_diode_node_arrays": 4,
}


def _owner_functions(src):
    """줄 번호 → 그 줄을 담은 **가장 안쪽** 함수 이름."""
    tree = ast.parse(src)
    owner = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = node.end_lineno or node.lineno
            for ln in range(node.lineno, end + 1):
                cur = owner.get(ln)
                if cur is None or node.lineno > cur[1]:
                    owner[ln] = (node.name, node.lineno)
    return {ln: v[0] for ln, v in owner.items()}


def _inline_assembly_sites():
    """(줄번호, 함수명) 목록."""
    with open(SRC_PATH, encoding="utf-8") as fh:
        src = fh.read()
    owner = _owner_functions(src)
    return [(i, owner.get(i, "<module>"))
            for i, line in enumerate(src.splitlines(), 1)
            if INLINE_ASSEMBLY_RE.search(line)]


def test_inline_assembly_census_is_pinned():
    """다이오드 배열을 인라인으로 조립하는 지점의 **현재 목록**을 고정한다.

    오늘 초록불이다. 새 소비 지점이 늘거나(=결함 재발 경로) 단위 1이 지점을
    줄이면 여기가 먼저 실패해서 **census를 갱신하라고 알린다.** 아래
    `test_inline_assembly_only_inside_helper`가 최종 목표라면, 이쪽은 그 사이의
    진행을 눈에 보이게 하는 눈금이다.
    """
    sites = _inline_assembly_sites()
    got = {}
    for _, fn in sites:
        got[fn] = got.get(fn, 0) + 1
    assert got == INLINE_ASSEMBLY_CENSUS, (
        f"인라인 조립 지점이 바뀌었다.\n  현재={dict(sorted(got.items()))}"
        f"\n  고정={dict(sorted(INLINE_ASSEMBLY_CENSUS.items()))}\n"
        f"  줄 번호={[(ln, fn) for ln, fn in sites]}")


def test_helper_exists(fest):
    """중앙 헬퍼 (v28.61 신설). 단위 0 시점에는 없어서 xfail이었다."""
    assert hasattr(fest.FESTSolver, HELPER_NAME), (
        f"FESTSolver.{HELPER_NAME}가 없다 — v28.61이 만든 중앙 조립 지점이다")


def test_inline_assembly_only_inside_helper():
    """**T1-(1) 소스 검사.** 배열 조립은 헬퍼 안에서만 한다.

    이것이 이 작업의 핵심 산출물이다. 6번째 분기를 추가하는 사람이 배율 블록을
    복제하면 — 계획서가 금지한 바로 그 행위 — 이 테스트가 잡는다. 결함의 원인은
    "한 곳만 고쳤다"가 아니라 **"여러 곳에서 각자 조립할 수 있었다"** 이고,
    그 가능성 자체를 없애는 것이 목적이다.

    v28.61은 진단·GUI 소비 지점(`losses` · `recomb_currents` · `_tab_current`)
    까지 배선했다. 남겨 두면 `cell_current`가 가졌던 **자기모순 값** 문제가
    그것들에 그대로 남기 때문이다(맵 없는 전압장 + 맵 있는 다이오드 식).
    """
    offenders = [(ln, fn) for ln, fn in _inline_assembly_sites()
                 if fn != HELPER_NAME]
    assert not offenders, (
        f"{HELPER_NAME} 밖에서 다이오드 배열을 조립하는 곳이 "
        f"{len(offenders)}곳 있다: {offenders}")


@pytest.mark.parametrize("case_id", sorted(ACTUAL_BRANCH))
def test_every_branch_calls_the_helper(fest, geo_factory, monkeypatch,
                                       case_id):
    """**T1-(2) 런타임 계수.** 각 분기가 헬퍼를 최소 1회 부른다.

    소스 검사만 두면 다른 문자열로 같은 짓을 하는 경우를 놓친다. 이쪽은 새로
    생긴 분기라도 **실제로 풀어 보고** 판정하므로 문자열에 의존하지 않는다.
    """
    label, geo, rs_j, legacy, mode = _case_by_id()[case_id][:5]
    orig = getattr(fest.FESTSolver, HELPER_NAME)   # 없으면 AttributeError
    calls = []

    def _spy(self, *a, **kw):
        calls.append(1)
        return orig(self, *a, **kw)

    monkeypatch.setattr(fest.FESTSolver, HELPER_NAME, _spy)
    monkeypatch.setenv("FEST_LEGACY_LOCAL_MATCH", "1" if legacy else "")
    m = geo_factory[geo]()
    dp = _dp(fest, rs_j, mode, None)
    m.S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
              PARAMS["Rs"], VB, PARAMS["cf"], dp, mode)
    assert calls, f"{label}: {HELPER_NAME}를 한 번도 부르지 않았다"


# =============================================================================
# 5. T3 — 비트 동일
# =============================================================================
#
# 두 방향이다.
#   (a) 맵 없음  → 오늘과 비트 동일. 핀 2건이 이미 감시하지만, 여기서는 **분기
#       6개 전부**에서 "맵을 붙였다 떼면 원래대로"를 확인한다.
#   (b) Phase A / full_area + 맵 → **오늘 값과 비트 동일.** 현재 유일하게 올바른
#       탠덤 경로이므로, 단위 1의 리팩터가 값을 건드리지 않았다는 증거가 된다.

# 2026-08-19 캡처 (Windows AMD64 · python 3.14.3 · numpy 2.4.3 · scipy 1.17.1 ·
# numpy BLAS = scipy-openblas). 캡처 조건: conftest의 mono 지오메트리
# (2x2mm, 8F+1BB, axis_segments_override=36), PARAMS, Vb=0.5,
# FEST_LEGACY_LOCAL_MATCH=1, Rs_junction=0.0, _canonical_map.
#
# `sha256`은 `_voltage_field()`가 만든 float64 배열의 바이트다 — 비트 단위 증거.
# `J`는 사람이 읽을 진단용이며 판정에도 함께 쓴다(어긋났을 때 크기를 보려고).
PHASE_A_PINS = {
    None: (18.65028360819871,
           "89eefe56d46876f639d2af5f8d0be8d2ad6a93cec8ec6649576f4035da0b1ff3"),
    "j01": (18.650282520545172,
            "14e43ffc66b6855c010ccbf1d68dfc724c0700fe371de8a4439905749e771d15"),
    "j02": (18.650283608197928,
            "c4091e831f6c8a2eac98a1ffb9cef26d9133533d078a7a47aeb1c50c1e9e70fe"),
    "gen": (23.076602333684352,
            "e1a7a26739ba389d16be0619719cbad12a95eda2b8249385e33016d111bcf1c5"),
    "rc": (18.65024359585303,
           "1966dd5a8935072bc2d880721cc5f96536191e02713a5107ae236f3d726f92e8"),
}


@pytest.mark.parametrize("target", [None, "j01", "j02", "gen", "rc"],
                         ids=["nomap", "j01", "j02", "gen", "rc"])
def test_phase_a_full_area_values_are_pinned(fest, geo_factory, bit_pin_gate,
                                             target):
    """Phase A / full_area의 현재 값을 **수정 전에** 못 박는다.

    단위 1은 이 경로의 인라인 블록을 헬퍼 호출로 **교체만** 한다(계산은 같다).
    값이 1비트라도 움직이면 리팩터가 물리를 건드린 것이므로 되돌려야 한다.

    비트 핀이므로 다른 스택에서는 SuperLU/BLAS 차이만으로 깨진다 —
    `conftest.PINNED_STACK`과 다르면 이유를 붙여 xfail로 낮춘다(v28.46 규약).
    """
    if bit_pin_gate:
        pytest.xfail(f"비트 핀 캡처 스택과 다름 ({bit_pin_gate}) — "
                     f"SuperLU/BLAS 차이로 비트 재현 불가")
    case = _case_by_id()["phaseA_full_area"]
    obs = _cached(fest, geo_factory, case, target)
    exp_J, exp_sha = PHASE_A_PINS[target]
    assert obs.digest() == exp_sha, (
        f"Phase A / full_area (map={target}) 전압장이 캡처와 다르다.\n"
        f"  J: 캡처={exp_J!r}  현재={obs.J!r}  (Δ={obs.J - exp_J:+.6e})")
    assert obs.J == exp_J, (
        f"전압장은 같은데 cell_current가 다르다 — cell_current 쪽만 바뀌었다: "
        f"캡처={exp_J!r} 현재={obs.J!r}")


@pytest.mark.parametrize("case_id", sorted(ACTUAL_BRANCH))
@pytest.mark.parametrize("target", IMPLEMENTED_TARGETS)
def test_clearing_map_restores_bit_identical_result(fest, geo_factory,
                                                    case_id, target):
    """맵을 붙였다 **None으로 떼면** 무맵 결과와 비트 동일이다 — 6분기 전부.

    무맵 경로 비트 동일의 근거는 *"1을 곱한다"* 가 아니라 **"곱셈을 아예 하지
    않는다"** 이다(`clear_spatial_map` 독스트링). 단위 1이 헬퍼로 옮길 때 그
    `is not None` 가드를 유지해야 이 성질이 남는다 — 가드를 잃고 `make_uniform`
    같은 것으로 바꾸면 여기가 즉시 실패한다.

    `test_spatial_map.py`에 같은 성질의 테스트가 있으나 **기본 fixture 경로
    하나**만 돈다. 결함의 교훈이 정확히 그것이었으므로(단위를 덮는 것과 경로를
    덮는 것은 다르다) 여기서는 분기 6개 전부에서 확인한다.
    """
    case = _case_by_id()[case_id]
    label, geo, rs_j, legacy, mode = case[:5]
    base = _cached(fest, geo_factory, case, None)

    prev = os.environ.get("FEST_LEGACY_LOCAL_MATCH")
    os.environ["FEST_LEGACY_LOCAL_MATCH"] = "1" if legacy else ""
    try:
        m = geo_factory[geo]()
        dp = _dp(fest, rs_j, mode, target)
        fest.clear_spatial_map(dp, target)
        assert fest.get_spatial_map(dp, target) is None
        result = m.S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"],
                           PARAMS["rc"], PARAMS["Rs"], VB, PARAMS["cf"],
                           dp, mode)
    finally:
        if prev is None:
            os.environ.pop("FEST_LEGACY_LOCAL_MATCH", None)
        else:
            os.environ["FEST_LEGACY_LOCAL_MATCH"] = prev

    assert np.array_equal(_voltage_field(result), base.V), (
        f"{label}: spatial_{target}를 붙였다 떼었더니 무맵 결과와 달라졌다 — "
        f"'맵 없음 = 곱셈 없음' 가드가 깨졌다")


# =============================================================================
# 6. 함정 자체를 고정한다
# =============================================================================

def test_phase_b_gen_map_now_reaches_the_residual(fest, geo_factory):
    """**판정 함정이 사라졌다는 것 자체를 고정한다.**

    v28.60에서 이 조합(Phase B / full_area + `gen`)은 이랬다:

        수렴 전압장 Δ = 0 (비트 동일)   ·   ΔJ = +4.426 mA/cm²

    전압장은 1비트도 안 움직이는데 보고되는 전류는 4.4 mA/cm² 바뀌었다.
    맵 없는 전압장에 맵 있는 다이오드 식을 씌운 **자기모순 값**이었고, Δ ≠ 0이라
    겉보기에는 작동하는 것처럼 보였다 — 그래서 결함이 오래 남았다.

    v28.61 이후에는 **둘 다** 움직인다. 전압장이 움직이는 것이 잔차가 맵을 봤다는
    증거이고, 그것이 이 테스트의 단언이다.

    > 여기 남기는 말: **`ΔJ ≠ 0`을 작동 근거로 쓰지 말 것.** 그 조건은 고치기
    > 전에도 참이었다. 새 물성을 추가할 때 판정은 항상 수렴 전압장으로 한다.
    """
    case = _case_by_id()["phaseB_full_area"]
    no_map = _cached(fest, geo_factory, case, None)
    with_map = _cached(fest, geo_factory, case, "gen")

    assert not np.array_equal(no_map.V, with_map.V), (
        "Phase B / full_area가 gen 맵을 잔차에 반영하지 않는다 — "
        "v28.61의 결함 수정이 회귀했다")
    assert abs(with_map.J - no_map.J) > 1.0, (
        f"gen 맵이 걸렸는데 cell_current가 거의 변하지 않았다 "
        f"(ΔJ={with_map.J - no_map.J:+.5e}) — 전압장은 변했으므로 "
        f"cell_current 쪽 배선이 끊겼을 수 있다")
