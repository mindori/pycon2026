from budget_battle import judge
from budget_battle.models import DebateTurn, Verdict


def test_prompt_carries_both_ledger_and_transcript(monkeypatch):
    captured = {}

    def fake_call(contents, schema, *, system_instruction=None, cache_key=None):
        captured["contents"] = contents
        captured["schema"] = schema
        captured["system_instruction"] = system_instruction
        return Verdict(score=72, diagnosis="무난합니다.", prescriptions=["a", "b", "c"])

    monkeypatch.setattr(judge.client, "generate_structured", fake_call)

    turns = [DebateTurn(speaker="자린고비 할머니", message="아껴라")]
    result = judge.judge_debate("총 지출 50,000원", turns)

    assert "총 지출 50,000원" in captured["contents"]
    assert "아껴라" in captured["contents"]
    assert captured["schema"] is Verdict
    assert captured["system_instruction"] == judge.JUDGE_INSTRUCTION
    assert result.score == 72


def test_works_with_an_empty_debate(monkeypatch):
    monkeypatch.setattr(
        judge.client,
        "generate_structured",
        lambda *args, **kwargs: Verdict(
            score=50, diagnosis="자료 부족", prescriptions=["a", "b", "c"]
        ),
    )
    assert judge.judge_debate("요약", []).score == 50


def test_judge_instruction_states_neutrality_and_three_prescriptions():
    assert "중립" in judge.JUDGE_INSTRUCTION
    assert "3개" in judge.JUDGE_INSTRUCTION
