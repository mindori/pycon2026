from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from budget_battle import client, config


class Dummy(BaseModel):
    value: str


@pytest.fixture(autouse=True)
def _no_backoff_delay(monkeypatch):
    monkeypatch.setattr(config, "RETRY_BASE_DELAY", 0.0)


@pytest.fixture
def cache_dir(monkeypatch, tmp_path):
    path = tmp_path / "cache"
    monkeypatch.setattr(config, "CACHE_DIR", path)
    return path


def _fake_client(responses):
    """호출될 때마다 responses를 순서대로 반환한다. Exception이면 raise한다."""
    remaining = list(responses)

    def generate_content(**kwargs):
        result = remaining.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    return SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))


def test_returns_parsed_object_on_success(monkeypatch, cache_dir):
    response = SimpleNamespace(parsed=Dummy(value="ok"), text='{"value": "ok"}')
    monkeypatch.setattr(client, "get_client", lambda: _fake_client([response]))

    result = client.generate_structured("prompt", Dummy)

    assert result.value == "ok"


def test_saves_cache_file_when_cache_key_given(monkeypatch, cache_dir):
    response = SimpleNamespace(parsed=Dummy(value="ok"), text="{}")
    monkeypatch.setattr(client, "get_client", lambda: _fake_client([response]))

    client.generate_structured("prompt", Dummy, cache_key="receipt_01")

    assert (cache_dir / "receipt_01.json").exists()


def test_retries_after_transient_failure(monkeypatch, cache_dir):
    response = SimpleNamespace(parsed=Dummy(value="ok"), text="{}")
    monkeypatch.setattr(
        client, "get_client", lambda: _fake_client([RuntimeError("429"), response])
    )

    assert client.generate_structured("prompt", Dummy).value == "ok"


def test_falls_back_to_cache_when_all_attempts_fail(monkeypatch, cache_dir):
    cache_dir.mkdir(parents=True)
    (cache_dir / "receipt_01.json").write_text('{"value": "cached"}', encoding="utf-8")
    monkeypatch.setattr(
        client, "get_client", lambda: _fake_client([RuntimeError("429")] * 3)
    )

    result = client.generate_structured("prompt", Dummy, cache_key="receipt_01")

    assert result.value == "cached"


def test_raises_when_no_cache_available(monkeypatch, cache_dir):
    monkeypatch.setattr(
        client, "get_client", lambda: _fake_client([RuntimeError("429")] * 3)
    )

    with pytest.raises(client.ApiCallFailed):
        client.generate_structured("prompt", Dummy, cache_key="absent")


def test_unparsed_response_counts_as_failure(monkeypatch, cache_dir):
    response = SimpleNamespace(parsed=None, text="그냥 텍스트")
    monkeypatch.setattr(client, "get_client", lambda: _fake_client([response] * 3))

    with pytest.raises(client.ApiCallFailed):
        client.generate_structured("prompt", Dummy)


def test_generate_text_returns_stripped_text(monkeypatch):
    response = SimpleNamespace(parsed=None, text="  안녕하세요  ")
    monkeypatch.setattr(client, "get_client", lambda: _fake_client([response]))

    assert client.generate_text("prompt") == "안녕하세요"


def test_generate_text_empty_response_counts_as_failure(monkeypatch, cache_dir):
    # 안전 필터에 걸리면 text가 빈 문자열로 온다. 이걸 성공으로 넘기면
    # 아무 말도 하지 않은 페르소나 발언이 그대로 토론과 판정에 들어간다.
    response = SimpleNamespace(parsed=None, text="   ")
    monkeypatch.setattr(client, "get_client", lambda: _fake_client([response] * 3))

    with pytest.raises(client.ApiCallFailed):
        client.generate_text("prompt")


def test_missing_api_key_fails_fast_without_retry_or_cache(monkeypatch, cache_dir):
    """API 키 누락은 영구 오류다. 재시도나 캐시 폴백으로 감추지 않고 즉시 안내한다."""
    cache_dir.mkdir(parents=True)
    (cache_dir / "receipt_01.json").write_text('{"value": "cached"}', encoding="utf-8")

    def no_key():
        raise RuntimeError("GOOGLE_API_KEY를 찾을 수 없습니다.")

    monkeypatch.setattr(client, "get_client", no_key)

    with pytest.raises(RuntimeError) as error:
        client.generate_structured("prompt", Dummy, cache_key="receipt_01")

    assert not isinstance(error.value, client.ApiCallFailed)
    assert "GOOGLE_API_KEY" in str(error.value)


def test_generate_text_missing_api_key_fails_fast(monkeypatch):
    """generate_text도 get_client() 실패를 재시도로 감싸지 않고 즉시 전파한다."""

    def no_key():
        raise RuntimeError("GOOGLE_API_KEY를 찾을 수 없습니다.")

    monkeypatch.setattr(client, "get_client", no_key)

    with pytest.raises(RuntimeError) as error:
        client.generate_text("prompt")

    assert not isinstance(error.value, client.ApiCallFailed)
