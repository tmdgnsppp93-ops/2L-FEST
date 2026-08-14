# Metal Optical Transparency 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 금속의 물리 폭(접촉·저항)과 광학 폭(shading)을 분리해, `T = 1 − optical/physical`를 finger·busbar 각각 입력받고 shading 경로에만 적용한다.

**Architecture:** 엔진은 이미 shading을 두 지점(`_build`의 `_sh_case`, `losses`의 `shade_frac`)에서만 소비하고 접촉·저항 경로는 물리 폭으로 분리되어 있다. 그 두 지점만 광학 폭으로 바꾸고 기준값 `_sh_geo`는 물리 폭으로 유지하면 `_gen_s = (1−sh_case)/(1−sh_geo)`가 T=0에서 정확히 1이 되어 비트 동일이 산술로 성립한다. 폭 환산은 `GridDesign.optical_widths()` 헬퍼 하나에 모으고, 보고 경로는 `CellGeometry.optical_shading_fraction()` 편의 메서드로 통일한다.

**Tech Stack:** Python ≥3.10, numpy/scipy/matplotlib/customtkinter (모두 기존 의존성), pytest.

**Spec:** `docs/superpowers/specs/2026-08-14-metal-optical-transparency-design.md` (커밋 `5e9329d`)

## Global Constraints

- **T=0에서 기존 결과가 비트 동일해야 한다.** `w * (1.0 - 0.0)`은 IEEE 754에서 `w`와 정확히 같으므로 헬퍼를 거쳐도 값이 변하지 않는다. 이 성질에 기대므로 헬퍼에서 곱셈 외의 연산(반올림·클램프)을 추가하지 말 것.
- **`_sh_geo`(2L_FEST.py:3977)는 물리 폭으로 유지한다.** 이것이 `_gen_s` 비율의 분모 기준이다. 광학으로 바꾸면 T의 효과가 상쇄된다.
- **접촉·저항 경로는 손대지 않는다** — `_Gc`(3949-3961), `assemble_K_met_1d`(3943)는 물리 폭을 계속 쓴다.
- **`busbar_recovery_factor`가 기본, T는 opt-in.** 기존 KIST 스윕(recovery 25%)의 거동을 바꾸지 않는다.
- **`engine_raw["total_shading"]`의 의미(물리)를 바꾸지 말 것** — 회귀 핀이 참조한다.
- 신규 `.py` 파일 없음. 모든 변경은 기존 파일 수정이다. 수정 파일에는 저장소 SPDX 헤더가 이미 있다.
- 잘못된 입력은 조용히 무시하지 말고 `ValueError`. (v28.43 `n_probe_points=0`, v28.54 `extraction_method` 전례)
- FEM 테스트는 `cell_mm=20.0` + `AX=36` / `NPTS=6` (`tests/test_optimizer.py:96-106` 관용구).
- 베이스라인: `pytest -m "not slow"` → **128 passed / 2 deselected / 6 xfailed** (2026-08-14 실측).
- 커밋 메시지 말미에 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`. PowerShell에서 큰따옴표가 인자 파싱을 깨뜨리므로 `git commit -F <파일>`로 넘길 것.

## File Structure

| 파일 | 이 계획에서의 책임 |
|---|---|
| `2L_FEST.py` | `GridDesign` T 파라미터·`optical_widths()`, `CellGeometry.optical_shading_fraction()`, 엔진 배선 2곳, 보고 경로 10곳, rear 경고, GUI 입력·프리뷰, changelog/버전 |
| `front_electrode/adapter.py` | `grid_params` 키 2개, recovery 상호배타 `ValueError`, `results`에 shading 2컬럼 |
| `front_electrode/optimizer.py` | 스윕 축 2개, `COMBO_CONFIRM_THRESHOLD`, `confirm` 콜백 |
| `front_electrode/roadmap.py` | CSV 행에 shading 2컬럼 |
| `scripts/optimize_m10.py` | 대화형 확인 함수 주입, `--yes` |
| `tests/test_transparency.py` | 신규 — 이 기능 전용 테스트 |
| `tests/test_roadmap.py` | `_fake_out`에 2키 추가 |

---

### Task 1: T 파라미터와 폭 환산 헬퍼

순수 함수만 다룬다. FEM 없음.

**Files:**
- Modify: `2L_FEST.py:960-980` (`GridDesign.__init__`), `2L_FEST.py:1302` 부근 (`CellGeometry`)
- Create: `tests/test_transparency.py`

**Interfaces:**
- Produces:
  - `GridDesign(..., optical_transparency_f=0.0, optical_transparency_b=0.0)`
  - `GridDesign.optical_widths(w_f, w_b) -> tuple[float, float]`
  - `CellGeometry.optical_shading_fraction(w_f=None, w_b=None) -> float`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_transparency.py` 신규 생성:

