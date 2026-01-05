import streamlit as st
import yfinance as yf
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go  # [추가됨] 차트 설정을 위한 라이브러리
from datetime import datetime, timedelta

# ---------------------------------------------------------
# 1. 페이지 설정 및 제목
# ---------------------------------------------------------
st.set_page_config(page_title="나만의 경제 대시보드", layout="wide")

st.title("📈 나만의 경제지표 대시보드")

# 외부 데이터 링크 버튼
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
    st.info("💡 팁: 차트는 데이터 범위에 맞춰 자동으로 확대됩니다.")

# ---------------------------------------------------------
# [핵심 함수] Plotly 차트 생성 (Y축 자동 조절 기능 포함)
# ---------------------------------------------------------
def create_plotly_chart(df, title, color='#2962FF'):
    """
    데이터프레임을 받아 Y축이 0이 아닌 데이터 범위에 맞춰지는
    Plotly 차트 객체를 반환하는 함수
    """
    if df is None or df.empty:
        return None
    
    # 최신 가격 (점선 표시용)
    try:
        last_price = float(df['Close'].iloc[-1])
    except:
        return None

    # 차트 생성
    fig = go.Figure()

    # 선 그래프 추가
    fig.add_trace(go.Scatter(
        x=df.index, 
        y=df['Close'], 
        mode='lines', 
        name='Close',
        line=dict(color=color, width=2)
    ))

    # 레이아웃 설정 (여기가 Y축 조절의 핵심입니다)
    fig.update_layout(
        title=dict(text=title, font=dict(size=14)),
        margin=dict(l=10, r=10, t=30, b=10), # 여백 최소화
        height=200, # 차트 높이 설정
        
        # X축 설정
        xaxis=dict(
            showgrid=True,
            gridcolor='lightgrey'
        ),
        
        # [수정 요청 반영] Y축: 0부터 시작하지 않고 데이터에 맞춤
        yaxis=dict(
            autorange=True, # 데이터 최소/최대값에 맞춰 자동 줌
            showgrid=True,
            gridcolor='lightgrey'
        ),
        paper_bgcolor='rgba(0,0,0,0)', # 배경 투명
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

# 감시할 주요 지표 리스트
tickers = {
    'USD/KRW (환율)': 'KRW=X', 
    'KOSPI (코스피)': '^KS11', 
    'S&P 500 (선물)': 'ES=F',
    'NASDAQ (선물)': 'NQ=F',
    'Gold (금 선물)': 'GC=F',
    'US 10Y Bond (미국채 10년)': '^TNX'
}

# 3개의 컬럼 생성
cols = st.columns(3)
ticker_items = list(tickers.items())

for i, (name, ticker) in enumerate(ticker_items):
    col = cols[i % 3]
    
    data = get_stock_data(ticker, start_date, end_date)
    
    with col:
        if data is not None and not data.empty:
            # Metric 계산
            try:
                last_price = float(data['Close'].iloc[-1])
                
                if len(data) >= 2:
                    prev_price = float(data['Close'].iloc[-2])
                    delta = last_price - prev_price
                    delta_pct = (delta / prev_price) * 100
                else:
                    delta = 0.0
                    delta_pct = 0.0
                
                # 숫자 표시
                st.metric(label=name, value=f"{last_price:,.2f}", delta=f"{delta:,.2f} ({delta_pct:.2f}%)")
                
                # [수정됨] st.line_chart 대신 Plotly 차트 사용
                fig = create_plotly_chart(data, name)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"데이터 처리 오류: {e}")
        else:
            st.error(f"{name} 데이터 오류")

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
                # [수정됨] 여기도 Plotly 차트로 교체 (초록색)
                fig = create_plotly_chart(df, display_name, color='#00C853')
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            st.error(f"'{code}' 처리 중 에러: {e}")
else:
    st.info("종목을 선택하거나 입력하면 차트가 표시됩니다.")
