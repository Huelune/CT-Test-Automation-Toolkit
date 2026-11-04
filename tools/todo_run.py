"""todo.md의 확인 명령을 절 번호로 골라 돌린다.

서버 PC는 PowerShell이 막혀 있고 명령을 창에 붙여 넣기도 어렵다. 그래서 저장소 루트의 `todo.bat`을
탐색기에서 더블클릭하면 `git pull` 뒤에 이 파일이 돈다. todo.md에 확인 명령이 있는 절을 더하거나
지울 때 SECTIONS도 함께 고친다.

화면에는 정해 둔 안내 문구와 확인 스크립트의 표준 출력만 찍는다. 입력받은 목록 경로는 찍지 않고,
고른 뒤에 화면을 지워 입력한 줄도 캡처에 남기지 않는다. 확인 스크립트의 표준 오류(예외 원문, 경고)는
경로가 들어 있을 수 있어 `%TEMP%`의 파일에만 쓰고, 화면에는 예외 종류와 파일 이름만 찍는다.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
LIST = '<목록>'  # 사용자가 창에 끌어다 놓은 목록 경로가 들어갈 자리

# 절 번호: (메뉴에 찍을 제목, 툴킷 Python에 넘길 인수). 상대 경로는 저장소 루트 기준이다.
SECTIONS = {}  # 지금 돌릴 절이 없다. 23절 확인은 tools/carry_probe.py <원래> <만든 뒤> <붙인 뒤>로 다시 돌릴 수 있다

E_NO_SECTION = '없는 절 번호: todo.bat을 다시 열고 위 목록의 번호를 넣기'
E_NO_LIST = '목록 경로가 비었음: todo.bat을 다시 열고 목록 파일을 창에 끌어다 놓은 뒤 Enter'
W_PULL = '[WARN] git pull 실패: 이전 코드로 돈다. 네트워크와 로컬 변경을 확인하고 다시 열기'
ERR_NAME = 'ct_todo_error.txt'
E_CRASH = '[ERROR] 예외로 멈춤({}): 이 화면을 보내 주기. 원문은 %TEMP%\\' + ERR_NAME + '(밖으로 보내지 않기)'
W_STDERR = '[WARN] 경고 출력이 있었음({}): 원문은 %TEMP%\\' + ERR_NAME + '(밖으로 보내지 않기)'


def clean_path(text: str) -> str:
    """창에 끌어다 놓으면 붙는 따옴표와 앞뒤 공백을 뗀다."""
    return text.strip().strip('"').strip()


def child_env() -> dict:
    """`ct.bat`처럼 `src`를 import 경로에 넣고 UTF-8로 돌린다."""
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join(p for p in (str(ROOT / 'src'), env.get('PYTHONPATH', '')) if p)
    env['PYTHONUTF8'] = '1'
    return env


def error_kind(stderr: str) -> str:
    """traceback 마지막 줄의 예외 이름만 낸다. 메시지 부분에는 경로나 값이 있을 수 있어 버리고,
    예외 이름 꼴(…Error, …Exception 등)이 아니면 파일 이름일 수 있어 찍지 않는다."""
    lines = [line for line in stderr.splitlines() if line.strip()]
    name = lines[-1].split(':', 1)[0].strip() if lines else ''
    pattern = r'(?:[A-Za-z_]\w*\.)*[A-Z]\w*(?:Error|Exception|Interrupt|Exit|Warning)'
    return name if re.fullmatch(pattern, name) else '종류 모름'


def warning_kinds(stderr: str) -> str:
    """경고 원문에서 경고 이름(UserWarning 등)만 모은다."""
    kinds = sorted(set(re.findall(r'\b([A-Z]\w*Warning)\b', stderr)))
    return ', '.join(kinds) if kinds else '종류 모름'


def run_child(args: List[str], cwd: str, env: dict) -> Tuple[int, str]:
    """표준 출력은 그대로 화면에 두고, 표준 오류만 받아 낸다."""
    proc = subprocess.run(args, cwd=cwd, env=env, stderr=subprocess.PIPE)
    return proc.returncode, proc.stderr.decode('utf-8', 'replace')


def clear() -> None:
    # cls는 cmd 내장 명령이라 셸이 필요하다. 고정 문자열만 넘긴다.
    os.system('cls' if os.name == 'nt' else 'clear')


def main(ask=input, run=run_child, clear_screen=clear) -> int:
    print('todo.md 확인 명령')
    for number, (title, _) in SECTIONS.items():
        print('  {}  {}'.format(number, title))
    number = ask('절 번호를 넣고 Enter: ').strip()
    if number not in SECTIONS:
        print(E_NO_SECTION)
        return 2
    title, args = SECTIONS[number]
    if LIST in args:
        path = clean_path(ask('목록 XLSX 파일을 이 창에 끌어다 놓고 Enter: '))
        if not path:
            print(E_NO_LIST)
            return 2
        args = [path if a == LIST else a for a in args]
    return run_toolkit('todo.md {}절: {}'.format(number, title), args, run, clear_screen)


def run_toolkit(title: str, args: List[str], run=run_child, clear_screen=clear) -> int:
    """화면을 지우고 제목을 찍은 뒤 툴킷 Python을 돌린다. `io_run.py`도 쓴다."""
    clear_screen()
    print(title)
    if os.environ.get('TODO_PULL') == 'fail':
        print(W_PULL)
    sys.stdout.flush()  # 확인 스크립트 출력보다 먼저 찍히게
    code, stderr = run([sys.executable] + args, cwd=str(ROOT), env=child_env())
    if stderr.strip():
        (Path(tempfile.gettempdir()) / ERR_NAME).write_text(stderr, encoding='utf-8')
        print(E_CRASH.format(error_kind(stderr)) if code else W_STDERR.format(warning_kinds(stderr)))
    print('exit={}'.format(code))
    return code


if __name__ == '__main__':
    sys.exit(main())