```python
# SPDX-FileCopyrightText: © 2026 KIST (Korea Institute of Science and Technology),
#   Dr. Inho Kim's Solar Cell Research Team. Developed by Seunghoon Lee.
# SPDX-License-Identifier: LicenseRef-KIST-Proprietary — see LICENSE.
"""Metal Optical Transparency 테스트.

정의(Manual v7.0 §2.7): T = 1 − optical_width/physical_width, 기본 0.
physical → contact area / 금속 저항, optical → shading.

순수 함수는 FEM 없이 즉시 검증하고, 엔진 배선만 20mm 소셀로 확인한다
(tests/test_optimizer.py:96-106의 AX/NPTS 관용구와 동일).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

AX = 36
NPTS = 6


def test_optical_widths_identity_at_zero(fest):
    """T=0이면 입력 폭을 그대로 돌려준다 — 비트 동일의 근거."""
    g = fest.GridDesign()
    assert g.optical_transparency_f == 0.0
    assert g.optical_transparency_b == 0.0
    w_f, w_b = 50e-4, 200e-4
    assert g.optical_widths(w_f, w_b) == (w_f, w_b)


def test_optical_widths_scales_each_side(fest):
    """finger와 busbar에 각각 다른 T가 걸린다."""
    g = fest.GridDesign(optical_transparency_f=0.3, optical_transparency_b=0.5)
    of, ob = g.optical_widths(100e-4, 200e-4)
    assert of == pytest.approx(70e-4)
    assert ob == pytest.approx(100e-4)


def test_transparency_range_validation(fest):
    """T<0 과 T>=1 은 ValueError. T=1은 광학 폭 0이라 무의미하다."""
    with pytest.raises(ValueError, match="optical_transparency_f"):
        fest.GridDesign(optical_transparency_f=-0.1)
    with pytest.raises(ValueError, match="optical_transparency_b"):
        fest.GridDesign(optical_transparency_b=1.0)
    with pytest.raises(ValueError, match="optical_transparency_b"):
        fest.GridDesign(optical_transparency_b=1.5)
    # 경계값은 통과해야 한다
    fest.GridDesign(optical_transparency_f=0.0, optical_transparency_b=0.999)


def test_optical_shading_fraction_matches_physical_at_zero(fest):
    """T=0에서 optical_shading_fraction == shading_fraction (비트 동일)."""
    geo = fest.CellGeometry(cell_w=2.0, cell_h=2.0,
                            front=fest.GridDesign(n_fingers=4, n_busbars=2))
    assert geo.optical_shading_fraction() == geo.shading_fraction()


def test_optical_shading_fraction_less_when_transparent(fest):
    """T>0이면 광학 shading이 물리 shading보다 작다."""
    geo = fest.CellGeometry(
        cell_w=2.0, cell_h=2.0,
        front=fest.GridDesign(n_fingers=4, n_busbars=2,
                              optical_transparency_f=0.4,
                              optical_transparency_b=0.4))
    assert geo.optical_shading_fraction() < geo.shading_fraction()
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_transparency.py -v`
Expected: `TypeError: GridDesign.__init__() got an unexpected keyword argument 'optical_transparency_f'`

- [ ] **Step 3: 최소 구현 작성**

`2L_FEST.py` — `GridDesign.__init__` 시그니처 (960행 부근). `taper_dist_mm=0.0):` 를 다음으로 교체:

```python
                 taper_factor=1.0, taper_dist_mm=0.0,
                 optical_transparency_f=0.0, optical_transparency_b=0.0):
```

`self.pattern_style = pattern_style` 바로 **위**에 검증과 저장을 넣는다:

```python
        # Metal optical transparency (Manual v7.0 §2.7).
        #   T = 1 − optical_width / physical_width,  기본 0 (광학폭 == 물리폭)
        #   physical width → contact area / 금속 저항
        #   optical  width → shading
        # 빛이 금속 facet에서 셀로 산란해 들어오므로 통상 optical < physical이다.
        for _n, _t in (("optical_transparency_f", optical_transparency_f),
                       ("optical_transparency_b", optical_transparency_b)):
            if not (0.0 <= float(_t) < 1.0):
                raise ValueError(
                    f"{_n}는 0 이상 1 미만이어야 한다 (받은 값 {_t!r}). "
                    "T=1은 광학 폭 0을 뜻해 물리적으로 무의미하다.")
        self.optical_transparency_f = float(optical_transparency_f)
        self.optical_transparency_b = float(optical_transparency_b)
```

같은 클래스 안, `compute_positions` 정의 **바로 앞**에 메서드를 추가:

```python
    def optical_widths(self, w_f, w_b):
        """물리 폭 → 광학 폭. T=0이면 입력을 그대로 반환한다.

        곱셈만 쓴다 — IEEE 754에서 w*1.0 == w 이므로 T=0 경로가 비트 동일이다.
        반올림이나 클램프를 넣으면 그 성질이 깨진다.
        """
        return (w_f * (1.0 - self.optical_transparency_f),
                w_b * (1.0 - self.optical_transparency_b))
```

`CellGeometry` — `shading_fraction` 정의(1302행) **바로 다음**에 편의 메서드를 추가:

```python
    def optical_shading_fraction(self, w_f=None, w_b=None):
        """광학 폭 기준 shading. 인자를 생략하면 설계 폭을 쓴다.

        보고 경로는 전부 이 메서드를 쓴다 — 사용자가 화면에서 읽는 "Shading"은
        금속이 덮은 면적이 아니라 실제로 잃는 빛이어야 한다.
        T=0이면 shading_fraction()과 비트 동일하다.
        """
        if w_f is None:
            w_f = self.w_f
        if w_b is None:
            w_b = self.w_b
        return self.shading_fraction(*self.front.optical_widths(w_f, w_b))
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_transparency.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋**

메시지를 `msg.txt`에 쓰고 `git commit -F msg.txt`:

```
feat(transparency): T 파라미터와 폭 환산 헬퍼

Manual v7.0 §2.7의 T = 1 - optical/physical. finger/busbar 각각 지정.
optical_widths()는 곱셈만 써서 T=0에서 입력을 비트 그대로 돌려준다.
보고 경로용 CellGeometry.optical_shading_fraction()도 함께 추가.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```
```bash
git add 2L_FEST.py tests/test_transparency.py
git commit -F msg.txt
```

---

### Task 2: 엔진 배선 + rear 경고 + 비트동일 회귀

**요구사항 3의 실증이 이 태스크에 있다.**

**Files:**
- Modify: `2L_FEST.py:3977-3979` (`_build`의 `_sh_case`), `2L_FEST.py:6913` (`losses`의 `shade_frac`)
- Modify: `tests/test_transparency.py` (append)

**Interfaces:**
- Consumes: Task 1의 `optical_shading_fraction`, `optical_widths`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_transparency.py` 끝에 append:

