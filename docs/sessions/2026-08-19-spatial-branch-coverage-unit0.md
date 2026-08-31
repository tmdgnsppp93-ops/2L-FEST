# 작업 세션 기록 — 2026-08-19: 우선순위 0 단위 0 (분기 커버리지 특성화)

> 이 문서는 **결정과 근거의 기록**이다. 무엇을 했는지는 커밋 메시지에, 앞으로 무엇을
> 할지는 `docs/WORKLOG.md`와 계획서에 있다. 여기에는 **왜 그렇게 결정했는지**와
> 그 과정에서 나온 발견을 남긴다.
>
> 앞 세션: `docs/sessions/2026-08-18-spatial-map-branch-defect.md`
> 계획: `docs/superpowers/plans/2026-08-18-spatial-map-branch-coverage.md`

| | |
|---|---|
| **시작** | `4a16f8d` (v28.60 + 결함 기록) |
| **범위** | **단위 0만.** 프로덕션 코드 0줄 변경 |
| **산출물** | `tests/test_spatial_branch_coverage.py` (90건) |
| **환경** | Windows 10 Pro / AMD64, Python 3.14.3 / numpy 2.4.3 / scipy 1.17.1 / scipy-openblas |
| **비트 핀** | `stack_mismatch() is None` — **strict 실행** |
| **결과** | 58 passed, 32 xfailed, 0 failed (95 s) |

---

## 0. 환경 결함은 해소됐다

`docs/WORKLOG.md`의 착수 지점 블록이 경고한 **`import numpy.testing` 무한 대기**
(2026-08-18 18:00경 발생)는 **재현되지 않는다.**

| 대상 | 2026-08-18 | 2026-08-19 |
|---|---|---|
| `import numpy.testing` | 90 s 타임아웃 ❌ | **2.55 s** ✅ |
| `import scipy.sparse.linalg` | 90 s 타임아웃 ❌ | **4.14 s** ✅ |

원인은 여전히 규명되지 않았다. **머신 상태 변화라는 진단이 맞았다는 것만
확인됐다** — 저장소는 그대로인데 증상이 사라졌다. 재발하면 같은 자리에 기록할 것.

### pytest가 깔려 있지 않았다

이 머신의 시스템 Python(3.14.3)이 `conftest.PINNED_STACK`과 **정확히 일치**하는데
pytest만 없었다. `.venv/`는 Python 3.11.9 / numpy 2.4.6이라 **핀 스택이 아니다** —
그쪽으로 돌리면 비트 핀이 전부 xfail로 낮아진다.

**시스템 Python에 pytest만 설치했다**(`pytest 9.1.1` + iniconfig/pluggy/pygments/
colorama). numpy·scipy는 건드리지 않았으므로 핀 스택은 그대로다. 실제로 이 세션의
비트 핀 5건이 strict로 통과했다.

> **다음 사람에게**: 테스트는 `python -m pytest`(시스템 Python)로 돌릴 것.
> `.venv/Scripts/python.exe`는 스택이 달라 비트 핀을 검증하지 못한다.

---

## 1. 계획서의 전제 두 개가 틀렸다

단위 0의 목적이 *"결함을 테스트로 먼저 고정한다"* 였는데, 고정하려고 실측해 보니
**계획서가 근거로 삼은 관측 방법 자체가 성립하지 않았다.** 이것이 이 세션의
가장 중요한 결과다.

### (a) `J01_top_arr`는 결함 분기에서도 **배열**이다

계획서 §단위 0 T2:

> `sys.settrace` f_locals로 각 분기의 `J01_top_arr`가 **배열인지 스칼라인지** 고정

`docs/spatial_map_convention.md` §6도 같은 말을 한다:

> 네 분기는 `J01_top_arr`를 **스칼라로만** 만든다

**둘 다 틀렸다.** 실측(`_solve_tandem_junction` 프레임):

```
J01_top_arr = ndarray[3809]
```

```python
J01_top_arr = dp.J01_top_pass * (1 - mf) + dp.J01_top_metal * mf
#                                    ^^ metal_frac — 이미 노드 길이 배열
```

`mf`(`self.metal_frac`)가 노드 길이 배열이라, 맵을 무시하는 분기에서도 결과는
`ndarray[N]`이다. **dtype·shape로는 결함이 전혀 보이지 않는다.** 스칼라인 것은
`J01_top_pass` 같은 *계수*이지 `J01_top_arr`가 아니다.

