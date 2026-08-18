# ✅ 단위 1 완료 — 2026-08-19 야간 무인 실행 요약

> **아침에 이 파일만 읽으면 된다.** 상세는 각 세션 기록에, 무엇을 바꿨는지는 커밋
> 메시지에 있다.

**상태: ✅ 우선순위 0 단위 0 · 단위 1 완료. 우선순위 3 계획서 작성 완료.**
중단 없음. 되돌린 것 없음. 워킹트리 깨끗.

---

## 커밋 목록 (3건, 전부 `origin/main`에 푸시됨)

| 커밋 | 내용 |
|---|---|
| `40d4ea9` | **단위 0** — 분기 커버리지 특성화 (프로덕션 0줄). 7 files, +1386/−26 |
| `49222fa` | **v28.61 단위 1** — `_diode_node_arrays` 중앙화, 결함 해소. 5 files, +673/−264 |
| `<이 커밋>` | 우선순위 3 계획서 + 진행 로그 + 이 요약 |

시작 HEAD `4a16f8d` → 현재 `main`.

---

## 테스트 수치

| 시점 | 전체 비-slow 회귀 | 비트 핀 |
|---|---|---|
| 단위 0 (v28.60) | **391 passed · 2 deselected · 38 xfailed · 0 failed** (1688 s) | strict 2 passed |
| 단위 1 (v28.61) | **423 passed · 2 deselected · 6 xfailed · 0 failed** (1671 s) | strict 2 passed |

**회귀 0건.** `391 + 32 = 423`, `38 − 32 = 6` — 늘어난 통과는 **전부** 단위 0의
xfail이 전환된 것이다. XPASS 0건. 남은 xfail 6건은 `test_junction_bf`의 Vb=0 잔차
평탄화(비-strict, 기존 항목).

판정 파일 `tests/test_spatial_branch_coverage.py`: 97건 — 단위 0에서
65 passed/32 xfailed → 단위 1에서 **97 passed / 0 xfailed**.

### 비트 동일 검증 (가장 중요한 것)

Phase A / full_area는 v28.60에서 **유일하게 올바른 탠덤 경로**였다. 단위 0이 수정
전에 캡처해 둔 5조합(무맵 + 맵 4종)의 전압장 sha256과 `cell_current`가
**v28.61 이후 전부 정확히 일치**한다. 리팩터가 값을 건드리지 않았다는 증거다.

환경: 집 데스크톱 (Win10 / AMD64 / scipy-openblas / py 3.14.3 · numpy 2.4.3 ·
scipy 1.17.1) — **핀 스택**, `stack_mismatch() is None`. 전부 `python -m pytest`.

---

## 무엇을 고쳤나

`spatial_j01`/`j02`/`gen` 세 맵이 프로덕션 tandem 설정 **전부**에서 잔차에
미반영이던 결함. **기본 설정(`Rs_junction=5000`)이 결함 경로**였고,
`cell_current`가 맵을 무조건 적용해 ΔJ ≠ 0이 나오는 바람에 **겉보기에는 작동하는
것처럼 보였다** — 그래서 오래 남았다.

`FESTSolver._diode_node_arrays` 신설로 조립 지점을 하나로 모았다.
census **34줄/13함수 → 4줄/1함수**.

---

## 단위 0이 찾아낸 것 — 계획서 전제 네 개가 틀렸다

| # | 계획서 | 실제 |
|---|---|---|
| 1 | 결함 분기 4개 | **5개** — `_solve_single_bifacial`(`2L_FEST.py:6513` 부근) |
| 2 | 소비 지점 9곳 | **13개 함수 34줄** — `losses`·`recomb_currents`·`_tab_current` 추가 |
| 3 | `J01_top_arr`가 스칼라 | **아니다.** `mf`가 배열이라 결함 분기에서도 `ndarray[N]` |
| 4 | 결함 칸 9개 | **12개** |

5번째 분기 때문에 `tests/test_base_lateral.py`의 `_NAMED_SOLVERS`도 고쳤다 —
그 분기를 감시하지 않아 커버리지 테스트가 통과해 버리고 있었다.
**벌크 횡전도에는 이 누락으로 인한 공백이 없었다**(`Rs_base`는 `_build` 안이라
디스패치보다 앞이다). 표의 라벨만 틀렸고 기능 커버리지는 온전했다.

부수로, KIST 캡처 비트 핀 2건이 **집 데스크톱에서 strict 통과**함을 확인해
WORKLOG §1-1-a/§1-2를 갱신했다 — **핀 스택 머신이 둘, 불일치는 맥북 하나뿐**이다.

---

## ▶ 다음 착수 지점: 우선순위 0 **단위 2** (문서만)

물리·코드 검증은 끝났다. 남은 것은 **낡은 문서를 실제 상태로 맞추는 것**이다.

| 대상 | 해야 할 것 |
|---|---|
| `docs/spatial_map_convention.md` §6 | 결함 → **해소** (24칸 표는 단위 0에서 이미 정정했다. 서술만) |
| `docs/pro_feature_map_2026-08-14.md` #6 | 부분구현 → **구현** (3차 개정) |
| `docs/WORKLOG.md` §2-6 | 보류 블록 해제 |
| `docs/registration_material.md` | v28.61 항목 추가 판단 |

