# 목록대로 입력·출력 지정하기 1차 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CT 파일 형식과 상관없는 부분을 만든다. 목록 XLSX 읽기, 목록과 테스트 맞춰 보기, 한 화면 요약,
`skipped.txt`, `ct.bat io-apply` 연결이 대상이다. 서버 PC에서 `ct.bat io-apply --list <목록>`으로
목록이 툴킷 형식에 맞는지 확인할 수 있게 한다.

**Architecture:** 모듈 넷으로 나눈다. `io_list`(목록 읽기), `io_match`(맞춰 보기, 순수 함수),
`ct_export`(CT 내보낸 폴더 읽기·사본 쓰기, 이번에는 "아직 없음"만 던진다), `io_apply`(명령, 화면,
`skipped.txt`)다. `io_apply.main`은 읽기·불러오기·쓰기 함수를 인자로 받아 단위 테스트에서 가짜로
바꾼다. 2차(todo.md 2절 결과 후)는 `ct_export`의 몸통만 채운다.

**Tech Stack:** Python 3.8+ 표준 라이브러리, openpyxl(목록 읽기만), unittest.

**Spec:** [io-designation.md](io-designation.md)

## Global Constraints

- Python 3.8 이상 문법만 쓴다(`str.removeprefix`, `list[str]` 같은 런타임 제네릭, `match` 문 금지).
  파일마다 `from __future__ import annotations`.
- 외부 패키지는 openpyxl뿐이고 목록 읽기에서만 import한다. 없으면 정해 둔 문구를 찍고 종료 코드 1.
- 단위 테스트는 `tests/unit`의 unittest. 실행: `python -m unittest discover -s tests/unit`.
- 화면(콘솔)과 로그 파일에는 개수, 정해 둔 문구, 출력 파일 이름만 넣는다. 함수·변수·파일 이름과
  경로는 `skipped.txt`에만 쓴다. 예외 메시지 원문은 어디에도 찍지 않고 예외 클래스 이름만 로그에 남긴다.
- 결과는 `paths.result_dir() / 'io' / <yyyyMMdd_HHmmss>`에 쓴다. 화면에는
  `result\io\<yyyyMMdd_HHmmss>\`처럼 저장소 기준 상대 경로만 찍는다.
- 예제와 테스트의 이름은 지어낸 것(`dmy_`, `secret_`)만 쓴다.
- 커밋은 Conventional Commits, 한국어 요약, 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  사용자에게 보이는 변경은 같은 커밋에 `CHANGELOG.md`를 고친다.
- 서버 PC에서 돌려 보기 전에는 "정적 구현 완료"까지만 쓴다.

## Review Focus

테스트가 직접 다루지 않지만 사용자가 실제로 부딪힐 만한 것. 각 줄의 테스트를 해당 태스크에 넣었다.

1. Codebeamer 내보내기의 머리글에 앞뒤 공백이 있거나, 머리글 위에 제목 줄이 있다. 공백은 받아들이고,
   제목 줄은 머리글 오류 문구로 멈춘다(Task 1 `test_header_spaces_ok_title_row_rejected`).
2. 목록 파일이 엑셀에 열려 있거나 경로가 틀렸다. 원문 없이 정해 둔 문구로 멈춘다(Task 1
   `test_read_list_missing_file_fixed_message`).
3. 칸 값이 숫자 0이거나 수식이다. 0은 빈칸이 아니라 `'0'`이다(Task 1 `test_zero_cell_is_text`).
4. 머리글만 있고 데이터 줄이 없다. 모두 0으로 찍고 종료 코드 0(Task 3 `test_main_empty_list`).
5. 같은 머리글이 두 번 있다. 첫 칸을 쓴다(Task 1 `test_duplicate_header_uses_first`).

---

### Task 1: 목록 XLSX 읽기

**Files:**
- Create: `src/ct_toolkit/io_list.py`
- Test: `tests/unit/test_io_list.py`

**Interfaces:**
- Produces:
  - 상수 `REQUIRED_HEADERS = ('함수', '변수', '구분')`, `OPTIONAL_HEADERS = ('파일', '타입', '범위')`,
    `DIRECTIONS = {'입력': 'in', '출력': 'out', '입출력': 'inout'}`
  - 상수 문구 `E_NO_OPENPYXL = 'openpyxl이 없음: 서버 PC에서 pip install -r requirements.txt'`,
    `E_LIST_OPEN = '목록을 열 수 없음: 파일이 있는지, XLSX인지, 엑셀에서 열려 있지 않은지 확인'`,
    `E_LIST_HEADER = '목록 첫 줄에 머리글이 없음({}): 첫 줄을 머리글로 맞추기'`(빠진 머리글을 `, `로 이어 넣는다)
  - 사유 `R_LIST_EMPTY = '목록 오류(필수 칸 비었음)'`, `R_LIST_DIRECTION = '목록 오류(구분 값)'`
  - `class ListFileError(Exception)`: `str(exc)`는 위 정해 둔 문구 중 하나뿐이다.
  - `@dataclass(frozen=True) class ListRow: row: int; function: str; variable: str; direction: str; file: str = ''; type_name: str = ''; range_text: str = ''`
    (`row`는 엑셀 행 번호, 머리글이 1행. `direction`은 `'in'|'out'|'inout'`)
  - `@dataclass(frozen=True) class ListError: row: int; function: str; variable: str; reason: str`
  - `@dataclass class ListRead: rows: List[ListRow]; errors: List[ListError]`, 속성 `total -> int`
    (`len(rows) + len(errors)`), `functions -> int`(`rows`의 서로 다른 함수 수)
  - `parse_rows(rows: Iterable[Sequence[object]]) -> ListRead`: 첫 항목이 머리글. 머리글이 없으면
    `ListFileError(E_LIST_HEADER.format(...))`.
  - `read_list(path: Path, importer: Callable[[str], object] = importlib.import_module) -> ListRead`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/unit/test_io_list.py`. 기존 테스트처럼 `sys.path.insert(0, .../src)`로 import한다.

