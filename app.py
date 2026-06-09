import re
from datetime import datetime, timedelta

import FinanceDataReader as fdr
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ---------------------------------------------------------
# 1. 페이지 설정 및 제목
# ---------------------------------------------------------
st.set_page_config(page_title="나만의 경제 대시보드", layout="wide")

st.title("📈 나만의 경제지표 대시보드")

col_link1, col_link2 = st.columns(2)
with col_link1:
    st.link_button(
        "🌍 OECD 경기선행지수 보러가기",
        "https://www.oecd.org/en/data/indicators/composite-leading-indicator-cli.html",
    )
with col_link2:
    st.link_button(
        "🇰🇷 한국 수출입 무역통계 보러가기",
        "https://unipass.customs.go.kr/ets/",
    )

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
    st.caption("※ 금융 데이터는 외부 서비스 상황에 따라 지연되거나 일시적으로 불러오지 못할 수 있습니다.")

if start_date >= end_date:
    st.error("시작일은 종료일보다 앞선 날짜로 선택해 주세요.")
    st.stop()

# yfinance의 end 날짜는 종료일이 포함되지 않는 경우가 많아 하루를 더해 전달합니다.
load_end_date = end_date + timedelta(days=1)


# ---------------------------------------------------------
# 공통 유틸 함수
# ---------------------------------------------------------
def to_float(value):
    """pandas Series/스칼라 값을 안전하게 float로 변환합니다."""
    if isinstance(value, pd.Series):
        value = value.iloc[0]
    return float(value)


def add_target(targets, ticker, label, seen=None):
    """중복 종목을 제거하면서 분석 대상 목록에 추가합니다."""
    if seen is None:
        seen = set()

    normalized_ticker = str(ticker).strip()
    if not normalized_ticker:
        return False

    key = normalized_ticker.upper()
    if key in seen:
        return False

    seen.add(key)
    targets.append((normalized_ticker, str(label).strip() or normalized_ticker))
    return True


# ---------------------------------------------------------
# [핵심 함수 1] 데이터 로드
# ---------------------------------------------------------
@st.cache_data(ttl=60 * 30, show_spinner=False)
def get_stock_data(ticker, start, end):
    df = pd.DataFrame()

    # 1. 한국 지수(KOSPI, KOSDAQ)는 FDR 사용
    if ticker in ["^KS11", "^KQ11"]:
        fdr_code = "KS11" if ticker == "^KS11" else "KQ11"
        try:
            df = fdr.DataReader(fdr_code, start, end)
        except Exception:
            return None

    # 2. 그 외 해외 지수·주식·환율·원자재는 yfinance 사용
    else:
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, interval="1d")
        except Exception:
            return None

    if df is None or df.empty:
        return None

    # yfinance 최신 버전의 MultiIndex 컬럼 문제 대응
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 차트 X축 오류 방지를 위해 시간대 정보 제거
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)

    return df


# ---------------------------------------------------------
# [핵심 함수 2] Plotly 차트 그리기
# ---------------------------------------------------------
def plot_advanced_chart(df, title, color="royalblue"):
    if df is None or df.empty or "Close" not in df.columns:
        return go.Figure()

    df = df.dropna(subset=["Close"])
    if len(df) < 2:
        return go.Figure()

    try:
        last_price = to_float(df["Close"].iloc[-1])
    except Exception:
        return go.Figure()

    y_min = df["Close"].min()
    y_max = df["Close"].max()

    try:
        y_min = to_float(y_min)
        y_max = to_float(y_max)
    except Exception:
        return go.Figure()

    padding = (y_max - y_min) * 0.1 if y_max != y_min else abs(y_max) * 0.01
    if padding == 0:
        padding = 1

    range_min = y_min - padding
    range_max = y_max + padding

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["Close"],
            mode="lines",
            name=title,
            line=dict(color=color, width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.2f}<extra></extra>",
        )
    )

    fig.add_hline(
        y=last_price,
        line_dash="dot",
        line_color="red",
        line_width=1,
        annotation_text=f"{last_price:,.2f}",
        annotation_position="top right",
        annotation_font_color="red",
    )

    fig.update_layout(
        title=dict(text=title, font=dict(size=14)),
        height=220,
        margin=dict(l=10, r=10, t=35, b=20),
        template="plotly_white",
        yaxis=dict(range=[range_min, range_max], showgrid=True, fixedrange=False),
        xaxis=dict(showgrid=False, tickformat="%Y-%m-%d", nticks=5),
    )
    return fig


