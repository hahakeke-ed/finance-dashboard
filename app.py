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

# [복구됨] 외부 데이터 링크 버튼
col_link1, col_link2 = st.columns(2)
with col_link1:
    st.link_button("🌍 OECD 경기선행지수 보러가기", "https://data.oecd.org/leadind/composite-leading-indicators-cli.htm")
with col_link2:
    st.link_button("🇰🇷 한국 수출입 무역통계 보러가기", "https://unipass.customs.go.kr/ets/")

st.markdown("---")

# ---------------------------------------------------------
# 2. 사이드바 (기간 설정 등)
# ---------------------------------------------------------
with st.sidebar:
    st.header("설정")
    start_date = st.date_input("시작일", datetime.now() - timedelta(days=365))
    end_date = st.date_input("종료일", datetime.now())
    st.markdown("---")
    st.info("💡 팁: 주요 지표는 자동으로 로드되며, 아래에서 개별 종목을 검색할 수 있습니다.")

# ---------------------------------------------------------
# 3. 주요 시장 지표 (3열 배치 + 차트 포함 복구)
# ---------------------------------------------------------
st.subheader("📊 주요 시장 지표")

@st.cache_data
def get_stock_data(ticker, start, end):
    try:
        data = yf.download(ticker, start=start, end=end, progress=False)
        return data
    except Exception as e:
        return None

# [복구 및 확장] 감시할 주요 지표 리스트 (나스닥, 금, 국채 추가)
tickers = {
    'USD/KRW (환율)': 'KRW=X', 
    'KOSPI (코스피)': '^KS11', 
    'S&P 500 (선물)': 'ES=F',
    'NASDAQ (선물)': 'NQ=F',
    'Gold (금 선물)': 'GC=F',
    'US 10Y Bond (미국채 10년)': '^TNX'
}

# 3개의 컬럼 생성 (한 줄에 3개씩 배치)
cols = st.columns(3)

# 딕셔너리 아이템을 리스트로 변환하여 인덱스로 접근
ticker_items = list(tickers.items())

for i, (name, ticker) in enumerate(ticker_items):
    # i를 3으로 나눈 나머지를 이용해 컬럼 지정 (0, 1, 2 반복)
    col = cols[i % 3]
    
    data = get_stock_data(ticker, start_date, end_date)
    
    with col:
        if data is not None and not data.empty:
            # Metric 계산
            last_price = data['Close'].iloc[-1]
            if len(data) >= 2:
                prev_price = data['Close'].iloc[-2]
                delta = last_price - prev_price
                delta_pct = (delta / prev_price) * 100
            else:
                delta = 0
                delta_pct = 0
            
            # 에러 방지용 float 변환
            last_price = float(last_price)
            delta = float(delta)
            delta_pct = float(delta_pct)
            
            # 숫자 표시
            st.metric(label=name, value=f"{last_price:,.2f}", delta=f"{delta:,.2f} ({delta_pct:.2f}%)")
            
            # [복구됨] 작은 차트 표시
            st.line_chart(data['Close'], height=150)
        else:
            st.error(f"{name} 데이터 오류")

st.markdown("---")

# ---------------------------------------------------------
# 4. [복구됨] 한국 주식 목록 가져오기 (FDR)
# ---------------------------------------------------------
@st.cache_data
def get_krx_dict():
    try:
        df = fdr.StockListing('KRX')
        stock_dict = {}
        for index, row in df.iterrows():
            try:
                name = row.get('Name', row.get('종목명'))
                code = str(row.get('Code', row.get('종목코드')))
                market = row.get('Market', row.get('시장구분'))
                
                if not name or not code: continue
                
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
        return {}

krx_stock_dict = get_krx_dict()

# ---------------------------------------------------------
# 5. 관심 종목 비교 분석 (복구됨: 검색 + 입력)
# ---------------------------------------------------------
st.subheader("🔎 관심 종목 상세 분석")
st.caption("한국 주식은 검색하고, 미국 주식은 코드를 직접 입력하여 비교할 수 있습니다.")

input_col1, input_col2 = st.columns(2)

with input_col1:
    selected_korea_stocks = st.multiselect(
        "🇰🇷 한국 주식 검색",
        options=list(krx_stock_dict.keys()),
        placeholder="종목명 검색 (예: 삼성전자)"
    )

with input_col2:
    manual_input = st.text_input(
        "🇺🇸 해외 종목 코드 직접 입력", 
        placeholder="콤마(,)로 구분 (예: PLTR, TSLA, NVDA)"
    )

# 종목 리스트 합치기
final_codes = []
final_names = []

# 한국 주식 처리
for item in selected_korea_stocks:
    final_codes.append(krx_stock_dict[item])
    final_names.append(item)

# 직접 입력 처리
if manual_input:
    manual_codes = [c.strip() for c in manual_input.split(',') if c.strip()]
    final_codes.extend(manual_codes)
    final_names.extend(manual_codes)

# 결과 차트 그리기
if final_codes:
    st.write(f"총 {len(final_codes)}개의 종목을 분석합니다.")
    # 2열로 차트 배치
    chart_cols = st.columns(2)
    
    for i, code in enumerate(final_codes):
        try:
            display_name = final_names[i]
            stock = yf.Ticker(code)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                st.warning(f"'{display_name}' 데이터가 없습니다.")
                continue

            col_idx = i % 2
            with chart_cols[col_idx]:
                st.markdown(f"#### {display_name}")
                st.line_chart(df['Close'])
                
        except Exception as e:
            st.error(f"'{code}' 처리 중 에러: {e}")
else:
    st.info("종목을 선택하거나 입력하면 차트가 표시됩니다.")
