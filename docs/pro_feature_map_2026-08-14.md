# Griddler PRO 전용 기능 감사 — 2L-FEST 구현 상태

> **성격**: 읽기 전용 감사. 코드 수정 없음, 신규 테스트 실행 없음.
> **작성**: 2026-08-14

## 감사 환경

| 항목 | 값 |
|---|---|
| 브랜치 | `feat/metal-optical-transparency` |
| 감사 시점 HEAD | `1ea447a` feat(transparency): 엔진 배선 + rear 경고 + 모델 불변 회귀 |
| 감사 시점 작업 트리 | `2L_FEST.py` 미커밋 변경 있음 (Task 3 보고 경로 광학화) |
| 버전 문자열 | `__build__` = `v28.54` (2026-08-14). *v28.55 bump는 미착수* |
| 테스트 | 파일 16개 / `test_` 함수 **121개** |

> **감사 대상 = 작업 트리** (감사 시점 HEAD + 미커밋 Task 3). 그 Task 3 변경분은 감사 직후 **`71bb298`** 로 커밋되었으므로, 본 보고서의 모든 판정은 `71bb298` 트리와 일치한다. 판정 내용은 커밋 전후로 바뀌지 않았다 — 이 표기만 사후 갱신했다.

---

## 판정표

| # | 기능 | 판정 | 근거 (file:line) | 비고 |
|---|---|---|---|---|
| 1 | 2T tandem — top/bot 서브셀 + interlayer 저항 + photon coupling J01 | **완전구현** | `2L_FEST.py:1682-1689`, `4400-4401`, `4451-4456`, `4682-4684`, `3702`, `4048`, `RS_JUNCTION_MIN:570` | 세 요소 모두 솔버에 배선. 단 구조가 Griddler와 다름(비고 A) |
| 2 | Cell cross-sectional model — 단면에서 J_L / J01_pass / J01_metal 역산 | **미구현** | 근거 부재 확인: `absorptance`·`light trapping`·`Basore`·`SRV`·`bulk_lifetime`·`wafer_thickness` 전문 검색 **0건** | J01_pass/J01_metal은 역산이 아니라 **직접 입력**(`1682` 부근 DiodeParams) |
| 3 | PC1D 에미터 계산 연동 (또는 대체 J0e 계산) | **미구현** | `PC1D`/`pc1d`/`EDNA`/`J0e` 전문 검색 **0건** | 대체 계산기도 없음 |
| 4 | Batch 실행 — 여러 케이스 연속 실행 | **완전구현** | `front_electrode/optimizer.py:66` `_sweep`, `:124` `optimize_grid`, `front_electrode/roadmap.py:330` `run_roadmap`, `scripts/optimize_m10.py:205` `run_busbars` | append+flush, `--resume`(`optimize_m10.py:212`), 병렬(`:290` `imap_unordered`) |
| 5 | 스크립트 실행 — 외부 파일로 케이스 정의 | **완전구현** | `front_electrode/roadmap.py:173` `load_scenario`, `:186` `expand_cases`, `scripts/scenarios/unist_tco.json`, `scripts/run_roadmap.py` CLI | JSON 시나리오 → 누적 전개 → CSV. `optimize_m10.py:27` argparse CLI 병행 |
| 6 | 비균일 공간 분포 입력 — txt/이미지에서 2D 맵 로드 | **부분구현** | 배선: `2L_FEST.py:3220` `SpatialMap`, `:3810` `_spatial_mult`, 소비 `:4000`(rc) `:4340-4342`(j01/j02/gen) `:5839-5840` | 비고 B |
| 7 | Metallization optimization — grid 설계 변수 스윕 | **완전구현 (7축)** | `front_electrode/optimizer.py:124-166` | 축 목록은 비고 C |
| 8 | Base lateral transport — bulk 내 횡방향 캐리어 전류 | **미구현** | 평면 인벤토리 `2L_FEST.py:3693-3702`: `_Ke`(front TCO) / `_Kr`(rear emitter) / `_Krm`(rear metal) / `_Km`(front metal) / `_K_junc`(interlayer). **bulk 평면 없음** | 횡전도는 표면·금속·interlayer 평면에만 존재 |
| 9 | Capacitive effects — I-V 스윕 속도 의존 과도 효과 | **미구현** | `capacit`/`transient`/`sweep_rate`/`dV/dt` 전문 검색 **0건** | 정상상태 전용 |
| 10 | Metal optical transparency | **완전구현 (신규)** | `2L_FEST.py:971-984`(파라미터·검증), `:1067-1068`(`optical_widths`), `:1347-1359`(`optical_shading_fraction`), `:4029`(`_sh_case`), `:6964`(`shade_frac`) | 비고 D. audit_2026-08-13 시점의 "미구현"에서 변경됨 |
| 11 | Tandem non-overlap 영역 Jsc 별도 입력 | **미구현** | `non-overlap`/`nonoverlap`/`top_area`/`overlap_frac` 전문 검색 **0건** | audit_2026-08-13 이후 **변경 없음** |

