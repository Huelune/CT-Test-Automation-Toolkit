"""tools/io_run.py 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# io_run은 같은 폴더의 todo_run을 import한다. 더블클릭으로 돌 때는 스크립트 폴더가 import 경로에 있다.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import io_run  # noqa: E402
import todo_run  # noqa: E402

LIST = '"C:\\secret_dir\\secret_list.xlsx" '
EXPORT = '  "C:\\secret_dir\\secret out"'


class _Run:
    def __init__(self, code: int = 0, stderr: str = '') -> None:
        self.code, self.stderr, self.calls = code, stderr, []

    def __call__(self, args, cwd, env):
        self.calls.append((args, cwd, env))
        return self.code, self.stderr


def _main(answers, run=None, tmp=None):
    """답을 차례로 넣어 main을 돌리고 (반환값, 화면, 실행 기록, 화면 지운 횟수)를 낸다."""
    answers, run, cleared, out = list(answers), run or _Run(), [], io.StringIO()
    with mock.patch.dict(os.environ, {'TODO_PULL': 'ok'}), contextlib.redirect_stdout(out), \
            mock.patch('tempfile.tempdir', tmp):
        code = io_run.main(ask=lambda _: answers.pop(0), run=run,
                           clear_screen=lambda: cleared.append(1))
    return code, out.getvalue(), run.calls, len(cleared)


class MainTest(unittest.TestCase):
    def test_reset_yes_passes_both_paths_and_flag_without_printing_them(self) -> None:
        code, screen, calls, cleared = _main([LIST, EXPORT, ' Y '], run=_Run(0))
        self.assertEqual(code, 0)
        args, cwd, env = calls[0]
        self.assertEqual(args[1:], ['-m', 'ct_toolkit', 'io-apply',
                                    '--list', 'C:\\secret_dir\\secret_list.xlsx',
                                    '--export', 'C:\\secret_dir\\secret out', '--reset-cases'])
        self.assertEqual(cwd, str(todo_run.ROOT))
        self.assertEqual(env['PYTHONUTF8'], '1')
        self.assertEqual(cleared, 1)
        self.assertNotIn('secret', screen)
        self.assertIn('케이스 정리 함', screen)
        self.assertTrue(screen.rstrip().endswith('exit=0'))

    def test_reset_no_leaves_out_flag(self) -> None:
        code, screen, calls, _ = _main([LIST, EXPORT, 'n'], run=_Run(1))
        self.assertEqual(code, 1)
        self.assertNotIn('--reset-cases', calls[0][0])
        self.assertIn('케이스 정리 안 함', screen)
        self.assertIn('exit=1', screen)

    def test_empty_list_stops_before_asking_more(self) -> None:
        answers = ['  ""  ', EXPORT, 'y']
        code, screen, calls, cleared = _main(answers)
        self.assertEqual((code, calls, cleared), (2, [], 0))
        self.assertIn(io_run.E_NO_LIST, screen)

    def test_empty_export_stops(self) -> None:
        code, screen, calls, _ = _main([LIST, ' '])
        self.assertEqual((code, calls), (2, []))
        self.assertIn(io_run.E_NO_EXPORT, screen)
        self.assertNotIn('secret', screen)

    def test_other_reset_answer_stops_without_echoing_it(self) -> None:
        code, screen, calls, _ = _main([LIST, EXPORT, 'secret yes'])
        self.assertEqual((code, calls), (2, []))
        self.assertIn(io_run.E_RESET, screen)
        self.assertNotIn('secret', screen)

    def test_crash_prints_kind_only(self) -> None:
        trace = 'Traceback:\n  File "C:\\secret\\x.py"\nPermissionError: C:\\secret_dir\n'
        with tempfile.TemporaryDirectory() as tmp:
            code, screen, _, _ = _main([LIST, EXPORT, 'y'], run=_Run(1, trace), tmp=tmp)
        self.assertEqual(code, 1)
        self.assertIn(todo_run.E_CRASH.format('PermissionError'), screen)
        self.assertNotIn('secret', screen)


if __name__ == '__main__':
    unittest.main()
