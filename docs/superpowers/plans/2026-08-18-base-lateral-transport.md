# Base Lateral Transport (벌크 횡방향 캐리어 전류) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 웨이퍼 벌크의 횡방향 다수캐리어 전도를 후면 평면의 면전도에 병렬로 더해, 지금까지 수직으로만 다뤄지던 벌크가 횡전도에도 기여하게 한다.

**Architecture:** **새 평면도 새 미지수도 만들지 않는다.** 매뉴얼 §4.3 항목 1이 *"add these bulk current **terms**"*라고 적은 그대로, 벌크를 다수캐리어 시트 하나로 환원해 `_Kr`(후면/베이스 평면)의 면전도에 **병렬 합성**한다. `assemble_K`가 `1/Rs`에 선형이므로 유효 면저항 하나를 계산해 기존 호출에 넘기면 끝이고, **미지 벡터·잔차·야코비안·분기 코드가 전부 불변**이다.

**Tech Stack:** Python ≥3.10, numpy / scipy(sparse) — **신규 의존성 없음.**

**Spec:** 규범 문서 **`docs/base_lateral_convention.md`** (단위 1 산출물). 매뉴얼 대응·코드 검증 실측·한계가 거기 있다. 이 계획서는 그 규약을 어떻게 구현할지만 다룬다.

---

## Global Constraints

