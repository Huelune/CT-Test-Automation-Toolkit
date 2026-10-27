# 로드맵

CT 단위 테스트를 돌리고 결과물을 정리하는 과정에서 자동화할 수 있는 부분을 조사한
결과(2026-10-27)와, 그중 이 저장소가 맡을 것의 후보 순서다.

## CT가 이미 하는 것

| 단계 | CT 기능 | CLI.ini 섹션(3.6 기준) |
| --- | --- | --- |
| 프로젝트 생성·분석 | 빌드 스크립트·VS·임베디드 프로젝트 가져오기 | `[Project]`(CPI 파일), `[Analysis]` |
| 테스트 생성 | 함수 격리 스텁 자동 생성, 전역변수 I/O 자동 설정 | `[InitializeTest]`, `[CreateTest]` |
| 테스트 케이스·데이터 | 자동 생성, AI 코드 기반 테스트 생성(2026.06) | `[CreateTestCase]` mode=flat/pairwise/random |
| 자산 가져오기 | 테스트·스텁·테스트 케이스·통합 테스트 | `[ImportTest]`, `[ImportStub]`, `[ImportTestCase]`, `[ImportIntegrationTest]` |
| 실행 | Host / Target(RTV) | `[ExecuteTest]` |
| 커버리지 | Statement, Branch, MC/DC, Function Call, Function | 3.6 CLI Setting에는 커버리지 내보내기 섹션이 없다 |
| 보고서 | HTML/XLSX/PDF/DOCX/PPTX, 요구사항 커버리지(CSV) | `[Report]` |
| CI | Jenkins 플러그인(CT Test Execution, CT Custom Command) | — |

## 이 저장소가 맡을 후보

순서는 잠정이다. 각 항목은 서버 PC 실행으로 확인하기 전까지 미검증이다.

1. **CLI.ini 생성과 UtCLI 실행 래퍼.** 템플릿에서 섹션을 켜고 끄는 설정으로 CLI.ini를
   만들고 `UtCLI.exe`를 돌린다. 종료 코드와 소요 시간을 로그에 남긴다.
2. **XLSX 보고서 요약.** CT 보고서에서 함수별 Pass/Fail, 커버리지를 읽어 한 장으로
   요약한다. 보고서 구조는 서버 PC의 실물(이름을 지운 사본)을 보고 정한다.
3. **커버리지 목표 미달 목록.** 목표(예: Branch 100%, MC/DC)에 못 미친 함수를 뽑아
   보완 대상과 미달 사유 작성 목록을 만든다.
4. **팀 산출물 양식 채우기.** 요약 결과를 팀 제출 양식에 옮긴다.
5. **요구사항 추적표(RTM).** CT의 요구사항 CSV 가져오기·내보내기를 이용한다.
6. **회귀 비교.** 두 실행 결과를 비교해 새로 실패한 테스트, 떨어진 커버리지를 찍는다.
7. **합격 기준 판정.** Jenkins 플러그인 문서에 임계값 설정이 없으니 스크립트 종료
   코드로 판정한다.

## 사람이 판단할 것

- 기대값 결정. CT의 "Host Output → Expected Value"는 수동 메뉴이고 요구사항 근거가 필요하다.
- 실패 원인 분석, 커버리지 미달 사유, 리뷰.

## 근거

- CT 2026.06 개요: https://www.manula.com/manuals/codescroll/controller-tester/2026.06/en/topic/ct-overview
- CLI Setting (3.6): https://www.manula.com/manuals/codescroll/controller-tester/3.6/en/topic/cli-setting
- CLI Execution (3.6): https://www.manula.com/manuals/codescroll/controller-tester/3.6/en/topic/cli-excution
- Jenkins 플러그인 (2026.06): https://www.manula.com/manuals/codescroll/controller-tester-user-guides/2026.06/en/topic/jenkins-plugin
- Export (3.6): https://www.manula.com/manuals/codescroll/controller-tester/3.6/en/topic/export
- Import (3.7): https://www.manula.com/manuals/codescroll/controller-tester/3.7/en/topic/import