```python
class ParseRowsTest(unittest.TestCase):
    def test_reads_rows_by_header_name_in_any_order(self):
        got = parse_rows([('구분', '기타', '변수', '함수', '범위'),
                          ('입력', 'x', 'dmy_gain', 'dmy_calc', '0~10'),
                          ('입출력', None, 'return', 'dmy_calc', None)])
        self.assertEqual(got.rows, [
            ListRow(2, 'dmy_calc', 'dmy_gain', 'in', range_text='0~10'),
            ListRow(3, 'dmy_calc', 'return', 'inout')])
        self.assertEqual((got.total, got.functions, got.errors), (2, 1, []))

    def test_strips_spaces_keeps_case(self):
        row = parse_rows([('함수', '변수', '구분'), (' Dmy_Calc ', ' Dmy_A', '출력 ')]).rows[0]
        self.assertEqual((row.function, row.variable, row.direction), ('Dmy_Calc', 'Dmy_A', 'out'))

    def test_blank_rows_ignored(self):
        got = parse_rows([('함수', '변수', '구분'), (None, None, None), ('', ' ', None),
                          ('dmy_calc', 'dmy_x', '입력')])
        self.assertEqual((got.total, got.rows[0].row), (1, 4))

    def test_missing_required_cell_is_error(self):
        got = parse_rows([('함수', '변수', '구분'), ('dmy_calc', None, '입력')])
        self.assertEqual(got.errors, [ListError(2, 'dmy_calc', '', R_LIST_EMPTY)])
        self.assertEqual(got.total, 1)

    def test_unknown_direction_is_error(self):
        got = parse_rows([('함수', '변수', '구분'), ('dmy_calc', 'dmy_x', 'Input')])
        self.assertEqual(got.errors[0].reason, R_LIST_DIRECTION)

    def test_missing_header_raises_fixed_message(self):
        with self.assertRaises(ListFileError) as ctx:
            parse_rows([('함수', '변수'), ('dmy_calc', 'dmy_x')])
        self.assertEqual(str(ctx.exception), E_LIST_HEADER.format('구분'))

    def test_header_spaces_ok_title_row_rejected(self):
        self.assertEqual(parse_rows([(' 함수', '변수 ', '구분')]).total, 0)
        with self.assertRaises(ListFileError):
            parse_rows([('입력 목록', None, None), ('함수', '변수', '구분')])

    def test_optional_columns_default_empty(self):
        row = parse_rows([('함수', '변수', '구분'), ('dmy_calc', 'dmy_x', '입력')]).rows[0]
        self.assertEqual((row.file, row.type_name, row.range_text), ('', '', ''))

    def test_zero_cell_is_text(self):
        row = parse_rows([('함수', '변수', '구분', '범위'), ('dmy_calc', 'dmy_x', '입력', 0)]).rows[0]
        self.assertEqual(row.range_text, '0')

    def test_duplicate_header_uses_first(self):
        row = parse_rows([('함수', '변수', '구분', '변수'), ('dmy_calc', 'dmy_x', '입력', 'dmy_y')]).rows[0]
        self.assertEqual(row.variable, 'dmy_x')


class ReadListTest(unittest.TestCase):
    def test_read_list_without_openpyxl(self):
        def no_module(name):
            raise ImportError(name)
        with self.assertRaises(ListFileError) as ctx:
            read_list(Path('x.xlsx'), importer=no_module)
        self.assertEqual(str(ctx.exception), E_NO_OPENPYXL)

    @unittest.skipUnless(HAS_OPENPYXL, 'openpyxl 없음')
    def test_read_list_missing_file_fixed_message(self):
        # 임시 폴더 아래 secret_dir/없는.xlsx. 문구가 정확히 E_LIST_OPEN이고 'secret'이 없다
        ...

    @unittest.skipUnless(HAS_OPENPYXL, 'openpyxl 없음')
    def test_read_list_reads_first_sheet(self):
        # openpyxl.Workbook()으로 첫 시트에 머리글+한 줄, 둘째 시트에 다른 내용 → rows 1개, 첫 시트 값
        ...

    @unittest.skipUnless(HAS_OPENPYXL, 'openpyxl 없음')
    def test_read_list_not_xlsx_fixed_message(self):
        # secret_dir/list.xlsx에 일반 텍스트를 쓴다 → ListFileError, str == E_LIST_OPEN
        ...
```

