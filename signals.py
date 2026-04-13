from __future__ import annotations
from typing import Dict, List, Any
import pandas as pd


def _reason(key: str, label: str, point: int, status: str) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "point": point,
        "status": status,  # positive / negative / neutral
    }


def evaluate_signal(symbol: str, row_prev: pd.Series, row: pd.Series) -> Dict[str, Any]:
    score = 0
    reasons: List[Dict[str, Any]] = []

    # 1. 短期トレンド
    if row["SMA5"] > row["SMA25"]:
        score += 1
        reasons.append(_reason("trend_above_ma", "SMA5 > SMA25", 1, "positive"))
    else:
        reasons.append(_reason("trend_above_ma", "SMA5 <= SMA25", 0, "neutral"))

    # 2. 終値が25日線より上
    if row["Close"] > row["SMA25"]:
        score += 1
        reasons.append(_reason("close_above_sma25", "終値 > SMA25", 1, "positive"))
    else:
        reasons.append(_reason("close_above_sma25", "終値 <= SMA25", 0, "neutral"))

    # 3. ゴールデンクロス
    if (row_prev["SMA5"] <= row_prev["SMA25"]) and (row["SMA5"] > row["SMA25"]):
        score += 2
        reasons.append(_reason("golden_cross", "ゴールデンクロス", 2, "positive"))
    else:
        reasons.append(_reason("golden_cross", "GCなし", 0, "neutral"))

    # 4. MACD
    macd_bullish = (row["MACD"] > row["MACD_SIGNAL"]) and (row["MACD_HIST"] > row_prev["MACD_HIST"])
    if macd_bullish:
        score += 1
        reasons.append(_reason("macd_bullish", "MACD強気", 1, "positive"))
    else:
        reasons.append(_reason("macd_bullish", "MACD強気条件を満たさず", 0, "neutral"))

    # 5. RSI（強すぎず弱すぎず）
    if 50 <= row["RSI14"] <= 62:
        score += 1
        reasons.append(_reason("rsi_healthy", "RSIが健全レンジ", 1, "positive"))
    elif row["RSI14"] > 75:
        score -= 1
        reasons.append(_reason("rsi_overbought", "RSI過熱", -1, "negative"))
    elif row["RSI14"] < 30:
        score -= 1
        reasons.append(_reason("rsi_oversold", "RSI売られすぎ", -1, "negative"))
    else:
        reasons.append(_reason("rsi_mid", "RSI中立", 0, "neutral"))

    # 6. ADX
    adx_strong = (row["ADX14"] > 20) and (row["PLUS_DI"] > row["MINUS_DI"])
    if adx_strong:
        score += 1
        reasons.append(_reason("adx_trend", "ADX強気トレンド", 1, "positive"))
    elif row["ADX14"] < 15:
        score -= 1
        reasons.append(_reason("adx_weak", "ADXが弱くトレンド不明瞭", -1, "negative"))
    else:
        reasons.append(_reason("adx_trend", "ADX中立", 0, "neutral"))

    # 7. 出来高
    vol_ratio = float(row["Volume"] / row["VOL20"]) if row["VOL20"] else 0.0
    volume_strong = row["Volume"] > 2.0 * row["VOL20"]
    volume_good = row["Volume"] > 1.5 * row["VOL20"]

    if volume_strong:
        score += 2
        reasons.append(_reason("volume_strong", "出来高大幅増加", 2, "positive"))
    elif volume_good:
        score += 1
        reasons.append(_reason("volume_expansion", "出来高増加", 1, "positive"))
    elif row["Volume"] < 0.8 * row["VOL20"]:
        score -= 1
        reasons.append(_reason("volume_thin", "出来高不足", -1, "negative"))
    else:
        reasons.append(_reason("volume_neutral", "出来高は中立", 0, "neutral"))

    # 8. ボラティリティ
    if row["ATR_PCT"] > 5:
        score -= 1
        reasons.append(_reason("atr_risk", "ATR%が高く値動きが荒い", -1, "negative"))
    else:
        reasons.append(_reason("atr_risk", "ATR%は許容範囲", 0, "neutral"))

    # 9. 押し目反発の簡易判定
    if (
        row_prev["RSI14"] < 45
        and 45 <= row["RSI14"] <= 55
        and row["Close"] > row_prev["Close"]
    ):
        score += 1
        reasons.append(_reason("pullback_rebound", "押し目反発", 1, "positive"))
    else:
        reasons.append(_reason("pullback_rebound", "押し目反発条件を満たさず", 0, "neutral"))

    # 10. MACD + 出来高の同時強化
    if macd_bullish and volume_good:
        score += 1
        reasons.append(_reason("macd_volume_combo", "MACD強気 + 出来高増", 1, "positive"))
    else:
        reasons.append(_reason("macd_volume_combo", "MACDと出来高の同時強化なし", 0, "neutral"))

    # 最終判定
    if (score <= -2) or ((row["SMA5"] < row["SMA25"]) and (row["MACD"] < row["MACD_SIGNAL"])):
        judgement = "SELL"
    elif (
        score >= 6
        and row["ADX14"] >= 20
        and vol_ratio >= 1.5
        and row["RSI14"] <= 72
        and row["Close"] > row["SMA25"]
    ):
        judgement = "STRONG BUY"
    elif (
        score >= 4
        and row["ADX14"] >= 15
        and row["RSI14"] <= 68
        and vol_ratio >= 1.0
    ):
        judgement = "BUY"
    else:
        judgement = "HOLD"

    return {
        "symbol": symbol,
        "judgement": judgement,
        "score": int(score),
        "close": float(row["Close"]),
        "indicators": {
            "rsi14": float(row["RSI14"]),
            "adx14": float(row["ADX14"]),
            "atr_pct": float(row["ATR_PCT"]),
            "vol_ratio": float(vol_ratio),
            "sma5": float(row["SMA5"]),
            "sma25": float(row["SMA25"]),
            "macd": float(row["MACD"]),
            "macd_signal": float(row["MACD_SIGNAL"]),
            "plus_di": float(row["PLUS_DI"]),
            "minus_di": float(row["MINUS_DI"]),
        },
        "reasons": reasons,
    }


def judge(row_prev: pd.Series, row: pd.Series, score: int) -> str:
    """
    旧コード互換用。徐々に廃止予定。
    """
    vol_ratio = float(row["Volume"] / row["VOL20"]) if row["VOL20"] else 0.0

    if (score <= -2) or ((row["SMA5"] < row["SMA25"]) and (row["MACD"] < row["MACD_SIGNAL"])):
        return "SELL"
    if (
        score >= 6
        and row["ADX14"] >= 20
        and vol_ratio >= 1.5
        and row["RSI14"] <= 72
        and row["Close"] > row["SMA25"]
    ):
        return "STRONG BUY"
    if (
        score >= 4
        and row["ADX14"] >= 15
        and row["RSI14"] <= 68
        and vol_ratio >= 1.0
    ):
        return "BUY"
    return "HOLD"


def score_row(row_prev: pd.Series, row: pd.Series) -> int:
    """
    旧コード互換用。徐々に廃止予定。
    """
    result = evaluate_signal("UNKNOWN", row_prev, row)
    return int(result["score"])