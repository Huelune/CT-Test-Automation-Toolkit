"""목록과 CT에서 내보낸 테스트 맞춰 보기.

목록의 줄마다 그 함수의 테스트에서 변수를 찾아 지정할지, 어떤 이유로 건너뛸지 가린다. 파일을
읽거나 쓰지 않는다. 내보낸 테스트는 `ct_export`가 `CtTest`로 만들어 넘긴다.
규칙은 docs/design/io-designation.md "맞춰 보기".
"""

from __future__ import annotations

import ntpath
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

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
    direction: str  # 'in' | 'out' | 'inout' | '' (지정 없음)
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
    applied: Dict[str, Dict[str, str]]  # 테스트 key -> {변수: 지정}
    skips: List[Skip]
    not_exported: List[str]  # 목록에는 있고 내보낸 테스트는 없는 함수
    unlisted: List[str]  # 내보낸 테스트는 있고 목록에는 없는 함수
    tests_total: int

    def count(self, reason: str) -> int:
        return sum(1 for s in self.skips if s.reason == reason)

    @property
    def assigned(self) -> int:
        return sum(len(v) for v in self.applied.values())


def _file_key(path: str) -> str:
    return ntpath.basename(path).casefold()


def match(rows: Sequence[ListRow], tests: Sequence[CtTest], reset_cases: bool = False) -> MatchResult:
    """`reset_cases`면 케이스를 지울 테스트라 값이 있어도 지정을 바꾼다."""
    groups: Dict[Tuple[str, str, str], List[ListRow]] = {}
    for r in rows:
        groups.setdefault((r.function, r.file, r.variable), []).append(r)

    by_function: Dict[str, List[CtTest]] = {}
    for t in tests:
        by_function.setdefault(t.function, []).append(t)

    applied: Dict[str, Dict[str, str]] = {}
    skips: List[Skip] = []
    not_exported = set()

    def skip(r: ListRow, reason: str) -> None:
        skips.append(Skip(r.row, r.function, r.variable, reason))

    for group in groups.values():
        if len({r.direction for r in group}) > 1:
            for r in group:
                skip(r, R_CONFLICT)
            continue
        r = group[0]
        candidates = by_function.get(r.function, [])
        if not candidates:
            not_exported.add(r.function)
            continue
        if len(candidates) > 1:
            candidates = [t for t in candidates
                          if r.file and _file_key(t.file) == _file_key(r.file)]
            if len(candidates) != 1:
                skip(r, R_MULTI)
                continue
        test = candidates[0]
        if r.file and test.file and _file_key(test.file) != _file_key(r.file):
            not_exported.add(r.function)  # 파일이 다른 같은 이름 함수만 내보냈다
            continue
        var = test.variables.get(r.variable)
        if var is None:
            skip(r, R_NO_VAR)
        elif not var.supported:
            skip(r, R_TYPE)
        elif not reset_cases and var.has_values and var.direction != r.direction:
            skip(r, R_HAS_VALUES)
        elif applied.get(test.key, {}).get(r.variable, r.direction) != r.direction:
            skip(r, R_CONFLICT)
        else:
            applied.setdefault(test.key, {})[r.variable] = r.direction

    listed = {r.function for r in rows}
    unlisted = sorted({t.function for t in tests if t.function not in listed})
    skips.sort(key=lambda s: s.row)
    return MatchResult(applied, skips, sorted(not_exported), unlisted, len(tests))
