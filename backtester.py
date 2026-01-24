"""
Portfolio backtesting engine
"""

import pandas as pd
import numpy as np
import base64
import hashlib


def _kdf(s, n):
    h = hashlib.sha256(s.encode()).digest()
    return int.from_bytes(h[:4], 'big') % n


def _cfg():
    _r = base64.b64decode(b'eyJhIjoyLCJiIjoxMH0=')
    _d = __import__('json').loads(_r)
    return _d[chr(97)], _d[chr(98)]


def calculate_signals(monthly_df):
    df = monthly_df.copy()
    _p, _q = _cfg()
    _s = df[df.columns[0]].rolling(_p).mean()
    _l = df[df.columns[0]].rolling(_q).mean()
    _c = (_s > _l).astype(int)
    df["_x"] = _s
    df["_y"] = _l
    df["signal"] = _c
    df["position"] = _c.shift(1)
    df["buy"] = (_c == 1) & (_c.shift(1) == 0)
    df["sell"] = (_c == 0) & (_c.shift(1) == 1)
    return df


def get_current_signal(monthly_df):
    """Returns current position status: 1=buy active, 0=no position"""
    if monthly_df.empty or len(monthly_df) < 11:
        return None
    df = calculate_signals(monthly_df)
    last_signal = df["signal"].iloc[-1] if len(df) > 0 else None
    last_buy = df["buy"].iloc[-1] if len(df) > 0 else False
    last_sell = df["sell"].iloc[-1] if len(df) > 0 else False
    return {
        "position": int(last_signal) if last_signal is not None else 0,
        "new_buy": bool(last_buy),
        "new_sell": bool(last_sell)
    }


def backtest_stock(monthly_df):
    df = calculate_signals(monthly_df)
    df["monthly_return"] = df[df.columns[0]].pct_change()
    df["strategy_return"] = df["position"] * df["monthly_return"]
    df["cumulative"] = (1 + df["strategy_return"].fillna(0)).cumprod()

    trades = []
    _in = False
    _ed, _ep = None, None
    _col = df.columns[0]

    for i, row in df.iterrows():
        if row.get("buy") and not _in:
            _in = True
            _ed = i
            _ep = row[_col]
        elif row.get("sell") and _in:
            _xp = row[_col]
            _pnl = (_xp - _ep) / _ep * 100
            trades.append({
                "매수일": _ed, "매도일": i,
                "매수가": _ep, "매도가": _xp,
                "수익률(%)": round(_pnl, 2)
            })
            _in = False

    return {
        "signals_df": df,
        "returns": df["strategy_return"],
        "cumulative": df["cumulative"],
        "trades": trades
    }


def backtest_portfolio(all_monthly_data):
    N = 30
    _as = {}
    _ar = {}

    for name, mdf in all_monthly_data.items():
        if mdf.empty or len(mdf) < 11:
            continue
        df = calculate_signals(mdf)
        df["_mr"] = df[df.columns[0]].pct_change()
        _as[name] = df["position"]
        _ar[name] = df["_mr"]

    if not _as:
        return {
            "portfolio_returns": pd.Series(dtype=float),
            "portfolio_cumulative": pd.Series(dtype=float),
            "active_counts": pd.Series(dtype=int)
        }

    sdf = pd.DataFrame(_as)
    rdf = pd.DataFrame(_ar)
    cidx = sdf.index.intersection(rdf.index)
    sdf = sdf.loc[cidx]
    rdf = rdf.loc[cidx]

    active_counts = sdf.sum(axis=1)
    wr = (sdf * rdf).fillna(0)
    portfolio_returns = wr.sum(axis=1) / N
    portfolio_cumulative = (1 + portfolio_returns).cumprod()

    return {
        "portfolio_returns": portfolio_returns,
        "portfolio_cumulative": portfolio_cumulative,
        "active_counts": active_counts
    }


def calculate_metrics(returns_series, benchmark_series=None):
    returns = returns_series.dropna()
    if len(returns) == 0:
        return {}

    cumulative = (1 + returns).cumprod()
    total_return = cumulative.iloc[-1] - 1

    n_years = len(returns) / 12
    cagr = (cumulative.iloc[-1]) ** (1 / n_years) - 1 if n_years > 0 and cumulative.iloc[-1] > 0 else 0

    peak = cumulative.cummax()
    drawdown = (cumulative - peak) / peak
    mdd = drawdown.min()

    sharpe = (returns.mean() / returns.std()) * np.sqrt(12) if returns.std() > 0 else 0

    positive_months = (returns > 0).sum()
    total_months = len(returns[returns != 0])
    win_rate = positive_months / total_months * 100 if total_months > 0 else 0

    avg_win = returns[returns > 0].mean() if (returns > 0).any() else 0
    avg_loss = abs(returns[returns < 0].mean()) if (returns < 0).any() else 1
    profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0

    metrics = {
        "누적수익률(%)": round(total_return * 100, 2),
        "CAGR(%)": round(cagr * 100, 2),
        "MDD(%)": round(mdd * 100, 2),
        "샤프비율": round(sharpe, 2),
        "승률(%)": round(win_rate, 1),
        "손익비": round(profit_loss_ratio, 2),
    }

    if benchmark_series is not None:
        bm = benchmark_series.dropna()
        common = returns.index.intersection(bm.index)
        if len(common) > 0:
            bm_common = bm.loc[common]
            bm_cum = (1 + bm_common).cumprod()
            bm_total = bm_cum.iloc[-1] - 1
            bm_n_years = len(bm_common) / 12
            bm_cagr = (bm_cum.iloc[-1]) ** (1 / bm_n_years) - 1 if bm_n_years > 0 and bm_cum.iloc[-1] > 0 else 0
            bm_peak = bm_cum.cummax()
            bm_dd = (bm_cum - bm_peak) / bm_peak
            bm_mdd = bm_dd.min()
            bm_sharpe = (bm_common.mean() / bm_common.std()) * np.sqrt(12) if bm_common.std() > 0 else 0

            metrics["벤치마크 누적수익률(%)"] = round(bm_total * 100, 2)
            metrics["벤치마크 CAGR(%)"] = round(bm_cagr * 100, 2)
            metrics["벤치마크 MDD(%)"] = round(bm_mdd * 100, 2)
            metrics["벤치마크 샤프비율"] = round(bm_sharpe, 2)

    return metrics
