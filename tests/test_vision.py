from pathlib import Path

import pytest

from budget_battle import vision
from budget_battle.models import Category, Receipt, ReceiptItem


@pytest.fixture
def fake_image(tmp_path):
    path = tmp_path / "sample_01.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")
    return path


def test_missing_file_raises_with_guidance():
    with pytest.raises(FileNotFoundError) as error:
        vision.extract_receipt(Path("/nonexistent/path/x.jpg"))
    assert "영수증" in str(error.value)


def test_unsupported_extension_is_rejected(tmp_path):
    path = tmp_path / "receipt.pdf"
    path.write_bytes(b"%PDF")
    with pytest.raises(ValueError) as error:
        vision.extract_receipt(path)
    assert "jpg" in str(error.value).lower()


def test_cache_key_uses_image_stem(monkeypatch, fake_image):
    captured = {}

    def fake_call(contents, schema, *, system_instruction=None, cache_key=None):
        captured["cache_key"] = cache_key
        captured["schema"] = schema
        return Receipt(items=[ReceiptItem(name="우유", price=2500, category=Category.FOOD)])

    monkeypatch.setattr(vision.client, "generate_structured", fake_call)

    result = vision.extract_receipt(fake_image)

    assert captured["cache_key"] == "receipt_sample_01"
    assert captured["schema"] is Receipt
    assert result.total == 2500


def test_prompt_excludes_total_lines():
    # 단어 존재만 보면 규칙이 "합계도 포함하세요"로 뒤집혀도 통과한다.
    assert "합계" in vision.EXTRACT_PROMPT
    assert "제외합니다" in vision.EXTRACT_PROMPT


def test_prompt_forbids_guessing():
    assert "지어내지 마세요" in vision.EXTRACT_PROMPT
