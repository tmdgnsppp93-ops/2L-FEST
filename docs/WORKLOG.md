# 작업 로그 — 이어서 작업하기 위한 인수인계

> **최종 갱신**: 2026-08-17 (§1-1 비트 핀 재현 실험 · §1-2 머신 분담 추가,
> §3 우선순위 전면 개정 — 박사님 지시)
> **브랜치**: `main` (= `origin/main`)
> **버전**: v28.55
> **다른 PC에서 시작하는 법**: `git clone` → `pip install -r requirements.txt` →
> `python -m pytest -q -m "not slow"` 로 아래 테스트 상태가 재현되는지 먼저 확인할 것.
> 재현되는 수치는 **머신에 따라 다르다** — §1-2 머신 분담을 먼저 볼 것.

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

### 1-1. 비트 핀 재현 실험 (2026-08-17, 맥북 arm64)

**PINNED_STACK 3종을 완전히 일치시킨 venv에서도 핀 2건이 실패했다.**

맥북 기본 스택(python 3.12.13 / numpy 2.4.6 / scipy 1.18.0)에서는
`pytest -q -m "not slow"` → **145 passed, 2 deselected, 8 xfailed**. 위 §1의
147/6과의 차이는 비트 핀 2건이 스택 불일치 xfail로 내려간 것뿐이다(물리 회귀 아님).

그래서 핀 스택을 그대로 재현한 별도 venv를 만들어 다시 돌렸다.

```
인터프리터  ~/.local/share/2lfest-pin/python/bin/python3.14
            python-build-standalone 릴리스 20260325 prebuilt, sha256 검증 통과
venv        ~/.venvs/2lfest-pin        (저장소 밖, 소스 빌드 아님)
스택        python 3.14.3 / numpy 2.4.3 / scipy 1.17.1  = PINNED_STACK 완전 일치
```

`stack_mismatch()`가 `None`이 되어 **xfail이 풀리고 strict로 실행됐다.** 결과:

| 테스트 | Vb | 계산값 | 핀 값 | 상대 편차 |
|---|---|---|---|---|
| `test_default_pin` | 0 (PINS[0]) | — | — | **통과** (≤1e-8) |
| `test_default_pin` | 0.85·Voc ≈ 1.6546 (PINS[1]) | 18.2152487015721 | 18.215245612864987 | 1.70e-7 |
| `test_legacy_pin` | 0 (PINS[0]) | — | — | **통과** (≤1e-8) |
| `test_legacy_pin` | 0.85·Voc ≈ 1.6546 (PINS[1]) | 18.276313956167442 | 18.276331778124046 | 9.75e-7 |

- **Vb=0은 1e-8 안에 든다.** 바이어스가 걸리는 두 번째 지점부터 벌어진다.
- 편차 크기(상대 1e-7~1e-6)는 `conftest`가 "SuperLU·BLAS 차이만으로 뜬다"고
  적어둔 범위와 같다.
- BLAS: numpy = **Accelerate**(blas·lapack 모두, detection method: system),
  scipy = 번들 OpenBLAS, host **aarch64/darwin**.
- `conftest.py`가 matplotlib을 import하므로 venv에 matplotlib도 필요하다
  (없으면 collection 단계에서 ImportError).

**결론: `PINNED_STACK` 3종(python·numpy·scipy)은 비트 재현의 충분조건이 아니다.**
OS·BLAS/LAPACK 구현·SuperLU 빌드가 **기록되지 않는 축**으로 남아 있고, 버전만
맞춰서는 1e-8 비트 동일이 성립하지 않는다.

이번 실험에서 `PINNED_STACK`·`conftest.py`·핀 값은 **일절 수정하지 않았고**
기준값 재캡처도 하지 않았다. venv는 저장소 밖에 있어 `git status`에 잡히지 않는다.

### 1-1-a. 원 캡처 머신 환경 (2026-08-18 기록) — 편차 원인 규명됨

> 위 실험 시점에는 "원 캡처 머신 정보가 저장소에 없어" 원인을 특정하지 못했다.
> **2026-08-18 KIST PC에서 직접 수집해 아래에 기록했고, 그 결과 원인이 규명됐다.**

