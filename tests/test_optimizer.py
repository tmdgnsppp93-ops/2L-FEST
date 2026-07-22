"""Phase 2 — optimizer 테스트 (작은 config로 headless 검증).

실제 M10 stage-2는 1조합 ≈17분이라 pytest에서 못 돌린다. optimizer 함수는
config 주도라 테스트는 작은 셀·소수 조합·coarse 메시로 수 초 내 검증한다.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from front_electrode import (  # noqa: E402
    optimize_fingers,
    roundtrip_check,
    export_csv,
    SCENARIO_MEASURED,
)

AX = 36
NPTS = 6


def test_optimize_fingers_sorted_and_best(fest, monkeypatch):
    """finger 스윕이 total_loss 오름차순 정렬 + best가 실제 최소인지."""
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_fingers(
        fest, cell_mm=20.0, finger_widths_um=[40.0, 80.0],
        finger_pitches_mm=[1.5, 2.5], busbar_number=2, busbar_width_mm=0.2,
        scenario=SCENARIO_MEASURED, axis_segments_override=AX, npts=NPTS)
    rs = opt["results"]
    assert len(rs) == 4
    losses = [r["results"]["total_loss"] for r in rs]
    assert losses == sorted(losses), "total_loss 오름차순 정렬이어야 함"
    assert opt["best"] is rs[0]
    assert opt["best"]["results"]["total_loss"] == min(losses)
    # 실제 실현된 정수 n_fingers / pitch가 기록됨
    for r in rs:
        assert isinstance(r["parameters"]["n_fingers"], int)
        assert r["parameters"]["finger_pitch_mm"] > 0
    # 시나리오 라벨(measured) 부착
    assert "measured" in opt["best"]["scenario_label"]


def test_roundtrip(fest, monkeypatch):
    """최적 조건을 직접 재입력 → 동일한 손실·효율(비트 동일)."""
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_fingers(
        fest, cell_mm=20.0, finger_widths_um=[50.0, 90.0],
        finger_pitches_mm=[1.8], busbar_number=2, busbar_width_mm=0.2,
        scenario=SCENARIO_MEASURED, axis_segments_override=AX, npts=NPTS)
    ok, re, best = roundtrip_check(
        fest, opt["best"], scenario=SCENARIO_MEASURED,
        axis_segments_override=AX, npts=NPTS)
    assert ok, "round-trip 재입력 결과가 최적 조합과 불일치"
    assert re["results"]["total_loss"] == best["results"]["total_loss"]
    assert re["results"]["efficiency"] == best["results"]["efficiency"]


def test_export_csv(fest, tmp_path, monkeypatch):
    """CSV export — 각 조합의 전체 입력 파라미터가 기록되는지."""
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_fingers(
        fest, cell_mm=20.0, finger_widths_um=[50.0], finger_pitches_mm=[1.5, 2.0],
        busbar_number=2, busbar_width_mm=0.2, scenario=SCENARIO_MEASURED,
        axis_segments_override=AX, npts=NPTS)
    path = os.path.join(str(tmp_path), "opt.csv")
    export_csv(opt, path)
    assert os.path.exists(path)
    with open(path, encoding="utf-8-sig") as fh:
        header = fh.readline()
    # 최적점을 Griddler로 재현할 수 있게 핵심 입력이 전부 있어야 함
    for col in ("n_fingers", "finger_pitch_mm", "finger_width_um",
                "busbar_number", "busbar_width_mm", "total_loss", "efficiency",
                "scenario_label"):
        assert col in header, f"CSV에 {col} 누락"
