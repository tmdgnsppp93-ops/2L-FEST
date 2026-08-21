# Griddler 2.5 / PRO 기능 명세 (GEDOS 개발 참조용)

> **출처**: Griddler 2.5 & PRO Manual v7.0 (2023-09-15), SERIS
> **성격**: 원문 요약·재서술. 원문 발췌 아님. 매뉴얼 PDF 자체는 저작권 문제로 repo에 포함하지 않음 (`~/dev/refs/` 별도 보관, 필요 시 `--add-dir`).
> **PDF 소재 (2026-08-19 확인)**: KIST PC `~/Desktop/이승훈/Griddler_and_PRO_manual.pdf` (123쪽). 집 데스크톱·맥북에는 **없다** — 이 문서가 그쪽 머신의 유일한 근거다.
> **최종 정리**: 2026-08-13
> **개정 2026-08-14** (매뉴얼 원문 §2.7 / §4.4 / §7 재확인): §2.8에 §4.4 워크플로와 Apply lock을 추가. §2.12에 Top Cell Position, 조도 3영역, Interlayer R, Photon Coupling J01을 추가하고 §7의 PRO 표기 부재를 근거와 함께 확정.
> **개정 2026-08-19** (매뉴얼 원문 §1.2 / §2.7 / §4.3 / §5.2.2 / §6.2 / §6.6 확인): **§1-1 등가회로** 신설(소자 목록·지배 방정식·**용량 소자 부재**), §2.4에 wafer internal series/shunt 상세, **§2.8-a Base Transport Calculator 상세** 신설(+`base_lateral_convention.md`의 `0.05 %p` 수치 정정), **§2.11-a 시간 의존 항목** 신설(§6.6 본문 전부 · §6.2의 복소 수명 근사). 계기: 우선순위 3 계획서가 명령어 이름 두 개만으로 모델을 추정해야 했던 상태.
> **개정 2026-08-14 (2차)**: §2.8에 **매뉴얼-빌드 불일치** 경고를 신설. 1차 개정에서 "매뉴얼 전문 검색 0건"을 RayFlare 부재의 근거로 썼으나, 사용자가 PRO 빌드 타이틀바에서 `<rayflare>`를 직접 확인했고 "Griddler Lock"도 같은 패턴(매뉴얼 0건·화면 존재)이다. **grep 0건은 매뉴얼이 현 빌드보다 낡았다는 근거로 읽어야 한다.** 같은 오류가 들어갔던 탠덤 광학 항목도 함께 정정.

---

## 0. 이 문서의 사용 규칙 (읽는 에이전트를 위한 지침)

**이 문서는 Griddler에 어떤 기능이 있는지만 서술한다. GEDOS에 그 기능이 있는지 없는지는 서술하지 않는다.**

- 모든 기능의 `구현상태` 열은 `?`로 비어 있다. 이는 "미구현"이 아니라 **"미확인"**을 뜻한다.
- 상태를 판정할 때는 반드시 저장소 코드를 직접 읽고, **파일:라인 근거**를 제시할 것.
- GUI에 버튼이나 입력란이 존재한다는 사실만으로 "구현"으로 판정하지 말 것. 계산 로직과 테스트 커버리지까지 확인할 것. (과거 GUI 클래스가 조용히 소비되어 실행 전까지 발견되지 않은 버그 이력 있음)
- 판정 결과는 이 파일을 수정하지 말고 별도 감사 보고서로 출력할 것. 이 파일은 Griddler 쪽 사실만 담는 중립 레퍼런스로 유지한다.

**구현 우선순위 등급 (`Pri` 열)**
| 등급 | 의미 |
|---|---|
| **A** | 현재 연구 과제에 직결. 우선 검토 |
| **B** | 중기적으로 필요 |
| **C** | 참고용. 현재 scope 밖 |

---

## 1. Griddler 코어 모델

셀의 front / rear plane을 삼각형 mesh로 나눈 **FEM 네트워크 모델**.

- 각 노드에서 semiconductor node voltage를 푼다 → 그 즉시 `V_diode,i`와 `I(V_diode,i)`가 결정됨
- 셀 전체 전류 = front 또는 rear semiconductor plane의 모든 노드에 대한 `I(V_diode,i)` 합
- 셀 전체 전압 = 전류가 추출되는 front 노드 전압 − rear 노드 전압 (rear는 보통 0 V = ground)
- 동작점은 조도(`I_L,i`)와 terminal voltage 경계조건으로 정의
- terminal voltage를 step-and-repeat으로 훑으면서 매번 셀 전압을 풀면 → 전체 I-V 특성이 나온다

> GEDOS의 2D distributed-diode 접근과 동일 계열. 비교 검증 시 이 정의를 기준으로 삼을 것.

### 1-1. 등가회로 — 매뉴얼 §1.2 본문 (2026-08-19 원문 확인)

> **왜 이 절이 새로 생겼나**: 위 §1은 "노드 전압을 푼다"까지만 적고 **등가회로의
> 소자 목록과 지배 방정식을 적지 않았다.** 과도·AC 항목(§6.6·§6.2)을 판정하려면
> *"용량 소자가 어디에 붙는가"* 를 먼저 알아야 하는데 그 근거가 저장소에 없었다.
> 매뉴얼 본문(p.5~6)에서 확인해 아래에 옮긴다.

**평면 구성.** 일반적으로 **1~8개 평면**이 존재한다. 가장 단순한 경우는 front 1개
평면뿐이고, 이때 rear는 *"완전한 횡전도 + 접지 전위"* 로 가정된다(= simulation
page의 `Full Area Rear Chuck Contacting`, §2.7.4). 가장 복잡한 경우는 front/rear
각각에 **semiconductor plane / metal finger plane**(핑거-반도체 접촉저항이 있을 때)
**/ metal busbar plane**(dual print로 busbar를 floating으로 둘 때) **/ ribbons
plane**(`Solder ribbons at probe points`)이 따로 존재한다.

ribbons plane을 뺀 나머지는 삼각 mesh로 분할되고, 삼각형 변이 노드를 저항으로
잇는다. 저항값은 그 영역의 **면저항**과 **삼각형 형상**(Galerkin 법)으로 정해진다.

**샌드위치 층 = 등가회로.** front / rear semiconductor plane 사이에 광전 특성을
담는 샌드위치 층이 있고, 이것이 각 노드에 붙는 작은 등가회로다. 매뉴얼은 이것을
**two diode model**이라 부른다. 소자는 다음이 **전부**다.

| 소자 | 매뉴얼 표기 |
|---|---|
| n=1 다이오드 | `n=1 diode` |
| n=2 다이오드 | `n=2 diode` |
| 광생성 전류원 (다이오드와 병렬) | `light induced current` |
| shunt 컨덕턴스 (병렬) | `shunt conductance` |
| (옵션) 노드와 등가회로 사이의 직렬 저항 | `Internal series resistance` — §2.7, 기본값 0 |

> ⚠ **용량 소자(capacitor)는 등가회로에 없다.** §1.2 그림에서 소자를 가리키는 라벨은
> `n=1 diode` · `n=2 diode` · `light induced current` · `shunt conductance` 네 개와,
> 노드-이웃노드를 잇는 `series resistance` 하나가 전부다(표의 5번째 항목은 §2.7이
> 켜는 옵션이다). §2.7의 등가회로 변형 그림 3종에도 용량 소자는 없다.
> 매뉴얼 전체에서 `capacitance`/`capacitive`가 소자를 가리키며 쓰인 곳은 **한 곳도
> 없다**(유일 등장은 Appendix C의 `electrochemical capacitance voltage` = ECV
> 도핑 프로파일 측정으로, 무관하다).

