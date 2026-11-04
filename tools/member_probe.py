"""원소·멤버 지정 설계의 서버 PC 견본 확인 도구 (todo.md 22절, case_check가 부른다).

CT가 구조체 배열 기호를 내보낸 CSV 머리글에 어떤 꼴로 적는지 보고(`show_lines`), CT가 기호 칸을 더하거나
뺀 CSV를 받아 주는지 알아볼 변형 CSV를 만든다(`make_variants`). 설계: docs/design/io-designation-members.md
"서버 PC 견본으로 먼저 볼 것".

화면에는 개수, 정해 둔 문구, 출력 폴더 이름만 찍는다. 견본 이름(`dmy_`로 시작하거나 `returnVar`)만
그대로 찍고 다른 이름은 `*`로 가린다. 명령줄로 받은 경로와 예외 원문은 찍지 않는다.
"""

from __future__ import annotations

import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from ct_toolkit import paths
from ct_toolkit.ct_export import (FIRST_LINE, NAME_PREFIX, RETURN_SYMBOL, SECTIONS, UNIT_DIR, decode_csv,
                                  split_fields)

E_OPEN = '[ERROR] 내보낸 폴더를 읽을 수 없음: todo.md 절의 경로로 내보냈는지 확인'
WIDTH = 118  # 120열 화면에 들어가도록
_ROW = re.compile(r'[^\n]*\n|[^\n]+')
_IDENT = re.compile(r'[A-Za-z_]\w*', re.ASCII)

# 변형 원본으로 삼을 테스트 CSV 이름의 앞부분. 칸을 더하고 빼는 내용은 make_variants에 있다.
CALC, PICK = 'dmy_calc_test', 'dmy_pick_test'


def _mask(name: str) -> str:
    """견본 이름만 그대로 두고 나머지는 `*`. 기호 안의 이름이 모두 견본이어야 그대로 둔다."""
    ids = _IDENT.findall(name)
    ok = ids and name.isascii() and all(i.startswith('dmy_') or i == RETURN_SYMBOL for i in ids)
    return name if ok else '*'


def _csvs(export_dir: Path) -> List[Path]:
    return sorted((p for p in export_dir.rglob('*') if p.suffix.lower() == '.csv'
                   and p.parent.name.lower() == UNIT_DIR and p.is_file()),
                  key=lambda p: p.relative_to(export_dir).as_posix())


def _read(path: Path) -> Optional[Tuple[str, str]]:
    """(글, 인코딩). 읽지 못하면 None."""
    try:
        return decode_csv(path.read_bytes())
    except (OSError, UnicodeDecodeError):
        return None


def show_lines(export_dir: Path, prefix: str = '') -> List[str]:
    """UnitTests CSV마다 `<테스트 이름>  <input> a, b  <expect> c` 한 줄. 118열을 넘으면 이어 쓴다.
    `prefix`를 주면 파일 이름이 그것으로 시작하는 CSV만 본다."""
    out: List[str] = []
    unreadable = 0
    for path in _csvs(export_dir):
        if not path.stem.startswith(prefix):
            continue
        read = _read(path)
        lines = read[0].splitlines() if read else []
        if len(lines) < 3 or lines[0].strip() != FIRST_LINE or not lines[1].startswith(NAME_PREFIX):
            unreadable += 1
            continue
        found: Dict[str, List[str]] = {}  # 구역 -> 기호들
        section: List[str] = []
        for cell in split_fields(lines[2])[1:]:
            cell = cell.strip()
            if _marker(cell):  # 모르는 구역(`<stub>` 등)의 기호는 버리는 목록에 모은다
                section = found.setdefault(cell, []) if cell in SECTIONS else []
            elif cell:
                section.append(_mask(cell))
        name = split_fields(lines[1])[0][len(NAME_PREFIX):].strip()
        text = '  '.join([_mask(name)] + ['{} {}'.format(s, ', '.join(found[s]))
                                          for s in SECTIONS if found.get(s)])
        out.extend(textwrap.wrap(text, WIDTH, subsequent_indent='    ', break_on_hyphens=False))
    if unreadable:
        out.append('읽지 못한 CSV {}'.format(unreadable))
    return out


def _find_source(export_dir: Path, prefix: str) -> Optional[Path]:
    return next((p for p in _csvs(export_dir) if p.stem.startswith(prefix) and _read(p)), None)


def _marker(cell: str) -> bool:
    return re.fullmatch(r'<\w+>', cell.strip()) is not None


