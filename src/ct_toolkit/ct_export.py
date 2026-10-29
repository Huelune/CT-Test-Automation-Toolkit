"""CT [테스트 내보내기] 폴더 읽기와 지정을 바꾼 사본 쓰기.

CT 2025가 입력·출력 지정을 내보낸 파일의 어디에 적는지 매뉴얼에 없다. todo.md 2절 견본 결과로
채운다. 그 전까지는 둘 다 `NotReady`를 던진다.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Mapping, Sequence

from .io_match import CtTest


class NotReady(Exception):
    """내보낸 파일 형식을 아직 모른다."""


def load_tests(export_dir: Path) -> List[CtTest]:
    """내보낸 폴더의 유닛 테스트를 읽는다."""
    raise NotReady()


def write_copy(export_dir: Path, out_dir: Path, tests: Sequence[CtTest],
               applied: Mapping[str, Mapping[str, str]], reset_cases: bool) -> None:
    """`applied`에 있는 테스트만 지정을 바꿔 `out_dir`에 쓴다. `reset_cases`면 케이스를 하나만 둔다."""
    raise NotReady()
