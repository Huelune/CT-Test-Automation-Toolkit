"""(조사용) CT에 든 Java와 FST로 `.utest`를 객체로 읽을 수 있는지 본다 (todo.md 26절).

`java_probe.py <처음 폴더> <체크한 뒤 폴더>`. 24절의 `out\\17`(CT가 처음 만든 `dmy_carry` 테스트)과 `out\\18`(전역 변수를
손으로 체크한 뒤)을 받는다. 환경 변수 `CT_HOME`의 CT 설치에서 다음을 찾는다.

- `java.exe`와 그 버전, 컴파일러 모듈(`jdk.compiler`), `javac.exe`, ECJ(이클립스 컴파일러)
- FST(`FSTConfiguration`)와 CT 모델(`UtTest`) 클래스가 든 jar(jar 안의 jar도 본다)

그다음 `tools/java/UtestDump.java`를 CT의 Java로 돌린다(소스 바로 실행, 안 되면 ECJ나 javac로 컴파일). 두 `.utest`를 FST로
읽어 객체 그래프를 받고, 견본 변수 이름이 든 경로, 크기가 바뀐 모음, 값이 바뀐 경로를 찍는다. 24·25절에서 `.utest`가 FST 꼴로
보였고, 바이트만으로는 변수 항목을 끼울 수 없어 CT의 Java로 읽고 고치는 길을 사용자가 골랐다(2026-11-04).

화면에는 개수, 정해 둔 문구, CT 설치 폴더 기준 상대 경로(제품 폴더·jar 이름), Java 버전 줄, Java 클래스·필드 이름, 숫자, 견본
이름만 찍는다. 다른 글자열은 utest_probe.show의 모양(9·a·A)으로 가린다. 예외는 클래스 이름만 찍는다. 전체 그래프는
`%TEMP%`의 파일에만 쓴다.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from member_probe import WIDTH
from utest_probe import NAMES, _utests, show

SOURCE = Path(__file__).resolve().parent / 'java' / 'UtestDump.java'
MAIN = 'UtestDump'
# 미리 컴파일한 클래스(Java 11 바이트코드). CT의 Java 21에는 컴파일러가 없고 CT 안의 ECJ는 2015년 판이라
# 컴파일하지 못했다(2026-11-04 26절). 소스를 고치면 다시 컴파일하고 SOURCE_SHA를 고친다(tools/java/README.md).
COMPILED = SOURCE.with_suffix('.class')
SOURCE_SHA = SOURCE.parent / 'UtestDump.sha256'
MARKERS = {
    'FST': ('org/nustaq/serialization/FSTConfiguration.class',
            'de/ruedigermoeller/serialization/FSTConfiguration.class'),
    'CT 모델': ('com/codescroll/ut/core/common/model/UtTest.class',),
    'ECJ': ('org/eclipse/jdt/internal/compiler/batch/Main.class',),
}
OPENS = ['java.base/' + p for p in ('java.lang', 'java.lang.reflect', 'java.lang.invoke', 'java.util',
                                     'java.util.concurrent', 'java.util.concurrent.atomic', 'java.text', 'java.math',
                                     'java.net', 'java.io', 'java.nio', 'java.time', 'sun.nio.ch')]
DUMP = 'ct_java_probe.txt'
E_ARGS = '[ERROR] 폴더 둘을 받지 못함: todo.bat 26으로 돌리기'
E_HOME = '[ERROR] CT 설치 폴더를 받지 못함: todo.bat 26을 다시 돌리고 물으면 CT 설치 폴더를 끌어다 놓기'
E_ONE = '[ERROR] {} 폴더의 dmy_carry 테스트 .utest가 {}개: todo.md 24절대로 내보낸 폴더를 그대로 두기'

Runner = Callable[[List[str]], Tuple[int, str, str]]
Node = Tuple[str, str]  # (타입, 값)


def run_cmd(args: List[str], timeout: int = 300) -> Tuple[int, str, str]:
    """(종료 코드, 표준 출력, 표준 오류). 실행하지 못하면 (-1, '', 예외 이름)."""
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return -1, '', type(exc).__name__
    return proc.returncode, proc.stdout.decode('utf-8', 'replace'), proc.stderr.decode('utf-8', 'replace')


class Found:
    """CT 설치에서 찾은 것. 경로는 절대 경로, rel은 화면용 상대 경로."""

    def __init__(self) -> None:
        self.jars: List[Path] = []
        self.bad_jars = 0
        self.javas: List[Path] = []
        self.javacs: List[Path] = []
        self.hits: Dict[str, List[str]] = {label: [] for label in MARKERS}
        self.roots: List[Path] = []  # 폴더로 풀린 번들의 클래스 뿌리
        self.nested: List[Tuple[Path, str]] = []  # (바깥 jar, 안의 jar 이름): 클래스 경로에 넣으려면 꺼내야 한다


def _marker(name: str) -> Optional[str]:
    for label, entries in MARKERS.items():
        if name in entries:
            return label
    return None


def scan(home: Path) -> Found:
    found = Found()
    for top, dirs, files in os.walk(home):
        dirs[:] = [d for d in dirs if d.lower() != 'backup']  # CT의 backup\init 아래 옛 사본(26절)
        for file in files:
            path = Path(top) / file
            low = file.lower()
            rel = path.relative_to(home)
            if low == 'java.exe':
                found.javas.append(path)
            elif low == 'javac.exe':
                found.javacs.append(path)
            elif low.endswith('.class'):
                posix = rel.as_posix()
                for label, entries in MARKERS.items():
                    for entry in entries:
                        if posix.endswith('/' + entry):
                            found.hits[label].append(posix[:-len(entry)].rstrip('/') or '.')
                            found.roots.append(Path(str(path)[:-len(entry)]))
            elif low.endswith('.jar'):
                found.jars.append(path)
                _scan_jar(path, rel.as_posix(), found)
    return found


def _scan_jar(path: Path, rel: str, found: Found) -> None:
    try:
        with zipfile.ZipFile(path) as jar:
            names = jar.namelist()
            for name in names:
                label = _marker(name)
                if label:
                    found.hits[label].append(rel)
            for inner in (n for n in names if n.lower().endswith('.jar')):
                try:
                    with zipfile.ZipFile(io.BytesIO(jar.read(inner))) as nested:
                        labels = {_marker(n) for n in nested.namelist()} - {None}
                except (zipfile.BadZipFile, OSError, RuntimeError):
                    continue
                for label in labels:
                    found.hits[label].append('{}!/{}'.format(rel, inner))
                found.nested.append((path, inner))
    except (zipfile.BadZipFile, OSError, RuntimeError):
        found.bad_jars += 1


def pick_java(found: Found) -> Optional[Path]:
    """CT 안의 `bin\\java.exe`를 먼저, 없으면 PATH의 java."""
    inside = sorted(found.javas, key=lambda p: (p.parent.name.lower() != 'bin', len(p.parts)))
    if inside:
        return inside[0]
    which = shutil.which('java')
    return Path(which) if which else None


def java_info(java: Path, run: Runner) -> Tuple[int, str, bool]:
    """(주 버전, 버전 첫 줄, jdk.compiler 모듈 유무)."""
    _, out, err = run([str(java), '-version'])
    first = ((err or out).strip().splitlines() or [''])[0]
    m = re.search(r'version "(\d+)(?:\.(\d+))?', first)
    major = 0 if not m else (int(m.group(2) or 0) if m.group(1) == '1' else int(m.group(1)))
    compiler = False
    if major >= 9:
        code, mods, _ = run([str(java), '--list-modules'])
        compiler = code == 0 and re.search(r'^jdk\.compiler@', mods, re.M) is not None
    return major, re.sub(r'[^\w ."\-+()]', '?', first)[:90], compiler


def _argfile(work: Path, classpath: List[Path], major: int) -> Path:
    """java 실행 인수 파일. 경로는 /로 쓴다(인수 파일 안에서 \\는 이스케이프다)."""
    lines = ['-cp', '"{}"'.format(os.pathsep.join(p.as_posix() for p in classpath)), '-Dfile.encoding=UTF-8']
    if major >= 9:
        for module in OPENS:
            lines += ['--add-opens', '{}=ALL-UNNAMED'.format(module)]
    path = work / 'java_args.txt'
    text = '\n'.join(lines) + '\n'
    try:  # java 런처는 인수 파일을 시스템 코드 페이지로 읽는다(임시 폴더 경로에 한글 계정 이름이 있을 수 있다)
        path.write_bytes(text.encode(_ansi()))
    except (UnicodeEncodeError, LookupError):
        path.write_text(text, encoding='utf-8')
    return path


def _ansi() -> str:
    if os.name != 'nt':
        return 'utf-8'
    import ctypes
    return 'cp{}'.format(ctypes.windll.kernel32.GetACP())


def _extract_nested(found: Found, work: Path) -> List[Path]:
    out: List[Path] = []
    for n, (outer, inner) in enumerate(found.nested):
        target = work / 'nested' / '{}_{}'.format(n, Path(inner).name)
        try:
            with zipfile.ZipFile(outer) as jar:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(jar.read(inner))
            out.append(target)
        except (zipfile.BadZipFile, OSError, KeyError, RuntimeError):
            continue
    return out


def prepare(java: Path, major: int, compiler: bool, found: Found, work: Path,
            run: Runner) -> Tuple[str, Optional[Callable[[Path], List[str]]]]:
    """(읽는 방법 이름, `.utest` 경로를 받아 java 명령을 돌려주는 함수). 방법이 없으면 None."""
    classpath = found.roots + found.jars + _extract_nested(found, work)
    if major >= 11 and COMPILED.is_file():
        args = _argfile(work, [COMPILED.parent] + classpath, major)
        return '미리 컴파일한 클래스', lambda utest: [str(java), '@' + str(args), MAIN, str(utest)]
    if major >= 11 and compiler:
        args = _argfile(work, classpath, major)
        return '소스 바로 실행', lambda utest: [str(java), '@' + str(args), str(SOURCE), str(utest)]
    classes = work / 'classes'
    classes.mkdir(parents=True, exist_ok=True)
    ecj = next((p for p in found.jars if any(h == p.name or h.endswith('/' + p.name) for h in found.hits['ECJ'])), None)
    if ecj is not None:
        how = 'ECJ로 컴파일'
        code, _, _ = run([str(java), '-cp', str(ecj), 'org.eclipse.jdt.internal.compiler.batch.Main', '-source', '1.8',
                          '-target', '1.8', '-nowarn', '-encoding', 'UTF-8', '-d', str(classes), str(SOURCE)])
    elif found.javacs:
        how = 'javac로 컴파일'
        code, _, _ = run([str(found.javacs[0]), '-encoding', 'UTF-8', '-d', str(classes), str(SOURCE)])
    else:
        return '컴파일 수단 없음', None
    if code != 0 or not (classes / (MAIN + '.class')).is_file():
        return how + ' 실패', None
    args = _argfile(work, [classes] + classpath, major)
    return how, lambda utest: [str(java), '@' + str(args), MAIN, str(utest)]


def parse_dump(text: str) -> Tuple[Optional[str], List[str], Optional[str], Dict[str, Node]]:
    """(OK 줄의 'FST 클래스 공장', TRY 사슬들, FAIL 사슬, 경로 -> (타입, 값))."""
    ok, fail = None, None
    tries: List[str] = []
    nodes: Dict[str, Node] = {}
    for line in text.splitlines():
        parts = line.split('\t')
        if parts[0] == 'OK' and len(parts) >= 3:
            ok = '{} {}'.format(parts[1].rsplit('.', 1)[0], parts[2])
        elif parts[0] == 'TRY' and len(parts) >= 3:
            tries.append(parts[2])
        elif parts[0] == 'FAIL' and len(parts) >= 2:
            fail = parts[1]
        elif parts[0] == 'N' and len(parts) >= 4:
            nodes[parts[1] or '/'] = (parts[2], parts[3])
    return ok, tries, fail, nodes


def safe_chain(chain: str) -> str:
    """예외 사슬에서 Java 이름 꼴만 남긴다."""
    return re.sub(r'[^\w.$<>() /]', '?', chain)[:110]


def value_text(node: Node) -> str:
    kind, value = node
    if kind == 'String':
        return show(value)
    return kind.rsplit('.', 1)[-1] if value == 'object' else value


def compare(a: Dict[str, Node], b: Dict[str, Node]) -> Tuple[List[str], List[str], List[str]]:
    """(이름 위치 줄, 크기가 바뀐 모음 줄, 같은 경로에서 값이 바뀐 줄)."""
    where: List[str] = []
    for name in NAMES:
        pa = next((p for p, (k, v) in a.items() if k == 'String' and v == name), '-')
        pb = next((p for p, (k, v) in b.items() if k == 'String' and v == name), '-')
        if pa != '-' or pb != '-':
            where.append('{}: 처음 {}  뒤 {}'.format(name, pa, pb))
    sizes, changed = [], []
    for path, (kind, value) in a.items():
        if path not in b:
            continue
        kind_b, value_b = b[path]
        if value.startswith(('size ', 'len ')) and value != value_b:
            sizes.append('{} ({}): {} → {}'.format(path, kind.rsplit('.', 1)[-1], value, value_b))
        elif (kind, value) != (kind_b, value_b) and kind != 'ref':
            changed.append('{}: {} → {}'.format(path, value_text((kind, value)), value_text((kind_b, value_b))))
    return where, sizes, changed


def _wrap(text: str, limit: int = 2) -> List[str]:
    lines = textwrap.wrap(text, WIDTH, initial_indent='  ', subsequent_indent='    ', break_on_hyphens=False)
    return lines[:limit] if len(lines) <= limit else lines[:limit - 1] + [lines[limit - 1][:WIDTH - 1] + '…']


def main(argv: Sequence[str], environ=None, run: Runner = run_cmd) -> int:
    environ = os.environ if environ is None else environ
    if len(argv) != 2:
        print(E_ARGS)
        return 1
    utests = []
    for label, folder in (('처음', Path(argv[0])), ('체크한 뒤', Path(argv[1]))):
        found_utests = _utests(folder)
        if len(found_utests) != 1:
            print(E_ONE.format(label, len(found_utests)))
            return 1
        utests.append(found_utests[0])
    home = Path(environ.get('CT_HOME', '').strip().strip('"') or '.')
    if not environ.get('CT_HOME', '').strip() or not home.is_dir():
        print(E_HOME)
        return 1
    found = scan(home)
    java = pick_java(found)
    print('CT 설치: jar {}개(못 읽은 jar {}), java.exe {}개, javac.exe {}개'.format(
        len(found.jars), found.bad_jars, len(found.javas), len(found.javacs)))
    for label, hits in found.hits.items():
        print(_wrap('{}: {}'.format(label, ', '.join(sorted(set(hits))[:3]) or '없음'), 1)[0])
    if java is None:
        print('  Java: 없음. CT 안에도 PATH에도 java.exe가 없음')
        return 0
    major, first, compiler = java_info(java, run)
    where = java.relative_to(home).as_posix() if home in java.parents else '(PATH)'
    print('  Java: {} | {} | 컴파일러 모듈 {}'.format(where, first, '있음' if compiler else '없음'))
    dump: List[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        how, command = prepare(java, major, compiler, found, Path(tmp), run)
        print('읽는 방법: {}'.format(how))
        graphs: List[Optional[Dict[str, Node]]] = []
        for label, utest in zip(('처음', '체크한 뒤'), utests):
            if command is None:
                graphs.append(None)
                continue
            code, out, err = run(command(utest))
            ok, tries, fail, nodes = parse_dump(out)
            dump += ['## {} (종료 {})'.format(label, code)] + out.splitlines()
            if ok:
                print('  {} 읽기: {}로 읽음, 노드 {}개'.format(label, ok, len(nodes)))
                graphs.append(nodes)
            else:
                reason = fail or (tries[-1] if tries else 'Java 실행 실패(종료 {}, 오류 {}줄)'.format(
                    code, len(err.splitlines())))
                print(_wrap('{} 읽기 실패: {}'.format(label, safe_chain(reason)), 2)[0])
                graphs.append(None)
    if graphs and graphs[0] is not None and graphs[1] is not None:
        where_lines, sizes, changed = compare(graphs[0], graphs[1])
        root = graphs[0].get('/', ('?', ''))[0]
        print('뿌리 {}, 노드 {} → {}'.format(root, len(graphs[0]), len(graphs[1])))
        print('이름 위치:')
        for line in where_lines:
            print(_wrap(line, 1)[0])
        print('크기가 바뀐 모음 {}:'.format(len(sizes)))
        for line in sizes[:6]:
            print(_wrap(line, 1)[0])
        print('값이 바뀐 경로 {}:'.format(len(changed)))
        for line in changed[:6]:
            print(_wrap(line, 1)[0])
        dump += ['## 이름 위치'] + where_lines + ['## 크기'] + sizes + ['## 바뀐 값'] + changed
    try:
        (Path(tempfile.gettempdir()) / DUMP).write_text('\n'.join(dump) + '\n', encoding='utf-8')
        print('전체 그래프: %TEMP%\\{}(밖으로 보내지 않기)'.format(DUMP))
    except OSError:
        print('[WARN] 전체 그래프 파일을 쓰지 못함: 임시 폴더 권한 확인')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
