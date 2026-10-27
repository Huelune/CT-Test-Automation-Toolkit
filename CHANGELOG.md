# Changelog

## Unreleased

- **`ct.bat selfcheck`로 서버 PC 환경을 한 화면에 점검합니다.** Python 버전, openpyxl,
  `UtCLI.exe`(환경 변수 `CT_UTCLI` 또는 `CT_HOME` 아래 플러그인 폴더), 로그 폴더 쓰기, git,
  콘솔 인코딩을 항목당 한 줄로 찍고, 필수 항목이 모두 통과하면 종료 코드 0입니다. 경로는
  찍지 않고 CT 플러그인 폴더 이름(버전)만 찍습니다.

- **모든 명령이 실행 로그를 남깁니다.** `result/logs/<yyyyMMdd_HHmmss>_<명령>.log`에 모든
  레벨을 남기고 콘솔에는 `STEP` 이상만 보입니다(`--console-level`로 조정). 명령의 끝 줄은
  `DONE`, `FAILED`, `INTERRUPTED` 중 하나입니다.

- **저장소를 만들었습니다.** Simulink-Test-Automation-Toolkit의 작업 규칙(AGENTS.md, 커밋
  규칙, 인수인계 문서, 서버 PC 실행 요청용 `todo.md`)을 CT 작업에 맞게 옮겼습니다.
