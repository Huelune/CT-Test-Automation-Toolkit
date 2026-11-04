"""(조사용) `.utest`를 Java 직렬화 규칙대로 풀어 두 테스트를 비교한다 (todo.md 24절).

`utest_probe.py <처음 폴더> <체크한 뒤 폴더>`. CT가 처음 만든 `dmy_carry` 테스트와, 전역 변수 [편집]에서 체크
안 된 것을 체크해 기대값으로 지정한 뒤의 같은 테스트를 내보낸 폴더 둘을 받는다. 체크 안 된 전역 변수가 처음
`.utest`에 아예 없는지, 들어 있고 표시만 다른지, 체크하면 어느 필드가 어떻게 바뀌는지 본다. 툴킷이 `.utest`를
고쳐 쓸 수 있는지 정하려는 조사 도구다. 고쳐 쓰는 기능은 결과를 보고 따로 설계한다.

먼저 꼴을 가린다(`unwrap`: Java 직렬화, gzip·zlib·zip이면 풀기, EMF 바이너리, XML, 앞 머리 + Java 직렬화). 24절 첫
화면에서 `.utest`는 Java 직렬화 머리로 시작하지 않았다. Java 직렬화로 풀 수 없으면 바이트를 낱개(ASCII 덩어리와 그 사이
바이트)로 나눠 비교한다(`tokens`). 이름이 어떤 꼴로 적혔는지(`found_as`)와 Java 클래스 이름 꼴(`classes`)도 찍는다.

풀기는 Java Object Serialization Stream Protocol(버전 5)을 따른다. 잎(기본형 필드 값, 글자열, null, 참조, 열거
상수, 블록 데이터)마다 `경로 = 값` 한 줄을 만든다. 경로는 클래스 단순 이름과 필드 이름을 이은 것이고 목록 위치는
넣지 않는다. 그래야 변수가 하나 끼어도 비교가 그 자리만 다르다고 나온다.

화면에는 개수, 정해 둔 문구, CT 클래스·필드 이름, 숫자, 견본 이름(`dmy_`)과 C 타입 낱말만 찍는다. 다른 글자열은
`*<길이>`로 가린다(경로, 계정 이름이 들어 있을 수 있다). 블록 데이터는 길이와 CRC만 찍는다. 전체 잎과 비교는
`%TEMP%`의 파일에만 쓴다.
"""

from __future__ import annotations

import difflib
import gzip
import io
import re
import struct
import sys
import tempfile
import textwrap
import zipfile
import zlib
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from member_probe import WIDTH, show_lines

MAGIC = b'\xac\xed\x00\x05'
(TC_NULL, TC_REFERENCE, TC_CLASSDESC, TC_OBJECT, TC_STRING, TC_ARRAY, TC_CLASS, TC_BLOCKDATA, TC_ENDBLOCKDATA,
 TC_RESET, TC_BLOCKDATALONG, TC_EXCEPTION, TC_LONGSTRING, TC_PROXYCLASSDESC, TC_ENUM) = range(0x70, 0x7F)
BASE_HANDLE = 0x7E0000
SC_WRITE_METHOD, SC_SERIALIZABLE, SC_EXTERNALIZABLE, SC_BLOCK_DATA = 0x01, 0x02, 0x04, 0x08
PRIM = {'B': ('>b', 1), 'C': ('>H', 2), 'D': ('>d', 8), 'F': ('>f', 4), 'I': ('>i', 4), 'J': ('>q', 8),
        'S': ('>h', 2), 'Z': ('>?', 1)}

PREFIX = 'dmy_carry_test'
NAMES = ('dmy_c_direct', 'dmy_c_callee', 'dmy_c_ptr', 'dmy_c_p', 'dmy_c_unused', 'dmy_sum', 'dmy_recs')
C_WORDS = {'signed', 'unsigned', 'int', 'char', 'short', 'long', 'float', 'double', 'void', 'const', 'volatile',
           'struct', 'union', 'enum', 'static', 'extern', 'returnVar'}
DUMP = 'ct_utest_probe.txt'
MAX_DIFF = 16  # 화면에 찍을 비교 줄 수
E_ARGS = '[ERROR] 폴더 둘을 받지 못함: todo.bat 24로 돌리기'
E_ONE = '[ERROR] {} 폴더의 dmy_carry 테스트 .utest가 {}개: todo.md 24절대로 하나만 두고 내보내기'