- **`Rs_base` 미지정(off)에서 기존과 비트 동일.** 최종 확인은 **원 캡처 PC**(`docs/WORKLOG.md` §1-2). 이 머신이 `PINNED_STACK`과 일치함은 2026-08-18 확인됨.
- **물리 변경: 있음**(on 경로). 따라서 §1-2 머신 분담이 적용된다.
- **`assemble_K`의 시그니처를 바꾸지 않는다.** 호출 인자만 바꾼다.
- **`_Ke`(전면 TCO)에는 넣지 않는다** — 실리콘 벌크를 페로브스카이트 상부셀 전극에 얹는 셈이 된다(`docs/base_lateral_convention.md` §3-5).
- 잘못된 입력은 조용히 고치거나 무시하지 말고 `ValueError` + 진단 가능한 메시지 (v28.43·v28.54·v28.57 전례).
- 단위 유니코드 규약(Ω, ·cm², µm — v28.21~28.26). 횡전도는 `↔`, 수직은 `↕`.
- 커밋 메시지 말미에 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`

---

## 물리 변경 여부

**있음** — 단, on 경로만이다.

| 상태 | 판정 |
|---|---|
| `Rs_base is None` (off) | **비트 동일** — 원 캡처 PC 핀 확인 필수 |
| `Rs_base` 지정 (on) | 새 물리. 비트 핀이 아니라 **새 기준값 캡처 대상** |

---

## ⚠ 계획 초안의 전제 2개가 틀렸다 — 정정 기록

이 계획서는 2026-08-18에 **크게 고쳐졌다.** 초안(커밋 `a013d89`)을 읽고 작업하면
안 되므로 무엇이 왜 바뀌었는지 남긴다.

### 정정 1 — Appendix A.5는 이 기능의 수식이 아니다

초안은 A.5를 이 기능의 해석식으로 지목하고 *"A.5를 읽기 전에는 코드를 쓰지 말라"*는
게이트까지 걸었다. **오독이었다.**

A.5는 **Base Transport Calculator**(§4.3 box 4~7)의 해석식이고, 출력 `Rs,base`는
**Ω·cm² 단위의 집중정수 접촉저항**으로서 *"finger contact res under rear
metallization"* 필드에 들어간다. **즉 A.5는 `Rs_vert_bot`과 같은 층위**(수직
집중정수)이며 횡전도가 아니다.

> A.5를 따라갔다면 벌크에 **수직 결합 + 새 평면**을 넣었을 텐데, 그것은 이 기능이
> 아니라 `Rs_vert_bot`의 중복 구현이 됐을 것이다.

실제 근거는 **§4.3 항목 1**이다 — `Jn = q·μn·n·∇ε_fn`, `Jp = q·μp·p·∇ε_fp`,
근사 2개(`μ` 평형값 고정 / `n`,`p` 두께 방향 일정), 표현은 *"add these bulk current
**terms**"*.

> 초안이 A.5 위에 세웠던 게이트·질문·계획은 **삭제하지 않고**
> §~~Appendix A.5 대응~~ — 오독 정정 절에 남겼다. A.5가 실제로 무엇인지와
> 왜 이 기능의 근거가 아닌지가 거기 있다.

### 정정 2 — 토폴로지는 α(새 평면)가 아니라 β(항 추가)다

초안은 α(직렬 삽입, 6번째 평면 신설)를 권고했다. **β가 맞다.** 근거 4개는
`docs/base_lateral_convention.md` §2-3에 있고, **코드 검증도 끝났다**(같은 문서 §3).

**그 결과 초안의 가장 큰 위험이 통째로 사라졌다:**

| | 초안 (α) | 확정 (β) |
|---|---|---|
| 미지 벡터 | `Ns` += N | **불변** |
| 잔차 | 블록 신설 + `F_Vr`·`Vbot` 수정 | **불변** |
| 야코비안 | 신설 5 + 수정 4 블록 | **불변** |
| 손대야 하는 잔차 분기 | 7곳 중 2곳 지원 + 5곳 거부 | **0곳** |
| 신규 파라미터 | `Rs_base` + `Gv_base` | **`Rs_base` 하나** |
| `Rs_vert_bot` 충돌 | 발생 → 거부 판정 필요 | **발생하지 않음** |
| 특이행렬(null mode) 위험 | 있음 (`Gv_base` 하한 필요) | **없음** |
| 예상 프로덕션 | ~350줄 | **~70줄** |
| 작업 단위 | 8개 | **6개** |

**WORKLOG §3이 경고한 "3개 분기" 함정은 β에서 발생하지 않는다.** 다만 그 함정이
실재한다는 것과 우리가 그것을 우회했다는 것은 **단위 0의 21개 테스트가 계속
감시**한다 — 나중에 누가 α로 되돌리면 그 테스트들이 기준이 된다.

---

## 잔차 분기 지도 (단위 0 실측, 참고용)

β에서는 **손댈 필요가 없지만**, `_Kr` 값 변경이 어디로 전파되는지 알아야 범위를
정할 수 있다.

| # | 잔차 위치 | 메서드 | `Ns` (실측) | `_Kr` 변경 반영 |
|---|---|---|---|---|
| 1 | `:4913` | `solve_tandem` 인라인 (Phase A) | 12,980 = `3N+Nm` | ❌ Δ = 0 |
| 2 | `:5142` | `_solve_tandem_junction` (B/full_area) | 16,789 = `4N+Nm` | ❌ Δ = 0 |
| 3 | `:5520` | `_solve_tandem_junction_bf` (**B/bifacial**) | 24,942 = `4N+Nm+Nrm` | ✅ 5.0e-05 |
| 4 | `:5864` | `_v29` Schur | — | **도달 불가** |
| 5 | `:6133` | `_solve_tandem_bifacial` (**A/bifacial**) | 19,483 = `3N+Nm+Nrm` | ✅ 4.5e-06 |
| 6 | `:6310` | `solve_single` (full_area) | 9,171 = `2N+Nm` | ❌ Δ = 0 |
| 7 | `:6421` | `solve_single` (**bifacial**) | 14,024 = `2N+Nm+Nrm` | ✅ 1.8e-04 |

**Δ = 0인 세 곳은 전부 `full_area`다.** 그 모드의 `_Kr`은 `assemble_K(0.001)`
하드코딩(`2L_FEST.py:4389-4390`)이고 `Vr ≡ 0`(span 0.000e+00)이라 **`K_r`을 어떻게
바꿔도 결과가 수학적으로 불변**이다. 그래서 `full_area`는 지원 대상이 아니라
**거부 대상**이다(§설계 결정 3).

---

## 설계 결정

> 전부 `docs/base_lateral_convention.md`에서 확정됐다. 여기서는 구현에 직접
> 필요한 형태로만 옮긴다.

### 1. 단위계 — **Ω/sq 확정**

`Rs_base` [Ω/sq] 하나. 도핑·이동도·두께를 받지 않는다.

매뉴얼 근사 (2)(`n`,`p`가 두께 방향 일정)가 벌크를 **2D 시트로 환원**하므로
`σ_sheet = q(μn·n + μp·p)·w`이고, **다수캐리어 항만 취해 상수로 받는다.** 전
물리를 넣으면 이 모델에 없는 파라미터 계층(도핑·이동도 모델·`wafer_thickness`)을
신설해야 하는데 1 Sun 효과가 0.05 %p라 실익이 없다.

기존 횡전도 파라미터가 전부 Ω/sq(`Rs_junction`·`Rs_rear_tco`·`Rs_front`)라
명명·단위도 일관된다.

### 2. 합성 방식 — 병렬 합, `assemble_K` **한 번만** 호출

```
1/Rs_r_eff = 1/Rs_rear_tco + 1/Rs_base
```

`assemble_K`의 `coeff = 1/(4·A·Rs)`가 `1/Rs`에 선형이라 이것이 곧 행렬 덧셈과
같다. 다만 **수치적으로 비트 동일이 아니다**(실측 상대 3.53e-16). 따라서:

> **"항상 두 번 조립해서 더한다"로 구현하면 안 된다. 유효 면저항을 계산해
> `assemble_K`를 한 번만 부른다.** off일 때는 합성을 건너뛰어 인자가 예전과
> **같은 실수**가 되게 한다.

`Rs_rear_tco`는 솔버에서 **정확히 한 곳**(`2L_FEST.py:4341`의 `assemble_K` 호출)에서만
소비되므로 합성은 그 호출 인자에서만 한다. `dp.Rs_rear_tco` 자체는 건드리지
않는다 — GUI 표시와 캐시 해시가 사용자 입력 그대로 남아야 한다.

### 3. 적용 범위 — `bifacial` / `patterned` **만**, `full_area`는 거부

| `rear_mode` | `_Kr` | `Vr` 분포 | 판정 |
|---|---|---|---|
| `full_area` | `assemble_K(0.001)` 하드코딩 | **span = 0** (완전 등전위) | **거부** |
| `bifacial` / `patterned` | `assemble_K(Rs_rear_tco)` | span = 48.1 mV | **지원** |

`full_area`는 전면적 후면 금속 접촉이라 다수캐리어 횡이동 거리가 웨이퍼 두께뿐이고,
모델이 이미 후면을 이상적 접촉으로 둔다. `Rs_base`를 받아도 **결과가 수학적으로
불변**(실측 Δ = 0.00e+00)이므로 **조용히 아무 효과가 없다.** 그것이 이 저장소가
반복해서 거부해 온 실패 형태다.

**단일셀도 지원한다.** β에서는 `_Kr` 하나만 바뀌므로 tandem/single 구분이 무의미하고
`rear_mode`가 유일한 기준이다. (초안이 단일셀을 제외한 이유는 *"잔차 지점이 별개"*
였는데 그 이유가 사라졌다.)

### 4. `Rs_vert_bot` 충돌 — **β에서는 발생하지 않는다**

초안 §설계 결정 3은 *"`Gv_base`와 `Rs_vert_bot`이 둘 다 0이 아니면 `ValueError`"*로
확정됐었다(박사님, 2026-08-18). **β에는 `Gv_base`가 없으므로 그 충돌 자체가
발생하지 않는다.**

`Rs_base`(횡, `↔`)와 `Rs_vert_bot`(수직, `↕`)은 **서로 다른 방향의 저항이라 이중
계산이 아니다.** 동시에 켜는 것을 막지 않는다.

> 그 판정은 **폐기가 아니라 대상이 사라져 비활성**이다. 근거(이중 계산은 잘못된
> 결과이고, 흡수는 `Rs_vert_bot`의 기존 의미를 바꿔 과거 결과 재현을 깬다)는
> `docs/base_lateral_convention.md` §5에 보존했다. 나중에 `Gv_base`를 신설하게
> 되면 그대로 되살린다.

---

## 매뉴얼 근거 — §4.3 항목 1

FEM 옵션의 수식은 **§4.3 항목 1 본문**에 있다.

```
Jn = q · μn · n · ∇ε_fn
Jp = q · μp · p · ∇ε_fp
```

**매뉴얼이 명시한 근사 2개:**

1. `μn`, `μp`는 **평형값**으로 고정
2. `n`과 `p`는 **웨이퍼 두께 방향으로 일정**

**매뉴얼의 표현: "add these bulk current terms"** — *terms*이지 *unknowns*가 아니다.

이 세 가지가 각각 무엇을 결정하는가:

| 매뉴얼 | 결정하는 것 |
|---|---|
| 근사 (2) — 두께 방향 일정 | 벌크가 **2D 시트로 환원**된다 → 단위계 **Ω/sq** (§설계 결정 1) |
| *"terms"* | 자유도를 늘리지 않는다 → 토폴로지 **β** (§설계 결정 2) |
| `ε_fn` / `ε_fp` | 이미 전면/후면 평면의 미지수 → 새 준페르미 준위 불필요 |

**β를 뒷받침하는 근거 4개**(`docs/base_lateral_convention.md` §2-3):

1. `ε_fn`·`ε_fp`가 **이미 전면/후면 평면의 미지수에 대응**한다
2. 매뉴얼 표현이 **"terms"**
3. 매뉴얼이 기록한 **수렴 저하가 미지수 증가가 아니라 전압 의존 컨덕턴스로 설명**된다
4. 효과가 전압에 따라 커진다는 관측(**1 Sun 0.05 %p vs 3.6 Suns 0.11 %p**)이
   `n`의 `exp(qV/kT)` 의존으로만 설명된다 — 미지수 추가 모델로는 이 스케일링이
   나오지 않는다

> 근거 4는 **우리 한계의 출처이기도 하다.** 우리는 `Rs_base`를 전압 무관 상수로
> 받으므로 그 스케일링을 재현하지 못한다(§명시할 한계).

---

## ~~Griddler 매뉴얼 Appendix A.5 대응~~ — ⚠ **오독 정정 (2026-08-18)**

> **이 절은 삭제하지 않고 남긴다.** 초안이 무엇을 잘못 짚었는지, 그리고 A.5가
> 실제로 무엇인지 알아야 같은 실수를 반복하지 않는다. **아래 내용은 이 기능의
> 근거가 아니다** — 근거는 §4.3 항목 1이고 §매뉴얼 근거 절에 있다.

### 초안이 무엇을 주장했나

계획 초안(커밋 `a013d89`)은 **Appendix A.5를 이 기능의 해석식으로 지목**했다.
그 위에 다음을 얹었다:

- 단위 1을 *"A.5를 읽기 전에는 코드를 한 줄도 쓰지 말라"*는 **게이트**로 세웠다
- A.5에 답을 물을 **"반드시 확인할 문장 5개"**를 적었다
- A.5가 체적 비저항으로 기술하면 **두께 입력을 신설**하겠다고 계획했다
- A.5에 *"base ↔ rear 수직 결합 항이 있는가"*를 물어 **`Gv_base` 신설 여부**를
  결정하겠다고 했다

**전부 잘못된 전제 위에 있었다.**

### A.5가 실제로 무엇인가

**A.5는 Base Transport Calculator(§4.3 box 4~7)의 해석식이다.**

| 항목 | 내용 |
|---|---|
| 소속 | §4.3의 **계산기(calculator)** — FEM 옵션이 아니다 |
| 출력 | `Rs,base` |
| **단위** | **Ω·cm²** (면저항 Ω/sq가 아니다) |
| **성격** | **집중정수 접촉저항** — 분포 횡전도가 아니다 |
| 들어가는 곳 | *"finger contact res under rear metallization"* 입력 필드 |

즉 A.5는 **웨이퍼 두께 방향으로 흐르는 전류가 겪는 저항을 하나의 스칼라로
환산해 주는 도우미**이고, 그 결과는 사용자가 손으로 다른 입력란에 옮겨 적는
값이다. 시뮬레이션 방정식이 아니다.

### 왜 이 기능의 근거가 아닌가

> **A.5는 `Rs_vert_bot`과 같은 층위다.**

| | A.5의 `Rs,base` | `DiodeParams.Rs_vert_bot` | **이 기능의 `Rs_base`** |
|---|---|---|---|
| 방향 | 수직 `↕` | 수직 `↕` | **횡 `↔`** |
| 단위 | Ω·cm² | Ω·cm² | **Ω/sq** |
| 성격 | 집중정수 | 집중정수 | **분포(FEM 평면)** |
| 적용 | 접촉저항 입력란 | 터미널 IR 강하로 사후 적용 (`2L_FEST.py:1720-1729`) | **`_Kr` 면전도에 병렬 합성** |

2L-FEST에는 **이미 `Rs_vert_bot`이 그 자리를 차지하고 있다.** A.5를 따라
구현했다면 만들어질 것은 이 기능이 아니라 **`Rs_vert_bot`의 중복 구현**이었고,
초안 §설계 결정 3이 *"이중 계산"*으로 판정한 바로 그 상태가 됐을 것이다.

**초안은 자기가 만들려던 것이 자기가 금지한 것임을 알아채지 못했다.** `Gv_base`
(수직 결합) 신설과 `Rs_vert_bot` 충돌 거부 판정이 같은 계획서 안에 나란히 있었던
것이 그 징후였다 — 새로 만드는 것이 이미 있는 것과 겹친다면, 애초에 겨냥한 물리가
틀렸을 가능성을 먼저 봤어야 했다.

### 초안의 "확인할 문장 5개"에 대한 실제 답

A.5가 아니라 **§4.3 항목 1**을 읽고 답한 결과다. 초안의 질문 자체가 A.5를 전제해서
일부는 성립하지 않는다.

| # | 초안의 질문 | 실제 답 |
|---|---|---|
| 1 | A.5가 면저항인가 체적 비저항인가 | **질문이 성립하지 않는다.** A.5는 Ω·cm² 집중정수다. §4.3 항목 1의 근사 (2)가 벌크를 2D 시트로 환원하므로 **Ω/sq**가 맞다 |
| 2 | base 노드가 rear와 별개인가 | **별개가 아니다.** `ε_fn`·`ε_fp`가 이미 전면/후면 평면의 미지수에 대응한다 → **β** |
| 3 | base ↔ rear 수직 저항 항이 있는가 | **없다.** 매뉴얼 표현이 *"add these bulk current **terms**"* — 항이지 자유도가 아니다. → **`Gv_base` 불필요** |
| 4 | emitter와 같은 Galerkin 이산화인가 | **같다.** 그래서 `assemble_K`를 그대로 재사용한다 |
| 5 | A.5가 명시한 적용 한계가 있는가 | A.5는 이 기능과 무관하므로 대상이 아니다. **우리 한계는 다른 데서 온다** — 소수캐리어의 전압 의존 기여를 상수로 근사한 것(§명시할 한계) |

### 여기서 배운 것

1. **"부록에 수식이 있다"는 것과 "그 수식이 이 기능의 것이다"는 다르다.** 초안은
   기능 이름(base transport)과 부록 제목이 겹친다는 이유로 연결했다.
2. **계산기(calculator)와 시뮬레이션 방정식을 구분해야 한다.** Griddler 매뉴얼은
   §4에 계산기류를 모아 두었고, 그 출력은 **사용자가 입력란에 옮겨 적는 스칼라**다.
   FEM이 푸는 식이 아니다.
3. **단위가 신호였다.** Ω·cm²는 집중정수, Ω/sq는 분포다. 초안이 §설계 결정 1에서
   *"Ω/sq vs Ω·cm 중 무엇이냐"*를 A.5에 물었을 때, **A.5의 답이 Ω·cm²(둘 다
   아님)라는 것 자체가 A.5가 다른 물건이라는 증거**였다.
4. **새로 만들 것이 이미 있는 것과 겹치면 겨냥이 틀렸는지 먼저 의심한다.**

> **매뉴얼 접근**: PDF는 저작권상 저장소에 없다(`~/dev/refs/`, `--add-dir`).
> 이 정정은 **박사님이 맥북에서 직접 확인**해 주신 것이다(2026-08-18).

---

## off에서 비트 동일이 보장되는 근거

**β는 초안(α)보다 근거가 강하다.** α에서는 *"평면을 아예 만들지 않고 다른 솔버로
분기"*라는 **구조적** 논증이 필요했는데, β는 **산술적**으로 끝난다.

```python
# _build 안, assemble_K 호출 직전
Rs_r_eff = Rs_rear_tco
if dp.Rs_base is not None:
    Rs_r_eff = 1.0 / (1.0 / Rs_rear_tco + 1.0 / dp.Rs_base)
