"""
KOSPI 시가총액 상위 30종목 데이터 수집 모듈
- Top 30 종목: FinanceDataReader → pykrx → 하드코딩 fallback
- 월봉 종가: yfinance(2001년~) → pykrx → FinanceDataReader
"""

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta


# Fallback: 2025년 1월 기준 KOSPI 시가총액 상위 30종목
# Streamlit Cloud 등 해외 서버에서 KRX 접근이 불가능할 때 사용
FALLBACK_TOP30 = [
    ("005930", "삼성전자", 400),
    ("000660", "SK하이닉스", 180),
    ("005380", "현대차", 55),
    ("373220", "LG에너지솔루션", 95),
    ("005935", "삼성전자우", 45),
    ("000270", "기아", 40),
    ("068270", "셀트리온", 35),
    ("105560", "KB금융", 32),
    ("055550", "신한지주", 28),
    ("035420", "NAVER", 27),
    ("028260", "삼성물산", 26),
    ("003670", "포스코홀딩스", 25),
    ("012330", "현대모비스", 24),
    ("035720", "카카오", 22),
    ("066570", "LG전자", 21),
    ("086790", "하나금융지주", 20),
    ("051910", "LG화학", 19),
    ("006400", "삼성SDI", 18),
    ("032830", "삼성생명", 17),
    ("003550", "LG", 16),
    ("096770", "SK이노베이션", 15),
    ("017670", "SK텔레콤", 14),
    ("030200", "KT", 13),
    ("034730", "SK", 12),
    ("009150", "삼성전기", 11),
    ("018260", "삼성에스디에스", 10),
    ("010130", "고려아연", 9),
    ("033780", "KT&G", 8),
    ("011200", "HMM", 7),
    ("316140", "우리금융지주", 6),
]


def get_latest_trading_date():
    """가장 최근 거래일을 반환 (주말 제외)"""
    today = datetime.today()
    # 주말이면 금요일로 이동
    if today.weekday() == 5:  # 토요일
        today -= timedelta(days=1)
    elif today.weekday() == 6:  # 일요일
        today -= timedelta(days=2)
    return today.strftime("%Y%m%d")


