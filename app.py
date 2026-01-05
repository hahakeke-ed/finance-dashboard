import streamlit as st
import yfinance as yf
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go 
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. 페이지 설정 및 제목
# ---------------------------------------------------------
st.set_page_config(page_title="나만의 경제 대시보드", layout="wide")

st.title("📈 나만의 경제지표 대시보드")

col_link1, col_link2 = st.columns(2)
with col_link1:
    st.link_button("🌍 OECD 경기선행지수 보러가기", "https://www.oecd.org/en/data/indicators/composite-leading-indicator-cli.html")
with col_link2:
    st.link_button("🇰🇷 한국 수출입 무역통계 보러가기", "https://unipass.customs.go.kr/ets/")

st.markdown("---")

# ---------------------------------------------------------
# 2. 사이드바 설정
# ---------------------------------------------------------
with st.sidebar:
    st.header("설정")
    default_start = datetime.now() - timedelta(days=365)
    default_end = datetime.now()
    
    start_date = st.date_input("시작일", default_start)
    end_date = st.date_input("종료일", default_end)
    st.markdown("---")
    st.info("💡 팁: 그래프에 마우스를 올리면 상세 가격을 볼 수 있습니다.")

# ---------------------------------------------------------
# [핵심 함수 1] 데이터 로드 (에러 원천 차단)
# ---------------------------------------------------------
@st.cache_data
def get_stock_data(ticker, start, end):
    df = pd.DataFrame()
    
    # 1. 한국 지수(KOSPI, KOSDAQ)는 FDR 사용 (yfinance보다 안정적)
    if ticker in ['^KS11', '^KQ11']:
        # FDR 코드로 변환
        fdr_code = 'KS11' if ticker == '^KS11' else 'KQ11'
        try:
            df = fdr.DataReader(fdr_code, start, end)
        except:
            return None
    
    # 2. 그 외 해외 지수는 yfinance 사용
    else:
        try:
            # interval='1d'로 하루 단위 데이터 강제
            df = yf.download(ticker, start=start, end=end, progress=False, interval='1d')
        except:
            return None

    # [중요] 데이터가 비었으면 None 반환
    if df is None or df.empty:
        return None

    # [핵심 수정] yfinance 최신 버전의 MultiIndex 컬럼 문제 해결
    # 컬럼이 ('Close', 'AAPL') 처럼 되어있으면 'Close'로 평탄화
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # [중요] 시간대(Timezone) 정보 제거 (차트 X축 오류 방지)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    return df

# ---------------------------------------------------------
# [핵심 함수 2] Plotly 차트 그리기 (Y축 스케일 최적화)
# ---------------------------------------------------------
def plot_advanced_chart(df, title, color='royalblue'):
    if df is None or df.empty or 'Close' not in df.columns:
        return go.Figure()
    
    # 결측치 제거
    df = df.dropna(subset=['Close'])
    if len(df) < 2: return go.Figure()

    # 값 추출 (Series일 경우 안전하게 변환)
    try:
        last_val = df['Close'].iloc[-1]
        last_price = float(last_val.iloc[0]) if isinstance(last_val, pd.Series) else float(last_val)
    except:
        return go.Figure()

    # [핵심] Y축 범위 동적 계산 (그래프 납작해짐 방지)
    # 데이터의 최소값과 최대값을 구해서 위아래 여백을 줌
    y_min = df['Close'].min()
    y_max = df['Close'].max()
    
    # Series일 경우 float로 변환
    if isinstance(y_min, pd.Series): y_min = float(y_min.iloc[0])
    if isinstance(y_max, pd.Series): y_max = float(y_max.iloc[0])

    padding = (y_max - y_min) * 0.1 if y_max != y_min else y_max * 0.01
    range_min = y_min - padding
    range_max = y_max + padding

    # 차트 생성
    fig = go.Figure()
    
    # 1. 선 그래프
    fig.add_trace(go.Scatter(
        x=df.index, y=df['Close'], 
        mode='lines', name=title,
        line=dict(color=color, width=2),
        hoverinfo='x+y'
    ))

    # 2. 현재가 점선
    fig.add_hline(
        y=last_price, line_dash="dot", line_color="red", line_width=1,
        annotation_text=f"{last_price:,.2f}", 
        annotation_position="top right",
        annotation_font_color="red"
    )

    # 3. 레이아웃 (축 설정)
    fig.update_layout(
        title=dict(text=title, font=dict(size=14)),
        height=200,
        margin=dict(l=10, r=10, t=30, b=20),
        template="plotly_white",
        yaxis=dict(
            range=[range_min, range_max], # 계산된 범위 강제 적용
            showgrid=True,
            fixedrange=False
        ),
        xaxis=dict(
            showgrid=False,
            tickformat='%Y-%m-%d', # 날짜 포맷 고정 (지저분한 시간 제거)
            nticks=5
        )
    )
    return fig

