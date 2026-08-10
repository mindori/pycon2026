"""LLM 호출 단일 창구. 재시도·지수 백오프·캐시 폴백을 담당한다.

이 파일은 튜토리얼 참가자가 작성하지 않는다. 현장 네트워크가 불안정해도
진도가 멈추지 않게 하려고 미리 넣어둔 안전장치다.
"""

import time
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from budget_battle import config

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")


class ApiCallFailed(RuntimeError):
    """재시도를 모두 소진하고 캐시 폴백도 실패한 경우."""


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    return genai.Client(api_key=config.get_api_key())


def _with_retry(call: Callable[[], R]) -> R:
    last_error: Exception | None = None
    for attempt in range(config.RETRY_ATTEMPTS):
        try:
            return call()
        except Exception as error:  # API 오류 종류가 다양해 광범위하게 잡는다
            last_error = error
            if attempt < config.RETRY_ATTEMPTS - 1:
                time.sleep(config.RETRY_BASE_DELAY * (2**attempt))
    raise ApiCallFailed(
        f"API 호출에 {config.RETRY_ATTEMPTS}회 실패했습니다: {last_error}"
    ) from last_error


def _cache_path(cache_key: str) -> Path:
    return config.CACHE_DIR / f"{cache_key}.json"


def _load_cache(cache_key: str, schema: type[T]) -> T | None:
    path = _cache_path(cache_key)
    if not path.exists():
        return None
    try:
        return schema.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(cache_key: str, value: BaseModel) -> None:
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(cache_key).write_text(
        value.model_dump_json(indent=2), encoding="utf-8"
    )


def generate_structured(
    contents: Any,
    schema: type[T],
    *,
    system_instruction: str | None = None,
    cache_key: str | None = None,
) -> T:
    """스키마를 강제해 파싱된 객체를 받는다.

    cache_key가 주어졌을 때만 캐시에 저장하고, 호출이 끝내 실패하면 캐시로
    폴백한다. cache_key가 없으면 폴백도 없다 — 판정관(judge.py)이 그 경우다.
    """

    # 재시도 루프 밖에서 한 번만 얻는다. API 키 누락 같은 설정 오류를
    # 3회 재시도하며 6초를 버리는 대신 즉시 안내 메시지로 알리기 위함이다.
    llm_client = get_client()

    def call() -> T:
        response = llm_client.models.generate_content(
            model=config.MODEL_ID,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                system_instruction=system_instruction,
            ),
        )
        if response.parsed is None:
            raise ValueError("모델이 스키마에 맞는 응답을 반환하지 않았습니다.")
        return response.parsed

    try:
        result = _with_retry(call)
    except ApiCallFailed:
        cached = _load_cache(cache_key, schema) if cache_key else None
        if cached is None:
            raise
        # 캐시 키는 파일 내용이 아니라 파일명이다. 참가자가 sample_01.jpg를
        # 자기 영수증으로 덮어쓴 상태에서 여기 걸리면 남의 추출 결과가 돌아온다.
        # 조용히 넘기면 그 뒤 토론과 점수가 통째로 남의 소비에 대한 것이 된다.
        print(f"(API 호출 실패 — cache/{cache_key}.json 에 저장된 결과를 대신 사용합니다)")
        return cached

    if cache_key:
        _save_cache(cache_key, result)
    return result


def generate_text(contents: Any, *, system_instruction: str | None = None) -> str:
    """자유 텍스트 응답을 받는다."""

    llm_client = get_client()

    def call() -> str:
        response = llm_client.models.generate_content(
            model=config.MODEL_ID,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system_instruction),
        )
        text = (response.text or "").strip()
        if not text:
            # generate_structured가 parsed=None을 실패로 올리는 것과 같은 이유다.
            # 빈 발언을 성공으로 넘기면 아무도 말하지 않은 토론에 점수가 매겨진다.
            raise ValueError("모델이 빈 응답을 반환했습니다.")
        return text

    return _with_retry(call)
