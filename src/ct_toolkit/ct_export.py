"""CT [테스트 내보내기] 폴더 읽기와 지정을 바꾼 사본 쓰기.

CT 2025는 입력·출력 지정을 테스트 데이터 CSV의 머리글 줄에 적는다(docs/design/io-designation.md
"견본 결과"). 폴더 안의 CSV를 `CtTest`로 읽는다. 함수 이름은 CSV 둘째 줄의 테스트 이름에서,
안 되면 같은 이름 `.utest`에서 얻고, `.utest`는 읽기만 한다. 사본은 CSV 머리글과 케이스 칸만
고쳐 원래 인코딩·줄 끝으로 쓴다(`rewrite_csv`, `write_copy`).
화면에 나갈 수 있는 `ExportError` 문구는 정해 둔 상수뿐이다(경로·예외 원문을 넣지 않는다).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Collection, Dict, List, Mapping, Optional, Set, Tuple

from .io_match import CtTest, CtVar

E_EXPORT_OPEN = '내보낸 폴더를 읽을 수 없음: --export에 [테스트 내보내기]로 고른 폴더를 주었는지 확인'
E_EXPORT_EMPTY = ('내보낸 폴더에 테스트 데이터 CSV가 없음: '
                  '[테스트 내보내기]에서 유닛 테스트의 테스트 데이터를 체크했는지 확인')

FIRST_LINE = 'CT(Controller Tester) Test Data'
NAME_PREFIX = 'test name:'
S_INPUT, S_EXPECT = '<input>', '<expect>'
SECTIONS = (S_INPUT, S_EXPECT, '<output>', '<toutput>')
RETURN_SYMBOL = 'returnVar'

_DIRECTION_SECTIONS = {'in': SECTIONS[:1], 'out': SECTIONS[1:], 'inout': SECTIONS, '': ()}

_LINE_END = re.compile(r'\r?\n')
_ROW = re.compile(r'[^\n]*\n|[^\n]+')  # 줄 끝까지 한 줄씩. `\r` 홀로는 줄 끝이 아니다
_MARKER = re.compile(r'<\w+>')
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


def _blocks(header: List[str]) -> List[Tuple[int, List[int]]]:
    """구역마다 (구역 표시 칸 번호, 그 뒤 다음 구역 표시 앞까지의 칸 번호들).

    `<...>` 꼴이면 모르는 구역(`<stub>` 등)도 구역 표시다. 구역 표시도 칸 하나를 차지한다.
    """
    blocks: List[Tuple[int, List[int]]] = []
    for i, cell in enumerate(header):
        if _MARKER.fullmatch(cell.strip()):
            blocks.append((i, []))
        elif blocks:
            blocks[-1][1].append(i)
    return blocks


def _symbol_columns(header: List[str]) -> Dict[str, List[Tuple[int, str]]]:
    """구역 표시 -> [(칸 번호, 기호)]. 빈 칸은 기호가 아니다."""
    columns: Dict[str, List[Tuple[int, str]]] = {}
    for marker, cells in _blocks(header):
        found = columns.setdefault(header[marker].strip(), [])
        found.extend((i, header[i].strip()) for i in cells if header[i].strip())
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


def _split_end(row: str) -> Tuple[str, str]:
    """(줄 내용, 줄 끝). 마지막 줄은 줄 끝이 없을 수 있다."""
    for end in ('\r\n', '\n'):
        if row.endswith(end):
            return row[:-len(end)], end
    return row, ''


def _new_header(header: List[str],
                directions: Mapping[str, str]) -> Tuple[List[str], List[Optional[int]]]:
    """고친 머리글과, 새 칸마다 케이스 값을 가져올 원래 칸 번호(없던 칸은 None).

    네 구역의 기호는 변수 이름이 `directions`에 있으면 새 지정대로, 없으면 원래 든 구역 그대로
    넣는다. 구역 안 순서는 머리글에 처음 나온 순서다. 모르는 구역은 칸마다 그대로 둔다. 같은
    구역 표시가 여러 번 나오면 첫 구역으로 합친다.
    """
    blocks = _blocks(header)
    first: Dict[str, int] = {}  # 기호 -> 네 구역 중 처음 나온 칸
    column: Dict[Tuple[str, str], int] = {}  # (구역, 기호) -> 그 구역의 원래 칸
    held: Dict[str, Set[str]] = {}  # 기호 -> 원래 든 구역
    for marker, cells in blocks:
        section = header[marker].strip()
        if section not in SECTIONS:
            continue
        for i in cells:
            symbol = header[i].strip()
            if symbol:
                first.setdefault(symbol, i)
                column.setdefault((section, symbol), i)
                held.setdefault(symbol, set()).add(section)
    sections_of: Dict[str, Collection[str]] = {}
    for symbol in first:
        variable = symbol_variable(symbol)[0]
        if variable in directions:
            sections_of[symbol] = _DIRECTION_SECTIONS[directions[variable]]
        else:
            sections_of[symbol] = held[symbol]
    ordered = sorted(first, key=first.__getitem__)
    members = {section: [s for s in ordered if section in sections_of[s]] for section in SECTIONS}

    # (구역 이름, 구역 표시 칸 또는 None, 모르는 구역이면 그 뒤 칸들)
    plan: List[Tuple[str, Optional[int], Optional[List[int]]]] = []
    for marker, cells in blocks:
        section = header[marker].strip()
        if section not in SECTIONS:
            plan.append((section, marker, cells))
        elif not any(item[0] == section for item in plan):
            plan.append((section, marker, None))
    for k, section in enumerate(SECTIONS):  # 없는 구역 표시는 순서에 맞는 자리에 넣는다
        if members[section] and not any(item[0] == section for item in plan):
            known = [(i, SECTIONS.index(item[0])) for i, item in enumerate(plan)
                     if item[0] in SECTIONS]
            before = [i for i, rank in known if rank < k]
            after = [i for i, rank in known if rank > k]
            at = max(before) + 1 if before else (min(after) if after else len(plan))
            plan.insert(at, (section, None, None))

    top = blocks[0][0]  # 첫 구역 표시 칸. 케이스 이름이 이 칸 아래에 있다
    new = header[:top]
    source: List[Optional[int]] = list(range(top))
    for section, marker, cells in plan:
        new.append(header[marker] if marker is not None else section)
        source.append(marker)
        if cells is not None:
            new.extend(header[i] for i in cells)
            source.extend(cells)
        else:
            for symbol in members[section]:
                new.append(header[first[symbol]])
                source.append(column.get((section, symbol)))
    if source[top] != top:  # 앞에 새 구역 표시가 들어갔다. 케이스 이름도 새 첫 표시 아래로 옮긴다
        source = [None if s == top else s for s in source]
        source[top] = top
    return new, source


def rewrite_csv(text: str, directions: Mapping[str, str], reset_cases: bool) -> str:
    """CT 테스트 데이터 CSV 글의 머리글과 케이스 칸을 `directions`대로 고친다.

    `directions`는 변수 이름 -> 'in'|'out'|'inout'|''(해제). 글에 없는 변수는 무시하고, 목록에 없는
    변수의 기호는 구역마다 원래 자리 그대로다. 1·2줄, 줄 끝, 마지막 줄 끝의 유무도 그대로다.
    `reset_cases`면 케이스를 지우고 번호 `1`, 이름 `""`, 나머지 빈칸인 한 줄만 둔다.
    바꿀 것이 없으면 `text`를 그대로 돌려준다.
    """
    rows = [_split_end(row) for row in _ROW.findall(text)]
    if len(rows) < 3:
        return text
    header = split_fields(rows[2][0])
    blocks = _blocks(header)
    if not blocks:
        return text
    present = {symbol_variable(header[i].strip())[0]
               for marker, cells in blocks if header[marker].strip() in SECTIONS
               for i in cells if header[i].strip()}
    if not reset_cases and not any(name in directions for name in present):
        return text
    new, source = _new_header(header, directions)
    if not reset_cases and new == header:
        return text

    eol = rows[0][1]
    last_end = rows[-1][1]
    top = blocks[0][0]  # 첫 구역 표시 칸. 케이스 이름 칸이다
    out = [rows[0], rows[1]]
    if reset_cases:
        reset = [''] * len(new)
        reset[0] = '1'
        if top > 0:
            reset[top] = '""'
        out.append((','.join(new), rows[2][1] or eol))
        out.append((','.join(reset), eol if last_end else ''))
    else:
        out.append((','.join(new), rows[2][1]))
        for body, end in rows[3:]:
            if body.strip():
                fields = split_fields(body)
                body = ','.join(fields[s] if s is not None and s < len(fields) else ''
                                for s in source)
            out.append((body, end))
    return ''.join(body + end for body, end in out)


def write_copy(export_dir: Path, out_dir: Path, edits: Mapping[str, Mapping[str, str]],
               reset_cases: bool) -> int:
    """`edits`에 든 CSV마다 지정을 고친 사본을 `out_dir / 키`에 원래 인코딩으로 쓴다. 쓴 개수를 돌려준다.

    키는 `export_dir` 기준 상대 경로(posix)다. `edits`에 없는 CSV와 `.utest`, `testInfo.export`는
    쓰지 않는다. 읽기·쓰기 오류(`OSError`)는 부르는 쪽이 받는다.
    """
    for key, directions in edits.items():
        text, encoding = decode_csv((export_dir / key).read_bytes())
        target = out_dir / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(rewrite_csv(text, directions, reset_cases).encode(encoding))
    return len(edits)
