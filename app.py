import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# -----------------------------------------------------------
# 1. 페이지 및 스타일 설정
# -----------------------------------------------------------
st.set_page_config(page_title="나만의 경제 지표 대시보드", layout="wide")

st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 My Economic & Market Dashboard")
st.markdown("시장의 맥박(Market)과 경제의 흐름(Macro)을 한눈에 파악합니다.")

# -----------------------------------------------------------
# 2. 사이드바 설정
# -----------------------------------------------------------
st.sidebar.header("⚙️ 설정 및 종목 검색")
ticker_input = st.sidebar.text_input("분석할 종목 코드", value="005930.KS")
period_days = st.sidebar.slider("차트 조회 기간 (일)", 30, 1000, 365)
st.sidebar.info("""
**Tip:**
* 코스피: 종목코드.KS (예: 005930.KS)
* 코스닥: 종목코드.KQ (예: 247540.KQ)
* 미국주식: 티커 (예: AAPL, TSLA)
""")

# -----------------------------------------------------------
# 3. 데이터 수집 함수 (오류 해결 버전)
# -----------------------------------------------------------
@st.cache_data
def get_market_data(ticker, days):
    """야후 파이낸스 주가 데이터 수집"""
    end = datetime.now()
    start = end - timedelta(days=days)
    try:
        # progress=False로 설정하여 불필요한 출력 방지
        data = yf.download(ticker, start=start, end=end, progress=False)
        return data
    except:
        return pd.DataFrame()

@st.cache_data
def get_fred_data_direct(series_id):
    """
    [핵심 수정] pandas_datareader 대신 FRED(미 연준) 웹사이트에서 
    직접 CSV를 가져옵니다. 에러가 발생하지 않는 가장 안전한 방식입니다.
    """
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        df = pd.read_csv(url, index_col='DATE', parse_dates=True)
        # 최근 5년치 데이터만 필터링
        start_date = datetime.now() - timedelta(days=365*5)
        return df[df.index > start_date]
    except Exception as e:
        return None

# -----------------------------------------------------------
# 4. [SECTION 1] 시장 핵심 지표 (상단 전광판)
# -----------------------------------------------------------
st.subheader("1️⃣ Market Pulse (시장 핵심 지표)")

indices = {
    "달러 인덱스": "DX-Y.NYB",
    "원/달러 환율": "KRW=X",
    "VIX (공포지수)": "^VIX",
    "S&P 500": "^GSPC",
    "나스닥": "^IXIC",
    "코스피": "^KS11",
    "코스닥": "^KQ11"
}

cols = st.columns(4)
idx = 0

for name, ticker in indices.items():
    data = get_market_data(ticker, 10)
    
    if not data.empty and len(data) >= 2:
        try:
            # 데이터 형식에 따른 안전한 값 추출
            latest = data['Close'].iloc[-1]
            prev = data['Close'].iloc[-2]
            
            # 값이 하나가 아니라 시리즈로 나올 경우를 대비
            if hasattr(latest, 'item'):
                latest = latest.item()
                prev = prev.item()
            elif hasattr(latest, 'values'): # numpy array일 경우
                 latest = latest.item()
                 prev = prev.item()

            change_pct = ((latest - prev) / prev) * 100
            
            with cols[idx % 4]:
                st.metric(label=name, value=f"{latest:,.2f}", delta=f"{change_pct:.2f}%")
        except:
            pass
        idx += 1

st.markdown("---")

# -----------------------------------------------------------
# 5. [SECTION 2] 거시경제 (Macro Trends)
# -----------------------------------------------------------
st.subheader("2️⃣ Macro Trends (거시 경제 흐름)")
st.caption("데이터 출처: FRED (미국 연준 데이터베이스)")

tab1, tab2 = st.tabs(["OECD 경기선행지수", "한국 수출액 추이"])

# FRED 데이터 직접 호출 (오류 없는 방식 사용)
korea_cli = get_fred_data_direct('LOLITOAKRM156S')  # 한국 선행지수
us_cli = get_fred_data_direct('LOLITONOUSM156S')    # 미국 선행지수
korea_exports = get_fred_data_direct('XTEXVA01KRM667S') # 한국 수출액

with tab1:
    if korea_cli is not None and us_cli is not None:
        fig_cli = go.Figure()
        fig_cli.add_trace(go.Scatter(x=korea_cli.index, y=korea_cli.iloc[:,0], name='한국', line=dict(color='blue', width=2)))
        fig_cli.add_trace(go.Scatter(x=us_cli.index, y=us_cli.iloc[:,0], name='미국', line=dict(color='red', width=2)))
        fig_cli.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="기준선(100)")
        fig_cli.update_layout(title="OECD 경기선행지수 (최근 5년)", height=400, hovermode="x unified")
        st.plotly_chart(fig_cli, use_container_width=True)
    else:
        st.warning("데이터를 불러오는 중입니다...")

with tab2:
    if korea_exports is not None:
        fig_exp = go.Figure()
        fig_exp.add_trace(go.Bar(x=korea_exports.index, y=korea_exports.iloc[:,0], name='수출액', marker_color='green'))
        fig_exp.update_layout(title="한국 월별 수출액 (USD)", height=400)
        st.plotly_chart(fig_exp, use_container_width=True)

st.markdown("---")

# -----------------------------------------------------------
# 6. [SECTION 3] 개별 종목 심층 분석
# -----------------------------------------------------------
st.subheader(f"3️⃣ 심층 분석: {ticker_input}")

if ticker_input:
    stock_data = get_market_data(ticker_input, period_days)
    
    if not stock_data.empty:
        try:
            fig_stock = go.Figure()
            
            # 데이터 차원(Dimension) 처리 (yfinance 버전에 따른 호환성)
            o = stock_data['Open'].iloc[:,0] if stock_data['Open'].ndim > 1 else stock_data['Open']
            h = stock_data['High'].iloc[:,0] if stock_data['High'].ndim > 1 else stock_data['High']
            l = stock_data['Low'].iloc[:,0] if stock_data['Low'].ndim > 1 else stock_data['Low']
            c = stock_data['Close'].iloc[:,0] if stock_data['Close'].ndim > 1 else stock_data['Close']
            
            fig_stock.add_trace(go.Candlestick(x=stock_data.index,
                            open=o, high=h, low=l, close=c,
                            name='주가'))
            
            fig_stock.update_layout(title=f"{ticker_input} 주가 흐름", xaxis_rangeslider_visible=False, height=500)
            st.plotly_chart(fig_stock, use_container_width=True)
            
            with st.expander("데이터 원본 보기"):
                st.dataframe(stock_data.sort_index(ascending=False))
        except Exception as e:
            st.error(f"차트를 그리는 중 오류가 발생했습니다: {e}")
    else:
        st.error(f"'{ticker_input}' 데이터를 찾을 수 없습니다. 티커를 확인해주세요.")
