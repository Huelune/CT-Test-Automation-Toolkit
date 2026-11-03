"""todo.md 13절: 툴킷이 내보낸 폴더의 테스트 데이터 CSV를 왜 못 읽는지 모양만 찍는다.

`todo.bat` 13이 `이름표=폴더` 인수로 부른다. 폴더 자리에 `LATEST`를 주면 `result\\io`의 가장 최근
사본 폴더다. 화면에는 개수, 예/아니오, 바이트 수, CT 형식의 구역 표시(`<input>` 등), 글자를 가린
모양(영문 a, 숫자 9, 그 밖의 글자 가)만 찍는다. 파일·폴더·테스트·변수 이름과 칸 값은 찍지 않는다.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ct_toolkit import ct_export as ce  # noqa: E402

MAX_FILES = 3  # 폴더마다 자세히 찍을 CSV 수


def yn(flag: bool) -> str:
    return '예' if flag else '아니오'


def shape(text: str, limit: int = 60) -> str:
    """같은 종류 글자가 이어지면 한 글자로 줄이고 글자는 가린다. 기호는 그대로 둔다."""
    out: List[str] = []
    for ch in text[:limit]:
        if ch.isascii() and ch.isalpha():
            kind = 'a'
        elif ch.isdigit():
            kind = '9'
        elif ch.isalnum():
            kind = '가'
        else:
            kind = ch if ch.isprintable() else '?'
        if not (out and out[-1] == kind and kind in 'a9가'):
            out.append(kind)
    return ''.join(out) + ('…' if len(text) > limit else '')


def verdict(lines: List[str], header: List[str]) -> str:
    """`ct_export._read_test`가 None을 내는 까닭을 같은 순서로 본다."""
    cells = {c.strip() for c in header}
    if any(line.count('"') % 2 for line in lines):
        return '따옴표 홀수 줄(따옴표 안 줄바꿈)'
    if len(lines) < 3:
        return '줄이 3개보다 적음'
    if lines[0].strip() != ce.FIRST_LINE:
        return '첫 줄이 CT 첫 줄과 다름'
    if not lines[1].startswith(ce.NAME_PREFIX):
        return "둘째 줄이 'test name:'으로 시작하지 않음"
    if header[0].strip():
        return '머리글 첫 칸이 빈칸이 아님'
    if not {ce.S_INPUT, ce.S_EXPECT} & cells:
        return '머리글에 <input>·<expect>가 없음'
    if ce._repeats_section(header):
        return '구역 표시가 되풀이됨'
    return ''


def describe(number: int, path: Path) -> List[str]:
    data = path.read_bytes()
    bom = ('utf-8' if data.startswith(b'\xef\xbb\xbf')
           else 'utf-16' if data[:2] in (b'\xff\xfe', b'\xfe\xff') else '없음')
    crlf = data.count(b'\r\n')
    head = '#{} 크기 {}B, BOM {}, NUL 바이트 {}, 줄 끝 CRLF {}·LF만 {}'.format(
        number, len(data), bom, yn(b'\x00' in data), crlf, data.count(b'\n') - crlf)
    try:
        text, encoding = ce.decode_csv(data)
    except UnicodeDecodeError:
        return [head, '    판정: 디코딩 실패(utf-8·cp949 둘 다 안 됨)']
    lines = ce._LINE_END.split(text)
    header = ce.split_fields(lines[2]) if len(lines) > 2 else ['']
    first = lines[0]
    second = lines[1] if len(lines) > 1 else ''
    markers = ', '.join('{} {}'.format(s, sum(1 for c in header if c.strip() == s)) for s in ce.SECTIONS)
    unknown = sum(1 for c in header if ce._MARKER.fullmatch(c.strip()) and c.strip() not in ce.SECTIONS)
    cases = [ce.split_fields(line) for line in lines[3:] if line.strip()]
    widths = sorted({len(c) for c in cases})
    odd = [i + 1 for i, line in enumerate(lines) if line.count('"') % 2]
    out = [head + ', 인코딩 {}, 줄 {}'.format(encoding, len(lines)),
           '    1줄 CT 첫 줄과 같음 {}'.format(yn(first.strip() == ce.FIRST_LINE))
           + ('' if first.strip() == ce.FIRST_LINE else ', 모양 ' + shape(first)),
           "    2줄 'test name:' 시작 {}, 칸 {}, 따옴표 {}, 모양 {}".format(
               yn(second.startswith(ce.NAME_PREFIX)), len(ce.split_fields(second)), second.count('"'),
               shape(second)),
           '    3줄 칸 {}, 첫 칸 빈칸 {}, {}, 모르는 구역 {}'.format(
               len(header), yn(not header[0].strip()), markers, unknown),
           '    케이스 줄 {}, 칸 수 {}'.format(len(cases), ','.join(map(str, widths)) or '-')]
    if odd:
        out.append('    따옴표 홀수 줄 {}: {} / 첫 줄 모양 {}'.format(
            len(odd), ','.join(map(str, odd[:10])), shape(lines[odd[0] - 1])))
    reason = verdict(lines, header)
    try:
        read = ce._read_test(path, path.name)
    except (OSError, UnicodeDecodeError):
        read = None
    if read is not None:
        out.append('    판정: 툴킷이 읽음')
    else:
        out.append('    판정: ' + (reason or '까닭 모름(이 화면을 보내 주기)'))
    return out


def latest_copy() -> Optional[Path]:
    folders = sorted(p for p in (ROOT / 'result' / 'io').glob('*') if p.is_dir())
    return folders[-1] if folders else None


def folder(label: str, where: Optional[Path]) -> List[str]:
    if where is None or not where.is_dir():
        return ['[{}] 폴더 없음'.format(label)]
    every = [p for p in where.rglob('*') if p.is_file()]
    csvs = sorted(p for p in every if p.suffix.lower() == '.csv')
    unit = [p for p in csvs if p.parent.name.lower() == ce.UNIT_DIR]
    utests = sum(1 for p in every if p.suffix.lower() == '.utest')
    out = ['[{}] 파일 {}, UnitTests 폴더 CSV {}, 다른 CSV {}, .utest {}'.format(
        label, len(every), len(unit), len(csvs) - len(unit), utests)]
    for number, path in enumerate(unit[:MAX_FILES], 1):
        try:
            out.extend(describe(number, path))
        except OSError:
            out.append('#{} 파일을 열 수 없음'.format(number))
    if len(unit) > MAX_FILES:
        out.append('    (나머지 CSV {}개는 생략)'.format(len(unit) - MAX_FILES))
    return out


def main(argv: List[str]) -> int:
    print('CSV 모양 보기')
    for arg in argv:
        label, _, place = arg.partition('=')
        where = latest_copy() if place == 'LATEST' else Path(place)
        for line in folder(label, where):
            print(line)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
