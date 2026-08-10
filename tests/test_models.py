import pytest
from pydantic import ValidationError

from budget_battle.models import Category, DebateTurn, Receipt, ReceiptItem, Verdict


def _item(name="아메리카노", price=4500, quantity=1, category=Category.CAFE):
    return ReceiptItem(name=name, price=price, quantity=quantity, category=category)


def test_total_multiplies_price_by_quantity():
    receipt = Receipt(items=[_item(price=4500, quantity=2), _item(price=1000, quantity=3)])
    assert receipt.total == 12000


def test_total_is_zero_without_items():
    assert Receipt(items=[]).total == 0


def test_store_and_date_are_optional():
    receipt = Receipt(items=[_item()])
    assert receipt.store is None
    assert receipt.purchased_at is None


def test_quantity_defaults_to_one():
    assert ReceiptItem(name="우유", price=2500, category=Category.FOOD).quantity == 1


def test_quantity_below_one_is_rejected():
    with pytest.raises(ValidationError):
        ReceiptItem(name="우유", price=2500, quantity=0, category=Category.FOOD)


def test_category_rejects_undefined_value():
    with pytest.raises(ValidationError):
        ReceiptItem(name="우유", price=2500, category="먹거리")


def test_beauty_health_category_exists():
    # 미용실·약국 영수증이 갈 곳이 없어 기타로 몰리면 토론 소재가 사라진다.
    item = ReceiptItem(name="커트", price=25000, category=Category.BEAUTY_HEALTH)
    assert item.category.value == "미용/건강"


def test_verdict_accepts_three_prescriptions():
    verdict = Verdict(score=70, diagnosis="괜찮습니다.", prescriptions=["a", "b", "c"])
    assert len(verdict.prescriptions) == 3


def test_verdict_tolerates_two_to_five_prescriptions():
    # 프롬프트는 3개를 요구하지만, 모델이 흔들려도 피날레가 깨지지 않도록 여유를 둔다.
    assert len(Verdict(score=70, diagnosis="x", prescriptions=["a", "b"]).prescriptions) == 2
    assert len(Verdict(score=70, diagnosis="x", prescriptions=list("abcde")).prescriptions) == 5


def test_verdict_rejects_one_prescription():
    with pytest.raises(ValidationError):
        Verdict(score=70, diagnosis="x", prescriptions=["a"])


def test_verdict_rejects_six_prescriptions():
    with pytest.raises(ValidationError):
        Verdict(score=70, diagnosis="x", prescriptions=list("abcdef"))


def test_verdict_score_must_not_exceed_100():
    with pytest.raises(ValidationError):
        Verdict(score=101, diagnosis="x", prescriptions=["a", "b", "c"])


def test_verdict_score_must_not_be_negative():
    with pytest.raises(ValidationError):
        Verdict(score=-1, diagnosis="x", prescriptions=["a", "b", "c"])


def test_debate_turn_holds_speaker_and_message():
    turn = DebateTurn(speaker="자린고비 할머니", message="아이고 이게 뭐냐")
    assert turn.speaker == "자린고비 할머니"
