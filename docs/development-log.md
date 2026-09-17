# Development Log

Circuit Simulation Assistant의
기획, 구현, 실패, 수정 및 검증 과정을 기록한다.

---

## 2026-09-14 — Project Planning

### Problem

LTspice를 사용하는 과정에서 다음과 같은 반복적인 불편을 경험했다.

- 소자를 직접 찾아 배치하고 값을 반복적으로 변경해야 함
- AC / DC / Transient simulation command의 문법과 parameter 순서를 매번 찾아봐야 함
- simulation 이후 원하는 voltage / current를 직접 probe해야 함
- -3 dB bandwidth 등의 값을 graph를 확대하며 직접 찾아야 함
- 여러 조건의 simulation 결과를 직접 비교해야 함
- 결과를 해석하고 report 형태로 다시 정리해야 함

### Initial Idea

초기에는 자연어로 회로 자체를 생성하고
simulation까지 자동화하는 방안도 고려했다.

### Scope Decision

Current mirror, feedback loop 등 실제 전자회로 실습의
복잡한 topology까지 자연어 기반 회로 생성으로 일반화할 경우
프로젝트 범위가 지나치게 커질 수 있다고 판단했다.

따라서 초기 프로젝트에서는

- schematic 작성: 사용자
- simulation 설정 및 실행: 프로그램
- 결과 측정: 프로그램
- 결과 해석: AI + 사용자

로 역할을 분리했다.

### Design Decision

사용자는 simulation을 자연어로 요청한다.

AI가 요청을 구조화한 뒤 바로 실행하지 않고,
사용자가 simulation 조건을 최종 검토하고 승인한 경우에만
LTspice를 실행하도록 설계했다.

### First Milestone

자연어 simulation 요청
→ 구조화된 simulation 조건
→ 사용자 검토 및 승인
→ LTspice 자동 실행
→ 성공 / 실패 확인

### SPEC

SPEC v0.1 작성 완료.

---

## 2026-09-14 — Streamlit-LTspice Integration

### 구현 내용

- `test_ltspice.py`의 성공 방식인 `SpiceEditor(.asc)` → `SimRunner(simulator=LTspice).run_now()`를 Streamlit 실행 버튼에 연결했다.
- 업로드한 파일은 `app.py` 위치를 기준으로 `simulation_input/<run_id>/`에 저장한다. 원본 파일을 직접 실행하거나 수정하지 않고, 저장된 복사본에서만 netlist를 생성한다.
- 결과는 `simulation_output/<run_id>/`에 저장한다. 실행별 폴더로 같은 이름의 업로드 및 과거 결과 덮어쓰기를 방지한다.
- 검토·승인 후 Run Simulation을 눌러야 실행된다. 버튼 비활성화와 별도로 실행 분기에서도 승인 및 입력을 확인한다. 회로·요청이 바뀌면 다시 검토하도록 하고, 조건 변경 및 재분석 시에도 승인을 해제한다.
- 이번 단계에서는 업로드된 `.asc`의 기존 directive만 실행한다. UI의 AC/DC/Transient 조건과 자연어 요청은 아직 적용되지 않으며, 실행 승인 전에 화면에 이 제한을 안내한다.
- 성공 상태와 비어 있지 않은 RAW/LOG 파일을 확인한 뒤 `Simulation completed` 및 두 파일의 절대 경로를 표시한다.
- 실패는 Streamlit 오류 메시지로 처리한다. LTspice 종료 코드, 예외 내용, 생성된 실패 로그가 있으면 경로와 마지막 4,000자를 표시한다.
- 외부 API, LLM 및 simulation directive 자동 생성은 추가하지 않았다. SPEC의 장기 목표는 유지하며, 이번 작업에서는 사용자가 지정한 Phase 2 연동 범위만 구현했다.

### 발생한 오류와 해결 방법

- 기존 코드는 `run_now()`의 반환 경로만으로 성공 메시지를 표시했다. 설치된 spicelib 코드를 확인하니 실패해도 경로를 반환할 수 있어, `runner.okSim`과 실제 RAW/LOG 존재 여부 및 크기를 확인하도록 수정했다.
- 실제 실패 실행에서 PyLTSpice가 `.log`를 `.fail`로 변경함을 확인했다. 고정된 `.log` 이름을 가정하지 않고 반환된 실패 로그 경로를 사용한다.
- 검증 준비 중 `test_ltspice.py`를 기본 CP949로 읽어 `UnicodeDecodeError`가 발생했다. 검증 스크립트에서 UTF-8을 명시해 해결했다.
- AppTest는 비활성 버튼의 강제 클릭을 허용하지 않았다. 비활성 상태는 그대로 확인하고, 서버 측 승인 검증은 테스트에서 버튼 이벤트만 주입하여 별도로 확인했다. 승인하지 않은 상태에서는 SpiceEditor와 SimRunner 모두 호출되지 않았다.
- 이전 오류 수정 작업에서 확인한 Python 설치 경로의 샌드박스 접근 제한 때문에, 승인된 프로젝트 가상환경 Python 실행 권한을 사용했다.

### 실제 검증 결과

환경: Python 3.13.5, Streamlit 1.63.0, PyLTSpice 6.0.1, spicelib 1.6.3, LTspice 26.0.1 (Windows).

1. `.\.venv\Scripts\python.exe -m py_compile app.py` — 통과.
2. 실제 `python -m streamlit run app.py` 서버를 로컬 임시 포트에서 실행 — `/_stcore/health`의 `200 / ok` 및 홈페이지 HTTP 200 확인 후 검증 서버 종료.
3. `.\.venv\Scripts\python.exe -u tests/verify_integration.py --real-ltspice` — 종료 코드 0.
   - Streamlit AppTest의 실제 파일 업로드 위젯으로 파일을 전달하고, Analyze Request → 승인 체크 → Run Simulation 순서로 실행했다. 성공·실패 실행에서는 PyLTSpice와 LTspice를 mock하지 않았다.
   - 초기 화면, 파일 미업로드 안내, 미승인 실행 차단, 승인만으로 실행되지 않음, 회로·요청·조건 변경 시 승인 해제를 확인했다.
   - `test_ltspice.py`의 `ASC_FILE`에 지정된 `Draft3.asc`를 읽어 업로드했다. 해당 스크립트를 원본 경로에서 직접 실행하지 않았다.
   - 실제 시뮬레이션 성공 및 화면의 `Simulation completed`, RAW/LOG 경로 표시 확인.
   - 원본 `.asc`와 프로젝트에 저장된 복사본의 바이트 내용 일치 및 실행 후 원본 보존 확인.
   - UI는 AC를 선택했지만 생성된 netlist에는 기존 `.tran 1m`이 유지되고 `.ac`가 추가되지 않았음을 확인했다.

성공 실행 증빙:

- 복사본: `simulation_input/7066714f8d20401ab7046e21ebb0f000/Draft3.asc`
- RAW: `simulation_output/7066714f8d20401ab7046e21ebb0f000/Draft3_1.raw` — 51,168 bytes.
- LOG: `simulation_output/7066714f8d20401ab7046e21ebb0f000/Draft3_1.log` — 528 bytes.
- 같은 출력 폴더에 netlist와 operating-point RAW도 생성됨.

실패 처리 증빙:

- 원본은 그대로 두고 업로드 데이터의 `FQB55N10`만 `MODEL_MISSING_FOR_VERIFICATION`으로 바꿔 실행했다.
- 실제 LTspice 종료 코드 1 및 `Node or model name expected.` 오류 확인.
- `simulation_output/12ed80c55c7440b3927286fcaba336bc/missing_model_1.fail` 생성 확인.
- 성공 메시지가 표시되지 않고 오류 내용이 표시되며, AppTest에서 처리되지 않은 앱 예외가 없음을 확인했다. 의도한 실패 시나리오 검증은 통과했다.

### 다음 단계 / TODO

- 검토·승인한 AC/DC/Transient 조건을 복사본의 simulation directive에 반영하고 입력값을 검증한다.
- 상대 경로의 외부 모델·include 파일을 참조하는 회로에 대한 업로드 및 경로 처리 범위를 정한다. 이번 검증은 LTspice 설치 환경에서 사용 가능한 모델을 쓰는 기존 성공 회로로 수행했다.
- 이후 계획에 따라 자연어 조건 구조화, 결과 측정 및 분석을 구현한다. 이번 작업만으로 전체 First Milestone이 완료된 것은 아니다.

---

## 2026-09-14 — AC Directive Generation

### 구현 내용

- `ac_analysis.py`에 AC 요청 parser, 주파수 단위 변환/검증, `.ac` directive 생성 및 schematic directive 편집을 분리했다.
- Analyze Request 시 추출한 값을 명시적인 Streamlit widget key에 저장한다. Review 화면에서 analysis, target, sweep, points, start/stop, measurements를 직접 수정할 수 있다. Points 기본값은 100이며 Decade/Octave는 구간당 점 수, Linear는 전체 점 수다.
- 현재 UI 값으로 `.ac` 미리보기를 표시하고, 조건 변경 시 승인을 해제한다. 미리보기 생성은 문자열 계산만 하며 파일이나 LTspice를 건드리지 않는다.
- 승인 후 Run Simulation에서만 실행용 복사본을 만들고, 승인한 UI 조건을 다시 검증하여 `.ac`를 적용한다. `run_ltspice()` 함수 자체에도 승인 검사를 추가했다.
- `AscEditor`로 `simulation_input/<run_id>/*.asc` 복사본을 읽고 `remove_Xinstruction()`, `add_instruction()`, `save_netlist()`를 사용한다. 기존 `.ac`, `.dc`, `.tran`, `.op`, `.noise`, `.tf`, `.four`를 제거하여 하나의 AC analysis만 실행한다.
- 같은 schematic TEXT 블록에 여러 directive가 있는 경우 AscEditor의 구조화된 directive 객체에서 analysis 줄만 제거한다. 이 예외 처리는 `.param` 등 같은 블록의 다른 명령을 보존하기 위한 것이며, 원본 `.asc` 텍스트 전체를 문자열 치환하지 않는다. 주석과 회로 구성도 보존한다.
- 편집한 복사본을 기존 `SpiceEditor` → `SimRunner.run_now()` 경로로 실행한다. 성공 후 RAW/LOG 경로와 실제 적용 directive를 표시한다.
- 비-AC 선택 시에는 이전과 같이 회로에 저장된 directive를 실행한다. DC/Transient 조건 생성 기능은 확장하지 않았다.
- Target/Measurements는 추출·검토할 요청 정보로 유지하며, `.save` 제한이나 Gain/Bandwidth 계산을 추가하지 않았다. LLM 및 외부 API도 추가하지 않았다.

### Parser 방식

- 정규식과 규칙만 사용한다. AC/.ac/교류 표시, `V(...)` 또는 `I(...)`, Gain/이득, Bandwidth/대역폭, Phase/위상 등을 추출한다.
- `10 Hz부터 1 MHz`, `from 10Hz to 1MHz`, `10 Hz ~ 1 MHz` 형태의 범위를 지원한다. Hz/kHz/MHz/GHz와 소수·지수 표기를 처리한다.
- 주파수 범위를 해석하지 못하면 빈칸으로 표시하고 사용자 입력을 요구한다. 고정된 100 MHz로 묵시적으로 실행하지 않는다. Target 생략 시 V(out)을 기본값으로 사용한다는 안내를 표시한다.
- 단위 계산은 Decimal로 수행하며 MHz는 LTspice의 `Meg`로 출력한다. 예: `1 MHz` → `1Meg`.
- 양수 주파수, start < stop, 정수 Points를 검증한다. 잘못된 입력은 미리보기 오류로 표시하고 승인/실행을 차단한다.

### 발생한 문제와 해결 방법

- 원래 Review 입력칸은 parser 결과와 연결되지 않아 요청의 1 MHz 대신 100 MHz를 표시했다. Analyze Request마다 parser 결과를 widget 상태에 반영하도록 변경했다. 재분석 시 이전 입력값이 남는 것도 방지했다.
- 단순히 `.ac`를 추가하면 기존 `.tran` 및 여러 analysis가 남을 수 있다. 설치된 AscEditor의 `add_instruction()`이 첫 번째 기존 analysis만 대체함을 확인하여, 충돌하는 analysis를 먼저 모두 제거하도록 했다. 혼합 TEXT 블록의 `.param`과 주석 보존도 테스트했다.
- 첫 실제 AC 실행은 성공했으나 테스트의 `RawRead.get_axis()`에서 축이 없다는 오류가 발생했다. 파일 헤더에는 AC Analysis와 frequency trace가 정상적으로 존재했다. 설치된 spicelib의 지연 로딩 동작을 조사하고 `get_trace("frequency").get_wave().real`로 frequency를 명시적으로 로딩하여 검증을 통과시켰다. 앱에 측정 기능을 추가한 것은 아니다.

### 실제 검증 결과

