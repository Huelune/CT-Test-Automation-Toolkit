"""(조사용) CT에서 테스트를 돌리기 전후로 파일 목록을 비교해 어디에 무엇이 생기는지 본다 (todo.md 28절).

설계는 `docs/design/branch-table.md` 1단계(TC별 분기 표의 데이터가 어디에 남는지 찾기). 여러 뿌리 폴더의 파일 목록을 실행
전후로 찍어 새로 생기거나 바뀐 파일을 가리고, 그 파일에 견본 이름(`NAMES`)이 들었는지 꼴과 함께 본다. 이 파일은 그 부품이다
(목록 찍기, 비교, 꼴 판별, 이름 가리기).

화면에는 개수, 정해 둔 문구, 가린 상대 경로(`mask_path`), 꼴 이름, 견본 이름 수만 찍는다. 절대 경로, 계정 이름, 예외 메시지
원문은 찍지 않는다.
"""

from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from member_probe import WIDTH  # noqa: F401  (화면 폭 규칙: 줄은 WIDTH를 넘지 않는다)
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
    for root in roots:
        for top, _dirs, files in os.walk(str(root), onerror=onerror):
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
    best: Optional[Tuple[str, Path]] = None
    for name, root in roots:
        try:
            Path(path).relative_to(root)
        except ValueError:
            continue
        if best is None or len(root.parts) > len(best[1].parts):
            best = (name, root)
    if best is None:
        return '?', path
    return best[0], str(Path(path).relative_to(best[1]))


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


_KEEP_PART = re.compile(r'dmy_.*|ctsample|\.[A-Za-z]\w*|(?:com|org|net|java|javax|jdk|sun)\.[\w.-]+')


def mask_path(rel: str) -> str:
    out = []
    for part in re.split(r'[\\/]', rel):
        low = part.lower()
        if _KEEP_PART.fullmatch(part) or 'codescroll' in low or 'suresoft' in low:
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
        with zipfile.ZipFile(str(path)) as zf:
            for info in zf.infolist():
                if info.filename.endswith('/'):
                    continue
                with zf.open(info) as f:
                    head = f.read(512)
                n = _count(zf.read(info)) if info.file_size <= BIG else None
                rows.append((info.filename, info.file_size, kind(head), n))
    except (zipfile.BadZipFile, OSError):
        return []
    return rows
