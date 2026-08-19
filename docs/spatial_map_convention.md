# 공간 분포 맵 규약 — **확정** (2026-08-18)

> **성격**: 규범 문서. 여기 적힌 것이 2L-FEST의 공식 규약이며, 코드·테스트·GUI가
> 전부 이 문서를 따른다.
> **관련**: 계획 `docs/superpowers/plans/2026-08-17-spatial-map-io.md` 단위 3 ·
> 대조 절차 `docs/crosscheck/2026-08-18-spatial-map-griddler.md` (보류) ·
> 회귀 `tests/test_spatial_map.py`

> ## ✅ 사용 보류 해제 — 2026-08-19 (v28.61)
>
> **아래 2026-08-18 보류는 해제됐다.** `spatial_j01` / `spatial_j02` / `spatial_gen`
> 세 맵이 **모든 분기에서 잔차에 반영된다.** `_diode_node_arrays` 중앙화로 소비
> 지점 13곳이 같은 헬퍼를 거치게 했고, 판정 파일
> `tests/test_spatial_branch_coverage.py`가 **97 passed · 0 xfailed**다(결함 칸 12 → 0).
> 상세는 §6.
>
> 보류 기간에 산출된 값은 **여전히 신뢰할 수 없다** — v28.60 이전의 Phase B
> 결과에 맵을 걸었다면 다시 계산할 것.
>
> <details><summary>원래 보류 문구 (2026-08-18) — 기록 보존</summary>
>
> > ## ⛔ 사용 보류 — 2026-08-18
> >
> > **`spatial_j01` / `spatial_j02` / `spatial_gen` 세 맵을 tandem 해석에 사용하지 말 것.**
> > 기본 설정을 포함한 **모든 프로덕션 tandem 설정**에서 잔차에 반영되지 않으며,
> > 그 상태로 나오는 값은 **물리적으로 성립하지 않는 자기모순 값**이다(§6).
> > `spatial_rc`는 영향 없다. 단일셀(`mode='single'`)도 영향 없다.
> >
> > 이 규약 문서의 §1~§5(행 방향·격자 정렬·보간·절대값)는 **여전히 유효하다** —
> > 결함은 맵의 *해석*이 아니라 맵이 *어디에 곱해지는가*에 있다.
>
> </details>

---

## 1. 확정 사항

| # | 규약 | 확정 내용 |
|---|---|---|
| 1 | **행 방향** | `matrix[0]` = **`y = 0`** — 파일의 **첫 데이터 줄이 셀의 아래쪽** 경계다 |
| 2 | **격자 정렬** | **꼭짓점 정렬(vertex-aligned)** — `np.linspace(0, H, ny)` / `np.linspace(0, W, nx)`. 픽셀 중심(cell-centered)이 **아니다** |
| 3 | 열 방향 | `matrix[:, 0]` = `x = 0` (왼쪽 경계) |
| 4 | 보간 | 쌍선형(`RegularGridInterpolator`, `method='linear'`) |
| 5 | 경계 밖 | 노드 좌표를 `[0,W]×[0,H]`로 **clip** 후 조회 — 외삽 없음, 경계값을 받는다 |
| 6 | 값 | **절대값**. txt/csv의 수가 그대로 배율이다 (정규화 없음) |

**요약 한 줄**: *첫 줄이 아래, 첫 열이 왼쪽, 모서리 값이 셀 모서리에 정확히 놓인다.*

### 그림으로

4×4 행렬이 30 × 30 mm 셀에 놓이는 방식 (`docs/crosscheck/spatial_4x4.txt`):

```
y=30mm ┤ 3.0   1.0   1.0   9.0     ← matrix[3]  (파일의 마지막 데이터 줄)
       │
y=20mm ┤ 1.0   1.0   1.0   1.0     ← matrix[2]
       │
y=10mm ┤ 1.0   1.0   1.0   1.0     ← matrix[1]
       │
y= 0mm ┤ 2.0   7.0   1.0   5.0     ← matrix[0]  (파일의 첫 데이터 줄)
       └────┬─────┬─────┬─────┬──
          x=0    10    20    30 mm
```

