# 작업 세션 기록 — 2026-08-19 야간: 우선순위 0 단위 1 (v28.61)

> 이 문서는 **결정과 근거의 기록**이다. 무엇을 했는지는 커밋 메시지에, 앞으로 무엇을
> 할지는 `docs/WORKLOG.md`와 계획서에 있다.
>
> 앞 세션: `docs/sessions/2026-08-19-spatial-branch-coverage-unit0.md`
> 진행 로그: `docs/sessions/2026-08-19-overnight-progress.md`
> 계획: `docs/superpowers/plans/2026-08-18-spatial-map-branch-coverage.md`

| | |
|---|---|
| **시작** | `40d4ea9` (단위 0) |
| **버전** | **v28.61** |
| **범위** | `_diode_node_arrays` 신설 + 소비 지점 13곳 배선 |
| **환경** | 집 데스크톱 (Win10 / AMD64 / scipy-openblas), 핀 스택 |
| **비트 핀** | **strict 2 passed** (3.3 s) |
| **Phase A 비트 동일** | 5조합 sha256·J값이 단위 0 캡처와 **정확히 일치** |
| **판정 파일** | `test_spatial_branch_coverage.py` **97 passed · 0 xfailed** |
| **전체 비-slow 회귀** | **423 passed · 2 deselected · 6 xfailed · 0 failed** (1671 s) |

> 회귀 수치가 단위 0 기준선과 정확히 대응한다: `391 + 32 = 423`,
> `38 − 32 = 6`. 즉 **늘어난 통과는 전부 단위 0의 xfail이 전환된 것**이고
> 기존 테스트 회귀는 0건이다. 남은 xfail 6건은 `test_junction_bf`의 Vb=0
> 잔차 평탄화(비-strict, 기존 항목)다. XPASS 0건.

---

## 0. 무엇을 고쳤나

`spatial_j01` / `spatial_j02` / `spatial_gen` 세 맵이 프로덕션 tandem 설정
**전부**에서 잔차에 미반영이던 결함을 해소했다. 원인은 `solve_tandem`이 배율 블록
(`v28.60`의 `:4932`)보다 **앞에서** 디스패치하는 것이었고, **기본 설정
(`Rs_junction = 5000`)이 결함 경로**였다.

결함 분기 5곳 — 단위 0이 실측으로 확정한 목록:

| 분기 | 설정 | 비고 |
|---|---|---|
| `_solve_tandem_junction` | Phase B / full_area | **기본 설정** |
| `_solve_tandem_junction_bf` | Phase B / bifacial | |
| `_solve_tandem_junction_bf_v29` | — | 죽은 경로 (도달 불가) |
| `_solve_tandem_bifacial` | Phase A / bifacial | |
| `_solve_single_bifacial` | 단일셀 / bifacial | **단위 0이 새로 찾아냈다** |

`RESIDUAL_SEES_MAP`의 `False` 12칸이 전부 `True`가 됐다.

---

## 1. 설계 — 왜 중앙화인가

계획서 §1의 판단을 그대로 따랐다. 분기마다 배율 블록을 복제하는 방식은 **금지**다.

> 결함의 원인은 *"한 곳만 고쳤다"* 가 아니라 **"여러 곳에서 각자 조립할 수
> 있었다"** 이고, 복제는 그 조건을 늘린다. 다음 사람이 6번째 분기를 추가할 때 같은
> 일이 다시 일어난다.

`FESTSolver._diode_node_arrays(dp, mode)` 하나가 다이오드 노드 배열을 조립하고,
**13개 소비 지점 전부가 이 메서드만 거친다.** 그러면 `cell_current` 주석이
주장하는 *"the same spatial multipliers the solver used"* 가 **구조적으로 참**이
된다 — 지금까지처럼 "그렇게 되어 있기를 바라는" 상태가 아니다.

### 계획서보다 넓어진 것 — 반환값

계획서의 스케치는 6-튜플이었다.

```
_diode_node_arrays(dp, mode='tandem')
    -> (J01_top_arr, J02_top_arr, _J01b, _J02b, _gen_t, _gen_b)
```

**`recomb_currents` 때문에 성분 4개를 더 반환한다.** 그 함수는 pass/metal 분해를
**보고 항목으로** 내보낸다(`pass_n1` / `met_n1` / `met_n2` / `pass_n2`). 결합된
배열로는 재현할 수 없다 — 함수의 존재 이유가 그 분해다.

그런데 성분을 더해서 결합값을 만들면 **비트가 깨진다**:

```
(a·m + b·m)  ≠  (a+b)·m        (부동소수점)
```