Leaf = Tuple[str, str, int]  # (경로, 값, 바이트 위치)


class UtestError(Exception):
    def __init__(self, kind: str, at: int = -1) -> None:
        super().__init__(kind)
        self.kind, self.at = kind, at


class _Desc:
    def __init__(self, name: str) -> None:
        self.name, self.flags = name, 0
        self.fields: List[Tuple[str, str]] = []  # (타입 코드, 필드 이름)
        self.super: Optional[_Desc] = None

    @property
    def simple(self) -> str:
        return self.name.rsplit('.', 1)[-1]


def show(text: str) -> str:
    """견본 이름·C 타입 낱말·숫자로만 된 글자열은 그대로, 나머지는 `*<길이>`."""
    ok = (len(text) <= 60 and re.fullmatch(r'[A-Za-z0-9_ .,()\[\]*&<>-]*', text) is not None
          and all(w.startswith('dmy_') or w in C_WORDS for w in re.findall(r'[A-Za-z_]\w*', text)))
    return '"{}"'.format(text) if ok else '*{}'.format(len(text))


class _Reader:
    def __init__(self, data: bytes) -> None:
        self.data, self.pos = data, 0
        self.handles: List[Tuple[str, object]] = []  # (경로, 값): 글자열은 str, 클래스 설명은 _Desc
        self.leaves: List[Leaf] = []
        self.strings: List[str] = []  # 읽은 글자열 객체 모두(필드 타입 이름 포함)

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise UtestError('끝이 잘림')
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def num(self, fmt: str, n: int):
        return struct.unpack(fmt, self.take(n))[0]

    def utf(self, long: bool = False) -> str:
        return self.take(self.num('>q', 8) if long else self.num('>H', 2)).decode('utf-8', 'replace')

    def peek(self) -> int:
        if self.pos >= len(self.data):
            raise UtestError('끝이 잘림')
        return self.data[self.pos]

    def ref(self) -> Tuple[str, object]:
        n = self.num('>i', 4) - BASE_HANDLE
        if not 0 <= n < len(self.handles):
            raise UtestError('없는 참조')
        return self.handles[n]

    def quiet(self, read):
        """잎을 남기지 않고 읽는다(필드 타입 이름, 열거 상수 이름)."""
        mark = len(self.leaves)
        value = read()
        del self.leaves[mark:]
        return value

    def run(self) -> None:
        if self.take(4) != MAGIC:
            raise UtestError('Java 직렬화 머리가 아님')
        while self.pos < len(self.data):
            self.content('')

    def content(self, path: str) -> None:
        if self.peek() in (TC_BLOCKDATA, TC_BLOCKDATALONG):
            at = self.pos
            tc = self.num('>B', 1)
            n = self.num('>B', 1) if tc == TC_BLOCKDATA else self.num('>i', 4)
            body = self.take(n)
            self.leaves.append((path + '.#', 'block {} crc {:08x}'.format(n, zlib.crc32(body)), at))
        else:
            self.object(path)

    def annotation(self, path: str) -> None:
        while self.peek() != TC_ENDBLOCKDATA:
            self.content(path + '.@')
        self.pos += 1

    def class_desc(self, path: str) -> Optional[_Desc]:
        tc = self.num('>B', 1)
        if tc == TC_NULL:
            return None
        if tc == TC_REFERENCE:
            value = self.ref()[1]
            if not isinstance(value, _Desc):
                raise UtestError('클래스 설명이 아닌 참조')
            return value
        if tc == TC_CLASSDESC:
            desc = _Desc(self.utf())
            self.take(8)  # serialVersionUID
            self.handles.append((path, desc))
            desc.flags = self.num('>B', 1)
            for _ in range(self.num('>h', 2)):
                code, name = chr(self.num('>B', 1)), self.utf()
                if code in '[L':
                    self.quiet(lambda: self.object(path))  # 필드 타입 이름 글자열
                elif code not in PRIM:
                    raise UtestError('모르는 필드 타입')
                desc.fields.append((code, name))
        elif tc == TC_PROXYCLASSDESC:
            desc = _Desc('Proxy')
            desc.flags = SC_SERIALIZABLE
            self.handles.append((path, desc))
            for _ in range(self.num('>i', 4)):
                self.utf()
        else:
            raise UtestError('클래스 설명이 아님 0x{:02x}'.format(tc))
        self.quiet(lambda: self.annotation(path))
        desc.super = self.class_desc(path)
        return desc

    def object(self, path: str) -> Optional[str]:
        """객체 하나를 읽고 잎을 남긴다. 글자열이면 그 값을 돌려준다."""
        at = self.pos
        tc = self.num('>B', 1)
        if tc == TC_NULL:
            self.leaves.append((path, 'null', at))
            return None
        if tc == TC_REFERENCE:
            target, value = self.ref()
            self.leaves.append((path, 'ref ' + (show(value) if isinstance(value, str) else target or '/'), at))
            return value if isinstance(value, str) else None
        if tc in (TC_STRING, TC_LONGSTRING):
            text = self.utf(tc == TC_LONGSTRING)
            self.handles.append((path, text))
            self.strings.append(text)
            self.leaves.append((path, show(text), at))
            return text
        if tc in (TC_CLASSDESC, TC_PROXYCLASSDESC):
            self.pos = at
            self.class_desc(path)
            return None
        if tc == TC_RESET:
            self.handles.clear()
            return None
        if tc == TC_EXCEPTION:
            raise UtestError('예외 객체')
        if tc not in (TC_OBJECT, TC_ARRAY, TC_ENUM, TC_CLASS):
            raise UtestError('모르는 표시 0x{:02x}'.format(tc))
        desc = self.class_desc(path)
        if desc is None:
            raise UtestError('클래스 설명 없음')
        here = path + '/' + desc.simple
        self.handles.append((here, None))
        if tc == TC_CLASS:
            self.leaves.append((path, 'class ' + desc.simple, at))
        elif tc == TC_ENUM:
            name = self.quiet(lambda: self.object(here)) or ''
            shown = name if re.fullmatch(r'[A-Za-z_]\w*', name) and name.isascii() else show(name)
            self.leaves.append((path, 'enum {}.{}'.format(desc.simple, shown), at))
        elif tc == TC_ARRAY:
            n = self.num('>i', 4)
            code = desc.name[1:2]
            if code in PRIM:
                body = self.take(n * PRIM[code][1])
                self.leaves.append((path, 'array {} len {} crc {:08x}'.format(desc.name, n, zlib.crc32(body)), at))
            else:
                for _ in range(n):
                    self.object(path + '[]')
        else:
            self.class_data(desc, here)
        return None

    def class_data(self, desc: _Desc, path: str) -> None:
        chain = []
        d: Optional[_Desc] = desc
        while d is not None:
            chain.append(d)
            d = d.super
        for d in reversed(chain):  # 윗클래스 먼저
            if d.flags & SC_SERIALIZABLE:
                for code, name in d.fields:
                    if code in PRIM:
                        at = self.pos
                        value = self.num(*PRIM[code])
                        shown = ('true' if value else 'false') if code == 'Z' else repr(value)
                        self.leaves.append((path + '.' + name, shown, at))
                    else:
                        self.object(path + '.' + name)
                if d.flags & SC_WRITE_METHOD:
                    self.annotation(path)
            elif d.flags & SC_EXTERNALIZABLE:
                if not d.flags & SC_BLOCK_DATA:
                    raise UtestError('블록이 아닌 외부화 객체')
                self.annotation(path)


