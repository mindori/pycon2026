import ast
from pathlib import Path

import pytest

STEPS = sorted((Path(__file__).resolve().parent.parent / "steps").glob("step*.py"))

# 각 스냅샷 시점에 아직 존재하면 안 되는 모듈
FORBIDDEN = {
    "step0_hello": {"vision", "ledger", "personas", "debate", "judge"},
    "step1_freetext": {"vision", "ledger", "personas", "debate", "judge"},
    "step2_structured": {"ledger", "personas", "debate", "judge"},
    "step3_ledger": {"personas", "debate", "judge"},
    "step4_debate": {"judge"},
    "step5_judge": set(),
}

#: 이 프로젝트에서 실제로 쓰이는 키 형식의 접두사. 값 자체는 절대 담지 않는다.
_SECRET_MARKERS = ("AIza", "AQ.")


def test_there_are_exactly_six_snapshots():
    assert len(STEPS) == 6


@pytest.mark.parametrize("path", STEPS, ids=lambda p: p.stem)
def test_snapshot_parses(path):
    ast.parse(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", STEPS, ids=lambda p: p.stem)
def test_snapshot_does_not_reference_future_modules(path):
    source = path.read_text(encoding="utf-8")
    for module in FORBIDDEN[path.stem]:
        assert module not in source, f"{path.name}이 아직 없는 {module}을 참조합니다"


@pytest.mark.parametrize("path", STEPS, ids=lambda p: p.stem)
def test_snapshot_has_no_hardcoded_secret(path):
    source = path.read_text(encoding="utf-8")
    for marker in _SECRET_MARKERS:
        assert marker not in source, f"{path.name}에 API 키가 박혀 있습니다"


def test_step5_judge_matches_main():
    root = Path(__file__).resolve().parent.parent
    assert (root / "steps" / "step5_judge.py").read_text(encoding="utf-8") == (
        root / "main.py"
    ).read_text(encoding="utf-8")
