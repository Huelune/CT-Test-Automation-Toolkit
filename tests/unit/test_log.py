"""ct_toolkit.log 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from ct_toolkit.log import RunLog, command_scope  # noqa: E402


class CommandScopeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.console = io.StringIO()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _only_log(self) -> str:
        files = list(self.dir.glob('*.log'))
        self.assertEqual(len(files), 1)
        return files[0].read_text(encoding='utf-8')

    def test_file_has_all_levels_console_only_step_and_above(self) -> None:
        with command_scope('demo', log_dir=self.dir, console=self.console) as log:
            log.debug('d-line')
            log.info('i-line')
            log.step('s-line')
            log.warn('w-line', reason='x')
        text = self._only_log()
        for word in ('d-line', 'i-line', 's-line', 'w-line | reason=x', '==> demo START',
                     '<== demo DONE'):
            self.assertIn(word, text)
        shown = self.console.getvalue()
        self.assertNotIn('d-line', shown)
        self.assertNotIn('i-line', shown)
        self.assertIn('s-line', shown)
        self.assertIn('[WARN] w-line', shown)

    def test_file_name_has_timestamp_and_command(self) -> None:
        with command_scope('self check', log_dir=self.dir, console=self.console):
            pass
        name = next(self.dir.glob('*.log')).name
        self.assertRegex(name, r'^\d{8}_\d{6}_self_check\.log$')

    def test_failure_writes_failed_line_and_reraises(self) -> None:
        with self.assertRaises(RuntimeError):
            with command_scope('demo', log_dir=self.dir, console=self.console):
                raise RuntimeError('boom')
        text = self._only_log()
        self.assertIn('<== demo FAILED | error=RuntimeError', text)
        self.assertNotIn('DONE', text)

    def test_interrupt_writes_interrupted_line(self) -> None:
        with self.assertRaises(KeyboardInterrupt):
            with command_scope('demo', log_dir=self.dir, console=self.console):
                raise KeyboardInterrupt
        self.assertIn('<== demo INTERRUPTED', self._only_log())

    def test_checkpoint_logs_start_end_and_failure(self) -> None:
        with command_scope('demo', log_dir=self.dir, console=self.console) as log:
            with log.checkpoint('first'):
                pass
            with self.assertRaises(ValueError):
                with log.checkpoint('second'):
                    raise ValueError
        text = self._only_log()
        self.assertIn('-> first 시작', text)
        self.assertIn('-> first 끝', text)
        self.assertIn('-> second 실패 | error=ValueError', text)

    def test_unwritable_log_dir_falls_back_to_console(self) -> None:
        blocker = self.dir / 'not_a_dir'
        blocker.write_text('x', encoding='utf-8')
        log = RunLog('demo', log_dir=blocker / 'logs', console=self.console)
        log.step('still shown')
        log.close()
        self.assertIsNone(log.path)
        shown = self.console.getvalue()
        self.assertIn('[WARN] 로그 파일을 열 수 없어', shown)
        self.assertIn('still shown', shown)

    def test_unknown_level_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            RunLog('demo', console_level='LOUD', log_dir=self.dir, console=self.console)


if __name__ == '__main__':
    unittest.main()