```python
# ---------------------------------------------------------------------------
# 엔진 배선 (FEM, 20mm 소셀)
# ---------------------------------------------------------------------------
def _build_case(fest, t_f=0.0, t_b=0.0):
    """20mm 소셀 + coarse 메시로 solver/geo/dp 한 세트를 만든다."""
    front = fest.GridDesign(n_fingers=4, n_busbars=2,
                            w_finger=100e-4, w_busbar=200e-4,
                            n_probe_points=10,
                            optical_transparency_f=t_f,
                            optical_transparency_b=t_b)
    geo = fest.CellGeometry(cell_w=2.0, cell_h=2.0, front=front)
    pts, tri = fest.generate_mesh(geo, axis_segments_override=AX)
    isf, isb, isp, ism, isrm, isrp = fest.classify_nodes(pts, geo)
    S = fest.FESTSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)
    return S, geo, fest.DiodeParams()


def _run(fest, t_f=0.0, t_b=0.0):
    """calc_iv + losses를 돌려 (iv, loss) 반환."""
    S, geo, dp = _build_case(fest, t_f, t_b)
    g = geo.front
    _, _, iv = S.calc_iv(g.rho_bulk, g.finger_h, g.w_f, g.rho_contact,
                         g.Rs_sheet, g.shape_cf, dp, mode="tandem", npts=NPTS)
    vb = iv.get("Vmpp_internal", iv["Vmpp"])
    res = iv.get("_mpp_result") or S.solve(
        g.rho_bulk, g.finger_h, g.w_f, g.rho_contact, g.Rs_sheet, vb,
        g.shape_cf, dp, "tandem")
    loss = S.losses(res, g.rho_bulk, g.finger_h, g.w_f, g.rho_contact,
                    g.Rs_sheet, g.shape_cf, dp,
                    Vmpp=iv["Vmpp"], Jmpp=iv["Jmpp"])
    return iv, loss


def test_transparency_zero_bit_identical(fest, monkeypatch):
    """★ T=0 명시 전달 == 미전달. 기존 결과 불변의 실증."""
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    iv_default, loss_default = _run(fest)                 # 파라미터 미전달과 동일 (기본 0)
    iv_zero, loss_zero = _run(fest, t_f=0.0, t_b=0.0)
    for k in ("Jsc", "Voc", "FF", "Eff", "Pmpp"):
        assert iv_zero[k] == iv_default[k], f"{k} 비트동일 실패"
    for k in ("Pe", "Pf_finger", "Pf_busbar", "Pc", "P_shade"):
        assert loss_zero[k] == loss_default[k], f"{k} 비트동일 실패"


def test_transparency_does_not_touch_contact(fest, monkeypatch):
    """★ 이 기능의 정의 — T는 shading에만 작용한다.

    물리 폭이 그대로이므로 접촉 손실(Pc)과 금속 저항 손실(Pf_finger,
    Pf_busbar)은 T와 무관해야 한다. shading만 줄고 효율은 올라야 한다.
    """
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    iv0, l0 = _run(fest, t_f=0.0, t_b=0.0)
    iv1, l1 = _run(fest, t_f=0.4, t_b=0.4)

    assert l1["Pc"] == l0["Pc"], "T가 접촉 손실을 건드렸다 — 물리/광학 분리 실패"
    assert l1["Pf_finger"] == l0["Pf_finger"], "T가 finger 저항을 건드렸다"
    assert l1["Pf_busbar"] == l0["Pf_busbar"], "T가 busbar 저항을 건드렸다"

    assert l1["P_shade"] < l0["P_shade"], "T를 줬는데 shading 손실이 안 줄었다"
    assert iv1["Eff"] > iv0["Eff"], "shading이 줄었는데 효율이 안 올랐다"


def test_rear_transparency_warns(fest, monkeypatch, capsys):
    """rear T는 모델에 반영되지 않는다 — 조용한 no-op으로 두지 않고 경고한다."""
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    front = fest.GridDesign(n_fingers=4, n_busbars=2, n_probe_points=10)
    rear = fest.GridDesign(n_fingers=4, n_busbars=2, n_probe_points=10,
                           optical_transparency_f=0.3)
    geo = fest.CellGeometry(cell_w=2.0, cell_h=2.0, front=front, rear=rear)
    pts, tri = fest.generate_mesh(geo, axis_segments_override=AX)
    isf, isb, isp, ism, isrm, isrp = fest.classify_nodes(pts, geo)
    S = fest.FESTSolver(pts, tri, isf, isb, isp, ism, geo, isrm, isrp)
    g = geo.front
    S._build(g.rho_bulk, g.finger_h, g.w_f, g.rho_contact, g.Rs_sheet,
             g.shape_cf, fest.DiodeParams())
    assert "rear optical transparency" in capsys.readouterr().out
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_transparency.py -v -k "does_not_touch or rear_transparency"`
Expected: `test_transparency_does_not_touch_contact` FAIL (`P_shade`가 안 줄어듦), `test_rear_transparency_warns` FAIL (경고 없음)

- [ ] **Step 3: 최소 구현 작성**

`2L_FEST.py:3978-3979` — `_sh_case` 계산을 광학 폭으로 교체. 기존:

```python
                _sh_case = float(self.geo.shading_fraction(w_f_opt=wf,
                                                           w_b_opt=wb_case))
```
를 다음으로:

```python
                # v28.55: 케이스 shading은 **광학 폭** 기준이다 (Manual §2.7).
                #   _sh_geo는 물리 폭 그대로 두어야 _gen_s의 분모 기준이 유지된다.
                #   T=0이면 두 값이 같아 _gen_s == 1 → 기존 경로와 비트 동일.
                _sh_case = float(self.geo.optical_shading_fraction(wf, wb_case))
```

`2L_FEST.py:6913` — `losses()`의 shading. 기존:

```python
        shade_frac = self.geo.shading_fraction(wf, wb_eff)
```
를 다음으로:

```python
        # v28.55: 광학 폭 기준 — 실제로 잃는 빛이 곧 shading 손실이다.
        shade_frac = self.geo.optical_shading_fraction(wf, wb_eff)
```

`_build` 안, `_sh_geo` 계산 블록 **바로 앞**에 rear 경고를 넣는다:

```python
        # v28.55: rear T는 배선하지 않는다 — shading_fraction()이 전면 기하만
        #   계산하고, 후면 입사광 차폐 자체가 현 모델에 없다. 조용한 no-op으로
        #   두면 v28.54에서 막은 extraction_method와 같은 함정이 되므로 경고한다.
        #   솔버 인스턴스당 1회만 출력한다(_build는 solve마다 호출된다).
        _rear = getattr(self.geo, "rear", None)
        if (_rear is not None and not getattr(self, "_rear_T_warned", False)
                and (getattr(_rear, "optical_transparency_f", 0.0) > 0.0
                     or getattr(_rear, "optical_transparency_b", 0.0) > 0.0)):
            print("  ⚠ rear optical transparency는 현재 모델에 반영되지 않는다 "
                  "(후면 입사광 차폐 미모델링). 값은 무시된다.", flush=True)
            self._rear_T_warned = True
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_transparency.py -v`
Expected: 8 passed

