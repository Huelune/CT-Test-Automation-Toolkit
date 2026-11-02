"""todo.md 10절: CT GUI에서 내보내거나 복사한 파일(C:\\ctsample\\gui)에 TC별 분기 결과가 있는지 요약한다.

지어낸 이름(`dmy_`, `ctsample`)만 들어 있는 견본 폴더용이다. 고객 프로젝트에 쓰지 않는다.
내보낸 파일에는 작성자·PC 이름이나 경로가 들어 있을 수 있어, 화면과 `probe10.txt` 모두에서 지금
계정·PC 이름과 `C:\\ctsample` 밖의 경로를 가린다.

글자 파일(메모장에 붙인 진리표, HTML, SVG, XML 등)은 줄로 읽어 케이스 이름이 든 줄을, 없으면 앞
줄을 찍는다. 그림·PDF처럼 글자가 아닌 파일은 크기만 찍는다.

    python examples\\ct_sample\\probe_gui.py [폴더]
"""

from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('C:/ctsample/gui')
OUT_NAME = 'probe10.txt'
CASES = ('dmy_low', 'dmy_high', 'dmy_mid')  # 6절 케이스 이름
TEXT = ('.txt', '.tsv', '.csv', '.json')
MARKUP = ('.html', '.htm', '.xml', '.svg')
WIDTH = 110
SHOW = 6  # 파일마다 화면에 찍을 줄 수
SCREEN = 34  # 화면에 찍을 전체 줄 수(나머지는 probe10.txt)
PATH = re.compile(r'[A-Za-z]:\\[^\s"<>|,;]*')
SECRETS = sorted({v for v in (os.environ.get(k, '') for k in ('USERNAME', 'COMPUTERNAME', 'USERDOMAIN'))
                  if len(v) >= 2}, key=len, reverse=True)


def mask(text: str) -> str:
    text = PATH.sub(lambda m: m.group(0) if m.group(0).lower().startswith('c:\\ctsample')
                    else '<경로>', text)
    for secret in SECRETS:
        text = re.sub(re.escape(secret), '<계정>', text, flags=re.I)
    return text


def decode_text(data: bytes) -> str:
    if data[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return data.decode('utf-16')
    for encoding in ('utf-8-sig', 'cp949'):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode('latin-1')


def text_lines(path: Path) -> list:
    text = decode_text(path.read_bytes())
    if path.suffix.lower() in MARKUP:
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', text, flags=re.S | re.I)
        text = html.unescape(re.sub(r'<[^>]+>', '\n', text))
    lines = (re.sub(r'[ \t]*\t[ \t]*', ' | ', line).strip() for line in text.splitlines())
    return [re.sub(r'\s+', ' ', line) for line in lines if line]


def main() -> int:
    files = sorted(p for p in ROOT.rglob('*') if p.is_file() and p.name != OUT_NAME) \
        if ROOT.is_dir() else []
    if not files:
        print('폴더 {}이(가) 없거나 비었음: 10절의 저장 위치를 확인'.format(ROOT))
        return 1
    screen, full = ['CT GUI 내보내기 요약', '파일 {}개'.format(len(files))], []
    for path in files:
        name = mask(path.relative_to(ROOT).as_posix())
        suffix = path.suffix.lower()
        if suffix not in TEXT + MARKUP:
            screen.append('== {} ({} bytes, 글자 파일 아님: 열어서 눈으로)'.format(name, path.stat().st_size))
            continue
        lines = [mask(line) for line in text_lines(path)]
        counts = ', '.join('{} {}'.format(c, sum(line.count(c) for line in lines)) for c in CASES)
        screen.append('== {} ({}줄, {})'.format(name, len(lines), counts))
        full.append('== ' + name)
        full.extend('  ' + line for line in lines)
        hits = [line for line in lines[1:] if any(case in line for case in CASES)]
        picks = lines[:1] + hits if hits else lines  # 첫 줄은 대개 표 머리글이다
        screen.extend('    ' + line[:WIDTH] for line in picks[:SHOW])
    out = ROOT / OUT_NAME
    out.write_text('\n'.join(screen + ['', '---- 전체 ----'] + full) + '\n', encoding='utf-8')
    if len(screen) > SCREEN:
        screen = screen[:SCREEN] + ['(화면에 다 못 찍음)']
    screen.append('전체: {}'.format(out.name))
    print('\n'.join(screen))
    return 0


if __name__ == '__main__':
    sys.exit(main())
