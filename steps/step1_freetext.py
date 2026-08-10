"""0막 — 영수증을 자유 텍스트로 읽기.

이 결과를 코드로 쓰려면 어떻게 해야 할까요? 그게 1막의 주제입니다.
"""

from google.genai import types

from budget_battle import client, config

image_path = config.RECEIPTS_DIR / "sample_01.jpg"
part = types.Part.from_bytes(data=image_path.read_bytes(), mime_type="image/jpeg")

print(client.generate_text([part, "이 영수증에 뭐가 적혀 있어? 항목과 금액을 알려줘."]))
