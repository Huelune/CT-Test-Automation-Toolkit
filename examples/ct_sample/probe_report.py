"""todo.md 6절: CT 견본 보고서 폴더(C:\\ctsample\\report)에 TC별 분기 결과가 있는지 한 화면에 요약한다.

지어낸 이름(`dmy_`, `ctsample`)만 들어 있는 견본 폴더용이다. 고객 프로젝트에 쓰지 않는다.
보고서에는 작성자·PC 이름이나 경로가 들어 있을 수 있어, 화면과 `probe6.txt` 모두에서 지금 계정·PC
이름과 `C:\\ctsample` 밖의 경로를 가린다.

    python examples\\ct_sample\\probe_report.py [폴더]
"""

from __future__ import annotations

import collections
import html
import os
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('C:/ctsample/report')
CASES = ('dmy_low', 'dmy_high', 'dmy_mid')  # todo.md 6절에서 만드는 케이스 이름
WIDTH = 110
PATH = re.compile(r'[A-Za-z]:\\[^\s"<>|,;]*')
SECRETS = sorted({v for v in (os.environ.get(k, '') for k in ('USERNAME', 'COMPUTERNAME', 'USERDOMAIN'))
                  if len(v) >= 2}, key=len, reverse=True)


def mask(text: str) -> str:
    text = PATH.sub(lambda m: m.group(0) if m.group(0).lower().startswith('c:\\ctsample')
                    else '<경로>', text)
    for secret in SECRETS:
        text = re.sub(re.escape(secret), '<계정>', text, flags=re.I)
    return text


def cell_text(value: object) -> str:
    return '' if value is None else str(value).strip()


def xlsx_rows(path: Path):
    """(시트 이름, 행 번호, 칸 값 목록)을 차례로 낸다."""
    import openpyxl
    book = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        for sheet in book.worksheets:
            sheet.reset_dimensions()
            for number, row in enumerate(sheet.iter_rows(values_only=True), 1):
                cells = [cell_text(v) for v in row]
                while cells and not cells[-1]:
                    cells.pop()
                if cells:
                    yield sheet.title, number, cells
    finally:
        book.close()


def html_lines(path: Path) -> list:
    text = path.read_bytes().decode('utf-8', 'replace')
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', text, flags=re.S | re.I)
    text = html.unescape(re.sub(r'<[^>]+>', '\n', text))
    return [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines() if line.strip()]


def main() -> int:
    screen, full = ['CT 견본 보고서 요약'], []
    files = sorted(p for p in ROOT.rglob('*') if p.is_file()) if ROOT.is_dir() else []
    if not files:
        print('폴더 {}이(가) 없거나 비었음: 6절의 보고서 저장 위치를 확인'.format(ROOT))
        return 1
    kinds = collections.Counter(p.suffix.lower() or '(없음)' for p in files)
    screen.append('파일 {}개: {}'.format(len(files), ', '.join('{} {}'.format(k, n)
                                                         for k, n in sorted(kinds.items()))))
    for path in files:
        name = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() == '.xlsx':
            try:
                rows = list(xlsx_rows(path))
            except ImportError:
                screen.append('  {}: openpyxl이 없어 못 읽음'.format(name))
                continue
            except Exception as exc:
                screen.append('  {}: 못 읽음({})'.format(name, type(exc).__name__))
                continue
            sheets = collections.OrderedDict()
            for title, _, _ in rows:
                sheets[title] = sheets.get(title, 0) + 1
            screen.append('== {} (시트 {}: {})'.format(name, len(sheets), ', '.join(
                '{} {}줄'.format(mask(t), n) for t, n in sheets.items())))
            full.append('== ' + name)
            hits = 0
            for title, number, cells in rows:
                line = '{}!{}: {}'.format(title, number, ' | '.join(cells))
                full.append('  ' + mask(line))
                if any(case in c for c in cells for case in CASES):
                    hits += 1
                    if hits <= 6:
                        screen.append('    ' + mask(line)[:WIDTH])
            screen.append('  케이스 이름이 든 줄 {}'.format(hits))
        elif path.suffix.lower() in ('.html', '.htm'):
            lines = html_lines(path)
            full.append('== ' + name)
            full.extend('  ' + mask(line) for line in lines)
            counts = [sum(line.count(case) for line in lines) for case in CASES]
            if not any(counts):
                continue
            screen.append('== {} ({}줄, {})'.format(name, len(lines), ', '.join(
                '{} {}회'.format(c, n) for c, n in zip(CASES, counts))))
            near = [i for i, line in enumerate(lines) if any(case in line for case in CASES)]
            for i in near[:2]:
                screen.extend('    ' + mask(l)[:WIDTH] for l in lines[i:i + 3])
    out = ROOT / 'probe6.txt'
    out.write_text('\n'.join(screen + ['', '---- 전체 ----'] + full) + '\n', encoding='utf-8')
    screen.append('전체: {}'.format(out.name))
    print('\n'.join(screen))
    return 0


if __name__ == '__main__':
    sys.exit(main())