| 항목 | 원 캡처 PC (KIST) | 맥북 |
|---|---|---|
| OS | `Windows-11-10.0.26100-SP0` | darwin |
| 아키텍처 | **x86-64** (`AMD64`)<br>Intel64 Family 6 Model 151 Stepping 5 | **aarch64** |
| Python | `3.14.3` (`tags/v3.14.3:323c59a`, MSC v.1944 64-bit, 2026-02-03 빌드) | `3.14.3` (재현 venv) |
| numpy | `2.4.3` | `2.4.3` (재현 venv) |
| scipy | `1.17.1` | `1.17.1` (재현 venv) |
| **numpy BLAS/LAPACK** | **scipy-openblas 0.3.31.dev** (detection: pkgconfig) | **Apple Accelerate** (detection: system) |
| **scipy BLAS/LAPACK** | scipy-openblas 0.3.30 | 번들 OpenBLAS |

**규명된 원인: 버전 3종은 같았지만 아키텍처와 BLAS 구현이 달랐다.**
맥북 재현 venv는 python·numpy·scipy 버전을 완전히 맞췄으므로 `stack_mismatch()`가
`None`이 되어 strict로 돌았지만, 실제로는

1. **x86-64 ↔ aarch64** — 벡터화 폭과 FMA 사용이 다르다
2. **scipy-openblas ↔ Apple Accelerate** — numpy의 BLAS 구현 자체가 다르다

두 축이 남아 있었다. 이 둘은 부동소수점 **누적 순서**를 바꾸므로 상대 1e-7~1e-6
편차가 나오는 것이 정상이며, 실측 편차(1.70e-7 / 9.75e-7)가 정확히 그 크기다.
`Vb=0`만 통과한 것도 앞뒤가 맞는다 — 반복이 짧아 차이가 누적될 여지가 적다.

> **재캡처 시 반드시 함께 기록할 것**: OS·아키텍처·`numpy.show_config('dicts')`의
> BLAS/LAPACK name·scipy `__config__`의 BLAS name. 버전 3종만으로는 부족하다는 것이
> 위 실험으로 실증됐다.
>
> 수집 명령: `python -c "import platform,numpy,scipy; print(platform.platform(), platform.machine()); print(numpy.show_config('dicts')['Build Dependencies']); print(scipy.__config__.show('dicts')['Build Dependencies'])"`

**`PINNED_STACK` 값 자체는 이 기록으로 바뀌지 않았다.** 게이트는 여전히 버전 3종만
비교하며, 이 표는 "게이트를 통과해도 머신이 다르면 핀이 깨질 수 있다"는 사실의 근거다.

### 1-2. 머신 분담

| 머신 | 역할 | 비트 핀 |
|---|---|---|
| **맥북** (arm64, python 3.12.13) | 코딩 + 일반 회귀(**145 passed**)까지 | **감시 없음** — xfail로 내려감. 스택을 맞춰도 §1-1대로 통과하지 않는다 |
| **원 캡처 PC** | **물리 변경 머지 전 핀 확인 필수** | strict fail로 강제됨 |

**물리를 변경하는 작업 일반에 적용된다: 맥북에서 "통과"를 확인해도 검증이 끝난 것이
아니다.** 이런 작업의 검증 조건은 대개 "기존 설정에서 결과 불변"이고, 그 판정을
비트 핀이 담당하는데 맥북에서는 그 핀이 꺼져 있다. 반드시 원 캡처 PC에서 확인한 뒤
머지할 것.

§3의 구현 확정 3건 중 **우선순위 2(base lateral transport)와 우선순위 3(capacitive
effects)이 여기 해당한다** — 둘 다 솔버의 물리 경로를 바꾼다. 우선순위 1(공간 분포
입력 인터페이스)은 입력 경로만 추가하므로 해당하지 않는다.

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

### 2-6. 공간 분포 입력 인터페이스 (구 §3 우선순위 1) — 완료 ⚠ **결함 발견 (2026-08-18)**

