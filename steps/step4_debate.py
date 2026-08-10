"""3막 끝 — 페르소나 토론 + 종료 조건 3종.

무한 루프(폭주) 방지, 호출 상한, 합의 감지가 토론 루프를 멈춥니다.
이 토론에 점수를 매기는 판정관을 붙이는 것이 4막의 주제입니다.
"""

from budget_battle import config, ledger, personas, vision
from budget_battle.debate import run_debate

image_path = config.RECEIPTS_DIR / "sample_01.jpg"
receipt = vision.extract_receipt(image_path)

book = ledger.build_ledger([receipt])
summary = ledger.summarize_for_agents(book)
print(f"[내 가계부]\n{summary}")

turns = run_debate(summary, personas.DEFAULT_PERSONAS)
for turn in turns:
    print(f"\n<{turn.speaker}>\n{turn.message}")
