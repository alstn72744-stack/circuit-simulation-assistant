# Public Screenshots

Prompt 010C에서 사용자가 제공한 실제 앱 screenshot 5장을 확인하고 README에 연결했습니다. 새 이미지를 생성하거나 원본을 편집하지 않았습니다.

| 파일 | 화면 내용 / 용도 |
| --- | --- |
| [01_trace_suggestion.png](01_trace_suggestion.png) | V(out)에 대한 V(Vout) 후보, 필수 signal 안내, 비활성 승인/실행 UI |
| [02_ac_response.png](02_ac_response.png) | AC voltage gain, -3 dB 기준선과 bandwidth 위치 |
| [03_parameter_sweep_results.png](03_parameter_sweep_results.png) | R1 값별 gain/bandwidth 및 상태 비교. 5kΩ의 bandwidth 미제공과 Partial Measurements 포함 |
| [04_transient_waveform.png](04_transient_waveform.png) | 시간에 따른 V(vout) / V(vin) 전압 파형 |
| [05_dc_sweep.png](05_dc_sweep.png) | V2에 따른 V(vout) DC curve와 선택한 sweep 지점 |

README는 Workflow와 Features 사이에서 앞의 2장을 표시하고, 나머지 3장은 펼치기 영역에 배치합니다. 모두 HTML `width="800"`, 높이 자동, 중앙 정렬을 사용합니다. GitHub의 이미지 컨테이너 폭 제한에 따라 좁은 화면에서는 축소되며, 이미지를 클릭하면 원본 파일을 확인할 수 있습니다.

5장을 직접 열어 확인한 범위에서 사용자명, 개인 절대 경로, 이메일, API key/secret은 보이지 않았습니다. PNG metadata도 색상·gamma·DPI 항목뿐이었습니다. 이는 보이는 화면과 metadata 검토 결과이며 포괄적인 개인정보 부재 보증은 아닙니다.

스크린샷은 화면 기능을 보여주며 새 simulation 검증 결과를 추가하지 않습니다. 특히 DC 이미지의 curve를 README Validation에 기록한 분압 fixture의 1.775 V 결과와 동일한 사례로 취급하지 않습니다. 기존 121 tests와 integration 수치, 미완료 검증 한계는 그대로 유지합니다.

프로젝트 root의 과거 `screenshots/` 및 `simulation_output/`은 계속 공개 제외됩니다. 최초 UI와 Analysis Summary 이미지는 향후 검토 후 추가할 수 있으며, 존재하지 않는 파일 링크는 만들지 않았습니다.
