
from __future__ import annotations
import feedparser
from typing import List, Dict

def pick_news(feeds: List[str], keywords: List[str], max_items: int = 50) -> Dict[str, list]:
    found = {kw: [] for kw in keywords}
    for url in feeds:
        d = feedparser.parse(url)
        for entry in d.entries[:max_items]:
            title = entry.get('title', '')
            summary = entry.get('summary', '')
            link = entry.get('link', '')
            text = f"{title} {summary}"
            for kw in keywords:
                if kw and kw in text:
                    found[kw].append({"title": title, "link": link})
    # 空のキーワードは削除
    return {k: v for k, v in found.items() if v}