def _add(rows: List[List[str]], section: str, symbol: str) -> None:
    """머리글(rows[0])의 그 구역 끝에 기호 칸을 넣고 케이스 줄에도 같은 자리에 빈 칸을 넣는다."""
    header = rows[0]
    start = [c.strip() for c in header].index(section)
    end = next((i for i in range(start + 1, len(header)) if _marker(header[i])), len(header))
    for n, row in enumerate(rows):
        row.extend([''] * (end - len(row)))
        row.insert(end, symbol if n == 0 else '')


def _remove(rows: List[List[str]], symbol: str) -> None:
    """머리글에서 그 기호의 모든 칸을 지우고 케이스 줄에서도 같은 칸을 지운다."""
    cols = [i for i, c in enumerate(rows[0]) if c.strip() == symbol]
    for row in rows:
        for i in reversed(cols):
            if i < len(row):
                del row[i]


def _write(source: Path, out_dir: Path, version: str,
           edit: Callable[[List[List[str]]], None]) -> None:
    """원본을 줄 끝·인코딩 그대로 읽어 `edit`로 머리글과 케이스 줄을 고쳐 `out_dir/version/`에 쓴다."""
    text, encoding = decode_csv(source.read_bytes())
    rows = _ROW.findall(text)
    at = [n for n, row in enumerate(rows) if n >= 2 and row.strip()]  # 머리글과 케이스 줄. 빈 줄은 둔다
    table = [split_fields(rows[n].rstrip('\r\n')) for n in at]
    edit(table)
    for n, fields in zip(at, table):
        body = rows[n].rstrip('\r\n')
        rows[n] = ','.join(fields) + rows[n][len(body):]
    target = out_dir / version / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(''.join(rows).encode(encoding))


def make_variants(export_dir: Path, out_dir: Path) -> List[str]:
    """CT가 기호 칸을 더하거나 뺀 CSV를 받는지 보는 변형 v1~v4를 쓰고 화면 줄을 돌려준다."""
    calc, pick = _find_source(export_dir, CALC), _find_source(export_dir, PICK)
    result: List[str] = []

    def make(version: str, source: Optional[Path], label: str, missing: str,
             edit: Callable[[List[List[str]]], None]) -> None:
        if source is None:
            result.append('{} 만들지 못함: {}'.format(version, missing))
            return
        _write(source, out_dir, version, edit)
        result.append('{} {}'.format(version, label))

    no_calc, no_pick = 'dmy_calc 테스트가 내보낸 폴더에 없음', 'dmy_pick 테스트가 내보낸 폴더에 없음'

    def add_expect(symbol: str) -> Callable[[List[List[str]]], None]:
        def edit(rows: List[List[str]]) -> None:
            for section in ('<expect>', '<output>', '<toutput>'):
                _add(rows, section, symbol)
        return edit

    make('v1', calc, 'dmy_hist[2]를 기대값에 더함', no_calc, add_expect('dmy_hist[2]'))

    symbol = None
    if pick is not None:
        header = [c.strip() for c in split_fields(_pick_header(pick))]
        symbols = [c for c in header if c and not _marker(c)]
        symbol = next((s.replace('[0]', '[2]', 1) for s in symbols if '[0].' in s), None) or \
            next((s[:-3] + '[2]' for s in symbols if s.endswith('[0]')), None)
        if symbol is None:
            result.append('v2 만들지 못함: 머리글에 [0] 원소 기호가 없음')
    if pick is None or symbol is not None:
        make('v2', pick, '{}를 기대값에 더함'.format(_mask(symbol or '')), no_pick, add_expect(symbol or ''))

    make('v3', calc, 'dmy_limit.dmy_zz를 입력값에 더함', no_calc,
         lambda rows: _add(rows, '<input>', 'dmy_limit.dmy_zz'))
    make('v4', calc, 'dmy_limit.dmy_hi를 모든 구역에서 뺌', no_calc,
         lambda rows: _remove(rows, 'dmy_limit.dmy_hi'))
    return result


def _pick_header(path: Path) -> str:
    lines = (_read(path) or ('', ''))[0].splitlines()
    return lines[2] if len(lines) > 2 else ''


def main(argv: Sequence[str]) -> int:
    args = [a for a in argv if a != '--make']
    if len(args) != 1 or not Path(args[0]).is_dir():
        print(E_OPEN)
        return 1
    export_dir = Path(args[0])
    for line in show_lines(export_dir):
        print(line)
    if '--make' in argv:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_dir = paths.result_dir() / 'probe' / stamp
        lines = make_variants(export_dir, out_dir)
        print('변형 CSV: result\\probe\\{}\\'.format(stamp))
        for line in lines:
            print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
