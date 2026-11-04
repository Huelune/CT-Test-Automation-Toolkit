"""목록과 CT에서 내보낸 테스트 맞춰 보기.

목록의 줄마다 그 함수의 테스트에서 변수·멤버·원소(CT 기호)를 찾아 지정할지, 어떤 이유로 건너뛸지 가린다. 파일을
읽거나 쓰지 않는다. 내보낸 테스트는 `ct_export`가 `CtTest`로 만들어 넘긴다.
규칙은 docs/design/io-designation.md와 docs/design/io-designation-members.md "맞춰 보기".
"""

from __future__ import annotations

import ntpath
import re
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .io_list import ListRow

R_MULTI = '함수 여럿'
R_NO_VAR = '변수 없음'
R_CONFLICT = '목록 충돌'
R_HAS_VALUES = '값 있음'
R_TYPE = '타입 제외'
R_NOT_IN_CT = 'CT에 없음'
SKIP_REASONS = (R_MULTI, R_NO_VAR, R_CONFLICT, R_HAS_VALUES, R_TYPE, R_NOT_IN_CT)  # 화면 순서

_LEAD = re.compile(r'[A-Za-z_]\w*')  # 맨 앞 식별자
_ZEROS = re.compile(r'\[0*(\d+)\]')
_RETURN = re.compile(r'^return(?=$|[.\[])')


@dataclass(frozen=True)
class CtVar:
    name: str  # 머리글에 적힌 CT 기호 그대로(리턴 값은 'returnVar')
    direction: str  # 'in' | 'out' | 'inout' | '' (지정 없음)
    has_values: bool = False  # 테스트 케이스에 이 기호의 값이 들어 있다
    supported: bool = True  # 툴킷이 이 종류의 지정을 쓸 줄 안다


@dataclass(frozen=True)
class CtTest:
    key: str  # ct_export가 사본을 쓸 때 쓰는 식별자
    function: str
    file: str
    symbols: Mapping[str, CtVar]  # CT 기호 -> 지정


@dataclass(frozen=True)
class Skip:
    row: int
    function: str
    variable: str
    reason: str


@dataclass
class MatchResult:
    # 아래 applied·changes는 테스트 key -> {목록 줄의 (해석된) 경로: 지정}. 줄 단위다
    applied: Dict[str, Dict[str, str]]
    skips: List[Skip]
    not_exported: List[str]  # 목록에는 있고 내보낸 테스트는 없는 함수
    unlisted: List[str]  # 내보낸 테스트는 있고 목록에는 없는 함수
    tests_total: int
    changes: Dict[str, Dict[str, str]] = field(default_factory=dict)  # applied 중 지금 지정과 다른 것
    released: Dict[str, List[str]] = field(default_factory=dict)  # 테스트 key -> 해제할 기호(이름 순)
    kept: Dict[str, List[str]] = field(default_factory=dict)  # 해제할 기호인데 값이 있어 둔 것(이름 순)
    symbol_changes: Dict[str, Dict[str, str]] = field(default_factory=dict)  # 테스트 key -> 기호 -> 새 지정

    def count(self, reason: str) -> int:
        return sum(1 for s in self.skips if s.reason == reason)

    @property
    def assigned(self) -> int:
        return sum(len(v) for v in self.applied.values())

    @property
    def changed_vars(self) -> int:
        return sum(len(v) for v in self.changes.values())

    @property
    def released_vars(self) -> int:
        return _variable_count(self.released)

    @property
    def kept_vars(self) -> int:
        return _variable_count(self.kept)

    @property
    def edits(self) -> Dict[str, Dict[str, str]]:
        """사본에 쓸 지정(기호 -> 지정): 바뀌는 것, 해제는 ''. `ct_export.write_copy`가 받는다."""
        out = {key: dict(v) for key, v in self.symbol_changes.items() if v}
        for key, names in self.released.items():
            out.setdefault(key, {}).update((n, '') for n in names)
        return out


def _lead(symbol: str) -> str:
    found = _LEAD.match(symbol)
    return found.group() if found else symbol


