# TC별 분기 표 1단계(데이터 찾기) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CT가 케이스별 분기 결과를 어디에 어떤 꼴로 남기는지 서버 PC 한 번의 확인으로 찾는다. 견본 소스와 정답 표,
실행 전후 파일 비교 조사 도구, todo.md 28절을 만든다.

**Architecture:** 조사 도구 하나(`tools/run_diff_probe.py`)가 대화식으로 돈다. 작업 공간 폴더를 받고, 파일 목록을 찍고,
사용자가 CT에서 실행하면 다시 찍어 비교한다. 이어서 `.csd`를 보고, CT를 다시 연 뒤 한 번 더 찍는다. 화면에는 가린 상대
경로와 개수만 찍고, 절대 경로가 든 전체 목록은 `result\branch_probe\run_diff.json`에 쓴다(다음 확인이 다시 쓴다).
2단계(읽기 코드와 `branch-table.bat`)는 이 확인 결과를 보고 따로 계획한다.

**Tech Stack:** Python 3.8+ 표준 라이브러리, unittest.

**Spec:** [branch-table.md](branch-table.md)

## Global Constraints

- Python 3.8 이상 문법만 쓴다(`str.removeprefix`, `list[str]` 같은 런타임 제네릭, `match` 문 금지). 파일마다
  `from __future__ import annotations`.
- 외부 패키지를 쓰지 않는다.
- 단위 테스트는 `tests/unit`의 unittest. 실행: `python -m unittest discover -s tests/unit`.
- 화면은 120열 40줄 안쪽이다. 줄 폭은 `member_probe.WIDTH`(118)를 넘지 않는다.
- 화면에는 개수, 정해 둔 문구, 가린 상대 경로, 꼴 이름, 앞 8바이트 16진수만 찍는다. 끌어다 놓은 경로는 받은 뒤
  화면을 지워 캡처에 남기지 않는다. 예외 메시지 원문은 찍지 않는다.
- 견본과 테스트의 이름은 지어낸 것(`dmy_`, `secret_`)만 쓴다. 견본 C 파일은 ASCII만 쓴다.
- 툴킷은 작업 공간과 CT 설치 폴더를 읽기만 한다. 쓰는 곳은 `paths.result_dir() / 'branch_probe'`뿐이다.
- 커밋은 Conventional Commits, 한국어 요약, 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  조사 도구는 CHANGELOG에 적지 않는다(지금까지의 조사 도구와 같음).

## Review Focus

- `%LOCALAPPDATA%`처럼 큰 폴더에서 목록을 찍다 권한 없는 폴더, 잠긴 파일, 그사이 지워진 파일을 만나면 멈추지 않고
  "못 읽은 폴더" 개수로 센다. → Task 2 `test_snapshot_skips_unreadable`.
- `%TEMP%`는 보통 `%LOCALAPPDATA%` 안에 있다. 한 파일을 두 번 세지 않고 가장 안쪽 뿌리(`TEMP`)로 적는다. →
  Task 2 `test_locate_picks_innermost_root`.
- 계정 이름이나 한글이 든 폴더 이름은 가려서 찍는다(`?`). → Task 2 `test_mask_path_hides_names`.
- 바뀐 파일이 아주 크면(기본 64MB 넘음) 이름 찾기를 건너뛰고 `-`로 찍는다. 멈추지 않는다. → Task 2
  `test_names_found_skips_big_file`.
- 사용자가 경로를 따옴표째 끌어다 놓거나, `.csd` 물음에 그냥 Enter를 누른다. → Task 3 `test_main_flow`,
  `test_main_skips_csd`.

---

### Task 1: 견본 소스와 정답 표

**Files:**
- Create: `examples/ct_sample/dmy_branch.example.c`

**Interfaces:**
- Produces: 함수 `int dmy_branch(int dmy_a, int dmy_b)`, 케이스 이름 `dmy_case_a`~`dmy_case_d`. Task 2의 `NAMES`와
  todo.md 28절이 이 이름을 쓴다.

- [ ] **Step 1: 견본 파일을 쓴다**

