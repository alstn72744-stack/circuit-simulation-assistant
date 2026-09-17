# Validation & Reproduction

## Recorded validation

Prompt 009A(2026-09-17)에서 121 unit/AppTest, 실제 AC/Transient/DC/Parameter Sweep integration 4종, 실제 Streamlit startup, Edge desktop/mobile graph layout 검증이 통과했습니다. [원본 기록](development-log.md#2026-09-17--core-ux-polish-after-real-user-testing-prompt-009a)에 실패와 수정·재실행도 남아 있습니다. 공개 준비 단계에서는 기존 Python 코드와 tests를 변경하지 않았고 전체 simulation을 다시 실행하지 않았습니다.

단위 테스트에는 PyLTSpice, Streamlit, NumPy/Matplotlib 등이 필요합니다. `requirements.txt`는 core 실행의 직접 의존성과 일부 하위 의존성 버전을 기록하며 새 환경 설치나 모든 전이 의존성의 재현을 보장하는 lockfile은 아닙니다. spicelib는 PyLTSpice, pandas는 Streamlit, Pillow는 Streamlit/Matplotlib의 실행 의존성입니다. OpenAI 및 Playwright는 core 파일에 포함하지 않습니다. 선택 OpenAI SDK 검사는 SDK 미설치 시 일부 skip될 수 있으므로 기존 전체 검증과 같은 구성을 원하면 `requirements-llm.txt`도 설치합니다. mock/fake transport 검사는 실제 API를 호출하지 않습니다.

## Local-only circuit configuration

기존 `test_ltspice.py`는 외부 개인 회로의 절대 경로를 포함하는 초기 smoke script입니다. 로컬 파일은 변경하지 않고 공개에서는 명시적으로 제외했습니다. 앱은 이 파일을 import하지 않습니다. MOSFET integration 스크립트들은 AST로 이 파일의 `ASC_FILE` 값을 읽습니다.

새 clone에서 해당 검증을 준비할 때만:

1. `test_ltspice.py.example`을 `test_ltspice.py`로 복사합니다. 기존 로컬 설정을 덮어쓰지 않습니다.
2. 소유권·배포 권한을 확인한 회로를 `local_circuits/Draft3.asc`에 준비합니다. `ASC_FILE`에는 상대 경로를 사용할 수 있습니다.
3. 기존 검증은 FQB55N10 MOSFET, V(vin)/V(vout), R1/C1, SINE(3.55 10m 10k) 등 원래 테스트 회로의 구성과 수치에 의존합니다. 임의 회로로 바꾸면 같은 결과를 기대할 수 없습니다. 원래 MOSFET fixture가 공개되지 않아 이 검증은 fresh clone에서 즉시 재현되지 않습니다.
4. 레거시 `test_ltspice.py`를 원본 회로에 직접 실행하지 않습니다. 기존 integration은 업로드 bytes와 실행용 복사본을 사용합니다.

프로젝트 root에서 한 번에 하나씩 실행합니다. 실행 폴더 전후 비교를 사용하는 검사가 있으므로 병렬 실행하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 tests/verify_integration.py --real-ltspice
.\.venv\Scripts\python.exe -X utf8 tests/verify_transient_integration.py --real-ltspice
.\.venv\Scripts\python.exe -X utf8 tests/verify_dc_integration.py --real-ltspice
.\.venv\Scripts\python.exe -X utf8 tests/verify_parameter_sweep_integration.py
```

DC integration은 공개된 `tests/fixtures/dc_divider.asc`, `dc_current_mirror.asc`를 사용합니다. 이 두 작은 ASC에는 개인 include 경로나 외부 모델 파일이 없으며 wildcard로 제외하지 않았습니다. GUI layout 수동 검증은 별도로 Playwright와 설치된 Edge를 필요로 합니다.

## Evidence and interpretation limits

`simulation_input/<run_id>/`는 실행 복사본, `simulation_output/<run_id>/`는 RAW/LOG/netlist/graph이며, 별도 verification 폴더에는 JSON과 감사 로그가 있습니다. 이 데이터는 개인 경로·회로 정보를 포함할 수 있어 모두 공개 제외합니다. 원본 개발 기록의 상대 경로는 증거의 provenance를 보존하기 위한 텍스트이고 공개 다운로드 링크가 아닙니다.

각 분석의 scalar/synthetic 검증과 regression은 직접적인 교차 분석 물리 검증과 구분합니다. AC와 Transient gain 비교에는 같은 frequency/bias/amplitude 조건이 필요하고, DC–Transient 비교에는 같은 topology의 DC bias와 정상상태가 필요합니다. 기존 DC 분압기/current mirror 검증만으로 MOSFET 증폭기의 DC–Transient 일관성을 입증하지 않습니다.
