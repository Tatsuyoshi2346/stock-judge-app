import pandas as pd
import yfinance as yf
from pathlib import Path

LOG_PATH = Path("judge_log.csv")

if not LOG_PATH.exists():
    print("judge_log.csv が見つかりません。先にBotで判定ログを作ってください。")
    raise SystemExit(1)

df = pd.read_csv(LOG_PATH)

if df.empty:
    print("judge_log.csv は空です。")
    raise SystemExit(1)

df["timestamp"] = pd.to_datetime(df["timestamp"])
df = df.sort_values("timestamp").copy()

results = []

for _, row in df.iterrows():
    symbol = row["symbol"]
    entry_date = row["timestamp"].date()
    entry_close = float(row["close"])

    try:
        hist = yf.download(
            symbol,
            start=str(entry_date),
            period="3mo",
            interval="1d",
            progress=False,
            auto_adjust=False,
        )

        if hist is None or hist.empty:
            continue

        hist = hist.dropna()

        close_data = hist["Close"]

        # DataFrame / Series 両対応
        if isinstance(close_data, pd.DataFrame):
            closes = close_data.iloc[:, 0].astype(float).tolist()
        else:
            closes = close_data.astype(float).tolist()

        ret_1d = None
        ret_5d = None
        ret_20d = None

        if len(closes) > 1:
            ret_1d = (closes[1] / entry_close - 1) * 100
        if len(closes) > 5:
            ret_5d = (closes[5] / entry_close - 1) * 100
        if len(closes) > 20:
            ret_20d = (closes[20] / entry_close - 1) * 100

        results.append({
            "timestamp": row["timestamp"],
            "symbol": symbol,
            "judgement": row["judgement"],
            "score": row["score"],
            "entry_close": entry_close,
            "ret_1d_pct": round(ret_1d, 2) if ret_1d is not None else None,
            "ret_5d_pct": round(ret_5d, 2) if ret_5d is not None else None,
            "ret_20d_pct": round(ret_20d, 2) if ret_20d is not None else None,
        })

    except Exception as e:
        print(f"{symbol} 取得失敗: {e}")

if not results:
    print("バックテスト対象がありません。")
    raise SystemExit(0)

bt = pd.DataFrame(results)

print("==== 個別結果 ====\n")
print(bt.to_string(index=False))
print()


# ===============================
# 平均リターン（NaN考慮）
# ===============================
print("==== 判定別平均リターン ====\n")
summary = bt.groupby("judgement")[["ret_1d_pct", "ret_5d_pct", "ret_20d_pct"]].mean().round(2)
print(summary)
print()


# ===============================
# 勝率（NaN除外）
# ===============================
def calc_winrate(series):
    s = series.dropna()
    if len(s) == 0:
        return None
    return round((s > 0).mean() * 100, 1)


print("==== 判定別勝率（1日後） ====\n")
win_1d = bt.groupby("judgement")["ret_1d_pct"].apply(calc_winrate)
print(win_1d)
print()

print("==== 判定別勝率（5日後） ====\n")
win_5d = bt.groupby("judgement")["ret_5d_pct"].apply(calc_winrate)
print(win_5d)
print()

print("==== 判定別勝率（20日後） ====\n")
win_20d = bt.groupby("judgement")["ret_20d_pct"].apply(calc_winrate)
print(win_20d)
print()


# ===============================
# CSV保存
# ===============================
out_path = Path("backtest_result.csv")
bt.to_csv(out_path, index=False, encoding="utf-8-sig")

print(f"バックテスト結果を保存しました: {out_path}")