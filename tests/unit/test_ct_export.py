"""ct_toolkit.ct_export 읽기·사본 쓰기 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from ct_toolkit import ct_export  # noqa: E402
from ct_toolkit.ct_export import (  # noqa: E402
    E_EXPORT_EMPTY, E_EXPORT_OPEN, ExportError, decode_csv, split_fields, symbol_variable)
from ct_toolkit.io_list import ListRow  # noqa: E402
from ct_toolkit.io_match import R_HAS_VALUES, match  # noqa: E402

# `load_tests`를 이름으로 가져오면 unittest가 테스트 불러오기 훅으로 오해하므로 모듈로 부른다.
load = ct_export.load_tests

HEADER = (',<input>,dmy_count,dmy_gain,dmy_hist[0],dmy_limit.dmy_hi,dmy_limit.dmy_lo,dmy_mode,'
          'dmy_ptr_mem[0],dmy_spare,dmy_x,<expect>,dmy_count,dmy_hist[0],dmy_level,returnVar,'
          '<output>,dmy_count,dmy_hist[0],dmy_level,returnVar,<toutput>,dmy_count,dmy_hist[0],'
          'dmy_level,returnVar')
UTEST = (b'\xac\xed\x00\x05' + b'\x00\x28dmy_calc(signed int, const signed int *)'
         + b'\x00\x18C:\\ctsample\\src\\dmy_io.c')


def _java_string(text: bytes) -> bytes:
    """Java 직렬화 문자열: 2바이트 big-endian 길이 + 바이트."""
    return len(text).to_bytes(2, 'big') + text


def _case(header: str = HEADER, values: Optional[dict] = None) -> str:
    """값 없는 케이스 줄. `values`는 {칸 번호: 값}."""
    fields = ['1', '""'] + [''] * (len(split_fields(header)) - 2)
    for index, value in (values or {}).items():
        fields[index] = value
    return ','.join(fields)


MIXED_HEADER = ',<input>,dmy_in,dmy_ok,st.cnt,st.mode,<expect>,dmy_ok,st.cnt'  # st.mode는 입력에만
CASE_NAMES = ('"#ID#a,b#ID#"', '"#ID#견본#ID#"')


def _sample_text(header: str = HEADER, values: Optional[dict] = None, eol: str = '\r\n') -> str:
    """견본 CSV 글: 케이스 두 줄(이름은 쉼표가 든 것과 한글). `values`는 {칸 번호: 값}."""
    lines = ['CT(Controller Tester) Test Data', 'test name:dmy_calc_test0,""', header]
    for name in CASE_NAMES:
        fields = split_fields(_case(header, values))
        fields[1] = name
        lines.append(','.join(fields))
    return eol.join(lines) + eol


def _column(header: List[str], section: str, symbol: str) -> int:
    """그 구역 안의 기호 칸 번호."""
    return header.index(symbol, header.index(section))


def _by_section(header_line: str) -> Dict[str, List[str]]:
    """구역 표시 -> 그 구역의 기호들(머리글 순서)."""
    found: Dict[str, List[str]] = {}
    section: List[str] = []
    for cell in split_fields(header_line)[1:]:
        if cell.startswith('<'):
            section = found.setdefault(cell, [])
        else:
            section.append(cell)
    return found


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

    def test_renamed_lists_tests_whose_name_is_not_function_test_number(self) -> None:
        self._sample(project='good')
        self._sample(name='renamed', project='by_utest')  # 함수는 .utest에서 찾는다
        self._sample(name='secret_other', project='no_utest', utest=None)  # 함수도 못 찾는다
        self._sample(name='dmy_calc_test', project='no_number')
        self._sample(name='dmy_calc_test1x', project='trailing')
        got = load(self.root)
        self.assertEqual(got.renamed, [
            'by_utest/UnitTests/dmy_calc_test0.csv', 'no_number/UnitTests/dmy_calc_test0.csv',
            'no_utest/UnitTests/dmy_calc_test0.csv', 'trailing/UnitTests/dmy_calc_test0.csv'])
        self.assertEqual(len(got.tests), 5)  # 맞춰 보기는 그대로 읽는다
        self.assertEqual({t.key: t.function for t in got.tests}['by_utest/UnitTests/dmy_calc_test0.csv'],
                         'dmy_calc')

    def test_well_formed_test_names_are_not_renamed(self) -> None:
        self._sample(name='dmy_calc_test12', project='a')
        self._sample(name='dmy_calc_test_test3', project='b')
        self.assertEqual(load(self.root).renamed, [])

    def test_utest_function_ignores_letter_length_byte(self) -> None:
        signature = b'dmy_calc(' + b'x' * 78 + b')'  # 88바이트라 길이 바이트가 'X'
        self.assertEqual(_java_string(signature)[:2], b'\x00X')
        utest = b'\xac\xed\x00\x05' + _java_string(signature)
        self.assertEqual(self._only(name='renamed', utest=utest).function, 'dmy_calc')

    def test_utest_function_string_may_continue_after_paren(self) -> None:
        utest = b'\xac\xed\x00\x05' + _java_string(b'dmy_calc(signed int, const signed int *)_0')
        self.assertEqual(self._only(name='renamed', utest=utest).function, 'dmy_calc')

    def test_utest_function_needs_matching_length(self) -> None:
        utest = b'\xac\xed\x00\x05\x00\x00\x00dmy_calc(a)'  # 앞 두 바이트가 길이로 안 맞는다
        self.assertEqual(self._only(name='renamed', utest=utest).function, 'renamed')

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

    def test_struct_members_in_different_sections_are_mixed(self) -> None:
        # 멤버 하나는 입력·기대값에, 다른 하나는 입력에만 있다: 한 방향으로 말할 수 없다
        test = self._only(header=MIXED_HEADER)
        self.assertEqual(test.variables['st'].direction, 'mixed')
        self.assertEqual(test.variables['dmy_ok'].direction, 'inout')
        self.assertEqual(test.variables['dmy_in'].direction, 'in')

    def test_mixed_struct_gets_every_member_in_the_listed_sections(self) -> None:
        test = self._only(header=MIXED_HEADER)
        got = match([ListRow(2, 'dmy_calc', 'st', 'inout')], [test])
        self.assertEqual((got.changes, got.skips), ({test.key: {'st': 'inout'}}, []))
        lines = ct_export.rewrite_csv(
            _sample_text(MIXED_HEADER), got.edits[test.key], True).split('\r\n')
        sections = _by_section(lines[2])
        for section in ('<input>', '<expect>', '<output>', '<toutput>'):
            self.assertTrue({'st.cnt', 'st.mode'} <= set(sections[section]), section)

    def test_mixed_struct_with_values_is_skipped_without_reset(self) -> None:
        mode = split_fields(MIXED_HEADER).index('st.mode')
        test = self._only(header=MIXED_HEADER, case=_case(MIXED_HEADER, {mode: '5'}))
        self.assertTrue(test.variables['st'].has_values)
        got = match([ListRow(2, 'dmy_calc', 'st', 'inout')], [test])
        self.assertEqual([s.reason for s in got.skips], [R_HAS_VALUES])
        self.assertEqual((got.applied, got.changes), ({}, {}))
        self.assertNotIn('st', got.edits.get(test.key, {}))  # 값을 잃지 않게 지정을 그대로 둔다
        reset = match([ListRow(2, 'dmy_calc', 'st', 'inout')], [test], True)
        self.assertEqual(reset.changes, {test.key: {'st': 'inout'}})

    def test_unlisted_mixed_variable_is_released(self) -> None:
        test = self._only(header=MIXED_HEADER)
        got = match([ListRow(2, 'dmy_calc', 'dmy_ok', 'inout')], [test])
        self.assertIn('st', got.released[test.key])

    def test_unknown_section_symbols_are_not_variables(self) -> None:
        header = HEADER.replace(',<output>,', ',<stub>,dmy_stub_ret,<output>,', 1)
        test = self._only(header=header)
        self.assertNotIn('dmy_stub_ret', test.variables)
        self.assertEqual(test.variables['return'].direction, 'out')

    def test_repeated_known_section_marker_is_unreadable(self) -> None:
        self._sample(project='good')
        for marker in ('<input>', '<expect>', '<output>', '<toutput>'):
            self._put('bad/{}.csv'.format(marker[1:-1]),
                      _csv(header=HEADER + ',{},dmy_extra'.format(marker)))
        got = load(self.root)
        self.assertEqual(got.unreadable,
                         ['bad/expect.csv', 'bad/input.csv', 'bad/output.csv', 'bad/toutput.csv'])
        self.assertEqual([t.key for t in got.tests], ['good/UnitTests/dmy_calc_test0.csv'])

    def test_repeated_unknown_section_marker_is_readable(self) -> None:
        test = self._only(header=HEADER + ',<stub>,dmy_a,<stub>,dmy_b')
        self.assertEqual(test.variables['dmy_x'].direction, 'in')

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


class RewriteTest(unittest.TestCase):
    def _rewrite(self, directions: dict, reset: bool = False, text: Optional[str] = None) -> str:
        return ct_export.rewrite_csv(_sample_text() if text is None else text, directions, reset)

    def test_no_change_is_identical(self) -> None:
        text = _sample_text()
        self.assertEqual(self._rewrite({}), text)
        self.assertEqual(self._rewrite({'secret_absent': 'out'}), text)
        self.assertEqual(self._rewrite({'dmy_gain': 'in'}), text)  # 지금과 같은 지정
        self.assertEqual(self._rewrite({'dmy_count': 'inout', 'dmy_level': 'out'}), text)
        bare = text.rstrip('\r\n')
        self.assertEqual(self._rewrite({}, text=bare), bare)
        self.assertEqual(self._rewrite({'dmy_count': 'inout'}, text=bare), bare)

    def test_change_keeps_line_ending_and_missing_final_one(self) -> None:
        change = {'dmy_count': 'out'}
        lf = self._rewrite(change, text=_sample_text(eol='\n'))
        self.assertNotIn('\r', lf)
        self.assertTrue(lf.endswith('\n'))
        self.assertEqual(len(lf.split('\n')), 6)  # 줄 다섯과 끝의 빈 조각
        bare = self._rewrite(change, text=_sample_text().rstrip('\r\n'))
        self.assertFalse(bare.endswith('\n'))
        self.assertEqual(len(bare.split('\r\n')), 5)
        self.assertEqual(bare.count('\n'), bare.count('\r\n'))

    def test_inout_to_out_removes_from_input(self) -> None:
        got = self._rewrite({'dmy_count': 'out', 'dmy_hist': 'out', 'dmy_spare': ''})
        lines = got.split('\r\n')
        self.assertEqual(lines[:2], _sample_text().split('\r\n')[:2])
        self.assertEqual(lines[2], (
            ',<input>,dmy_gain,dmy_limit.dmy_hi,dmy_limit.dmy_lo,dmy_mode,dmy_ptr_mem[0],dmy_x,'
            '<expect>,dmy_count,dmy_hist[0],dmy_level,returnVar,'
            '<output>,dmy_count,dmy_hist[0],dmy_level,returnVar,'
            '<toutput>,dmy_count,dmy_hist[0],dmy_level,returnVar'))

    def test_in_to_out_keeps_sorted_order(self) -> None:
        sections = _by_section(self._rewrite({'dmy_gain': 'out'}).split('\r\n')[2])
        self.assertEqual(sections['<expect>'],
                         ['dmy_count', 'dmy_gain', 'dmy_hist[0]', 'dmy_level', 'returnVar'])
        self.assertEqual(sections['<output>'], sections['<expect>'])
        self.assertEqual(sections['<toutput>'], sections['<expect>'])
        self.assertNotIn('dmy_gain', sections['<input>'])

    def test_untouched_symbols_keep_their_order(self) -> None:
        header = ',<input>,dmy_x,dmy_y,<expect>,dmy_a,dmy_x'
        got = self._rewrite({'dmy_y': 'out'}, text=_sample_text(header))
        sections = _by_section(got.split('\r\n')[2])
        self.assertEqual(sections['<input>'], ['dmy_x'])
        self.assertEqual(sections['<expect>'], ['dmy_a', 'dmy_x', 'dmy_y'])

    def test_unsorted_section_gets_joiners_at_its_end(self) -> None:
        header = ',<input>,dmy_b,dmy_a,<expect>,dmy_z,dmy_y'
        one = self._rewrite({'dmy_a': 'inout'}, text=_sample_text(header))
        self.assertEqual(one.split('\r\n')[2], (
            ',<input>,dmy_b,dmy_a,<expect>,dmy_z,dmy_y,dmy_a,<output>,dmy_a,<toutput>,dmy_a'))
        two = self._rewrite({'dmy_a': 'inout', 'dmy_b': 'inout'}, text=_sample_text(header))
        self.assertEqual(_by_section(two.split('\r\n')[2])['<expect>'],
                         ['dmy_z', 'dmy_y', 'dmy_b', 'dmy_a'])  # 머리글에 처음 나온 순서
        gone = self._rewrite({'dmy_a': ''}, text=_sample_text(header))
        self.assertEqual(gone.split('\r\n')[2], ',<input>,dmy_b,<expect>,dmy_z,dmy_y')

    def test_section_without_change_stays_as_it_was(self) -> None:
        header = ',<input>,dmy_b,dmy_a,<expect>,dmy_z,dmy_y'
        got = self._rewrite({'dmy_z': 'inout'}, text=_sample_text(header))
        self.assertEqual(_by_section(got.split('\r\n')[2])['<input>'], ['dmy_b', 'dmy_a', 'dmy_z'])
        self.assertEqual(_by_section(got.split('\r\n')[2])['<expect>'], ['dmy_z', 'dmy_y'])

    def test_out_to_inout_adds_to_input(self) -> None:
        sections = _by_section(self._rewrite({'return': 'inout'}).split('\r\n')[2])
        self.assertEqual(sections['<input>'][-1], 'returnVar')
        self.assertIn('returnVar', sections['<expect>'])
        self.assertIn('returnVar', sections['<toutput>'])

    def test_values_follow_their_columns(self) -> None:
        old = split_fields(HEADER)
        old_x = _column(old, '<input>', 'dmy_x')
        values = {old_x: '7', _column(old, '<expect>', 'dmy_level'): '3',
                  _column(old, '<output>', 'returnVar'): '9'}
        got = self._rewrite({'dmy_count': 'out', 'dmy_spare': ''}, text=_sample_text(values=values))
        lines = got.split('\r\n')
        header = split_fields(lines[2])
        x = _column(header, '<input>', 'dmy_x')
        self.assertNotEqual(x, old_x)
        for row, name in zip(lines[3:5], CASE_NAMES):
            fields = split_fields(row)
            self.assertEqual(len(fields), len(header))
            self.assertEqual((fields[0], fields[header.index('<input>')]), ('1', name))
            self.assertEqual(fields[x], '7')
            self.assertEqual(fields[_column(header, '<expect>', 'dmy_level')], '3')
            self.assertEqual(fields[_column(header, '<output>', 'returnVar')], '9')
            self.assertEqual(sum(1 for f in fields if f), 5)  # 번호, 이름, 값 셋뿐
        self.assertEqual(lines[5:], [''])

    def test_reset_cases_leaves_one_empty_case(self) -> None:
        old = split_fields(HEADER)
        text = _sample_text(values={_column(old, '<input>', 'dmy_x'): '7'})
        lines = self._rewrite({'dmy_gain': 'out'}, True, text).split('\r\n')
        width = len(split_fields(lines[2]))
        self.assertEqual(lines[3:], ['1,""' + ',' * (width - 2), ''])
        self.assertEqual(lines[:2], text.split('\r\n')[:2])

    def test_reset_cases_keeps_line_ending_and_missing_final_one(self) -> None:
        got = self._rewrite({}, True, _sample_text(eol='\n'))
        self.assertNotIn('\r', got)
        self.assertEqual(len(got.split('\n')), 5)  # 줄 넷과 끝의 빈 조각
        bare = self._rewrite({}, True, _sample_text().rstrip('\r\n'))
        self.assertEqual(len(bare.split('\r\n')), 4)
        self.assertFalse(bare.endswith('\n'))

    def test_unknown_section_kept(self) -> None:
        header = HEADER + ',<stub>,dmy_stub_ret'
        stub = len(split_fields(HEADER)) + 1
        got = self._rewrite({'dmy_count': 'out'}, text=_sample_text(header, {stub: 'v'}))
        lines = got.split('\r\n')
        self.assertEqual(split_fields(lines[2])[-2:], ['<stub>', 'dmy_stub_ret'])
        self.assertEqual(split_fields(lines[3])[-1], 'v')
        self.assertNotIn('dmy_stub_ret', _by_section(lines[2])['<toutput>'])

    def test_unknown_section_in_the_middle_keeps_place(self) -> None:
        got = self._rewrite({'a': 'out'}, text=_sample_text(',<input>,a,<stub>,s,<expect>,b'))
        self.assertEqual(got.split('\r\n')[2],
                         ',<input>,<stub>,s,<expect>,a,b,<output>,a,<toutput>,a')

    def test_missing_expect_section_added(self) -> None:
        got = self._rewrite({'b': 'out'}, text=_sample_text(',<input>,a,b'))
        lines = got.split('\r\n')
        self.assertEqual(lines[2], ',<input>,a,<expect>,b,<output>,b,<toutput>,b')
        self.assertEqual([len(split_fields(row)) for row in lines[3:5]], [9, 9])

    def test_missing_input_section_takes_the_case_name_column(self) -> None:
        got = self._rewrite({'a': 'inout'}, text=_sample_text(',<expect>,a', {2: '5'}))
        lines = got.split('\r\n')
        self.assertEqual(lines[2], ',<input>,a,<expect>,a,<output>,a,<toutput>,a')
        self.assertEqual(split_fields(lines[3]), ['1', CASE_NAMES[0], '', '', '5', '', '', '', ''])
        reset = self._rewrite({'a': 'inout'}, True, _sample_text(',<expect>,a')).split('\r\n')
        self.assertEqual(reset[3], '1,"",,,,,,,')

    def test_blank_header_cell_keeps_its_column_and_values(self) -> None:
        header = ',<input>,a,,b,<expect>,c'
        text = _sample_text(header, {3: '9'})  # 빈 머리글 칸 아래의 값
        got = self._rewrite({'a': 'out'}, text=text).split('\r\n')
        new = split_fields(got[2])
        self.assertEqual(got[2], ',<input>,,b,<expect>,a,c,<output>,a,<toutput>,a')
        self.assertEqual(split_fields(got[3])[2], '9')
        self.assertEqual(new[2], '')
        # 그 구역에 변화가 없으면 빈 칸도 제자리다
        got = self._rewrite({'c': ''}, text=text).split('\r\n')
        self.assertEqual(got[2], ',<input>,a,,b,<expect>')
        self.assertEqual(split_fields(got[3])[3], '9')
        # 앞 기호가 구역 끝에 들어올 때는 마지막 기호 뒤(뒤쪽 빈 칸 앞)에 놓인다
        got = self._rewrite({'c': 'inout'}, text=text).split('\r\n')
        self.assertEqual(got[2], ',<input>,a,,b,c,<expect>,c,<output>,c,<toutput>,c')
        self.assertEqual(split_fields(got[3])[3], '9')
        trailing = self._rewrite({'b': 'out'}, text=_sample_text(',<input>,a,b,', {4: '8'}))
        self.assertEqual(trailing.split('\r\n')[2], ',<input>,a,,<expect>,b,<output>,b,<toutput>,b')
        self.assertEqual(split_fields(trailing.split('\r\n')[3])[3], '8')

    def test_case_fields_beyond_the_header_are_kept(self) -> None:
        lines = ['CT(Controller Tester) Test Data', 'test name:x_test0,""', ',<input>,a,b',
                 '1,"",5,6,extra1,extra2']
        got = self._rewrite({'a': 'out'}, text='\r\n'.join(lines) + '\r\n').split('\r\n')
        fields = split_fields(got[3])
        self.assertEqual(got[2], ',<input>,b,<expect>,a,<output>,a,<toutput>,a')
        self.assertEqual(fields[:9], ['1', '""', '6', '', '', '', '', '', ''])
        self.assertEqual(fields[9:], ['extra1', 'extra2'])

    def test_repeated_known_marker_is_not_rewritten(self) -> None:
        text = _sample_text(',<input>,a,<input>,b')
        self.assertEqual(self._rewrite({'a': 'out'}, text=text), text)

    def test_directions_are_validated_first(self) -> None:
        for bad in ('secret', 'OUT', None):
            for text in (_sample_text(), '', 'CT\r\n'):
                with self.assertRaises(ValueError) as ctx:
                    ct_export.rewrite_csv(text, {'dmy_gain': 'in', 'secret_var': bad}, False)
                self.assertEqual(str(ctx.exception), ct_export.E_DIRECTION)
                self.assertNotIn('secret', str(ctx.exception))
        for good in ('in', 'out', 'inout', ''):
            ct_export.rewrite_csv(_sample_text(), {'dmy_gain': good}, False)


class WriteCopyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.export = Path(self._tmp.name) / 'export'
        self.out = Path(self._tmp.name) / 'out'

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _put(self, rel: str, data: bytes) -> Path:
        path = self.export / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def _written(self) -> List[str]:
        return sorted(p.relative_to(self.out).as_posix() for p in self.out.rglob('*') if p.is_file())

    def test_write_copy_only_edits_keeps_relative_path_and_cp949(self) -> None:
        data = _sample_text().encode('cp949')
        key = 'a/UnitTests/dmy_calc_test0.csv'
        for project in ('a', 'b'):
            self._put('{}/UnitTests/dmy_calc_test0.csv'.format(project), data)
            self._put('{}/UnitTests/dmy_calc_test0.utest'.format(project), UTEST)
        self._put('a/testInfo.export', b'<xml/>')
        count = ct_export.write_copy(self.export, self.out, {key: {'dmy_count': 'out'}}, False)
        self.assertEqual(count, 1)
        self.assertEqual(self._written(), [key])
        got = (self.out / key).read_bytes().decode('cp949')
        self.assertIn('견본', got)
        self.assertEqual(got.count('\n'), got.count('\r\n'))
        self.assertEqual(_by_section(got.split('\r\n')[2])['<input>'],
                         ['dmy_gain', 'dmy_hist[0]', 'dmy_limit.dmy_hi', 'dmy_limit.dmy_lo',
                          'dmy_mode', 'dmy_ptr_mem[0]', 'dmy_spare', 'dmy_x'])
        self.assertEqual((self.export / key).read_bytes(), data)  # 내보낸 폴더는 그대로

    def test_unchanged_copy_is_byte_identical(self) -> None:
        text = _sample_text()
        files = {'p/bom.csv': text.encode('utf-8-sig'),
                 'p/bare.csv': text.rstrip('\r\n').encode('cp949'),
                 'p/lf.csv': _sample_text(eol='\n').encode('utf-8')}
        for key, data in files.items():
            self._put(key, data)
        edits = {key: {} for key in files}
        self.assertEqual(ct_export.write_copy(self.export, self.out, edits, False), 3)
        for key, data in files.items():
            self.assertEqual((self.out / key).read_bytes(), data, key)

    def test_utf8_bom_is_written_back_on_change(self) -> None:
        key = 'p/UnitTests/dmy_calc_test0.csv'
        self._put(key, _sample_text().encode('utf-8-sig'))
        ct_export.write_copy(self.export, self.out, {key: {'dmy_spare': ''}}, False)
        written = (self.out / key).read_bytes()
        self.assertTrue(written.startswith(b'\xef\xbb\xbfCT('))
        self.assertNotIn('dmy_spare', written.decode('utf-8-sig'))
        self.assertIn('견본', written.decode('utf-8-sig'))

    def test_missing_original_raises_oserror(self) -> None:
        with self.assertRaises(OSError):
            ct_export.write_copy(self.export, self.out, {'p/none.csv': {'x': 'in'}}, False)


if __name__ == '__main__':
    unittest.main()
