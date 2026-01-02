import streamlit as st
import yfinance as yf
import pandas as pd

# ... (기존 설정 코드는 유지) ...

st.subheader("종목 비교 분석")

# [수정 1] 입력창 4개를 가로로 배치 (st.columns 사용)
col1, col2, col3, col4 = st.columns(4)

with col1:
    code1 = st.text_input("종목 1", placeholder="예: 005930.KS")
with col2:
    code2 = st.text_input("종목 2", placeholder="예: PLTR")
with col3:
    code3 = st.text_input("종목 3")
with col4:
    code4 = st.text_input("종목 4")

# 입력된 코드들을 리스트로 정리 (빈 칸 제외)
raw_codes = [code1, code2, code3, code4]
codes = [c.strip() for c in raw_codes if c.strip()]

# [수정 2] 입력된 코드가 있을 경우 반복문을 돌며 차트 생성
if codes:
    # 차트를 2열로 예쁘게 배치하기 위해 컨테이너 생성
    chart_cols = st.columns(2) 
    
    for i, code in enumerate(codes):
        try:
            # 데이터 가져오기
            stock = yf.Ticker(code)
            df = stock.history(period='1y') # 기간은 필요에 따라 조절 (1mo, 3mo, 1y 등)
            
            if df.empty:
                st.warning(f"'{code}'에 대한 데이터가 없습니다.")
                continue

            # [수정 3] 종목 이름 가져오기
            # yfinance 정보에서 긴 이름(longName)을 가져오고, 없으면 shortName, 그것도 없으면 코드를 씀
            stock_name = stock.info.get('longName', stock.info.get('shortName', code))
            
            # (옵션) 한국 주식(.KS, .KQ)의 경우 yfinance가 영어 이름을 줄 수 있습니다.
            # 이 경우 별도의 매핑이 없으면 영어로 나옵니다. 
            
            # 차트 그리기 위치 지정 (왼쪽, 오른쪽 번갈아가며 배치)
            col_index = i % 2 
            with chart_cols[col_index]:
                st.markdown(f"### {stock_name} ({code})") # 제목: 이름 + 코드
                st.line_chart(df['Close'])
                
                # 만약 2개가 꽉 차면 다음 줄을 위해 새로운 컬럼 생성 (선택 사항, Streamlit은 자동 줄바꿈 됨)
                
        except Exception as e:
            st.error(f"'{code}' 처리 중 오류 발생: {e}")

else:
    st.info("종목 코드를 입력해주세요.")