`HAS_OPENPYXL = importlib.util.find_spec('openpyxl') is not None`. 파일을 실제로 여는 테스트
셋은 openpyxl이 없으면 건너뛴다(없으면 `E_NO_OPENPYXL`이 먼저 나기 때문이다).

- [ ] **Step 2: 실패를 확인한다**

Run: `python -m unittest tests.unit.test_io_list -v` (저장소 루트, `PYTHONPATH` 없이 테스트 파일의 `sys.path`로)
Expected: `ModuleNotFoundError: No module named 'ct_toolkit.io_list'`로 실패.

- [ ] **Step 3: `io_list.py`를 구현한다**

- 칸 값 → 문자열: `None`이면 `''`, 아니면 `str(value).strip()`. 참·거짓으로 빈칸을 가리지 않는다(0 때문에).
- 빈 줄(모든 칸이 `''`)은 세지 않는다. 행 번호는 빈 줄도 포함한 엑셀 행 번호다.
- 필수 칸이 빈 줄은 `R_LIST_EMPTY`, `구분`이 `DIRECTIONS`에 없으면 `R_LIST_DIRECTION`. 둘 다면 앞의 것.
- `read_list`: `importer('openpyxl')`가 `ImportError`면 `E_NO_OPENPYXL`.
  `load_workbook(path, read_only=True, data_only=True)`의 `worksheets[0]`에서 `iter_rows(values_only=True)`.
  여는 중 나는 모든 예외(`Exception`)는 원문을 버리고 `ListFileError(E_LIST_OPEN)`으로 바꾼다.
  다 읽으면 workbook을 닫는다.

- [ ] **Step 4: 통과를 확인한다**

Run: `python -m unittest tests.unit.test_io_list -v`
Expected: 모두 OK(openpyxl이 없는 Python이면 skip 3개).

- [ ] **Step 5: 커밋**

```bash
git add src/ct_toolkit/io_list.py tests/unit/test_io_list.py
git commit  # feat: 입력·출력 지정 목록 XLSX를 머리글 이름으로 읽는다
```

---

### Task 2: 목록과 내보낸 테스트 맞춰 보기

**Files:**
- Create: `src/ct_toolkit/io_match.py`
- Test: `tests/unit/test_io_match.py`

