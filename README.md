# 2L-FEST PRO — 2-Layer Front Electrode Simulation Tool

태양전지 **전면 전극(그리드) 설계**와 **2단자(2T) 탠덤 셀** 성능을
유한요소법(FEM) 기반으로 시뮬레이션하는 데스크톱 도구입니다.

- **버전**: v28.47 (`wf_wired`)
- **개발**: Seunghoon Lee — KIST, Dr. Inho Kim's Solar Cell Research Team
- **언어/UI**: Python 3.10+ / CustomTkinter (다크·라이트 테마)

---

## 주요 기능

| # | 기능 | 설명 |
|---|------|------|
| 1 | 구속 메시 (Constrained mesh) | 핑거/버스바 경계를 메시 엣지로 강제하는 Delaunay 삼각 메시 |
| 2 | 가변 그리드 설계 | 핑거 수·버스바 수·선폭을 파라미터로 H-패턴 전극 생성 |
| 3 | J01 공간 분포 | 패시베이션 영역 vs 금속 접촉 영역의 포화전류 차등 적용 |
| 4 | 음영 손실(Shading) | 광학적 선폭 기반 음영 손실 계산 |
| 5 | 실측 I-V 오버레이 | CSV로 측정 I-V를 불러와 시뮬레이션과 비교 |
| 6 | 2T 탠덤 모델 | 직렬 연결 2단자 2-다이오드 탠덤 셀 해석 |
| 7 | Pro UI | CustomTkinter 기반 현대적 GUI |
| 8 | 리포트 출력 | PDF 리포트 자동 생성 (구조도 + 해석 조건) |

추가: DXF 그리드 도면 입출력(선택), 한국어/모노스페이스 폰트 크로스플랫폼 자동 설정,
메시 분포 진단(비대칭/편향 경고) 등.

---

## 설치

> **요구사항: Python 3.10 이상** (`X | None` 타입힌트 사용 — 3.9에서는 실행 불가)

```bash
# 1) (권장) 가상환경
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2) 의존성 설치
pip install -r requirements.txt
```

**필수 패키지**: numpy, scipy, matplotlib, customtkinter
**선택 패키지**: ezdxf (DXF 도면 입출력 기능 사용 시)

---

## 실행

```bash
python 2L_FEST_v28_18_wf_wired.py
```

실행 시 GUI 창이 열립니다. 셀 형상·그리드 파라미터·다이오드 파라미터를 입력한 뒤
해석을 실행하면 I-V 곡선, 전위/전류 분포, 효율 지표와 PDF 리포트를 얻을 수 있습니다.

> macOS: `run.command` 를 더블클릭하면 항상 이 폴더의 최신 빌드를 Python 3.10+로 실행합니다.

### 전면전극 최적화 창 — 한/영 (Front electrode optimizer — KO/EN)

결과 화면 우측 상단의 **⚙ Optimize** 버튼이 전면전극 최적화 창을 엽니다.
이 창은 **한국어 / English** 전환을 지원합니다 (v28.47~).

- 사이드바 최상단의 **Language / 언어** 버튼으로 즉시 전환 — 재시작 불필요.
  이미 계산된 결과가 있으면 결과 텍스트·그래프도 함께 다시 그려집니다.
- 선택한 언어는 `~/.2l-fest/settings.json`에 저장되어 다음 실행에 유지됩니다.
- **기본값은 English.** 저장된 설정이 있으면 그 설정을 따릅니다.
- 언어는 표시 문자열에만 영향을 주며 **계산 결과는 완전히 동일**합니다.
- **Run optimization / Save CSV 버튼은 사이드바 하단에 고정**되어 있어 창을 줄여도
  항상 보입니다. 입력 필드가 많아 잘릴 때는 사이드바가 스크롤됩니다.
- busbar / pitch / finger / recovery factor / edge margin / FEM / efficiency 같은
  기술 용어와 기호·단위(ρ_L, mΩ·cm²)는 한국어 모드에서도 영문 그대로 둡니다.

> The optimizer window is bilingual. Use the **Language** selector at the top of the
> sidebar to switch between English and Korean; the change applies immediately and
> is remembered for the next run. English is the default. Switching the language
> never changes the computed numbers — only the displayed text.

문자열을 추가·수정하려면 `front_electrode/i18n.py` **한 파일만** 고치면 됩니다
(KO/EN 양쪽에 같은 키를 넣을 것 — 누락은 `pytest tests/test_i18n.py`가 잡습니다).

---

## 실험 I-V 비교 (EXP I-V)

측정한 실제 I-V를 시뮬레이션 곡선 위에 겹쳐 모델을 검증하는 기능입니다.

- GUI의 **EXP I-V** 버튼 → CSV 선택 → **COMPARE** 탭에서 검은 점으로 오버레이.
- 입력 양식은 **`experimental_IV_template.csv`** 참고 (그대로 열어 본인 데이터로 교체).

CSV 양식:
- `#` 줄 = 주석(무시), 빈 줄 무시, **주석 제외 첫 줄 = 헤더(무시)**
- 구분자 자동 감지: 쉼표 > 탭 > 공백
- **1열 = V [Volt], 2열 = J [mA/cm²]** (3열 이후 무시)
- 측정값이 전류(A/mA)면 셀 면적으로 나눠 **J [mA/cm²]** 로 변환
- 부호: 조명 I-V 1사분면 — V=0에서 J=+Jsc, V=Voc에서 J=0

```csv
V,J
0.000,19.40
1.720,18.60
1.960,0.00
```

