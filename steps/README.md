# 막혔을 때

각 단계가 끝난 시점의 완성 코드입니다. 진도를 놓쳤다면 해당 파일을 복사해 이어가세요.

    cp steps/step2_structured.py main.py
    uv run python main.py

| 단계 | 파일 | 여기까지 되면 |
|---|---|---|
| 0막 중 | step0_hello.py | 터미널에 AI 인사말이 한 줄 출력됨 |
| 0막 끝 | step1_freetext.py | 영수증 설명이 자유 텍스트로 터미널에 출력됨 |
| 1막 끝 | step2_structured.py | 영수증이 `Receipt` 객체로 파싱되어 항목별 카테고리와 합계가 출력됨 |
| 2막 끝 | step3_ledger.py | 카테고리별 집계와 가계부 요약 텍스트가 출력됨 |
| 3막 끝 | step4_debate.py | 두 페르소나가 최대 2라운드까지 토론(합의되면 더 일찍 종료) |
| 4막 끝 | step5_judge.py | 판정관까지 실행되어 재무 건강 점수와 처방이 출력됨 (`main.py`와 동일) |
