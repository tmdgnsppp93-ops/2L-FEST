# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""형상 계수(shape_cf) 설명 노트가 인용하는 기하 헬퍼 회귀 테스트 (v28.52).

이 값들은 **GUI 설명 문구에만** 쓰인다. 그래서 이 파일이 지키는 것은 두 가지다:
 (a) 화면에 찍히는 숫자가 손계산과 맞는가 — 설명이 틀린 숫자를 말하면 안 된다.
 (b) 설명 전용이라는 경계가 유지되는가 — 솔버/손실 경로가 이 헬퍼를 쓰기
     시작하면 '엔진 미반영'이라는 화면 문구가 거짓이 된다.
"""
import math
import os
import re


def test_dome_cf_is_pi_over_4(fest):
    """반타원 단면적 (π/4)wh ÷ 외접 사각형 wh = π/4. 화면의 0.785 출처."""
    assert fest.SHAPE_CF_DOME == math.pi / 4.0
    assert round(fest.SHAPE_CF_DOME, 4) == 0.7854
    assert fest.SHAPE_CF_RECT == 1.0


def test_recapture_slope_threshold(fest):
    """유리 n=1.5: θc=41.81°, 필요한 표면 기울기는 그 절반인 20.9°."""
    a = fest.recapture_slope_threshold_deg(1.5)
    assert abs(a - math.degrees(math.asin(1 / 1.5)) / 2.0) < 1e-12
    assert abs(a - 20.905) < 0.01


def test_recapture_fraction_matches_closed_form(fest):
    """u_min = k/√(1+k²), k = tan(θc/2)/(2h/w) 를 독립 계산해 대조."""
    for w, h in [(50.0, 10.0), (65.0, 8.5), (40.0, 20.0), (120.0, 5.0)]:
        k = math.tan(math.asin(1 / 1.5) / 2.0) / (2.0 * h / w)
        expect = 1.0 - k / math.sqrt(1.0 + k * k)
        got = fest.dome_recapture_width_fraction(w, h)
        assert abs(got - expect) < 1e-12, (w, h, got, expect)


def test_default_before_finger_is_31_percent(fest):
    """BEFORE 기본 단면 50×10 µm에서 화면에 찍히는 값이 31%인지 고정."""
    frac = fest.dome_recapture_width_fraction(50.0, 10.0)
    assert abs(frac - 0.3094) < 5e-4
    assert f"{frac * 100:.0f}%" == "31%"


def test_flat_top_recaptures_nothing(fest):
    """완전 평탄면은 기울기 0 → 정반사가 수직으로 되돌아 나가 재포획 0%."""
    assert fest.dome_recapture_width_fraction(50.0, 0.0) == 0.0
    assert fest.dome_recapture_width_fraction(0.0, 10.0) == 0.0
    assert fest.dome_recapture_width_fraction(-1.0, 10.0) == 0.0


def test_recapture_is_monotonic_in_aspect_ratio(fest):
    """가파를수록(h/w↑) 조건을 만족하는 폭이 넓어진다 — 평탄화=회수 감소."""
    prev = -1.0
    for h in (1.0, 2.5, 5.0, 10.0, 20.0, 40.0):
        cur = fest.dome_recapture_width_fraction(50.0, h)
        assert cur > prev, h
        prev = cur
    assert 0.0 <= prev <= 1.0


def test_recovery_default_falls_back_without_front_electrode(fest):
    """지연 임포트가 실패해도 문서화된 0.25로 떨어진다(엔진 독립성 유지)."""
    assert fest._busbar_recovery_default() == 0.25


def test_note_header_fits_the_card(fest):
    """헤더 바 가용 폭은 250(카드) − 2×10(padx) = 230px뿐이다.

    v28.52의 EN 문구는 272px라 잘렸다(실측). 디스플레이 없이도 회귀를 막으려고
    실측 환산치(size 11 bold ≈ 7.2px/char, 한글 ≈ 11px/char)로 상한을 건다.
    """
    hdr = fest._TR['shape_note_hdr']
    en, kr = hdr['EN'], hdr['KR']
    assert len(en) * 7.2 <= 230, f"EN 헤더 {len(en)}자 ≈ {len(en)*7.2:.0f}px > 230"
    kr_px = sum(11.0 if ord(c) > 0x2000 else 7.2 for c in kr)
    assert kr_px <= 230, f"KR 헤더 ≈ {kr_px:.0f}px > 230"


def test_helpers_stay_gui_only(fest):
    """설명 전용 경계 — 솔버/손실 코드가 이 헬퍼를 호출하기 시작하면 실패한다.

    화면이 '엔진 미반영'이라고 말하므로, 호출처는 설명 텍스트를 만드는
    _refresh_shape_note / _draw_shape_sketches 와 정의부뿐이어야 한다.
    """
    src = open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "2L_FEST.py"), encoding="utf-8").read()
    # 헤더 changelog는 코드가 아니다 — 함수명을 서술한 문장이 호출로 잡히면
    # 다음 릴리스 노트를 쓸 때마다 이 테스트가 거짓으로 깨진다.
    src = src.split('Author: Seunghoon', 1)[1].split('"""', 1)[1]
    for name in ("dome_recapture_width_fraction", "recapture_slope_threshold_deg"):
        # 정의 1건 + 호출 1건(설명 문구 생성)만 허용
        uses = [m.start() for m in re.finditer(r"\b%s\s*\(" % name, src)]
        assert len(uses) == 2, f"{name}: 예상 밖 호출 {len(uses)}건 — 엔진 유입 의심"
    # 솔버 본문이 봉지 굴절률을 참조하지 않는지(광학 경로 오염 방지).
    # 슬라이스 끝은 헬퍼 정의 블록 바로 앞 — 정의부 자체는 당연히 참조한다.
    solver_body = src.split("class FESTSolver")[1].split(
        "# 형상 계수(shape_cf) 설명용 순수 기하 헬퍼")[0]
    assert "N_ENCAP_GLASS" not in solver_body
    assert "recapture" not in solver_body