> ## ⛔ 이 항목은 "완료"이지만 **기능은 사용 보류**다
>
> **근거: 호출 경로 (2026-08-18 확정).** 프로브 실측은 나오는 대로 이 절에 추가한다.
>
> `spatial_j01` / `spatial_j02` / `spatial_gen` 3종이 **프로덕션 tandem 설정
> 전부에서 잔차에 반영되지 않는다.** `spatial_rc` 1종만 정상이고, 단일셀은 영향
> 없다. `solve_tandem`이 배율 블록(`2L_FEST.py:4932`)보다 앞에서 디스패치하기
> 때문이다 — 네 분기(`:5224` `:5595` `:5914` `:6191`)가 `J01_top_arr`를 스칼라로만
> 만든다.
>
> **기본 설정이 결함 경로다.** `Rs_junction = 5000`(`:1916`)이 클래스 기본값이고
> Phase A는 `FEST_LEGACY_LOCAL_MATCH`로만 도달한다. 정상 동작하는 유일한 tandem
> 칸이 레거시 전용이다.
>
> **조용한 무효가 아니라 자기모순 값이다.** `cell_current`(`:6717`)가 맵을 무조건
> 적용하므로, *맵이 안 걸린 전압장*을 *맵이 걸린 다이오드 식*으로 재계산한
> 혼합물이 나온다. Δ ≠ 0이라 겉보기에 작동하는 것처럼 보인다 — `Rs_base`(v28.60)와
> **판정 함정의 방향이 반대**이고, 그쪽보다 나쁘다(값이 옛것인 게 아니라 성립하지
> 않는 값이다).
>
> 상세·16칸 표·수정 방향: `docs/spatial_map_convention.md` §6.
> 판정 하향: `docs/pro_feature_map_2026-08-14.md` #6 (구현 → 부분구현).
>
> **아래 "완료" 기록은 지우지 않는다** — 단위 0~5는 계획대로 수행됐고 로더·GUI·
> 규약·캐시 무효화는 실제로 완성됐다. 빠진 것은 **엔진 배선의 분기 커버리지**이며,
> 그것이 계획에도 테스트에도 항목으로 존재하지 않았다는 것이 이 발견의 핵심이다.

| 커밋 | 내용 |
|---|---|
| `1730653` | 단위 0 — `SpatialMap` 특성화 테스트 30건 (프로덕션 0줄) |
| `ea6aba4` | v28.56 단위 1 — 캐시 무효화 `id()` → 내용 기반 `content_key()` |
| `0cdd6ab` | v28.57 단위 2 — txt/csv 로더 `load_spatial_map_txt` |
| `48ce20f` | v28.58 단위 3 보류·규약 확정 + 단위 4 GUI 배선 |
| (이번) | 단위 5 — 문서·등록 자료 마무리 |

계획: `docs/superpowers/plans/2026-08-17-spatial-map-io.md`.
세션 기록: `docs/sessions/2026-08-18-spatial-map-io.md`(단위 0~2, 맥북) ·
`docs/sessions/2026-08-18-spatial-map-gui.md`(단위 3~5, 원 캡처 PC).

**핵심은 엔진이 이미 완성되어 있었다는 것이다.** `SpatialMap`이 5개 모드를 제공하고
`_spatial_mult`를 거쳐 접촉 컨덕턴스·J01/J02/광생성에 실제로 곱해지고 있었다. 없던
것은 **사용자가 맵을 만들 방법 하나뿐**이었다(앱 코드의 `SpatialMap(` 생성 0건).
따라서 이 작업은 물리 변경이 아니라 **입력 경로 추가**였고, 예정대로 물리식은 한 줄도
바뀌지 않았다.

> ⛔ **2026-08-18 정정 — 위 문단이 이 작업의 핵심 오판이다.**
>
> *"엔진이 이미 완성되어 있었다"* 는 **거짓이었다.** `_spatial_mult`는 `solve_tandem`의
> 인라인 폴스루 경로에서만 J01/J02/광생성에 곱해지고 있었고, 프로덕션 tandem이 실제로
> 가는 네 분기에서는 곱해지지 않았다. 접촉 컨덕턴스(`rc`)만 `_build` 안에 있어 무사했다.
>
> **왜 그렇게 판단했는가**: `_spatial_mult` 호출 지점을 세어 "소비 4곳"을 확인했다.
> 그 4곳이 **전부**라고 본 것이 틀렸다 — 세어야 했던 것은 *배율을 소비하는 곳*이 아니라
> *다이오드 배열을 조립하는 곳*이었고, 후자는 7곳이다. **있는 것을 센 것은 맞지만,
> 없는 것을 찾지 않았다.**
>
> 이 오판이 통과한 이유는 아래 "비트 핀이 통과했다"와 같은 뿌리다 — 맵이 없는 경로만
> 검증했기 때문에, 맵이 있을 때 어느 분기로 가는지는 한 번도 확인되지 않았다.

