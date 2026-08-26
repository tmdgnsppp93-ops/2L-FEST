# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Pin test: BIFACIAL rear-plane path bit-preservation (3 branches × base on/off).

왜 이 파일이 필요한가
--------------------
저장소의 기존 절대값 비트 핀은 **전부 `full_area` mono 경로**다:

    tests/test_default_pin.py:19-37              (make_mono, full_area)
    tests/test_legacy_pin.py:19-37               (make_mono, full_area)
    tests/test_spatial_branch_coverage.py:882    (phaseA_full_area 케이스만)

그런데 `full_area`에서는 `_build`가 `else` 분기(`2L_FEST.py:5249-5252`,
`assemble_K(0.001)` 하드코딩)를 타므로 벌크 횡전도의 병렬 합성 줄
(`2L_FEST.py:5198-5202`)이 **실행조차 되지 않는다.** 즉 위 세 핀은 `Rs_base`
코드 경로를 한 줄도 지나가지 않는다 — bifacial 후면 평면 전체가 절대값
회귀 감시 밖에 있었다.

이 파일이 그 공백을 메운다. 대상은 후면이 실제 전도 평면인 3분기 전부다
(`tests/test_base_lateral.py`의 BRANCH_CASES 3·5·7):

    _solve_tandem_junction_bf   Phase B / bifacial   (2L_FEST.py:6246)
    _solve_tandem_bifacial      Phase A / bifacial   (2L_FEST.py:6877)
    _solve_single_bifacial      단일셀 / bifacial     (2L_FEST.py:6338 디스패치)

각 분기를 **`Rs_base = None`(off)과 `Rs_base = 50 Ω/sq`(on) 두 상태**로 캡처한다.

  - **off**: 향후 변경이 무벌크 경로를 건드리지 않았다는 회귀 감시.
            `2L_FEST.py:5199`의 `is not None` 가드가 사라지면 여기가 즉시 깨진다.
  - **on** : 벌크 횡전도를 **전압 무관 상수**로 처리하는 현재 모델(v28.59 규약
            `docs/base_lateral_convention.md` §1-2 β)의 기준선. 나중에 bias
            point별 `Rs_base(V_junction)` 갱신을 넣으면 on 값은 **반드시**
            움직이고 off 값은 **반드시** 그대로여야 한다. 그 두 조건을 동시에
            확인할 수 있는 것이 이 파일뿐이다.

⚠ 이 파일은 **엔진을 한 줄도 바꾸지 않고** 현재 값을 못 박기만 한다.

캡처 환경 (tests/conftest.py:50-64의 교훈 — 버전 3종만 적으면 다음 사람이 같은
실험을 반복하게 된다. OS·아키텍처·BLAS 백엔드까지 남긴다.)
------------------------------------------------------------------------------
    캡처일        2026-08-26
    OS            Windows-11-10.0.26100-SP0
    아키텍처      AMD64 (x86-64)
                  Intel64 Family 6 Model 151 Stepping 5, GenuineIntel (Alder Lake)
    python        3.14.3 (tags/v3.14.3:323c59a, Feb  3 2026) [MSC v.1944 64bit]
    numpy         2.4.3
    scipy         1.17.1
    numpy BLAS    scipy-openblas 0.3.31.dev
                  "OpenBLAS 0.3.31.dev USE64BITINT DYNAMIC_ARCH NO_AFFINITY
                   Haswell MAX_THREADS=24"
    numpy LAPACK  scipy-openblas 0.3.31.dev (동일 빌드)
    엔진 빌드     GEDOS v28.69 build f8a3d4c61883 (2026-08-21)
    지오메트리    conftest._bifacial_geo — 2×2 cm, 전면 8F+1BB, 후면 6F+1BB,
                  axis_segments_override=36 → N=5459 노드

    아키텍처(x86-64 vs aarch64)와 BLAS 백엔드(OpenBLAS vs Apple Accelerate)는
    부동소수점 누적 순서를 바꾸므로 상대 1e-7~1e-6이 뜨는 것이 정상이다.
    맥북에서 python·numpy·scipy를 일치시켜도 핀이 깨진 실증이 conftest에 있다.

