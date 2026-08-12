"""PyCon 2026 튜토리얼 환경 진단.

표준 라이브러리만 사용한다. 참가자는 `uv sync`를 실행하기 전에 이 스크립트부터
돌리므로, 의존성을 설치하기 전에도 실행돼야 하고 구버전 파이썬에서도
SyntaxError 없이 실행돼야 한다(그래야 "당신 파이썬이 낡았습니다"를 알려줄 수
있다). 그래서 `X | Y` 같은 최신 문법을 쓰지 않는다.

실행: python check_env.py
"""

import json
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Tuple

MIN_PYTHON = (3, 11)

# budget_battle/config.py의 MODEL_ID와 반드시 같은 값이어야 한다. check_env.py는
# 의존성 설치 전에 실행되므로 config.py를 import할 수 없어(python-dotenv 필요)
# 문자열로 중복 정의한다. 두 값이 어긋나면 tests/test_check_env.py가 잡는다.
MODEL_ID = "gemini-3.6-flash"

MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models?key={key}"
GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)


def python_version_ok(version: Tuple[int, int]) -> bool:
    return version >= MIN_PYTHON


def parse_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    parsed = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        parsed[key.strip()] = value.strip().strip("\"'")
    return parsed


def _report(label: str, ok: bool, fix_hint: str) -> bool:
    print("{} {}".format("✅" if ok else "❌", label))
    if not ok:
        print("   → {}".format(fix_hint))
    return ok


def _verify_key_works(key: str) -> Tuple[bool, str]:
    """키가 인증을 통과하는지만 본다. 모델이 실제로 호출되는지는 별도로 본다."""
    try:
        with urllib.request.urlopen(MODELS_URL.format(key=key), timeout=10) as response:
            json.load(response)
        return True, ""
    except urllib.error.HTTPError as error:
        return False, "서버가 {}를 반환했습니다. 키가 올바른지 확인하세요.".format(error.code)
    except urllib.error.URLError as error:
        return False, "네트워크에 연결할 수 없습니다: {}. 인터넷 연결을 확인하세요.".format(error.reason)
    except Exception as error:
        return False, "예상치 못한 오류: {}".format(error)


def _verify_model_responds(key: str) -> Tuple[bool, str]:
    """키 유효성만으로는 부족하다. 7/25에 gemini-2.5-flash가 키는 멀쩡한 채로
    신규 사용자에게 404를 낸 적이 있다 — 모델 목록에는 여전히 나와 있었다.
    실제로 MODEL_ID에 generateContent를 한 번 때려야 이런 사고를 미리 잡는다.

    상태 코드에 따라 의미가 다르므로 나눠서 처리한다.
    - 429(분당 요청 한도 초과)는 키가 인증을 통과했다는 증거이지 실패가
      아니다. client.py는 이 순간을 재시도로 넘기지만 check_env.py는 한 번만
      때리므로, 429를 실패로 잡으면 멀쩡한 키를 가진 참가자에게 "키가
      안 됩니다"라는 거짓 경보를 준다. 통과로 치되 안내는 남긴다.
    - 404는 모델 자체가 사라진 것 — 이 검사가 원래 잡으려던 실패 상황이다
      (7/25에 gemini-2.5-flash가 이렇게 죽었다). 그대로 실패 처리한다.
    - 401/403은 키가 거부된 것이므로 실패 처리한다.
    """
    url = GENERATE_URL.format(model=MODEL_ID, key=key)
    payload = json.dumps({"contents": [{"parts": [{"text": "ping"}]}]}).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            json.load(response)
        return True, ""
    except urllib.error.HTTPError as error:
        if error.code == 429:
            return True, (
                "지금은 분당 요청 한도에 걸려 있습니다. 키는 정상입니다 — "
                "1분 정도 뒤에 다시 실행하거나 그대로 실습을 시작해도 됩니다."
            )
        if error.code == 404:
            return False, (
                "모델 '{}'을(를) 찾을 수 없습니다(404). 배포된 저장소가 최신인지 "
                "확인하고, 계속되면 강사에게 문의하세요.".format(MODEL_ID)
            )
        if error.code in (401, 403):
            return False, "키가 거부되었습니다({}). 키가 올바른지 다시 확인하세요.".format(
                error.code
            )
        return False, "서버가 {}를 반환했습니다. 잠시 후 다시 시도하거나 강사에게 문의하세요.".format(
            error.code
        )
    except urllib.error.URLError as error:
        return False, "네트워크에 연결할 수 없습니다: {}. 인터넷 연결을 확인하세요.".format(error.reason)
    except Exception as error:
        return False, "예상치 못한 오류: {}".format(error)


def main() -> int:
    print("=" * 46)
    print(" PyCon 2026 AI 가계부 배틀 — 환경 진단")
    print("=" * 46)

    results = [
        _report(
            "파이썬 {}.{}".format(sys.version_info[0], sys.version_info[1]),
            python_version_ok((sys.version_info[0], sys.version_info[1])),
            "파이썬 {}.{} 이상을 설치하세요: https://www.python.org/downloads/".format(
                MIN_PYTHON[0], MIN_PYTHON[1]
            ),
        ),
        _report(
            "uv 설치됨",
            shutil.which("uv") is not None,
            "docs/prework/02-install.md의 uv 설치 명령을 실행하세요.",
        ),
    ]

    env_path = Path(__file__).resolve().parent / ".env"
    parsed = parse_env_file(env_path)
    key = parsed.get("GOOGLE_API_KEY") or parsed.get("GEMINI_API_KEY") or ""
    key_present = bool(key) and "여기에" not in key

    if not _report(
        ".env 파일에 GOOGLE_API_KEY(또는 GEMINI_API_KEY) 있음",
        key_present,
        ".env.example을 .env로 복사하고 발급받은 키를 붙여넣으세요. "
        "(docs/prework/01-api-key.md 참고)",
    ):
        results.append(False)
        results.append(
            _report("API 키가 실제로 동작함", False, "위 항목을 먼저 해결한 뒤 다시 실행하세요.")
        )
        results.append(
            _report(
                "모델({})이 응답함".format(MODEL_ID),
                False,
                "위 항목을 먼저 해결한 뒤 다시 실행하세요.",
            )
        )
    else:
        key_ok, key_reason = _verify_key_works(key)
        results.append(_report("API 키가 실제로 동작함", key_ok, key_reason))
        if key_ok:
            model_ok, model_detail = _verify_model_responds(key)
            if model_ok and model_detail:
                # 429는 통과지만 참가자에게 남길 안내가 있는 경우다. 실패용
                # fix_hint 줄(❌일 때만 출력)에 태우지 않고 라벨에 붙여
                # ✅ 옆에 그대로 보이게 한다.
                label = "모델({}) 확인됨 — {}".format(MODEL_ID, model_detail)
                results.append(_report(label, True, ""))
            else:
                results.append(
                    _report("모델({})이 응답함".format(MODEL_ID), model_ok, model_detail)
                )
        else:
            results.append(
                _report(
                    "모델({})이 응답함".format(MODEL_ID),
                    False,
                    "위 항목을 먼저 해결한 뒤 다시 실행하세요.",
                )
            )

    print("-" * 46)
    if all(results):
        print("모두 통과했습니다. 당일에 뵙겠습니다!")
        return 0
    print("❌ 항목을 해결한 뒤 다시 실행해 주세요.")
    print("   해결이 어려우면 8/16(일) 저녁 온라인 사전 점검에 참여해 주세요.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
