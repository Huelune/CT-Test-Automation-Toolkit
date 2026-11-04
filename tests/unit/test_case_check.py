"""tools/case_check.py 단위 테스트 (stdlib unittest).

견본 꼴(16절에서 다시 만든 dmy_calc, dmy_rec.example.c의 dmy_pick으로 짐작한 꼴)의 내보낸 폴더로 경우 목록
엑셀의 기대가 툴킷 판정과 맞는지 본다. 실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import contextlib
import importlib.util
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
import case_check  # noqa: E402
from test_ct_export import UTEST, _csv  # noqa: E402
from test_member_probe import PICK_HEADER  # noqa: E402

HAS_OPENPYXL = importlib.util.find_spec('openpyxl') is not None

# 16절에서 예제 목록으로 다시 만든 dmy_calc 테스트의 머리글(dmy_spare 해제, dmy_count·dmy_hist는 출력만)
CALC_HEADER = (',<input>,dmy_gain,dmy_limit.dmy_hi,dmy_limit.dmy_lo,dmy_mode,dmy_ptr_mem[0],dmy_x,'
               '<expect>,dmy_count,dmy_hist[0],dmy_level,returnVar,<output>,dmy_count,dmy_hist[0],dmy_level,'
               'returnVar,<toutput>,dmy_count,dmy_hist[0],dmy_level,returnVar')


@unittest.skipUnless(HAS_OPENPYXL, 'openpyxl 없음')
class CaseCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.export = Path(tmp.name) / 'export'

    def _export(self, calc_header: str = CALC_HEADER) -> None:
        unit = self.export / 'ctsample' / 'UnitTests'
        unit.mkdir(parents=True)
        (unit / 'dmy_calc_test0.csv').write_bytes(_csv(header=calc_header))
        (unit / 'dmy_calc_test0.utest').write_bytes(UTEST)  # 소스 파일 dmy_io.c
        (unit / 'dmy_pick_test0.csv').write_bytes(_csv(name='dmy_pick_test0', header=PICK_HEADER))

    def _run(self, argv) -> tuple:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = case_check.main(argv)
        return code, out.getvalue()

    def test_every_case_matches_on_sample_shaped_export(self) -> None:
        self._export()
        code, screen = self._run([str(self.export)])
        self.assertEqual(code, 0, screen)
        lines = screen.splitlines()
        self.assertEqual(lines[0], '견본 머리글')
        self.assertTrue(any(line.startswith('dmy_pick_test0  <input> dmy_i') for line in lines))
        self.assertIn('경우 19: 맞음 16, 틀림 0, 참고 3', lines)
        self.assertIn('참고  행 18 CT에 없음', lines)  # 짐작한 꼴에는 [2] 원소가 없다
        self.assertIn('다시 돌림: 바뀔 테스트 0', lines)
        self.assertIn('해제 기대 3: 맞음 3, 틀림 0', lines)
        self.assertIn('추가 경우 4: 맞음 4, 틀림 0', lines)
        self.assertNotIn('틀림  ', screen)
        self.assertNotIn('변형', screen)  # 변형 폴더를 주지 않았다

    def test_missing_variant_folder_makes_variants(self) -> None:
        self._export()
        out = Path(self.export.parent) / 'result'
        with mock.patch.object(case_check.paths, 'result_dir', return_value=out):
            code, screen = self._run([str(self.export), str(self.export.parent / 'secret_13')])
        self.assertEqual(code, 0, screen)
        self.assertIn('v1 dmy_hist[2]를 기대값에 더함', screen.splitlines())
        self.assertTrue(any(line.startswith('변형 CSV: result\\probe\\') for line in screen.splitlines()))
        self.assertEqual(len(list(out.glob('probe/*/v1/dmy_calc_test0.csv'))), 1)
        self.assertNotIn('secret', screen)

    def test_existing_variant_folder_shows_its_headers_on_one_screen(self) -> None:
        self._export()
        variants = self.export.parent / 'out13' / 'ctsample' / 'UnitTests'
        variants.mkdir(parents=True)
        for n in range(4):  # 원래 것과 변형 셋(v1, v3, v4)
            (variants / 'dmy_calc_test{}.csv'.format(n)).write_bytes(
                _csv(name='dmy_calc_test{}'.format(n), header=CALC_HEADER))
        for n in range(2):  # 원래 것과 변형 v2
            (variants / 'dmy_pick_test{}.csv'.format(n)).write_bytes(
                _csv(name='dmy_pick_test{}'.format(n), header=PICK_HEADER))
        code, screen = self._run([str(self.export), str(variants.parent.parent)])
        lines = screen.splitlines()
        self.assertEqual(code, 0, screen)
        self.assertIn('변형으로 만든 테스트 머리글', lines)
        self.assertTrue(any(line.startswith('dmy_calc_test3  <input>') for line in lines))
        self.assertNotIn('변형 CSV', screen)
        self.assertTrue(all(len(line) <= 120 for line in lines))
        self.assertLessEqual(len(lines), 39)  # todo_run이 제목과 exit= 줄을 더한다

    def test_unexpected_result_is_reported_with_row_number(self) -> None:
        # CT가 [2] 원소를 가져왔다면 행 7(dmy_hist[2], 기대 CT에 없음)은 지정된다
        self._export(CALC_HEADER.replace('dmy_hist[0],', 'dmy_hist[0],dmy_hist[2],'))
        code, screen = self._run([str(self.export)])
        self.assertEqual(code, 1)
        self.assertIn('틀림  행 7 기대 CT에 없음, 결과 지정', screen.splitlines())

    def test_missing_folder_stops_without_printing_path(self) -> None:
        code, screen = self._run([str(self.export / 'secret_missing')])
        self.assertEqual((code, screen.strip()), (1, case_check.E_OPEN))

    def test_names_other_than_samples_are_masked(self) -> None:
        self._export()
        (self.export / 'ctsample' / 'UnitTests' / 'secret_f_test0.csv').write_bytes(
            _csv(name='secret_f_test0', header=',<input>,secret_x,<expect>,returnVar'))
        screen = self._run([str(self.export)])[1]
        self.assertNotIn('secret', screen)


if __name__ == '__main__':
    unittest.main()