- `.\.venv\Scripts\python.exe -m py_compile app.py ac_analysis.py` — 통과.
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_ac_analysis.py -v` — 6개 테스트 통과. 한국어/영어 parser, 누락된 범위, 단위 변환, 잘못된 조건, 복수 analysis 제거와 비-analysis 명령 보존을 검증했다.
- `.\.venv\Scripts\python.exe -u tests/verify_integration.py --real-ltspice` — 종료 코드 0. 실제 Streamlit AppTest 파일 업로드와 승인 버튼을 거쳐 아래 시뮬레이션들을 실행했다.
- 별도 임시 포트에서 실제 Streamlit 서버 실행 — health `200 / ok`, 홈페이지 HTTP 200. 검증 서버만 종료했고 기존 서버는 건드리지 않았다.

요청 문장:

> V(out)을 10 Hz부터 1 MHz까지 AC simulation하고 gain과 -3 dB bandwidth를 구해줘

결과:

- UI: AC, Start 10 Hz, Stop 1 MHz, Target V(out), Gain/-3 dB Bandwidth, Points 100.
- 미리보기 및 실제 적용 directive: `.ac dec 100 10 1Meg`.
- 복사본: `simulation_input/7f909dfb9d424893a6ff6aef0fd95979/Draft3.asc` — 기존 `.tran` 대신 승인한 `.ac` 저장 확인.
- RAW: `simulation_output/7f909dfb9d424893a6ff6aef0fd95979/Draft3_1.raw` — 89,348 bytes.
- LOG: `simulation_output/7f909dfb9d424893a6ff6aef0fd95979/Draft3_1.log` — 528 bytes.
- RAW Plotname = AC Analysis, frequency 시작 10 Hz, 끝 1,000,000 Hz, 총 501개 지점. 100 MHz가 아님을 실제 RAW로 확인했다.
- 원본 `test_ltspice.py`의 ASC_FILE은 실행 전후 바이트 내용이 동일하다. 복사본만 analysis directive가 변경됐다.

추가 실제 검증:

- 화면에서 Stop=2 MHz, Points=20으로 수정하고 다시 승인 — `.ac dec 20 10 2Meg` 적용 및 RAW 끝 주파수 2,000,000 Hz 확인. 결과: `simulation_output/53a06ebe08f64f76b6ea414502d76384/Draft3_1.raw`.
- 기존 비-AC 경로 회귀 검증 — 저장된 `.tran 1m` 실행 성공 및 RAW Transient Analysis 확인. 결과: `simulation_output/68f73e3ef0a8405b84e072e38503db0c/Draft3_1.raw`.
- 잘못된 모델명의 업로드로 실제 AC 실패 유도 — 종료 코드 1, 오류/실패 로그 표시, 앱 crash 및 잘못된 성공 메시지 없음. 로그: `simulation_output/2ab52b25a3dc45e59bd2b4cec28026f9/missing_model_1.fail`.
- 미승인 상태에서 입력 폴더 변화 없음, AscEditor/SpiceEditor/SimRunner 호출 없음 확인. 테스트에서 버튼 이벤트를 주입해도 서버 측 검사로 차단됐다.
- 회로/요청/조건/Points 변경 시 승인 초기화, 재분석 시 새로운 범위 반영, 잘못된 주파수에서 승인 및 실행 차단 확인.

### 남은 TODO

- 단위가 생략된 자연어 범위, 더 다양한 표현 및 모호한/복수 요청 처리 개선. 현재 지원하지 않는 범위는 Review에서 직접 입력해야 한다.
- Target의 실제 trace 존재 여부 검증, 이후 단계의 결과 측정·분석. 이번에 사용한 기존 회로의 노드명은 Vout이며, 요청 예문의 V(out)은 검토 정보로만 보존했다.
- 외부 모델/include 파일을 사용하는 회로의 업로드와 경로 처리.
- DC/Transient 조건 생성, LLM 연동, Gain/-3 dB Bandwidth 계산은 이번 작업 범위에서 제외했다.

---

## 2026-09-14 — AC Result Analysis

### 구현 내용

- `ac_result_analysis.py`를 추가하여 RAW 읽기, trace 검증, complex transfer function, Gain, 저주파 Gain, -3 dB bandwidth 및 Matplotlib 그래프를 분리했다. 정량 계산에는 Python/NumPy만 사용한다.
- Review 화면에 `Target Signal`, `Reference / Input Signal`을 제공한다. Reference는 임의의 회로 이름이나 AC 1 V를 가정하지 않고 사용자가 직접 입력한다. Reference 변경 시 승인이 해제되며 빈 Target/Reference로는 승인할 수 없다.
- `PyLTSpice.RawRead`로 AC RAW의 frequency 및 두 complex voltage trace를 명시적으로 로딩한다. 기존에 확인한 지연 로딩 특성 때문에 `get_trace(...).get_wave()`를 사용한다.
- trace 이름은 앞뒤 공백 제거와 대소문자 정규화만 허용하며 유사 이름을 추정하지 않는다. 없는 이름은 그대로 오류에 표시하고 사용 가능한 전체 RAW trace 목록을 제공한다. 전압 이득이므로 두 신호 모두 voltage trace여야 한다.
- 성공 후 Measured Results에 저주파 Gain, -3 dB Level, -3 dB Bandwidth를 표시한다. Gain-Frequency 그래프는 log-frequency 축, Gain curve, threshold 수평선 및 crossing 표시를 포함한다.
- 시뮬레이션 성공과 결과 분석 실패를 구분한다. RAW/LOG가 생성됐지만 trace가 없는 경우에도 Simulation completed와 파일 경로는 유지되고, 분석 오류만 표시한다.
- 원본 보존, 승인 후 복사본 편집, 실제 AC directive, 실패 처리 및 기존 비-AC 실행 경로를 유지했다. LLM/API, DC/Transient 분석, report, screenshot automation, parameter sweep은 추가하지 않았다.

### Gain 계산 정의

각 주파수에서 `H(f) = V_target(f) / V_reference(f)`를 complex 값으로 계산한다.
`Gain_dB(f) = 20 * log10(abs(H(f)))`를 적용한다. Reference가 1 V라는 가정은 없다.

- Reference 크기가 0이거나 유효 Reference 최대 크기의 `1e-12` 이하인 샘플은 제외한다. 이 기준은 Reference 전체 크기를 바꿔도 동일한 상대 기준이다.
- non-finite 입력/출력, 나눗셈 overflow, magnitude=0은 유효한 유한 dB 값으로 사용할 수 없으므로 NaN으로 표시한다. 그래프에서 해당 지점은 공백이 되고 제외 개수를 안내한다.
- frequency는 양수·유한값·엄격한 증가 순서여야 한다. 길이가 다르거나 샘플 수가 3개 미만이면 분석 오류로 처리한다.

### Low-frequency gain 결정 방식

- 최초 `min(10, 전체 샘플 수)`개 주파수 구간 안에서 유효한 Gain[dB] 샘플의 median을 G0로 사용한다.
- 최소 3개의 유효 샘플이 있어야 한다. 처음부터 데이터가 잘못된 경우 더 높은 주파수의 샘플로 조용히 대체하지 않는다.
- 실제 사용한 샘플 수와 초기 주파수 범위를 화면에 표시한다. 초기 Gain 범위가 0.5 dB보다 넓으면 평탄한 passband가 아닐 가능성을 안내한다.
- 이번 실제 회로에서는 처음 10개 샘플, 약 10–12.303 Hz 구간을 사용했다.

### -3 dB bandwidth와 interpolation

- Threshold는 `G0 - 3.0 dB`로 정의한다.
- 주파수가 증가하면서 threshold를 처음 아래 방향으로 통과하는 인접한 유효 샘플을 찾는다. 정확히 threshold에 도달하는 샘플도 crossing으로 처리한다.
- 두 지점 `(f1, g1)`, `(f2, g2)` 사이에서는 `a = (Threshold - g1) / (g2 - g1)`로 놓고 `log10(f_bw) = log10(f1) + a * (log10(f2) - log10(f1))`로 보간한다.
- 유효한 sweep에서 crossing이 없으면 `Not found within sweep range`를 표시한다. sweep 밖의 값을 외삽하지 않는다.
- invalid sample을 건너뛰어 보간하지 않는다. 앞선 invalid 구간 때문에 첫 crossing을 확정할 수 없거나 시작점이 threshold보다 이미 낮으면 `Cannot determine...` 상태를 표시하고 수치를 만들지 않는다.
- G0보다 1 dB 이상 peaking하면 안내를 표시한다. 계산 기준은 계속 초기 baseline에 대한 첫 downward crossing이며 low-pass response를 우선 가정한다.

### 발생한 오류와 해결 방법

- 기존 integration test는 요청/업로드 변경 후 바로 승인하는 순서였다. 새 필수 Reference 입력이 비워진 상태에서 AppTest가 비활성 승인 checkbox 클릭을 거절했다. Reference 미입력 시 차단을 검증한 후 Reference를 다시 입력하도록 테스트를 수정했고 재실행을 통과했다.
- 실제 회로에 없는 Target/Reference를 요청한 실행에서는 RAW 생성 성공 이후 `MissingTraceError`로 검출했다. 임의 보정 없이 누락 이름과 전체 목록을 화면에 표시하고 앱이 계속 실행됨을 확인했다.
- 잘못된 모델을 넣은 기존 실제 실패 시나리오도 종료 코드 1과 `.fail` 로그 표시로 정상 처리했다. 결과 분석을 추가한 뒤에도 시뮬레이션 실패를 성공으로 표시하지 않았다.

### 실제 검증 결과

실행 명령:

- `.\.venv\Scripts\python.exe -m py_compile app.py ac_result_analysis.py tests/verify_integration.py` — 통과.
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py' -v` — 14개 테스트 통과(기존 6개 + 결과 분석 8개).
- `.\.venv\Scripts\python.exe -u tests/verify_integration.py --real-ltspice` — 최종 종료 코드 0.
- 별도 임시 Streamlit 서버의 health `200 / ok` 및 홈페이지 HTTP 200 확인. 검증 서버만 종료했다.

계산 검증:

- Synthetic: `H(f)=4/(1+j*f/1000)`에 1 V가 아니고 주파수에 따라 크기와 위상이 변하는 Reference를 곱해 Target을 만들었다. 복원된 complex H가 이론값과 일치했다.
- Synthetic 저주파 Gain: 12.041199826 dB. 이론적 정확한 -3.000 dB 주파수는 997.628345111 Hz, 계산값은 997.603603208 Hz, 상대 오차 약 0.00248007%. 1차 pole 주파수의 -3.0103 dB와 정확한 -3 dB의 차이를 테스트에 반영했다.
- 첫 샘플에 큰 outlier가 있어도 median baseline이 유지됨을 확인했다.
- sweep 내 crossing이 없는 응답은 bandwidth=None과 `Not found within sweep range`를 반환했다.
- peaking, zero/near-zero Reference, NaN/Inf, zero Target, invalid gap, 잘못된 frequency 및 부족한 데이터 처리 통과.
- log 보간은 알려진 두 점의 기하평균 crossing과 비교했고, 그래프의 log 축/threshold/BW 표시를 검사했다.

실제 MOSFET 회로 end-to-end:

- `test_ltspice.py`의 원본 `Draft3.asc`를 업로드하고, 자연어 AC 조건을 분석한 뒤 Review에서 Target=`V(vout)`, Reference=`V(vin)`을 입력했다. 이 이름들은 검증 회로의 입력값이며 분석 함수에 하드코딩하지 않았다.
- 승인 후 `.ac dec 100 10 1Meg` 실행 성공, RAW 10–1,000,000 Hz / 501개 샘플.
- Low-Frequency Gain: **38.983432121 dB**.
- -3 dB Level: **35.983432121 dB**.
- -3 dB Bandwidth: **6274.787804816 Hz (6.274787805 kHz)**.
- 별도의 Python scalar complex 연산, `math.log10`, `statistics.median`, natural-log 보간 계산과 비교했다. G0 차이 < 1e-10 dB, BW 상대 차이 < 1e-10으로 일치했다.
- Streamlit의 세 metric이 표시됨을 확인했다. 동일한 결과의 Matplotlib PNG를 저장하고 시각적으로 곡선, log 축, threshold 및 BW 표시를 확인했다.
- 실제 없는 두 trace를 입력한 별도 실행에서는 누락 이름과 사용 가능한 `V(vout)`, `V(vin)` 등을 표시하고 앱 crash가 없었다.
- UI에서 바꾼 `.ac dec 20 10 2Meg` 실제 실행, 기존 저장된 `.tran` 실행, 모델 오류 시 실패 표시, 승인 차단 및 원본 바이트 보존 regression test도 통과했다.

증빙:

- 복사본: `simulation_input/71d6f110b0e44256a761bd739bbe6041/Draft3.asc`.
- RAW: `simulation_output/71d6f110b0e44256a761bd739bbe6041/Draft3_1.raw` — 89,348 bytes.
- LOG: `simulation_output/71d6f110b0e44256a761bd739bbe6041/Draft3_1.log` — 528 bytes.
- 그래프: `simulation_output/71d6f110b0e44256a761bd739bbe6041/gain_frequency.png`.
- Missing trace 실행: `simulation_output/9093c898856946898fadd5eaa6292707/Draft3_1.raw`.
- 모델 오류: `simulation_output/88c96126e424409b848e1981b48dad67/missing_model_1.fail`.

### 현재 계산법의 한계 / 다음 TODO

- 초기 sweep가 평탄한 low-frequency passband에 있어야 한다. 시작 주파수가 너무 높거나 처음 10개 샘플에 roll-off가 포함되면 G0와 bandwidth가 편향될 수 있다. 이후 plateau 선택 및 신뢰도 기준 개선을 검토한다.
- log-frequency 보간 정확도는 sweep 점 간격과 곡률에 의존한다. 서로 다른 해상도에서 결과 수렴을 검토할 수 있다.
- high-pass/band-pass 및 여러 passband를 일반적으로 판정하지 않는다. peaking 안내는 단순 기준이며 응답 형태를 보장하지 않는다.
- zero Target의 -infinity dB 및 매우 작은 Reference는 제외하므로 이런 구간에서는 crossing을 확정하지 않는다.
- 전압 trace의 단일 AC sweep만 분석한다. parameter-stepped RAW는 명시적으로 거절한다.
- 누락 trace의 직접 수정 후 기존 RAW 재분석 및 결과 유지 UX는 향후 개선할 수 있다. 현재는 입력 수정·재승인·실행 경로를 사용한다.
- 외부 모델/include 처리, 나머지 측정 기능은 후속 작업이며 LLM/DC/Transient 분석/report/screenshot automation은 이번 범위에 포함하지 않았다.

---

## 2026-09-15 — Transient Analysis (Prompt 005, 중단 작업 재개)

### 중단 상태와 이어서 수행한 작업

- 재개 시 `app.py`의 Transient 검토/승인/실행/결과 화면, `transient_analysis.py`, `transient_result_analysis.py`, Transient unit/integration tests 및 기존 integration test의 Transient 요청 갱신이 이미 작성되어 있었다. 공통 analysis directive 편집 기능도 `ac_analysis.py`에 구현되어 있었다.
- 디스크 기준 `python -m py_compile app.py`와 기존 unit tests 24개가 통과했다. 확인한 범위에서 syntax error, 미완성 분기 또는 새로 작성해야 할 중복 구현은 없었다. 기존 코드를 유지하고 실제 실행 검증부터 이어갔다.
- 실제 LTspice 검증에서 발견한 RAW 저장 시작 시간 Offset 누락만 결과 읽기 모듈에서 수정했다. 해당 unit test를 추가하고 integration test에서 보정된 시간축을 검증하도록 수정했다.
- 아래 모든 검증을 마친 후 development/prompt log를 작성했다. 이번 재개에서 `app.py`, parser 및 AC 계산 로직을 다시 구현하거나 덮어쓰지 않았다.

### Prompt 005 구현 내용과 parser 방식

- 정규식으로 Transient 여부, Stop Time, 선택적인 Start Saving Time/Maximum Timestep, Target/Reference 및 요청 측정 항목을 추출한다. 시간은 ns/us/µs/μs/ms/s와 영어·한국어 단위 표현을 지원하고 Decimal로 검증/변환한다.
- 예문 `V(out)을 1 ms 동안 transient simulation하고 V(in)과 비교해서 voltage gain과 output swing을 구해줘.`에서 Stop=1 ms, Target=V(out), Reference=V(in), Voltage Gain/Output Swing을 추출한다. `10 us 동안 transient 돌리고 V(out)의 rise time과 overshoot를 구해줘.`도 처리한다.
- 선택 시간이 없으면 빈 필드를 유지한다. Review에서 직접 수정할 수 있고 수정 시 승인이 초기화된다. Stop>0, 0≤Saving Start<Stop, 0<Maximum Timestep≤Stop을 검증한다. Gain 요청 시 Reference가 필수다.
- `.tran 1m`, `.tran 0 2m 1m 1u` 등을 실행 전에 미리 보여준다. 최대 timestep만 지정하면 Tstart 자리에 0을 사용하는데, 이는 directive의 위치 인자이며 UI 기본값을 채우는 것이 아니다.
- 승인 후에만 업로드 바이트를 `simulation_input/<run id>`의 실행용 복사본에 저장한다. PyLTSpice AscEditor의 parsed directive 편집을 사용하여 충돌하는 analysis를 제거하고 `.param` 등은 보존한다. 원본 사용자 ASC에는 쓰지 않는다.
- 실제 LTspice 실행 후 RAW/LOG/적용 directive를 표시한다. `transient_result_analysis.py`에서 PyLTSpice RawRead, NumPy 계산, Matplotlib waveform을 담당한다. 요청된 측정만 표시하며 적용할 수 없는 항목은 이유와 함께 수치 없이 안내한다.
- trace는 공백 정리/대소문자 비교만 허용하고 이름을 추정하지 않는다. 실제 회로의 V(vin)/V(vout)은 Review에서 입력한 값이며 코드의 기본 회로 이름이 아니다. 누락된 trace와 사용 가능한 전체 목록을 표시한다.

### 측정 정의와 유효성 판단

- Output Swing: **저장된 전체 구간**의 Target 최대값, 최소값, max-min. Gain의 정상상태 측정 구간과 다를 수 있다.
- Voltage Gain: 안정된 주기 응답에서 마지막 세 개의 완전한 입력 주기를 공통 구간으로 사용한다. `Input Vpp=max(reference)-min(reference)`, `Output Vpp=max(target)-min(target)`, `Gain=Output Vpp/Input Vpp`, `Gain_dB=20*log10(Gain)`. 구간 경계는 원래 시간축에서 선형 보간한다. 위상/반전 부호는 측정하지 않는 크기 이득이다.
- 주기 판별은 마지막 세 주기의 주기 편차 5% 이하, 주기당 원본 샘플 12개 이상, 위상 정규화한 waveform 변화 8% 이하를 요구한다. 입력/출력 주기가 일치해야 한다. 입력 진폭이 `max(1e-12 V, max(abs(reference))*1e-9)` 이하이거나 나눗셈 결과가 비정상이면 Gain을 만들지 않는다.
- 단일 step은 시간상 균등 보간 후 초기 약 5% 구간 median과 마지막 약 10% 구간 median을 사용한다. 양 끝 plateau 변동은 step 크기의 2% 이하여야 하며, 하나의 지속되는 전이를 요구한다. 짧은 sine 일부, ramp, 평탄한 신호를 step으로 확정하지 않는다.
- Rise/Fall Time: step 또는 충분한 상·하 plateau가 확인된 pulse에서 10→90% / 90→10% crossing 간 시간 차이를 계산한다. **실제 비균등 시간축의 인접 샘플 사이 선형 보간**을 사용한다. 반대 방향의 단일 step에는 해당 항목을 반환하지 않는다.
- Overshoot: 단일 step의 최종 plateau를 넘어선 최대 excursion을 V 및 step 크기에 대한 %로 계산한다. 상승/하강 step의 방향을 정규화한다. 반복 sine 또는 안정된 최종값이 없는 pulse에는 반환하지 않는다.
- Settling Time: 최종값 ±2% **step 크기**의 band로 마지막 진입하는 시점을 선형 보간한다. 함수 인자 `settling_tolerance`로 5% 등도 지정할 수 있다. 시간 원점은 RAW에서 검출한 **1% 전이 onset**이며, 소스 명령의 정확한 step 시점과 구분하여 화면에 명시한다. 마지막 진입 후 전체 저장 길이의 10% 이상 관측되어야 한다. 원래의 step 이전 구간이나 충분한 최종 plateau가 없으면 계산하지 않는다.
- NaN/Inf, 길이 불일치, 잘못된 시간축/invalid gap은 분석 오류로 처리한다. 전압 trace의 단일 Transient만 지원하며 parameter-stepped RAW는 거절한다. 시뮬레이션 성공과 분석 실패를 구분하고 앱 전체는 유지한다.
- 그래프는 Target/Reference 전압과 Time[s]를 표시하고 유효한 측정에만 crossing/peak/settling marker 및 band를 추가한다.

### 발생한 오류와 해결 방법

