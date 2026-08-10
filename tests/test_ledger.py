from budget_battle.ledger import build_ledger, summarize_for_agents
from budget_battle.models import Category, Receipt, ReceiptItem


def _receipt(*items):
    return Receipt(items=list(items))


def _item(price, category, quantity=1, name="항목"):
    return ReceiptItem(name=name, price=price, quantity=quantity, category=category)


def test_same_category_within_one_receipt_is_summed():
    ledger = build_ledger([_receipt(_item(3000, Category.FOOD), _item(2000, Category.FOOD))])
    assert ledger.totals[Category.FOOD] == 5000


def test_same_category_across_receipts_is_summed():
    ledger = build_ledger([
        _receipt(_item(3000, Category.FOOD)),
        _receipt(_item(2000, Category.FOOD)),
    ])
    assert ledger.totals[Category.FOOD] == 5000


def test_quantity_is_applied():
    ledger = build_ledger([_receipt(_item(1000, Category.CAFE, quantity=3))])
    assert ledger.totals[Category.CAFE] == 3000


def test_absent_category_is_not_a_key():
    ledger = build_ledger([_receipt(_item(1000, Category.CAFE))])
    assert Category.TRANSPORT not in ledger.totals


def test_empty_input_produces_empty_ledger():
    ledger = build_ledger([])
    assert ledger.totals == {}
    assert ledger.grand_total == 0
    assert ledger.receipt_count == 0


def test_grand_total_sums_every_category():
    ledger = build_ledger([_receipt(_item(3000, Category.FOOD), _item(4500, Category.CAFE))])
    assert ledger.grand_total == 7500


def test_summary_is_sorted_by_amount_desc():
    ledger = build_ledger([_receipt(_item(1000, Category.CAFE), _item(9000, Category.FOOD))])
    summary = summarize_for_agents(ledger)
    assert summary.index("식비") < summary.index("카페/간식")


def test_summary_includes_total_and_receipt_count():
    ledger = build_ledger([_receipt(_item(9000, Category.FOOD))])
    summary = summarize_for_agents(ledger)
    assert "9,000" in summary
    assert "1장" in summary


def test_summary_says_so_when_there_is_nothing():
    assert "영수증이 없어" in summarize_for_agents(build_ledger([]))


def test_read_receipts_with_no_items_do_not_claim_there_was_no_receipt():
    # Vision이 읽기에 실패한 경우다. 이 문자열은 그대로 에이전트 프롬프트가 되므로
    # "영수증이 없다"고 말하면 토론과 판정이 거짓 전제 위에서 진행된다.
    summary = summarize_for_agents(build_ledger([_receipt(), _receipt()]))
    assert "영수증이 없어" not in summary
    assert "2장" in summary
    assert "인식하지 못했습니다" in summary


def test_zero_total_does_not_divide_by_zero():
    ledger = build_ledger([_receipt(_item(0, Category.ETC))])
    summary = summarize_for_agents(ledger)
    assert "0원" in summary  # 항목은 있으므로 인식 실패 분기로 새면 안 된다
