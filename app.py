from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from io import BytesIO
from typing import Iterable

import FinanceDataReader as fdr
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots


st.set_page_config(page_title="경제 대시보드 + VCP 차트", layout="wide")


MARKET_TICKERS = [
    {"name": "KOSPI", "symbol": "KS11", "provider": "fdr"},
    {"name": "KOSDAQ", "symbol": "KQ11", "provider": "fdr"},
    {"name": "S&P 500 선물", "symbol": "ES=F", "provider": "yf"},
    {"name": "NASDAQ 선물", "symbol": "NQ=F", "provider": "yf"},
    {"name": "Gold 선물", "symbol": "GC=F", "provider": "yf"},
    {"name": "WTI Crude Oil", "symbol": "CL=F", "provider": "yf"},
    {"name": "Bitcoin", "symbol": "BTC-USD", "provider": "yf"},
    {"name": "US 10Y Bond", "symbol": "^TNX", "provider": "yf"},
    {"name": "USD/KRW", "symbol": "KRW=X", "provider": "yf"},
    {"name": "VIX", "symbol": "^VIX", "provider": "yf"},
]

REQUIRED_VCP_COLUMNS = {
    "ticker",
    "name",
    "vcp_phase",
    "vcp_phase_label",
    "pivot_price",
    "pivot_distance_pct",
}


def to_float(value, default: float | None = None) -> float | None:
    if isinstance(value, pd.Series):
        value = value.iloc[0]
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def normalize_ticker(value) -> str:
    ticker = str(value).strip()
    if not ticker or ticker.lower() == "nan":
        return ""
    if re.fullmatch(r"\d{1,6}", ticker):
        return ticker.zfill(6)
    return ticker.upper()


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    frame = _flatten_columns(df).copy()
    frame = frame.rename(columns={str(col): str(col).lower() for col in frame.columns})

    if "date" not in frame.columns:
        index_name = frame.index.name or "date"
        frame = frame.reset_index().rename(columns={index_name: "date", "index": "date"})

    rename_map = {
        "adj close": "adj_close",
        "change": "change",
    }
    frame = frame.rename(columns=rename_map)

    required = ["date", "open", "high", "low", "close"]
    if not set(required).issubset(frame.columns):
        return pd.DataFrame()

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    if "volume" not in frame.columns:
        frame["volume"] = 0

    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    frame = frame.sort_values("date")
    return frame[["date", "open", "high", "low", "close", "volume"]].reset_index(drop=True)


def _trading_day_xaxis(frame: pd.DataFrame) -> dict[str, object]:
    return {
        "type": "category",
        "categoryorder": "array",
        "categoryarray": frame["date_label"].tolist(),
    }


def _volume_colors(frame: pd.DataFrame) -> list[str]:
    return [
        "#2f9e73" if close >= open_ else "#ef553b"
        for open_, close in zip(frame["open"], frame["close"])
    ]


def resample_weekly(prices: pd.DataFrame) -> pd.DataFrame:
    if prices.empty:
        return pd.DataFrame()

    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date")
    if frame.empty:
        return pd.DataFrame()

    return (
        frame.set_index("date")
        .resample("W-FRI")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )


