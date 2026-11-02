"""CT [테스트 내보내기] 폴더 읽기와 지정을 바꾼 사본 쓰기.

CT 2025는 입력·출력 지정을 테스트 데이터 CSV의 머리글 줄에 적는다(docs/design/io-designation.md
"견본 결과"). 폴더 안의 CSV를 `CtTest`로 읽는다. 함수 이름은 CSV 둘째 줄의 테스트 이름에서,
안 되면 같은 이름 `.utest`에서 얻고, `.utest`는 읽기만 한다. 사본 쓰기는 아직 없다.
화면에 나갈 수 있는 `ExportError` 문구는 정해 둔 상수뿐이다(경로·예외 원문을 넣지 않는다).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Set, Tuple

from .io_match import CtTest, CtVar

E_EXPORT_OPEN = '내보낸 폴더를 읽을 수 없음: --export에 [테스트 내보내기]로 고른 폴더를 주었는지 확인'
E_EXPORT_EMPTY = ('내보낸 폴더에 테스트 데이터 CSV가 없음: '
                  '[테스트 내보내기]에서 유닛 테스트의 테스트 데이터를 체크했는지 확인')

FIRST_LINE = 'CT(Controller Tester) Test Data'
NAME_PREFIX = 'test name:'
S_INPUT, S_EXPECT = '<input>', '<expect>'
SECTIONS = (S_INPUT, S_EXPECT, '<output>', '<toutput>')
RETURN_SYMBOL = 'returnVar'

_LINE_END = re.compile(r'\r?\n')
_IDENT = re.compile(r'[A-Za-z_]\w*')
_SUPPORTED = re.compile(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*|\[\d+\])*')  # 변수, 멤버, 배열 원소
_TEST_NAME = re.compile(r'(.+)_test\d+')
_UTEST_CANDIDATE = re.compile(rb'(?=[A-Za-z_]\w*\()')  # 시그니처 글자열이 시작할 수 있는 자리
_UTEST_FUNCTION = re.compile(rb'([A-Za-z_]\w*)\(')
_PRINTABLE = re.compile(rb'[\x20-\x7e]+')
_UTEST_FILE = re.compile(rb'\\([\x21-\x5b\x5d-\x7e]+?\.(?:c|cc|cpp|cxx))(?![\w])')


class ExportError(Exception):
    """내보낸 폴더를 쓸 수 없다. `str(exc)`는 화면에 찍어도 되는 정해 둔 문구다."""


@dataclass
class ExportRead:
    tests: List[CtTest]
    unreadable: List[str]  # 읽지 못한 CSV의 내보낸 폴더 기준 상대 경로(posix)


def split_fields(line: str) -> List[str]:
    """쉼표로 나눈다. 따옴표 안의 쉼표는 나누지 않고, 칸은 따옴표까지 원문 그대로 둔다."""
    fields: List[str] = []
    start = 0
    quoted = False
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == ',' and not quoted:
            fields.append(line[start:i])
            start = i + 1
    fields.append(line[start:])
    return fields


def symbol_variable(symbol: str) -> Tuple[str, bool]:
    """CT 기호가 가리키는 변수 이름과 툴킷이 그 기호 꼴을 쓸 줄 아는지."""
    found = _IDENT.match(symbol)
    name = found.group() if found else symbol
    if name == RETURN_SYMBOL:
        name = 'return'
    return name, _SUPPORTED.fullmatch(symbol) is not None


def decode_csv(data: bytes) -> Tuple[str, str]:
    """(글, 인코딩 이름). BOM이 있으면 utf-8-sig, UTF-8이 아니면 CT 견본의 cp949."""
    if data.startswith(b'\xef\xbb\xbf'):
        return data.decode('utf-8-sig'), 'utf-8-sig'
    try:
        return data.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError:
        return data.decode('cp949'), 'cp949'


def _symbol_columns(header: List[str]) -> Dict[str, List[Tuple[int, str]]]:
    """구역 표시 -> [(칸 번호, 기호)]. 구역 표시도 칸 하나를 차지한다."""
    columns: Dict[str, List[Tuple[int, str]]] = {}
    section: Optional[str] = None
    for i, cell in enumerate(c.strip() for c in header):
        if cell in SECTIONS:
            section = cell
            columns.setdefault(section, [])
        elif section is not None and cell:
            columns[section].append((i, cell))
    return columns


def _variables(columns: Mapping[str, List[Tuple[int, str]]],
               cases: List[List[str]]) -> Dict[str, CtVar]:
    """`<input>`은 입력, `<expect>`는 출력 지정이다. 값도 그 두 구역의 칸만 본다."""
    directions: Dict[str, Set[str]] = {}
    cells: Dict[str, List[int]] = {}
    unsupported: Set[str] = set()
    for section, direction in ((S_INPUT, 'in'), (S_EXPECT, 'out')):
        for column, symbol in columns.get(section, []):
            name, supported = symbol_variable(symbol)
            directions.setdefault(name, set()).add(direction)
            cells.setdefault(name, []).append(column)
            if not supported:
                unsupported.add(name)
    variables: Dict[str, CtVar] = {}
    for name, found in directions.items():
        direction = 'inout' if len(found) > 1 else next(iter(found))
        has_values = any(column < len(case) and case[column].strip()
                         for case in cases for column in cells[name])
        variables[name] = CtVar(name, direction, has_values, name not in unsupported)
    return variables


def _utest_function(utest: bytes) -> Optional[str]:
    """`.utest`(Java 직렬화)의 첫 함수 시그니처 글자열에서 함수 이름.

    Java는 문자열을 2바이트 big-endian 길이와 그 길이만큼의 바이트로 쓴다. 길이가 맞는 것만
    받아, 길이 바이트가 영문자여도 함수 이름에 붙지 않는다. 글자열이 `)` 뒤로 이어져도 된다.
    """
    for found in _UTEST_CANDIDATE.finditer(utest):
        start = found.start()
        if start < 2:
            continue
        length = int.from_bytes(utest[start - 2:start], 'big')
        text = utest[start:start + length]
        if length >= 3 and len(text) == length and _PRINTABLE.fullmatch(text):
            head = _UTEST_FUNCTION.match(text)
            if head:
                return head.group(1).decode('ascii')
    return None


def _function_and_file(csv_path: Path, test_name: str) -> Tuple[str, str]:
    """함수는 테스트 이름 `<함수>_test<N>`에서, 안 되면 `.utest`에서. 소스 파일은 `.utest`에서."""
    try:
        utest = csv_path.with_suffix('.utest').read_bytes()
    except OSError:
        utest = b''
    named = _TEST_NAME.fullmatch(test_name)
    function = named.group(1) if named else _utest_function(utest) or test_name
    files = _UTEST_FILE.findall(utest)
    return function, files[-1].decode('ascii') if files else ''


def _read_test(csv_path: Path, key: str) -> Optional[CtTest]:
    """CT 테스트 데이터 꼴이 아니면 None. 읽기·디코딩 오류는 부르는 쪽이 받는다."""
    text, _ = decode_csv(csv_path.read_bytes())
    lines = _LINE_END.split(text)
    if len(lines) < 3 or lines[0].strip() != FIRST_LINE or not lines[1].startswith(NAME_PREFIX):
        return None
    header = split_fields(lines[2])
    if header[0].strip() or not {S_INPUT, S_EXPECT} & {c.strip() for c in header}:
        return None
    test_name = split_fields(lines[1])[0][len(NAME_PREFIX):].strip()
    cases = [split_fields(line) for line in lines[3:] if line.strip()]
    function, file = _function_and_file(csv_path, test_name)
    return CtTest(key, function, file, _variables(_symbol_columns(header), cases))


def load_tests(export_dir: Path) -> ExportRead:
    """내보낸 폴더 아래 모든 테스트 데이터 CSV를 읽는다. CT 꼴이 아닌 CSV는 `unreadable`에 모은다."""
    if not export_dir.is_dir():
        raise ExportError(E_EXPORT_OPEN)
    try:
        found = sorted((p.relative_to(export_dir).as_posix(), p)
                       for p in export_dir.rglob('*') if p.suffix.lower() == '.csv' and p.is_file())
    except OSError:
        raise ExportError(E_EXPORT_OPEN) from None
    tests: List[CtTest] = []
    unreadable: List[str] = []
    for key, path in found:
        try:
            test = _read_test(path, key)
        except (OSError, UnicodeDecodeError):
            test = None
        if test is None:
            unreadable.append(key)
        else:
            tests.append(test)
    if not tests:
        raise ExportError(E_EXPORT_EMPTY)
    return ExportRead(tests, unreadable)


def write_copy(export_dir: Path, out_dir: Path, edits: Mapping[str, Mapping[str, str]],
               reset_cases: bool) -> int:
    """지정을 바꾼 사본 CSV를 `out_dir`에 쓰고 쓴 개수를 돌려준다. 아직 없다."""
    raise NotImplementedError
