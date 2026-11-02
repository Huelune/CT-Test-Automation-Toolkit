"""tools/todo_run.py 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_PATH = Path(__file__).resolve().parents[2] / 'tools' / 'todo_run.py'
_SPEC = importlib.util.spec_from_file_location('todo_run', str(_PATH))
todo_run = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(todo_run)

# 실제 절은 todo.md를 처리하면서 바뀌므로, 실행 경로는 지어낸 절 둘로 본다.
PLAIN, LISTED = '91', '92'
FAKE_SECTIONS = {
    PLAIN: ('견본 확인', ['tools/todo_run.py']),
    LISTED: ('목록 확인', ['-m', 'ct_toolkit', 'io-apply', '--list', todo_run.LIST]),
}


TRACEBACK = ('Traceback (most recent call last):\n'
             '  File "C:\\Users\\secret_user\\repo\\examples\\probe.py", line 9, in <module>\n'
             "FileNotFoundError: [Errno 2] No such file: 'C:\\\\secret_dir\\\\probe5.txt'\n")


class _Run:
    def __init__(self, code: int = 0, stderr: str = '') -> None:
        self.code, self.stderr, self.calls = code, stderr, []

    def __call__(self, args, cwd, env):
        self.calls.append((args, cwd, env))
        return self.code, self.stderr


def _main(answers, run=None, pull='ok', tmp=None):
    """답을 차례로 넣어 main을 돌리고 (반환값, 화면, 실행 기록, 화면 지운 횟수)를 낸다."""
    answers, run, cleared, out = list(answers), run or _Run(), [], io.StringIO()
    with mock.patch.dict(os.environ, {'TODO_PULL': pull}), contextlib.redirect_stdout(out), \
            mock.patch('tempfile.tempdir', tmp), \
            mock.patch.dict(todo_run.SECTIONS, FAKE_SECTIONS, clear=True):
        code = todo_run.main(ask=lambda _: answers.pop(0), run=run,
                             clear_screen=lambda: cleared.append(1))
    return code, out.getvalue(), run.calls, len(cleared)


class MainTest(unittest.TestCase):
    def test_section_runs_probe_from_repo_root(self) -> None:
        code, screen, calls, cleared = _main([PLAIN], run=_Run(0))
        self.assertEqual(code, 0)
        args, cwd, env = calls[0]
        self.assertEqual(args[1:], FAKE_SECTIONS[PLAIN][1])
        self.assertTrue((todo_run.ROOT / args[1]).is_file())
        self.assertEqual(cwd, str(todo_run.ROOT))
        self.assertEqual(env['PYTHONUTF8'], '1')
        self.assertEqual(cleared, 1)
        self.assertIn('todo.md {}절'.format(PLAIN), screen)
        self.assertTrue(screen.rstrip().endswith('exit=0'))

    def test_every_section_script_and_example_list_exist(self) -> None:
        for title, args in todo_run.SECTIONS.values():
            for arg in args:
                if arg.endswith(('.py', '.xlsx')):
                    self.assertTrue((todo_run.ROOT / arg).is_file(), arg)

    def test_export_sections_use_the_sample_list_and_export_folders(self) -> None:
        sample = 'examples/ct_sample/io_list.example.xlsx'
        for number, folder, reset in (('11', 'C:/ctsample/out/1', True),
                                      ('12', 'C:/ctsample/out/9', False)):
            args = todo_run.SECTIONS[number][1]
            self.assertEqual(args[:6], ['-m', 'ct_toolkit', 'io-apply', '--list', sample, '--export'])
            self.assertEqual(args[6:], [folder] + (['--reset-cases'] if reset else []))

    def test_list_section_passes_dropped_path_without_printing_it(self) -> None:
        dropped = '"C:\\secret_dir\\secret_list.xlsx" '
        code, screen, calls, _ = _main([LISTED, dropped], run=_Run(3))
        self.assertEqual(code, 3)
        args, _, env = calls[0]
        self.assertEqual(args[1:], ['-m', 'ct_toolkit', 'io-apply', '--list',
                                    'C:\\secret_dir\\secret_list.xlsx'])
        self.assertTrue(env['PYTHONPATH'].startswith(str(todo_run.ROOT / 'src')))
        self.assertNotIn('secret', screen)
        self.assertIn('exit=3', screen)

    def test_unknown_section_stops_without_echoing_input(self) -> None:
        code, screen, calls, cleared = _main(['secret9'])
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])
        self.assertEqual(cleared, 0)
        self.assertIn(todo_run.E_NO_SECTION, screen)
        self.assertNotIn('secret', screen)

    def test_empty_list_path_stops(self) -> None:
        code, screen, calls, _ = _main([LISTED, '  ""  '])
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])
        self.assertIn(todo_run.E_NO_LIST, screen)

    def test_crash_prints_kind_only_and_keeps_traceback_in_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, screen, _, _ = _main([PLAIN], run=_Run(1, TRACEBACK), tmp=tmp)
            saved = (Path(tmp) / todo_run.ERR_NAME).read_text(encoding='utf-8')
        self.assertEqual(code, 1)
        self.assertIn(todo_run.E_CRASH.format('FileNotFoundError'), screen)
        self.assertNotIn('secret', screen)
        self.assertEqual(saved, TRACEBACK)

    def test_warning_on_success_points_to_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, screen, _, _ = _main([PLAIN], run=_Run(0, 'C:\\secret\\x.py:1: UserWarning: secret\n'),
                                       tmp=tmp)
        self.assertEqual(code, 0)
        self.assertIn(todo_run.W_STDERR.format('UserWarning'), screen)
        self.assertNotIn('secret', screen)

    def test_error_kind_ignores_message_and_odd_last_lines(self) -> None:
        self.assertEqual(todo_run.error_kind(TRACEBACK), 'FileNotFoundError')
        self.assertEqual(todo_run.error_kind('x\nC:\\secret: bad\n'), '종류 모름')
        self.assertEqual(todo_run.error_kind('secret.py:3: oops\n'), '종류 모름')
        self.assertEqual(todo_run.error_kind('zipfile.BadZipFile: x\n'), '종류 모름')
        self.assertEqual(todo_run.error_kind('a.b.InvalidFileException: secret\n'),
                         'a.b.InvalidFileException')
        self.assertEqual(todo_run.error_kind(''), '종류 모름')

    def test_warning_kinds_lists_names_only(self) -> None:
        text = 'C:\\secret\\a.py:1: UserWarning: x\nb.py:2: DeprecationWarning: secret\n'
        self.assertEqual(todo_run.warning_kinds(text), 'DeprecationWarning, UserWarning')
        self.assertEqual(todo_run.warning_kinds('secret\n'), '종류 모름')

    def test_failed_pull_is_warned_after_clearing(self) -> None:
        _, screen, _, _ = _main([PLAIN], pull='fail')
        self.assertIn(todo_run.W_PULL, screen.split('todo.md {}절'.format(PLAIN))[1])
        _, screen, _, _ = _main([PLAIN])
        self.assertNotIn(todo_run.W_PULL, screen)


if __name__ == '__main__':
    unittest.main()