self._Kr, _ = assemble_K(self.pts, self.simp, Rs_r_eff, self.areas, self.b, self.c)
```

`dp.Rs_base is None`이면 **`Rs_r_eff`가 `Rs_rear_tco` 그 자체**다. `assemble_K`가
받는 인자가 예전과 완전히 동일하므로:

- 부동소수점 연산이 **하나도 추가되지 않는다** (공간 분포의 *"곱셈을 아예 하지
  않음"*과 같은 계열)
- 행렬 값이 비트 동일
- sparsity pattern·`Ns`·SuperLU 열 순열이 전부 동일
- **잔차·야코비안·분기 코드는 애초에 손대지 않았다**

> ⚠ **이 근거를 깨는 구현 3가지 — 금지한다.**
>
> | 금지 | 왜 |
> |---|---|
> | 항상 `1/(1/Rs + 1/Rs_base)`를 계산하고 off를 `Rs_base=inf`로 표현 | `1/(1/Rs + 0)`가 `Rs`와 비트 동일하다는 보장이 없다 |
> | `K(Rs_rear) + K(Rs_base)` 행렬 덧셈 | 실측 상대 3.5e-16 차이. off를 `K + 0`으로 표현해도 저장된 명시적 0이 패턴을 바꿀 수 있다 |
> | `dp.Rs_rear_tco`를 제자리 수정 | GUI 표시·캐시 해시가 사용자 입력과 어긋난다 |

### 캐시

`_build`의 해시 튜플(`2L_FEST.py:4317`)에 `Rs_base`를 넣어야 한다. 넣지 않으면
`Rs_base`만 바꿨을 때 재빌드가 일어나지 않아 **옛 `_Kr`이 조용히 재사용된다** —
v28.56이 `id()` 캐시에서 겪은 실패와 같은 형태다.

동시에 **`Rs_base is None`일 때 해시 항이 예전과 같은 값**이어야 한다. `_sm_tag`가
맵 없을 때 `0`을 넣어 무맵 경로의 캐시 거동을 보존한 것과 같은 처리다(`:4314` 주석).

---

## 작업 단위 분할

각 단위는 **종료 시점에 일관된 상태**여야 한다: 테스트 통과, 반쯤 배선된 기능 없음,
앱 실행 가능, 단독 커밋 가능.

베이스라인(2026-08-18 원 캡처 PC 실측): **279 passed / 2 deselected / 6 xfailed**
(1391 s). 비트 핀 2건 strict 통과.

---

### 단위 0 — 7개 잔차 분기 특성화 테스트 ✅ 완료 (2026-08-18, `a013d89`)

> **결과: `tests/test_base_lateral.py` 21 passed (46 s). 프로덕션 코드 0줄.**
> 특성화 테스트이므로 전부 첫 실행에 통과하는 것이 정상이다.
>
> **§잔차 분기 지도의 표가 실측으로 확인됐다.** `spsolve`를 가로채 `J.shape[0]`을
> 관측했고, 6개 live 분기가 전부 예측한 오프셋 식과 일치했다. 분기 4(`_v29` Schur)는
> 어떤 설정에서도 도달하지 않아 죽은 코드임이 확인됐다.
>
> ⚠ **`fest.spsolve` 하나만 패치하면 절반이 새어 나간다.**
> `_solve_tandem_junction`(`:5041`) · `_solve_tandem_junction_bf`(`:5392`) ·
> `_v29`(`:5733`)는 **메서드 안에서 다시 import** 하므로 모듈 전역 패치가 무시된다.
> `scipy.sparse.linalg.spsolve`도 함께 패치해야 한다.
>
> **계획 대비 편차**: `_observed_Ns`를 *"결과 dict 평면 길이 합산"*으로 계획했으나
> `solve()` 반환 dict에 `Vrm`이 없어(`:6512` 부근) 쓸 수 없다. `spsolve` 훅으로 바꿨다.
>
> **β 확정 후에도 이 21건은 그대로 유효하다.** 손댈 분기가 0곳이 되었으므로 역할이
> *"작업 대상 지도"*에서 **"β 전제의 회귀 감시"**로 바뀌었다 — `Ns`가 변하면 누군가
> α로 되돌린 것이고, 그러면 β의 비트 동일 근거가 무너진다.

**확정된 헬퍼 계약** (`tests/test_base_lateral.py`에 구현됨. 단위 1~5가 그대로 쓴다):

```python
PARAMS = dict(rm=3e-6, hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)
VB = 0.5