**대안으로 채택한 관측**: 무맵 실행과 유맵 실행에서 **같은 지역 변수를 비트
비교**한다. 파생값이 아니라 조작 대상 자체이고, dtype에 의존하지 않으며, 변수가
아예 없는 경우(`_gen_t`는 맵 경로에서만 생긴다)도 "안 실었다"로 정확히 판정된다.

> 계획서의 의도 — *"해석의 여지가 없는 직접 관측"* — 는 그대로 지켰다.
> 지표만 바꿨다.

### (b) `cell_current` 함정은 계획서 말대로였다 (확인)

이쪽은 계획서가 옳았고, 실측이 그것을 못 박았다.

```
phaseB_full_area + gen 맵:   전압장 Δ = 0 (비트 동일)   ΔJ = +4.426 mA/cm²
```

전압장은 **1비트도 안 움직이는데** 보고되는 전류는 4.4 mA/cm² 바뀐다. 이 조합이
`test_cell_current_delta_is_not_evidence_of_working`으로 고정돼 있다 — 단위 1
이후에도 *"ΔJ ≠ 0이니 고쳐졌다"* 로 판단하지 말라는 표식이다.

---

## 2. 결함 분기가 하나 더 있다 — `_solve_single_bifacial`

§6의 16칸 표는 이렇게 끝난다:

> 단일셀(`solve_single` `:6431`)은 4종 모두 정상이다.

**단일셀 full_area만 정상이다.** `solve_single`은 `GEDOS.py:6396`에서

```python
if (self.geo.rear_mode in ('bifacial', 'patterned')
        and self._J_static_single_bf is not None):
    return self._solve_single_bifacial(...)
```

로 빠져나가고, `_solve_single_bifacial`(`:6513`)에는 `_spatial_mult` 호출이
**하나도 없다**(`:6546-6547`이 인라인 조립).

실측 — 단일셀 bifacial에 맵을 붙인 결과:

| 대상 | 전압장 Δ | 지역 배열 |
|---|---|---|
| `j01` | **0 (비트 동일)** | 안 바뀜 |
| `j02` | **0 (비트 동일)** | 안 바뀜 |
| `gen` | **0 (비트 동일)** | 안 바뀜 |
| `rc` | 2.376e-03 | (해당 없음 — B 계층) |

**결함 칸은 9개가 아니라 12개다.** §6 표는 4행이 아니라 5행이어야 한다.

### 왜 못 봤나 — 표가 이 분기를 감시하지 않았다

`tests/test_base_lateral.py`의 `_NAMED_SOLVERS`에 `_solve_single_bifacial`이
없었다. 그래서 `_probe`가 `single_bifacial` 케이스를 `inline`으로 판정하고,
`test_case_table_covers_every_reachable_named_solver`도 **통과했다** — 감시하지
않는 분기는 "도달했다"로 세어지지 않기 때문이다.

그 파일 독스트링의 *"미지 벡터 레이아웃을 독립적으로 조립하는 잔차 지점은 7곳"* 은
**처음부터 맞았다**(인라인 2 + 이름 있는 5). 틀린 것은 tuple 하나였다.

### 원본 표를 고쳤다 (박사님 지시)

처음에는 `BRANCH_CASES`를 건드리지 않고 새 파일에 `ACTUAL_BRANCH`를 따로 두는
쪽으로 갔다 — 공용 자산이고 `docs/base_lateral_convention.md`·계획서가 "6분기
표"로 참조하기 때문이다. **지시에 따라 원본을 고쳤다.** 표가 두 벌이 되는 것보다
한 벌이 맞는 것이 낫다는 판단이 옳다.

- `_NAMED_SOLVERS`에 `_solve_single_bifacial` 추가
- 케이스 7의 기대 분기 `_INLINE` → `"_solve_single_bifacial"`
- 두 곳에 정정 경위 주석. Ns 식(`2N+Nm+Nrm`)은 **그때도 맞았으므로**
  `test_unknown_vector_layout_is_pinned`는 영향 없다

되돌아가는 것을 막는 장치는 새 파일에 둔다:

| 테스트 | 무엇을 막는가 |
|---|---|
| `test_named_solvers_covers_single_bifacial` | tuple에서 다시 빠지는 것 |
| `test_actual_branch_agrees_with_base_lateral_table` | 두 표가 갈리는 것 |

**검증**: `test_base_lateral.py`의 디스패치·레이아웃·커버리지·게이트 관련 24건
전부 통과(72 s).

### 벌크 횡전도에는 같은 누락이 없었다 ✅