**Interfaces:**
- Consumes: `ListRow`(Task 1)
- Produces:
  - 사유 `R_MULTI = '함수 여럿'`, `R_NO_VAR = '변수 없음'`, `R_CONFLICT = '목록 충돌'`,
    `R_HAS_VALUES = '값 있음'`, `R_TYPE = '타입 제외'`, 화면 순서
    `SKIP_REASONS = (R_MULTI, R_NO_VAR, R_CONFLICT, R_HAS_VALUES, R_TYPE)`
  - `@dataclass(frozen=True) class CtVar: name: str; direction: str; has_values: bool = False; supported: bool = True`
    (`direction`은 `'in'|'out'|'inout'|''`, `''`은 지정 없음. 리턴 값의 이름은 `'return'`)
  - `@dataclass(frozen=True) class CtTest: key: str; function: str; file: str; variables: Mapping[str, CtVar]`
    (`key`는 `ct_export`가 사본을 쓸 때 쓰는 불투명한 식별자)
  - `@dataclass(frozen=True) class Skip: row: int; function: str; variable: str; reason: str`
  - `@dataclass class MatchResult: applied: Dict[str, Dict[str, str]]; skips: List[Skip]; not_exported: List[str]; unlisted: List[str]; tests_total: int`
    와 `count(reason: str) -> int`, 속성 `assigned -> int`(`applied` 안 변수 수 합)
  - `match(rows: Sequence[ListRow], tests: Sequence[CtTest], reset_cases: bool = False) -> MatchResult`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

도우미: `_row(row, function, variable, direction='in', file='')` → `ListRow`,
`_test(key, function, file='dmy_io.c', **vars)` → `CtTest`(값은 `CtVar`).

```python
class MatchTest(unittest.TestCase):
    def test_applies_listed_variables(self):
        t = _test('k1', 'dmy_calc', dmy_a=CtVar('dmy_a', ''), dmy_b=CtVar('dmy_b', 'in'))
        got = match([_row(2, 'dmy_calc', 'dmy_a', 'in'), _row(3, 'dmy_calc', 'dmy_b', 'out')], [t])
        self.assertEqual(got.applied, {'k1': {'dmy_a': 'in', 'dmy_b': 'out'}})
        self.assertEqual((got.assigned, got.skips, got.tests_total), (2, [], 1))

    def test_function_not_exported_is_not_a_skip(self):
        got = match([_row(2, 'dmy_ghost', 'dmy_a')], [])
        self.assertEqual((got.not_exported, got.skips), (['dmy_ghost'], []))

    def test_exported_test_without_rows_is_unlisted(self):
        got = match([], [_test('k1', 'dmy_other')])
        self.assertEqual((got.unlisted, got.applied), (['dmy_other'], {}))

    def test_same_name_functions_need_file(self):
        a = _test('ka', 'dmy_f', 'src\\a.c', dmy_x=CtVar('dmy_x', ''))
        b = _test('kb', 'dmy_f', 'src\\b.c', dmy_x=CtVar('dmy_x', ''))
        got = match([_row(2, 'dmy_f', 'dmy_x'), _row(3, 'dmy_f', 'dmy_x', 'out', file='B.C')], [a, b])
        self.assertEqual(got.skips, [Skip(2, 'dmy_f', 'dmy_x', R_MULTI)])
        self.assertEqual(got.applied, {'kb': {'dmy_x': 'out'}})

    def test_unknown_variable_skipped(self):
        got = match([_row(2, 'dmy_calc', 'dmy_typo')], [_test('k1', 'dmy_calc')])
        self.assertEqual(got.skips, [Skip(2, 'dmy_calc', 'dmy_typo', R_NO_VAR)])

    def test_unsupported_kind_skipped(self):
        t = _test('k1', 'dmy_calc', dmy_s=CtVar('dmy_s', '', supported=False))
        self.assertEqual(match([_row(2, 'dmy_calc', 'dmy_s')], [t]).count(R_TYPE), 1)

    def test_values_block_direction_change_without_reset(self):
        t = _test('k1', 'dmy_calc', dmy_v=CtVar('dmy_v', 'in', has_values=True))
        self.assertEqual(match([_row(2, 'dmy_calc', 'dmy_v', 'out')], [t]).count(R_HAS_VALUES), 1)
        self.assertEqual(match([_row(2, 'dmy_calc', 'dmy_v', 'in')], [t]).applied, {'k1': {'dmy_v': 'in'}})

    def test_reset_cases_ignores_values(self):
        t = _test('k1', 'dmy_calc', dmy_v=CtVar('dmy_v', 'in', has_values=True))
        got = match([_row(2, 'dmy_calc', 'dmy_v', 'out')], [t], reset_cases=True)
        self.assertEqual(got.applied, {'k1': {'dmy_v': 'out'}})

    def test_duplicate_rows_same_direction_count_once(self):
        t = _test('k1', 'dmy_calc', dmy_a=CtVar('dmy_a', ''))
        got = match([_row(2, 'dmy_calc', 'dmy_a'), _row(5, 'dmy_calc', 'dmy_a')], [t])
        self.assertEqual((got.assigned, got.skips), (1, []))

    def test_conflicting_rows_all_skipped(self):
        t = _test('k1', 'dmy_calc', dmy_a=CtVar('dmy_a', ''))
        got = match([_row(2, 'dmy_calc', 'dmy_a', 'in'), _row(3, 'dmy_calc', 'dmy_a', 'out')], [t])
        self.assertEqual([s.row for s in got.skips], [2, 3])
        self.assertEqual({s.reason for s in got.skips}, {R_CONFLICT})
        self.assertEqual(got.applied, {})

    def test_skips_sorted_by_row(self):
        got = match([_row(9, 'dmy_calc', 'dmy_z'), _row(4, 'dmy_calc', 'dmy_y')], [_test('k1', 'dmy_calc')])
        self.assertEqual([s.row for s in got.skips], [4, 9])
```

