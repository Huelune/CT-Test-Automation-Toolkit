# 원소·멤버 단위 입력·출력 지정 구현 계획 (견본 확인 + 1차)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 목록 `변수` 칸의 `a.b`, `v[0]`, `v[1].s` 같은 줄이 그 기호만 지정하고, 어느 줄에도 덮이지 않는 기호는
해제한다. CT 머리글에 없는 원소·멤버는 `CT에 없음`으로 건너뛴다. 2차(칸 더하기)를 정할 서버 PC 견본 확인 절도
만든다.

**Architecture:** `ct_export`가 테스트를 변수가 아니라 CT 기호 단위(`CtTest.symbols`)로 읽는다. `io_match`는 목록
줄을 기호 경로로 바꿔(`to_symbol`) 기호마다 가장 자세한 줄을 고르고, 기호 단위로 바뀜·해제를 낸다
(`MatchResult.symbol_changes`, `released`). `rewrite_csv`는 기호 이름 키를 먼저 본다. 화면 문구·단위는 그대로
두고 `CT에 없음`만 더한다. 견본 확인은 `tools/member_probe.py`가 머리글을 찍고 변형 CSV를 만든다.

**Tech Stack:** Python 3.8+ 표준 라이브러리, unittest. 예시 XLSX 고치기에만 openpyxl.

**Spec:** [io-designation-members.md](io-designation-members.md) (승인 2026-11-04). 상위:
[io-designation.md](io-designation.md).

## Global Constraints

- Python 3.8 이상 문법만 쓴다. 파일마다 `from __future__ import annotations`. 표준 라이브러리만 쓴다.
- 단위 테스트는 `tests/unit`의 unittest. 실행: `python -m unittest discover -s tests/unit`. 지금 173개가 통과한다.
- 화면과 로그에는 개수, 정해 둔 문구, 출력 폴더·파일 이름만 넣는다. 함수·변수·기호 이름과 경로는 `skipped.txt`
  에만 쓴다. 예외: `tools/member_probe.py`는 견본 확인용이라 `dmy_`로 시작하는 이름과 `returnVar`만 찍고 나머지는
  `*`로 가린다.
- 예제와 테스트의 이름은 지어낸 것(`dmy_`, `secret_`)만 쓴다.
- 지금의 변수 단위 목록(`dmy_limit`, `dmy_ptr`, `return`)은 지금과 같은 결과를 낸다. 기존 단위 테스트는
  "mixed"를 다루던 것만 기호 단위로 바꾸고 나머지는 그대로 통과해야 한다.
- 화면 문구와 개수 단위는 그대로다. `지정` 줄의 `변수 N(그중 바뀜 M)`은 목록 줄 수, 해제·값 있어 둠은 변수 수
  (기호가 하나라도 해제된 변수를 1로 셈)다. `건너뜀` 줄 끝에만 `CT에 없음 N`이 붙는다. 한 줄 120열 안.
- 커밋은 Conventional Commits, 한국어 요약, 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  사용자에게 보이는 변경은 같은 커밋에 `CHANGELOG.md`를 고친다. push는 `git push origin HEAD:develop HEAD:main`.

## Review Focus

- 목록 칸 안의 공백·앞 0(`v[ 01 ] . s`): CT 기호 `v[1].s`를 덮어야 한다(Task 2 테스트).
- 이름이 다른 이름의 앞부분(`a`와 `ab`): `a` 줄이 `ab`를 덮으면 안 된다(Task 2 테스트).
- 위 줄(`a`)이 `값 있음`으로 건너뛰어도 아래 줄(`a.b`)은 따로 판정하고, 위 줄 몫의 기호는 해제하지 않는다(Task 2
  테스트).
- 함수 여럿·파일 불일치로 테스트를 못 고른 멤버 줄(`a.b`): 그 함수 테스트들에서 `a.b`가 해제되면 안 된다(Task 2
  테스트).
- 이름 꼴이 아니라 사본에서 뺀 테스트: 그 테스트의 기호 단위 바뀜도 `edits`에서 빠져야 한다(Task 2 테스트).

