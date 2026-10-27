# 작업 기록 보관

[인수인계](../ai/handoff.md)에서 빠진 날짜별 기록이다. 과거 결정의 이유를 찾을 때만 본다.
새 기록은 이 파일 끝에 날짜 절로 붙인다.

## 2026-10-27 저장소 시작

- Simulink-Test-Automation-Toolkit의 작업 규칙(AGENTS.md, 커밋 규칙, 인수인계, todo.md
  요청 방식)을 CT 작업에 맞게 옮겨 저장소를 만들었다.
- 언어는 Python + 배치 래퍼(`ct.bat`)로 정했다. CLI.ini 생성, UtCLI 실행, XLSX 보고서
  정리를 Python으로 하고 서버 PC에서는 `ct.bat` 한 줄로 부른다.
- 공개 저장소로 시작한다. 그래서 고객 데이터와 내부 이름을 커밋하지 않는 규칙을
  AGENTS.md에 적었다.
- 첫 서버 PC 요청은 환경 점검(`todo.md` 1절)이다.
