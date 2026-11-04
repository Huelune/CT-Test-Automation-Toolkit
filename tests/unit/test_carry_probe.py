"""tools/carry_probe.py 단위 테스트 (stdlib unittest).

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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import carry_probe  # noqa: E402
from test_ct_export import _csv  # noqa: E402
from test_member_probe import PICK_HEADER, _header_line, _put  # noqa: E402

# 원래 테스트: CT에서 [2]를 늘리고 전역 변수 dmy_gain을 체크한 것
ORIGINAL = PICK_HEADER.replace('dmy_recs[0].dmy_t,<expect>',
                               'dmy_recs[0].dmy_t,dmy_recs[2].dmy_s,dmy_gain,<expect>')
# CSV로 만든 테스트: 늘린 것이 빠지고 dmy_sum은 사본에서 뺐다
MADE = PICK_HEADER.replace('dmy_sum,', '')
# 붙인 뒤: 늘린 것이 돌아오고 dmy_recs[0].dmy_t가 입력으로만 바뀌었다
PASTED = ORIGINAL.replace('dmy_sum,', '').replace('<expect>,dmy_recs[0].dmy_t,', '<expect>,') \
    .replace('<output>,dmy_recs[0].dmy_t,', '<output>,').replace('<toutput>,dmy_recs[0].dmy_t,', '<toutput>,')


class CarryProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.first, self.made, self.pasted = (self.root / n for n in ('14', '15', '16'))
        _put(self.first, 'dmy_pick_test0.csv', _csv(name='dmy_pick_test0', header=ORIGINAL))
        _put(self.first, 'dmy_calc_test0.csv', _csv())  # dmy_pick이 아닌 테스트는 보지 않는다

    def _run(self) -> tuple:
        buf = io.StringIO()
        with mock.patch.object(carry_probe.paths, 'result_dir', return_value=self.root / 'result'), \
                contextlib.redirect_stdout(buf):
            code = carry_probe.main([str(self.first), str(self.made), str(self.pasted)])
        return code, buf.getvalue()

    def test_first_run_writes_copy_without_released_symbol(self) -> None:
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertIn('사본 CSV: result\\probe\\', out)
        self.assertIn('dmy_recs[2].dmy_s', out)
        self.assertNotIn('dmy_calc', out)
        self.assertNotIn('[WARN]', out)
        copies = list((self.root / 'result' / 'probe').glob('*/copy/dmy_pick_test0.csv'))
        self.assertEqual(len(copies), 1)
        header = _header_line(copies[0])
        self.assertNotIn('dmy_sum', header)
        self.assertIn('dmy_gain', header)

    def test_second_run_reports_gone_added_and_moved(self) -> None:
        _put(self.made, 'dmy_pick_test0.csv', _csv(name='dmy_pick_test0', header=ORIGINAL))
        _put(self.made, 'dmy_pick_test1.csv', _csv(name='dmy_pick_test1', header=MADE))
        _put(self.pasted, 'dmy_pick_test0.csv', _csv(name='dmy_pick_test0', header=ORIGINAL))
        _put(self.pasted, 'dmy_pick_test1.csv', _csv(name='dmy_pick_test1', header=PASTED))
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertNotIn('사본 CSV', out)
        lines = out.splitlines()
        made = lines[lines.index('CSV로 만든 뒤: dmy_pick 테스트 2') + 1:]
        self.assertEqual(made[0].strip(), 'dmy_pick_test0  원래와 같음')
        self.assertIn('빠짐 3: dmy_recs[2].dmy_s, dmy_gain, dmy_sum', made[1])
        pasted = lines[lines.index('세부 항목 붙인 뒤: dmy_pick 테스트 2') + 2]
        self.assertIn('빠짐 1: dmy_sum', pasted)
        self.assertIn('더해짐 0', pasted)
        self.assertIn('방향 바뀜 1: dmy_recs[0].dmy_t(inout→in)', pasted)
        self.assertTrue(all(len(line) <= 120 for line in lines))

    def test_missing_pasted_folder_is_one_line(self) -> None:
        _put(self.made, 'dmy_pick_test1.csv', _csv(name='dmy_pick_test1', header=MADE))
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertIn('세부 항목 붙인 뒤: 폴더 없음', out)

    def test_two_pick_tests_in_first_folder_stop(self) -> None:
        _put(self.first, 'dmy_pick_test1.csv', _csv(name='dmy_pick_test1', header=MADE))
        code, out = self._run()
        self.assertEqual(code, 1)
        self.assertIn('dmy_pick 테스트가 2개', out)

    def test_warns_without_expanded_element(self) -> None:
        _put(self.first, 'dmy_pick_test0.csv', _csv(name='dmy_pick_test0', header=PICK_HEADER))
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertIn('[WARN] 원래 테스트에 [0]이 아닌 원소가 없음', out)

    def test_other_names_are_masked_and_paths_not_printed(self) -> None:
        secret = self.root / 'secret_dir'
        self.first = secret / '14'
        _put(self.first, 'dmy_pick_test0.csv',
             _csv(name='dmy_pick_test0', header=ORIGINAL.replace('dmy_gain', 'secret_g')))
        code, out = self._run()
        self.assertEqual(code, 0)
        self.assertNotIn('secret', out)

    def test_wrong_args_exit_1(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(carry_probe.main(['secret_only_one']), 1)
        self.assertNotIn('secret', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