_build_args(dp)                                         -> dict   # _build(**_build_args(dp))
_solve(m, dp, Vb=VB, mode="tandem")                     -> dict
_cell_current(m, dp, Vb=VB, mode="tandem")              -> float
_probe(fest, m, dp, monkeypatch, Vb=VB, mode=...)       -> (branch_name, ns_tuple)
_observed_Ns(fest, m, dp, monkeypatch, Vb=VB, mode=...) -> int
_plane_sizes(m)                                         -> (N, Nm, Nrm)
_dp(fest, rs_junction=None)                             -> DiodeParams
```

> `_probe`·`_observed_Ns`는 `monkeypatch`를 받는다(`spsolve`를 가로채므로).
> `_cell_current`는 안 받는다.

---

### 단위 1 — 규약 확정 (문서, 프로덕션 코드 0줄) ✅ 완료 (2026-08-18)

> **산출물: `docs/base_lateral_convention.md`** — 확정 6항목 · 매뉴얼 대응 ·
> 코드 검증 실측 · 한계 명시. 테스트 8건 추가(21 → **29 passed**).
>
> 초안의 *"Appendix A.5 게이트"*는 오독이었으므로 제거했다(§정정 1). 실제 근거는
> §4.3 항목 1이고 그것은 이미 확보되어 있었다.
>
> **코드 검증 4건을 실측으로 끝냈다** — 가설이 아니라 측정이다:
> `assemble_K` 선형성(상대 3.53e-16, 비트 동일 아님) · sparsity pattern 불변
> (nnz 25,905 동일) · `_Kr` 변경이 bifacial 3분기에 전파되고 full_area 3분기에는
> Δ = 0 · `full_area`의 `Vr` span = 0.000e+00.
>
> 이 검증이 없었으면 β를 *"그럴듯한 가설"*로만 두고 단위 2를 시작했을 것이고,
> **`full_area`에서 아무 효과가 없다는 사실은 사용자가 발견**했을 것이다.

- [ ] **Step 1: 규약 문서의 실측값을 테스트로 고정한다**

규약 문서 §3의 숫자는 **설계의 근거**다. 코드가 바뀌어 그 숫자가 달라지면 규약이
무효가 되는데, 문서만으로는 알 수 없다.

```python
def test_assemble_K_is_linear_in_sheet_conductance(fest, make_mono):
    """β의 수학적 근거 — 병렬 합성 = 행렬 덧셈.

    assemble_K의 coeff = 1/(4·A·Rs)가 1/Rs에 선형이라 성립한다. 이것이 깨지면
    "유효 면저항 한 번 계산"이 "두 평면을 더한 것"과 달라져 규약이 무효가 된다.
    """
    m = make_mono()
    Ka, _ = fest.assemble_K(m.pts, m.S.simp, 50.0, m.S.areas, m.S.b, m.S.c)
    Kb, _ = fest.assemble_K(m.pts, m.S.simp, 500.0, m.S.areas, m.S.b, m.S.c)
    Kp, _ = fest.assemble_K(m.pts, m.S.simp, 1.0 / (1 / 50.0 + 1 / 500.0),
                            m.S.areas, m.S.b, m.S.c)
    d = abs((Ka + Kb).tocsr() - Kp)
    assert (d.max() if d.nnz else 0.0) / abs(Kp).max() < 1e-14