---

### Task 1: 서버 PC 견본 확인 도구와 todo.md 19·20절

**Files:**
- Create: `examples/ct_sample/dmy_rec.example.c`
- Create: `tools/member_probe.py`
- Create: `tests/unit/test_member_probe.py`
- Modify: `tools/todo_run.py` (`SECTIONS`)
- Modify: `todo.md` (18절 뒤에 19·20절)

**Interfaces:**
- Consumes: `ct_export.decode_csv(data) -> (text, encoding)`, `ct_export.split_fields(line)`, `ct_export.SECTIONS`,
  `ct_export.UNIT_DIR`, `paths.result_dir()`.
- Produces (이 Task 안에서만 쓴다):
  - `show_lines(export_dir: Path) -> List[str]`
  - `make_variants(export_dir: Path, out_dir: Path) -> List[str]` (화면 줄)
  - `main(argv: Sequence[str]) -> int` — `member_probe.py <내보낸 폴더> [--make]`

`dmy_rec.example.c`(ASCII만, 머리 주석은 `dmy_io.example.c`와 같은 꼴):

```c
typedef struct {
    int dmy_s;
    int dmy_t;
} dmy_rec_t;

dmy_rec_t dmy_recs[4];   /* read and written, array of struct */
int dmy_sum;             /* written */

int dmy_pick(int dmy_i)
{
    dmy_recs[dmy_i & 3].dmy_t = dmy_recs[dmy_i & 3].dmy_s + 1;
    dmy_sum = dmy_recs[0].dmy_s + dmy_recs[2].dmy_t;
    return dmy_recs[3].dmy_t;
}
```

`show_lines`: 내보낸 폴더의 `UnitTests` CSV(상대 경로 순)마다 `<테스트 이름>  <input> a, b  <expect> c` 꼴 한 줄(네
구역 모두, 빈 구역은 생략). 이름·기호는 `dmy_`로 시작하거나 `returnVar`이면 그대로, 아니면 `*`. 118열을 넘으면
4칸 들여 다음 줄로 잇는다. CT 꼴이 아닌 CSV는 마지막에 `읽지 못한 CSV N` 한 줄로만 센다.

`make_variants`: 내보낸 폴더에서 이름이 `dmy_calc_test`, `dmy_pick_test`로 시작하는 첫 CSV를 원본으로 삼아
`out_dir/v1`~`v4/<원래 파일 이름>`에 쓴다. 칸을 더할 때는 그 구역 끝(다음 구역 표시 앞)에 넣고 케이스 줄의 같은
자리에 빈 칸을 넣는다. 칸을 뺄 때는 머리글과 케이스 줄에서 그 칸을 지운다. 인코딩과 줄 끝은 원본 그대로.

| 변형 | 원본 | 바꾸는 것 |
| --- | --- | --- |
| v1 | dmy_calc | `dmy_hist[2]`를 `<expect>`, `<output>`, `<toutput>`에 더함 |
| v2 | dmy_pick | 머리글에서 처음 나오는 `[0].`이 든 기호의 `[0]`을 `[2]`로 바꾼 기호를 `<expect>`, `<output>`, `<toutput>`에 더함 |
| v3 | dmy_calc | `dmy_limit.dmy_zz`를 `<input>`에 더함 |
| v4 | dmy_calc | `dmy_limit.dmy_hi`를 모든 구역에서 뺌 |

돌려주는 줄: 변형마다 `v1 dmy_hist[2]를 기대값에 더함` 꼴의 정해 둔 문구 한 줄, 원본이 없으면 `v2 만들지 못함:
dmy_pick 테스트가 내보낸 폴더에 없음`.

