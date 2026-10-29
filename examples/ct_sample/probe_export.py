"""todo.md 4절: CT 견본 내보내기 폴더(C:\\ctsample\\out)를 한 화면에 요약한다.

지어낸 이름(`dmy_`, `ctsample`)만 들어 있는 견본 폴더용이다. 고객 프로젝트에 쓰지 않는다.
서버 PC는 PowerShell이 막혀 있어 툴킷의 Python으로 바이트를 본다. 화면에는 요약만 찍고 전체는
`probe5.txt`에 쓴다.

    python examples\\ct_sample\\probe_export.py [폴더]
"""

from __future__ import annotations

import difflib
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('C:/ctsample/out')
SHOW = 8  # 파일마다 화면에 찍을 줄 수
WIDTH = 110


def files(folder: Path) -> dict:
    if not folder.is_dir():
        return {}
    return {p.relative_to(folder).as_posix(): p for p in sorted(folder.rglob('*')) if p.is_file()}


def decode(data: bytes) -> tuple:
    for encoding in ('utf-8-sig', 'cp949'):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            pass
    return data.decode('latin-1'), 'latin-1'


def text_lines(path: Path) -> list:
    return decode(path.read_bytes())[0].splitlines()


def compare(a: str, b: str, title: str, screen: list, full: list) -> None:
    fa, fb = files(ROOT / a), files(ROOT / b)
    screen.append('== {} -> {} ({})'.format(a, b, title))
    full.append(screen[-1])
    if not fa or not fb:
        screen.append('  폴더 {}이(가) 없거나 비었음'.format(a if not fa else b))
        return
    for name in sorted(set(fa) | set(fb)):
        if name not in fa or name not in fb:
            screen.append('  {}: {}에만 있음'.format(name, a if name in fa else b))
            continue
        diff = [d for d in difflib.unified_diff(text_lines(fa[name]), text_lines(fb[name]),
                                                lineterm='', n=0)
                if not d.startswith(('---', '+++', '@@'))]
        if not diff:
            screen.append('  {}: 같음'.format(name))
            continue
        screen.append('  {}: 다른 줄 {}'.format(name, len(diff)))
        screen.extend('    ' + d[:WIDTH] for d in diff[:SHOW])
        full.append('  ' + name)
        full.extend('    ' + d for d in diff)


def describe(folder: str, screen: list, full: list) -> None:
    found = files(ROOT / folder)
    screen.append('== {} 파일 원문 요약'.format(folder))
    full.append(screen[-1])
    if not found:
        screen.append('  폴더 {}이(가) 없거나 비었음'.format(folder))
        return
    for name, path in found.items():
        data = path.read_bytes()
        text, encoding = decode(data)
        lines = text.splitlines()
        full.append('  ' + name)
        full.extend('    {}: {}'.format(i, line) for i, line in enumerate(lines, 1))
        if name.lower().endswith('testinfo.export'):
            continue  # 4절 첫 실행 캡처에서 봤다
        screen.append('  {}: {} bytes, BOM {}, CRLF {}, LF {}, {}로 읽힘, {}줄'.format(
            name, len(data), '있음' if data.startswith(b'\xef\xbb\xbf') else '없음',
            data.count(b'\r\n'), data.count(b'\n'), encoding, len(lines)))
        picks = list(enumerate(lines, 1))
        if name.lower().endswith('.csv'):
            picks = picks[:1] + picks[3:6]  # 1줄과 케이스 줄. 2·3줄은 2절에서 봤다
        screen.extend('    {}: {}'.format(i, line[:WIDTH]) for i, line in picks[:5])


def main() -> int:
    screen, full = ['CT 견본 요약'], []
    screen.append('파일 수: ' + ', '.join('{} {}'.format(d, len(files(ROOT / d))) for d in '1234'))
    compare('1', '2', '지정 전후', screen, full)
    compare('1', '4', '다시 가져오기 전후', screen, full)
    describe('3', screen, full)
    out = ROOT / 'probe5.txt'
    out.write_text('\n'.join(screen + ['', '---- 전체 ----'] + full) + '\n', encoding='utf-8')
    screen.append('전체: {}'.format(out.name))
    print('\n'.join(screen))
    return 0


if __name__ == '__main__':
    sys.exit(main())
