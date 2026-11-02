# 목록대로 입력·출력 지정하기 2차 구현 계획 (`--export`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ct.bat io-apply --list <목록> --export <내보낸 폴더>`가 CT 테스트 데이터 CSV의 머리글을 목록대로
고친 사본을 `result\io\<시각>\`에 쓴다. 사용자는 원래 테스트를 지우고 [테스트 데이터로 테스트 생성하기]로
그 CSV를 넣는다.

**Architecture:** 1차의 네 모듈을 그대로 둔다. `ct_export`는 CSV 읽기(`load_tests`)와 머리글 고쳐 쓰기
(`rewrite_csv`, `write_copy`)를 채운다. `io_match`는 포인터 파라미터 이름(`p` → `p_mem`)을 찾고, 실제로
바뀌는 지정(`changes`)과 목록에 없어 해제할 변수(`released`)를 따로 낸다. `io_apply`는 새 결과로 화면과
`skipped.txt`를 쓴다. `.utest`는 함수·파일 이름을 얻으려고 읽기만 한다.

**Tech Stack:** Python 3.8+ 표준 라이브러리, unittest.

**Spec:** [io-designation.md](io-designation.md) ("사용 흐름", "맞춰 보기", "사본", "화면과 기록", 견본 결과
2·4·8·9절)

## Global Constraints

- Python 3.8 이상 문법만 쓴다. 파일마다 `from __future__ import annotations`.
- 표준 라이브러리만 쓴다(openpyxl은 1차의 목록 읽기에만 있다).
- 단위 테스트는 `tests/unit`의 unittest. 실행: `python -m unittest discover -s tests/unit`.
- 화면과 로그 파일에는 개수, 정해 둔 문구, 출력 폴더·파일 이름만 넣는다. 함수·변수·파일 이름과 경로는
  `skipped.txt`에만 쓴다. 예외 메시지 원문은 찍지 않는다. `ExportError`의 문구는 정해 둔 상수다.
- 예제와 테스트의 이름은 지어낸 것(`dmy_`, `secret_`)만 쓴다.
- CSV 형식(견본): 1줄 `CT(Controller Tester) Test Data`, 2줄 `test name:<테스트 이름>,""`, 3줄 머리글
  (첫 칸 빈칸, 구역 표시 `<input>`·`<expect>`·`<output>`·`<toutput>`과 기호들), 4줄부터 케이스
  (`1,""` 뒤 값 칸). 견본 인코딩은 cp949, 줄 끝 CRLF, BOM 없음. 구역 표시도 칸 하나를 차지한다.
- 커밋은 Conventional Commits, 한국어 요약, 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  사용자에게 보이는 변경은 같은 커밋에 `CHANGELOG.md`를 고친다.

## Review Focus

- 케이스 이름에 쉼표가 든 칸(`"#ID#a,b#ID#"`): 칸이 밀리지 않고 그대로 남아야 한다(Task 3 테스트).
- 프로젝트 둘을 한 폴더에 내보내 같은 CSV 이름이 두 번 나옴: 상대 경로로 따로 읽고 따로 써야 한다
  (Task 1·3 테스트).
- 마지막 줄 끝에 줄바꿈이 없거나 UTF-8(BOM 포함) CSV: 바꿀 것이 없으면 바이트까지 같게 다시 써야
  한다(Task 3 테스트).
- 사용자가 만든 CSV 등 CT 꼴이 아닌 CSV가 섞인 폴더: 멈추지 않고 "읽지 못한 CSV"로 센다(Task 1 테스트).
- 테스트 이름을 바꿨고 `.utest`도 없음: 함수 이름을 지어내지 않고 테스트 이름 그대로 두어 "목록에 없는
  테스트"로 잡힌다(Task 1 테스트).

---

### Task 1: `ct_export` 읽기

**Files:**
- Modify: `src/ct_toolkit/ct_export.py` (`NotReady` 지우고 아래로 바꾼다)
- Create: `tests/unit/test_ct_export.py`

**Interfaces:**
- Consumes: `io_match.CtTest(key, function, file, variables)`, `io_match.CtVar(name, direction, has_values, supported)`.
- Produces:
  - `E_EXPORT_OPEN = '내보낸 폴더를 읽을 수 없음: --export에 [테스트 내보내기]로 고른 폴더를 주었는지 확인'`
  - `E_EXPORT_EMPTY = '내보낸 폴더에 테스트 데이터 CSV가 없음: [테스트 내보내기]에서 유닛 테스트의 테스트 데이터를 체크했는지 확인'`
  - `class ExportError(Exception)` — `str(exc)`는 위 상수 중 하나.
  - `@dataclass class ExportRead: tests: List[CtTest]; unreadable: List[str]` (읽지 못한 CSV의 상대 경로, posix)
  - `split_fields(line: str) -> List[str]` — 따옴표 안 쉼표는 나누지 않고 칸 원문(따옴표 포함)을 그대로 둔다.
  - `symbol_variable(symbol: str) -> Tuple[str, bool]` — (변수 이름, 쓸 줄 앎).
  - `decode_csv(data: bytes) -> Tuple[str, str]` — (글, 인코딩 이름). BOM이면 `utf-8-sig`, 아니면 `utf-8`, 안 되면 `cp949`.
  - `load_tests(export_dir: Path) -> ExportRead`
  - `CtTest.key`는 `export_dir` 기준 CSV 상대 경로(posix), 예 `ctsample/UnitTests/dmy_calc_test0.csv`.

테스트 픽스처: 견본 머리글을 그대로 쓴다.

```python
HEADER = (',<input>,dmy_count,dmy_gain,dmy_hist[0],dmy_limit.dmy_hi,dmy_limit.dmy_lo,dmy_mode,'
          'dmy_ptr_mem[0],dmy_spare,dmy_x,<expect>,dmy_count,dmy_hist[0],dmy_level,returnVar,'
          '<output>,dmy_count,dmy_hist[0],dmy_level,returnVar,<toutput>,dmy_count,dmy_hist[0],'
          'dmy_level,returnVar')
