from budget_battle import debate
from budget_battle.models import DebateTurn
from budget_battle.personas import DEFAULT_PERSONAS, FLEX, FRUGAL, GUARDRAIL, Persona

PAIR = (Persona(name="A", instruction="a"), Persona(name="B", instruction="b"))


def _fixed_reply(message="계속 반박합니다"):
    def speak(persona, ledger_summary, turns):
        return DebateTurn(speaker=persona.name, message=message)

    return speak


def test_runs_rounds_times_speakers_when_nobody_agrees(monkeypatch):
    monkeypatch.setattr(debate, "_speak", _fixed_reply())
    turns = debate.run_debate("요약", PAIR, max_rounds=3, max_calls=99)
    assert len(turns) == 6


def test_speaking_order_follows_persona_order(monkeypatch):
    monkeypatch.setattr(debate, "_speak", _fixed_reply())
    turns = debate.run_debate("요약", PAIR, max_rounds=2, max_calls=99)
    assert [turn.speaker for turn in turns] == ["A", "B", "A", "B"]


def test_call_cap_stops_before_round_cap(monkeypatch):
    monkeypatch.setattr(debate, "_speak", _fixed_reply())
    turns = debate.run_debate("요약", PAIR, max_rounds=10, max_calls=3)
    assert len(turns) == 3


def test_agreement_mark_stops_immediately(monkeypatch):
    calls = {"count": 0}

    def agree_on_second(persona, ledger_summary, turns):
        calls["count"] += 1
        message = "그 말이 맞네요 [합의]" if calls["count"] == 2 else "아니요"
        return DebateTurn(speaker=persona.name, message=message)

    monkeypatch.setattr(debate, "_speak", agree_on_second)
    turns = debate.run_debate("요약", PAIR, max_rounds=10, max_calls=99)
    assert len(turns) == 2
    assert calls["count"] == 2


def test_zero_rounds_makes_no_call(monkeypatch):
    def must_not_be_called(*args, **kwargs):
        raise AssertionError("호출되면 안 됩니다")

    monkeypatch.setattr(debate, "_speak", must_not_be_called)
    assert debate.run_debate("요약", PAIR, max_rounds=0) == []


def test_history_grows_without_mutating_previous_lists(monkeypatch):
    seen = []

    def recording_speak(persona, ledger_summary, turns):
        seen.append(turns)   # 길이가 아니라 리스트 자체를 붙잡아 둔다
        return DebateTurn(speaker=persona.name, message="말")

    monkeypatch.setattr(debate, "_speak", recording_speak)
    debate.run_debate("요약", PAIR, max_rounds=2, max_calls=99)
    # 뮤테이션했다면 네 참조가 모두 같은 리스트라 [4, 4, 4, 4]가 된다
    assert [len(turns) for turns in seen] == [0, 1, 2, 3]


def test_defaults_come_from_config(monkeypatch):
    monkeypatch.setattr(debate, "_speak", _fixed_reply())
    turns = debate.run_debate("요약", PAIR)
    assert len(turns) == 4  # MAX_ROUNDS=2 x 2 personas


def test_transcript_joins_speaker_and_message():
    turns = [DebateTurn(speaker="A", message="가"), DebateTurn(speaker="B", message="나")]
    assert debate.format_transcript(turns) == "A: 가\nB: 나"


def test_transcript_of_empty_history_is_a_notice():
    assert "없" in debate.format_transcript([])


def test_speak_passes_persona_instruction_as_system_instruction(monkeypatch):
    captured = {}

    def fake_generate_text(contents, *, system_instruction=None):
        captured["system_instruction"] = system_instruction
        captured["contents"] = contents
        return "발언 내용"

    monkeypatch.setattr(debate.client, "generate_text", fake_generate_text)
    turn = debate._speak(FRUGAL, "가계부 요약", [])

    assert captured["system_instruction"] == FRUGAL.instruction
    assert "가계부 요약" in captured["contents"]
    assert turn.speaker == FRUGAL.name
    assert turn.message == "발언 내용"


def test_both_personas_carry_the_guardrail():
    assert GUARDRAIL in FRUGAL.instruction
    assert GUARDRAIL in FLEX.instruction


def test_guardrail_explains_the_agreement_mark():
    assert debate.AGREEMENT_MARK in GUARDRAIL


def test_default_personas_is_a_pair():
    assert len(DEFAULT_PERSONAS) == 2