**지배 방정식** (원문 기호 그대로):

```
I(V_diode,i) = I_L,i
             − I01,i · exp( q·V_diode,i / (kT) )
             − I02,i · exp( q·V_diode,i / (2kT) )
             − G_shunt,i · V_diode,i

V_diode,i = V_node,i − V_ref,i
```

`V_ref,i`는 **반대편 semiconductor plane의 전압을 노드 i 위치에서 보간한 값**이다.
이것으로 노드 i에서 Kirchhoff 전류법칙을 세운다:

```
Σ_(이웃 노드 j)  ( V_node,j − V_node,i ) / R_series,i,j   +   I(V_diode,i)  =  0
```

> **시간 항이 없다.** 위 KCL은 각 노드에서 **정상상태** 전류 연속 조건이며, 매뉴얼은
> 이 연립방정식을 반복법으로 푼다고만 기술한다. §6.2가 이 성질을 명시적으로
> 확인해 준다 — *"the Griddler solver is inherently for steady state situations"*
> (아래 §2.11-a).

---

## 2. 전체 기능 인벤토리

### 2.1 Design H Pattern Page (§2.4) — 무료판 포함

| # | 기능 | 무료/PRO | 내용 | Pri | 구현상태 |
|---|---|---|---|---|---|
| 1 | Wafer Type | 무료 | square (multi 전형) / pseudo-square (mono 전형) / circular (lab 사이즈) | B | ? |
| 2 | Ingot Diameter | 무료 | pseudo-square일 때 **웨이퍼 대각선**을 정의 | B | ? |
| 3 | Shingling Pattern | 무료 | 각 면에 busbar 1개를 **웨이퍼 가장자리**에 배치. 셀 길이 < 폭 | C | ? |
| 4 | Wafer Length / Width | 무료 | M10 등 포맷 정의 | A | ? |
| 5 | No of BB / BB width / Solder-Probe Points | 무료 | busbar 개수·폭 및 **busbar당 접점 개수** | A | ? |
| 6 | Busbar Style | **PRO 6종 / 무료 3종** | busbar는 unit segment의 반복이며 각 segment가 접점 1개를 포함. **무료판은 segment 치수 조정 불가** | B | ? |
| 7 | Busbar Ending | **PRO 전용** | busbar 양 끝 segment 형상. "Straight" = 추가 segment 없음 + 4종. **무료판은 선택 불가** | C | ? |
| 8 | Print Method | 무료 | **Single print**: busbar·finger가 같은 금속층, 전체가 emitter와 접촉, 양쪽 모두 metal-induced recombination 발생 / **Dual print**: finger만 반도체 접촉, busbar는 finger에만 전기적으로 연결된 "floating" 상태 | **A** | ? |
| 9 | Fingers Definition | 무료 | No of fingers, Finger width, **Taper fingers** (busbar 근처 구간을 넓게: "taper from" 최대폭 + "over distance of" 테이퍼 길이) | **A** | ? |
| 10 | End Joining | 무료 | finger 끝단 연결 | B | ? |
| 11 | Edge Gap | 무료 | **edge margin에 해당** | **A** | ? |
| 12–14 | Rear Pattern | 무료 | 활성화 시 3종: (a) full area metal (Al-BSF형) / (b) line contact + full area metal (PERC·LBSF형, 주기적 line opening) / (c) H-pattern (bifacial). 비활성화 시 rear plane은 lateral conductance 완전 가정 하에 ground 고정 | **A** | ? |
| 15–19 | 기타 | 무료 | Redo/Undo, Toggle Front/Back View, **Save to AutoCAD DXF**, 패턴 자동저장 | B | ? |

> **Note**: Griddler는 H-pattern을 dxf로 **내보내기**도 지원한다 (§2.6의 layer 규약 준수). GEDOS는 현재 dxf **가져오기**만 논의되었으나, 내보내기가 있으면 외부 공유·CAD 검증에 유용.

### 2.2 Meshing Page (§2.5) — 무료판 포함

| 단계 | 내용 | Pri | 구현상태 |
|---|---|---|---|
| Step 0 (optional) | Post editing: `Create Breaks` (지정 사각형 내 금속 제거) / `Create Extra Rectangles` (금속 추가) / `Create Extra Terminals` (solder·probe 점 추가). 커서가 cross-hair로 바뀌어 두 모서리 지정 | C | ? |
| Step 1 | Analyze Pattern — 각 layer의 모든 shape을 하나로 merge | B | ? |
| Step 2 | Mesh Detail — **금속에 접선 방향**과 **수직 방향**의 mesh 밀도를 각각 지정 | **A** | ? |
| Step 3–4 | Mesh 실행 및 확인 | B | ? |

**Griddler의 메시 밀도 가이드라인 (중요)**
- busbar 사이 finger를 따라 **최소 4개 노드**
- finger 사이에 **최소 4개 노드**
- 단, busbar가 매우 많고 finger가 매우 짧으면 예외

> 이 기준은 GEDOS의 **수렴성 검증에 바로 쓸 수 있다.** 과거 M10과 소면적 셀의 수렴 방향이 서로 반대였던 현상(지배적 이산화 오차 항이 다름)을 이 기준으로 재점검할 것.

정밀 편집은 GUI 대신 커맨드로도 가능. 예: `DRAWEXTRAFRONTSHAPE 1 x1 y1 x2 y2 x3 y3 x4 y4` — layer 1(fingers)에 지정 꼭짓점의 금속 polygon 추가 (좌표 단위 cm).

### 2.3 Import AutoCAD DXF (§2.6) — 무료판 포함

- H-pattern이 아닌 **임의 형상** 지원. 매뉴얼 예시는 MWT 셀의 snowflake 패턴 (약 3.8 × 3.8 cm 단위 구역, 중심에 probe point)
- Griddler가 임의 형상을 삼각 mesh로 변환하고, 시뮬레이션 결과 전압 분포가 매끄러우면 mesh 품질 양호로 판단
- dxf 작성용 **design rule**이 별도 제공됨 (front page의 help 버튼)

> **박사님 결정 사항 (2026-08-13 랩미팅)**: CAD import 패턴은 fixed design이므로 **파라미터 sweep 대상이 아니다.** Sweep은 수치 입력 방식 디자인에만 적용. 이 구분을 코드 구조에도 반영할 것.

### 2.4 Simulation Page (§2.7)

| 기능 | 무료/PRO | 내용 | Pri | 구현상태 |
|---|---|---|---|---|
| Metallization sheet resistance | 무료 | front/rear의 finger층·busbar층·semiconductor층 sheet resistance 정의 | **A** | ? |
| Wafer internal series R / shunt conductance | 무료 | 기본값 0. 비영값이면 등가회로에 직렬 저항 또는 shunt path 삽입 | **A** | ? |
| **Temperature ≠ 25°C** | **PRO** | 모듈 시뮬레이션에 필요 (모듈 온도는 상온보다 높음) | B | ? |
| **External series resistance > 0** | **PRO** | 모듈의 케이블·인터커넥션 저항 | B | ? |
| **Metal Optical Transparency** | 무료 | **physical width**(contact area 결정)와 **optical width**(shading 결정)의 비율 | **A** | ? |
| Current extraction mode | 무료 | `Extract Current at Each Probe Point` (I-V tester 프로브 모사) / `Solder ribbons at probe points, extract current at ribbon ends` (모듈 모사) | B | ? |