`main`: 폴더가 없으면 `[ERROR] 내보낸 폴더를 읽을 수 없음: todo.md 절의 경로로 내보냈는지 확인`, 1. 있으면
`show_lines`를 찍고, `--make`면 `paths.result_dir() / 'probe' / <yyyyMMdd_HHmmss>`에 `make_variants`를 쓰고
`변형 CSV: result\probe\<시각>\`과 그 줄들을 찍는다. 0.

- [ ] **Step 1: `tests/unit/test_member_probe.py`에 실패하는 테스트를 쓴다.** `tools`를 `sys.path`에 넣는 것은
  `test_io_run.py`처럼. 견본 CSV는 `test_ct_export`의 `_csv(header=...)`로 만든다.
  - `test_show_masks_names_not_starting_with_dmy`: 머리글에 `secret_x`, 테스트 이름 `secret_f_test0`인 CSV와
    견본 CSV → 모든 줄에 `secret`이 없고, `dmy_gain`과 `dmy_calc_test0`은 있다.
  - `test_show_lines_fit_120`: 기호 40개짜리 머리글 → 모든 줄 `len(line) <= 120`.
  - `test_make_writes_four_variants`: `dmy_calc_test0.csv`(`test_ct_export.HEADER`)와 `dmy_pick_test0.csv`(머리글
    `,<input>,dmy_i,dmy_recs[0].dmy_s,dmy_recs[0].dmy_t,<expect>,dmy_recs[0].dmy_t,dmy_sum,returnVar,<output>,dmy_recs[0].dmy_t,dmy_sum,returnVar,<toutput>,dmy_recs[0].dmy_t,dmy_sum,returnVar`)
    → v1 `<expect>`에 `dmy_hist[2]`, v2 `<expect>`에 `dmy_recs[2].dmy_s`, v3 `<input>`에 `dmy_limit.dmy_zz`, v4 머리글에
    `dmy_limit.dmy_hi` 없음. 네 파일 모두 케이스 줄의 칸 수가 머리글 칸 수와 같다(`split_fields`). 구역은
    `test_ct_export._by_section`으로 본다.
  - `test_missing_pick_test_reports_and_continues`: dmy_calc만 있는 폴더 → 돌려준 줄에 `v2 만들지 못함`이 있고 v1·v3·v4
    파일은 있다.
  - `test_main_missing_folder_exits_1`: 없는 폴더 → 1, 출력에 그 경로가 없다.
- [ ] **Step 2:** `python -m unittest tests.unit.test_member_probe` → import 실패로 FAIL.
- [ ] **Step 3:** `examples/ct_sample/dmy_rec.example.c`와 `tools/member_probe.py`를 위 대로 만든다.
- [ ] **Step 4:** `python -m unittest discover -s tests/unit` → 모두 PASS.
- [ ] **Step 5: `todo_run.SECTIONS`와 todo.md.**
  - `'19': ('원소·멤버 견본 머리글 보기와 변형 CSV 만들기', ['tools/member_probe.py', 'C:/ctsample/out/12', '--make'])`
  - `'20': ('변형 CSV로 만든 테스트 머리글 보기', ['tools/member_probe.py', 'C:/ctsample/out/13'])`
  - todo.md 19절(왜: 설계 "서버 PC 견본으로 먼저 볼 것" 1~4. CT: 저장소의 `examples\ct_sample\dmy_rec.example.c`를
    `C:\ctsample\src\dmy_rec.c`로 복사해 `ctsample` 프로젝트에 넣고 분석, `dmy_pick` 테스트 만들기, 전체를 새 빈 폴더 `C:\ctsample\out\12`에 [가로]로
    내보내기, `todo.bat` 19. 확인할 것: `dmy_pick` 줄에 `dmy_recs[...]` 기호가 어떤 꼴로 몇 개 오는지, 변형 네 줄.
    돌려줄 것: 캡처 한 장)와 20절(CT: 19절이 쓴 `result\probe\<가장 늦은 시각>\v1`~`v4`의 CSV를 하나씩 [테스트 데이터로
    테스트 생성하기]로 넣고 알림이 나오면 변형 번호와 알림 종류를 적기, 전체를 새 빈 폴더 `C:\ctsample\out\13`에
    내보내기, `todo.bat` 20. 확인할 것: 새로 생긴 테스트에 `dmy_hist[2]`, `dmy_recs[2]…`, `dmy_limit.dmy_zz`가 있는지,
    `dmy_limit.dmy_hi`가 빠졌는지. 돌려줄 것: 캡처 한 장과 알림 종류). 경로 입력은 없다.
- [ ] **Step 6:** `python -m unittest discover -s tests/unit` → PASS. 커밋:
  `feat: 원소·멤버 지정 견본 확인용 member_probe와 todo.md 19·20절을 더한다`

### Task 2: 기호 단위 맞춰 보기 (1차)

**Files:**
- Modify: `src/ct_toolkit/io_match.py`
- Modify: `src/ct_toolkit/ct_export.py` (`_variables` → `_symbols`, `_read_test`, `_new_header`, `rewrite_csv` 설명)
- Modify: `src/ct_toolkit/io_apply.py` (`_without_tests`, `write_skipped`)
- Test: `tests/unit/test_io_match.py`, `tests/unit/test_ct_export.py`, `tests/unit/test_io_apply.py`

**Interfaces:**
- Produces:
  - `CtVar(name, direction, has_values=False, supported=True)` — `name`은 머리글에 적힌 CT 기호 그대로(리턴은
    `returnVar`), `direction`은 `'in'|'out'|'inout'|''`. `'mixed'`는 없어진다.
  - `CtTest(key, function, file, symbols)` — 필드 이름 `variables` → `symbols: Mapping[str, CtVar]`(키는 CT 기호).
  - `R_NOT_IN_CT = 'CT에 없음'`, `SKIP_REASONS = (R_MULTI, R_NO_VAR, R_CONFLICT, R_HAS_VALUES, R_TYPE, R_NOT_IN_CT)`.
  - `to_symbol(variable: str) -> str` — 공백을 모두 지우고, 첨자 앞 0을 떼고(`[01]`→`[1]`, `[0]`은 그대로), 맨 앞
    `return`(그 뒤가 끝이거나 `.`·`[`)을 `returnVar`로 바꾼다.
  - `covers(path: str, symbol: str) -> bool` — `symbol == path`이거나 `path` 바로 뒤에 `.`, `[`, `->`가 이어진다.
  - `MatchResult`에 마지막 필드 `symbol_changes: Dict[str, Dict[str, str]]`(테스트 key → 기호 → 새 지정). `applied`와
    `changes`는 테스트 key → 줄 경로(해석된 것) → 지정(줄 단위, 지금처럼). `released`·`kept`는 기호 이름 목록(이름 순).
    `released_vars`·`kept_vars`는 테스트마다 기호의 맨 앞 식별자(`[A-Za-z_]\w*`)가 다른 것의 수를 더한다. `edits`는
    `symbol_changes`와 해제 기호(`''`)로 만든다.
  - `rewrite_csv(text, directions, reset_cases)` — `directions` 키가 기호 그대로면 그것을, 아니면 그 기호의 변수
    이름(`symbol_variable`)을 본다.

`match`의 판정(설계 "맞춰 보기"):

1. 줄을 `(함수, 파일, to_symbol(변수))`로 묶고, 묶음 안 `구분`이 다르면 모두 `목록 충돌`(지금처럼).
2. 묶음마다 테스트를 고른다(`_pick`, 지금처럼). 못 고르면 그 경로와 `경로 + '_mem'`을 그 함수의 보호 경로로 둔다.
3. 고른 테스트에서 경로를 해석한다: 경로가 덮는 기호가 없고 경로가 식별자 하나면 `경로 + '_mem'`으로 다시 본다.
   덮는 기호가 여전히 없으면, 경로의 맨 앞 식별자(또는 그 `_mem`)를 맨 앞 식별자로 가진 기호가 테스트에 있으면
   `CT에 없음`, 없으면 `변수 없음`.
4. 한 테스트에서 해석된 경로가 같은 묶음이 둘 이상이면 행 번호가 앞선 것만 남기고, 뒤의 것은 `구분`이 다르면
   `목록 충돌`, 같으면 조용히 하나로 친다.
5. 기호마다 덮는 경로 가운데 가장 긴 경로의 줄이 주인이다. 줄의 몫 = 자기가 주인인 기호.
6. 줄마다 몫으로 판정한다: 몫에 `supported=False`가 있으면 `타입 제외`, `reset_cases`가 아니고 몫 가운데 지정이
   바뀌는 기호에 값이 있으면 `값 있음`, 아니면 `applied[key][경로] = 구분`, 바뀌는 기호를 `symbol_changes`에, 하나라도
   바뀌면 `changes[key][경로] = 구분`. 몫이 비어도 `applied`에는 든다.
7. 보호 기호 = 3에서 덮은 기호(건너뛴 줄 것도) ∪ 2의 보호 경로가 덮는 기호. 고른 테스트의 기호 가운데 보호되지 않고
   `supported`이고 `direction`이 빈 값이 아닌 것은 해제(`reset_cases`가 아니고 값이 있으면 `kept`).

- [ ] **Step 1: `test_io_match.py`에 실패하는 테스트를 더한다.** 기호 이름은 `_test('k', 'dmy_f', **{'a.b': CtVar('a.b', 'in')})`처럼 넘긴다.
  - `test_member_rows_designate_only_those_members`: 기호 `a.b`, `a.d`, `a.C`, `a.e`(모두 `in`), 줄 `a.b` 입력,
    `a.d` 입력, `a.C` 출력 → `changes == {'k': {'a.C': 'out'}}`, `symbol_changes == {'k': {'a.C': 'out'}}`,
    `released == {'k': ['a.e']}`, `released_vars == 1`, `edits == {'k': {'a.C': 'out', 'a.e': ''}}`.
  - `test_element_row_covers_its_members`: 기호 `v[0].s`, `v[0].t`, `v[1].s`(모두 `in`), 줄 `v[0]` 출력, `v[1].s` 입력 →
    `symbol_changes == {'k': {'v[0].s': 'out', 'v[0].t': 'out'}}`, `assigned == 2`, `changed_vars == 1`, `released == {}`.
  - `test_most_specific_row_wins`: 기호 `a.b`, `a.d`(`in`), 줄 `a` 입력, `a.b` 출력 → `symbol_changes == {'k': {'a.b': 'out'}}`, `assigned == 2`.
  - `test_missing_member_is_not_in_ct_and_unknown_variable_is_no_var`: 기호 `v[0].s`(`in`), 줄 `v[0].s` 입력, `v[2].s` 출력,
    `w[0]` 입력 → skips `[(v[2].s 줄, R_NOT_IN_CT), (w[0] 줄, R_NO_VAR)]`.
  - `test_name_prefix_is_not_covered`: 기호 `a`, `ab`(`in`), 줄 `a` 출력 → `symbol_changes == {'k': {'a': 'out'}}`, `released == {'k': ['ab']}`.
  - `test_spaces_and_leading_zero_are_normalized`: 기호 `v[1].s`(`in`), 줄 변수 `'v[ 01 ] . s'` 출력 → `applied == {'k': {'v[1].s': 'out'}}`.
  - `test_return_row_matches_return_var`: 기호 `returnVar`(`out`), 줄 `return` 출력 → `applied == {'k': {'returnVar': 'out'}}`, `changes == {}`.
  - `test_skipped_parent_row_keeps_its_share_and_child_still_applies`: 기호 `a.b`(`in`), `a.d`(`in`, 값 있음), 줄 `a` 출력,
    `a.b` 출력 → skips `[(a 줄, R_HAS_VALUES)]`, `symbol_changes == {'k': {'a.b': 'out'}}`, `released == {}`.
  - `test_unpicked_member_row_protects_symbols`: 같은 함수 테스트 A(`src\\a.c`), B(`src\\b.c`), 둘 다 기호 `a.b`, `x`(`in`).
    줄 `x` 입력(파일 `a.c`, A를 고름), `a.b` 출력(파일 없음) → skips `[(a.b 줄, R_MULTI)]`, `released == {}`(A의 `a.b`는
    못 고른 줄이 이름 붙여 보호된다).
  - `test_released_counts_variables`: 기호 `a.b`, `a.d`, `x`(`in`), 줄 `x` 입력 → `released == {'k': ['a.b', 'a.d']}`, `released_vars == 1`.
- [ ] **Step 2:** `python -m unittest tests.unit.test_io_match` → 새 테스트 FAIL(`symbol_changes`·`R_NOT_IN_CT` 없음).
- [ ] **Step 3: `io_match`를 위 Interfaces와 판정대로 고친다.** `_find`는 3의 해석으로 바뀐다.
- [ ] **Step 4: `ct_export`를 고친다.** `_symbols(columns, cases) -> Dict[str, CtVar]`: `<input>`·`<expect>`의 기호마다 든
  구역으로 `in`/`out`/`inout`, 값은 그 기호의 칸만, `supported`는 `symbol_variable(기호)[1]`. `_read_test`는 이것으로
  `CtTest`를 만든다. `_new_header`는 `기호 in directions`면 기호로, 아니면 `symbol_variable(기호)[0]`로 지정을 찾는다.
- [ ] **Step 5: `test_ct_export.py`를 기호 단위로 바꾼다.**
  - `test_load_groups_symbols_by_variable` → `test_load_reads_symbols`: `set(test.symbols) == {'dmy_count', 'dmy_gain',
    'dmy_hist[0]', 'dmy_limit.dmy_hi', 'dmy_limit.dmy_lo', 'dmy_mode', 'dmy_ptr_mem[0]', 'dmy_spare', 'dmy_x', 'dmy_level',
    'returnVar'}`, 방향은 `dmy_count`·`dmy_hist[0]`이 `inout`, `dmy_level`·`returnVar`가 `out`, 나머지 `in`.
  - `test.variables['return']` → `test.symbols['returnVar']`, `['dmy_x']` 등은 키 그대로 `symbols`로. 지원 안 되는 기호
    테스트는 `test.symbols['p->x']`(`supported` 거짓, `in`).
  - mixed 테스트 넷을 바꾼다: `test_struct_members_keep_their_own_sections`(`MIXED_HEADER` → `st.cnt` `inout`, `st.mode`
    `in`, `dmy_ok` `inout`, `dmy_in` `in`), `test_whole_struct_row_puts_every_member_in_listed_sections`(지금 assertion
    그대로, `changes == {key: {'st': 'inout'}}`), 값 테스트(`st.mode`에 값 → `R_HAS_VALUES`, `edits`에 `st.mode` 없음,
    reset이면 `changes == {key: {'st': 'inout'}}`), `test_unlisted_struct_members_are_released`(`released[key]`에 `st.cnt`와
    `st.mode`).
  - 새 `test_rewrite_with_symbol_key_moves_only_that_member`: `rewrite_csv(_sample_text(), {'dmy_limit.dmy_hi': ''}, False)`
    → `<input>`에 `dmy_limit.dmy_lo`는 있고 `dmy_limit.dmy_hi`는 없다.
- [ ] **Step 6: `io_apply`를 고친다.** `_without_tests`가 `symbol_changes`도 거른다. `write_skipped`는 `R_NOT_IN_CT`
  건너뜀의 이유 칸을 `'CT에 없음: CT에서 원소·멤버를 늘린 뒤 다시 내보내기'`(상수 `R_NOT_IN_CT_TEST`)로 쓴다.
- [ ] **Step 7: `test_io_apply.py`.**
  - `_result()`에 `symbol_changes={'k1': {'dmy_a': 'in'}}`를 더한다. `test_full_summary_lines`의 건너뜀 줄 기대를
    `'건너뜀    함수 여럿 0, 변수 없음 1, 목록 충돌 0, 값 있음 0, 타입 제외 0, CT에 없음 0'`으로.
  - 새 `test_skipped_file_explains_not_in_ct`: `Skip(5, 'dmy_calc', 'v[2].s', R_NOT_IN_CT)` → 파일에 `R_NOT_IN_CT_TEST`.
  - 새 `test_member_rows_end_to_end`: `MIXED_HEADER` CSV 견본 폴더, 목록 `st.cnt` 출력, `dmy_ok` 입출력, `dmy_in` 입력 →
    사본의 `<expect>`에 `st.cnt`, `<input>`에 `st.cnt`·`st.mode` 없음, 화면 `목록에 없어 해제 1`.
  - 새 `test_renamed_test_member_changes_left_out`: 이름 꼴이 아닌 테스트에서 기호가 바뀌는 경우 `writer`가 받은
    `edits`에 그 키가 없다.
  - `test_main_end_to_end_on_sample_export`와 `test_screen_fits_one_page`는 그대로 통과해야 한다.
- [ ] **Step 8:** `python -m unittest discover -s tests/unit` → 모두 PASS. 커밋:
  `feat: 목록의 원소·멤버 줄(a.b, v[1].s)을 기호 단위로 지정하고 CT에 없는 것은 건너뛴다` (CHANGELOG는 Task 3)

### Task 3: 문서와 예시 목록

**Files:**
- Modify: `README.md` ("입력·출력 지정 목록 형식"의 구조체·배열 줄, 건너뜀 설명)
- Modify: `examples/io_list_template.example.xlsx`, `tests/unit/test_io_list.py`
- Modify: `CHANGELOG.md`, `todo.md`(18절 주의), `docs/ai/handoff.md`, `docs/design/io-designation-members.md`(상태)

- [ ] **Step 1: README.** 구조체·배열 줄을 바꾼다: 이름만 적으면 전체, `a.b`, `v[0]`, `v[1].s`처럼 적으면 그것과 그 아래만,
  한 기호에 여러 줄이 걸리면 더 자세한 줄, 적지 않은 멤버·원소는 지정 해제, CT가 아직 가져오지 않은 원소·멤버는
  `CT에 없음`으로 건너뛰니 CT에서 늘린 뒤 내보낸다. "입력·출력 지정 쓰는 순서" 끝에 확인 단계를 더한다: 사본으로
  테스트를 만든 뒤 다시 내보내 `io-apply.bat`을 `n`으로 돌려 `바꾼 것 0`인지 본다(목록 오타로 CT가 버린 기호가
  여기서 드러난다, 설계 "다시 돌려 확인").
- [ ] **Step 2: 예시 XLSX.** openpyxl로 `목록` 시트 `dmy_ctrl_update` 줄 뒤에 두 줄을 넣는다: `ID 1014, dmy_ctrl_update,
  dmy_tbl[0], 출력, , dmy_tbl_t[4], , 원소까지 적으면 그 원소만(멤버 전체)`와 `ID 1015, dmy_ctrl_update, dmy_tbl[2].dmy_a,
  출력, , int, , 원소의 멤버까지 적으면 그것만. 적지 않은 원소·멤버는 지정 해제`. `적는 법` 시트의 구조체·배열 줄도
  Step 1과 같게 바꾼다. `test_template_example_reads_without_errors`의 기대를 `(15, 3, [])`로.
- [ ] **Step 3: 나머지 문서.** CHANGELOG 맨 위에 원소·멤버 줄 항목. todo.md 18절 주의를 "멤버·원소 줄도 된다. CT가 아직
  가져오지 않은 원소·멤버는 `CT에 없음`으로 건너뛰니, 그런 함수는 CT에서 원소·멤버를 늘린 뒤 내보낸다"로. handoff "단계"·
  "다음 할 일"(19·20절)과 실물 미검증(기호 단위 판정은 단위 테스트만, CT 기호 꼴은 19절)을 고친다. 설계 문서 상태에
  "1차 정적 구현".
- [ ] **Step 4:** `python -m unittest discover -s tests/unit` → PASS. 커밋:
  `docs: 원소·멤버 줄 적는 법을 README와 예시 목록에 적는다`. push.