def _run(data: bytes) -> _Reader:
    """다 읽은 _Reader. 풀지 못하면 UtestError(종류, 바이트 위치, 거기까지 읽은 reader)."""
    reader = _Reader(data)
    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 20000))
    try:
        reader.run()
    except UtestError as exc:
        exc.at, exc.reader = reader.pos, reader
        raise
    except RecursionError:
        exc = UtestError('너무 깊음', reader.pos)
        exc.reader = reader
        raise exc from None
    finally:
        sys.setrecursionlimit(limit)
    return reader


def parse(data: bytes) -> List[Leaf]:
    """잎 목록. 풀지 못하면 UtestError(종류, 바이트 위치)."""
    return _run(data).leaves


def unwrap(data: bytes) -> Tuple[str, bytes]:
    """(꼴 이름, 풀 내용). 압축이면 풀고, 앞에 머리가 붙은 Java 직렬화면 그 뒤를 준다. 2026-11-04 24절 첫 화면에서
    `.utest`가 Java 직렬화 머리로 시작하지 않아 더했다."""
    if data[:4] == MAGIC:
        return 'Java 직렬화', data
    inner, kind = None, ''
    try:
        if data[:2] == b'\x1f\x8b':
            inner, kind = gzip.decompress(data), 'gzip'
        elif data[:1] == b'\x78' and data[1:2] in (b'\x01', b'\x5e', b'\x9c', b'\xda'):
            inner, kind = zlib.decompress(data), 'zlib'
        elif data[:4] == b'PK\x03\x04':
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = archive.namelist()
                inner, kind = archive.read(names[0]), 'zip 항목 {}개'.format(len(names))
    except (OSError, EOFError, zlib.error, zipfile.BadZipFile, IndexError):
        return '압축 머리지만 못 풂', data
    if inner is not None:
        sub, payload = unwrap(inner)
        return '{} > {}'.format(kind, sub), payload
    if data[:4] == b'\x89emf':
        return 'EMF 바이너리', data
    if data.lstrip(b'\xef\xbb\xbf \t\r\n')[:1] == b'<':
        return 'XML', data
    at = data.find(MAGIC)
    if at > 0:
        return '앞 {}바이트 머리 + Java 직렬화'.format(at), data[at:]
    return '모름', data