def make_price_volume_chart(
    prices: pd.DataFrame,
    title: str,
    volume_title: str = "Volume",
    moving_average_windows: tuple[int, ...] = (20, 50),
    pivot_price: float | None = None,
    pivot_distance_pct: float | None = None,
    vcp_phase_label: str | None = None,
) -> go.Figure:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.73, 0.27],
        subplot_titles=(title, volume_title),
    )

    required_columns = {"date", "open", "high", "low", "close", "volume"}
    if prices.empty or not required_columns.issubset(prices.columns):
        fig.update_layout(title=f"{title} - 가격/거래량 데이터를 불러오지 못했습니다.")
        return fig

    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date")
    frame["date_label"] = frame["date"].dt.strftime("%Y-%m-%d")
    if frame.empty:
        fig.update_layout(title=f"{title} - 가격/거래량 데이터를 불러오지 못했습니다.")
        return fig

    fig.add_trace(
        go.Candlestick(
            x=frame["date_label"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            name=title,
        ),
        row=1,
        col=1,
    )

    close = frame["close"]
    for window in moving_average_windows:
        if len(close) >= window:
            fig.add_trace(
                go.Scatter(
                    x=frame["date_label"],
                    y=close.rolling(window).mean(),
                    mode="lines",
                    name=f"MA{window}",
                    line={"width": 1.2},
                ),
                row=1,
                col=1,
            )

    if pivot_price is not None and pd.notna(pivot_price):
        distance_text = ""
        if pivot_distance_pct is not None and pd.notna(pivot_distance_pct):
            distance_text = f" ({pivot_distance_pct:+.1f}%)"
        phase_text = f" - {vcp_phase_label}" if vcp_phase_label else ""
        fig.add_hline(
            y=float(pivot_price),
            row=1,
            col=1,
            line_dash="dash",
            line_color="#f08c00",
            line_width=1.4,
            annotation_text=f"Pivot {float(pivot_price):,.0f}{distance_text}{phase_text}",
            annotation_position="top left",
        )

        fig.add_trace(
            go.Scatter(
                x=[frame["date_label"].iloc[-1]],
                y=[float(close.iloc[-1])],
                mode="markers+text",
                marker={"size": 9, "color": "#222222"},
                text=["현재가"],
                textposition="bottom right",
                name="현재가",
            ),
            row=1,
            col=1,
        )

    volume = pd.to_numeric(frame["volume"], errors="coerce").fillna(0)
    fig.add_trace(
        go.Bar(
            x=frame["date_label"],
            y=volume,
            marker_color=_volume_colors(frame),
            name="Volume",
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    shared_xaxis = _trading_day_xaxis(frame)
    fig.update_xaxes(**shared_xaxis, rangeslider_visible=False, row=1, col=1)
    fig.update_xaxes(**shared_xaxis, row=2, col=1)
    fig.update_layout(
        height=760,
        hovermode="x unified",
        bargap=0.15,
        margin={"l": 24, "r": 24, "t": 56, "b": 24},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
    )
    return fig


def make_line_chart(df: pd.DataFrame, title: str, color: str = "royalblue") -> go.Figure:
    frame = normalize_price_frame(df)
    if frame.empty:
        return go.Figure()

    last_price = to_float(frame["close"].iloc[-1])
    y_min = to_float(frame["close"].min())
    y_max = to_float(frame["close"].max())
    if last_price is None or y_min is None or y_max is None:
        return go.Figure()

    padding = (y_max - y_min) * 0.1 if y_max != y_min else abs(y_max) * 0.01
    if padding == 0:
        padding = 1

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frame["date"],
            y=frame["close"],
            mode="lines",
            name=title,
            line={"color": color, "width": 2},
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
        title={"text": title, "font": {"size": 14}},
        height=220,
        margin={"l": 10, "r": 10, "t": 35, "b": 20},
        template="plotly_white",
        yaxis={"range": [y_min - padding, y_max + padding], "showgrid": True, "fixedrange": False},
        xaxis={"showgrid": False, "tickformat": "%Y-%m-%d", "nticks": 5},
    )
    return fig


def _download_yfinance(ticker: str, start: datetime, end: datetime, retries: int = 2) -> pd.DataFrame:
    for attempt in range(retries + 1):
        try:
            df = yf.download(ticker, start=start, end=end, progress=False, interval="1d", auto_adjust=False)
            frame = normalize_price_frame(df)
            if not frame.empty:
                return frame
        except Exception:
            pass
        if attempt < retries:
            time.sleep(0.6 * (attempt + 1))
    return pd.DataFrame()


@st.cache_data(ttl=60 * 30, show_spinner=False)
def get_market_history(symbol: str, provider: str, start: datetime, end: datetime) -> pd.DataFrame:
    if provider == "fdr":
        try:
            return normalize_price_frame(fdr.DataReader(symbol, start, end))
        except Exception:
            return pd.DataFrame()
    return _download_yfinance(symbol, start, end)


@st.cache_data(ttl=60 * 30, show_spinner=False)
def get_stock_history(ticker: str, start: datetime, end: datetime) -> pd.DataFrame:
    normalized = normalize_ticker(ticker)
    if not normalized:
        return pd.DataFrame()

    if re.fullmatch(r"\d{6}", normalized):
        try:
            frame = normalize_price_frame(fdr.DataReader(normalized, start, end))
            if not frame.empty:
                return frame
        except Exception:
            pass

        for suffix in [".KS", ".KQ"]:
            frame = _download_yfinance(normalized + suffix, start, end)
            if not frame.empty:
                return frame
        return pd.DataFrame()

    return _download_yfinance(normalized, start, end)


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def get_krx_dict() -> dict[str, str]:
    try:
        listing = fdr.StockListing("KRX")
    except Exception:
        return {}

    symbol_col = "Code" if "Code" in listing.columns else "Symbol"
    name_col = "Name"
    market_col = "Market" if "Market" in listing.columns else None
    stock_dict = {}

    for _, row in listing.iterrows():
        name = row.get(name_col)
        code = row.get(symbol_col)
        market = str(row.get(market_col, "")).upper() if market_col else ""
        if not name or pd.isna(code):
            continue

        code = str(code).strip().zfill(6)
        if not code.isdigit():
            continue

        if "KOSPI" in market:
            yahoo_code = code + ".KS"
        elif "KOSDAQ" in market:
            yahoo_code = code + ".KQ"
        else:
            yahoo_code = code

        stock_dict[f"{name} ({code})"] = yahoo_code
    return stock_dict


def build_krx_lookup(stock_dict: dict[str, str]):
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


def add_target(targets: list[tuple[str, str]], ticker: str, label: str, seen: set[str]) -> bool:
    normalized = normalize_ticker(ticker)
    if not normalized:
        return False
    key = normalized.upper()
    if key in seen:
        return False
    seen.add(key)
    targets.append((normalized, str(label).strip() or normalized))
    return True


def parse_bulk_input(text: str, stock_dict: dict[str, str], max_items: int = 20):
    display_to_ticker, code_to_item, name_to_items = build_krx_lookup(stock_dict)
    raw_tokens = re.split(r"[\n,;\t]+", text or "")
    targets = []
    failed = []
    seen = set()

    for raw_token in raw_tokens:
        token = raw_token.strip()
        token = re.sub(r"^[\-\d\.\)\s]+", "", token).strip()
        token = token.strip("'\"`[]{}")
        if not token:
            continue

        if len(targets) >= max_items:
            failed.append(f"{token} - 최대 {max_items}개 제한")
            continue

        if token in display_to_ticker:
            add_target(targets, display_to_ticker[token], token, seen)
            continue

        code_match = re.search(r"(?<!\d)(\d{6})(?!\d)", token)
        if code_match:
            stock_code = code_match.group(1)
            if stock_code in code_to_item:
                yahoo_code, display_name = code_to_item[stock_code]
                add_target(targets, yahoo_code, display_name, seen)
            else:
                add_target(targets, stock_code, stock_code, seen)
            continue

        if token in name_to_items:
            candidates = name_to_items[token]
            if len(candidates) == 1:
                yahoo_code, display_name = candidates[0]
                add_target(targets, yahoo_code, display_name, seen)
            else:
                failed.append(f"{token} - 같은 종목명 후보 {len(candidates)}개")
            continue

        ticker_like = re.fullmatch(r"[A-Za-z0-9\^\.\-=]{1,20}", token)
        if ticker_like:
            add_target(targets, token.upper(), token.upper(), seen)
            continue

        failed.append(f"{token} - 인식 실패")

    return targets, failed


def read_uploaded_csv(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.getvalue()
    for encoding in ["utf-8-sig", "utf-8", "cp949", "euc-kr"]:
        try:
            return pd.read_csv(BytesIO(raw), encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(BytesIO(raw))


def filter_vcp_phase_2(df: pd.DataFrame, selected_phases: Iterable[str]) -> pd.DataFrame:
    frame = df.copy()
    frame["ticker"] = frame["ticker"].map(normalize_ticker)
    frame["vcp_phase"] = frame["vcp_phase"].astype(str)
    frame["score"] = pd.to_numeric(frame.get("score"), errors="coerce")
    frame["stockeasy_rs"] = pd.to_numeric(frame.get("stockeasy_rs"), errors="coerce")
    phase_mask = frame["vcp_phase"].isin(selected_phases)
    return frame[phase_mask].sort_values(["score", "stockeasy_rs"], ascending=False, na_position="last")


def render_metric_chart(name: str, symbol: str, provider: str, start: datetime, end: datetime):
    data = get_market_history(symbol, provider, start, end)
    cache_key = f"last_market_{symbol}"

    if data.empty and cache_key in st.session_state:
        data = st.session_state[cache_key]
        st.caption("이번 로드는 실패해 현재 세션의 마지막 성공 데이터를 표시합니다.")
    elif not data.empty:
        st.session_state[cache_key] = data

    if data.empty:
        st.error(f"{name} 데이터 로드 실패")
        return

    close = data["close"].dropna()
    if len(close) < 2:
        st.warning(f"{name} 비교 가능한 데이터가 부족합니다.")
        return

    last_price = to_float(close.iloc[-1], 0) or 0
    prev_price = to_float(close.iloc[-2], last_price) or last_price
    delta = last_price - prev_price
    delta_pct = (delta / prev_price) * 100 if prev_price else 0

    st.metric(name, f"{last_price:,.2f}", f"{delta:,.2f} ({delta_pct:.2f}%)")
    st.plotly_chart(make_line_chart(data, name), use_container_width=True, config={"displayModeBar": False})


st.title("경제 대시보드 + VCP 후보 차트")

link_col1, link_col2 = st.columns(2)
with link_col1:
    st.link_button(
        "OECD 경기선행지수 보기",
        "https://www.oecd.org/en/data/indicators/composite-leading-indicator-cli.html",
    )
with link_col2:
    st.link_button(
        "관세청 수출입 무역통계 보기",
        "https://unipass.customs.go.kr/ets/",
    )

with st.sidebar:
    st.header("설정")
    default_start = datetime.now() - timedelta(days=365)
    default_end = datetime.now()
    start_date = st.date_input("시작일", default_start)
    end_date = st.date_input("종료일", default_end)
    st.markdown("---")
    st.caption("주요 지표는 30분 캐시와 간단한 재시도를 적용합니다.")

if start_date >= end_date:
    st.error("시작일은 종료일보다 앞선 날짜여야 합니다.")
    st.stop()

start_dt = datetime.combine(start_date, datetime.min.time())
end_dt = datetime.combine(end_date + timedelta(days=1), datetime.min.time())

tab_vcp, tab_market, tab_manual = st.tabs(["VCP CSV 차트", "주요 경제지표", "관심 종목"])

with tab_vcp:
    st.subheader("Stock Trend Radar CSV 업로드")
    uploaded_file = st.file_uploader(
        "CSV 파일을 업로드하면 VCP 2번대 종목을 필터링하고 프로젝트와 같은 캔들+거래량 차트를 생성합니다.",
        type=["csv"],
    )

    if uploaded_file is None:
        st.info("Stock Trend Radar에서 내려받은 CSV 파일을 업로드하세요.")
    else:
        try:
            uploaded_df = read_uploaded_csv(uploaded_file)
        except Exception as exc:
            st.error(f"CSV를 읽지 못했습니다: {exc}")
            st.stop()

        missing = sorted(REQUIRED_VCP_COLUMNS - set(uploaded_df.columns))
        if missing:
            st.error("CSV에 필요한 컬럼이 없습니다: " + ", ".join(missing))
            st.stop()

        phase_options = sorted(
            [phase for phase in uploaded_df["vcp_phase"].dropna().astype(str).unique() if phase.startswith("2.")]
        )
        if not phase_options:
            st.warning("이 CSV에는 vcp_phase가 2번대로 시작하는 종목이 없습니다.")
            st.stop()

        left, right = st.columns([2, 1])
        with left:
            selected_phases = st.multiselect("표시할 VCP 단계", phase_options, default=phase_options)
        with right:
            max_rows = st.slider("표 후보 수", 5, 100, 30, 5)

        vcp_df = filter_vcp_phase_2(uploaded_df, selected_phases).head(max_rows)
        if vcp_df.empty:
            st.warning("선택한 VCP 단계에 해당하는 종목이 없습니다.")
            st.stop()

        display_cols = [
            col
            for col in [
                "name",
                "ticker",
                "score",
                "stockeasy_rs",
                "rs_1m",
                "rs_3m",
                "rs_6m",
                "vcp_phase",
                "vcp_phase_label",
                "pivot_price",
                "pivot_distance_pct",
                "pivot_timing_label",
                "reasons",
            ]
            if col in vcp_df.columns
        ]
        st.dataframe(vcp_df[display_cols], use_container_width=True, hide_index=True)

        labels = (vcp_df["name"].astype(str) + " (" + vcp_df["ticker"].astype(str) + ")").tolist()
        selected_label = st.selectbox("차트를 볼 종목", labels)
        selected = vcp_df.iloc[labels.index(selected_label)]

        chart_data = get_stock_history(selected["ticker"], start_dt, end_dt)
        if chart_data.empty:
            st.error(f"{selected['name']} ({selected['ticker']}) 가격 데이터를 불러오지 못했습니다.")
        else:
            daily_tab, weekly_tab = st.tabs(["일봉", "주봉"])
            chart_title = f"{selected['name']} ({selected['ticker']})"
            pivot_price = to_float(selected.get("pivot_price"))
            pivot_distance_pct = to_float(selected.get("pivot_distance_pct"))
            phase_label = str(selected.get("vcp_phase_label", ""))

            with daily_tab:
                st.plotly_chart(
                    make_price_volume_chart(
                        chart_data,
                        chart_title,
                        "거래량",
                        pivot_price=pivot_price,
                        pivot_distance_pct=pivot_distance_pct,
                        vcp_phase_label=phase_label,
                    ),
                    use_container_width=True,
                )

            with weekly_tab:
                weekly = resample_weekly(chart_data)
                st.plotly_chart(
                    make_price_volume_chart(
                        weekly,
                        chart_title + " 주봉",
                        "주간 거래량",
                        moving_average_windows=(10, 30),
                        pivot_price=pivot_price,
                        pivot_distance_pct=pivot_distance_pct,
                        vcp_phase_label=phase_label,
                    ),
                    use_container_width=True,
                )

            metric_cols = st.columns(4)
            metric_cols[0].metric("총점", f"{to_float(selected.get('score'), 0):.1f}")
            metric_cols[1].metric("StockEasy RS", f"{to_float(selected.get('stockeasy_rs'), 0):.1f}")
            metric_cols[2].metric("Pivot", f"{pivot_price:,.0f}" if pivot_price else "-")
            metric_cols[3].metric("Pivot 거리", f"{pivot_distance_pct:+.1f}%" if pivot_distance_pct is not None else "-")

            if "vcp_watch_point" in selected:
                st.write("관찰 포인트:", selected.get("vcp_watch_point"))
            if "breakout_note" in selected:
                st.write("돌파 메모:", selected.get("breakout_note"))

with tab_market:
    st.subheader("주요 경제지표")
    cols = st.columns(3)
    for i, item in enumerate(MARKET_TICKERS):
        with cols[i % 3]:
            render_metric_chart(item["name"], item["symbol"], item["provider"], start_dt, end_dt)

with tab_manual:
    st.subheader("관심 종목 상세 분석")
    krx_stock_dict = get_krx_dict()

    col_search1, col_search2 = st.columns(2)
    with col_search1:
        selected_korea = st.multiselect("한국 주식", list(krx_stock_dict.keys()))
    with col_search2:
        manual_input = st.text_input("해외 티커 또는 6자리 종목코드", placeholder="AAPL, TSLA, 005930")

    with st.expander("여러 종목 한 번에 입력", expanded=True):
        example_text = "삼성전자\nSK하이닉스\n005930\nAAPL\nTSLA"
        with st.form("bulk_stock_form", clear_on_submit=False):
            bulk_input = st.text_area(
                "종목명, 6자리 코드, 해외 티커를 줄바꿈 또는 쉼표로 입력",
                value=st.session_state.get("bulk_input", ""),
                placeholder=example_text,
                height=140,
            )
            submitted = st.form_submit_button("입력 적용")

        if submitted:
            bulk_targets, bulk_failed = parse_bulk_input(bulk_input, krx_stock_dict, max_items=20)
            st.session_state["bulk_input"] = bulk_input
            st.session_state["bulk_targets"] = bulk_targets
            st.session_state["bulk_failed"] = bulk_failed

        bulk_targets = st.session_state.get("bulk_targets", [])
        bulk_failed = st.session_state.get("bulk_failed", [])
        if bulk_targets:
            st.success("인식된 종목: " + ", ".join([name for _, name in bulk_targets]))
        if bulk_failed:
            st.warning("인식하지 못한 항목: " + ", ".join(bulk_failed[:10]))
        if st.button("입력 결과 초기화"):
            st.session_state["bulk_targets"] = []
            st.session_state["bulk_failed"] = []
            st.session_state["bulk_input"] = ""
            st.rerun()

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
                with st.spinner(f"{display_name} 데이터를 불러오는 중..."):
                    df = get_stock_history(code, start_dt, end_dt)
                if not df.empty:
                    st.plotly_chart(
                        make_price_volume_chart(df, display_name, "거래량"),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    st.warning(f"{display_name} 데이터가 없습니다. 종목코드 또는 티커를 확인하세요.")
    else:
        st.info("종목을 선택하거나 입력하면 차트가 표시됩니다.")

st.markdown("---")
st.caption("본 대시보드는 참고용 정보 제공 도구이며, 투자 권유 또는 매매 추천이 아닙니다.")
