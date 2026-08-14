"""프로젝트 전역 설정. 모든 상수와 비밀값 접근은 이 모듈을 거친다."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL_ID = "gemini-3.6-flash"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RECEIPTS_DIR = PROJECT_ROOT / "receipts"
CACHE_DIR = PROJECT_ROOT / "cache"

MAX_ROUNDS = 2
MAX_CALLS = 6

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 2.0


def get_api_key() -> str:
    """API 키를 읽는다. 없으면 다음 행동을 알려주는 메시지와 함께 실패한다.

    google-genai SDK는 GOOGLE_API_KEY와 GEMINI_API_KEY를 둘 다 인식한다.
    온라인 튜토리얼 다수가 후자를 쓰므로 두 이름 모두 받아들이되,
    둘 다 설정된 경우 GOOGLE_API_KEY를 우선한다.
    """
    key = os.getenv("GOOGLE_API_KEY", "").strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY를 찾을 수 없습니다.\n"
            "1) .env.example 파일을 복사해 .env 로 이름을 바꾸세요.\n"
            "2) 강사가 메일로 보내드린 키를 그 안에 붙여넣으세요.\n"
            "   메일이 안 왔으면 강사에게 알려 주세요.\n"
            "(GEMINI_API_KEY 라는 이름으로 넣어도 인식합니다.)"
        )
    return key
