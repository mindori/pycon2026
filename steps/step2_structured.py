"""1막 끝 — 영수증을 구조화된 데이터로 받기.

Category를 자유 문자열이 아니라 Enum으로 가둔 덕분에 "카페", "카페/간식",
"커피" 같은 표기가 난립하지 않습니다. 합계도 LLM이 아니라 파이썬이 더합니다.
"""

from budget_battle import config, vision

image_path = config.RECEIPTS_DIR / "sample_01.jpg"
receipt = vision.extract_receipt(image_path)

print(f"{receipt.store} / {receipt.purchased_at}")
for item in receipt.items:
    print(f"  {item.name} — {item.price:,}원 x {item.quantity} ({item.category.value})")
print(f"합계: {receipt.total:,}원")