def test_assemble_K_sparsity_is_independent_of_sheet_resistance(fest, make_mono):
    """패턴이 같아야 Ns·SuperLU 열 순열이 같다 — β의 구조적 근거."""
    m = make_mono()
    Ka, _ = fest.assemble_K(m.pts, m.S.simp, 50.0, m.S.areas, m.S.b, m.S.c)
    Kb, _ = fest.assemble_K(m.pts, m.S.simp, 500.0, m.S.areas, m.S.b, m.S.c)
    assert Ka.shape == Kb.shape and Ka.nnz == Kb.nnz
    assert np.array_equal(Ka.indices, Kb.indices)
    assert np.array_equal(Ka.indptr, Kb.indptr)


def test_full_area_rear_plane_is_an_ideal_equipotential(fest, make_mono):
    """full_area를 거부하는 근거 — Vr ≡ 0이라 K_r을 바꿔도 결과가 불변이다.

    이 성질이 깨지면(후면을 실제 면저항으로 바꾸면) full_area도 지원 대상이
    되므로 규약 §3-4를 다시 판정해야 한다.
    """
    m = make_mono()
    Vr = np.asarray(_solve(m, _dp(fest, 100.0))["Vr"])
    assert float(Vr.max() - Vr.min()) == 0.0


def test_full_area_result_is_insensitive_to_rear_plane(fest, make_mono):
    """full_area에서 _Kr을 2배로 해도 전류가 비트 동일하다.

    _build는 _cache_hash가 같으면 조기 반환하므로, 여기서 평면을 직접 바꾸면
    다음 solve가 그 값을 그대로 쓴다.
    """
    m = make_mono()
    dp = _dp(fest, 100.0)
    j0 = _cell_current(m, dp)
    m.S._Kr = (m.S._Kr * 2.0).tocsr()
    assert _cell_current(m, dp) == j0


def test_bifacial_rear_plane_carries_a_real_lateral_drop(fest, make_bifacial):
    """bifacial은 반대다 — Vr에 실제 전압강하가 있어 벌크 전도가 의미를 갖는다."""
    m = make_bifacial()
    Vr = np.asarray(_solve(m, _dp(fest, 100.0))["Vr"])
    assert float(Vr.max() - Vr.min()) > 1e-3
```

추가로 **`Rs_rear_tco`가 후면 평면에만 쓰이는지**(다른 강성행렬에 새지 않는지)를
조립된 행렬 직접 비교로 확인하고, 아래 함정도 함께 고정한다.

- [ ] **Step 2: 실행 — 그리고 여기서 함정 하나가 나왔다**

Run: `python -m pytest tests/test_base_lateral.py -q`
Expected: PASS

> ⚠ **평면을 손으로 갈아 끼우는 테스트는 warm-up solve를 먼저 해야 한다.**
> 처음 쓴 `test_rear_tco_feeds_only_the_rear_plane`이 여기서 실패했고, 원인이
> 모델이 아니라 **연속법 램프**였다.
>
> `Rs_junction > 50`이면 `solve_tandem`이 `[50, 200, 1000, 5000, target]`으로
> 램프하며 **각 단계마다 `_build`를 부른다**(`2L_FEST.py:4713-4726`). 그 호출은
> `Rs_junction`이 달라 캐시 해시가 어긋나므로 **전체 재빌드**가 일어나고, 손으로
> 넣은 `_Kr`이 버려진다. warm-start 캐시가 있으면 램프를 통째로 건너뛰므로(`:4713`)
> 살아남는다.
>
> 실측: warm-up 없음 → 교체분 **버려짐** / warm-up 있음 → **살아남음**.
> `test_hand_patched_plane_is_discarded_without_warmup`이 이 성질을 고정한다.
>
> **단위 2~4가 평면을 직접 조작하는 테스트를 쓸 때 반드시 지킬 것.** 모르고 쓰면
> *"평면을 바꿨는데 결과가 안 변한다"*를 모델 성질로 오해하게 된다.
>
> 이 사건이 `full_area` 판정에도 교훈을 준다 — 실제로 결과가 안 변하는 경우
> (`full_area`)와 조작이 무효화된 경우(램프 재빌드)가 **겉보기에 똑같다.**
> 그래서 §3-4의 근거를 "전류가 안 변한다"가 아니라 **"`Vr` span = 0"**이라는
> 독립적인 사실로 잡았다.

- [ ] **Step 3: 커밋**

```bash
git add docs/base_lateral_convention.md \
        docs/superpowers/plans/2026-08-18-base-lateral-transport.md \
        tests/test_base_lateral.py
