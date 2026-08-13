# Roadmap 러너 설계 — Griddler PRO §5.1 Efficiency Improvement Diagram 상당

> **작성**: 2026-08-13
> **대상 빌드**: `2L_FEST.py` v28.53, `main` = `1b91d8a`
> **근거**: `docs/audit_2026-08-13.md` §6 권고 5
> **상태**: 설계 승인됨 (2026-08-13)

---

## 1. 목적과 범위

baseline 설계에서 파라미터를 순차 누적 변경하며 각 케이스의 I-V를 재실행하고, 결과를 CSV에 누적한 뒤 Jsc / Voc / FF / Efficiency 4-panel로 출력한다. Griddler PRO §5.1의 동작 흐름을 GUI 세션 상태에 묶이지 않는 파일 기반으로 재현한다.

### 이 도구가 하는 일

**고정 설계에서 파라미터를 바꾼다.** 시나리오 파일에 적힌 값을 그대로 엔진에 넣고 돌린다. 그 이상도 이하도 아니다.

### 이 도구가 하지 않는 일

**설계 최적화를 하지 않는다.** roadmap 러너는 탐색하지 않는다. `optimize_grid`가 이미 그 역할을 하고 있으며, 두 기능을 한 도구에 합치면 "이 막대가 파라미터 변경의 효과인가, 재최적화의 효과인가"를 구분할 수 없게 된다. 이 경계는 설계 원칙이지 구현 편의가 아니다.

따라서 최적 설계가 필요한 분석은 반드시 §2의 2단계 워크플로우를 따른다.

---

## 2. 2단계 워크플로우 — 최적화와 roadmap의 분업

UNIST 논문의 "TCO modification 전 → 후" figure가 첫 사용처이며, 이 절차를 표준으로 삼는다.

### 왜 2단계인가

ρ_c를 낮추면 **최적 설계 자체가 이동한다.** 접촉 저항이 줄면 finger를 더 성기게 깔아도 되므로 최적 pitch가 커지고 최적 BB 개수가 달라진다. 그러므로 "ρ_c만 바꾼 결과"와 "ρ_c를 바꾸고 재최적화한 결과"는 다른 수치이며, 논문 figure는 둘 중 무엇을 주장하는지 명확해야 한다.

roadmap 러너는 탐색을 하지 않으므로, 최적 설계는 **미리 구해서 시나리오 파일에 옮겨 적어야** 한다.

### 절차

**Stage A — ρ_c별 최적 설계 확보 (`optimize_grid`)**

ρ_c 값마다 독립적으로 Cartesian 스윕을 돌려 최적 조합을 얻는다.

```
optimize_grid(..., rho_contact_list=[10.0], ...)  →  최적 설계 D₁ (as-is)
optimize_grid(..., rho_contact_list=[2.0],  ...)  →  최적 설계 D₂ (modified)
```

`rho_contact_list`에 두 값을 한 번에 넣어도 되지만, 그 경우 전역 `best`는 항상 ρ_c가 낮은 쪽에서 나오므로 **ρ_c별 최적을 따로 뽑아야 한다** — `edge_margin`에 대해 `best_by_edge`가 존재하는 것과 같은 이유다 (`optimizer.py:143-147`).

산출된 D₁ / D₂의 파라미터를 시나리오 파일에 손으로 옮긴다. **이 이관이 수작업이므로 §5의 provenance 필드가 필수다** — 어떤 값이 어느 스윕에서 왔는지 CSV에 남지 않으면 figure의 근거를 추적할 수 없다.

**Stage B — roadmap 실행**

권장 형태는 3행이다. 두 효과를 분리하기 위해서다.

| case_index | 상태 | 이 막대가 말하는 것 |
|---|---|---|
| 0 | D₁ @ ρ_c = 10 | baseline |
| 1 | D₁ @ ρ_c = 2 | **TCO 개선 단독 효과** (설계 고정) |
| 2 | D₂ @ ρ_c = 2 | **재최적화가 추가로 얻는 몫** |

케이스 1은 `set`에 `rho_contact_mohm_cm2`만, 케이스 2는 설계 파라미터(`finger_spacing_mm`, `n_busbars` 등)만 담는다. 누적 방식이므로 케이스 2에서 ρ_c는 자동으로 2를 유지한다.

D₁ = D₂이면(= ρ_c 변화가 최적해를 옮기지 않으면) 케이스 2의 막대가 0이 되며, 그 자체가 유의미한 결과다.

**최소 동작 예시**는 케이스 1만 있는 2행 형태이며, `scripts/scenarios/unist_tco.json`으로 동봉한다.

---

## 3. 파일 구조

