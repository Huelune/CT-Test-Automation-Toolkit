# CT Test Automation Toolkit

슈어소프트 CT(Controller Tester)로 단위 테스트를 돌리고 결과물을 정리하는 과정을
자동화하는 Python 도구입니다. CT가 이미 하는 일(테스트·스텁 생성, 실행, 커버리지 측정,
보고서 생성)은 CT CLI(2023 이후 `csc.exe`, 3.x 이하 `UtCLI.exe`)로 부르고, 그 앞뒤의 반복
작업(CLI.ini 준비, 보고서 요약, 커버리지 미달 목록, 팀 산출물 양식 채우기)을 맡습니다.

저장소: [Huelune/CT-Test-Automation-Toolkit](https://github.com/Huelune/CT-Test-Automation-Toolkit)

> 아직 초기 단계입니다. 지금은 저장소 골격, 실행 로그, 서버 PC 환경 점검만 있습니다.
> 앞으로 만들 것은 [로드맵](docs/design/roadmap.md)에 있습니다.

## 요구 환경

| 항목 | 필요 범위 |
| --- | --- |
| Windows | CT가 설치된 서버 PC |
| Python | 3.8 이상 (`python` 또는 `py -3`) |
| CT | `csc.exe`(2023 이후) 또는 `UtCLI.exe`(3.x 이하)가 있는 설치본 |
| openpyxl | XLSX 보고서를 읽는 기능에서만 필요 (`pip install -r requirements.txt`) |

## 서버 PC에서 처음 준비하기

```bat
git clone https://github.com/Huelune/CT-Test-Automation-Toolkit.git
cd CT-Test-Automation-Toolkit
set CT_HOME=<CT 설치 폴더>
ct.bat selfcheck
```

`CT_HOME` 대신 `CT_UTCLI`에 `UtCLI.exe`의 전체 경로를 줘도 됩니다. 계속 쓰려면
`setx`로 저장합니다. 업데이트는 `git pull`입니다(서버 PC는 `main`을 받습니다).

## 명령

| 명령 | 하는 일 |
| --- | --- |
| `ct.bat selfcheck` | Python, openpyxl, CT CLI(`csc.exe`, `UtCLI.exe`), 로그 폴더 쓰기, git을 점검하고 한 화면에 요약 |
| `ct.bat version` | 툴킷 버전 |

모든 명령은 `result/logs/<yyyyMMdd_HHmmss>_<명령>.log`에 실행 로그를 남깁니다. 콘솔에는
`STEP` 이상만 보이고, 로그 파일에는 모든 줄이 남습니다.

## 폴더

```text
ct.bat                 서버 PC 실행 진입점
src/ct_toolkit/        Python 패키지
tests/unit/            단위 테스트 (unittest)
docs/ai/               작업 규칙과 인수인계 (에이전트용)
docs/design/           설계와 로드맵
todo.md                서버 PC 실행 요청
result/                실행 결과와 로그 (커밋하지 않음)
```

## 개발

```bat
python -m unittest discover -s tests/unit
```

작업 규칙은 [AGENTS.md](AGENTS.md), 커밋 규칙은
[docs/ai/commit-convention.md](docs/ai/commit-convention.md)에 있습니다.
