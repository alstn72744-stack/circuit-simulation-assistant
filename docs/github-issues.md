# GitHub Issue Candidates

아래는 문서상의 후보이며 실제 GitHub issue나 remote를 생성하지 않았습니다.

| 후보 | 완료 기준 / 범위 |
| --- | --- |
| Actual OpenAI API smoke test | 소유자가 비용/전송 데이터를 검토한 뒤 수동 실행. 오류/응답/수치 경계 기록. mock 검증과 구분 |
| Portable public MOSFET fixture | 배포 권한이 확인된 fixture와 configuration으로 기존 개인 `ASC_FILE` 의존 제거. 기존 test logic 변경은 별도 작업 |
| Fresh-clone setup verification | 새 Windows 환경에서 requirements 설치, unit suite, 공개 fixture DC 실행 검증 |
| Cross-analysis physical consistency | 같은 회로·bias·주파수에서 AC vs small-signal Transient, DC bias vs Transient 정상상태 비교 및 허용 오차 명시 |
| Image-to-circuit input | topology 검토·사용자 승인·오류 범위를 먼저 정의하는 별도 scope |
| Long legend / narrow-screen readability | 긴 trace 이름, 여러 curve, 작은 화면에서 확대·글꼴 접근성 검토 |
| Result persistence / reanalysis | 기존 RAW의 조건·evidence를 보존하며 재분석, stale result 방지 |
| Cancel / resume sweep | point별 상태와 부분 결과 보존, 취소/재개 승인 동작 정의 |
| Report export | 검증된 수치/graph/evidence 출처를 유지하는 export, 추론과 사실 구분 |
| External model/include handling | 필요한 모델 파일의 경로·업로드·재현성 및 배포 권한 처리 |

## Resolved during real user testing

- V(out)/V(vout) trace suggestion with explicit selection and renewed approval.
- Repeated AC condition entry: same-circuit/type successful-condition reuse; explicit overrides win.
- Oversized graphs: shared centered 83% desktop width and responsive scaling.
- RAW/LOG table clutter: compact table with full point Evidence.
- DC requested-point parsing and separate result card.

검증 및 남은 한계는 [실제 사용자 테스트 글](devlog/09-real-user-testing.md)에 기록했습니다.