지시대로 확인했다. **`Rs_base`에는 이 누락으로 인한 공백이 없다** — 구조적
이유가 있다.

`Rs_base`는 `_build`(`GEDOS.py:4396-4488`) 안에서 후면 평면 면전도에 병렬
합성된다:

```
1/Rs_r_eff = 1/Rs_rear_tco + 1/Rs_base      (:4488)
```

**`_build`는 디스패치보다 앞**이라 모든 경로에서 반드시 실행된다. `spatial_rc`가
무사한 것과 **정확히 같은 이유**다(B 계층 = 강성 조립). 잔차(A 계층)에 있는
`j01`/`j02`/`gen`만 디스패치 뒤에 놓여 갈린다.

실제로 이 분기를 푸는 테스트가 이미 둘 있다:

| 테스트 | 확인 내용 |
|---|---|
| `test_single_mode_bifacial_supports_base` (`:1007`) | 단일셀+bifacial에서 `Rs_base=500`이 결과를 바꾼다 |
| `test_base_gate_follows_the_rear_plane_not_the_phase` (`:1029`) | `BRANCH_CASES` 6개 전부를 실제로 풀어 게이트 판정 |

즉 **표의 라벨이 틀렸을 뿐 기능 커버리지는 온전했다.** 라벨 오류가 실제 결함으로
이어진 것은 공간 분포(A 계층) 쪽뿐이다.

> 이 대비가 결함 기록의 교훈을 정밀하게 만든다. *"분기 표는 저장소의 공용
> 자산이어야 한다"* 는 맞지만, **표가 틀렸을 때 실제로 다치는 것은 디스패치
> 뒤에 있는 것(A 계층)뿐**이다. 앞에 있는 것(B 계층)은 표와 무관하게 안전하다.
> 새 물성을 추가할 때 먼저 물어야 할 것은 "표를 통과시켰나"가 아니라
> **"이것이 `_build` 앞인가 뒤인가"** 다.

---

## 3. 인라인 조립 지점은 9곳이 아니라 13개 함수 34줄이다

계획서 §1 "소비 지점 (7곳 + 진단 2곳)" 표를 AST로 검산했다
(`J0\d_(?:top|single)_pass\s*\*\s*\(\s*1\s*-\s*mf\s*\)`).

| 함수 | 줄 수 | 계획서 표 | 성격 |
|---|:---:|:---:|---|
| `solve_tandem` | 2 | ✅ #1 | 잔차(인라인) |
| `_solve_tandem_junction` | 2 | ✅ #2 | 잔차 |
| `_solve_tandem_junction_bf` | 2 | ✅ #3 | 잔차 |
| `_solve_tandem_junction_bf_v29` | 2 | ✅ #4 | 잔차(죽은 경로) |
| `_solve_tandem_bifacial` | 2 | ✅ #5 | 잔차 |
| `solve_single` | 2 | ✅ #6 | 잔차(인라인) |
| **`_solve_single_bifacial`** | 2 | ❌ **없음** | **잔차** ← §2 |
| `cell_current` | 4 | ✅ #7 | 사후처리 |
| `_phase_b_interlayer_diagnostics` | 2 | ✅ #8 | 진단 |
| `current_matching_diagnostics` | 2 | ✅ #9 | 진단 |
| **`losses`** | 6 | ❌ **없음** | 사후처리 |
| **`recomb_currents`** | 4 | ❌ **없음** | 사후처리 |
| **`_tab_current`** | 2 | ❌ **없음** | **GUI** |

`_tab_current`는 `DP.J01_top_pass*(1-mf)`로 공백 없이 쓴다 — 정규식이 공백을
흡수하도록 만든 이유다.

**단위 1에 넘기는 판단**: `losses` · `recomb_currents` · `_tab_current`를 헬퍼로
배선하지 않으면, `cell_current`가 가졌던 **자기모순 값** 문제가 그 셋에 그대로
남는다(맵 없는 전압장 + 맵 있는 다이오드 식). 계획서 §1이 `cell_current`를 고치는
근거로 든 논리가 그대로 적용된다.

census는 `test_inline_assembly_census_is_pinned`가 고정한다 — **오늘 초록불**이고,
지점이 늘거나 줄면 즉시 실패해서 갱신을 요구한다.

---

## 4. `J02_single`의 기본값이 0이라 한 칸이 관측 불가였다

```
DiodeParams.J02_single_pass  = 0.0
DiodeParams.J02_single_metal = 0.0
```

