# Metal Optical Transparency 설계

> **작성**: 2026-08-14
> **대상 빌드**: `GEDOS.py` v28.54, 브랜치 `fix/extraction-method-disable`
> **근거**: Griddler 2.5 & PRO Manual v7.0 §2.7 (p.28) — 2026-08-14 원문 확인
> **관련**: `docs/audit_2026-08-13.md` §5 체크 2 (미구현 판정), `docs/griddler_feature_map.md` §2.4
> **상태**: 설계 승인됨 (2026-08-14)

---

## 1. 정의 (매뉴얼 §2.7)

```
metal optical transparency  T = 1 − (optical width / physical width)
기본값 T = 0  →  optical width == physical width (차폐 감소 없음)
```

- **physical width** → contact area를 정한다. 접촉 컨덕턴스와 금속 저항이 여기에 걸린다.
- **optical width** → 빛을 가리는 정도를 정한다. shading이 여기에 걸린다.
- finger와 busbar 각각 지정한다.
- 물리적 근거: 빛이 금속 facet에서 셀로 직접 산란하거나, 모듈에서는 facet 산란 후 glass–air 계면에서 내부 반사되어 셀로 되돌아온다. 그래서 통상 optical width < physical width다.

---

## 2. 왜 지금 배선이 쉬운가

엔진은 이미 shading을 두 경로로만 소비하고, 접촉·저항 경로는 물리 폭으로 분리되어 있다.

```
(a) 발전량 스케일      _build()  3977-3983
      _sh_geo  = shading_fraction()                 ← 설계 물리 폭 (기준)
      _sh_case = shading_fraction(wf, wb_case)      ← ★ 광학 폭으로 교체
      _gen_s   = (1 − _sh_case) / (1 − _sh_geo)
      illum_frac = _illum_frac_base × _gen_s

(b) 손실 line-item     losses()  6913
      shade_frac = shading_fraction(wf, wb_eff)     ← ★ 광학 폭으로 교체
      P_shade    = shade_frac × Jmpp × Vmpp

(c) 접촉·저항          _Gc 3949-3961, assemble_K_met_1d 3943
      전부 물리 폭 사용 — 손대지 않는다
```

**`_sh_geo`는 물리 폭으로 유지한다.** 이것이 비율의 분모 기준이다. T=0이면 `_sh_case == _sh_geo` → `_gen_s = 1` → 기존 경로와 **산술적으로 동일**하다. 요구사항 3(비트 동일)이 구조로 성립한다.

기존 훅 `shading_fraction(w_f_opt, w_b_opt)`은 이미 "이 폭이면 shading이 얼마"라는 순수 함수다. T를 이 함수 **안에** 넣지 않고, 호출자가 광학 폭을 계산해 넘긴다. 경계가 깨끗하고 어느 호출자가 물리/광학을 원하는지 호출부에서 드러난다.

---

## 3. API

```python
class GridDesign:
    def __init__(..., optical_transparency_f=0.0, optical_transparency_b=0.0):
        ...

    def optical_widths(self, w_f, w_b):
        """물리 폭 → 광학 폭. T=0이면 입력을 그대로 반환한다."""
        return (w_f * (1.0 - self.optical_transparency_f),
                w_b * (1.0 - self.optical_transparency_b))
```

검증: `0 ≤ T < 1`. T=1은 광학 폭 0을 뜻해 물리적으로 무의미하므로 배제한다.

---

## 4. busbar recovery factor와의 상호 배타

**이 설계에서 가장 중요한 결정이다.**

`front_electrode/adapter.py`의 `busbar_recovery_factor`가 이미 같은 물리를 모델링한다.

| | busbar recovery factor (기존) | optical transparency (신규) |
|---|---|---|
| 물리 | busbar가 가린 빛 일부가 반사되어 재입사 | 금속 facet 산란으로 optical width < physical width |
| 계층 | adapter **사후 line-item** | 엔진 **입력** |
| FEM 피드백 | **없음** (adapter 25-29행이 명시) | **있음** (`_gen_s` 경유) |
| 수식 | `recovered = raw_bb × f` | `w_b_opt = w_b × (1−T_b)` |

둘 다 켜면 같은 빛을 두 번 회수한다. **동시 지정은 `ValueError`로 막는다.** 조용히 둘 다 적용되는 것이 최악이다.

finger에는 recovery 모델이 없으므로 `optical_transparency_f`는 충돌하지 않는다.

### 어느 쪽이 기본인가 — recovery가 기본, T는 opt-in

T 쪽이 물리적으로 더 엄밀하지만(회수광이 FEM 전류에 실제로 반영된다), **지금 갈아타지 않는다.** T 값의 근거가 될 문헌값·측정값이 아직 없기 때문이다. 근거 확보 후 재검토한다.

