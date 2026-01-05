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
        try:
            # 최신 종가와 전일 대비 변동률 계산
            last_price = data['Close'].iloc[-1]
            
            if len(data) >= 2:
                prev_price = data['Close'].iloc[-2]
                delta = last_price - prev_price
                delta_pct = (delta / prev_price) * 100
            else:
                delta = 0
                delta_pct = 0
                
            # [에러 수정 부분] 모든 변수를 명확하게 float(실수)로 변환
            last_price = float(last_price)
            delta = float(delta)
            delta_pct = float(delta_pct)
            
            col.metric(label=name, value=f"{last_price:,.2f}", delta=f"{delta:,.2f} ({delta_pct:.2f}%)")
        except Exception as e:
            col.error(f"데이터 처리 오류: {e}")
    else:
        col.error(f"{name} 데이터 없음")

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
        df = fdr.StockListing('KRX')
        
        stock_dict = {}
        for index, row in df.iterrows():
            # 데이터프레임 구조에 따라 컬럼명이 다를 수 있어 예외처리 추가
            try:
                name = row.get('Name', row.get('종목명'))
                code = str(row.get('Code', row.get('종목코드'))) # 코드는 문자열로 변환
                market = row.get('Market', row.get('시장구분'))
                
                if not name or not code: 
                    continue
                
                # Yahoo Finance용 접미사 붙이기
                if 'KOSPI' in str(market).upper():
                    yahoo_code = code + '.KS'
                elif 'KOSDAQ' in str(market).upper():
                    yahoo_code = code + '.KQ'
                else:
                    continue 
                
                display_name = f"{name} ({code})"
                stock_dict[display_name] = yahoo_code
            except:
                continue
            
        return stock_dict
    except Exception as e:
        st.error(f"주식 목록을 불러오는 중 오류 발생: {e}")
        return {}

# 주식 목록 로드
krx_stock_dict = get_krx_dict()

# ---------------------------------------------------------
# 6. 관심 종목 비교 분석 (검색 + 직접 입력 통합)
# ---------------------------------------------------------
st.subheader("관심 종목 상세 분석")

col1, col2 = st.columns(2)

# [입력 1] 한국 주식 검색
with col1:
    selected_korea_stocks = st.multiselect(
        "🇰🇷 한국 주식/ETF 검색 (이름으로 검색)",
        options=list(krx_stock_dict.keys()),
        placeholder="예: 삼성전자, KODEX 200"
    )

# [입력 2] 해외 주식/기타 직접 입력
with col2:
    manual_input = st.text_input(
        "🇺🇸 해외 주식 또는 직접 입력 (콤마 구분)", 
        placeholder="예: PLTR, TSLA, AAPL"
    )

# ---------------------------------------------------------
# 7. 차트 그리기 로직
# ---------------------------------------------------------
final_codes = []
final_names = []

# 1) 한국 주식
for item in selected_korea_stocks:
    yahoo_ticker = krx_stock_dict[item]
    final_codes.append(yahoo_ticker)
    final_names.append(item)

# 2) 직접 입력
if manual_input:
    manual_codes = [c.strip() for c in manual_input.split(',') if c.strip()]
    final_codes.extend(manual_codes)
    final_names.extend(manual_codes)

# 3) 통합 차트
if final_codes:
    st.caption(f"총 {len(final_codes)}개의 종목을 분석합니다.")
    chart_cols = st.columns(2)
    
    for i, code in enumerate(final_codes):
        try:
            display_name = final_names[i]
            
            stock = yf.Ticker(code)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                st.warning(f"'{display_name}' ({code}) 데이터가 없습니다.")
                continue

            col_index = i % 2
            with chart_cols[col_index]:
                st.markdown(f"#### {display_name}")
                st.line_chart(df['Close'])
                
        except Exception as e:
            st.error(f"'{code}' 처리 중 에러: {e}")

else:
    st.info("왼쪽에서 한국 주식을 검색하거나, 오른쪽에서 해외 주식 코드를 입력하세요.")
