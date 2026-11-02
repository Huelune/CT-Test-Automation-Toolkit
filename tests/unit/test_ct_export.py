"""ct_toolkit.ct_export 읽기 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from ct_toolkit import ct_export  # noqa: E402
from ct_toolkit.ct_export import (  # noqa: E402
    E_EXPORT_EMPTY, E_EXPORT_OPEN, ExportError, decode_csv, split_fields, symbol_variable)

# `load_tests`를 이름으로 가져오면 unittest가 테스트 불러오기 훅으로 오해하므로 모듈로 부른다.
load = ct_export.load_tests

HEADER = (',<input>,dmy_count,dmy_gain,dmy_hist[0],dmy_limit.dmy_hi,dmy_limit.dmy_lo,dmy_mode,'
          'dmy_ptr_mem[0],dmy_spare,dmy_x,<expect>,dmy_count,dmy_hist[0],dmy_level,returnVar,'
          '<output>,dmy_count,dmy_hist[0],dmy_level,returnVar,<toutput>,dmy_count,dmy_hist[0],'
          'dmy_level,returnVar')
UTEST = (b'\xac\xed\x00\x05' + b'\x00\x27dmy_calc(signed int, const signed int *)'
         + b'\x00\x18C:\\ctsample\\src\\dmy_io.c')


def _case(header: str = HEADER, values: Optional[dict] = None) -> str:
    """값 없는 케이스 줄. `values`는 {칸 번호: 값}."""
    fields = ['1', '""'] + [''] * (len(split_fields(header)) - 2)
    for index, value in (values or {}).items():
        fields[index] = value
    return ','.join(fields)


def _csv(name: str = 'dmy_calc_test0', header: str = HEADER, case: Optional[str] = None) -> bytes:
    lines = ['CT(Controller Tester) Test Data', 'test name:{},""'.format(name), header,
             _case(header) if case is None else case]
    return ('\r\n'.join(lines) + '\r\n').encode('cp949')


class SymbolTest(unittest.TestCase):
    def test_symbol_variable(self) -> None:
        for symbol, want in [('dmy_limit.dmy_hi', ('dmy_limit', True)),
                             ('dmy_hist[0]', ('dmy_hist', True)),
                             ('dmy_ptr_mem[0]', ('dmy_ptr_mem', True)),
                             ('returnVar', ('return', True)),
                             ('a[1][2].b', ('a', True)),
                             ('p->x', ('p', False)),
                             ('(*p).x', ('(*p).x', False))]:
            self.assertEqual(symbol_variable(symbol), want, symbol)

    def test_split_fields_keeps_quoted_commas(self) -> None:
        self.assertEqual(split_fields('1,"#ID#a,b#ID#",,7'), ['1', '"#ID#a,b#ID#"', '', '7'])


class DecodeTest(unittest.TestCase):
    def test_decode_csv_encodings(self) -> None:
        self.assertEqual(decode_csv('가a'.encode('utf-8-sig')), ('가a', 'utf-8-sig'))
        self.assertEqual(decode_csv('가a'.encode('utf-8')), ('가a', 'utf-8'))
        self.assertEqual(decode_csv('가a'.encode('cp949')), ('가a', 'cp949'))


class LoadTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _put(self, rel: str, data: bytes) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def _sample(self, name: str = 'dmy_calc_test0', header: str = HEADER,
                case: Optional[str] = None, project: str = 'ctsample',
                utest: Optional[bytes] = UTEST) -> None:
        self._put('{}/UnitTests/dmy_calc_test0.csv'.format(project), _csv(name, header, case))
        if utest is not None:
            self._put('{}/UnitTests/dmy_calc_test0.utest'.format(project), utest)

    def _only(self, **kwargs):
        self._sample(**kwargs)
        got = load(self.root)
        self.assertEqual((len(got.tests), got.unreadable), (1, []))
        return got.tests[0]

    def test_load_groups_symbols_by_variable(self) -> None:
        test = self._only()
        self.assertEqual(set(test.variables), {
            'dmy_count', 'dmy_gain', 'dmy_hist', 'dmy_limit', 'dmy_mode', 'dmy_ptr_mem',
            'dmy_spare', 'dmy_x', 'dmy_level', 'return'})
        self.assertEqual({n: v.direction for n, v in test.variables.items()}, {
            'dmy_count': 'inout', 'dmy_hist': 'inout', 'dmy_gain': 'in', 'dmy_limit': 'in',
            'dmy_mode': 'in', 'dmy_ptr_mem': 'in', 'dmy_spare': 'in', 'dmy_x': 'in',
            'dmy_level': 'out', 'return': 'out'})
        self.assertTrue(all(v.supported and not v.has_values for v in test.variables.values()))

    def test_function_and_file(self) -> None:
        test = self._only()
        self.assertEqual((test.function, test.file, test.key),
                         ('dmy_calc', 'dmy_io.c', 'ctsample/UnitTests/dmy_calc_test0.csv'))

    def test_function_from_utest_when_test_renamed(self) -> None:
        self.assertEqual(self._only(name='renamed').function, 'dmy_calc')

    def test_renamed_without_utest_keeps_test_name(self) -> None:
        test = self._only(name='renamed', utest=None)
        self.assertEqual((test.function, test.file), ('renamed', ''))

    def test_has_values_only_from_input_and_expect(self) -> None:
        fields = split_fields(HEADER)
        gain = fields.index('dmy_gain')
        output_return = [i for i, f in enumerate(fields) if f == 'returnVar'][1]  # <output> 구역
        test = self._only(case=_case(values={gain: '5', output_return: '9'}))
        self.assertTrue(test.variables['dmy_gain'].has_values)
        self.assertFalse(test.variables['return'].has_values)
        self.assertFalse(test.variables['dmy_x'].has_values)

    def test_has_values_from_expect_column(self) -> None:
        fields = split_fields(HEADER)
        expect_level = fields.index('dmy_level')
        test = self._only(case=_case(values={expect_level: '3'}))
        self.assertTrue(test.variables['dmy_level'].has_values)

    def test_unsupported_symbol_marks_variable(self) -> None:
        header = HEADER.replace(',dmy_x,<expect>', ',dmy_x,p->x,<expect>')
        test = self._only(header=header)
        self.assertFalse(test.variables['p'].supported)
        self.assertEqual(test.variables['p'].direction, 'in')
        self.assertTrue(test.variables['dmy_x'].supported)

    def test_two_projects_same_file_name(self) -> None:
        self._sample(project='a')
        self._sample(project='b')
        got = load(self.root)
        self.assertEqual([t.key for t in got.tests],
                         ['a/UnitTests/dmy_calc_test0.csv', 'b/UnitTests/dmy_calc_test0.csv'])

    def test_non_ct_csv_is_unreadable(self) -> None:
        self._sample()
        self._put('other/x.csv', b'a,b\r\n')
        got = load(self.root)
        self.assertEqual(got.unreadable, ['other/x.csv'])
        self.assertEqual(len(got.tests), 1)

    def test_undecodable_csv_is_unreadable(self) -> None:
        self._sample()
        self._put('other/bad.csv', b'\xff\xfe\x80\x81\xff')
        got = load(self.root)
        self.assertEqual(got.unreadable, ['other/bad.csv'])

    def test_utf8_bom_csv_is_read(self) -> None:
        text = _csv().decode('cp949')
        self._put('p/UnitTests/dmy_calc_test0.csv', text.encode('utf-8-sig'))
        got = load(self.root)
        self.assertEqual([t.function for t in got.tests], ['dmy_calc'])

    def test_missing_dir_raises(self) -> None:
        with self.assertRaises(ExportError) as ctx:
            load(self.root / 'secret_missing')
        self.assertEqual(str(ctx.exception), E_EXPORT_OPEN)

    def test_no_readable_csv_raises(self) -> None:
        folders: List[Path] = [self.root / 'empty', self.root / 'not_ct']
        folders[0].mkdir()
        self._put('not_ct/x.csv', b'a,b\r\n')
        for folder in folders:
            with self.assertRaises(ExportError) as ctx:
                load(folder)
            self.assertEqual(str(ctx.exception), E_EXPORT_EMPTY)


if __name__ == '__main__':
    unittest.main()
