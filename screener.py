from __future__ import annotations
import pandas as pd
import numpy as np
import yfinance as yf

def _as_series(x: pd.Series | pd.DataFrame, name: str, index) -> pd.Series:
    """DataFrameで来ても1列目を取り出し、必ずSeriesで返す保険"""
    if isinstance(x, pd.DataFrame):
        x = x.iloc[:, 0]
    x = pd.Series(x, index=index, name=name)
    return x.astype(float)

def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = (delta.clip(lower=0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / (loss + 1e-9)
    out = 100 - (100 / (1 + rs))
    return _as_series(out, "RSI14", series.index)

def ema(series: pd.Series, span: int) -> pd.Series:
    out = series.ewm(span=span, adjust=False).mean()
    return _as_series(out, f"EMA{span}", series.index)

def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return (
        _as_series(macd_line, "MACD", close.index),
        _as_series(signal_line, "MACD_SIGNAL", close.index),
        _as_series(hist, "MACD_HIST", close.index),
    )

def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return _as_series(tr, "TR", high.index)

def adx_wilder(df: pd.DataFrame, period: int = 14):
    """Return Series: ADX, +DI, -DI, ATR (Wilder's)"""
    # yfinanceの列がMultiIndex化しても対応できるよう、確実にSeries化
    high = _as_series(df.loc[:, ("High" if "High" in df.columns else df.columns[df.columns.get_loc("High")])], "High", df.index)
    low  = _as_series(df.loc[:, ("Low"  if "Low"  in df.columns else df.columns[df.columns.get_loc("Low")])],  "Low",  df.index)
    close= _as_series(df.loc[:, ("Close"if "Close" in df.columns else df.columns[df.columns.get_loc("Close")])], "Close",df.index)

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm= down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    tr = _true_range(high, low, close)

    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di  = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr + 1e-9))
    minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / (atr + 1e-9))

    dx = 100 * ((plus_di - minus_di).abs() / ((plus_di + minus_di) + 1e-9))
    adx_val = dx.ewm(alpha=1/period, adjust=False).mean()

    # すべてSeriesで返す
    return (
        _as_series(adx_val, "ADX14", df.index),
        _as_series(plus_di, "+DI", df.index),
        _as_series(minus_di, "-DI", df.index),
        _as_series(atr, "ATR14", df.index),
    )

def fetch_ohlc(symbol: str, period: str = "1y") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval="1d", auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise ValueError(f"No data for {symbol}")
    # 列がMultiIndexになるケースに備え、可能ならフラット化
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [' '.join([str(c) for c in col if c!='']) for col in df.columns]
        # 代表列名を標準化
        ren = {}
        for name in df.columns:
            ln = name.lower()
            if "open" in ln:  ren[name] = "Open"
            if "high" in ln:  ren[name] = "High"
            if "low" in ln:   ren[name] = "Low"
            if "close" in ln and "adj" not in ln: ren[name] = "Close"
            if "adj close" in ln or ("close" in ln and "adj" in ln): ren[name] = "Adj Close"
            if "volume" in ln: ren[name] = "Volume"
        df = df.rename(columns=ren)
    return df.dropna()

def build_features(symbol: str) -> pd.DataFrame:
    df = fetch_ohlc(symbol)

    close = _as_series(df["Close"], "Close", df.index)
    volume = _as_series(df["Volume"], "Volume", df.index)

    df["SMA5"]  = close.rolling(5).mean()
    df["SMA25"] = close.rolling(25).mean()

    macd_line, signal_line, hist = macd(close)
    df["MACD"] = macd_line
    df["MACD_SIGNAL"] = signal_line
    df["MACD_HIST"] = hist

    df["RSI14"] = rsi(close, 14)

    adx_val, plus_di, minus_di, atr = adx_wilder(df, 14)
    df["ADX14"] = adx_val
    df["PLUS_DI"] = plus_di
    df["MINUS_DI"] = minus_di
    df["ATR14"] = atr
    df["ATR_PCT"] = df["ATR14"] / close * 100

    df["VOL20"] = volume.rolling(20).mean()

    return df.dropna()
