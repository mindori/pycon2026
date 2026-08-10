import pytest

from budget_battle import config


def test_returns_api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")
    assert config.get_api_key() == "test-key-123"


def test_missing_key_raises_with_guidance(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as error:
        config.get_api_key()
    assert ".env" in str(error.value)


def test_blank_key_is_treated_as_missing(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "   ")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        config.get_api_key()


def test_falls_back_to_gemini_api_key(monkeypatch):
    """google-genai SDK는 GEMINI_API_KEY도 인식하므로, 온라인 튜토리얼을 따라
    이 이름으로 키를 설정한 참가자도 통과해야 한다."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-456")
    assert config.get_api_key() == "gemini-key-456"


def test_google_api_key_wins_when_both_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    assert config.get_api_key() == "google-key"


def test_neither_key_set_raises_with_guidance(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as error:
        config.get_api_key()
    assert "GOOGLE_API_KEY" in str(error.value)


def test_path_constants_are_relative_to_project_root():
    assert config.RECEIPTS_DIR.name == "receipts"
    assert config.CACHE_DIR.name == "cache"
    assert config.RECEIPTS_DIR.parent == config.PROJECT_ROOT
