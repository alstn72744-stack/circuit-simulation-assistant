# Circuit Simulation Assistant

Natural-language-driven LTspice simulation and deterministic circuit analysis.

사용자가 작성한 LTspice schematic의 시뮬레이션과 결과 분석을 돕는 Windows / Streamlit 프로젝트입니다. 자연어 요청은 rule-based parser로 구조화하고, 사용자의 검토·수정·승인 후 LTspice로 실행합니다. RAW 결과의 정량적 측정·비교는 Python의 deterministic analysis가 담당합니다.

## Why I Built It

전자회로 실험에서 directive 문법 확인, waveform 수동 측정, 소자 값 변경에 따른 반복 시뮬레이션, 결과 비교와 보고서 정리에 드는 시간을 줄이고 싶었습니다.

처음에는 임의의 회로를 자동 생성하는 방식도 고려했습니다. current mirror와 feedback 같은 topology의 복잡성을 고려해, **v1에서는 schematic 작성은 사용자에게 맡기고 시뮬레이션·분석 자동화에 집중**하도록 범위를 줄였습니다. [문제 정의](problem-definition.md)와 [SPEC](SPEC.md)에 이 결정과 장기 계획을 기록했습니다. SPEC의 목표 기능이 모두 구현된 것은 아닙니다.

## Workflow

```text
Natural-language Request
  → Review / Edit
  → User Approval
  → LTspice (execution copy)
  → Deterministic Python Analysis
  → Comparison / Analysis Summary
  → AI Interpretation Layer (optional, explicit user action)
```

## Features

- **AC:** Target / Reference complex transfer function, low-frequency gain, -3 dB bandwidth, frequency graph.
- **Transient:** Input / Output Vpp, voltage gain, output swing; 적용 가능한 step에서 rise / fall time, overshoot, settling time.
- **DC Sweep:** 단일 voltage/current source sweep, min/max, requested-point interpolation, difference / matching error.
- **R/C Parameter Sweep:** 한 소자의 값 목록 또는 start/stop/step 지정, AC/Transient/DC 반복 실행, 비교 표·측정값 그래프·overlay, 실패 지점 기록 후 다음 지점 실행.
- **Analysis Summary:** 측정 사실·파생 사실·경고·비교 결과·증거를 JSON-compatible 구조로 분리.
- **AI Interpretation:** LLM-ready prompt 미리보기·내보내기, OpenAI/mock provider, 수치 일관성 검사. 수치·단위 일치 검사는 물리적 원인이나 해석의 정확성을 증명하지 않습니다.
- **Review UX:** 사용자 승인, 원본 ASC 보존, trace 추천 후 재승인, 같은 회로·분석의 이전 성공 조건 재사용, 전체 RAW/LOG Evidence.

## Validation

2026-09-17 Prompt 009A의 **121 tests passed**(기존 104 + UX 17) 및 실제 AC / Transient / DC / Parameter Sweep integration 4종 통과 기록을 보존합니다. 이번 공개 준비에서는 코드를 변경하거나 simulation을 재실행하지 않았습니다.

| 실제 검증 사례 | 결과 |
| --- | --- |
| MOSFET AC, 10 Hz–1 MHz | Low-frequency gain ≈ **38.983 dB**, -3 dB BW ≈ **6.275 kHz** |
| MOSFET Transient, 10 kHz 입력 | 정상상태 Vpp gain ≈ **47.492 V/V** |
| R1 AC sweep, 500Ω / 1kΩ / 2kΩ / 5kΩ | 비교 결과·trend·5kΩ bandwidth 미검출 기록 |
| DC requested point, 분압 fixture | V2=3.55 V에서 **1.775 V**, 원본 보간 정밀도는 Summary에 유지 |

