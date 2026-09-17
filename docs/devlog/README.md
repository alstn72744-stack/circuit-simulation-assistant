# Development Blog Index

원본 [Development Log](../development-log.md)와 [Prompt Log](../prompt-log.md)는 순차 개발 기록으로 보존합니다. 아래는 포트폴리오 글을 위한 outline입니다. **09만 이번 단계에서 작성했으며**, 나머지는 제목·핵심 내용·원본 section을 정리한 계획입니다.

| 글 | 핵심 내용 | 작성에 사용할 source section |
| --- | --- | --- |
| 00 Problem Definition & Scope | 반복 실험 작업, current mirror/feedback 복잡도, schematic 생성 제외 결정 | [Problem Definition](../../problem-definition.md), [SPEC](../../SPEC.md), Development Log의 Project Planning |
| 01 Initial Prototype | 자연어 요청, review/edit, 승인 경계, 최초 UI | Prompt Log의 Prompt 001 — Initial Interface |
| 02 LTspice Integration | 성공 smoke 방식, 복사본 실행, RAW/LOG, 실제 실패 처리 | 양쪽 로그의 Streamlit-LTspice Integration / Prompt 002 |
| 03 AC Analysis | 1 MHz parsing 오류, directive 적용, complex ratio, log-frequency interpolation | AC Directive Generation / AC Result Analysis; Prompt 003·004 |
| 04 Transient Analysis | Vpp와 정상상태, waveform 적용 조건, RAW Offset 수정 | Transient Analysis / Prompt 005 |
| 05 DC Sweep | source/signal 구분, requested-point 보간, matching error, fixture 검증 | DC Sweep Analysis / Prompt 006 |
| 06 Parameter Sweep | parsing → component 검증 → R/C 반복 실행, 실패 point와 비교 | Prompt 007A·007A-1·007B 및 동일 개발 section |
| 07 Analysis Summary | measured/derived/warning 분리, deterministic trend, 증거 참조 | Analysis Summary Builder / Prompt 007C |
| 08 AI Interpretation Architecture | path sanitization, fact/inference 경계, mock/OpenAI provider, 수치 일치 검사의 한계 | Prompt 008A·008B 및 동일 개발 section |
| [09 Real User Testing & UX Refinement](09-real-user-testing.md) | 테스트 통과 후 발견된 trace/조건 반복/graph/table/DC point UX와 회귀 검증 | Core UX Polish / Prompt 009A, Real User Testing Findings |

각 글에는 문제 → 선택한 범위 → 구현 판단 → 실패·수정 → 검증 → 한계 순서를 권장합니다. 로컬 증거 파일명은 필요할 때 상대 경로로 설명하고, 개인정보를 검토한 이미지만 [screenshots](../screenshots/README.md)에 추가합니다. [후속 Issue 후보](../github-issues.md)도 별도로 관리합니다.
