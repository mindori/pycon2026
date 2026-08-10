"""LLM 입출력 계약. 이 파일의 description은 그대로 모델에게 전달되는 지시문이다."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Category(str, Enum):
    """소비 카테고리. LLM이 자유 문자열을 뱉지 못하도록 가두는 장치."""

    FOOD = "식비"
    CAFE = "카페/간식"
    TRANSPORT = "교통"
    SHOPPING = "쇼핑"
    CULTURE = "문화/여가"
    BEAUTY_HEALTH = "미용/건강"
    LIVING = "생활용품"
    ETC = "기타"


class ReceiptItem(BaseModel):
    name: str = Field(description="영수증에 적힌 상품명 그대로")
    price: int = Field(description="단가(원). 쉼표 없이 정수로 적는다")
    quantity: int = Field(default=1, ge=1, description="수량. 표기가 없으면 1")
    category: Category = Field(description="상품이 속한 소비 카테고리")


class Receipt(BaseModel):
    store: str | None = Field(default=None, description="매장명. 읽을 수 없으면 null")
    purchased_at: date | None = Field(default=None, description="구매 일자. 읽을 수 없으면 null")
    items: list[ReceiptItem] = Field(description="구매 항목 목록")

    @property
    def total(self) -> int:
        """합계는 LLM이 아니라 파이썬이 계산한다."""
        return sum(item.price * item.quantity for item in self.items)


class DebateTurn(BaseModel):
    speaker: str
    message: str


class Verdict(BaseModel):
    score: int = Field(ge=0, le=100, description="재무 건강 점수(0~100)")
    diagnosis: str = Field(description="두세 문장의 진단")
    prescriptions: list[str] = Field(
        min_length=2,
        max_length=5,
        description="오늘 당장 실행 가능한 처방 정확히 3개",
    )