@st.cache_data(ttl=3600)
def get_top30_kospi_stocks():
    """
    KOSPI 시가총액 상위 30종목 조회
    Returns: DataFrame with columns [종목코드, 종목명, 시가총액, 시가총액(조)]
    """

    # 1차: FinanceDataReader 시도 (안정적)
    try:
        import FinanceDataReader as fdr

        df = fdr.StockListing("KOSPI")
        if not df.empty:
            if "Marcap" in df.columns:
                cap_col = "Marcap"
            elif "시가총액" in df.columns:
                cap_col = "시가총액"
            else:
                cap_col = None

            if cap_col:
                df = df.sort_values(cap_col, ascending=False).head(30)

                result = pd.DataFrame()
                result["종목코드"] = df["Code"].values if "Code" in df.columns else df.index
                result["종목명"] = df["Name"].values if "Name" in df.columns else df["종목명"].values
                result["시가총액"] = df[cap_col].values
                result["시가총액(조)"] = (result["시가총액"] / 1e12).round(1)
                return result.reset_index(drop=True)
    except Exception as e:
        st.warning(f"FinanceDataReader 데이터 조회 실패: {e}")

    # 2차: pykrx 시도
    date = get_latest_trading_date()
    try:
        from pykrx import stock as pykrx_stock

        df = pykrx_stock.get_market_cap(date, market="KOSPI")
        if df.empty:
            prev_date = (datetime.strptime(date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
            df = pykrx_stock.get_market_cap(prev_date, market="KOSPI")

        if not df.empty:
            df = df.sort_values("시가총액", ascending=False).head(30)
            df = df.reset_index()
            ticker_col = df.columns[0]
            df_result = pd.DataFrame()
            df_result["종목코드"] = df[ticker_col]

            names = []
            for ticker in df_result["종목코드"]:
                name = pykrx_stock.get_market_ticker_name(ticker)
                names.append(name)
            df_result["종목명"] = names
            df_result["시가총액"] = df["시가총액"].values
            df_result["시가총액(조)"] = (df_result["시가총액"] / 1e12).round(1)
            return df_result.reset_index(drop=True)
    except Exception as e:
        st.warning(f"pykrx 데이터 조회 실패: {e}")

    # 3차: Fallback - 하드코딩된 종목 리스트 사용
    st.info("실시간 데이터 조회 실패. 기본 종목 리스트를 사용합니다.")
    fallback_df = pd.DataFrame(FALLBACK_TOP30, columns=["종목코드", "종목명", "시가총액(조)"])
    fallback_df["시가총액"] = fallback_df["시가총액(조)"] * 1e12
    return fallback_df[["종목코드", "종목명", "시가총액", "시가총액(조)"]]


@st.cache_data(ttl=3600)
def get_stock_ohlcv(ticker, period_years=1):
    """
    종목의 일별 OHLCV 데이터 조회
    Args:
        ticker: 종목코드 (예: '005930')
        period_years: 조회 기간 (년)
    Returns: DataFrame with columns [시가, 고가, 저가, 종가, 거래량]
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=int(period_years * 365))
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    # 1차: pykrx 시도
    try:
        from pykrx import stock as pykrx_stock

        df = pykrx_stock.get_market_ohlcv(start_str, end_str, ticker)
        if not df.empty:
            df.index.name = "날짜"
            # 컬럼명 통일
            col_map = {"시가": "시가", "고가": "고가", "저가": "저가", "종가": "종가", "거래량": "거래량"}
            df = df.rename(columns=col_map)
            return df[["시가", "고가", "저가", "종가", "거래량"]]
    except Exception as e:
        st.warning(f"pykrx OHLCV 조회 실패: {e}")

    # 2차: FinanceDataReader 시도
    try:
        import FinanceDataReader as fdr

        df = fdr.DataReader(ticker, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        if not df.empty:
            result = pd.DataFrame(index=df.index)
            result.index.name = "날짜"
            result["시가"] = df["Open"]
            result["고가"] = df["High"]
            result["저가"] = df["Low"]
            result["종가"] = df["Close"]
            result["거래량"] = df["Volume"]
            return result
    except Exception as e:
        st.warning(f"FinanceDataReader OHLCV 조회 실패: {e}")

    # 3차: yfinance 시도
    try:
        import yfinance as yf

        # 한국 주식은 .KS 접미사 사용
        yf_ticker = f"{ticker}.KS"
        stock = yf.Ticker(yf_ticker)
        df = stock.history(start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"))
        if not df.empty:
            result = pd.DataFrame(index=df.index)
            result.index.name = "날짜"
            result["시가"] = df["Open"]
            result["고가"] = df["High"]
            result["저가"] = df["Low"]
            result["종가"] = df["Close"]
            result["거래량"] = df["Volume"]
            return result
    except Exception as e:
        st.warning(f"yfinance OHLCV 조회 실패: {e}")

    st.error(f"종목 {ticker}의 OHLCV 데이터를 가져올 수 없습니다.")
    return pd.DataFrame(columns=["시가", "고가", "저가", "종가", "거래량"])


def resample_to_monthly(df):
    """일봉 데이터를 월봉으로 리샘플링"""
    if df.empty:
        return df

    monthly = df.resample("ME").agg({
        "시가": "first",
        "고가": "max",
        "저가": "min",
        "종가": "last",
        "거래량": "sum"
    }).dropna()

    return monthly


@st.cache_data(ttl=7200)
def get_kospi_index_monthly():
    """
    KOSPI 지수(^KS11)의 2001년 1월부터 현재까지 월봉 종가 데이터 조회
    Returns: DataFrame with columns ['종가'], index: 날짜 (월말)
    """
    start_date = datetime(2001, 1, 1)

    # 1차: yfinance 시도
    try:
        import yfinance as yf

        kospi = yf.Ticker("^KS11")
        df = kospi.history(start=start_date.strftime("%Y-%m-%d"), timeout=60)
        if df is not None and not df.empty and len(df) > 10:
            daily_df = pd.DataFrame({"종가": df["Close"].values}, index=df.index)
            if daily_df.index.tz is not None:
                daily_df.index = daily_df.index.tz_localize(None)
            daily_df.index.name = "날짜"
            monthly = daily_df.resample("ME").agg({"종가": "last"}).dropna()
            return monthly
    except Exception:
        pass

    # 2차: FinanceDataReader 시도
    try:
        import FinanceDataReader as fdr

        df = fdr.DataReader("KS11", start_date.strftime("%Y-%m-%d"))
        if df is not None and not df.empty and len(df) > 10:
            daily_df = pd.DataFrame({"종가": df["Close"].values}, index=df.index)
            daily_df.index.name = "날짜"
            monthly = daily_df.resample("ME").agg({"종가": "last"}).dropna()
            return monthly
    except Exception:
        pass

    return pd.DataFrame(columns=["종가"])


@st.cache_data(ttl=7200)
def get_stock_monthly_close(ticker):
    """
    종목의 2001년 1월부터 현재까지 월봉 종가 데이터 조회
    Args:
        ticker: 종목코드 (예: '005930')
    Returns: DataFrame with columns ['종가'], index: 날짜 (월말)
    """
    start_date = datetime(2001, 1, 1)
    end_date = datetime.today()
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")

    daily_df = pd.DataFrame()

    # 1차: yfinance 시도 (해외 서버에서 가장 안정적)
    try:
        import yfinance as yf

        yf_ticker = f"{ticker}.KS"
        stock = yf.Ticker(yf_ticker)
        df = stock.history(start=start_date.strftime("%Y-%m-%d"), timeout=60)
        if df is not None and not df.empty and len(df) > 10:
            daily_df = pd.DataFrame({"종가": df["Close"].values}, index=df.index)
            if daily_df.index.tz is not None:
                daily_df.index = daily_df.index.tz_localize(None)
            daily_df.index.name = "날짜"
    except Exception:
        pass

    # 2차: FinanceDataReader 시도
    if daily_df.empty:
        try:
            import FinanceDataReader as fdr

            df = fdr.DataReader(ticker, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
            if df is not None and not df.empty and len(df) > 10:
                daily_df = pd.DataFrame({"종가": df["Close"].values}, index=df.index)
                daily_df.index.name = "날짜"
        except Exception:
            pass

    # 3차: pykrx 시도 (한국 서버에서만 잘 동작)
    if daily_df.empty:
        try:
            from pykrx import stock as pykrx_stock

            df = pykrx_stock.get_market_ohlcv(start_str, end_str, ticker)
            if df is not None and not df.empty and len(df) > 10:
                df.index.name = "날짜"
                daily_df = df[["종가"]].copy()
        except Exception:
            pass

    if daily_df.empty:
        return pd.DataFrame(columns=["종가"])

    # 월봉으로 리샘플링 (월말 종가)
    monthly = daily_df.resample("ME").agg({"종가": "last"}).dropna()
    return monthly
