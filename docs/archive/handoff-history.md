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

## 2026-10-28 selfcheck가 csc.exe도 찾게 함

- 9/30 조사 노트(2025.12·2026.06 매뉴얼)에 CT 2023 이후의 CLI가 설치 폴더 바로 아래
  `csc.exe`라고 적혀 있었다. 저장소의 selfcheck와 로드맵은 3.6 매뉴얼만 보고 `UtCLI.exe`만
  찾고 있었다. 2026.06 매뉴얼 CI/CD 페이지에서 `csc.exe` 위치를 다시 확인했다.
- 서버 PC의 CT가 2023 이후 버전이면 1절이 CT CLI FAIL로 끝나 다시 돌려야 한다. 그래서
  1절을 돌리기 전에 selfcheck가 `csc.exe`와 `UtCLI.exe`를 둘 다 찾게 했다. 캡처 한 장으로
  어느 CLI인지 가린다.
