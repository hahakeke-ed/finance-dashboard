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
    # 주봉으로 보기 때문에 기간을 조금 넉넉히 잡는 것이 좋습니다 (기본 1년)
    start_date = st.date_input("시작일", datetime.now() - timedelta(days=365))
    end_date = st.date_input("종료일", datetime.now())
    st.markdown("---")
    st.info("💡 팁: 모든 차트는 '주봉(Weekly)' 기준이며, 최신 가격에 점선이 표시됩니다.")

# ---------------------------------------------------------
# [공통 함수] Plotly 차트 생성 (주봉, Y축 조절, 점선 추가)
# ---------------------------------------------------------
def create_plotly_chart(df, title, color='#2962FF'):
    # 1. 데이터가 비어있으면 None 반환
    if df is None or df.empty:
        return None

    # 2. 주봉(Weekly)으로 변환 (Resample)
    df_weekly = df['Close'].resample('W').last()
    
    # [수정된 부분] 최신 가격을 확실하게 float(실수)로 변환
    try:
        last_price = float(df_weekly.iloc[-1])
    except:
        return None # 가격을 가져올 수 없으면 차트 생성 중단

    # 3. 차트 그리기
    fig = go.Figure()

    # 선 그래프 추가
    fig.add_trace(go.Scatter(
        x=df_weekly.index, 
        y=df_weekly.values, 
        mode='lines', 
        name='Close',
        line=dict(color=color, width=2)
    ))

    # 4. 최신 값 점선 추가 (Horizontal Line)
    fig.add_hline(
        y=last_price, 
        line_dash="dot", 
        line_color="red", 
        line_width=1,
        annotation_text=f"{last_price:,.2f}", 
        annotation_position="bottom right",
        annotation_font_color="red"
    )

    # 5. 레이아웃 설정 (Y축 조절, X축 월 표시)
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        margin=dict(l=10, r=10, t=40, b=10), 
        height=250, 
        
        xaxis=dict(
            tickformat="%m월", 
            showgrid=True,
            gridcolor='lightgrey'
        ),
        
        yaxis=dict(
            autorange=True, 
            showgrid=True,
            gridcolor='lightgrey',
        ),
        paper_bgcolor='rgba(0,0,0,0)', 
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

# ---------------------------------------------------------
# 3. 주요 시장 지표 (요청하신 순서대로 배치)
# ---------------------------------------------------------
st.subheader("📊 주요 시장 지표 (주봉 기준)")

@st.cache_data
def get_stock_data(ticker, start, end):
    try:
        data = yf.download(ticker, start=start, end=end, progress=False)
        return data
    except Exception as e:
        return None

tickers = {
    '1. KOSPI (코스피)': '^KS11',
    '2. KOSDAQ (코스닥)': '^KQ11',
    '3. S&P 500 (선물)': 'ES=F',
    '4. NASDAQ (선물)': 'NQ=F',
    '5. Gold (금)': 'GC=F',
    '6. WTI Oil (원유)': 'CL=F',
    '7. Bitcoin (비트코인)': 'BTC-USD',
    '8. US 10Y Bond (미국채)': '^TNX',
    '9. USD/KRW (환율)': 'KRW=X'
}

cols = st.columns(3)
ticker_items = list(tickers.items())

for i, (name, ticker) in enumerate(ticker_items):
    col = cols[i % 3] 
    
    data = get_stock_data(ticker, start_date, end_date)
    
    with col:
        if data is not None and not data.empty:
            try:
                # 전일비 계산
                last_price = data['Close'].iloc[-1]
                if len(data) >= 2:
                    prev_price = data['Close'].iloc[-2]
                    delta = last_price - prev_price
                    delta_pct = (delta / prev_price) * 100
                else:
                    delta = 0; delta_pct = 0
                
                # Metric 표시 (float 변환 필수)
                st.metric(
                    label=name, 
                    value=f"{float(last_price):,.2f}", 
                    delta=f"{float(delta):,.2f} ({float(delta_pct):.2f}%)"
                )
                
                # Plotly 차트 그리기
                fig = create_plotly_chart(data, name)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"차트 처리 중 오류: {e}")
            
        else:
            st.error(f"{name} 데이터 오류 (불러오기 실패)")

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
st.subheader("🔎 관심 종목 상세 분석 (주봉)")

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
                fig = create_plotly_chart(df, display_name, color='#00C853') 
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            st.error(f"'{code}' 처리 중 에러: {e}")
else:
    st.info("종목을 선택하거나 입력하면 차트가 표시됩니다.")
