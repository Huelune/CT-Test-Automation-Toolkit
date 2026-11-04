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
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 견본 CSV 만들기는 test_ct_export와 같이 쓴다

from test_ct_export import MIXED_HEADER, UTEST, _by_section, _case, _csv  # noqa: E402
from ct_toolkit import ct_export  # noqa: E402
from ct_toolkit.__main__ import _parser  # noqa: E402
from ct_toolkit.ct_export import (  # noqa: E402
    E_EXPORT_EMPTY, E_EXPORT_OPEN, ExportError, ExportRead)
from ct_toolkit.io_apply import (  # noqa: E402
    E_OUT_WRITE, M_LIST_ONLY, M_NEXT, M_NOTHING, M_RENAMED_ONLY, R_KEPT, R_NOT_IN_CT_TEST, R_RELEASED,
    R_RENAMED, R_RENAMED_TEST, R_UNREADABLE, main, summary_lines, write_skipped)
from ct_toolkit.io_list import (  # noqa: E402
    E_LIST_OPEN, R_LIST_EMPTY, ListError, ListFileError, ListRead, ListRow)
from ct_toolkit.io_match import R_NO_VAR, R_NOT_IN_CT, CtTest, CtVar, MatchResult, Skip  # noqa: E402
from ct_toolkit.log import RunLog  # noqa: E402

NOW = _dt.datetime(2026, 10, 29, 15, 30, 0)
STAMP = '20261029_153000'
OUT = 'result\\io\\{}\\'.format(STAMP)
SAMPLE_KEY = 'ctsample/UnitTests/dmy_calc_test0.csv'


def _listed() -> ListRead:
    """함수 2, 줄 6, 목록 오류 1."""
    rows = [ListRow(2, 'dmy_calc', 'dmy_a', 'in'), ListRow(4, 'dmy_calc', 'dmy_typo', 'in'),
            ListRow(5, 'dmy_calc', 'dmy_b', 'out'), ListRow(6, 'dmy_calc', 'dmy_c', 'in'),
            ListRow(7, 'dmy_ghost', 'dmy_d', 'out')]
    return ListRead(rows, [ListError(3, 'dmy_calc', '', R_LIST_EMPTY)])


def _result() -> MatchResult:
    """내보낸 것 3, 바꾼 것 2(k1 지정 변경, k2 해제), 지정 변수 3(그중 바뀜 1), 해제 1."""
    return MatchResult(applied={'k1': {'dmy_a': 'in', 'dmy_b': 'out'}, 'k2': {'dmy_c': 'in'}},
                       skips=[Skip(4, 'dmy_calc', 'dmy_typo', R_NO_VAR)],
                       not_exported=['dmy_ghost'], unlisted=['dmy_other'], tests_total=3,
                       changes={'k1': {'dmy_a': 'in'}}, released={'k2': ['dmy_old']},
                       symbol_changes={'k1': {'dmy_a': 'in'}})


def _empty_result() -> MatchResult:
    """바꿀 지정이 없다."""
    return MatchResult(applied={'k1': {'dmy_a': 'in'}}, skips=[], not_exported=[], unlisted=[],
                       tests_total=1)


def _export() -> ExportRead:
    """`_result()`의 테스트 k1, k2와 읽지 못한 CSV 하나."""
    return ExportRead([CtTest('k1', 'dmy_calc', 'dmy_io.c', {}),
                       CtTest('k2', 'dmy_func', 'dmy_io.c', {})], ['other/x.csv'])


def _sample_list() -> ListRead:
    """예제 목록(examples/ct_sample/io_list.example.xlsx)과 같은 9줄."""
    rows = [ListRow(2, 'dmy_calc', 'dmy_gain', 'in'), ListRow(3, 'dmy_calc', 'dmy_mode', 'in'),
            ListRow(4, 'dmy_calc', 'dmy_limit', 'in'), ListRow(5, 'dmy_calc', 'dmy_x', 'in'),
            ListRow(6, 'dmy_calc', 'dmy_ptr', 'in'), ListRow(7, 'dmy_calc', 'dmy_level', 'out'),
            ListRow(8, 'dmy_calc', 'dmy_hist', 'out'), ListRow(9, 'dmy_calc', 'dmy_count', 'out'),
            ListRow(10, 'dmy_calc', 'return', 'out')]
    return ListRead(rows, [])


