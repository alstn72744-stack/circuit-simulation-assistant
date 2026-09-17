# Problem Definition

## Background

LTspice를 이용한 회로 실습에서는 회로 구성부터 시뮬레이션 조건 설정, 결과 측정까지 반복적인 수작업이 많이 발생한다.

특히 회로 이론 자체보다 LTspice 사용법을 매번 다시 찾아보는 데 시간이 많이 들었다.

## Pain Points

### 1. 회로 구성의 반복 작업

회로를 구성할 때 필요한 소자를 하나씩 찾아 배치해야 하고,
저항, 커패시터, 전압원 등의 값을 바꿔가며 여러 번 시뮬레이션해야 한다.

Parameter를 비교하는 실험에서는 같은 작업을 반복하게 되어 번거롭다.

### 2. Simulation Command 작성의 어려움

AC Analysis, DC Sweep, Transient Analysis를 수행할 때
LTspice command의 문법과 parameter 순서를 정확히 기억하기 어렵다.

예를 들어,

- 어떤 명령어를 사용해야 하는지
- start / stop 값의 순서가 무엇인지
- step 값을 어디에 넣어야 하는지
- AC simulation의 decade 설정은 어떻게 하는지

등을 매번 다시 찾아봐야 했다.

회로를 분석하는 것보다 simulator 사용법을 확인하는 데 불필요한 시간이 소비되었다.

### 3. Simulation Result의 수동 측정

Simulation이 끝난 후에도 원하는 전압이나 전류를 직접 probe해야 한다.

결과가 그래프로 표시되더라도 필요한 성능 지표가 자동으로 계산되지 않기 때문에
사용자가 직접 값을 확인해야 한다.

### 4. 주요 성능 지표를 직접 찾아야 함

AC response에서 -3 dB bandwidth를 구하는 경우처럼,
그래프를 확대하면서 특정 지점을 직접 찾아야 하는 작업이 필요하다.

Gain, Bandwidth, Rise Time 등의 값을 반복적으로 수동 측정하는 과정은 시간이 많이 들고
사용자마다 측정 결과가 조금씩 달라질 가능성도 있다.

## Initial Challenge

회로의 기본 정보와 사용자가 원하는 분석 조건을 입력하면,

1. 적절한 LTspice simulation command를 생성하고
2. 반복적인 simulation parameter 변경을 자동화하며
3. simulation 결과에서 필요한 성능 지표를 자동으로 추출하고
4. 결과를 이해하기 쉬운 형태로 정리할 수 있을까?

## Goal

사용자가 LTspice 명령어나 결과 측정 방법을 매번 찾아보지 않아도,

회로 설계와 결과 해석 자체에 더 집중할 수 있도록
LTspice simulation workflow를 자동화하는 도구를 개발한다.

정량적인 계산은 Python 기반으로 수행하고,
AI는 사용자의 자연어 요구를 simulation 조건으로 변환하거나
결과를 설명하는 역할을 담당한다.

최종 설계 판단은 사용자가 수행한다.