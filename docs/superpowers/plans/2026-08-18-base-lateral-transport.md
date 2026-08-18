# Base Lateral Transport (벌크 횡방향 캐리어 전류) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 웨이퍼 벌크(base)의 횡방향 다수캐리어 전류를 6번째 전도 평면으로 신설해, 지금까지 수직으로만 다뤄지던 벌크가 횡전도에도 기여하게 한다.

**Architecture:** 현재 횡전도 평면은 5개다 — `_Ke`(front TCO) / `_Kr`(rear emitter) / `_Km`(front metal) / `_Krm`(rear metal) / `_K_junc`(interlayer). 벌크 평면은 없다. 신설 평면 `_K_base`는 **기존 평면과 같은 `assemble_K` 기계**(면저항 → Galerkin 강성)를 그대로 쓰되, **미지 벡터에 N개 자유도를 추가**하므로 잔차·야코비안·BC·warm-start 레이아웃이 전부 영향을 받는다. 끄면(`Rs_base = None`) **평면을 아예 만들지 않고 기존 솔버로 분기**한다 — `_K_junc`의 Phase A/B 분기와 같은 구조다.

**Tech Stack:** Python ≥3.10, numpy / scipy(sparse, SuperLU) — **신규 의존성 없음**.

**Spec:** 별도 스펙 문서 없음. 요구사항은 `docs/WORKLOG.md` §3 우선순위 2와 2026-08-18 박사님 지시이며, 설계 결정은 이 계획서 §설계 결정에 흡수했다 (공간 분포 계획 `2026-08-17-spatial-map-io.md`와 같은 방식).

---

## Global Constraints

- **벌크 횡전도 off에서 기존과 비트 동일.** 최종 확인은 **원 캡처 PC**(`docs/WORKLOG.md` §1-2). 이 머신이 `PINNED_STACK`과 일치함은 2026-08-18 확인됨.
- **물리 변경: 있음.** 따라서 §1-2 머신 분담이 적용되고, 맥북 초록불은 검증 완료가 아니다.
- **`SpatialMap.evaluate()`·`assemble_K`의 기존 시그니처를 바꾸지 않는다.** 새 평면은 `assemble_K`를 **호출**하지 확장하지 않는다.
- 잘못된 입력은 조용히 고치거나 무시하지 말고 `ValueError` + 진단 가능한 메시지 (v28.43 `n_probe_points=0`, v28.54 `extraction_method`, v28.57 로더 전례).
- 신규 `.py` 파일에는 저장소 SPDX 헤더.
- 단위 유니코드 규약 준수(Ω, ·cm², µm — v28.21~28.26). 횡전도는 `↔`, 수직은 `↕` (기존 라벨 규약).
- 커밋 메시지 말미에 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`
- **단위 1(단위계·토폴로지 확정) 이전에는 프로덕션 코드를 한 줄도 쓰지 않는다.**

---

## 물리 변경 여부

**있음.** 이 계획은 새 전도 경로를 솔버에 넣는다 — 지금까지 없던 물리다.

| 상태 | 판정 |
|---|---|
| `Rs_base` 미지정(off) | **기존과 비트 동일이어야 한다** — 원 캡처 PC 핀 확인 필수 |
| `Rs_base` 지정(on) | 새 물리. 비트 핀 대상이 아니라 **새 기준값 캡처 대상** |

v28.56(캐시 판정 변경)과 성격이 다르다. 그때는 "무맵 경로 불변"만 확인하면 됐지만, 여기서는 **on 경로의 물리적 타당성**까지 별도로 논증해야 한다(단위 6의 극한 검증).

---

## ⚠ 이 작업의 핵심 함정 — 잔차 분기는 3개가 아니라 **7개**다

`docs/WORKLOG.md` §3이 *"Phase B tandem 잔차가 3개 분기로 갈라져 있고 세 곳 모두 손봐야 한다"*고 경고한다. **착수 전 재조사 결과, 그 경고는 옳지만 숫자가 과소평가되어 있다.** WORKLOG가 센 3개는 `_K_junc`를 쓰는 분기이고, 미지 벡터 레이아웃을 독립적으로 조립하는 잔차 지점은 **총 7곳**이다.

| # | 잔차 위치 | 메서드 (정의 줄) | `Ns` | 평면 구성 | Phase | 이 계획에서 |
|---|---|---|---|---|---|---|
| 1 | `2L_FEST.py:4913` | `solve_tandem` 인라인 (`:4679`) | `3N+Nm` (`:4747`) | Ve, Vm, Vtop, Vr | A / full_area | **거부**(단위 5) |
| 2 | `2L_FEST.py:5142` | `_solve_tandem_junction` (`:5017`) | `4N+Nm` (`:5044`) | + Vint | **B / full_area** | **지원**(단위 3) |
| 3 | `2L_FEST.py:5520` | `_solve_tandem_junction_bf` (`:5378`) | `4N+Nm+Nrm` (`:5395`) | + Vrm | **B / bifacial** | **지원**(단위 4) |
| 4 | `2L_FEST.py:5864` | `_solve_tandem_junction_bf_v29` (`:5710`) | `3N+Nm+Nrm` (`:5736`) | Schur 축약 | B / bifacial | **거부**(단위 5) — 현재 미사용 |
| 5 | `2L_FEST.py:6133` | `_solve_tandem_bifacial` (`:5979`) | `3N+Nm+Nrm` (`:5988`) | Vint 없음 | A / bifacial | **거부**(단위 5) |
| 6 | `2L_FEST.py:6310` | `solve_single` (`:6238`) | `2N+Nm` (`:6251`) | Ve, Vm, Vr | 단일셀 | **거부**(단위 5) |
| 7 | `2L_FEST.py:6421` | `solve_single` bifacial 분기 | `2N+Nm+Nrm` (`:6368`) | + Vrm | 단일셀 | **거부**(단위 5) |

> ⚠ **"한 곳만 고치면 경로에 따라 결과가 갈린다"가 바로 이 표다.** 사용자는 `rear_mode` 하나만 바꿔도 다른 잔차 지점으로 넘어가는데, 그 지점에 벌크 평면이 없으면 **입력한 `Rs_base`가 조용히 무시된다.** 오류도 경고도 없이 "벌크 횡전도를 켰는데 결과가 안 변한다"로 나타난다.
>
> **이 계획의 대응은 "7곳 전부 구현"이 아니라 "2곳 지원 + 5곳 명시적 거부"다.** 이유는 §설계 결정 3에 있다. 거부가 곧 일관성이며, 거부를 빠뜨리는 것이 이 작업 최대의 위험이다.

---

## 설계 결정

### 1. 단위계 — **코드보다 먼저 확정한다** (단위 1)

공간 분포 계획에서 *"정규화 규약 결정 — 코드보다 이 결정이 먼저다. 규약이 바뀌면 산출 수치가 통째로 바뀐다"*고 적었던 것과 **같은 성격의 결정**이다. 여기서도 단위계가 바뀌면 사용자가 넣은 숫자의 의미가 통째로 바뀌고, 이미 저장된 시나리오 JSON·CSV가 전부 무효가 된다.

**후보 두 가지:**

| | A안 — **Ω/sq (면저항)** | B안 — Ω·cm (체적 비저항) + 두께 |
|---|---|---|
| 입력 | `Rs_base` 하나 | `rho_base` + `t_wafer` 둘 |
| 코드 | `assemble_K(..., Rs_base, ...)` **그대로** | 매번 `Rs = rho/t` 환산 후 호출 |
| 기존 명명 | `Rs_junction`·`Rs_rear_tco`·`Rs_rear_metal_sheet` **전부 Ω/sq** | 기존과 다른 축 |
| 물리 직관 | 웨이퍼 두께가 숨는다 | 두께가 드러난다 |
| Griddler 대응 | **Appendix A.5 확인 필요** | **Appendix A.5 확인 필요** |

**현 시점 권고: A안(Ω/sq).** 근거 셋:

1. **`assemble_K`가 이미 Ω/sq를 받는다**(`2L_FEST.py:2649`, 도크스트링 *"stiffness matrix from sheet resistance"*, `coeff = 1/(4·A·Rs)`). B안은 호출부마다 환산을 끼워 넣어야 하고, 환산을 한 곳이라도 빠뜨리면 **단위가 섞인 채로 조립된다.**
2. **횡전도 평면 파라미터가 전부 Ω/sq다.** `Rs_junction`(interlayer) · `Rs_rear_tco` · `Rs_rear_metal_sheet` · `Rs_front`. 여기만 Ω·cm를 쓰면 GUI 라벨과 CSV 열에서 **같은 성격의 값이 두 단위로 섞인다.**
3. **두께는 이미 모델 밖이다.** `DiodeParams`에 웨이퍼 두께 필드가 없다(`wafer_thickness` 전문 검색 0건 — `docs/pro_feature_map_2026-08-14.md` #2). B안을 택하면 **두께 입력을 새로 만들어야 하고**, 그 값은 벌크 횡전도 외에는 아무 데도 쓰이지 않아 "이 값이 무엇에 영향을 주는가"를 사용자에게 설명하기 어렵다.

> ⚠ **권고이지 확정이 아니다. 단위 1의 산출물은 Appendix A.5를 읽고 내린 결정이다.** A.5가 체적 비저항으로 기술한다면 B안이 되고, 그때는 두께 입력 신설이 이 계획의 범위로 들어온다(단위 1에서 계획을 갱신할 것).
>
> **환산 관계는 어느 쪽이든 같다**: `Rs [Ω/sq] = ρ [Ω·cm] / t [cm]`. 이 식은 `docs/griddler_feature_map.md:105`에 이미 기록돼 있다. B안이 되더라도 **내부 저장은 Ω/sq로 두고 입력단에서만 환산**하면 위 1·2의 문제는 피할 수 있다 — 그것이 B안이 되었을 때의 권고안이다.

### 2. 토폴로지 — 벌크 평면이 **무엇과 무엇 사이에** 놓이는가 (단위 1)

이것이 단위계보다 더 큰 결정이며, **Appendix A.5 없이는 확정할 수 없다.**

현재 하부셀 전압은 **두 평면의 차**로 정의된다(`2L_FEST.py:5104`):

```python
Vbot = V_int - Vr        # 상부 = interlayer, 하부 = rear emitter
```

즉 하부셀 다이오드가 **interlayer와 rear 평면을 직접 잇고**, 그 사이 벌크에는 횡전도가 없다. 벌크 평면을 넣는 방법이 둘이다.

**후보 α — 직렬 삽입 (평면 하나 추가, `Vbot` 정의 변경)**

```
V_int  ──┬── (하부셀 다이오드) ──  V_base  ──(수직 Gv_base)──  Vr
         │                           │
      K_junc                       K_base          ← 신설
