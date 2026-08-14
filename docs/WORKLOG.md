# 작업 로그 — 이어서 작업하기 위한 인수인계

> **최종 갱신**: 2026-08-14
> **브랜치**: `main` (= `origin/main`)
> **버전**: v28.55
> **다른 PC에서 시작하는 법**: `git clone` → `pip install -r requirements.txt` →
> `python -m pytest -q -m "not slow"` 로 아래 테스트 상태가 재현되는지 먼저 확인할 것.

---

## 1. 현재 테스트 상태

```
pytest -q -m "not slow"
147 passed, 2 deselected, 6 xfailed
```

- **2 deselected** — 풀 M10 핀 테스트. 조합당 약 17분이라 기본 실행에서 제외한다.
  돌리려면 `-m "not slow"`를 빼면 된다.
- **6 xfailed** — `tests/test_junction_bf.py`의 Vb=0 케이스. 단락 조건에서 수렴
  잔차가 평탄해지는 현상이며, 해가 정확함을 별도 테스트로 확인한 뒤 표시해 둔 것이다.
  **결함이 아니다.**
- `tests/test_default_pin.py` / `test_legacy_pin.py`의 스택 불일치 xfail은 이 머신에서
  발동하지 않았다 — 즉 **비트 핀이 실제로 강제되고 있다.** 다른 PC에서 이 둘이
  xfail로 바뀌면 BLAS/SuperLU 조합이 달라진 것이지 물리 회귀가 아니다.

> ⚠ `tests/test_gui_layout.py`는 실제 Tk 창을 만든다. 이 머신에서 세션 도중
> `_tkinter.TclError: Can't find a usable init.tcl`로 실패하기 시작했는데, 변경을
> stash한 상태에서도 동일하게 재현되어 **코드와 무관한 환경 문제**로 확인했다.
> 전체 스위트로 돌리면 통과한다(파일 조합에 따라 갈린다). 다른 PC에서 이 파일만
> 따로 돌려 실패하면 이 항목을 먼저 의심할 것.

---

## 2. 완료한 작업

### 2-1. 효율 개선 roadmap 러너 (Griddler PRO §5.1 상당)

기준 설계에서 파라미터를 순차 누적 변경하며 각 케이스를 재계산하고, CSV 누적 +
Jsc/Voc/FF/Eff 4패널 PNG로 출력한다. 케이스 정의를 GUI 세션이 아닌 JSON 파일에 둔다.

| 커밋 | 내용 |
|---|---|
| `d632229` | 머지 커밋 (7 files, +1257) |
| `41f0636` | 시나리오 스키마 로드·검증·누적 전개 |
| `9143d4a` | provenance 수집 + CSV 행 조립 |
| `39034fe` | 실행 루프 + resume + 비트 동일 회귀 |
| `8e13315` `62afee8` | 4-panel 플롯 + 세로 여백 수정 |
| `dd17742` | CLI + UNIST 예시 시나리오 |
| `2c7b59e` | 4-panel 평평화 임계 |

- 설계: `docs/superpowers/specs/2026-08-13-roadmap-runner-design.md`
- 계획: `docs/superpowers/plans/2026-08-13-roadmap-runner.md`
- 진입점: `scripts/run_roadmap.py`, 예시 `scripts/scenarios/unist_tco.json`

**설계상 경계**: 이 러너는 **탐색하지 않는다.** 최적 설계는 `optimize_grid`로 먼저
구해 시나리오 파일에 옮겨 적는다(스펙 §2의 2단계 워크플로우). 두 기능을 합치면
"이 막대가 파라미터 변경의 효과인가 재최적화의 효과인가"를 구분할 수 없다.

### 2-2. extraction_method 조치 (v28.54)

`extraction_method`는 `GridDesign`에 저장만 되고 솔버가 읽지 않아, "Ribbon Ends"나
"Floating"을 골라도 probe_point와 **같은 결과가 에러 없이** 나왔다. 솔버 연결 전까지
GUI 드롭다운을 비활성화하고 `(not implemented)` 라벨을 붙였다.

| 커밋 | 내용 |
|---|---|
| `8ff7dee` | GUI 비활성화 + 라벨 |
| `02c3301` | main 머지 |

- 근거: `docs/audit_2026-08-13.md` §4 "Current extraction mode"
- **솔버 배선은 여전히 없다.** 이 조치는 오해를 막은 것이지 기능 구현이 아니다.

### 2-3. Metal Optical Transparency (v28.55)

금속의 물리 폭(접촉 면적·저항)과 광학 폭(음영)을 분리한다.
`T = 1 − optical/physical`, 기본 0, finger·busbar 각각 지정.

| 커밋 | 내용 |
|---|---|
| `1cd92dd` | 머지 커밋 (10 files, +1723 −26) |
| `184ed65` | T 파라미터 + `optical_widths` 헬퍼 |
| `1ea447a` | 엔진 배선 + rear 경고 + 모델 불변 회귀 |
| `71bb298` | 보고 경로 11곳 광학화 |
| `f22544a` | adapter 배선 + recovery 상호배타 + shading 2컬럼 |
| `ce960ca` | `optimize_grid` 축 7→9 + 조합 수 확인 콜백 |
| `7c13035` | roadmap CSV shading 2컬럼 |
| `f1f0758` | GUI 입력란 + 광학 폭 프리뷰 |