작업 중 나온 것 셋:

- **캐시 무효화가 `id()` 기반이었다** — 맵의 **주소**로 변경을 감지했다. 앱이 맵을
  만든 적이 없어 드러나지 않았을 뿐, 이 작업이 만들려는 기능이 바로 그 전제를
  깨뜨린다. GUI가 맵 하나를 두고 필드만 갱신하면 **100 % 옛 결과를 조용히 재사용**한다.
  `content_key()`(mode + 스칼라 13개 + 행렬 sha256)로 정정했다.
- **Griddler 대조는 할 수 없었다** — 무료판에 공간 분포 입력이 없다(PRO 전용). 규약을
  **자체 규약으로 확정 선언**했다(`docs/spatial_map_convention.md`).
  ⚠ **"우리 규약을 선언했다"이지 "Griddler와 일치함을 확인했다"가 아니다.** 절차서는
  PRO 확보 대비로 보존했고 기대값 8점은 테스트로 고정했다.
- **비트 핀이 원 캡처 PC에서 통과했다** — v28.56이 `_build`의 캐시 적중 판정을
  건드렸으므로 §1-2상 핀 확인 대상이었다. 258 passed / 2 deselected / **6 xfailed**
  (핀 2건이 strict 실행·통과). *"맵이 없으면 예전과 같이 0으로 태그하므로 무맵 경로는
  불변"*이 **구조적 논증이 아니라 실측으로** 확인됐다.

**남은 것: 2단계 이미지 입력(jpg/tif/bmp).** 규약이 반대라(상대값·평균 1 정규화)
별도 함수로 두기로 했고, Pillow 의존성이 등록 자료의 구성요소 기재와 얽혀 **저작권
등록 이후**로 미뤘다. 착수 시 §3의 새 항목으로 올린다.

---

## 3. 다음 할 일 (우선순위 순)

> **2026-08-17 전면 개정 — 박사님 지시.** 우선순위 1~3이 **구현 확정 3건**이다.
> 이전 §3 항목(taper / mesh 4-노드 판정기 / temperature)은 **지시 범위 밖이라
> 후순위**로 내렸다(§3-후순위). RayFlare·PC1D·cell cross-sectional model은
> **구현 불필요 확정**(§3-제외). tandem non-overlapping Jsc는 **보류**(§3-보류).
>
> 아래 "물리 변경" 표시는 §1-2 머신 분담과 직결된다 — **있음**인 항목은 원 캡처
> PC에서 비트 핀을 확인한 뒤에 머지해야 한다.
>
> **2026-08-18: 우선순위 1(공간 분포 입력)은 완료되어 §2-6으로 옮겼다.**
> 번호는 재조정하지 않는다 — 다른 문서가 "우선순위 2 = Base lateral transport"로
> 참조하고 있어 재번호하면 그 참조가 조용히 어긋난다.
>
> **2026-08-18 (2차): 우선순위 2(Base lateral transport)도 완료됐다** (v28.59 `54d55c2`
> + v28.60 `0d80ae5`). 그리고 **우선순위 0이 새로 생겼다** — 우선순위 1의 결함이다.
> 같은 이유로 번호를 재조정하지 않고 **0번**을 앞에 붙였다.

---

## ▶ 다음 착수 지점 (2026-08-18 기준)

> **여기서부터 이어서 하면 된다.**

**착수 대상: 우선순위 0 — 공간 분포 맵 분기 커버리지 수정.**

