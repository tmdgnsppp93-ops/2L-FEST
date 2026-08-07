"""front_electrode — M10 전면전극 최적 설계 부가 모듈.

기존 2L-FEST 계산 엔진(2L_FEST_..._wf_wired.py)을 **수정하지 않고** 감싸는
별도 패키지. Phase 1에서는 adapter(evaluate_existing_simulation)와 busbar
반사광 회수(recovery)만 제공한다. Optimizer(Phase 2), preset/UI(Phase 3)는
이후 단계에서 추가된다.

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
    SCENARIO_ENGINE_DEFAULT,
    optimize_fingers,
    optimize_grid,
    optimize_busbars,
    roundtrip_check,
    export_csv,
)
from .presets import PRESETS, MAINSTREAM_PRESETS, get_preset

__all__ = [
    "DEFAULT_BUSBAR_RECOVERY_FACTOR",
    "RECOVERY_IS_POST_PROCESS",
    "apply_recovery",
    "busbar_shading_breakdown",
    "evaluate_existing_simulation",
    "SCENARIO_MEASURED",
    "SCENARIO_ENGINE_DEFAULT",
    "optimize_fingers",
    "optimize_grid",
    "optimize_busbars",
    "roundtrip_check",
    "export_csv",
    "PRESETS",
    "MAINSTREAM_PRESETS",
    "get_preset",
]