- 격자 간격은 `H/(ny-1)` = 10 mm — **`H/ny` = 7.5 mm가 아니다**(그것이 픽셀 중심이다)
- 네 모서리 값(2 / 5 / 3 / 9)이 셀의 네 꼭짓점에 **정확히** 놓인다
- **파일을 텍스트 편집기로 보면 위아래가 뒤집혀 보인다** — 사람은 첫 줄을 위로
  읽지만 여기서는 아래다. GUI 미리보기가 `origin='lower'`로 그리는 이유다

---

## 2. 왜 이렇게 확정했나

### 근거: **Griddler 대조 불가 → 자체 규약 채택**

원래 계획은 같은 파일을 Griddler 2.5에 넣어 대조한 뒤 확정하는 것이었다
(계획 단위 3). **그 대조는 할 수 없다.**

| 근거 | 내용 |
|---|---|
| 벤더 비교표 | *"Input spatial property distributions as txt or TIFF"* → **Free = NO** |
| 매뉴얼 §3.1 | Nonuniform cell parameters = **PRO 전용** |
| 실물 확인 | 무료판 화면에 **진입점 자체가 없다** |

우회로도 없다 — 손 입력은 비균일 분포를 만들지 못하고, DXF import는 금속 패턴이지
물성 분포가 아니다. 자세한 내용은
`docs/crosscheck/2026-08-18-spatial-map-griddler.md` §7.

### 그래서 왜 "미판정"이 아니라 "확정"인가

미판정으로 두면 이후 모든 단위가 *"규약이 아직 안 정해졌다"*를 이유로 멈춘다. 실제로
확정을 미룰 이유도 없다 — **이것은 이미 엔진이 하고 있는 동작이고**
(`SpatialMap.evaluate()`의 `csv` 분기), 단위 0의 특성화 테스트 30건이 그 동작을
이미 고정해 두었다. 확정 선언은 새 동작을 만드는 것이 아니라 **이미 있는 동작을
공식 규약으로 승격**하는 것이다.

`np.linspace(0, H, ny)`가 주는 꼭짓점 정렬은 그 자체로 합리적이기도 하다 — 파일의
값이 셀 경계에서 그대로 재현되므로, 사용자가 "모서리를 2.0으로 하고 싶다"고 하면
그대로 2.0이 된다. 픽셀 중심이면 모서리에서 외삽 또는 clip이 개입해 값이 흐려진다.

---

## 3. 확정이 뒤집힐 경우의 처리

PRO를 확보해 대조한 결과가 이 규약과 **어긋나면**:

> **보정은 `load_spatial_map_txt` 안에서만 한다. `SpatialMap.evaluate()`는 어떤
> 경우에도 건드리지 않는다.**

| 대조 결과 | 조치 | 바뀌는 코드 |
|---|---|---|
| 상하 반전 | 로더에서 `matrix[::-1]` | `load_spatial_map_txt` 내부만 |
| 픽셀 중심 | 로더에서 정렬 보정 | `load_spatial_map_txt` 내부만 |

**이유**: `evaluate()`를 고치면 단위 0의 특성화 테스트 30건이 깨지는데, **그 테스트가
바로 회귀 감시 기준이다.** 기준을 같이 움직이면 무엇이 회귀인지 판정할 수 없게 된다.
로더 안에서 보정하면 엔진 규약은 그대로 남고, 파일 → 행렬 변환 지점 한 곳만 바뀐다.

또 하나: `evaluate()`는 파일뿐 아니라 **메모리에서 직접 만든 행렬**(스크립트·
`_audit.py`)도 받는다. 거기에 파일 포맷 보정을 섞으면 두 입력 경로의 의미가
달라진다. 보정은 파일 경로에만 속한다.