독립 scalar 계산, synthetic response, 승인 차단, 원본 보존, 실패 처리로 검증했습니다. **AC 저주파 소신호 gain과 10 kHz Transient Vpp gain은 서로 다른 지표**입니다. 현재 기록만으로 동일 동작점·조건의 AC–Transient 및 DC–Transient 물리적 교차검증을 완료했다고 주장하지 않습니다. 비교 조건을 맞춘 검증은 [후속 Issue](docs/github-issues.md)로 남겼습니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p "test_*.py"
```

실제 integration 재현에 필요한 로컬 MOSFET 회로 설정, 공개 fixture 범위와 증거 위치는 [검증 안내](docs/validation.md)를 확인하세요. 개발 기록의 `simulation_output/` 경로는 로컬 증거 참조이며 공개 저장소에는 결과 파일을 포함하지 않습니다.

## AI-Assisted Development

**Problem Definition → SPEC → scoped Codex prompt → implementation → test → real-user validation → refinement** 순서로 진행했습니다. 각 단계에서 범위와 승인 경계를 정하고, 실패 원인을 조사해 실제 LTspice 실행까지 검증했습니다.

정량적인 회로 계산은 LTspice / Python이 담당합니다. AI interpretation은 검증된 Summary를 입력으로 받으며, 측정 사실·파생 사실·추론·불확실성을 구분하도록 설계했습니다.

## Development Log

- [개발 블로그 목차](docs/devlog/README.md) · [실제 사용자 테스트와 UX 개선](docs/devlog/09-real-user-testing.md)
- [원본 Development Log](docs/development-log.md) · [원본 Prompt Log](docs/prompt-log.md)
- [스크린샷 계획](docs/screenshots/README.md) · [GitHub Issue 후보](docs/github-issues.md)
- [공개 전 보안·개인정보 점검](docs/publication-review.md)

## Getting Started

검증 환경: Windows, Python 3.13.5, LTspice 26.0.1. LTspice는 별도 설치하며 PyLTSpice가 실행 파일을 찾을 수 있어야 합니다. 설치된 환경의 core 실행 의존성(직접 의존성과 일부 하위 의존성 고정)을 [requirements.txt](requirements.txt)에 기록했습니다. 새 환경에서의 설치 검증은 아직 하지 않았습니다.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:LLM_PROVIDER = "mock"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

`.asc` 업로드 → 요청 입력 → Analyze Request → 조건 수정·승인 → Run 순서입니다. mock에는 API key가 필요 없습니다. OpenAI provider의 선택 의존성은 [requirements-llm.txt](requirements-llm.txt)에 있으며, 실제 API smoke test는 아직 수행하지 않았습니다. `.env` 자동 로더는 없습니다.

OpenAI provider를 사용할 때만 core 설치에 다음을 추가합니다. 설치 자체는 API를 호출하지 않습니다. 기본 simulation / Summary / mock 사용에는 필요하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-llm.txt
```

실제 provider 사용 시에는 `LLM_PROVIDER=openai`와 `OPENAI_API_KEY`를 환경변수 또는 로컬 `.streamlit/secrets.toml`로 설정합니다. 실제 키는 저장소에 넣지 않습니다. 앞서 설정한 mock provider는 자동으로 변경되지 않습니다.

## Project Structure

```text
app.py                         Streamlit review / approval / results
*_analysis.py                  Analysis-specific parsing and directives
*_result_analysis.py           RAW measurements and graphs
simulation_runner.py           Approved execution on circuit copies
parameter_sweep*.py            R/C sweep parsing, execution, comparison
analysis_summary.py            Deterministic structured facts and evidence
ai_interpretation.py            LLM-ready prompt builder
llm_client.py                  Optional OpenAI / mock interpretation
ui_helpers.py                  Display formatting and review defaults
tests/                         Unit, AppTest, integration; small ASC fixtures
docs/                          Original logs, devlog, publication guidance
```

## Current Limitations / Future Work

- Actual API smoke test not yet performed; 실제 응답 품질은 검증하지 않았습니다.
- 한 번에 **하나의 R/C** sweep만 지원하며 nested sweep / cancel-resume는 지원하지 않습니다.
- AC bandwidth는 low-pass 우선, Transient step 측정은 waveform 적용 조건이 있습니다.
- 외부 model/include 업로드, 결과 저장·재분석, 긴 legend·좁은 화면 UX는 후속 과제입니다.
- Image-to-circuit와 보고서 생성은 향후 구현할 기능입니다.
- 개인 MOSFET 회로와 로컬 증거는 배포하지 않습니다. 라이선스와 공개할 회로·이미지 권리는 소유자가 공개 전에 결정해야 합니다.
