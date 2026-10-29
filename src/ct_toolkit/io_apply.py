"""목록대로 입력·출력 지정하기 (`ct.bat io-apply`).

화면에는 개수와 정해 둔 문구, 출력 파일 이름만 찍는다. 함수·변수 이름은 결과 폴더의
`skipped.txt`에만 쓴다. 이 파일은 서버 PC에서만 본다. 설계는 docs/design/io-designation.md.

종료 코드: 0 끝까지 됨(건너뛴 줄이 있어도), 1 목록·내보낸 폴더·결과 폴더 문제로 멈춤.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import List, Optional

from . import ct_export, paths
from .io_list import ListFileError, ListRead, read_list
from .io_match import SKIP_REASONS, MatchResult, match
from .log import RunLog

E_EXPORT_NOT_READY = 'CT 내보낸 폴더 읽기는 아직 없음: todo.md 2절 견본 결과를 기다리는 중'
E_OUT_WRITE = '결과 폴더에 쓸 수 없음: result 폴더 권한과 남은 공간을 확인'
M_LIST_ONLY = '내보낸 폴더(--export)를 주지 않아 목록만 확인했습니다'

SKIPPED_NAME = 'skipped.txt'
R_UNLISTED = '목록에 없는 테스트'


def summary_lines(listed: ListRead, result: Optional[MatchResult], out_display: str,
                  reset_cases: bool) -> List[str]:
    """한 화면 요약. `result`가 없으면 목록만 확인한 것이다."""
    lines = ['목록      함수 {}, 줄 {}, 목록 오류 {}'.format(
        listed.functions, listed.total, len(listed.errors))]
    skipped = '건너뛴 줄 {}{}'.format(out_display, SKIPPED_NAME)
    if result is None:
        return lines + [skipped, M_LIST_ONLY]
    changed = len(result.applied)
    return lines + [
        '테스트    내보낸 것 {}, 바꾼 것 {}, 케이스 정리 {}, 목록에 없는 것 {}'.format(
            result.tests_total, changed, changed if reset_cases else 0, len(result.unlisted)),
        '지정      변수 {}'.format(result.assigned),
        '안 다룸   내보내지 않은 함수 {}'.format(len(result.not_exported)),
        '건너뜀    ' + ', '.join('{} {}'.format(r, result.count(r)) for r in SKIP_REASONS),
        '사본      {}'.format(out_display),
        skipped,
    ]


def write_skipped(path: Path, listed: ListRead, result: Optional[MatchResult]) -> None:
    """사람이 손으로 마저 할 줄. 탭 구분이라 엑셀로도 열린다."""
    lines = ['행\t함수\t변수\t이유']
    lines += ['{}\t{}\t{}\t{}'.format(e.row, e.function, e.variable, e.reason)
              for e in sorted(listed.errors, key=lambda e: e.row)]
    if result is not None:
        lines += ['{}\t{}\t{}\t{}'.format(s.row, s.function, s.variable, s.reason)
                  for s in result.skips]
        lines += ['-\t{}\t-\t{}'.format(name, R_UNLISTED) for name in result.unlisted]
    with open(path, 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(lines) + '\n')


def main(log: RunLog, list_path: Path, export_dir: Optional[Path] = None,
         reset_cases: bool = False, *, out_root: Optional[Path] = None,
         now: Optional[_dt.datetime] = None, reader=read_list,
         loader=ct_export.load_tests, writer=ct_export.write_copy) -> int:
    log.step('CT Test Automation Toolkit {} 입력·출력 지정'.format(paths.version()))
    try:
        with log.checkpoint('목록 읽기'):
            listed = reader(list_path)
    except ListFileError as exc:
        log.error(str(exc))
        return 1
    if listed.errors:
        log.warn('목록 오류 {}줄'.format(len(listed.errors)))

    stamp = (now or _dt.datetime.now()).strftime('%Y%m%d_%H%M%S')
    out_dir = (out_root or paths.result_dir() / 'io') / stamp
    out_display = 'result\\io\\{}\\'.format(stamp)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        log.error(E_OUT_WRITE)
        return 1

    result = None
    if export_dir is not None:
        try:
            with log.checkpoint('내보낸 폴더 읽기'):
                tests = loader(export_dir)
            result = match(listed.rows, tests, reset_cases)
            for reason in SKIP_REASONS:
                if result.count(reason):
                    log.warn('건너뜀 {} {}'.format(reason, result.count(reason)))
            if result.unlisted:
                log.warn('{} {}'.format(R_UNLISTED, len(result.unlisted)))
            with log.checkpoint('사본 쓰기'):
                writer(export_dir, out_dir, tests, result.applied, reset_cases)
        except ct_export.NotReady:
            log.error(E_EXPORT_NOT_READY)
            return 1

    try:
        write_skipped(out_dir / SKIPPED_NAME, listed, result)
    except OSError:
        log.error(E_OUT_WRITE)
        return 1
    for line in summary_lines(listed, result, out_display, reset_cases):
        log.step(line)
    log.step('로그: {}'.format(log.path.name if log.path is not None else '(없음)'))
    return 0
