
from __future__ import annotations
import argparse
import yaml
from datetime import datetime
import pytz
from apscheduler.schedulers.blocking import BlockingScheduler

from screener import build_features
from signals import score_row, judge
from notify import post_discord
from news import pick_news

def load_config(path: str = "config.yml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_once(cfg: dict, tickers_override: list[str] | None = None, use_news: bool = True) -> str:
    tz = pytz.timezone(cfg.get("timezone", "Asia/Tokyo"))
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    tickers = tickers_override or cfg.get("tickers", [])
    exclude = set(cfg.get("exclude", []) or [])
    tickers = [t for t in tickers if t not in exclude]

    lines = [f"**Stock Judge Bot v2**  ({now})"]
    lines.append("")
    lines.append("`symbol | close | score | rsi | adx | atr% | vol/vol20 | judgement`")

    for symbol in tickers:
        try:
            df = build_features(symbol)
            last = df.iloc[-1]
            prev = df.iloc[-2]
            score = score_row(prev, last)
            decision = judge(prev, last, score)
            vol_ratio = round(last['Volume'] / last['VOL20'], 2) if last['VOL20'] else 0.0
            lines.append(f"{symbol} | {last['Close']:.2f} | {score:+d} | {last['RSI14']:.1f} | {last['ADX14']:.1f} | {last['ATR_PCT']:.1f}% | {vol_ratio}x | **{decision}**")
        except Exception as e:
            lines.append(f"{symbol} | ERROR: {e}")

    # ニュース（任意）
    if use_news and cfg.get("news", {}).get("enabled", False):
        feeds = cfg["news"].get("feeds", [])
        keywords = cfg["news"].get("keywords", [])
        picked = pick_news(feeds, keywords, cfg["news"].get("max_items", 50))
        if picked:
            lines.append("")
            lines.append("**News hits (keyword → title)**")
            count = 0
            for kw, items in picked.items():
                for it in items[:5]:  # 各キーワード最大5件
                    lines.append(f"- {kw} → {it['title']}  <{it['link']}>")
                    count += 1
            if count == 0:
                lines.append("- (no matches)")

    text = "\n".join(lines)
    post_discord(cfg.get("discord_webhook_url", ""), text)
    print(text)
    return text

def run_scheduler(cfg: dict):
    tz = pytz.timezone(cfg.get("timezone", "Asia/Tokyo"))
    scheduler = BlockingScheduler(timezone=tz)

    for hhmm in cfg.get("schedules", []):
        hour, minute = map(int, hhmm.split(":"))
        scheduler.add_job(lambda: run_once(cfg), "cron", hour=hour, minute=minute, id=f"job_{hhmm}")

    print("[scheduler] Jobs:")
    for j in scheduler.get_jobs():
        print(" -", j)

    print("[scheduler] Start... (Ctrl+C to stop)")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("[scheduler] stopped.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="一度だけ実行して終了")
    ap.add_argument("--tickers", type=str, default="", help="カンマ区切りでティッカーを上書き")
    ap.add_argument("--no-news", action="store_true", help="ニュース解析を無効化")
    args = ap.parse_args()

    cfg = load_config()

    override = [s.strip() for s in args.tickers.split(",") if s.strip()] if args.tickers else None
    if args.once:
        run_once(cfg, tickers_override=override, use_news=not args.no_news)
    else:
        run_scheduler(cfg)
