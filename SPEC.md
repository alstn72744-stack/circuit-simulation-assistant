# Circuit Simulation Assistant — SPEC v0.1

## 진행 방식

- AI와 논의하면서 SPEC을 단계적으로 작성한다.
- 한 번에 한 섹션씩 논의한다.
- 질문은 한 번에 하나씩 진행한다.
- 이미 작성된 내용도 필요하면 수정한다.
- 사용 기술, 확인 시나리오, 완성 기준은 AI가 먼저 제안하고 사용자가 승인하거나 수정한다.
- 실제 개발 과정에서 SPEC과 다른 판단이 필요해지면 변경 이유를 기록하고 SPEC을 업데이트한다.


## 개발 환경 / 사전 지식

- OS: Windows
- 개발 환경: VS Code
- 개발 언어: Python
- 회로 시뮬레이터: LTspice
- Python 개발 경험: 초급
- LTspice 사용 경험:
  - 회로 실습
  - AC / DC / Transient simulation 경험
  - 기본적인 회로 구성 및 simulation 경험


# 1. 앱 설명

## 앱 이름

Circuit Simulation Assistant (가칭)


## 개요

회로를 구성하고 simulation을 실행한 뒤 결과를 확인·분석하는 과정에서 발생하는

- simulation command 작성
- simulation 조건 설정
- 반복적인 parameter 변경
- 결과 측정
- 결과 분석

등의 반복 작업을 줄여주는 회로 simulation 보조 도구이다.

사용자는 회로 schematic 자체는 LTspice에서 직접 작성한다.

이후 원하는 simulation과 분석 내용을 자연어로 입력하면 프로그램이 이를 해석하고,
사용자의 최종 확인을 거쳐 LTspice simulation을 실행한다.

Simulation 결과에서 필요한 데이터를 자동으로 추출하고,
Python을 이용해 정량적인 값을 계산한 뒤,
AI가 결과를 해석하고 추가적인 insight를 제공한다.


## 타겟 사용자

초기 타겟은 LTspice를 이용해 회로 실습이나 기초적인 회로 설계를 수행하는
전자·전기공학 전공 학생이다.

특히 다음 과정에서 불편을 느끼는 사용자를 대상으로 한다.

- SPICE simulation command의 문법을 매번 찾아봐야 하는 경우
- AC / DC / Transient 등의 parameter 입력 순서를 매번 확인해야 하는 경우
- 소자 값을 바꿔가며 반복해서 simulation해야 하는 경우
- waveform에서 원하는 값을 직접 probe해야 하는 경우
- -3 dB bandwidth 등의 값을 그래프를 확대하면서 직접 찾아야 하는 경우
- simulation 결과를 해석하고 report로 정리해야 하는 경우


## 핵심 기능

사용자가 작성한 LTspice 회로를 기반으로 자연어로 원하는 분석 조건을 입력하면,

자연어 요청
→ simulation 조건 구조화
→ 사용자 검토 및 수정
→ 사용자 최종 승인
→ LTspice simulation 설정 생성
→ LTspice 자동 실행
→ 결과 데이터 추출
→ 주요 성능 지표 자동 계산
→ AI 결과 해석
→ report에 사용할 수 있는 형태로 결과 정리

의 workflow를 제공한다.

AI는 자연어 이해와 결과 해석에 사용한다.

Gain, bandwidth, rise time 등 정량적인 계산은 가능한 한 Python 기반의 deterministic한 방식으로 수행한다.

최종 simulation 실행과 회로 설계 판단은 사용자가 수행한다.


## 향후 확장 방향

초기에는 LTspice 기반으로 개발한다.

장기적으로는

- 보다 다양한 수준의 회로 설계 사용자 지원
- 다른 circuit simulation tool 지원
- 회로 자동 생성
- parameter optimization
- 자동 report 생성

등으로 확장할 가능성을 열어둔다.

단, 이러한 기능은 현재 초기 개발 범위에는 포함하지 않는다.


# 2. 사용자 입력 및 동작 흐름

## 회로 입력

사용자는 먼저 LTspice에서 직접 schematic을 작성하고 회로 파일을 저장한다.