머리 주석은 `dmy_carry.example.c`처럼 "지어낸 견본, 고객 코드 아님, ASCII만, `dmy_` 이름"을 적는다. 함수 몸통은 이대로
쓴다(정답 표가 이 몸통에 맞춰 있다).

```c
int dmy_branch(int dmy_a, int dmy_b)
{
    int dmy_r;
    int dmy_i;

    if (dmy_a > 10) {
        dmy_r = 1;
    } else if (dmy_a < 0) {
        dmy_r = 2;
    } else {
        dmy_r = 3;
    }

    switch (dmy_b) {
    case 1:
        dmy_r += 10;
        break;
    case 2:
        dmy_r += 20;
        break;
    default:
        dmy_r += 30;
        break;
    }

    for (dmy_i = 0; dmy_i < dmy_b; dmy_i++) {
        dmy_r++;
    }

    if (dmy_a == 5 && dmy_b == 5) {
        dmy_r += 100;
    }

    while (dmy_r > 100) {
        dmy_r -= 100;
    }

    return (dmy_r > 20) ? dmy_r : -dmy_r;
}
```

함수 아래 주석에 케이스 값과 정답 표를 둔다.

```
case        dmy_a  dmy_b  return
dmy_case_a     20      1     -12
dmy_case_b     -3      2      24
dmy_case_c      5      0      33
dmy_case_d      5      5      38

decision (source order)          a      b      c        d
1 if (dmy_a > 10)                T      F      F        F
2 else if (dmy_a < 0)            -      T      F        F
3 switch (dmy_b)                 case 1 case 2 default  default
4 for (dmy_i < dmy_b)            T/F    T/F    F        T/F
5 if (dmy_a == 5 && dmy_b == 5)  F      F      F        T
6 while (dmy_r > 100)            F      F      F        T/F
7 (dmy_r > 20) ? :               F      T      T        T
```

- [ ] **Step 2: 정답 표를 손으로 다시 따라간다**

케이스마다 몸통을 한 줄씩 따라가 표의 칸과 `return` 값이 맞는지 본다. 예: `dmy_case_d`는 `dmy_r` 3 → 33 → 반복 5번에 38 →
`&&` 참으로 138 → `while` 한 번 돌아 38 → `38 > 20` 참이라 38을 돌려준다. 이 PC에 C 컴파일러가 있으면(`gcc --version`)
케이스 넷을 돌려 `return` 값까지 확인한다.

- [ ] **Step 3: 커밋**

```bash
git add examples/ct_sample/dmy_branch.example.c
git commit -m "test: 케이스별 분기 결과를 찾을 견본 소스와 정답 표를 더한다"
```

---

### Task 2: 조사 도구의 부품(목록 찍기, 비교, 꼴, 가리기)

**Files:**
- Create: `tools/run_diff_probe.py`
- Test: `tests/unit/test_run_diff_probe.py`(모듈은 `test_todo_run.py`처럼 `importlib`로 경로에서 읽는다)

**Interfaces:**
- Consumes: `tools/utest_probe.py`의 `shape(text: str, limit: int = 60) -> str`(가리기), `tools/member_probe.py`의 `WIDTH`.
- Produces (Task 3이 쓴다):
  - `NAMES: Tuple[str, ...] = ('dmy_branch', 'dmy_case_a', 'dmy_case_b', 'dmy_case_c', 'dmy_case_d')`
  - `Snap = Dict[str, Tuple[int, int]]` — 절대 경로 → (크기, `st_mtime_ns`)
  - `snapshot(roots: Sequence[Path]) -> Tuple[Snap, int]` — (목록, 못 읽은 폴더 수)
  - `diff(before: Snap, after: Snap) -> Dict[str, List[str]]` — 키 `'new'`, `'changed'`, `'removed'`, 값은 정렬한 절대 경로
  - `locate(path: str, roots: Sequence[Tuple[str, Path]]) -> Tuple[str, str]` — (뿌리 이름, 그 뿌리 기준 상대 경로)
  - `kind(head: bytes) -> str`
  - `names_found(path: Path, limit: int = 64 << 20) -> Optional[int]`
  - `mask_path(rel: str) -> str`
  - `zip_entries(path: Path) -> List[Tuple[str, int, str, Optional[int]]]` — (항목 이름 원문, 크기, 꼴, 견본 이름 수)

