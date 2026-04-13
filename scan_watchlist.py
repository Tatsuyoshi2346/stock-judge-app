import yaml
import pandas as pd
from pathlib import Path

from screener import build_features
from signals import evaluate_signal

CONFIG_PATH = Path("config.yml")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def scan_symbol(symbol: str) -> dict | None:
    try:
        df = build_features(symbol)
        if df is None or len(df) < 2:
            return None

        last = df.iloc[-1]
        prev = df.iloc[-2]
        result = evaluate_signal(symbol, prev, last)

        return {
            "symbol": result["symbol"],
            "judgement": result["judgement"],
            "score": result["score"],
            "close": round(result["close"], 2),
            "rsi14": round(result["indicators"]["rsi14"], 2),
            "adx14": round(result["indicators"]["adx14"], 2),
            "atr_pct": round(result["indicators"]["atr_pct"], 2),
            "vol_ratio": round(result["indicators"]["vol_ratio"], 2),
            "reasons": " / ".join(
                [
                    f"{'+' if r['point'] > 0 else ''}{r['point']} {r['label']}"
                    for r in result["reasons"]
                    if r["point"] != 0
                ]
            ),
        }
    except Exception as e:
        return {
            "symbol": symbol,
            "judgement": "ERROR",
            "score": None,
            "close": None,
            "rsi14": None,
            "adx14": None,
            "atr_pct": None,
            "vol_ratio": None,
            "reasons": str(e),
        }


def judgement_rank(j: str) -> int:
    order = {
        "STRONG BUY": 0,
        "BUY": 1,
        "HOLD": 2,
        "SELL": 3,
        "ERROR": 4,
    }
    return order.get(j, 99)


def main():
    cfg = load_config()
    tickers = cfg.get("tickers", []) or []
    exclude = set(cfg.get("exclude", []) or [])

    targets = [t for t in tickers if t not in exclude]

    if not targets:
        print("監視銘柄がありません。config.yml を確認してください。")
        return

    rows = []
    for symbol in targets:
        print(f"scanning: {symbol}")
        result = scan_symbol(symbol)
        if result:
            rows.append(result)

    if not rows:
        print("結果がありません。")
        return

    df = pd.DataFrame(rows)

    # 並び順：STRONG BUY → BUY → HOLD → SELL → ERROR
    # その中でスコア降順
    df["rank"] = df["judgement"].apply(judgement_rank)
    df = df.sort_values(by=["rank", "score"], ascending=[True, False], na_position="last")
    df = df.drop(columns=["rank"])

    print("\n==== 監視銘柄スキャン結果 ====\n")
    print(df.to_string(index=False))
    print()

    out_path = Path("watchlist_scan.csv")
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"保存しました: {out_path}")

    print("\n==== STRONG BUY ====")
    strong = df[df["judgement"] == "STRONG BUY"]
    if strong.empty:
        print("なし")
    else:
        print(strong[["symbol", "score", "close", "rsi14", "adx14", "vol_ratio"]].to_string(index=False))

    print("\n==== BUY ====")
    buy = df[df["judgement"] == "BUY"]
    if buy.empty:
        print("なし")
    else:
        print(buy[["symbol", "score", "close", "rsi14", "adx14", "vol_ratio"]].to_string(index=False))


if __name__ == "__main__":
    main()