import io
import json
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


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "여기에_강사가_보낸_키를_붙여넣으세요",
        "여기에_발급받은_키를_붙여넣으세요",
        "당일_수업_시작_전에_공개됩니다",
    ],
)
def test_is_placeholder_detects_korean_guidance_text(value):
    """안내문을 그대로 둔 .env를 통과시키면 안 된다. Google API 키는 전부
    ASCII이므로 한글이 한 글자라도 있으면 아직 안 넣은 것이다. 특정 문구를
    하드코딩하면 문서를 고칠 때마다 검사가 샌다."""
    assert check_env.is_placeholder(value) is True


@pytest.mark.parametrize(
    "value",
    [
        # scripts/sync-public.sh의 시크릿 스캐너는 AIza…/AQ.… 패턴을 파일에서
        # grep으로 찾는다. 가짜 키라도 소스에 통째로 적어두면 배포가 막히므로
        # 이어붙여 만든다. 스캐너를 무디게 고치는 것보다 이쪽이 안전하다.
        "AIza" + "B" * 35,
        "AQ." + "A" * 50,
        "real-key",
    ],
)
def test_is_placeholder_accepts_real_looking_keys(value):
    assert check_env.is_placeholder(value) is False


def test_main_rejects_untouched_env_example(monkeypatch, tmp_path, capsys):
    """.env.example을 복사만 하고 키를 안 넣은 상태. 네트워크도 안 타야 한다."""
    env_path = tmp_path / ".env"
    env_path.write_text("GOOGLE_API_KEY=여기에_강사가_보낸_키를_붙여넣으세요\n", encoding="utf-8")
    monkeypatch.setattr(check_env, "__file__", str(tmp_path / "check_env.py"))
    monkeypatch.setattr(check_env.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(check_env, "python_version_ok", lambda version: True)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("키를 안 넣었을 때는 네트워크를 호출하면 안 된다")

    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fail_if_called)

    exit_code = check_env.main()

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "❌" in output
    assert "강사가 메일로 보내드린 키" in output


def test_classify_rate_limit_treats_quota_as_pass():
    ok, detail = check_env.classify_rate_limit(
        '{"error":{"message":"Quota exceeded for quota metric requests"}}'
    )
    assert ok is True
    assert "한도" in detail


@pytest.mark.parametrize(
    "message",
    [
        "Your prepayment credits are depleted. Please go to AI Studio",
        "Please enable billing for this project",
    ],
)
def test_classify_rate_limit_treats_billing_as_failure(message):
    """크레딧 소진 429는 기다려도 안 풀린다. 2026-08-12 리허설에서 죽은 키가
    ✅ 다섯 개와 '1분 뒤 다시 실행하세요' 안내를 받고 통과했다."""
    ok, reason = check_env.classify_rate_limit(json.dumps({"error": {"message": message}}))
    assert ok is False
    assert "크레딧" in reason
    assert "기다려도" in reason


def test_verify_model_responds_429_billing_body_is_a_failure(monkeypatch):
    body = b'{"error":{"message":"Your prepayment credits are depleted."}}'

    def _raise(*args, **kwargs):
        raise urllib.error.HTTPError(
            "http://example.com", 429, "error", {}, io.BytesIO(body)
        )

    monkeypatch.setattr(check_env.urllib.request, "urlopen", _raise)
    ok, reason = check_env._verify_model_responds("fake-key")
    assert ok is False
    assert "크레딧" in reason


def test_verify_key_works_defers_429_to_the_model_check(monkeypatch):
    """키 확인(GET)이 429를 받아도 '키가 틀렸다'고 하면 안 된다. 429는 인증을
    통과했다는 증거이고, 종류 판별은 본문을 보는 모델 검사가 한다."""
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_http_error(429))
    ok, reason = check_env._verify_key_works("fake-key")
    assert ok is True
    assert reason == ""


def test_resolve_effective_key_prefers_shell_over_env_file():
    """config.py의 load_dotenv()는 override=False라 쉘 값이 .env를 이긴다.
    진단이 .env만 보면 '고쳐도 반영 안 되는데 ✅'가 된다."""
    key, shadowing = check_env.resolve_effective_key(
        {"GOOGLE_API_KEY": "from-file"}, {"GOOGLE_API_KEY": "from-shell"}
    )
    assert key == "from-shell"
    assert shadowing == "GOOGLE_API_KEY"


def test_resolve_effective_key_uses_env_file_when_shell_is_clean():
    key, shadowing = check_env.resolve_effective_key({"GOOGLE_API_KEY": "from-file"}, {})
    assert key == "from-file"
    assert shadowing is None


def test_resolve_effective_key_google_wins_over_gemini():
    key, _ = check_env.resolve_effective_key(
        {"GOOGLE_API_KEY": "google", "GEMINI_API_KEY": "gemini"}, {}
    )
    assert key == "google"


def test_resolve_effective_key_shell_gemini_shadows_env_file_gemini():
    """2026-08-12에 실제로 걸린 배치다 — .env에는 죽은 키, 쉘에는 다른 키."""
    key, shadowing = check_env.resolve_effective_key(
        {"GEMINI_API_KEY": "dead-key"}, {"GEMINI_API_KEY": "live-key"}
    )
    assert key == "live-key"
    assert shadowing == "GEMINI_API_KEY"


def test_resolve_effective_key_ignores_blank_shell_value():
    key, shadowing = check_env.resolve_effective_key(
        {"GOOGLE_API_KEY": "from-file"}, {"GOOGLE_API_KEY": "   "}
    )
    assert key == "from-file"
    assert shadowing is None


def test_main_warns_when_shell_shadows_env_file(monkeypatch, tmp_path, capsys):
    env_path = tmp_path / ".env"
    env_path.write_text("GOOGLE_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setattr(check_env, "__file__", str(tmp_path / "check_env.py"))
    monkeypatch.setattr(check_env.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(check_env, "python_version_ok", lambda version: True)
    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen_success)
    monkeypatch.setenv("GOOGLE_API_KEY", "from-shell")

    exit_code = check_env.main()

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "덮어쓰고 있습니다" in output
    assert "GOOGLE_API_KEY" in output


def test_main_fails_when_credits_are_depleted(monkeypatch, tmp_path, capsys):
    """진단 전체가 ❌로 끝나야 한다. 이게 통과하면 참가자는 0막에서야 안다."""
    env_path = tmp_path / ".env"
    env_path.write_text("GOOGLE_API_KEY=real-key\n", encoding="utf-8")
    monkeypatch.setattr(check_env, "__file__", str(tmp_path / "check_env.py"))
    monkeypatch.setattr(check_env.shutil, "which", lambda name: "/usr/bin/uv")
    monkeypatch.setattr(check_env, "python_version_ok", lambda version: True)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    def _fake_urlopen(*args, **kwargs):
        target = args[0] if args else kwargs.get("url")
        if isinstance(target, urllib.request.Request):
            raise urllib.error.HTTPError(
                "http://example.com",
                429,
                "error",
                {},
                io.BytesIO(b'{"error":{"message":"Your prepayment credits are depleted."}}'),
            )
        return _FakeHTTPResponse(b'{"ok": true}')

    monkeypatch.setattr(check_env.urllib.request, "urlopen", _fake_urlopen)

    exit_code = check_env.main()

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "❌" in output
    assert "크레딧" in output
    assert "모두 통과했습니다" not in output


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
