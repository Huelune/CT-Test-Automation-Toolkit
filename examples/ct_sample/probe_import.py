"""todo.md 8절: CSV 머리글만 고친 내보내기 폴더를 CT로 가져오면 지정이 따라오는지 본다.

지어낸 이름(`dmy_`, `ctsample`)만 들어 있는 견본 폴더용이다. 고객 프로젝트에 쓰지 않는다.

처음 돌리면 `C:\\ctsample\\out\\1`(CT가 처음 잡은 지정)을 `out\\5`로 복사하고, 그 안의
`dmy_calc_test0.csv`에서 `dmy_spare`를 입력 구역에서 뺀다(케이스 줄의 칸도 함께). `.utest`와
`testInfo.export`는 그대로 둔다. 매번 폴더 1~8의 CSV마다 입력·기대 기호를 폴더 1의
`dmy_calc_test0`과 비교해 한 줄로 찍는다.

    python examples\\ct_sample\\probe_import.py [폴더]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('C:/ctsample/out')
BASE = 'dmy_calc_test0'
DROP = 'dmy_spare'  # 폴더 5에서 입력에서 뺄 기호
BOM = b'\xef\xbb\xbf'


def decode(data: bytes) -> tuple:
    if data.startswith(BOM):
        return data[3:].decode('utf-8'), 'utf-8-sig'
    try:
        return data.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError:
        return data.decode('cp949'), 'cp949'


def split_fields(line: str) -> list:
    """따옴표 안의 쉼표는 나누지 않고, 칸 원문(따옴표 포함)을 그대로 둔다."""
    fields, cur, quoted = [], [], False
    for ch in line:
        if ch == '"':
            quoted = not quoted
        if ch == ',' and not quoted:
            fields.append(''.join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append(''.join(cur))
    return fields


def sections(header: list) -> dict:
    """머리글 칸에서 `<input>`, `<expect>` 같은 구역마다 기호 목록을 낸다."""
    found, current = {}, None
    for field in header[1:]:
        if field.startswith('<') and field.endswith('>'):
            current = field
            found[current] = []
        elif current is not None:
            found[current].append(field)
    return found


def drop_input(text: str, symbol: str) -> str:
    """셋째 줄(머리글)의 `<input>` 구역에서 symbol 칸을 머리글과 케이스 줄 모두에서 뺀다."""
    lines = text.splitlines(keepends=True)
    header = split_fields(lines[2].rstrip('\r\n'))
    start = header.index('<input>')
    stop = next((i for i in range(start + 1, len(header)) if header[i].startswith('<')), len(header))
    column = header.index(symbol, start + 1, stop)
    for n in range(2, len(lines)):
        body = lines[n].rstrip('\r\n')
        fields = split_fields(body)
        if len(fields) > column:
            del fields[column]
        lines[n] = ','.join(fields) + lines[n][len(body):]
    return ''.join(lines)


def csv_files(folder: Path) -> dict:
    return {p.stem: p for p in sorted(folder.rglob('*.csv'))} if folder.is_dir() else {}


def read_sections(path: Path) -> dict:
    lines = decode(path.read_bytes())[0].splitlines()
    return sections(split_fields(lines[2])) if len(lines) > 2 else {}


def prepare(screen: list) -> None:
    src, dst = ROOT / '1', ROOT / '5'
    if dst.exists():
        return
    base = csv_files(src).get(BASE)
    if base is None:
        screen.append('폴더 1에 {}.csv가 없음: 4절의 out\\1을 지우지 않았는지 확인'.format(BASE))
        return
    if DROP not in read_sections(base).get('<input>', []):
        screen.append('폴더 1의 입력에 {}가 없음: 5를 만들지 않음'.format(DROP))
        return
    shutil.copytree(str(src), str(dst))
    target = csv_files(dst)[BASE]
    text, encoding = decode(target.read_bytes())
    data = drop_input(text, DROP).encode('utf-8' if encoding == 'utf-8-sig' else encoding)
    target.write_bytes((BOM if encoding == 'utf-8-sig' else b'') + data)
    screen.append('out\\5를 만들었음: {}.csv 입력에서 {}를 뺐다. 이제 CT 단계로'.format(BASE, DROP))


def change(base: list, other: list) -> str:
    gone = ['-' + s for s in base if s not in other]
    added = ['+' + s for s in other if s not in base]
    return '{}({})'.format(len(other), ' '.join(gone + added) if gone or added else '같음')


def main() -> int:
    screen = ['CT 견본 가져오기 실험']
    if not ROOT.is_dir():
        print('폴더 {}이(가) 없음: 4절의 내보내기 경로를 확인'.format(ROOT))
        return 1
    prepare(screen)
    base_csv = csv_files(ROOT / '1').get(BASE)
    if base_csv is None:
        screen.append('비교 기준(폴더 1의 {}.csv)이 없음'.format(BASE))
        print('\n'.join(screen))
        return 1
    base = read_sections(base_csv)
    screen.append('폴더 테스트           입력(폴더 1 {}와 비교)          기대'.format(BASE))
    for folder in '12345678':
        for name, path in csv_files(ROOT / folder).items():
            got = read_sections(path)
            screen.append('{:<4} {:<16} 입력 {:<30} 기대 {}'.format(
                folder, name, change(base.get('<input>', []), got.get('<input>', [])),
                change(base.get('<expect>', []), got.get('<expect>', []))))
    print('\n'.join(screen))
    return 0


if __name__ == '__main__':
    sys.exit(main())