초기 프로젝트에서는 자연어를 기반으로 임의의 회로 schematic을 자동 생성하지 않는다.

이는 current mirror, feedback loop 등 복잡한 topology까지 일반화할 경우
프로젝트 범위가 지나치게 커지는 것을 방지하기 위한 결정이다.


## Simulation 요청

사용자는 앱에서 LTspice 회로 파일을 선택한다.

이후 자연어로 원하는 simulation 및 측정 조건을 입력한다.

예:

"V(out)의 AC simulation을 10 Hz부터 100 MHz까지 돌리고
gain과 -3 dB bandwidth를 구해줘."


## 자연어 요청 구조화

프로그램은 사용자의 자연어 입력을 바로 실행하지 않는다.

AI가 먼저 요청을 구조화된 simulation 조건으로 변환한다.

예:

Analysis Type: AC

Sweep Type: Decade

Target Node: V(out)

Start Frequency: 10 Hz

Stop Frequency: 100 MHz

Measurement:
- Gain
- -3 dB Bandwidth


## 사용자 검토

AI가 해석한 simulation 조건은 실행 전에 사용자에게 표시한다.

사용자는

- analysis 종류
- simulation 범위
- target node / current
- parameter
- 측정 항목

등을 직접 확인하고 수정할 수 있다.


## 실행 승인

AI가 해석한 조건은 자동으로 실행하지 않는다.

사용자가 구조화된 simulation 조건을 최종 검토하고
명시적으로 승인한 경우에만 LTspice simulation을 실행한다.

사용자의 승인 없이는 LTspice가 실행되지 않는다.


## Simulation 실행 이후

사용자가 실행을 승인하면 프로그램은 다음 순서로 처리한다.

1. LTspice simulation directive 생성
2. LTspice 자동 실행
3. simulation 성공 / 실패 확인
4. simulation result 및 log 추출
5. 필요한 waveform / data 추출
6. 주요 성능 지표 계산
7. 결과 graph 생성
8. AI 결과 해석
9. 추가적인 이상 현상 및 trade-off 분석
10. LTspice waveform 결과 이미지 확보
11. report에 사용할 수 있는 형태로 결과 정리


## Result Display

Simulation 결과는 역할에 따라 구분해서 표시한다.

### Simulation Summary

- Analysis 종류
- Simulation 범위
- 측정 대상
- 주요 simulation 조건

### Measured Results

Python으로 계산된 정량적인 결과를 표시한다.

예:

- Gain
- Bandwidth
- Rise Time
- Fall Time
- Settling Time
- Overshoot
- Voltage
- Current
- Power
- 기타 사용자가 요청한 측정값

### Waveform / Graph

Simulation 결과 graph를 표시한다.

필요한 경우

- 여러 waveform 비교
- 측정 지점
- -3 dB point
- peak
- threshold crossing

등을 표시한다.

### AI Analysis

AI가 다음 내용을 설명한다.

- 사용자가 요청한 결과
- 회로 조건과 결과의 관계
- 주요 trade-off
- 추가로 발견한 이상 현상
- 추가 분석이 필요한 부분

측정 데이터에서 직접 확인되는 사실과
회로 이론을 바탕으로 한 AI의 추론은 구분해서 표시한다.

### LTspice Evidence

실제 LTspice simulation 결과 화면을 이미지 형태로 확보할 수 있도록 한다.

이 이미지는 전자회로 실험 report 등에서 simulation 증빙 자료로 사용할 수 있도록 한다.

### Report Output

Simulation 결과를 report에 옮기기 쉬운 형태로 정리한다.


# 3. 기능 목록

## Simulation 지원

최종적으로 다음 LTspice analysis를 지원하는 것을 목표로 한다.

- Operating Point Analysis (.op)
- DC Sweep (.dc)
- Transient Analysis (.tran)
- AC Analysis (.ac)
- Noise Analysis (.noise)
- Transfer Function Analysis (.tf)
- Fourier Analysis (.four)

추가적으로 반복 simulation을 위해 다음 기능도 지원한다.

- Parameter Sweep (.step)
- Temperature Sweep

모든 기능을 처음부터 동시에 구현하지 않고,
개발 과정에서 순차적으로 추가한다.


## Natural Language Simulation Request