class SummaryTest(unittest.TestCase):
    def test_full_summary_lines(self) -> None:
        self.assertEqual(summary_lines(_listed(), _result(), OUT, True, unreadable=1, copied=2), [
            '목록      함수 2, 줄 6, 목록 오류 1',
            '테스트    내보낸 것 3, 바꾼 것 2, 케이스 정리 2, 목록에 없는 것 1',
            '지정      변수 3(그중 바뀜 1), 목록에 없어 해제 1, 값 있어 둠 0',
            '안 다룸   내보내지 않은 함수 1, 읽지 못한 CSV 1, 이름 꼴이 아닌 테스트 0',
            '건너뜀    함수 여럿 0, 변수 없음 1, 목록 충돌 0, 값 있음 0, 타입 제외 0, CT에 없음 0',
            '사본      ' + OUT + ' (CSV 2)',
            '건너뛴 줄 ' + OUT + 'skipped.txt',
            M_NEXT])

    def test_list_only_summary_lines(self) -> None:
        self.assertEqual(summary_lines(_listed(), None, OUT, False), [
            '목록      함수 2, 줄 6, 목록 오류 1',
            '건너뛴 줄 ' + OUT + 'skipped.txt',
            M_LIST_ONLY])

    def test_no_reset_shows_zero_cleaned(self) -> None:
        lines = summary_lines(_listed(), _result(), OUT, False, copied=2)
        self.assertEqual(lines[1], '테스트    내보낸 것 3, 바꾼 것 2, 케이스 정리 0, 목록에 없는 것 1')

    def test_nothing_to_change_says_so(self) -> None:
        lines = summary_lines(_listed(), _empty_result(), OUT, True)
        self.assertEqual(lines[1], '테스트    내보낸 것 1, 바꾼 것 0, 케이스 정리 0, 목록에 없는 것 0')
        self.assertEqual(lines[-3:], ['사본      ' + OUT + ' (CSV 0)',
                                      '건너뛴 줄 ' + OUT + 'skipped.txt',
                                      M_NOTHING])

    def test_renamed_tests_are_counted_on_the_not_handled_line(self) -> None:
        lines = summary_lines(_listed(), _result(), OUT, True, unreadable=1, copied=2, renamed=3)
        self.assertEqual(lines[3], '안 다룸   내보내지 않은 함수 1, 읽지 못한 CSV 1, 이름 꼴이 아닌 테스트 3')
        self.assertEqual(lines[-1], M_NEXT)
        only = summary_lines(_listed(), _empty_result(), OUT, True, renamed=1)
        self.assertEqual(only[-1], M_RENAMED_ONLY)  # 바꿀 지정은 있지만 사본에 넣지 않았다
        self.assertEqual(summary_lines(_listed(), _empty_result(), OUT, True)[-1], M_NOTHING)

    def test_kept_variables_are_counted(self) -> None:
        result = _result()
        result.kept = {'k1': ['dmy_val1', 'dmy_val2']}
        self.assertEqual(summary_lines(_listed(), result, OUT, False, copied=2)[2],
                         '지정      변수 3(그중 바뀜 1), 목록에 없어 해제 1, 값 있어 둠 2')


class SkippedFileTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / 'skipped.txt'

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _lines(self) -> List[str]:
        return self.path.read_text(encoding='utf-8-sig').splitlines()

    def test_skipped_file_lists_errors_skips_and_unlisted(self) -> None:
        result = _result()
        result.released = {}
        write_skipped(self.path, _listed(), result, _export())
        self.assertEqual(self._lines()[1:], [
            '3\tdmy_calc\t\t목록 오류(필수 칸 비었음)',
            '4\tdmy_calc\tdmy_typo\t변수 없음',
            '-\tdmy_other\t-\t목록에 없는 테스트',
            '-\tother/x.csv\t-\t' + R_UNREADABLE])

    def test_skipped_file_lists_released_and_unreadable(self) -> None:
        write_skipped(self.path, _listed(), _result(), _export())
        self.assertEqual(self._lines(), [
            '행\t함수\t변수\t이유',
            '3\tdmy_calc\t\t목록 오류(필수 칸 비었음)',
            '4\tdmy_calc\tdmy_typo\t변수 없음',
            '-\tdmy_other\t-\t목록에 없는 테스트',
            '-\tdmy_func\tdmy_old\t' + R_RELEASED,
            '-\tother/x.csv\t-\t' + R_UNREADABLE])
        self.assertEqual((R_RELEASED, R_UNREADABLE), ('목록에 없어 해제', '읽지 못한 CSV'))

    def test_skipped_file_lists_kept_variables(self) -> None:
        result = _result()
        result.kept = {'k1': ['dmy_val1', 'dmy_val2']}
        write_skipped(self.path, _listed(), result, _export())
        lines = self._lines()
        self.assertEqual(lines[5:7], ['-\tdmy_calc\tdmy_val1\t' + R_KEPT,
                                      '-\tdmy_calc\tdmy_val2\t' + R_KEPT])
        self.assertEqual(R_KEPT, '목록에 없지만 값 있음')

    def test_skipped_file_lists_renamed_tests(self) -> None:
        write_skipped(self.path, _listed(), _result(), _export(), ['k2'])
        self.assertIn('-\tdmy_func\t-\t' + R_RENAMED_TEST, self._lines())
        self.assertEqual((R_RENAMED, R_RENAMED_TEST),
                         ('이름 꼴이 아닌 테스트', '테스트 이름이 <함수>_test<N> 꼴이 아님'))

    def test_skipped_file_explains_not_in_ct(self) -> None:
        result = _result()
        result.skips = [Skip(5, 'dmy_calc', 'v[2].s', R_NOT_IN_CT)]
        write_skipped(self.path, _listed(), result, _export())
        self.assertIn('5\tdmy_calc\tv[2].s\t' + R_NOT_IN_CT_TEST, self._lines())

    def test_list_only_skipped_file_has_list_errors(self) -> None:
        write_skipped(self.path, _listed(), None)
        self.assertEqual(self._lines(), [
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

    def _run(self, listed: ListRead, tests=None, unreadable=None, renamed=None, **kwargs) -> int:
        def reader(path: Path) -> ListRead:
            return listed

        def loader(path: Path) -> ExportRead:
            self.loaded.append(path)
            return ExportRead(tests or [], unreadable or [], renamed or [])

        def writer(*args) -> int:
            self.writes.append(args)
            return len(args[2])

        kwargs.setdefault('loader', loader)
        kwargs.setdefault('writer', writer)
        return main(self.log, Path('list.xlsx'), now=NOW, out_root=self.out_root, reader=reader,
                    **kwargs)

    def _log_text(self) -> str:
        self.log.close()
        return self.log.path.read_text(encoding='utf-8')

    def _skipped(self, name: str = STAMP) -> str:
        return (self.out_root / name / 'skipped.txt').read_text(encoding='utf-8-sig')

    def test_main_list_only(self) -> None:
        code = self._run(_listed())
        self.assertEqual(code, 0)
        self.assertTrue((self.out_root / STAMP / 'skipped.txt').is_file())
        self.assertIn(M_LIST_ONLY, self.console.getvalue())
        self.assertEqual(self.loaded, [])

    def test_main_full_with_fake_export(self) -> None:
        tests = [CtTest('k1', 'dmy_calc', 'dmy_io.c', {'dmy_a': CtVar('dmy_a', '')})]
        listed = ListRead([ListRow(2, 'dmy_calc', 'dmy_a', 'out')], [])
        code = self._run(listed, tests, export_dir=Path('export'), reset_cases=True)
        self.assertEqual(code, 0)
        self.assertEqual(self.writes, [(Path('export'), self.out_root / STAMP,
                                        {'k1': {'dmy_a': 'out'}}, True)])
        screen = self.console.getvalue()
        self.assertIn('지정      변수 1(그중 바뀜 1), 목록에 없어 해제 0, 값 있어 둠 0', screen)
        self.assertIn('사본      ' + OUT + ' (CSV 1)', screen)
        self.assertIn(M_NEXT, screen)
        self.assertNotIn(M_NOTHING, screen)

    def test_nothing_to_change_does_not_write_copies(self) -> None:
        tests = [CtTest('k1', 'dmy_calc', 'dmy_io.c', {'dmy_a': CtVar('dmy_a', 'in')})]
        listed = ListRead([ListRow(2, 'dmy_calc', 'dmy_a', 'in')], [])
        code = self._run(listed, tests, export_dir=Path('export'))
        self.assertEqual(code, 0)
        self.assertEqual(self.writes, [])
        screen = self.console.getvalue()
        self.assertIn('바꾼 것 0', screen)
        self.assertIn('사본      ' + OUT + ' (CSV 0)', screen)
        self.assertIn(M_NOTHING, screen)
        self.assertNotIn(M_NEXT, screen)
        self.assertTrue((self.out_root / STAMP / 'skipped.txt').is_file())

    def test_main_export_error_stops(self) -> None:
        code = main(self.log, Path('list.xlsx'), self.tmp / 'no_such_export', now=NOW,
                    out_root=self.out_root, reader=lambda path: _listed())
        self.assertEqual(code, 1)
        self.assertIn(E_EXPORT_OPEN, self.console.getvalue())

    def test_export_error_stops_before_result_folder(self) -> None:
        def loader(path: Path) -> ExportRead:
            raise ExportError(E_EXPORT_EMPTY)
        code = self._run(_listed(), export_dir=Path('export'), loader=loader)
        self.assertEqual(code, 1)
        self.assertIn(E_EXPORT_EMPTY, self.console.getvalue())
        self.assertFalse(self.out_root.exists())

    def test_same_second_runs_get_separate_folders(self) -> None:
        self._run(_listed())
        self.assertIn('건너뛴 줄 ' + OUT + 'skipped.txt', self.console.getvalue())
        self.console.seek(0)
        self.console.truncate(0)
        self._run(_listed())
        second = self.console.getvalue()
        self.assertIn('건너뛴 줄 result\\io\\{}_2\\skipped.txt'.format(STAMP), second)
        self.assertNotIn(OUT, second)
        self._run(_listed())
        self.assertEqual(sorted(p.name for p in self.out_root.iterdir()),
                         [STAMP, STAMP + '_2', STAMP + '_3'])
        for name in (STAMP, STAMP + '_2', STAMP + '_3'):
            self.assertTrue((self.out_root / name / 'skipped.txt').is_file(), name)

    def test_copy_write_error_stops_with_fixed_message(self) -> None:
        tests = [CtTest('k1', 'dmy_calc', 'dmy_io.c', {'dmy_a': CtVar('dmy_a', '')})]
        listed = ListRead([ListRow(2, 'dmy_calc', 'dmy_a', 'out')], [])

        def writer(*args) -> int:
            raise OSError('C:\\secret_dir\\secret_copy.csv')
        code = self._run(listed, tests, export_dir=Path('export'), writer=writer)
        self.assertEqual(code, 1)
        self.assertIn(E_OUT_WRITE, self.console.getvalue())
        self.assertNotIn('secret', self.console.getvalue())
        self.assertNotIn('secret', self._log_text())

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

    def test_unreadable_csv_warns_with_count_and_lands_in_skipped(self) -> None:
        tests = [CtTest('k1', 'dmy_calc', 'dmy_io.c', {})]
        listed = ListRead([ListRow(2, 'dmy_calc', 'dmy_x', 'in')], [])
        self._run(listed, tests, unreadable=['other/a.csv', 'other/b.csv'], export_dir=Path('export'))
        warns = [line for line in self._log_text().splitlines() if ' WARN ' in line]
        self.assertTrue(any('읽지 못한 CSV 2' in line and 'other' not in line for line in warns), warns)
        self.assertIn('안 다룸   내보내지 않은 함수 0, 읽지 못한 CSV 2, 이름 꼴이 아닌 테스트 0',
                      self.console.getvalue())
        skipped = self._skipped()
        self.assertIn('-\tother/a.csv\t-\t읽지 못한 CSV', skipped)
        self.assertIn('-\tother/b.csv\t-\t읽지 못한 CSV', skipped)

    def _renamed_run(self, **kwargs) -> int:
        """k1(이름 꼴이 아님)과 k2 둘 다 지정이 바뀌는 테스트."""
        tests = [CtTest('k1', 'secret_fn1', 'secret_a.c', {'secret_a': CtVar('secret_a', '')}),
                 CtTest('k2', 'secret_fn2', 'secret_b.c', {'secret_b': CtVar('secret_b', '')})]
        listed = ListRead([ListRow(2, 'secret_fn1', 'secret_a', 'out'),
                           ListRow(3, 'secret_fn2', 'secret_b', 'out')], [])
        return self._run(listed, tests, export_dir=Path('export'), reset_cases=True, **kwargs)

    def test_renamed_tests_are_left_out_of_copies_and_counted(self) -> None:
        self.assertEqual(self._renamed_run(renamed=['k1']), 0)
        self.assertEqual(self.writes, [(Path('export'), self.out_root / STAMP,
                                        {'k2': {'secret_b': 'out'}}, True)])
        screen = self.console.getvalue()
        self.assertIn('테스트    내보낸 것 2, 바꾼 것 1, 케이스 정리 1, 목록에 없는 것 0', screen)
        self.assertIn('지정      변수 1(그중 바뀜 1), 목록에 없어 해제 0, 값 있어 둠 0', screen)
        self.assertIn('안 다룸   내보내지 않은 함수 0, 읽지 못한 CSV 0, 이름 꼴이 아닌 테스트 1', screen)
        self.assertIn('사본      ' + OUT + ' (CSV 1)', screen)
        self.assertIn(M_NEXT, screen)
        self.assertNotIn('secret', screen)
        self.assertNotIn('secret', self._log_text())
        skipped = self._skipped()
        self.assertIn('-\tsecret_fn1\t-\t' + R_RENAMED_TEST, skipped)
        self.assertNotIn('secret_fn2\t-\t' + R_RENAMED_TEST, skipped)
        warns = [line for line in self._log_text().splitlines() if ' WARN ' in line]
        self.assertTrue(any('이름 꼴이 아닌 테스트 1' in line for line in warns), warns)

    def test_only_renamed_tests_to_change_writes_nothing(self) -> None:
        self._renamed_run(renamed=['k1', 'k2'])
        self.assertEqual(self.writes, [])
        screen = self.console.getvalue()
        self.assertIn('바꾼 것 0', screen)
        self.assertIn('이름 꼴이 아닌 테스트 2', screen)
        self.assertIn('사본      ' + OUT + ' (CSV 0)', screen)
        self.assertIn(M_RENAMED_ONLY, screen)
        self.assertNotIn(M_NOTHING, screen)
        self.assertEqual(self._skipped().count(R_RENAMED_TEST), 2)

    def test_renamed_test_without_changes_is_not_counted(self) -> None:
        # 바꿀 것이 없어 어차피 사본에 안 넣는 테스트는 이름 꼴을 따지지 않는다
        tests = [CtTest('k1', 'dmy_calc', 'dmy_io.c', {'dmy_a': CtVar('dmy_a', 'in')})]
        listed = ListRead([ListRow(2, 'dmy_calc', 'dmy_a', 'in')], [])
        self._run(listed, tests, renamed=['k1'], export_dir=Path('export'))
        self.assertIn('이름 꼴이 아닌 테스트 0', self.console.getvalue())
        self.assertIn(M_NOTHING, self.console.getvalue())
        self.assertNotIn(R_RENAMED_TEST, self._skipped())
        warns = [line for line in self._log_text().splitlines() if ' WARN ' in line]
        self.assertFalse(any(R_RENAMED in line for line in warns), warns)

    def test_released_and_kept_variables_are_counted_and_listed(self) -> None:
        variables = {'dmy_a': CtVar('dmy_a', ''), 'dmy_old': CtVar('dmy_old', 'in'),
                     'dmy_val': CtVar('dmy_val', 'in', True)}
        tests = [CtTest('k1', 'dmy_calc', 'dmy_io.c', variables)]
        listed = ListRead([ListRow(2, 'dmy_calc', 'dmy_a', 'out')], [])
        self._run(listed, tests, export_dir=Path('export'))
        self.assertIn('지정      변수 1(그중 바뀜 1), 목록에 없어 해제 1, 값 있어 둠 1',
                      self.console.getvalue())
        skipped = self._skipped()
        self.assertIn('-\tdmy_calc\tdmy_old\t목록에 없어 해제', skipped)
        self.assertIn('-\tdmy_calc\tdmy_val\t목록에 없지만 값 있음', skipped)
        self.assertEqual(self.writes[0][2], {'k1': {'dmy_a': 'out', 'dmy_old': ''}})
        infos = [line for line in self._log_text().splitlines() if ' INFO ' in line]
        self.assertTrue(any('목록에 없어 해제 1' in line for line in infos), infos)

    def test_main_end_to_end_on_sample_export(self) -> None:
        export = self.tmp / 'export'
        csv = export / SAMPLE_KEY
        csv.parent.mkdir(parents=True)
        csv.write_bytes(_csv())
        csv.with_suffix('.utest').write_bytes(UTEST)
        (export / 'ctsample' / 'testInfo.export').write_bytes(b'<xml/>')
        code = self._run(_sample_list(), export_dir=export, reset_cases=True,
                         loader=ct_export.load_tests, writer=ct_export.write_copy)
        self.assertEqual(code, 0)
        screen = self.console.getvalue()
        for want in ('바꾼 것 1', '변수 9(그중 바뀜 2)', '목록에 없어 해제 1', '값 있어 둠 0',
                     '사본      ' + OUT + ' (CSV 1)', M_NEXT):
            self.assertIn(want, screen)
        copies = sorted(p.relative_to(self.out_root / STAMP).as_posix()
                        for p in (self.out_root / STAMP).rglob('*') if p.is_file())
        self.assertEqual(copies, [SAMPLE_KEY, 'skipped.txt'])  # .utest와 testInfo.export는 안 쓴다
        lines = (self.out_root / STAMP / SAMPLE_KEY).read_bytes().decode('cp949').split('\r\n')
        sections = _by_section(lines[2])
        self.assertEqual(sections['<input>'], [
            'dmy_gain', 'dmy_limit.dmy_hi', 'dmy_limit.dmy_lo', 'dmy_mode', 'dmy_ptr_mem[0]', 'dmy_x'])
        self.assertEqual(sections['<expect>'], [
            'dmy_count', 'dmy_hist[0]', 'dmy_level', 'returnVar'])
        self.assertEqual(len(lines), 5)  # 머리말 세 줄, 케이스 한 줄, 끝의 빈 문자열
        self.assertTrue(lines[3].startswith('1,""'))
        self.assertNotIn('dmy_', screen)
        self.assertNotIn('dmy_', self._log_text())
        self.assertIn('-\tdmy_calc\tdmy_spare\t목록에 없어 해제', self._skipped())

    def _member_export(self) -> Path:
        export = self.tmp / 'export'
        csv = export / SAMPLE_KEY
        csv.parent.mkdir(parents=True)
        csv.write_bytes(_csv(header=MIXED_HEADER, case=_case(MIXED_HEADER)))
        csv.with_suffix('.utest').write_bytes(UTEST)
        return export

    def test_member_rows_end_to_end(self) -> None:
        listed = ListRead([ListRow(2, 'dmy_calc', 'st.cnt', 'out'), ListRow(3, 'dmy_calc', 'dmy_ok', 'inout'),
                           ListRow(4, 'dmy_calc', 'dmy_in', 'in')], [])
        code = self._run(listed, export_dir=self._member_export(), reset_cases=True,
                         loader=ct_export.load_tests, writer=ct_export.write_copy)
        self.assertEqual(code, 0)
        lines = (self.out_root / STAMP / SAMPLE_KEY).read_bytes().decode('cp949').split('\r\n')
        sections = _by_section(lines[2])
        self.assertIn('st.cnt', sections['<expect>'])
        self.assertNotIn('st.cnt', sections['<input>'])
        self.assertNotIn('st.mode', sections['<input>'])
        self.assertIn('목록에 없어 해제 1', self.console.getvalue())

    def test_renamed_test_member_changes_left_out(self) -> None:
        tests = [CtTest('k1', 'dmy_calc', 'dmy_io.c', {'st.a': CtVar('st.a', 'in'), 'st.b': CtVar('st.b', 'in')})]
        listed = ListRead([ListRow(2, 'dmy_calc', 'st.a', 'out')], [])
        self._run(listed, tests, renamed=['k1'], export_dir=Path('export'))
        self.assertEqual(self.writes, [])  # 바뀌는 기호와 해제 기호 모두 사본에 넣지 않는다

    def test_main_hides_names_and_paths(self) -> None:
        self.out_root = self.tmp / 'secret_dir'
        tests = [CtTest('secret_key', 'secret_fn', 'secret_file.c',
                        {'secret_var': CtVar('secret_var', ''),
                         'secret_released': CtVar('secret_released', 'in'),
                         'secret_kept': CtVar('secret_kept', 'in', True)}),
                 CtTest('secret_key2', 'secret_unlisted', 'secret_file.c', {})]
        listed = ListRead([ListRow(2, 'secret_fn', 'secret_var', 'in'),
                           ListRow(3, 'secret_fn', 'secret_typo', 'in'),
                           ListRow(4, 'secret_ghost', 'secret_x', 'in')],
                          [ListError(5, 'secret_bad', '', R_LIST_EMPTY)])
        code = self._run(listed, tests, unreadable=['secret_dir/x.csv'],
                         export_dir=self.tmp / 'secret_export')
        self.assertEqual(code, 0)
        self.assertIn('값 있어 둠 1', self.console.getvalue())
        self.assertIn('읽지 못한 CSV 1', self.console.getvalue())
        self.assertNotIn('secret', self.console.getvalue())
        self.assertNotIn('secret', self._log_text())
        skipped = self._skipped()
        for name in ('secret_fn', 'secret_released', 'secret_kept', 'secret_dir/x.csv'):
            self.assertIn(name, skipped)

    def test_main_hides_symbol_names(self) -> None:
        tests = [CtTest('secret_key', 'secret_fn', 'secret_file.c',
                        {'secret_s.secret_m': CtVar('secret_s.secret_m', 'out'),
                         'secret_s.secret_n': CtVar('secret_s.secret_n', 'in'),
                         'secret_t.secret_k': CtVar('secret_t.secret_k', 'in')})]
        listed = ListRead([ListRow(2, 'secret_fn', 'secret_s.secret_m', 'in'),
                           ListRow(3, 'secret_fn', 'secret_t.secret_gone', 'in')], [])
        code = self._run(listed, tests, export_dir=Path('export'))
        self.assertEqual(code, 0)
        self.assertNotIn('secret', self.console.getvalue())
        self.assertNotIn('secret', self._log_text())
        skipped = self._skipped()
        for name in ('secret_t.secret_gone', 'secret_s.secret_n', 'secret_t.secret_k'):
            self.assertIn(name, skipped)

    def test_screen_fits_one_page(self) -> None:
        tests = [CtTest('k1', 'dmy_calc', 'dmy_io.c', {'dmy_a': CtVar('dmy_a', '')})]
        self._run(_listed(), tests, unreadable=['other/x.csv'], export_dir=Path('export'))
        lines = self.console.getvalue().splitlines()
        self.assertLessEqual(len(lines), 40)
        self.assertTrue(all(len(line) <= 120 for line in lines), lines)


class ParserTest(unittest.TestCase):
    def test_io_apply_arguments(self) -> None:
        args = _parser().parse_args(['io-apply', '--list', 'a.xlsx', '--export', 'd',
                                     '--reset-cases'])
        self.assertEqual((args.command, args.list_path, args.export_dir, args.reset_cases),
                         ('io-apply', Path('a.xlsx'), Path('d'), True))


if __name__ == '__main__':
    unittest.main()
