"""실행 로그.

모든 명령은 `command_scope`로 감싼다. 명령 하나가 로그 파일 하나
(`result/logs/<yyyyMMdd_HHmmss>_<명령>.log`)를 열고, 시작·끝 줄을 남긴다.

    with command_scope('selfcheck') as log:
        with log.checkpoint('UtCLI 탐색'):
            ...
        log.warn('openpyxl 없음', reason='ImportError')

레벨은 DEBUG < INFO < STEP < WARN < ERROR다. 콘솔에는 `console_level`(기본 STEP) 이상만
찍고, 파일에는 모든 레벨을 남긴다. 화면에는 사람이 읽을 결과만 찍고 진행 상황은 로그로
보내는 것이 원칙이다.

로그 파일을 열 수 없으면 WARN 한 줄을 콘솔에 찍고 콘솔만으로 계속한다. 로그를 못 쓴다고
명령이 멈추지 않는다.

**회사 내부 정보(고객 함수·파일 이름, 경로, 계정)를 메시지에 넣지 않는다.** 개수, 비율,
정해 둔 문구, 출력 파일 이름만 넣는다.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import re
import sys
import time
from pathlib import Path
from typing import Iterator, Optional, TextIO

from . import paths

LEVELS = ('DEBUG', 'INFO', 'STEP', 'WARN', 'ERROR')
_RANK = {name: rank for rank, name in enumerate(LEVELS)}
_SAFE_NAME = re.compile(r'[^A-Za-z0-9_.-]+')


def _rank(level: str) -> int:
    try:
        return _RANK[level.upper()]
    except KeyError:
        raise ValueError('알 수 없는 로그 레벨: {}'.format(level)) from None


class RunLog:
    """명령 하나의 실행 로그."""

    def __init__(self, command: str, console_level: str = 'STEP',
                 log_dir: Optional[Path] = None, console: Optional[TextIO] = None,
                 clock=None) -> None:
        self.command = command
        self.console_level = console_level.upper()
        _rank(self.console_level)
        self._console = console if console is not None else sys.stdout
        self._clock = clock or _dt.datetime.now
        self._file: Optional[TextIO] = None
        self.path: Optional[Path] = None
        self.counts = {name: 0 for name in LEVELS}
        self._open_file(log_dir if log_dir is not None else paths.log_dir())

    # -- 파일 ---------------------------------------------------------------

    def _open_file(self, directory: Path) -> None:
        stamp = self._clock().strftime('%Y%m%d_%H%M%S')
        name = '{}_{}.log'.format(stamp, _SAFE_NAME.sub('_', self.command) or 'command')
        try:
            directory.mkdir(parents=True, exist_ok=True)
            self.path = directory / name
            self._file = open(self.path, 'a', encoding='utf-8', newline='\n')
        except OSError as exc:
            self.path = None
            self._file = None
            self._emit_console('WARN', '로그 파일을 열 수 없어 콘솔에만 찍습니다 ({})'.format(
                type(exc).__name__))

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None

    # -- 쓰기 ---------------------------------------------------------------

    def _emit_console(self, level: str, message: str) -> None:
        if _rank(level) < _rank(self.console_level):
            return
        prefix = '' if level == 'STEP' else '[{}] '.format(level)
        try:
            self._console.write(prefix + message + '\n')
            self._console.flush()
        except UnicodeEncodeError:
            encoding = getattr(self._console, 'encoding', None) or 'ascii'
            safe = (prefix + message).encode(encoding, 'replace').decode(encoding)
            self._console.write(safe + '\n')

    def log(self, level: str, message: str, **context: object) -> None:
        level = level.upper()
        _rank(level)
        self.counts[level] += 1
        if context:
            message = '{} | {}'.format(
                message, ' '.join('{}={}'.format(k, v) for k, v in context.items()))
        if self._file is not None:
            stamp = self._clock().strftime('%Y-%m-%d %H:%M:%S')
            self._file.write('{} {:<5} {}\n'.format(stamp, level, message))
            self._file.flush()
        self._emit_console(level, message)

    def debug(self, message: str, **context: object) -> None:
        self.log('DEBUG', message, **context)

    def info(self, message: str, **context: object) -> None:
        self.log('INFO', message, **context)

    def step(self, message: str, **context: object) -> None:
        self.log('STEP', message, **context)

    def warn(self, message: str, **context: object) -> None:
        self.log('WARN', message, **context)

    def error(self, message: str, **context: object) -> None:
        self.log('ERROR', message, **context)

    @contextlib.contextmanager
    def checkpoint(self, name: str) -> Iterator[None]:
        """오래 걸리는 호출 앞뒤에 시작·끝 줄을 남긴다. 예외는 ERROR로 남기고 다시 던진다."""
        start = time.monotonic()
        self.info('-> {} 시작'.format(name))
        try:
            yield
        except BaseException as exc:
            self.error('-> {} 실패'.format(name), error=type(exc).__name__,
                       elapsed='{:.1f}s'.format(time.monotonic() - start))
            raise
        self.info('-> {} 끝'.format(name), elapsed='{:.1f}s'.format(time.monotonic() - start))


@contextlib.contextmanager
def command_scope(command: str, console_level: str = 'STEP',
                  log_dir: Optional[Path] = None,
                  console: Optional[TextIO] = None) -> Iterator[RunLog]:
    """명령 하나의 로그 범위. 끝 줄은 DONE, FAILED, INTERRUPTED 중 하나다."""
    log = RunLog(command, console_level=console_level, log_dir=log_dir, console=console)
    start = time.monotonic()
    log.info('==> {} START'.format(command), version=paths.version(),
             python='{}.{}.{}'.format(*sys.version_info[:3]))
    try:
        yield log
    except KeyboardInterrupt:
        log.warn('<== {} INTERRUPTED'.format(command),
                 elapsed='{:.1f}s'.format(time.monotonic() - start))
        raise
    except BaseException as exc:
        log.error('<== {} FAILED'.format(command), error=type(exc).__name__,
                  elapsed='{:.1f}s'.format(time.monotonic() - start))
        raise
    else:
        log.info('<== {} DONE'.format(command), elapsed='{:.1f}s'.format(time.monotonic() - start),
                 warn=log.counts['WARN'], error=log.counts['ERROR'])
    finally:
        log.close()
