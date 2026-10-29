"""ct_toolkit.io_match 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from ct_toolkit.io_list import ListRow  # noqa: E402
from ct_toolkit.io_match import (  # noqa: E402
    R_CONFLICT, R_HAS_VALUES, R_MULTI, R_NO_VAR, R_TYPE, CtTest, CtVar, Skip, match)


def _row(row: int, function: str, variable: str, direction: str = 'in', file: str = '') -> ListRow:
    return ListRow(row, function, variable, direction, file=file)


def _test(key: str, function: str, file: str = 'dmy_io.c', **variables: CtVar) -> CtTest:
    return CtTest(key, function, file, variables)


class MatchTest(unittest.TestCase):
    def test_applies_listed_variables(self) -> None:
        t = _test('k1', 'dmy_calc', dmy_a=CtVar('dmy_a', ''), dmy_b=CtVar('dmy_b', 'in'))
        got = match([_row(2, 'dmy_calc', 'dmy_a', 'in'), _row(3, 'dmy_calc', 'dmy_b', 'out')], [t])
        self.assertEqual(got.applied, {'k1': {'dmy_a': 'in', 'dmy_b': 'out'}})
        self.assertEqual((got.assigned, got.skips, got.tests_total), (2, [], 1))

    def test_function_not_exported_is_not_a_skip(self) -> None:
        got = match([_row(2, 'dmy_ghost', 'dmy_a')], [])
        self.assertEqual((got.not_exported, got.skips), (['dmy_ghost'], []))

    def test_exported_test_without_rows_is_unlisted(self) -> None:
        got = match([], [_test('k1', 'dmy_other')])
        self.assertEqual((got.unlisted, got.applied), (['dmy_other'], {}))

    def test_same_name_functions_need_file(self) -> None:
        a = _test('ka', 'dmy_f', 'src\\a.c', dmy_x=CtVar('dmy_x', ''))
        b = _test('kb', 'dmy_f', 'src\\b.c', dmy_x=CtVar('dmy_x', ''))
        got = match([_row(2, 'dmy_f', 'dmy_x'), _row(3, 'dmy_f', 'dmy_x', 'out', file='B.C')], [a, b])
        self.assertEqual(got.skips, [Skip(2, 'dmy_f', 'dmy_x', R_MULTI)])
        self.assertEqual(got.applied, {'kb': {'dmy_x': 'out'}})

    def test_file_mismatch_with_single_test_is_not_exported(self) -> None:
        # 파일이 다른 같은 이름 함수만 내보냈으면 그 테스트를 바꾸지 않는다
        a = _test('ka', 'dmy_f', 'src\\a.c', dmy_x=CtVar('dmy_x', ''))
        got = match([_row(2, 'dmy_f', 'dmy_x', file='b.c')], [a])
        self.assertEqual((got.applied, got.not_exported, got.skips), ({}, ['dmy_f'], []))

    def test_file_unknown_in_test_still_applies(self) -> None:
        t = _test('k1', 'dmy_f', '', dmy_x=CtVar('dmy_x', ''))
        got = match([_row(2, 'dmy_f', 'dmy_x', file='b.c')], [t])
        self.assertEqual(got.applied, {'k1': {'dmy_x': 'in'}})

    def test_unknown_variable_skipped(self) -> None:
        got = match([_row(2, 'dmy_calc', 'dmy_typo')], [_test('k1', 'dmy_calc')])
        self.assertEqual(got.skips, [Skip(2, 'dmy_calc', 'dmy_typo', R_NO_VAR)])

    def test_unsupported_kind_skipped(self) -> None:
        t = _test('k1', 'dmy_calc', dmy_s=CtVar('dmy_s', '', supported=False))
        self.assertEqual(match([_row(2, 'dmy_calc', 'dmy_s')], [t]).count(R_TYPE), 1)

    def test_values_block_direction_change_without_reset(self) -> None:
        t = _test('k1', 'dmy_calc', dmy_v=CtVar('dmy_v', 'in', has_values=True))
        self.assertEqual(match([_row(2, 'dmy_calc', 'dmy_v', 'out')], [t]).count(R_HAS_VALUES), 1)
        self.assertEqual(match([_row(2, 'dmy_calc', 'dmy_v', 'in')], [t]).applied,
                         {'k1': {'dmy_v': 'in'}})

    def test_reset_cases_ignores_values(self) -> None:
        t = _test('k1', 'dmy_calc', dmy_v=CtVar('dmy_v', 'in', has_values=True))
        got = match([_row(2, 'dmy_calc', 'dmy_v', 'out')], [t], reset_cases=True)
        self.assertEqual(got.applied, {'k1': {'dmy_v': 'out'}})

    def test_duplicate_rows_same_direction_count_once(self) -> None:
        t = _test('k1', 'dmy_calc', dmy_a=CtVar('dmy_a', ''))
        got = match([_row(2, 'dmy_calc', 'dmy_a'), _row(5, 'dmy_calc', 'dmy_a')], [t])
        self.assertEqual((got.assigned, got.skips), (1, []))

    def test_conflicting_rows_all_skipped(self) -> None:
        t = _test('k1', 'dmy_calc', dmy_a=CtVar('dmy_a', ''))
        got = match([_row(2, 'dmy_calc', 'dmy_a', 'in'), _row(3, 'dmy_calc', 'dmy_a', 'out')], [t])
        self.assertEqual([s.row for s in got.skips], [2, 3])
        self.assertEqual({s.reason for s in got.skips}, {R_CONFLICT})
        self.assertEqual(got.applied, {})

    def test_skips_sorted_by_row(self) -> None:
        got = match([_row(9, 'dmy_calc', 'dmy_z'), _row(4, 'dmy_calc', 'dmy_y')],
                    [_test('k1', 'dmy_calc')])
        self.assertEqual([s.row for s in got.skips], [4, 9])


if __name__ == '__main__':
    unittest.main()