# ---------------------------------------------------------
# 3. 주요 시장 지표 출력
# ---------------------------------------------------------
st.subheader("📊 주요 시장 지표")

tickers = {
    'KOSPI (코스피)': '^KS11', 
    'KOSDAQ (코스닥)': '^KQ11',
    'S&P 500 (선물)': 'ES=F',
    'NASDAQ (선물)': 'NQ=F',
    'Gold (금 선물)': 'GC=F',
    'WTI Crude Oil (원유)': 'CL=F',   
    'Bitcoin (비트코인)': 'BTC-USD',  
    'US 10Y Bond (미국채 10년)': '^TNX',
    'USD/KRW (환율)': 'KRW=X', 
}

cols = st.columns(3)

for i, (name, ticker) in enumerate(tickers.items()):
    col = cols[i % 3]
    
    # 데이터 로드
    data = get_stock_data(ticker, start_date, end_date)
    
    with col:
        # 데이터가 정상적으로 로드되었는지 확인
        if data is not None and not data.empty and 'Close' in data.columns:
            try:
                # 안전한 값 추출 로직
                series = data['Close']
                val_last = series.iloc[-1]
                val_prev = series.iloc[-2]
                
                # Series 타입 체크 및 변환
                last_price = float(val_last.iloc[0]) if isinstance(val_last, pd.Series) else float(val_last)
                prev_price = float(val_prev.iloc[0]) if isinstance(val_prev, pd.Series) else float(val_prev)

                delta = last_price - prev_price
                delta_pct = (delta / prev_price) * 100
                
                # Metric 표시
                st.metric(label=name, value=f"{last_price:,.2f}", delta=f"{delta:,.2f} ({delta_pct:.2f}%)")
                
                # 차트 표시
                fig = plot_advanced_chart(data, name)
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
            except Exception as e:
                st.error(f"데이터 처리 중 오류: {e}")
        else:
            st.error(f"'{name}' 데이터 로드 실패")

st.markdown("---")

# ---------------------------------------------------------
# 4. 한국 주식 목록 및 검색 기능
# ---------------------------------------------------------
@st.cache_data
def get_krx_dict():
    try:
        df = fdr.StockListing('KRX')
        stock_dict = {}
        for index, row in df.iterrows():
            name = row.get('Name')
            code = str(row.get('Code'))
            if not name or not code: continue
            
            # 야후 파이낸스용 코드로 변환
            market = row.get('Market')
            if 'KOSPI' in str(market).upper():
                yahoo_code = code + '.KS'
            elif 'KOSDAQ' in str(market).upper():
                yahoo_code = code + '.KQ'
            else:
                continue
                
            stock_dict[f"{name} ({code})"] = yahoo_code
        return stock_dict
    except:
        return {}

krx_stock_dict = get_krx_dict()

# ---------------------------------------------------------
# 5. 관심 종목 비교 분석
# ---------------------------------------------------------
st.subheader("🔎 관심 종목 상세 분석")

col_search1, col_search2 = st.columns(2)
with col_search1:
    selected_korea = st.multiselect("🇰🇷 한국 주식", list(krx_stock_dict.keys()))
with col_search2:
    manual_input = st.text_input("🇺🇸 해외 티커 입력", placeholder="예: TSLA, AAPL")

# 분석할 종목 리스트 생성
target_codes = []
target_names = []

for item in selected_korea:
    target_codes.append(krx_stock_dict[item])
    target_names.append(item)

if manual_input:
    for code in manual_input.split(','):
        c = code.strip()
        if c:
            target_codes.append(c)
            target_names.append(c)

if target_codes:
    chart_cols = st.columns(2)
    for i, code in enumerate(target_codes):
        with chart_cols[i % 2]:
            df = get_stock_data(code, start_date, end_date)
            if df is not None and not df.empty:
                fig = plot_advanced_chart(df, target_names[i], color='green')
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"{target_names[i]} 데이터 없음")
else:
    st.info("종목을 선택하면 차트가 표시됩니다.")
