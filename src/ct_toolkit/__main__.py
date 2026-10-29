"""`python -m ct_toolkit <명령>` 진입점. 서버 PC에서는 `ct.bat <명령>`으로 부른다.

종료 코드: 0 성공, 1 점검·실행 실패, 2 잘못된 인자, 130 사용자 중단.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import io_apply, paths, selfcheck
from .log import LEVELS, command_scope


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='ct.bat', description='CT Test Automation Toolkit')
    parser.add_argument('--console-level', default='STEP', choices=LEVELS,
                        help='콘솔에 찍을 최소 레벨 (기본 STEP). 파일 로그는 항상 전부 남는다')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('selfcheck', help='서버 PC 환경 점검')
    io = sub.add_parser('io-apply', help='목록(XLSX)대로 CT 테스트의 입력·출력 지정')
    io.add_argument('--list', dest='list_path', type=Path, required=True,
                    help='Codebeamer에서 내보낸 목록 XLSX')
    io.add_argument('--export', dest='export_dir', type=Path,
                    help='CT [테스트 내보내기] 폴더. 없으면 목록만 확인한다')
    io.add_argument('--reset-cases', action='store_true',
                    help='지정을 바꾼 테스트의 케이스를 모두 지우고 값 없는 케이스 하나만 둔다')
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
            if args.command == 'io-apply':
                return io_apply.main(log, args.list_path, args.export_dir, args.reset_cases)
    except KeyboardInterrupt:
        return 130
    parser.error('알 수 없는 명령: {}'.format(args.command))
    return 2


if __name__ == '__main__':
    sys.exit(main())