- [ ] **Step 5: 전체 회귀 확인**

Run: `python -m pytest -q -m "not slow"`
Expected: `136 passed, 2 deselected, 6 xfailed` — **기존 128개가 하나도 안 깨져야 한다.**

- [ ] **Step 6: 커밋**

```
feat(transparency): 엔진 배선 + rear 경고 + 비트동일 회귀

_build의 _sh_case와 losses의 shade_frac을 광학 폭으로 바꾸고 _sh_geo는
물리 폭 기준으로 유지한다. T=0에서 _gen_s == 1이 되어 비트 동일이
산술로 성립한다. 접촉/저항 경로는 물리 폭 그대로 무수정.

test_transparency_does_not_touch_contact가 이 기능의 정의를 못박는다 —
T를 바꿔도 Pc/Pf_finger/Pf_busbar는 == 로 불변, P_shade만 감소.

rear T는 배선하지 않되 조용한 no-op으로 두지 않고 경고한다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```
```bash
git add 2L_FEST.py tests/test_transparency.py
git commit -F msg.txt
```

---

### Task 3: 보고 경로 광학화

기계적 변경이다. T=0에서는 전부 동일하므로 회귀 위험이 없다.

**Files:**
- Modify: `2L_FEST.py` 10곳 (아래 표)

**Interfaces:**
- Consumes: Task 1의 `optical_shading_fraction`

- [ ] **Step 1: 호출부 10곳 교체**

`_sh_geo`(3977)는 **건드리지 않는다.** 나머지를 아래 표대로 바꾼다.

| 행 | 기존 | 변경 후 |
|---|---|---|
| 1473 | `self.shading_fraction()` | `self.optical_shading_fraction()` |
| 7534 | `GEO.shading_fraction()` | `GEO.optical_shading_fraction()` |
| 8772 | `GEO.shading_fraction()` | `GEO.optical_shading_fraction()` |
| 9865 | `GEO.shading_fraction()` | `GEO.optical_shading_fraction()` |
| 11176 | `GEO.shading_fraction(w_f_opt=wf_b, w_b_opt=wb_b)` | `GEO.optical_shading_fraction(wf_b, wb_b)` |
| 11177 | `GEO.shading_fraction(w_f_opt=wf_a, w_b_opt=wb_a)` | `GEO.optical_shading_fraction(wf_a, wb_a)` |
| 12122 | `GEO.shading_fraction(w_f_opt=bp[2], w_b_opt=bp[3])` | `GEO.optical_shading_fraction(bp[2], bp[3])` |
| 12123 | `GEO.shading_fraction(w_f_opt=ap[2], w_b_opt=ap[3])` | `GEO.optical_shading_fraction(ap[2], ap[3])` |
| 12127 | `GEO.shading_fraction()` | `GEO.optical_shading_fraction()` |
| 12781, 12788 | `GEO.shading_fraction()` | `GEO.optical_shading_fraction()` |

- [ ] **Step 2: 남은 물리 호출이 `_sh_geo` 하나뿐인지 확인**

Run: `grep -n "\.shading_fraction(" 2L_FEST.py | grep -v "def shading_fraction" | grep -v "optical_shading_fraction"`
Expected: 3977(`_sh_geo`)과 `optical_shading_fraction` 내부 호출(1303 부근) 두 줄만 나온다. 주석 줄(2984)은 무시.

- [ ] **Step 3: 회귀 확인**

Run: `python -m pytest -q -m "not slow"`
Expected: `136 passed, 2 deselected, 6 xfailed` (T=0이므로 값 불변)

- [ ] **Step 4: 커밋**

```
refactor(transparency): 보고 경로 10곳을 광학 shading으로 통일

사용자가 화면과 리포트에서 읽는 "Shading"은 금속이 덮은 면적이 아니라
실제로 잃는 빛이어야 한다. _sh_geo(_gen_s의 분모 기준)만 물리 폭으로
남긴다. T=0에서는 전부 동일해 값 변화 없음.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

---

### Task 4: adapter — grid_params 키, recovery 상호배타, shading 2컬럼

**Files:**
- Modify: `front_electrode/adapter.py` (`_build_geometry` 152-171, `_grid_overrides` 222-224, 물성 블록 253-257 뒤, `results` 323-334)
- Modify: `tests/test_transparency.py` (append)

**Interfaces:**
- Consumes: Task 1의 `GridDesign(optical_transparency_f=, optical_transparency_b=)`
- Produces:
  - `grid_params` 키 `optical_transparency_finger`, `optical_transparency_busbar`
  - `results["shading_physical"]`, `results["shading_optical"]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_transparency.py` 끝에 append:

```python
# ---------------------------------------------------------------------------
# adapter 경로
# ---------------------------------------------------------------------------
from front_electrode import (  # noqa: E402
    SCENARIO_MEASURED,
    evaluate_existing_simulation,
)


def _grid(**over):
    g = dict(cell_w_mm=20.0, cell_h_mm=20.0, finger_spacing_mm=1.8,
             w_finger_um=50.0, n_busbars=2, w_busbar_mm=0.2,
             n_probe_points=10)
    g.update(over)
    return g


def test_adapter_transparency_zero_bit_identical(fest, monkeypatch):
    """T=0 키를 넘긴 것과 안 넘긴 것이 비트 동일."""
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    kw = dict(scenario=SCENARIO_MEASURED, busbar_recovery_factor=0.0,
              mode="tandem", npts=NPTS, axis_segments_override=AX)
    base = evaluate_existing_simulation(fest, _grid(), **kw)
    zero = evaluate_existing_simulation(
        fest, _grid(optical_transparency_finger=0.0,
                    optical_transparency_busbar=0.0), **kw)
    for k in ("Jsc", "Voc", "FF", "Eff", "Pmpp", "Pc", "Pf_finger"):
        assert zero["engine_raw"][k] == base["engine_raw"][k], f"{k} 비트동일 실패"


