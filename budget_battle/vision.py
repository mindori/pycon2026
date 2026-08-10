"""영수증 사진을 Receipt 객체로 바꾼다."""

from pathlib import Path

from google.genai import types

from budget_battle import client
from budget_battle.models import Receipt

EXTRACT_PROMPT = """이 영수증 사진을 읽고 구매 항목을 빠짐없이 추출하세요.

규칙:
- 항목명은 영수증에 적힌 그대로 옮깁니다. 의역하지 마세요.
- 금액은 쉼표 없이 정수(원)로 적습니다.
- 합계, 부가세, 받은금액, 거스름돈, 할인 줄은 구매 항목이 아니므로 제외합니다.
- 매장명이나 날짜를 읽을 수 없으면 null로 두세요. 추측해서 지어내지 마세요.
- 품목이 한 줄도 적혀 있지 않은 카드 전표라면, 매장명을 항목명으로 하고
  승인 금액을 가격으로 하는 항목 하나만 만드세요.
"""

_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

#: 지원 확장자의 단일 출처. main.py와 app.py가 이 목록을 재사용한다.
SUPPORTED_SUFFIXES = tuple(_MIME_TYPES)


def _mime_type(image_path: Path) -> str:
    mime = _MIME_TYPES.get(image_path.suffix.lower())
    if mime is None:
        raise ValueError(
            f"지원하지 않는 이미지 형식입니다: {image_path.suffix}\n"
            f"jpg, jpeg, png, webp 중 하나로 변환해 주세요."
        )
    return mime


def extract_receipt(image_path: Path) -> Receipt:
    """영수증 이미지 한 장을 구조화된 Receipt로 변환한다."""
    if not image_path.exists():
        raise FileNotFoundError(
            f"영수증 이미지를 찾을 수 없습니다: {image_path}\n"
            f"receipts/ 폴더에 파일이 있는지 확인하세요."
        )

    image_part = types.Part.from_bytes(
        data=image_path.read_bytes(),
        mime_type=_mime_type(image_path),
    )
    return client.generate_structured(
        contents=[image_part, EXTRACT_PROMPT],
        schema=Receipt,
        cache_key=f"receipt_{image_path.stem}",
    )