| 항목 | 값 |
|---|---|
| 계획서 | `docs/superpowers/plans/2026-08-18-spatial-map-branch-coverage.md` |
| 시작 단위 | **단위 0 (특성화, 프로덕션 0줄)** |
| 새 파일 | `tests/test_spatial_branch_coverage.py` |
| 재사용 | `tests/test_base_lateral.py`의 `BRANCH_CASES`를 **import** (복제 금지) |
| 물리 변경 | 없음 (맵 없으면 비트 동일) |
| 원 캡처 PC 필요 | **단위 1 이후에만** — 단위 0은 어디서 해도 된다 |
| 현재 HEAD | `0d80ae5` v28.60 |

**단위 0에서 할 일 (코드 수정 없음, 테스트만)**

1. `BRANCH_CASES` × `SPATIAL_TARGETS` 교차 파라미터화로 16칸 표를 테스트화
   — 판정은 **수렴 전압장**으로. `cell_current`로 판정하면 안 된다(§2-6 함정)
2. `sys.settrace` f_locals로 각 분기의 `J01_top_arr`가 배열인지 스칼라인지 고정
3. **Phase A / full_area + 맵**의 현재 값을 캡처해 파일에 박기
   — 단위 1 리팩터가 값을 안 건드렸다는 증거로 쓴다
4. 이 시점에서 테스트는 **빨간불이 정상**이다 (결함을 고정하는 것이므로)

> ### ⚠ 이 머신에 미해결 환경 결함이 있다 (2026-08-18 18:00경 발생)
>
> **`import numpy.testing`이 무한 대기한다.** 그 여파로
> `import scipy.sparse.linalg`(→ `scipy._lib.array_api_compat` → `numpy.testing`)가
> 멈추고, **테스트·프로브를 하나도 돌릴 수 없다.**
>
> | 대상 | 결과 |
> |---|---|
> | `import numpy` / `import scipy` | 각 0.1 s ✅ |
> | `import numpy.testing` | **90 s 타임아웃** ❌ |
> | `import scipy.sparse.linalg` | **90 s 타임아웃** ❌ |
>
> `-X importtime` 추적상 `numpy.testing._private.extbuild` 부근에서
> `importlib.metadata` → `tempfile` → `random` → `socket`까지 마친 뒤 멈춘다.
> **`socket` 직후**라 프록시 자동탐지(WPAD)/네트워크 대기 계열로 보이나
> **원인은 규명하지 못했다.** `no_proxy=*` 등 프록시 환경변수로는 해소되지 않는다.
> 프로세스를 전부 정리한 뒤 새 인터프리터에서도 재현된다 — **동시 실행 경합이
> 아니다**(조사 초기의 그 가설은 틀렸다).
>
> **같은 날 17:14에는 정상이었다** — 그 시각 시작한 전체 회귀가 20분 이상 실제
> 솔브를 돌렸다. 즉 저장소가 아니라 **머신 상태 변화**다. 그 회귀는 이후
> faulthandler 스택 덤프를 남기고 비정상 종료했는데, 같은 원인일 가능성이 있다.
>
> **집에서 이어받을 때**: 재부팅 후 `python -c "import numpy.testing"`이 즉시
> 끝나는지부터 확인할 것. 그게 안 되면 테스트가 한 건도 못 돈다.

---

### 우선순위 0 — 공간 분포 맵 분기 커버리지 수정 ⛔ **최우선**

**물리 변경: 없음** (맵 없으면 비트 동일). 규모: 소~중.

우선순위 1이 남긴 **결함**이다. `spatial_j01`/`j02`/`gen` 3종이 프로덕션 tandem
분기 전부에서 잔차에 미반영이고, `cell_current`가 맵을 무조건 적용해 **자기모순
값**이 나온다. **기본 설정(`Rs_junction = 5000`)이 결함 경로다.**

GUI에 이미 노출된 기능이라 우선순위가 가장 높다 — 사용자가 맵을 걸면 숫자가
바뀌므로(Δ ≠ 0) 겉보기에 작동하는 것처럼 보인다.

- 계획: `docs/superpowers/plans/2026-08-18-spatial-map-branch-coverage.md`
- 결함 상세: `docs/spatial_map_convention.md` §6 · 본 문서 §2-6
- 설계: `_diode_node_arrays` 중앙화 (소비 9곳이 같은 함수를 거치게)
- 핵심 산출물은 수정 자체가 아니라 **T1 우회 불가 검증** — 새 분기가 생겨도
  배열을 직접 조립하지 못하게 막는 테스트

