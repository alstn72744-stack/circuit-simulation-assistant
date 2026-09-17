# 09 — Real User Testing & UX Refinement

자동화 테스트를 통과해도 실제 사용자가 요청을 입력하고 결과를 읽는 과정에서는 다른 문제가 드러났습니다. Prompt 009A 전에는 104개 테스트와 실제 simulation workflow가 검증돼 있었지만, 실제 사용에서는 이름을 추측해야 하거나 같은 조건을 반복 입력하는 불편이 남았습니다.

이번 단계는 계산 알고리즘을 확장하지 않고 이 흐름을 다듬는 데 집중했습니다. 사용 한도로 중단됐던 코드를 재구현하지 않고, 저장된 변경사항과 실패하는 테스트를 확인한 뒤 이어서 완료했습니다.

## Findings and changes

| 관찰 | 개선 | 유지한 경계 |
| --- | --- | --- |
| 사용자는 V(out)을 요청했지만 RAW에는 V(vout)이 있었음 | 유일한 case/단순 v-prefix 후보에 `Did you mean V(vout)?` 추천 | 자동 대체하지 않음. 사용자가 선택/수정하면 승인 해제 후 재검토 |
| 단일 AC 직후 Parameter Sweep에서 같은 조건을 다시 입력 | 동일 circuit bytes hash + analysis type의 이전 성공 조건을 누락 필드 초기값으로 재사용 | 새 명시값 우선, 다른 회로/분석이나 실패 결과에서 가져오지 않음, 자동 실행 없음 |
| graph가 desktop 화면을 지나치게 차지 | 공통 helper로 약 83% 폭 중앙 정렬, 원래 종횡비와 글꼴 최소 크기 유지 | 좁은 화면은 가용 폭으로 축소, 계산과 curve data 불변 |
| RAW/LOG 절대 경로가 비교 표를 넓힘 | 기본 표에서 경로 제외, point별 Details / Evidence에 전체 경로 보존 | 파일과 Summary evidence 삭제 없음 |
| DC 요청의 특정 지점 값이 눈에 띄지 않음 | source와 requested point를 구분하고 별도 result card 표시 | 기존 deterministic interpolation 사용, 외삽 없음 |

표시 단위도 `6274.788 Hz → 6.275 kHz`, `0.0199997 V → 20.000 mV`처럼 읽기 쉽게 바꿨습니다. 변환은 화면에만 적용하며 JSON과 Analysis Summary의 원본 수치를 반올림하지 않습니다.

## A parsing failure exposed by the workflow

> V2를 3.4 V부터 3.7 V까지 0.01 V 간격으로 DC sweep하고 V(vout)의 변화를 보여줘. 3.55 V에서의 V(vout)도 구해줘.

이 요청은 sweep source **V2**, requested point **3.55 V**로 해석돼야 합니다. 재개 후 검사에서 기존 source regex가 `V(vout)` 안의 `vout`을 source로 오인하는 문제가 확인됐습니다. source 토큰 경계를 보완하고 `3.55 V에서` parsing을 DC parser로 모아 UI 중복 처리를 없앴습니다.

실제 분압 검증 회로에서는 **Value at V2 = 3.55 V** 카드가 **1.775 V**를 표시했고, Summary에는 **1.774999976158142 V**가 남았습니다. 이는 분압 fixture 결과이며 MOSFET 증폭기의 측정값이 아닙니다.

## Verification

- **121 unit/AppTest passed**: 기존 104개 + UX 17개. 추천 선택과 재승인, silent substitution 없음, 조건 재사용·명시값 우선·회로/분석 분리, Evidence, 단위, DC card, graph rendering을 포함합니다.
- 실제 **AC / Transient / DC / Parameter Sweep integration 4종** 재검증 통과. 승인 차단, 원본 ASC 보존, RAW/LOG와 Summary, 실패 후 계속 실행을 확인했습니다.
- 실제 Edge: desktop 1440px viewport에서 부모 폭 1280px 대비 graph 1062.40625px(**83.0005%**), 중앙 오차 0px. 390px viewport에서는 358px, 좌우 여백 16px, 가로 overflow 없음. AC/Transient/DC/parameter metric/AC overlay 5종을 확인했습니다.
- 실제 Streamlit startup health/root HTTP 200 확인. Transient 재검증 중 evidence PNG 덮어쓰기에서 발생한 Windows 오류는 앱 증거를 보존하고 검증 이미지를 별도 파일로 저장하도록 테스트를 보완한 뒤 통과했습니다.

테스트는 동작 경계를 지키는 데 도움이 됐고, 실제 사용은 무엇을 기본값으로 보여주고 어디에 결과를 배치해야 하는지 드러냈습니다. 다음 UX 후보는 좁은 화면의 그래프 확대 접근성과 긴 legend 가독성입니다.

## Sources

- [Development Log: Prompt 009A](../development-log.md#2026-09-17--core-ux-polish-after-real-user-testing-prompt-009a)
- [Prompt Log: Prompt 009A](../prompt-log.md#prompt-009a--core-ux-polish-after-real-user-testing)
- 로컬 검증 증거: `simulation_output/prompt_009a_regression_9d2d235eebee48b49dce73a83b10d6a9/`, `simulation_output/ux_layout_verification_7071b21a97894143af2a77a072bc9784/`. 공개 저장소에는 생성 파일을 포함하지 않습니다.
