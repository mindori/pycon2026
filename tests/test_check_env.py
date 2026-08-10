import io
import urllib.error
import urllib.request

import pytest

import check_env
from budget_battle import config


def test_parses_key_value_pairs(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "# 주석\n\nGOOGLE_API_KEY=abc123\nOTHER = spaced \n", encoding="utf-8"
    )
    parsed = check_env.parse_env_file(path)
    assert parsed["GOOGLE_API_KEY"] == "abc123"
    assert parsed["OTHER"] == "spaced"


def test_missing_file_yields_empty_dict(tmp_path):
    assert check_env.parse_env_file(tmp_path / "absent") == {}


def test_quotes_are_stripped(tmp_path):
    path = tmp_path / ".env"
    path.write_text('GOOGLE_API_KEY="quoted"\n', encoding="utf-8")
    assert check_env.parse_env_file(path)["GOOGLE_API_KEY"] == "quoted"


def test_python_version_gate():
    assert check_env.python_version_ok((3, 11)) is True
    assert check_env.python_version_ok((3, 12)) is True
    assert check_env.python_version_ok((3, 10)) is False


def test_model_id_matches_config():
    """check_env.py는 config.py를 import할 수 없어(python-dotenv 필요) MODEL_ID를
    문자열로 중복 정의한다. 두 값이 어긋나면 참가자가 배포 저장소에서는 통과하는데
    실제 앱은 다른 모델을 부르는, 진단이 거짓말을 하는 상황이 생긴다."""
    assert check_env.MODEL_ID == config.MODEL_ID


class _FakeHTTPResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _fake_urlopen_success(*args, **kwargs):
    return _FakeHTTPResponse(b'{"ok": true}')


def _fake_urlopen_http_error(code):
    def _raise(*args, **kwargs):
        raise urllib.error.HTTPError("http://example.com", code, "error", {}, None)

    return _raise


def _fake_urlopen_url_error(*args, **kwargs):
    raise urllib.error.URLError("연결 실패")


def test_verify_key_works_success(monkeypatch):
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_success)
    ok, reason = check_env._verify_key_works("fake-key")
    assert ok is True
    assert reason == ""


def test_verify_key_works_http_error(monkeypatch):
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_http_error(403))
    ok, reason = check_env._verify_key_works("fake-key")
    assert ok is False
    assert "403" in reason


def test_verify_key_works_network_error(monkeypatch):
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_url_error)
    ok, reason = check_env._verify_key_works("fake-key")
    assert ok is False
    assert "네트워크" in reason


def test_verify_model_responds_success(monkeypatch):
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_success)
    ok, reason = check_env._verify_model_responds("fake-key")
    assert ok is True
    assert reason == ""


def test_verify_model_responds_404_mentions_model_id(monkeypatch):
    """모델이 없어졌을 때(신규 사용자 404)를 키 오류와 구분해 알려줘야 한다."""
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_http_error(404))
    ok, reason = check_env._verify_model_responds("fake-key")
    assert ok is False
    assert check_env.MODEL_ID in reason


def test_verify_model_responds_other_http_error(monkeypatch):
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_http_error(500))
    ok, reason = check_env._verify_model_responds("fake-key")
    assert ok is False
    assert "500" in reason


def test_verify_model_responds_network_error(monkeypatch):
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_url_error)
    ok, reason = check_env._verify_model_responds("fake-key")
    assert ok is False
    assert "네트워크" in reason


def test_verify_model_responds_429_is_a_pass_not_a_failure(monkeypatch):
    """429(분당 요청 한도 초과)는 키가 인증을 통과했다는 증거다. client.py는
    이 순간을 재시도로 넘기지만 check_env.py는 한 번만 때리므로, 이걸 실패로
    잡으면 멀쩡한 키를 가진 참가자에게 '키가 안 됩니다'라는 거짓 경보를 준다."""
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_http_error(429))
    ok, detail = check_env._verify_model_responds("fake-key")
    assert ok is True
    assert "한도" in detail


@pytest.mark.parametrize("code", [401, 403])
def test_verify_model_responds_401_403_report_key_rejected(monkeypatch, code):
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_http_error(code))
    ok, reason = check_env._verify_model_responds("fake-key")
    assert ok is False
    assert "거부" in reason
    assert str(code) in reason


def test_main_returns_zero_when_all_pass(monkeypatch, tmp_path, capsys):
    env_path = tmp_path / ".env"
    env_path.write_text("GOOGLE_API_KEY=real-key\n", encoding="utf-8")
    monkeypatch.setattr(check_env, "__file__", str(tmp_path / "check_env.py"))
    monkeypatch.setattr(check_env.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_success)
    monkeypatch.setattr(check_env, "python_version_ok", lambda version: True)

    exit_code = check_env.main()

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "모두 통과했습니다" in output


def test_main_passes_with_caveat_when_model_call_is_rate_limited(monkeypatch, tmp_path, capsys):
    """429가 나도 전체 진단은 통과해야 한다. 키 확인(GET)은 성공시키고
    모델 호출(POST)만 429를 내는 가짜 urlopen으로 두 요청을 구분한다."""
    env_path = tmp_path / ".env"
    env_path.write_text("GOOGLE_API_KEY=real-key\n", encoding="utf-8")
    monkeypatch.setattr(check_env, "__file__", str(tmp_path / "check_env.py"))
    monkeypatch.setattr(check_env.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(check_env, "python_version_ok", lambda version: True)

    def _fake_urlopen(*args, **kwargs):
        target = args[0] if args else kwargs.get("url")
        if isinstance(target, urllib.request.Request):
            raise urllib.error.HTTPError("http://example.com", 429, "rate limited", {}, None)
        return _FakeHTTPResponse(b'{"ok": true}')

    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen)

    exit_code = check_env.main()

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "❌" not in output
    assert "한도" in output
    assert "모두 통과했습니다" in output


def test_main_returns_one_when_key_missing(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(check_env, "__file__", str(tmp_path / "check_env.py"))
    monkeypatch.setattr(check_env.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(check_env, "python_version_ok", lambda version: True)

    exit_code = check_env.main()

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "❌" in output


def test_main_skips_api_calls_when_key_missing(monkeypatch, tmp_path, capsys):
    """키가 없으면 urlopen을 아예 호출하지 않아야 한다 — 테스트가 네트워크를
    타지 않는다는 요구사항과, 참가자에게 헛된 대기시간을 주지 않는다는 요구를
    동시에 지킨다."""
    monkeypatch.setattr(check_env, "__file__", str(tmp_path / "check_env.py"))
    monkeypatch.setattr(check_env.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(check_env, "python_version_ok", lambda version: True)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("키가 없을 때는 네트워크를 호출하면 안 된다")

    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fail_if_called)

    exit_code = check_env.main()

    assert exit_code == 1