### 우선순위 1 — 공간 분포 입력 인터페이스 (파일 로더 + GUI) — ✅ **완료 → §2-6** ⚠ **결함**

**2026-08-18 완료 (v28.56 ~ v28.58).** 상세·발견·남은 것은 **§2-6**에 있다.
여기에는 착수 판단에 필요한 것만 남긴다.

| 단위 | 결과 |
|---|---|
| 0 특성화 테스트 | 30건 (`SpatialMap` 테스트가 저장소에 하나도 없었다) |
| 1 캐시 무효화 | v28.56 — `id()` → 내용 기반 `content_key()` |
| 2 txt/csv 로더 | v28.57 — `load_spatial_map_txt`, 절대값 규약 |
| 3 Griddler 대조 | ⏸ **대조 불가**(무료판 미지원) → **자체 규약 확정** |
| 4 GUI 배선 | v28.58 — SPATIAL MAPS 카드 + 설정 창 |
| 5 문서 마무리 | 등록 자료·감사 문서·이 문서 갱신 |

**물리 변경 없음**이 계획대로 지켜졌고, 원 캡처 PC에서 비트 핀 2건이 strict로
통과해 무맵 경로 불변이 실측 확인됐다(§1-2).

⚠ 규약은 **선언**이지 **확인**이 아니다 — Griddler와 같은 파일이 같은 결과를 준다는
주장은 하지 않는다. PRO 확보 시 재개 절차는
`docs/crosscheck/2026-08-18-spatial-map-griddler.md` §7.

**후속으로 남은 것**: 2단계 이미지 입력(Pillow) — 저작권 등록 이후. §2-6 참조.

### 우선순위 2 — Base lateral transport (bulk 횡방향 캐리어 전류) — ✅ **완료 (2026-08-18)**

> **v28.59 `54d55c2` + v28.60 `0d80ae5`.** 아래 착수 시점 기술은 **그대로 둔다** —
> 실제 구현이 이 예상과 어떻게 달랐는지가 기록으로 남아야 한다.
>
> **예상과 달랐던 점**: 아래 "6번째 전도 평면 신설 / 3개 분기 모두 손봐야 한다"가
> **불필요했다.** β 토폴로지(후면 평면 면전도에 **병렬 합성**)로 정리되면서
> `1/Rs_eff = 1/Rs_rear_tco + 1/Rs_base` 한 줄이 됐고, `assemble_K`가 `1/Rs`에
> 선형이라 **미지 벡터가 불변**이다. 손대야 할 곳 **7 → 0**.
> 매뉴얼 Appendix A.5를 근거로 삼았던 초안의 오독(그쪽 `Rs,base`는 Ω·cm² 집중정수라
> `Rs_vert_bot` 층위다)을 정정한 기록은 계획서에 보존했다.
>
> - 규약: `docs/base_lateral_convention.md`
> - 계획: `docs/superpowers/plans/2026-08-18-base-lateral-transport.md`
> - 테스트: `tests/test_base_lateral.py` 68건. 비트 핀 2건 strict 통과.

**물리 변경: 있음.** 규모: 대.

현재 횡전도 평면은 5개다 — `_Ke`(front TCO) / `_Kr`(rear emitter) / `_Krm`(rear metal)
/ `_Km`(front metal) / `_K_junc`(interlayer). 선언부 `2L_FEST.py:3721-3730`.
**bulk 평면이 없다** — 벌크는 수직 방향으로만 다뤄지고 횡전도는 표면·금속·interlayer
평면에만 존재한다.

작업 범위:

1. **6번째 전도 평면 신설** — 조립(`assemble_K` 계열) + 미지 벡터 레이아웃(오프셋)
   + 잔차 + 야코비안. Phase B tandem 잔차가 **3개 분기**로 갈라져 있고(`_K_junc`를
   쓰는 `Kint_c` 패턴이 `2L_FEST.py:4673` / `5046` / `5365` 부근에 각각 있다)
   **세 곳 모두 손봐야 한다.** 한 곳만 고치면 경로에 따라 결과가 갈린다.