---

## 4. 코드·테스트 대응

| 규약 | 구현 | 회귀 |
|---|---|---|
| 행 방향 | `SpatialMap.evaluate()` csv 분기 `y_axis = linspace(0, H_cm, ny_)` | `test_csv_row_zero_is_y_zero` · `test_loader_first_row_is_y_zero` |
| 꼭짓점 정렬 | 같은 줄 (`linspace`의 끝점 포함) | `test_csv_corners_are_vertex_aligned` |
| 외삽 없음 | `np.clip(y, 0, H_cm)` | `test_csv_clips_outside_points_no_extrapolation` |
| 절대값 | 로더가 값을 건드리지 않음 | `test_loader_keeps_absolute_values_no_normalization` |
| **기준선 8점** | — | `test_crosscheck_4x4_matches_documented_expectations` |

마지막 항목이 이 문서와 대조 절차서 §2의 숫자를 **코드에 묶는다.** PRO 대조 때
우리 쪽 기준선이 되는 값이므로, 그때까지 코드가 바뀌어 문서와 어긋나면 대조 자체가
무의미해진다.

---

## 5. 이 규약이 적용되지 않는 것

- **이미지 입력(2단계)** — 규약이 반대다(**상대값**, 평균 1 정규화). `load_spatial_map_txt`에
  확장자 분기를 넣지 않고 **별도 함수**로 둔다. 격자 정렬·행 방향은 같지만, 이미지는
  좌표계가 위에서 아래로 내려가는 것이 관례라 **뒤집기가 필요할 수 있다** — 그
  판단은 2단계에서 한다
- **면저항(`Rs`) 공간 분포** — 주입 지점이 강성행렬 조립 단계라 성격이 다르다.
  대상 물성은 `j01` / `j02` / `gen` / `rc` 4종으로 확정(계획 §대상 물성)

---

## 6. 해소된 결함 — 분기 누락 (2026-08-18 발견 → 2026-08-19 해소, v28.61)

> ## ✅ 해소 (2026-08-19, v28.61)
>
> | | |
> |---|---|
> | **수정** | `FESTSolver._diode_node_arrays(dp, mode)` 신설 — 다이오드 노드 배열을 조립하는 **유일한** 경로 |
> | **배선** | 소비 지점 **13개 함수 34줄** 전부(계획서가 예상한 9곳이 아니었다) |
> | **결함 칸** | **12 → 0.** `RESIDUAL_SEES_MAP`의 `False`가 전부 `True`가 됐다 |
> | **판정 파일** | `tests/test_spatial_branch_coverage.py` — **97 passed · 0 xfailed** (단위 0에서 65 passed · 32 xfailed) |
> | **비트 동일** | Phase A / full_area 5조합(무맵·j01·j02·gen·rc)이 단위 0 캡처와 sha256·J값까지 **정확히 일치** |
> | **비트 핀** | `test_default_pin` · `test_legacy_pin` **strict 2 passed** (핀 스택) |
> | **전체 회귀** | 423 passed · 2 deselected · 6 xfailed · 0 failed. 늘어난 통과는 **전부 단위 0의 xfail 전환**(391+32 = 423, 38−32 = 6) |
> | 기록 | `docs/sessions/2026-08-19-spatial-branch-coverage-unit0.md` · `…-unit1.md` · 계획 `docs/superpowers/plans/2026-08-18-spatial-map-branch-coverage.md` |
>
> **재발 방지가 핵심 산출물이다.** 두 겹으로 막는다 —
> (1) **소스 검사**: `_diode_node_arrays` 본문 **밖**에서 배율 패턴이 나타나면 실패
> (`INLINE_ASSEMBLY_CENSUS`가 13함수 34줄 → **1함수 4줄**로 줄었다),
> (2) **런타임 계수**: 각 분기를 실제로 풀며 헬퍼 호출을 세어 **분기당 최소 1회**를
> 확인. 소스 검사는 우회 가능하고 런타임 계수는 새 분기를 모르므로 **둘 다** 둔다.
>
> **아래 §6 본문은 지우지 않는다.** 무엇이 왜 결함이었는지, 판정 함정이 무엇이었는지가
> 남아야 같은 일이 반복되지 않는다. 시제만 과거로 읽을 것.

