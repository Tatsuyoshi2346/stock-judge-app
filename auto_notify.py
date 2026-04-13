import yaml
import requests

from screener import build_features
from signals import evaluate_signal


def load_config():
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def classify_candidate(result: dict) -> bool:
    """
    HOLDの中から、STRONG BUY予備軍になりそうな銘柄を判定
    """
    ind = result["indicators"]

    return (
        result["judgement"] == "HOLD"
        and result["score"] >= 2
        and 48 <= float(ind["rsi14"]) <= 68
        and float(ind["adx14"]) >= 12
        and float(result["close"]) > float(ind["sma25"])
        and float(ind["macd"]) > float(ind["macd_signal"])
    )


def format_line(result: dict) -> str:
    ind = result["indicators"]
    return (
        f"{result['symbol']} | score {result['score']} | "
        f"close {result['close']:.2f} | "
        f"RSI {ind['rsi14']:.1f} | "
        f"ADX {ind['adx14']:.1f} | "
        f"Vol {ind['vol_ratio']:.2f}x"
    )


def main():
    cfg = load_config()
    webhook = cfg.get("discord_webhook_url")

    if not webhook:
        print("Webhook未設定")
        return

    tickers = cfg.get("tickers", []) or []
    exclude = set(cfg.get("exclude") or [])

    strong_list = []
    buy_list = []
    candidate_list = []

    for symbol in tickers:
        if symbol in exclude:
            continue

        try:
            df = build_features(symbol)
            if df is None or len(df) < 2:
                continue

            last = df.iloc[-1]
            prev = df.iloc[-2]
            result = evaluate_signal(symbol, prev, last)

            if result["judgement"] == "STRONG BUY":
                strong_list.append(result)
            elif result["judgement"] == "BUY":
                buy_list.append(result)
            elif classify_candidate(result):
                candidate_list.append(result)

        except Exception as e:
            print(symbol, e)

    # 何も無ければ静かに終了
    if not strong_list and not buy_list and not candidate_list:
        print("通知対象なし")
        return

    lines = []

    if strong_list:
        lines.append("**🔥 STRONG BUY**")
        for r in strong_list:
            lines.append(format_line(r))
        lines.append("")

    if buy_list:
        lines.append("**📈 BUY**")
        for r in buy_list:
            lines.append(format_line(r))
        lines.append("")

    if candidate_list:
        lines.append("**👀 CANDIDATE**")
        for r in candidate_list:
            lines.append(format_line(r))
        lines.append("")

    message = "\n".join(lines).strip()

    try:
        response = requests.post(webhook, json={"content": message}, timeout=10)
        response.raise_for_status()
        print("Discord通知送信OK")
    except Exception as e:
        print(f"Discord送信失敗: {e}")


if __name__ == "__main__":
    main()