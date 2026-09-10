"""
signals.py
Mengambil data riil (Yahoo Finance, ticker format XXXX.JK untuk BEI),
menghitung indikator teknikal (EMA, RSI, MACD, Volume, Fibonacci),
lalu menghasilkan sinyal BUY/HOLD/SELL beserta trading plan lengkap.
"""

import pandas as pd
import yfinance as yf

from liquidity_filter import is_liquid


def to_yf_ticker(ticker: str) -> str:
    """Pastikan ticker berformat Yahoo Finance, contoh: BUMI -> BUMI.JK"""
    ticker = ticker.strip().upper()
    if not ticker.endswith(".JK"):
        ticker += ".JK"
    return ticker


def fetch_stock_data(ticker: str, period: str = "1y"):
    """Ambil data historis harian dari Yahoo Finance."""
    yf_ticker = to_yf_ticker(ticker)
    df = yf.download(yf_ticker, period=period, interval="1d", progress=False, auto_adjust=True)

    if df is None or df.empty:
        return None

    # yfinance kadang mengembalikan kolom MultiIndex -> ratakan
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna()
    return df


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["EMA200"] = df["Close"].ewm(span=200, adjust=False).mean()
    df["Vol_MA20"] = df["Volume"].rolling(window=20).mean()

    # RSI 14
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0.0).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 1e-9)
    df["RSI14"] = 100 - (100 / (1 + rs))

    # MACD (12, 26, 9)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    return df


def _fibonacci_levels(df: pd.DataFrame, lookback: int = 50):
    recent = df.tail(lookback)
    high_val = float(recent["High"].max())
    low_val = float(recent["Low"].min())
    diff = high_val - low_val
    return {
        "high": high_val,
        "low": low_val,
        "fibo_382": high_val - 0.382 * diff,
        "fibo_50": high_val - 0.5 * diff,
        "fibo_618": high_val - 0.618 * diff,
        "fibo_786": high_val - 0.786 * diff,
    }


def generate_signal(ticker: str, min_rrr: float = 2.0):
    """
    Analisis lengkap satu saham: liquiditas -> tren -> trigger entry -> RRR.
    Return dict hasil analisis, atau dict dengan action="REJECTED"/"HOLD" jika tidak lolos.
    """
    df = fetch_stock_data(ticker)
    if df is None or len(df) < 60:
        return {"ticker": ticker, "action": "NO_DATA", "reason": "Data historis tidak cukup / ticker salah"}

    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    price = float(latest["Close"])
    avg_value = float((df["Close"] * df["Volume"]).tail(20).mean())
    avg_volume = float(df["Volume"].tail(20).mean())

    liquid, reason = is_liquid(price=price, avg_value=avg_value, avg_freq=avg_volume)
    if not liquid:
        return {"ticker": ticker, "action": "REJECTED", "reason": reason, "price": price}

    ema20, ema50 = float(latest["EMA20"]), float(latest["EMA50"])
    rsi = float(latest["RSI14"])
    macd, macd_sig = float(latest["MACD"]), float(latest["MACD_Signal"])
    prev_macd, prev_macd_sig = float(prev["MACD"]), float(prev["MACD_Signal"])
    volume, vol_ma = float(latest["Volume"]), float(latest["Vol_MA20"])

    is_uptrend = ema20 > ema50 and price > ema50
    is_rsi_healthy = 40 <= rsi <= 65
    is_macd_cross = prev_macd < prev_macd_sig and macd > macd_sig
    recent_high = float(df["Close"].iloc[-21:-1].max())
    is_breakout = price > recent_high
    is_vol_spike = vol_ma > 0 and volume > vol_ma * 1.5

    strategy = None
    if is_uptrend and is_rsi_healthy and is_macd_cross:
        strategy = "Uptrend Pullback / MACD Golden Cross"
    elif is_uptrend and is_breakout and is_vol_spike:
        strategy = "Volume Breakout"

    if strategy is None:
        action = "SELL" if price < ema50 else "HOLD"
        return {
            "ticker": ticker, "action": action, "price": price, "rsi": round(rsi, 1),
            "reason": "Trend breakdown (di bawah EMA50)" if action == "SELL" else "Belum ada setup valid",
        }

    fibo = _fibonacci_levels(df)
    entry_price = price
    stop_loss = round(fibo["fibo_618"] * 0.98)
    risk = entry_price - stop_loss

    if risk <= 0:
        return {"ticker": ticker, "action": "HOLD", "price": price, "reason": "Perhitungan stop loss tidak valid"}

    tp1 = round(entry_price + risk * 2)
    tp2 = round(entry_price + risk * 3.5)
    rrr = round((tp1 - entry_price) / risk, 2)

    if rrr < min_rrr:
        return {
            "ticker": ticker, "action": "HOLD", "price": price,
            "reason": f"RRR {rrr} di bawah minimum {min_rrr} (sinyal ditolak, disiplin risk management)",
        }

    return {
        "ticker": ticker,
        "action": "BUY",
        "strategy": strategy,
        "price": round(entry_price),
        "rsi": round(rsi, 1),
        "entry_zone": f"{round(fibo['fibo_618'])} - {round(fibo['fibo_50'])}",
        "sl": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "rrr": rrr,
    }