def test_shading_columns_physical_and_optical(fest, monkeypatch):
    """T=0이면 두 컬럼이 같고, T>0이면 optical < physical."""
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    kw = dict(scenario=SCENARIO_MEASURED, busbar_recovery_factor=0.0,
              mode="tandem", npts=NPTS, axis_segments_override=AX)
    zero = evaluate_existing_simulation(fest, _grid(), **kw)["results"]
    assert zero["shading_physical"] == zero["shading_optical"]

    tr = evaluate_existing_simulation(
        fest, _grid(optical_transparency_finger=0.4,
                    optical_transparency_busbar=0.4), **kw)["results"]
    assert tr["shading_optical"] < tr["shading_physical"]
    # 물리 shading은 T와 무관하다 (금속이 덮은 면적은 그대로)
    assert tr["shading_physical"] == pytest.approx(zero["shading_physical"])


def test_transparency_conflicts_with_recovery(fest):
    """같은 물리를 두 번 계산하는 조합은 막는다. 메시지에 해결책 양쪽이 있어야 한다."""
    with pytest.raises(ValueError) as ei:
        evaluate_existing_simulation(
            fest, _grid(optical_transparency_busbar=0.3),
            scenario=SCENARIO_MEASURED, busbar_recovery_factor=0.25,
            mode="tandem", npts=NPTS, axis_segments_override=AX)
    msg = str(ei.value)
    assert "optical_transparency_busbar=0" in msg
    assert "busbar_recovery_factor=0" in msg


def test_finger_transparency_does_not_conflict(fest, monkeypatch):
    """finger에는 recovery 모델이 없으므로 충돌하지 않는다."""
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    out = evaluate_existing_simulation(
        fest, _grid(optical_transparency_finger=0.3),
        scenario=SCENARIO_MEASURED, busbar_recovery_factor=0.25,
        mode="tandem", npts=NPTS, axis_segments_override=AX)
    assert out["results"]["shading_optical"] < out["results"]["shading_physical"]
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_transparency.py -v -k "adapter or shading_columns or conflicts or finger_transparency"`
Expected: `KeyError: 'shading_physical'` 및 `DID NOT RAISE ValueError`

- [ ] **Step 3: 최소 구현 작성**

`front_electrode/adapter.py` — `_build_geometry`의 두 `GridDesign(...)` 호출(152-171)에 각각 인자 2개를 추가한다. 먼저 함수 앞부분 `n_probe = int(...)` 아래에 읽기를 넣는다:

```python
    t_f = float(gp.get("optical_transparency_finger", 0.0) or 0.0)
    t_b = float(gp.get("optical_transparency_busbar", 0.0) or 0.0)
```
그리고 두 `GridDesign(...)` 호출 각각의 `edge_gap=edge_margin_cm, busbar_length_frac=bb_frac,` 다음 줄에:

```python
            optical_transparency_f=t_f, optical_transparency_b=t_b,
```

`_grid_overrides`(222-224)의 키 튜플에 두 항목을 추가:

```python
    _grid_overrides = {k: grid_params[k] for k in
                       ("edge_margin_mm", "rho_bulk_uohm_cm", "rho_contact_mohm_cm2",
                        "optical_transparency_finger", "optical_transparency_busbar")
                       if grid_params.get(k) is not None}
```

`geo = _build_geometry(fest, grid_params)` **바로 앞**에 상호배타 검사를 넣는다:

```python
    # busbar recovery factor와 optical transparency는 같은 물리(busbar 반사광
    # 회수)를 서로 다른 계층에서 모델링한다 — 둘 다 켜면 이중계산이다.
    # recovery는 사후 line-item이라 FEM에 피드백되지 않고, T는 엔진 입력이라
    # 발전량에 실제로 들어간다. 조용히 둘 다 적용되는 것이 최악이므로 막는다.
    _t_b_in = float(grid_params.get("optical_transparency_busbar", 0.0) or 0.0)
    if float(busbar_recovery_factor) > 0.0 and _t_b_in > 0.0:
        raise ValueError(
            f"busbar_recovery_factor(={busbar_recovery_factor})와 "
            f"optical_transparency_busbar(={_t_b_in})를 동시에 쓸 수 없다 — "
            "같은 물리(busbar 반사광 회수)를 두 번 계산한다.\n"
            "  · 기존 방식 유지: optical_transparency_busbar=0 으로 둘 것 "
            "(권장 — 현재 기본)\n"
            "  · 광학 폭으로 전환: busbar_recovery_factor=0 으로 둘 것 "
            "(T 값의 문헌/측정 근거가 있을 때만)")
```

`return` dict의 `"results"` 블록에 두 키를 추가한다 (`"efficiency": efficiency,` 다음 줄):

```python
            # 금속이 덮은 면적(물리) vs 빛을 잃은 면적(광학). T=0이면 같은 값이다.
            # 논문에서 두 값을 구분해 설명해야 하므로 항상 둘 다 남긴다.
            "shading_physical": geo.shading_fraction(wf, geo.w_b),
            "shading_optical": geo.optical_shading_fraction(wf, geo.w_b),
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_transparency.py -v`
Expected: 12 passed

- [ ] **Step 5: 커밋**

```
feat(transparency): adapter 배선 + recovery 상호배타 + shading 2컬럼

grid_params에 optical_transparency_finger/_busbar를 받고 GridDesign으로
넘긴다. busbar recovery factor와 동시 지정은 ValueError — 같은 물리를
두 번 계산하기 때문이며, 메시지에 어느 쪽을 0으로 둘지 양쪽 안내를 넣었다.
finger는 recovery 모델이 없어 충돌하지 않는다.

results에 shading_physical / shading_optical을 함께 남긴다. T=0이면 동일.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

---

### Task 5: optimize_grid 스윕 축 + 조합 수 확인

**Files:**
- Modify: `front_electrode/optimizer.py:124-180` (`optimize_grid`)
- Modify: `scripts/optimize_m10.py` (CLI 확인 함수, `--yes`)
- Modify: `tests/test_transparency.py` (append)