```
front_electrode/roadmap.py        신규 — 로드·검증·누적전개·실행·CSV 누적
front_electrode/roadmap_plot.py   신규 — 4-panel matplotlib
scripts/run_roadmap.py            신규 — argparse CLI
scripts/scenarios/unist_tco.json  신규 — 최소 동작 예시 시나리오
tests/test_roadmap.py             신규 — 단위·회귀 테스트
front_electrode/__init__.py       ★ 유일한 기존 파일 수정 (export 추가, 가산적)
```

엔진(`2L_FEST.py`)과 `adapter.py`는 **한 줄도 수정하지 않는다.** 요구사항 "기존 결과 비트 불변"이 구조적으로 성립한다 — 기존 스윕/최적화 경로가 새 코드에 물리적으로 도달할 수 없다.

계산(`roadmap.py`)과 그림(`roadmap_plot.py`)을 분리하는 이유는 CSV만 있으면 FEM 재실행 없이 그림을 다시 그릴 수 있어야 하기 때문이다. 논문 figure는 스타일을 여러 번 고친다.

---

## 4. 시나리오 스키마 (JSON)

**JSON을 쓴다.** PyYAML은 `requirements.txt`에 없고 설치되어 있지도 않다. 이 저장소는 PyInstaller로 데스크톱 앱을 번들하므로 런타임 의존성 추가에는 비용이 따른다. `json`은 표준 라이브러리다.

`scripts/scenarios/unist_tco.json`:

```json
{
  "schema": "2lfest.roadmap/1",
  "name": "UNIST TCO modification",

  "engine": {
    "mode": "tandem",
    "npts": 14,
    "target_nodes": 82000,
    "scenario": "measured"
  },

  "baseline": {
    "label": "as-is (baseline)",
    "cell_w_mm": 182.0,
    "cell_h_mm": 182.0,
    "finger_spacing_mm": 2.193,
    "w_finger_um": 20.0,
    "n_busbars": 8,
    "w_busbar_mm": 0.20,
    "n_probe_points": 10,
    "edge_margin_mm": 0.0,
    "rho_bulk_uohm_cm": 4.22,
    "rho_contact_mohm_cm2": 10.0
  },

  "cases": [
    {
      "label": "TCO modified",
      "note": "rho_c 10 -> 2 mOhm.cm2 (placeholder — 실측값 미확보)",
      "set": { "rho_contact_mohm_cm2": 2.0 }
    }
  ],

  "provenance": {
    "finger_spacing_mm":    { "tag": "derived",  "note": "optimize_grid edge0 최적 (opt_grid_m10_measured.csv, 31.330%)" },
    "n_busbars":            { "tag": "derived",  "note": "동일 스윕 최적 (8BB)" },
    "w_finger_um":          { "tag": "derived",  "note": "동일 스윕 고정축 20um (ITRPV 인쇄 현실성)" },
    "w_busbar_mm":          { "tag": "derived",  "note": "동일 스윕의 고정축 0.20mm — pitch/BB 최적해와 같은 근거" },
    "rho_bulk_uohm_cm":     { "tag": "measured", "note": "KIST low-T sinter 90C/30min/5MPa" },
    "rho_contact_mohm_cm2": { "tag": "assumed",  "note": "placeholder — 실측값 미확보" },
    "edge_margin_mm":       { "tag": "assumed",  "note": "공정 제약 미확정 (0 = 마진 없음 가정)" }
  }
}
```

### 설계 결정

**`baseline` 키는 `evaluate_existing_simulation`의 `grid_params`와 1:1로 동일하다.** 중간 매핑 레이어를 두지 않는다. 매핑이 있으면 오역이 조용히 들어온다.

**`set`의 키는 `baseline` 키의 부분집합만 허용한다.** 모르는 키는 즉시 `ValueError`다. 이 저장소가 반복해서 겪은 사고(v28.43 `n_probe_points=0`, `extraction_method` 죽은 파라미터)는 전부 "조용히 무시되고 그럴듯한 틀린 값"이었다. 오타난 키를 통과시키면 같은 계열의 버그를 새로 만드는 셈이다.

**`schema` 버전 필드**를 둔다. 나중에 다이오드 파라미터 축을 열 때 `2lfest.roadmap/2`로 구분한다.

**`engine.scenario`는 문자열 → 상수 매핑이다.** `"measured"` → `SCENARIO_MEASURED`, `"default"` → `SCENARIO_ENGINE_DEFAULT` (둘 다 `front_electrode`가 이미 export한다). 그 외 문자열은 `ValueError`.

**`label`은 시나리오 내에서 유일해야 한다** (baseline 포함). `--resume`이 label을 키로 완료 케이스를 skip하므로, 중복 label은 조용한 오작동을 만든다. 로드 시 검증한다.

### 예시 시나리오 값의 근거 — `w_busbar_mm = 0.20`인 이유

