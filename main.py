"""AI 가계부 배틀 CLI."""

import argparse
from pathlib import Path

from budget_battle import client, config, debate, judge, ledger, personas, vision

_API_FAILURE_MESSAGE = """
AI 호출에 실패했습니다.

- 네트워크 연결을 확인하세요. 현장 와이파이가 느리면 개인 핫스팟을 써 보세요.
- 무료 티어 분당 요청 한도에 걸렸을 수 있습니다. 1분 정도 기다렸다가 다시 실행해 보세요.
- 계속 실패하면 강사에게 백업 API 키를 요청하세요.

(원인: {error})
"""


def _receipt_paths(given: list[Path]) -> list[Path]:
    if given:
        return given
    # glob 패턴 대신 suffix를 소문자로 비교한다. macOS·리눅스의 glob은
    # 대소문자를 구분해서, 폰으로 찍은 IMG_1234.JPG 가 조용히 누락된다.
    found = sorted(
        path
        for path in config.RECEIPTS_DIR.glob("*")
        if path.suffix.lower() in vision.SUPPORTED_SUFFIXES
    )
    if not found:
        raise SystemExit(
            f"영수증 이미지가 없습니다.\n"
            f"{config.RECEIPTS_DIR} 폴더에 사진을 넣거나, 경로를 인자로 넘기세요.\n"
            f"예: uv run python main.py receipts/sample_01.jpg"
        )
    return found


def run_battle(paths: list[Path], rounds: int) -> None:
    """영수증 → 가계부 → 토론 → 판정까지 한 번에 돌린다."""
    print(f"영수증 {len(paths)}장을 읽는 중...")
    receipts = [vision.extract_receipt(path) for path in paths]
    for receipt in receipts:
        # total은 LLM이 아니라 파이썬이 계산한 값이다. 1막에서 짚은 원칙이
        # 완성된 앱에서도 눈에 보이게 여기서 한 번 출력한다.
        store = receipt.store or "매장 미상"
        when = receipt.purchased_at or "날짜 미상"
        print(f"  {store} / {when} / {receipt.total:,}원")

    book = ledger.build_ledger(receipts)
    summary = ledger.summarize_for_agents(book)
    print(f"\n{'=' * 40}\n[내 가계부]\n{summary}")

    print(f"\n{'=' * 40}\n[토론 시작]")
    turns = debate.run_debate(summary, personas.DEFAULT_PERSONAS, max_rounds=rounds)
    for turn in turns:
        print(f"\n<{turn.speaker}>\n{turn.message}")

    verdict = judge.judge_debate(summary, turns)
    print(f"\n{'=' * 40}\n[판정]")
    print(f"재무 건강 점수: {verdict.score}점")
    print(f"{verdict.diagnosis}\n")
    for number, prescription in enumerate(verdict.prescriptions, start=1):
        print(f"  {number}. {prescription}")


def main() -> None:
    parser = argparse.ArgumentParser(description="영수증을 던지면 AI 둘이 토론합니다.")
    parser.add_argument("images", nargs="*", type=Path, help="영수증 이미지 경로")
    parser.add_argument("--rounds", type=int, default=config.MAX_ROUNDS, help="토론 라운드 수")
    args = parser.parse_args()

    if args.rounds < 1:
        raise SystemExit("--rounds 는 1 이상이어야 합니다.")

    paths = _receipt_paths(args.images)

    try:
        run_battle(paths, args.rounds)
    except client.ApiCallFailed as error:
        raise SystemExit(_API_FAILURE_MESSAGE.format(error=error))
    except RuntimeError as error:
        # config.get_api_key()의 설정 오류. 이미 다음 행동까지 적힌 안내를
        # 담고 있으므로 트레이스백 15줄에 묻지 말고 그대로 보여준다.
        raise SystemExit(str(error))


if __name__ == "__main__":
    main()
