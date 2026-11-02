"""목록과 CT에서 내보낸 테스트 맞춰 보기.

목록의 줄마다 그 함수의 테스트에서 변수를 찾아 지정할지, 어떤 이유로 건너뛸지 가린다. 파일을
읽거나 쓰지 않는다. 내보낸 테스트는 `ct_export`가 `CtTest`로 만들어 넘긴다.
규칙은 docs/design/io-designation.md "맞춰 보기".
"""

from __future__ import annotations

import ntpath
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .io_list import ListRow

R_MULTI = '함수 여럿'
R_NO_VAR = '변수 없음'
R_CONFLICT = '목록 충돌'
R_HAS_VALUES = '값 있음'
R_TYPE = '타입 제외'
SKIP_REASONS = (R_MULTI, R_NO_VAR, R_CONFLICT, R_HAS_VALUES, R_TYPE)  # 화면 순서


@dataclass(frozen=True)
class CtVar:
    name: str  # 리턴 값은 'return'
    # 'in' | 'out' | 'inout' | '' (지정 없음) | 'mixed': 멤버·원소마다 든 구역이 달라 한 지정이 아님
    # ('mixed'는 어떤 목록 지정과도 같지 않으므로 늘 바뀌는 것으로 본다)
    direction: str
    has_values: bool = False  # 테스트 케이스에 값이 들어 있다
    supported: bool = True  # 툴킷이 이 종류의 지정을 쓸 줄 안다


@dataclass(frozen=True)
class CtTest:
    key: str  # ct_export가 사본을 쓸 때 쓰는 식별자
    function: str
    file: str
    variables: Mapping[str, CtVar]


@dataclass(frozen=True)
class Skip:
    row: int
    function: str
    variable: str
    reason: str


@dataclass
class MatchResult:
    applied: Dict[str, Dict[str, str]]  # 테스트 key -> {찾은 CtVar.name: 지정}
    skips: List[Skip]
    not_exported: List[str]  # 목록에는 있고 내보낸 테스트는 없는 함수
    unlisted: List[str]  # 내보낸 테스트는 있고 목록에는 없는 함수
    tests_total: int
    changes: Dict[str, Dict[str, str]] = field(default_factory=dict)  # applied 중 지금 지정과 다른 것
    released: Dict[str, List[str]] = field(default_factory=dict)  # 테스트 key -> 해제할 변수(이름 순)
    kept: Dict[str, List[str]] = field(default_factory=dict)  # 해제할 변수인데 값이 있어 둔 것(이름 순)

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
        return sum(len(v) for v in self.released.values())

    @property
    def kept_vars(self) -> int:
        return sum(len(v) for v in self.kept.values())

    @property
    def edits(self) -> Dict[str, Dict[str, str]]:
        """사본에 쓸 지정: 바뀌는 것, 해제는 ''. `ct_export.write_copy`가 받는다."""
        out = {key: dict(v) for key, v in self.changes.items()}
        for key, names in self.released.items():
            out.setdefault(key, {}).update((n, '') for n in names)
        return out


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


def _find(test: CtTest, name: str) -> Optional[CtVar]:
    """목록의 변수 이름으로 테스트 변수를 찾는다. 포인터 파라미터는 `이름_mem`으로 내보내진다."""
    var = test.variables.get(name)
    return var if var is not None else test.variables.get(name + '_mem')


def match(rows: Sequence[ListRow], tests: Sequence[CtTest], reset_cases: bool = False) -> MatchResult:
    """`reset_cases`면 케이스를 지울 테스트라 값이 있어도 지정을 바꾼다."""
    groups: Dict[Tuple[str, str, str], List[ListRow]] = {}
    for r in rows:
        groups.setdefault((r.function, r.file, r.variable), []).append(r)

    by_function: Dict[str, List[CtTest]] = {}
    for t in tests:
        by_function.setdefault(t.function, []).append(t)

    applied: Dict[str, Dict[str, str]] = {}
    changes: Dict[str, Dict[str, str]] = {}
    skips: List[Skip] = []
    not_exported = set()
    picked: Dict[str, CtTest] = {}  # 목록 줄이 고른 테스트(줄을 건너뛰었어도 센다)
    found: Dict[str, Set[str]] = {}  # 테스트 key -> 목록 줄이 찾은 변수(건너뛰었어도 센다)
    named: Dict[str, Set[str]] = {}  # 함수 -> 테스트를 못 고른 줄이 이름 붙인 변수와 그 `_mem` 꼴

    def skip(r: ListRow, reason: str) -> None:
        skips.append(Skip(r.row, r.function, r.variable, reason))

    for group in groups.values():
        r = group[0]
        test, multi = _pick(by_function.get(r.function, []), r)
        var: Optional[CtVar] = None
        if test is not None:
            picked[test.key] = test
            var = _find(test, r.variable)
            if var is not None:
                found.setdefault(test.key, set()).add(var.name)
        else:  # 함수 여럿이나 파일이 달라 버려진 줄도 그 변수가 어느 테스트의 것인지는 모른다
            named.setdefault(r.function, set()).update((r.variable, r.variable + '_mem'))
        if len({g.direction for g in group}) > 1:
            for g in group:
                skip(g, R_CONFLICT)
            continue
        if test is None:
            if multi:
                skip(r, R_MULTI)
            else:
                not_exported.add(r.function)
            continue
        if var is None:
            skip(r, R_NO_VAR)
        elif not var.supported:
            skip(r, R_TYPE)
        elif not reset_cases and var.has_values and var.direction != r.direction:
            skip(r, R_HAS_VALUES)
        elif applied.get(test.key, {}).get(var.name, r.direction) != r.direction:
            skip(r, R_CONFLICT)
        else:
            applied.setdefault(test.key, {})[var.name] = r.direction
            if var.direction != r.direction:
                changes.setdefault(test.key, {})[var.name] = r.direction

    released: Dict[str, List[str]] = {}
    kept: Dict[str, List[str]] = {}
    for key, test in picked.items():
        rel: List[str] = []
        keep: List[str] = []
        listed_names = named.get(test.function, ())
        for v in test.variables.values():
            if (v.supported and v.direction and v.name not in found.get(key, ())
                    and v.name not in listed_names):
                # 값이 든 변수를 해제하면 값을 잃으므로 케이스를 지울 때만 해제한다
                (rel if reset_cases or not v.has_values else keep).append(v.name)
        if rel:
            released[key] = sorted(rel)
        if keep:
            kept[key] = sorted(keep)

    listed = {r.function for r in rows}
    unlisted = sorted({t.function for t in tests if t.function not in listed})
    skips.sort(key=lambda s: s.row)
    return MatchResult(applied, skips, sorted(not_exported), unlisted, len(tests), changes, released, kept)