그래서 결합값과 성분을 **따로** 계산한다. 결합값은 v28.60의 연산 순서
(`(pass + metal)` 후 `* m`)를 그대로 지키고, 성분은 각각 `* m`한다. 둘의 합이
결합값과 다른 것은 **의도된 것**이며 헬퍼 독스트링에 근거를 적었다.

> 이것이 계획서를 그대로 실행하지 않고 멈춰서 판단한 지점이다. 6-튜플을 고수하면
> `recomb_currents`를 배선하려고 그 함수의 보고 항목을 합쳐야 했고, 그것은
> **단언을 약화시키는 것이 아니라 기능을 없애는 것**이었다.

### 반환 형식

`types.SimpleNamespace` (모듈 `import types`가 이미 있다). 10개 값을 튜플로 풀면
호출 지점마다 순서를 맞춰야 하고, 나중에 항목이 늘면 13곳을 다시 손대야 한다.

---

## 2. 비트 동일을 어떻게 지켰나

무맵 경로가 v28.60과 비트 동일해야 한다. 근거 네 가지를 헬퍼 독스트링에 적었다.

| # | 근거 |
|---|---|
| 1 | 맵이 `None`이면 곱셈을 **아예 하지 않는다**(`is not None` 가드). `make_uniform` 같은 1.0 배열로 대체하면 곱셈이 실행되어 이 근거가 사라진다 |
| 2 | 결합값은 v28.60의 연산 순서 그대로 `(pass + metal)` 후 `* m` |
| 3 | `J01b = dp.J01_bot * 1.0` — IEEE754에서 `x * 1.0 == x` (정확) |
| 4 | `gen_t`는 맵이 없으면 `illum_frac` **그 객체** |

### 실측 확인

Phase A / full_area는 v28.60에서 **유일하게 올바른 탠덤 경로**였다. 단위 0이 수정
전에 캡처해 둔 값과 대조했다.

| 맵 | `cell_current` | 전압장 sha256 (앞 16자) | 판정 |
|---|---|---|---|
| 없음 | 18.65028360819871 | `89eefe56d46876f6` | ✅ 동일 |
| `j01` | 18.650282520545172 | `14e43ffc66b6855c` | ✅ 동일 |
| `j02` | 18.650283608197928 | `c4091e831f6c8a2e` | ✅ 동일 |
| `gen` | 23.076602333684352 | `e1a7a26739ba389d` | ✅ 동일 |
| `rc` | 18.65024359585303 | `1966dd5a89350728` | ✅ 동일 |

**5조합 전부 비트 동일.** 리팩터가 계산을 건드리지 않았다는 증거다.
비트 핀 2건(`test_default_pin` · `test_legacy_pin`)도 strict로 통과했다 — 그쪽은
기본 설정(Phase B / full_area)이므로 **수정 대상 분기에서** 무맵 불변을 확인한
것이다.

---

## 3. gen 맵은 전면 항에만 곱한다

bifacial 분기들의 바닥 광전류는 이런 형태다.

```python
Jph_b_eff = (ilf + dp.bifacial_gain * self.rear_illum_frac) * dp.Jph_bot
```

`ilf`만 `gen_b`로 바꿨다. **후면 입사광에는 맵을 곱하지 않는다** — `gen` 맵은
전면 광학 비균일성의 기술이고, 후면은 별개 광원이다.

이것은 새 판단이 아니다. `cell_current`가 v28.16부터 쓰던 규약과 같다:

```python
Jph_eff = (_gen + dp.bifacial_gain * self.rear_illum_frac) * dp.Jph_single
```

즉 **이미 저장소 안에 있던 규약을 잔차로 확장한 것**이고, 새 물리를 만든 것이
아니다. 무맵에서 `gen_b is ilf`이므로 비트 동일도 유지된다.

---

## 4. 손대지 않은 것 두 개 — 근거

### (a) `_bf_v29`의 `Jph_b_eff`

```python
Jph_b_eff = dp.Jph_bot * (1 + dp.bifacial_gain)      # 스칼라, ilf 없음
```

다른 분기와 달리 **원래부터 `illum_frac`이 없다.** "전면 항"이 없으므로 `gen` 맵을
곱할 기준이 없다. 여기서 형태를 바꾸는 것은 **검증되지 않은 물리를 죽은 경로에
신설**하는 것이므로 하지 않았다 — v28.59가 `_bf_v29`에 벌크 평면을 넣지 않기로 한
판단과 같은 성질이다.

그 분기의 `J01_top_arr` / `J02_top_arr` / `_J01b` / `_J02b` / `gen_t`는 헬퍼로
배선했다. 나중에 배선될 때 결함이 되살아나지 않게 하려는 것이고, 그것은 **이미
있는 물리를 일관되게 적용**하는 것이다.