> **[당시 기록] 근거: 호출 경로 (2026-08-18 확정).** 프로브 실측은 나오는 대로 이 절에 추가한다.
> 수정 계획: `docs/superpowers/plans/` (작성 중).

### 무엇이 잘못됐나 (v28.60 이전)

`spatial_j01` · `spatial_j02` · `spatial_gen` 세 맵이 **프로덕션 tandem 설정
전부에서 잔차에 반영되지 않는다.** `spatial_rc` 하나만 정상이다.

`solve_tandem`이 배율을 계산하는 블록(`2L_FEST.py:4932`)보다 **앞에서** 다른
솔버로 빠져나가기 때문이다:

```
solve_tandem(:4828)
  :4837  _build(...)                      ← rc 배율(:4592). 항상 실행된다.
  :4857  return _solve_tandem_junction_bf    ┐ warm-start
  :4867  _build(...)  (연속법 램프 매 스텝)   │ 램프도 _build를 재호출하므로
  :4875  return _solve_tandem_junction_bf    ┘ rc는 램프 경로에서도 유효
  :4886  return _solve_tandem_junction_bf  ← Phase B + bifacial
  :4889  return _solve_tandem_junction     ← Phase B + full_area
  :4894  return _solve_tandem_bifacial     ← Phase A + bifacial
  :4932  _m_j01/_m_j02/_m_gen = _spatial_mult(...)   ← 여기 도달해야 적용
```

네 분기는 `J01_top_arr`를 스칼라로만 만든다(`:5224` · `:5595` · `:5914` · `:6191`) —
`_spatial_mult` 호출이 아예 없다.

### 24칸 표 (2026-08-19 실측으로 정정)

> **이 표는 원래 16칸이었고 "단일셀은 4종 모두 정상"으로 끝났다. 그것이 틀렸다.**
> 단위 0의 실측이 **`_solve_single_bifacial`이라는 5번째 결함 분기**를 찾아냈다.
> 원본 서술은 아래 §"정정 전 서술"에 보존한다.
>
> 근거: `tests/test_spatial_branch_coverage.py`의 `RESIDUAL_SEES_MAP` ·
> `docs/sessions/2026-08-19-spatial-branch-coverage-unit0.md` §2.
> 판정은 **수렴 전압장 비트 비교**로 했다 — `cell_current`가 아니다(아래 함정 절).

| 조합 | 도달 분기 | `rc` | `j01` | `j02` | `gen` |
|---|---|:---:|:---:|:---:|:---:|
| Phase A / full_area | 인라인 `solve_tandem :4932` | ✅ | ✅ | ✅ | ✅ |
| **Phase B / full_area** | `_solve_tandem_junction` | ✅ | ❌ | ❌ | ❌ |
| **Phase B / bifacial** | `_solve_tandem_junction_bf` | ✅ | ❌ | ❌ | ❌ |
| **Phase A / bifacial** | `_solve_tandem_bifacial` | ✅ | ❌ | ❌ | ❌ |
| 단일셀 / full_area | 인라인 `solve_single :6431` | ✅ | ✅ | ✅ | ✅ |
| **단일셀 / bifacial** | **`_solve_single_bifacial` `:6513`** | ✅ | ❌ | ❌ | ❌ |

**결함 칸은 9개가 아니라 12개다.**

#### 같은 표, v28.61 이후 (현재)