- [ ] **Step 2: 실패를 확인한다**

Run: `python -m unittest tests.unit.test_io_match -v`
Expected: `ModuleNotFoundError: No module named 'ct_toolkit.io_match'`.

- [ ] **Step 3: `io_match.py`를 구현한다**

판정 순서는 테스트만으로 정해지지 않으므로 이 순서를 지킨다.

1. 줄을 `(function, file, variable)`로 묶는다(처음 나온 순서 유지). 한 묶음 안에 `direction`이
   둘 이상이면 그 묶음의 모든 줄을 `R_CONFLICT`로 건너뛴다. 아니면 첫 줄만 쓴다.
2. 묶음 대표 줄마다:
   1. 같은 `function`의 테스트가 없으면 `not_exported`에 넣고 다음으로(건너뜀 아님).
   2. 둘 이상이면 `file`이 비지 않았을 때 `ntpath.basename(...).casefold()`가 같은 테스트만 남긴다.
      하나가 아니면 `R_MULTI`. 테스트가 하나뿐이면 `file`은 보지 않는다.
   3. 변수가 없으면 `R_NO_VAR`, `supported`가 거짓이면 `R_TYPE`.
   4. `reset_cases`가 거짓이고 `has_values`가 참이고 지정이 바뀌면 `R_HAS_VALUES`.
   5. 같은 테스트·변수에 다른 지정이 이미 들어갔으면 `R_CONFLICT`, 아니면 `applied`에 넣는다.
3. `unlisted`는 목록에 함수 이름이 한 번도 없는 테스트의 함수 이름. `not_exported`, `unlisted`는
   중복 없이 정렬, `skips`는 행 번호로 정렬.

- [ ] **Step 4: 통과를 확인한다**

Run: `python -m unittest tests.unit.test_io_match -v`
Expected: 모두 OK.

- [ ] **Step 5: 커밋**

```bash
git add src/ct_toolkit/io_match.py tests/unit/test_io_match.py
git commit  # feat: 목록과 내보낸 테스트를 맞춰 지정할 것과 건너뛸 것을 가린다
```

---

### Task 3: `ct.bat io-apply` 명령과 한 화면 요약

**Files:**
- Create: `src/ct_toolkit/ct_export.py`, `src/ct_toolkit/io_apply.py`
- Modify: `src/ct_toolkit/__main__.py`(`_parser`와 `main`의 분기), `README.md`(명령 표), `CHANGELOG.md`(Unreleased 맨 위)
- Test: `tests/unit/test_io_apply.py`

**Interfaces:**
- Consumes: `read_list`, `ListRead`, `ListFileError`(Task 1), `match`, `MatchResult`, `CtTest`,
  `SKIP_REASONS`(Task 2), `RunLog`(`log.py`), `paths.result_dir()`, `paths.version()`
