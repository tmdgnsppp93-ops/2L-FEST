# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""front_electrode — M10 전면전극 최적 설계 부가 모듈.

기존 2L-FEST 계산 엔진(2L_FEST_..._wf_wired.py)을 **수정하지 않고** 감싸는
별도 패키지. 구성: adapter(엔진 호출 래퍼 + busbar 반사광 회수),
optimizer(grid search), presets(ITRPV 탐색범위), ui(최적화 창), i18n(한/영 문자열).

절대 원칙: 새 물리식/새 효율식을 만들지 않는다. 기존 엔진의 손실·효율 값을
그대로 사용하고, busbar recovery는 **busbar shading line-item에만** 적용하는
사후 보정이다(회수광은 전류 재계산에 피드백되지 않는 근사 — adapter.py 참조).
"""
from .adapter import (
    DEFAULT_BUSBAR_RECOVERY_FACTOR,
    RECOVERY_IS_POST_PROCESS,
    apply_recovery,
    busbar_shading_breakdown,
    evaluate_existing_simulation,
)
from .optimizer import (
    SCENARIO_MEASURED,
    SCENARIO_AS_CURED,
    SCENARIO_ENGINE_DEFAULT,
    optimize_fingers,
    optimize_grid,
    roundtrip_check,
    export_csv,
)
from .presets import PRESETS, MAINSTREAM_PRESETS, get_preset
from .i18n import (
    LANGUAGES,
    DEFAULT_LANGUAGE,
    T,
    get_language,
    set_language,
    label_for,
    missing_keys,
)

__all__ = [
    "DEFAULT_BUSBAR_RECOVERY_FACTOR",
    "RECOVERY_IS_POST_PROCESS",
    "apply_recovery",
    "busbar_shading_breakdown",
    "evaluate_existing_simulation",
    "SCENARIO_MEASURED",
    "SCENARIO_AS_CURED",
    "SCENARIO_ENGINE_DEFAULT",
    "optimize_fingers",
    "optimize_grid",
    "roundtrip_check",
    "export_csv",
    "PRESETS",
    "MAINSTREAM_PRESETS",
    "get_preset",
    "LANGUAGES",
    "DEFAULT_LANGUAGE",
    "T",
    "get_language",
    "set_language",
    "label_for",
    "missing_keys",
]
