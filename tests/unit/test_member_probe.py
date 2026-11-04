"""tools/member_probe.py 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # test_ct_export의 견본 만들기를 쓴다
import member_probe  # noqa: E402
from ct_toolkit.ct_export import split_fields  # noqa: E402
from test_ct_export import HEADER, _by_section, _csv  # noqa: E402

PICK_HEADER = (',<input>,dmy_i,dmy_recs[0].dmy_s,dmy_recs[0].dmy_t,<expect>,dmy_recs[0].dmy_t,dmy_sum,'
               'returnVar,<output>,dmy_recs[0].dmy_t,dmy_sum,returnVar,<toutput>,dmy_recs[0].dmy_t,'
               'dmy_sum,returnVar')


def _put(root: Path, name: str, data: bytes) -> None:
    path = root / 'UnitTests' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _header_line(path: Path) -> str:
    return path.read_bytes().decode('cp949').split('\r\n')[2]


class ProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.export = self.root / 'export'
        self.out = self.root / 'out'

    def test_show_masks_names_not_starting_with_dmy(self) -> None:
        _put(self.export, 'secret_f_test0.csv',
             _csv(name='secret_f_test0', header=',<input>,secret_x,<expect>,secret_x'))
        _put(self.export, 'dmy_calc_test0.csv', _csv())
        lines = member_probe.show_lines(self.export)
        text = '\n'.join(lines)
        self.assertNotIn('secret', text)
        self.assertEqual(member_probe._mask('dmy_x한'), '*')  # 영문 아닌 글자가 든 이름도 가린다
        self.assertIn('dmy_gain', text)
        self.assertIn('dmy_calc_test0', text)

    def test_show_counts_unreadable(self) -> None:
        _put(self.export, 'secret_bad.csv', b'not a ct file\r\n')
        _put(self.export, 'dmy_calc_test0.csv', _csv())
        lines = member_probe.show_lines(self.export)
        self.assertEqual(lines[-1], '읽지 못한 CSV 1')

    def test_show_lines_fit_120(self) -> None:
        header = ',<input>,' + ','.join('dmy_long_symbol_{}'.format(i) for i in range(40))
        _put(self.export, 'dmy_calc_test0.csv', _csv(header=header))
        lines = member_probe.show_lines(self.export)
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(len(line) <= 120 for line in lines))

    def test_make_writes_four_variants(self) -> None:
        _put(self.export, 'dmy_calc_test0.csv', _csv(header=HEADER))
        _put(self.export, 'dmy_pick_test0.csv', _csv(name='dmy_pick_test0', header=PICK_HEADER))
        lines = member_probe.make_variants(self.export, self.out)
        self.assertEqual(len(lines), 4)
        v1, v2, v3, v4 = (self.out / 'v{}'.format(n) for n in (1, 2, 3, 4))
        names = {'v1': 'dmy_calc_test0.csv', 'v2': 'dmy_pick_test0.csv',
                 'v3': 'dmy_calc_test0.csv', 'v4': 'dmy_calc_test0.csv'}
        for folder in (v1, v2, v3, v4):
            path = folder / names[folder.name]
            header = _header_line(path)
            for row in path.read_bytes().decode('cp949').split('\r\n')[3:]:
                if row:
                    self.assertEqual(len(split_fields(row)), len(split_fields(header)), folder.name)
        self.assertIn('dmy_hist[2]', _by_section(_header_line(v1 / names['v1']))['<expect>'])
        self.assertIn('dmy_recs[2].dmy_s', _by_section(_header_line(v2 / names['v2']))['<expect>'])
        self.assertIn('dmy_limit.dmy_zz', _by_section(_header_line(v3 / names['v3']))['<input>'])
        self.assertNotIn('dmy_limit.dmy_hi', _header_line(v4 / names['v4']))

    def test_missing_pick_test_reports_and_continues(self) -> None:
        _put(self.export, 'dmy_calc_test0.csv', _csv(header=HEADER))
        lines = member_probe.make_variants(self.export, self.out)
        self.assertTrue(any('v2 만들지 못함' in line for line in lines))
        for n in (1, 3, 4):
            self.assertTrue((self.out / 'v{}'.format(n) / 'dmy_calc_test0.csv').is_file())
        self.assertFalse((self.out / 'v2').exists())

    def test_main_missing_folder_exits_1(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = member_probe.main([str(self.root / 'secret_missing')])
        self.assertEqual(code, 1)
        self.assertNotIn('secret', buf.getvalue())

    def test_main_make_writes_under_result_probe(self) -> None:
        _put(self.export, 'dmy_calc_test0.csv', _csv(header=HEADER))
        buf = io.StringIO()
        with mock.patch.object(member_probe.paths, 'result_dir', return_value=self.root / 'result'), \
                contextlib.redirect_stdout(buf):
            code = member_probe.main([str(self.export), '--make'])
        self.assertEqual(code, 0)
        self.assertIn('변형 CSV: result\\probe\\', buf.getvalue())
        self.assertEqual(len(list((self.root / 'result' / 'probe').glob('*/v1/*.csv'))), 1)


if __name__ == '__main__':
    unittest.main()
