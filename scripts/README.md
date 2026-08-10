# scripts/ — 헤드리스 최적화 드라이버와 측정 기록

## 드라이버

| 파일 | 용도 |
|---|---|
| `optimize_m10.py` | M10 전면전극 최적화 (stage: fingers / busbars / grid). 병렬 워커, `--resume`, CSV 즉시 append |
| `rerun_baseline.py` | 속도개선 전후 비교용 baseline 재실행 |

## CSV — **재생성 가능하지만 보존한다**

전부 FEM 스윕 **출력**이라 원리상 재생성 가능하다. 그러나 다음 이유로 저장소에 남긴다.

- `docs/front_electrode_model_scope.md`가 인용하는 **수치의 근거**다. 지우면 문서의
  주장을 뒷받침할 원자료가 사라진다.
- 재생성 비용이 크다 — 풀 M10 1조합 ≈17분, 전체 합계 **10시간 이상**의 FEM 계산.
- 용량은 전부 합쳐 50 KB 남짓이라 저장 부담이 없다.

| 파일 | 내용 | 인용처 |
|---|---|---|
| `opt_fingers_full.csv` | Stage 1 (39mm 소셀) finger width × pitch | docs §5 |
| `opt_busbars_m10_measured.csv` | edge 0, busbar 스윕 (pressed ρ=4.22) | docs §6 |
| `opt_busbars_m10_measured_breakdown.csv` | 위와 같은 조건 + Pe/Pc 손실 분해 재생성 | docs §7 |
| `opt_busbars_m10_measured_edge1mm.csv` | edge 1.0mm, busbar 4~20BB | docs §7 |
| `opt_busbars_m10_default.csv` | 엔진 기본(as-printed) 시나리오 — **현재 결론에는 미사용**, 이력 보존 | — |
| `opt_grid_m10_measured.csv` | edge 0, pitch × busbar 결합 스윕 | docs §8 |
| `opt_grid_m10_measured_edge1mm.csv` | edge 1.0mm, pitch × busbar 결합 스윕 | docs §8 |
| `opt_grid_m10_ascured_vs_pressed.csv` | ρ_L 9 vs 4.22 (가압 효과 분리) | docs §9 |
| `rerun_baseline_result.csv` | 속도개선 회귀 baseline | — |

**컬럼 주의**: `efficiency`는 recovery OFF 기준이다. recovery 25% 반영값은
`efficiency_rec25` / `total_loss_rec25` 컬럼을 볼 것. `FF`/`Jsc`/`Voc`는 v28.48부터
기록되므로 그 이전 CSV에는 없다.
