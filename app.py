import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# -----------------------------------------------------------
# 1. 페이지 설정 (반드시 코드 최상단에 딱 한 번만 있어야 합니다)
# -----------------------------------------------------------
st.set_page_config(
    page_title="경제 지표 & 포트폴리오 대시보드", 
    page_icon="📈", 
    layout="wide"
)

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

# -----------------------------------------------------------
# 3. 사이드바: 종목 설정 & 메모장
# -----------------------------------------------------------
st.sidebar.header("🔍 관심 종목 설정")

# 핵심 인기 종목 100선
popular_stocks = {
    # 한국 코스피
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS", "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS", "현대차": "005380.KS", "기아": "000270.KS",
    "POSCO홀딩스": "005490.KS", "NAVER": "035420.KS", "카카오": "035720.KS",
    "삼성물산": "028260.KS", "KB금융": "105560.KS", "신한지주": "055550.KS",
    "셀트리온": "068270.KS", "LG화학": "051910.KS", "삼성SDI": "006400.KS",
    # 한국 코스닥
    "알테오젠": "196170.KQ", "에코프로비엠": "247540.KQ", "에코프로": "086520.KQ",
    "HLB": "028300.KQ", "리가켐바이오": "141080.KQ", "클래시스": "214150.KQ",
    "엔켐": "348370.KQ", "휴젤": "145020.KQ", "리노공업": "058470.KQ",
    # 미국 빅테크
    "애플 (Apple)": "AAPL", "마이크로소프트 (MSFT)": "MSFT", "엔비디아 (NVIDIA)": "NVDA",
    "구글 (Alphabet)": "GOOGL", "아마존 (Amazon)": "AMZN", "테슬라 (Tesla)": "TSLA",
    "메타 (Meta)": "META", "TSMC (TSM)": "TSM", "AMD": "AMD", "브로드컴": "AVGO",
    "넷플릭스": "NFLX", "인텔": "INTC", "마이크론": "MU", "팔란티어": "PLTR",
    # ETF
    "S&P 500 (SPY)": "SPY", "나스닥 100 (QQQ)": "QQQ", 
    "필라델피아 반도체 (SOXX)": "SOXX", "반도체 3배 (SOXL)": "SOXL", "나스닥 3배 (TQQQ)": "TQQQ",
    "배당성장 (SCHD)": "SCHD", "커버드콜 (JEPI)": "JEPI", "비트코인 ETF (IBIT)": "IBIT"
}

ticker_to_name = {v: k for k, v in popular_stocks.items()}

# 멀티 선택 박스
selected_names = st.sidebar.multiselect(
    "1. 주요 인기 종목 선택",
    options=list(popular_stocks.keys()),
    default=["삼성전자", "테슬라 (Tesla)", "엔비디아 (NVIDIA)"]
)

# 직접 입력 창
custom_input = st.sidebar.text_input(
    "2. 직접 코드 입력하여 추가(콤마 구분)", 
    placeholder="예: 000100.KS, PLTR"
)

# 최종 종목 리스트 생성
final_tickers = []
for name in selected_names:
    final_tickers.append(popular_stocks[name])

if custom_input:
    custom_list = [x.strip() for x in custom_input.split(',')]
    final_tickers.extend(custom_list)

if len(final_tickers) > 6:
    st.sidebar.warning("⚠️ 속도를 위해 6개까지만 표시합니다.")
    final_tickers = final_tickers[:6]

st.sidebar.markdown("---")

# === 메모장 기능 ===
st.sidebar.header("📝 간단 메모장")
st.sidebar.caption("※ 주의: 탭을 닫거나 새로고침하면 내용이 사라집니다.")
memo = st.sidebar.text_area("매매 아이디어 / 할 일", height=200, placeholder="여기에 메모를 입력하세요...")

# -----------------------------------------------------------
# 4. [SECTION 1] Market Pulse (시장 핵심 지표)
# -----------------------------------------------------------
st.subheader("1️⃣ Market Pulse (시장 핵심 지표)")

# [수정] S&P 500을 ETF(SPY)로 교체하여 로딩 오류 해결
indices = {
    "S&P 500 (ETF)": "SPY",   # ^GSPC 대신 SPY 사용
    "나스닥": "^IXIC",
    "코스피": "^KS11",
    "코스닥": "^KQ11",
    "원/달러 환율": "KRW=X",
    "VIX (공포지수)": "^VIX",
    "국제 금값": "GC=F",     
    "WTI 원유": "CL=F",      
    "비트코인": "BTC-USD"
}

