# Public Repository Review — Prompt 010A

2026-09-17의 로컬 공개 준비 점검입니다. GitHub remote 생성, push, LLM/API 호출은 수행하지 않았습니다. 현재 환경에는 Git executable과 `.git` metadata가 없어 Git index/history 검사는 수행할 수 없었습니다.

## Security / privacy scan

초기 프로젝트 파일 47개와 simulation 입력/출력 파일 1,658개의 구조를 확인했습니다. 1,450개 텍스트/RAW header를 검색하고, 이미지 등 binary 255개는 텍스트 검색에서 제외했습니다. RAW 325개는 header만 읽었으며 waveform binary 자체는 검색하지 않았습니다. `.venv`, cache, Git metadata는 프로젝트 작성물이 아닌 검사 제외 영역입니다. 이미지 OCR이나 포괄적인 개인정보 식별을 수행한 것은 아닙니다.

검색 범주: API key/token의 알려진 형식, credential 할당·참조, password/secret, 사용자 home 절대 경로, machine-specific 경로, email, 현재 Windows 사용자 식별자. 결과에는 값 대신 파일·행·분류만 저장했습니다. **확인한 범위에서 실제 credential 또는 email은 발견되지 않았습니다.** 환경변수나 계정의 secret store는 열람하지 않았습니다.

| 위치 | 발견 / 판단 | 조치 |
| --- | --- | --- |
| `test_ltspice.py:3` | 개인 사용자·학교 과제 디렉터리가 포함된 외부 ASC 절대 경로 | 로컬 원본과 test logic을 유지하고 해당 파일만 명시적으로 ignore. 공개용 `test_ltspice.py.example`은 상대 경로 사용 |
| `simulation_input/`, `simulation_output/` | 업로드된 회로, 생성 netlist/LOG/JSON 등의 사용자 경로·식별자. 초기 스캔에서 personal-path 일치 행 2,578건 | 두 디렉터리 전체 공개 제외. 로컬 증거와 파일은 삭제하지 않음 |
| `screenshots/` | 기존 이미지 4개, 사용자 경로/개인정보가 화면에 있는지 전수 시각 검토하지 않음 | 원본 보존·공개 제외. 검토한 사본만 `docs/screenshots/`에 게시 |
| `tests/test_ai_interpretation.py:107–108`, `tests/test_llm_client.py:24` | path sanitization을 위한 가상 사용자 경로 | 실제 사용자 경로가 아닌 fixture이므로 유지 |
| `tests/test_llm_client.py:43,52–53,198,238` | mock/fake transport/configuration용 가짜 key 문자열 | credential 원문을 점검 문서에 복사하지 않고 테스트 유지 |
| `simulation_output/llm_mock_verification_*/`의 JSON 6개 | `token` 키가 credential 후보로 잡혔지만 numerical validation의 인용 숫자 메타데이터 | 생성 데이터 공개 제외; 실제 인증 token으로 분류하지 않음 |
| `ai_interpretation.py`, `llm_client.py`, `tests/`의 기타 경로 문자열 | path 정규식, generic test paths, 표준 Edge 설치 경로 | 개인 정보가 아닌 기능/검증용 코드로 유지 |
| `docs/development-log.md`, `docs/prompt-log.md` | 개인 사용자 절대 경로 없음. 기존 증거는 project-relative 경로. `AC:`/`DC:`와 URL 등 일부 regex false positive | 과거 본문을 바꾸지 않고 이번 작업 결과만 append |

이 점검은 secret 부재의 보증이 아닙니다. 새로 게시할 파일과 commit history는 게시 시점에 다시 확인해야 합니다. 로컬 상세 결과와 hash baseline은 공개 제외된 `simulation_output/publication_audit/`에만 저장합니다.

사용 한도 이후 재개 시 기존 helper로 스캔을 재실행해 정상 종료를 확인했습니다. 프로젝트 파일 57개, 생성 파일 1,658개 중 텍스트/RAW header 1,460개를 검사했고 알려진 credential 형식/email 일치는 0건입니다. API key/password/secret/token 할당 후보는 기존 테스트용 가짜 문자열과 JSON의 인용 숫자였으며 새 실제 자격증명은 확인되지 않았습니다. `simulation_output/publication_audit/audit.py`, `validate.py`, baseline/scan/validation JSON과 임시 기록은 **공개 제외된 로컬 검증 도구**입니다. 공개 폴더로 옮기지 않았습니다.

## Inclusion / exclusion decisions

- `.gitignore`는 venv/cache, `.env` 계열, Streamlit secrets, RAW/LOG/실패 로그, simulation 입력/출력, IDE 임시 파일을 제외합니다.
- `test_ltspice.py`는 **의도적인 단일 예외**입니다. 앱 실행 코드는 모두 공개 대상이며 `tests/` 전체와 작은 ASC fixture 2개는 제외하지 않습니다. 대신 레거시 설정 template과 [재현 안내](validation.md)를 제공합니다.
- 기존 이미지를 무조건 공개하지 않습니다. 검토 후 넣을 `docs/screenshots/`는 ignore하지 않습니다. 소유자가 코드·fixture·이미지의 배포 권한과 LICENSE를 결정해야 합니다.
- `.gitignore`는 이미 추적된 파일이나 과거 commit을 제거하지 않습니다. 현재 Git metadata가 없어 그런 상태를 확인하지 못했습니다.

## Validation scope