**Wafer Internal Series / Shunt 상세** (매뉴얼 §2.7 본문, 2026-08-19 원문 확인)

- **기본값은 둘 다 0이다.** *"By default the wafer internal series resistance and
  shunt conductance are both set to zero."*
- **internal series resistance**를 0이 아니게 하면 **노드와 §1.2 등가회로 사이에
  저항 하나가 삽입**된다 (*"inserts an extra resistor in-between the node and the
  equivalent circuit shown in section 1.2"*). 즉 등가회로 **바깥**, 노드와 회로
  사이의 직렬 소자다 — 다이오드와 병렬이 아니다.
- **internal shunt conductance**를 0이 아니게 하면 등가회로의 **shunt 소자**가
  전류 경로를 만든다. 즉 이것은 §1.2 등가회로가 **원래 갖고 있는 소자**를 켜는
  것이지 새 소자를 넣는 것이 아니다.
- 매뉴얼은 두 값을 올렸을 때 I-V 특성이 어떻게 바뀌는지를 스크린샷으로만 보이고,
  **수식은 §1.2의 것 외에 따로 주지 않는다.**
- 같은 절에 Temperature(PRO)와 External series resistance(PRO)가 함께 있다.
  external series resistance는 셀 **바깥**(모듈 케이블·인터커넥션)이므로
  wafer internal series resistance와 층위가 다르다.

> **단위 표기 주의**: 매뉴얼 본문은 이 두 항목의 단위를 문장 안에 적지 않는다
> (화면 입력란 라벨에만 있다). 인용할 때 단위를 추정해 적지 말 것 —
> Appendix A.5 오독의 실체가 정확히 *"단위를 확인하지 않고 층위를 단정한 것"*
> 이었다.

**Sheet resistance 변환식** (GEDOS 입력 검증용)

```
ρ_sheet = ρ_bulk / t_layer
  예: ρ_bulk = 3e-8 Ω·m, t_layer = 10 µm  →  ρ_sheet = 3 mΩ/sq

ρ_sheet = R_line × w_line
  예: R_line = 0.333 Ω/cm, w_line = 60 µm  →  ρ_sheet = 2 mΩ/sq
```

**온도 스케일링 (PRO)**

```
J01(T) = J01(25°C) × [ n_i(T) / n_i(25°C) ]^2
J02(T) = J02(25°C) × [ n_i(T) / n_i(25°C) ]^1

n_i(T) = 9.15e19 × ( (T+273.15)/300 )^2 × exp( -6880 / (T+273.15) )
   T: °C, n_i: 실리콘 진성 캐리어 농도
```

> ⚠️ **Griddler가 모델링하지 않는 것 (우리도 동일 한계를 문서화할 것)**
> - Jsc의 온도계수 (밴드갭 감소 → IR 흡수 증가분)
> - 캐리어 mobility 변화에 따른 semiconductor sheet resistance 변화

**Metal Optical Transparency의 물리적 근거**
금속 finger·busbar의 optical width는 통상 physical width보다 **작다**. 빛이 금속 facet에서 셀 쪽으로 직접 산란되거나, 모듈에서는 facet에서 산란된 뒤 glass-air 계면에서 내부 반사되어 셀로 되돌아오기 때문.

> **직접 적용처**: 상용 MBB(16BB/18BB)의 busbar는 연속 스트립이 아니라 분절된 solder pad + 극세 연결선 구조다. 이를 단일 폭의 연속 스트립으로 모델링하면 shading을 과대평가한다. physical/optical width 분리가 이 문제의 정공법.

### 2.5 Loss Chart (§2.8) — 무료판 포함

`Find Jsc Voc MPP` 실행 후 나타나며, 라디오 버튼으로 4개 차트 전환.

| # | 차트 | 단위·내용 | Pri | 구현상태 |
|---|---|---|---|---|
| 1 | Power loss bar graph | mW/cm². MPP 출력 + shading 손실 + recombination 손실 + 저항 손실 분해 | **A** | ? |
| 2 | Recombination pie @ MPP | mA/cm². 합계 × wafer area = MPP에서의 총 recombination 전류 | B | ? |
| 3 | Recombination pie @ OC | 포화전류밀도. MPP 값을 `exp(qVoc/kT)`로 나눈 것이며 통상 fA/cm² 단위 → J0 항들과 직접 비교 가능 | B | ? |
| 4 | **FF drops waterfall** | 아래 참조 | **A** | **원리가 다른 물건** — `docs/ff_waterfall_convention.md` |

**FF drops waterfall 계산 순서 (Griddler 정의 그대로)**

1. Edge recombination off (있는 경우)
2. Passivated 영역의 front J01을 **median 값**으로 치환 (공간 비균일 분포가 설정된 경우)
3. n=2 diode off
4. Metal contact에 의한 recombination 증가분 off — 금속 영역의 J01, J02를 대응하는 passivated 영역 값과 동일하게 설정
5. Shunt conductance off (있는 경우)
6. 마지막 시나리오의 총 I01로 **저항 없는 ideal FF** 계산:
   `I(V) = I_L − I01 · (exp(qV/kT) − 1)`

**핵심 해석 규칙 두 가지 (반드시 함께 구현):**
- 마지막 시뮬레이션 FF와 ideal FF의 **차이는 전부 직렬 저항 탓으로 귀속**된다
- 그 직렬 저항 내부에서 각 성분(finger / busbar / emitter / contact)의 FF 침식 기여 비율은 **MPP에서의 전력 소산 기여 비율과 같다고 가정**한다

> ### ⚠ GEDOS의 워터폴은 이 정의가 **아니다** — 수치를 직접 대조할 수 없다
>
> Griddler는 위 6단계 **순차 재시뮬레이션**이고, GEDOS `_tab_waterfall`은
> 재시뮬레이션 없이 단일 해의 **FEM 손실 분해를 누적**한다. 그래서
> 2단계(중앙값 치환)가 우리에게는 필요 없지만 — 그 단계는 0D 재구성을 위해
> 공간 분포를 스칼라로 접는 장치이고 우리 막대는 손실 적분의 항이다 —
> 같은 이유로 **두 워터폴의 막대는 이름이 같아도 같은 양이 아니다.**
>
> 물리적으로는 우리 쪽이 강하다(잔차 귀속·전력 비율 가정이 불필요). 그러나
> 교차검증에서 이 차이를 모르면 **불일치를 결함으로 오인한다.** 대조 가능한
> 양의 목록과 6단계 러너 착수 전제: **`docs/ff_waterfall_convention.md`**

> 이 차트는 구축에 시간이 걸린다고 매뉴얼이 명시 (여러 시나리오를 순차 시뮬레이션하므로). 성능 최적화 시 참고.
>
> **직접 적용처**: edge margin 증가에 따른 FF 감소의 원인 규명. 현재 "직렬 저항 성분으로 판단됨"으로 hedge된 주장을 수치로 확정할 수 있다.

### 2.6 Nonuniform Cell Parameters (§3.1)

- 대부분의 cell parameter에 **공간 분포**를 부여 가능
- 파라미터 옆 버튼 → canvas → `Enable` 체크 → `Import pattern`
- 입력 포맷: **jpg / tif / bmp / txt**
  - `txt` (수치 행렬): **절대값 그대로** 할당
  - 이미지 포맷: **상대값**으로 할당되며, 평균값을 별도 입력란에 지정
- 비균일 설정된 항목은 시뮬레이션 페이지에서 숫자가 **파란색**으로 표시됨

| Pri | 구현상태 |
|---|---|
| B | ? |

> 페로브스카이트 top cell의 공간 균일도 이슈, 또는 pressing 압력 불균일에 따른 국소 contact resistance 분포 모사에 활용 가능.

### 2.7 Cell Parameter Database (§3.2) — PRO 전용

- 전 세계에서 수집한 published cell parameter를 저장하고 lookup으로 적용
- 약 월 1회 갱신되며, 프로그램 실행 후 DB 최초 접근 시 자동으로 업데이트 검색·다운로드

| Pri | 구현상태 |
|---|---|
| B | ? |

> **우리 버전 설계 제안**: 외부 published 값 대신 **랩 자체 측정값 DB**로 구성. 각 항목에 `measured` / `assumed` / `derived` 태그 + 측정일자 + 측정자 + 측정방법을 필수 필드로 두면, data provenance 원칙이 소프트웨어 레벨에서 강제된다.

### 2.8 Solar Cell Diode Parameter Calculations (§4) — PRO 전용

| 절 | 기능 | 내용 | Pri | 구현상태 |
|---|---|---|---|---|
| 4.2 | Cell Cross Section Diagram | 셀 단면 기반 전류·재결합 파라미터 계산 인터페이스 | C | ? |
| 4.3 | Base Transport Calculator | base 영역 수송 계산. **local contact calculator** 포함 (PERC/LBSF를 full-area metal + 유효 파라미터로 모사할 때 사용) | C | ? |
| 4.4 | **Illumination Optics** | 외부 계산기 연동: **OPAL2** (PV Lighthouse 무료 온라인), **wafer ray tracer** (PV Lighthouse), **cmd PC1D 6-2** | B | ? |
| 4.5 | Doped Layer Calculations | emitter J0e, IQE 계산. cmd-PC1D-6.2 호출 방식이며 EDNA2와 벤치마킹됨 (Appendix C) | C | ? |
| 4.6 | Transfer to Simulation Page | 계산된 항들을 시뮬레이션 페이지로 전달 | C | ? |

### ⚠️ 매뉴얼 v7.0과 현재 PRO 빌드가 불일치한다

**이 절을 읽을 때의 전제**: 매뉴얼 v7.0은 2023-09 판이고, 현재 PRO 빌드에는 매뉴얼에 없는 기능이 최소 둘 있다. **매뉴얼 전문 검색에서 안 나온다는 사실을 기능 부재의 근거로 쓰면 안 된다.** 아래 두 사례가 그 이유다.

| 항목 | 매뉴얼 v7.0 | 실제 PRO 빌드 |
|---|---|---|
| **RayFlare** | 전문 0건 (대소문자 무관) | **존재.** 사용자가 창 타이틀바의 `<rayflare>`를 직접 확인 |
| **Griddler Lock** | 전문 0건 | **존재.** 화면에 있음 |

즉 매뉴얼이 낡았다. 이 문서의 §4 관련 기술은 v7.0 시점의 스냅샷으로 읽고, 최신 기능은 빌드에서 직접 확인해야 한다.

**RayFlare에 대해 확정된 것**

- **LGPL v3 오픈소스 Python 패키지**다 (qpv-research-group, JOSS 논문 게재). 광학 전용 — 박막 다층 간섭, ray tracing, RCWA를 한 프레임워크에서 다룬다
- Griddler PRO 안에서 **별도 창**으로 뜬다 (타이틀바 `<rayflare>`)
- **Griddler 본체와의 인터페이스는 매우 얕다 — `Jgen` 스칼라 하나.** 광학 계산 결과가 발전 전류밀도 단일 값으로 넘어오는 구조다
- **Apply lock / Griddler Lock**이 셀 구조를 두 모듈 사이에서 동기화하는 별도 계층으로 존재한다

**아직 확정되지 않은 것**

- PRO가 rayflare **Python 패키지를 실제로 호출**하는지, 아니면 같은 모델을 **자체 재구현**했는지. → About 메뉴의 **LGPL 고지 유무**로 판별 예정 (LGPL v3는 동적 링크 시 고지 의무가 있으므로, 고지가 있으면 실제 호출 쪽 근거가 된다)

> **용어 재검토 필요**: 이 문서는 랩미팅의 "레이 플레이어"를 *PV Lighthouse의 wafer ray tracer*의 음성 인식 오류로 정정했었다. 그러나 **"레이 플레이어"는 음성상 "RayFlare"에 훨씬 가깝다.** 당시 언급 대상이 wafer ray tracer가 아니라 RayFlare였을 가능성이 높다. 확인 후 확정할 것.
> (매뉴얼에서 *wafer ray tracer*라는 표현 자체는 Appendix A 도입부 p.106에 실재하며, cmd PC1D 6-2 · OPAL2와 함께 "외부 계산기"로 묶여 언급된다. 다만 §4.4 본문에 단계별 워크플로가 실린 것은 OPAL2 하나뿐이다.)

**우리에게 주는 함의**: 인터페이스가 `Jgen` 스칼라 하나라면, GEDOS가 RayFlare를 붙이는 난이도도 그만큼 낮다. 광학 계산을 직접 구현할 필요 없이 **동일한 얕은 경계(스펙트럼 → Jgen)** 만 맞추면 된다. 다만 LGPL v3라 배포 형태(동적 링크 / 별도 프로세스 / 재구현)에 따라 라이선스 의무가 달라지므로, 붙이기 전에 배포 방식을 먼저 정해야 한다.

**§4.4 워크플로 (2026-08-14 본문 확인)**

1. 셀 단면 다이어그램에서 `Front/Rear Illumination Optics`를 눌러 광학 페이지를 연다
2. 이 페이지는 입력 두 가지를 요구한다 — **300–1200 nm 실리콘 영역 흡수율**과 **같은 구간의 조도 스펙트럼**. 기본값은 임의의 PERC 실리콘 흡수율 곡선 + AM1.5G(정규화 발전 전류밀도 46.3 mA/cm²)이며 둘 다 import/붙여넣기로 교체 가능
3. `OPAL (free)` 버튼 → PV Lighthouse의 OPAL2로 이동 → 표면 형상과 반사방지막을 정의해 입사면 광학을 계산 → `RAT data` 탭의 열 전체를 복사 → Griddler 광학 페이지 상단 박스에 붙여넣기. Griddler가 `Transmission` 열을 자동 인식한다
4. `Light Trapping` 버튼으로 부위별 internal reflectance와 doped layer별 free carrier absorption 반영 여부를 조정
5. 셀 단면 창에서 `Apply All`을 눌러야 비차폐 영역의 J_L이 실제로 반영된다

**Apply lock (자동 재계산 잠금)**

`Apply lock`을 켜두면 **metallization pattern이 바뀔 때마다** Griddler가 light trapping과 J0 계산을 자동으로 다시 돌리고, 갱신된 비차폐 영역 J_L을 자동 적용한다. 자물쇠 아이콘을 눌러 강제 적용도 가능하다. 이것이 §4.4를 단순한 "값 입력"이 아니라 **설계 변경에 연동되는 계산 경로**로 만드는 장치다.

**탠덤과의 관계 — 매뉴얼 v7.0에는 연결이 서술되지 않는다 (빌드 확인 필요)**

2026-08-14 확인: `tandem`이라는 단어는 목차를 빼면 **p.99–105(§7)에만** 등장하고, 그 7페이지 안에는 `absorptance` / `Optics` / `spectrum` / `OPAL` / `light trapping` 중 **어느 것도 나오지 않는다.** 매뉴얼 기준으로 §4.4 광학 페이지는 단일 셀 모델에 붙는 기능이고, tandem의 조도는 §7에서 영역별 조도·Jsc 값을 **직접 입력**받는다.

> ⚠️ **여기서 "Griddler에는 없다"로 결론짓지 말 것.** 위의 매뉴얼-빌드 불일치가 그대로 적용된다. RayFlare가 광학 전용 모듈이고 인터페이스가 `Jgen` 스칼라라는 점을 감안하면, **서브셀별 Jgen을 각각 산출하는 형태로 현 빌드가 이미 탠덤 광학을 다루고 있을 가능성이 있다.** 매뉴얼 v7.0에 서술이 없다는 것까지가 확인된 사실이다.
>
> **빌드에서 확인할 것**: tandem 모드에서 top/bottom 각각에 RayFlare 창을 띄울 수 있는지, 띄운다면 top cell 결과가 bottom cell 입력 스펙트럼에 반영되는지.

**Illumination Optics 핵심 로직 (연동 없이도 구현 가능한 부분)**

```
J_L = J_Si,absorption − J_loss,FCA − J_loss,emitter − J_loss,base
```

- PRO v2.50034 이후, import한 흡수율 데이터가 **1200 nm에서 30%를 초과하면 transmittance 곡선**으로 간주하고 light trapping 계산으로 absorptance를 도출. **30% 이하면** 유한 두께가 이미 반영된 absorptance로 간주하고, 외삽으로 transmittance를 역산
- Light trapping은 **Basore 모델** 사용. 파라미터(T1, T2, Tn, Rf1, Rfn, Rb1, Rbn)는 양면 표면 형상(planar/pyramid), 금속·비금속 영역의 internal reflectance, 양면 grid layout에 의해 결정됨
- Griddler가 이를 자동 재계산하는 이유: metallization pattern이 바뀌면 light trapping이 바뀌기 때문 (금속 영역과 비금속 영역의 internal reflectance가 다름). wafer resistivity와 doped layer profile도 free carrier absorption을 통해 영향

> **구현 판단**: 외부 툴 연동은 부담이 크다. **absorptance/transmittance 곡선 import + 30% 판별 로직 + Basore light trapping**만 구현해도 효용의 대부분을 확보한다. Tandem 기능과 함께 가면 의미가 커진다 (perovskite top cell이 Si bottom cell의 흡수 스펙트럼을 바꾸므로).

### 2.8-a Base Transport Calculator 상세 (§4.3) — 2026-08-19 원문 확인

> **왜 상세가 필요한가**: §6.2가 시간 의존성을 **이 계산기 안에서** 구현한다고
> 적었고(§2.11-a), Appendix A의 제목 자체가 *"Mathematical Formulae used in the
> Cell Cross Sectional Diagram and **Base Transport Calculator** Pages"* 다.
> 즉 **Appendix A = 이 계산기의 수식**이며, FEM 솔버의 수식이 아니다.
> 이것이 벌크 횡전도 초안에서 Appendix A.5를 솔버 모델로 읽은 오독의 구조다.

**계산기의 성격** (원문 재서술): 셀 단면도와 base transport calculator가 함께
*"straightforward, analytical equations의 그물"* 을 이루어, Griddler가 쓰는 다이오드
항 — `J_L,front`, `J_L,rear`, `J01,front^pass`, `J01,front^metal`, `J01,rear^pass`,
`J01,rear^metal` — 을 **산출**한다. 산출된 값은 `Apply`로 시뮬레이션 페이지의
입력란에 **써 넣어진다**(§4.6).

**화면 항목 7가지**

| # | 항목 | 내용 |
|---|---|---|
| 1 | **Simulate Lateral Base Currents** | 기본 **off**. 아래 별도 항목 |
| 2 | Wafer Type / Thickness / Resistivity | base 도핑 준위 → 평형 소수캐리어 농도 → 재결합 전류밀도 |
| 3 | Auger and Radiative Recombination | 실리콘 고유(intrinsic) 재결합 on/off |
| 4 | Base Contact Geometry | 주기적 base 금속 접촉 3종: stripe / 정사각 배열 원형 점 / 육각 배열 원형 점 |
| 5 | Base Local Contact Resistance | base 주기 접촉의 금속-반도체 접촉저항 |
| 6 | Bulk Lifetime, Contact SRV, Passivation SRV | 벌크 수명 τ, 접촉부 SRV, 패시베이션부 SRV |
| 7 | **Effective Base J01 · Effective Contact Resistance** | 위 전부를 Appendix A 해석식에 넣어 산출. `Apply`는 유효 base J01을 rear의 **passivated·metal J01 양쪽**에, 유효 접촉저항을 rear metallization의 `finger contact res`에 적용 |

**1. Simulate Lateral Base Currents — 원문 그대로**

> Griddler는 본질적으로 **2D 시뮬레이터**여서 전류가 위·아래 평면에서 횡방향으로만
> 흐르고, 다이오드로 표현되는 "샌드위치" 층에서는 흐르지 않는다. 실제로는 전자와
> 정공이 준중성 벌크에서 드리프트·확산할 수 있고 그것이 횡전류로 나타난다. 이
> 옵션을 켜면 **벌크 전류 항이 추가**되며, 대가는 **전압 솔버의 수렴률과 전체
> 시뮬레이션 속도**다.

```
J_n = q · µ_n · n · ∇ε_fn
J_p = q · µ_p · p · ∇ε_fp
```

**두 가지 중요한 근사**를 매뉴얼이 명시한다:

1. `µ_n`, `µ_p`는 **평형값**을 쓴다
2. `n`, `p`는 **웨이퍼 깊이 방향으로 일정**하다고 본다

**옵션 on/off 비교표 (매뉴얼 p.49 실제 수치)**

Voc ≈ 669 mV 셀, 1 Sun:

| | Jsc (mA/cm²) | Voc (mV) | FF (%) | Eff (%) | Vmp (mV) | Jmp (mA/cm²) |
|---|---|---|---|---|---|---|
| without | 37.997627 | 669.1464 | 80.76277 | **20.53472** | 572.5797 | 35.863513 |
| with | 37.997627 | 669.3543 | 80.77673 | **20.54465** | 573.0274 | 35.852824 |

같은 셀, **3.6 Suns**:

| | Jsc (mA/cm²) | Voc (mV) | FF (%) | Eff (%) | Vmp (mV) | Jmp (mA/cm²) |
|---|---|---|---|---|---|---|
| without | 136.79145 | 702.4682 | 77.84141 | **20.77753** | 578.7787 | 129.236087 |
| with | 136.791451 | 703.4755 | 78.12487 | **20.88309** | 582.1547 | 129.139407 |

> ### ⚠ 저장소 문서의 수치 정정 (2026-08-19)
>
> `docs/base_lateral_convention.md`와 벌크 횡전도 계획서가 이 관측을
> **"1 Sun 0.05 %p → 3.6 Suns 0.11 %p"** 로 인용해 왔다. 위 표에서 실제로 계산하면
>
> | 조건 | Δ효율 (절대, %p) | Δ효율 (상대, %) |
> |---|---|---|
> | 1 Sun | **+0.0099** | +0.048 |
> | 3.6 Suns | **+0.1056** | +0.508 |
>
> 즉 **1 Sun의 0.05는 %p가 아니라 상대 %** 이고, 3.6 Suns의 0.11은 %p다.
> **두 값의 단위가 서로 다른 채로 한 문장에 인용돼 있었다.** 절대 %p로 통일하면
> 0.0099 → 0.1056으로 **약 10.6배**이며, 인용된 2.2배보다 전압 의존성이 훨씬 강하다.
> 따라서 *"효과가 전압 상승에 따라 커진다"* 는 논지 자체는 그대로 서고, **강해진다.**
>
> 매뉴얼은 이 차이를 *"거의 같다(almost the same)"* 로 요약하고, *"leaving the
> option off produces accurate I-V results for most cases"* 라고 적는다.

### 2.9 Efficiency Improvement Diagram (§5.1) — PRO 전용

**동작 흐름**

1. 현재 세션을 저장 → baseline으로 등록
2. 커맨드 윈도우가 스크립트를 자동 생성: baseline 로드 → I-V 실행 → `summary.txt` 생성 후 baseline의 I-V 파라미터를 첫 행에 기록
3. 사용자가 파라미터를 변경 (H-pattern 재설계, cross section diagram, base transport 등 **어떤 변경이든 허용**되며 모두 로깅됨)
4. `Comment` 박스에 변경 내용 설명을 입력하고 Enter → 해당 케이스에 대한 I-V 실행과 결과 저장이 스크립트에 추가됨
5. 3–4를 반복한 뒤 `Play`
6. Griddler가 baseline부터 순차 재실행하며 각 케이스의 I-V 파라미터를 `summary.txt`에 누적
7. 완료 후 **Jsc / Voc / FF / Efficiency 4개 그래프**를 라디오 버튼으로 전환하며 표시. 저장 가능
8. `Stop`으로 로깅 종료. 스크립트는 저장·재실행·공유 가능 (`Batch`로 로드)

| Pri | 구현상태 |
|---|---|
| **A** | ? |

> **직접 적용처**: UNIST 협업 논문의 "TCO modification 전 → 후 효율 개선" figure가 정확히 이 형태다. baseline(수정 전 ρ_c) → 개선 케이스(수정 후 ρ_c) roadmap.
>
> **우리 구현 방향**: Griddler의 GUI 로깅 방식을 흉내낼 필요 없음. **시나리오 정의 파일(JSON/YAML) + 순차 실행 + 결과 누적 + 4-panel 출력**으로 동등 기능 구현이 가능하며 재현성도 더 좋다.

### 2.10 Command Window (§5.2) — PRO 전용

Griddler는 MATLAB 기반이라 자체 커맨드 언어를 제공한다. 확인된 커맨드:

| 커맨드 | 기능 |
|---|---|
| `DEFINE <name> <start> <end> <step>` | 배열 생성. 예: `DEFINE J02_VALUE 10 40 10` → [10,20,30,40] |
| `FOR <var> <start> <end> <step>` … `NEXT <var>` | 루프. **중첩 가능** |
| `EVAL<...>` | 대괄호 내 수식을 MATLAB 문법으로 평가. 예: `REARJ01 EVAL<[J0e_VALUE]*1.5>` |
| `[ARRAY(LOOPVAR)]` | 루프 반복 횟수를 인덱스로 배열 참조 |
| `FINDJSCVOCMPP` | I-V 계산 실행 |
| `SAVESUMMARY {file.txt} {comment}` | Jsc, Voc, FF, efficiency, Vmp, Jmp를 **한 행으로 누적 기록** |
| `SAVESESSION {name}.mat` | 세션 저장 (파일명에 변수 보간 가능) |
| `DRAWEXTRAFRONTSHAPE <layer> <x1 y1 …>` | 금속 polygon 추가 (cm 단위) |
| `TEMPERATURE <start> <end> <step> <out.txt>` | 온도 sweep |
| Parallel FOR (§5.2.4) | 루프 병렬 실행 |

| Pri | 구현상태 |
|---|---|
| **A** | ? |

> **우리 구현 방향**: 커맨드 언어를 재현하지 말 것. GEDOS는 Python이므로 **배치 설정 파일 + `itertools.product` 기반 다중 파라미터 sweep + 파생 파라미터 표현식 + 결과 CSV/xlsx 누적 append + `multiprocessing` 병렬화**가 기능적으로 동등하며 사용성이 낫다.
>
> Griddler가 parallel FOR을 별도 절로 다룬다는 것은 이 계산이 실제로 오래 걸린다는 신호다. sweep 속도가 병목이라면 병렬화 우선순위를 올릴 것.

**§5.2.2 "Some Useful Commands"가 실제로 다루는 것은 3개뿐이다** (2026-08-19 원문 확인):
`OPTIMIZEFRONTFINGERSNUM` / `OPTIMIZEREARFINGERSNUM`, `FINDJSCVOCMPP`, `SAVESUMMARY`.

> ⚠ **`SETSWEEPRATE` / `SETSWEEPTIMING`은 §5.2.2에 없다.** 매뉴얼 전체에서 이 두
> 명령이 나오는 곳은 **§6.6 본문 한 곳뿐**이다(§2.11-a). 마찬가지로 §6.2의
> `ACSWEEP` · `DIFFERENTIALMODE` · `BIASPERTURBATION` · `LIGHTPERTURBATION` ·
> `BULKLIFETIME` · `CALCEFFECTIVEREARJ01`도 §5.2.2에 없고 §6.2 예제 스크립트에만
> 나온다. **명령어 사전은 §5.2.2가 아니라 프로그램 안의 glossary**이며(§5.2.1:
> 명령 앞 몇 글자 + `tab` → 자동완성, 클릭하면 설명 창), 매뉴얼은 그 glossary의
> 내용을 싣지 않는다.
>
> → **"§5.2.2에 없다"를 기능 부재의 근거로 쓰면 안 된다.** §2.8의 매뉴얼-빌드
> 불일치 경고와 같은 계열의 함정이다.

### 2.11 Other Usages (§6) — PRO 전용

| 절 | 기능 | Pri | 구현상태 |
|---|---|---|---|
| 6.1 | Luminescence image data 시뮬레이션 (SolarEYE 연동) | C | ? |
| 6.2 | Small signal AC response — **본문 요약 §2.11-a** | C | ? |
| 6.3 | **Four-wire I-V 정밀 시뮬레이션** | B | ? |
| 6.4 | **Shingle 및 cut wafer 셀** | B | ? |
| 6.5 | Crack 시뮬레이션 | C | ? |
| 6.6 | Transient 특성 (`SETSWEEPRATE` / `SETSWEEPTIMING`) — **본문 전부 §2.11-a** | C | ? |
| 6.7 | Photoluminescence line scan | C | ? |
| 6.8 | Hotspot 및 wafer edge reverse bias breakdown (역바이어스 I-V, hotspot map, 주변 mesh 세밀화, REPORT에 전력 소산 기록) | C | ? |

> 6.3은 랩에서 4-probe 측정을 상시 수행하므로 중기적으로 관심 대상. 6.4는 half-cell 계산이 필요해지면.

### 2.11-a 시간 의존 항목 — §6.6 Transient · §6.2 Small Signal AC (2026-08-19 원문 확인)

> **왜 따로 떼어 적나**: 위 표에 `6.6 | Transient 특성 | C | ?` 한 줄뿐이라
> 우선순위 3(capacitive effects) 계획서가 **명령어 이름 두 개만 가지고** 모델을
> 추정해야 했다. 아래는 그 두 절의 **본문 전부**를 사실만 옮긴 것이다.
> 판정·설계는 여기 적지 않는다(이 문서 §0 규칙).

#### §6.6 Simulating transient solar cell characteristics

**분량**: 목차 p.90 / 본문 페이지 헤더 **91**. 본문은 **문단 하나 + 명령어 2개 +
예시 그림 1장**이 전부다. **수식은 한 줄도 없다.**

**본문이 말하는 물리 원인** (재서술):

> 고수명(high lifetime) 셀은 인가 전압에 대해 **정상상태에 도달하는 데 밀리초
> 단위의 시간**이 걸릴 수 있다. 전압 스윕 속도가 너무 빨라서 각 동작점이 참
> 정상상태가 되지 못하면, **측정된 I-V 특성에 매우 큰 편차**가 생길 수 있다.

즉 매뉴얼이 지목하는 원인은 **캐리어 수명에 따른 정상상태 도달 시간**이다.
`capacitance`·`junction capacitance`·`diffusion capacitance` 같은 말은 이 절에
**나오지 않는다.**

**명령어 2개** — *"in the simulation screen use **either of** these commands"*:

| 명령 | 인자 | 매뉴얼 설명 |
|---|---|---|
| `SETSWEEPRATE` | `{V/s}` | I-V 스윕의 **등속(constant) 전압 램프율**을 V/s로 설정 |
| `SETSWEEPTIMING` | `{filename.txt}` | **2열 텍스트 파일**을 읽는다. 각 행이 **(시간[s], 전압[V])**. 이것으로 *전압마다 다른 스윕 속도*를 정한다. 실제 I-V 테스터가 등속 램프가 아닐 수 있어 후자가 더 정확할 수 있다고 기술 |

**예시**: Voc = 741 mV인 고 Voc 셀의 **역방향(reverse) JV 스윕**을 `SETSWEEPRATE 100`
(= 100 V/s)으로 돌린 *"exaggerated example"*. 결과는 그림으로만 제시되며 **수치
표는 없다.**

**기술되지 않은 것** (= 매뉴얼에 없음):

- 용량 소자의 형태·값·부착 위치 (§1-1 등가회로에 용량 소자 자체가 없다)
- 시간 이산화 방식 (음함수/양함수, 차수, 스텝 제어)
- 파라미터화 — 무엇을 입력해야 과도 효과가 켜지는지 (`SETSWEEPRATE` 외)
- 후면·interlayer의 시간 응답 취급
- 탠덤(§7)에서의 동작

#### §6.2 Simulation of Small Signal AC Response

**§6.6과 반드시 함께 읽어야 하는 절이다** — 매뉴얼에서 시간 의존성을 **수식으로**
기술하는 유일한 곳이기 때문이다.

**핵심 문장** (원문):

> *"While the Griddler solver is **inherently for steady state situations**, it is
> possible to **approximate** what's called small signal AC response..."*

**구현 위치** (원문):

> *"To implement calculations of small signal AC response, the following changes are
> made in **the base transport calculator and luminescence signal calculation**."*

**방법**: **복소 벌크 수명** τ\* 를 정의한다.

```
1/τ*  =  1/τ  +  iω
L_diff = sqrt( D · τ* )
```

그리고 이 `L_diff`를 **Appendix A의 식 전체에 그대로 사용**한다. 발광 신호 계산도
같은 복소 `L_diff`를 쓰는 형태로 바꾼다(`Φ_luminescence = C·f(ω)·(exp(qV_diode/kT) − 1) + B·I_L`).
매뉴얼은 이를 *"equivalent to building in the complex diffusion length influence
into c"* 라고 정리한다.

> ⚠ **FEM 네트워크에는 소자가 추가되지 않는다.** AC 응답은 **계산기(Appendix A)가
> 만들어 내는 유효 다이오드 항을 복소수로 바꾸는 것**으로 구현된다. §1-1 등가회로의
> 소자 목록은 그대로다.

**관련 명령어** (§6.2 예제 스크립트에서 확인):

| 명령 | 뜻 |
|---|---|
| `DIFFERENTIALMODE {0=DC}` | DC / 차분(AC) 모드 전환 |
| `BIASPERTURBATION {mV}` | AC 전압 진폭 |
| `LIGHTPERTURBATION {Suns}` | AC 조도 진폭 |
| `ACSWEEP {out.txt} {4=ROI PL 기록} {f_from} {f_to} {N pts, log}` | 주파수 스윕 |
| `BULKLIFETIME {µs}` · `CALCEFFECTIVEREARJ01` | 계산기 입력 → **유효 rear J01** 산출·적용 |

**출력 수치는 존재한다** — p.83에 `ACSWEEP` 출력 텍스트 50행이 실려 있다(주파수
10 Hz ~ 1 MHz, DC 1 Sun / 659 mV, AC 조도 0.01 Suns 기준의 sense 전압·전류·발광의
실수/허수/크기/위상). 대조에 쓰려면 **PRO 실행 없이도 이 표를 기준선으로 쓸 수
있다.**

#### 두 절의 관계 — 사실만

- §6.2는 **정상상태 솔버를 유지한 채** 계산기 쪽 파라미터를 복소수로 만들어
  **근사**한다. 매뉴얼이 스스로 `approximate`라고 적는다.
- §6.6은 **시뮬레이션 화면의 명령어**이고, 모델은 기술되어 있지 않다.
- 두 절 모두 **같은 물리량(벌크 수명 τ)** 을 원인으로 지목한다. §6.6은 "high
  lifetime → ms 정상상태 도달", §6.2는 `1/τ* = 1/τ + iω`.
- **`capacitance`라는 소자·기호는 두 절 어디에도 없다.**

### 2.12 2J Tandem Solar Cell Simulation (§7)

> ✅ **버전 구분 — 2026-08-14 본문 확인 결과 PRO 전용이 아니다.**
> 근거 두 가지. (1) 목차에서 `3.2`, `4`, `4.2`~`4.6`, `5`, `5.1`, `5.2`는 모두 제목에 `(PRO version)`이 붙어 있고 `6`은 헤더 자체가 "Other Usages of Griddler 2.5 **PRO**"인데, **§7만 표기가 없다.** (2) 본문 p.99–105 어디에도 PRO 한정이라는 서술이 없다.
> 매뉴얼이 "무료판 포함"이라고 적극적으로 명시하지는 않으므로, 표기 체계상 PRO 전용이 아니라는 것까지가 확인 가능한 범위다.

**Griddler의 tandem 모델 구조**

2J tandem = **두 개의 일반 Griddler 셀 모델을 겹친 것**. 구체적으로 Griddler는
- top cell에서 **rear metallization을 잘라내고**
- bottom cell에서 **top metallization을 잘라낸 뒤**
- **새로운 interlayer를 추가하여 접합**한다

**필요 구성 요소**

| 요소 | 내용 |
|---|---|
| Enable Tandem | 기본 체크됨. 해제하면 현재 로드된 모델을 **단일 셀로 해석**하여 시뮬레이션 |
| Load top / bottom cell | 각각 별도의 Griddler 모델 파일을 로드 |
| Edit Top/Bottom Cell | 메인 시뮬레이션 화면에서 top/bottom을 토글하며 개별 편집 (편집 후 저장 필수) |
| **Top Cell Position** | top cell이 bottom cell보다 작을 때 **겹쳐지는 상대 위치**를 고른다. top cell이 bottom cell 면적 안에 온전히 들어가는지 보장하는 것은 **사용자 책임**이라고 매뉴얼이 못박는다 |
| Illumination 입력 위치 이동 | tandem 모드에서는 조도 입력이 메인 화면에서 **tandem 설정 화면으로 이동** |
| **조도 3영역 분리** | 조도를 **top cell / bottom cell / top과 겹치지 않는 bottom cell 영역** 세 곳에 따로 정의한다. 세 값이 서로 다르면 "Make Equal" 체크를 먼저 해제해야 한다 |
| **Non-overlapping area Jsc** | 메인 화면의 조도 입력란 자리에, **top cell이 bottom cell보다 작은 경우** 겹치지 않는 영역에서의 bottom cell 1-Sun Jsc를 별도로 정의하는 박스가 생김 |
| **Interlayer Sheet R + Contact R** | interlayer의 면저항과, 두 interlayer가 서로 맞닿는 접촉저항을 tandem 설정 화면에서 정의. 두 값 모두 blue N 버튼으로 **비균일 공간 패턴** 지정 가능 |
| **Photon Coupling J01** | luminescence coupling / photon recycling. top cell의 복사 재결합이 만든 광자가 bottom cell에 흡수되어 광전류가 되는 현상. Griddler는 단순형으로 처리한다:<br>`광자속 [cm⁻²s⁻¹] = (Photon coupling J01) × (exp(qV_Jtop/kT) − 1)` |
| Current Extraction Method 이동 | tandem 모드에서 전면·후면 extraction method 팝업이 tandem 설정 화면으로 옮겨가고, 메인 시뮬레이션 화면에서는 **회색 처리**된다 |
| Session 저장 | tandem 세션 전체를 **zip**으로 저장·복원 |

| Pri | 구현상태 |
|---|---|
| **A** | ? |

> **우리에게 유리한 점**: GEDOS는 이미 2-layer 구조이므로 골격이 존재한다.
>
> **⚠ 이 절만 예외적으로 구현상태를 병기한다** (§0 규칙의 예외 — 2026-08-14 사용자 지시). 근거는 `docs/audit_2026-08-13.md`.
> - **Photon Coupling J01 — 이미 구현됨.** GEDOS의 `J01_coupling`이 같은 함수형을 쓰며, 소스 주석이 이 절(v7.0 §7 item 7)을 이미 인용하고 있다. 솔버 3개 경로에서 야코비안 항까지 포함해 처리한다.
> - **Interlayer Sheet R / Contact R — 이미 구현됨.** `Rs_junction`(횡전도 평면)과 `Rc_junction`(수직 접촉)이 대응하고, 비균일 패턴은 `SpatialMap`이 담당한다.
>
> **미구현 격차는 "non-overlapping area Jsc" 하나가 아니라 세 가지 묶음이다.** 감사 보고서가 이 항목을 Jsc 입력 하나로 축소해 기록했는데, 실제로는:
> 1. **Top Cell Position** — 두 셀의 상대 위치라는 기하 자유도 자체가 없다
> 2. **조도 3영역 분리** — 현재는 top/bottom에 각각 하나의 조도만 줄 수 있고, "겹치지 않는 영역"이라는 제3영역 개념이 없다
> 3. **Non-overlapping area Jsc** — 위 2번의 입력에 해당
>
> 실험용 tandem 셀에서 top cell 면적이 bottom보다 작은 경우가 흔하며, 이를 반영하지 않으면 Jsc가 과대평가된다.

---

## 3. Griddler가 명시한 한계 (우리도 상속·문서화할 것)

Appendix A.1 기준:

- 계산 다수가 **25°C 실리콘 물성**에 의존한다: 전자·정공 mobility, 광흡수계수, free carrier absorption 계수, intrinsic recombination rate, doped layer 물성(J0e, sheet resistance, IQE)
- 따라서 **계산기류는 25°C 실리콘에서만 정확하다**
- 시뮬레이션 화면에서 온도를 바꾸면 J0들이 n_i(T)에 따라 조정되지만, 이는 **근사이며 엄밀한 처리가 아니다**
- 결함 준위 등 다수 인자를 고려해야 하는 완전한 온도 의존성은 프로그램 범위 밖

---

## 4. 용어 대응표 (Griddler ↔ GEDOS)

| Griddler | GEDOS | 비고 |
|---|---|---|
| Edge Gap | edge margin | 랩미팅 확인 결과 1.0 mm 적용 시 최적 BB 개수가 이동 |
| No of BB / BB width | busbar count / busbar width | 논문 계산에서는 **고정** 파라미터 |
| Finger width / No of fingers | finger width / pitch | 논문 계산에서 **sweep** 대상 |
| Layer sheet resistance | Rs_junction | Griddler PRO 등가 default는 5000 Ω/sq (10k Ω/sq 두 층의 병렬) |
| Metal sheet resistance | ρ_L 기반 환산 | `ρ_sheet = ρ_bulk / t` 또는 `R_line × w_line` |
| Solder/Probe Points | — | busbar당 접점 개수. 미대응 여부 확인 필요 |
| Single / Dual print | — | 미대응 여부 확인 필요. **busbar가 반도체와 접촉하는지 여부**를 결정하므로 contact 손실 계산에 직접 영향 |

---

## 5. 감사(audit) 시 특히 확인할 것

1. **§2.8 FF drops waterfall** — 존재 여부뿐 아니라 위 6단계 순서와 **두 가지 귀속 규칙**(잔차 전부를 직렬 저항에 귀속 / 성분별 비율은 MPP 전력 소산 비율과 동일 가정)이 실제 로직에 반영되어 있는지
2. **§2.7 Metal Optical Transparency** — physical width와 optical width가 실제로 **분리되어** shading과 contact area에 각각 다르게 들어가는지, 아니면 단일 폭으로 통합되어 있는지
3. **§2.4 Print method** — busbar가 반도체와 접촉하는지 여부가 모델링되어 있는지
4. **§2.5 mesh 밀도 기준** — busbar 간 finger당 4노드 / finger 간 4노드 기준을 만족하는지, 자동 검사가 있는지
5. **§7 Tandem** — non-overlapping area의 bottom cell Jsc 별도 입력이 있는지
6. **§5.1 / §5.2** — 다중 파라미터 동시 sweep과 결과 누적 저장이 baseline 대비 roadmap 형태로 출력 가능한지

각 항목에 대해 **파일:라인 근거**와 함께 `완전구현 / 부분구현 / 미구현`을 판정하고, 부분구현이면 빠진 부분을 명시할 것.