```

- `Vbot = V_int − V_base`로 바뀌고, `V_base`와 `Vr`은 수직 컨덕턴스 `Gv_base`로 이어진다.
- **`Gv_base`라는 새 파라미터가 필요하다** — 그리고 그 값은 지금 `Rs_vert_bot`(§3 참조)이 사후 보정으로 처리 중인 물리와 **정확히 겹친다.** 이중 계산 위험.
- 미지 벡터 +N, 잔차 +1블록, 야코비안 +4블록(`dV_base` 결합).

**후보 β — 병렬 추가 (`Vr` 평면의 전도도에 합산)**

```
Vr 평면의 유효 면전도 = 1/Rs_rear_tco + 1/Rs_base
                        (rear 확산층)   (벌크)
```

- 다수캐리어가 rear 확산층으로도, 벌크로도 횡이동할 수 있다는 해석. **평면 수가 늘지 않는다** — `_Kr` 조립 시 병렬 합성 면저항을 쓰면 끝난다.
- 미지 벡터·잔차·야코비안 **레이아웃 무변경** → 7개 분기를 손댈 필요가 없다.
- 대신 **"6번째 전도 평면 신설"이라는 지시와 어긋난다.** 그리고 벌크와 rear 확산층이 같은 등전위면이라는 강한 가정이 들어간다 — 두께 방향 전압강하를 0으로 본다는 뜻이라, `Rs_vert_bot`이 0이 아닐 때 모순이다.

**현 시점 권고: α(직렬 삽입).** 지시가 "6번째 전도 평면 신설"이고, β는 벌크를 rear 표면과 등전위로 묶어 **벌크를 독립 평면으로 다루지 않기** 때문이다. 다만 α는 `Gv_base` 신설을 강제하므로 §3의 이중 계산을 반드시 함께 처리해야 한다.

> **단위 1의 판정 항목**: A.5가 base lateral transport를 (a) 독립 노드 평면 + 수직 결합으로 기술하는가(α), (b) 기존 rear 노드의 전도도 항으로 기술하는가(β). 이 문장 하나가 계획의 절반을 결정한다.

### 3. **`Rs_vert_bot`과의 이중 계산** — 착수 전 반드시 인지할 것

`DiodeParams.Rs_vert_bot`(`2L_FEST.py:1729`)은 *"Si bulk / contact"*의 수직 직렬저항이며, 주석이 명시하듯 **터미널 IR 강하로 사후 적용**된다:

```
V_terminal = V_solver − J × (Rs_vert_top + Rs_vert_bot)
```

즉 **벌크는 지금도 모델 안에 있다 — 다만 lumped 수직 성분으로만.** 후보 α의 `Gv_base`는 바로 그 물리다. 둘 다 켜면 벌크 수직 저항이 **두 번 계산된다.**

**✅ 확정 (2026-08-18, 박사님 판단): ㄴ — 거부.** `Gv_base`를 별도 입력으로 두고,
**`Rs_vert_bot`과 `Gv_base`가 둘 다 0이 아니면 `ValueError`로 거부한다.**

| | 대응 | 판정 |
|---|---|---|
| ㄱ | `Rs_base` 지정 시 `Rs_vert_bot`을 `Gv_base`로 흡수하고 사후 보정에서 제외 | ❌ 기각 |
| **ㄴ** | `Gv_base`를 별도 입력으로 두고, 둘 다 0이 아니면 **`ValueError`로 거부** | ✅ **확정** |
| ㄷ | `Gv_base` 없이 `V_base ≡ Vr` (수직 이상적) | ❌ 기각 (α가 β로 붕괴) |

**판단 근거 (박사님, 2026-08-18):**

1. **이중 계산은 선택지가 아니라 잘못된 결과다.** 벌크 수직 저항을 두 번 세면 나오는
   숫자는 "보수적인 값"이 아니라 **틀린 값**이다. 두 입력을 동시에 허용하는 설계는
   사용자에게 틀린 결과를 만들 자유를 주는 것이고, 그것은 입력 검증의 실패다.
   조합이 물리적으로 성립하지 않으면 **계산하지 않는 것이 옳다.**

2. **흡수(ㄱ)는 `Rs_vert_bot`의 기존 의미를 바꿔 과거 결과 재현을 깬다.** 지금
   `Rs_vert_bot`은 조건과 무관하게 *"터미널 IR 강하로 사후 적용되는 벌크+접촉 수직
   저항"*이다(`2L_FEST.py:1720-1729`). 흡수하면 **`Rs_base` 지정 여부에 따라 같은
   필드가 다른 의미**를 갖는다 — 사후 보정이었다가 FEM 내부 결합이 된다.
   그러면 `scripts/scenarios/*.json`·CSV·논문 계산에 남아 있는 `Rs_vert_bot` 값이
   **어느 의미로 기록된 것인지 사후에 판정할 수 없고, 과거 결과를 재현할 수 없다.**
   조용한 의미 변화는 되돌릴 수 없지만, 거부는 시끄럽고 되돌릴 수 있다.

이 판단은 저장소의 기존 방침과 같은 계열이다 — v28.43(`n_probe_points=0`)·
v28.54(`extraction_method`)·v28.57(로더의 0·음수·NaN)이 전부 **"조용히 고치거나
무시하지 말고 진단 가능한 메시지와 함께 거부"**를 택했다.

> **구현 위치**: 단위 1이 토폴로지 α를 확정하면 `Gv_base`가 신설되고, 그때 이 검증이
> 단위 2(파라미터 신설)의 일부가 된다. 토폴로지가 β로 판정되면 `Gv_base` 자체가
> 없으므로 이 충돌도 사라진다 — **그 경우 이 결정은 무효가 아니라 무해하게 비활성**이다.
>
> **오류 메시지 요건**: 두 값과 각각의 의미(`↕` 사후 보정 vs `↕` FEM 결합), 그리고
> **어느 쪽을 0으로 두면 되는지**를 함께 적는다. 거부만 하고 길을 안 알려주면
> 사용자는 둘 중 무엇을 지워야 하는지 모른다.

### 4. 대상 범위 — **지원 2 + 거부 5**

7개 분기를 전부 구현하지 않는 이유:

- 분기 4(`_v29` Schur)는 **현재 호출되지 않는다** — `solve_tandem`(`:4726`) 주석이 *"currently sub-optimal, kept for future"*라고 적어 두었다. 죽은 경로에 새 물리를 넣으면 검증되지 않은 코드가 늘어난다.
- 분기 1·5는 **Phase A**(`Rs_junction=0`)다. Phase B가 production 모델이고(`RS_JUNCTION_MIN` 클램프, v28.33), Phase A는 `FEST_LEGACY_LOCAL_MATCH=1` 탈출구로만 도달한다. 레거시 경로에 새 물리를 얹지 않는다.
- 분기 6·7은 **단일셀**이다. 벌크 횡전도 자체는 단일셀에도 의미가 있으나, 지시가 tandem 맥락이고 범위를 넓히면 단위가 두 배가 된다. **별도 항목으로 신설**한다(공간 분포에서 면저항 맵을 별도 항목으로 뺀 것과 같은 판단).

**거부는 침묵이 아니라 오류다.** 지원하지 않는 조합에서 `Rs_base`가 지정되면 `ValueError`를 던진다(단위 5). 이것이 §함정의 유일한 해독제다.

---

## 맵/평면 off에서 비트 동일이 보장되는 근거

> **박사님 질문: 공간 분포에서 썼던 "곱셈을 아예 안 함"이 여기서도 성립하는가?**
> **답: 그 형태로는 성립하지 않는다. 한 단계 위 — "평면을 아예 만들지 않음"으로 올려야 한다.**

### 왜 "0을 더함"은 여기서 근거가 못 되는가

공간 분포는 **곱셈 하나**를 건너뛰는 문제였다. 소비 지점이 전부 `if ... is not None:` 가드 안이라, 맵이 없으면 부동소수점 연산이 **하나도 추가되지 않았다**. 그것이 비트 동일의 산술적 근거였다.

벌크 평면을 "`Rs_base` 미지정이면 `K_base = 0` 행렬을 더한다"로 구현하면 얼핏 같아 보인다. `x + 0.0 == x`는 IEEE 754에서 정확하니까. **그러나 그 논증은 여기서 무너진다.**

1. **미지 벡터 길이가 바뀐다.** `Ns = 4N+Nm` → `5N+Nm`. 잔차·야코비안·해 벡터가 전부 다른 크기가 된다.
2. **희소 행렬의 sparsity pattern이 바뀐다.** `scipy.sparse.linalg.spsolve`는 SuperLU를 부르고, SuperLU는 **패턴에 따라 열 순열(COLAMD)과 pivot 순서를 정한다.** 결합이 정확히 0인 블록을 붙여도 순열이 달라지면 **나머지 블록의 소거 순서가 달라지고, 부동소수점 누적 순서가 달라진다.**
3. 그 결과는 §registration_material.md §5-1이 실측으로 기록한 것과 같은 종류의 편차다 — **단락에서는 안 보이고 바이어스에서 뉴턴 반복 누적으로 드러나는 상대 1e-7 수준.** 즉 "0을 더했으니 비트 동일"은 **틀린 논증이고, 틀린 방식도 이미 실측으로 알려져 있다.**

> ⚠ 이 함정은 그럴듯해서 위험하다. `assert K_base.nnz == 0`을 확인하고 안심하기 쉬운데, **nnz가 0이어도 행렬 차원이 커졌으면 분해가 달라진다.**

### 성립하는 근거 — `_K_junc`의 Phase A/B 분기와 동형

저장소에 **이미 같은 문제를 푼 전례**가 있다. `_K_junc`는 interlayer 평면을 켜고 끄는데, 끄는 방식이 "0 행렬을 더함"이 **아니다**:

```python
# 2L_FEST.py:4488 부근 — 평면을 만들지 않는다
if <Phase B 조건>:
    self._K_junc, _ = assemble_K(...)
else:
    self._K_junc = None                  # ← 평면 자체가 없다

# 2L_FEST.py:4735-4741 — 디스패치가 갈린다
if self._K_junc is not None and self.geo.rear_mode == 'full_area':
    return self._solve_tandem_junction(...)      # Ns = 4N+Nm  (:5044)
...
Ns = 3 * N + Nm                                   # (:4747) 옛 레이아웃 그대로
```

**off 경로는 옛 코드를 그대로 실행한다.** 행렬 차원도, sparsity pattern도, SuperLU 순열도, 연산 순서도 전부 이전과 동일하다. 이것이 비트 동일의 근거이며, 공간 분포의 "곱셈을 안 함"과 **같은 계열의 논증을 한 단계 위(솔버 디스패치)에서 편 것**이다.

| | 공간 분포 (v28.56~58) | 벌크 평면 (이 계획) |
|---|---|---|
| off 표현 | `dp.spatial_x = None` | `dp.Rs_base = None` |
| 건너뛰는 것 | **곱셈 한 번** | **평면 조립 + 솔버 분기 전체** |
| 근거 층위 | 산술 (`if ... is not None:` 가드) | 구조 (`Ns`·디스패치 분리) |
| 위반 형태 | `SpatialMap(mode='uniform')`으로 대체 | **`K_base = 0` 행렬로 대체** |

**따라서 이 계획의 불변식은 하나다:**

> **`dp.Rs_base is None`이면 `self._K_base is None`이고, 디스패치는 벌크 평면 없는 기존 솔버로 간다. `Ns`는 옛 값 그대로다.**

`_K_base`를 만들어 놓고 결합만 0으로 두는 구현은 **금지**한다. 단위 2의 `test_base_off_keeps_legacy_unknown_layout`이 이 규칙을 지킨다.

### 어디까지가 "비트 동일"인가

`_build`의 **캐시 해시에 `Rs_base`를 넣어야 한다**(`2L_FEST.py:4318`의 `h` 튜플). 넣지 않으면 `Rs_base`만 바꿨을 때 재빌드가 일어나지 않아 **옛 `_K_base`가 조용히 재사용된다** — v28.56이 `id()` 캐시에서 겪은 것과 정확히 같은 실패다.

동시에 **`Rs_base is None`일 때 해시 항은 예전과 같은 값이어야 한다.** `_sm_tag`가 맵 없을 때 `0`을 넣어 무맵 경로의 캐시 거동을 보존한 것과 같은 처리다(`:4314` 주석). 단위 2에서 `None → 0` 태그로 고정한다.

---

## Griddler 매뉴얼 Appendix A.5 대응

> ⚠ **이 절은 지금 채울 수 없다. 그리고 채우기 전에는 단위 2 이후로 넘어가면 안 된다.**

**매뉴얼 PDF가 이 저장소에 없다.** 저작권 문제로 `~/dev/refs/`에 별도 보관하며 필요 시 `--add-dir`로 접근한다(`docs/WORKLOG.md` §5, `docs/griddler_feature_map.md:4`). 이 머신(원 캡처 PC)에서는 접근하지 못했다.

저장소 안에 A.5 내용은 **없다.** 확인한 것: `docs/griddler_feature_map.md`의 Appendix 언급은 A.1(온도 한계, `:366`)과 C(EDNA2 벤치마킹, `:193`)뿐이고, A 도입부 p.106이 외부 계산기 문맥으로 한 번 나온다(`:219`). **A.5는 어느 문서에도 요약돼 있지 않다.**

### 단위 1에서 채울 대응표 (양식)

A.5를 읽고 **아래 표를 채우는 것이 단위 1의 산출물**이다. 빈칸을 남긴 채 코드로 넘어가면, 우리 식과 Griddler 식이 다른 것을 **수치가 어긋난 뒤에야** 알게 된다.

| A.5 기호 | A.5의 정의 | 2L-FEST 대응 | 단위 | 일치 여부 |
|---|---|---|---|---|
| (base 면전도 항) | | `_K_base` / `assemble_K(..., Rs_base, ...)` | Ω/sq? | |
| (base 노드 전압) | | `V_base` (후보 α) 또는 `Vr`에 흡수(후보 β) | V | |
| (base ↔ rear 수직 결합) | | `Gv_base` (후보 α) 또는 없음(β) | S/cm²? | |
| (base 두께 의존성) | | 두께 필드 없음 → 단위계 결정에 직결 | cm | |
| (majority/minority 구분) | | 현재 모델은 다수/소수 캐리어를 구분하지 않는다 | — | |

### 반드시 확인할 문장 5개

1. **A.5가 base 전류를 면저항(Ω/sq)으로 쓰는가, 체적 비저항 + 두께로 쓰는가** → §설계 결정 1을 확정한다.
2. **base 노드가 rear 노드와 별개인가, 같은 노드인가** → §설계 결정 2의 α/β를 확정한다.
3. **base와 rear 사이 수직 저항 항이 있는가** → `Gv_base` 신설 여부, 그리고 `Rs_vert_bot` 이중 계산 대응(§설계 결정 3)을 확정한다.
4. **base 전도가 emitter와 같은 Galerkin 이산화를 쓰는가** → `assemble_K` 재사용 가능 여부. 다르면(예: 두께 방향 평균 처리) 별도 조립 함수가 필요하다.
5. **A.5가 명시한 적용 한계** — A.1이 *"계산기류는 25 °C 실리콘에서만 정확"*이라는 한계를 달아 두었듯(`griddler_feature_map.md:366`), A.5에도 한계 문장이 있을 가능성이 높다. **있으면 우리도 상속해 문서화한다**(§3 "Griddler가 명시한 한계 — 우리도 상속·문서화할 것"의 방침).

### 대조가 불가능한 것으로 판명되면

공간 분포 단위 3의 전례를 따른다 — **자체 규약으로 확정 선언하고, 그것이 "Griddler와 동일"이 아니라 "동일 목적의 자체 구현"임을 문서에 명시**한다(`docs/spatial_map_convention.md` · `docs/pro_feature_map_2026-08-14.md` #6 개정 참조). 다만 **A.5는 무료판 UI 기능이 아니라 매뉴얼 서술이므로, 접근만 하면 읽을 수 있다.** 공간 분포와 달리 "원리적으로 불가"가 아니라 "이 머신에서 미접근"이다 — 맥북에서 `--add-dir`로 열면 해결된다.

---

## 6번째 평면이 미지 벡터·잔차·야코비안에 미치는 영향

후보 α 기준. 지원 대상 2개 분기 각각에 대해 아래가 전부 바뀐다.

### 1) 미지 벡터 레이아웃

오프셋은 **모든 잔차 지점에서 하드코딩된 산술**이다(`oVe = 0; oVm = N; oVt = N + Nm; oVr = N + Nm + N`, `:4748`). 새 블록을 **끝에 붙인다** — 중간에 끼우면 기존 오프셋이 전부 밀려 warm-start·프로롱게이션·BC 인덱스가 조용히 어긋난다.

| 분기 | 현재 `Ns` | 벌크 on `Ns` | 신설 오프셋 |
|---|---|---|---|
| `_solve_tandem_junction` | `4N + Nm` | `5N + Nm` | `oVbase = 4N + Nm` |
| `_solve_tandem_junction_bf` | `4N + Nm + Nrm` | `5N + Nm + Nrm` | `oVbase = 4N + Nm + Nrm` |

**함께 바뀌는 것 4가지** — 이걸 빠뜨리면 수렴은 하는데 값이 틀린다:

- **초기 추정** (`:4754` 계열) — `V[oVbase:...]`를 채워야 한다. 안 채우면 0에서 시작해 반복 수가 늘고, 최악의 경우 다른 국소해로 간다.
- **mesh prolongation 시드** (`_apply_mesh_prolongation_seed`, `:4192`) — 평면 딕셔너리(`{"Ve": (oVe, None), ...}`, `:4760`)에 `"Vbase"` 항목 추가.
- **warm-start 캐시** (`_warm_V_junc_bf` 등, `:4321-4327`) — 저장된 벡터 길이가 달라지므로, **`Rs_base` 변경 시 반드시 무효화**되어야 한다. 캐시 해시(`h`, `:4318`)에 `Rs_base`를 넣으면 `_build`가 자동으로 지운다(`:4321`).
- **경계조건 인덱스** (`bc_front`/`bc_rear`, `:4803-4804`) — 벌크 평면에 BC를 걸지 않으면 **`K_base`만으로는 특이행렬**이다(순수 Neumann → 상수 이동 null mode). 아래 참조.

### 2) 잔차

후보 α의 벌크 노드 KCL. **저장소의 보편 규약**은 *"위 평면은 `K@V − I`, 아래 평면은 `K@V + I`"*이고, TANDEM-1 수정 때 이 규약이 명시적으로 못 박혔다(`:5162-5168` 주석). 벌크 평면은 하부셀의 **아래쪽**이자 rear의 **위쪽**이므로:

```
F_Vbase = K_base @ V_base + Ib − Gv_base·(V_base − Vr) = 0
F_Vr    = Kr @ Vr + Gv_base·(V_base − Vr)            ← Ib가 Gv_base 항으로 대체됨
Vbot    = V_int − V_base                        ← 정의 변경(기존: V_int − Vr)
```

> ⚠ **`F_Vr`의 소스 항이 `Ib`에서 `Gv_base·(V_base − Vr)`로 바뀐다.** 즉 벌크 평면 추가는 "블록 하나 추가"가 아니라 **기존 `F_Vr`·`Vbot`의 수정**을 동반한다. 이것이 7개 분기를 한 번에 못 고치는 이유이기도 하다.

### 3) 야코비안

현재 `_solve_tandem_junction`의 야코비안은 COO 블록 **13개**를 이어 붙인다(`:5176-5252`). 벌크 평면은 여기에 블록을 더하고 기존 블록 일부를 고친다.

**신설 블록 (5)**

| 블록 | 값 |
|---|---|
| `∂F_Vbase/∂V_base` | `K_base + Gv_base·I − dIb` (`dVbot/dV_base = −1`) |
| `∂F_Vbase/∂Vr` | `−Gv_base·I` |
| `∂F_Vbase/∂V_int` | `+dIb` (`dVbot/dV_int = +1`) |
| `∂F_Vr/∂V_base` | `+Gv_base·I` |
| `∂F_Vbase/∂Vtop` | `−dILC` (LC 켜졌을 때만) |

**수정 블록 (4)** — 기존 `Ib`가 `V_base` 의존으로 옮겨 가면서:

| 블록 | 현재 (`:5215-5231`) | 벌크 on |
|---|---|---|
| `∂F_Vr/∂Vr` | `Kr − dIb` | `Kr − Gv_base·I` (`dIb` 항 제거) |
| `∂F_Vr/∂V_int` | `+dIb` | **삭제** |
| `∂F_Vr/∂Vtop` | `+dILC` | **삭제** (`F_Vbase`로 이동) |
| `∂F_Vint/∂Vr` | `+dIb` | `∂F_Vint/∂V_base = +dIb`로 이동 |

> **야코비안 오류는 조용하다.** 잔차가 맞으면 뉴턴은 (느리게) 수렴하므로 **틀린 야코비안도 맞는 답을 준다** — 반복 수만 늘 뿐. 따라서 단위 3의 검증은 수렴 여부가 아니라 **유한차분 대조**여야 한다(아래 Task 3 Step 1).

### 4) 특이성 — 벌크 평면에 BC가 필요한가

`K_base`만으로는 **상수 이동 null mode**가 있다(순수 Neumann). 현재 `Vr`은 `rear_probe_idx`에 Dirichlet BC(`Vr[gi] = 0`, `:4927`·`:5155`)가 걸려 고정된다.

- 후보 α에서 `V_base`는 `Gv_base`를 통해 `Vr`에 묶이므로, **`Gv_base > 0`이면 null mode가 제거된다.**
- **`Gv_base = 0`이면 특이하다** → `Gv_base`의 하한을 두어야 한다. `RS_JUNCTION_MIN = 0.1`(`2L_FEST.py:686` 부근)이 정확히 같은 목적의 전례다 — *"interlayer stiffness가 항상 조립 가능하도록"*.
- v28 changelog `:93`이 기록한 *"(V_int+c, Vr+c) null mode 제거"* 사건과 **같은 종류의 위험**이다. 그때 Vint를 비-DOF화해 해결했다. 여기서도 단위 3의 첫 테스트는 **비특이성 검사**여야 한다(`test_junction_bf_nonsingular`(`tests/test_junction_bf.py:110`)가 선례).

---

## 작업 단위 분할

각 단위는 **종료 시점에 일관된 상태**여야 한다: 테스트 통과, 반쯤 배선된 기능 없음, 앱 실행 가능, 단독 커밋 가능. 뒤 단위를 하지 않고 멈춰도 저장소가 깨지지 않는다.

베이스라인(2026-08-18 원 캡처 PC 실측): **258 passed / 2 deselected / 6 xfailed** (1276 s). 비트 핀 2건이 strict 통과 상태.

---

### 단위 0 — 7개 잔차 분기 특성화 테스트 ✅ 완료 (2026-08-18)

> **결과: `tests/test_base_lateral.py` 21 passed (46 s). 프로덕션 코드 0줄.**
> 특성화 테스트이므로 **전부 첫 실행에 통과하는 것이 정상**이다 — 현재 동작을
> 고정할 뿐 바꾸지 않는다. 공간 분포 단위 0(30건 전부 첫 실행 통과)과 같은 성격.
>
> **§함정의 7분기 표가 실측으로 확인됐다.** 계획 작성 시 코드를 읽어 세운 표인데,
> `spsolve`를 가로채 `J.shape[0]`을 관측한 결과 6개 live 분기가 **전부 예측한
> 오프셋 식과 일치**했다:
>
> | 설정 | 디스패치 | 관측 `Ns` | 식 |
> |---|---|---|---|
> | Phase A / full_area | 인라인 (`solve_tandem`) | 12,980 | `3N+Nm` ✅ |
> | **Phase B / full_area** | `_solve_tandem_junction` | 16,789 | `4N+Nm` ✅ |
> | **Phase B / bifacial** | `_solve_tandem_junction_bf` | 24,942 | `4N+Nm+Nrm` ✅ |
> | Phase A / bifacial | `_solve_tandem_bifacial` | 19,483 | `3N+Nm+Nrm` ✅ |
> | 단일셀 / full_area | 인라인 (`solve_single`) | 9,171 | `2N+Nm` ✅ |
> | 단일셀 / bifacial | 인라인 (`solve_single`) | 14,024 | `2N+Nm+Nrm` ✅ |
>
> (`N`=3,809 / `Nm`=1,553 (mono), `N`=5,459 / `Nm`=1,703 / `Nrm`=1,403 (bifacial))
>
> **분기 4(`_v29` Schur)는 어떤 설정에서도 도달하지 않았다** — 죽은 코드라는
> 계획의 전제가 실측으로 확인됐다. `test_v29_schur_branch_is_unreachable`이 그
> 사실을 고정한다. 누군가 이 분기를 다시 배선하면 그 테스트가 실패해서 벌크 평면
> 대응을 함께 하라고 알린다.
>
> #### 계획 대비 편차 — `_observed_Ns` 구현 방식
>
> 계획은 *"결과 dict의 평면 길이를 합산"*이었으나 **그 방법은 쓸 수 없다.**
> `solve()`가 돌려주는 dict에 `Vrm`(rear metal)이 없다(`2L_FEST.py:6512` 부근).
> bifacial 분기의 `Ns`를 그 방법으로는 셀 수 없다.
>
> 대신 **뉴턴 루프의 `spsolve(J, -F)` 호출을 가로채 `J.shape[0]`을 읽는다.**
> 그것이 정의상 `Ns`이고, 프로덕션 코드에 디버그 훅을 남기지 않는다. 단위 3의
> 야코비안 유한차분 대조도 같은 훅을 쓴다 — 그래서 헬퍼를 `_probe` 하나로 모았다.
>
> ⚠ **`fest.spsolve` 하나만 패치하면 절반이 새어 나간다.**
> `_solve_tandem_junction`(`:5041`) · `_solve_tandem_junction_bf`(`:5392`) ·
> `_v29`(`:5733`)는 **메서드 안에서 다시 import** 하므로 모듈 전역 패치가 무시된다.
> 원본 `scipy.sparse.linalg.spsolve`도 함께 패치해야 한다. 이 사실을 모르고
> 짰다면 Phase B 두 분기가 조용히 관측되지 않았을 것이고, **하필 그 둘이 벌크
> 평면을 넣을 분기다.**
>
> #### 고정한 것 (21건)
>
> | 절 | 건수 | 내용 |
> |---|---|---|
> | 1 디스패치 | 13 | 설정 → 분기 매핑 6건 · `Ns` 오프셋 식 6건 · 표 완전성 메타 1건 |
> | (v29) | 1 | Schur 분기 도달 불가 |
> | 2 스위치 | 4 | `Rs_junction`이 Phase A↔B를 가르며 **`Ns`가 정확히 +N** · legacy 플래그가 Phase A의 전제 · `rear_mode`가 `Nrm` 유무 · 단일셀은 tandem 분기에 안 감 |
> | 3 기준선 | 3 | `Rs_base`/`Gv_base` 아직 없음 · `_K_base` 없고 평면은 5개 · **`Rs_vert_bot`이 `Ns`를 안 바꾼다(= FEM 밖)** |
>
> `test_rs_junction_switches_phase_a_to_phase_b`가 특히 유용하다 — **평면 하나
> 추가 = 자유도 정확히 +N**을 실측으로 보인다. 벌크 평면이 할 일이 같은 형태이므로,
> 단위 3·4의 `Ns` 기대값이 이 관계에서 곧바로 나온다.
>
> `test_rs_vert_bot_is_a_post_hoc_lumped_correction`은 §설계 결정 3의 전제를
> 고정한다 — `Rs_vert_bot`을 바꿔도 `Ns`가 변하지 않는다는 것이 곧 "FEM 밖에서
> 사후 적용된다"는 뜻이고, 그래서 `Gv_base`와 이중 계산이 된다.
>
> #### 세션 스코프 픽스처를 쓰지 않은 이유
>
> `mono`/`bifacial`(session) 대신 `make_mono`/`make_bifacial`(fresh)을 쓴다.
> 공유하면 이 파일이 남긴 `_warm_V_junc_bf`가 다른 파일의 값 테스트로 새어 나가고,
> 그러면 연속법(homotopy) 램프가 통째로 생략된다(`2L_FEST.py:4713`). 46초는 그
> 위험을 피하는 값으로 싸다.

#### 확정된 헬퍼 계약 — 뒤 단위가 그대로 쓴다

`tests/test_base_lateral.py`에 구현되어 있다. **단위 2~7은 이 시그니처를 따른다.**

```python
PARAMS = dict(rm=3e-6, hf=10e-4, wf=50e-4, rc=5e-3, Rs=15.0, cf=1.0)
VB = 0.5

_build_args(dp)                                   -> dict   # _build(**_build_args(dp))
_solve(m, dp, Vb=VB, mode="tandem")               -> dict   # solve() 결과
_cell_current(m, dp, Vb=VB, mode="tandem")        -> float  # 단자 전류 [A]
_probe(fest, m, dp, monkeypatch, Vb=VB, mode=...) -> (branch_name, ns_tuple)
_observed_Ns(fest, m, dp, monkeypatch, Vb=VB, mode=...) -> int
_plane_sizes(m)                                   -> (N, Nm, Nrm)
_dp(fest, rs_junction=None)                       -> DiodeParams
```

> ⚠ `_probe`·`_observed_Ns`는 **`monkeypatch`를 받는다** — `spsolve`를 가로채기
> 때문이다. `_cell_current`는 안 받는다. 계획 초안이 `_cell_current(fest, m, dp, ...)`로
> 적었던 곳은 전부 `_cell_current(m, dp, ...)`로 읽을 것.

**단위 3에서 신설할 헬퍼** (아직 없다):

```python
_residual_and_jacobian(fest, m, dp, monkeypatch, Vb=VB, nth=0) -> (F, J)
    # _probe와 같은 spsolve 훅. spsolve(J, -F)의 인자를 그대로 돌려준다.
    # nth = 몇 번째 뉴턴 반복인지.

_jacobian_at(fest, m, dp, monkeypatch, Vb=VB)                  -> csr_matrix

_F_of_x(fest, m, dp, Vb=VB)                                    -> callable
    # x -> F(x). 유한차분이 부를 잔차 함수. 뉴턴 루프를 돌리지 않고
    # 잔차 조립부만 재실행하는 얇은 래퍼로 만든다.

_finite_difference_jacobian(F_fn, x0, eps=1e-7)                -> ndarray
    # 중앙차분. F를 2·Ns번 부르므로 **전용 초소형 메시에서만** 쓸 것.

_tiny_solver(fest)                                             -> solver
    # 유한차분 전용 초소형 메시. tests/test_optimizer.py:96-106의
    # cell_mm=20.0 + AX=36 관용구를 더 줄인 것(AX≈8).
    # make_mono의 N=3,809에서 Ns≈16,789 → 유한차분 33,578회 solve는 불가능하다.

_equivalent_bifacial(dp)                                       -> DiodeParams
    # rear TCO/metal 면저항을 1e-4 Ω/sq로 낮춰 rear 평면을 등전위로 붕괴시킨다.
    # full_area의 lumped rear와 전기적으로 등가 → 단위 4의 교차 일치 테스트 전제.
    # ⚠ 0을 넣으면 assemble_K의 coeff = 1/(4·A·Rs)가 0으로 나눈다(:2649).
```

### 단위 1 — 단위계·토폴로지 확정 (문서, 프로덕션 코드 0줄) 🚧 **게이트**

**이 단위를 끝내기 전에는 단위 2 이후로 넘어가지 않는다.** 공간 분포 계획에서 *"정규화 규약 결정이 코드보다 먼저"*였던 것과 같은 자리다.

**Files:**
- Create: `docs/base_lateral_convention.md` (규범 문서 — `docs/spatial_map_convention.md`와 같은 성격)
- Modify: 이 계획서 (§설계 결정 1·2·3의 권고를 **확정**으로 교체)

- [ ] **Step 1: Appendix A.5에 접근한다**

맥북에서 `--add-dir ~/dev/refs/`로 매뉴얼을 열거나, 원 캡처 PC로 해당 PDF를 복사한다. **저장소에 넣지 않는다**(저작권 — `docs/WORKLOG.md` §5).

- [ ] **Step 2: §Appendix A.5 대응의 "반드시 확인할 문장 5개"에 답한다**

각 답을 **요약·재서술**로 적는다. 원문 발췌 금지(`docs/griddler_feature_map.md:4`의 방침).

- [ ] **Step 3: 결정 3건을 확정한다**

| 결정 | 선택지 | 현 권고 |
|---|---|---|
| 단위계 | Ω/sq vs Ω·cm+두께 | **Ω/sq** (§설계 결정 1) |
| 토폴로지 | α 직렬 삽입 vs β 병렬 합산 | **α** (§설계 결정 2) |
| `Rs_vert_bot` 충돌 | — | ✅ **ㄴ 거부로 확정** (2026-08-18, §설계 결정 3) — 단위 1에서 재논의 불필요 |

- [ ] **Step 4: `docs/base_lateral_convention.md`를 쓴다**

담을 것: 확정 3건 · 근거(A.5 대응표) · 파라미터 이름과 단위 · **뒤집힐 경우의 처리 범위**. 공간 분포 규약 문서와 같은 구조를 따른다.

- [ ] **Step 5: 이 계획서를 갱신한다**

권고 → 확정. **B안(Ω·cm)이 되었다면 두께 입력 신설을 단위 2에 추가**하고, **β(병렬)가 되었다면 단위 3~5를 통째로 다시 쓴다**(평면이 늘지 않으므로 훨씬 작아진다).

- [ ] **Step 6: 커밋**

```bash
git add docs/base_lateral_convention.md docs/superpowers/plans/2026-08-18-base-lateral-transport.md
git commit -m "docs: 벌크 횡전도 단위계·토폴로지 확정 (Appendix A.5 대조)"
```

**회귀 영향 범위: 없음.** 문서만.

---

### 단위 2 — 파라미터 신설 + off 경로 비트 동일 고정 (솔버 무변경)

`DiodeParams.Rs_base`(단위 1 확정 이름)를 만들고 캐시 해시에 넣되, **어느 솔버도 아직 읽지 않는다.** 종료 시점에 앱 동작은 완전히 이전과 같다.

**Files:**
- Modify: `2L_FEST.py:1729` 부근 (`DiodeParams` 필드), `2L_FEST.py:4318` (`h` 튜플), `2L_FEST.py:4130-4139` (`_K_base = None` 선언)
- Test: `tests/test_base_lateral.py`

**Interfaces:**
- Produces: `DiodeParams.Rs_base = None` (기본값, Ω/sq) · `FESTSolver._K_base = None`

- [ ] **Step 1: 실패하는 테스트를 쓴다 — off가 옛 레이아웃을 유지하는가**

```python
def test_base_off_keeps_legacy_unknown_layout(fest, make_mono, monkeypatch):
    """**off는 "0 행렬을 더함"이 아니라 "평면을 안 만듦"이다.**

    K_base를 만들어 놓고 결합만 0으로 두면 Ns와 sparsity pattern이 바뀌고,
    SuperLU의 열 순열이 달라져 비트 동일이 깨진다(§비트 동일 근거).
    """
    m = make_mono()
    dp = fest.DiodeParams()
    dp.Rs_junction = 100.0
    assert dp.Rs_base is None                 # 기본값
    m.S._build(**_build_args(dp))
    assert m.S._K_base is None                # 평면 자체가 없다
    assert _observed_Ns(fest, m, dp, monkeypatch) == 4 * m.S.N + m.S.Nm  # 옛 레이아웃


def test_base_none_keeps_cache_tag_unchanged(fest, make_mono):
    """맵 없을 때 _sm_tag가 0인 것과 같은 처리 — 무벌크 경로의 캐시 거동 보존."""
    m = make_mono()
    dp = fest.DiodeParams()
    m.S._build(**_build_args(dp))
    h_before = m.S._cache_hash
    dp.Rs_base = None
    m.S._build(**_build_args(dp))
    assert m.S._cache_hash == h_before        # 재빌드 없음


def test_base_change_invalidates_build_cache(fest, make_mono):
    """Rs_base를 바꿨는데 재빌드가 안 되면 옛 _K_base가 조용히 재사용된다 —
    v28.56이 id() 캐시에서 겪은 실패와 같은 형태다."""
    m = make_mono()
    dp = fest.DiodeParams()
    m.S._build(**_build_args(dp))
    h_before = m.S._cache_hash
    dp.Rs_base = 500.0
    m.S._build(**_build_args(dp))
    assert m.S._cache_hash != h_before
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `python -m pytest tests/test_base_lateral.py -q -k base_`
Expected: FAIL — `AttributeError: 'DiodeParams' object has no attribute 'Rs_base'`

- [ ] **Step 3: 최소 구현**

`DiodeParams`에 `Rs_base = None` 추가(주석에 단위 Ω/sq·`↔` 기호·`Rs_vert_bot`과의 차이 명시), `FESTSolver.__init__`에 `self._K_base = None`, `_build`의 `h` 튜플에 `(dp.Rs_base if dp.Rs_base is not None else 0)` 추가.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_base_lateral.py -q`
Expected: PASS

- [ ] **Step 5: 비트 핀 확인 (원 캡처 PC 필수)**

Run: `python -m pytest tests/test_default_pin.py tests/test_legacy_pin.py -q`
Expected: **2 passed** (xfail 아님 — 스택 일치 확인). 여기서 깨지면 `h` 튜플 변경이 무맵/무벌크 경로의 캐시 거동을 바꾼 것이다.

- [ ] **Step 6: 전체 스위트 + 커밋**

```bash
python -m pytest -q -m "not slow"      # 258+N passed / 2 deselected / 6 xfailed
git add 2L_FEST.py tests/test_base_lateral.py
git commit -m "v28.59: 벌크 횡전도 파라미터 신설 (Rs_base) — 솔버 배선 없음"
```

**회귀 영향 범위:** `_build`의 캐시 해시 튜플. **`Rs_base is None`이면 해시 항이 `0`으로 고정되어 이전과 동일**해야 하고, 그 경우 캐시 거동·결과 모두 불변이어야 한다. 솔버 무변경.

> **버전을 여기서 올린다.** 프로덕션 자료구조가 바뀌므로 v28.58인 채로 두면 "같은 버전인데 다른 상태"가 된다 — 공간 분포 단위 1과 같은 판단.

---

### 단위 3 — 분기 2(`_solve_tandem_junction`, Phase B / full_area)에 벌크 평면

**7개 중 첫 번째 분기.** 가장 단순한 5평면 경로부터 시작한다(rear metal 없음).

**Files:**
- Modify: `2L_FEST.py:4488` 부근(`_K_base` 조립), `2L_FEST.py:5017-5378`(`_solve_tandem_junction` 전체 — `Ns`·초기추정·잔차·야코비안·BC)
- Test: `tests/test_base_lateral.py`

**Interfaces:**
- Consumes: `dp.Rs_base` (단위 2) · `dp.Gv_base` (단위 1이 ㄴ안을 확정한 경우, S/cm²)
- Produces: `oVbase = 4 * N + Nm` 오프셋 · `result["V_base"]` 키

- [ ] **Step 1: 실패하는 테스트를 쓴다 — 야코비안 유한차분 대조**

**수렴 여부로 판정하지 않는다.** 틀린 야코비안도 (느리게) 수렴하기 때문이다.

```python
def test_base_jacobian_matches_finite_difference(fest, monkeypatch):
    """야코비안 오류는 조용하다 — 반복 수만 늘고 답은 맞는다.
    그래서 수렴이 아니라 유한차분으로 판정한다."""
    m = _tiny_solver(fest)      # 유한차분은 초소형 메시에서만 가능하다
    dp = _dp(fest, 100.0)
    dp.Rs_base = 500.0
    F, J = _residual_and_jacobian(fest, m, dp, monkeypatch)
    J_fd = _finite_difference_jacobian(_F_of_x(fest, m, dp), x0)
    assert np.allclose(J.toarray(), J_fd, rtol=1e-4, atol=1e-9)


def test_base_plane_is_nonsingular(fest, make_mono, monkeypatch):
    """K_base 단독은 상수 이동 null mode를 갖는다(순수 Neumann).
    Gv_base 결합이 그것을 제거하는지 확인한다 — v28의 (V_int+c, Vr+c) 사건과 같은 위험."""
    m = make_mono()
    dp = _dp(fest, 100.0); dp.Rs_base = 500.0
    J = _jacobian_at(fest, m, dp, monkeypatch)
    assert np.linalg.matrix_rank(J.toarray()) == J.shape[0]
```

- [ ] **Step 2: 실패 확인**

Run: `python -m pytest tests/test_base_lateral.py -q -k jacobian`
Expected: FAIL (평면이 아직 없어 `Ns`가 `4N+Nm`이므로 차원 불일치)

- [ ] **Step 3: `_build`에 `_K_base` 조립을 추가한다**

```python
# 2L_FEST.py:4488 부근 — _K_junc 조립 바로 뒤
if dp.Rs_base is not None:
    self._K_base, _ = assemble_K(
        self.pts, self.simp, dp.Rs_base, self.areas, self.b, self.c)
else:
    self._K_base = None      # ← 평면을 만들지 않는다(§비트 동일 근거)
```

- [ ] **Step 4: `_solve_tandem_junction`에 6번째 평면을 넣는다**

`Ns = 5*N + Nm`, `oVbase = 4*N + Nm`, `Vbot = V_int - V_base`, 잔차 `F_Vbase`/`F_Vr` 수정, 야코비안 신설 5블록 + 수정 4블록, 초기추정·프로롱게이션 시드·BC. §"6번째 평면이 …에 미치는 영향"의 표 그대로.

**`Rs_base is None`이면 이 메서드는 예전 코드를 그대로 탄다** — `Ns`·오프셋·블록 구성이 전부 분기되어야 한다.

- [ ] **Step 5: 테스트 통과 + off 비트 동일 재확인**

Run: `python -m pytest tests/test_base_lateral.py tests/test_invariants.py -q`
Expected: PASS. 특히 `test_base_off_keeps_legacy_unknown_layout`이 여전히 통과해야 한다.

- [ ] **Step 6: 물리 방향 확인 — 극한에서 기존 해로 수렴하는가**

```python
def test_base_infinite_sheet_r_approaches_no_base_plane(fest, make_mono):
    """Rs_base → ∞ (횡전도 없음)이면 벌크 평면이 없는 해에 수렴해야 한다.

    비트 동일은 기대하지 않는다(Ns가 다르므로 SuperLU 순열이 다르다).
    물리적 동등성 수준의 일치를 본다 — registration_material.md §5-1의
    두 층 구분과 같은 판정 기준이다.
    """
    m = make_mono(); dp = _dp(fest, 100.0)
    J_ref = _cell_current(m, dp)                        # Rs_base None
    dp.Rs_base = 1e12
    J_big = _cell_current(m, dp)
    assert J_big == pytest.approx(J_ref, rel=1e-6)


def test_base_lower_sheet_r_raises_current(fest, make_mono):
    """벌크 횡전도가 좋아지면 저항 손실이 줄어 전류가 오른다."""
    ...
```

- [ ] **Step 7: 전체 스위트 + 비트 핀 + 커밋**

```bash
python -m pytest -q -m "not slow"
python -m pytest tests/test_default_pin.py tests/test_legacy_pin.py -q   # 2 passed
git add 2L_FEST.py tests/test_base_lateral.py
git commit -m "v28.60: 벌크 횡전도 — Phase B full_area 분기 (7분기 중 1)"
```

**회귀 영향 범위:** `_solve_tandem_junction` 전체. **`Rs_base is None` 경로는 불변**이어야 하고 테스트가 지킨다. 나머지 6개 분기 무변경 — 그 분기에서 `Rs_base`를 지정하면 **아직 조용히 무시된다.** 단위 5가 그것을 오류로 바꾼다.

> ⚠ **단위 3 종료 시점은 "일관"하지만 "완결"은 아니다.** 여기서 멈추면 지원 조합이 하나뿐인 상태로 남는다. 그래도 저장소는 깨지지 않는다 — 다만 **단위 5를 반드시 같은 작업 묶음에서 끝낸다.** 그러지 않으면 §함정이 그대로 실현된다.

---

### 단위 4 — 분기 3(`_solve_tandem_junction_bf`, Phase B / bifacial)에 벌크 평면

단위 3과 **같은 변경을 다른 레이아웃에** 적용한다. `Nrm`(rear metal)이 끼어 오프셋이 하나 더 밀린다.

**Files:**
- Modify: `2L_FEST.py:5378-5710` (`_solve_tandem_junction_bf`)
- Test: `tests/test_base_lateral.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다 — 두 분기가 같은 답을 주는가**

**이것이 §함정에 대한 직접적인 방어다.**

```python
def test_full_area_and_bifacial_agree_when_rear_is_equivalent(fest, make_mono,
                                                              make_bifacial):
    """rear를 전기적으로 등가하게 두면 두 분기가 같은 답을 줘야 한다.

    "한 곳만 고치면 경로에 따라 결과가 갈린다"(WORKLOG §3)를 잡는 테스트다.
    단위 3만 하고 단위 4를 빼먹으면 여기서 걸린다.
    """
    dp = _dp(fest, 100.0); dp.Rs_base = 500.0
    J_fa = _cell_current(make_mono(), dp)
    J_bf = _cell_current(make_bifacial(), _equivalent_bifacial(dp))
    assert J_bf == pytest.approx(J_fa, rel=1e-3)
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_base_lateral.py -q -k agree` → FAIL (bifacial 분기가 `Rs_base`를 무시한다)

- [ ] **Step 3: `_solve_tandem_junction_bf`에 6번째 평면을 넣는다**

`Ns = 5*N + Nm + Nrm`, `oVbase = 4*N + Nm + Nrm`. 잔차·야코비안은 단위 3과 같은 표. **`_warm_V_junc_bf` 캐시 길이도 함께 바뀐다** — `Rs_base` 변경 시 무효화는 단위 2의 해시가 처리한다.

- [ ] **Step 4: 야코비안 유한차분 + 비특이성을 이 분기에도 적용한다**

단위 3 Step 1의 두 테스트를 `make_bifacial`로 파라미터화한다. **"단위 3과 비슷하게"가 아니라 실제로 파라미터에 추가한다** — 분기별로 다른 코드이므로 별도 검증이 필요하다.

- [ ] **Step 5: 연속법(homotopy) 경로 확인**

`solve_tandem`(`:4694-4725`)은 `Rs_junction > 50`일 때 `[50, 200, 1000, 5000, target]`으로 램프한다. **각 램프 스텝이 `_build`를 다시 부르므로 `_K_base`도 매번 재조립된다** — 비용은 늘지만 정확하다. 램프 중 warm-start 벡터 길이가 일관되는지 확인한다.

```bash
python -m pytest tests/test_junction_bf.py -q     # 기존 4건 통과 유지
```

- [ ] **Step 6: 전체 스위트 + 비트 핀 + 커밋**

```bash
python -m pytest -q -m "not slow"
python -m pytest tests/test_default_pin.py tests/test_legacy_pin.py -q
git add 2L_FEST.py tests/test_base_lateral.py
git commit -m "v28.61: 벌크 횡전도 — Phase B bifacial 분기 (7분기 중 2)"
```

**회귀 영향 범위:** `_solve_tandem_junction_bf` + 연속법 경로. off 불변.

---

### 단위 5 — 나머지 5개 분기에서 **명시적 거부** 🔒

**§함정의 해독제.** 지원하지 않는 조합에서 `Rs_base`가 지정되면 조용히 무시하지 말고 거부한다.

**Files:**
- Modify: `2L_FEST.py:4679` (`solve_tandem` 디스패치 앞), `2L_FEST.py:6238` (`solve_single` 진입)
- Test: `tests/test_base_lateral.py`

- [ ] **Step 1: 실패하는 테스트를 쓴다 — 미지원 조합은 오류다**

```python
UNSUPPORTED = [
    ("full_area", 0.0,   True,  "Phase A"),        # 분기 1
    ("bifacial",  0.0,   True,  "Phase A"),        # 분기 5
    ("single",    None,  False, "단일셀"),          # 분기 6·7
]


@pytest.mark.parametrize("rear_mode,rs_j,legacy,label", UNSUPPORTED)
def test_unsupported_branch_rejects_base_map(fest, make_mono, make_bifacial,
                                             monkeypatch, rear_mode, rs_j,
                                             legacy, label):
    """조용히 무시하면 "켰는데 결과가 안 변한다"로 나타난다 — 오류도 경고도 없이.

    v28.43(n_probe_points=0) · v28.54(extraction_method) · v28.57(로더)의
    같은 판단: 잘못된 입력은 고치지도 무시하지도 말고 거부한다.
    """
    ...
    dp.Rs_base = 500.0
    with pytest.raises(ValueError) as exc:
        _solve(fest, m, dp, Vb=0.0, mode=mode)
    msg = str(exc.value)
    assert "Rs_base" in msg
    assert label in msg or "지원" in msg
    assert "Rs_junction" in msg or "Phase B" in msg     # 어떻게 하면 되는지 안내
```

- [ ] **Step 2: 실패 확인** — Run: `python -m pytest tests/test_base_lateral.py -q -k unsupported` → FAIL (아무것도 안 던진다)

- [ ] **Step 3: 디스패치 앞에 게이트를 넣는다**

```python
# solve_tandem 진입부, _build 직후
if dp.Rs_base is not None and not self._base_supported(dp):
    raise ValueError(
        f"벌크 횡전도(Rs_base={dp.Rs_base} Ω/sq)는 Phase B tandem에서만 "
        f"지원한다 — 현재 rear_mode={self.geo.rear_mode!r}, "
        f"Rs_junction={dp.Rs_junction}. Rs_junction > 0으로 두거나 "
        f"Rs_base=None으로 해제할 것. (계획 단위 5: 7개 잔차 분기 중 2곳만 지원)")
```

`solve_single`에도 같은 게이트를 둔다(문구는 단일셀용으로).

- [ ] **Step 4: 통과 확인 + off는 여전히 조용한지**

```python
def test_unsupported_branch_is_silent_when_base_is_off(fest, make_mono):
    """Rs_base가 None이면 미지원 분기도 예전처럼 조용히 잘 돈다."""
```

Run: `python -m pytest tests/test_base_lateral.py -q`
Expected: PASS

- [ ] **Step 5: 전체 스위트 + 비트 핀 + 커밋**

```bash
python -m pytest -q -m "not slow"
python -m pytest tests/test_default_pin.py tests/test_legacy_pin.py -q
git add 2L_FEST.py tests/test_base_lateral.py
git commit -m "v28.62: 벌크 횡전도 미지원 분기 명시적 거부 (조용한 무시 제거)"
```

**회귀 영향 범위:** `solve_tandem`·`solve_single` 진입부에 가드 1개씩. **`Rs_base is None`이면 가드가 통과만 하므로 기존 경로 불변** — 비교 연산 하나가 추가될 뿐 부동소수점 연산은 없다.

---

### 단위 6 — 물리 검증 (프로덕션 코드 0줄)

on 경로가 **맞는 답**을 주는지 확인한다. 단위 3~5는 "레이아웃이 일관되는가"를 봤고, 여기서는 "물리가 맞는가"를 본다.

**Files:**
- Modify: `tests/test_base_lateral.py`

- [ ] **Step 1: 해석해 극한 3개를 고정한다**

```python
def test_base_zero_lateral_matches_lumped_rs_vert(fest, make_mono):
    """Rs_base → ∞ 이면 벌크가 횡전도에 기여하지 않으므로,
    기존 Rs_vert_bot 사후 보정 모델과 물리적으로 같아야 한다."""


def test_base_perfect_lateral_removes_base_resistive_loss(fest, make_mono):
    """Rs_base → 0 이면 벌크가 등전위 → 벌크 저항 손실이 사라진다."""


def test_base_loss_scales_with_sheet_resistance(fest, make_mono):
    """Rs_base를 2배로 하면 벌크 저항 손실도 (저저항 극한에서) 약 2배."""
```

- [ ] **Step 2: 손실 배분에 벌크 항이 나타나는지 확인한다**

`losses()`·FF 워터폴에 벌크 성분이 빠져 있으면 **손실 합이 안 맞는다.** 에너지 균형 테스트(`tests/test_invariants.py:65,79`)를 벌크 on 조건으로 파라미터화한다.

- [ ] **Step 3: 새 기준값을 캡처한다 (원 캡처 PC에서)**

on 경로는 새 물리이므로 **비트 핀 대상이 아니라 새 핀 대상**이다. `PINNED_STACK`·OS·아키텍처·BLAS를 **함께 기록**한다 — `docs/WORKLOG.md` §1-1-a가 요구하는 항목.

- [ ] **Step 4: 전체 스위트 + 커밋**

```bash
git add tests/test_base_lateral.py
git commit -m "test: 벌크 횡전도 물리 검증 — 극한 3개 + 에너지 균형 + 새 핀"
```

**회귀 영향 범위: 없음.** 테스트만.

---

### 단위 7 — GUI + 문서·버전 마무리

- [ ] **Step 1: GUI 입력란**

STEP 1(Design)의 **REAR DESIGN 카드** 또는 STEP 3(Diode)에 `Rs_base` 한 줄. 라벨은 `Bulk R ↔`(횡전도 `↔` 규약), 단위 `Ω/sq`, **빈칸 = off(`None`)**. `Rs_vert_bot`(`↕`)과 나란히 두면 수직/횡 대비가 드러난다.

**i18n 키를 EN/KR 양쪽에 넣는다.** `_TR`에 `bulk_lateral` / `bulk_lateral_hint`. 힌트에 **`Rs_vert_bot`과의 차이**를 적는다 — 이름이 비슷해 혼동하기 쉽다.

- [ ] **Step 2: 사이드바 카드 헤더를 `_card_headers` 위치 zip에 넣지 않는다**

v28.58의 SPATIAL MAPS와 같은 함정 — 그 zip은 4개 위치 고정 매핑이라 5번째를 넣으면 라벨이 조용히 엇갈린다.

- [ ] **Step 3: 문서**

| 문서 | 갱신 |
|---|---|
| `2L_FEST.py` 헤더 changelog + `__build__` | 최종 버전 확인 |
| `docs/pro_feature_map_2026-08-14.md` #8 | **미구현 → 구현(범위 명시)**. 개정 이력 표에 줄 추가. **"7개 분기 중 2곳 지원"을 판정 문구에 넣는다** — #6에서 "자체 규약"을 명시한 것과 같은 이유 |
| `docs/registration_material.md` | §2-5 기능 목록 + §7 한계(지원 범위) + 수치 재생성 |
| `docs/WORKLOG.md` | §3 우선순위 2 → §2-7 완료 이동. **번호 재조정 금지**(우선순위 3 참조가 어긋난다) |
| `docs/base_lateral_convention.md` | 단위 1의 결정이 구현과 일치하는지 최종 확인 |
| `docs/sessions/` | 세션 기록 |

- [ ] **Step 4: 등록 자료 수치 재생성**

```bash
python -m pytest -q -m "not slow" > pytest.log
python scripts/gen_registration_stats.py --from-log pytest.log --write
python scripts/gen_registration_stats.py --from-log pytest.log --check
```

- [ ] **Step 5: 커밋**

**회귀 영향 범위:** GUI 레이아웃(사이드바 세로 넘침 — `_gui_i18n_check.py`가 판정) + `tests/test_gui_layout.py`. 문서 + `__build__`.

---

## 미해결 — 단위 1에서 판정할 것

1. **단위계** — Ω/sq(권고) vs Ω·cm+두께. §설계 결정 1. **B안이면 두께 입력 신설이 단위 2로 들어온다.**
2. **토폴로지** — α 직렬 삽입(권고) vs β 병렬 합산. §설계 결정 2. **β면 단위 3~5가 통째로 작아진다**(평면이 늘지 않으므로 7분기를 손댈 필요가 없다).
3. ~~**`Rs_vert_bot` 이중 계산**~~ — ✅ **종결 (2026-08-18): ㄴ 거부 확정.** 둘 다 0이 아니면 `ValueError`. 근거는 §설계 결정 3.
4. **`Gv_base` 하한값** — `RS_JUNCTION_MIN = 0.1`과 같은 성격의 클램프가 필요한가. §특이성.
5. **단일셀 지원 여부** — 이 계획은 거부한다. 필요해지면 **별도 항목으로 신설**하며, 그때도 물리 변경 있음으로 분류된다.

---

## 예상 규모

| 단위 | 프로덕션 | 테스트 | 문서 | 비트 핀 확인 |
|---|---|---|---|---|
| 0 특성화 | 0줄 | ~150줄 | — | 불필요 |
| 1 결정 🚧 | 0줄 | 0줄 | 신규 1 + 계획 갱신 | 불필요 |
| 2 파라미터 | ~15줄 | ~80줄 | changelog | **필수** |
| 3 분기 2 | ~120줄 | ~120줄 | changelog | **필수** |
| 4 분기 3 | ~130줄 | ~80줄 | changelog | **필수** |
| 5 거부 🔒 | ~25줄 | ~70줄 | changelog | **필수** |
| 6 물리 검증 | 0줄 | ~150줄 | — | 새 핀 캡처 |
| 7 GUI·문서 | ~60줄 | ~40줄 | 5개 문서 | 불필요 |

> 단위 3·4가 **비슷해 보이지만 복붙하면 안 된다.** 오프셋 식과 야코비안 블록 구성이 다르고, `_solve_tandem_junction_bf`에는 rear metal 결합(`Gc_rear`)이 추가로 있다. 단위 4 Step 1의 교차 일치 테스트가 복붙 실수를 잡는 장치다.