그래서 단일셀에서 `j02` 맵은 **무엇을 곱해도 결과가 같다**. `dV = 0`이고 `ΔJ`도
정확히 `0.0`이다 — 이것은 결함이 아니라 **관측 불가**다. 구분하지 않으면
`single_full_area/j02` 칸이 "정상인데 안 변한다"와 "결함이라 안 변한다"를 섞어
버린다.

**단일셀 케이스에 한해** `J02_SINGLE_PROBE = 1e-9`를 넣어 칸을 관측 가능하게
만들었다. 탠덤 칸은 기본값 그대로다 — T3 비트 핀과의 대조를 유지해야 하기
때문이다. 확인:

| | `J02 = 0` (기본) | `J02 = 1e-9` |
|---|---|---|
| `single_full_area` | dV = 0 (관측 불가) | dV = **3.902e-06** → 정상 ✅ |
| `single_bifacial` | dV = 0 | dV = **0 (비트 동일)** → 결함 ❌ |

값을 넣으니 두 칸이 갈렸다. 이것이 §2의 결함을 확정한 마지막 근거다.

---

## 5. 빨간불을 어떻게 남길 것인가

계획서:

> 이 시점에서 테스트는 **빨간불이 정상이다** (결함을 고정하는 것이므로)

문자 그대로 하면 저장소 전체가 빨간불이 되고, **단위 1·2가 회귀 게이트를 못
쓴다** — 진짜 회귀와 "예정된 빨간불"을 구분할 수 없다. 이 저장소가 계속 경계해 온
실패 유형이 정확히 그것이다(`conftest.py`의 비트 핀 스택 게이트 주석 참조).

**결함 칸마다 `xfail(strict=True)`를 붙였다.** `test_junction_bf.py:42`의 선례와
같은 형태다.

| 시점 | 상태 |
|---|---|
| 오늘 | 결함 칸 = **xfail**(단언은 실제로 실패한다). 전체는 초록불 |
| 단위 1 이후 | 같은 칸이 통과 → **XPASS → strict 실패** |

즉 단위 1은 마커를 지우지 않으면 초록불이 되지 않는다. *"수정 전 빨간불 · 수정 후
초록불"* 의 의도는 유지하면서, 그 사이에 다른 회귀를 감시할 수 있게 한 것이다.

**단위 1의 완료 조건**: `RESIDUAL_SEES_MAP`의 `False`를 전부 `True`로 바꾸고 이
파일이 초록불이 되는 것.

### `strict=True`를 실측 확인했다 (박사님 지시)

`strict`가 빠지면 이 방식이 **통째로 무력해진다** — 단위 1이 결함을 고쳤을 때
XPASS가 조용히 통과하고, 마커는 그대로 남아 다음 사람은 여전히 결함이 있다고
읽는다. 그래서 주장하지 않고 수집된 마커를 직접 덤프해 세었다.

```
xfail 마커가 붙은 테스트: 32
  strict=True : 32
  그 외        : 0

   12  test_residual_sees_spatial_map
   12  test_branch_local_diode_arrays_carry_the_map
    6  test_every_branch_calls_the_helper
    1  test_helper_exists
    1  test_inline_assembly_only_inside_helper
```

**32/32 strict=True.** 그리고 32건 전부 실제로 xfail로 떴다(0 failed = XPASS
없음) — 즉 **단언이 진짜로 실패하는** 마커이지, 통과하는데 잘못 붙인 것이 아니다.
strict라면 후자는 즉시 실패로 드러난다.

되돌아가는 것을 막으려고 `test_every_defect_marker_is_strict`를 넣었다. `_cross()`가
만드는 파라미터 마커와 데코레이터 3종을 introspection으로 검사한다.

> **저장소 전체에 `xfail_strict = true`를 넣지 않은 이유**: `test_junction_bf.py:42`가
> 의도적으로 `strict=False`를 쓴다. 그쪽은 "환경에 따라 갈리는 알려진 허용"이고
> 이쪽은 "고쳐야 할 결함"이다 — 성격이 다르므로 ini로 일괄 강제하면 그 구분이
> 사라진다. 파일 안에서 검사하는 쪽을 택했다.

---

## 6. T3 — 캡처한 핀

Phase A / full_area는 현재 **유일하게 올바른 탠덤 경로**다. 단위 1의 리팩터가 값을
건드리지 않았다는 증거로 쓰려고 수정 전에 캡처했다.