def _variable_count(found: Mapping[str, Sequence[str]]) -> int:
    """테스트마다 기호의 맨 앞 식별자가 다른 것의 수를 더한다(기호 여럿이어도 변수 하나로 센다)."""
    return sum(len({_lead(s) for s in names}) for names in found.values())


def to_symbol(variable: str) -> str:
    """목록의 변수를 CT 기호 꼴로: 공백을 지우고, 첨자 앞 0을 떼고, 맨 앞 `return`을 `returnVar`로."""
    text = _ZEROS.sub(lambda m: '[' + m.group(1) + ']', re.sub(r'\s+', '', variable))
    return _RETURN.sub('returnVar', text, count=1)


def covers(path: str, symbol: str) -> bool:
    """경로가 그 기호를 덮는다: 같거나, 경로 바로 뒤에 `.`, `[`, `->`가 이어진다."""
    return symbol == path or (symbol.startswith(path) and symbol[len(path):].startswith(('.', '[', '->')))


def _file_key(path: str) -> str:
    return ntpath.basename(path).casefold()


def _pick(candidates: Sequence[CtTest], r: ListRow) -> Tuple[Optional[CtTest], bool]:
    """줄이 가리키는 테스트를 고른다. 못 고르면 (None, 함수 여럿이라서인지)이고, 아니면 내보내지 않은 것이다."""
    if len(candidates) > 1:
        candidates = [t for t in candidates if r.file and _file_key(t.file) == _file_key(r.file)]
        if len(candidates) != 1:
            return None, True
    if not candidates:
        return None, False
    test = candidates[0]
    if r.file and test.file and _file_key(test.file) != _file_key(r.file):
        return None, False  # 파일이 다른 같은 이름 함수만 내보냈다
    return test, False


def _resolve(test: CtTest, path: str) -> Tuple[str, List[str]]:
    """목록 경로가 덮는 테스트 기호를 찾는다. 덮는 것이 없고 경로가 식별자 하나면 `경로_mem`으로 다시 본다
    (포인터 파라미터는 `이름_mem`으로 내보내진다). (해석된 경로, 덮는 기호들)."""
    found = [s for s in test.symbols if covers(path, s)]
    if not found and _LEAD.fullmatch(path):
        mem = path + '_mem'
        found = [s for s in test.symbols if covers(mem, s)]
        if found:
            return mem, found
    return path, found