로컬 Markdown 링크·anchor, 코드 fence 짝, 문서 제목, 기존 Python/test/fixture SHA-256 불변 여부를 검사합니다. `.gitignore`는 현재 사용하는 단순 anchored path / directory / basename wildcard를 평가해 앱·tests·ASC가 숨겨지지 않는지 확인합니다. **실제 `git check-ignore` 검증은 Git 미설치로 수행하지 못했습니다.** 기본 의존성은 설치된 버전에서 기록했고 새 환경 설치 검증은 별도 TODO입니다.

기존 121 tests와 실제 integration 4종 통과는 Prompt 009A 기록입니다. 이번에는 기존 Python 코드·test logic을 수정하지 않아 전체 regression을 재실행하지 않았습니다.

최종 검증 결과: Markdown 9개 문서의 로컬 링크/anchor **26개 통과**, 기존 source/test/fixture **38개 SHA-256 동일**, 원본 로그 두 파일의 과거 바이트 prefix 보존, 중요 코드·tests의 의도치 않은 ignore **0개**. 최종 스캔은 프로젝트 파일 57개를 포함했고 알려진 credential 형식 및 email 일치 **0건**이었습니다. 공개 제외된 초기 스크립트 외의 실제 사용자 경로는 없었으며 테스트의 가상 경로는 유지했습니다. `.env`와 `.streamlit/secrets.toml`은 현재 존재하지 않습니다.

## Human checks before publishing

1. Git 설치 후 로컬 저장소에서 staged diff/파일 목록을 확인합니다. `git status --short`, `git diff --cached --stat`, `git diff --cached`와 `git check-ignore -v`로 실제 ignore 상태를 확인합니다. 기존 history가 있다면 별도 secret/history scan도 필요합니다.
2. 개인 초기 스크립트, simulation 폴더, `.env`, secrets, 미검토 screenshots가 staged되지 않았는지 확인합니다. ignore는 이미 추적된 파일의 보호 장치가 아닙니다.
3. 공개할 circuit/model/image의 권리, 사용자 식별 정보·경로, license를 확인합니다. LICENSE는 소유자 선택 없이 추가하지 않았습니다.
4. 개인 MOSFET fixture 제외에 따른 integration 재현성 제한과 새 환경 설치 미검증을 확인합니다. [Issue 후보](github-issues.md)에 후속 작업을 남겼습니다.
5. README의 역사적 검증 수치·121 tests, 실제 API smoke 미수행, 교차 분석 물리 검증의 한계를 최종 확인합니다. 원본 로그의 상대 증거 경로는 공개 파일 링크가 아닙니다.

### Git 설치 후 실행 순서 (소유자 수동 작업)

아래 명령은 이번 작업에서 실행하지 않았습니다. 프로젝트 root에서 시작합니다.

1. Git을 설치하고 새 터미널에서 `git --version`을 확인합니다. `.git`이 없는 현재 폴더에서만 `git init -b main`을 실행합니다. 기존 저장소가 생겼다면 초기화 대신 상태/history를 먼저 확인합니다.
2. 파일과 제외 규칙을 확인합니다.

   ```powershell
   git status --short --untracked-files=all
   git check-ignore -v --no-index -- .env .streamlit/secrets.toml .venv/pyvenv.cfg simulation_input/check.asc simulation_output/check.raw simulation_output/check.log simulation_output/publication_audit/audit.py simulation_output/publication_audit/scan.json test_ltspice.py local_circuits/Draft3.asc screenshots/check.png
   git check-ignore -v --no-index -- app.py tests/test_ui_helpers.py tests/fixtures/dc_divider.asc tests/fixtures/dc_current_mirror.asc test_ltspice.py.example docs/screenshots/README.md
   git add --dry-run .
   ```

   첫 check-ignore에는 제외 규칙이 표시돼야 합니다. 두 번째는 출력 없음/종료 코드 1이 정상입니다(공개 대상이 ignore되지 않음). 예상과 다르면 staging 전에 수정합니다.
3. 공개할 회로·이미지의 권리와 LICENSE, commit author 이름/email을 검토하고, 파일을 stage한 뒤 **내용까지** 확인합니다.

   ```powershell
   git add .
   git diff --cached --name-only
   git diff --cached --stat
   git diff --cached
   git status --short
   ```

   제외 파일이 staged돼 있지 않은지 확인하고, staged 내용에 대해 secret scan을 다시 수행합니다. 기존 history가 있다면 history도 검사합니다. 이번 로컬 audit helper는 Git index/history scanner가 아니므로 이를 대체하지 않습니다. 문제 파일은 staging에서 제외하거나 수정한 뒤 재검토합니다.
4. 검토를 통과한 뒤 `git commit -m "Prepare public repository"`를 실행합니다. GitHub에서 README/LICENSE 자동 생성 없이 **빈 remote repository**를 만들고, 아래 `<YOUR_REPOSITORY_URL>`을 실제 주소로 바꿉니다.

   ```powershell
   git remote add origin <YOUR_REPOSITORY_URL>
   git remote -v
   ```

5. **push 직전 최종 commit/history의 secret scan**과 `git status`를 다시 확인합니다. 주소·공개 범위가 맞고 검사에 문제가 없을 때만 `git push -u origin main`을 실행합니다. 로컬 개인 파일이 그대로 있다는 사실은 공개 실패가 아니며, commit에 포함되지 않는 것이 기준입니다.
