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
    st.link_button("🌍 OECD 경기선행지수 보러가기", "https://data.oecd.org/leadind/composite-leading-indicators-cli.htm")
with col_link2:
    st.link_button("🇰🇷 한국 수출입 무역통계 보러가기", "https://unipass.customs.go.kr/ets/")

st.markdown("---")

# ---------------------------------------------------------
# 2. 사이드바
# ---------------------------------------------------------
with st.sidebar:
    st.header("설정")
    start_date = st.date_input("시작일", datetime.now() - timedelta(days=365))
    end_date = st.date_input("종료일", datetime.now())
    st.markdown("---")
    st.info("💡 팁: 그래프에 마우스를 올리면 상세 가격을 볼 수 있습니다.")

# ---------------------------------------------------------
# [수정된 함수] 오류 해결: 값을 강제로 float로 변환
# ---------------------------------------------------------
def plot_advanced_chart(df, title, color='royalblue'):
    if df is None or df.empty:
        return go.Figure()
    
    # [수정 포인트] 데이터가 Series나 DataFrame일 경우를 대비해 안전하게 값 추출
    close_data = df['Close']
    
    # 마지막 값을 가져옴
    last_val_raw = close_data.iloc[-1]
    
    # 만약 가져온 값이 Series(리스트 형태)라면 첫 번째 값을 꺼냄
    if isinstance(last_val_raw, pd.Series):
        last_val_raw = last_val_raw.iloc[0]
        
    # 순수 숫자(float)로 변환 (여기서 에러 방지)
    last_price = float(last_val_raw)
    
    fig = go.Figure()
    
    # 메인 라인
    fig.add_trace(go.Scatter(
        x=df.index, 
        y=df['Close'], 
        mode='lines', 
        name=title,
        line=dict(color=color, width=2)
    ))

    # 점선 추가
    fig.add_hline(
        y=last_price, 
        line_dash="dot", 
        line_color="red", 
        line_width=1,
        annotation_text=f"{last_price:,.2f}", 
        annotation_position="top left",
        annotation_font_color="red"
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        height=250,
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis=dict(autorange=True, fixedrange=False), 
        xaxis=dict(showgrid=False),
        template="plotly_white"
    )
    
    return fig

@st.cache_data
def get_stock_data(ticker, start, end):
    try:
        data = yf.download(ticker, start=start, end=end, progress=False)
        return data
    except Exception as e:
        return None

# ---------------------------------------------------------
# 3. 주요 시장 지표
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
ticker_items = list(tickers.items())

for i, (name, ticker) in enumerate(ticker_items):
    col = cols[i % 3]
    
    data = get_stock_data(ticker, start_date, end_date)
    
    with col:
        if data is not None and not data.empty:
            # [수정 포인트] Metric 계산 시에도 안전하게 값 추출
            try:
                # Close 컬럼 가져오기
                close_series = data['Close']
                
                # 값 추출 (Series일 경우 처리)
                val_last = close_series.iloc[-1]
                if isinstance(val_last, pd.Series): val_last = val_last.iloc[0]
                last_price = float(val_last)

                if len(data) >= 2:
                    val_prev = close_series.iloc[-2]
                    if isinstance(val_prev, pd.Series): val_prev = val_prev.iloc[0]
                    prev_price = float(val_prev)
                    
                    delta = last_price - prev_price
                    delta_pct = (delta / prev_price) * 100
                else:
                    delta = 0
                    delta_pct = 0
                
                st.metric(label=name, value=f"{last_price:,.2f}", delta=f"{delta:,.2f} ({delta_pct:.2f}%)")
                
                # 차트 그리기
                fig = plot_advanced_chart(data, name)
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
            except Exception as e:
                st.error(f"데이터 처리 오류: {e}")
        else:
            st.error(f"{name} 데이터 없음")

st.markdown("---")

# ---------------------------------------------------------
# 4. 한국 주식 목록 가져오기
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
# 5. 관심 종목 비교 분석
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

final_codes = []
final_names = []

for item in selected_korea_stocks:
    final_codes.append(krx_stock_dict[item])
    final_names.append(item)

if manual_input:
    manual_codes = [c.strip() for c in manual_input.split(',') if c.strip()]
    final_codes.extend(manual_codes)
    final_names.extend(manual_codes)

if final_codes:
    st.write(f"총 {len(final_codes)}개의 종목을 분석합니다.")
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
                fig = plot_advanced_chart(df, display_name, color='green')
                st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            st.error(f"'{code}' 처리 중 에러: {e}")
else:
    st.info("종목을 선택하거나 입력하면 차트가 표시됩니다.")