2. **입력 파라미터 신설** — 벌크 면저항 상당값. 단위계(Ω/sq vs Ω·cm)를 먼저 확정할 것.
   `Rs_junction`(횡)과 `Rc_junction`(수직)의 명명·단위 규약을 따르면 혼선이 적다.
3. GUI 입력란 + 라벨(↔ 수평 기호 규약, v28.21~28.26 참조).

- **검증 조건: 벌크 횡전도 off(=0)에서 기존과 비트 동일.** → 원 캡처 PC 필수(§1-2).
- 근거: `docs/pro_feature_map_2026-08-14.md` #8

### 우선순위 3 — Capacitive effects (I-V 스윕 과도 효과)

**물리 변경: 있음 (구조 변경).** 규모: 대 — 셋 중 가장 크다.

엔진은 **정상상태 전용**이다. 2026-08-17 재확인: `capacit`/`transient`/`sweep_rate`/
`hysteresis` 전문 검색이 엔진·테스트에서 **0건**(유일한 히트는 `solcore_xval/`의
ngspice 주석으로 무관).

작업 범위:

1. **시간 축 도입** — 지금 IV 스윕은 각 Vb에서 **독립적인** 정상상태 해를 푼다.
   과도 효과를 넣으면 해가 **이력 의존**이 되어 스윕 루프 구조 자체가 바뀐다.
2. **정전용량 모델** — 접합 용량 + 확산 용량, 노드별. 파라미터 신설.
3. **시간 적분기** — implicit 계열 + 시간 스텝 제어. 잔차·야코비안에 dV/dt 항 추가.
4. **스윕 속도 입력**(dV/dt) + 정·역방향 스윕과 이력 곡선 출력.

- ⚠ **warm-start·캐시 전제와 충돌할 수 있다.** v28.28 Phase B warm-start(2.2배)와
  `_cache_hash` 경로는 "같은 입력 → 같은 해"를 가정한다. 이력 의존이 들어오면 이
  가정이 깨지므로 **착수 전에 캐시 무효화 규칙부터 정할 것.**
- **검증 조건: dV/dt→0 극한에서 기존 정상상태 해와 비트 동일.** → 원 캡처 PC 필수(§1-2).
- 근거: `docs/pro_feature_map_2026-08-14.md` #9

### 구현 불필요 확정 (박사님 판단, 2026-08-17)

아래 3건은 **구현하지 않는다.** 감사 보고서에 "미구현"으로 적혀 있어도 격차로
취급하지 말 것.

| 항목 | 사유 |
|---|---|
| **RayFlare 광학 연동** | 랩 내부에서 **Python-CROWM**을 쓴다 |
| **PC1D 에미터 계산 연동** | 지시 범위 밖 |
| **Cell cross-sectional model** | 지시 범위 밖. J01_pass/J01_metal은 역산이 아니라 직접 입력이 현 설계 |

→ §4-1(RayFlare 연동 시점)은 이 결정으로 **해소됐다.**

### 보류 — tandem non-overlapping Jsc (박사님께 재확인 중)

이전 §3 우선순위 3의 "tandem 3종 세트"(Top Cell Position / 조도 3영역 분리 /
Non-overlapping area Jsc). **박사님 재확인 답을 받기 전에는 착수하지 말 것.**

- 내용: 실험용 tandem에서 top cell이 작은 경우가 흔하고, 제3영역(겹치지 않는 bottom)
  개념이 없으면 Jsc가 과대평가된다.
- 근거: `docs/griddler_feature_map.md` §2.12 (2026-08-14 개정본)

### 후순위 — 지시 범위 밖 (기존 항목, 내용 보존)

지시 3건이 끝난 뒤에 다시 볼 것. 분석 자체는 유효하다.

**taper 물리 연결** — `taper_factor`가 `metal_rects_front()`까지만 가고 금속 저항에
도달하지 않는다(`assemble_K_met_1d`가 스칼라 폭 하나만 받음). `shading_fraction`도
균일 폭을 가정해 확장부 면적을 누락한다. 순효과: **taper를 켜면 저항 이득 없이
재결합·접촉 손실만 늘어 항상 불리하게 나온다.** `front_electrode/`·`scripts/`·`tests/`
전체에서 `taper`/`pattern_style` 참조가 0건이라 기존 산출 수치에는 영향 없음(잠복).
검증 조건은 "h_pattern 결과 불변". 근거: `docs/audit_2026-08-13.md` §3-4,
`docs/pro_feature_map_2026-08-14.md` "taper" 절.

