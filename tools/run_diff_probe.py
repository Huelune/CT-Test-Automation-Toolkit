"""(조사용) CT에서 테스트를 돌리기 전후로 파일 목록을 비교해 어디에 무엇이 생기는지 본다 (todo.md 28절).

설계는 `docs/design/branch-table.md` 1단계(TC별 분기 표의 데이터가 어디에 남는지 찾기). 여러 뿌리 폴더의 파일 목록을 실행
전후로 찍어 새로 생기거나 바뀐 파일을 가리고, 그 파일에 견본 이름(`NAMES`)이 들었는지 꼴과 함께 본다. 이 파일은 그 부품이다
(목록 찍기, 비교, 꼴 판별, 이름 가리기).

화면에는 개수, 정해 둔 문구, 가린 상대 경로(`mask_path`), 꼴 이름, 견본 이름 수만 찍는다. 절대 경로, 계정 이름, 예외 메시지
원문은 찍지 않는다.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ct_toolkit import paths
from member_probe import WIDTH  # 화면 폭 규칙: 줄은 WIDTH를 넘지 않는다
from utest_probe import shape

NAMES: Tuple[str, ...] = ('dmy_branch', 'dmy_case_a', 'dmy_case_b', 'dmy_case_c', 'dmy_case_d')
Snap = Dict[str, Tuple[int, int]]  # 절대 경로 -> (크기, st_mtime_ns)
BIG = 64 << 20


def snapshot(roots: Sequence[Path]) -> Tuple[Snap, int]:
    """뿌리마다 파일 (크기, 수정 시각)을 모은다. 못 연 폴더나 못 읽은 파일은 세고 넘어간다(절대 경로 키라 중복 없음)."""
    snap: Snap = {}
    bad = 0

    def onerror(_exc: OSError) -> None:
        nonlocal bad
        bad += 1
    for root in roots:  # realpath: 8.3 짧은 이름·대소문자가 달라도 같은 파일은 같은 키
        for top, _dirs, files in os.walk(os.path.realpath(str(root)), onerror=onerror):
            for name in files:
                full = os.path.join(top, name)
                try:
                    st = os.stat(full)
                except OSError:
                    bad += 1
                    continue
                snap[full] = (st.st_size, st.st_mtime_ns)
    return snap, bad


def diff(before: Snap, after: Snap) -> Dict[str, List[str]]:
    return {
        'new': sorted(set(after) - set(before)),
        'changed': sorted(k for k in after if k in before and after[k] != before[k]),
        'removed': sorted(set(before) - set(after)),
    }


def locate(path: str, roots: Sequence[Tuple[str, Path]]) -> Tuple[str, str]:
    """경로를 품은 뿌리 중 가장 깊은 것의 (이름, 상대 경로). 없으면 ('?', 경로)."""
    real = Path(os.path.realpath(path))
    best: Optional[Tuple[str, Path]] = None
    for name, root in roots:
        r = Path(os.path.realpath(str(root)))
        try:
            real.relative_to(r)
        except ValueError:
            continue
        if best is None or len(r.parts) > len(best[1].parts):
            best = (name, r)
    if best is None:
        return '?', path
    return best[0], str(real.relative_to(best[1]))


def kind(head: bytes) -> str:
    if not head:
        return 'empty'
    for magic, name in ((b'PK\x03\x04', 'zip'), (b'\x1f\x8b', 'gzip'), (b'SQLite format 3\x00', 'sqlite'),
                        (b'H:2', 'h2'), (b'\xac\xed', 'java-ser')):
        if head.startswith(magic):
            return name
    if head[:2] == b'\x00\x01' and head[3:].startswith(b'com.'):
        return 'fst?'
    if head[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return 'utf16'
    if head.lstrip(b'\xef\xbb\xbf \t\r\n').startswith(b'<'):
        return 'xml'
    try:
        text = head.decode('utf-8')
    except UnicodeDecodeError as e:
        if e.start < len(head) - 3:  # 끝에서 잘린 글자 하나는 봐준다
            return 'binary'
        text = head[:e.start].decode('utf-8')
    return 'binary' if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', text) else 'text'


def _count(data: bytes) -> int:
    return sum(1 for n in NAMES if n.encode() in data or n.encode('utf-16-le') in data)


def names_found(path: Path, limit: int = BIG) -> Optional[int]:
    """`limit`보다 크거나 읽지 못하면 None, 아니면 ASCII나 UTF-16LE로 든 견본 이름 수."""
    try:
        if path.stat().st_size > limit:
            return None
        return _count(path.read_bytes())
    except OSError:
        return None


_KEEP_PART = re.compile(r'dmy_\w*|ctsample|\.[A-Za-z]\w*|(?:com|org|net|java|javax|jdk|sun)\.[\w.-]+', re.ASCII)


def mask_path(rel: str) -> str:
    out = []
    for part in re.split(r'[\\/]', rel):
        low = part.lower()
        if part.isascii() and (_KEEP_PART.fullmatch(part) or 'codescroll' in low or 'suresoft' in low):
            out.append(part)
            continue
        ext = re.search(r'\.[A-Za-z0-9]{1,8}$', part)
        cut = ext.start() if ext else len(part)
        out.append(shape(part[:cut], limit=10 ** 6) + part[cut:])
    return '\\'.join(out)


def zip_entries(path: Path) -> List[Tuple[str, int, str, Optional[int]]]:
    """(항목 이름 원문, 크기, 꼴, 견본 이름 수). zip이 아니면 []. 이름 원문은 호출한 쪽이 가려서 찍는다."""
    rows: List[Tuple[str, int, str, Optional[int]]] = []
    try:
        zf = zipfile.ZipFile(str(path))
    except (zipfile.BadZipFile, OSError):
        return []
    with zf:
        for info in zf.infolist():
            if info.filename.endswith('/'):
                continue
            try:
                data = zf.read(info) if info.file_size <= BIG else None
                head = data[:512] if data is not None else zf.open(info).read(512)
                rows.append((info.filename, info.file_size, kind(head), None if data is None else _count(data)))
            except Exception:  # 암호·미지원 압축·깨진 항목: 한 항목 때문에 멈추지 않는다
                rows.append((info.filename, info.file_size, 'unreadable', None))
    return rows


E_HOME = '[ERROR] CT 설치 폴더를 받지 못함: todo.bat 28을 다시 돌리고 물으면 CT 설치 폴더를 끌어다 놓기'
E_WS = '[ERROR] 작업 공간 폴더가 아님: todo.bat 28을 다시 돌리고 CT 작업 공간 폴더를 끌어다 놓기'
W_NONE = '[WARN] 실행 뒤 바뀐 파일 0: CT에서 테스트를 실제로 실행했는지 확인하고 다시 돌리기'
W_META = '[WARN] .metadata가 없음: 끌어다 놓은 폴더가 CT 작업 공간인지 확인'
W_JSON = '[WARN] run_diff.json을 쓰지 못함: result 폴더 쓰기 권한과 빈 공간을 확인하고 다시 돌리기'
P_WS = '견본 작업 공간 폴더(ctsample 프로젝트가 든 CT 작업 공간)를 이 창에 끌어다 놓고 Enter: '
P_RUN = 'CT에서 dmy_branch 테스트를 실행한 뒤 이 창에서 Enter: '
P_CSD = 'CT [내보내기] > [커버리지 내보내기]로 만든 .csd 파일을 끌어다 놓고 Enter(없으면 그냥 Enter): '
P_REOPEN = 'CT를 닫았다 다시 열고, 케이스 하나를 골라 소스 편집기에 참·거짓 표시가 보이면 이 창에서 Enter: '
M_SCAN = '파일 목록을 찍는 중(몇 분 걸릴 수 있음)…'
MAX_ROWS = 16
MAX_ENTRIES = 8
STATUS = (('new', '새'), ('changed', '바뀜'), ('removed', '지움'))


def _clear() -> None:
    os.system('cls' if os.name == 'nt' else 'clear')  # 고정 문자열만 넘긴다


def _clean(text: str) -> str:
    return text.strip().strip('"').strip()


def _n(count: Optional[int]) -> str:
    return '-' if count is None else '{}/{}'.format(count, len(NAMES))


def _fit(prefix: str, path: str, suffix: str = '') -> str:
    """줄이 WIDTH를 넘으면 경로 앞쪽을 …로 줄여 파일 이름을 남긴다."""
    room = WIDTH - len(prefix) - len(suffix)
    return prefix + (path if len(path) <= room else '…' + path[-(room - 1):]) + suffix


def _entry(path: str, status: str, before: Snap, after: Snap, roots: List[Tuple[str, Path]]) -> Dict[str, Any]:
    root, rel = locate(path, roots)
    removed = status == 'removed'
    head = b''
    if not removed:
        try:
            with open(path, 'rb') as fh:
                head = fh.read(32)
        except OSError:
            pass
    ct = root in ('WS', 'CT') or any(k in rel.lower() for k in ('codescroll', 'suresoft'))
    return {'path': path, 'root': root, 'rel': rel, 'status': status, 'size': (before if removed else after)[path][0],
            'kind': '-' if removed or not head else kind(head), 'head': head.hex(),
            'names': None if removed else names_found(Path(path)), 'ct': ct, 'reopen': '-'}


def _row(e: Dict[str, Any]) -> str:
    hexa = ' '.join('{:02x}'.format(b) for b in bytes.fromhex(e['head'])[:8]) or '-'
    shown = '?' if e['root'] == '?' else e['root'] + '\\' + mask_path(e['rel'])
    prefix = '{:<2} {:<4} {:>11} {:<8} {:<23}  {:<4}'.format(
        e['label'], e['reopen'], e['size'], e['kind'], hexa, _n(e['names']))
    return _fit(prefix + ' ', shown)


def summary_lines(counts: Dict[str, int], bad: int, secs: int, has_meta: bool, entries: List[Dict[str, Any]],
                  csd: Optional[Dict[str, Any]], reopen_new: int, json_ok: bool) -> List[str]:
    """화면에 찍을 줄. 개수, 정해 둔 문구, 가린 상대 경로, 꼴 이름만 쓴다."""
    out = ['28절 결과: 실행 전후 파일 비교']
    out.append('목록: {}개, 못 읽은 폴더 {}, 목록 찍기 3번 {}초'.format(
        ', '.join('{} {}'.format(k, v) for k, v in counts.items()), bad, secs))
    if not has_meta:
        out.append(W_META)
    if not entries:
        out.append(W_NONE)
    else:
        per = {k: sum(1 for e in entries if e['status'] == k) for k, _ in STATUS}
        by_root = ', '.join('{} {}'.format(r, sum(1 for e in entries if e['root'] == r)) for r in counts)
        out.append('실행 뒤: 새로 {}, 바뀜 {}, 지워짐 {} ({})'.format(per['new'], per['changed'], per['removed'], by_root))
        hit = [e for e in entries if e['names']]
        rows = sorted(hit + [e for e in entries if not e['names'] and e['ct']],
                      key=lambda e: (-(e['names'] or 0), not e['ct'], -e['size']))[:MAX_ROWS]
        out.append('견본 이름이 든 것 {}, CT 관련 경로 {}, 나머지 {}은 json에만'.format(
            len(hit), sum(1 for e in entries if not e['names'] and e['ct']), len(entries) - len(rows)))
        if rows:
            out.append('상태 다시연뒤      크기 꼴       앞 8바이트              이름 경로')
            out.extend(_row(e) for e in rows)
    if csd is None:
        out.append('.csd: 건너뜀')
    elif csd['kind'] is None:
        out.append('.csd: 파일을 못 읽음')
    else:
        zipped = csd['kind'] == 'zip'
        out.append('.csd: 크기 {}, 꼴 {}, 견본 이름 {}{}'.format(
            csd['size'], csd['kind'], _n(csd['names']), ', 항목 {}개'.format(len(csd['entries'])) if zipped else ''))
        for name, size, k, n in csd['entries'][:MAX_ENTRIES]:
            out.append(_fit('  항목 ', mask_path(name), ' {:>9} {:<8} 이름 {}'.format(size, k, _n(n))))
    total = sum(1 for e in entries if e['status'] != 'removed')
    reopen = {k: sum(1 for e in entries if e['reopen'] == k) for k in ('남음', '바뀜', '없음')}
    out.append('다시 연 뒤: 실행 때 생기거나 바뀐 {}개 중 남음 {}, 바뀜 {}, 없음 {}, 다시 열며 새로 바뀐 것 {}'.format(
        total, reopen['남음'], reopen['바뀜'], reopen['없음'], reopen_new))
    out.append('자세한 목록: result\\branch_probe\\run_diff.json' if json_ok else W_JSON)
    return out


def main(argv: Sequence[str], ask: Callable[[str], str] = input, clear: Callable[[], None] = _clear,
         environ: Optional[Mapping[str, str]] = None, out_dir: Optional[Path] = None) -> int:
    env = os.environ if environ is None else environ
    home = _clean(env.get('CT_HOME', ''))
    if not home or not Path(home).is_dir():
        print(E_HOME)
        return 2
    ws = _clean(ask(P_WS))
    clear()  # 끌어다 놓은 경로가 입력 줄에 남아 있다
    if not ws or not Path(ws).is_dir():
        print(E_WS)
        return 2
    roots: List[Tuple[str, Path]] = [('WS', Path(ws)), ('CT', Path(home))]
    for name in ('TEMP', 'APPDATA', 'LOCALAPPDATA'):
        value = _clean(env.get(name, ''))
        if value and Path(value).is_dir():
            roots.append((name, Path(value)))
    dirs = [r for _, r in roots]

    def scan() -> Tuple[Snap, int, float]:
        print(M_SCAN)
        t0 = time.monotonic()
        snap, bad = snapshot(dirs)
        return snap, bad, time.monotonic() - t0
    before, bad1, t1 = scan()
    ask(P_RUN)
    after, bad2, t2 = scan()
    delta = diff(before, after)
    entries = [dict(_entry(k, st, before, after, roots), label=label) for st, label in STATUS for k in delta[st]]
    csd_text = _clean(ask(P_CSD))
    clear()
    csd = None
    if csd_text:
        csd_path = Path(csd_text)
        csd = {'path': csd_text, 'kind': None, 'size': 0, 'names': None, 'entries': []}
        try:
            with open(csd_path, 'rb') as fh:
                head = fh.read(32)
            csd.update(kind=kind(head), size=csd_path.stat().st_size, names=names_found(csd_path),
                       head=head.hex(), entries=zip_entries(csd_path) if kind(head) == 'zip' else [])
        except OSError:
            pass
    ask(P_REOPEN)
    reopened, bad3, t3 = scan()

    run_keys = set(delta['new']) | set(delta['changed'])
    for e in entries:
        if e['status'] != 'removed':
            now = reopened.get(e['path'])
            e['reopen'] = '없음' if now is None else ('남음' if now == after[e['path']] else '바뀜')
    new_after = sorted(k for k in set(after) | set(reopened) if after.get(k) != reopened.get(k) and k not in run_keys)

    counts = {name: 0 for name, _ in roots}
    for k in before:
        counts[locate(k, roots)[0]] += 1
    json_ok = True
    try:
        target = out_dir if out_dir is not None else paths.result_dir() / 'branch_probe'
        target.mkdir(parents=True, exist_ok=True)
        data = {'roots': {n: os.path.realpath(str(r)) for n, r in roots}, 'files': entries, 'csd': csd,
                'reopen_new': new_after}
        (target / 'run_diff.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    except OSError:
        json_ok = False
    clear()
    lines = summary_lines(counts, max(bad1, bad2, bad3), int(round(t1 + t2 + t3)), (Path(ws) / '.metadata').is_dir(),
                          entries, csd, len(new_after), json_ok)
    print('\n'.join(lines))
    return 0 if entries else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