예시의 설계 파라미터는 **전부 같은 스윕 한 번에서 나온 값이다**: `scripts/opt_grid_m10_measured.csv`의 최적행 (pitch 2.1928 mm / 82 fingers / **8BB** / **wbb 0.20 mm** / wf 20 µm, Eff 31.330 %). `w_busbar_mm`을 0.20으로 두어야 pitch·BB 최적해와 근거가 일관된다. 그래서 provenance 태그도 `derived`다.

**0.25 mm는 여기에 넣지 않는다.** 0.25는 ITRPV 기반 **16BB** 논문 계산에서 쓸 값이며, 그 계산에서는 busbar 개수도 8 → 16으로 함께 바뀐다. 즉 설계점이 통째로 이동하므로 **Stage A를 처음부터 다시 돌려 16BB·0.25 mm 조건의 최적해를 새로 구해야 한다.** 그 결과가 나오기 전에 0.25를 이 시나리오에 끼워 넣으면, 8BB 최적화에서 나온 pitch와 16BB용 busbar 폭이 한 행에 섞인 — 어느 스윕에도 대응하지 않는 — 조합이 된다.

두 조건은 별개의 시나리오 파일로 관리한다.

---

## 5. Provenance — 데이터 출처를 소프트웨어가 강제한다

기능 명세 §3.2가 제안한 "`measured` / `assumed` / `derived` 태그를 필수 필드로 두면 data provenance 원칙이 소프트웨어 레벨에서 강제된다"를 이 범위에서 실현한다.

### 태그 정의

| 태그 | 의미 |
|---|---|
| `measured` | 랩 또는 협력기관 실측값 |
| `derived` | 다른 계산의 산출물 (`optimize_grid` 최적해 등) |
| `assumed` | 가정값 — 문헌, 관행, 또는 미확보 |

### 강제 규칙 (2단계)

1. **어떤 케이스가 `set`하는 키는 provenance 항목이 필수다.** 없으면 `ValueError`. figure의 주장이 걸린 값이기 때문이다.
2. baseline의 나머지 키는 없으면 CSV에 `unspecified`로 기록하고 **실행 시 경고를 출력한다.**

### 실행 환경 provenance

시나리오 파일이 같아도 엔진이 다르면 결과가 다르다. 세 가지를 함께 기록한다.

| 필드 | 취득 | 잡아내는 것 |
|---|---|---|
| `git_commit` | `git rev-parse --short HEAD` (+ dirty 표시) | 저장소 상태 |
| `engine_version` | `fest.__build__["version"]` | 엔진 버전 라벨 |
| `engine_sha` | `fest._build_sha()` — 엔진 파일 sha256 앞 12자 | **커밋되지 않은 엔진 수정** |
| `scenario_file` | 파일 basename | 어떤 시나리오인지 |
| `scenario_sha256` | 파일 바이트 sha256 앞 12자 | 시나리오 파일의 조용한 수정 |

`engine_sha`가 `git_commit`보다 강한 앵커다. 커밋하지 않고 엔진을 고친 채 돌린 결과를 구분해 낸다.

git 명령 실패는 치명적이지 않다 — `"unknown"`으로 기록하고 계속한다.

---

## 6. 실행 흐름

```
load_scenario(path)                   → Scenario      (스키마·provenance 검증)
expand_cases(scenario)                → [(idx, label, note, grid_params), ...]
                                        ★ 순수 함수 — 누적 전개, FEM 불필요
run_roadmap(fest, sc, csv_path, resume=False)
    for 각 케이스 (순차):
        out = evaluate_existing_simulation(fest, grid, scenario=..., mode=...,
                                           npts=..., target_nodes=...)
        append_row(csv) + flush        ← optimize_m10.py 패턴 재사용
plot_roadmap(csv_path, png_path)
```

`expand_cases`를 순수 함수로 분리한 것이 핵심이다. 누적 전개 로직 자체를 FEM 없이 밀리초 단위로 테스트할 수 있다.

누적 전개 예시:
```
baseline    {rho_c=10, spacing=2.193, nbb=8}
case1 set rho_c=2          → {rho_c=2, spacing=2.193, nbb=8}
case2 set spacing=2.4,nbb=6 → {rho_c=2, spacing=2.4,  nbb=6}
```

**병렬화는 넣지 않는다.** 전개 후에는 각 케이스가 독립이라 기술적으로 가능하지만, roadmap은 보통 2~6케이스라 이득이 없다. `--resume`(case label 기준 skip)만으로 장시간 실행이 충분히 안전하다.

---

## 7. 출력 형식

### CSV (케이스당 1행, 즉시 append + flush)

```
case_index, label, note,
<grid_params 전 필드>,
Jsc, Voc, FF, Eff, Pmpp, Vmpp, Jmpp,          ← engine_raw
P_shade, Pe, Pf_finger, Pf_busbar, Pc, total_loss,
prov_<key> …                                   ← 파라미터별 provenance 태그
git_commit, engine_version, engine_sha,
scenario_file, scenario_sha256,
nodes, mode, n_probe_auto_bumped, elapsed_s, timestamp
```