사용자가 자연어로 원하는 simulation을 입력할 수 있다.

AI는 자연어 요청에서 필요한 simulation 조건을 추출한다.

구조화된 simulation 조건은 사용자가 검토 및 수정할 수 있다.


## User Approval

Simulation은 사용자의 최종 승인 이후에만 실행한다.

AI의 해석 결과가 곧바로 LTspice 실행으로 이어지지 않도록 한다.


## LTspice Automatic Execution

프로그램에서 LTspice를 자동으로 실행할 수 있도록 한다.

Simulation 완료 후 result와 log 파일을 프로그램이 인식한다.


## Automatic Measurement

사용자가 요청한 node voltage 또는 device current를 자동으로 추출한다.

Simulation 종류에 따라 필요한 주요 성능 지표를 Python으로 계산한다.

예:

AC Analysis
- Gain
- -3 dB Bandwidth
- Frequency response

Transient Analysis
- Rise Time
- Fall Time
- Settling Time
- Overshoot
- Output Swing

DC Analysis
- Voltage
- Current
- Sweep characteristic

측정 기능은 개발 과정에서 지속적으로 확장한다.


## Comparative Analysis

동일한 회로 구조에서 simulation 조건이나 특정 소자 값을 변경한 여러 결과를 비교할 수 있다.

예:

- 서로 다른 frequency range의 결과 비교
- RD 값 변경 전후 비교
- RC / CL 변경 비교
- Bias 조건 변경 비교
- Parameter sweep 결과 비교

프로그램은 여러 simulation 결과의 주요 수치를 나란히 표시한다.

필요한 경우 다음 변화량을 계산한다.

- Gain
- Bandwidth
- Rise / Fall Time
- Power
- Current
- Overshoot
- 기타 성능 지표

AI는 parameter 변화가 결과에 미친 영향을 분석하고 trade-off를 설명한다.


## AI Result Interpretation

AI는 사용자가 요청한 측정 항목을 우선적으로 설명한다.

또한 simulation 결과에서 유의미한 현상이나 trade-off가 발견되면
사용자가 요청하지 않았더라도 추가 insight를 제공한다.

예:

- Gain 증가와 bandwidth 감소
- 예상보다 큰 overshoot
- Output clipping
- Output swing 제한
- 특정 parameter에 대한 높은 sensitivity
- 비정상적인 waveform
- 예상과 다른 operating region

단,

측정 데이터로 확인된 사실

과

회로 이론을 기반으로 AI가 추론한 내용

을 명확하게 구분한다.


## Simulation Error Diagnosis

Simulation이 실패하면 단순히 실패 여부만 표시하지 않는다.

LTspice의 log 및 error message를 읽어 가능한 원인을 분석한다.

예:

- Floating node
- Convergence failure
- Missing device model
- Invalid simulation directive
- 잘못된 node reference
- 잘못된 parameter
- 기타 LTspice error

프로그램은 다음 내용을 구분하여 표시한다.

1. LTspice가 실제로 출력한 error
2. AI가 추론한 가능한 원인
3. 사용자가 확인할 수 있는 수정 방법

AI의 추론은 확정적인 원인으로 표현하지 않는다.

최종 수정 및 재실행 여부는 사용자가 결정한다.


## Report Generation

초기 버전에서는 simulation 결과를 앱 내부에서
report에 옮기기 쉬운 형태로 구조화하여 표시한다.

포함 내용:

- Simulation 조건
- 주요 측정값
- 결과 graph
- LTspice waveform 이미지
- AI 결과 해석
- 추가 insight

장기적으로는 위 내용을 이용해
Word(.docx) 형식의 실험 report 초안을 자동 생성하는 기능으로 확장한다.


# 4. 사용 기술

## 개발 언어

Python


## 사용자 인터페이스

Streamlit

용도:

- LTspice 회로 파일 선택
- 자연어 simulation 요청
- AI가 구조화한 조건 표시
- 조건 수정
- 실행 승인
- 결과 graph 표시
- 측정값 표시
- AI 분석 표시


## LTspice 연동

LTspice

PyLTSpice

주요 용도:

- 기존 schematic / netlist 기반 simulation
- simulation directive 적용
- parameter 변경
- parameter sweep
- simulation 실행
- result / log 처리