- 설계: `docs/superpowers/specs/2026-08-14-metal-optical-transparency-design.md`
- 계획: `docs/superpowers/plans/2026-08-14-metal-optical-transparency.md`

**반드시 알아둘 것 두 가지**

1. **비트 동일이 성립하는 이유**: `_sh_geo`(설계 물리 폭)는 그대로 두고 `_sh_case`만
   광학 폭으로 바꿨다. 그래서 `_gen_s = (1−sh_case)/(1−sh_geo)`가 T=0에서 정확히 1이
   된다. `optical_widths()`가 곱셈만 쓰는 것도 이 때문이다(IEEE 754에서 `w*1.0 == w`).
   **반올림이나 클램프를 넣으면 이 성질이 깨진다.**
2. **불변이어야 하는 것은 모델이지 소산 전력이 아니다.** `Pc`는 전력이라 T가 발전량을
   늘리면 당연히 오른다(실측 발전량비 1.0164, `Pc`비 1.0332 = 1.0164²). 회귀 테스트는
   `_Gc`/`_Km`/`_Ke`/`metal_frac`의 비트 동일을 본다.

### 2-4. 감사 보고서 2건

| 문서 | 내용 |
|---|---|
| `docs/audit_2026-08-13.md` | Griddler 피처맵 Pri A 전체 + §5 체크리스트. 완전 6 / 부분 7 / 미구현 2 |
| `docs/pro_feature_map_2026-08-14.md` | PRO 전용 기능 11개. 완전 6 / 부분 1 / 미구현 4 |

둘 다 **호출 경로를 따라가 확인**했다. "함수·파라미터 존재"를 구현 근거로 삼지 않았다.

### 2-5. 등록 자료 자동 산출 ★ (지시 목록에는 "다음 할 일"이었으나 완료됨)

| 커밋 | 내용 |
|---|---|
| `a005eef` | `scripts/gen_registration_stats.py` + 문서 갱신 |
| `ce454c2` | `--check` 변동성 필드 제외 + 문서 정리 |

`docs/registration_material.md`의 규모·테스트 수·버전이 수동 기재라 5판 동안 낡았던
문제를 해결했다. 문서의 `<!-- STATS:BEGIN x -->` ~ `<!-- STATS:END x -->` 사이를
스크립트가 재생성한다.

```bash
python -m pytest -q -m "not slow" > pytest.log
python scripts/gen_registration_stats.py --from-log pytest.log --write
python scripts/gen_registration_stats.py --from-log pytest.log --check   # exit 1이면 낡음
```

**남은 수동 수치는 없다.** 서술(마일스톤 표, 기능 설명)만 손으로 갱신하면 된다.

---

## 3. 다음 할 일 (우선순위 순)

### 우선순위 1 — taper 물리 연결

`taper_factor`가 `metal_rects_front()`까지만 가고 **금속 저항에 도달하지 않는다.**
`assemble_K_met_1d`가 스칼라 폭 하나만 받기 때문이다. `shading_fraction`도 균일 폭을
가정해 확장부 면적을 누락한다.

- **순효과: taper를 켜면 저항 이득 없이 재결합·접촉 손실만 늘어 항상 불리하게 나온다.**
- 다행히 `front_electrode/`·`scripts/`·`tests/` 전체에서 `taper`/`pattern_style` 참조가
  **0건**이라 모든 최적화가 `h_pattern` 고정으로 돈다 → **기존 산출 수치에 영향 없음(잠복)**.
- 그래서 고쳐도 회귀 위험이 낮다. "h_pattern 결과 불변"이 그대로 검증 조건이 된다.
- 근거: `docs/audit_2026-08-13.md` §3-4, `docs/pro_feature_map_2026-08-14.md` "taper" 절

### 우선순위 2 — mesh 4-노드 판정기

Griddler 매뉴얼의 메시 밀도 기준(busbar 사이 finger당 최소 4노드, finger 사이 4노드)을
판정하는 코드가 없다. 현재 진단은 삼각형 각도·aspect(`mesh_quality_metrics`)와
대칭성·밀도 편향(`mesh_distribution_metrics`)뿐이다.

- `mesh_quality_metrics`에 `NodesPerFingerSpan` / `NodesBetweenFingers` 두 지표 추가
- 비용이 작고, 메모리에 남은 "M10과 소면적 셀의 수렴 방향이 반대" 현상을 이 기준으로
  즉시 재점검할 수 있다
- 근거: `docs/griddler_feature_map.md` §2.2, `docs/audit_2026-08-13.md` §5 체크 4

### 우선순위 3 — tandem 3종 세트

감사가 "non-overlapping area Jsc 미구현"으로 적었으나, 매뉴얼 원문 확인 결과 실제
격차는 **세 가지 묶음**이다.

1. **Top Cell Position** — 두 셀의 상대 위치라는 기하 자유도 자체가 없다
2. **조도 3영역 분리** — top / bottom / 겹치지 않는 bottom 영역. 현재는 제3영역 개념이 없다
3. **Non-overlapping area Jsc** — 위 2번의 입력