baseline이 `case_index = 0`이다.

**4-panel 값은 `engine_raw`에서 뽑는다** (`adapter.py:336-344`). `results.efficiency`가 아니다 — 후자는 busbar recovery 사후보정이 섞여 있고, 논문 figure에는 보정 없는 순수 엔진값이 안전하다.

`elapsed_s`와 `timestamp`는 비결정적이므로 회귀 대조 시 제외한다 (`optimize_m10.py`의 `NONDETERMINISTIC_COLS`와 같은 규약).

### PNG — 2×2 패널

축·제목은 영문 고정이다. 논문 figure가 첫 사용처이고, 한글 폰트 탐색 실패 시의 깨짐을 원천 차단한다.

```
┌─ Jsc [mA/cm²] ────────┬─ Voc [V] ─────────────┐
│      ●━━━━━●          │   ●━━━━━●             │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │  ← baseline 기준선(파선)
│ baseline 39.42        │ baseline 1.951        │
├─ FF [%] ──────────────┼─ Efficiency [%] ──────┤
│      ●━━━━━●          │      ●━━━━━●          │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   │
│ baseline 78.31        │ baseline 31.33        │
└───────────────────────┴───────── total +0.54 ─┘
```

- x축: 케이스 라벨 (baseline 포함, `case_index` 순)
- 각 패널에 baseline 값 수평 파선 + 수치 주석
- 각 점에 절대값, 그 아래 baseline 대비 Δ (+/−)
- Efficiency 패널 제목에만 총 Δ 병기
- 출력 경로: CSV와 같은 basename의 `.png`, dpi 150

---

## 8. 테스트 전략

| 테스트 | 내용 | 비용 |
|---|---|---|
| `test_expand_cumulative` | 누적 전개가 기대 상태 시퀀스 산출 | 순수함수, 즉시 |
| `test_rejects_unknown_key` | `set`의 모르는 키 → `ValueError` | 즉시 |
| `test_requires_provenance_for_changed_key` | `set` 키에 provenance 없으면 `ValueError` | 즉시 |
| `test_baseline_bit_identical` | **★ roadmap baseline 결과 == `evaluate_existing_simulation` 직접 호출 결과 (비트 동일)** | 20 mm 소셀 |
| `test_csv_schema` | 헤더·행수·`case_index` 순서·provenance 컬럼 존재 | 즉시 |

`test_baseline_bit_identical`이 "기존 결과 비트 불변"의 실증이다. 신규 파일만 추가한다는 구조적 보장에 더해, baseline 경로가 기존 경로와 **같은 함수를 같은 인자로 호출한다**는 것을 수치로 못박는다.

FEM이 필요한 테스트는 **기존 선례 `tests/test_optimizer.py:96-106` `test_edge_margin_zero_is_bit_identical`을 그대로 따른다** — `cell_mm=20.0` + 모듈 상수 `AX` / `NPTS`, 그리고 기존 경로와 새 경로를 같은 인자로 돌려 `==`로 비트 비교하는 구조. 같은 목적의 테스트가 이미 이 형태로 존재하므로 새 관용구를 만들 이유가 없고, 20 mm 소셀은 스위트 시간에 거의 영향을 주지 않는다 (M10은 1조합 ≈17분이며 `slow` 마커 대상이다).

베이스라인 실측(2026-08-13, `pytest -m "not slow"`): **94 passed / 2 deselected / 6 xfailed, 11분 29초.** 6 xfail은 `test_junction_bf.py`의 Vb=0 케이스로 설계상 예상된 것이다. `test_default_pin` / `test_legacy_pin`의 스택 불일치 xfail은 발동하지 않았다 — 이 머신에서 **비트 핀이 실제로 강제되고 있다.**

**착수 전제**: `pytest -m "not slow"` 베이스라인이 초록이어야 한다. 기존 실패가 있으면 그것을 먼저 기록해 새 변경이 만든 실패와 구분한다.

---

## 9. 비범위 (이번에 하지 않는 것)

- **다이오드 파라미터 축** — `adapter.py:259`가 `dp = fest.DiodeParams()`로 기본값을 새로 만들므로 J01 / Rsh / Rs_junction 등은 현재 경로로 바꿀 수 없다. 열려면 adapter에 override 주입구가 필요하고, 그 변경이 기존 스윕에 영향 없음을 별도로 증명해야 한다. `schema` 버전 필드로 후속 확장 여지를 남긴다.
- **독립(비누적) 케이스 모드** — 누적만 지원한다.
- **병렬 실행** — §6 참조.
- **GUI 연동** — CLI 전용. GUI 세션 상태에 묶이지 않는 것이 이 도구의 존재 이유다.