- Produces:
  - `ct_export.py`: `class NotReady(Exception)`,
    `load_tests(export_dir: Path) -> List[CtTest]`,
    `write_copy(export_dir: Path, out_dir: Path, tests: Sequence[CtTest], applied: Mapping[str, Mapping[str, str]], reset_cases: bool) -> None`.
    둘 다 이번에는 `NotReady`만 던진다. 모듈 docstring에 "todo.md 2절 견본 결과로 채운다".
  - `io_apply.py`:
    - 문구 `E_EXPORT_NOT_READY = 'CT 내보낸 폴더 읽기는 아직 없음: todo.md 2절 견본 결과를 기다리는 중'`,
      `E_OUT_WRITE = '결과 폴더에 쓸 수 없음: result 폴더 권한과 남은 공간을 확인'`,
      `M_LIST_ONLY = '내보낸 폴더(--export)를 주지 않아 목록만 확인했습니다'`
    - `summary_lines(listed: ListRead, result: Optional[MatchResult], out_display: str, reset_cases: bool) -> List[str]`
    - `write_skipped(path: Path, listed: ListRead, result: Optional[MatchResult]) -> None`
    - `main(log: RunLog, list_path: Path, export_dir: Optional[Path] = None, reset_cases: bool = False, *, out_root: Optional[Path] = None, now: Optional[datetime] = None, reader=read_list, loader=ct_export.load_tests, writer=ct_export.write_copy) -> int`
  - CLI: `ct.bat io-apply --list <xlsx> [--export <폴더>] [--reset-cases]`

`--export` 없이 돌리면 목록만 확인한다(설계에 없던 것을 더함, 내 판단). 2절 결과를 기다리는 동안
사용자가 Codebeamer 목록을 툴킷 형식에 맞춰 보는 용도다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

공통: `RunLog('io-apply', log_dir=tmp/'logs', console=io.StringIO(), clock=lambda: FIXED)`,
`now=datetime(2026, 10, 29, 15, 30, 0)`, `out_root=tmp/'io'`. 가짜 `reader`는 정해 둔 `ListRead`를
돌려주고, 가짜 `loader`는 `CtTest` 목록을, 가짜 `writer`는 받은 인자를 기록한다.

```python
class SummaryTest(unittest.TestCase):
    def test_full_summary_lines(self):
        # listed: 함수 2, 줄 6, 목록 오류 1 / result: tests_total 3, applied 2개 테스트에 변수 3,
        # unlisted 1, not_exported 1, 변수 없음 1 / reset_cases=True
        self.assertEqual(summary_lines(listed, result, 'result\\io\\20261029_153000\\', True), [
            '목록      함수 2, 줄 6, 목록 오류 1',
            '테스트    내보낸 것 3, 바꾼 것 2, 케이스 정리 2, 목록에 없는 것 1',
            '지정      변수 3',
            '안 다룸   내보내지 않은 함수 1',
            '건너뜀    함수 여럿 0, 변수 없음 1, 목록 충돌 0, 값 있음 0, 타입 제외 0',
            '사본      result\\io\\20261029_153000\\',
            '건너뛴 줄 result\\io\\20261029_153000\\skipped.txt'])

    def test_list_only_summary_lines(self):
        self.assertEqual(summary_lines(listed, None, 'result\\io\\20261029_153000\\', False), [
            '목록      함수 2, 줄 6, 목록 오류 1',
            '건너뛴 줄 result\\io\\20261029_153000\\skipped.txt',
            M_LIST_ONLY])

    def test_no_reset_shows_zero_cleaned(self):
        # 같은 result, reset_cases=False → 둘째 줄 '케이스 정리 0'
        ...


class SkippedFileTest(unittest.TestCase):
    def test_skipped_file_lists_errors_skips_and_unlisted(self):
        # utf-8-sig, 탭 구분, 줄 순서: 머리글, 목록 오류(행 순), 건너뜀(행 순), 목록에 없는 테스트
        self.assertEqual(path.read_text(encoding='utf-8-sig').splitlines(), [
            '행\t함수\t변수\t이유',
            '3\tdmy_calc\t\t목록 오류(필수 칸 비었음)',
            '4\tdmy_calc\tdmy_typo\t변수 없음',
            '-\tdmy_other\t-\t목록에 없는 테스트'])


class MainTest(unittest.TestCase):
    def test_main_list_only(self):          # export_dir=None → 0, skipped.txt 생김, 콘솔에 M_LIST_ONLY, loader 안 부름
    def test_main_full_with_fake_export(self):  # → 0, writer가 (export_dir, out_dir, tests, applied, True)로 불림
    def test_main_default_loader_not_ready(self):  # loader 기본값 → 1, 콘솔에 E_EXPORT_NOT_READY
    def test_main_list_error_stops(self):   # reader가 ListFileError(E_LIST_OPEN) → 1, 콘솔에 E_LIST_OPEN
    def test_main_empty_list(self):         # 머리글만 → 0, '목록      함수 0, 줄 0, 목록 오류 0'
    def test_main_warns_skip_counts(self):  # 변수 없음 1 → 로그 파일에 'WARN' 줄과 '변수 없음 1'
    def test_main_hides_names_and_paths(self):
        # 함수·변수·키 이름을 모두 secret_로, out_root를 tmp/'secret_dir'로.
        # 콘솔 문자열과 로그 파일 내용에 'secret'이 없다.
        # skipped.txt에는 'secret_fn'이 있다(이름은 거기에만 간다는 대조군).


class ParserTest(unittest.TestCase):
    def test_io_apply_arguments(self):
        args = _parser().parse_args(['io-apply', '--list', 'a.xlsx', '--export', 'd', '--reset-cases'])
        self.assertEqual((args.command, args.list_path, args.export_dir, args.reset_cases),
                         ('io-apply', Path('a.xlsx'), Path('d'), True))
```