| 조합 | 도달 분기 | `rc` | `j01` | `j02` | `gen` |
|---|---|:---:|:---:|:---:|:---:|
| Phase A / full_area | 인라인 → `_diode_node_arrays` | ✅ | ✅ | ✅ | ✅ |
| **Phase B / full_area** (기본 설정) | `_solve_tandem_junction` | ✅ | ✅ | ✅ | ✅ |
| **Phase B / bifacial** | `_solve_tandem_junction_bf` | ✅ | ✅ | ✅ | ✅ |
| **Phase A / bifacial** | `_solve_tandem_bifacial` | ✅ | ✅ | ✅ | ✅ |
| 단일셀 / full_area | 인라인 → `_diode_node_arrays` | ✅ | ✅ | ✅ | ✅ |
| **단일셀 / bifacial** | `_solve_single_bifacial` | ✅ | ✅ | ✅ | ✅ |

**24칸 전부 ✅.** 근거는 같은 파일의 같은 dict(`RESIDUAL_SEES_MAP`)이고, 판정
방식도 그대로 **수렴 전압장 비트 비교**다 — 기준을 바꾸지 않았다.

죽은 경로 `_solve_tandem_junction_bf_v29`도 같은 헬퍼를 쓰게 해 두었다(도달
불가라 표에는 없다). 나중에 배선될 때 결함이 되살아나지 않게 하려는 것이다.

#### 정정 전 서술 (2026-08-18)

> 단일셀(`solve_single` `:6431`)은 4종 모두 정상이다.

`solve_single`은 rear가 `bifacial`/`patterned`이면 `:6396`에서
`_solve_single_bifacial`로 **빠져나간다.** 그쪽은 `_spatial_mult` 호출이 없고
`:6546-6547`에서 인라인으로 조립한다 — 탠덤 네 분기와 같은 구조의 결함이다.
`solve_single` 본문만 읽으면 정상으로 보이는 것이 원인이었다.

> **바로 위 "`J01_top_arr`를 스칼라로만 만든다"도 틀렸다.** `mf`(`metal_frac`)가
> 이미 노드 길이 배열이라 **결함 분기에서도 `ndarray[N]`이다.** 스칼라인 것은
> `J01_top_pass` 같은 *계수*다. dtype·shape로는 결함이 보이지 않으므로 관측은
> **무맵/유맵 실행의 같은 지역 변수 비트 비교**로 해야 한다(계획서 단위 0의
> 관측 지표도 이 때문에 교체됐다).

#### 왜 테스트가 이 분기를 못 봤나

`tests/test_base_lateral.py`의 `_NAMED_SOLVERS`에 `_solve_single_bifacial`이
없어서 `single_bifacial` 케이스가 `_INLINE`으로 판정됐고,
`test_case_table_covers_every_reachable_named_solver`도 그 분기를 세지 않아
**통과했다.** 감시하지 않는 분기는 "도달했다"로 카운트되지 않는다.
2026-08-19에 그 원본 표를 고쳤다.

**벌크 횡전도(`Rs_base`)에는 같은 누락이 없었다** — `_build`(`:4396-4488`) 안의
강성 조립이라 디스패치보다 앞이고, `spatial_rc`가 무사한 것과 같은 구조적 이유로
모든 분기에 적용된다. 즉 **표가 틀렸을 때 실제로 다치는 것은 디스패치 뒤(A 계층)
뿐이다.** 새 물성을 추가할 때 먼저 물어야 할 것은 "표를 통과시켰나"가 아니라
**"이것이 `_build` 앞인가 뒤인가"** 다.

`rc`가 무사한 이유는 **계층이 다르기 때문**이다 — `rc`는 `_build` 안에서 `_Gc`를
고치는 강성 조립(B 계층)이고, `_build`는 디스패치보다 **앞**이라 모든 경로에서
반드시 실행된다. 연속법 램프(`:4867`)도 스텝마다 `_build`를 다시 부른다.
나머지 3종은 노드 잔차(A 계층)라 디스패치 **뒤**에 있다.

### 기본 설정이 결함 경로였다 (v28.61에서 해소)

