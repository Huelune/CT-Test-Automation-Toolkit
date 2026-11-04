"""tools/java_probe.py 단위 테스트 (stdlib unittest). Java는 돌리지 않고 명령 실행을 흉내 낸다.

실행:
    python -m unittest discover -s tests/unit
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import java_probe  # noqa: E402
from test_member_probe import _put  # noqa: E402

FST = 'org/nustaq/serialization/FSTConfiguration.class'
MODEL = 'com/codescroll/ut/core/common/model/UtTest.class'


def _jar(path: Path, entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w') as jar:
        for name, data in entries.items():
            jar.writestr(name, data)


def _nested(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as jar:
        for name, data in entries.items():
            jar.writestr(name, data)
    return buf.getvalue()


BEFORE = '\n'.join([
    'TRY\tcreateDefaultConfiguration\tjava.io.IOException < secret C:\\Users\\secret_acct',
    'OK\torg.nustaq.serialization.FSTConfiguration\tcreateUnsafeBinaryConfiguration',
    'N\t\tcom.codescroll.ut.core.common.model.UtTest\tobject',
    'N\t.path\tString\tC:\\secret_dir\\dmy_carry.c',
    'N\t.globals\tjava.util.ArrayList\tsize 1',
    'N\t.globals[0]\tcom.codescroll.ut.core.common.model.UtVar\tobject',
    'N\t.globals[0].name\tString\tdmy_c_direct',
    'N\t.globals[0].io\tenum com.codescroll.Io\tOUT',
    'N\t.hash\tString\tSECRET_dmy_carry736104709',
])
AFTER = '\n'.join([
    'OK\torg.nustaq.serialization.FSTConfiguration\tcreateUnsafeBinaryConfiguration',
    'N\t\tcom.codescroll.ut.core.common.model.UtTest\tobject',
    'N\t.path\tString\tC:\\secret_dir\\dmy_carry.c',
    'N\t.globals\tjava.util.ArrayList\tsize 2',
    'N\t.globals[0]\tcom.codescroll.ut.core.common.model.UtVar\tobject',
    'N\t.globals[0].name\tString\tdmy_c_callee',
    'N\t.globals[0].io\tenum com.codescroll.Io\tOUT',
    'N\t.globals[1]\tcom.codescroll.ut.core.common.model.UtVar\tobject',
    'N\t.globals[1].name\tString\tdmy_c_direct',
    'N\t.hash\tString\tSECRET_dmy_carry1411251611',
])


class JavaProbeTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'secret_root'
        self.home = self.root / 'CT'
        _jar(self.home / 'plugins' / 'org.nustaq.fst_2.57.jar', {FST: b''})
        _jar(self.home / 'plugins' / 'com.codescroll.ut.core.jar',
             {'lib/model.jar': _nested({MODEL: b''}), 'plugin.xml': b''})
        (self.home / 'jre' / 'bin').mkdir(parents=True)
        (self.home / 'jre' / 'bin' / 'java.exe').write_bytes(b'')
        (self.home / 'plugins' / 'broken.jar').write_bytes(b'not a zip')
        self.before, self.after = self.root / '17', self.root / '18'
        _put(self.before, 'dmy_carry_test0.utest', b'b')
        _put(self.after, 'dmy_carry_test0.utest', b'a')
        self.commands = []

    def _run(self, args):
        self.commands.append(args)
        if '-version' in args:
            return 0, '', 'openjdk version "17.0.9" 2023-10-17\nOpenJDK Runtime\n'
        if '--list-modules' in args:
            return 0, 'java.base@17.0.9\njdk.compiler@17.0.9\n', ''
        return 0, BEFORE if args[-1].endswith(str(Path('17') / 'UnitTests' / 'dmy_carry_test0.utest')) else AFTER, ''

    def _main(self, environ=None):
        buf = io.StringIO()
        with mock.patch.object(java_probe.tempfile, 'gettempdir', return_value=str(self.root)), \
                contextlib.redirect_stdout(buf):
            code = java_probe.main([str(self.before), str(self.after)],
                                   environ if environ is not None else {'CT_HOME': str(self.home)}, self._run)
        return code, buf.getvalue()

    def test_compiled_class_matches_source(self) -> None:
        import hashlib
        self.assertTrue(java_probe.COMPILED.is_file())
        expected = java_probe.SOURCE_SHA.read_text(encoding='utf-8').strip()
        self.assertEqual(hashlib.sha256(java_probe.SOURCE.read_bytes()).hexdigest(), expected,
                         'UtestDump.java가 바뀌었다: tools/java/README.md대로 다시 컴파일하고 해시를 고친다')

    def test_scan_skips_backup_copies(self) -> None:
        _jar(self.home / 'backup' / 'init' / 'plugins' / 'old_fst.jar', {FST: b''})
        found = java_probe.scan(self.home)
        self.assertEqual(found.hits['FST'], ['plugins/org.nustaq.fst_2.57.jar'])
        self.assertFalse(any('backup' in str(p) for p in found.jars))

    def test_scan_finds_markers_in_jars_and_nested_jars(self) -> None:
        found = java_probe.scan(self.home)
        self.assertEqual(found.hits['FST'], ['plugins/org.nustaq.fst_2.57.jar'])
        self.assertEqual(found.hits['CT 모델'], ['plugins/com.codescroll.ut.core.jar!/lib/model.jar'])
        self.assertEqual(found.bad_jars, 1)
        self.assertEqual(len(found.javas), 1)

    def test_main_reads_both_and_compares_without_secret(self) -> None:
        code, out = self._main()
        self.assertEqual(code, 0, out)
        self.assertNotIn('secret', out.lower())
        self.assertIn('Java: jre/bin/java.exe | openjdk version "17.0.9" 2023-10-17 | 컴파일러 모듈 있음', out)
        self.assertIn('읽는 방법: 미리 컴파일한 클래스', out)
        self.assertEqual(self.commands[-1][-2], java_probe.MAIN)
        self.assertIn('처음 읽기: org.nustaq.serialization createUnsafeBinaryConfiguration로 읽음, 노드 7개', out)
        self.assertIn('dmy_c_direct: 처음 .globals[0].name  뒤 .globals[1].name', out)
        self.assertIn('.globals (ArrayList): size 1 → size 2', out)
        self.assertIn('.globals[0].name: "dmy_c_direct" → "dmy_c_callee"', out)
        self.assertTrue(all(len(line) <= 120 for line in out.splitlines()))
        args_file = next(a for a in self.commands[-1] if a.startswith('@'))[1:]
        self.assertTrue(Path(args_file).name == 'java_args.txt')

    def test_failure_prints_only_java_names(self) -> None:
        self._run_old = self._run
        self._run = lambda args: (self._run_old(args) if '-version' in args or '--list-modules' in args
                                  else (1, 'FAIL\tjava.lang.ClassNotFoundException(com.codescroll.X) < '
                                        'java.io.IOException\n', 'secret stack'))
        code, out = self._main()
        self.assertEqual(code, 0, out)
        self.assertIn('처음 읽기 실패: java.lang.ClassNotFoundException(com.codescroll.X)', out)
        self.assertNotIn('secret', out.lower())

    def test_without_compiled_class_uses_source_or_reports_no_compiler(self) -> None:
        missing = Path(self.root / 'none.class')
        with mock.patch.object(java_probe, 'COMPILED', missing):
            code, out = self._main()
            self.assertIn('읽는 방법: 소스 바로 실행', out)
            self._run_old = self._run
            self._run = lambda args: ((0, 'java.base@17\n', '') if '--list-modules' in args else self._run_old(args))
            code, out = self._main()
        self.assertIn('읽는 방법: 컴파일 수단 없음', out)

    def test_missing_ct_home(self) -> None:
        code, out = self._main({})
        self.assertEqual(code, 1)
        self.assertIn(java_probe.E_HOME, out)


if __name__ == '__main__':
    unittest.main()
