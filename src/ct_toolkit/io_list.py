"""입력·출력 지정 목록(XLSX) 읽기.

목록은 사용자가 Codebeamer에서 내보낸다. 첫 시트의 첫 줄이 머리글이고, 칸은 머리글 이름으로
찾는다. 형식은 docs/design/io-designation.md "목록 형식".

여기서 나는 오류 문구는 화면에 그대로 찍는다. 그래서 정해 둔 문구만 쓰고 파일 경로나 예외
원문을 넣지 않는다.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Sequence

REQUIRED_HEADERS = ('함수', '변수', '구분')
OPTIONAL_HEADERS = ('파일', '타입', '범위')
DIRECTIONS = {'입력': 'in', '출력': 'out', '입출력': 'inout'}

E_NO_OPENPYXL = 'openpyxl이 없음: 서버 PC에서 pip install -r requirements.txt'
E_LIST_OPEN = '목록을 열 수 없음: 파일이 있는지, XLSX인지, 엑셀에서 열려 있지 않은지 확인'
E_LIST_HEADER = '목록 첫 줄에 머리글이 없음({}): 첫 줄을 머리글로 맞추기'

R_LIST_EMPTY = '목록 오류(필수 칸 비었음)'
R_LIST_DIRECTION = '목록 오류(구분 값)'


class ListFileError(Exception):
    """목록을 읽을 수 없다. 메시지는 위 정해 둔 문구 중 하나뿐이다."""


@dataclass(frozen=True)
class ListRow:
    row: int  # 엑셀 행 번호. 머리글이 1행
    function: str
    variable: str
    direction: str  # 'in' | 'out' | 'inout'
    file: str = ''
    type_name: str = ''
    range_text: str = ''


@dataclass(frozen=True)
class ListError:
    row: int
    function: str
    variable: str
    reason: str


@dataclass
class ListRead:
    rows: List[ListRow]
    errors: List[ListError]

    @property
    def total(self) -> int:
        return len(self.rows) + len(self.errors)

    @property
    def functions(self) -> int:
        return len({r.function for r in self.rows})


def _text(value: object) -> str:
    return '' if value is None else str(value).strip()


def parse_rows(rows: Iterable[Sequence[object]]) -> ListRead:
    """첫 항목을 머리글로 보고 나머지를 목록 줄로 읽는다. 빈 줄은 세지 않는다."""
    it = iter(rows)
    header = [_text(v) for v in next(it, ())]
    index: Dict[str, int] = {}
    for i, name in enumerate(header):
        index.setdefault(name, i)
    missing = [h for h in REQUIRED_HEADERS if h not in index]
    if missing:
        raise ListFileError(E_LIST_HEADER.format(', '.join(missing)))

    result = ListRead([], [])
    for number, values in enumerate(it, start=2):
        cells = [_text(v) for v in values]
        if not any(cells):
            continue

        def cell(name: str) -> str:
            i = index.get(name)
            return cells[i] if i is not None and i < len(cells) else ''

        function, variable, direction = cell('함수'), cell('변수'), cell('구분')
        if not (function and variable and direction):
            result.errors.append(ListError(number, function, variable, R_LIST_EMPTY))
        elif direction not in DIRECTIONS:
            result.errors.append(ListError(number, function, variable, R_LIST_DIRECTION))
        else:
            result.rows.append(ListRow(number, function, variable, DIRECTIONS[direction],
                                       cell('파일'), cell('타입'), cell('범위')))
    return result


def read_list(path: Path, importer: Callable[[str], object] = importlib.import_module) -> ListRead:
    """XLSX 목록의 첫 시트를 읽는다."""
    try:
        openpyxl = importer('openpyxl')
    except ImportError:
        raise ListFileError(E_NO_OPENPYXL) from None
    try:
        book = openpyxl.load_workbook(str(path), read_only=True, data_only=True)  # type: ignore[attr-defined]
        try:
            values = list(book.worksheets[0].iter_rows(values_only=True))
        finally:
            book.close()
    except Exception:  # 원문에는 경로가 들어 있을 수 있어 버린다
        raise ListFileError(E_LIST_OPEN) from None
    return parse_rows(values)