**mesh 4-노드 판정기** — Griddler 매뉴얼의 메시 밀도 기준(busbar 사이 finger당 최소
4노드, finger 사이 4노드)을 판정하는 코드가 없다. 현재 진단은 `mesh_quality_metrics`
(각도·aspect)와 `mesh_distribution_metrics`(대칭성·밀도 편향)뿐. `NodesPerFingerSpan` /
`NodesBetweenFingers` 두 지표를 추가하면 되고 비용이 작다. "M10과 소면적 셀의 수렴
방향이 반대" 현상을 이 기준으로 재점검할 수 있다. 근거: `docs/griddler_feature_map.md`
§2.2, `docs/audit_2026-08-13.md` §5 체크 4.

**temperature 지원** — `T = 298.15`가 모듈 상수로 하드코딩되어 있고 `n_i(T)` 스케일링이
없다. Griddler PRO는 `J01(T) = J01(25°C)·(n_i(T)/n_i(25°C))²`, `J02`는 1승. 매뉴얼이
명시한 한계도 함께 상속·문서화할 것(Jsc 온도계수, mobility 변화에 따른 면저항 변화는
Griddler도 미모델링). 부수: `_solve_tandem_junction_bf_v29`가 `VT = 0.02568`을 지역
재정의한다(전역 0.02570, 0.09 % 차이) — 온도 작업 시 함께 정리. 근거:
`docs/griddler_feature_map.md` §2.4, `docs/audit_2026-08-13.md` §4.

### 상시 — registration_material.md 서술 갱신

수치는 자동화되었으므로(§2-5) **서술만** 남았다. 등록 직전에:

```bash
python scripts/gen_registration_stats.py --from-log pytest.log --check
```
로 수치 최신성을 확인하고, 마일스톤 표에 새 버전 행을 추가하면 된다.

---

## 4. 미해결 판단 사항

### 4-1. RayFlare 연동 시점 — ✅ 해소 (2026-08-17)

> **박사님 판단으로 종결: 연동하지 않는다.** 랩 내부에서 **Python-CROWM**을 쓴다.
> 아래 조사 내용은 판단 근거로 남겨 두지만 **더 이상 미해결 항목이 아니다.**
> LGPL v3 배포 형태 문제도 함께 소멸했다. (§3-제외 참조)

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

> ⚠ 위 감사 2건의 **"미구현" = 할 일이 아니다.** 무엇이 없는지를 적은 문서이지
> 무엇을 만들지를 정한 문서가 아니다. 착수 대상은 §3이 정한다 — 감사가 미구현으로
> 적은 항목 중 3건은 §3-제외에서 **구현하지 않기로 확정**됐다.
| `docs/registration_material.md` | 저작권 등록용. 수치는 스크립트가 생성 |
| `docs/front_electrode_model_scope.md` | 전면전극 모델 범위 |
| `_experiments_README.md` | 루트 `_*_results.csv`의 실행 조건. **수치 인용 전 반드시 확인** |
| `docs/spatial_map_convention.md` | **규범 문서** — 공간 분포 파일 규약(행 방향·격자 정렬). 여기 적힌 것이 공식 규약이고 코드·테스트·GUI가 이를 따른다 |
| `docs/crosscheck/` | 외부 도구 대조 절차와 판정. 대조가 **불가능해도 절차는 보존**한다 — 도구를 확보하면 그대로 재개한다 |
| `docs/superpowers/specs/` · `plans/` | 기능별 설계·구현 계획 |
| `docs/sessions/` | 세션별 작업 기록 — **왜 그렇게 결정했는지**와 그 과정의 발견. 커밋 메시지(무엇을)·계획서(앞으로)와 역할이 다르다 |

> 매뉴얼 PDF는 저작권 문제로 저장소에 없다. 별도 보관 중이며 필요 시
> `--add-dir`로 접근한다. 이 저장소의 매뉴얼 관련 기술은 모두 **요약·재서술**이다.