- [ ] **Step 1: 실패하는 테스트를 쓴다**

| 테스트 | 확인할 것 |
| --- | --- |
| `test_kind` | `b''`→`'empty'`, `b'PK\x03\x04…'`→`'zip'`, `b'\x1f\x8b…'`→`'gzip'`, `b'SQLite format 3\x00…'`→`'sqlite'`, `b'H:2,block…'`→`'h2'`, `b'\xac\xed\x00\x05…'`→`'java-ser'`, `b'\x00\x01\x2acom.codescroll…'`→`'fst?'`, `b'\xff\xfe<\x00'`→`'utf16'`, `b'\xef\xbb\xbf  <?xml'`→`'xml'`, `'가나다'.encode()*200`을 512바이트에서 자른 것→`'text'`, `bytes(range(256))`→`'binary'` |
| `test_mask_path_hides_names` | `mask_path('.metadata/.plugins/com.codescroll.ut.core_1.0.0/secret_prj/dmy_branch_test0.dat')` == `'.metadata\\.plugins\\com.codescroll.ut.core_1.0.0\\aaaaaa_aaa\\dmy_branch_test0.dat'`; `mask_path('Users\\홍길동\\ctsample\\Run9.bin')` == `'Aaaaa\\???\\ctsample\\Aaa9.bin'`; 결과에 `secret`이 없다 |
| `test_snapshot_and_diff` | 임시 폴더에 `a.txt`, `b.txt`를 두고 찍은 뒤 `a.txt` 내용을 바꾸고 `b.txt`를 지우고 `c.txt`를 만든다. `diff`가 `new==[c]`, `changed==[a]`, `removed==[b]` |
| `test_snapshot_skips_unreadable` | `os.stat`(또는 `os.scandir`)이 한 파일·한 폴더에서 `PermissionError`를 내게 `mock`하면, 예외 없이 나머지를 찍고 못 읽은 수가 1 이상 |
| `test_locate_picks_innermost_root` | 뿌리 `[('LOCALAPPDATA', L), ('TEMP', L/'Temp')]`에서 `L/'Temp'/'x.bin'` → `('TEMP', 'x.bin')`; 두 뿌리를 함께 찍은 `snapshot`에 그 파일이 한 번만 있다 |
| `test_names_found` | ASCII `dmy_case_a`와 UTF-16LE `dmy_case_b`가 든 파일 → 2; 아무것도 없는 파일 → 0 |
| `test_names_found_skips_big_file` | `limit=10`에 20바이트 파일 → `None`; 없는 파일 → `None` |
| `test_zip_entries` | 항목 둘(`secret_a.xml`에 `<r>dmy_case_c</r>`, `b.bin`에 임의 바이트)인 zip → `[('secret_a.xml', 17, 'xml', 1), ('b.bin', n, 'binary', 0)]`; zip이 아닌 파일 → `[]` |

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `python -m unittest tests.unit.test_run_diff_probe -v` (저장소 루트에서)
Expected: 모듈이 없어 FAIL(`FileNotFoundError` 또는 `ModuleNotFoundError`)

- [ ] **Step 3: 부품을 구현한다**

- 머리 docstring에 이 도구가 무엇을 왜 하는지(todo.md 28절, 설계 `docs/design/branch-table.md` 1단계)와 화면에 찍는 것의
  범위를 적는다(`java_probe.py` 머리처럼).
- `snapshot`: `os.walk(root, onerror=…)`로 돌고 파일마다 `os.stat`. 폴더를 못 열거나 파일 `stat`이 `OSError`면 세고 넘어간다.
  여러 뿌리의 결과는 절대 경로 키로 합쳐 중복이 없다.