- [ ] **Step 2: 실패를 확인한다**

Run: `python -m unittest tests.unit.test_io_apply -v`
Expected: `ModuleNotFoundError: No module named 'ct_toolkit.io_apply'`.

- [ ] **Step 3: `ct_export.py`, `io_apply.py`를 만들고 `__main__.py`에 잇는다**

`main` 순서:

1. `log.step('CT Test Automation Toolkit {} 입력·출력 지정'.format(paths.version()))`.
2. `with log.checkpoint('목록 읽기')`로 `reader(list_path)`. `ListFileError`는 checkpoint 밖에서 잡아
   `log.error(str(exc))`, 종료 코드 1. 목록 오류가 있으면 `log.warn('목록 오류 {}줄'.format(n))`.
3. `out_dir = (out_root or paths.result_dir() / 'io') / now.strftime('%Y%m%d_%H%M%S')`를 만든다.
   `OSError`면 `log.error(E_OUT_WRITE)`, 1. 화면용은 `'result\\io\\{}\\'.format(stamp)`.
4. `export_dir`가 없으면 `write_skipped(out_dir / 'skipped.txt', listed, None)`, 요약을 찍고 0.
5. 있으면 `log.checkpoint('내보낸 폴더 읽기')`로 `loader`, `NotReady`면 `log.error(E_EXPORT_NOT_READY)`, 1.
   `match`, 건너뜀 이유별·목록에 없는 테스트 개수가 0보다 크면 `log.warn('건너뜀 {} {}'.format(reason, n))`,
   `log.warn('목록에 없는 테스트 {}'.format(n))`. `log.checkpoint('사본 쓰기')`로 `writer`
   (`NotReady`도 같은 문구로 1), `write_skipped`, 요약.
6. 요약은 `summary_lines`의 줄마다 `log.step`, 마지막에 `log.step('로그: {}'.format(log.path.name))`
   (`log.path`가 없으면 `'(없음)'`, `selfcheck.render`와 같다).

`__main__.py`: `io-apply` 서브파서에 `--list`(`dest='list_path'`, `type=Path`, `required=True`),
`--export`(`dest='export_dir'`, `type=Path`), `--reset-cases`(`store_true`). 분기에서
`io_apply.main(log, args.list_path, args.export_dir, args.reset_cases)`를 돌려준다.

README 명령 표에 한 줄: `ct.bat io-apply --list <목록.xlsx>` — 목록이 툴킷 형식에 맞는지 확인하고
개수를 한 화면에 찍음. CT 내보낸 폴더(`--export`)는 todo.md 2절 결과 후. CHANGELOG에는
`ct.bat io-apply --list`로 목록을 확인할 수 있다는 것과, 이름은 `skipped.txt`에만 쓴다는 것을 적는다.

