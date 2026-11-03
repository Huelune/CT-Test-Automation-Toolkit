"""examples/ct_sample/probe_csv.py 단위 테스트 (stdlib unittest). 13절을 지울 때 함께 지운다."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path

_PATH = Path(__file__).resolve().parents[2] / 'examples' / 'ct_sample' / 'probe_csv.py'
_SPEC = importlib.util.spec_from_file_location('probe_csv', str(_PATH))
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)

GOOD = ('CT(Controller Tester) Test Data\r\ntest name:secret_fn_test0,""\r\n'
        ',<input>,secret_a,<expect>,secret_b\r\n1,"",7,,\r\n')
MULTILINE = ('CT(Controller Tester) Test Data\r\ntest name:secret_fn_test4,"secret note\r\nsecret more"\r\n'
             ',<input>,secret_a,<expect>,secret_b\r\n1,"",,,\r\n')
OTHER_FIRST = 'secret header 2026\r\ntest name:secret_fn_test0,""\r\n,<input>,secret_a\r\n'


class ProbeTest(unittest.TestCase):
    def _run(self, files) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            unit = Path(tmp) / 'secret_proj' / 'UnitTests'
            unit.mkdir(parents=True)
            for name, data in files.items():
                (unit / name).write_bytes(data)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                probe.main(['다시=' + tmp])
        return out.getvalue()

    def test_verdicts_and_no_names(self) -> None:
        screen = self._run({'secret_1.csv': GOOD.encode('cp949'),
                            'secret_2.csv': MULTILINE.encode('cp949'),
                            'secret_3.csv': OTHER_FIRST.encode('cp949')})
        self.assertIn('[다시] 파일 3, UnitTests 폴더 CSV 3', screen)
        self.assertIn('판정: 툴킷이 읽음', screen)
        self.assertIn('판정: 따옴표 홀수 줄(따옴표 안 줄바꿈)', screen)
        self.assertIn('따옴표 홀수 줄 2: 2,3', screen)
        self.assertIn('판정: 첫 줄이 CT 첫 줄과 다름', screen)
        self.assertIn('모양 a a 9', screen)
        self.assertNotIn('secret', screen.lower())
        self.assertNotIn('tmp', screen.lower())

    def test_utf16_file_is_named_as_such(self) -> None:
        screen = self._run({'secret.csv': GOOD.encode('utf-16')})
        self.assertIn('BOM utf-16, NUL 바이트 예', screen)
        self.assertNotIn('secret', screen.lower())

    def test_shape_masks_letters(self) -> None:
        self.assertEqual(probe.shape('test name:dmy_calc_test12,""'), 'a a:a_a_a9,""')


if __name__ == '__main__':
    unittest.main()