**Interfaces:**
- Consumes: Task 4의 `grid_params` 키
- Produces:
  - `optimizer.COMBO_CONFIRM_THRESHOLD = 50`
  - `optimize_grid(..., transparency_finger_list=(0.0,), transparency_busbar_list=(0.0,), confirm=None)` — `confirm: (n_combos: int) -> bool`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_transparency.py` 끝에 append:

```python
# ---------------------------------------------------------------------------
# 스윕 축
# ---------------------------------------------------------------------------
from front_electrode import (  # noqa: E402
    COMBO_CONFIRM_THRESHOLD,
    optimize_grid,
)


def test_transparency_sweep_axis(fest, monkeypatch):
    """T가 축이 되면 조합 수가 늘고 각 조합에 값이 실린다."""
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    opt = optimize_grid(
        fest, cell_mm=20.0, finger_widths_um=[50.0], finger_pitches_mm=[1.8],
        n_busbars_list=[2], busbar_widths_mm=[0.2],
        transparency_finger_list=[0.0, 0.4],
        scenario=SCENARIO_MEASURED, axis_segments_override=AX, npts=NPTS)
    assert opt["n_combos"] == 2
    effs = [r["results"]["efficiency"] for r in opt["results"]]
    assert max(effs) > min(effs), "T를 바꿨는데 효율이 그대로다"


def test_combo_confirm_not_called_by_default():
    """confirm=None이면 프롬프트 경로에 들어가지 않는다.

    optimize_grid는 pytest와 백그라운드 드라이버에서도 호출된다. 라이브러리
    안에서 input()을 부르면 테스트가 멈추고 비대화형 실행은 EOF로 죽는다.
    """
    assert COMBO_CONFIRM_THRESHOLD == 50


def test_combo_confirm_can_cancel(fest, monkeypatch):
    """임계를 넘고 confirm이 False를 주면 실행 전에 취소된다."""
    monkeypatch.delenv("FEST_LEGACY_LOCAL_MATCH", raising=False)
    monkeypatch.setattr("front_electrode.optimizer.COMBO_CONFIRM_THRESHOLD", 1)
    calls = []
    with pytest.raises(RuntimeError, match="취소"):
        optimize_grid(
            fest, cell_mm=20.0, finger_widths_um=[50.0, 60.0],
            finger_pitches_mm=[1.8], n_busbars_list=[2], busbar_widths_mm=[0.2],
            scenario=SCENARIO_MEASURED, axis_segments_override=AX, npts=NPTS,
            confirm=lambda n: (calls.append(n), False)[1])
    assert calls == [2], "confirm이 조합 수와 함께 정확히 한 번 불려야 한다"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_transparency.py -v -k "sweep_axis or combo_confirm"`
Expected: `ImportError: cannot import name 'COMBO_CONFIRM_THRESHOLD' from 'front_electrode'`

- [ ] **Step 3: 최소 구현 작성**

`front_electrode/optimizer.py` — 모듈 상단(`import` 블록 다음)에 상수를 추가:

```python
# 조합 수가 이 값을 넘으면 호출자에게 확인을 요청한다. M10 1조합 ≈17분이므로
# 50조합 ≈14시간이다. 프롬프트 자체는 CLI가 담당한다 — 라이브러리에서
# input()을 부르면 pytest와 백그라운드 실행이 멈춘다.
COMBO_CONFIRM_THRESHOLD = 50
```

`optimize_grid` 시그니처에 인자 3개를 추가한다. `edge_margins_mm=None, n_probe_points=0,` 다음에:

```python
                  transparency_finger_list=(0.0,), transparency_busbar_list=(0.0,),
                  confirm=None,
```

축 전개 루프(151-162)를 교체한다:

```python
    edges = list(edge_margins_mm) if edge_margins_mm else [edge_margin_mm]
    grid_list = []
    for wf, pitch, nbb, wbb, rho_l, rho_c, edge, t_f, t_b in itertools.product(
            finger_widths_um, finger_pitches_mm, n_busbars_list,
            busbar_widths_mm, rho_bulk_list, rho_contact_list, edges,
            transparency_finger_list, transparency_busbar_list):
        d = dict(cell_w_mm=cell_mm, cell_h_mm=cell_mm,
                 finger_spacing_mm=pitch, w_finger_um=wf,
                 n_busbars=nbb, w_busbar_mm=wbb,
                 n_probe_points=n_probe_points, edge_margin_mm=edge)
        if rho_l is not None:
            d["rho_bulk_uohm_cm"] = rho_l
        if rho_c is not None:
            d["rho_contact_mohm_cm2"] = rho_c
        # 0.0이면 키를 넣지 않는다 — 기본 실행의 grid dict를 기존과 동일하게 유지.
        if t_f:
            d["optical_transparency_finger"] = t_f
        if t_b:
            d["optical_transparency_busbar"] = t_b
        grid_list.append(d)

    if len(grid_list) > COMBO_CONFIRM_THRESHOLD and confirm is not None:
        if not confirm(len(grid_list)):
            raise RuntimeError(
                f"{len(grid_list)}개 조합 실행이 사용자에 의해 취소되었다")
```

`front_electrode/__init__.py`의 optimizer import 블록과 `__all__`에 `COMBO_CONFIRM_THRESHOLD`를 추가한다.

`scripts/optimize_m10.py` — `main()` 위에 확인 함수를 추가:

```python
_MIN_PER_COMBO_M10 = 17.0   # 실측 기준 (풀 M10 1조합)


