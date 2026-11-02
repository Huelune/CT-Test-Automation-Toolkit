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


class PointerNameTest(unittest.TestCase):
    def test_pointer_param_finds_mem_variable(self) -> None:
        t = _test('k', 'dmy_f', dmy_ptr_mem=CtVar('dmy_ptr_mem', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_ptr', 'in')], [t])
        self.assertEqual(got.applied, {'k': {'dmy_ptr_mem': 'in'}})
        self.assertEqual((got.changes, got.skips), ({}, []))

    def test_exact_name_wins_over_mem(self) -> None:
        t = _test('k', 'dmy_f', buf=CtVar('buf', 'in'), buf_mem=CtVar('buf_mem', 'out'))
        got = match([_row(2, 'dmy_f', 'buf', 'out')], [t])
        self.assertEqual(got.applied, {'k': {'buf': 'out'}})
        # 찾지 않은 buf_mem은 목록에 없는 변수로 해제된다
        self.assertEqual(got.released, {'k': ['buf_mem']})

    def test_mem_name_is_only_a_fallback(self) -> None:
        # 목록 이름이 이미 _mem으로 끝나면 그 이름 그대로 찾고, 없으면 변수 없음이다
        t = _test('k', 'dmy_f', dmy_ptr_mem=CtVar('dmy_ptr_mem', ''))
        got = match([_row(2, 'dmy_f', 'dmy_ptr_mem'), _row(3, 'dmy_f', 'dmy_other')], [t])
        self.assertEqual(got.applied, {'k': {'dmy_ptr_mem': 'in'}})
        self.assertEqual(got.skips, [Skip(3, 'dmy_f', 'dmy_other', R_NO_VAR)])

    def test_pointer_and_mem_rows_conflict_on_same_variable(self) -> None:
        # 두 줄이 같은 테스트 변수(dmy_ptr_mem)를 찾으므로 방향이 다르면 뒤 줄이 충돌이다
        t = _test('k', 'dmy_f', dmy_ptr_mem=CtVar('dmy_ptr_mem', ''))
        got = match([_row(2, 'dmy_f', 'dmy_ptr', 'out'), _row(3, 'dmy_f', 'dmy_ptr_mem', 'in')], [t])
        self.assertEqual(got.applied, {'k': {'dmy_ptr_mem': 'out'}})
        self.assertEqual(got.skips, [Skip(3, 'dmy_f', 'dmy_ptr_mem', R_CONFLICT)])


class ChangesAndReleaseTest(unittest.TestCase):
    def test_changes_only_differing(self) -> None:
        t = _test('k', 'dmy_f', dmy_a=CtVar('dmy_a', 'in'), dmy_b=CtVar('dmy_b', 'inout'))
        got = match([_row(2, 'dmy_f', 'dmy_a', 'in'), _row(3, 'dmy_f', 'dmy_b', 'out')], [t])
        self.assertEqual(got.applied, {'k': {'dmy_a': 'in', 'dmy_b': 'out'}})
        self.assertEqual(got.changes, {'k': {'dmy_b': 'out'}})
        self.assertEqual((got.assigned, got.changed_vars), (2, 1))

    def test_unlisted_variable_released(self) -> None:
        t = _test('k', 'dmy_f', dmy_a=CtVar('dmy_a', 'in'), dmy_z=CtVar('dmy_z', 'out'),
                  dmy_spare=CtVar('dmy_spare', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_a', 'in')], [t])
        self.assertEqual(got.released, {'k': ['dmy_spare', 'dmy_z']})  # 이름 순
        self.assertEqual(got.released_vars, 2)
        self.assertEqual(got.edits['k']['dmy_spare'], '')
        self.assertEqual(got.edits['k']['dmy_z'], '')

    def test_unsupported_or_found_but_skipped_not_released(self) -> None:
        t = _test('k', 'dmy_f',
                  dmy_s=CtVar('dmy_s', 'in', supported=False),  # 쓸 줄 모른다
                  dmy_v=CtVar('dmy_v', 'in', has_values=True),  # 값 있음으로 건너뛴다
                  dmy_free=CtVar('dmy_free', ''),  # 지정이 없다
                  dmy_gone=CtVar('dmy_gone', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_v', 'out')], [t])
        self.assertEqual(got.count(R_HAS_VALUES), 1)
        # 건너뛴 줄도 테스트를 골랐으므로 해제는 일어나고, dmy_gone만 대상이다
        self.assertEqual(got.released, {'k': ['dmy_gone']})

    def test_variable_skipped_as_unsupported_not_released(self) -> None:
        t = _test('k', 'dmy_f', dmy_s=CtVar('dmy_s', 'in', supported=False),
                  dmy_gone=CtVar('dmy_gone', 'out'))
        got = match([_row(2, 'dmy_f', 'dmy_s')], [t])
        self.assertEqual(got.count(R_TYPE), 1)
        self.assertEqual(got.released, {'k': ['dmy_gone']})

    def test_unlisted_variable_with_values_is_kept_not_released(self) -> None:
        # 값이 든 변수를 해제하면 값을 잃으므로 해제하지 않고 따로 센다
        t = _test('k', 'dmy_f', dmy_a=CtVar('dmy_a', 'in'),
                  dmy_v=CtVar('dmy_v', 'out', has_values=True), dmy_gone=CtVar('dmy_gone', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_a', 'in')], [t])
        self.assertEqual(got.released, {'k': ['dmy_gone']})
        self.assertEqual((got.kept, got.kept_vars), ({'k': ['dmy_v']}, 1))
        self.assertEqual(got.edits, {'k': {'dmy_gone': ''}})  # kept는 사본에 쓰지 않는다

    def test_reset_cases_releases_variable_with_values(self) -> None:
        t = _test('k', 'dmy_f', dmy_a=CtVar('dmy_a', 'in'),
                  dmy_v=CtVar('dmy_v', 'out', has_values=True))
        got = match([_row(2, 'dmy_f', 'dmy_a', 'in')], [t], reset_cases=True)
        self.assertEqual(got.released, {'k': ['dmy_v']})
        self.assertEqual((got.kept, got.kept_vars), ({}, 0))

    def test_only_row_without_variable_still_releases(self) -> None:
        # 줄이 변수 없음으로 건너뛰어도 그 줄이 테스트를 골랐으므로 해제는 일어난다
        t = _test('k', 'dmy_f', dmy_gone=CtVar('dmy_gone', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_none')], [t])
        self.assertEqual(got.skips, [Skip(2, 'dmy_f', 'dmy_none', R_NO_VAR)])
        self.assertEqual(got.released, {'k': ['dmy_gone']})

    def test_test_without_rows_not_released(self) -> None:
        listed = _test('k1', 'dmy_f', dmy_a=CtVar('dmy_a', 'in'))
        other = _test('k2', 'dmy_other', dmy_x=CtVar('dmy_x', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_a', 'in')], [listed, other])
        self.assertEqual((got.released, got.edits), ({}, {}))
        self.assertEqual(got.unlisted, ['dmy_other'])

    def test_rows_that_pick_no_test_release_nothing(self) -> None:
        # 함수 여럿으로 건너뛴 줄과 내보내지 않은 줄은 테스트를 고르지 못한다
        a = _test('ka', 'dmy_f', 'src\\a.c', dmy_x=CtVar('dmy_x', 'in'))
        b = _test('kb', 'dmy_f', 'src\\b.c', dmy_x=CtVar('dmy_x', 'in'))
        c = _test('kc', 'dmy_g', 'src\\c.c', dmy_x=CtVar('dmy_x', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_y'), _row(3, 'dmy_g', 'dmy_y', file='d.c')], [a, b, c])
        self.assertEqual(got.count(R_MULTI), 1)
        self.assertEqual(got.not_exported, ['dmy_g'])
        self.assertEqual(got.released, {})

    def test_conflicting_list_rows_keep_the_variable(self) -> None:
        # 목록이 충돌해 건너뛴 변수도 목록에 있는 변수라 해제하지 않는다
        t = _test('k', 'dmy_f', dmy_x=CtVar('dmy_x', 'in'), dmy_gone=CtVar('dmy_gone', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_x', 'in'), _row(3, 'dmy_f', 'dmy_x', 'out')], [t])
        self.assertEqual([s.reason for s in got.skips], [R_CONFLICT, R_CONFLICT])
        self.assertEqual(got.released, {'k': ['dmy_gone']})

    def test_variable_of_row_dropped_as_multi_is_not_released(self) -> None:
        # 함수 여럿으로 버려진 줄이 이름 붙인 변수(와 그 _mem)는 다른 줄이 고른 테스트에서도 해제하지 않는다
        a = _test('ka', 'dmy_f', 'src\\a.c')
        b = _test('kb', 'dmy_f', 'src\\b.c', dmy_x=CtVar('dmy_x', ''), dmy_y=CtVar('dmy_y', 'in'),
                  dmy_z_mem=CtVar('dmy_z_mem', 'out'), dmy_gone=CtVar('dmy_gone', 'in'))
        rows = [_row(2, 'dmy_f', 'dmy_y'), _row(3, 'dmy_f', 'dmy_z'),
                _row(4, 'dmy_f', 'dmy_x', 'in', file='b.c')]
        got = match(rows, [a, b])
        self.assertEqual([s.reason for s in got.skips], [R_MULTI, R_MULTI])
        self.assertEqual(got.applied, {'kb': {'dmy_x': 'in'}})
        self.assertEqual(got.released, {'kb': ['dmy_gone']})  # dmy_y, dmy_z_mem은 건드리지 않는다

    def test_variable_of_row_for_other_file_is_not_released(self) -> None:
        # 파일이 달라 내보내지 않은 것으로 센 줄도 그 함수의 줄이다
        a = _test('ka', 'dmy_f', 'src\\a.c', dmy_x=CtVar('dmy_x', ''), dmy_y=CtVar('dmy_y', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_x', 'in', file='a.c'),
                     _row(3, 'dmy_f', 'dmy_y', 'in', file='b.c')], [a])
        self.assertEqual((got.not_exported, got.released), (['dmy_f'], {}))
        self.assertEqual(got.applied, {'ka': {'dmy_x': 'in'}})

    def test_conflict_for_unexported_function_is_not_not_exported(self) -> None:
        got = match([_row(2, 'dmy_f', 'dmy_x', 'in'), _row(3, 'dmy_f', 'dmy_x', 'out')], [])
        self.assertEqual((got.not_exported, got.count(R_CONFLICT)), ([], 2))

    def test_released_test_without_changes_still_in_edits(self) -> None:
        t = _test('k', 'dmy_f', dmy_a=CtVar('dmy_a', 'in'), dmy_spare=CtVar('dmy_spare', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_a', 'in')], [t])
        self.assertEqual(got.changes, {})
        self.assertEqual(got.edits, {'k': {'dmy_spare': ''}})

    def test_edits_merge_changes_and_released(self) -> None:
        t = _test('k', 'dmy_f', dmy_b=CtVar('dmy_b', 'inout'), dmy_spare=CtVar('dmy_spare', 'in'))
        got = match([_row(2, 'dmy_f', 'dmy_b', 'out')], [t])
        self.assertEqual(got.edits, {'k': {'dmy_b': 'out', 'dmy_spare': ''}})
        self.assertEqual(got.changes, {'k': {'dmy_b': 'out'}})  # edits가 changes를 바꾸지 않는다


if __name__ == '__main__':
    unittest.main()
