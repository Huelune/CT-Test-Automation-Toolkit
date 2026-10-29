"""ct_toolkit.io_list 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from ct_toolkit.io_list import (  # noqa: E402
    E_LIST_HEADER, E_LIST_OPEN, E_NO_OPENPYXL, R_LIST_DIRECTION, R_LIST_EMPTY,
    ListError, ListFileError, ListRow, parse_rows, read_list)

HAS_OPENPYXL = importlib.util.find_spec('openpyxl') is not None


class ParseRowsTest(unittest.TestCase):
    def test_reads_rows_by_header_name_in_any_order(self) -> None:
        got = parse_rows([('구분', '기타', '변수', '함수', '범위'),
                          ('입력', 'x', 'dmy_gain', 'dmy_calc', '0~10'),
                          ('입출력', None, 'return', 'dmy_calc', None)])
        self.assertEqual(got.rows, [
            ListRow(2, 'dmy_calc', 'dmy_gain', 'in', range_text='0~10'),
            ListRow(3, 'dmy_calc', 'return', 'inout')])
        self.assertEqual((got.total, got.functions, got.errors), (2, 1, []))

    def test_strips_spaces_keeps_case(self) -> None:
        row = parse_rows([('함수', '변수', '구분'), (' Dmy_Calc ', ' Dmy_A', '출력 ')]).rows[0]
        self.assertEqual((row.function, row.variable, row.direction), ('Dmy_Calc', 'Dmy_A', 'out'))

    def test_blank_rows_ignored(self) -> None:
        got = parse_rows([('함수', '변수', '구분'), (None, None, None), ('', ' ', None),
                          ('dmy_calc', 'dmy_x', '입력')])
        self.assertEqual((got.total, got.rows[0].row), (1, 4))

    def test_missing_required_cell_is_error(self) -> None:
        got = parse_rows([('함수', '변수', '구분'), ('dmy_calc', None, '입력')])
        self.assertEqual(got.errors, [ListError(2, 'dmy_calc', '', R_LIST_EMPTY)])
        self.assertEqual(got.total, 1)

    def test_unknown_direction_is_error(self) -> None:
        got = parse_rows([('함수', '변수', '구분'), ('dmy_calc', 'dmy_x', 'Input')])
        self.assertEqual(got.errors[0].reason, R_LIST_DIRECTION)

    def test_missing_header_raises_fixed_message(self) -> None:
        with self.assertRaises(ListFileError) as ctx:
            parse_rows([('함수', '변수'), ('dmy_calc', 'dmy_x')])
        self.assertEqual(str(ctx.exception), E_LIST_HEADER.format('구분'))

    def test_header_spaces_ok_title_row_rejected(self) -> None:
        self.assertEqual(parse_rows([(' 함수', '변수 ', '구분')]).total, 0)
        with self.assertRaises(ListFileError):
            parse_rows([('입력 목록', None, None), ('함수', '변수', '구분')])

    def test_optional_columns_default_empty(self) -> None:
        row = parse_rows([('함수', '변수', '구분'), ('dmy_calc', 'dmy_x', '입력')]).rows[0]
        self.assertEqual((row.file, row.type_name, row.range_text), ('', '', ''))

    def test_zero_cell_is_text(self) -> None:
        row = parse_rows([('함수', '변수', '구분', '범위'), ('dmy_calc', 'dmy_x', '입력', 0)]).rows[0]
        self.assertEqual(row.range_text, '0')

    def test_duplicate_header_uses_first(self) -> None:
        row = parse_rows([('함수', '변수', '구분', '변수'),
                          ('dmy_calc', 'dmy_x', '입력', 'dmy_y')]).rows[0]
        self.assertEqual(row.variable, 'dmy_x')


class ReadListTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / 'secret_dir'
        self.dir.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_read_list_without_openpyxl(self) -> None:
        def no_module(name: str) -> object:
            raise ImportError(name)
        with self.assertRaises(ListFileError) as ctx:
            read_list(Path('x.xlsx'), importer=no_module)
        self.assertEqual(str(ctx.exception), E_NO_OPENPYXL)

    @unittest.skipUnless(HAS_OPENPYXL, 'openpyxl 없음')
    def test_read_list_missing_file_fixed_message(self) -> None:
        with self.assertRaises(ListFileError) as ctx:
            read_list(self.dir / 'secret_missing.xlsx')
        self.assertEqual(str(ctx.exception), E_LIST_OPEN)
        self.assertNotIn('secret', str(ctx.exception))

    @unittest.skipUnless(HAS_OPENPYXL, 'openpyxl 없음')
    def test_read_list_reads_first_sheet(self) -> None:
        import openpyxl
        book = openpyxl.Workbook()
        book.active.append(['함수', '변수', '구분'])
        book.active.append(['dmy_calc', 'dmy_gain', '입력'])
        other = book.create_sheet('다른 시트')
        other.append(['함수', '변수', '구분'])
        other.append(['dmy_other', 'dmy_x', '출력'])
        other.append(['dmy_other', 'dmy_y', '출력'])
        path = self.dir / 'list.xlsx'
        book.save(str(path))
        got = read_list(path)
        self.assertEqual(got.rows, [ListRow(2, 'dmy_calc', 'dmy_gain', 'in')])

    @unittest.skipUnless(HAS_OPENPYXL, 'openpyxl 없음')
    def test_read_list_not_xlsx_fixed_message(self) -> None:
        path = self.dir / 'list.xlsx'
        path.write_text('secret_text,not,xlsx\n', encoding='utf-8')
        with self.assertRaises(ListFileError) as ctx:
            read_list(path)
        self.assertEqual(str(ctx.exception), E_LIST_OPEN)


if __name__ == '__main__':
    unittest.main()
