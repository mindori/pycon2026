"""두 페르소나의 토론 루프.

종료 조건 3종이 서로 다른 실패를 막는다:
  ① max_rounds  - 무한 루프(폭주)를 막는다
  ② max_calls   - 예상치 못한 비용 폭증을 막는다
  ③ 합의 감지    - 결론이 난 뒤의 무의미한 반복을 막는다
"""

from budget_battle import client, config
from budget_battle.models import DebateTurn
from budget_battle.personas import Persona

AGREEMENT_MARK = "[합의]"


def format_transcript(turns: list[DebateTurn]) -> str:
    if not turns:
        return "(아직 발언이 없습니다)"
    return "\n".join(f"{turn.speaker}: {turn.message}" for turn in turns)


def _speak(
    persona: Persona, ledger_summary: str, turns: list[DebateTurn]
) -> DebateTurn:
    prompt = (
        f"[가계부]\n{ledger_summary}\n\n"
        f"[지금까지의 토론]\n{format_transcript(turns)}\n\n"
        f"이제 {persona.name}인 당신의 차례입니다. 의견을 말하세요."
    )
    message = client.generate_text(prompt, system_instruction=persona.instruction)
    return DebateTurn(speaker=persona.name, message=message)


def run_debate(
    ledger_summary: str,
    personas: tuple[Persona, Persona],
    max_rounds: int = config.MAX_ROUNDS,
    max_calls: int = config.MAX_CALLS,
) -> list[DebateTurn]:
    turns: list[DebateTurn] = []

    for _ in range(max_rounds):  # ① 하드 캡
        for persona in personas:
            if len(turns) >= max_calls:  # ② 호출 상한
                return turns

            turn = _speak(persona, ledger_summary, turns)
            turns = [*turns, turn]

            if AGREEMENT_MARK in turn.message:  # ③ 수렴 감지
                return turns

    return turns
