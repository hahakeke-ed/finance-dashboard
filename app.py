import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# -----------------------------------------------------------
# 1. 페이지 설정
# -----------------------------------------------------------
st.set_page_config(page_title="경제 지표 & 포트폴리오 대시보드", layout="wide")

st.markdown("""
<style>
    .stMetric {
        background-color: #f8f9fa;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Economic & Portfolio Dashboard")
st.markdown("거시경제 흐름과 나의 관심 종목을 한눈에 비교 분석합니다.")

# -----------------------------------------------------------
# 2. 데이터 수집 함수
# -----------------------------------------------------------
@st.cache_data
def get_stock_data(ticker, period='1y'):
    try:
        df = yf.download(ticker, period=period, progress=False)
        return df
    except:
        return pd.DataFrame()

@st.cache_data
def get_fred_data_robust(series_id):
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        storage_options = {'User-Agent': 'Mozilla/5.0'}
        df = pd.read_csv(url, index_col='DATE', parse_dates=True, storage_options=storage_options)
        start_date = datetime.now() - timedelta(days=365*5)
        return df[df.index > start_date]
    except:
        return None

# -----------------------------------------------------------
# 3. 사이드바: 확장된 종목 리스트
# -----------------------------------------------------------
st.sidebar.header("🔍 관심 종목 설정")

# 핵심 인기 종목 100선 (한국/미국/ETF)
popular_stocks = {
    # === 한국 코스피 (대형주) ===
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대차": "005380.KS",
    "기아": "000270.KS",
    "셀트리온": "068270.KS",
    "KB금융": "105560.KS",
    "POSCO홀딩스": "005490.KS",
    "NAVER": "035420.KS",
    "카카오": "035720.KS",
    "신한지주": "055550.KS",
    "삼성물산": "028260.KS",
    "현대모비스": "012330.KS",
    "LG화학": "051910.KS",
    "삼성SDI": "006400.KS",
    "하나금융지주": "086790.KS",
    "메리츠금융지주": "138040.KS",
    "LG전자": "066570.KS",
    "두산에너빌리티": "034020.KS",
    "HMM": "011200.KS",
    "한화에어로스페이스": "012450.KS",
    "HD현대중공업": "329180.KS",
    "크래프톤": "259960.KS",
    "SK텔레콤": "017670.KS",
    "우리금융지주": "316140.KS",
    "KT": "030200.KS",
    "기업은행": "024110.KS",
    
    # === 한국 코스닥 (대장주) ===
    "알테오젠": "196170.KQ",
    "에코프로비엠": "247540.KQ",
    "에코프로": "086520.KQ",
    "HLB": "028300.KQ",
    "리가켐바이오": "141080.KQ",
    "클래시스": "214150.KQ",
    "엔켐": "348370.KQ",
    "휴젤": "145020.KQ",
    "리노공업": "058470.KQ",
    "삼천당제약": "000250.KQ",
    "레인보우로보틱스": "277810.KQ",
    "HPSP": "403870.KQ",
    "JYP Ent.": "035900.KQ",
    "펄어비스": "263750.KQ",

    # === 미국 빅테크 (M7 + 주요주) ===
    "애플 (Apple)": "AAPL",
    "마이크로소프트 (MSFT)": "MSFT",
    "엔비디아 (NVIDIA)": "NVDA",
    "구글 (Alphabet A)": "GOOGL",
    "아마존 (Amazon)": "AMZN",
    "테슬라 (Tesla)": "TSLA",
    "메타 (Meta)": "META",
    "브로드컴 (Broadcom)": "AVGO",
    "TSMC (ADR)": "TSM",
    "일라이릴리 (Lilly)": "LLY",
    "노보노디스크 (Novo)": "NVO",
    "ASML": "ASML",
    "AMD": "AMD",
    "넷플릭스": "NFLX",
    "코스트코": "COST",
    "인텔": "INTC",
    "마이크론": "MU",
    "팔란티어": "PLTR",
    "코인베이스": "COIN",
    "아이온큐": "IONQ",
    "유니티": "U",
    
    # === 주요 ETF (지수/레버리지) ===
    "S&P 500 (SPY)": "SPY",
    "나스닥 100 (QQQ)": "QQQ",
    "필라델피아 반도체 (SOXX)": "SOXX",
    "반도체 3배 (SOXL)": "SOXL",
    "나스닥 3배 (TQQQ)": "TQQQ",
    "테슬라 1.5배 (TSLL)": "TSLL",
    "배당성장 (SCHD)": "SCHD",
    "월배당 커버드콜 (JEPI)": "JEPI",
    "비트코인 현물 ETF (IBIT)": "IBIT"
}

# 멀티 선택 박스
selected_names = st.sidebar.multiselect(
    "1. 주요 인기 종목 선택 (검색 가능)",
    options=list(popular_stocks.keys()),
    default=["삼성전자", "테슬라 (Tesla)", "엔비디아 (NVIDIA)"]
)

# 직접 입력 창
custom_input = st.sidebar.text_input(
    "2. 리스트에 없는 종목 직접 입력", 
    placeholder="예: 000100.KS, SOFI, NVDL"
)

# 최종 종목 리스트 만들기
final_tickers = []
for name in selected_names:
    final_tickers.append(popular_stocks[name])

if custom_input:
    custom_list = [x.strip() for x in custom_input.split(',')]
    final_tickers.extend(custom_list)

# 최대 6개 제한 및 경고
if len(final_tickers) > 6:
    st.sidebar.warning("⚠️ 종목이 6개를 넘으면 속도가 느려질 수 있어 앞쪽 6개만 표시합니다.")
    final_tickers = final_tickers[:6]

st.sidebar.markdown("---")
st.sidebar.caption("※ PC화면 최적화: 차트는 마우스로 확대/축소 가능합니다.")

# -----------------------------------------------------------
# 4. [SECTION 1] Market Pulse (3열 라인 차트)
# -----------------------------------------------------------
st.subheader("1️⃣ Market Pulse (시장 핵심 지표)")

indices = {
    "달러 인덱스": "DX-Y.NYB",
    "원/달러 환율": "KRW=X",
    "VIX (공포지수)": "^VIX",
    "S&P 500": "^GSPC",
    "나스닥": "^IXIC",
    "코스피": "^KS11",
    "비트코인": "BTC-USD"
}

cols = st.columns(3)

for i, (name, ticker) in enumerate(indices.items()):
    data = get_stock_data(ticker, period="1y")
    with cols[i % 3]:
        if not data.empty and len(data) > 1:
            try:
                # 데이터 값 추출 (호환성)
                last_val = data['Close'].iloc[-1]
                prev_val = data['Close'].iloc[-2]
                val = last_val.item() if hasattr(last_val, 'item') else last_val
                prev = prev_val.item() if hasattr(prev_val, 'item') else prev_val
                
                pct = ((val - prev) / prev) * 100
                color = "red" if pct >= 0 else "blue"
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=data.index, 
                    y=data['Close'].iloc[:,0] if data['Close'].ndim>1 else data['Close'],
                    mode='lines', name=name,
                    line=dict(color=color, width=1.5),
                    fill='tozeroy', fillcolor=f"rgba({'255,0,0' if pct>=0 else '0,0,255'}, 0.1)"
                ))
                fig.update_layout(
                    title=f"<b>{name}</b> {val:,.2f} ({pct:+.2f}%)",
                    margin=dict(l=10, r=10, t=40, b=20), height=200,
                    xaxis=dict(visible=False), yaxis=dict(showgrid=False)
                )
                st.plotly_chart(fig, use_container_width=True)
            except: st.error(f"{name} 오류")

st.markdown("---")

# -----------------------------------------------------------
# 5. [SECTION 2] 거시경제
# -----------------------------------------------------------
st.subheader("2️⃣ Macro Trends (거시 경제 흐름)")
tab1, tab2 = st.tabs(["OECD 경기선행지수", "한국 수출액"])

k_cli = get_fred_data_robust('LOLITOAKRM156S')
us_cli = get_fred_data_robust('LOLITONOUSM156S')
k_exp = get_fred_data_robust('XTEXVA01KRM667S')

with tab1:
    if k_cli is not None and us_cli is not None:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=k_cli.index, y=k_cli.iloc[:,0], name='한국', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=us_cli.index, y=us_cli.iloc[:,0], name='미국', line=dict(color='red')))
        fig.add_hline(y=100, line_dash="dash", line_color="gray")
        fig.update_layout(height=400, title="OECD 경기선행지수 (최근 5년)", hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    else: st.error("데이터 로딩 실패 (FRED)")

with tab2:
    if k_exp is not None:
        st.plotly_chart(go.Figure(data=[go.Bar(x=k_exp.index, y=k_exp.iloc[:,0], marker_color='green')], 
                                  layout=dict(title="한국 월별 수출액 (USD)", height=400)), use_container_width=True)

st.markdown("---")

# -----------------------------------------------------------
# 6. [SECTION 3] 포트폴리오 (주봉 + 거래량)
# -----------------------------------------------------------
st.subheader(f"3️⃣ Portfolio Watch (선택 종목: {len(final_tickers)}개)")

if not final_tickers:
    st.info("👈 왼쪽 사이드바에서 종목을 선택하세요.")
else:
    s_cols = st.columns(3)
    for i, ticker in enumerate(final_tickers):
        with s_cols[i % 3]:
            try:
                df = get_stock_data(ticker, period='1y')
                if df.empty:
                    st.warning(f"{ticker} 데이터 없음"); continue
                
                # 주봉 변환
                logic = {'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}
                if isinstance(df.columns, pd.MultiIndex):
                    df_w = df.resample('W-FRI').agg({
                        ('Open', ticker): 'first', ('High', ticker): 'max', 
                        ('Low', ticker): 'min', ('Close', ticker): 'last', ('Volume', ticker): 'sum'
                    })
                    df_w.columns = ['Open','High','Low','Close','Volume']
                else:
                    df_w = df.resample('W-FRI').agg(logic)
                
                # 차트 생성
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
                fig.add_trace(go.Candlestick(x=df_w.index, open=df_w['Open'], high=df_w['High'], low=df_w['Low'], close=df_w['Close'], name="주가"), row=1, col=1)
                colors = ['red' if o < c else 'blue' for o, c in zip(df_w['Open'], df_w['Close'])]
                fig.add_trace(go.Bar(x=df_w.index, y=df_w['Volume'], marker_color=colors, name="거래량"), row=2, col=1)
                
                last_p = df['Close'].iloc[-1]
                p_val = last_p.item() if hasattr(last_p, 'item') else last_p
                
                fig.update_layout(title=f"<b>{ticker}</b> {p_val:,.0f}" if "KS" in ticker or "KQ" in ticker else f"<b>{ticker}</b> ${p_val:,.2f}",
                                  height=400, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=40,b=20,l=10,r=10))
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"{ticker} 차트 오류")
