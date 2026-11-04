"""목록대로 입력·출력 지정하기 (`ct.bat io-apply`).

`--export`를 주면 CT [테스트 내보내기] 폴더를 읽어 목록과 맞춰 보고, 지정이 바뀌는 테스트의 CSV
사본을 결과 폴더에 쓴다. 사용자는 그 CSV로 CT에서 테스트를 다시 만든다.

화면에는 개수와 정해 둔 문구, 출력 파일 이름만 찍는다. 함수·변수 이름은 결과 폴더의
`skipped.txt`에만 쓴다. 이 파일은 서버 PC에서만 본다. 설계는 docs/design/io-designation.md.

종료 코드: 0 끝까지 됨(건너뛴 줄이 있어도), 1 목록·내보낸 폴더·결과 폴더 문제로 멈춤.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from . import ct_export, paths
from .io_list import ListFileError, ListRead, read_list
from .io_match import R_NOT_IN_CT, SKIP_REASONS, MatchResult, match
from .log import RunLog

E_OUT_WRITE = '결과 폴더에 쓸 수 없음: result 폴더 권한과 남은 공간을 확인'
M_LIST_ONLY = '내보낸 폴더(--export)를 주지 않아 목록만 확인했습니다'
M_NEXT = '다음: CT에서 바꾼 테스트의 원래 것을 지우고 [테스트 데이터로 테스트 생성하기]로 사본 CSV를 넣기'
M_NOTHING = '바꿀 지정이 없어 사본 CSV를 쓰지 않았습니다'
M_RENAMED_ONLY = '바꿀 테스트가 모두 이름 꼴이 아니라 사본 CSV를 쓰지 않았습니다'

SKIPPED_NAME = 'skipped.txt'
R_UNLISTED = '목록에 없는 테스트'
R_RELEASED = '목록에 없어 해제'
R_KEPT = '목록에 없지만 값 있음'
R_UNREADABLE = '읽지 못한 CSV'
R_RENAMED = '이름 꼴이 아닌 테스트'  # 화면·로그용
R_RENAMED_TEST = '테스트 이름이 <함수>_test<N> 꼴이 아님'  # skipped.txt 이유
R_NOT_IN_CT_TEST = 'CT에 없음: CT에서 원소·멤버를 늘린 뒤 다시 내보내기'  # skipped.txt 이유

_MAX_SAME_SECOND = 1000  # 같은 시각의 결과 폴더 이름(`_2`, `_3`…)을 시도하는 한도


def summary_lines(listed: ListRead, result: Optional[MatchResult], out_display: str,
                  reset_cases: bool, unreadable: int = 0, copied: int = 0,
                  renamed: int = 0) -> List[str]:
    """한 화면 요약. `result`가 없으면 목록만 확인한 것이다.

    `renamed`는 지정이 바뀔 테스트였지만 이름 꼴이 아니라 사본에서 뺀 개수다. `result`는 그 테스트를
    뺀 것이다(`main`이 `_without_tests`로 뺀다).
    """
    lines = ['목록      함수 {}, 줄 {}, 목록 오류 {}'.format(
        listed.functions, listed.total, len(listed.errors))]
    skipped = '건너뛴 줄 {}{}'.format(out_display, SKIPPED_NAME)
    if result is None:
        return lines + [skipped, M_LIST_ONLY]
    changed = len(result.edits)
    return lines + [
        '테스트    내보낸 것 {}, 바꾼 것 {}, 케이스 정리 {}, 목록에 없는 것 {}'.format(
            result.tests_total, changed, changed if reset_cases else 0, len(result.unlisted)),
        '지정      변수 {}(그중 바뀜 {}), {} {}, 값 있어 둠 {}'.format(
            result.assigned, result.changed_vars, R_RELEASED, result.released_vars,
            result.kept_vars),
        '안 다룸   내보내지 않은 함수 {}, {} {}, {} {}'.format(
            len(result.not_exported), R_UNREADABLE, unreadable, R_RENAMED, renamed),
        '건너뜀    ' + ', '.join('{} {}'.format(r, result.count(r)) for r in SKIP_REASONS),
        '사본      {} (CSV {})'.format(out_display, copied),
        skipped,
        M_NEXT if copied else M_RENAMED_ONLY if renamed else M_NOTHING,
    ]


def write_skipped(path: Path, listed: ListRead, result: Optional[MatchResult],
                  export: Optional[ct_export.ExportRead] = None,
                  renamed: Sequence[str] = ()) -> None:
    """사람이 손으로 마저 할 줄. 탭 구분이라 엑셀로도 열린다. `renamed`는 사본에서 뺀 테스트 키."""
    lines = ['행\t함수\t변수\t이유']
    lines += ['{}\t{}\t{}\t{}'.format(e.row, e.function, e.variable, e.reason)
              for e in sorted(listed.errors, key=lambda e: e.row)]
    if result is not None:
        functions = {t.key: t.function for t in export.tests} if export is not None else {}
        lines += ['{}\t{}\t{}\t{}'.format(s.row, s.function, s.variable,
                                          R_NOT_IN_CT_TEST if s.reason == R_NOT_IN_CT else s.reason)
                  for s in result.skips]
        lines += ['-\t{}\t-\t{}'.format(name, R_UNLISTED) for name in result.unlisted]
        lines += ['-\t{}\t-\t{}'.format(functions.get(key, '-'), R_RENAMED_TEST)
                  for key in sorted(renamed)]
        for reason, found in ((R_RELEASED, result.released), (R_KEPT, result.kept)):
            lines += ['-\t{}\t{}\t{}'.format(functions.get(key, '-'), name, reason)
                      for key in sorted(found) for name in found[key]]
    if export is not None:
        lines += ['-\t{}\t-\t{}'.format(name, R_UNREADABLE) for name in export.unreadable]
    with open(path, 'w', encoding='utf-8-sig') as f:
        f.write('\n'.join(lines) + '\n')


def _without_tests(result: MatchResult, keys: Sequence[str]) -> MatchResult:
    """사본에서 뺀 테스트의 지정·해제를 결과에서도 뺀다(화면과 skipped.txt가 사본과 어긋나지 않게)."""
    def kept(found: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        return {k: v for k, v in found.items() if k not in keys}

    def kept_lists(found: Dict[str, List[str]]) -> Dict[str, List[str]]:
        return {k: v for k, v in found.items() if k not in keys}

    return dataclasses.replace(result, applied=kept(result.applied), changes=kept(result.changes),
                               symbol_changes=kept(result.symbol_changes),
                               released=kept_lists(result.released), kept=kept_lists(result.kept))


def _make_out_dir(root: Path, stamp: str) -> Tuple[Path, str]:
    """`root/<stamp>` 폴더를 만든다. 이미 있으면 `<stamp>_2`, `_3`…으로 새로 만든다. 만든 (경로, 이름)."""
    root.mkdir(parents=True, exist_ok=True)
    for n in range(1, _MAX_SAME_SECOND + 1):
        name = stamp if n == 1 else '{}_{}'.format(stamp, n)
        try:
            (root / name).mkdir()
        except FileExistsError:
            continue
        return root / name, name
    raise FileExistsError(stamp)


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

    export = None
    result = None
    renamed: List[str] = []  # 지정이 바뀔 테스트인데 이름 꼴이 아니라 사본에서 뺀 것의 키
    if export_dir is not None:
        try:
            with log.checkpoint('내보낸 폴더 읽기'):
                export = loader(export_dir)
        except ct_export.ExportError as exc:
            log.error(str(exc))
            return 1
        result = match(listed.rows, export.tests, reset_cases)
        # CT는 `<함수>_test<N>` 꼴이 아닌 이름의 CSV로는 테스트를 만들지 않는다. 그런 사본은 쓰지 않는다
        renamed = sorted(set(result.edits) & set(export.renamed))
        if renamed:
            result = _without_tests(result, renamed)
        for reason in SKIP_REASONS:
            if result.count(reason):
                log.warn('건너뜀 {} {}'.format(reason, result.count(reason)))
        if result.unlisted:
            log.warn('{} {}'.format(R_UNLISTED, len(result.unlisted)))
        if export.unreadable:
            log.warn('{} {}'.format(R_UNREADABLE, len(export.unreadable)))
        if renamed:
            log.warn('{} {}: 사본에 넣지 않음'.format(R_RENAMED, len(renamed)))
        if result.kept_vars:
            log.warn('{} {}'.format(R_KEPT, result.kept_vars))
        if result.released_vars:
            log.info('{} {}'.format(R_RELEASED, result.released_vars))

    # 내보낸 폴더를 읽지 못했으면 결과 폴더를 만들지 않는다
    stamp = (now or _dt.datetime.now()).strftime('%Y%m%d_%H%M%S')
    try:
        out_dir, out_name = _make_out_dir(out_root or paths.result_dir() / 'io', stamp)
    except OSError:
        log.error(E_OUT_WRITE)
        return 1
    out_display = 'result\\io\\{}\\'.format(out_name)

    copied = 0
    if result is not None and result.edits:
        try:
            with log.checkpoint('사본 쓰기'):
                copied = writer(export_dir, out_dir, result.edits, reset_cases)
        except OSError:
            log.error(E_OUT_WRITE)
            return 1
        log.info('사본 CSV {}'.format(copied))

    try:
        write_skipped(out_dir / SKIPPED_NAME, listed, result, export, renamed)
    except OSError:
        log.error(E_OUT_WRITE)
        return 1
    unreadable = len(export.unreadable) if export is not None else 0
    for line in summary_lines(listed, result, out_display, reset_cases, unreadable, copied,
                              len(renamed)):
        log.step(line)
    log.step('로그: {}'.format(log.path.name if log.path is not None else '(없음)'))
    return 0