git commit -m "docs: 벌크 횡전도 규약 확정 (β 토폴로지) + A.5 오독 정정"
```

**회귀 영향 범위: 없음.** 문서 + 테스트.

---

### 단위 2 — `Rs_base` 신설 + `_Kr` 병렬 합성 (구현 전체)

**β에서는 이 단위가 구현의 전부다.** 초안의 단위 2~5(파라미터 / 분기 2 / 분기 3 /
거부)가 여기와 단위 3으로 합쳐진다.

**Files:**
- Modify: `2L_FEST.py:1786` 부근(`DiodeParams.Rs_base`), `:4299` 부근(검증 + 유효 면저항), `:4317`(캐시 해시), `:4341`(`assemble_K` 호출 인자)
- Test: `tests/test_base_lateral.py`

**Interfaces:**
- Produces: `DiodeParams.Rs_base = None` (Ω/sq, 기본값 = off)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

```python
def test_rs_base_defaults_to_none(fest):
    assert fest.DiodeParams.Rs_base is None


def test_base_off_is_bit_identical(fest, make_bifacial):
    """**off는 assemble_K 인자를 건드리지 않는다.**

    Rs_base is None이면 Rs_r_eff가 Rs_rear_tco 그대로이므로 부동소수점 연산이
    하나도 추가되지 않는다 — 공간 분포의 "곱셈을 아예 하지 않음"과 같은 계열.
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    j0 = _cell_current(m, dp)
    dp.Rs_base = None
    assert _cell_current(m, dp) == j0          # 비트 동일


def test_base_on_matches_parallel_sheet_resistance(fest, make_bifacial):
    """벌크 500 Ω/sq를 켠 결과 == 후면 TCO를 병렬 합성값으로 바꾼 결과.

    규약 §1의 4번(병렬 합)을 직접 고정한다.
    """
    m1, m2 = make_bifacial(), make_bifacial()
    dp1 = _dp(fest, 100.0); dp1.Rs_base = 500.0
    dp2 = _dp(fest, 100.0)
    dp2.Rs_rear_tco = 1.0 / (1.0 / dp2.Rs_rear_tco + 1.0 / 500.0)
    assert _cell_current(m1, dp1) == pytest.approx(_cell_current(m2, dp2),
                                                   rel=1e-12)


def test_base_does_not_mutate_user_rear_tco(fest, make_bifacial):
    """dp.Rs_rear_tco는 사용자 입력 그대로 남아야 한다 (GUI 표시·캐시 해시)."""
    m = make_bifacial()
    dp = _dp(fest, 100.0); dp.Rs_base = 500.0
    before = dp.Rs_rear_tco
    _solve(m, dp)
    assert dp.Rs_rear_tco == before


def test_base_change_invalidates_build_cache(fest, make_bifacial):
    """Rs_base를 바꿨는데 재빌드가 안 되면 옛 _Kr이 조용히 재사용된다 —
    v28.56이 id() 캐시에서 겪은 실패와 같은 형태다."""
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    m.S._build(**_build_args(dp))
    h0 = m.S._cache_hash
    dp.Rs_base = 500.0
    m.S._build(**_build_args(dp))
    assert m.S._cache_hash != h0


def test_base_none_keeps_cache_tag_unchanged(fest, make_bifacial):
    """맵 없을 때 _sm_tag가 0인 것과 같은 처리 — off 경로의 캐시 거동 보존."""
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    m.S._build(**_build_args(dp))
    h0 = m.S._cache_hash
    dp.Rs_base = None
    m.S._build(**_build_args(dp))
    assert m.S._cache_hash == h0


def test_unknown_layout_unchanged_by_base(fest, make_bifacial, monkeypatch):
    """**β의 핵심** — 벌크를 켜도 미지 벡터가 변하지 않는다."""
    m = make_bifacial()
    N, Nm, Nrm = _plane_sizes(m)
    dp = _dp(fest, 100.0)
    assert _observed_Ns(fest, m, dp, monkeypatch) == 4 * N + Nm + Nrm
    dp.Rs_base = 500.0
    assert _observed_Ns(fest, m, dp, monkeypatch) == 4 * N + Nm + Nrm


@pytest.mark.parametrize("bad", [0.0, -1.0, float("nan"), float("inf")])
def test_base_rejects_non_positive_or_non_finite(fest, make_bifacial, bad):
    """면저항은 유한하고 양수여야 한다. 0은 무한 컨덕턴스라 물리적으로 성립하지
    않고, assemble_K의 coeff = 1/(4·A·Rs)가 0으로 나눈다(:2649)."""
    m = make_bifacial()
    dp = _dp(fest, 100.0); dp.Rs_base = bad
    with pytest.raises(ValueError) as exc:
        _solve(m, dp)
    assert "Rs_base" in str(exc.value)
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_base_lateral.py -q -k base`
Expected: FAIL — `AttributeError: type object 'DiodeParams' has no attribute 'Rs_base'`

- [ ] **Step 3: 최소 구현**

```python
# DiodeParams — 2L_FEST.py:1786 Rs_rear_tco 옆
    # 벌크 횡전도 면저항 [Ω/sq, ↔]. None = 끔(기존과 비트 동일).
    # 후면 평면(_Kr)의 면전도에 **병렬**로 더해진다 — 새 평면·새 미지수 없음.
    # 매뉴얼 §4.3 항목 1의 "add these bulk current terms"에 대응.
    # 수직 성분은 Rs_vert_bot(↕)이며 층위가 다르다 — 이중 계산이 아니다.
    # 규약·한계: docs/base_lateral_convention.md
    Rs_base = None

# _build — Rs_rear_tco를 읽는 :4299 부근
        Rs_base = dp.Rs_base
        if Rs_base is not None:
            if not np.isfinite(Rs_base) or Rs_base <= 0:
                raise ValueError(
                    f"Rs_base는 유한하고 양수인 면저항이어야 한다 [Ω/sq] "
                    f"(받은 값 {Rs_base!r}). 끄려면 None으로 둘 것.")

# 캐시 해시 — :4317
        h = (rm, hf, wf, wb_case, rc, rc_rear, Rs_front, cf,
             Rs_rear_metal_auto, Rs_rear_tco, Rs_j,
             (Rs_base if Rs_base is not None else 0), _sm_tag)

# 후면 평면 조립 — :4341
            Rs_r_eff = Rs_rear_tco
            if Rs_base is not None:
                # 면전도 병렬 합. assemble_K는 1/Rs에 선형이라 이것이 곧
                # "K(TCO) + K(bulk)"와 같다(규약 §3-1). 다만 비트 동일이
                # 아니므로 **여기서 한 번만** 조립한다.
                Rs_r_eff = 1.0 / (1.0 / Rs_rear_tco + 1.0 / Rs_base)
            self._Kr, _ = assemble_K(
                self.pts, self.simp, Rs_r_eff, self.areas, self.b, self.c)
```

- [ ] **Step 4: 통과 확인**

Run: `python -m pytest tests/test_base_lateral.py -q`
Expected: PASS

- [ ] **Step 5: 비트 핀 확인 (원 캡처 PC 필수)**

Run: `python -m pytest tests/test_default_pin.py tests/test_legacy_pin.py -q`
Expected: **2 passed** (xfail 아님). 깨지면 해시 튜플 변경이 off 경로의 캐시 거동을
바꾼 것이다.

- [ ] **Step 6: 전체 스위트 + 커밋**

```bash
python -m pytest -q -m "not slow"        # 279+N passed / 2 deselected / 6 xfailed
git add 2L_FEST.py tests/test_base_lateral.py
git commit -m "v28.59: 벌크 횡전도 — 후면 평면 면전도에 병렬 합성 (미지 벡터 불변)"
```

**회귀 영향 범위:** `_build`의 캐시 해시 + 후면 평면 조립 인자. **`Rs_base is None`
경로는 `assemble_K` 인자가 이전과 동일**하므로 비트 동일. 잔차·야코비안·분기 코드
무변경.

---

### 단위 3 — `full_area` 거부 게이트 🔒

**조용한 무효를 오류로 바꾼다.** `full_area`에서 `Rs_base`는 결과를 전혀 바꾸지
않는다(실측 Δ = 0.00e+00) — 알려주지 않으면 사용자는 *"켰는데 안 변한다"*를 겪는다.

**Files:**
- Modify: `2L_FEST.py:4299` 부근 (단위 2의 검증 블록에 이어서)
- Test: `tests/test_base_lateral.py`

- [ ] **Step 1: 실패하는 테스트**

```python
def test_full_area_rejects_base_lateral(fest, make_mono):
    """full_area는 후면을 이상적 접촉으로 두므로 벌크 횡전도를 표현할 수 없다.

    조용히 무시하면 "켰는데 결과가 안 변한다"로 나타난다 — 오류도 경고도 없이.
    v28.43 · v28.54 · v28.57과 같은 판단: 거부하고 길을 알려준다.
    """
    m = make_mono()
    dp = _dp(fest, 100.0); dp.Rs_base = 500.0
    with pytest.raises(ValueError) as exc:
        _solve(m, dp)
    msg = str(exc.value)
    assert "Rs_base" in msg
    assert "full_area" in msg
    assert "bifacial" in msg or "patterned" in msg     # 어떻게 하면 되는지
    assert "None" in msg                                # 끄는 방법


def test_full_area_is_silent_when_base_is_off(fest, make_mono):
    """Rs_base가 None이면 full_area도 예전처럼 조용히 잘 돈다."""
    m = make_mono()
    assert _cell_current(m, _dp(fest, 100.0)) > 0


def test_single_mode_bifacial_supports_base(fest, make_bifacial):
    """단일셀도 rear_mode만 맞으면 지원한다 — β에서는 tandem/single 구분이 없다."""
    m = make_bifacial()
    dp = fest.DiodeParams()
    j0 = _cell_current(m, dp, mode="single")
    dp.Rs_base = 500.0
    assert _cell_current(m, dp, mode="single") != j0
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_base_lateral.py -q -k full_area_rejects`
Expected: FAIL (아무것도 안 던진다)

- [ ] **Step 3: 게이트 구현**

```python
        if Rs_base is not None and self.geo.rear_mode not in ('bifacial',
                                                              'patterned'):
            raise ValueError(
                f"벌크 횡전도(Rs_base={Rs_base} Ω/sq)는 rear_mode="
                f"{self.geo.rear_mode!r}에서 표현할 수 없다. full_area는 후면을 "
                f"이상적 접촉(0.001 Ω/sq, V_rear ≡ 0)으로 두므로 후면 평면의 "
                f"면전도를 바꿔도 결과가 수학적으로 변하지 않는다. "
                f"rear_mode를 'bifacial'/'patterned'로 두거나 Rs_base=None으로 "
                f"끌 것. (docs/base_lateral_convention.md §3-4)")
```

- [ ] **Step 4: 통과 확인 → 비트 핀 → 전체 스위트 → 커밋**

```bash
python -m pytest tests/test_base_lateral.py -q
python -m pytest tests/test_default_pin.py tests/test_legacy_pin.py -q
python -m pytest -q -m "not slow"
git commit -m "v28.60: 벌크 횡전도 — full_area 거부 게이트 (조용한 무효 제거)"
```

**회귀 영향 범위:** `_build` 진입부 가드 1개. `Rs_base is None`이면 비교 하나가
추가될 뿐 부동소수점 연산은 없다.

---

### 단위 4 — 물리 검증 (프로덕션 코드 0줄)

- [ ] **Step 1: 극한 3개**

```python
def test_base_infinite_sheet_r_approaches_off(fest, make_bifacial):
    """Rs_base → ∞ (벌크 횡전도 없음)이면 off와 같은 답에 수렴한다.

    비트 동일은 기대하지 않는다 — 1/(1/Rs + 1/1e12)가 Rs와 비트 동일하지 않다.
    물리적 동등성 수준의 일치를 본다(registration_material.md §5-1의 두 층 구분).
    """
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    j_off = _cell_current(m, dp)
    dp.Rs_base = 1e12
    assert _cell_current(m, dp) == pytest.approx(j_off, rel=1e-9)


def test_base_lower_sheet_r_raises_current(fest, make_bifacial):
    """벌크 횡전도가 좋아지면 후면 저항 손실이 줄어 전류가 오른다."""
    m = make_bifacial()
    dp = _dp(fest, 100.0)
    dp.Rs_base = 1000.0
    j_weak = _cell_current(m, dp)
    dp.Rs_base = 50.0
    j_strong = _cell_current(m, dp)
    assert j_strong > j_weak


def test_base_equal_to_tco_halves_effective_sheet_r(fest, make_bifacial):
    """Rs_base == Rs_rear_tco이면 유효 면저항이 정확히 절반이 된다."""
    m1, m2 = make_bifacial(), make_bifacial()
    dp1 = _dp(fest, 100.0); dp1.Rs_base = dp1.Rs_rear_tco
    dp2 = _dp(fest, 100.0); dp2.Rs_rear_tco = dp2.Rs_rear_tco / 2.0
    assert _cell_current(m1, dp1) == pytest.approx(_cell_current(m2, dp2),
                                                   rel=1e-12)
```

- [ ] **Step 2: 손실 배분 — 에너지 균형**

`losses()`·FF 워터폴이 후면 평면 손실을 이미 세고 있으므로 **벌크는 그 항에
흡수된다.** 별도 항목을 만들지 않는다 — 물리적으로 같은 평면의 전도이기 때문이다.
`tests/test_invariants.py:65,79`의 에너지 균형을 벌크 on 조건으로 파라미터화해 합이
맞는지 확인한다.

> ⚠ **보고에서 "벌크 손실"을 따로 떼어 말할 수 없다**는 뜻이다. 규약 문서와 등록
> 자료에 이 사실을 적는다.

- [ ] **Step 3: 새 기준값 캡처 (원 캡처 PC)**

on 경로는 새 물리이므로 새 핀 대상이다. `PINNED_STACK`·OS·아키텍처·BLAS를 **함께
기록**한다(`docs/WORKLOG.md` §1-1-a 요구사항).

- [ ] **Step 4: 커밋**

**회귀 영향 범위: 없음.** 테스트만.

---

### 단위 5 — GUI + 문서·버전 마무리

- [ ] **Step 1: GUI 입력란**

REAR DESIGN 카드의 `Rear Sheet R ↔` 바로 아래에 `Bulk R ↔` [Ω/sq]. **빈칸 =
off(`None`)**. `Rs_vert_bot`(`↕`)과 기호로 대비된다.

i18n 키 EN/KR 양쪽. 힌트에 **두 가지**를 적는다:

1. `Rs_vert_bot`(수직)과 다르다 — 이중 계산이 아니다
2. **`full_area`에서는 쓸 수 없다** — 입력란을 `rear_mode`에 따라 비활성화하고
   `(bifacial only)` 라벨을 단다. v28.54 `extraction_method`의 처리와 같다

- [ ] **Step 2: 문서**

| 문서 | 갱신 |
|---|---|
| `2L_FEST.py` 헤더 changelog + `__build__` | 최종 확인 |
| `docs/base_lateral_convention.md` | 구현과 일치 확인 |
| `docs/pro_feature_map_2026-08-14.md` #8 | **미구현 → 구현(범위·근사 명시)**. 개정 이력 표에 줄 추가. #6에서 *"자체 규약"*을 명시한 것과 같은 이유로 **"저주입 극한 한정 · full_area 미지원"**을 판정 문구에 넣는다 |
| `docs/registration_material.md` | §2-5 기능 목록 + §7 한계(**소수캐리어 전압 의존 미모델링 · full_area 미지원 · 벌크 손실 분리 불가**) + 수치 재생성 |
| `docs/WORKLOG.md` | §3 우선순위 2 → §2-7 완료 이동. **번호 재조정 금지** |
| `docs/sessions/` | 세션 기록 |

- [ ] **Step 3: 등록 자료 수치 재생성**

```bash
python -m pytest -q -m "not slow" > pytest.log
python scripts/gen_registration_stats.py --from-log pytest.log --write
python scripts/gen_registration_stats.py --from-log pytest.log --check
```

- [ ] **Step 4: 커밋**

**회귀 영향 범위:** GUI 레이아웃(`_gui_i18n_check.py`) + `tests/test_gui_layout.py`.

---

## 명시할 한계 (규약 문서 §4 — 코드 주석·GUI·등록 자료에 상속)

> **소수캐리어의 전압 의존 기여는 모델링하지 않는다. 따라서 저주입 극한에서만
> Griddler와 대응하며, 집광 조건의 고주입 효과는 재현하지 않는다.**

- `Rs_base`를 **전압 무관 상수**로 받는다. 실제로는 `n`이 `exp(qV/kT)`로 커져
  고주입에서 시트 컨덕턴스가 오른다.
- 그래서 Griddler가 보고한 전압 의존성(**1 Sun 0.05 %p → 3.6 Suns 0.11 %p**)의
  **증가분을 재현하지 못한다.** 1 Sun 근처에서 맞춘 `Rs_base`는 집광 조건에서 벌크
  전도를 과소평가한다(= 손실 과대평가, **보수적 방향**).
- **`full_area`에서는 지원하지 않는다** — 모델이 후면을 이상적 접촉으로 두기 때문.
- **벌크 손실을 손실 배분에서 따로 떼어 보고할 수 없다** — 후면 평면 손실에 흡수된다.

---

## 미해결

**없다.** 초안의 미해결 5건은 전부 종결됐다.

| # | 항목 | 결과 |
|---|---|---|
| 1 | 단위계 | ✅ Ω/sq 확정 (근사 (2)가 2D 시트로 환원) |
| 2 | 토폴로지 | ✅ β 확정 + **코드 검증 완료** |
| 3 | `Rs_vert_bot` 이중 계산 | ✅ β에서 **발생하지 않음** (`Gv_base` 부재) |
| 4 | `Gv_base` 하한 | ✅ **대상 소멸** |
| 5 | 단일셀 지원 | ✅ **지원**. β에서는 `rear_mode`만이 기준이다 |

**새로 확정된 것 1건**: `full_area` 미지원 — 초안에 없던 항목이며 코드 검증에서
나왔다.

---

## 예상 규모

| 단위 | 프로덕션 | 테스트 | 문서 | 비트 핀 |
|---|---|---|---|---|
| 0 특성화 ✅ | 0줄 | 21건 | — | 불필요 |
| 1 규약 ✅ | 0줄 | **8건** | 신규 1 + 계획 재작성 | 불필요 |
| 2 구현 | **~20줄** | ~9건 | changelog | **필수** |
| 3 거부 | ~10줄 | ~3건 | changelog | **필수** |
| 4 물리 검증 | 0줄 | ~6건 | — | 새 핀 |
| 5 GUI·문서 | ~40줄 | ~3건 | 5개 문서 | 불필요 |

> 초안(α)의 예상 프로덕션은 **~350줄**이었다. **β는 ~70줄이다.** 차이는 전부 잔차·
> 야코비안·오프셋 수술이고, 그것을 없앤 것이 매뉴얼 §4.3 항목 1의 **"terms"** 한
> 단어다.
