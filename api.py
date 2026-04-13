from fastapi import FastAPI, HTTPException
from screener import build_features
from signals import evaluate_signal
import yaml

app = FastAPI(title="Stock Judge API", version="1.0.0")


def load_config():
    with open("config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def normalize_symbol(symbol: str) -> str:
    s = symbol.strip().upper()
    if s.isdigit() and len(s) == 4:
        return f"{s}.T"
    if len(s) >= 4 and s[:-1].isdigit() and s[-1].isalpha():
        return f"{s}.T"
    return s


def classify_candidate(result: dict) -> bool:
    ind = result["indicators"]
    return (
        result["judgement"] == "HOLD"
        and result["score"] >= 2
        and 48 <= float(ind["rsi14"]) <= 68
        and float(ind["adx14"]) >= 12
        and float(result["close"]) > float(ind["sma25"])
        and float(ind["macd"]) > float(ind["macd_signal"])
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/judge/{symbol}")
def judge_symbol(symbol: str):
    try:
        normalized = normalize_symbol(symbol)
        df = build_features(normalized)
        if df is None or len(df) < 2:
            raise HTTPException(status_code=400, detail="Not enough data")
        last = df.iloc[-1]
        prev = df.iloc[-2]
        return evaluate_signal(normalized, prev, last)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/watchlist")
def watchlist():
    cfg = load_config()
    tickers = cfg.get("tickers", []) or []
    exclude = set(cfg.get("exclude") or [])

    results = []
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
            result["candidate"] = classify_candidate(result)
            results.append(result)
        except Exception as e:
            results.append({
                "symbol": symbol,
                "judgement": "ERROR",
                "score": None,
                "candidate": False,
                "error": str(e),
            })

    order = {"STRONG BUY": 0, "BUY": 1, "HOLD": 2, "SELL": 3, "ERROR": 4}
    results.sort(key=lambda x: (order.get(x.get("judgement", "ERROR"), 99), -(x.get("score") or -999)))
    return {"count": len(results), "items": results}


@app.get("/candidates")
def candidates():
    cfg = load_config()
    tickers = cfg.get("tickers", []) or []
    exclude = set(cfg.get("exclude") or [])

    strong_buy = []
    buy = []
    candidate = []

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
                strong_buy.append(result)
            elif result["judgement"] == "BUY":
                buy.append(result)
            elif classify_candidate(result):
                candidate.append(result)
        except Exception:
            continue

    return {
        "strong_buy": strong_buy,
        "buy": buy,
        "candidate": candidate,
    }