- `locate`: 경로를 품은 뿌리 중 가장 긴 것을 고른다.
- `kind`: 위 표의 차례로 본다. `fst?`는 `head[:2] == b'\x00\x01'`이고 `head[3:].startswith(b'com.')`. `xml`은 UTF-8 BOM과 앞
  공백을 뗀 뒤 `<`로 시작. `text`는 UTF-8로 풀리고(끝에서 잘린 글자 하나는 봐준다) 제어 문자가 `\t\r\n`뿐일 때.
- `mask_path`: `\`와 `/`로 나눈 마디마다, 다음이면 그대로 둔다: `dmy_`로 시작, `ctsample`, `\.[A-Za-z]\w*`(`.metadata` 같은
  점 폴더), `(?:com|org|net|java|javax|jdk|sun)\.[\w.-]+`, 소문자로 `codescroll`이나 `suresoft`가 듦. 아니면 마지막 확장자
  (`\.[A-Za-z0-9]{1,8}$`)는 두고 앞부분만 `utest_probe.shape`로 가린다. 마디는 `\`로 잇는다.
- `names_found`: 크기가 `limit`보다 크거나 읽지 못하면 `None`. 아니면 `NAMES` 중 ASCII나 UTF-16LE로 든 것의 수.
- `zip_entries`: `zipfile.BadZipFile`·`OSError`면 `[]`. 항목마다 앞 512바이트로 `kind`, 64MB 안이면 이름 수.

- [ ] **Step 4: 테스트가 통과하는지 본다**

Run: `python -m unittest tests.unit.test_run_diff_probe -v`
Expected: 8개 모두 OK

- [ ] **Step 5: 커밋은 Task 3과 함께 한다**(이 부품만으로는 쓸 데가 없다)

---

### Task 3: 조사 도구의 흐름과 한 화면 결과

**Files:**
- Modify: `tools/run_diff_probe.py`
- Test: `tests/unit/test_run_diff_probe.py`

**Interfaces:**
- Consumes: Task 2의 모든 부품.
- Produces: `main(argv: Sequence[str], ask: Callable[[str], str] = input, clear: Callable[[], None] = _clear, environ:
  Optional[Mapping[str, str]] = None, out_dir: Optional[Path] = None) -> int`. `out_dir` 기본값은
  `paths.result_dir() / 'branch_probe'`. `if __name__ == '__main__': sys.exit(main(sys.argv[1:]))`.
  todo.md 28절(Task 4)이 `tools/run_diff_probe.py`를 인수 없이 부른다.

**흐름과 문구(그대로 쓴다):**

1. `CT_HOME`이 없거나 폴더가 아니면 `E_HOME = '[ERROR] CT 설치 폴더를 받지 못함: todo.bat 28을 다시 돌리고 물으면 CT 설치 폴더를 끌어다 놓기'`, 종료 코드 2.
2. `ask(P_WS)`, `P_WS = '견본 작업 공간 폴더(ctsample 프로젝트가 든 CT 작업 공간)를 이 창에 끌어다 놓고 Enter: '`. 따옴표와
   공백을 떼고(`todo_run.clean_path`와 같게) `clear()`. 폴더가 아니면 `E_WS = '[ERROR] 작업 공간 폴더가 아님: todo.bat 28을 다시 돌리고 CT 작업 공간 폴더를 끌어다 놓기'`, 종료 코드 2.
3. 뿌리: `WS`(받은 폴더), `CT`(`CT_HOME`), `TEMP`, `APPDATA`, `LOCALAPPDATA`(환경 변수, 없거나 폴더가 아니면 뺀다).
   `M_SCAN = '파일 목록을 찍는 중(몇 분 걸릴 수 있음)…'`을 찍고 `snapshot` → 앞 목록.
4. `ask(P_RUN)`, `P_RUN = 'CT에서 dmy_branch 테스트를 실행한 뒤 이 창에서 Enter: '`. `M_SCAN`, `snapshot` → 실행 뒤 목록, `diff`.
5. `ask(P_CSD)`, `P_CSD = 'CT [내보내기] > [커버리지 내보내기]로 만든 .csd 파일을 끌어다 놓고 Enter(없으면 그냥 Enter): '`.
   따옴표를 떼고 `clear()`.
6. `ask(P_REOPEN)`, `P_REOPEN = 'CT를 닫았다 다시 열고, 케이스 하나를 골라 소스 편집기에 참·거짓 표시가 보이면 이 창에서 Enter: '`.
   `M_SCAN`, `snapshot` → 다시 연 뒤 목록. 실행 때 새로 생기거나 바뀐 파일마다 다시 연 뒤 `남음`(크기·시각 같음),
   `바뀜`, `없음`을 정한다.
7. `clear()` 뒤 결과를 찍고, `out_dir / 'run_diff.json'`을 쓴다. 바뀐 파일이 0이면 종료 코드 1, 아니면 0.

**결과 화면(이 차례, 40줄 안쪽):**

```
28절 결과: 실행 전후 파일 비교
목록: WS 1234, CT 5678, TEMP 90, APPDATA 1200, LOCALAPPDATA 34000개, 못 읽은 폴더 3, 목록 찍기 3번 95초
[WARN] .metadata가 없음: 끌어다 놓은 폴더가 CT 작업 공간인지 확인        ← 받은 폴더에 .metadata가 없을 때만
실행 뒤: 새로 12, 바뀜 5, 지워짐 1 (WS 10, CT 0, TEMP 6, APPDATA 1, LOCALAPPDATA 1)
견본 이름이 든 것 4, CT 관련 경로 6, 나머지 8은 json에만
상태 다시연뒤      크기 꼴       앞 8바이트              이름 경로
새   남음       123456 zip      50 4b 03 04 14 00 08 00  3/5  WS\.metadata\.plugins\com.codescroll.ut.core\aaaa9.dat
…(최대 16줄)
.csd: 크기 9999, 꼴 zip, 견본 이름 3/5, 항목 4개                          ← 건너뛰면 '.csd: 건너뜀'
  항목 aaaa.xml        2048 xml      이름 2/5                             ← zip일 때 항목 최대 8줄
