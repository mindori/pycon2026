from pathlib import Path

import pytest

import main
from budget_battle import client, config


def test_explicit_paths_win_over_the_receipts_dir(tmp_path):
    given = [tmp_path / "a.jpg"]
    assert main._receipt_paths(given) == given


def test_receipts_dir_is_globbed_when_no_paths_given(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RECEIPTS_DIR", tmp_path)
    (tmp_path / "sample_02.jpg").write_bytes(b"x")
    (tmp_path / "sample_01.png").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")

    found = main._receipt_paths([])

    assert [path.name for path in found] == ["sample_01.png", "sample_02.jpg"]


def test_uppercase_extensions_are_found(monkeypatch, tmp_path):
    # 폰으로 찍은 사진은 IMG_1234.JPG 인 경우가 흔하다. glob은 대소문자를
    # 구분하므로, 이걸 놓치면 파일이 눈앞에 보이는데 "없습니다"가 뜬다.
    monkeypatch.setattr(config, "RECEIPTS_DIR", tmp_path)
    (tmp_path / "IMG_1234.JPG").write_bytes(b"x")
    (tmp_path / "photo.Jpeg").write_bytes(b"x")

    found = main._receipt_paths([])

    assert [path.name for path in found] == ["IMG_1234.JPG", "photo.Jpeg"]


def test_rounds_below_one_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RECEIPTS_DIR", tmp_path)
    (tmp_path / "sample_01.jpg").write_bytes(b"x")
    monkeypatch.setattr("sys.argv", ["main.py", "--rounds", "0"])

    with pytest.raises(SystemExit) as exit_info:
        main.main()

    assert "1 이상" in str(exit_info.value)


def test_empty_receipts_dir_exits_with_guidance(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RECEIPTS_DIR", tmp_path)
    with pytest.raises(SystemExit) as exit_info:
        main._receipt_paths([])
    assert "영수증 이미지가 없습니다" in str(exit_info.value)


def test_api_failure_message_names_the_three_remedies():
    message = main._API_FAILURE_MESSAGE.format(error="429")
    assert "핫스팟" in message
    assert "1분" in message
    assert "백업" in message