따라서:
- `busbar_recovery_factor`는 기존 기본값·거동을 그대로 유지한다.
- `optical_transparency_b`는 기본 0이며, 쓰려는 사람이 명시적으로 켠다.
- 기존 KIST 스윕 결과(recovery 25%)는 아무 영향을 받지 않는다.

### 에러 메시지 규약

메시지는 **어느 쪽을 0으로 둘지 안내**해야 한다. 진단만 하고 끝내면 사용자가 어느 쪽을 포기해야 하는지 모른다.

```
ValueError:
  busbar_recovery_factor(=0.25)와 optical_transparency_busbar(=0.30)를
  동시에 쓸 수 없다 — 같은 물리(busbar 반사광 회수)를 두 번 계산한다.
  · 기존 방식 유지: optical_transparency_busbar=0 으로 둘 것 (권장 — 현재 기본)
  · 광학 폭으로 전환: busbar_recovery_factor=0 으로 둘 것
    (T 값의 문헌/측정 근거가 있을 때만)
```

---

## 5. 보고 경로 — 광학으로 통일

엔진의 `shading_fraction()` 호출부는 14곳이다. **`_sh_geo`(3977) 하나만 물리로 남기고 나머지는 전부 광학**으로 간다. 사용자가 화면에서 읽는 "Shading"은 실제로 잃는 빛이어야 한다. T=0에서는 전부 동일하므로 회귀 위험이 없다.

대상: summary(1473), 리포트(7534, 12781, 12788), GUI 상태(8772), DXF 프리뷰(9865), COMPARE(11176-77), 워터폴(12122-27), `losses()`(6913), `_sh_case`(3978).

---

## 6. CSV — 물리 shading과 광학 shading을 둘 다 기록

T>0일 때 "금속이 덮은 면적"과 "빛을 잃은 면적"은 다른 값이며, 논문에서 이 둘을 구분해 설명할 수 있어야 한다. T=0이면 같은 값이라 무해하다.

**adapter 반환 `results`에 두 키를 추가한다** (`export_csv`가 `parameters` + `results`를 쓰므로 자동으로 CSV에 실린다):

| 키 | 의미 | 계산 |
|---|---|---|
| `shading_physical` | 금속이 덮은 면적 비율 | `shading_fraction(wf, wb_eff)` — 케이스 물리 폭 |
| `shading_optical` | 빛을 잃은 면적 비율 | `shading_fraction(*optical_widths(wf, wb_eff))` — 같은 케이스 폭의 광학 환산 |

둘 다 **케이스 폭** 기준이다 (설계 폭이 아니라 그 실행에 실제로 쓰인 폭). T=0이면 두 값이 정확히 같다.

`engine_raw["total_shading"]`은 **기존 의미(물리) 그대로 두고 건드리지 않는다.** 회귀 핀이 이 키를 참조하므로 의미를 바꾸면 안 된다. 이 값은 §5의 엔진 호출부가 아니라 adapter의 `busbar_shading_breakdown()`이 따로 계산하므로, §5의 "보고 경로 광학화"와 충돌하지 않는다 — 서로 다른 코드 경로다.

**roadmap 러너 CSV에도 같은 두 컬럼을 싣는다.** roadmap CSV가 곧 논문 figure의 데이터 원장이므로 여기에 없으면 위 목적을 달성하지 못한다. `front_electrode/roadmap.py`의 `build_row`가 `out["results"]`에서 두 키를 읽어 추가한다.

> 명명 주의: `results`에 이미 `optical_loss`가 있으나 그것은 **전력**(mW/cm²)이다. 새 두 키는 **면적 비율**이다. 혼동을 막기 위해 `optical_*` 대신 `shading_*` 접두를 쓴다.

---

## 7. rear 범위 — front만 배선, rear는 경고

`GridDesign`이 front/rear 공용 클래스라 rear 인스턴스에도 속성이 생기지만 **front만 배선한다.** 근거: `shading_fraction()`은 전면 기하(`fg_x_range`, `bb_y_range`)만 계산하고, bifacial rear의 후면 입사광 차폐는 현재 모델에 아예 없다.

**단, 조용한 no-op으로 남기지 않는다.** `_build()`에서 `geo.rear`의 T가 0보다 크면 경고를 출력한다.

> `extraction_method`(v28.54에서 방금 비활성화)가 정확히 "GUI/입력에는 있는데 솔버가 읽지 않는" 사례였다. 그것을 고쳐놓고 같은 함정을 새로 만들 수는 없다.

---

## 8. GUI

`FRONT GRID DESIGN` 카드에 2행을 추가한다.

```
Finger optical T   [0.0]   0~1
Busbar optical T   [0.0]   0~1
```

