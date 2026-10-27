"""저장소 기준 경로.

경로는 항상 여기서 만든다. 서버 PC에서 어느 폴더에서 `ct.bat`을 불러도 같은 곳을 가리키게
하려고 현재 폴더(`os.getcwd()`)는 쓰지 않는다.
"""

from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent


def project_root() -> Path:
    """저장소 루트(`ct.bat`이 있는 폴더)."""
    return _PACKAGE_DIR.parent.parent


def result_dir() -> Path:
    """실행 결과 루트. 커밋하지 않는다."""
    return project_root() / 'result'


def log_dir() -> Path:
    """실행 로그 폴더."""
    return result_dir() / 'logs'


def version() -> str:
    """`VERSION.txt`의 버전 문자열. 없으면 'unknown'."""
    try:
        return (project_root() / 'VERSION.txt').read_text(encoding='utf-8').strip() or 'unknown'
    except OSError:
        return 'unknown'