상세는 `docs/WORKLOG.md`의 **▶ 다음 착수 지점** 절.

### 별건으로 기록해 둔 것 (단위 2 범위 밖)

- **바닥 서브셀 pass/metal 가중** — 헬퍼가 `dp.J01_bot`(=`J01_bot_pass`)만 쓰고
  `J01_bot_metal`은 아무도 읽지 않는다. `DiodeParams` 주석이 예고해 둔 항목이나
  v28.61은 v28.60 동작 보존이 조건이라 건드리지 않았다. → unit1 기록 §5
- **`_bf_v29`의 `Jph_b_eff`** — 원래부터 `illum_frac`이 없는 스칼라라 gen 맵을 곱할
  기준이 없다. 죽은 경로이므로 배선하지 않았다. → unit1 기록 §4-(a)
- **`_tab_current`의 `VT_ = 0.02585`** — 모듈 `VT`와 다르다. 통일하면 표시값이 바뀐다
- **`Rsh` 5번째 대상** — 박사님 지시로 보류

---

## 우선순위 3 계획서 (코드 0줄)

`docs/superpowers/plans/2026-08-19-capacitive-effects.md`

읽을 때 알아 둘 두 가지.

1. **매뉴얼 PDF가 저장소에 없다.** §6.6 관련 in-repo 기록은
   `docs/griddler_feature_map.md:310`의 `| 6.6 | Transient 특성 | C | ? |` 한 줄이고,
   §1.2 Core Model 등가회로도 정리돼 있지 않다. 그래서 계획서는 문장마다
   **[지시] / [repo] / [유도]** 표식을 붙여 근거를 분리했다. base lateral의
   Appendix A.5 오독을 반복하지 않기 위한 규칙 R1~R4도 명시했다.
   **단위 0의 첫 작업이 매뉴얼 확인이다.**
2. **코드로 판정한 결론 두 개**가 WORKLOG의 기존 기술보다 정확하다.
   - 시간 항은 **새 미지수를 만들지 않는다**(음함수 차분이면 대각 기여뿐).
     단, 시간 적분 방식 확정이 전제다.
   - 진짜 구조 변경은 잔차가 아니라 `calc_iv`다. 이력 의존과 양립 불가한 요소가
     넷이라 **`calc_iv_transient`를 신설**하고 기존 경로는 손대지 않는다.

페로브스카이트 이온 이동 히스테리시스는 **범위 밖**이다(PRO에 없고 시간 상수가
3~6자리 다르다). 계획서 §0에 근거를 맨 앞에 적었다.

---

## 지시 대비 이행

| 단계 | 상태 |
|---|---|
| 1. 단위 0 회귀 → 커밋 → 푸시 | ✅ `40d4ea9` |
| 2. 단위 1 구현 → 검증 → 커밋 → 푸시 | ✅ `49222fa` |
| 3. 세션 기록 + 착수 지점 갱신 → 커밋 → 푸시 | ✅ `49222fa`에 포함 |
| 4. 우선순위 3 계획서 → 커밋 → 푸시 | ✅ 이 커밋 |
| 5. 단위 2 이후 / 우선순위 3 구현 **착수 금지** | ✅ 하지 않음 |

**금지 항목 전부 준수**: `PINNED_STACK`·`conftest.py` 무수정, 핀 기준값 재캡처
없음, 물리식 변경 없음, `Rsh` 추가 없음, reset/rebase/force push/브랜치 삭제 없음,
amend 없음.

**단언 약화 없음** — 두 건은 예외 규정에 해당하며 근거를 주석에 남겼다.

1. `test_mode_single_never_reaches_tandem_branches` — 단언이 `== _INLINE`이었는데
   독스트링 명제("tandem 분기에 가지 않는다")보다 **강했다.** 그게 통과했던 것은
   `_NAMED_SOLVERS`에 `_solve_single_bifacial`이 빠져 있었기 때문이다. 명제에 맞게
   `not in _TANDEM_SOLVERS`로 좁혔다.
2. `test_cell_current_delta_is_not_evidence_of_working` →
   `test_phase_b_gen_map_now_reaches_the_residual` — 약화가 아니라 **사실이 바뀌어
   반전**했다. 단위 0에서 그 테스트에 *"단위 1이 고치면 갱신해야 한다"* 고 적어 둔
   그대로다. 남기는 말은 유지했다: **`ΔJ ≠ 0`을 작동 근거로 쓰지 말 것.**

### 한 가지 보고

`git config user.name` / `user.email`이 **설정돼 있지 않아** 커밋할 수 없었다.
기존 커밋 작성자와 동일하게 **저장소 로컬**로만 설정했다(`--global` 아님):
`Seunghoon Lee <tmdgnsppp93@gmail.com>`. 전역 설정은 건드리지 않았다.

또 시스템 Python에 **pytest만** 설치했다(9.1.1 + iniconfig/pluggy/pygments/colorama).
`.venv`는 py 3.11.9 / numpy 2.4.6이라 **핀 스택이 아니고**, 그쪽으로 돌리면 비트 핀이
조용히 xfail로 내려간다. numpy·scipy는 건드리지 않았으므로 핀 스택은 그대로다.
→ 테스트는 `python -m pytest`로 돌릴 것. WORKLOG §1-2에 함께 적었다.
