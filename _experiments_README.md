# 루트 실험 산출물 — 실행 조건 기록

이 폴더(저장소 루트)의 `_*_results.csv` 파일들은 **일회성 분석 실행의 결과**다.
`scripts/opt_*.csv`(정규 스윕 결과)와 **조건이 다르므로 수치를 섞어 인용하면 안 된다.**

> **왜 이 문서가 있는가**: `_pitch_ext_results.csv`는 8BB/pitch 2.2 조합의 효율을
> **31.398 %** 로 적는데, 문서·메일에서 인용해 온 값은 **31.330 %** 다. 같은 설계점인데
> 숫자가 다르다. 이유는 메시가 아니라 **busbar 반사광 회수(recovery) 반영 여부**다.
> 조건을 적어두지 않으면 나중에 잘못 인용된다.

---

## 기준값과의 관계

`_recovery_sens_results.csv`의 `recovery=0.0, nbb=8` 행이 앵커다:

| 출처 | 조건 | efficiency |
|---|---|---|
| `scripts/opt_grid_m10_measured.csv` (정규 스윕) | recovery 없음 | `31.32996488165442` |
| `_recovery_sens_results.csv` `recovery=0.0, nbb=8` | recovery 없음 | `31.32996488165442` |
| `_recovery_sens_results.csv` `recovery=0.25, nbb=8` | recovery 25 % | `31.39820147706627` |
| `_pitch_ext_results.csv` `pitch=2.2, nbb=8` | recovery 25 % | `31.39820147706627` |

**두 값은 소수점 끝까지 일치한다.** 즉 세 파일은 같은 엔진·같은 메시로 돈 결과이고,
차이는 오직 recovery 반영 여부다.

**문서·논문에 인용할 기본값은 recovery 없는 `31.330 %` 다.** recovery는 회수광이 FEM
전류 재계산에 피드백되지 않는 사후 근사이며(`front_electrode/adapter.py` 모듈
docstring 참조), 값의 근거가 되는 실측이 아직 없다.

---

## 파일별 조건

### `_edgeopt_results.csv` — 엣지 마진에 따른 최적점 이동

- 생성: `_edgeopt.py` (이 저장소에 함께 있음 — 재현 가능)
- 셀 182 mm, finger 20 µm, busbar 0.20 mm, scenario `measured`
- 스윕: pitch [1.8, 2.2, 2.6] mm × busbar [6, 8, 10] × edge margin [0, 1.0] mm
- **메시: `axis_segments_override=40` — 매우 성긴 미리보기 수준**, `npts=6`
- recovery **0.25 사후 반영**
- ⚠ **효율의 절대값을 인용하지 말 것.** 성긴 메시라 정규 스윕과 다르다.
  이 파일의 쓸모는 **최적점이 어느 쪽으로 이동하는가**이다.

읽어낸 결론:

| edge margin | 최적 busbar | 최적 pitch | efficiency |
|---|---|---|---|
| 0 mm | **8BB** | 2.193 mm | 31.3919 |
| 1.0 mm | **10BB** | 2.6 mm | 31.087 |

엣지 마진이 붙으면 최적 busbar 개수가 **8 → 10으로 올라간다.** 이것이 v28.46
"엣지 마진 조건의 최적 설계 재확정(8BB→10BB)"의 근거다.
단 pitch는 이 실행이 [1.802, 2.193, 2.6] 세 점만 봤기 때문에 1.767이 후보에
없었다. 마진 1 mm의 확정 최적(pitch 1.767 / 10BB)은 정규 스윕
`scripts/opt_grid_m10_measured_edge1mm.csv`를 볼 것.

### `_pitch_ext_results.csv` — pitch 범위 확장

- 셀 182 mm, **풀 메시**(노드 80,781 ~ 83,915), busbar 8·10
- pitch를 3.0 mm까지 확장해 최적이 경계에 걸리는지 확인
- recovery **0.25 반영** (기준값 대비 +0.068 %abs)
- 생성 스크립트가 남아 있지 않다 — 이 CSV가 유일한 기록이다

읽어낸 결론: pitch 2.2~2.4에서 최고이고 2.6 이상에서 단조 감소한다. 즉 최적이
탐색 범위 경계에 걸려 있지 않다(runaway 아님).

### `_recovery_sens_results.csv` — recovery 계수 민감도

- 셀 182 mm, **풀 메시**, pitch 고정(n_fingers 82 = pitch 2.193), busbar 6·8·10·12
- recovery 0.0 / 0.25 / 0.37 세 수준
- `Eff_base` 열이 **recovery 미반영 원본값**이다 — 위 앵커 표의 근거
- 생성 스크립트가 남아 있지 않다

읽어낸 결론: recovery를 올리면 busbar 개수가 많은 쪽의 손해가 줄어 **최적 busbar가
위로 밀린다.** nbb 8과 10의 격차가 recovery 0에서 0.031 %abs인데 0.37에서
0.006 %abs로 좁혀진다. `adapter.py`가 주석 `[2-fix-d]`로 예고한 경향과 일치한다.

---

## 제외한 산출물

다음은 `.gitignore`에 넣었다.

| 파일 | 이유 |
|---|---|
| `GEDO_Results.csv` | 0 바이트. v28.20이 고친 "CSV 내보내기 0바이트 버그"의 잔재 |
| `_edgeopt_out.txt` | 콘솔 실행 로그(폰트 로딩 메시지 포함). CSV에 같은 내용이 있다 |
