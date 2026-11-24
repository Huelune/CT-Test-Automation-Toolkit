"""tools/run_diff_probe.py 부품 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
import run_diff_probe as p  # noqa: E402


class PartsTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_kind(self) -> None:
        text = '가나다'.encode() * 200
        cases = [
            (b'', 'empty'), (b'PK\x03\x04rest', 'zip'), (b'\x1f\x8b\x08', 'gzip'),
            (b'SQLite format 3\x00', 'sqlite'), (b'H:2,block', 'h2'),
            (b'\xac\xed\x00\x05sr', 'java-ser'), (b'\x00\x01\x2acom.codescroll', 'fst?'),
            (b'\xff\xfe<\x00', 'utf16'), (b'\xef\xbb\xbf  <?xml', 'xml'),
            (text[:512], 'text'), (bytes(range(256)), 'binary'),
        ]
        for head, want in cases:
            self.assertEqual(p.kind(head), want, head[:8])

    def test_mask_path_hides_names(self) -> None:
        got = p.mask_path('.metadata/.plugins/com.codescroll.ut.core_1.0.0/secret_prj/dmy_branch_test0.dat')
        self.assertEqual(got, '.metadata\\.plugins\\com.codescroll.ut.core_1.0.0\\aaaaaa_aaa\\dmy_branch_test0.dat')
        self.assertNotIn('secret', got)
        self.assertNotIn('홍', p.mask_path('com.홍길동/x.dat'))
        self.assertNotIn('홍', p.mask_path('.홍길동/x.dat'))
        self.assertEqual(p.mask_path('Users\\홍길동\\ctsample\\Run9.bin'), 'Aaaaa\\???\\ctsample\\Aaa9.bin')

    def test_mask_path_drops_product_substring_rule(self) -> None:
        got = p.mask_path('secret_CodeScroll_prj/x.dat')
        self.assertNotIn('secret', got)
        self.assertNotIn('CodeScroll', got)
        self.assertNotIn('secret', p.mask_path('secret_suresoft/x.dat'))

    def test_classify_drive_root(self) -> None:
        key = os.sep + 'a' + os.sep + 'b.dat'
        self.assertEqual(p._classify(key, [('X', os.sep)]), ('X', 'a' + os.sep + 'b.dat'))

    def test_zip_entries_survive_unicode_error(self) -> None:
        z = self.dir / 'u.zip'
        z.write_bytes(b'x')
        err = UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'secret')
        with mock.patch.object(zipfile, 'ZipFile', side_effect=err):
            self.assertEqual(p.zip_entries(z), [])

    def test_snapshot_prunes_reparse_dirs(self) -> None:
        (self.dir / 'junc').mkdir()
        (self.dir / 'junc' / 'in.txt').write_text('1')
        (self.dir / 'ok.txt').write_text('2')
        real = os.lstat

        def fake(path, *a, **k):
            if str(path).endswith('junc'):
                return mock.Mock(st_file_attributes=0x400, st_mode=0)
            return real(path, *a, **k)
        with mock.patch('run_diff_probe.os.lstat', side_effect=fake):
            snap, _ = p.snapshot([self.dir])
        self.assertEqual(list(snap), [str(self.dir / 'ok.txt')])

    def test_summary_wraps_huge_counts(self) -> None:
        counts = {n: 10 ** 14 for n in ('WS', 'CT', 'SAMPLE', 'TEMP', 'APPDATA', 'LOCALAPPDATA')}
        lines = p.summary_lines(counts, 10 ** 9, 10 ** 9, True, [], None, 0, True)
        self.assertLessEqual(len(lines), 40)
        for line in lines:
            self.assertLessEqual(p.dwidth(line), p.WIDTH, line)

    def test_ask_prints_prompt_to_stdout(self) -> None:
        buf = io.StringIO()
        with mock.patch('builtins.input', return_value='ans') as inp, contextlib.redirect_stdout(buf):
            self.assertEqual(p._ask('x'), 'ans')
        inp.assert_called_once_with()
        self.assertEqual(buf.getvalue(), 'x')

    def test_ask_drains_pending_keys(self) -> None:
        fake = mock.Mock()
        fake.kbhit.side_effect = [True, True, False]
        with mock.patch.object(p.os, 'name', 'nt'), mock.patch.dict(sys.modules, {'msvcrt': fake}), \
                mock.patch('builtins.input', return_value=''), contextlib.redirect_stdout(io.StringIO()):
            p._ask('x')
        self.assertEqual(fake.getwch.call_count, 2)

    def test_snapshot_and_diff(self) -> None:
        a, b, c = (self.dir / n for n in ('a.txt', 'b.txt', 'c.txt'))
        a.write_text('1')
        b.write_text('2')
        before, bad = p.snapshot([self.dir])
        self.assertEqual(bad, 0)
        a.write_text('changed!')
        b.unlink()
        c.write_text('3')
        after, _ = p.snapshot([self.dir])
        d = p.diff(before, after)
        self.assertEqual(d, {'new': [str(c)], 'changed': [str(a)], 'removed': [str(b)]})

    def test_snapshot_skips_unreadable(self) -> None:
        (self.dir / 'ok.txt').write_text('1')
        (self.dir / 'locked.txt').write_text('2')
        real = os.stat

        def fake(path, *a, **k):
            if str(path).endswith('locked.txt'):
                raise PermissionError('secret')
            return real(path, *a, **k)
        with mock.patch('run_diff_probe.os.stat', side_effect=fake):
            snap, bad = p.snapshot([self.dir])
        self.assertEqual(list(snap), [str(self.dir / 'ok.txt')])
        self.assertGreaterEqual(bad, 1)

        real_scandir = os.scandir

        def fake_scandir(path):
            if str(path).endswith('sub'):
                raise PermissionError('secret')
            return real_scandir(path)
        (self.dir / 'sub').mkdir()
        with mock.patch('os.scandir', side_effect=fake_scandir):
            snap, bad = p.snapshot([self.dir])
        self.assertGreaterEqual(bad, 1)
        self.assertIn(str(self.dir / 'ok.txt'), snap)

    def test_locate_picks_innermost_root(self) -> None:
        (self.dir / 'Temp').mkdir()
        f = self.dir / 'Temp' / 'x.bin'
        f.write_bytes(b'1')
        roots = [('LOCALAPPDATA', self.dir), ('TEMP', self.dir / 'Temp')]
        self.assertEqual(p.locate(str(f), roots), ('TEMP', 'x.bin'))
        snap, _ = p.snapshot([r for _, r in roots])
        self.assertEqual([k for k in snap if k == str(f)], [str(f)])

    @unittest.skipUnless(os.name == 'nt', '대소문자 다른 경로는 윈도우에서만')
    def test_roots_spelled_differently_count_once(self) -> None:
        (self.dir / 'Temp').mkdir()
        f = self.dir / 'Temp' / 'x.bin'
        f.write_bytes(b'1')
        temp = str(self.dir / 'Temp').upper()
        snap, _ = p.snapshot([self.dir, Path(temp)])
        self.assertEqual(len(snap), 1)
        roots = [('LOCALAPPDATA', self.dir), ('TEMP', Path(temp))]
        self.assertEqual(p.locate(str(f), roots), ('TEMP', 'x.bin'))

    def test_zip_entries_survive_bad_entry(self) -> None:
        z = self.dir / 'm.zip'
        with zipfile.ZipFile(z, 'w') as zf:
            zf.writestr('good.xml', '<r/>')
            zf.writestr('bad.bin', b'abc')
        real = zipfile.ZipFile.read

        def fake(self_, item, *a, **k):
            if getattr(item, 'filename', item) == 'bad.bin':
                raise RuntimeError('secret')
            return real(self_, item, *a, **k)
        with mock.patch.object(zipfile.ZipFile, 'read', fake):
            rows = p.zip_entries(z)
        self.assertEqual(rows, [('good.xml', 4, 'xml', 0), ('bad.bin', 3, 'unreadable', None)])

    def test_names_found(self) -> None:
        f = self.dir / 'n.bin'
        f.write_bytes(b'xx dmy_case_a yy' + 'dmy_case_b'.encode('utf-16-le'))
        self.assertEqual(p.names_found(f), 2)
        e = self.dir / 'e.bin'
        e.write_bytes(b'nothing')
        self.assertEqual(p.names_found(e), 0)

    def test_names_found_skips_big_file(self) -> None:
        f = self.dir / 'big.bin'
        f.write_bytes(b'x' * 20)
        self.assertIsNone(p.names_found(f, limit=10))
        self.assertIsNone(p.names_found(self.dir / 'missing.bin'))

    def test_zip_entries(self) -> None:
        z = self.dir / 'a.zip'
        blob = bytes(range(256))
        with zipfile.ZipFile(z, 'w') as zf:
            zf.writestr('secret_a.xml', '<r>dmy_case_c</r>')
            zf.writestr('b.bin', blob)
        self.assertEqual(p.zip_entries(z), [('secret_a.xml', 17, 'xml', 1), ('b.bin', 256, 'binary', 0)])
        notzip = self.dir / 'n.txt'
        notzip.write_text('hello')
        self.assertEqual(p.zip_entries(notzip), [])


class MainTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.ws = self.tmp / 'secret_user' / 'ws'
        self.ct = self.tmp / 'ct'
        self.local = self.tmp / 'local'
        self.temp = self.local / 'Temp'
        self.roam = self.tmp / 'roam'
        self.out = self.tmp / 'out'
        self.outside = self.tmp / 'outside'
        for d in (self.ws / '.metadata', self.ct, self.temp, self.roam, self.outside):
            d.mkdir(parents=True)
        (self.ws / '.metadata' / '.log').write_bytes(b'x')
        self.env = {'CT_HOME': str(self.ct), 'TEMP': str(self.temp), 'APPDATA': str(self.roam),
                    'LOCALAPPDATA': str(self.local)}
        self.clears: list = []
        self.sample = self.tmp / 'ctsample'  # 실제 샘플 폴더에 기대지 않는다
        patch = mock.patch.object(p, 'SAMPLE_DIR', self.sample)
        patch.start()
        self.addCleanup(patch.stop)

    def run_main(self, run=None, csd='', reopen=None, ws=None, env=None, marker='', ws_answers=None):
        answers = list(ws_answers) if ws_answers else None

        def ask(prompt):
            if prompt == p.P_WS:
                if answers:
                    return answers.pop(0)
                return '"{}"'.format(self.ws if ws is None else ws)
            if prompt == p.P_RUN:
                run and run()
            elif prompt == p.P_CSD:
                return csd
            elif prompt == p.P_REOPEN:
                reopen and reopen()
                return marker
            return ''
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = p.main([], ask=ask, clear=lambda: self.clears.append(buf.tell()),
                          environ=self.env if env is None else env, out_dir=self.out)
        return code, buf.getvalue()

    def check_screen(self, text: str) -> None:
        self.assertNotIn('secret', text)
        self.assertNotIn(str(self.tmp), text)
        self.assertNotIn(os.path.realpath(str(self.tmp)), text)
        lines = text.splitlines()
        self.assertLessEqual(len(lines), 40)
        for line in lines:
            self.assertLessEqual(p.dwidth(line), p.WIDTH, line)

    def test_main_flow(self) -> None:
        run1 = self.ws / '.metadata' / '.plugins' / 'com.codescroll.ut.core' / 'secret_dir' / 'run1.dat'

        def run():
            run1.parent.mkdir(parents=True)
            run1.write_bytes(b'..dmy_case_a..')
            with zipfile.ZipFile(self.temp / 'secret_tmp.bin', 'w') as zf:
                zf.writestr('inner.xml', '<r/>')
            (self.ws / '.metadata' / '.log').write_bytes(b'longer log')
        csd = self.outside / 'x.csd'
        with zipfile.ZipFile(csd, 'w') as zf:
            zf.writestr('secret_e.xml', '<r>'.encode('utf-16-le') + 'dmy_case_b'.encode('utf-16-le'))
        code, text = self.run_main(run, str(csd), lambda: run1.unlink())
        self.assertEqual(code, 0, text)
        for want in ('새로 2', '바뀜 1', '.csd: 크기', '이름 1/5', '없음 1', 'aaa9.dat'):
            self.assertIn(want, text)
        self.check_screen(text)
        self.assertEqual(len(self.clears), 3)
        self.assertTrue(text[self.clears[-1]:].startswith('28절 결과'))
        data = json.loads((self.out / 'run_diff.json').read_text(encoding='utf-8'))
        self.assertIn(os.path.realpath(str(run1)), [x['path'] for x in data['files']])
        z = [x for x in data['files'] if x['path'].endswith('secret_tmp.bin')][0]
        self.assertEqual(z['zip'][0][0], 'inner.xml')

    def test_main_skips_csd(self) -> None:
        code, text = self.run_main(lambda: (self.temp / 'a.bin').write_bytes(b'1'), '')
        self.assertIn('.csd: 건너뜀', text)
        self.assertEqual(code, 0)
        self.check_screen(text)

    def test_main_no_change(self) -> None:
        code, text = self.run_main()
        self.assertIn(p.W_NONE, text)
        self.assertEqual(code, 1)
        self.check_screen(text)

    def test_main_bad_inputs(self) -> None:
        code, text = self.run_main(env={})
        self.assertEqual((code, text.strip()), (2, p.E_HOME))
        code, text = self.run_main(ws=self.tmp / 'missing')
        self.assertEqual((code, text.strip()), (2, p.E_WS))

    def test_main_many_files(self) -> None:
        def run():
            for i in range(30):
                (self.ct / 'f{}.bin'.format(i)).write_bytes(b'x' * (i + 1))
        code, text = self.run_main(run)
        lines = text.splitlines()
        self.assertEqual(sum(1 for line in lines if line.startswith('새 ')), 16)
        self.assertIn('나머지 14개는 json에만', text)
        self.check_screen(text)

    def test_main_file_outside_all_roots(self) -> None:
        ext = self.outside / 'secret_ext.bin'
        ext.write_bytes(b'abc')
        real, calls = p.snapshot, []

        def fake(roots):
            snap, bad = real(roots)
            calls.append(1)
            snap[str(ext)] = (3, len(calls))  # 두 번째 목록부터 값이 달라 '바뀜'으로 잡힌다
            return snap, bad
        with mock.patch.object(p, 'snapshot', fake):
            code, text = self.run_main()
        self.assertEqual(code, 0, text)
        self.check_screen(text)
        self.assertTrue((self.out / 'run_diff.json').is_file())

    def test_main_asks_workspace_again_without_metadata(self) -> None:
        nometa = self.tmp / 'secret_plain'
        nometa.mkdir()
        run = lambda: (self.temp / 'a.bin').write_bytes(b'1')  # noqa: E731
        code, text = self.run_main(run, ws_answers=[str(nometa), str(self.ws)])
        self.assertEqual(code, 0, text)
        self.assertIn(p.W_META, text[:self.clears[1]])
        self.assertNotIn(p.W_META, text[self.clears[-1]:])
        self.check_screen(text)
        self.clears.clear()
        code, text = self.run_main(run, ws_answers=[str(nometa), str(nometa)])
        self.assertEqual(code, 0, text)
        self.assertIn(p.W_META, text[self.clears[-1]:])
        code, text = self.run_main(ws_answers=[str(nometa), str(self.tmp / 'missing')])
        self.assertEqual((code, text.strip().splitlines()[-1]), (2, p.E_WS))

    def test_main_sample_root_and_innermost_workspace(self) -> None:
        (self.sample / 'src').mkdir(parents=True)
        (self.sample / 'ws' / '.metadata').mkdir(parents=True)

        def run():
            (self.sample / 'src' / 'n.c').write_bytes(b'dmy_case_a')
            (self.sample / 'ws' / '.metadata' / 'n.dat').write_bytes(b'dmy_case_a')
        code, text = self.run_main(run, ws=self.sample / 'ws')
        final = text[self.clears[-1]:]
        self.assertIn('SAMPLE ', final)
        self.assertIn('SAMPLE\\aaa\\a.c', final)
        self.assertIn('WS\\.metadata\\a.dat', final)
        self.check_screen(text)

    def test_main_shows_files_changed_on_close(self) -> None:
        def reopen():
            (self.temp / 'closed.dat').write_bytes(b'dmy_case_b')
        code, text = self.run_main(lambda: (self.temp / 'a.bin').write_bytes(b'1'), reopen=reopen)
        final = text[self.clears[-1]:]
        self.assertIn('다시 열며 새로 바뀐 것 1', final)
        row = [x for x in final.splitlines() if x.startswith('닫음')]
        self.assertEqual(len(row), 1, final)
        self.assertIn('1/5', row[0])
        self.assertIn('견본 이름이 든 것 1, CT 관련 경로 0, 나머지 1개는 json에만', final)
        data = json.loads((self.out / 'run_diff.json').read_text(encoding='utf-8'))
        self.assertIn('closed.dat', ' '.join(x['path'] for x in data['files']))
        self.check_screen(text)

    def test_main_csd_items_ranked_by_names(self) -> None:
        csd = self.outside / 'x.csd'
        with zipfile.ZipFile(csd, 'w') as zf:
            for i in range(10):
                zf.writestr('secret_{}.xml'.format(i), '<r>dmy_case_a</r>' if i == 9 else '<r/>')
        code, text = self.run_main(lambda: (self.temp / 'a.bin').write_bytes(b'1'), str(csd))
        final = text[self.clears[-1]:]
        self.assertIn('견본 이름 1/5, 항목 10개', final)
        first = [x for x in final.splitlines() if x.startswith('  항목')][0]
        self.assertIn('이름 1/5', first)
        self.check_screen(text)

    def test_main_marker_answer(self) -> None:
        for answer, want in (('Y ', '보임'), ('n', '안 보임'), ('', '답 없음'), ('몰라', '답 없음')):
            code, text = self.run_main(lambda: (self.temp / 'a.bin').write_bytes(b'1'), marker=answer)
            line = [x for x in text.splitlines() if x.startswith('다시 연 뒤 참·거짓')][0]
            self.assertTrue(line.endswith(': ' + want), line)

    def test_main_hex_only_for_binary_kinds(self) -> None:
        def run():
            (self.temp / 'a.txt').write_bytes(b'secretdata dmy_case_a')
            (self.temp / 'b.bin').write_bytes(bytes(range(40)) + b'dmy_case_a')
        code, text = self.run_main(run)
        rows = {('a.txt' if 'a.txt' in x else 'b.bin'): x for x in text.splitlines() if x.startswith('새 ')}
        self.assertNotIn('73 65 63', rows['a.txt'])
        self.assertIn('00 01 02 03', rows['b.bin'])

    def test_fit_keeps_root_and_width(self) -> None:
        line = p._fit('상태 ', '가' * 80 + 'file.dat', ' 이름 1/5', keep='WS\\')
        self.assertLessEqual(p.dwidth(line), p.WIDTH)
        self.assertTrue(line.startswith('상태 WS\\…'))
        self.assertIn('file.dat', line)


if __name__ == '__main__':
    unittest.main()
