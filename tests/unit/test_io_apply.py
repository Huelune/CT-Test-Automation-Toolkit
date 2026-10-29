"""ct_toolkit.io_apply 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import datetime as _dt
import io
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from ct_toolkit.__main__ import _parser  # noqa: E402
from ct_toolkit.io_apply import (  # noqa: E402
    E_EXPORT_NOT_READY, M_LIST_ONLY, main, summary_lines, write_skipped)
from ct_toolkit.io_list import (  # noqa: E402
    E_LIST_OPEN, R_LIST_EMPTY, ListError, ListFileError, ListRead, ListRow)
from ct_toolkit.io_match import R_NO_VAR, CtTest, CtVar, MatchResult, Skip  # noqa: E402
from ct_toolkit.log import RunLog  # noqa: E402

NOW = _dt.datetime(2026, 10, 29, 15, 30, 0)
OUT = 'result\\io\\20261029_153000\\'


def _listed() -> ListRead:
    """함수 2, 줄 6, 목록 오류 1."""
    rows = [ListRow(2, 'dmy_calc', 'dmy_a', 'in'), ListRow(4, 'dmy_calc', 'dmy_typo', 'in'),
            ListRow(5, 'dmy_calc', 'dmy_b', 'out'), ListRow(6, 'dmy_calc', 'dmy_c', 'in'),
            ListRow(7, 'dmy_ghost', 'dmy_d', 'out')]
    return ListRead(rows, [ListError(3, 'dmy_calc', '', R_LIST_EMPTY)])


def _result() -> MatchResult:
    return MatchResult(applied={'k1': {'dmy_a': 'in', 'dmy_b': 'out'}, 'k2': {'dmy_c': 'in'}},
                       skips=[Skip(4, 'dmy_calc', 'dmy_typo', R_NO_VAR)],
                       not_exported=['dmy_ghost'], unlisted=['dmy_other'], tests_total=3)


class SummaryTest(unittest.TestCase):
    def test_full_summary_lines(self) -> None:
        self.assertEqual(summary_lines(_listed(), _result(), OUT, True), [
            '목록      함수 2, 줄 6, 목록 오류 1',
            '테스트    내보낸 것 3, 바꾼 것 2, 케이스 정리 2, 목록에 없는 것 1',
            '지정      변수 3',
            '안 다룸   내보내지 않은 함수 1',
            '건너뜀    함수 여럿 0, 변수 없음 1, 목록 충돌 0, 값 있음 0, 타입 제외 0',
            '사본      result\\io\\20261029_153000\\',
            '건너뛴 줄 result\\io\\20261029_153000\\skipped.txt'])

    def test_list_only_summary_lines(self) -> None:
        self.assertEqual(summary_lines(_listed(), None, OUT, False), [
            '목록      함수 2, 줄 6, 목록 오류 1',
            '건너뛴 줄 result\\io\\20261029_153000\\skipped.txt',
            M_LIST_ONLY])

    def test_no_reset_shows_zero_cleaned(self) -> None:
        lines = summary_lines(_listed(), _result(), OUT, False)
        self.assertEqual(lines[1], '테스트    내보낸 것 3, 바꾼 것 2, 케이스 정리 0, 목록에 없는 것 1')


class SkippedFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'skipped.txt'

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_skipped_file_lists_errors_skips_and_unlisted(self) -> None:
        write_skipped(self.path, _listed(), _result())
        self.assertEqual(self.path.read_text(encoding='utf-8-sig').splitlines(), [
            '행\t함수\t변수\t이유',
            '3\tdmy_calc\t\t목록 오류(필수 칸 비었음)',
            '4\tdmy_calc\tdmy_typo\t변수 없음',
            '-\tdmy_other\t-\t목록에 없는 테스트'])

    def test_list_only_skipped_file_has_list_errors(self) -> None:
        write_skipped(self.path, _listed(), None)
        self.assertEqual(self.path.read_text(encoding='utf-8-sig').splitlines(), [
            '행\t함수\t변수\t이유',
            '3\tdmy_calc\t\t목록 오류(필수 칸 비었음)'])


class MainTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.console = io.StringIO()
        self.log = RunLog('io-apply', log_dir=self.tmp / 'logs', console=self.console,
                          clock=lambda: NOW)
        self.out_root = self.tmp / 'io'
        self.writes: List[tuple] = []
        self.loaded: List[Path] = []

    def tearDown(self) -> None:
        self.log.close()
        self._tmp.cleanup()

    def _run(self, listed: ListRead, tests=None, **kwargs) -> int:
        def reader(path: Path) -> ListRead:
            return listed

        def loader(path: Path) -> List[CtTest]:
            self.loaded.append(path)
            return tests or []

        def writer(*args) -> None:
            self.writes.append(args)

        kwargs.setdefault('loader', loader)
        kwargs.setdefault('writer', writer)
        return main(self.log, Path('list.xlsx'), now=NOW, out_root=self.out_root, reader=reader,
                    **kwargs)

    def _log_text(self) -> str:
        self.log.close()
        return self.log.path.read_text(encoding='utf-8')

    def test_main_list_only(self) -> None:
        code = self._run(_listed())
        self.assertEqual(code, 0)
        self.assertTrue((self.out_root / '20261029_153000' / 'skipped.txt').is_file())
        self.assertIn(M_LIST_ONLY, self.console.getvalue())
        self.assertEqual(self.loaded, [])

    def test_main_full_with_fake_export(self) -> None:
        tests = [CtTest('k1', 'dmy_calc', 'dmy_io.c', {'dmy_a': CtVar('dmy_a', '')})]
        listed = ListRead([ListRow(2, 'dmy_calc', 'dmy_a', 'out')], [])
        code = self._run(listed, tests, export_dir=Path('export'), reset_cases=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.writes, [(Path('export'), self.out_root / '20261029_153000', tests,
                                        {'k1': {'dmy_a': 'out'}}, True)])
        self.assertIn('지정      변수 1', self.console.getvalue())

    def test_main_default_loader_not_ready(self) -> None:
        code = main(self.log, Path('list.xlsx'), Path('export'), now=NOW, out_root=self.out_root,
                    reader=lambda path: _listed())
        self.assertEqual(code, 1)
        self.assertIn(E_EXPORT_NOT_READY, self.console.getvalue())

    def test_main_list_error_stops(self) -> None:
        def reader(path: Path) -> ListRead:
            raise ListFileError(E_LIST_OPEN)
        code = main(self.log, Path('list.xlsx'), now=NOW, out_root=self.out_root, reader=reader)
        self.assertEqual(code, 1)
        self.assertIn(E_LIST_OPEN, self.console.getvalue())

    def test_main_empty_list(self) -> None:
        code = self._run(ListRead([], []))
        self.assertEqual(code, 0)
        self.assertIn('목록      함수 0, 줄 0, 목록 오류 0', self.console.getvalue())

    def test_main_warns_skip_counts(self) -> None:
        tests = [CtTest('k1', 'dmy_calc', 'dmy_io.c', {})]
        listed = ListRead([ListRow(2, 'dmy_calc', 'dmy_typo', 'in')], [])
        self._run(listed, tests, export_dir=Path('export'))
        warns = [line for line in self._log_text().splitlines() if ' WARN ' in line]
        self.assertTrue(any('변수 없음 1' in line for line in warns), warns)

    def test_main_hides_names_and_paths(self) -> None:
        self.out_root = self.tmp / 'secret_dir'
        tests = [CtTest('secret_key', 'secret_fn', 'secret_file.c',
                        {'secret_var': CtVar('secret_var', '')}),
                 CtTest('secret_key2', 'secret_unlisted', 'secret_file.c', {})]
        listed = ListRead([ListRow(2, 'secret_fn', 'secret_var', 'in'),
                           ListRow(3, 'secret_fn', 'secret_typo', 'in'),
                           ListRow(4, 'secret_ghost', 'secret_x', 'in')],
                          [ListError(5, 'secret_bad', '', R_LIST_EMPTY)])
        code = self._run(listed, tests, export_dir=self.tmp / 'secret_export')
        self.assertEqual(code, 0)
        self.assertNotIn('secret', self.console.getvalue())
        self.assertNotIn('secret', self._log_text())
        skipped = (self.out_root / '20261029_153000' / 'skipped.txt').read_text(encoding='utf-8-sig')
        self.assertIn('secret_fn', skipped)


class ParserTest(unittest.TestCase):
    def test_io_apply_arguments(self) -> None:
        args = _parser().parse_args(['io-apply', '--list', 'a.xlsx', '--export', 'd',
                                     '--reset-cases'])
        self.assertEqual((args.command, args.list_path, args.export_dir, args.reset_cases),
                         ('io-apply', Path('a.xlsx'), Path('d'), True))


if __name__ == '__main__':
    unittest.main()