- 첫 실제 추가 검증 `.tran 0 2m 1m 1u`에서 integration test의 예상 시간 1–2 ms와 PyLTSpice가 반환한 0–1 ms가 달라 assertion이 실패했다. netlist에는 승인된 directive가 정확히 적용되어 있었다.
- RAW header를 직접 확인하니 `Offset: 1.0000000000000000e-03`과 상대 시간 0–1 ms가 저장되어 있었다. 설치된 RawRead/Axis 코드는 compression의 음수 시간을 보정하지만 header Offset을 더하지 않았다. [PyLTSpice RAW 형식 문서](https://pyltspice.readthedocs.io/en/latest/_modules/spicelib/raw/raw_read.html)도 Offset을 저장 시작 시간으로 설명한다.
- `read_transient_result`에서 header Offset을 시간축에 더하도록 수정했다. Offset 미존재 시 0을 사용하고 NaN/음수는 거절한다. UI 그래프, 측정 구간, marker가 동일한 절대 시간축을 사용한다. 재실행에서 1–2 ms 및 정상 Gain 계산을 확인했다.
- 디버그 출력 과정의 Windows native command 따옴표 전달 오류는 명령을 바로잡아 해결했다. 앱 syntax error와는 무관하다. 콘솔의 Unicode 출력은 `-X utf8`로 실행했다.

### 실제 수행한 검증 결과

아래 명령은 프로젝트 `.venv`의 Python으로 실행했다.

- `python -m py_compile app.py` — 통과. 수정 후 parser/결과 모듈 및 integration/unit test 파일까지 추가 문법 검사 통과.
- `python -X utf8 -m unittest discover -s tests -p test_*.py -v` — **25개 모두 통과: Transient 11개, 기존 AC 14개**.
- `python -X utf8 -u tests/verify_transient_integration.py --real-ltspice` — 수정 후 **종료 코드 0**. 자연어→검토/수정→승인→directive→LTspice→RAW→측정→화면을 Streamlit AppTest로 실제 수행.
- `.tran 1m` 실제 실행 성공, RAW 51,168 bytes, LOG 528 bytes. 화면의 7개 metric 및 waveform 생성 확인. PNG를 저장하고 두 신호/축/범례를 시각 확인했다.
- `.tran 0 2m 1m 1u` 실제 실행 성공, 보정한 저장 시간 0.001–0.002 s 확인. 실제 sine 응답에서 Rise/Fall/Overshoot/Settling을 요청해 모두 수치 없이 적용 불가 안내가 나오는지 확인했다.
- 없는 Target `V(missing)`으로 실제 재실행: Simulation completed와 RAW/LOG를 유지하고 누락 이름/사용 가능 목록을 표시했다. 앱 crash 없음.
- 승인 전 버튼 이벤트를 강제로 주입해도 편집기/runner 호출과 입력 파일 생성이 없었다. 조건 변경 시 승인 초기화 및 잘못된 시간 차단도 통과했다. 실제 원본 ASC는 모든 실행 전후 바이트가 동일했다.
- `python -X utf8 -u tests/verify_integration.py --real-ltspice` — **종료 코드 0**. 기존 AC 1 MHz/수정 2 MHz 실제 실행, missing trace, 승인·원본 보존, Transient 경로 및 잘못된 모델로 유도한 실제 LTspice 실패 처리가 모두 통과했다. 모델 오류는 예상한 음성 테스트이며 앱 실패가 아니다.
- 별도 headless Streamlit 서버를 임시 port 64897에 실행했다. `/_stcore/health` HTTP 200/ok 및 홈페이지 HTTP 200 확인 후 검증 서버만 종료했다.

### Synthetic 계산 검증

| 검증 | 계산값 | 이론값 / 판정 |
| --- | --- | --- |
| 1차 step, tau=0.04 s, Rise/Fall | 각각 0.087888971564 s | tau·ln(9)=0.087888983093 s; 오차 <1 µs |
| 2차 step, damping=0.25, wn=80 | Overshoot 44.434171077% | 44.434422509%; 오차 <0.001 percentage point |
| 1차 step, 2% settling, 1% onset 기준 | 0.156078922454 s | tau·ln(0.99/0.02)=0.156078906783 s; 오차 <2 µs |
| 5% settling | 허용 오차 내 일치 | 변경 가능한 tolerance 검증 통과 |
| DC offset 포함 반전 sine | Input 0.4 Vpp, Output 1.2 Vpp, Gain 3 V/V | 20·log10(3) dB와 일치 |
| 단일 trapezoid pulse | Rise/Fall 각각 0.016 s | 이론값과 일치; Overshoot 적용 불가 |
| sine, half sine, ramp, flat, missing/flat reference, NaN | 부적절한 측정값 없음 | 이유 표시 또는 분석 오류; 잘못된 0/무한대 결과 없음 |
| RAW Offset | 상대→절대 시간 보정 | 누락/양수 및 비정상 Offset 회귀 테스트 통과 |

### 실제 MOSFET Transient 측정 결과

`test_ltspice.py`의 기존 Draft3.asc(FQB55N10 MOSFET, 입력 SINE(3.55 10m 10k))를 읽어서 업로드했다. 사용자의 원본 회로 소자/입력 소스는 변경하지 않았다. Review에서 Target=V(vout), Reference=V(vin)을 지정했다.

`.tran 1m` 결과:

| 항목 | 계산 결과 |
| --- | --- |
| 정상상태 측정 구간 | 약 0.699998683–0.999998651 ms, 마지막 완전한 3주기 |
| Input Vpp | **0.019999742508 V** |
| Output Vpp | **0.949819087982 V** |
| Voltage Gain | **47.491565834178 V/V** |
| Voltage Gain (dB) | **33.532329776956 dB** |
| 전체 저장 구간 Output Maximum | 5.784930706024 V |
| 전체 저장 구간 Output Minimum | 4.760293006897 V |
| 전체 저장 구간 Output Swing | 1.024637699127 Vpp |

별도로 알려진 입력 10 kHz의 마지막 0.3 ms에서 Python max/min으로 계산한 Vpp 비율과 비교하여 상대 차이 0.1% 이내를 확인했다. 전체 구간 Output Swing에는 초기 응답이 포함되므로 정상상태 Output Vpp와 다르다. 이 Transient gain은 해당 입력 주파수/진폭의 Vpp 비율이고 AC의 저주파 소신호 gain과 같은 지표가 아니다.

기존 AC 회귀 결과: `.ac dec 100 10 1Meg`, 501 samples, G0=**38.983432121 dB**, threshold=35.983432121 dB, BW=**6274.787804816 Hz**. 별도 scalar complex/math 계산과 G0 오차 <1e-10 dB, BW 상대 오차 <1e-10으로 일치했다.

증빙:

- 기본 Transient 복사본: `simulation_input/01dd08c2c94b43248c9175fe3cc3200b/Draft3.asc`.
- 기본 RAW/LOG: `simulation_output/01dd08c2c94b43248c9175fe3cc3200b/Draft3_1.raw`, `Draft3_1.log`.
- waveform: `simulation_output/01dd08c2c94b43248c9175fe3cc3200b/transient_waveform.png`.
- Optional 시간 검증: `simulation_output/aa5172c83fc84eb0b7b6e58d78c299ef/Draft3_1.raw`.
- Transient missing trace: `simulation_output/14f8a4e501b24124a812effe4c7033ae/Draft3_1.raw`.
- AC 회귀: `simulation_output/0ca1ef607838400a83f6a121c80d30e3/Draft3_1.raw`, `gain_frequency.png`.
- 의도한 모델 오류: `simulation_output/43739afcf85046c2a01e6cb2262f73f1/missing_model_1.fail`.

### 한계와 다음 TODO

- 현재 step/pulse/주기 판단은 보수적인 규칙이다. arbitrary waveform의 일반적인 의미를 판정하지 않는다. 짧은 기록, 매우 좁은 pulse, plateau가 없는 응답에는 값이 나오지 않을 수 있다.
- Rise/Fall/Settling은 적절한 저장 구간과 timestep에 의존한다. 소스의 정확한 전이 시점 대신 1% 검출 onset을 쓰는 settling 정의를 유지하며, 충분한 관측 이후의 미래 안정성을 보장하지 않는다.
- 후속 검증에서 서로 다른 timestep/관측 길이에 대한 수렴성, 실제 step/pulse 회로 및 더 다양한 noisy waveform을 추가할 수 있다. 이번 실제 회로는 sine이므로 edge/settling 수치는 synthetic으로 검증했고 실제 sine에는 반환하지 않았다.
- parser는 첫 번째 명시 신호를 Target, 다음 신호를 Reference로 해석한다. 복잡하거나 모호한 표현은 Review에서 수정해야 한다. 일반적인 자연어 이해로 확장하지 않았다.
- 외부 모델/include 업로드와 경로 관리, 기존 RAW 재분석/결과 유지 UX는 기존 후속 TODO로 남긴다.
- 이번 scope의 필수 검증은 완료했다. LLM/API, DC 확장, parameter sweep, AI insight, Word report 및 screenshot automation은 추가하지 않았다.

---

## 2026-09-15 — DC Sweep Analysis (Prompt 006)

### 구현 내용

- `dc_analysis.py` 추가: DC 요청 판별, 정규식 parser, 전압/전류 단위 변환, sweep 조건 검증, `.dc` 생성 및 sweep source 존재 검증을 분리했다.
- `dc_result_analysis.py` 추가: PyLTSpice DC RAW 읽기, 정확한 trace 검증, Min/Max, 지정 지점 값, signed/absolute difference, Matching Error, Matplotlib 그래프를 구현했다. 정량 계산은 Python/NumPy만 사용한다.
- `app.py`에는 DC Review와 결과 표시만 연결했다. Sweep Source, Start/Stop/Step, Target, Optional Comparison, Measurements 및 Selected Sweep Point를 직접 수정할 수 있다. 수정하면 승인이 해제된다.
- 지정 지점 요청만 있고 sweep 범위가 없는 경우 범위를 추측하지 않는다. Review에서 Start/Stop/Step을 입력해야 승인할 수 있다. 측정 요청 없이 curve만 요청하면 Minimum/Maximum을 기본 선택으로 표시하고 직접 변경할 수 있다.
- 성공 시 Simulation completed, 실제 `.dc`, RAW/LOG, 요청한 metric, 비교 table 및 graph를 표시한다. Difference/Matching Error는 전체 sweep의 curve와 유효 구간 Min/Max로 제공하며 table에서 각 sweep 지점의 값을 확인할 수 있다.
- 기존 AC/Transient parser와 계산 모듈은 수정하지 않았다. `run_ltspice`에 DC 조건을 추가하고 동시에 둘 이상의 analysis 조건을 전달하면 거절한다. 기존 승인 검사, 실행별 복사본, 공통 AscEditor 편집 및 시뮬레이션 실패 처리 경로를 재사용했다.

### Parser / directive / sweep source

- 명시적인 DC/직류 또는 source를 포함한 sweep 요청을 판별한다. 명시적 AC 요청은 source 이름이 포함되어도 기존 AC parser로 보낸다.
- 예문 `V1을 0 V부터 5 V까지 10 mV 간격으로 sweep하고 V(out)을 보여줘.`에서 DC Sweep, V1, 0 V, 5 V, 10 mV, V(out)을 추출한다.
- 두 current 이름이 있으면 첫 신호가 Target, 두 번째가 Comparison이다. `차이`/`difference`, `absolute difference`/`절대 차이`, `matching error`, Min/Max 및 `V1 = 3 V` 형식의 지점 요청을 해석한다. 실제 MOS RAW 이름인 Id(M1)/Id(M2)도 parser에서 보존한다.
- 독립 전압원 V... 또는 전류원 I... 하나만 지원한다. V source 값에는 V, I source 값에는 A 단위를 사용한다. p/n/u/µ/μ/m/k/M/Meg/G 배율과 단위 없는 기본 V/A 숫자를 처리한다. 대문자 M은 SI mega로 읽고 LTspice에는 반드시 Meg로 출력한다.
- Start<Stop, Step>0, Step≤범위 및 float에서 구별 가능한 increment를 검증한다. 음수 시작값은 지원한다. descending, 동일 Start/Stop, 0/음수 Step, 비정상 수치, 단위 불일치, source에 명령문 삽입 등은 실행 전에 차단한다.
- `V1, 0 V, 5 V, 10 mV` → **`.dc V1 0 5 10m`**. 전류원 예시는 **`.dc I1 0 1m 10u`**. UI의 선택 지점은 측정 조건이며 `.dc` 범위를 조용히 변경하지 않는다.
- directive 문자열을 미리 보여주지만 파일 편집과 netlist 생성/시뮬레이션은 승인 후에만 수행한다. `simulation_input/<run id>`의 복사본에 공통 `apply_analysis_directive`를 적용하여 기존 `.ac/.tran/.dc/.op` 등의 충돌을 제거하고 model/param 등은 보존한다.
- 승인 후 생성한 SpiceEditor netlist의 `get_components("VI")`로 source 이름을 확인한다. 없는 source는 입력 이름과 사용 가능한 독립 source 목록을 표시하고 `run_now`를 호출하지 않는다. netlist 생성 자체도 LTspice를 호출하므로 승인 검사 뒤에 둔다. [PyLTSpice editor API](https://pyltspice.readthedocs.io/en/latest/classes/spice_editor.html)와 [공식 LTspice schematic reference](https://analogdevicesinc.github.io/ltspice-reference/ai_ref/SCHEMATIC-REFERENCE.html)를 확인했다.

### RAW 읽기와 계산 정의

- Plotname이 `DC transfer characteristic`인지 확인한다. 첫 RAW trace를 sweep axis로 읽고 Target/Comparison을 명시적으로 로딩한다. axis label은 승인된 source 이름과 V/A 단위를 사용한다.
- RAW trace 이름은 앞뒤 공백과 대소문자만 정규화한다. `I(M1)`을 임의로 `Id(M1)`으로 대체하지 않는다. 실제 없는 trace는 누락 이름 및 RAW 전체 목록을 표시하고 앱은 유지한다.
- 단일 real-valued sweep의 최소 2개 샘플, 같은 배열 길이, finite 값, 엄격히 증가하는 x를 요구한다. parameter-stepped, descending/nested axis와 invalid gap은 거절한다.
- **Minimum / Maximum**: 저장된 Target curve 전체의 min/max이며 부호를 보존한다.
- **Value at Sweep Point**: 인접한 두 저장 샘플 사이에서 x축에 대해 선형 보간한다. 예: x=[0,1,3,5], y=2x+1의 x=2에서 5. sweep 밖으로 외삽하지 않는다. UI의 nominal 범위 내라도 실제 RAW의 마지막 저장 지점을 넘으면 분석 오류로 표시한다.
- **Difference**: `Target - Comparison`. **Absolute Difference**: `abs(Target - Comparison)`. LTspice current 방향에 따른 부호를 그대로 사용하며 크기만 먼저 비교하는 방식으로 바꾸지 않는다. 두 trace의 물리 단위가 같아야 한다.
- **Matching Error (%)**: `abs(Target - Comparison) / abs(Target) * 100`. **분모는 Target, 즉 첫 번째 trace**이다. Optional Comparison이라는 이름을 보고 분모를 반대로 사용하지 않도록 Review 설명 및 결과 설명에 명시했다.
- 분모 절댓값이 `max(1e-12 [trace unit], max(abs(Target))*1e-9)` 이하면 해당 sample을 계산하지 않는다. 함수의 `denominator_floor` 인자로 절대 기준을 분리했으며 UI는 기본 정의를 사용한다. NaN/overflow 결과는 NaN으로 표시하고 제외 개수를 안내한다. 유효 값이 전혀 없으면 잘못된 0%나 무한대를 metric으로 만들지 않는다.
- Difference와 Matching Error의 Min/Max는 유효 sample만 사용한다. NaN은 table에서 결측값, graph에서는 gap으로 남긴다. 서로 다른 단위의 두 trace는 별도 축 영역에 그릴 수 있지만 차이/Matching Error 계산은 거절한다.
- 그래프는 간단한 선형 sweep 축, Target/Comparison 곡선, 범례와 단위 label을 포함한다. 지정 지점은 marker로 표시하고 차이/Matching Error는 각각 별도 subplot에 표시한다.

### 실제 검증 회로

1. `tests/fixtures/dc_divider.asc`: V1과 직렬 1 kΩ 저항 두 개의 분압기. V(out)=V1/2이며 원본 fixture에는 `.tran 1m`과 `.param fixture=1`이 들어 있어 analysis 교체와 unrelated directive 보존도 확인한다.
2. 위 fixture의 **업로드 바이트만** 전류원 I1 형태로 바꾼 테스트: I1 0–1 mA에서 V(out)=-1000·I1. 파일 원본에는 쓰지 않는다.
3. `tests/fixtures/dc_current_mirror.asc`: M1 diode connection, M1/M2 공통 gate, source/body ground, VDD=5 V, reference 저항 10 kΩ, M2 drain 전압 V1 sweep. 테스트용 LEVEL=1 NMOS 모델(VTO=1, KP=100u, LAMBDA=0.02), 두 소자 모두 L=10u/W=100u를 사용한다. 원본 `.ac`를 실행용 복사본의 `.dc`로 바꾼다. 이 모델은 측정 경로 검증용이며 특정 실제 부품을 대표하지 않는다.

사용자의 기존 MOSFET ASC는 수정하지 않았다. 새 회로는 요청에서 허용한 테스트 전용 fixture이며 앱의 arbitrary circuit generation 기능은 추가하지 않았다.

### 발생한 오류 / 해결 방법

- 첫 unit test에서 `DC sweep I1 from 0 A to 1 mA step 10 uA`의 Step을 1 mA로 잘못 추출했다. `숫자 + step` suffix regex가 Stop과 다음 단어를 함께 읽은 것이 원인이었다. `step/increment + 숫자` 구문을 먼저 해석하도록 수정하고 전체 35개 unit test를 다시 통과했다.
- 전류원 fixture의 첫 실제 실행은 시뮬레이션 자체가 성공했으나 출력이 모두 0이었다. 생성 netlist의 `I1 NC_01 NC_02 0`에서 미연결을 확인했다. 설치된 `current.asy`의 핀은 y=0/80, `voltage.asy`는 y=16/96이므로 심볼 이름만 바꿔서는 연결되지 않았다. 검증 fixture의 전류원 위치를 16만큼 옮기고 `I1 in 0 0` netlist assertion을 추가했다. 재실행에서 이론값 -0.5 V를 확인했다. 앱 수치 계산을 기대값에 맞춰 변경하지 않았다.
- 예문의 MOS 이름 `I(M1)/I(M2)`가 실제 RAW에 없음을 예상한 missing-trace 시나리오로 검증했다. 사용 가능한 `Id(M1)/Id(M2)` 목록을 표시하고, 이 이름을 직접 지정한 정상 검증에서 drain current 비교를 수행했다.
- missing model 회로는 예상대로 실제 LTspice 실패를 일으켰다. 오류/log를 표시하고 성공 메시지나 앱 crash는 없었다.

### 실제 수행한 검증 결과

프로젝트 `.venv` Python으로 실행했다.

- `python -m py_compile app.py` 및 dc modules/unit/integration test 파일 문법 검사 — 통과.
- `python -X utf8 -m unittest discover -s tests -p test_*.py` — **35개 모두 통과: AC 14, Transient 11, DC 10**.
- Synthetic: 비균등 선형 데이터 보간/범위 밖 거절, signed/absolute difference, 음수 전류를 포함한 알려진 10% matching, zero/near-zero 분모, 전부 invalid인 curve, missing trace, 잘못된 x/NaN/Inf/overflow, 단위 불일치 및 graph/marker 확인 — 통과.
- `python -X utf8 -u tests/verify_dc_integration.py --real-ltspice` — fixture 수정 후 **최종 종료 코드 0**. Streamlit AppTest로 자연어→Review→수정/승인→실제 LTspice→RAW→metric/table/graph 경로를 수행했다.
- 미승인 버튼 이벤트를 주입해도 AscEditor/SpiceEditor/SimRunner 호출 및 simulation_input 파일 변화 없음. Source/Step/Comparison/선택 지점 수정 시 승인 해제, 역전 범위 차단 — 통과.
- source가 없는 경우 실제 netlist 검사 후 run_now 차단, 없는 trace의 이름/목록 표시, 실제 모델 오류 처리, 두 fixture 원본 바이트 보존 — 통과.
- `python -X utf8 -u tests/verify_integration.py --real-ltspice` — **종료 코드 0**. AC parser/승인, 1 MHz/수정 2 MHz 실제 실행, 결과 계산, missing trace, 기존 Transient 경로, 원본 보존 및 실제 실패 처리 — 통과.
- `python -X utf8 -u tests/verify_transient_integration.py --real-ltspice` — **종료 코드 0**. `.tran 1m`, `.tran 0 2m 1m 1u`, 저장 시간 Offset 1–2 ms, Vpp Gain, sine의 부적절한 step 측정 거절, missing trace 및 원본 보존 — 통과.
- 별도 headless Streamlit 임시 서버 port 65040: health HTTP 200/ok, 홈페이지 HTTP 200 확인 후 검증 서버만 종료했다. DC 분압 및 mirror PNG를 저장하고 축/곡선/marker/범례를 시각 확인했다.

### 실제 DC 결과

**분압기** — `.dc V1 0 5 10m`, 501 samples, RAW/LOG 생성 성공.

- Sweep: 0–5 V.
- V(out) Minimum=**0 V**, Maximum=**2.5 V**.
- V1=3 V의 V(out)=**1.5 V**. 전체 curve를 V1/2 이론값과 비교하여 절대 허용 오차 1e-6 V 이내 일치.
- UI에서 Start=-1 V, Stop=4 V, Step=100 mV로 수정·재승인한 `.dc V1 -1 4 100m`의 실제 RAW 범위도 -1–4 V로 확인했다.
- 전류원 변형 `.dc I1 0 1m 10u`에서 전체 curve=-1000·I1, I1=500 µA에서 V(out)=**-0.5 V** 확인.

**Current mirror** — `.dc V1 0 5 10m`, Target=Id(M1), Comparison=Id(M2), 501 samples, RAW/LOG 생성 성공.

| V1=3 V에서 | 실제 계산 결과 |
| --- | --- |
| Id(M1), Target/분모 | **321.240600897 µA** |
| Id(M2), Comparison | **328.761205310 µA** |
| Target - Comparison | **-7.520604413 µA** |
| Matching Error | **2.34111267131%** |

전체 sweep의 Difference 범위는 약 -19.926694222–321.240600897 µA, Matching Error 범위는 **0.004647689297–100%**이다. 100%는 V1=0에서 Id(M2)=0이고 분모 Id(M1)는 0이 아닌 실제 sample의 값이다. 특정 동작 구간으로 자동 제한한 결과가 아니다.

별도의 Python scalar `float` 차이와 `abs` 나눗셈으로 전체 current curve를 재계산했다. Difference는 rtol=1e-12/atol=1e-15 A, Matching Error는 rtol=1e-12/atol=1e-12 percentage point 이내로 NumPy 결과와 일치했다.

### AC / Transient 실제 회귀 수치

- AC: G0=**38.983432121 dB**, threshold=35.983432121 dB, BW=**6274.787804816 Hz**. 기존 결과 및 독립 scalar 계산과 일치했다.
- Transient: Input Vpp=**0.019999742508 V**, Output Vpp=**0.949819087982 V**, Gain=**47.491565834178 V/V (33.532329776956 dB)**. 이전 정상상태 결과와 일치했다.

증빙:

- 분압기: `simulation_output/f565408029a3423ebf5dfd9283af5ac7/dc_divider_1.raw`, `dc_divider_1.log`, `dc_sweep.png`.
- 수정 범위: `simulation_output/e870514b2771434e8014aba56771e9ba/dc_divider_1.raw`.
- 전류원: `simulation_output/3545c6b610f44ca4966c6574186a8ba0/dc_current_source_1.raw`.
- Current mirror: `simulation_output/7adea84984e64db2944cb8dc51d709f1/dc_current_mirror_1.raw`, `dc_current_mirror_1.log`, `dc_mirror.png`.
- DC missing trace: `simulation_output/cb9d4a0689eb4f2dad2ab1269c5bddb3/dc_current_mirror_1.raw`.
- 의도한 DC 모델 오류: `simulation_output/89aff9f3c5df4b909ca1d82ae2432932/broken_mirror_1.fail`.
- AC 회귀: `simulation_output/e335c4dd6b664726a8156ca831293473/Draft3_1.raw`.
- Transient 회귀: `simulation_output/0175a425779f42cda09510cfe067ff47/Draft3_1.raw`.
- 각 실행용 ASC 복사본은 동일 run id의 `simulation_input` 폴더에 있다.

### 현재 한계 / 다음 TODO

- 독립 source 하나의 ascending linear DC sweep만 지원한다. descending, nested sweep, 온도/parameter sweep은 이번 범위가 아니며 일반적인 arbitrary circuit generation도 없다.
- Matching Error의 분모는 고정된 Target 정의이다. 다른 정규화 방식이나 current 부호 방향 정렬은 후속 명시적 옵션으로 검토한다. near-zero 기준 이하의 영역에서는 값이 제공되지 않는다.
- 보간은 저장된 sample 사이 선형 근사이므로 nonlinear curve에서는 Step 해상도에 의존한다. 특정 구간 선정/해상도 수렴 검증은 후속 과제다.
- 자연어는 지원한 규칙만 해석한다. 복잡한 요청, 다른 source에 대한 지점 조건, 단위 없는 자연어 범위 등은 Review에서 직접 확인·수정해야 한다. trace alias 추정은 하지 않는다.
- 외부 model/include 경로 관리, 기존 RAW 재분석과 결과 유지 UX는 기존 TODO다.
- Prompt 006의 필수 end-to-end 구현/검증은 완료했다. LLM/API, AI 해석, parameter sweep, Word report, LTspice screenshot automation은 추가하지 않았다.

---

## 2026-09-15 — Parameter Sweep Request Parsing (Prompt 007A)

- `parameter_sweep.py`에 실행 기능 없는 parser/검증을 추가했다. `R1을 1k, 2k, 5k, 10k로 바꿔가며 AC simulation하고 gain과 -3 dB bandwidth를 비교해줘.` 및 `R1을 1k부터 10k까지 1k 간격으로 sweep해줘.`를 구조화한다.
- Sweep Type=Component Value, Component, 목록 또는 Start/Stop/Step, Analysis Type, Measurements를 별도 Review 화면에서 수정한다. 현재 R/C/L + 숫자 형식의 component 이름과 양수 numeric/SPICE suffix 값을 지원한다. 분석 종류가 없으면 Not specified로 표시하고 검토자가 선택해야 승인할 수 있다. AC/Transient/DC 측정 이름 추출은 기존 parser를 재사용한다.
- 기존 실행 함수와 AC/Transient/DC parser는 수정하지 않았다. Parameter Sweep 화면은 독립 state와 승인 checkbox를 사용하고 `st.stop()`으로 기존 Run Simulation 경로 전에 종료한다. 승인하면 `Parameter Sweep execution will be implemented in the next step.` 안내만 표시한다. 조건 수정 시 승인이 해제된다.
- 빈 목록/잘못된 항목, 지원하지 않는 component, 0/음수/비정상 값, 역전 범위 및 잘못된 Step은 승인 불가로 처리한다. 값 목록을 부분적으로 버리거나 범위를 여러 실행으로 확장하지 않는다. SPICE suffix m/M은 milli, Meg는 mega로 명시한다.
- 검증: `python -m py_compile app.py parameter_sweep.py tests/test_parameter_sweep.py` 통과. `python -X utf8 -m unittest discover -s tests -p test_*.py -v` **43개 통과**(기존 35 + parser 6 + Streamlit AppTest 2). 승인/수정/입력 모드 전환, 기존 AC/Transient/DC 검토 화면 복귀, PyLTSpice editor/runner 미호출 및 simulation_input/output 파일 목록 무변경을 확인했다. 실제 LTspice 실행은 수행하지 않았다.
- 다음 TODO: component 존재 여부와 분석별 상세 조건 검토 후, 별도 단계에서 승인된 복사본 변경·실행·결과 비교를 설계한다. 이번에는 실제 component 변경, PyLTSpice sweep, 다중 실행, 비교 분석, LLM/API/AI 해석/report를 구현하지 않았다.

---

## 2026-09-15 — Parameter Sweep Component Validation (Prompt 007A-1)

- `parameter_sweep.py`에 업로드 ASC 바이트의 `SYMBOL`/`SYMATTR InstName`을 메모리에서 읽는 존재 검증을 추가했다. 파일 저장, 외부 symbol 로딩, netlist 생성 또는 LTspice 호출은 없다. 최상위 schematic의 component만 확인하며 comment/text에 적힌 이름은 제외한다. UTF-8/UTF-16 BOM 및 ANSI 파일의 ASCII component 이름을 처리한다.
- Review에서 대소문자와 앞뒤 공백만 정규화하여 정확히 비교한다. 존재하면 `Component found: R1`, 없으면 요청 이름과 확인된 목록을 표시하고 승인을 차단한다. 빈 입력도 차단하며 유사 이름을 대체하지 않는다. 기존 parser/실행 경로는 유지하고, 정상 승인 후에도 기존의 다음 단계 실행 안내만 표시한다.
- `python -m py_compile app.py` 통과. `python -X utf8 -m unittest discover -s tests -p test_parameter_sweep.py -v` **관련 13개 통과**: 존재/누락/대소문자/빈 입력, encoding/comment, 기존 parsing 및 UI 검증. 원본 fixture 바이트와 simulation 폴더 목록 보존, PyLTSpice 미호출을 확인했다. 요청대로 관련 테스트만 수행했다.
- 실제 value 변경, parameter sweep 실행, 비교 분석, LLM/API/report는 추가하지 않았다.

---

## 2026-09-15 — Parameter Sweep Execution & Comparative Analysis (Prompt 007B)

### 구현 및 기존 기능 재사용

- 기존 `parameter_sweep.py` parser/존재 검증과 Review UI를 확장했다. R1뿐 아니라 RD/CL 같은 이름을 처리하며 대소문자만 정규화하고 실제 ASC의 component를 확인한다. 기존 AC/Transient/DC parser 및 결과 계산 모듈은 변경하지 않았다.
- `generate_sweep_values()`는 기존 numeric/SPICE suffix 검증과 Decimal 연산을 사용한다. Explicit Values 순서를 보존하며 range는 Start + n × Step으로 생성한다. Stop에 정확히 도달하면 포함하고, 간격에 맞지 않는 Stop은 임의로 추가하지 않는다. 양수/유한 값, Start < Stop, 유효 Step, 최대 100 points를 검증한다. p/n/u/µ/m/k/Meg 등을 지원하며 M은 milli이다.
- `app.py`는 기존 분석별 상세 조건/trace/measurement UI를 재사용한다. Component/값/분석 조건/directive preview를 검토하고 최종 승인한 뒤 `Run Parameter Sweep`으로 실행한다. 조건·요청·업로드 수정 시 승인이 해제된다. 승인 전에는 파일 생성, component 변경 및 LTspice 호출이 없다. 별도 분기로 기존 Run Simulation 경로와 구분된다.
- 기존 단일 실행 함수를 `simulation_runner.py`로 추출하여 단일 실행과 sweep 모두에서 재사용한다. 각 point마다 UUID별 `simulation_input/<id>` 및 `simulation_output/<id>`를 생성한다. 업로드 바이트의 복사본을 `AscEditor`로 열고 공식 `set_component_value()`로 R/C 값만 변경한 뒤 기존 directive 편집/SpiceEditor/SimRunner 절차를 실행한다. 원본 ASC는 읽기만 한다. 참고: https://pyltspice.readthedocs.io/en/latest/classes/asc_editor.html
- `parameter_sweep_execution.py`는 순차 실행, point별 상태/오류, 기존 RAW 분석 호출, 비교 표/요약/그래프를 담당한다. `OK`, `Partial Measurements`, `Simulation Failed`, `Analysis Failed`를 구분한다. RAW/LOG/directive/오류를 point별로 남기고 다음 point를 계속 실행한다. LTspice가 실패 시 생성하는 `.fail` 경로도 LOG 항목에 보존한다.
- AC의 Target/Reference complex gain, 초기 구간 median G0 및 log-frequency 보간 BW를 그대로 재사용한다. Transient는 기존 주기성 검증/Vpp gain/Output Swing/edge·step 적합성 판단을, DC는 기존 Min/Max/지점 보간/Difference/Matching Error를 사용한다. 요청한 측정 항목을 결과로 내보내며, 기존 분석에 필요한 공통 curve 계산은 재사용한다. 아직 미구현인 Phase/Peak Gain 등은 parameter 실행 승인 전에 거절한다.
- 모든 point를 비교 표에 표시한다. 유효 측정값에 한해 최솟값/최댓값과 해당 parameter, 요청 순서의 마지막-첫 번째 유효 값 차이를 계산한다. 동률은 첫 point를 표시하고 실패/미검출 값을 채워 넣지 않는다. 측정별 별도 그래프에서 실패 지점은 NaN으로 끊고, 파형 overlay는 처음 8개의 분석 가능한 curve로 제한한다. Parameter 축은 Ohm/F, 각 measurement 축에는 해당 단위를 표시한다.

### 실제 MOSFET R1 AC sweep

`test_ltspice.py`의 기존 `Draft3.asc`(FQB55N10 amplifier)를 사용했다. 실제 drain resistor **R1**에 500, 1k, 2k, 5k를 적용하고 Target=`V(vout)`, Reference=`V(vin)`, directive=`.ac dec 100 10 1Meg`로 Streamlit AppTest에서 승인 후 실제 LTspice를 실행했다.

| R1 [Ohm] | Low-Frequency Gain [dB] | -3 dB BW [Hz] | 결과 |
| --- | ---: | ---: | --- |
| 500 | 32.9628426354 | 13129.4689675 | OK |
| 1k | 38.9834321205 | 6274.78780482 | OK |
| 2k | 45.0039676504 | 2613.29689907 | OK |
| 5k | -38.2161724208 | Not found within sweep range | Partial Measurements |

네 point 모두 simulation 및 RAW/LOG 생성에 성공했다. 5k는 simulation 실패가 아니며 -3 dB crossing만 미검출이다. 관측된 500→2k 구간에서 Gain은 약 12.0411 dB 증가하고 BW는 약 10.5162 kHz 감소한다. 전체의 최대 Gain은 2k, 최대 검출 BW는 500이다. 5k 응답의 원인 추론이나 AI trade-off 설명은 추가하지 않았다.

### 두 번째 실제 검증: MOSFET C1 Transient 및 분압기 DC

동일 원본의 load capacitor **C1**, range=10n부터 30n까지 10n 간격, directive=`.tran 0 2m 1m 1u`, Target=`V(vout)`, Reference=`V(vin)`으로 Voltage Gain과 Output Swing을 요청했다. 세 point 모두 OK이며 Input Vpp는 약 **0.019990205765 V**이다. Gain은 기존 마지막 세 완전한 input cycle 기준이며 Output Swing은 저장 구간 전체 기준이다.

| C1 | Output Vpp for Gain [V] | Gain [V/V] | Gain [dB] | Output Swing p-p [V] |
| --- | ---: | ---: | ---: | ---: |
| 10n | 1.36663579941 | 68.3652692468 | 36.6967105709 | 1.36663722992 |
| 20n | 1.00553941727 | 50.3016041505 | 34.0316367041 | 1.00554180145 |
| 30n | 0.769561767578 | 38.4969407836 | 31.7085243805 | 0.769564628601 |

추가로 기존 `tests/fixtures/dc_divider.asc`에서 R1=1k/2k, `.dc V1 0 5 10m`, Target=`V(out)`, Min/Max를 실제 실행했다. Maximum은 각각 **2.5 V / 1.66666662693 V**, Minimum은 둘 다 0 V로 분압식 2.5 V / 5÷3 V와 atol=1e-6 이내 일치했다. 각각 독립 복사본과 RAW/LOG를 확인했다.

### 일부 실패 / 오류 처리와 계산 확인

- 별도 실제 R1=1k/2k/5k sweep에서 테스트용 runner가 2k point의 업로드 바이트에만 없는 MOSFET model 이름을 넣었다. 이는 실패 처리 검증용 주입이며 제품의 component 편집은 공식 API를 사용한다. 1k 정상 → 2k 실제 LTspice exit code 1/`.fail` → 5k 실행 및 gain 분석 성공으로 이어졌다. 실패 point에는 수치를 만들지 않고 표/Notes/LOG에 오류를 보존했다.
- 단위 테스트에서 중간 simulation 실패, RAW 생성 후 analysis 실패, BW 미검출, 전 point 실패, extrema/delta 및 그래프 결측 처리를 확인했다. 누락 component/승인 전에는 runner를 호출하지 않으며 강제로 보낸 미승인 UI 이벤트도 차단한다.
- 범위 생성 검토 중 매우 큰 범위의 Decimal 정수 나눗셈은 제한 검사 전에 예외를 낼 수 있어, 먼저 비율을 100-point 상한과 비교하도록 보완했다. `stop=1e100`도 사용자용 ValueError로 거절하는 테스트를 추가했다. 실행 함수 추출 후 PyLTSpice import를 함수 안에 유지하여 기존 테스트의 simulator/editor 대체 및 승인 경계 검증을 보존했다.
- 정상 결과 그래프(AC Gain/BW 비교 및 overlay, Transient Gain 비교 및 overlay)를 직접 열어 축/단위/곡선/범례가 표시되는지 확인했다.

### 수행한 검증 및 증빙

- 프로젝트 `.venv`의 Python으로 `python -m py_compile app.py` 및 새 module/integration script 문법 검사 통과.
- `python -X utf8 -m unittest discover -s tests -p "test_*.py"`: **56개 모두 통과**. AC 14 + Transient 11 + DC 10 + 기존 parameter parser/component/UI 13 + 새 execution 8. 기존 synthetic 계산 검증도 포함한다.
- `tests/verify_parameter_sweep_integration.py`: 실제 MOSFET AC 4회 + C1 Transient 3회 + divider DC 2회 + 의도한 중간 실패 sweep 3회, 총 **12 point 실행(11 simulation 성공, 1 의도한 실패)**. Streamlit 승인/실행/결과 표, 각 복사본의 값/directive, RAW/LOG, 원본 byte 보존, 분석/비교 표/그래프를 검증했다.
- 기존 `tests/verify_integration.py --real-ltspice`, `tests/verify_transient_integration.py --real-ltspice`, `tests/verify_dc_integration.py --real-ltspice`: 모두 exit 0. AC 범위 수정/누락 trace/실제 모델 실패, Transient optional time/sine의 부적절한 step 지표 거절, DC 전압·전류원/미러/누락 trace·source/실제 모델 실패 및 원본 보존 통과.
- 기존 AC 회귀 수치 G0=38.983432121 dB, BW=6274.787804816 Hz; 기존 Transient 회귀 Gain=47.491565834178 V/V, Input/Output Vpp=0.019999742508/0.949819087982 V로 이전 결과와 일치했다. DC mirror @3 V Matching Error=2.34111267131%로 이전 수치 및 독립 scalar 계산과 일치했다.
- 실제 Streamlit headless 서버를 임시 port 49404로 시작하여 root 및 `/_stcore/health` HTTP 200/`ok`를 확인하고 검증용 서버만 종료했다. AppTest의 bare-mode ScriptRunContext warning은 테스트 실행 환경 안내이며 예외/실패는 없었다.
- sweep 결과/요약 JSON과 비교/overlay PNG: `simulation_output/parameter_sweep_verification_2d8cc0ff331f440487402f34d5af2c08/`. 각 JSON에 개별 RAW/LOG/directive와 Notes가 있다. 실행용 ASC는 각 RAW의 parent run id와 동일한 `simulation_input/<id>`에 있다.
- 새 AC 회귀 RAW: `simulation_output/a68eba2d9ffa4ab9b9c1361004777277/Draft3_1.raw`; Transient 회귀: `simulation_output/1c927e0b5e8f4dbfb206ecb715c7c7c9/Draft3_1.raw`; DC mirror 회귀: `simulation_output/3f20a116257543f6b0820df9263aa052/dc_current_mirror_1.raw`.

### 현재 한계 / 다음 TODO

- 하나의 최상위 resistor/capacitor, 양수 값, 최대 100 points의 순차 실행을 지원한다. 기존 parser의 L 인식은 유지하지만 실제 L 실행은 차단한다. transistor W/L, 다중 component/nested sweep, optimization은 구현하지 않았다.
- RAW 분석의 기존 제한을 유지한다: AC BW는 low-pass 가정/주어진 sweep 안의 crossing, Transient는 waveform 적합성 및 저장 sample 해상도, DC는 하나의 독립 source ascending sweep이다. 원본에 `.step`이 있는 nested/stepped RAW는 지원 범위가 아니며 기존 분석기가 거절한다.
- 아직 결과는 실행한 화면에서만 표시하며 재실행 상태 유지/기존 RAW 불러오기, 취소·재개 및 대량 실행 관리, 외부 model/include 경로 관리는 후속 TODO이다. Overlay는 8개까지만 보이지만 표에는 모든 point가 있다.
- LLM/API, AI 원인 설명, Word report, LTspice screenshot automation, arbitrary circuit generation은 추가하지 않았다.

---

## 2026-09-16 — Analysis Summary Builder (Prompt 007C)

### 구현 / summary schema

- `analysis_summary.py`에 `build_analysis_summary()`와 `build_sweep_summary()`를 추가했다. 기존 ACResult/TransientResult/DCResult/SweepPoint에서 이미 계산된 결과를 읽으며 RAW 측정 수식이나 simulation을 다시 구현하지 않는다. 기존 `comparison_summary()`를 min/max/요청 순서의 변화량 계산에 재사용한다.
- 공통 schema v1.0: `schema_version`, `analysis_type`, `status`, `simulation_conditions`, `measured_facts`, `derived_facts`, `warnings`, `comparison_results`, `evidence`. 단일 분석의 불필요한 derived/comparison 필드는 빈 dict로 둔다.
- `simulation_conditions`: 검토한 조건, target/reference/comparison, 실제 저장 축 범위, 선택 지점 및 분석기가 사용한 측정 방법/notes. Sweep은 component, parameter 단위(Ohm/F), 분석 종류/상세 조건을 담고 point별 `analysis_context`에도 실제 측정 구간과 방법을 보존한다.
- `measured_facts`: 단일 분석은 `{value, unit, status}`를 사용한다. Transient는 측정 그룹 아래에 실제 계산된 값을 둔다. Sweep은 point index/value/label, 원래 실행·분석 status, 측정명(단위 포함)→값, notes를 보존한다. 실패한 point에 남은 stale metric이 있어도 summary에서는 제외한다. 수치가 없으면 null 또는 빈 측정 그룹이며 대체 수치를 만들지 않는다.
- `derived_facts`: parameter 값 순으로 비교한 전체 monotonic 여부, 유효 sample 수와 연속 구간의 방향/시작·끝 값/변화량/변화율, 판단 규칙을 기록한다. `comparison_results`에는 기존 비교 함수의 extrema/해당 parameter label/요청 순서의 last-first delta를 보존한다. 두 항목의 정렬 기준은 명시적으로 구분한다.
- `warnings`: code/message 및 필요한 measurement, point index/parameter value, 누락·사용 가능 trace, 비정상 값의 JSON 경로 또는 trend 판단 근거를 담는다. `evidence`에는 RAW/LOG/그래프 경로, 실제 적용 directive, parameter value만 참조로 담는다. 파일 내용이나 전체 waveform/complex transfer array는 넣지 않는다.
- `json_native()`는 NumPy scalar/ndarray, tuple, Decimal, Path를 JSON native 값으로 바꾼다. NaN/Inf는 null로 바꾸고 `non_finite_result`와 위치를 기록한다. 모든 검증은 `json.dumps(..., allow_nan=False)`로 strict JSON 직렬화 및 JSON 재읽기를 확인한다. 임의 객체를 문자열로 숨겨 직렬화하지 않는다.
- `app.py`의 AC/Transient/DC 및 Parameter Sweep 결과 아래에 **Analysis Summary**를 추가했다. 숫자와 규칙 결과를 고정 형식의 읽기 쉬운 텍스트로 표시하고 `Summary JSON` expander에서 구조를 확인한다. 기존 Matplotlib 그림을 해당 실행 결과 폴더에 저장하여 실제 graph reference를 제공한다. 그림 저장 오류는 화면에 설명하고 빈 경로 목록으로 남겨 simulation 성공을 뒤집지 않는다.
- `parameter_sweep_execution.py`의 계산/실행 순서는 유지했다. 예외의 missing/available trace 목록을 구조적으로 보존하는 `failure` 필드만 추가했다. 승인 전 실행/파일 생성 차단 및 원본 ASC 복사본 원칙은 유지한다.

### measured / derived / warning 분리 및 trend 규칙

- Measured는 기존 Python 분석기가 실제 RAW에서 계산한 값이다. Derived는 이 값들의 비교 연산이며 회로 topology, 동작 영역, 원인 또는 이론적 trade-off를 추론하지 않는다. 분석기 notes는 그대로 보존하며 주의 내용은 `analysis_caution`으로 표시한다.
- Parameter를 숫자 오름차순으로 정렬한다. 중복/비정상 parameter는 trend 판단을 보류한다. 수치 변화의 동등성 허용오차는 `max(1e-15, max(abs(a),abs(b))*1e-9)`이다. 이 기준에서 increasing/decreasing/constant 및 plateau를 포함한 nondecreasing/nonincreasing을 구분한다.
- 실패·누락·NaN/Inf 사이를 이어 붙이지 않는다. 전체 측정이 빠지면 monotonic=`incomplete`, 유효 값이 두 개 미만이면 `insufficient_data`이다. 인접한 유효 구간만 방향이 같은 최대 연속 segment로 정리하므로 일부 구간의 추세를 전체 sweep의 추세로 단정하지 않는다.
- 변화율은 `100*(last-first)/abs(first)`이다. 기준값 0에서는 null이며, dB 측정에는 백분율을 만들지 않고 dB 차이만 기록한다. extrema는 유효 값만 사용하고 동률은 요청 순서의 첫 point를 사용한다.
- 큰 이탈은 **앞선 두 번의 변화가 같은 방향이고, 다음 변화가 반대 방향이며, 그 절댓값이 앞선 두 절대 변화의 median의 3배보다 큰 경우** `large_trend_reversal`로 기록한다. 최소 네 개의 연속 유효 point가 필요하다. 실제 변화량, 기준 median, factor=3, 앞선 parameter 목록을 함께 남긴다. 이는 v1의 관측 규칙이며 통계적 outlier 확정이나 물리적 원인 진단이 아니다.
- BW 미검출은 `bandwidth_not_found`, invalid sample 때문에 결정 불가인 경우는 `bandwidth_undetermined`로 구분한다. `trace_missing`, `simulation_failed`, `analysis_failed`, `measurement_missing`, `measurement_not_applicable`, `non_finite_result`를 별도로 기록한다. 하나의 상황이 누락 측정 경고와 구체적인 BW 경고에 함께 나타날 수 있다.

### 기존 실제 RAW로 생성한 summary 예시

Prompt 007B의 archived RAW 7개(R1 AC 4개, C1 Transient 3개)를 기존 분석기로 다시 읽고, 이전 JSON에 저장된 모든 측정값과 rtol/atol=1e-12 이내 일치함을 검증했다. `tests/verify_summary_evidence.py`에서 재현할 수 있다.

| R1 [Ohm] | Gain [dB] | BW [Hz] | summary |
| --- | ---: | ---: | --- |
| 500 | 32.9628426354 | 13129.4689675 | 유효 |
| 1000 | 38.9834321205 | 6274.78780482 | 유효 |
| 2000 | 45.0039676504 | 2613.29689907 | 유효 |
| 5000 | -38.2161724208 | null | BW crossing 미검출 / 큰 추세 반전 |

- 500→2000 Ohm: Gain increasing, delta=**+12.0411250150 dB**. BW decreasing, delta=**-10516.1720684 Hz**, relative change=**-80.0959436704%**.
- Gain 전체는 `non_monotonic`이다. 2000→5000 Ohm의 **-83.2201400712 dB** 변화는 앞선 두 변화의 median **6.02056250751 dB**의 3배보다 크고 방향이 반대라 큰 반전으로 기록된다. 5000 Ohm에서 왜 이런 결과가 나왔는지는 설명하지 않는다.
- BW 전체는 마지막 지점이 없으므로 `incomplete`이며 500→2000 Ohm의 유효 감소 구간만 기록한다. 검출된 BW의 maximum은 500 Ohm, minimum은 2000 Ohm이다.
- C1=10n/20n/30n에서 Gain=**68.3652692468/50.3016041505/38.4969407836 V/V**. 전체 monotonic=`decreasing`, delta=**-29.8683284632 V/V**, relative change=**-43.6893305509%**, summary warnings=0이다.
- Strict JSON 예시: `simulation_output/analysis_summary_verification_549e8321287a4134820a3e4524e3ceda/mosfet_resistor_ac_analysis_summary.json` 및 `mosfet_capacitor_transient_analysis_summary.json`. 원본 RAW/LOG와 기존 PNG 참조가 포함되어 있다.

### 현재 한계 / 다음 TODO

- 큰 반전 규칙은 네 개 이상의 연속 유효 측정과 고정 factor=3을 요구한다. 모든 이상점/완만한 이탈을 찾는 일반 탐지기가 아니며 불균일 parameter 간격으로 변화량을 정규화하지 않는다. 후속 단계에서 다양한 sweep의 false positive/negative를 검증하고 임계값 설정을 검토한다.
- 수치 허용오차는 측정의 native 단위에 적용하는 고정 규칙이다. 서로 다른 해상도·극소 시간 값에 대한 domain별 tolerance는 후속 검토 사항이다.
- 기존 분석기의 low-pass 가정, 저장 구간/시간 해상도, waveform 적용 가능성, 단일 DC source 및 R/C sweep 제한을 유지한다. 원시 curve 전체나 오차 추정치를 summary에서 새로 만들지 않는다.
- Schema는 v1.0이며 향후 소비자 계약·버전 migration, 결과 저장/불러오기 UX, 조건이 서로 다른 결과를 비교하기 전 동등성 확인은 다음 TODO이다. JSON 예시는 검증 스크립트가 저장하며 앱에는 텍스트와 JSON 보기를 제공한다.
- OpenAI/LLM/API 연결, AI 결과 해석, 원인 설명, Word report, screenshot automation은 구현하지 않았다.

### 최종 검증 결과 / 오류 처리

- 프로젝트 가상환경의 `python -m py_compile app.py` 및 변경 module/test script 문법 검사 통과.
- `python -X utf8 -m unittest discover -s tests -p "test_*.py"`: **70개 모두 통과**. 기존 AC 14 + Transient 11 + DC 10 + Parameter 21 = 56개를 유지하고 summary 테스트 14개를 추가했다. AC/Transient/DC adapter, BW 미검출, 적용 불가/누락, R1 구간 추세와 반전, C1 정렬/단조 감소, 실패/비정상 값 제외, gap 미연결, 중복 parameter/상수/허용오차, missing trace metadata, strict JSON 및 입력 객체 비변경을 확인했다.
- 기존 `verify_integration.py --real-ltspice`, `verify_transient_integration.py --real-ltspice`, `verify_dc_integration.py --real-ltspice` **모두 exit 0**. 기존 승인 차단/변경 시 재승인/원본 보존/범위 수정/trace 누락/실제 simulation 실패 검증에 더해 실제 화면의 Summary JSON, schema 필드, JSON의 비정상 수치 없음 및 graph reference 파일 존재를 확인했다.
- 실제 AC 회귀 G0=38.9834321205 dB, BW=6274.78780482 Hz; Transient 회귀 Gain=47.4915658342 V/V; DC mirror @3 V Matching Error=2.34111267131%로 기존 결과와 일치했다.
- `verify_parameter_sweep_integration.py`: R1 AC 4회, C1 Transient 3회, divider DC 2회, 중간 실패 3-point sweep을 실제 재실행했다. 총 **12 points: 11 simulation 성공, 의도한 모델 오류 1회**. R1/C1 수치가 위 archived 결과와 일치하고 화면의 summary, 구간 추세/5k 반전·BW 미검출, C1 monotonic decrease를 assertion으로 확인했다. 중간 실패 후 마지막 point 실행/분석, 실패 수치 제외, RAW/LOG/원본 ASC 보존도 통과했다.
- Parameter 결과와 새 `*_analysis_summary.json` 증빙: `simulation_output/parameter_sweep_verification_4c1a3f6140324301b12b993c469039e1/`. 실제 UI에서 표시한 전체 조건 포함 JSON은 첫 point 결과 폴더 `simulation_output/d8931690b16e469787e8a487f9a120ee/analysis_summary.json`(R1), `simulation_output/0cb55acf85de478897485122691e08b0/analysis_summary.json`(C1)에 검증 스크립트가 보관했다.
- 단일 분석 UI summary 증빙: `simulation_output/0688c3b0bfd5418cacac71c21dee72a2/analysis_summary.json`(AC), `simulation_output/a878b80f2faf469cbd1f7187d2e53902/analysis_summary.json`(Transient), `simulation_output/31574c6cef88483bbe37739e9fd1c688/analysis_summary.json`(DC). Missing trace summary 예: `simulation_output/7aa1d00f6a4e4e4c971a0a5a23094752/analysis_summary.json`.
- 별도 Streamlit 서버를 임시 port 57923에서 실행하여 health `200/ok` 및 root HTTP 200을 확인하고 검증용 프로세스만 종료했다.
- 새 기능의 테스트 실패나 실제 계산값 변경은 없었다. 설계 검토에서 실패 point의 stale metric 배제, JSON NaN/Inf 정리, 부분 구간과 전체 monotonic 구분 및 parameter 단위/측정 context 보존을 명시했다. 의도한 모델 오류는 기존 실제 실패 시나리오이며 앱 crash 없이 처리됐다. Streamlit AppTest의 bare-mode warning은 테스트 환경 안내이다.

---

## 2026-09-16 — AI Interpretation Prompt Builder (Prompt 008A)

### 구현 / 입력 경계

- `ai_interpretation.py`에 `build_interpretation_prompt(summary)`와 `prompt_as_text(prompt)`를 추가했다. 표준 라이브러리만 사용하는 provider-neutral 순수 함수이며 파일 읽기, RAW 접근, simulator 실행, 네트워크/API 호출 또는 key 설정이 없다.
- 입력은 기존 JSON-compatible Analysis Summary 하나다. 기존 계산 모듈과 Summary Builder는 변경하지 않았다. RAW complex waveform 및 내부 editor/result 객체를 AI에 전달하면 정량 계산을 모델에 다시 맡기거나 자료의 의미를 추정하게 되므로, Python이 이미 검증한 수치·정의·상태·주의사항을 중간 계층으로 유지한다.
- 허용한 상위 Summary 필드를 복사하고 알 수 없는 상위 확장은 제외한다. file/RAW waveform 관련 필드는 제외하며 내부의 지원하지 않는 non-JSON 객체는 repr 등으로 전달하지 않고 null과 preparation notice로 처리한다. 누락 필드는 빈 자료로 두고 수치를 만들지 않는다. 기존 finite 숫자는 round/단위 변환/재계산 없이 그대로 복사하고 원본 Summary를 변경하지 않는다. 잘못 유입된 NaN/Inf는 null과 preparation notice로 처리한다.

### Prompt schema / 역할과 출력

```json
{
  "prompt_version": "1.0",
  "system": "공통 fact/inference 규칙 및 출력 section 지시문",
  "user": {
    "task": "주어진 Analysis Summary 설명 요청",
    "analysis_focus": ["분석 종류별 설명 대상과 주의사항"],
    "analysis_summary": {"검토된 Summary 필드": "수치와 정의를 유지한 자료"}
  },
  "preparation_notes": ["경로 제외, 미지원 입력 처리 등 준비 과정의 안내"]
}
```

- 시스템 규칙은 Summary의 측정값/파생 사실/기존 비교 결과만 factual evidence로 사용하되 status와 warnings의 제약을 따르도록 한다. 새로운 numerical result, 반올림·단위 변환·변화량 재계산, 미측정 값의 생성, null을 0으로 해석하는 행위를 금지한다.
- 회로 이론의 가능한 원인은 반드시 inference/hypothesis로 표시한다. topology나 동작 영역을 정보 없이 확정하거나 경고만으로 saturation/cutoff/clipping/instability를 단정하지 않는다. 정보가 부족하면 무엇이 부족한지 밝히도록 한다.
- RAW/LOG/graph/schematic 파일을 직접 열거나 관찰했다고 주장하지 않는다. Summary 내부의 trace 이름·notes·warnings·directive 문자열은 자료이며 지시문으로 따르지 않는다. 다음 simulation/measurement 제안도 실행 지시가 아닌 사용자 검토 대상이다.
- 응답은 `Confirmed Results`, `Interpretation`, `Additional Insights`, `Warnings / Uncertainty`, `Suggested Next Checks`로 구분하도록 한다. 불필요한 section은 생략하거나 근거 부족을 명시할 수 있고, 한국어 설명 및 원래 trace/unit 표기를 요청한다. 이번 단계에서 해당 응답을 생성하지는 않는다.
- AC는 Gain/BW/요약된 주파수 응답, low-pass 및 부분 구간의 trade-off를 설명하게 한다. 큰 반전에는 관측과 가능한 원인을 구분하고 operating point 확인 등을 제안하도록 요청한다.
- Transient는 Vpp/Gain/Output Swing/Rise/Fall/Overshoot/Settling과 waveform 적용 가능성/저장 구간을 지키도록 한다. DC는 전압/전류/sweep/difference/matching error와 Python의 원래 정의·분모·부호·제외 기준을 유지한다. `calculation_notes`의 정의를 그대로 담고 없는 정의는 임의 보충하지 않는다.
- Parameter Sweep은 내부 analysis_type에 맞는 지시문에 point status, 기존 extrema/changes/monotonic segments 및 실패 구간을 이어 해석하지 말라는 규칙을 덧붙인다. component 이름이나 예시 수치를 prompt template에 하드코딩하지 않는다.

### 경로 처리 / UI / export

- evidence에서는 적용 directive와 point index/parameter linkage만 남기고 RAW/LOG/PNG 로컬 경로는 제외한다. Summary의 자유 텍스트에 섞인 Windows drive/UNC/file URI, 여러 directory로 된 POSIX 경로 및 simulation_input/output 경로도 해당 줄의 나머지를 보수적으로 가린다. `Target / Reference`, `[V/V]`, matching-error 수식은 유지하도록 테스트했다.
- 파일을 직접 읽거나 첨부하지 않는다. Summary에 이미 포함된 simulator 오류 발췌는 경로를 가린 채 남을 수 있으며, preview의 preparation notice에 이 점을 명시했다. 경로 처리기는 범용 secret/DLP scanner가 아니므로 향후 실제 전송 전 검토는 별도 단계에서 설계한다.
- 기존 Summary 아래 **AI Interpretation** / **Prepare AI Interpretation** / prompt preview / structured facts preview / JSON 다운로드를 추가했다. **LLM execution is not connected yet.**를 명시하고 실제 inference나 API는 호출하지 않는다. Plain text는 `prompt_as_text()`와 검증용 `.txt` export로도 확인할 수 있다.
- Streamlit rerun 시 Run Simulation 분기 안의 Summary가 사라지는 구조를 확인하여 완료 Summary와 준비한 prompt만 session_state에 보관했다. Preview/export 때문에 simulator가 다시 실행되지 않는다. 조건·요청·업로드 변경 및 새로운 실행 시작 시 캐시를 비워 이전 결과가 잘못 표시되지 않도록 했다. Parameter 분기의 `st.stop()` 전에도 동일한 UI를 표시한다. 전체 waveform/result 객체를 캐시에 추가하지 않았다.

### 검증과 현재 한계

- `python -m py_compile app.py ai_interpretation.py` 및 새 test/verification script 문법 검사 통과.
- 기존 70개 + 새 13개, 전체 **83개 unit tests 통과**. AC/Transient/DC/Parameter prompt, DC 정의 보존, warnings/실패/누락, 수치 exact equality, unknown fields/internal objects, strict JSON, 원본 비변경, 경로 가림, fact/inference 규칙 및 embedded instruction 경계, 두 UI 경로의 Prepare/rerun/reset을 검사했다.
- UI 테스트에서 미승인 Run 비활성화, 승인 후 단 한 번의 실행, Prepare 후 runner call count 불변, 재실행 실패 시 stale prompt 제거, 업로드·조건 변경 시 초기화, 원본 fixture 바이트 보존, preview/다운로드 위젯 표시를 확인했다. API client와 호출 코드는 존재하지 않는다.
- 실제 Streamlit server를 임시 port 52892로 시작하여 root HTTP 200과 health 200/ok를 확인하고 검증용 서버만 종료했다.
- 이 단계의 guardrail 검증은 prompt 구조와 입력 보존 검증이다. 아직 모델이 응답하지 않았으므로 hallucination 방지 효과나 모델의 지시 준수율을 검증한 것은 아니다. 실제 LLM/provider 연결, 응답의 fact/inference·숫자 일치 평가, context 크기 정책과 추가 개인정보 검토는 다음 단계 TODO이다. Word report/screenshot automation도 추가하지 않았다.

### 실제 Summary 기반 prompt 예시

- `tests/verify_interpretation_prompt.py`로 기존 실제 R1 AC, C1 Transient, DC current mirror, 중간 simulation 실패 sweep Summary를 입력했다. 각 입력의 measured/derived/comparison/warnings에 있는 모든 native numerical field를 경로별로 비교하여 prompt의 값과 **정확히 동일**함을 확인했다. strict JSON round-trip, 로컬 경로 제외 및 원본 Summary 바이트 비변경도 통과했다.
- 최종 export: `simulation_output/interpretation_prompt_verification_9365455aff504265a84e121e3e778b2a/`. `1_Parameter_Sweep.json/.txt`는 R1, `2_Parameter_Sweep.json/.txt`는 C1, `3_DC_Sweep.json/.txt`는 DC, `4_Parameter_Sweep.json/.txt`는 실제 실패 point가 포함된 경우다. 모두 prompt이며 AI 응답이 아니다.
- R1 prompt의 structured facts는 500/1000/2000/5000 Ohm의 Gain **32.96284263539796 / 38.98343212053324 / 45.00396765042122 / -38.21617242078733 dB**를 보존한다. BW는 **13129.468967511782 / 6274.787804816243 / 2613.296899065459 / null Hz**이다.
- 기존 Derived facts의 500→2000 Ohm Gain delta **12.041125015023255 dB**, BW relative change **-80.09594367044141%**, 5000 Ohm의 `large_trend_reversal`과 `bandwidth_not_found`를 그대로 담는다. Prompt는 이를 관측 사실로 설명하고 가능한 회로적 이유는 inference로 표시하며 operating point 등 추가 확인을 제안하도록 요청한다. 특정 원인이나 새로운 수치를 삽입하지 않는다.
- C1 prompt도 Gain **68.3652692468245 / 50.301604150515836 / 38.49694078358876 V/V**와 기존 monotonic decrease를 그대로 담는다. DC prompt는 기존 matching-error 식/Target 분모/near-zero 제외 기준을 보존한다. 실패 prompt의 측정값은 빈 dict이고 오류·상태는 남기며 경로를 가린다.

### 중단 후 재개 / 최종 검증 (2026-09-16)

- 재개 시 prompt builder, app preview/cache/export, 관련 unit/UI test 13개 및 실제 Summary 검증 스크립트는 이미 구현되어 있었다. development log도 작성되어 있었으나 실제 integration의 최종 완료 기록과 prompt log의 008A 항목이 남아 있었다. 미완성 코드나 syntax error는 발견하지 않았다. 이번 재개에서는 구현 코드를 변경하지 않고 검증과 두 문서 보완만 수행했다.
- 중단 전 terminal session의 종료 상태는 더 이상 조회할 수 없었다. 기존 `simulation_output/parameter_sweep_verification_4d4ec854d24843808e8a0fde67ad7d56/partial_failure_analysis_summary.json`에서 실패 후 마지막 point까지 생성된 결과를 확인한 뒤, 종료 코드를 확실히 남기기 위해 실제 integration 4종을 순차 재실행했다.
- `python -m py_compile app.py ai_interpretation.py tests/test_ai_interpretation.py tests/verify_interpretation_prompt.py`: 통과. `python -X utf8 -m unittest discover -s tests -p "test_*.py"`: **83개 모두 통과 (18.090초)**. AC 14, Transient 11, DC 10, Parameter 21, Analysis Summary 14, AI prompt/UI 13개다.
- 실제 `verify_integration.py --real-ltspice`, `verify_transient_integration.py --real-ltspice`, `verify_dc_integration.py --real-ltspice`, `verify_parameter_sweep_integration.py` 모두 **exit 0**. 로그와 종료 코드는 `simulation_output/prompt_008a_resume_57f1d68413a5415ea641997cfdd3b6ec/`의 각 `*.py.log` 및 `results.json`에 저장했다. 승인 전 편집/실행 차단, 조건 수정 후 재승인, 원본 ASC 바이트 보존, RAW/LOG 및 graph reference, Summary 표시/strict JSON, missing trace와 실제 simulator 오류의 앱 crash 없는 처리가 통과했다.
- 실제 AC G0=38.983432121 dB, BW=6274.787804816 Hz; Transient Input Vpp=0.01999974250793457 V, Output Vpp=0.9498190879821777 V, Gain=47.49156583417774 V/V; DC mirror @3 V Matching Error=2.34111267131%. 기존 계산 결과를 유지했다. AC 조건 변경, Transient 선택 시간 구간과 sine의 부적절한 step metric 거절, DC voltage/current source 및 누락 trace 검사도 통과했다.
- Parameter integration은 R1 AC 4점, C1 Transient 3점, divider DC 2점 및 중간 실패 3점을 실제 실행했다. **12 points 중 11 simulation 성공과 의도한 모델 오류 1건**이다. 중간 실패 시나리오의 R1=1k는 OK, 2k는 Simulation Failed(측정값 없음, `.fail` 기록), 5k는 계속 실행되어 Partial Measurements(Gain=-38.21617242078733 dB, BW=null)로 기록됐다. 실패 point를 수치/추세로 메우지 않았다. 증거: `simulation_output/parameter_sweep_verification_f5fdb2d9c69942c69d4f072ded638037/`의 결과와 `partial_failure_analysis_summary.json`.
- `verify_summary_evidence.py`로 이번 R1/C1 실제 RAW 7개를 다시 읽어 기존 measurement와 rtol/atol=1e-12 이내 일치, R1 유효 구간 Gain 증가/BW 감소 및 5k 경고, C1 monotonic decrease, strict JSON을 확인했다. 두 Summary 출력은 `simulation_output/analysis_summary_verification_265bbf070f094ded8bd2cf350a9a4b8d/`에 있다.
- `verify_interpretation_prompt.py`로 기존 실제 Summary 6종(R1, C1, DC mirror, 중간 실패, 단일 AC, 단일 Transient)과 이번 새 중간 실패 Summary 1종, **총 7개 입력 검증을 통과**했다. measured/derived/comparison/warnings 내 모든 native numerical field가 prompt와 경로별로 정확히 같고, strict JSON round-trip 및 원본 Summary 바이트 비변경을 확인했다. 수치와 단위는 그대로 유지하며 측정/파생 사실/경고를 분리하고, interpretation은 별도 지시문으로만 준비한다. 로컬 경로 제외와 formula 보존은 관련 unit test에서도 확인했다.
- 6종 prompt JSON/TXT: `simulation_output/interpretation_prompt_verification_11b439d75b3442269d3ae11069edb477/` (1=R1, 2=C1, 3=DC, 4=중단 전 실패, 5=AC, 6=Transient). 새 중간 실패 prompt: `simulation_output/interpretation_prompt_verification_ad7fa2054c56494c8a778def724114de/1_Parameter_Sweep.json` 및 `.txt`. 이는 AI 응답이 아닌 생성된 입력 prompt다.
- Streamlit을 임시 port **52079**에서 실행하여 health HTTP 200/ok와 root HTTP 200을 확인하고 검증 서버만 종료했다. 두 AppTest 경로에서 AI Interpretation preview, structured facts, JSON download 위젯, Prepare 후 simulator 재실행 없음, 재실행 실패/조건/요청/업로드 변경 시 이전 prompt 초기화가 통과했다. 브라우저 외관에 대한 수동 시각 검사는 이번 재개에서 수행하지 않았다.
- 새 결함이나 회귀 실패는 발견되지 않았다. 의도적으로 잘못된 모델을 사용한 LTspice exit 1은 오류 처리 테스트의 기대 결과이며, bare-mode Streamlit warning은 AppTest 실행 안내다. 실제 LLM/API는 연결하거나 호출하지 않았다. 남은 TODO는 향후 provider 연결, 실제 응답의 fact/inference 및 수치 준수 평가, context 크기 정책과 전송 전 개인정보 검토다. 현재 검증은 prompt 준비/데이터/UI에 한정되며 모델의 실제 지시 준수 효과는 아직 검증하지 않았다.

---

## 2026-09-16 — LLM Interpretation Integration (Prompt 008B)

### 구현 / provider 및 입력 경계

- `llm_client.py`에 `interpret_analysis(prompt_payload, config)`를 추가했다. 기존 LTspice → Python 분석 → Analysis Summary → Prompt 008A의 뒤에 OpenAI/mock 호출과 응답 검증을 연결했다. AC/Transient/DC/Parameter Sweep의 parser, 계산, simulation runner, `analysis_summary.py`, `ai_interpretation.py`는 변경하지 않았다.
- UI는 provider 모듈을 호출하며 API 코드를 직접 포함하지 않는다. 전송 직전 기존 builder로 system/user 내용의 정합성을 확인하고 변경된 지시문, 다시 유입된 경로/RAW/internal object를 거절한다. 실제 요청은 기존 system 및 structured user와 출력 형식 지시만 포함한다. RAW나 파일을 읽지 않으며 Summary 밖의 계산을 요청하지 않는다.
- OpenAI Responses API의 `text.format`에 strict JSON Schema를 전달한다. `confirmed_results`, `interpretation`, `additional_insights`, `warnings_uncertainty`, `suggested_next_checks` 모두 필수 string list이며 추가 필드는 허용하지 않는다. 로컬에서도 키와 자료형을 확인한다. 기존 system 규칙에 JSON field 대응, 추론/가설 표시, 새 숫자 생성 금지만 덧붙인다.
- 공식 [Structured Outputs 문서](https://developers.openai.com/api/docs/guides/structured-outputs)와 [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create)를 확인했다. 기본 모델은 Structured Outputs를 지원하는 [gpt-4.1-mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini)이며 `DEFAULT_MODEL` 한 곳에 둔다. `OPENAI_MODEL` 또는 UI에서 변경 가능하다. 이는 계정별 모델 접근 권한이나 실제 응답 품질을 검증했다는 의미는 아니다.
- SDK는 OpenAI provider 실행 시에만 import한다. `requirements-llm.txt`에 선택 의존성을 기록했고 가상환경에 `openai 2.54.0`을 설치했다. Mock은 표준 라이브러리만 사용하므로 SDK가 없어도 동작한다. SDK 미설치는 앱 crash 없이 설치 안내로 표시한다.

### 설정 / 사용자 실행 / 비용 경계

- `LLMConfig`가 provider/model/key/temperature/timeout/output limit/input limit를 관리한다. 환경변수가 Streamlit secrets보다 우선한다. `OPENAI_API_KEY`는 코드에 저장하지 않고 config repr, prompt, 반환 결과 및 오류 메시지에 넣지 않는다. Streamlit에서 키 자체를 표시하거나 session_state에 추가하지 않는다. 누락된 secrets 파일은 정상적인 미설정 상태로 처리한다.
- 키 없음: **API key not configured**와 비활성화된 Run AI Interpretation 버튼을 표시한다. `LLM_PROVIDER=mock` 또는 UI의 mock 선택으로 키 없이 실행 가능하다. Prepare/일반 rerun/다운로드/모델 선택만으로 호출하지 않는다. 별도 **Run AI Interpretation** 클릭에 한해서 실행한다. Simulation 승인은 AI 요청 승인을 대신하지 않는다.
- 기본 timeout=45초, max output=2500 tokens, max input=60000 characters. 환경설정 이름은 `LLM_TIMEOUT_SECONDS`, `LLM_MAX_OUTPUT_TOKENS`, `LLM_MAX_INPUT_CHARACTERS`이다. 상한 검증 후 너무 큰 입력은 자동 잘라내지 않고 호출 전에 거절한다. `LLM_TEMPERATURE`는 선택 사항이며 기본값 None은 API에 전달하지 않는다. 모델마다 지원 옵션이 다를 수 있다.
- 화면에서 provider/model과 문자 수, UTF-8 byte 수를 이용한 보수적 token 추정치를 표시한다. 이는 실제 tokenizer 수나 청구 금액이 아니다. System/user와 schema 크기를 포함하며 실제 API 비용이 발생할 수 있음을 안내한다. 호출은 timeout과 `max_retries=0`, `store=False`를 사용하며 자동 재시도/추가 fallback 호출을 하지 않는다. `store=False`를 별도의 데이터 보존 정책 보장으로 해석하지 않는다.
- Mock 실행 예: PowerShell에서 `$env:LLM_PROVIDER='mock'` 후 `.\.venv\Scripts\python.exe -m streamlit run app.py`. OpenAI 설정은 환경변수 또는 `.streamlit/secrets.toml`의 `OPENAI_API_KEY`, `OPENAI_MODEL`을 사용한다. 실제 키를 문서나 저장소에 기록하지 않는다. SDK 설치는 `.\.venv\Scripts\python.exe -m pip install -r requirements-llm.txt`.

### 응답 / 수치 검사 / 오류 처리

- Mock은 명확히 예시라고 표시된 고정된 다섯 필드 응답이다. 실제 회로 원인이나 측정 수치를 만들지 않는다. 같은 parsing/validation/UI 경로를 사용하여 API 비용 없이 기능을 검사한다.
- `validate_numerical_claims()`는 Summary의 조건/측정/파생/비교/경고에서 숫자와 알려진 단위를 수집한다. 응답의 숫자를 정규식과 Decimal로 비교하며 소수·부호·과학적 표기·천 단위 쉼표를 처리한다. `R1` 등 식별자 안 숫자는 수치 인용으로 취급하지 않는다. `-3 dB` 같은 기존 measurement 명칭과 정의도 허용 근거에 포함한다.
- 알려진 수치가 없으면 `unsupported_number`, 값은 있으나 단위 조합이 확인되지 않으면 `unverified_unit` 경고다. Sweep measurement의 `[unit]`, 단일 결과의 `{value, unit}`, 파생 변화율 `%`를 처리한다. 실패/사용 불가 record의 stale value는 허용하지 않는다. 반올림이나 단위 변환 결과를 새로 계산해 맞춰주지 않는다. 문제가 있으면 **AI response validation warning**을 표시하고 원 응답과 검증된 Summary를 수정하지 않는다.
- 이 검사는 lexical consistency이며 의미 검증이 아니다. 동일한 수치를 다른 trace/parameter/metric에 잘못 귀속시켜도 탐지하지 못할 수 있다. 숫자가 포함된 정의/metadata와 충돌할 수 있고 지원하지 않는 표기, 단위, 목록 번호 등에 false positive/negative가 가능하다. 새로운 원인 단정이나 가설 표기의 실제 준수도 자동 증명하지 않는다. 경고가 없음을 AI 내용의 정확성 인증으로 표시하지 않는다.
- Invalid JSON/잘못된 schema/빈 응답은 structured facts로 확정하지 않고 **Unverified raw response** fallback으로 표시한다. 출력 한도 등 incomplete response도 원문과 경고를 표시하며 수치 검사한다. refusal, authentication/permission, timeout, rate limit/quota, network, provider/configuration/dependency 오류를 안전한 메시지로 반환한다. 예외 원문에는 key/request/path가 섞일 수 있어 그대로 출력하지 않는다.
- App은 AI 결과만 별도 session_state에 보관한다. 실패해도 완료 Summary와 기존 파일 참조/수치는 유지한다. 모델/provider/조건/업로드/요청 변경, 새 simulation 또는 Prepare 시 오래된 AI 결과를 지운다. 기존 preview/export를 유지하고 다섯 응답 section을 plain text로 표시한다. AI 버튼이 LTspice 실행을 재호출하지 않는다.

### 실제 검증 결과

- `python -m py_compile app.py llm_client.py tests/test_llm_client.py tests/verify_llm_interpretation.py tests/verify_openai_interpretation.py`: 통과. `pip check`: No broken requirements found.
- 최종 `python -X utf8 -m unittest discover -s tests -p "test_*.py"`: **104개 모두 통과, 17.173초**. 기존 83개 유지 + 새 provider/validation/UI 21개. 기존 prompt UI 검사 두 개도 단일/Sweep simulation → Prepare → mock AI 실행 → 조건/실패 초기화까지 보완했다.
- 새 검사는 key 누락, env/secrets 우선순위, mock 무호출, exact numeric/단위/과학적 표기, rounding/new claim 경고, 실패 record 배제, schema 오류/fallback, refusal/incomplete, 인증/timeout/rate/network 오류 및 단일 호출, 요청 크기/변조 차단, SDK 미설치, UI 명시적 실행과 rerun/cache/reset을 포함한다. 실제 설치 SDK도 `httpx.MockTransport`로 검사해 Responses 요청 schema와 응답 읽기 동작을 확인했다. 모든 unit test는 외부 API를 사용하지 않는다.
- `tests/verify_llm_interpretation.py`로 실제 AC, Transient, DC current mirror, R1 AC sweep, C1 Transient sweep, 중간 실패 sweep **6종 Summary**를 검증했다. 각 입력의 mock 응답, 실제 measurement를 정확히 인용한 fake structured response, 새 수치 987654321.123 dB를 넣은 경고 응답, strict JSON 및 원본 Summary 바이트 보존 모두 통과했다. 증거: `simulation_output/llm_mock_verification_a0a956ea351d40c4826df7143bfe152f/`의 JSON 6개. `exact_measurement_response`는 검증용 fake 응답이며 실제 모델 출력이 아니다.
- 실제 `verify_integration.py --real-ltspice`, `verify_transient_integration.py --real-ltspice`, `verify_dc_integration.py --real-ltspice`, `verify_parameter_sweep_integration.py` **4종 모두 exit 0**. 로그/종료 코드: `simulation_output/prompt_008b_regression_2df91970e9d44014aab0675ad0e03a29/`. AC Gain=38.983432121 dB/BW=6274.787804816 Hz, Transient Gain=47.49156583417774 V/V 및 기존 DC 계산 결과를 유지했다. 승인 차단/원본 ASC 보존/Summary/RAW/LOG/graph/실제 오류 처리 검증도 통과했다.
- Parameter 회귀는 12 points 중 11 simulation 성공, 의도한 중간 모델 오류 1건 후 마지막 point까지 계속 실행했다. 증거: `simulation_output/parameter_sweep_verification_339970f8c4094016b0eac554946ae526/`. 5k의 BW null과 실패 point의 빈 measurement가 유지됐다.
- 별도 Streamlit 서버를 `LLM_PROVIDER=mock`, port **55257**에서 실행하여 health 200/ok와 root HTTP 200을 확인하고 검증 서버만 종료했다. 결과 preview/Run/오류/section 표시와 상태 유지 검증은 AppTest로 수행했다.
- 환경변수 `OPENAI_API_KEY`는 미설정이었다. `tests/verify_openai_interpretation.py`를 실행하여 **SKIP: API key not configured**를 확인했다. 실제 유료 API 호출은 **0회**다. 향후 수동 실행은 `python tests/verify_openai_interpretation.py <verified-summary.json> --execute`이며 key와 명시적 flag가 둘 다 있어야 호출한다. 자동 unit suite에서는 실행하지 않는다.
- 검증에서 새 회귀 실패는 없었다. SDK 부재는 선택 의존성 설치로 해결했고 일반 sandbox Python 실행 경로 제한은 이미 승인된 가상환경 실행 권한을 사용했다. LTspice 모델 오류는 의도한 실패 테스트이며 AppTest bare-mode warning도 앱 오류가 아니다.

### 한계 / 다음 TODO

- 실제 계정의 모델 접근, quota, latency, 출력 한도 및 실제 응답의 fact/inference·수치 준수율은 키 설정 후 별도 smoke/evaluation이 필요하다. SDK/fake HTTP 검증만으로 실제 API 성공이나 AI 해석 품질을 주장하지 않는다.
- 현재 numerical check는 보수적인 숫자/단위 membership 검사다. 향후 trace/point/measurement 식별자를 갖는 claim-evidence 연결, 다국어/단위 표기, 모델의 수치 재인용과 가설 경계 평가를 개선한다. Prompt 008A의 경로 제거는 범용 개인정보/secret scanner가 아니므로 실제 전송 데이터 검토는 여전히 필요하다.
- 크기 초과는 거절하며 자동 요약/분할, 정확한 tokenizer 기반 비용 계산은 구현하지 않는다. Word report, screenshot automation, arbitrary circuit generation, autonomous optimization, multi-agent system은 추가하지 않았다.

---

## 2026-09-17 — Core UX Polish After Real User Testing (Prompt 009A)

### 중단 상태와 이어서 완료한 범위

- 재개 시 `app.py`, `ui_helpers.py`, `tests/test_ui_helpers.py`에 공통 83% 그래프 영역, 표시 단위, 비교 표 정리/Evidence, 회로·분석별 성공 조건 history, trace 추천 버튼, DC point 카드와 UI 측 parsing adapter가 이미 작성되어 있었다. 변경사항을 되돌리거나 재구현하지 않았다. 이전 terminal handle은 조회할 수 없어 저장된 코드 기준으로 테스트를 다시 실행했다.
- 새 UX 검사 16개 중 15개가 통과했고 DC 후속 요청 검사 1개가 실패했다. `V(vout)` 안의 `vout`을 sweep source로 인식해 이전 V2를 재사용하지 못한 것이 원인이었다. `dc_analysis.py`의 source 토큰 경계에 여는 괄호를 포함해 node 내부 이름을 제외했다. `3.55 V에서`의 point parsing은 DC parser로 옮겨 단일/Sweep/UI에서 공통으로 사용하고 중복 UI 처리 부분을 제거했다. 계산/interpolation은 변경하지 않았다.
- 정확한 사용자 문장과 분석 종류 분리 검사를 보완하고, 실제 브라우저 레이아웃 fixture/verification 및 기존 DC/Parameter integration assertions를 추가했다. `ac_analysis.py`, `transient_analysis.py`, 모든 정량 계산 모듈, Parameter Sweep 실행 모듈, Summary schema, LLM/API는 변경하지 않았다.

### Real User Testing Findings

| 사용자 테스트에서 발견한 문제 | 수정 내용 |
| --- | --- |
| **V(out) vs V(vout)**: 요청 이름과 실제 trace 이름 차이로 분석 실패 | 승인 전에 업로드 ASC의 FLAG voltage label을 읽고, 분석 실패 후에는 실제 RAW available traces를 사용해 유일한 case/단순 v-prefix 후보를 추천한다. `Did you mean V(vout)?`와 선택 버튼을 표시한다. 사용자가 선택하기 전 원래 trace를 유지하며 선택/수정 후 승인을 해제한다. |
| **Repeated AC condition entry**: 단일 AC 후 parameter sweep에서 Target/Reference/범위/Points 재입력 | 업로드 bytes의 SHA-256 및 analysis type별로 마지막 성공한 review 조건을 session에 보관한다. 새 요청에 빠진 필드만 초기값으로 채우고 재사용 필드를 안내한다. 새 명시값이 우선하며 다른 회로/분석에는 자동 전파하지 않는다. 실패한 분석은 성공 history를 덮어쓰지 않는다. |
| **Oversized graph**: 부모 영역 전체 폭으로 표시 | 공통 `show_graph/style_graph`로 데스크톱 83% 중앙 영역, 동일한 figure 폭/글꼴 최소 크기/DPI를 관리한다. 각 그래프의 원래 종횡비는 유지한다. 좁은 화면에서는 사용 가능한 폭으로 축소한다. |
| **RAW/LOG table clutter**: Windows 절대 경로가 비교 표 폭을 차지 | 표시용 복사 테이블에서 RAW/LOG/Directive/Notes 및 중복 Parameter Value 열을 제외한다. Summary의 원본 evidence와 파일은 유지하고 **Point Details / Evidence**에서 point별 전체 RAW/LOG 경로, directive, 상태/notes를 확인한다. 일반 rerun에서도 Evidence가 남는다. |
| **DC requested-point visibility**: `3.55 V에서`를 놓치고 Min/Max만 표시 | DC parser에서 sweep source/range/step과 requested point를 독립적으로 인식한다. 기존 `read_dc_result`의 보간값을 **Value at V2 = 3.55 V** 카드로 표시하며 일반 metric과 중복 표시하지 않는다. |

### 표시와 데이터 경계

- `human_value()`는 UI 표시용 engineering prefix 및 소수 3자리를 사용한다. 예: 13129.469 Hz → 13.129 kHz, 6274.788 Hz → 6.275 kHz, 0.0199997 V → 20.000 mV. Non-finite/미검출은 Not available이다. 1000.000 mV 같은 rounding 경계는 1.000 V로 표시한다. 기존 수치/result 객체/원본 비교 테이블/Analysis Summary/JSON 값은 그대로 보존하며 표시 문자열을 계산 입력으로 쓰지 않는다.
- Graph: Streamlit columns `[0.085, 0.83, 0.085]`, gap=None. 기존 figure 높이/폭 비율을 보존하면서 폭 8 inch로 통일하고 160 DPI PNG로 표시한다. title 최소 12 pt, axis/tick 최소 11 pt, legend 최소 10.5 pt. PNG의 bbox를 잘라내지 않아 종횡비를 유지한다. `st.pyplot`의 savefig kwargs deprecation이 확인되어 직접 PNG buffer를 만든 뒤 `st.image(width='stretch')`로 표시한다. 실제 graph evidence 저장 경로도 유지한다.
- Trace 후보는 exact name이 없을 때 유일한 case match 또는 전압 node의 v 접두어 한 글자 차이만 허용한다. 편집 거리로 임의 이름을 추측하거나 I(M1)을 Id(M1)로 바꾸지 않는다. ASC label 목록은 전체 netlist/RAW inventory가 아니므로 목록에 없는 모든 trace를 실행 전에 금지하지 않는다. 실제 RAW의 authoritative missing-trace 검사/오류는 기존 분석기가 유지한다.
- 재사용 필드는 AC Target/Reference/Start/Stop/Points/Sweep Type, Transient signal/time 설정, DC signal/source/range/step이다. Measurement 선택과 이전 requested point를 새 요청에 자동 추가하지 않는다. 명시된 Target/Reference와 AC start/stop labels/points/sweep를 우선 처리하며 UI는 항상 review/edit/approve를 요구한다. History는 같은 세션에만 존재하고 파일 내용 변경 시 분리된다.
- 사용자 예문 `V2를 3.4 V부터 3.7 V까지 0.01 V 간격으로 DC sweep하고 V(vout)의 변화를 보여줘. 3.55 V에서의 V(vout)도 구해줘.`는 source=V2, start=3.4 V, stop=3.7 V, step=0.01 V, point=3.55 V, target=V(vout)로 해석된다. 후속 point-only 요청도 이전 성공한 DC 조건이 있는 경우에만 해당 source/range 초기값을 재사용한다. 범위 밖 point는 기존 validation에서 차단하며 extrapolation하지 않는다.

### 검증 결과

- `python -m py_compile app.py ui_helpers.py dc_analysis.py tests/test_ui_helpers.py tests/ux_preview.py tests/verify_ux_layout.py`: 통과.
- 최종 `python -X utf8 -m unittest discover -s tests -p "test_*.py"`: **121개 모두 통과, 108.467초**. 기존 104개와 신규 UX 17개다. DC source/point 분리, 보간값 card, 추천 승인/no silent substitution, 성공 AC→Sweep 재사용, 새 조건 우선, 다른 회로/analysis 배제, 실패 history 배제, Evidence rerun 접근, 단위/원본 정밀도 보존, 그래프 5종 rendering/종횡비를 포함한다.
- `tests/verify_ux_layout.py`: 실제 설치 Edge의 headless 브라우저에서 AC/Transient/DC/parameter metric/AC overlay **5종** 검증 통과. 1440px viewport의 부모 폭 1280px에서 image=1062.40625px, ratio=0.8300048828125, 중앙 오차=0px. 390px viewport에서는 image=358px, 좌우 여백 16px, 중앙 오차=0px이며 모든 그래프와 페이지에 가로 overflow가 없었다. 이미지 자연 종횡비와 화면 비율도 일치한다.
- Browser 증거: `simulation_output/ux_layout_verification_7071b21a97894143af2a77a072bc9784/geometry.json`, `desktop.png`, `mobile.png`. 스크린샷도 확인했다. 좁은 화면의 글자는 이미지와 함께 축소되며 확대/장문 legend 개선은 후속 UX 검토 대상이다. Playwright 1.63.0은 이 선택적 개발 검증을 위해 가상환경에 설치했으며 앱 실행 의존성으로 추가하지 않았다.
- 실제 `app.py` Streamlit 서버를 임시 port **58735**에서 시작해 health HTTP 200/ok 및 root HTTP 200을 확인하고 검증용 서버만 종료했다. 신규 UI 및 기존 사용자 승인·AI 상태 동작은 AppTest로 확인했다.
- 실제 Transient 회귀 첫 실행은 simulation/RAW/수치 검증 이후, 검증 스크립트가 앱의 기존 `transient_waveform.png`를 덮어쓰는 단계에서 Windows `OSError: [Errno 22] Invalid argument`로 중단됐다. 해당 파일은 이미 정상 크기로 존재했고 읽기 전용이 아니었다. OS 수준의 일시적 원인은 확정하지 않았다. 앱 evidence를 덮어쓸 필요가 없으므로 Transient/DC 검증은 기존 이미지 존재를 확인한 뒤 별도 `*_verification.png`에 저장하도록 보완했다. Transient/DC 실제 재검증은 모두 통과했다. 앱의 저장/계산 로직에는 변경이 없다.
- 실제 DC 분압 fixture를 메모리에서 V2/V(vout) 이름으로 바꾼 복사본에 사용자 예문을 적용했다. `.dc V2 3.4 3.7 10m`, point=3.55 V가 실행됐고 **Value at V2 = 3.55 V** 카드가 **1.775 V**를 표시했다. RAW 기반 기존 보간값 **1.774999976158142 V**는 Summary에 그대로 남았다. 이는 검증용 분압 회로 결과이며 사용자 MOSFET 회로의 결과라고 간주하지 않는다.
- 최종 실제 `verify_integration.py --real-ltspice`, `verify_transient_integration.py --real-ltspice`, `verify_dc_integration.py --real-ltspice`, `verify_parameter_sweep_integration.py` **4종 모두 exit 0**. 승인 전 실행 차단, 원본 ASC bytes 보존, 실제 directive/RAW/LOG/graph, trace 오류와 simulator 실패 처리, Analysis Summary 검사도 통과했다. 감사 로그 및 종료 코드: `simulation_output/prompt_009a_regression_9d2d235eebee48b49dce73a83b10d6a9/`. 최초 Transient 실패 로그도 보존하고 재실행 로그는 `.retry.log`로 구분했다.
- 실제 Parameter AC/Transient/DC 및 중간 실패 scenario 총 12 points 중 정상 simulation 11건, 의도한 모델 오류 1건을 검증했다. 실패 후 마지막 point까지 실행됐고 5kΩ BW는 null로 유지됐다. 화면의 비교 표에는 RAW/LOG columns가 없고 Point Details / Evidence에는 생성된 전체 경로가 있었다. 실제 결과/그림/Summary: `simulation_output/parameter_sweep_verification_15514f0f8807461f81ce3e39196973ff/`.
- 검증 스크립트 보완 이후 `app.py`, helper/parser, UX 및 수정한 세 integration 스크립트 문법 검사를 다시 통과했다. 전체 unit/AppTest 수는 **121개**, 별도 실제 LTspice integration **4종** 및 실제 브라우저 layout 검증 **1종**이다. 외부 LLM/API 호출은 수행하지 않았다.

### 남은 UX TODO / 한계

- 이번 요청의 필수 항목은 완료했다. 후속 사용자 테스트에서 아주 좁은 화면의 그래프 확대 접근성과 긴 legend의 가독성을 검토한다. 현재 PNG는 비율을 유지하며 화면 폭에 맞게 줄어든다.
- Trace 추천은 유일한 case/v-prefix 후보로 제한한다. ASC FLAG만으로 자동 생성 node와 모든 current trace를 알 수 없으며, 임의 별칭 확정은 하지 않는다. 더 다양한 자연어 조건 표기는 별도 범위로 검토한다.
- 계산 알고리즘, Parameter Sweep 실행, Summary schema, 기존 LLM/API 기능은 유지했다. 새 분석/report 기능은 추가하지 않았다.

---

## 2026-09-17 — Prompt 010A — GitHub Public Repository Preparation

- 현재 기능/기존 변경사항을 유지하고 공개용 문서와 제외 규칙만 준비했다. SPEC, problem definition, 양쪽 원본 로그, 코드·tests·requirements와 simulation_output 구조를 읽었다. README에는 구현된 AC/Transient/DC/R/C sweep, deterministic measurements, Summary, OpenAI/mock layer와 한계를 구분했다. AI-assisted 개발의 scope 결정과 실제 사용자 검증 흐름을 설명했다.
- `README.md`, `.gitignore`, `requirements.txt`, `test_ltspice.py.example`, `docs/validation.md`, `docs/publication-review.md`, `docs/github-issues.md`, `docs/devlog/README.md`, `docs/devlog/09-real-user-testing.md`, `docs/screenshots/README.md`를 추가했다. 기본 requirements는 설치된 직접 의존성 버전이며 fresh install을 검증한 lockfile은 아니다. 기존 requirements-llm.txt는 보존했다.
- `.gitignore`는 개인 업로드/결과·RAW/LOG·secret·venv/cache·IDE 임시 파일을 제외한다. 개인 외부 ASC 경로가 있는 레거시 `test_ltspice.py`는 내용을 바꾸지 않고 명시적으로 공개 제외했다. 상대 경로 설정 template을 제공했다. 모든 `tests/` 코드와 작은 공개 ASC fixture 2개는 포함된다. 개인 MOSFET 원본은 공개하지 않아 해당 integration은 fresh clone에서 즉시 재현되지 않음을 문서화했다.
- 초기 47개 프로젝트 파일과 생성 파일 1,658개 구조, 텍스트/RAW header 1,450개를 점검했다. 실제 credential/email은 확인되지 않았다. 개인 경로가 있는 로컬 스크립트와 생성 폴더는 공개 제외했다. 테스트 fake key/path, 숫자 검증 token 메타데이터는 실제 secret과 구분했다. 이미지 255개는 텍스트 검사에서 제외했으며 기존 screenshots 4개도 검토 전 공개 제외했다. 상세 파일/행과 한계는 publication-review에 기록했다. secret 값은 출력/문서에 복사하지 않았다.
- 기존 로그에서 실제 개인 사용자 절대 경로는 발견하지 못했고 증거 경로는 이미 project-relative였다. 과거 기록을 삭제하거나 재작성하지 않았다. 블로그 index는 00–09 outline과 source section을 연결하며 09 글만 실제 관찰·오류·수정·121 tests/4종 integration 증거를 기반으로 작성했다. 스크린샷은 이름/계획만 만들고 이미지를 생성하지 않았다.
- AC/Transient scalar 검증과 DC fixture 검증은 존재하지만 동일 조건의 AC–Transient / DC–Transient 물리적 교차검증 완료 근거는 찾지 못했다. README에서 완료로 과장하지 않고 조건과 추가 검증 Issue를 명시했다. 실제 API smoke 미수행도 유지했다.
- 공개 준비 검증은 Markdown local links/anchors·fence, ignore 포함/제외, 기존 Python/tests/fixtures의 SHA-256 불변 여부다. Git executable 및 .git metadata가 없어 실제 git check-ignore/index/history 검사는 하지 못했다. 단순 ignore 규칙 평가로 확인하고 게시 전 Git 검증은 사람이 수행할 항목으로 기록했다. Python source/test logic은 변경하지 않아 121 tests를 이번에 재실행하지 않았다.
- GitHub remote/issue 생성, push, API/LLM 호출, simulation 재실행, UI/계산 알고리즘 변경은 수행하지 않았다. 후속 TODO: Git staged/history 확인, 소유권/LICENSE 결정, 공개 MOSFET fixture, fresh-clone 설치, 검토한 screenshot 추가.

- 최종 공개 준비 검증: Markdown 9개 문서의 로컬 링크/anchor 26개 통과, 기존 source/test/fixture 38개 SHA-256 동일, 두 원본 로그의 과거 바이트 prefix 보존, 중요 코드/tests의 의도치 않은 ignore 0개. 최종 57개 프로젝트 파일 포함 스캔에서 알려진 credential 형식/email 일치 0건. 실제 사용자 경로는 공개 제외된 초기 스크립트와 생성 데이터에만 남는다. Git 미설치에 따른 index/history 검증 제한은 유지된다.

### Prompt 010A 최종 검증 재개 및 완료

- 기존 생성 파일을 유지하고 마지막 audit를 다시 실행해 정상 종료를 확인했다. 프로젝트 57개/생성 파일 1,658개, 텍스트·RAW header 1,460개 검사. 알려진 실제 credential 형식 및 이메일 일치 0건. key/password/token 후보는 기존 synthetic test 값과 숫자 인용 메타데이터로 확인했다. 개인 경로는 공개 제외된 local script/생성 데이터, 테스트의 가상 경로와 구분했다. secret 값은 출력하지 않았다.
- simulation_output/publication_audit의 helper·baseline·scan 결과는 공개 제외 임시 도구로 유지했다. .env, secrets.toml, venv, simulation 입력/출력, RAW/LOG, local script와 미검토 screenshot 제외 규칙을 확인했다. 실제 Git index/history 검증을 완료한 것으로 주장하지 않는다.
- requirements.txt의 7개 패키지는 core 직접/하위 실행 의존성이다. 설치 metadata에서 spicelib는 PyLTSpice, pandas는 Streamlit, Pillow는 Streamlit/Matplotlib 의존성임을 확인했다. 버전은 유지하고 주석을 정확히 고쳤다. README에 optional requirements-llm.txt 설치 명령과 mock/API 설정 분리를 명시했다. 새 환경 설치는 이번에 수행하지 않았다.
- README의 121 tests/4종 integration은 기존 검증 기록이며 이번 재실행 주장 없음. AC–Transient/DC–Transient 직접 물리 교차검증과 actual API smoke는 미완료 한계로 유지했다. publication-review에 Git 설치 → init → status/check-ignore → dry-run/staged review → secret scan → commit/빈 remote → push 직전 history scan 순서를 추가했다. 명령은 문서화만 했다.
- 최종 local links/anchors 26개 통과, Markdown 9개 검사, 기존 Python/tests/fixture 38개 SHA-256 동일, 과거 로그 prefix 보존, 의도치 않은 중요 파일 ignore 0개. 앱 소스/tests 수정 및 전체 regression 재실행 없음. 010A의 로컬 준비/검증/기록을 완료했다. 실제 Git 초기화/add/remote/push 및 LLM/API 호출은 하지 않았다.

---

## Prompt 010B — README Presentation Polish

- README를 Why I Built It → Workflow → Features → Validation → AI-Assisted Development → Development Log → Getting Started → Project Structure → Current Limitations / Future Work 순서로 정리했다. 설치/requirements 설명은 내용 그대로 뒤로 이동했고, 상단 소개를 사용자 schematic·자연어 review/approval·Python deterministic analysis의 3문장으로 다듬었다. 기능 의미를 유지하며 혼합 표현 일부만 정리했다.
- 보고된 깨진 문장은 현재 로컬 원문과 렌더링에서 발견되지 않았다. 공개 GitHub 페이지 조회는 실패해 원격 현상의 원인을 단정하거나 해결했다고 주장하지 않는다. Markdown 표/inline code/link를 검사하고 EOF의 불필요한 빈 줄을 정리했다. 가짜 이미지/placeholder 링크를 추가하지 않았다.
- Markdown parser와 headless Edge의 실제 HTML DOM 검사 통과: 요청한 9개 섹션, 검증 표 4행, 기존 코드 블록/inline code 유지, 이미지 0개. 전체 공개 문서 9개의 상대 링크/anchor 26개 통과. Validation 및 Getting Started 본문은 이전과 동일하며 121 tests·실제 integration 수치와 미완료 API/물리 교차검증 한계를 유지했다.
- 기존 Python/tests/fixture와 requirements 파일 총 40개 SHA-256 동일. 앱/tests/requirements 내용, simulation, LLM/API는 변경·실행하지 않았다. 임시 렌더러/검증 결과는 공개 제외된 simulation_output/publication_audit에만 보관했다. 공개 문서 변경은 README와 두 로그뿐이다.

---

## Prompt 010C — README Screenshot Integration

- 사용자가 제공한 docs/screenshots의 이미지 5장을 직접 확인하고 Workflow 뒤/Features 앞에 Screenshots를 추가했다. Trace suggestion와 AC 2장은 기본 표시, Parameter Sweep·Transient·DC 3장은 details 펼치기로 배치했다. 화면에 보이는 기능만 caption/alt로 설명하며 기존 Validation/설치 본문은 그대로 유지했다.
- HTML width=800, 중앙 정렬, 높이 자동, 원본 이미지 링크를 통일했다. GitHub와 유사한 responsive image CSS를 적용한 로컬 Edge에서 desktop 1280px의 이미지 폭 800px, mobile 390px의 폭 358px를 확인했다. 5장 모두 로딩·종횡비·컨테이너 내 표시 및 펼치기 동작 통과. 실제 GitHub 배포 화면 검증은 아니다. 상대 링크/이미지 참조 41개 정상.
- 시각 검토에서 개인 경로·사용자명·이메일·secret은 보이지 않았고 PNG metadata는 색상/gamma/DPI 항목이었다. 이미지 생성·편집 없이 원본 5개를 보존했다. DC curve screenshot은 기존 분압 fixture의 1.775 V 검증과 같은 사례로 주장하지 않는다. docs/screenshots/README.md를 실제 파일명/용도/검토 결과로 갱신했다.
- 기존 source/tests/fixture/requirements 40개 및 이미지 원본 5개 SHA-256 동일. 소스/tests/requirements 변경, simulation, commit/push는 수행하지 않았다. 공개 문서는 README·스크린샷 안내·두 로그만 수정했다. 제공된 PNG 5개는 untracked 상태를 유지하며 staging하지 않았다.
