"""todo.md 7절: CT 견본 보고서 폴더(C:\\ctsample\\report)에 TC별 분기 결과가 있는지 한 화면에 요약한다.

지어낸 이름(`dmy_`, `ctsample`)만 들어 있는 견본 폴더용이다. 고객 프로젝트에 쓰지 않는다.
보고서에는 작성자·PC 이름이나 경로가 들어 있을 수 있어, 화면과 `probe6.txt` 모두에서 지금 계정·PC
이름과 `C:\\ctsample` 밖의 경로를 가린다.

6절 첫 실행에서 `.xlsx`(요약, 케이스 이름 없음)와 `.html` 말고 `.xls` 3개가 나왔다. `.xls`는 앞
바이트로 형식을 가른다. 글자 파일(HTML·XML)이면 줄로 읽고, 옛 엑셀(OLE2)이면 xlrd가 있으면 그것으로,
없으면 파일 안의 글자열(ASCII, UTF-16)을 순서대로 뽑아 본다.

    python examples\\ct_sample\\probe_report.py [폴더]
"""

from __future__ import annotations

import collections
import html
import os
import re
import sys
import warnings
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('C:/ctsample/report')
CASES = ('dmy_low', 'dmy_high', 'dmy_mid')  # todo.md 6절에서 만든 케이스 이름
BRANCH = re.compile(r'분기|branch|true|false|참|거짓', re.I)
WIDTH = 110
SHOW = 3  # 파일마다 화면에 찍을 케이스 줄 수
PATH = re.compile(r'[A-Za-z]:\\[^\s"<>|,;]*')
SECRETS = sorted({v for v in (os.environ.get(k, '') for k in ('USERNAME', 'COMPUTERNAME', 'USERDOMAIN'))
                  if len(v) >= 2}, key=len, reverse=True)
OLE2 = b'\xd0\xcf\x11\xe0'
HANGUL = re.compile(r'[\uac00-\ud7a3]')


def mask(text: str) -> str:
    text = PATH.sub(lambda m: m.group(0) if m.group(0).lower().startswith('c:\\ctsample')
                    else '<경로>', text)
    for secret in SECRETS:
        text = re.sub(re.escape(secret), '<계정>', text, flags=re.I)
    return text


def cell_text(value: object) -> str:
    return '' if value is None else str(value).strip()


def joined(cells) -> str:
    cells = [cell_text(v) for v in cells]
    while cells and not cells[-1]:
        cells.pop()
    return ' | '.join(cells)


def xlsx_lines(path: Path) -> list:
    import openpyxl
    book = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    try:
        out = []
        for sheet in book.worksheets:
            sheet.reset_dimensions()
            for number, row in enumerate(sheet.iter_rows(values_only=True), 1):
                line = joined(row)
                if line:
                    out.append('{}!{}: {}'.format(sheet.title, number, line))
        return out
    finally:
        book.close()


def html_lines(text: str) -> list:
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', text, flags=re.S | re.I)
    text = html.unescape(re.sub(r'<[^>]+>', '\n', text))
    return [re.sub(r'\s+', ' ', line).strip() for line in text.splitlines() if line.strip()]


def decode_text(data: bytes) -> str:
    if data[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return data.decode('utf-16')
    for encoding in ('utf-8-sig', 'cp949'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode('latin-1')


def ole_strings(data: bytes) -> list:
    """옛 엑셀 안의 글자열을 파일 순서대로. 8비트 ASCII와 UTF-16(한글 포함)을 함께 본다."""
    found = [(m.start(), m.group().decode('ascii')) for m in re.finditer(rb'[\x20-\x7e]{3,}', data)]
    for parity in (0, 1):
        body = data[parity:]
        text = body[:len(body) // 2 * 2].decode('utf-16le', 'replace')
        for m in re.finditer(r'[\u0020-\u007e\uac00-\ud7a3]{2,}', text):
            s = m.group()
            if HANGUL.search(s) or len(s) >= 3:
                found.append((parity + 2 * m.start(), s))
    return [s for _, s in sorted(found)]


def xls_lines(path: Path, data: bytes) -> tuple:
    if not data.startswith(OLE2):
        return 'xls 글자 파일', html_lines(decode_text(data))
    try:
        import xlrd
    except ImportError:
        return 'xls OLE2, 글자열', ole_strings(data)
    book = xlrd.open_workbook(str(path))
    return 'xls OLE2, xlrd', ['{}!{}: {}'.format(s.name, r + 1, joined(s.row_values(r)))
                              for s in book.sheets() for r in range(s.nrows) if joined(s.row_values(r))]


def read_lines(path: Path) -> tuple:
    suffix = path.suffix.lower()
    if suffix == '.xlsx':
        return 'xlsx', xlsx_lines(path)
    data = path.read_bytes()
    if suffix == '.xls':
        return xls_lines(path, data)
    if suffix in ('.html', '.htm', '.xml', '.txt', '.csv'):
        return suffix[1:], html_lines(decode_text(data))
    return None, []


def main() -> int:
    warnings.simplefilter('ignore')  # openpyxl 경고 원문에는 설치 경로(계정)가 들어 있다
    screen, full = ['CT 견본 보고서 요약'], []
    files = sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name != 'probe6.txt') \
        if ROOT.is_dir() else []
    if not files:
        print('폴더 {}이(가) 없거나 비었음: 6절의 보고서 저장 위치를 확인'.format(ROOT))
        return 1
    kinds = collections.Counter(p.suffix.lower() or '(없음)' for p in files)
    screen.append('파일 {}개: {}'.format(len(files), ', '.join('{} {}'.format(k, n)
                                                         for k, n in sorted(kinds.items()))))
    for path in files:
        name = mask(path.relative_to(ROOT).as_posix())
        try:
            kind, lines = read_lines(path)
        except ImportError:
            screen.append('== {}: openpyxl이 없어 못 읽음'.format(name))
            continue
        except Exception as exc:
            screen.append('== {}: 못 읽음({})'.format(name, type(exc).__name__))
            continue
        if kind is None:
            screen.append('== {}: 읽지 않는 형식'.format(name))
            continue
        lines = [mask(line) for line in lines]
        full.append('== {} ({})'.format(name, kind))
        full.extend('  ' + line for line in lines)
        hits = [i for i, line in enumerate(lines) if any(case in line for case in CASES)]
        counts = ', '.join('{} {}'.format(c, sum(line.count(c) for line in lines)) for c in CASES)
        screen.append('== {} ({}, {}줄, {}, 분기 낱말 {}줄)'.format(
            name, kind, len(lines), counts, sum(1 for line in lines if BRANCH.search(line))))
        for i in hits[:SHOW]:
            screen.append('    ' + ' / '.join(lines[i:i + 3])[:WIDTH])
    out = ROOT / 'probe6.txt'
    out.write_text('\n'.join(screen + ['', '---- 전체 ----'] + full) + '\n', encoding='utf-8')
    screen.append('전체: {}'.format(out.name))
    print('\n'.join(screen))
    return 0


if __name__ == '__main__':
    sys.exit(main())