# ---------------------------------------------------------
# 3. 주요 시장 지표 출력
# ---------------------------------------------------------
st.subheader("📊 주요 시장 지표")

market_tickers = {
    "KOSPI (코스피)": "^KS11",
    "KOSDAQ (코스닥)": "^KQ11",
    "S&P 500 (선물)": "ES=F",
    "NASDAQ (선물)": "NQ=F",
    "Gold (금 선물)": "GC=F",
    "WTI Crude Oil (원유)": "CL=F",
    "Bitcoin (비트코인)": "BTC-USD",
    "US 10Y Bond (미국채 10년)": "^TNX",
    "USD/KRW (환율)": "KRW=X",
    "VIX (공포지수)": "^VIX",
}

cols = st.columns(3)

for i, (name, ticker) in enumerate(market_tickers.items()):
    col = cols[i % 3]
    data = get_stock_data(ticker, start_date, load_end_date)

    with col:
        if data is not None and not data.empty and "Close" in data.columns:
            try:
                close_series = data["Close"].dropna()
                if len(close_series) < 2:
                    st.warning(f"'{name}' 비교 가능한 데이터가 부족합니다.")
                    continue

                last_price = to_float(close_series.iloc[-1])
                prev_price = to_float(close_series.iloc[-2])

                delta = last_price - prev_price
                delta_pct = (delta / prev_price) * 100 if prev_price != 0 else 0

                st.metric(
                    label=name,
                    value=f"{last_price:,.2f}",
                    delta=f"{delta:,.2f} ({delta_pct:.2f}%)",
                )

                fig = plot_advanced_chart(data, name)
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            except Exception as e:
                st.error(f"데이터 처리 중 오류: {e}")
        else:
            st.error(f"'{name}' 데이터 로드 실패")

st.markdown("---")


# ---------------------------------------------------------
# 4. 한국 주식 목록 및 검색 기능
# ---------------------------------------------------------
@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def get_krx_dict():
    try:
        df = fdr.StockListing("KRX")
        stock_dict = {}

        for _, row in df.iterrows():
            name = row.get("Name")
            code = row.get("Code")
            market = row.get("Market")

            if not name or pd.isna(code):
                continue

            code = str(code).strip()
            if code.isdigit():
                code = code.zfill(6)

            market_text = str(market).upper()
            if "KOSPI" in market_text:
                yahoo_code = code + ".KS"
            elif "KOSDAQ" in market_text:
                yahoo_code = code + ".KQ"
            else:
                continue

            stock_dict[f"{name} ({code})"] = yahoo_code

        return stock_dict
    except Exception:
        return {}


def build_krx_lookup(stock_dict):
    """일괄 입력 해석을 위한 한국 종목 검색용 사전을 만듭니다."""
    display_to_ticker = dict(stock_dict)
    code_to_item = {}
    name_to_items = {}

    for display_name, yahoo_code in stock_dict.items():
        match = re.match(r"^(.+)\s+\((\d{6})\)$", display_name)
        if not match:
            continue

        stock_name = match.group(1).strip()
        stock_code = match.group(2).strip()

        code_to_item[stock_code] = (yahoo_code, display_name)
        name_to_items.setdefault(stock_name, []).append((yahoo_code, display_name))

    return display_to_ticker, code_to_item, name_to_items


def parse_bulk_input(text, stock_dict, max_items=20):
    """종목명, 한국 종목코드, 해외 티커를 한꺼번에 입력받아 분석 대상 목록으로 변환합니다."""
    display_to_ticker, code_to_item, name_to_items = build_krx_lookup(stock_dict)

    raw_tokens = re.split(r"[\n,;\t]+", text or "")
    targets = []
    failed = []
    seen = set()

    for raw_token in raw_tokens:
        token = raw_token.strip()
        token = re.sub(r"^[\-•·*\d\.\)\s]+", "", token).strip()
        token = token.strip("'\"`[]{}")

        if not token:
            continue

        if len(targets) >= max_items:
            failed.append(f"{token} 외 추가 입력은 최대 {max_items}개 제한으로 제외")
            continue

        # 1. 드롭다운 표시명 그대로 붙여넣은 경우: 삼성전자 (005930)
        if token in display_to_ticker:
            add_target(targets, display_to_ticker[token], token, seen)
            continue

        # 2. 텍스트 안에 6자리 한국 종목코드가 들어 있는 경우
        code_match = re.search(r"(?<!\d)(\d{6})(?!\d)", token)
        if code_match:
            stock_code = code_match.group(1)
            if stock_code in code_to_item:
                yahoo_code, display_name = code_to_item[stock_code]
                add_target(targets, yahoo_code, display_name, seen)
            else:
                failed.append(f"{token} (KRX 코드 확인 실패)")
            continue

        # 3. 한국 종목명을 정확히 입력한 경우
        if token in name_to_items:
            candidates = name_to_items[token]
            if len(candidates) == 1:
                yahoo_code, display_name = candidates[0]
                add_target(targets, yahoo_code, display_name, seen)
            else:
                failed.append(f"{token} (동일 종목명 후보 {len(candidates)}개)")
            continue

        # 4. 해외 티커로 보이는 경우
        ticker_like = re.fullmatch(r"[A-Za-z0-9\^\.\-=]{1,20}", token)
        if ticker_like:
            ticker = token.upper()
            add_target(targets, ticker, ticker, seen)
            continue

        failed.append(f"{token} (인식 실패)")

    return targets, failed