def match(rows: Sequence[ListRow], tests: Sequence[CtTest], reset_cases: bool = False) -> MatchResult:
    """`reset_cases`면 케이스를 지울 테스트라 값이 있어도 지정을 바꾼다.

    목록 줄의 경로(`a`, `a.b`, `v[0]`)는 자기가 덮는 CT 기호 가운데 더 긴 경로의 줄이 덮지 않는 것만
    지정한다. 어느 줄도 덮지 않는 지정 있는 기호는 해제한다.
    """
    groups: Dict[Tuple[str, str, str], List[ListRow]] = {}
    for r in rows:
        groups.setdefault((r.function, r.file, to_symbol(r.variable)), []).append(r)

    by_function: Dict[str, List[CtTest]] = {}
    for t in tests:
        by_function.setdefault(t.function, []).append(t)

    applied: Dict[str, Dict[str, str]] = {}
    changes: Dict[str, Dict[str, str]] = {}
    symbol_changes: Dict[str, Dict[str, str]] = {}
    skips: List[Skip] = []
    not_exported = set()
    picked: Dict[str, CtTest] = {}  # 목록 줄이 고른 테스트(줄을 건너뛰었어도 센다)
    protected: Dict[str, Set[str]] = {}  # 테스트 key -> 목록 줄이 덮은 기호(건너뛰었어도 센다)
    named: Dict[str, Set[str]] = {}  # 함수 -> 테스트를 못 고른 줄이 이름 붙인 경로와 그 `_mem` 꼴
    # 테스트 key -> [(가장 앞선 행 번호, 줄 묶음, 해석된 경로, 덮는 기호들)]
    blocked: Dict[str, List[str]] = {}  # 테스트 key -> 목록 충돌로 건너뛴 줄의 해석된 경로
    pending: Dict[str, List[Tuple[int, List[ListRow], str, List[str]]]] = {}

    def skip(r: ListRow, reason: str) -> None:
        skips.append(Skip(r.row, r.function, r.variable, reason))

    for (_, _, path), group in groups.items():
        r = group[0]
        test, multi = _pick(by_function.get(r.function, []), r)
        resolved, found = (_resolve(test, path) if test is not None else (path, []))
        if test is not None:
            picked[test.key] = test
            protected.setdefault(test.key, set()).update(found)
        else:  # 함수 여럿이나 파일이 달라 버려진 줄도 그 경로가 어느 테스트의 것인지는 모른다
            named.setdefault(r.function, set()).update((path, path + '_mem'))
        if len({g.direction for g in group}) > 1:
            for g in group:
                skip(g, R_CONFLICT)
            if test is not None:
                blocked.setdefault(test.key, []).append(resolved)
            continue
        if test is None:
            if multi:
                skip(r, R_MULTI)
            else:
                not_exported.add(r.function)
        elif not found:
            leads = {_lead(s) for s in test.symbols}
            lead = _lead(path)
            skip(r, R_NOT_IN_CT if lead in leads or lead + '_mem' in leads else R_NO_VAR)
        else:
            pending.setdefault(test.key, []).append((min(g.row for g in group), group, resolved, found))

    for key, items in pending.items():
        test = picked[key]
        first: Dict[str, Tuple[List[ListRow], List[str]]] = {}  # 해석된 경로 -> (줄 묶음, 덮는 기호들)
        for _, group, path, found in sorted(items, key=lambda item: item[0]):
            if path not in first:
                first[path] = (group, found)
            elif first[path][0][0].direction != group[0].direction:
                skip(group[0], R_CONFLICT)
        # 기호 -> (가장 긴 경로, 지정하지 않는 줄의 경로인지). 건너뛴 줄의 몫은 CT의 지정 그대로 둔다
        owner: Dict[str, Tuple[str, bool]] = {}
        skipped_paths = blocked.get(key, []) + sorted(named.get(test.function, ()))
        for path, is_blocked in ([(p, False) for p in first] + [(p, True) for p in skipped_paths]):
            for s in test.symbols:
                # 길이가 같으면 지정하는 줄이 이긴다: 지정하지 않는 소유자는 더 긴 경로일 때만 몫을 가져간다
                if covers(path, s) and (s not in owner or len(path) > len(owner[s][0])
                                        or (len(path) == len(owner[s][0]) and owner[s][1] and not is_blocked)):
                    owner[s] = (path, is_blocked)
        for path, (group, _) in first.items():
            r = group[0]
            share = [s for s in test.symbols if owner.get(s) == (path, False)]
            moves = [s for s in share if test.symbols[s].direction != r.direction]
            if any(not test.symbols[s].supported for s in share):
                skip(r, R_TYPE)
            elif not reset_cases and any(test.symbols[s].has_values for s in moves):
                skip(r, R_HAS_VALUES)
            else:
                applied.setdefault(key, {})[path] = r.direction
                if moves:
                    changes.setdefault(key, {})[path] = r.direction
                    symbol_changes.setdefault(key, {}).update((s, r.direction) for s in moves)

    released: Dict[str, List[str]] = {}
    kept: Dict[str, List[str]] = {}
    for key, test in picked.items():
        rel: List[str] = []
        keep: List[str] = []
        listed_paths = named.get(test.function, ())
        for name, v in test.symbols.items():
            if (v.supported and v.direction and name not in protected.get(key, ())
                    and not any(covers(p, name) for p in listed_paths)):
                # 값이 든 기호를 해제하면 값을 잃으므로 케이스를 지울 때만 해제한다
                (rel if reset_cases or not v.has_values else keep).append(name)
        if rel:
            released[key] = sorted(rel)
        if keep:
            kept[key] = sorted(keep)

    listed = {r.function for r in rows}
    unlisted = sorted({t.function for t in tests if t.function not in listed})
    skips.sort(key=lambda s: s.row)
    return MatchResult(applied, skips, sorted(not_exported), unlisted, len(tests), changes, released, kept,
                       symbol_changes)
