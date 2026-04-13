
from __future__ import annotations
import requests
import json

def post_discord(webhook_url: str, content: str):
    if not webhook_url or webhook_url.endswith("REPLACE_ME"):
        print("[notify] Webhook URL 未設定のため送信スキップ")
        return
    headers = {"Content-Type": "application/json"}
    data = {"content": content}
    resp = requests.post(webhook_url, headers=headers, data=json.dumps(data), timeout=10)
    try:
        resp.raise_for_status()
    except Exception as e:
        print("[notify] Discord送信エラー:", e)