**완전구현 6 / 부분구현 1 / 미구현 4 / 미확인 0**

---

## 부분구현 상세

### #6 비균일 공간 분포

- **되는 것**: 공간 맵이 솔버에 실제로 반영된다. `SpatialMap.evaluate()`가 노드 좌표에서 배율을 만들고(`3249`), `_spatial_mult`(`3810`)를 거쳐 접촉 컨덕턴스(`4000`), J01/J02/광생성(`4340-4342`), 단일셀 경로(`5839-5840`)에 곱해진다. 모드 5종: `uniform` / `rectangle` / `gaussian` / `checkerboard` / `csv`(2D 행렬 직접 주입).
- **안 되는 것**: **파일에서 읽어 들이는 경로가 없다.** `np.loadtxt`·`imread` 전문 검색 0건이고, `2L_FEST.py` 안에서 `SpatialMap(`을 생성하는 코드가 **한 줄도 없다**(생성 사례는 `_audit.py:135-145` 스모크 스크립트뿐). 즉 사용자는 GUI·CLI 어디로도 맵을 넣을 수 없고, Python으로 직접 객체를 만들어 `DiodeParams`에 꽂아야 한다. Griddler의 txt/jpg/tif/bmp import에 대응하는 기능은 없다.

---

## 비고

**A. #1 tandem의 구조 차이**
전기적 요소(2T 직렬 결합, interlayer 횡전도 `_K_junc`, 수직 접촉 `Rc_junction`, photon coupling)는 전부 배선되어 있고 `J01_coupling`은 야코비안 항(`4454` `dJLC_dVtop`)까지 포함해 처리된다. 다만 Griddler는 **top/bottom을 각각 독립된 셀 모델 파일로 로드**하는 반면, 2L-FEST의 top/bot은 `DiodeParams`의 필드 쌍으로만 구분되며 서브셀별 기하·전극 그리드를 갖지 않는다. 이 항목이 요구한 세 요소 기준으로는 완전구현이나, 구조적 대응은 아니다.

**C. #7 스윕 축 — 정확히 7개**
`optimize_grid`의 `itertools.product`(`optimizer.py:153-155`) 기준:

| # | 축 | 인자 |
|---|---|---|
| 1 | finger 폭 | `finger_widths_um` |
| 2 | finger pitch | `finger_pitches_mm` |
| 3 | busbar 개수 | `n_busbars_list` |
| 4 | busbar 폭 | `busbar_widths_mm` |
| 5 | 금속 비저항 | `rho_bulk_list` |
| 6 | 접촉 비저항 | `rho_contact_list` |
| 7 | edge margin | `edge_margins_mm` |

