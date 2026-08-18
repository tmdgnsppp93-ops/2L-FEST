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

## 3. 다음 할 일 (우선순위 순)

> **2026-08-17 전면 개정 — 박사님 지시.** 우선순위 1~3이 **구현 확정 3건**이다.
> 이전 §3 항목(taper / mesh 4-노드 판정기 / temperature)은 **지시 범위 밖이라
> 후순위**로 내렸다(§3-후순위). RayFlare·PC1D·cell cross-sectional model은
> **구현 불필요 확정**(§3-제외). tandem non-overlapping Jsc는 **보류**(§3-보류).
>
> 아래 "물리 변경" 표시는 §1-2 머신 분담과 직결된다 — **있음**인 항목은 원 캡처
> PC에서 비트 핀을 확인한 뒤에 머지해야 한다.

### 우선순위 1 — 공간 분포 입력 인터페이스 (파일 로더 + GUI)

**물리 변경: 없음** (입력 경로만 추가). 규모: 중.

엔진 쪽은 **이미 다 되어 있다.** `SpatialMap`(`2L_FEST.py:3248`)이 5개 모드
(`uniform`/`rectangle`/`gaussian`/`checkerboard`/`csv`)를 제공하고, `_spatial_mult`
(`2L_FEST.py:3838`)를 거쳐 접촉 컨덕턴스·J01/J02/광생성·단일셀 경로에 실제로 곱해진다.

**없는 것은 사용자가 맵을 넣을 방법 하나뿐이다.** 2026-08-17 재확인: 저장소 전체에서
`SpatialMap(`을 생성하는 코드가 `_audit.py:135-145`(스모크 스크립트)뿐이고 **앱
코드에는 0건**이다. 즉 지금은 Python으로 직접 객체를 만들어 꽂는 수밖에 없다.

작업 범위:

1. **파일 로더** — txt/csv 2D 행렬 → `mode='csv'`의 `matrix` 인자로 직결되므로
   행렬을 만드는 데까지만 하면 된다. 이미지(jpg/tif/bmp)까지 받으려면 **Pillow
   의존성 추가**가 필요하고 `requirements.txt`가 함께 바뀐다.
2. **정규화 규약 결정** — 픽셀값/셀값을 어떻게 배율로 환산할지(절대값이냐 평균 1
   정규화냐). **코드보다 이 결정이 먼저다.** 규약이 바뀌면 산출 수치가 통째로 바뀐다.
3. **GUI** — 대상 물성 선택(j01 / j02 / gen / rc), 파일 선택, 미리보기.
   `_load_dxf`(`2L_FEST.py:9896`)의 `filedialog` + 검증 + 경고 패턴이 그대로 선례다.

- **검증 조건: 맵을 지정하지 않으면 기존과 비트 동일.** 기본 경로에 값을 주입하지
  않으므로 이건 설계상 성립해야 하고, 성립하지 않으면 배선이 잘못된 것이다.
- 근거: `docs/pro_feature_map_2026-08-14.md` #6 및 "비고 B"

### 우선순위 2 — Base lateral transport (bulk 횡방향 캐리어 전류)

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
| `docs/superpowers/specs/` · `plans/` | 기능별 설계·구현 계획 |
| `docs/sessions/` | 세션별 작업 기록 — **왜 그렇게 결정했는지**와 그 과정의 발견. 커밋 메시지(무엇을)·계획서(앞으로)와 역할이 다르다 |

> 매뉴얼 PDF는 저작권 문제로 저장소에 없다. 별도 보관 중이며 필요 시
> `--add-dir`로 접근한다. 이 저장소의 매뉴얼 관련 기술은 모두 **요약·재서술**이다.
