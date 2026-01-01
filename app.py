import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_datareader.data as web
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 페이지 설정 (반드시 최상단)
st.set_page_config(page_title="나만의 경제 지표 대시보드", layout="wide")

# 스타일 꾸미기
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

# ==========================================
# 1. 사이드바 (설정)
# ==========================================
st.sidebar.header("⚙️ 설정 및 종목 검색")
ticker_input = st.sidebar.text_input("분석할 종목 코드 (예: 005930.KS, TSLA)", value="005930.KS")
period_days = st.sidebar.slider("차트 조회 기간 (일)", 30, 1000, 365)

st.sidebar.info("""
**Tip:**
* 코스피: 종목코드.KS
* 코스닥: 종목코드.KQ
* 미국주식: 티커 (AAPL, TSLA 등)
""")

# ==========================================
# 2. 데이터 수집 함수들
# ==========================================
@st.cache_data
def get_market_data(ticker, days):
    end = datetime.now()
    start = end - timedelta(days=days)
    return yf.download(ticker, start=start, end=end)

@st.cache_data
def get_macro_data():
    # FRED에서 데이터 가져오기 (오류 방지를 위한 예외처리)
    try:
        start = datetime(2018, 1, 1)
        end = datetime.now()
        
        # FRED 코드 매핑
        # OECD 선행지수 (한국, 미국-선진국대표, 중국-이머징대표) 
        # *FRED 코드는 변경될 수 있어 대표적인 G7, 한국 코드를 사용
        korea_cli = web.DataReader('LOLITOAKRM156S', 'fred', start, end) # OECD CLI: Korea
        us_cli = web.DataReader('LOLITONOUSM156S', 'fred', start, end)   # OECD CLI: US
        
        # 한국 수출 데이터 (Total Exports, USD)
        korea_exports = web.DataReader('XTEXVA01KRM667S', 'fred', start, end)
        
        return korea_cli, us_cli, korea_exports
    except Exception as e:
        return None, None, None

# ==========================================
# 3. [SECTION 1] 시장 핵심 지표 (Scoreboard)
# ==========================================
st.subheader("1️⃣ Market Pulse (시장 핵심 지표)")

# 표시할 지표 정의 (이름: 야후티커)
indices = {
    "달러 인덱스": "DX-Y.NYB",
    "원/달러 환율": "KRW=X",
    "VIX (공포지수)": "^VIX",
    "S&P 500": "^GSPC",
    "나스닥": "^IXIC",
    "코스피": "^KS11",
    "코스닥": "^KQ11"
}

# 4열로 배치 (화면 크기에 따라 자동 줄바꿈 됨)
cols = st.columns(4)
idx = 0

for name, ticker in indices.items():
    data = get_market_data(ticker, 10) # 최근 10일치만 가져와서 등락 계산
    
    if not data.empty:
        # 최신가 및 변동률 계산
        latest = data['Close'].iloc[-1].item()
        prev = data['Close'].iloc[-2].item()
        change_pct = ((latest - prev) / prev) * 100
        
        # 색상 설정 (상승: 빨강, 하락: 파랑 - 한국식)
        color = "red" if change_pct >= 0 else "blue"
        
        with cols[idx % 4]:
            st.metric(label=name, value=f"{latest:,.2f}", delta=f"{change_pct:.2f}%")
        idx += 1

st.markdown("---")

# ==========================================
# 4. [SECTION 2] 거시경제 (Macro Trends)
# ==========================================
st.subheader("2️⃣ Macro Trends (거시 경제 흐름)")
st.caption("OECD 선행지수와 수출 데이터는 월별로 업데이트됩니다. (Data Source: FRED)")

tab1, tab2 = st.tabs(["OECD 경기선행지수 (Trend)", "한국 수출액 추이"])

k_cli, u_cli, k_exp = get_macro_data()

with tab1:
    if k_cli is not None:
        fig_cli = go.Figure()
        # 정규화된 값이므로 100 기준
        fig_cli.add_trace(go.Scatter(x=k_cli.index, y=k_cli.iloc[:,0], name='한국 (Korea)', line=dict(color='blue', width=2)))
        fig_cli.add_trace(go.Scatter(x=u_cli.index, y=u_cli.iloc[:,0], name='미국 (US/G7 Proxy)', line=dict(color='red', width=2)))
        fig_cli.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="기준선(100)")
        fig_cli.update_layout(title="OECD 경기선행지수 추이 (100=균형)", height=400)
        st.plotly_chart(fig_cli, use_container_width=True)
    else:
        st.warning("거시경제 데이터를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")

with tab2:
    if k_exp is not None:
        fig_exp = go.Figure()
        fig_exp.add_trace(go.Bar(x=k_exp.index, y=k_exp.iloc[:,0], name='수출액(USD)', marker_color='green'))
        fig_exp.update_layout(title="한국 월별 수출액 (단위: USD)", height=400)
        st.plotly_chart(fig_exp, use_container_width=True)

st.markdown("---")

# ==========================================
# 5. [SECTION 3] 개별 종목 심층 분석
# ==========================================
st.subheader(f"3️⃣ 심층 분석: {ticker_input}")

if ticker_input:
    stock_data = get_market_data(ticker_input, period_days)
    
    if not stock_data.empty:
        # 캔들차트 + 이동평균선 아이디어
        fig_stock = go.Figure()
        
        # 캔들
        fig_stock.add_trace(go.Candlestick(x=stock_data.index,
                        open=stock_data['Open'].iloc[:,0] if stock_data['Open'].ndim > 1 else stock_data['Open'],
                        high=stock_data['High'].iloc[:,0] if stock_data['High'].ndim > 1 else stock_data['High'],
                        low=stock_data['Low'].iloc[:,0] if stock_data['Low'].ndim > 1 else stock_data['Low'],
                        close=stock_data['Close'].iloc[:,0] if stock_data['Close'].ndim > 1 else stock_data['Close'],
                        name='주가'))
        
        fig_stock.update_layout(title=f"{ticker_input} 주가 흐름", xaxis_rangeslider_visible=False, height=500)
        st.plotly_chart(fig_stock, use_container_width=True)
        
        with st.expander("📊 데이터 원본 보기"):
            st.dataframe(stock_data.sort_index(ascending=False))
    else:
        st.error(f"'{ticker_input}'에 대한 데이터를 찾을 수 없습니다. 티커를 확인해주세요.")
