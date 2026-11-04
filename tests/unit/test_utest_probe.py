"""tools/utest_probe.py 단위 테스트 (stdlib unittest). Java가 없어 직렬화 바이트를 손으로 짓는다.

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import contextlib
import io
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import utest_probe  # noqa: E402
from test_ct_export import _csv  # noqa: E402
from test_member_probe import _put  # noqa: E402

END, NULL = b'\x78', b'\x70'


def _utf(text: str) -> bytes:
    data = text.encode('utf-8')
    return struct.pack('>H', len(data)) + data


def _str(text: str) -> bytes:
    return b'\x74' + _utf(text)


def _ref(handle: int) -> bytes:
    return b'\x71' + struct.pack('>i', 0x7E0000 + handle)


def _desc(name: str, flags: int, fields: bytes, count: int, super_: bytes = NULL) -> bytes:
    return b'\x72' + _utf(name) + b'\0' * 8 + bytes([flags]) + struct.pack('>h', count) + fields + END + super_


def _var(first: bool, checked: bool, direction: str, name: str) -> bytes:
    """UtVar 객체. 처음이면 클래스 설명(h7, 타입 글자열 h8, 열거 설명 h10·h11)을 새로 쓰고 아니면 참조한다."""
    if first:  # h7 UtVar 설명, h8 'Lcom/dmy/Dir;', h9 객체
        desc = _desc('com.dmy.UtVar', 0x02, b'Z' + _utf('checked') + b'L' + _utf('dir') + _str('Lcom/dmy/Dir;')
                     + b'L' + _utf('vname') + _ref(1), 3)
        # h10 Dir 설명, h11 Enum 설명, h12 열거 객체, h13 상수 이름, h14 vname
        enum_desc = _desc('com.dmy.Dir', 0x12, b'', 0, _desc('java.lang.Enum', 0x12, b'', 0))
    else:
        desc, enum_desc = _ref(7), _ref(10)
    return (b'\x73' + desc + bytes([checked]) + b'\x7e' + enum_desc + _str(direction) + _str(name))


def _stream(checked: bool = False, extra: bool = False) -> bytes:
    """UtTest{count, name, vars: ArrayList[UtVar…]}, 기본형 배열 하나, 블록 하나, 가릴 글자열 하나."""
    ut = _desc('com.dmy.UtTest', 0x02, b'I' + _utf('count') + b'L' + _utf('name') + _str('Ljava/lang/String;')
               + b'L' + _utf('vars') + _str('Ljava/util/ArrayList;'), 3)  # h0, h1, h2; 객체 h3
    items = [_var(True, checked, 'NONE', 'dmy_c_direct')] + ([_var(False, True, 'OUT', 'dmy_c_unused')] if extra else [])
    array_list = (b'\x73' + _desc('java.util.ArrayList', 0x03, b'I' + _utf('size'), 1)  # h5, 객체 h6
                  + struct.pack('>i', len(items)) + b'\x77\x04' + struct.pack('>i', len(items)) + b''.join(items) + END)
    body = b'\x73' + ut + struct.pack('>i', 7) + _str('C:\\secret_dir\\dmy_carry.c') + array_list
    ints = b'\x75' + _desc('[I', 0x02, b'', 0) + struct.pack('>i', 2) + struct.pack('>ii', 1, 2)
    return b'\xac\xed\x00\x05' + body + ints + b'\x77\x02ab' + _str('secret_account')


class UtestProbeTest(unittest.TestCase):
    def test_parse_reads_fields_strings_enums_and_lists(self) -> None:
        listed = utest_probe.parse(_stream())
        self.assertTrue(any(p == '' and v.startswith('array [I len 2') for p, v, _ in listed))
        leaves = {p: v for p, v, _ in listed}
        self.assertEqual(leaves['/UtTest.count'], '7')
        self.assertEqual(leaves['/UtTest.name'], '~A:\\aaaaaa_aaa\\dmy_carry.a')
        var = '/UtTest.vars/ArrayList.@/UtVar'
        self.assertEqual(leaves[var + '.checked'], 'false')
        self.assertEqual(leaves[var + '.dir'], 'enum Dir.NONE')
        self.assertEqual(leaves[var + '.vname'], '"dmy_c_direct"')
        self.assertEqual(leaves['/UtTest.vars/ArrayList.size'], '1')
        self.assertEqual(leaves[''], '~aaaaaa_aaaaaaa')  # 맨 끝 글자열 secret_account는 모양만

    def test_diff_shows_flag_change_and_inserted_variable(self) -> None:
        summary, lines = utest_probe.diff_lines(utest_probe.parse(_stream()),
                                                utest_probe.parse(_stream(checked=True, extra=True)))
        self.assertIn('- /UtTest.vars/ArrayList.@/UtVar.checked = false', lines)
        self.assertIn('+ /UtTest.vars/ArrayList.@/UtVar.checked = true', lines)
        self.assertIn('+ /UtTest.vars/ArrayList.@/UtVar.vname = "dmy_c_unused"', lines)
        self.assertIn('+ /UtTest.vars/ArrayList.@/UtVar.dir = enum Dir.OUT', lines)
        self.assertTrue(summary.startswith('다른 곳 '))

    def test_bad_stream_reports_kind_and_position(self) -> None:
        with self.assertRaises(utest_probe.UtestError) as caught:
            utest_probe.parse(b'not java')
        self.assertEqual(caught.exception.kind, 'Java 직렬화 머리가 아님')
        with self.assertRaises(utest_probe.UtestError) as caught:
            utest_probe.parse(_stream()[:40])
        self.assertEqual(caught.exception.kind, '끝이 잘림')

    def test_show_keeps_only_sample_names_and_c_words(self) -> None:
        self.assertEqual(utest_probe.show('dmy_carry(signed int)'), '"dmy_carry(signed int)"')
        self.assertEqual(utest_probe.show('ACCOUNT'), '~AAAAAAA')
        self.assertEqual(utest_probe.show('C:\\a'), '~A:\\a')
        self.assertEqual(utest_probe.show('2026-11-04 12:09'), '~9999-99-99 99:99')
        self.assertEqual(utest_probe.show('*com.codescroll.ut.UtTest'), '~*com.codescroll.ut.UtTest')
        self.assertEqual(utest_probe.show('x' * 70), '~' + 'a' * 60 + '…70')
        self.assertEqual(utest_probe.show('계정'), '~??')

    def test_layout_shows_bytes_around_names_without_secret(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        before, after = Path(tmp.name) / 'secret_a', Path(tmp.name) / 'secret_b'
        head = b'\x00\x01\x2acom.codescroll.ut.UtTest\x05secret_user\x01'
        _put(before, 'dmy_carry_test0.utest', head + b'\x0cdmy_c_direct\x00\x01')
        _put(after, 'dmy_carry_test0.utest', head + b'\x0cdmy_c_direct\x00\x02\x0cdmy_c_callee\x00\x02'
             + b'\x0cdmy_c_unused\x03')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = utest_probe.main([str(before), str(after), '--layout'])
        out = buf.getvalue()
        self.assertEqual(code, 0, out)
        self.assertNotIn('secret', out)
        self.assertIn('처음 앞부분: x 00 01 | t ~*com.codescroll.ut.UtTest', out)
        self.assertIn('t ~aaaaaa_aaaa', out)
        self.assertIn('처음 dmy_c_direct 둘레: ', out)
        self.assertIn('체크한 뒤 dmy_c_callee 둘레: ', out)
        self.assertIn('체크한 뒤 dmy_c_unused 둘레: ', out)
        self.assertTrue(all(len(line) <= 120 for line in out.splitlines()))

    def test_main_prints_counts_and_no_secret(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / 'secret_root'
        before, after = root / '17', root / '18'
        header = ',<input>,dmy_v,<expect>,dmy_c_direct,returnVar'
        for folder, data in ((before, _stream()), (after, _stream(checked=True, extra=True))):
            _put(folder, 'dmy_carry_test0.csv', _csv(name='dmy_carry_test0', header=header))
            _put(folder, 'dmy_carry_test0.utest', data)
        buf = io.StringIO()
        with mock.patch.object(utest_probe.tempfile, 'gettempdir', return_value=tmp.name), \
                contextlib.redirect_stdout(buf):
            code = utest_probe.main([str(before), str(after)])
        out = buf.getvalue()
        self.assertEqual(code, 0, out)
        self.assertNotIn('secret', out)
        self.assertIn('이름 있음: dmy_c_direct(Java 글자열)  없음: dmy_c_callee', out)
        self.assertIn('dmy_c_unused(Java 글자열)', out)
        self.assertIn('꼴 Java 직렬화', out)
        self.assertIn('다른 곳 ', out)
        self.assertTrue(all(len(line) <= 120 for line in out.splitlines()))
        self.assertTrue((Path(tmp.name) / utest_probe.DUMP).is_file())

    def test_unwrap_finds_compressed_or_prefixed_java(self) -> None:
        import gzip
        self.assertEqual(utest_probe.unwrap(gzip.compress(_stream()))[0], 'gzip > Java 직렬화')
        kind, payload = utest_probe.unwrap(b'HDR!' + _stream())
        self.assertEqual(kind, '앞 4바이트 머리 + Java 직렬화')
        self.assertEqual(payload, _stream())
        self.assertEqual(utest_probe.unwrap(b'\x01\x02xyz')[0], '모름')

    def test_found_as_tells_how_the_name_is_written(self) -> None:
        self.assertEqual(utest_probe.found_as(b'\x05dmy_c_p\x07', [], 'dmy_c_p'), '그대로')
        self.assertEqual(utest_probe.found_as(b'\x05dmy_c_ptr\x07', [], 'dmy_c_p'), '')
        self.assertEqual(utest_probe.found_as(b'\x01dmy_c_' + bytes([ord('p') | 0x80]), [], 'dmy_c_p'), 'Kryo')
        self.assertEqual(utest_probe.found_as('dmy_c_p'.encode('utf-16-le'), [], 'dmy_c_p'), 'UTF-16')

    def test_classes_skip_domains(self) -> None:
        data = b'\x01com.codescroll.ut.UtTest\x02mail.secret.co.kr\x03secret@corp.example.com\x04'
        self.assertEqual(utest_probe.classes(data), ['com.codescroll.ut.UtTest'])

    def test_main_unknown_format_compares_tokens_without_secret(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        before, after = Path(tmp.name) / 'secret_a', Path(tmp.name) / 'secret_b'
        head = b'\x89UT\x01' + b'C:\\secret\\x.c' + b'\x00com.codescroll.ut.UtVar\x01'
        for folder, body in ((before, b'dmy_c_direct\x00\x01'),
                             (after, b'dmy_c_direct\x00\x02\x09dmy_c_callee\x00\x02')):
            _put(folder, 'dmy_carry_test0.utest', head + body)
        buf = io.StringIO()
        with mock.patch.object(utest_probe.tempfile, 'gettempdir', return_value=tmp.name), \
                contextlib.redirect_stdout(buf):
            code = utest_probe.main([str(before), str(after)])
        out = buf.getvalue()
        self.assertEqual(code, 0, out)
        self.assertNotIn('secret', out)
        self.assertIn('꼴 모름', out)
        self.assertIn('클래스 이름 꼴 1: com.codescroll.ut.UtVar', out)
        self.assertIn('바이트 낱개 비교: ', out)
        self.assertIn('@ t "dmy_c_direct"  - x 00 01  + x 00 02 09 / t "dmy_c_callee" / x 00 02', out)

    def test_main_needs_one_utest_per_folder(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = utest_probe.main([str(Path(tmp.name) / 'secret_a'), str(Path(tmp.name) / 'secret_b')])
        self.assertEqual(code, 1)
        self.assertIn('처음 폴더의 dmy_carry 테스트 .utest가 0개', buf.getvalue())
        self.assertNotIn('secret', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