cols = st.columns(3)

for i, (name, ticker) in enumerate(indices.items()):
    data = get_stock_data(ticker, period="1y")
    
    with cols[i % 3]:
        if not data.empty and len(data) > 1:
            try:
                # 데이터 값 추출
                last_val = data['Close'].iloc[-1]
                prev_val = data['Close'].iloc[-2]
                val = last_val.item() if hasattr(last_val, 'item') else last_val
                prev = prev_val.item() if hasattr(prev_val, 'item') else prev_val
                
                pct = ((val - prev) / prev) * 100
                color = "red" if pct >= 0 else "blue"
                
                fig = go.Figure()
                
                # 라인 차트
                fig.add_trace(go.Scatter(
                    x=data.index, 
                    y=data['Close'].iloc[:,0] if data['Close'].ndim>1 else data['Close'],
                    mode='lines', name=name,
                    line=dict(color=color, width=2)
                ))

                # [점선] 현재가 가로 점선 추가
                fig.add_hline(y=val, line_dash="dot", line_color=color, line_width=1, opacity=0.7)

                # VIX 배경색 (최대 80으로 제한)
                if "VIX" in name:
                    fig.add_hrect(y0=0, y1=20, fillcolor="green", opacity=0.1, layer="below")
                    fig.add_hrect(y0=20, y1=30, fillcolor="gray", opacity=0.1, layer="below")
                    fig.add_hrect(y0=30, y1=80, fillcolor="red", opacity=0.1, layer="below")

                fig.update_layout(
                    title=dict(text=f"<b>{name}</b> {val:,.2f} ({pct:+.2f}%)", font=dict(size=14)),
                    margin=dict(l=10, r=10, t=30, b=20), height=200,
                    yaxis=dict(showgrid=True, autorange=True, fixedrange=False), 
                    xaxis=dict(visible=True, showgrid=False, tickformat="%y.%m", tickfont=dict(size=10))
                )
                st.plotly_chart(fig, use_container_width=True)
            except: st.error(f"{name} 오류")
        else:
            st.warning(f"{name}: 데이터 로딩 실패")

st.markdown("---")

# -----------------------------------------------------------
# 5. [SECTION 2] 거시경제
# -----------------------------------------------------------
st.subheader("2️⃣ Macro Trends (주요 경제 사이트 바로가기)")
st.info("데이터 로딩 오류를 방지하기 위해, 각 기관의 공식 데이터 페이지로 직접 연결합니다.")

col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    st.markdown("#### 🇰🇷 KR 한국 수출입 통계")
    st.link_button("관세청 수출입 무역통계 보기", "https://unipass.customs.go.kr/ets/index.do")
with col_m2:
    st.markdown("#### 🌏 OECD 경기선행지수")
    st.link_button("OECD Data (CLI) 바로가기", "https://data.oecd.org/leadind/composite-leading-indicator-cli.htm")
with col_m3:
    st.markdown("#### 🇺🇸 US FRED (미 연준 데이터)")
    st.link_button("FRED 메인 페이지", "https://fred.stlouisfed.org/")

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
                
                # 차트 제목 로직
                last_p = df['Close'].iloc[-1]
                p_val = last_p.item() if hasattr(last_p, 'item') else last_p
                
                stock_name = ticker_to_name.get(ticker, ticker)
                
                if "KS" in ticker or "KQ" in ticker:
                    title_text = f"<b>{stock_name}</b> ({ticker}) {p_val:,.0f} KRW"
                else:
                    title_text = f"<b>{stock_name}</b> ({ticker}) ${p_val:,.2f}"

                # [점선] 현재가 가로 점선 추가 (포트폴리오)
                fig.add_hline(y=p_val, line_dash="dot", line_color="gray", line_width=1, opacity=0.7)

                fig.update_layout(title=dict(text=title_text, font=dict(size=14)),
                                  height=400, showlegend=False, xaxis_rangeslider_visible=False, margin=dict(t=40,b=20,l=10,r=10))
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"{ticker} 차트 오류")