- [ ] **Step 4: 전체 테스트와 3.8 문법 검사**

Run: `python -m unittest discover -s tests/unit`
Expected: `OK`(openpyxl 없는 Python이면 `OK (skipped=3)`).

Run: `python -c "import ast,glob; [ast.parse(open(f,encoding='utf-8').read(),f,feature_version=(3,8)) for f in glob.glob('src/ct_toolkit/*.py')+glob.glob('tests/unit/*.py')]; print('py38 ok')"`
Expected: `py38 ok`

- [ ] **Step 5: 커밋**

```bash
git add src/ct_toolkit/ct_export.py src/ct_toolkit/io_apply.py src/ct_toolkit/__main__.py \
        tests/unit/test_io_apply.py README.md CHANGELOG.md
git commit  # feat: ct.bat io-apply로 입력·출력 목록을 확인하고 한 화면에 요약한다
```

---

### Task 4: 예제 목록과 서버 PC 확인 요청

**Files:**
- Create: `examples/ct_sample/io_list.example.xlsx`
- Modify: `todo.md`(다음 번호 절), `docs/ai/handoff.md`(실물 미검증 목록)

**Interfaces:**
- Consumes: `ct.bat io-apply --list`(Task 3), `examples/ct_sample/dmy_io.example.c`의 이름

- [ ] **Step 1: 예제 목록을 만든다**

openpyxl로 한 번 만들고 생성 스크립트는 커밋하지 않는다. 첫 시트 머리글
`함수, 변수, 구분, 파일, 타입, 범위`, 줄은 todo.md 2절 표와 같은 9줄(`dmy_calc`의 `dmy_gain` 입력 …
`return` 출력, `dmy_spare` 없음). `파일`은 비우고 `범위`는 몇 줄에만 지어낸 값(`0~100`).

- [ ] **Step 2: 로컬에서 예제로 돌려 본다**

Run: `ct.bat io-apply --list examples\ct_sample\io_list.example.xlsx` (cmd)
Expected: `목록      함수 1, 줄 9, 목록 오류 0`, `M_LIST_ONLY` 줄, 종료 코드 0.
`result\io\<시각>\skipped.txt`는 머리글 한 줄뿐.

- [ ] **Step 3: todo.md에 다음 번호 절을 쓴다**

왜: 서버 PC의 openpyxl로 목록을 읽는지, 사용자의 Codebeamer 목록이 형식에 맞는지 본다.
명령 블록(실제 목록 경로가 캡처에 남지 않게 `set` 다음에 `cls`):

```bat
prompt $G
set "CTLIST=<Codebeamer에서 내보낸 목록.xlsx 전체 경로>"
cls
git pull
ct.bat io-apply --list examples\ct_sample\io_list.example.xlsx
echo exit=%ERRORLEVEL%
ct.bat io-apply --list "%CTLIST%"
echo exit=%ERRORLEVEL%
```

확인할 것: 예제는 `함수 1, 줄 9, 목록 오류 0`, `exit=0`. 실제 목록은 `목록 오류` 개수와 `exit`.
돌려줄 것: 화면 캡처 한 장. 목록 오류가 있으면 이유 종류(`skipped.txt`의 이유 칸 값)만 말로.

- [ ] **Step 4: handoff 실물 미검증 목록에 한 줄**

`ct.bat io-apply --list`: 단위 테스트만 통과, 서버 PC의 openpyxl과 실제 Codebeamer 목록으로는 안 돌림.

- [ ] **Step 5: 커밋하고 develop·main에 push**

```bash
git add examples/ct_sample/io_list.example.xlsx todo.md docs/ai/handoff.md
git commit  # docs: io-apply 목록 확인을 서버 PC에 요청한다
git push origin HEAD:develop && git push origin HEAD:main
```

---

## 2차(이 계획 밖)

todo.md 2절 결과가 오면 별도 계획으로 `ct_export.load_tests`, `write_copy`를 채우고 `NotReady`를
없앤다. 고친 사본을 CT로 다시 가져오는 확인(설계의 "다음 요청")도 그때 todo.md로 요청한다.
README의 사용 흐름(내보낸 뒤 가져오기 전까지 CT에서 그 테스트를 고치지 않는다는 안내 포함)도
`--export`가 실제로 돌 때 쓴다.
