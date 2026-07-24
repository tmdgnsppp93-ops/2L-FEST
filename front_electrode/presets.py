"""front_electrode presets — M10 전면전극 탐색범위 (별도 데이터 파일).

지시서 §3a. UI/optimizer에 값을 하드코딩하지 않고 여기에 모아 둔다. 모든 범위는
UI에서 사용자가 수정 가능한 **초기값**이며, 출처/조사일을 각 항목에 그대로 기록한다.

출처(원문 확인):
  · ITRPV 15th edition full report, VDMA, May 2024 (Results 2023),
    Fig.32(finger width)/33(busbar)/51(Cu wire) — 공개 PDF 전문 확인 2026-07-21
  · ITRPV 16th edition official presentation, Dr. M. Fischer (ITRPV steering
    committee), PV CellTech Frankfurt 2025-03-11, p.14/17/23/27 — 원문 확인 2026-07-21
  · ⚠ 16판 수치는 공식 발표자료 기준. 16판 전체 보고서는 itrpv.vdma.org에서 무료
    다운로드(등록 필요) — 보고서 인용 시 명시할 것.
  · 조사: 1차 2026-07-16, ITRPV 원문 확인 2026-07-21.

배경 사실(전부 원문 확인):
  · n-type TOPCon 2025 시장 68%, PERC 18% (16판 p.14)
  · 0BB(busbar-less) 2034 시장 ~37% 전망 (15판 Fig.33) — M10_0BB_future 근거
  · TOPCon B-도핑 에미터 면저항 2025: homogeneous 157 / selective 167 Ω/□ →
    2035 185/200 Ω/□ (16판 p.17) — 확산 에미터형 셀 시뮬레이션 시 sheet R 참고
  · TOPCon M10/G12 웨이퍼 2025 표준 130µm, n-TOPCon 양산효율 2025 25.5% (16판 p.12/p.25)

근거를 찾지 못한 값(인쇄 MBB 버스바 폭, finger pitch)은 kind="engineering"으로
명확히 구분한다(임의 확정 아님).
"""

_SRC_15 = "ITRPV 15th ed. (VDMA, May 2024, Results 2023)"
_SRC_16 = "ITRPV 16th ed. presentation (Fischer, 2025-03-11)"

# 각 preset: 탐색범위(초기값) + 근거. finger/busbar는 dict로 range/center/kind/src 기록.
PRESETS = {
    "M10_MBB_2025": {
        "label": "M10 MBB 2025 (인쇄 버스바)",
        "cell_size_mm": (182.0, 182.0),          # M10 규격 고정
        "busbar_number": [9, 10, 11, 12],        # ≤12BB (15판 Fig.33: 2023 시장 62%)
        "busbar_number_src": f"{_SRC_15} Fig.33",
        "busbar_width_mm": {"range": [0.3, 0.8], "kind": "engineering",
                            "note": "인쇄 MBB 버스바 폭 — ITRPV 미제공(engineering range)"},
        "finger_width_um": {"range": [15, 30], "center": [22, 25],
                            "kind": "sourced", "src": f"{_SRC_15} Fig.32 / {_SRC_16} p.23"},
        "finger_pitch_mm": {"range": [1.0, 2.2], "kind": "engineering",
                            "note": "설계 탐색변수 — ITRPV는 pitch/핑거개수 미제공"},
    },
    "M10_SMBB_2025": {
        "label": "M10 SMBB 2025 (와이어)",
        "cell_size_mm": (182.0, 182.0),
        "busbar_number": [13, 16, 18, 20],       # 중심 16-18 (16판 p.23 "up to 18 BBs standard")
        "busbar_number_src": f"{_SRC_16} p.23; 상용 16BB M10 실존(Fly Solar/Flagsun, 2026-07-16 확인)",
        "busbar_width_mm": {"range": [0.20, 0.30], "kind": "sourced",
                            "src": f"SMBB Cu wire 유효폭: {_SRC_15} Fig.51 (Ø280→200µm) / {_SRC_16} p.27 (Ø260→200µm)"},
        "finger_width_um": {"range": [15, 30], "center": [22, 25],
                            "kind": "sourced", "src": f"{_SRC_15} Fig.32 / {_SRC_16} p.23"},
        "finger_pitch_mm": {"range": [1.0, 2.2], "kind": "engineering",
                            "note": "설계 탐색변수 — ITRPV 미제공"},
    },
    "M10_Custom": {
        "label": "M10 Custom (사용자 자유 입력)",
        "cell_size_mm": (182.0, 182.0),
        "busbar_number": [8, 12, 16, 20],
        "busbar_number_src": "사용자 정의 초기값",
        "busbar_width_mm": {"range": [0.2, 0.8], "kind": "engineering", "note": "사용자 조정"},
        "finger_width_um": {"range": [15, 40], "kind": "engineering", "note": "사용자 조정"},
        "finger_pitch_mm": {"range": [1.0, 2.5], "kind": "engineering", "note": "사용자 조정"},
    },
    # ⚠ 0BB는 mainstream preset과 섞지 말 것 — 별도 비교/미래 기술 전용.
    "M10_0BB_future": {
        "label": "M10 0BB future (busbar-less, 미래기술 전용)",
        "cell_size_mm": (182.0, 182.0),
        "busbar_number": [0],                    # busbar-less (wire interconnect)
        "busbar_number_src": f"0BB 2034 시장 ~37% 전망 ({_SRC_15} Fig.33)",
        "busbar_width_mm": {"range": [0.0, 0.0], "kind": "engineering", "note": "busbar 없음"},
        "finger_width_um": {"range": [15, 30], "kind": "sourced", "src": f"{_SRC_15} Fig.32"},
        "finger_pitch_mm": {"range": [1.0, 2.2], "kind": "engineering", "note": "설계 탐색변수"},
        "engine_note": "n_busbars=0은 현재 엔진의 H-pattern 집전(버스바 필요)과 맞지 않아 "
                       "직접 시뮬레이션 불가할 수 있음 — 와이어 인터커넥트 모델은 본 모델 범위 밖. "
                       "비교/문서 목적 preset.",
    },
}

# mainstream(주류) preset 목록 — 0BB는 제외(섞지 말 것).
MAINSTREAM_PRESETS = ["M10_MBB_2025", "M10_SMBB_2025", "M10_Custom"]


def get_preset(name):
    """이름으로 preset dict 반환(사본). 없으면 KeyError."""
    if name not in PRESETS:
        raise KeyError(f"unknown preset: {name} (가능: {list(PRESETS)})")
    import copy
    return copy.deepcopy(PRESETS[name])