7번 축에는 해석 가드가 붙어 있다 — 마진은 설계 자유도가 아니라 공정 제약이라 전역 argmax를 취하면 항상 최소 마진이 뽑히므로, `best` 대신 `best_by_edge`(마진별 최적)를 제공한다(`optimizer.py:143-147`).
*optical transparency 2축 추가는 계획에만 있고 미착수다.*

**D. #10 transparency 배선 확인**
`_sh_geo`(`4028`)는 **물리 폭**으로 남고 `_sh_case`(`4029`)만 광학 폭이다. 이 비대칭이 `_gen_s = (1−sh_case)/(1−sh_geo)`를 T=0에서 정확히 1로 만들어 기존 결과의 비트 동일을 보장한다. 접촉·저항 경로(`_Gc` `3997` 부근, `assemble_K_met_1d` `3979`)는 물리 폭을 계속 쓴다. 측정 확인: T 0→0.4에서 `_Gc`·`_Km`·`_Ke`·`metal_frac`이 비트 동일, `illum_frac` 합만 ×1.0164.

---

## 함께 확인한 항목

### extraction_method — GUI 비활성화 완료

- **커밋 `8ff7dee`** ui(v28.54): Current Extraction 드롭다운 비활성화 + (not implemented) 라벨 → **`02c3301`로 main에 머지됨**
- 현재 상태: 전면 `2L_FEST.py:8514`(`(not implemented)` 라벨), `:8525`(`state="disabled"`) / 후면 `:8653`, `:8664`
- **솔버 배선은 여전히 없다.** `extraction_method`는 `:1012`에 저장되고 GUI가 `:9005`·`:9046`에서 넘길 뿐, 솔버가 읽는 지점이 없다. 조치는 "틀린 결과를 옳다고 믿는 상태"를 막은 것이지 기능 구현이 아니다.

### taper — 저항 계산 미배선, optimize 경로에서 미사용

- 전체 참조 3곳뿐: `2L_FEST.py:970-1003`(저장·기본값), `:1372-1375`(`metal_rects_front`), `:1441-1444`(`metal_rects_front_split`, 표시 전용)
- **금속 저항에 도달하지 않는다.** `assemble_K_met_1d`(호출 `:3979`)는 스칼라 폭 하나만 받는다. BB 근처를 넓혀 저항을 낮추는 것이 taper의 목적인데 그 효과가 모델에 없다.
- **shading 보고값에도 미반영.** `shading_fraction`(`:1325` 이하)은 균일 폭을 가정해 확장부 면적을 누락한다.
- **optimize 경로에서 사용되지 않는다.** `front_electrode/`·`scripts/`·`tests/` 전체에서 `taper`/`pattern_style` 참조 **0건** → 모든 최적화·스윕은 `h_pattern` 고정으로 돈다. 따라서 이 결함이 기존 산출 수치에 영향을 준 적은 없다(잠복).
- 순효과: taper를 켜면 저항 이득 없이 `metal_frac` 경유 재결합·접촉 손실만 늘어 **항상 불리하게 나온다.**

---

## 감사 방법과 한계

- 모든 판정은 `grep`으로 호출 경로를 추적해 확인했다. "함수·파라미터 존재"를 구현 근거로 삼지 않았다.
- 미구현 판정 4건(#2·#3·#8·#9)과 #11은 **전문 검색 0건**에 근거한다. 다만 `docs/griddler_feature_map.md` §2.8이 기록한 대로 **검색 0건이 부재의 결정적 증거는 아니다**(다른 이름으로 구현되었을 가능성). 이름을 바꿔 구현했을 가능성을 배제하려면 각 기능의 물리적 입력(예: #2의 bulk lifetime·SRV, #9의 시간 적분)이 어디에도 없다는 점을 함께 근거로 삼았다 — 이들 물리량 없이는 해당 계산이 성립하지 않는다.
- 감사 시점에 #10은 미커밋 작업 트리 기준이었다. 해당 변경분이 `71bb298`로 커밋되어 지금은 이 보고서 전체가 커밋된 트리와 일치한다.