def _confirm_combos(n):
    """대화형 확인. 비대화형(EOF)이면 취소로 간주한다."""
    hours = n * _MIN_PER_COMBO_M10 / 60.0
    print(f"\n⚠ {n}개 조합 — 풀 M10 1조합 ≈{_MIN_PER_COMBO_M10:.0f}분 기준 "
          f"예상 {hours:.1f}시간", flush=True)
    try:
        return input("  진행할까요? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        print("  (비대화형 입력 — 취소한다. --yes 로 건너뛸 수 있다.)", flush=True)
        return False
```
`argparse`에 플래그를 추가:
```python
    ap.add_argument("--yes", action="store_true",
                    help="조합 수 확인 프롬프트를 건너뛴다(장시간 실행 자동화용)")
```
`optimize_grid`를 호출하는 지점에 `confirm=(None if args.yes else _confirm_combos)`를 넘긴다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_transparency.py -v`
Expected: 15 passed

- [ ] **Step 5: 커밋**

```
feat(transparency): optimize_grid 스윕 축 + 조합 수 확인 콜백

축이 7개에서 9개가 된다. 기본값이 단일원소라 축을 주지 않으면 조합 수와
grid dict가 기존과 동일하다(0.0이면 키를 넣지 않는다).

조합 수가 COMBO_CONFIRM_THRESHOLD(=50, M10 기준 약 14시간)를 넘으면
호출자에게 확인을 요청한다. 프롬프트는 CLI에 두고 라이브러리는 confirm
콜백만 받는다 — 라이브러리에서 input()을 부르면 pytest와 백그라운드
실행이 멈추기 때문이다. confirm=None(기본)이면 기존과 동일하게 동작한다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

---

### Task 6: roadmap CSV에 shading 2컬럼

roadmap CSV가 논문 figure의 데이터 원장이므로 여기에 없으면 §6의 목적을 달성하지 못한다.

**Files:**
- Modify: `front_electrode/roadmap.py` (`build_row`)
- Modify: `tests/test_roadmap.py` (`_fake_out`)

**Interfaces:**
- Consumes: Task 4의 `results["shading_physical"]`, `results["shading_optical"]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_roadmap.py`의 `_fake_out()` 안 `"results"` dict에 두 키를 추가한다:

```python
        "results": {"total_loss": 1.07, "efficiency": eff,
                    "shading_physical": 0.0173, "shading_optical": 0.0173},
```
그리고 파일 끝에 append:

```python
def test_build_row_carries_shading_columns():
    """논문 figure 원장이므로 물리/광학 shading을 둘 다 싣는다."""
    sc = _min_scenario()
    sc["_meta"] = {"file": "s.json", "sha256": "0123456789ab"}
    out = _fake_out()
    out["results"]["shading_optical"] = 0.0121      # T>0 상황
    row = build_row(expand_cases(sc)[0], out, sc,
                    provenance_env(_FakeFest, sc), 1.0)
    assert row["shading_physical"] == 0.0173
    assert row["shading_optical"] == 0.0121
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `python -m pytest tests/test_roadmap.py::test_build_row_carries_shading_columns -v`
Expected: `KeyError: 'shading_physical'`

- [ ] **Step 3: 최소 구현 작성**

`front_electrode/roadmap.py`의 `build_row`에서 `row["total_loss"] = out["results"]["total_loss"]` 다음 줄에:

```python
    # 금속이 덮은 면적 vs 빛을 잃은 면적. T=0이면 같은 값이지만 항상 둘 다 남긴다
    # — 논문에서 이 둘을 구분해 설명해야 한다.
    row["shading_physical"] = out["results"]["shading_physical"]
    row["shading_optical"] = out["results"]["shading_optical"]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_roadmap.py -v`
Expected: 27 passed

- [ ] **Step 5: 커밋**

```
feat(transparency): roadmap CSV에 shading_physical / shading_optical

roadmap CSV가 논문 figure의 데이터 원장이므로 금속이 덮은 면적과 빛을
잃은 면적을 둘 다 남긴다. T=0이면 같은 값이다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

---

### Task 7: GUI 입력란 + 광학 폭 프리뷰 + 버전

**Files:**
- Modify: `2L_FEST.py:8368-8374` (`tb_hpat` 카드), `8907` 부근 (`_apply_grid_design` 파싱), `8945-8955` (`GridDesign(...)` 호출), `11991-12003` (DESIGN 탭 프리뷰), `276-280` (`__build__`), docstring changelog

**Interfaces:**
- Consumes: Task 1의 `GridDesign(optical_transparency_f=, optical_transparency_b=)`

- [ ] **Step 1: 입력란 2개 추가**

`2L_FEST.py:8373` 다음에 두 줄을 추가하고 `tb_hpat` 리스트를 확장한다:

```python
        e7 = _make_entry_row2(grid_card, "Finger optical T", "0.0",  "0~1", 6)
        e8 = _make_entry_row2(grid_card, "Busbar optical T", "0.0",  "0~1", 7)
        self.tb_hpat = [e1, e2, e3, e4, e5, e6, e7, e8]
```
8366-8367의 주석도 함께 갱신한다:
```python
        # tb_hpat keeps original layout: [0]=N Fingers, [1]=Spacing, [2]=N Busbars,
        # [3]=Finger Length, [4]=Busbar Length, [5]=Edge Gap,
        # [6]=Finger optical T, [7]=Busbar optical T   (v28.55)
```

- [ ] **Step 2: 파싱과 검증 추가**

`2L_FEST.py:8907`의 `edge_gap = _parse_gui_float(...)` 다음에:

```python
            t_finger = _parse_gui_float(self.tb_hpat[6].get(), "Finger optical T")
            t_busbar = _parse_gui_float(self.tb_hpat[7].get(), "Busbar optical T")
            _require_range("Finger optical T", t_finger, min_value=0.0,
                           max_value=1.0, max_inclusive=False)
            _require_range("Busbar optical T", t_busbar, min_value=0.0,
                           max_value=1.0, max_inclusive=False)
```

- [ ] **Step 3: GridDesign에 전달**

`2L_FEST.py:8955`의 `pattern_style=pattern_style)` 를 다음으로 교체:

```python
                               pattern_style=pattern_style,
                               optical_transparency_f=t_finger,
                               optical_transparency_b=t_busbar)
```

- [ ] **Step 4: DESIGN 탭에 광학 폭 오버레이**

`2L_FEST.py:12003`의 pads 루프 다음에 추가:

```python
        # v28.55: 광학 폭 오버레이. 물리 폭 사각형 위에 광학 폭을 점선으로 겹쳐
        #   그려 T가 실제로 반영되고 있음을 눈으로 확인시킨다. T=0이면 안 그린다.
        _t_f = GEO.front.optical_transparency_f
        _t_b = GEO.front.optical_transparency_b
        if _t_f > 0:
            for rx, ry, rw, rh in fingers:
                h = rh * (1.0 - _t_f)
                ax1.add_patch(Rectangle((rx * 10, (ry + (rh - h) / 2) * 10),
                                         rw * 10, h * 10,
                                         fc='none', ec='#FFEB3B', lw=0.8,
                                         ls='--', zorder=6))
        if _t_b > 0:
            for rx, ry, rw, rh in busbars:
                w = rw * (1.0 - _t_b)
                ax1.add_patch(Rectangle(((rx + (rw - w) / 2) * 10, ry * 10),
                                         w * 10, rh * 10,
                                         fc='none', ec='#FFEB3B', lw=1.2,
                                         ls='--', zorder=6))
