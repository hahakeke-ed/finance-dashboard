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
# 2. 사이드바 (기간 설정 등)
# ---------------------------------------------------------
with st.sidebar:
    st.header("설정")
    # 차트의 변화를 잘 보기 위해 기본 기간 설정
    start_date = st.date_input("시작일", datetime.now() - timedelta(days=365))
    end_date = st.date_input("종료일", datetime.now())
    st.markdown("---")
    st.info("💡 팁: 차트 최신 가격에 붉은 점선이 표시됩니다.")

# ---------------------------------------------------------
# [공통 함수] Plotly 차트 생성 (깔끔한 일봉, Y축 자동조절)
# ---------------------------------------------------------
def create_plotly_chart(df, title, color='#2962FF'):
    # 1. 데이터 검증
    if df is None or df.empty:
        return None
    
    # 2. 최신 가격 가져오기 (에러 방지 로직 강화)
    try:
        last_price = float(df['Close'].iloc[-1])
    except:
        return None # 가격 변환 실패 시 차트 그리지 않음

    # 3. 차트 그리기
    fig = go.Figure()

    # 선 그래프 (일별 데이터 그대로 사용 -> 매끄러운 곡선)
    fig.add_trace(go.Scatter(
        x=df.index, 
        y=df['Close'], 
        mode='lines', 
        name='Close',
        line=dict(color=color, width=2)
    ))

    # 4. 최신 값 점선 추가 (Y축과 연결)
    fig.add_hline(
        y=last_price, 
        line_dash="dot", 
        line_color="red", 
        line_width=1,
        annotation_text=f"{last_price:,.2f}", 
        annotation_position="bottom right",
        annotation_font_color="red"
    )

    # 5. 레이아웃 설정 (핵심 수정 사항 반영)
    fig.update_layout(
        title=dict(text=title, font=dict(size=14)),
        margin=dict(l=10, r=10, t=30, b=10), # 여백 최소화
        height=250, 
        
        # [수정] X축: 복잡한 포맷 제거 -> 원래대로 깔끔하게
        xaxis=dict(
            showgrid=True,
            gridcolor='lightgrey'
        ),
        
        # [수정] Y축: 0부터 시작하지 않음 (autorange=True)
        # 변화량이 잘 보이도록 데이터 범위에 맞춰 자동 줌인
        yaxis=dict(
            autorange=True, 
            fixedrange=False, # 사용자가 줌 가능
            showgrid=True,
            gridcolor='lightgrey'
        ),
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

# ---------------------------------------------------------
# 3. 주요 시장 지표
# ---------------------------------------------------------
st.subheader("📊 주요 시장 지표")

@st.cache_data
def get_stock_data(ticker, start, end):
    try:
        data = yf.download(ticker, start=start, end=end, progress=False)
        return data
    except Exception as e:
        return None

# [요청하신 순서 적용]
tickers = {
    '1. KOSPI (코스피)': '^KS11',
    '2. KOSDAQ (코스닥)': '^KQ11',
    '3. S&P 500': 'ES=F',
    '4. NASDAQ (나스닥)': 'NQ=F',
    '5. Gold (금)': 'GC=F',
    '6. WTI Oil (원유)': 'CL=F',
    '7. Bitcoin (비트코인)': 'BTC-USD',
    '8. US 10Y Bond (미국채)': '^TNX',
    '9. USD/KRW (환율)': 'KRW=X'
}

# 3열 배치
cols = st.columns(3)
ticker_items = list(tickers.items())

for i, (name, ticker) in enumerate(ticker_items):
    col = cols[i % 3] 
    
    data = get_stock_data(ticker, start_date, end_date)
    
    with col:
        if data is not None and not data.empty:
            try:
                # 데이터 추출
                close_data = data['Close']
                last_price = float(close_data.iloc[-1])
                
                # 전일비 계산
                if len(close_data) >= 2:
                    prev_price = float(close_data.iloc[-2])
                    delta = last_price - prev_price
                    delta_pct = (delta / prev_price) * 100
                else:
                    delta = 0.0
                    delta_pct = 0.0
                
                # Metric 표시
                st.metric(
                    label=name, 
                    value=f"{last_price:,.2f}", 
                    delta=f"{delta:,.2f} ({delta_pct:.2f}%)"
                )
                
                # 차트 표시
                fig = create_plotly_chart(data, name)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"표시 오류: {e}")
        else:
            # 데이터가 안 불러와질 경우 (일시적 서버 오류 등)
            st.warning(f"{name}: 데이터 로딩 실패")

st.markdown("---")

# ---------------------------------------------------------
# 4. 한국 주식 목록 가져오기 (FDR)
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
        placeholder="콤마(,)로 구분 (예: PLTR, TSLA)"
    )

# 종목 리스트 합치기
final_codes = []
final_names = []

for item in selected_korea_stocks:
    final_codes.append(krx_stock_dict[item])
    final_names.append(item)

if manual_input:
    manual_codes = [c.strip() for c in manual_input.split(',') if c.strip()]
    final_codes.extend(manual_codes)
    final_names.extend(manual_codes)

# 결과 차트 그리기
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
                # 초록색 차트
                fig = create_plotly_chart(df, display_name, color='#00C853')
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            st.error(f"'{code}' 처리 중 에러: {e}")
else:
    st.info("종목을 선택하거나 입력하면 차트가 표시됩니다.")