스택이 다르면(conftest.PINNED_STACK 불일치) RTOL=1e-8은 SuperLU/BLAS 차이만으로
깨진다 → 실패 대신 **이유를 붙인 xfail**로 낮춘다(v28.46 규약,
test_default_pin.py와 동일). 핀 스택에서는 그대로 strict fail이라 회귀 감시는
유지된다.

재현 방법
--------
    pytest tests/test_bifacial_pin.py -q

값을 다시 캡처해야 하면 `_measure()`를 직접 부르면 된다 — 이 함수는 fixture를
쓰지 않으므로 pytest 밖에서도 그대로 돈다. **테스트가 재는 것과 캡처가 재는
것이 같은 코드**여야 하므로 별도 캡처 스크립트를 두지 않는다.
"""
import os

import pytest

# tests/test_default_pin.py:19 와 같은 solve 인자. 값이 갈리면 다른 핀 파일과의
# 비교가 깨진다.
PARAMS = dict(rm=3e-6, hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)
RTOL = 1e-8

# 벌크 횡전도 on 상태에서 쓸 면저항 [Ω/sq]. 기본 Rs_rear_tco=50과 같은 값이라
# 유효 면저항이 정확히 25(=50‖50)가 되어, 어긋났을 때 사람이 암산으로 확인할 수
# 있다(docs/base_lateral_convention.md §1-4의 병렬 합).
RS_BASE_ON = 50.0

# 후면이 실제 전도 평면인 3분기. `tests/test_base_lateral.py`의 BRANCH_CASES
# 3·5·7과 같은 설정이며, 그 파일의 test_dispatch_target_is_pinned가 "이 설정이
# 이 분기로 간다"를 이미 고정하고 있다. 여기서는 그 위에 **값**을 얹는다.
#
#   rs_junction : None이면 DiodeParams 기본값(5000)을 그대로 쓴다
#                 (test_default_pin이 "DEFAULT (Phase B) path"를 핀하는 것과 같은 취지).
#   legacy      : FEST_LEGACY_LOCAL_MATCH 환경변수
BRANCHES = {
    "tandem_junction_bf": dict(
        solver="_solve_tandem_junction_bf",
        mode="tandem", legacy=False, rs_junction=None,
    ),
    "tandem_bifacial": dict(
        solver="_solve_tandem_bifacial",
        mode="tandem", legacy=True, rs_junction=0.0,
    ),
    "single_bifacial": dict(
        solver="_solve_single_bifacial",
        mode="single", legacy=False, rs_junction=None,
    ),
}

# (분기, 벌크) → cell_current [mA/cm2] 3점 (Vb = 0, 0.85·Voc0, 0.95·Voc0).
# 벌크 키: "off" = Rs_base None, "on" = Rs_base 50.0 Ω/sq.
#
# ⚠ **tandem 분기의 점 0(Vb=0)은 벌크에 대해 구조적으로 둔감하다.** 캡처 중
#    확인한 사실이며(2026-08-26), 결함이 아니라 모델의 성질이다:
#      · tandem의 `cell_current`는 **상부셀** 전류를 돌려준다
#        (`2L_FEST.py:7498-7508`, 전류 정합이라 그것이 곧 셀 전류다).
#      · Phase B / Vb=0에서 `Vtop`은 메시 전체가 정확히 0이다(실측 span = 0).
#        그러면 `Jt = _gen·Jph_top − J01(e⁰−1) − J02(e⁰−1) − 0/Rsh = _gen·Jph_top`
#        이라 후면 평면이 식에서 사라진다.
#      · 벌크 자체는 정상 적용된다 — 같은 점에서 `_Kr`의 최대 원소가 정확히
#        2배(4.6739 → 9.3478 = 50‖50)이고 `Vr`이 max|Δ| 8.53e-04 V 움직인다.
#        보고되는 전류만 그 변화를 볼 수 없는 것이다.
#    그래서 `("tandem_junction_bf", "off")[0]`과 `..."on")[0]`은 **비트 동일**이다.
#    off 경로 감시로는 유효하지만 `Rs_base`에 대해서는 아무것도 말해 주지 않으므로,
#    벌크 감시는 점 1·2가 담당한다(test_base_on_actually_moves_the_pinned_values).
#
# 캡처: 2026-08-26, 위 "캡처 환경" 블록의 스택.
PINS = {
    ("tandem_junction_bf", "off"): [18.769380090090642,
                                    18.399534574923617,
                                    11.337050189098363],
    ("tandem_junction_bf", "on"): [18.769380090090642,
                                   18.409802106813615,
                                   11.651452502960243],
    ("tandem_bifacial", "off"): [18.76654343134871,
                                 18.39279625866821,
                                 11.831536817655973],
    ("tandem_bifacial", "on"): [18.766543346088568,
                                18.401662292725184,
                                12.15219029477223],
    ("single_bifacial", "off"): [22.53461519641728,
                                 21.49872947890967,
                                 13.248179654471448],
    ("single_bifacial", "on"): [22.535016854457545,
                                21.76631013822096,
                                13.994311827163381],
}

# 벌크 감시가 실제로 성립하는 점 인덱스. 위 주석의 이유로 점 0은 제외한다.
BASE_SENSITIVE_POINTS = (1, 2)


def _measure(fest, make_bifacial, branch_id, rs_base):
    """한 (분기, 벌크) 조합의 3점을 잰다. **fixture를 쓰지 않는다.**

    monkeypatch fixture 대신 try/finally로 직접 되돌리는 이유: 이 함수를 pytest
    밖(캡처 스크립트)에서도 그대로 부를 수 있어야 "캡처한 코드"와 "검증하는
    코드"가 같아진다. 둘이 갈리면 핀은 자기 자신만 확인하게 된다.

    솔버는 **매 호출 새로 만든다** — off와 on이 같은 솔버를 공유하면 off의
    warm-start가 on으로 새어 들어가 값이 호출 순서에 의존한다
    (tests/test_base_lateral.py:775 독스트링의 경고).

    Returns
    -------
    (Js, branches, Voc0)
        Js       : cell_current 3점 [mA/cm2]
        branches : 각 점에서 처음 불린 이름 있는 솔버 (분기 확인용)
        Voc0     : 바이어스 격자를 만든 기준 Voc [V]
    """
    cfg = BRANCHES[branch_id]

    prev = os.environ.get("FEST_LEGACY_LOCAL_MATCH")
    if cfg["legacy"]:
        os.environ["FEST_LEGACY_LOCAL_MATCH"] = "1"
    else:
        os.environ.pop("FEST_LEGACY_LOCAL_MATCH", None)

    name = cfg["solver"]
    orig = getattr(fest.FESTSolver, name)
    seen = []

    def _wrapper(self, *a, **kw):
        seen.append(name)
        return orig(self, *a, **kw)

    setattr(fest.FESTSolver, name, _wrapper)
    try:
        S = make_bifacial().S
        dp = fest.DiodeParams()
        if cfg["rs_junction"] is not None:
            dp.Rs_junction = cfg["rs_junction"]
        dp.Rs_base = rs_base

        if cfg["mode"] == "single":
            Voc0 = float(dp.expected_voc(mode="single"))
        else:
            Voc0 = float(dp.expected_voc()[2])

        Js = []
        branches = []
        for Vb in (0.0, 0.85 * Voc0, 0.95 * Voc0):
            seen.clear()
            res = S.solve(PARAMS["rm"], PARAMS["hf"], PARAMS["wf"], PARAMS["rc"],
                          PARAMS["Rs"], Vb, PARAMS["cf"], dp, cfg["mode"])
            Js.append(float(S.cell_current(res, dp)))
            branches.append(seen[0] if seen else None)
    finally:
        setattr(fest.FESTSolver, name, orig)
        if prev is None:
            os.environ.pop("FEST_LEGACY_LOCAL_MATCH", None)
        else:
            os.environ["FEST_LEGACY_LOCAL_MATCH"] = prev

    return Js, branches, Voc0


@pytest.mark.parametrize("base_key", ["off", "on"])
@pytest.mark.parametrize("branch_id", sorted(BRANCHES))
def test_bifacial_pin(fest, make_bifacial, bit_pin_gate, branch_id, base_key):
    """bifacial 3분기 × 벌크 on/off의 cell_current를 비트 단위로 고정한다."""
    if bit_pin_gate:
        pytest.xfail(f"비트 핀 캡처 스택과 다름 ({bit_pin_gate}) — "
                     "1e-8 비트 동일은 이 스택에서 성립하지 않는다(물리 회귀 아님)")

    pins = PINS[(branch_id, base_key)]
    rs_base = None if base_key == "off" else RS_BASE_ON

    Js, branches, Voc0 = _measure(fest, make_bifacial, branch_id, rs_base)

    expected_branch = BRANCHES[branch_id]["solver"]
    assert branches == [expected_branch] * 3, (
        f"{branch_id}: {expected_branch!r}로 가야 하는데 {branches!r}로 갔다 — "
        f"디스패치가 바뀌었으면 이 핀은 다른 코드를 재고 있다")

    if pins is None:
        pytest.fail(
            f"핀 미캡처 — PINS[({branch_id!r}, {base_key!r})] = {Js!r}"
            f"   (Voc0={Voc0!r})")

    assert len(pins) == 3
    for Vb_i, (J, pin) in enumerate(zip(Js, pins)):
        assert abs(J - pin) <= RTOL * abs(pin), (
            f"{branch_id}/{base_key} 점{Vb_i}: {J!r} vs pinned {pin!r} "
            f"(Δrel={(J - pin) / pin:+.3e})")


def test_base_on_actually_moves_the_pinned_values(bit_pin_gate):
    """off와 on의 핀이 **바이어스 점에서** 서로 달라야 한다.

    같으면 `Rs_base`가 그 분기에서 조용히 무시되고 있다는 뜻이고, 그러면 on 핀은
    아무것도 감시하지 못한다 — 이 저장소가 반복해서 거부해 온 실패 형태다
    (v28.43 · v28.54 · v28.57 · 그리고 v28.59의 full_area 거부 게이트).

    점 0(Vb=0)은 제외한다 — tandem에서 구조적으로 벌크에 둔감하다(PINS 위 주석).
    핀 값끼리만 비교하므로 solve를 돌리지 않는다.
    """
    for branch_id in sorted(BRANCHES):
        off = PINS[(branch_id, "off")]
        on = PINS[(branch_id, "on")]
        if off is None or on is None:
            pytest.skip("핀 미캡처")
        for i in BASE_SENSITIVE_POINTS:
            assert off[i] != on[i], (
                f"{branch_id} 점{i}: 벌크 on/off의 핀이 같다 — Rs_base가 이 "
                f"분기에서 결과를 바꾸지 않는다")


def test_base_effect_is_larger_at_higher_bias(bit_pin_gate):
    """벌크 효과가 **고전압에서 더 크다** — 현재 모델의 성질을 기록한다.

    상수 `Rs_base` 모델에서도 바이어스가 오르면 저항성 손실 비중이 커지므로
    |Δ|가 커진다. 나중에 `Rs_base(V_junction)`를 넣으면 이 격차가 **더** 벌어져야
    한다(Griddler 매뉴얼 p.49: 1 Sun +0.0099 %p vs 3.6 Suns +0.1056 %p, 약 10.6배;
    `docs/griddler_feature_map.md` §2.8-a). 여기서 방향이 뒤집히면 V-의존 도입이
    잘못된 것이다.
    """
    for branch_id in sorted(BRANCHES):
        off = PINS[(branch_id, "off")]
        on = PINS[(branch_id, "on")]
        if off is None or on is None:
            pytest.skip("핀 미캡처")
        d1 = abs(on[1] - off[1])
        d2 = abs(on[2] - off[2])
        assert d2 > d1, (
            f"{branch_id}: 벌크 효과가 고전압에서 더 작다 "
            f"(0.85·Voc에서 {d1:.6e}, 0.95·Voc에서 {d2:.6e})")


def test_off_pins_are_not_accidentally_shared_between_branches(bit_pin_gate):
    """3분기의 off 핀이 서로 달라야 한다 — 같으면 분기 설정이 겹친 것이다."""
    seen = {}
    for branch_id in sorted(BRANCHES):
        pins = PINS[(branch_id, "off")]
        if pins is None:
            pytest.skip("핀 미캡처")
        key = tuple(pins)
        assert key not in seen, (
            f"{branch_id}와 {seen[key]}의 off 핀이 같다 — 두 케이스가 같은 "
            f"설정으로 같은 분기를 돌고 있다")
        seen[key] = branch_id