krx_stock_dict = get_krx_dict()

# ---------------------------------------------------------
# 5. 관심 종목 비교 분석
# ---------------------------------------------------------
st.subheader("🔎 관심 종목 상세 분석")

col_search1, col_search2 = st.columns(2)
with col_search1:
    selected_korea = st.multiselect("🇰🇷 한국 주식", list(krx_stock_dict.keys()))
with col_search2:
    manual_input = st.text_input("🇺🇸 해외 티커 간단 입력", placeholder="예: TSLA, AAPL")

with st.expander("📋 종목 일괄 입력으로 한꺼번에 차트 보기", expanded=True):
    st.caption("종목명, 6자리 종목코드, 해외 티커를 줄바꿈 또는 쉼표로 입력한 뒤 [일괄 입력 적용]을 누르세요.")

    example_text = "삼성전자\nSK하이닉스\n005930\nAAPL\nTSLA"

    with st.form("bulk_stock_form", clear_on_submit=False):
        bulk_input = st.text_area(
            "종목 일괄 입력",
            value=st.session_state.get("bulk_input", ""),
            placeholder=example_text,
            height=140,
        )
        submitted = st.form_submit_button("📋 일괄 입력 적용")

    if submitted:
        bulk_targets, bulk_failed = parse_bulk_input(bulk_input, krx_stock_dict, max_items=20)
        st.session_state["bulk_input"] = bulk_input
        st.session_state["bulk_targets"] = bulk_targets
        st.session_state["bulk_failed"] = bulk_failed

    bulk_targets = st.session_state.get("bulk_targets", [])
    bulk_failed = st.session_state.get("bulk_failed", [])

    if bulk_targets:
        recognized_names = ", ".join([name for _, name in bulk_targets])
        st.success(f"인식된 종목 {len(bulk_targets)}개: {recognized_names}")

    if bulk_failed:
        st.warning("인식하지 못한 항목: " + ", ".join(bulk_failed[:10]))

    if st.button("🧹 일괄 입력 결과 초기화"):
        st.session_state["bulk_targets"] = []
        st.session_state["bulk_failed"] = []
        st.session_state["bulk_input"] = ""
        st.rerun()

# 분석할 종목 리스트 생성
analysis_targets = []
seen_tickers = set()

for item in selected_korea:
    add_target(analysis_targets, krx_stock_dict[item], item, seen_tickers)

if manual_input:
    for code in re.split(r"[,;\n\t]+", manual_input):
        ticker = code.strip().upper()
        if ticker:
            add_target(analysis_targets, ticker, ticker, seen_tickers)

for ticker, label in st.session_state.get("bulk_targets", []):
    add_target(analysis_targets, ticker, label, seen_tickers)

if analysis_targets:
    st.info(f"총 {len(analysis_targets)}개 종목의 차트를 표시합니다.")

    chart_cols = st.columns(2)
    for i, (code, display_name) in enumerate(analysis_targets):
        with chart_cols[i % 2]:
            with st.spinner(f"{display_name} 데이터 불러오는 중..."):
                df = get_stock_data(code, start_date, load_end_date)

            if df is not None and not df.empty:
                fig = plot_advanced_chart(df, display_name, color="green")
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            else:
                st.warning(f"{display_name} 데이터 없음 또는 티커 확인 필요")
else:
    st.info("종목을 선택하거나 일괄 입력을 적용하면 차트가 표시됩니다.")

st.markdown("---")
st.caption("본 대시보드는 참고용 정보 제공 도구이며, 투자 권유 또는 매매 추천이 아닙니다.")