실험용 tandem에서 top cell이 작은 경우가 흔하며, 반영하지 않으면 Jsc가 과대평가된다.

- 근거: `docs/griddler_feature_map.md` §2.12 (2026-08-14 개정본)

### 우선순위 4 — temperature 지원

`T = 298.15`가 모듈 상수로 하드코딩되어 있고 `n_i(T)` 스케일링이 없다. Griddler PRO는
`J01(T) = J01(25°C)·(n_i(T)/n_i(25°C))²`, `J02`는 1승으로 처리한다.

- 매뉴얼이 명시한 한계도 함께 상속·문서화할 것: Jsc 온도계수와 캐리어 mobility 변화에
  따른 반도체 면저항 변화는 Griddler도 모델링하지 않는다
- 근거: `docs/griddler_feature_map.md` §2.4, `docs/audit_2026-08-13.md` §4
- 부수: `_solve_tandem_junction_bf_v29`가 `VT = 0.02568`을 지역 재정의한다(전역 0.02570).
  0.09 % 차이. 온도 작업 시 함께 정리할 것

### 우선순위 5 — registration_material.md 서술 갱신

수치는 자동화되었으므로(§2-5) **서술만** 남았다. 등록 직전에:

```bash
python scripts/gen_registration_stats.py --from-log pytest.log --check
```
로 수치 최신성을 확인하고, 마일스톤 표에 새 버전 행을 추가하면 된다.

---

## 4. 미해결 판단 사항

### 4-1. RayFlare 연동 시점

**확정된 사실**
- RayFlare는 Griddler PRO 빌드에 **존재한다** (사용자가 창 타이틀바 `<rayflare>` 직접 확인)
- 매뉴얼 v7.0(2023-09) 전문 검색 0건 → **매뉴얼이 현 빌드보다 낡았다는 근거**이지
  기능 부재의 근거가 아니다. "Griddler Lock"도 같은 패턴이다
- LGPL v3 오픈소스 Python 패키지 (qpv-research-group, JOSS 논문)
- Griddler 본체와의 인터페이스는 **`Jgen` 스칼라 하나**로 매우 얕다

**미확정**
- PRO가 rayflare 패키지를 **실제 호출**하는지, 아니면 모델을 **재구현**했는지
  → About 메뉴의 **LGPL 고지 유무**로 판별 예정

**판단이 필요한 지점**: 인터페이스가 얕아 붙이는 난이도는 낮지만, **LGPL v3라 배포
형태(동적 링크 / 별도 프로세스 / 재구현)에 따라 라이선스 의무가 달라진다.**
저작권 등록과 배포 계획을 먼저 정한 뒤 착수해야 한다.

- 근거: `docs/griddler_feature_map.md` §2.8 "매뉴얼 v7.0과 현재 PRO 빌드가 불일치한다"

### 4-2. recovery vs T 전환 여부

`busbar_recovery_factor`(기존)와 `optical_transparency_busbar`(신규)는 **같은 물리
(busbar 반사광 회수)를 서로 다른 계층에서 모델링한다.** 동시 지정은 `ValueError`로
막아두었다.

| | recovery factor | optical transparency |
|---|---|---|
| 계층 | adapter 사후 line-item | 엔진 입력 |
| FEM 피드백 | **없음** (상한 근사) | **있음** |

**T 쪽이 물리적으로 더 엄밀하지만 아직 갈아타지 않았다** — T 값의 근거가 될 문헌값·
측정값이 없기 때문이다. 현재 recovery가 기본, T는 opt-in이다.

**판단이 필요한 지점**: 기존 KIST 스윕 결과가 recovery 25 %를 쓰고 있어, 전환하면
논문 수치가 바뀐다. T의 실측 또는 문헌 근거를 확보한 뒤 결정할 것.

- 근거: `docs/superpowers/specs/2026-08-14-metal-optical-transparency-design.md` §4

---

## 5. 참고 — 문서 지도

| 문서 | 성격 |
|---|---|
| `docs/griddler_feature_map.md` | Griddler 쪽 **사실만** 담는 중립 레퍼런스. 구현 상태를 여기 적지 말 것(§2.12는 예외, 사용자 지시) |
| `docs/audit_2026-08-13.md` | Pri A 기능 감사 (v28.53 기준) |
| `docs/pro_feature_map_2026-08-14.md` | PRO 전용 기능 감사 (읽기 전용) |
| `docs/registration_material.md` | 저작권 등록용. 수치는 스크립트가 생성 |
| `docs/front_electrode_model_scope.md` | 전면전극 모델 범위 |
| `_experiments_README.md` | 루트 `_*_results.csv`의 실행 조건. **수치 인용 전 반드시 확인** |
| `docs/superpowers/specs/` · `plans/` | 기능별 설계·구현 계획 |

> 매뉴얼 PDF는 저작권 문제로 저장소에 없다. 별도 보관 중이며 필요 시
> `--add-dir`로 접근한다. 이 저장소의 매뉴얼 관련 기술은 모두 **요약·재서술**이다.
