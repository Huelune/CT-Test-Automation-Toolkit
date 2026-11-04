"""원소·멤버 지정 견본 확인 도구 (todo.md 22절). `case_check.py <견본 폴더> [<변형 폴더>]`.

견본 폴더(CT가 dmy_calc·dmy_pick 테스트를 내보낸 것)의 머리글을 찍고, 모든 경우를 한 번에 본다.
`examples/ct_sample/io_cases.example.xlsx`의 줄마다 `기대` 칸과 툴킷의 판정을 맞춰 본다. 실제 흐름처럼 케이스
정리(`io-apply.bat`의 `y`)로 판정해 사본을 만들고, 그 사본을 견본 폴더의 복사본에 덮어 케이스 정리 없이(`n`) 다시
돌렸을 때 바뀔 것이 없는지(README 8단계의 확인), `해제 기대` 시트의 기호가 사본에서 빠졌는지도 본다. 목록 한 장으로 만들 수 없는 함수 여럿·값 있음·타입 제외는 내보낸 dmy_calc CSV를 고친 사본으로
따로 본다. 이 확인의 파일은 임시 폴더에만 쓴다.

변형 폴더를 주었는데 아직 없으면 CT가 기호 칸을 더하거나 뺀 CSV를 받는지 볼 변형을 `result\\probe\\<시각>\\`에
만들고, 있으면(사용자가 변형을 CT에 넣고 내보낸 뒤) 그 머리글을 찍는다(member_probe).

화면에는 행 번호, 정해 둔 낱말(지정, 건너뜀 이유), 개수, 견본 이름(member_probe의 가림 규칙)만 찍는다.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import warnings
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Sequence, Tuple

from member_probe import CALC, E_OPEN, _add, _find_source, _mask, _write, make_variants, show_lines

from ct_toolkit import paths
from ct_toolkit.ct_export import ExportError, load_tests, write_copy
from ct_toolkit.io_list import ListFileError, ListRow, read_list
from ct_toolkit.io_match import R_HAS_VALUES, R_MULTI, R_TYPE, MatchResult, match, to_symbol

CASES = Path('examples') / 'ct_sample' / 'io_cases.example.xlsx'
APPLIED, NOT_EXPORTED, UNKNOWN = '지정', '내보내지 않은 함수', '알 수 없음'
E_LIST = '[ERROR] 경우 목록을 읽을 수 없음: 저장소의 examples\\ct_sample\\io_cases.example.xlsx가 있는지 확인'


def read_cases(path: Path) -> Tuple[List[ListRow], Dict[int, str], List[Tuple[str, str]]]:
    """(목록 줄, 행 번호 -> 기대, 해제 기대 (함수, 기호)). 줄은 툴킷과 같이 `read_list`로 읽는다."""
    rows = read_list(path).rows
    import openpyxl
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')  # openpyxl 경고는 설치 경로와 함께 찍힌다
        book = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        table = list(book.worksheets[0].iter_rows(values_only=True))
        at = [str(c).strip() if c is not None else '' for c in table[0]].index('기대')
        expected = {n: str(r[at]).strip() for n, r in enumerate(table[1:], start=2)
                    if at < len(r) and r[at] is not None}
        released = [(str(r[0]).strip(), str(r[1]).strip())
                    for r in book['해제 기대'].iter_rows(min_row=2, values_only=True) if r[0] and r[1]]
    finally:
        book.close()
    return rows, expected, released


def row_result(r: ListRow, result: MatchResult, keys: Dict[str, List[str]]) -> str:
    """줄 하나의 판정: 건너뜀 이유, 지정, 내보내지 않은 함수."""
    for s in result.skips:
        if s.row == r.row:
            return s.reason
    path = to_symbol(r.variable)
    for key in keys.get(r.function, []):
        got = result.applied.get(key, {})
        if r.direction in (got.get(path), got.get(path + '_mem')):
            return APPLIED
    return NOT_EXPORTED if r.function in result.not_exported else UNKNOWN


def check_list(export_dir: Path, rows: List[ListRow], expected: Dict[int, str],
               released: List[Tuple[str, str]], work: Path) -> Tuple[List[str], bool]:
    """목록 경우, 다시 돌림, 해제 기대를 보고 (화면 줄, 모두 맞음)을 돌려준다."""
    tests = load_tests(export_dir).tests
    keys: Dict[str, List[str]] = {}
    for t in tests:
        keys.setdefault(t.function, []).append(t.key)
    # CT가 막 만든 테스트에는 자동 생성 케이스 값이 있다. 실제 흐름처럼 케이스 정리(y)로 고치고 다시 돌림은 n으로 본다
    result = match(rows, tests, True)
    right, detail, wrong = 0, [], 0
    for r in rows:
        want, got = expected.get(r.row, ''), row_result(r, result, keys)
        options = want.split('|')
        if got not in options:
            wrong += 1
            detail.append('틀림  행 {} 기대 {}, 결과 {}'.format(r.row, want or '(비었음)', got))
        elif len(options) > 1:
            detail.append('참고  행 {} {}'.format(r.row, got))
        else:
            right += 1
    lines = ['경우 {}: 맞음 {}, 틀림 {}, 참고 {}'.format(len(rows), right, wrong, len(detail) - wrong)] + detail

    again_dir = work / 'again'  # 사용자가 사본으로 테스트를 다시 만들고 다시 내보낸 것과 같은 꼴
    shutil.copytree(str(export_dir), str(again_dir))
    write_copy(export_dir, again_dir, result.edits, True)
    again = load_tests(again_dir).tests
    left = len(match(rows, again).edits)
    lines.append('다시 돌림: 바뀔 테스트 {}{}'.format(left, '' if left == 0 else ' (틀림)'))

    by_function: Dict[str, list] = {}
    for t in again:
        by_function.setdefault(t.function, []).append(t)
    missed = [s for f, s in released
              if not by_function.get(f) or any(s in t.symbols for t in by_function[f])]
    lines.append('해제 기대 {}: 맞음 {}, 틀림 {}'.format(len(released), len(released) - len(missed), len(missed)))
    lines.extend('틀림  해제 안 됨 {}'.format(_mask(s)) for s in missed)
    return lines, wrong == 0 and left == 0 and not missed


def _set_value(symbol: str, value: str) -> Callable[[List[List[str]]], None]:
    """첫 케이스 줄에서 그 기호의 칸마다 값을 넣는다."""
    def edit(rows: List[List[str]]) -> None:
        if len(rows) < 2:
            return
        case = rows[1]
        case.extend([''] * (len(rows[0]) - len(case)))
        for i, cell in enumerate(rows[0]):
            if cell.strip() == symbol:
                case[i] = value
    return edit


def extra_cases(export_dir: Path, work: Path) -> Tuple[List[str], bool]:
    """목록 한 장으로 만들 수 없는 경우를 dmy_calc CSV를 고친 사본으로 본다."""
    calc = _find_source(export_dir, CALC)
    if calc is None:
        return ['추가 경우 만들지 못함: dmy_calc 테스트가 내보낸 폴더에 없음'], False
    level = ListRow(2, 'dmy_calc', 'dmy_level', 'in')  # 견본에서 dmy_level은 출력이라 입력은 바뀜이다
    cases = [  # (화면 이름, 폴더 이름, 쓸 폴더들, 고치기, 줄, 케이스 정리, 기대)
        ('함수 여럿', 'multi', ['a/UnitTests', 'b/UnitTests'], lambda rows: None,
         ListRow(2, 'dmy_calc', 'dmy_gain', 'in'), False, R_MULTI),
        ('값 있음', 'values', ['UnitTests'], _set_value('dmy_level', '1'), level, False, R_HAS_VALUES),
        ('값 있음+케이스 정리', 'reset', ['UnitTests'], _set_value('dmy_level', '1'), level, True, APPLIED),
        ('타입 제외', 'type', ['UnitTests'], lambda rows: _add(rows, '<input>', 'dmy_q->dmy_z'),
         ListRow(2, 'dmy_calc', 'dmy_q', 'in'), False, R_TYPE),
    ]
    wrong: List[str] = []
    for label, folder, places, edit, row, reset, want in cases:
        root = work / folder
        for place in places:
            _write(calc, root, place, edit)
        got = match([row], load_tests(root).tests, reset)
        result = next((s.reason for s in got.skips), APPLIED if got.applied else UNKNOWN)
        if result != want:
            wrong.append('틀림  {} 기대 {}, 결과 {}'.format(label, want, result))
    lines = ['추가 경우 {}: 맞음 {}, 틀림 {}'.format(len(cases), len(cases) - len(wrong), len(wrong))]
    return lines + wrong, not wrong


def main(argv: Sequence[str]) -> int:
    if len(argv) not in (1, 2) or not Path(argv[0]).is_dir():
        print(E_OPEN)
        return 1
    export_dir = Path(argv[0])
    try:
        rows, expected, released = read_cases(paths.project_root() / CASES)
    except (ListFileError, OSError, KeyError, ValueError, IndexError):
        print(E_LIST)
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        try:
            lines, ok = check_list(export_dir, rows, expected, released, work)
            extra, extra_ok = extra_cases(export_dir, work)
        except ExportError as exc:
            print('[ERROR] ' + str(exc))
            return 1
    lines = ['견본 머리글'] + show_lines(export_dir) + lines + extra
    if len(argv) == 2 and Path(argv[1]).is_dir():
        lines += ['변형으로 만든 테스트 머리글'] + show_lines(Path(argv[1]))
    elif len(argv) == 2:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        lines += ['변형 CSV: result\\probe\\{}\\'.format(stamp)]
        lines += make_variants(export_dir, paths.result_dir() / 'probe' / stamp)
    for line in lines:
        print(line)
    return 0 if ok and extra_ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