_KINDS = ('Java 글자열', '그대로', 'Kryo', 'UTF-16')


def found_as(data: bytes, strings: Sequence[str], name: str) -> str:
    """이름이 적힌 꼴(_KINDS 가운데 하나). 없으면 ''.

    Java 글자열은 2바이트 길이 + 바이트, 그대로는 앞뒤가 영숫자가 아닌 ASCII, Kryo는 마지막 글자에 0x80을 더한 ASCII,
    UTF-16은 little-endian이다."""
    raw = name.encode('ascii')
    word = re.compile(r'(?<![A-Za-z0-9_])' + re.escape(name) + r'(?![A-Za-z0-9_])')
    if any(word.search(s) for s in strings) or struct.pack('>H', len(raw)) + raw in data:
        return _KINDS[0]
    if re.search(rb'(?<![A-Za-z0-9_])' + re.escape(raw) + rb'(?![A-Za-z0-9_])', data):
        return _KINDS[1]
    if re.search(rb'(?<![A-Za-z0-9_])' + re.escape(raw[:-1] + bytes([raw[-1] | 0x80])), data):
        return _KINDS[2]
    if name.encode('utf-16-le') in data:
        return _KINDS[3]
    return ''


# Java 클래스 이름 꼴: 흔한 뿌리 + 소문자 꾸러미 + 대문자로 시작하는 이름. 끝이 소문자인 도메인·메일 주소는 걸리지 않는다.
CLASS = r'(?:java|javax|com|org|net|sun|jdk)(?:\.[a-z][a-z0-9_]*)+\.[A-Z][\w$]*'


def classes(data: bytes) -> List[str]:
    """바이트 안의 Java 클래스 이름 꼴(CLASS), 처음 나온 차례로 겹치지 않게."""
    seen: List[str] = []
    for m in re.finditer(CLASS.encode('ascii'), data):
        text = m.group().decode('ascii')
        if text not in seen:
            seen.append(text)
    return seen


def tokens(data: bytes) -> List[str]:
    """꼴을 모를 때 비교할 낱개: 4자 이상 ASCII 덩어리는 `t <글>`(가림), 그 사이 바이트는 `x <16진>`(12바이트 넘으면
    길이와 CRC)."""
    out: List[str] = []
    pos = 0

    def binary(chunk: bytes) -> str:
        if len(chunk) <= 12:
            return 'x ' + ' '.join('{:02x}'.format(b) for b in chunk)
        return 'x {}바이트 crc {:08x}'.format(len(chunk), zlib.crc32(chunk))

    for m in re.finditer(rb'[\x20-\x7e]{4,}', data):
        if m.start() > pos:
            out.append(binary(data[pos:m.start()]))
        text = m.group().decode('ascii')
        out.append('t ' + (text if re.fullmatch(CLASS, text) else show(text)))
        pos = m.end()
    if pos < len(data):
        out.append(binary(data[pos:]))
    return out


def _short(line: str, width: int) -> str:
    return line if len(line) <= width else '…' + line[-(width - 1):]


def diff_lines(before: List[Leaf], after: List[Leaf]) -> Tuple[str, List[str]]:
    """(요약 한 줄, 다른 곳의 `- 경로 = 값`/`+ 경로 = 값` 줄 전부)."""
    return diff_seq(['{} = {}'.format(p, v) for p, v, _ in before], ['{} = {}'.format(p, v) for p, v, _ in after])