## 데이터 처리 및 수치 분석

NumPy

Pandas

용도:

- waveform data 처리
- Gain / Bandwidth / Rise Time 등 계산
- 여러 simulation 결과 비교


## 그래프

Matplotlib

용도:

- AC / DC / Transient 결과 시각화
- 여러 simulation 조건 비교
- 주요 측정 지점 표시


## AI 기능

LLM API

용도:

- 자연어 simulation 요청 이해
- 요청을 구조화된 simulation 조건으로 변환
- simulation 결과 해석
- 추가적인 이상 현상 및 trade-off 탐지
- LTspice error log 설명

AI가 정량적인 계산을 직접 담당하지 않는 것을 기본 원칙으로 한다.


## LTspice 결과 증빙

Windows 기반 GUI automation 및 screenshot 기능을 검토한다.

목표:

- 실제 LTspice waveform viewer 결과 확보
- simulation 결과를 이미지로 저장
- 실험 report에 사용할 수 있는 증빙 이미지 생성

구체적인 구현 기술은 개발 및 테스트 후 결정한다.


## 향후 Report Export

python-docx 사용을 우선 검토한다.

목표:

- Simulation 조건
- Graph
- LTspice screenshot
- 측정값
- AI 분석

을 포함하는 Word(.docx) report 초안 자동 생성.


# 5. 개발 계획

## Phase 1. 기본 앱 구조

- Streamlit 앱 기본 구조
- LTspice 회로 파일 선택
- 자연어 simulation 요청 입력
- AI가 자연어 요청을 구조화된 simulation 조건으로 변환
- 구조화된 조건 표시
- 사용자 수정
- 사용자 실행 승인


## Phase 2. LTspice 자동 실행

- Python과 LTspice 연결
- Simulation directive 적용
- LTspice 자동 실행
- Simulation 성공 / 실패 감지
- Result file 인식
- Log file 인식


## First Milestone

첫 번째 구현 목표는 Phase 1과 Phase 2까지 완료하는 것이다.

First Milestone 완료 조건:

1. 사용자가 LTspice 회로 파일을 선택할 수 있다.
2. 자연어로 simulation 요청을 입력할 수 있다.
3. AI가 요청을 구조화된 simulation 조건으로 변환한다.
4. 사용자가 구조화된 조건을 검토할 수 있다.
5. 사용자가 조건을 수정할 수 있다.
6. 사용자의 최종 승인 이후에만 simulation이 실행된다.
7. Python에서 LTspice를 자동 실행할 수 있다.
8. Simulation 성공 / 실패를 확인할 수 있다.
9. 생성된 result / log 파일을 프로그램이 인식한다.


## Phase 3. 결과 자동 측정

Simulation result에서 필요한 데이터를 자동 추출한다.

Simulation 종류별 주요 성능 지표를 계산한다.


## Phase 4. 비교 분석

- 특정 component value 변경
- Parameter sweep
- 여러 simulation 실행
- 결과 비교
- 변화량 계산
- Trade-off 분석


## Phase 5. AI 결과 해석

- 측정 결과 요약
- 회로 조건과 결과 관계 설명
- 추가 이상 현상 탐지
- Trade-off 분석
- 측정 사실과 AI 추론 분리


## Phase 6. Error Diagnosis

- LTspice log 분석
- Simulation error 분류
- 가능한 원인 설명
- 해결 방법 제안


## Phase 7. 결과 정리

다음 항목을 앱에서 report-friendly한 형태로 정리한다.

- Simulation Summary
- Measured Results
- Graph
- AI Analysis
- LTspice Evidence


## Phase 8. 향후 확장

- Word(.docx) report 자동 생성
- 다른 simulation tool 지원
- 자연어 기반 임의 회로 생성
- Design parameter optimization


# 6. 확인 시나리오

## Scenario 1. RC Low-Pass Filter AC Simulation

미리 작성된 RC Low-Pass Filter LTspice 회로를 사용한다.

사용자가 자연어로 다음과 같이 요청한다.

"10 Hz부터 1 MHz까지 AC sweep을 돌려줘."

AI가 요청을 구조화한다.

예:

Analysis Type: AC

Sweep Type: Decade

Start Frequency: 10 Hz

Stop Frequency: 1 MHz

사용자가 조건을 확인하고 승인한다.

프로그램이 simulation directive를 생성한다.

LTspice가 자동으로 실행된다.

Simulation이 정상적으로 완료되는지 확인한다.

Result와 log 파일을 프로그램이 인식하는지 확인한다.


## Scenario 2. Common-Source Amplifier

MOSFET 기반 Common-Source Amplifier 회로를 사용한다.

RC filter와 동일한 workflow가 실제 transistor circuit에서도 동작하는지 확인한다.

이를 통해 프로그램이 단순 passive circuit에만 의존하지 않는지 검증한다.


## Scenario 3. AI 해석 결과 수정

사용자가 자연어 simulation 요청을 입력한다.

AI가 simulation 조건을 구조화한다.

사용자가

- Start Frequency
- Stop Frequency
- Simulation type
- Target node
- 기타 parameter

등을 수정한다.

수정된 조건이 최종 simulation에 반영되는지 확인한다.


## Scenario 4. 승인하지 않은 경우

AI가 simulation 조건을 구조화한다.

사용자가 실행을 승인하지 않는다.

LTspice가 실행되지 않는지 확인한다.


## Scenario 5. Simulation 실패

의도적으로 오류가 있는 simulation 조건 또는 회로를 사용한다.

프로그램이 simulation 실패를 감지하는지 확인한다.

LTspice log / error output을 정상적으로 가져오는지 확인한다.

향후 Error Diagnosis 단계에서는
해당 log를 AI가 분석하여 원인을 설명하는 기능까지 검증한다.


# 7. 완성 기준

다음 조건을 만족하면 Circuit Simulation Assistant의 목표 기능을 구현한 것으로 판단한다.


## Natural Language Input

사용자가 자연어로 원하는 simulation 조건을 입력할 수 있다.

AI가 자연어 요청을 구조화된 simulation 조건으로 변환할 수 있다.


## User Validation

AI가 해석한 simulation 조건을 실행 전에 확인할 수 있다.

사용자가 조건을 수정할 수 있다.

사용자의 최종 승인 없이는 simulation이 실행되지 않는다.


## LTspice Integration

사용자가 작성한 LTspice 회로 파일을 프로그램에서 선택할 수 있다.

프로그램이 simulation directive를 생성할 수 있다.

Python에서 LTspice를 자동으로 실행할 수 있다.

Simulation 성공 / 실패를 감지할 수 있다.

LTspice result와 log를 읽을 수 있다.


## Simulation Support

최종적으로 다음 analysis를 지원한다.

- Operating Point
- DC Sweep
- Transient Analysis
- AC Analysis
- Noise Analysis
- Transfer Function
- Fourier Analysis
- Parameter Sweep
- Temperature Sweep


## Automatic Measurement

사용자가 요청한 node voltage 또는 device current를 자동으로 추출할 수 있다.

Simulation 종류에 따라 필요한 주요 성능 지표를 Python으로 계산할 수 있다.

여러 simulation 또는 parameter sweep 결과를 비교할 수 있다.


## Result Analysis

측정값과 waveform을 앱에서 확인할 수 있다.

AI가 사용자가 요청한 결과를 설명할 수 있다.

사용자가 요청하지 않았더라도 유의미한 이상 현상이나 trade-off가 발견되면 추가 insight를 제공한다.

측정 데이터에서 확인된 사실과 AI의 추론을 구분한다.


## Error Diagnosis

Simulation 실패 시 LTspice log를 가져올 수 있다.

Simulator가 실제로 보고한 오류와 AI가 추론한 가능한 원인을 구분한다.

가능한 해결 방법을 사용자에게 제안할 수 있다.


## Report Support

Simulation 조건, 측정값, graph, AI 분석을 report에 옮기기 쉬운 형태로 정리한다.

실제 LTspice waveform 결과 화면을 이미지로 확보할 수 있다.


## Validation

RC Low-Pass Filter에서 정상 동작을 검증한다.

MOSFET 기반 Common-Source Amplifier에서도 동일한 workflow가 정상적으로 작동하는지 검증한다.