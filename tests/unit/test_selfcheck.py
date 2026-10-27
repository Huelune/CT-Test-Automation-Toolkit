"""ct_toolkit.selfcheck 단위 테스트 (stdlib unittest).

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))

from ct_toolkit import selfcheck as sc  # noqa: E402
from ct_toolkit.log import RunLog  # noqa: E402

SECRET = 'secret_customer_dir'


def _make_utcli(home: Path, plugin: str) -> Path:
    exe = home / 'plugins' / plugin / 'bin' / 'UtCLI.exe'
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text('', encoding='utf-8')
    return exe


def _make_csc(home: Path) -> Path:
    exe = home / 'csc.exe'
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_text('', encoding='utf-8')
    return exe


class FindCtCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name) / SECRET

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_nothing_set(self) -> None:
        c = sc.find_ct_cli({})
        self.assertEqual((c.status, c.required), (sc.FAIL, True))
        self.assertIn('CT_HOME', c.detail)

    def test_ct_home_missing_folder(self) -> None:
        c = sc.find_ct_cli({'CT_HOME': str(self.home)})
        self.assertEqual(c.status, sc.FAIL)
        self.assertIn('폴더가 없음', c.detail)

    def test_ct_home_without_cli(self) -> None:
        self.home.mkdir(parents=True)
        c = sc.find_ct_cli({'CT_HOME': str(self.home)})
        self.assertEqual(c.status, sc.FAIL)
        self.assertIn('csc.exe', c.detail)
        self.assertIn('UtCLI.exe', c.detail)

    def test_ct_home_finds_csc_and_hides_path(self) -> None:
        _make_csc(self.home)
        c = sc.find_ct_cli({'CT_HOME': str(self.home)})
        self.assertEqual(c.status, sc.OK)
        self.assertIn('csc.exe', c.detail)
        self.assertNotIn('UtCLI', c.detail)
        self.assertNotIn(SECRET, c.detail)

    def test_ct_home_with_csc_and_utcli_reports_both(self) -> None:
        _make_csc(self.home)
        _make_utcli(self.home, 'com.codescroll.ut_ut_3.6.2')
        c = sc.find_ct_cli({'CT_HOME': str(self.home)})
        self.assertEqual(c.status, sc.OK)
        self.assertIn('csc.exe', c.detail)
        self.assertIn('com.codescroll.ut_ut_3.6.2', c.detail)

    def test_ct_home_finds_plugin_and_hides_path(self) -> None:
        _make_utcli(self.home, 'com.codescroll.ut_ut_3.6.2')
        c = sc.find_ct_cli({'CT_HOME': '"{}"'.format(self.home)})
        self.assertEqual(c.status, sc.OK)
        self.assertIn('com.codescroll.ut_ut_3.6.2', c.detail)
        self.assertNotIn(SECRET, c.detail)

    def test_several_plugins_reports_count(self) -> None:
        _make_utcli(self.home, 'com.codescroll.ut_ut_3.5.0')
        _make_utcli(self.home, 'com.codescroll.ut_ut_3.6.2')
        c = sc.find_ct_cli({'CT_HOME': str(self.home)})
        self.assertIn('3.6.2', c.detail)
        self.assertIn('후보 2개', c.detail)

    def test_ct_utcli_wins_over_ct_home(self) -> None:
        exe = _make_utcli(self.home, 'com.codescroll.ut_ut_3.6.2')
        c = sc.find_ct_cli({'CT_UTCLI': str(exe), 'CT_HOME': 'nowhere'})
        self.assertEqual(c.status, sc.OK)
        self.assertIn('CT_UTCLI', c.detail)
        self.assertNotIn(SECRET, c.detail)

    def test_ct_utcli_missing_file(self) -> None:
        c = sc.find_ct_cli({'CT_UTCLI': str(self.home / 'UtCLI.exe')})
        self.assertEqual(c.status, sc.FAIL)
        self.assertNotIn(SECRET, c.detail)


class SimpleChecksTest(unittest.TestCase):
    def test_python_version(self) -> None:
        self.assertEqual(sc.check_python((3, 8, 0)).status, sc.OK)
        self.assertEqual(sc.check_python((3, 7, 9)).status, sc.FAIL)

    def test_openpyxl_missing_is_warning(self) -> None:
        def fail(_name):
            raise ImportError

        c = sc.check_openpyxl(fail)
        self.assertEqual((c.status, c.required), (sc.WARN, False))

    def test_git_missing_is_warning(self) -> None:
        self.assertEqual(sc.check_git(lambda _n: None).status, sc.WARN)
        self.assertEqual(sc.check_git(lambda _n: 'git').status, sc.OK)


class RenderTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.console = io.StringIO()
        self.log = RunLog('selfcheck', log_dir=Path(self._tmp.name), console=self.console)

    def tearDown(self) -> None:
        self.log.close()
        self._tmp.cleanup()

    def test_exit_code_follows_required_checks_only(self) -> None:
        checks = [sc.Check('a', sc.OK, 'a', True), sc.Check('b', sc.WARN, 'b', False)]
        self.assertEqual(sc.render(checks, self.log), 0)
        self.assertIn('필수 통과 1 / 1, 경고 1', self.console.getvalue())

        checks.append(sc.Check('c', sc.FAIL, 'c', True))
        self.assertEqual(sc.render(checks, self.log), 1)

    def test_full_run_fits_one_screen_and_hides_paths(self) -> None:
        env = {'CT_HOME': os.path.join(self._tmp.name, SECRET)}
        code = sc.render(sc.run_checks(self.log, env), self.log)
        shown = self.console.getvalue()
        self.assertEqual(code, 1)  # CT CLI 없음
        self.assertLessEqual(len(shown.splitlines()), 40)
        self.assertTrue(all(len(line) <= 120 for line in shown.splitlines()))
        self.assertNotIn(SECRET, shown)
        self.assertNotIn(self._tmp.name, shown)


if __name__ == '__main__':
    unittest.main()