---

## 앱으로 배포 (standalone, 파이썬 불필요)

파이썬 설치 없이 더블클릭으로 쓰는 단독 실행 앱을 만듭니다 (PyInstaller).

> ⚠️ **하나의 파일로 Mac+Windows 둘 다는 불가능합니다.** PyInstaller는 각 OS의
> 네이티브 바이너리를 만들기 때문에 **Mac 앱은 macOS에서, Windows exe는 Windows에서**
> 각각 빌드해야 합니다 (크로스 컴파일 불가 — 모든 파이썬 패키저 공통).

### 방법 A — GitHub Actions로 둘 다 자동 빌드 (Windows PC 불필요, 권장)

`.github/workflows/build-apps.yml` 가 **macOS·Windows 러너에서 동시에** 빌드합니다.

1. GitHub 저장소 **Actions** 탭 → "Build apps (macOS + Windows)" → **Run workflow**
   (또는 `vXX` 태그 push 시 자동 실행)
2. 끝나면 **Artifacts** 에서 `2L-FEST-PRO-macOS`, `2L-FEST-PRO-Windows` 각각 다운로드.

### 방법 B — 각 OS에서 직접 빌드

```bash
# 1회: 의존성 + 빌드도구
pip install numpy scipy matplotlib customtkinter ezdxf pyinstaller

./build_app.command     # macOS  -> dist/"2L-FEST PRO.app"  (~125 MB)
build_app.bat           # Windows -> dist\"2L-FEST PRO"\"2L-FEST PRO.exe"
```

- 미서명 빌드라 첫 실행 시: macOS는 **우클릭 → 열기**, Windows는 SmartScreen **추가 정보 → 실행**.
- 빌드 산출물(`build/`, `dist/`, `*.spec`)은 git에서 제외됩니다.

---

## 검증 스크립트

| 파일 | 용도 |
|------|------|
| `_validate_tandem.py` | 0D 해석해 ↔ FEM 솔버 탠덤 결과 교차검증 |
| `_validate_griddler.py` | 그리드 설계 모듈 검증 |
| `_audit.py` | 31개 계산 경로 헤드리스 스모크 테스트 (전 모드·지오메트리·SpatialMap·리포트·DXF) |
| `_gui_test.py` | 실제 GUI 구동 스모크 테스트 (탭 렌더·CSV/PNG 저장·DXF/실측 CSV 로드) |
| `_diag_bifacial.py` | bifacial 후면조도 진단 (top/bottom 전류정합 분석) |
| `_gui_i18n_check.py` | 실제 GUI 위젯 좌표로 한/영 번역 전수 + 레이아웃 넘침 + Run/Save 가시성 검사 (스크린샷 불필요, 엔진 미로드) |

`_review_extract.txt`는 실행 도구가 아니라 **코드 리뷰 결과 기록**이다(지오메트리 8건,
검증 5건). `CellGeometry.shading_fraction`의 `A_ov` 과다 차감 등 **엔진의 알려진 한계가
여기에만 기록돼 있어** 삭제하지 않고 보존한다. 해당 항목들은 기본 설정(pad=0,
busbar_length_frac=1)에서는 발현되지 않으며, 영향 크기도 shading 0.003 %abs 수준으로
검증돼 있다.

```bash
python _validate_tandem.py
python _validate_griddler.py
python -m pytest -m "not slow"     # 단위·회귀 테스트 (tests/)
```

---

## 코드 구조

단일 실행 파일 `2L_FEST_v28_18_wf_wired.py` (약 12,000줄). 핵심 클래스:

| 클래스 | 역할 |
|--------|------|
| `GridDesign` | 한쪽 면(전면/후면)의 H-패턴 전극 설계 |
| `CellGeometry` | 웨이퍼 형상 + 전·후면 GridDesign 통합 |
| `DiodeParams` | 탠덤 2-다이오드 파라미터 |
| `SpatialMap` | 노드별 파라미터 배수 분포 |
| `MeshProlongationSeedProvider` | 거친 메시 해를 보간해 초기값 제공(수렴 가속) |
| `FESTSolver` | FEM 분포 회로 솔버(핵심 해석 엔진) |
| `DxfGrid` | DXF 그리드 도면 입출력 |
| `FESTProApp` | CustomTkinter 메인 GUI 애플리케이션 |

부가 패키지 `front_electrode/` — 엔진을 **수정하지 않고** 감싸는 전면전극 최적화 모듈:

| 모듈 | 역할 |
|--------|------|
| `adapter.py` | 엔진 호출 래퍼 + busbar 반사광 회수(recovery) 사후 보정 |
| `optimizer.py` | grid search (finger / busbar / 결합 스윕) |
| `presets.py` | ITRPV 기반 탐색범위 preset |
| `ui.py` | 최적화 창 (CustomTkinter + matplotlib) |
| `i18n.py` | **표시 문자열 중앙 저장소 (한국어 / English)** |

---

## 동작 환경

- OS: Windows / macOS / Linux (폰트 자동 탐지로 크로스플랫폼 지원)
- Python: 3.10 이상 (검증 환경 3.12)
- 디스플레이 필요 (GUI 애플리케이션)

---

## 저작권

© KIST (Korea Institute of Science and Technology), Dr. Inho Kim's Solar Cell Research Team.
본 소프트웨어의 권리관계(직무저작물 여부 포함)는 소속 기관 규정을 따릅니다.
자세한 내용은 `LICENSE` 파일 참조.