def diff_seq(a: List[str], b: List[str]) -> Tuple[str, List[str]]:
    """두 줄 목록의 (요약, 다른 줄). 다른 곳마다 바로 앞의 같은 줄을 `@ …`로 붙인다(어느 이름 옆인지 보려고)."""
    counts = {'insert': 0, 'delete': 0, 'replace': 0}
    lines: List[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        counts[tag] += 1
        lines += (['@ ' + a[i1 - 1]] if i1 else []) + ['- ' + x for x in a[i1:i2]] + ['+ ' + x for x in b[j1:j2]]
    summary = '다른 곳 {}군데(더해짐 {}, 빠짐 {}, 바뀜 {}), 다른 줄 {}'.format(
        sum(counts.values()), counts['insert'], counts['delete'], counts['replace'], len(lines))
    return summary, lines


def _utests(folder: Path) -> List[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.rglob('*.utest') if p.stem.startswith(PREFIX) and p.is_file())


def main(argv: Sequence[str]) -> int:
    if len(argv) != 2:
        print(E_ARGS)
        return 1
    parsed: List[Optional[List[Leaf]]] = []
    payloads: List[bytes] = []
    dump: List[str] = []
    for label, folder in (('처음', Path(argv[0])), ('체크한 뒤', Path(argv[1]))):
        utests = _utests(folder)
        if len(utests) != 1:
            print(E_ONE.format(label, len(utests)))
            return 1
        print('{} 머리글'.format(label))
        for line in show_lines(folder, PREFIX):
            print('  ' + line)
        data = utests[0].read_bytes()
        kind, payload = unwrap(data)
        payloads.append(payload)
        print('  .utest {}바이트, 앞 8바이트 {}, 꼴 {}, 푼 내용 {}바이트'.format(
            len(data), ' '.join('{:02x}'.format(b) for b in data[:8]), kind, len(payload)))
        failed: Optional[UtestError] = None
        reader: Optional[_Reader] = None
        if payload[:4] == MAGIC:
            try:
                reader = _run(payload)
            except UtestError as exc:
                failed, reader = exc, exc.reader
        strings = reader.strings if reader else []
        ways = {n: found_as(payload, strings, n) for n in NAMES}
        text = '  이름 있음: {}  없음: {}'.format(
            ', '.join('{}({})'.format(n, w) for n, w in ways.items() if w) or '-',
            ', '.join(n for n, w in ways.items() if not w) or '-')
        names = classes(payload)
        for line in textwrap.wrap(text, WIDTH, subsequent_indent='    ', break_on_hyphens=False)[:2]:
            print(line)
        print('  클래스 이름 꼴 {}: {}'.format(len(names), ', '.join(names[:3]) or '-')[:WIDTH + 2])
        if failed is not None:
            print('  [ERROR] .utest 풀기 실패: {} ({}바이트 위치, 잎 {}까지 읽음)'.format(
                failed.kind, failed.at, len(reader.leaves)))
        elif reader is not None:
            print('  풀기: 잎 {}'.format(len(reader.leaves)))
        if reader is not None:
            dump += ['## {} 잎'.format(label)] + ['{:8d} {} = {}'.format(at, p, v) for p, v, at in reader.leaves]
        dump += ['## {} 클래스 이름 꼴'.format(label)] + names
        parsed.append(None if failed or reader is None else reader.leaves)
    if parsed[0] is not None and parsed[1] is not None:
        summary, lines = diff_lines(parsed[0], parsed[1])
    else:  # Java 직렬화로 못 풀면 바이트 낱개로 비교한다
        summary, lines = diff_seq(tokens(payloads[0]), tokens(payloads[1]))
        summary = '바이트 낱개 비교: ' + summary
    print(summary)
    for line in lines[:MAX_DIFF]:
        print('  ' + _short(line, WIDTH))
    if len(lines) > MAX_DIFF:
        print('  … 나머지 {}줄은 파일에'.format(len(lines) - MAX_DIFF))
    dump += ['## 비교', summary] + lines
    try:
        (Path(tempfile.gettempdir()) / DUMP).write_text('\n'.join(dump) + '\n', encoding='utf-8')
        print('전체 잎과 비교: %TEMP%\\{}(밖으로 보내지 않기)'.format(DUMP))
    except OSError:
        print('[WARN] 전체 잎 파일을 쓰지 못함: 임시 폴더 권한 확인')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
