import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. 페이지 설정 및 제목
# ---------------------------------------------------------
st.set_page_config(page_title="나만의 경제 대시보드", layout="wide")

st.title("📈 나만의 경제지표 대시보드")
st.markdown("---")

# ---------------------------------------------------------
# 2. 사이드바 (기간 설정 등)
# ---------------------------------------------------------
with st.sidebar:
    st.header("설정")
    # 기본적으로 최근 1년 데이터를 보여줌
    start_date = st.date_input("시작일", datetime.now() - timedelta(days=365))
    end_date = st.date_input("종료일", datetime.now())

# ---------------------------------------------------------
# 3. 주요 지표 요약 (환율, KOSPI, S&P500 선물)
# ---------------------------------------------------------
st.subheader("주요 시장 지표")

# 데이터 가져오기 함수 (캐싱을 통해 속도 향상)
@st.cache_data
def get_stock_data(ticker, start, end):
    try:
        data = yf.download(ticker, start=start, end=end, progress=False)
        return data
    except Exception as e:
        return None

# 환율(KRW=X), 코스피(^KS11), S&P500 선물(ES=F)
tickers = {'USD/KRW': 'KRW=X', 'KOSPI': '^KS11', 'S&P 500 Futures': 'ES=F'}
cols = st.columns(len(tickers))

for col, (name, ticker) in zip(cols, tickers.items()):
    data = get_stock_data(ticker, start_date, end_date)
    if data is not None and not data.empty:
        # 최신 종가와 전일 대비 변동률 계산
        last_price = data['Close'].iloc[-1]
        
        # 데이터가 2개 이상일 때만 전일비 계산
        if len(data) >= 2:
            prev_price = data['Close'].iloc[-2]
            delta = last_price - prev_price
            delta_pct = (delta / prev_price) * 100
        else:
            delta = 0
            delta_pct = 0
            
        # float 변환 (시리즈 형태일 경우 방지)
        last_price = float(last_price)
        delta = float(delta)
        
        col.metric(label=name, value=f"{last_price:,.2f}", delta=f"{delta:,.2f} ({delta_pct:.2f}%)")
    else:
        col.error(f"{name} 데이터 오류")

st.markdown("---")

# ---------------------------------------------------------
# 4. S&P 500 선물 차트 (해결된 부분)
# ---------------------------------------------------------
st.subheader("S&P 500 선물 (Futures) 차트")
sp_futures_data = get_stock_data('ES=F', start_date, end_date)

if sp_futures_data is not None and not sp_futures_data.empty:
    st.line_chart(sp_futures_data['Close'])
else:
    st.write("S&P 500 선물 데이터를 불러올 수 없습니다.")

st.markdown("---")

# ---------------------------------------------------------
# 5. 관심 종목 비교 분석 (요청하신 4개 입력창 수정 부분)
# ---------------------------------------------------------
st.subheader("관심 종목 상세 분석")
st.caption("비교하고 싶은 종목 코드를 입력하세요. (입력한 개수만큼 차트가 생성됩니다)")

# [수정됨] 입력창 4개를 가로로 배치
input_cols = st.columns(4)

with input_cols[0]:
    code1 = st.text_input("종목 1", placeholder="예: 005930.KS")
with input_cols[1]:
    code2 = st.text_input("종목 2", placeholder="예: PLTR")
with input_cols[2]:
    code3 = st.text_input("종목 3")
with input_cols[3]:
    code4 = st.text_input("종목 4")

# 입력된 코드 리스트 정리
raw_codes = [code1, code2, code3, code4]
codes = [c.strip() for c in raw_codes if c.strip()]

if codes:
    # 차트를 2열로 배치하기 위한 컨테이너
    chart_cols = st.columns(2)
    
    for i, code in enumerate(codes):
        try:
            # yfinance로 데이터 로드
            stock = yf.Ticker(code)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                # 데이터가 없으면 경고 메시지 출력 후 다음 루프로
                st.warning(f"'{code}'에 대한 데이터가 없습니다. 코드를 확인해주세요.")
                continue

            # 종목 이름 가져오기 시도
            # 한국 주식은 영어 이름으로 나올 수 있음 (yfinance 한계)
            info = stock.info
            stock_name = info.get('longName', info.get('shortName', code))
            
            # 차트 그리기 (짝수 인덱스는 왼쪽, 홀수 인덱스는 오른쪽)
            col_index = i % 2
            with chart_cols[col_index]:
                st.markdown(f"#### {stock_name}")
                st.code(code) # 코드를 명확히 보여줌
                st.line_chart(df['Close'])
                
        except Exception as e:
            st.error(f"'{code}' 처리 중 에러 발생: {e}")

else:
    st.info("위 입력창에 종목 코드를 입력하면 차트가 표시됩니다.")
