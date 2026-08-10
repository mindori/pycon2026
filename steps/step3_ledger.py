"""2막 끝 — 영수증을 가계부로 정리하기.

여기까지는 순수 파이썬이라 API 사고가 없는 구간입니다. 이 요약 텍스트를
두고 다음 막에서 AI 둘이 토론합니다.
"""

from budget_battle import config, ledger, vision

image_path = config.RECEIPTS_DIR / "sample_01.jpg"
receipt = vision.extract_receipt(image_path)

book = ledger.build_ledger([receipt])
summary = ledger.summarize_for_agents(book)

print(summary)
