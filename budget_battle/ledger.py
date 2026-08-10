"""추출한 영수증들을 카테고리별로 집계한다. LLM을 쓰지 않는 순수 파이썬 구간."""

from collections import Counter

from pydantic import BaseModel

from budget_battle.models import Category, Receipt


class Ledger(BaseModel):
    totals: dict[Category, int]
    receipt_count: int

    @property
    def grand_total(self) -> int:
        return sum(self.totals.values())


def build_ledger(receipts: list[Receipt]) -> Ledger:
    """영수증 목록을 카테고리별 합계로 집계한다."""
    counter: Counter[Category] = Counter()
    for receipt in receipts:
        for item in receipt.items:
            counter[item.category] += item.price * item.quantity
    return Ledger(totals=dict(counter), receipt_count=len(receipts))


def summarize_for_agents(ledger: Ledger) -> str:
    """에이전트에게 넘길 가계부 요약 텍스트를 만든다.

    이 문자열은 화면 출력이 아니라 다음 세 번의 LLM 호출에 그대로 들어가는
    프롬프트다. 여기서 사실이 아닌 문장을 만들면 토론과 판정 전체가 그
    거짓 전제 위에서 진행되고, 어디서도 예외가 나지 않는다.
    """
    if ledger.receipt_count == 0:
        return "영수증이 없어 분석할 소비 내역이 없습니다."

    if not ledger.totals:
        return (
            f"영수증 {ledger.receipt_count}장을 읽었지만 항목을 하나도 인식하지 못했습니다.\n"
            "사진이 흐리거나 잘렸을 수 있습니다. 더 밝은 곳에서 다시 찍어 보세요."
        )

    total = ledger.grand_total
    ranked = sorted(ledger.totals.items(), key=lambda pair: -pair[1])
    lines = [
        f"- {category.value}: {amount:,}원"
        + (f" ({amount / total * 100:.0f}%)" if total else "")
        for category, amount in ranked
    ]
    return f"영수증 {ledger.receipt_count}장, 총 지출 {total:,}원\n" + "\n".join(lines)
