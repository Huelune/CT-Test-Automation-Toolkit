# 에이전트 작업 인수인계

사용자용 매뉴얼이 아니다. 다른 PC나 새 에이전트 세션이 현재 브랜치와 검증 경계를
잘못 해석하지 않도록 유지하는 작업 상태 문서다. AGENTS.md에 따라 브랜치 변경, 병합,
서버 PC 실행 요청 전에 반드시 읽는다.

**지금 유효한 것만 둔다.** 날짜별 작업 기록(무엇을 왜 바꿨는지, 접은 실험)은
[작업 기록 보관](../archive/handoff-history.md) 끝에 날짜 절로 붙이고, 여기에는 결과로
바뀐 "현재 기준"과 "실물 미검증 목록"만 고친다.

## 현재 기준

- 기준일: 2026-10-29
- 브랜치: 작업은 `develop`, `main`은 `develop`의 fast-forward만 받는다. 서버 PC의
  클론은 `main`을 `git pull`한다.
- 단계: 저장소 골격, 실행 로그(`ct_toolkit.log`), 환경 점검(`ct.bat selfcheck`)까지.
  CT를 부르는 기능은 아직 없다. 단위 테스트는 에이전트 PC의 Python 3.12·3.14에서
  통과했다. 3.8은 문법 검사만 했다.
- 에이전트 PC: CT와 서버 PC의 결과 폴더가 없다. 실행 증거는 서버 PC에서만 나온다.
- 서버 PC(2026-10-29 `ct.bat selfcheck`): Python 3.14.7, openpyxl 3.1.5, git 있음, 콘솔
  utf-8(한글 정상). CT CLI는 `CT_HOME` 아래 `csc.exe`만 있고 `UtCLI.exe`는 없다. 2023 이후
  버전이고, 정확한 버전(Help > About)은 아직 모른다.
- CT 기능 근거: 슈어소프트 CT 매뉴얼(manula.com). CLI 키는 3.6 매뉴얼의 CLI Setting,
  기능 목록은 2026.06 매뉴얼에서 확인했다.
- CT CLI는 버전마다 프로그램이 다르다. 2023 이후는 설치 폴더 바로 아래 `csc.exe`
  (`csc.exe -e -w <워크스페이스> --ini -O <CLI.ini>`, 2026.06 매뉴얼 CI/CD·CLI 프로젝트 실행),
  3.x 이하는 `plugins\com.codescroll.ut*\bin\UtCLI.exe`(3.6 매뉴얼 CLI Execution)다.
- 다음 할 일 후보는 [로드맵](../design/roadmap.md).

## 브랜치 지도

| 브랜치 | 역할 |
| --- | --- |
| `main` | 서버 PC가 pull하는 배포 기준. `develop`의 fast-forward만 받는다 |
| `develop` | 작업 브랜치 |

## 실물 미검증 목록

정적 구현과 단위 테스트만 거친 것이다. 서버 PC 실행 결과가 나오면 해당 줄을 지우고
결과를 작업 기록에 남긴다.

- 지금은 없다. `ct.bat`, 콘솔 한글, CT CLI 탐색, 실행 로그 쓰기는 2026-10-29 서버 PC
  환경 점검으로 확인했다.
