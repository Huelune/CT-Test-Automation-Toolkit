"""CT [테스트 내보내기] 폴더 읽기와 지정을 바꾼 사본 쓰기.

CT 2025는 입력·출력 지정을 테스트 데이터 CSV의 머리글 줄에 적는다(docs/design/io-designation.md
"견본 결과"). 폴더 아래 `UnitTests` 폴더의 CSV를 `CtTest`로 읽는다. 함수 이름은 CSV 둘째 줄의
테스트 이름에서, 안 되면 같은 이름 `.utest`에서 얻고, `.utest`는 읽기만 한다. 사본은 CSV 머리글과
케이스 칸만 고쳐 원래 인코딩·줄 끝으로 쓴다(`rewrite_csv`, `write_copy`).
화면에 나갈 수 있는 `ExportError` 문구는 정해 둔 상수뿐이다(경로·예외 원문을 넣지 않는다).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Set, Tuple

from .io_match import CtTest, CtVar

E_EXPORT_OPEN = '내보낸 폴더를 읽을 수 없음: --export에 [테스트 내보내기]로 고른 폴더를 주었는지 확인'
E_EXPORT_EMPTY = ('내보낸 폴더에 테스트 데이터 CSV가 없음: '
                  '[테스트 내보내기]에서 유닛 테스트의 테스트 데이터를 체크했는지 확인')
E_EXPORT_NOT_CT = ('내보낸 폴더의 CSV가 CT 테스트 데이터 꼴이 아님: '
                   'CT [테스트 내보내기]로 만든 폴더를 주었는지 확인')
E_DIRECTION ='지정 값이 in, out, inout, 빈 값(해제) 중 하나가 아님'  # 값은 내부 정보일 수 있어 넣지 않는다

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
_UTEST_FILE = re.compile(rb'\\([\x21-\x5b\x5d-\x7e]+?\.(?:c|cc|cpp|cxx))(?![\w])', re.IGNORECASE)
UNIT_DIR = 'unittests'  # 유닛 테스트 CSV가 든 폴더 이름(대소문자 무시). 통합 테스트 CSV는 읽지 않는다


class ExportError(Exception):
    """내보낸 폴더를 쓸 수 없다. `str(exc)`는 화면에 찍어도 되는 정해 둔 문구다."""


@dataclass
class ExportRead:
    tests: List[CtTest]
    unreadable: List[str]  # 읽지 못한 CSV의 내보낸 폴더 기준 상대 경로(posix)
    # 테스트 이름이 `<함수>_test<N>` 꼴이 아닌 테스트의 키. CT는 이런 CSV 이름으로 테스트를 만들지
    # 않으므로(매뉴얼 2025.12 share-test) 사본에 넣지 않는다. 맞춰 보기에는 그대로 쓴다.
    renamed: List[str] = field(default_factory=list)


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


def _repeats_section(header: List[str]) -> bool:
    """알려진 구역 표시(`<input>` 등)가 두 번 이상 나온다. 모르는 구역은 되풀이되어도 된다."""
    found = [cell.strip() for cell in header if cell.strip() in SECTIONS]
    return len(found) != len(set(found))


def _symbol_columns(header: List[str]) -> Dict[str, List[Tuple[int, str]]]:
    """구역 표시 -> [(칸 번호, 기호)]. 빈 칸은 기호가 아니다."""
    columns: Dict[str, List[Tuple[int, str]]] = {}
    for marker, cells in _blocks(header):
        found = columns.setdefault(header[marker].strip(), [])
        found.extend((i, header[i].strip()) for i in cells if header[i].strip())
    return columns


def _variables(columns: Mapping[str, List[Tuple[int, str]]],
               cases: List[List[str]]) -> Dict[str, CtVar]:
    """`<input>`은 입력, `<expect>`는 출력 지정이다. 값도 그 두 구역의 칸만 본다.

    구조체·배열 변수의 기호들이 든 구역이 서로 다르면(멤버마다 지정이 다름) 방향은 'mixed'다.
    목록의 지정 하나가 모든 기호에 같게 들어가야 하므로 'mixed'는 어떤 지정과도 같지 않다.
    """
    held: Dict[str, Dict[str, Set[str]]] = {}  # 변수 -> 기호 -> 든 구역(in/out)
    cells: Dict[str, List[int]] = {}
    unsupported: Set[str] = set()
    for section, direction in ((S_INPUT, 'in'), (S_EXPECT, 'out')):
        for column, symbol in columns.get(section, []):
            name, supported = symbol_variable(symbol)
            held.setdefault(name, {}).setdefault(symbol, set()).add(direction)
            cells.setdefault(name, []).append(column)
            if not supported:
                unsupported.add(name)
    variables: Dict[str, CtVar] = {}
    for name, symbols in held.items():
        kinds = {frozenset(found) for found in symbols.values()}
        if len(kinds) > 1:
            direction = 'mixed'
        else:
            found = next(iter(kinds))
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


def _read_test(csv_path: Path, key: str) -> Optional[Tuple[CtTest, bool]]:
    """(테스트, 테스트 이름이 `<함수>_test<N>` 꼴이 아닌지). CT 테스트 데이터 꼴이 아니면 None.

    읽기·디코딩 오류는 부르는 쪽이 받는다."""
    text, _ = decode_csv(csv_path.read_bytes())
    lines = _LINE_END.split(text)
    if any(line.count('"') % 2 for line in lines):  # 따옴표 안의 줄바꿈: 줄 단위로는 칸을 맞출 수 없다
        return None
    if len(lines) < 3 or lines[0].strip() != FIRST_LINE or not lines[1].startswith(NAME_PREFIX):
        return None
    header = split_fields(lines[2])
    if header[0].strip() or not {S_INPUT, S_EXPECT} & {c.strip() for c in header}:
        return None
    if _repeats_section(header):  # 어느 칸이 어느 구역인지 정할 수 없어 고쳐 쓰지 않는다
        return None
    test_name = split_fields(lines[1])[0][len(NAME_PREFIX):].strip()
    cases = [split_fields(line) for line in lines[3:] if line.strip()]
    function, file = _function_and_file(csv_path, test_name)
    test = CtTest(key, function, file, _variables(_symbol_columns(header), cases))
    return test, _TEST_NAME.fullmatch(test_name) is None


def load_tests(export_dir: Path) -> ExportRead:
    """내보낸 폴더 아래 `UnitTests` 폴더의 테스트 데이터 CSV를 읽는다.

    다른 폴더의 CSV(통합 테스트 등)는 단위 테스트가 아니라 무시한다. CT 꼴이 아닌 CSV는 `unreadable`에
    모은다. `UnitTests`의 CSV가 없으면 `E_EXPORT_EMPTY`, 있는데 하나도 못 읽으면 `E_EXPORT_NOT_CT`다.
    """
    if not export_dir.is_dir():
        raise ExportError(E_EXPORT_OPEN)
    try:
        found = sorted((p.relative_to(export_dir).as_posix(), p) for p in export_dir.rglob('*')
                       if p.suffix.lower() == '.csv' and p.parent.name.lower() == UNIT_DIR
                       and p.is_file())
    except OSError:
        raise ExportError(E_EXPORT_OPEN) from None
    tests: List[CtTest] = []
    unreadable: List[str] = []
    renamed: List[str] = []
    for key, path in found:
        try:
            read = _read_test(path, key)
        except (OSError, UnicodeDecodeError):
            read = None
        if read is None:
            unreadable.append(key)
        else:
            tests.append(read[0])
            if read[1]:
                renamed.append(key)
    if not tests:
        raise ExportError(E_EXPORT_NOT_CT if unreadable else E_EXPORT_EMPTY)
    return ExportRead(tests, unreadable, renamed)


def _split_end(row: str) -> Tuple[str, str]:
    """(줄 내용, 줄 끝). 마지막 줄은 줄 끝이 없을 수 있다."""
    for end in ('\r\n', '\n'):
        if row.endswith(end):
            return row[:-len(end)], end
    return row, ''


def _section_cells(header: List[str], cells: List[int], members: Set[str],
                   first: Mapping[str, int]) -> List[Tuple[str, Optional[int]]]:
    """한 구역의 새 칸들 [(머리글 글, 케이스 값을 가져올 원래 칸 번호 또는 None)].

    남는 기호와 빈 칸은 원래 순서와 자리 그대로다(빈 칸은 어느 변수에도 안 속하므로 값째 남는다).
    구역의 기호가 원래 오름차순(파이썬 문자열 순서)이면 새로 드는 기호는 그 순서의 자리에, 아니면
    마지막 기호 뒤에 머리글에 처음 나온 순서로 놓는다. 바뀌는 것이 없으면 구역은 그대로다.
    """
    original = [header[i].strip() for i in cells if header[i].strip()]
    kept = [i for i in cells if not header[i].strip() or header[i].strip() in members]
    last = max((n for n, i in enumerate(kept) if header[i].strip()), default=-1)
    body, tail = kept[:last + 1], kept[last + 1:]  # 뒤쪽 빈 칸은 새 기호 뒤로 간다
    ordered = original == sorted(original)
    have = set(original)
    joiners = sorted(s for s in members if s not in have)
    if not ordered:
        joiners.sort(key=first.__getitem__)
    result: List[Tuple[str, Optional[int]]] = []
    for i in body:
        symbol = header[i].strip()
        while ordered and symbol and joiners and joiners[0] < symbol:
            result.append((header[first[joiners[0]]], None))
            del joiners[0]
        result.append((header[i], i))
    result.extend((header[first[symbol]], None) for symbol in joiners)
    result.extend((header[i], i) for i in tail)
    return result


def _new_header(header: List[str],
                directions: Mapping[str, str]) -> Tuple[List[str], List[Optional[int]]]:
    """고친 머리글과, 새 칸마다 케이스 값을 가져올 원래 칸 번호(없던 칸은 None).

    네 구역의 기호는 변수 이름이 `directions`에 있으면 새 지정대로, 없으면 원래 든 구역 그대로
    넣는다. 구역 안 순서와 빈 칸은 `_section_cells`를 따른다. 모르는 구역은 칸마다 그대로 둔다.
    알려진 구역 표시가 되풀이되는 머리글은 받지 않는다(`_repeats_section`).
    """
    blocks = _blocks(header)
    first: Dict[str, int] = {}  # 기호 -> 네 구역 중 처음 나온 칸
    held: Dict[str, Set[str]] = {}  # 기호 -> 원래 든 구역
    for marker, cells in blocks:
        section = header[marker].strip()
        if section not in SECTIONS:
            continue
        for i in cells:
            symbol = header[i].strip()
            if symbol:
                first.setdefault(symbol, i)
                held.setdefault(symbol, set()).add(section)
    members: Dict[str, Set[str]] = {section: set() for section in SECTIONS}
    for symbol in first:
        variable = symbol_variable(symbol)[0]
        now = _DIRECTION_SECTIONS[directions[variable]] if variable in directions else held[symbol]
        for section in now:
            members[section].add(symbol)

    # (구역 이름, 구역 표시 칸 또는 None, 모르는 구역이면 그 뒤 칸들)
    plan: List[Tuple[str, Optional[int], Optional[List[int]]]] = []
    for marker, cells in blocks:
        section = header[marker].strip()
        plan.append((section, marker, None if section in SECTIONS else cells))
    for k, section in enumerate(SECTIONS):  # 없는 구역 표시는 순서에 맞는 자리에 넣는다
        if members[section] and not any(item[0] == section for item in plan):
            known = [(i, SECTIONS.index(item[0])) for i, item in enumerate(plan)
                     if item[0] in SECTIONS]
            before = [i for i, rank in known if rank < k]
            after = [i for i, rank in known if rank > k]
            at = max(before) + 1 if before else (min(after) if after else len(plan))
            plan.insert(at, (section, None, None))
    cells_of = {header[marker].strip(): cells for marker, cells in blocks}

    top = blocks[0][0]  # 첫 구역 표시 칸. 케이스 이름이 이 칸 아래에 있다
    new = header[:top]
    source: List[Optional[int]] = list(range(top))
    for section, marker, cells in plan:
        new.append(header[marker] if marker is not None else section)
        source.append(marker)
        if cells is None:
            cells_here = _section_cells(header, cells_of.get(section, []), members[section], first)
        else:
            cells_here = [(header[i], i) for i in cells]
        new.extend(text for text, _ in cells_here)
        source.extend(i for _, i in cells_here)
    if source[top] != top:  # 앞에 새 구역 표시가 들어갔다. 케이스 이름도 새 첫 표시 아래로 옮긴다
        source = [None if s == top else s for s in source]
        source[top] = top
    return new, source


def rewrite_csv(text: str, directions: Mapping[str, str], reset_cases: bool) -> str:
    """CT 테스트 데이터 CSV 글의 머리글과 케이스 칸을 `directions`대로 고친다.

    `directions`는 변수 이름 -> 'in'|'out'|'inout'|''(해제)이고 값이 그 밖이면 `ValueError`
    (`E_DIRECTION`)다. 글에 없는 변수는 무시하고, 목록에 없는 변수의 기호는 구역마다 원래 자리
    그대로다. 1·2줄, 줄 끝, 마지막 줄 끝의 유무도 그대로다. 머리글보다 넓은 케이스 칸은 고친 줄
    뒤에 붙여 둔다. `reset_cases`면 케이스를 지우고 번호 `1`, 이름 `""`, 나머지 빈칸인 한 줄만 둔다.
    바꿀 것이 없거나 CT 머리글 꼴이 아니면(구역 표시가 없거나 알려진 구역 표시가 되풀이됨)
    `text`를 그대로 돌려준다.
    """
    allowed = tuple(_DIRECTION_SECTIONS)
    if any(value not in allowed for value in directions.values()):
        raise ValueError(E_DIRECTION)
    rows = [_split_end(row) for row in _ROW.findall(text)]
    if len(rows) < 3:
        return text
    header = split_fields(rows[2][0])
    blocks = _blocks(header)
    if not blocks or _repeats_section(header):
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
                row = [fields[s] if s is not None and s < len(fields) else '' for s in source]
                body = ','.join(row + fields[len(header):])
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
