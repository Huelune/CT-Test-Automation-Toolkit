# CT Test Automation Toolkit

슈어소프트 CT(Controller Tester)로 단위 테스트를 돌리고 결과물을 정리하는 과정을
자동화하는 Python 도구입니다. CT가 이미 하는 일(테스트·스텁 생성, 실행, 커버리지 측정,
보고서 생성)은 CT CLI(2023 이후 `csc.exe`, 3.x 이하 `UtCLI.exe`)로 부르고, 그 앞뒤의 반복
작업(CLI.ini 준비, 보고서 요약, 커버리지 미달 목록, 팀 산출물 양식 채우기)을 맡습니다.

저장소: [Huelune/CT-Test-Automation-Toolkit](https://github.com/Huelune/CT-Test-Automation-Toolkit)

> 아직 초기 단계입니다. 지금은 저장소 골격, 실행 로그, 서버 PC 환경 점검, 입력·출력 지정(목록
> 확인과 CT 테스트 데이터 CSV 고치기)만 있습니다. CSV 고치기(`--export`)는 서버 PC의 견본 프로젝트(함수
> 하나)로 한 바퀴 확인했고, 실제 프로젝트에는 아직 써 보지 않았습니다.
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
| `ct.bat io-apply --list <목록.xlsx>` | 입력·출력 지정 목록이 툴킷 형식에 맞는지 확인하고 개수를 한 화면에 찍음. 처리하지 못한 줄은 `result\io\<시각>\skipped.txt` |
| `ct.bat io-apply --list <목록.xlsx> --export <내보낸 폴더> [--reset-cases]` | 위에 더해, CT [테스트 내보내기] 폴더를 목록과 맞춰 보고 지정이 바뀌는 테스트의 CSV 사본을 `result\io\<시각>\`에 씀. 쓰는 순서는 아래 "입력·출력 지정 쓰는 순서" |
| `ct.bat version` | 툴킷 버전 |

모든 명령은 `result/logs/<yyyyMMdd_HHmmss>_<명령>.log`에 실행 로그를 남깁니다. 콘솔에는
`STEP` 이상만 보이고, 로그 파일에는 모든 줄이 남습니다.

## 입력·출력 지정 목록 형식

`ct.bat io-apply`가 읽는 목록입니다. Codebeamer에서 내보낸 것을 이 모양으로 맞춥니다. 실제 목록을 만들 때는
[examples/io_list_template.example.xlsx](examples/io_list_template.example.xlsx)를 복사해 씁니다. 여러 함수,
같은 이름 static 함수, 구조체·배열·포인터·리턴을 적는 법이 지어낸 이름으로 들어 있고, `비고` 칸과 둘째 시트
"적는 법"에 설명이 있습니다(툴킷은 첫 시트만 읽고 `ID`·`비고` 칸은 무시합니다). 견본 프로젝트용 예제는
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

- 구조체·배열은 이름만 적으면 전체입니다(`dmy_limit`, `dmy_hist`). `dmy_limit.dmy_a`, `dmy_tbl[0]`,
  `dmy_tbl[1].dmy_s`처럼 적으면 그것과 그 아래만 지정합니다.
- 한 기호에 여러 줄이 걸리면 더 자세한 줄을 따릅니다. 적지 않은 멤버·원소는 지정을 해제합니다.
- CT가 아직 가져오지 않은 원소·멤버는 `CT에 없음`으로 건너뜁니다. CT에서 원소·멤버를 늘린 뒤 내보냅니다.
- 포인터 파라미터는 파라미터 이름을 적습니다(`dmy_ptr`). CT의 `dmy_ptr_mem[0]`에 들어갑니다.
- 리턴 값은 `return`입니다. CT의 `returnVar`에 들어갑니다.

함수 하나의 입력·출력은 빠짐없이 적습니다. `--export`를 주면 목록에 그 함수 줄이 있는 테스트에서
목록에 없는 변수의 지정을 해제합니다(값이 든 변수는 `--reset-cases`를 줄 때만).

| 함수 | 변수 | 구분 | 파일 | 타입 | 범위 |
| --- | --- | --- | --- | --- | --- |
| dmy_calc | dmy_gain | 입력 | | int | 0~100 |
| dmy_calc | dmy_limit | 입력 | | dmy_limit_t | |
| dmy_calc | dmy_ptr | 입력 | | const int * | |
| dmy_calc | dmy_count | 출력 | | int | |
| dmy_calc | return | 출력 | | int | |

## 입력·출력 지정 쓰는 순서

CT에서 만든 테스트의 입력·출력 지정을 목록대로 한꺼번에 바꿉니다. 툴킷은 CT의 파일을 직접 고치지
않습니다. 지정을 바꾼 테스트 데이터 CSV를 새 폴더에 쓰고, CT가 그 CSV로 테스트를 다시 만듭니다.

1. Codebeamer에서 목록을 위 형식의 XLSX로 만듭니다.
2. CT에서 대상 함수들의 테스트를 만듭니다. 여러 함수를 한 번에 만들어도 됩니다. 자동으로 생긴
   테스트 케이스는 지우지 않고 둡니다.
3. [내보내기] > [테스트] > [테스트 내보내기]로 새 빈 폴더에 내보냅니다. 유닛 테스트는 테스트와 테스트
   데이터를 모두 체크합니다. 한 함수에 테스트가 둘 이상이면 툴킷은 어느 것에 지정할지 몰라 그 함수의
   줄을 `함수 여럿`으로 건너뜁니다. CT에 같은 함수의 테스트가 여럿 있을 때도, 예전에 내보낸 CSV가 남은
   폴더에 다시 내보낼 때도 그렇습니다. 툴킷은 내보낸 폴더의 `UnitTests` 폴더에 있는
   CSV만 읽습니다. CT [환경 설정] > [테스트] > [데이터 내보내기]의 내보내기 변수 출력 방향은 [가로](CT
   기본값)여야 합니다. [세로]로 내보낸 CSV는 툴킷이 읽지 못하고 `세로 방향임` 알림을 찍습니다.
4. 저장소 폴더의 `io-apply.bat`을 탐색기에서 더블클릭합니다. 묻는 대로 목록 XLSX 파일, 3에서 내보낸
   폴더를 차례로 창에 끌어다 놓고 Enter를 누른 뒤, 케이스 정리를 `y`나 `n`으로 고릅니다.
   - `y`: 지정을 바꾼 테스트의 케이스를 모두 지우고 값 없는 케이스 하나만 둡니다. CT가 막 만든 테스트에
     씁니다.
   - `n`: 케이스와 값을 그대로 둡니다. 값까지 넣은 테스트에 다시 돌릴 때 씁니다.

   내보낸 폴더는 읽기만 하고, 고친 CSV를 `result\io\<yyyyMMdd_HHmmss>\`에 내보낸 폴더와 같은 상대
   경로로 씁니다. 끌어다 놓은 경로는 화면에 찍히지 않습니다. 명령 창을 쓸 수 있는 PC에서는 같은 일을
   아래 명령으로 합니다(`y`는 `--reset-cases`).

   ```bat
   ct.bat io-apply --list <목록.xlsx> --export <내보낸 폴더> --reset-cases
   ```

5. 화면의 `바꾼 것`이 사본에 CSV가 있는 테스트 수입니다. CT에서 그 테스트의 원래 것을 지웁니다. 지울
   테스트는 사본 폴더에 있는 CSV의 이름(`<함수>_test<N>`)과 같은 것입니다. 지우지 않으면 같은 함수의
   테스트가 둘이 됩니다. 잘못 지웠으면 내보낸 폴더를 [테스트 가져오기]로 넣어 되살립니다.
6. [가져오기] > [테스트] > [테스트 데이터로 테스트 생성하기]에서 [추가…]로 사본의 CSV를 모두 골라
   [완료]합니다. [테스트 가져오기]는 CSV 머리글의 지정을 따르지 않으므로 쓰지 않습니다.
7. 화면에 찍힌 `건너뜀` 개수만큼 `result\io\<시각>\skipped.txt`를 보고 손으로 지정한 뒤 값 넣기로
   넘어갑니다.
8. 사본으로 만든 테스트를 다시 내보내 `io-apply.bat`을 `n`으로 돌려 `바꾼 것 0`인지 봅니다. 목록 오타로
   CT가 버린 기호가 여기서 드러납니다.

- 목록에 없는 변수는 지정을 해제합니다. 값이 이미 든 변수는 `--reset-cases`를 주지 않으면 해제하지 않고
  `값 있어 둠`으로 셉니다. 지정이 바뀌는 변수에 값이 있으면 그 줄은 `값 있음`으로 건너뜁니다.
- 목록에 함수 줄이 없는 테스트와, 지정이 목록과 이미 같은 테스트는 사본에 넣지 않습니다.
- 테스트 이름이 `<함수>_test<N>` 꼴이 아닌 테스트도 사본에 넣지 않습니다. CT는 이름 꼴이 틀린 CSV로
  테스트를 만들지 않아 원래 테스트를 지운 뒤 되살릴 수 없기 때문입니다. 화면의 `안 다룸` 줄에
  `이름 꼴이 아닌 테스트` 개수가 찍히면 그 테스트는 `skipped.txt`를 보고 손으로 지정합니다.
- `skipped.txt`에는 함수·변수 이름이 있습니다. 이 파일은 서버 PC에서만 보고 밖으로 보내지 않습니다.
  화면과 실행 로그에는 개수와 정해 둔 문구만 찍힙니다.
- 같은 시각에 두 번 돌리면 결과 폴더 이름에 `_2`, `_3`이 붙습니다.

## 폴더

```text
ct.bat                 서버 PC 실행 진입점
src/ct_toolkit/        Python 패키지
tests/unit/            단위 테스트 (unittest)
docs/ai/               작업 규칙과 인수인계 (에이전트용)
docs/design/           설계와 로드맵
todo.md                서버 PC 실행 요청
todo.bat               서버 PC에서 더블클릭해 todo.md 절의 확인을 돌린다 (tools/todo_run.py)
io-apply.bat           서버 PC에서 더블클릭해 목록대로 입력·출력 지정 (tools/io_run.py)
result/                실행 결과와 로그 (커밋하지 않음)
```

## 개발

```bat
python -m unittest discover -s tests/unit
```

작업 규칙은 [AGENTS.md](AGENTS.md), 커밋 규칙은
[docs/ai/commit-convention.md](docs/ai/commit-convention.md)에 있습니다.
