"""토론 전체를 읽고 재무 건강 점수와 처방을 내는 판정관.

1막에서 배운 구조화 출력이 여기서 다시 쓰인다.
"""

from budget_battle import client
from budget_battle.debate import format_transcript
from budget_battle.models import DebateTurn, Verdict

JUDGE_INSTRUCTION = (
    "당신은 중립적인 재무 판정관입니다. "
    "두 토론자의 주장을 모두 참고하되 어느 한쪽에 치우치지 않습니다. "
    "점수는 0~100점으로 매기고, 처방은 오늘 당장 실행할 수 있는 것으로 "
    "정확히 3개 제시합니다."
)


def judge_debate(ledger_summary: str, turns: list[DebateTurn]) -> Verdict:
    prompt = (
        f"[가계부]\n{ledger_summary}\n\n"
        f"[토론 기록]\n{format_transcript(turns)}\n\n"
        "위 내용을 종합해 재무 건강 점수와 처방을 내리세요."
    )
    return client.generate_structured(
        contents=prompt,
        schema=Verdict,
        system_instruction=JUDGE_INSTRUCTION,
    )
