# CT Test Automation Toolkit

슈어소프트 CT(Controller Tester)로 단위 테스트를 돌리고 결과물을 정리하는 과정을
자동화하는 Python 도구입니다. CT가 이미 하는 일(테스트·스텁 생성, 실행, 커버리지 측정,
보고서 생성)은 CT CLI(2023 이후 `csc.exe`, 3.x 이하 `UtCLI.exe`)로 부르고, 그 앞뒤의 반복
작업(CLI.ini 준비, 보고서 요약, 커버리지 미달 목록, 팀 산출물 양식 채우기)을 맡습니다.

저장소: [Huelune/CT-Test-Automation-Toolkit](https://github.com/Huelune/CT-Test-Automation-Toolkit)

> 아직 초기 단계입니다. 지금은 저장소 골격, 실행 로그, 서버 PC 환경 점검, 입력·출력 지정 목록
> 확인만 있습니다.
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
| `ct.bat io-apply --list <목록.xlsx>` | 입력·출력 지정 목록이 툴킷 형식에 맞는지 확인하고 개수를 한 화면에 찍음. 처리하지 못한 줄은 `result\io\<시각>\skipped.txt`. CT 내보낸 폴더(`--export`)를 고치는 기능은 아직 없음 |
| `ct.bat version` | 툴킷 버전 |

모든 명령은 `result/logs/<yyyyMMdd_HHmmss>_<명령>.log`에 실행 로그를 남깁니다. 콘솔에는
`STEP` 이상만 보이고, 로그 파일에는 모든 줄이 남습니다.

## 입력·출력 지정 목록 형식

`ct.bat io-apply`가 읽는 목록입니다. Codebeamer에서 내보낸 것을 이 모양으로 맞춥니다. 예제는
[examples/ct_sample/io_list.example.xlsx](examples/ct_sample/io_list.example.xlsx)입니다.

- 엑셀 파일(`.xlsx`)의 첫 시트만 읽습니다.
- 첫 줄이 머리글입니다. 머리글 위에 제목 줄을 두지 않습니다.
- 한 줄에 변수 하나를 적습니다. 함수 이름은 줄마다 다시 적고 셀 병합은 하지 않습니다. 병합하면
  아래 줄의 함수 칸이 빈 것으로 읽혀 목록 오류가 됩니다.
- 칸은 머리글 이름으로 찾습니다. 순서는 상관없고 다른 칸이 더 있어도 됩니다.

| 머리글 | 적는 것 | 비워도 되나 |
| --- | --- | --- |
| `함수` | 함수 이름. 소스에 적힌 그대로(대소문자 구분) | 아니오 |
| `변수` | 전역 변수나 파라미터 이름. 리턴 값은 `return` | 아니오 |
| `구분` | `입력`, `출력`, `입출력` 중 하나. 다른 글자는 목록 오류 | 아니오 |
| `파일` | 함수가 있는 소스 파일 이름(예: `dmy_io.c`). 같은 이름 함수가 다른 파일에도 있을 때만 필요 | 예 |
| `타입` | 참고용. 툴킷은 비교하지 않음 | 예 |
| `범위` | 참고용. 지금은 읽기만 함 | 예 |

변수 이름은 소스의 이름 그대로 적습니다. CT 화면의 이름과 다를 수 있습니다.

- 구조체는 변수 이름만 적습니다(`dmy_limit`). 멤버 전체에 같은 지정이 들어가며, 멤버를 따로 적지
  않습니다.
- 배열은 `[ ]` 없이 이름만 적습니다(`dmy_hist`).
- 포인터 파라미터는 파라미터 이름을 적습니다(`dmy_ptr`). CT의 `dmy_ptr_mem[0]`에 들어갑니다.
- 리턴 값은 `return`입니다. CT의 `returnVar`에 들어갑니다.

함수 하나의 입력·출력은 빠짐없이 적습니다. CT 테스트를 고치는 단계(`--export`, 개발 중)에서는
목록에 그 함수 줄이 있으면 목록에 없는 변수의 지정을 해제합니다.

| 함수 | 변수 | 구분 | 파일 | 타입 | 범위 |
| --- | --- | --- | --- | --- | --- |
| dmy_calc | dmy_gain | 입력 | | int | 0~100 |
| dmy_calc | dmy_limit | 입력 | | dmy_limit_t | |
| dmy_calc | dmy_ptr | 입력 | | const int * | |
| dmy_calc | dmy_count | 출력 | | int | |
| dmy_calc | return | 출력 | | int | |

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