캡처 조건: mono 지오메트리(2×2 mm, 8F+1BB, `axis_segments_override=36`),
`PARAMS`, `Vb = 0.5`, `GEDOS_LEGACY_LOCAL_MATCH=1`, `Rs_junction = 0.0`,
gaussian 맵(bg 1.0 / feature 2.0 / center (1,1) / σ 0.4).

| 맵 | `cell_current` [mA/cm²] | 전압장 sha256 (앞 16자) |
|---|---|---|
| 없음 | 18.65028360819871 | `89eefe56d46876f6` |
| `j01` | 18.650282520545172 | `14e43ffc66b6855c` |
| `j02` | 18.650283608197928 | `c4091e831f6c8a2e` |
| `gen` | 23.076602333684352 | `e1a7a26739ba389d` |
| `rc` | 18.65024359585303 | `1966dd5a89350728` |

전체 다이제스트는 `PHASE_A_PINS`에 있다. `_voltage_field()`가 만든 float64 배열의
바이트라 **비트 단위 증거**다. 스택이 다르면 `bit_pin_gate`가 xfail로 낮춘다.

> `Vm`은 비금속 노드가 `NaN`이라 그대로 두면 `np.array_equal`이 항상 False다.
> NaN 위치는 메시 구조가 정하므로 두 실행에서 동일 — **0.0으로 치환**해서
> 비교한다. 이 규약이 깨지면 다이제스트가 통째로 달라진다.

---

## 7. 머신 분담 기록을 갱신했다 (박사님 지시)

**"원 캡처 PC"는 KIST 하나가 아니었다.** 이 머신(집 데스크톱)도 핀 스택이다.

| 축 | KIST PC | 집 데스크톱 | 같은가 |
|---|---|---|:---:|
| 아키텍처 | AMD64 | AMD64 | ✅ |
| Python | 3.14.3 `tags/v3.14.3:323c59a` MSC v.1944 | **동일 빌드 문자열** | ✅ |
| numpy / scipy | 2.4.3 / 1.17.1 | 2.4.3 / 1.17.1 | ✅ |
| numpy BLAS | scipy-openblas 0.3.31.dev (pkgconfig) | 동일 | ✅ |
| scipy BLAS | scipy-openblas 0.3.30 | 동일 | ✅ |
| OS | Windows-11-10.0.26100 | Windows-10-10.0.19045 | ❌ |
| CPU | Model 151 Stepping 5 | Model 158 Stepping 13 | ❌ |

**결정적 확인**: KIST에서 캡처한 핀 2건(`test_default_pin` · `test_legacy_pin`,
RTOL 1e-8)을 이 머신에서 돌려 **strict로 2 passed (4.4 s)**. 버전 게이트가 통과한
것만으로는 부족하다는 것이 맥북 사례로 실증됐으므로, 게이트가 아니라 **핀 값 자체**로
확인했다.

즉 **OS 버전과 CPU 세대가 달라도 핀이 재현된다.** §1-1-a가 규명한 두 축(아키텍처 ·
BLAS 구현)이 실제 판정 요인이고 Windows 빌드·CPU 스테핑은 아니라는 것이 **반증
사례로** 확인된 셈이다. 핀 재현의 실질 조건은 세 개다: x86-64 · scipy-openblas ·
버전 3종.

`docs/WORKLOG.md` §1-1-a에 열을 추가하고 §1-2 표를 3행(KIST / 집 데스크톱 / 맥북)으로
바꿨다. **불일치는 맥북 하나뿐이다.**

> ⚠ 함께 적어 둔 함정: 집 데스크톱의 `.venv/`(py 3.11.9 / numpy 2.4.6)는 핀 스택이
> **아니다.** 그쪽으로 돌리면 오류도 실패도 없이 핀만 조용히 xfail로 내려간다.
> `python -m pytest`(시스템)로 돌릴 것.

---

## 8. 하지 않은 것

- **프로덕션 코드 수정** — 단위 1의 일이다
- **`docs/spatial_map_convention.md` §6을 "해소"로 갱신** — 계획서대로 단위 2의
  일이다. 다만 §6 표가 **틀렸다는 것**은 지금 알게 됐으므로 그 사실만 §6에
  덧붙였다(해소 선언이 아니라 정정)
- **`losses`/`recomb_currents`/`_tab_current` 배선 결정** — §3에 근거만 남기고
  판단은 단위 1로 넘긴다
- **`Rsh` 5번째 대상 추가** — 계획서 §하지 않는 것 그대로, 박사님 지시로 보류