- 범위 검증 `0 ≤ T < 1`. 위반 시 기존 `_require_range` 관용구로 에러.
- **DESIGN 탭 프리뷰에 광학 폭을 점선으로 겹쳐 그린다.** T가 실제로 먹고 있음을 눈으로 확인시키는 장치다.
- 후면 카드에는 넣지 않는다 (§7).

---

## 9. 스윕 축

```
adapter grid_params:   optical_transparency_finger, optical_transparency_busbar
optimize_grid 인자:    transparency_finger_list=(0.0,), transparency_busbar_list=(0.0,)
adapter _grid_overrides: 두 키 추가 (roundtrip 비트 동일 보존)
```

기본값이 단일원소 튜플이므로 축을 주지 않으면 조합 수가 그대로다.

### 조합 수 확인 프롬프트 — 라이브러리가 아니라 CLI에서

`optimize_grid`가 7축 → **9축**이 된다. 조합 수가 **50**을 넘으면 실행 전에 사용자 확인을 받는다 (M10 1조합 ≈17분 → 50조합 ≈14시간).

**⚠ 프롬프트를 `optimize_grid` 안에 넣으면 안 된다.** 이 함수는 pytest와 백그라운드 드라이버에서도 호출된다. 라이브러리 안에서 `input()`을 부르면 테스트가 멈추고, 비대화형 실행은 EOF로 죽는다.

구조:

```python
COMBO_CONFIRM_THRESHOLD = 50

# 라이브러리 — 판단만 하고 결정은 호출자에게 위임한다.
# confirm: (n_combos: int) -> bool.  True면 진행, False면 취소.
def optimize_grid(..., confirm=None):
    grid_list = [...]                       # 축 전개
    if len(grid_list) > COMBO_CONFIRM_THRESHOLD and confirm is not None:
        if not confirm(len(grid_list)):
            raise RuntimeError(
                f"{len(grid_list)}개 조합 실행이 사용자에 의해 취소되었다")
    ...
```

- `confirm=None`(기본) → 프롬프트 없음. 테스트·백그라운드 실행은 지금과 동일하게 동작한다.
- CLI(`scripts/optimize_m10.py`)가 대화형 확인 함수를 주입한다. `--yes` 플래그로 건너뛸 수 있다.
- CLI는 확인 문구에 **예상 소요 시간**을 함께 보여준다 (조합 수 × 최근 실측 1조합 시간).

---

## 10. 테스트

| 테스트 | FEM | 내용 |
|---|---|---|
| `test_optical_widths_pure` | ✗ | 헬퍼 순수 함수. T=0 항등, T=0.3에서 0.7배 |
| `test_transparency_range_validation` | ✗ | T<0, T≥1 → `ValueError` |
| `test_transparency_zero_bit_identical` | ✓ 20mm | **T=0 전달 == 미전달.** `tests/test_optimizer.py:96-106` 선례 그대로 (cell 20mm / AX=36 / NPTS=6 / `==` 비교) |
| `test_transparency_does_not_touch_contact` | ✓ 20mm | **핵심** — T를 바꿔도 `Pc`·`Pf_finger` **불변**, `P_shade`만 감소하고 `Eff` 증가 |
| `test_transparency_conflicts_with_recovery` | ✗ | 동시 지정 → `ValueError`. 메시지에 양쪽 해결책이 모두 들어있는지도 확인 |
| `test_rear_transparency_warns` | ✓ 20mm | rear T 설정 시 경고 출력 (`capsys`) |
| `test_shading_columns_physical_and_optical` | ✓ 20mm | T=0에서 두 컬럼 동일, T>0에서 optical < physical |
| `test_transparency_sweep_axis` | ✓ 20mm | `optimize_grid` 축 전달 + 조합 수 반영 |
| `test_combo_confirm_not_called_by_default` | ✗ | `confirm=None`이면 프롬프트 경로에 들어가지 않음 (테스트 정지 방지의 실증) |

`test_transparency_does_not_touch_contact`가 이 기능의 정의다 — 물리 폭과 광학 폭의 분리를 수치로 못박는다.

**착수 전제**: `pytest -m "not slow"` 베이스라인이 초록이어야 한다. 최근 실측(2026-08-14) **128 passed / 2 deselected / 6 xfailed**.

---

## 11. 비범위

- **rear 광학 차폐 모델링** — 후면 입사광 차폐 자체가 현재 모델에 없다. T만 얹어봐야 근거가 없다.
- **T의 문헌값·측정값 데이터베이스** — 값의 근거 확보는 별개 과제이며, 그 전까지 T는 opt-in으로 남는다.
- **recovery factor 제거** — T로 완전히 갈아타는 것은 근거 확보 후 재검토한다.
- **DXF 임포트 패턴에서의 T** — DXF 경로는 rect별 고유 폭을 쓰므로 단일 T 적용이 정의되지 않는다. 현행처럼 케이스-폭 머신너리가 비활성이다.
