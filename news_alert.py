from __future__ import annotations
import os, json, time, re, datetime as dt
from typing import List, Dict, Any
import yaml
import feedparser
import requests
from bs4 import BeautifulSoup

# 既存の判定ロジックを再利用（任意）
from screener import build_features
from signals import score_row, judge as judge_signal

CFG_PATH = os.path.join(os.path.dirname(__file__), "config.yml")
SEEN_PATH = os.path.join(os.path.dirname(__file__), "news_seen.json")

def load_cfg() -> dict:
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_seen() -> Dict[str, float]:
    if not os.path.exists(SEEN_PATH):
        return {}
    try:
        with open(SEEN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_seen(seen: Dict[str, float]) -> None:
    with open(SEEN_PATH, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)

def jst_now() -> dt.datetime:
    # UTC→JST(+9)
    return dt.datetime.utcnow() + dt.timedelta(hours=9)

def within_market_hours(now: dt.datetime) -> bool:
    # 平日 09:00-15:00（日本）だけ通知したい場合
    if now.weekday() >= 5:
        return False
    hhmm = now.hour * 60 + now.minute
    return 9*60 <= hhmm <= 15*60

def fetch_article_text(url: str, timeout: int = 8) -> str:
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # ざっくり本文抽出（失敗してもOK）
        texts = [t.get_text(" ", strip=True) for t in soup.find_all(["p","h1","h2","h3","li"])]
        return " ".join(texts)[:5000]
    except Exception:
        return ""

def map_to_tickers(text: str, cfg: dict) -> List[str]:
    """テキストからティッカーを抽出: 1) 手動エイリアス 2) 4桁→.T 3) 英字ティッカー"""
    out: List[str] = []
    alias = cfg.get("news", {}).get("ticker_alias", {}) or {}

    # 1) 手動エイリアス（長い文字列に先にマッチ）
    for name, ticker in sorted(alias.items(), key=lambda x: -len(x[0])):
        if name.lower() in text.lower():
            out.append(ticker)

    # 2) 東証 4桁
    for m in re.findall(r"\b(\d{4})\b", text):
        out.append(f"{m}.T")

    # 3) 英字ティッカー（BRK.B などを許容）
    for m in re.findall(r"\b([A-Z]{1,5}(?:\.[A-Z])?)\b", text):
        # 短い一般語は弾く（IT, CEO, AIなど）
        if m in {"CEO","AI","IPO","ETF","GDP","EV","USB"}:
            continue
        out.append(m)

    # 除外・重複排除
    exclude = set(cfg.get("exclude") or [])
    uniq = []
    for t in out:
        if t not in uniq and t not in exclude:
            uniq.append(t)
    return uniq[:10]

def score_item(title: str, summary: str, text: str, tickers: List[str], cfg: dict) -> int:
    """ニューススコア: キーワード命中 + ティッカー含有 + 新鮮度ざっくり"""
    score = 0
    kw = cfg.get("news", {}).get("keywords", []) or []
    blob = f"{title} {summary} {text}".lower()
    for k in kw:
        if k and k.lower() in blob:
            score += 1
    score += min(len(tickers), 3)  # 銘柄が見つかっていれば加点
    return score

def fetch_news(cfg: dict) -> List[Dict[str, Any]]:
    feeds = cfg.get("news", {}).get("feeds", []) or []
    max_items = int(cfg.get("news", {}).get("max_items", 50))
    items: List[Dict[str, Any]] = []
    for url in feeds:
        try:
            parsed = feedparser.parse(url)
            for e in parsed.entries[:max_items]:
                title = e.get("title", "")
                link = e.get("link", "")
                summary = BeautifulSoup(e.get("summary", ""), "html.parser").get_text(" ", strip=True)
                items.append({"title": title, "link": link, "summary": summary, "published": e.get("published", "")})
        except Exception:
            continue
    return items

def judge_ticker(ticker: str) -> dict:
    """
    直近の判定を付与して dict を返す:
    { "ticker": "7203.T", "decision": "BUY|SELL|HOLD|NA", "score": +3, "rsi": 55.3, "adx": 21.0 }
    """
    try:
        df = build_features(ticker)
        last, prev = df.iloc[-1], df.iloc[-2]
        sc = score_row(prev, last)
        dec = judge_signal(prev, last, sc)
        return {
            "ticker": ticker,
            "decision": str(dec),
            "score": int(sc),
            "rsi": float(last.get("RSI14", 0.0)),
            "adx": float(last.get("ADX14", 0.0)),
        }
    except Exception:
        return {"ticker": ticker, "decision": "NA", "score": 0, "rsi": 0.0, "adx": 0.0}


def build_payload(topics: list[dict], cfg: dict) -> dict:
    """
    Webhookに投げる payload を返す（Embed対応）。
    - content（ヘッダ）+ embeds（各ニュース1枚）
    """
    now = jst_now().strftime("%Y-%m-%d %H:%M")
    use_buy = bool(cfg.get("news", {}).get("alert", {}).get("use_buy_judgement", True))

    embeds = []
    for t in topics[:10]:  # Webhookは1メッセージ最大10 embeds
        # Signals（任意）
        # Signals（BUYだけ詳しく。NAは除外）
        signals = []
        decisions = []
        if use_buy and t["tickers"]:
            for tk in t["tickers"][:4]:  # 1カード最大4銘柄
                info = judge_ticker(tk)
                if info["decision"] == "NA":
                    continue
                decisions.append(info["decision"])
                if info["decision"] == "BUY":
                    signals.append(f"**{info['ticker']}**: **BUY** (score {info['score']:+d}, RSI {info['rsi']:.1f}, ADX {info['adx']:.1f})")

        # 色決定：BUY優先→SELL→その他
        color = 3447003  # 青
        if "BUY" in decisions:
            color = 3066993  # 緑
        elif "SELL" in decisions:
            color = 15548997  # 赤

        # 概要テキスト（長すぎ防止）
        desc = (t.get("summary") or "").strip()
        if len(desc) > 280:
            desc = desc[:280] + "…"

        embed = {
            "title": t["title"][:256],
            "url": t["link"],
            "description": desc,
            "color": color,
            "fields": [
                {
                    "name": "Tickers",
                    "value": (", ".join(t["tickers"][:8]) if t["tickers"] else "-"),  # 表示は最大8件
                    "inline": True,
                },
                {
                    "name": "Score",
                    "value": str(t.get("score", 0)),
                    "inline": True,
                },
            ],
            "footer": {"text": "News Scanner"},
            "timestamp": jst_now().astimezone(dt.timezone.utc).isoformat()  # Discord表示はUTC推奨
        }

        # BUYあればSignals欄を追加
        if use_buy and signals:
            embed["fields"].append({
                "name": "Signals (BUYのみ表示)",
                "value": "\n".join(signals)[:1024],
                "inline": False,
            })

        embeds.append(embed)

    payload = {
        "content": "",  # ← Embedだけ送る。ヘッダー行はなし
        "embeds": embeds,
    }
    return payload



def send_discord(webhook: str, content_or_payload) -> None:
    """
    content_or_payload が str の場合は従来どおりメッセージ送信、
    dict の場合は Embed を含む payload を送信。
    """
    if not webhook:
        print("Webhook未設定。出力のみ。\n", content_or_payload)
        return
    try:
        if isinstance(content_or_payload, dict):
            r = requests.post(webhook, json=content_or_payload, timeout=10)
        else:
            r = requests.post(webhook, json={"content": str(content_or_payload)}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print("Discord送信失敗:", e)

def main():
    cfg = load_cfg()
    if not cfg.get("news", {}).get("enabled", True):
        print("news disabled.")
        return

    now = jst_now()
    alert_cfg = cfg.get("news", {}).get("alert", {}) or {}
    if alert_cfg.get("market_hours_only", False) and not within_market_hours(now):
        print("out of market hours, skip.")
        return

    seen = load_seen()
    dedupe_days = int(alert_cfg.get("dedupe_days", 3))
    cutoff = time.time() - dedupe_days * 86400

    # 期限切れ既読の掃除
    seen = {k: v for k, v in seen.items() if v >= cutoff}

    raw_items = fetch_news(cfg)

    candidates: List[Dict[str, Any]] = []
    for it in raw_items:
        if it["link"] in seen:
            continue
        # 本文も取得して精度UP（軽微に重い）
        body = fetch_article_text(it["link"])
        tickers = map_to_tickers(" ".join([it["title"], it["summary"], body]), cfg)
        score = score_item(it["title"], it["summary"], body, tickers, cfg)
        if score == 0 and not tickers:
            continue
        candidates.append({
            "title": it["title"],
            "summary": it["summary"],
            "link": it["link"],
            "tickers": tickers,
            "score": score
        })

    # 優先順位：スコア降順 → ティッカーが watchlist に含まれるものを前へ
    watch = set(cfg.get("tickers") or [])
    def prio(x):
        bonus = any(t in watch for t in x["tickers"])
        return (x["score"], 1 if bonus else 0)

    candidates.sort(key=prio, reverse=True)

    max_posts = int(alert_cfg.get("max_posts", 6))
    top = candidates[:max_posts]
    if not top:
        print("ヒットなし")
        return

    payload = build_payload(top, cfg)
    send_discord(cfg.get("discord_webhook_url", ""), payload)

    # 既読登録
    ts = time.time()
    for t in top:
        seen[t["link"]] = ts
    save_seen(seen)

if __name__ == "__main__":
    main()
