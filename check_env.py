"""PyCon 2026 튜토리얼 환경 진단.

표준 라이브러리만 사용한다. 참가자는 `uv sync`를 실행하기 전에 이 스크립트부터
돌리므로, 의존성을 설치하기 전에도 실행돼야 하고 구버전 파이썬에서도
SyntaxError 없이 실행돼야 한다(그래야 "당신 파이썬이 낡았습니다"를 알려줄 수
있다). 그래서 `X | Y` 같은 최신 문법을 쓰지 않는다.

실행: python check_env.py
"""

import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple

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


#: 429 응답 본문에 이 단어들이 있으면 분당 한도가 아니라 결제·크레딧 문제다.
#: 전자는 1분 뒤 풀리고 후자는 영원히 안 풀리므로, 같은 안내를 주면 안 된다.
_BILLING_MARKERS = ("credit", "billing", "prepay", "depleted")


def _error_body(error: urllib.error.HTTPError) -> str:
    """HTTPError의 응답 본문을 읽는다. 읽을 수 없으면 빈 문자열."""
    try:
        raw = error.read()
    except Exception:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw or ""


def classify_rate_limit(body: str) -> Tuple[bool, str]:
    """429를 두 종류로 가른다.

    같은 429지만 뜻이 정반대다. 분당 요청 한도는 잠깐 기다리면 풀리므로 통과로
    쳐야 하고(멀쩡한 키에 거짓 경보를 주지 않기 위해), 크레딧 소진·결제 문제는
    기다려도 절대 안 풀리므로 실패로 쳐야 한다. 2026-08-12 리허설에서 크레딧이
    소진된 키가 ✅ 다섯 개를 받고 "1분 뒤 다시 실행하세요"라는 안내까지 얻었다.
    """
    lowered = body.lower()
    for marker in _BILLING_MARKERS:
        if marker in lowered:
            return False, (
                "이 키가 속한 프로젝트의 크레딧이 소진됐습니다(429). 분당 한도와 달리 "
                "기다려도 풀리지 않습니다 — https://aistudio.google.com/apikey 에서 "
                "결제를 확인하거나, 새 프로젝트로 키를 다시 발급받으세요. "
                "(같은 프로젝트에서 키만 새로 만들면 결과가 같습니다.)"
            )
    return True, (
        "지금은 분당 요청 한도에 걸려 있습니다. 키는 정상입니다 — "
        "1분 정도 뒤에 다시 실행하거나 그대로 실습을 시작해도 됩니다."
    )


def resolve_effective_key(
    parsed: Dict[str, str], environ: Dict[str, str]
) -> Tuple[str, Optional[str]]:
    """앱이 **실제로** 쓰게 될 키와, 그게 쉘에서 왔다면 그 변수 이름을 돌려준다.

    config.py의 load_dotenv()는 override=False라 이미 쉘에 export된 값이 .env를
    이긴다. 그런데 이 스크립트는 .env 파일을 직접 파싱하므로, 그대로 두면 진단과
    실행이 서로 다른 키를 보게 된다 — .env를 아무리 고쳐도 반영되지 않는데
    진단은 ✅를 준다. 그래서 config.get_api_key()와 같은 우선순위를 재현한다.
    """
    for name in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
        from_shell = (environ.get(name) or "").strip()
        if from_shell:
            return from_shell, name
        from_file = (parsed.get(name) or "").strip()
        if from_file:
            return from_file, None
    return "", None


def is_placeholder(value: str) -> bool:
    """아직 키를 넣지 않은 상태인지 본다.

    .env.example과 각 문서의 예시는 "여기에_강사가_보낸_키를_붙여넣으세요"처럼
    한글 안내문을 값 자리에 둔다. Google API 키는 전부 ASCII이므로, 값에 한글이
    한 글자라도 있으면 안내문을 그대로 둔 것이다. 특정 문구를 하드코딩하면
    문서를 고칠 때마다 검사가 새는데, 이 규칙은 문구가 바뀌어도 버틴다.
    """
    if not value.strip():
        return True
    return any("가" <= ch <= "힣" for ch in value)


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
        if error.code == 429:
            # 이 검사는 키의 인증 통과 여부만 본다. 429는 인증을 통과했다는
            # 증거이므로 여기서 판단하지 않고 모델 호출 검사로 넘긴다 —
            # 크레딧 소진인지 분당 한도인지는 그쪽이 본문을 보고 가른다.
            return True, ""
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
    - 429는 본문을 읽어 두 종류로 가른다(classify_rate_limit 참고). 분당 요청
      한도라면 키가 인증을 통과했다는 증거이지 실패가 아니다 — 실패로 잡으면
      멀쩡한 키를 가진 참가자에게 거짓 경보를 준다. 반면 크레딧 소진이면
      기다려도 안 풀리므로 실패로 쳐야 한다.
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
            return classify_rate_limit(_error_body(error))
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
    key_present = not is_placeholder(key)

    if not _report(
        ".env 파일에 GOOGLE_API_KEY(또는 GEMINI_API_KEY) 있음",
        key_present,
        "강사가 메일로 보내드린 키를 .env 파일에 붙여넣으세요. "
        "메일이 안 왔으면 강사에게 알려 주세요. (docs/prework/01-api-key.md 참고)",
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
        # .env가 아니라 앱이 실제로 쓰게 될 키를 검사한다. 쉘에 export된 값이
        # .env를 이기는데 여기서 .env만 보면, 진단은 ✅인데 앱은 다른 키로
        # 나가는 상황이 그대로 통과한다.
        key, shadowing_var = resolve_effective_key(parsed, dict(os.environ))
        if shadowing_var is not None:
            print(
                "   ⚠️  쉘 환경변수 {}가 .env를 덮어쓰고 있습니다. 아래 검사와 실제 실행은\n"
                "       .env가 아니라 그 값을 씁니다 — .env를 고쳐도 반영되지 않습니다.\n"
                "       ~/.zshrc 등에서 export 줄을 지우고 터미널을 새로 여세요.".format(
                    shadowing_var
                )
            )
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
