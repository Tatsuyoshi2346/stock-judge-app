import pandas as pd
from pathlib import Path

LOG_PATH = Path("judge_log.csv")

if not LOG_PATH.exists():
    print("judge_log.csv が見つかりません。先にBotで判定を記録してください。")
    raise SystemExit(1)

df = pd.read_csv(LOG_PATH)

if df.empty:
    print("judge_log.csv は空です。")
    raise SystemExit(1)

print("==== 判定ログ集計 ====\n")

print("【総件数】")
print(len(df))
print()

print("【判定別件数】")
print(df["judgement"].value_counts())
print()

print("【判定別 平均スコア】")
print(df.groupby("judgement")["score"].mean().round(2))
print()

print("【判定別 平均RSI】")
print(df.groupby("judgement")["rsi14"].mean().round(2))
print()

print("【判定別 平均ADX】")
print(df.groupby("judgement")["adx14"].mean().round(2))
print()

print("【判定別 平均ATR%】")
print(df.groupby("judgement")["atr_pct"].mean().round(2))
print()

print("【判定別 平均出来高倍率】")
print(df.groupby("judgement")["vol_ratio"].mean().round(2))
print()

print("【銘柄別 出現回数 上位10】")
print(df["symbol"].value_counts().head(10))
print()

print("【銘柄別 最新判定 上位10件】")
latest = df.sort_values("timestamp").groupby("symbol").tail(1)
print(latest[["timestamp", "symbol", "judgement", "score", "close"]].tail(10).to_string(index=False))
print()

print("==== 集計完了 ====")