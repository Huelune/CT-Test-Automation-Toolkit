"""서버 PC 환경 점검 (`ct.bat selfcheck`).

한 화면에 항목당 한 줄을 찍는다. 사용자는 이 화면을 캡처 한 장으로 돌려준다.
경로와 계정은 찍지 않는다. CT 플러그인 폴더 이름(제품 버전이 들어 있다)은 찍는다.

필수 항목이 하나라도 FAIL이면 종료 코드 1, 아니면 0이다.
"""

from __future__ import annotations

import glob
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Mapping, Optional, Sequence

from . import paths
from .log import RunLog

MIN_PYTHON = (3, 8)
# CT 3.6 매뉴얼 CLI Execution 기준 위치: <CT 설치 폴더>\plugins\com.codescroll.ut_ut_3.x.x\bin
UTCLI_GLOB = os.path.join('plugins', 'com.codescroll.ut*', 'bin', 'UtCLI.exe')

OK, WARN, FAIL = 'OK', 'WARN', 'FAIL'


@dataclass
class Check:
    name: str
    status: str
    detail: str
    required: bool


def check_python(version_info: Sequence[int] = tuple(sys.version_info[:3])) -> Check:
    text = 'Python {}.{}.{}'.format(*version_info[:3])
    if tuple(version_info[:2]) >= MIN_PYTHON:
        return Check('python', OK, text, True)
    return Check('python', FAIL, '{} - 3.8 이상 필요'.format(text), True)


def check_openpyxl(importer: Callable[[str], object] = __import__) -> Check:
    try:
        module = importer('openpyxl')
    except ImportError:
        return Check('openpyxl', WARN,
                     'openpyxl 없음 - 보고서 기능 전에 pip install -r requirements.txt', False)
    return Check('openpyxl', OK, 'openpyxl {}'.format(getattr(module, '__version__', '?')), False)


def find_utcli(environ: Mapping[str, str]) -> Check:
    """`CT_UTCLI`(파일 경로)를 먼저 보고, 없으면 `CT_HOME` 아래를 찾는다."""
    direct = environ.get('CT_UTCLI', '').strip().strip('"')
    if direct:
        if Path(direct).is_file():
            return Check('utcli', OK, 'UtCLI.exe (CT_UTCLI)', True)
        return Check('utcli', FAIL, 'CT_UTCLI가 가리키는 파일이 없음', True)

    home = environ.get('CT_HOME', '').strip().strip('"')
    if not home:
        return Check('utcli', FAIL, 'CT_HOME, CT_UTCLI 둘 다 설정 안 됨', True)
    if not Path(home).is_dir():
        return Check('utcli', FAIL, 'CT_HOME 폴더가 없음', True)

    matches = sorted(glob.glob(os.path.join(home, UTCLI_GLOB)))
    if not matches:
        return Check('utcli', FAIL,
                     'CT_HOME 아래 plugins\\com.codescroll.ut*\\bin\\UtCLI.exe 없음', True)
    plugin = Path(matches[-1]).parent.parent.name
    extra = '' if len(matches) == 1 else ', 후보 {}개 중 마지막'.format(len(matches))
    return Check('utcli', OK, 'UtCLI.exe (CT_HOME, {}{})'.format(plugin, extra), True)


def check_log(log: RunLog) -> Check:
    if log.path is not None:
        return Check('log', OK, '로그 파일 쓰기', True)
    return Check('log', FAIL, '로그 파일을 열 수 없음 - result\\logs 쓰기 권한 확인', True)


def check_git(which: Callable[[str], Optional[str]] = shutil.which) -> Check:
    if which('git'):
        return Check('git', OK, 'git', False)
    return Check('git', WARN, 'git 없음 - 업데이트를 git pull로 받을 수 없음', False)


def check_console(stream=None) -> Check:
    stream = stream if stream is not None else sys.stdout
    return Check('console', OK, '콘솔 인코딩 {}'.format(getattr(stream, 'encoding', None) or '?'),
                 False)


def run_checks(log: RunLog, environ: Optional[Mapping[str, str]] = None) -> List[Check]:
    environ = os.environ if environ is None else environ
    checks = []
    for label, func in (
        ('Python', check_python),
        ('openpyxl', check_openpyxl),
        ('UtCLI 탐색', lambda: find_utcli(environ)),
        ('로그 쓰기', lambda: check_log(log)),
        ('git', check_git),
        ('콘솔', check_console),
    ):
        with log.checkpoint(label):
            try:
                result = func()
            except Exception as exc:  # 점검 하나가 터져도 나머지는 계속 본다
                result = Check(label, FAIL, '{} 점검 중 예외 {}'.format(label, type(exc).__name__),
                               True)
        log.info('selfcheck', name=result.name, status=result.status)
        checks.append(result)
    return checks


def render(checks: Sequence[Check], log: RunLog) -> int:
    """화면 출력. 종료 코드를 돌려준다."""
    log.step('CT Test Automation Toolkit {} 환경 점검'.format(paths.version()))
    for c in checks:
        log.step('  {:<5} {}'.format(c.status, c.detail))
    required = [c for c in checks if c.required]
    passed = sum(1 for c in required if c.status == OK)
    warned = sum(1 for c in checks if c.status == WARN)
    log.step('필수 통과 {} / {}, 경고 {}'.format(passed, len(required), warned))
    log.step('로그: {}'.format(log.path.name if log.path is not None else '(없음)'))
    return 0 if passed == len(required) else 1


def main(log: RunLog) -> int:
    return render(run_checks(log), log)