```

케이스 줄은 `'1,""' + ',' * (len(split_fields(HEADER)) - 2)`. 파일은 `CT(Controller Tester) Test Data`,
`test name:dmy_calc_test0,""`, 머리글, 케이스를 CRLF로 이어 cp949로 쓴다. `.utest`는
`b'\xac\xed\x00\x05' + b'\x00\x27dmy_calc(signed int, const signed int *)' + b'\x00\x18C:\\ctsample\\src\\dmy_io.c'`.

- [ ] **Step 1: 실패하는 테스트를 쓴다** (`tests/unit/test_ct_export.py`)
  - `test_symbol_variable`: `dmy_limit.dmy_hi`→`('dmy_limit', True)`, `dmy_hist[0]`→`('dmy_hist', True)`,
    `dmy_ptr_mem[0]`→`('dmy_ptr_mem', True)`, `returnVar`→`('return', True)`, `a[1][2].b`→`('a', True)`,
    `p->x`→`('p', False)`, `(*p).x`→`('(*p).x', False)`.
  - `test_split_fields_keeps_quoted_commas`: `split_fields('1,"#ID#a,b#ID#",,7')` == `['1', '"#ID#a,b#ID#"', '', '7']`.
  - `test_load_groups_symbols_by_variable`: 변수 이름 집합이 `{'dmy_count','dmy_gain','dmy_hist','dmy_limit',
    'dmy_mode','dmy_ptr_mem','dmy_spare','dmy_x','dmy_level','return'}`, 지정은 `dmy_count`·`dmy_hist` `inout`,
    `dmy_gain` `in`, `dmy_level`·`return` `out`.
  - `test_function_and_file`: 기본 이름이면 `function == 'dmy_calc'`, `file == 'dmy_io.c'`, `key` 위와 같음.
  - `test_function_from_utest_when_test_renamed`: 2줄이 `test name:renamed,""`이면 `.utest`에서 `dmy_calc`.
  - `test_renamed_without_utest_keeps_test_name`: `.utest`가 없으면 `function == 'renamed'`, `file == ''`.
  - `test_has_values_only_from_input_and_expect`: 케이스 줄 `dmy_gain` 칸에 `5`, `<output>`의 `returnVar` 칸에
    `9` → `dmy_gain.has_values` 참, `return.has_values` 거짓.
  - `test_unsupported_symbol_marks_variable`: 머리글 `<input>`에 `p->x`를 더하면 `variables['p'].supported` 거짓.
  - `test_two_projects_same_file_name`: `a/UnitTests/dmy_calc_test0.csv`, `b/UnitTests/dmy_calc_test0.csv` →
    테스트 둘, key가 다르다.
  - `test_non_ct_csv_is_unreadable`: `other/x.csv`(`a,b`)가 섞이면 `unreadable == ['other/x.csv']`, 테스트는 하나.
  - `test_missing_dir_raises` → `ExportError`, `str(exc) == E_EXPORT_OPEN`.
  - `test_no_readable_csv_raises` → 빈 폴더와 CT 꼴 아닌 CSV만 있는 폴더 둘 다 `E_EXPORT_EMPTY`.

- [ ] **Step 2: 실패를 확인한다**

Run: `python -m unittest tests.unit.test_ct_export -v` (저장소 루트, `PYTHONPATH=src`가 아니면 테스트 파일이
1차 테스트처럼 `sys.path`에 `src`를 넣는다)
Expected: ImportError(`ExportError` 등 없음)

- [ ] **Step 3: 구현한다** (`src/ct_toolkit/ct_export.py`)
  - 기호 꼴: `^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*|\[\d+\])*$`이면 쓸 줄 안다. 변수 이름은 앞의 식별자,
    `returnVar`는 `return`. 꼴이 아니면 앞 식별자가 있으면 그것, 없으면 기호 전체를 이름으로 하고 `False`.
  - CT 꼴 판정: 1줄이 `CT(Controller Tester) Test Data`, 2줄이 `test name:`으로 시작, 3줄 첫 칸이 빈칸이고
    `<input>`이나 `<expect>`가 있다. 아니거나 `decode_csv`가 실패하면 unreadable.
  - 함수 이름: 테스트 이름이 `^(.+)_test\d+$`면 그 앞. 아니면 같은 폴더 같은 stem의 `.utest` 바이트에서
    `rb'([A-Za-z_]\w*)\([\x20-\x7e]*?\)'` 첫 일치. 둘 다 없으면 테스트 이름.
  - 파일 이름: `.utest` 바이트에서 `rb'\\([\x21-\x5b\x5d-\x7e]+?\.(?:c|cc|cpp|cxx))(?![\w])'` 마지막 일치(소스
    경로의 마지막 부분). 없으면 `''`.
  - 지정: 변수의 기호가 `<input>`에 있으면 in, `<expect>`에 있으면 out, 둘 다면 inout.
  - 값: `<input>`·`<expect>` 구역의 그 변수 칸 중 하나라도 케이스 줄에서 비어 있지 않으면 `has_values`.
  - 변수의 기호 중 하나라도 쓸 줄 모르면 `supported=False`.
  - 폴더가 없으면 `E_EXPORT_OPEN`, 읽은 테스트가 0이면 `E_EXPORT_EMPTY`.

- [ ] **Step 4: 통과를 확인한다**

Run: `python -m unittest discover -s tests/unit`
Expected: OK. (`io_apply`가 `ct_export.NotReady`를 쓰므로 이 단계에서 `io_apply`의 `except` 줄을
`except ct_export.ExportError as exc: log.error(str(exc)); return 1`로 바꾸고, `test_main_default_loader_not_ready`는
`test_main_export_error_stops`로 바꿔 없는 폴더를 주고 `E_EXPORT_OPEN`이 찍히는지 본다. 나머지는 Task 4.)

- [ ] **Step 5: 커밋한다** — `feat: CT 테스트 데이터 CSV에서 함수와 변수 지정을 읽는다`

### Task 2: `io_match` 포인터 이름, 바뀜과 해제

**Files:**
- Modify: `src/ct_toolkit/io_match.py`
- Modify: `tests/unit/test_io_match.py`

**Interfaces:**
- Consumes: Task 1의 `CtTest`, `CtVar`(그대로).
- Produces (`MatchResult`에 기본값 있는 필드를 끝에 더한다):
  - `applied: Dict[str, Dict[str, str]]` — 키를 목록 이름이 아니라 찾은 `CtVar.name`으로 한다.
  - `changes: Dict[str, Dict[str, str]]` — `applied` 중 지금 지정과 다른 것만.
  - `released: Dict[str, List[str]]` — 테스트 key → 해제할 변수 이름(정렬).
  - `@property changed_vars -> int`, `@property released_vars -> int`
  - `@property edits -> Dict[str, Dict[str, str]]` — `changes`에 `released`를 `''`로 합친 것. `ct_export.write_copy`가 받는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**
  - `test_pointer_param_finds_mem_variable`: 목록 `dmy_ptr` in, 테스트 변수 `dmy_ptr_mem` in →
    `applied == {'k': {'dmy_ptr_mem': 'in'}}`, `changes == {}`.
  - `test_exact_name_wins_over_mem`: 테스트에 `buf`와 `buf_mem`이 다 있으면 목록 `buf`는 `buf`를 찾는다.
  - `test_changes_only_differing`: `dmy_a` in→in, `dmy_b` inout→out → `changes == {'k': {'dmy_b': 'out'}}`, `changed_vars == 1`.
  - `test_unlisted_variable_released`: 목록에 없는 `dmy_spare`(in) → `released == {'k': ['dmy_spare']}`,
    `edits['k']['dmy_spare'] == ''`.
  - `test_unsupported_or_found_but_skipped_not_released`: 쓸 줄 모르는 변수, "값 있음"으로 건너뛴 변수는 해제하지 않는다.
  - `test_test_without_rows_not_released`: 목록에 함수 줄이 없는 테스트는 `released`에 없다.
  - `test_released_test_without_changes_still_in_edits`: 바뀌는 지정이 없어도 해제가 있으면 `edits`에 있다.

- [ ] **Step 2: 실패를 확인한다** — Run: `python -m unittest tests.unit.test_io_match -v`, Expected: FAIL

- [ ] **Step 3: 구현한다**
  - 변수 찾기: `variables.get(name)`, 없으면 `variables.get(name + '_mem')`.
  - 해제 대상: 목록 줄이 고른 테스트(건너뛰었어도 테스트를 고른 줄 포함)마다, 그 테스트의 변수 중 어느 목록
    줄로도 찾지 않았고 `supported`이며 지정이 있는 것.

- [ ] **Step 4: 통과를 확인한다** — Run: `python -m unittest discover -s tests/unit`, Expected: OK

- [ ] **Step 5: 커밋한다** — `feat: 맞춰 보기가 포인터 파라미터를 찾고 바뀐 지정과 해제할 변수를 낸다`

### Task 3: `ct_export` 머리글 고쳐 쓰기

**Files:**
- Modify: `src/ct_toolkit/ct_export.py`
- Modify: `tests/unit/test_ct_export.py`

**Interfaces:**
- Consumes: Task 1의 `split_fields`, `symbol_variable`, `decode_csv`; Task 2의 `MatchResult.edits` 꼴.
- Produces:
  - `rewrite_csv(text: str, directions: Mapping[str, str], reset_cases: bool) -> str` — `directions`는 변수 이름 →
    `'in'|'out'|'inout'|''`(`''`는 해제). 없는 변수는 그대로.
  - `write_copy(export_dir: Path, out_dir: Path, edits: Mapping[str, Mapping[str, str]], reset_cases: bool) -> int` —
    key마다 원본을 읽어 고쳐 `out_dir / key`에 원래 인코딩으로 쓰고, 쓴 CSV 수를 돌려준다.

규칙(`docs/design/io-designation.md` "사본"):

- 1·2줄과 줄 끝(원본 1줄의 끝을 따름, 마지막 줄 끝의 유무도 원본대로), 인코딩은 그대로.
- 바뀌는 변수의 기호는 새 지정대로 넣는다: in이면 `<input>`, out이면 `<expect>`·`<output>`·`<toutput>`,
  inout이면 넷 다. 해제는 넷 다에서 뺀다. 바뀌지 않는 변수의 기호는 구역마다 원래 자리 그대로.
- 구역 안 기호 순서: 남는 기호는 원래 순서와 자리 그대로. CT가 오름차순(파이썬 문자열 순서)으로 쓴 구역이면
  새로 드는 기호를 그 순서의 자리에 넣고, 아니면 마지막 기호 뒤에 머리글에 처음 나온 순서로 붙인다. 바뀌는 것이
  없는 구역은 그대로다. 모르는 구역(`<stub>` 등)은 기호까지 그대로.
- 필요한 구역 표시가 없으면 `<input>`, `<expect>`, `<output>`, `<toutput>` 순서에 맞는 자리에 넣는다.
- 케이스 줄: 새 칸마다 원래 같은 (구역, 기호) 칸의 값, 구역 표시 칸은 원래 같은 표시 칸의 값, 없던 칸은 빈칸.
  `reset_cases`면 케이스 줄을 `1,""`와 빈칸만으로 된 한 줄로 바꾼다(`""`는 첫 구역 표시 칸).

- [ ] **Step 1: 실패하는 테스트를 쓴다**
  - `test_no_change_is_identical`: 견본 CSV(케이스 두 줄, 이름 `"#ID#a,b#ID#"`와 `"#ID#견본#ID#"`)에
    `rewrite_csv(text, {}, False) == text`. 마지막 줄 끝이 없는 글과 BOM 있는 UTF-8 파일도 `write_copy`로 써서
    바이트가 같다.
  - `test_inout_to_out_removes_from_input`: `{'dmy_count': 'out', 'dmy_hist': 'out', 'dmy_spare': ''}` →
    머리글이 `,<input>,dmy_gain,dmy_limit.dmy_hi,dmy_limit.dmy_lo,dmy_mode,dmy_ptr_mem[0],dmy_x,<expect>,dmy_count,
    dmy_hist[0],dmy_level,returnVar,<output>,...,<toutput>,...`(뒤 두 구역은 `<expect>`와 같음). 이것이 견본 2절에서
    사용자가 손으로 만든 지정이다.
  - `test_in_to_out_keeps_sorted_order`: `{'dmy_gain': 'out'}` → `<expect>`가 `dmy_count,dmy_gain,dmy_hist[0],
    dmy_level,returnVar`(정렬된 구역이라 정렬 자리에 든다).
  - `test_unsorted_section_gets_joiners_at_its_end`: 정렬되지 않은 구역은 새 기호가 마지막 기호 뒤에 머리글에
    처음 나온 순서로 붙는다.
  - `test_values_follow_their_columns`: `dmy_x` 칸 `7`, 케이스 이름 칸이 바꾼 뒤에도 같은 기호·표시 아래 있고, 모든
    줄의 칸 수가 머리글과 같다.
  - `test_reset_cases_leaves_one_empty_case`: 케이스 두 줄 → `1,""`와 빈칸 한 줄.
  - `test_unknown_section_kept`: 머리글 끝 `,<stub>,dmy_stub_ret`과 그 값이 그대로.
  - `test_missing_expect_section_added`: 머리글 `,<input>,a,b`, `{'b': 'out'}` → `,<input>,a,<expect>,b,<output>,b,<toutput>,b`.
  - `test_write_copy_only_edits_keeps_relative_path_and_cp949`: 두 프로젝트 중 하나만 `edits`에 있으면 그 하나만
    `out/a/UnitTests/dmy_calc_test0.csv`에 쓰이고 반환값 1, cp949와 CRLF, `견본`이 그대로.

- [ ] **Step 2: 실패를 확인한다** — Run: `python -m unittest tests.unit.test_ct_export -v`, Expected: FAIL

- [ ] **Step 3: 구현한다** — 칸 위치마다 (구역, 기호) 또는 구역 표시를 적어 두고 새 머리글을 만든 뒤 같은 표로
  케이스 줄을 옮긴다.

- [ ] **Step 4: 통과를 확인한다** — Run: `python -m unittest discover -s tests/unit`, Expected: OK

- [ ] **Step 5: 커밋한다** — `feat: 목록대로 CT 테스트 데이터 CSV의 머리글을 고친 사본을 쓴다`

### Task 4: `io_apply` 연결, 문서, 서버 PC 요청

**Files:**
- Modify: `src/ct_toolkit/io_apply.py`, `tests/unit/test_io_apply.py`
- Modify: `tools/todo_run.py`(`SECTIONS`에 `11`, `12`), `todo.md`(11·12절)
- Modify: `README.md`(명령 표의 `io-apply` 줄과 사용 흐름), `CHANGELOG.md`, `docs/ai/handoff.md`(실물 미검증), `docs/archive/handoff-history.md`

**Interfaces:**
- Consumes: Task 1 `load_tests -> ExportRead`, `ExportError`; Task 2 `MatchResult.edits/changed_vars/released_vars/released`; Task 3 `write_copy(...) -> int`.
- Produces:
  - `main(log, list_path, export_dir=None, reset_cases=False, *, out_root=None, now=None, reader=read_list, loader=ct_export.load_tests, writer=ct_export.write_copy) -> int`(시그니처 그대로)
  - `summary_lines(listed, result, out_display, reset_cases, unreadable=0, copied=0) -> List[str]`
  - `write_skipped(path, listed, result, export=None)` — `export: Optional[ExportRead]`
  - 상수: `R_RELEASED = '목록에 없어 해제'`, `R_UNREADABLE = '읽지 못한 CSV'`,
    `M_NEXT = '다음: CT에서 바꾼 테스트의 원래 것을 지우고 [테스트 데이터로 테스트 생성하기]로 사본 CSV를 넣기'`,
    `M_NOTHING = '바꿀 지정이 없어 사본 CSV를 쓰지 않았습니다'`. `E_EXPORT_NOT_READY`는 지운다.

화면(설계 "화면과 기록"):

```text
테스트    내보낸 것 {tests_total}, 바꾼 것 {len(edits)}, 케이스 정리 {len(edits) if reset else 0}, 목록에 없는 것 {unlisted}
지정      변수 {assigned}(그중 바뀜 {changed_vars}), 목록에 없어 해제 {released_vars}
안 다룸   내보내지 않은 함수 {not_exported}, 읽지 못한 CSV {unreadable}
건너뜀    (그대로)
사본      result\io\{stamp}\ (CSV {copied})
건너뛴 줄 result\io\{stamp}\skipped.txt
{M_NEXT if copied else M_NOTHING}
```

- [ ] **Step 1: 실패하는 테스트를 쓴다** (`tests/unit/test_io_apply.py`)
  - `test_full_summary_lines`를 위 꼴로 고친다(`바꾼 것`, `그중 바뀜`, `목록에 없어 해제`, `읽지 못한 CSV`, `M_NEXT`).
  - `test_nothing_to_change_says_so`: `edits`가 비면 `M_NOTHING`, writer를 부르지 않는다.
  - `test_export_error_stops_before_result_folder`: loader가 `ExportError(E_EXPORT_EMPTY)` → 종료 1, 화면에 그 문구,
    `out_root` 아래 폴더가 생기지 않는다.
  - `test_same_second_runs_get_separate_folders`: 같은 `now`로 두 번 → 둘째 화면에 `result\io\<stamp>_2\`.
  - `test_skipped_file_lists_released_and_unreadable`: `-\t<함수>\t<변수>\t목록에 없어 해제`, `-\t<상대 경로>\t-\t읽지 못한 CSV` 줄.
  - `test_main_end_to_end_on_sample_export`: 가짜 reader(예제 목록과 같은 9줄 `ListRow`)와 실제 loader·writer로 Task 1 픽스처
    폴더를 돌리면 사본 CSV의 `<input>`이 `dmy_gain,dmy_limit.dmy_hi,dmy_limit.dmy_lo,dmy_mode,dmy_ptr_mem[0],dmy_x`이고,
    화면에 `바꾼 것 1`, `변수 9(그중 바뀜 2)`, `목록에 없어 해제 1`.
  - `test_main_hides_names_and_paths`에 `secret_` 변수(해제됨)와 `secret_dir/x.csv`(읽지 못함)를 더해 화면·로그에 `secret`이 없는지 본다.

- [ ] **Step 2: 실패를 확인한다** — Run: `python -m unittest tests.unit.test_io_apply -v`, Expected: FAIL

- [ ] **Step 3: 구현한다**
  - 순서: 목록 읽기 → (`--export`면) 내보낸 폴더 읽기·맞춰 보기 → 결과 폴더 만들기 → `edits`가 있으면 사본 쓰기 → `skipped.txt` → 요약.
    결과 폴더가 이미 있으면 `_2`, `_3`…을 붙인다.
  - WARN: 건너뜀 이유별 개수(그대로), 목록에 없는 테스트 수(그대로), 읽지 못한 CSV 수. 해제 수는 INFO.
  - 사본 쓰기 `OSError`는 `E_OUT_WRITE`.

- [ ] **Step 4: 통과를 확인한다** — Run: `python -m unittest discover -s tests/unit`, Expected: OK

- [ ] **Step 5: 문서와 서버 PC 요청을 쓴다**
  - README: 명령 표의 `io-apply` 줄을 `--export`까지로 고치고, 설계 "사용 흐름" 2~7단계를 사용자 말로 옮긴다.
  - CHANGELOG `Unreleased`: `--export`로 머리글을 고친 CSV를 쓰고, CT [테스트 데이터로 테스트 생성하기]로 넣는다.
  - handoff 실물 미검증: `--export`는 서버 PC에서 안 돌렸다(todo.md 11·12절).
  - `tools/todo_run.py` `SECTIONS`:
    `'11': ('io-apply로 견본 CSV 고치기', ['-m', 'ct_toolkit', 'io-apply', '--list', 'examples/ct_sample/io_list.example.xlsx', '--export', 'C:/ctsample/out/1', '--reset-cases'])`,
    `'12': ('다시 내보낸 견본 확인', ['-m', 'ct_toolkit', 'io-apply', '--list', 'examples/ct_sample/io_list.example.xlsx', '--export', 'C:/ctsample/out/9'])`.
  - todo.md 11절: `todo.bat` → 11(기대: `바꾼 것 1`, `변수 9(그중 바뀜 2)`, `목록에 없어 해제 1`) → CT에서 `dmy_calc_test*`
    테스트를 모두 지우고 [테스트 데이터로 테스트 생성하기]로 `result\io\<최신>\ctsample\UnitTests\dmy_calc_test0.csv` →
    테스트 정보 탭에서 입력 6개(손으로 한 2절 지정과 같음)인지 → [테스트 내보내기]로 `C:\ctsample\out\9` → 12절.
    12절: `todo.bat` → 12(기대: `바꾼 것 0`, `그중 바뀜 0`, `목록에 없어 해제 0`, `M_NOTHING`). 돌려줄 것: 두 화면, 새 테스트의 스텁·설정이
    원래와 달라 보인 것이 있으면 한 줄.

- [ ] **Step 6: 커밋한다** — `feat: io-apply --export가 머리글을 고친 CSV를 쓰고 견본 확인을 todo.md 11·12절로 요청한다`
  - 커밋 뒤 develop과 main에 push한다(서버 PC가 새 코드를 받아야 하는 요청).