다시 연 뒤: 실행 때 생기거나 바뀐 18개 중 남음 16, 바뀜 1, 없음 1, 다시 열며 새로 바뀐 것 40
자세한 목록: result\branch_probe\run_diff.json
```

- 실행 뒤 줄이 0이면 그 자리에 `W_NONE = '[WARN] 실행 뒤 바뀐 파일 0: CT에서 테스트를 실제로 실행했는지 확인하고 다시 돌리기'`.
- 표에 넣는 차례: 견본 이름 수가 많은 것, CT 관련 경로(뿌리가 `WS`·`CT`이거나 경로에 `codescroll`·`suresoft`), 크기가 큰 것.
  견본 이름도 없고 CT 관련도 아닌 파일은 개수만 센다. 지워진 파일은 꼴·이름 칸을 `-`로 둔다.
- 경로 칸은 `<뿌리>\` + `mask_path(상대 경로)`이고, 줄이 `WIDTH`를 넘으면 경로 앞쪽을 `…`로 줄여 파일 이름을 남긴다.
- `run_diff.json`(서버 PC에만 남음): 뿌리별 절대 경로, 파일마다 절대 경로·뿌리·상대 경로·상태·다시 연 뒤·크기·꼴·앞 32바이트
  16진수·이름 수·zip 항목, `.csd`의 같은 정보, 다시 열며 새로 바뀐 파일의 절대 경로.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

| 테스트 | 확인할 것 |
| --- | --- |
| `test_main_flow` | 임시 폴더로 뿌리 다섯을 만들고(`TEMP`는 `LOCALAPPDATA` 안, `WS`에 `.metadata`, 경로에 `secret_user`가 든 폴더), `ask`가 물음마다 다음을 한다: `P_WS`에 `'"<WS>"'` 반환; `P_RUN`에 `WS\.metadata\.plugins\com.codescroll.ut.core\secret_dir\run1.dat`(내용 `b'..dmy_case_a..'`)와 `TEMP\secret_tmp.bin`을 만들고 미리 둔 `WS\.metadata\.log`를 크기가 달라지게 바꿈; `P_CSD`에 UTF-16LE `dmy_case_b`가 든 항목 하나짜리 zip `.csd` 경로 반환; `P_REOPEN`에 `run1.dat`을 지움. 결과: 종료 코드 0, 출력에 `새로 2`, `바뀜 1`, `.csd: 크기`, `이름 1/5`, `없음 1`, `aaa9.dat`; 출력 어디에도 `secret`과 임시 폴더 경로가 없음; 줄 수 40 이하, 줄마다 `WIDTH` 이하; `clear`가 `P_WS` 뒤와 결과 앞에서 불림; `out_dir/'run_diff.json'`에 `run1.dat`의 절대 경로가 있음. `.csd`와 `out_dir`은 뿌리 밖 임시 폴더에 둔다 |
| `test_main_skips_csd` | `P_CSD`에 `''` → 출력에 `.csd: 건너뜀` |
| `test_main_no_change` | `P_RUN`에서 아무것도 안 바꿈 → 출력에 `W_NONE`, 종료 코드 1 |
| `test_main_bad_inputs` | `CT_HOME` 없음 → `E_HOME`, 2; `P_WS`에 없는 폴더 → `E_WS`, 2 |
| `test_main_many_files` | `P_RUN`에서 CT 관련 파일 30개를 만듦 → 표 줄 16개, `나머지` 줄의 수가 맞고 줄 수 40 이하 |

- [ ] **Step 2: 테스트가 실패하는지 본다**

Run: `python -m unittest tests.unit.test_run_diff_probe -v`
Expected: 새 테스트 5개가 `main`이 없어 FAIL, Task 2의 8개는 OK

- [ ] **Step 3: `main`과 화면 찍기를 구현한다**

화면 줄을 만드는 일은 `summary_lines(...) -> List[str]`로 떼어 `main`은 흐름만 갖게 한다(인자는 구현자가 정한다). 걸린 시간은
`time.monotonic()`으로 잰다.

- [ ] **Step 4: 테스트가 통과하는지 본다**

Run: `python -m unittest tests.unit.test_run_diff_probe -v`
Expected: 13개 모두 OK

- [ ] **Step 5: 이 PC에서 한 번 손으로 돌려 본다**

임시 폴더 다섯을 뿌리로 주는 작은 스크립트나 `cmd`에서 환경 변수를 잡고 `python tools\run_diff_probe.py`를 돌려, 물음마다
Enter를 누르며 화면 모양과 한글이 깨지지 않는지 본다(`PYTHONUTF8=1`).

- [ ] **Step 6: 전체 단위 테스트를 돌린다**

Run: `python -m unittest discover -s tests/unit`
Expected: 모두 OK

- [ ] **Step 7: 커밋**

```bash
git add tools/run_diff_probe.py tests/unit/test_run_diff_probe.py
git commit -m "feat: CT 실행 전후 파일을 비교해 케이스별 분기 데이터를 찾는 조사 도구를 더한다"
```

---

### Task 4: todo.md 28절, 27절 내리기, 인수인계, 배포

**Files:**
- Modify: `todo.md`(27절을 지우고 28절을 쓴다), `tools/todo_run.py:32-35`(`SECTIONS`), `docs/ai/handoff.md`,
  `docs/archive/handoff-history.md`(끝에 날짜 절), `docs/design/branch-table.md`(상태 줄)
- Test: `tests/unit/test_todo_run.py`(바뀌는 것 없음, 돌리기만)

**Interfaces:**
- Consumes: Task 1의 견본 경로와 케이스 이름, Task 3의 문구(`P_*`).
- Produces: `SECTIONS = {'28': ('실행 전후 파일 비교로 케이스별 분기 데이터 찾기', ['tools/run_diff_probe.py', CT])}`.

- [ ] **Step 1: `SECTIONS`를 바꾼다**

`'27'`을 지우고 위 `'28'` 하나만 둔다.

- [ ] **Step 2: todo.md를 고친다**

맨 위 "지금 할 일" 표(순서, 어디서, 할 일, 걸리는 시간):

| 순서 | 어디서 | 할 일 | 걸리는 시간 |
| --- | --- | --- | --- |
| 1 | 탐색기 | 저장소의 `examples\ct_sample\dmy_branch.example.c`를 `C:\ctsample\src\dmy_branch.c`로 복사 | 1분 |
| 2 | CT | `ctsample` 프로젝트에 넣고 분석 → `dmy_branch` 테스트 만들기 → 케이스를 28절 표대로 4개 두기(자동으로 생긴 케이스는 지우고, F2로 이름을 바꿈). **아직 실행하지 않는다** | 5분 |
| 3 | `todo.bat` | 더블클릭 → `28` → 물음대로(작업 공간 폴더 끌어다 놓기 → CT에서 실행 → `.csd` 내보내 끌어다 놓기 → CT 닫았다 다시 열기) | 10~15분 |
| 4 | 화면 | 끝 화면을 캡처해서 보내기. 오른쪽 위 워터마크는 잘라서 | |

그 아래: CT에서 할 일이 있다는 것, 돌려줄 것(화면 한 장), `result\branch_probe\run_diff.json`은 보내지 않는다는 것.

28절 본문:
- **왜:** 분기 표는 CT가 잰 케이스별 결과로만 채운다(설계 `docs/design/branch-table.md`). CT는 케이스를 고르면 소스 편집기에
  참·거짓을 그리므로 결과가 어딘가 있다. 실행 전후로 바뀐 파일과 `.csd`를 보고, CT를 다시 연 뒤에도 남는지 본다.
  이 확인은 파일을 읽기만 한다.
- 케이스 표: Task 1의 케이스 값 표(이름, `dmy_a`, `dmy_b`). 실행 뒤 CT 화면의 리턴 값이 `return` 칸과 같은지도 본다.
- **확인할 것:** 화면의 줄(`목록`, `실행 뒤`, 표, `.csd`, `다시 연 뒤`)과 볼 것의 표. 표에서는 "견본 이름이 든 파일"과
  "다시 연 뒤 남음"인 CT 관련 파일이 후보다.
- 27절은 지운다(`.utest` 길은 입력·출력 지정을 다시 볼 때 이어 간다).

- [ ] **Step 3: 인수인계 문서를 고친다**

- `docs/ai/handoff.md` "현재 기준": 기준일 2026-11-24. 2026-11-20 목표를 다시 정해 일을 둘로 나누고 분기 표를 먼저 한다는 것,
  설계(`docs/design/branch-table.md`, 2026-11-24 승인)와 이 계획의 링크, 28절 요청. "다음 할 일"을 분기 표 1단계로 바꾼다.
  `.utest` 관련 줄들은 지우지 않고 그 앞에 "입력·출력 지정(보류, 2026-11-20)" 머리 줄을 둔다.
- `docs/archive/handoff-history.md` 끝: `## 2026-11-20 목표를 다시 정하고 TC별 분기 표부터 함` 절에 사용자가 말한 두 가지
  일, 분기 표가 검토자 제출물이라 정확해야 한다는 것, 방법 A를 고른 것, 27절을 내린 것, 2025.12 CLI 키 확인(입력·출력
  지정·커버리지 내보내기 키 없음)을 적는다.
- `docs/design/branch-table.md` 상태 줄: `상태: 승인(2026-11-24).`

- [ ] **Step 4: 전체 단위 테스트를 돌린다**

Run: `python -m unittest discover -s tests/unit`
Expected: 모두 OK

- [ ] **Step 5: 커밋**

```bash
git add todo.md tools/todo_run.py docs/ai/handoff.md docs/archive/handoff-history.md docs/design/branch-table.md
git commit -m "docs: 케이스별 분기 데이터를 찾는 28절을 요청하고 .utest 조사 27절을 내린다"
```

- [ ] **Step 6: 서버 PC가 받게 `develop`과 `main`에 올린다**

`git fetch` 뒤 `origin/develop`과 `origin/main`이 이 브랜치의 조상인지 확인하고(fast-forward만), `git push origin HEAD:develop HEAD:main`.
조상이 아니면 멈추고 사용자에게 알린다.
