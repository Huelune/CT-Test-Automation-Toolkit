# Changelog

## Unreleased

- **`ct.bat io-apply --list <목록.xlsx>`로 입력·출력 지정 목록을 확인합니다.** Codebeamer에서
  내보낸 목록의 첫 시트를 머리글(`함수`, `변수`, `구분`, `파일`, `타입`, `범위`) 이름으로 읽어,
  함수·줄·목록 오류 개수를 한 화면에 찍습니다. 필수 칸이 비었거나 `구분` 값이 틀린 줄은
  `result\io\<시각>\skipped.txt`에 행 번호와 함께 남습니다. 함수·변수 이름은 이 파일에만 쓰고
  화면과 로그에는 찍지 않습니다. CT에서 내보낸 테스트를 목록대로 고치는 `--export`는 CT 파일
  형식을 확인한 뒤 붙입니다.

- **`ct.bat selfcheck`가 CT 2023 이후의 `csc.exe`도 찾습니다.** `CT_HOME` 바로 아래의
  `csc.exe`와 플러그인 폴더의 `UtCLI.exe`(3.x 이하)를 둘 다 보고 찾은 것을 모두 한 줄에
  찍습니다. 서버 PC의 CT가 어느 CLI를 쓰는지 캡처 한 장으로 알 수 있습니다.

- **`ct.bat selfcheck`로 서버 PC 환경을 한 화면에 점검합니다.** Python 버전, openpyxl,
  `UtCLI.exe`(환경 변수 `CT_UTCLI` 또는 `CT_HOME` 아래 플러그인 폴더), 로그 폴더 쓰기, git,
  콘솔 인코딩을 항목당 한 줄로 찍고, 필수 항목이 모두 통과하면 종료 코드 0입니다. 경로는
  찍지 않고 CT 플러그인 폴더 이름(버전)만 찍습니다.

- **모든 명령이 실행 로그를 남깁니다.** `result/logs/<yyyyMMdd_HHmmss>_<명령>.log`에 모든
  레벨을 남기고 콘솔에는 `STEP` 이상만 보입니다(`--console-level`로 조정). 명령의 끝 줄은
  `DONE`, `FAILED`, `INTERRUPTED` 중 하나입니다.

- **저장소를 만들었습니다.** Simulink-Test-Automation-Toolkit의 작업 규칙(AGENTS.md, 커밋
  규칙, 인수인계 문서, 서버 PC 실행 요청용 `todo.md`)을 CT 작업에 맞게 옮겼습니다.
