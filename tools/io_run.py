"""실제 작업에서 `ct.bat io-apply --list … --export …`를 돌린다.

서버 PC는 명령을 창에 칠 수 없다. 그래서 저장소 루트의 `io-apply.bat`을 탐색기에서 더블클릭하면
`git pull` 뒤에 이 파일이 돌고, 목록 XLSX와 CT에서 내보낸 폴더를 창에 끌어다 놓게 한다.

받은 경로는 화면에 찍지 않고, 다 받은 뒤 화면을 지워 입력한 줄도 캡처에 남기지 않는다. 표준 오류는
`todo_run.py`와 같이 `%TEMP%`의 파일에만 쓴다.
"""

from __future__ import annotations

import sys

from todo_run import clean_path, clear, run_child, run_toolkit

E_NO_LIST = '목록 경로가 비었음: io-apply.bat을 다시 열고 목록 XLSX 파일을 창에 끌어다 놓은 뒤 Enter'
E_NO_EXPORT = '내보낸 폴더 경로가 비었음: io-apply.bat을 다시 열고 CT에서 내보낸 폴더를 창에 끌어다 놓은 뒤 Enter'
E_RESET = 'y나 n이 아님: io-apply.bat을 다시 열고 y나 n을 넣기'


def main(ask=input, run=run_child, clear_screen=clear) -> int:
    print('입력·출력 지정 (io-apply)')
    list_path = clean_path(ask('목록 XLSX 파일을 이 창에 끌어다 놓고 Enter: '))
    if not list_path:
        print(E_NO_LIST)
        return 2
    export = clean_path(ask('CT [테스트 내보내기]로 내보낸 폴더를 이 창에 끌어다 놓고 Enter: '))
    if not export:
        print(E_NO_EXPORT)
        return 2
    print('지정을 바꾼 테스트의 케이스를 모두 지우고 값 없는 케이스 하나만 둘까요?')
    print('  y  CT가 막 만든 테스트(값을 아직 안 넣음)')
    print('  n  값을 넣은 테스트(값을 남김)')
    reset = ask('y나 n을 넣고 Enter: ').strip().lower()
    if reset not in ('y', 'n'):
        print(E_RESET)
        return 2
    args = ['-m', 'ct_toolkit', 'io-apply', '--list', list_path, '--export', export]
    if reset == 'y':
        args.append('--reset-cases')
    title = '입력·출력 지정: 케이스 정리 {}'.format('함' if reset == 'y' else '안 함')
    return run_toolkit(title, args, run, clear_screen)


if __name__ == '__main__':
    sys.exit(main())
