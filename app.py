import streamlit as st
import yfinance as yf
import pandas as pd
import FinanceDataReader as fdr
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
    start_date = st.date_input("시작일", datetime.now() - timedelta(days=365))
    end_date = st.date_input("종료일", datetime.now())
    st.markdown("---")
    st.info("💡 팁: 한국 주식은 검색 기능을, 미국 주식은 코드 입력을 이용하세요.")

# ---------------------------------------------------------
# 3. 주요 지표 요약 (환율, KOSPI, S&P500 선물)
# ---------------------------------------------------------
st.subheader("주요 시장 지표")

@st.cache_data
def get_stock_data(ticker, start, end):
    try:
        data = yf.download(ticker, start=start, end=end, progress=False)
        return data
    except Exception as e:
        return None

tickers = {'USD/KRW': 'KRW=X', 'KOSPI': '^KS11', 'S&P 500 Futures': 'ES=F'}
cols = st.columns(len(tickers))

for col, (name, ticker) in zip(cols, tickers.items()):
    data = get_stock_data(ticker, start_date, end_date)
    if data is not None and not data.empty:
        last_price = data['Close'].iloc[-1]
        if len(data) >= 2:
            prev_price = data['Close'].iloc[-2]
            delta = last_price - prev_price
            delta_pct = (delta / prev_price) * 100
        else:
            delta = 0; delta_pct = 0
            
        col.metric(label=name, value=f"{float(last_price):,.2f}", delta=f"{float(delta):,.2f} ({delta_pct:.2f}%)")
    else:
        col.error(f"{name} 데이터 오류")

st.markdown("---")

# ---------------------------------------------------------
# 4. S&P 500 선물 차트
# ---------------------------------------------------------
st.subheader("S&P 500 선물 (Futures) 차트")
sp_futures_data = get_stock_data('ES=F', start_date, end_date)

if sp_futures_data is not None and not sp_futures_data.empty:
    st.line_chart(sp_futures_data['Close'])
else:
    st.write("S&P 500 선물 데이터를 불러올 수 없습니다.")

st.markdown("---")

# ---------------------------------------------------------
# 5. [핵심 기능] 한국 주식 목록 가져오기 (FDR 사용)
# ---------------------------------------------------------
@st.cache_data
def get_krx_dict():
    """
    FinanceDataReader를 사용하여 KRX 전체 상장 종목(ETF 포함)을 가져오고,
    '종목명 (코드)' : 'YahooTicker' 형태의 딕셔너리로 반환합니다.
    """
    try:
        # KRX 전체 리스트 다운로드 (시간이 조금 걸리므로 캐싱 필수)
        df = fdr.StockListing('KRX')
        
        stock_dict = {}
        for index, row in df.iterrows():
            name = row['Name']
            code = str(row['Code'])
            market = row['Market']
            
            # Yahoo Finance용 접미사 붙이기
            # 코스피 -> .KS, 코스닥 -> .KQ
            if 'KOSPI' in market:
                yahoo_code = code + '.KS'
            elif 'KOSDAQ' in market:
                yahoo_code = code + '.KQ'
            else:
                continue # 코넥스 등 기타 시장은 제외 (필요 시 추가 가능)
            
            # 검색창에 보일 이름: "삼성전자 (005930)"
            display_name = f"{name} ({code})"
            stock_dict[display_name] = yahoo_code
            
        return stock_dict
    except Exception as e:
        st.error(f"주식 목록을 불러오는 중 오류 발생: {e}")
        return {}

# 주식 목록 로드 (앱 실행 시 1회 실행됨)
krx_stock_dict = get_krx_dict()

# ---------------------------------------------------------
# 6. 관심 종목 비교 분석 (검색 + 직접 입력 통합)
# ---------------------------------------------------------
st.subheader("관심 종목 상세 분석")

col1, col2 = st.columns(2)

# [입력 1] 한국 주식 검색 (Multiselect)
with col1:
    selected_korea_stocks = st.multiselect(
        "🇰🇷 한국 주식/ETF 검색 (이름으로 검색)",
        options=list(krx_stock_dict.keys()),
        placeholder="예: 삼성전자, KODEX 200"
    )

# [입력 2] 해외 주식/기타 직접 입력 (Text Input)
with col2:
    manual_input = st.text_input(
        "🇺🇸 해외 주식 또는 직접 입력 (콤마 구분)", 
        placeholder="예: PLTR, TSLA, AAPL"
    )

# ---------------------------------------------------------
# 7. 차트 그리기 로직
# ---------------------------------------------------------
# 1) 한국 주식 선택된 것들의 Yahoo 코드 찾기
final_codes = []
final_names = []

for item in selected_korea_stocks:
    yahoo_ticker = krx_stock_dict[item] # 딕셔너리에서 코드 변환
    final_codes.append(yahoo_ticker)
    final_names.append(item) # 차트 제목용 이름

# 2) 직접 입력된 코드들 추가
if manual_input:
    manual_codes = [c.strip() for c in manual_input.split(',') if c.strip()]
    final_codes.extend(manual_codes)
    final_names.extend(manual_codes) # 직접 입력은 이름을 코드로 대체

# 3) 통합된 리스트로 차트 그리기
if final_codes:
    st.caption(f"총 {len(final_codes)}개의 종목을 분석합니다.")
    chart_cols = st.columns(2)
    
    for i, code in enumerate(final_codes):
        try:
            # 이름 설정 (한국 주식은 한글 이름, 직접 입력은 코드 그대로)
            display_name = final_names[i]
            
            stock = yf.Ticker(code)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                st.warning(f"'{display_name}' ({code}) 데이터가 없습니다.")
                continue

            # 차트 배치
            col_index = i % 2
            with chart_cols[col_index]:
                st.markdown(f"#### {display_name}")
                st.line_chart(df['Close'])
                
        except Exception as e:
            st.error(f"'{code}' 처리 중 에러: {e}")

else:
    st.info("왼쪽에서 한국 주식을 검색하거나, 오른쪽에서 해외 주식 코드를 입력하세요.")
