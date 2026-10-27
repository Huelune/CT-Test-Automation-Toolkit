"""`python -m ct_toolkit <명령>` 진입점. 서버 PC에서는 `ct.bat <명령>`으로 부른다.

종료 코드: 0 성공, 1 점검·실행 실패, 2 잘못된 인자, 130 사용자 중단.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from . import paths, selfcheck
from .log import LEVELS, command_scope


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='ct.bat', description='CT Test Automation Toolkit')
    parser.add_argument('--console-level', default='STEP', choices=LEVELS,
                        help='콘솔에 찍을 최소 레벨 (기본 STEP). 파일 로그는 항상 전부 남는다')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('selfcheck', help='서버 PC 환경 점검')
    sub.add_parser('version', help='툴킷 버전')
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    if args.command == 'version':
        print(paths.version())
        return 0

    try:
        with command_scope(args.command, console_level=args.console_level) as log:
            if args.command == 'selfcheck':
                return selfcheck.main(log)
    except KeyboardInterrupt:
        return 130
    parser.error('알 수 없는 명령: {}'.format(args.command))
    return 2


if __name__ == '__main__':
    sys.exit(main())
