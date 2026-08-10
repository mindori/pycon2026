"""4막 피날레 — 참가자가 만든 모듈을 그대로 쓰는 웹 UI.

실행: uv run streamlit run app.py
"""

import tempfile
from pathlib import Path

import streamlit as st

from budget_battle import client, config, debate, judge, ledger, personas, vision

st.set_page_config(page_title="AI 가계부 배틀", page_icon="🧾")
st.title("🧾 AI 가계부 배틀")
st.caption("영수증을 올리면 AI 둘이 당신의 지갑을 두고 토론합니다.")

uploads = st.file_uploader(
    "영수증 사진", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True
)
rounds = st.slider("토론 라운드", min_value=1, max_value=4, value=2)
st.caption(
    f"라운드를 올려도 호출 상한 {config.MAX_CALLS}턴에 걸리면 거기서 멈춥니다 — "
    "종료 조건이 하나가 아닌 이유입니다."
)

if st.button("배틀 시작", disabled=not uploads):
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for upload in uploads:
            path = Path(tmpdir) / upload.name
            path.write_bytes(upload.getvalue())
            paths.append(path)

        try:
            with st.spinner("영수증을 읽는 중..."):
                receipts = [vision.extract_receipt(path) for path in paths]

            book = ledger.build_ledger(receipts)
            summary = ledger.summarize_for_agents(book)

            st.subheader("내 가계부")
            st.bar_chart({category.value: amount for category, amount in book.totals.items()})
            st.text(summary)

            st.subheader("토론")
            with st.spinner("AI 둘이 싸우는 중..."):
                turns = debate.run_debate(
                    summary, personas.DEFAULT_PERSONAS, max_rounds=rounds
                )
            avatars = {personas.FRUGAL.name: "👵", personas.FLEX.name: "💃"}
            for turn in turns:
                with st.chat_message(turn.speaker, avatar=avatars.get(turn.speaker, "🤖")):
                    st.markdown(f"**{turn.speaker}**\n\n{turn.message}")

            st.subheader("판정")
            with st.spinner("판정관이 심사하는 중..."):
                verdict = judge.judge_debate(summary, turns)
            st.metric("재무 건강 점수", f"{verdict.score}점")
            st.write(verdict.diagnosis)
            for number, prescription in enumerate(verdict.prescriptions, start=1):
                st.write(f"{number}. {prescription}")

        except client.ApiCallFailed as error:
            st.error(
                "AI 호출에 실패했습니다.\n\n"
                "- 네트워크 연결을 확인하세요. 개인 핫스팟을 써 보세요.\n"
                "- 무료 티어 분당 한도일 수 있습니다. 1분 뒤 다시 눌러 보세요.\n"
                "- 계속 실패하면 강사에게 백업 API 키를 요청하세요."
            )
            st.caption(f"원인: {error}")
        except RuntimeError as error:
            st.error(str(error))