```

- [ ] **Step 5: 위젯 인자와 엔진 로드 확인**

Run:
```bash
python -c "import sys; sys.path.insert(0,'tests'); sys.path.insert(0,'.'); import conftest; f=conftest._load_fest(); print(f.__build__); g=f.GridDesign(optical_transparency_f=0.3); print(g.optical_widths(100e-4, 200e-4))"
```
Expected: build dict이 출력되고 `(0.007, 0.02)`가 나온다.

- [ ] **Step 6: 버전과 changelog**

`__build__`(276-280)을 `"version": "v28.55"`, `"date": "2026-08-14"`로 바꾸고, docstring changelog 끝(`Author:` 줄 앞)에 항목을 추가한다:

```
v28.55: [feat] Metal Optical Transparency — 금속의 물리 폭과 광학 폭 분리.
         T = 1 − optical/physical (Manual v7.0 §2.7), finger·busbar 각각 지정.
         physical width는 contact area와 금속 저항에, optical width는 shading에
         쓴다. 배선은 _build의 _sh_case와 losses의 shade_frac 두 곳뿐이며
         _sh_geo는 물리 폭 기준으로 남겨 _gen_s = (1−sh_case)/(1−sh_geo)가
         T=0에서 정확히 1이 되게 했다 → **기존 결과 비트 동일**.
         보고 경로 10곳은 optical_shading_fraction()으로 통일(화면의 "Shading"은
         실제로 잃는 빛이어야 한다). rear T는 배선하지 않고 경고만 낸다 —
         후면 입사광 차폐 자체가 모델에 없어서이며, v28.54에서 막은
         extraction_method 같은 조용한 no-op을 새로 만들지 않기 위해서다.
         busbar recovery factor와는 상호 배타(ValueError) — 같은 물리를 두 번
         계산한다. recovery가 기본이고 T는 opt-in이다(T 값의 근거 미확보).
         CSV에 shading_physical / shading_optical 병기. optimize_grid에 축 2개
         추가(7→9축)와 조합 수 확인 콜백(임계 50).
```

- [ ] **Step 7: 전체 회귀 확인**

Run: `python -m pytest -q -m "not slow"`
Expected: `139 passed, 2 deselected, 6 xfailed`

- [ ] **Step 8: 커밋**

```
feat(transparency): GUI 입력란 + 광학 폭 프리뷰 (v28.55)

FRONT GRID DESIGN 카드에 Finger/Busbar optical T 입력란을 추가하고
0 <= T < 1 범위를 검증한다. DESIGN 탭 프리뷰에 광학 폭을 노란 점선으로
겹쳐 그려 T가 실제로 먹고 있음을 눈으로 확인시킨다 — v28.54에서 막은
extraction_method처럼 "GUI에 있는데 아무 일도 안 하는" 상태를 만들지
않기 위해서다.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
```

---

## Self-Review

**1. 스펙 커버리지**

| 스펙 절 | 구현 태스크 |
|---|---|
| §1 정의 | Task 1 (검증·헬퍼), Task 7 (changelog) |
| §2 배선 2지점 + `_sh_geo` 유지 | Task 2 |
| §3 API | Task 1 |
| §4 recovery 상호배타 + 메시지 규약 | Task 4 |
| §5 보고 경로 광학화 | Task 3 |
| §6 CSV 2컬럼 (adapter + roadmap) | Task 4, Task 6 |
| §7 rear 경고 | Task 2 |
| §8 GUI + 프리뷰 | Task 7 |
| §9 스윕 축 + confirm 콜백 + CLI | Task 5 |
| §10 테스트 9종 | Task 1(4) · 2(3) · 4(4) · 5(3) · 6(1) — 총 15개 |
| §11 비범위 | 구현 안 함 — 의도적 |

**2. 플레이스홀더 스캔** — 모든 코드 스텝에 실제 코드가 있다. "적절히 처리"류 없음.

**3. 타입 일관성**
- `optical_widths(w_f, w_b) -> (float, float)` — Task 1 정의, Task 2·3의 `optical_shading_fraction` 내부에서 사용
- `optical_shading_fraction(w_f=None, w_b=None) -> float` — Task 1 정의, Task 2(엔진)·3(보고)·4(adapter)에서 동일 시그니처로 호출
- `confirm: (int) -> bool` — Task 5 정의, CLI `_confirm_combos(n)`가 같은 형태
- `results` 키 `shading_physical`/`shading_optical` — Task 4 생성, Task 6 소비. 이름 일치
- grid_params 키 `optical_transparency_finger`/`_busbar` (사용자 단위, adapter 경계) vs GridDesign 인자 `optical_transparency_f`/`_b` (엔진 내부) — **의도적으로 다른 이름**이며 Task 4가 변환한다. 기존 `w_finger_um` → `w_finger` 규약과 같은 패턴

**4. 알려진 위험**
- Task 2 `test_transparency_does_not_touch_contact`의 `l1["Pc"] == l0["Pc"]`는 `==` 비교다. `_Gc`는 물리 폭만 쓰므로 성립해야 하지만, 만약 깨지면 **테스트를 완화하지 말고 배선이 새는 지점을 찾을 것.** 이 등식이 곧 기능의 정의다.
- Task 5에서 `itertools.product`의 언패킹이 7개에서 9개로 늘어난다. 순서를 틀리면 조용히 잘못된 조합이 만들어지므로, 축 순서와 변수 순서를 반드시 대조할 것.
- Task 7의 `tb_hpat` 인덱스는 기존 코드 여러 곳에서 참조된다(8812, 8826, 8831-8832). **append만 하므로 기존 인덱스 0-5는 그대로다.**