`test_v29_schur_branch_is_unreachable`이 이 분기가 계속 죽어 있음을 감시하므로,
누군가 배선하면 그 테스트가 먼저 실패해서 `Jph_b_eff` 판정을 함께 하라고 알린다.

### (b) `_tab_current`의 `VT_ = 0.02585`

GUI 패널이 모듈 `VT`와 **다른 값**을 쓴다. 통일하면 표시값이 바뀐다. 별건이므로
손대지 않았다. 다이오드 배열만 헬퍼로 배선했다.

### (c) 0D 해석 참조 함수

`solve_0d_tandem_iv` 계열(`:3920` 부근)은 `dp.J01_bot_pass` 등을 직접 읽고 자체
`metal_frac` **스칼라** 인자로 가중한다. 노드 배열이 아니라 **공간 균일 0D
교차검증 참조**이므로 소비 지점이 아니다. census 정규식이 잡지 않은 것이 맞다.

---

## 5. 남은 불일치 — 단위 2로 넘긴다

`losses`의 바닥 항은 헬퍼의 `J01b`/`J02b`/`gen_b`로 배선했다. 그러나 **바닥
서브셀의 pass/metal 가중**은 여전히 없다 — 헬퍼가 `dp.J01_bot`(= `J01_bot_pass`)만
쓰고, `J01_bot_metal`은 아무도 읽지 않는다. `DiodeParams` 주석(`:1986`)이

> 솔버에서 array weighting을 쓸 때는 `_bot_pass` / `_bot_metal`을 명시 참조 (Phase 1)

라고 적어 둔 것이 그 예고다. v28.61은 **v28.60의 동작을 그대로 보존**하는 것이
비트 동일 조건이므로 여기서 바꾸지 않았다. 별건으로 기록한다.

---

## 6. 테스트

`tests/test_spatial_branch_coverage.py`는 단위 0에서 만든 판정 파일이다. 코드는
그대로 두고 **데이터와 마커만** 갱신했다.

| 항목 | 단위 0 | 단위 1 |
|---|---|---|
| `RESIDUAL_SEES_MAP`의 `False` | 12 | **0** |
| `_cross()`가 붙이는 xfail | 24 | **0** (dict 기반이라 자동) |
| 헬퍼 부재 xfail | 8 | **0** (데코레이터 제거) |
| `INLINE_ASSEMBLY_CENSUS` | 13함수 34줄 | **1함수 4줄** |
| 결과 | 65 passed · 32 xfailed | **97 passed · 0 xfailed** |

`_cross()`의 마커가 `RESIDUAL_SEES_MAP`에서 파생되도록 짜 두었기 때문에, dict의
`False`를 `True`로 바꾸는 것만으로 24개 마커가 사라졌다. 단위 0에서 그렇게 만든
것이 여기서 값을 했다.

### 바뀐 테스트 두 개

- `test_every_defect_marker_is_strict` → `test_no_unresolved_defect_cells_remain`.
  결함 칸이 0개임을 단언하고, **다시 생기면** 그 마커가 strict여야 한다는 검사를
  유지한다.
- `test_cell_current_delta_is_not_evidence_of_working` →
  `test_phase_b_gen_map_now_reaches_the_residual`. 같은 조합(Phase B + `gen`)을
  **반전**해서 고정한다. v28.60에서는 전압장 Δ = 0인데 ΔJ = +4.426이었고, 이제
  둘 다 움직인다.

  > 단언을 약화시킨 것이 아니라 **사실이 바뀌어서 반전**한 것이다. 단위 0에서
  > 이 테스트에 *"단위 1이 고치면 갱신해야 한다"* 고 적어 둔 그대로다.
  > 남기는 말은 그대로다 — **`ΔJ ≠ 0`을 작동 근거로 쓰지 말 것.** 그 조건은
  > 고치기 전에도 참이었다.

---

## 7. 하지 않은 것

- **`docs/spatial_map_convention.md` §6을 "해소"로 갱신** — 계획서 단위 2의 일이다.
  이 세션의 지시 범위가 단위 1까지였으므로 넘긴다. §6은 지금 **낡은 상태**다
  (결함이 있다고 적혀 있다).
- **`docs/pro_feature_map_2026-08-14.md` #6을 "구현"으로 3차 개정** — 같은 이유.
- **바닥 서브셀 pass/metal 가중** — §5.
- **`Rsh` 5번째 대상 추가** — 계획서 §하지 않는 것 그대로 보류.
