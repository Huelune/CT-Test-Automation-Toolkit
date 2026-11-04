"""CSV로 만든 테스트에 원래 테스트에서 늘린 원소·체크한 전역 변수가 따라오는지 보는 견본 확인 (todo.md 23절).

`carry_probe.py <원래 폴더> <만든 뒤 폴더> <붙인 뒤 폴더>`. 같은 절을 두 번 돌린다.

- 첫 번째(만든 뒤 폴더가 아직 없음): 원래 폴더의 `dmy_pick` 테스트 머리글을 찍고, 툴킷 사본처럼 `dmy_sum`을
  모든 구역에서 뺀 사본 CSV를 `result\\probe\\<시각>\\copy\\`에 쓴다.
- 두 번째: 사용자가 그 사본으로 만든 테스트(만든 뒤 폴더)와 [테스트 세부 항목 복사]를 붙인 뒤(붙인 뒤 폴더)의
  `dmy_pick` 테스트마다 원래 테스트보다 빠진 기호, 더해진 기호, 방향이 바뀐 기호를 한 줄로 찍는다.

화면에는 개수, 정해 둔 문구, 견본 이름(member_probe의 가림 규칙)만 찍는다. 받은 경로는 찍지 않는다.
"""

from __future__ import annotations

import re
import sys
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from member_probe import PICK, WIDTH, _mask, _remove, _write, show_lines

from ct_toolkit import paths
from ct_toolkit.ct_export import ExportError, load_tests
from ct_toolkit.io_match import CtTest

RELEASED = 'dmy_sum'  # 툴킷이 해제한 것처럼 사본에서 뺄 기호
E_ARGS = '[ERROR] 폴더 셋을 받지 못함: todo.bat 23으로 돌리기'
E_ONE = '[ERROR] 원래 폴더의 dmy_pick 테스트가 {}개: dmy_pick 테스트를 하나만 남기고 다시 내보내기'
E_NO_RELEASED = '[ERROR] 원래 테스트에 dmy_sum이 없어 사본을 만들지 못함: 이 화면을 보내 주기'
W_NO_ELEMENT = '[WARN] 원래 테스트에 [0]이 아닌 원소가 없음: CT에서 dmy_recs에 [2]를 늘렸는지 확인'
_ELEMENT = re.compile(r'\[[1-9]\d*\]')


def pick_tests(export_dir: Path) -> Dict[str, CtTest]:
    """테스트 이름(CSV 파일 이름) -> `dmy_pick` 테스트. 읽지 못하면 ExportError."""
    return {Path(t.key).stem: t for t in load_tests(export_dir).tests if Path(t.key).stem.startswith(PICK)}


def diff_line(name: str, base: Mapping[str, str], other: Mapping[str, str]) -> List[str]:
    """`name  빠짐 N: …  더해짐 N: …  방향 바뀜 N: a(in→inout)`. 같으면 `name  원래와 같음`."""
    gone = [_mask(s) for s in base if s not in other]
    added = [_mask(s) for s in other if s not in base]
    moved = ['{}({}→{})'.format(_mask(s), base[s], other[s]) for s in base if s in other and base[s] != other[s]]
    if not (gone or added or moved):
        text = '{}  원래와 같음'.format(_mask(name))
    else:
        text = '  '.join([_mask(name)] + ['{} {}{}'.format(label, len(items), ': ' + ', '.join(items) if items else '')
                                          for label, items in (('빠짐', gone), ('더해짐', added), ('방향 바뀜', moved))])
    return textwrap.wrap(text, WIDTH, subsequent_indent='    ', break_on_hyphens=False)


def _directions(test: CtTest) -> Dict[str, str]:
    return {s: v.direction for s, v in test.symbols.items()}


def main(argv: Sequence[str]) -> int:
    if len(argv) != 3:
        print(E_ARGS)
        return 1
    first, made, pasted = (Path(a) for a in argv)
    try:
        originals = pick_tests(first)
    except ExportError as exc:
        print('[ERROR] 원래 폴더: ' + str(exc))
        return 1
    if len(originals) != 1:
        print(E_ONE.format(len(originals)))
        return 1
    (name, original), = originals.items()
    base = _directions(original)
    print('원래 테스트 머리글')
    for line in show_lines(first, PICK):
        print(line)
    if not any(_ELEMENT.search(s) for s in base):
        print(W_NO_ELEMENT)

    if not made.is_dir():  # 첫 번째: 사본을 만든다
        if RELEASED not in base:
            print(E_NO_RELEASED)
            return 1
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        _write(first / original.key, paths.result_dir() / 'probe' / stamp, 'copy',
               lambda rows: _remove(rows, RELEASED))
        print('사본 CSV: result\\probe\\{}\\copy\\ ({}를 모든 구역에서 뺌)'.format(stamp, RELEASED))
        return 0

    for label, folder in (('CSV로 만든 뒤', made), ('세부 항목 붙인 뒤', pasted)):
        if not folder.is_dir():
            print('{}: 폴더 없음'.format(label))
            continue
        try:
            tests = pick_tests(folder)
        except ExportError as exc:
            print('{}: [ERROR] {}'.format(label, exc))
            continue
        print('{}: dmy_pick 테스트 {}'.format(label, len(tests)))
        for test_name, test in sorted(tests.items()):
            for line in diff_line(test_name, base, _directions(test)):
                print('  ' + line)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