`DiodeParams.Rs_junction = 5000.0`(`:1916`)이 **클래스 기본값**이고, `Rs_j ≤ 0`은
`RS_JUNCTION_MIN = 0.1`로 클램프된다(`:4436-4440`). 즉 **Phase A는
`FEST_LEGACY_LOCAL_MATCH` 환경변수로만 도달 가능한 레거시 경로**다.

표에서 ✅가 붙은 유일한 tandem 칸이 그 레거시 경로다. **아무것도 건드리지 않고
GUI에서 맵을 불러오면 결함 경로로 간다.**

### 조용한 무효가 아니라 **자기모순 값**이었다 ⚠

> **v28.61에서 이 자기모순은 사라졌다.** `cell_current`도 `_diode_node_arrays`를
> 거치므로, 아래 주석이 주장하는 *"the same spatial multipliers the solver used"* 가
> 이제 **구조적으로 참**이다 — "그렇게 되어 있기를 바라는" 상태가 아니다.
> **아래의 판정 함정 경고는 그대로 유효하다** — `ΔJ ≠ 0`은 고치기 전에도 참이었으므로
> 앞으로도 작동 근거로 쓰면 안 된다.

`cell_current`(`:6717-6727`)는 맵을 **무조건** 적용한다. 주석까지 이렇게 적혀 있다:

> *"the same spatial multipliers the solver used must be applied here"*

Phase B에서 이 전제가 **거짓**이다. 그 결과 보고되는 J는

**맵이 안 걸린 전압장**에서 수렴시킨 뒤 → **맵이 걸린 다이오드 식**으로 재계산

한 혼합물이다. 전압장과 전류식이 서로 다른 모델을 쓰므로 **어느 물리에도
대응하지 않는 값**이다.

그래서 **Δ ≠ 0이 나온다.** 맵을 걸면 숫자가 바뀌므로 겉보기에는 작동하는 것처럼
보인다 — 이것이 이 결함이 오래 남은 이유다.

> **판정 함정**: `Rs_base`(v28.60)와 **방향이 반대**다. 저쪽은 Δ = 0이라 놓쳤고,
> 이쪽은 Δ ≠ 0이라 놓쳤다. 그리고 이쪽이 더 나쁘다 — 조용한 무효는 값이 옛것일
> 뿐이지만, 이건 성립하지 않는 값이다.
>
> 따라서 **`cell_current` 차이를 작동 근거로 쓰면 안 된다.** 판정은 수렴 전압장
> 자체나 잔차 지역변수(`J01_top_arr`가 배열인가 스칼라인가) 관측으로 한다.

### 왜 111개 테스트가 못 잡았나 — 단위를 덮는 것과 경로를 덮는 것은 다르다

`tests/test_spatial_map.py`는 111건을 수집하는데, 그 안에 `bifacial` ·
`Rs_junction` · `junction` 문자열이 **0건**이다. 111건은

- `SpatialMap.evaluate()` 자체(모드별 수식, FEM 없음)
- 로더 `load_spatial_map_txt`(파싱·검증)
- 레지스트리 · 캐시 무효화 · GUI 배선
- FEM을 도는 것들은 **전부 기본 fixture 경로**

를 덮는다. **맵이 곱해지는 지점이 설정에 따라 여러 개라는 사실 자체가 시야에
없었다.** 각 단위는 정확히 검증됐고 전부 통과했다 — 통과한 것이 옳았다. 덮이지
않은 것은 단위가 아니라 **단위들을 잇는 경로**다.

도구는 이미 있었다. `tests/test_base_lateral.py`의 단위 0(`BRANCH_CASES`)이 정확히
이 공백을 메우려고 만들어진 분기 표인데, 공간 분포 작업에는 적용되지 않았다.
**분기 표는 한 기능의 소유물이 아니라 저장소의 공용 자산이어야 한다.**

교훈: **노드별로 곱해지는 물성을 추가할 때는 단위 테스트와 별개로 분기 표를
반드시 통과시킨다.**
