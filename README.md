
# Stock Judge Bot v2 (JP/US対応)

**目的**: 指定した銘柄群に対して、テクニカル指標（5/25MA, MACD, RSI, ADX, ATR, 出来高）からスコアリングし、**BUY / SELL / HOLD** を判定。Discordへ定時通知（既定: 09:00 / 12:00 / 20:00 JST）。

## 必要要件
- Python 3.10+ 推奨
- Yahoo Finance由来の株価取得に `yfinance` を使用
- ニュースはRSS（`feedparser`）＋簡易キーワードマッチ（必要に応じてOFF可）

## セットアップ

```bash
# 1) 仮想環境（任意）
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) 依存パッケージ
pip install -r requirements.txt

# 3) 設定ファイルを編集
#   - DiscordのWebhook URL
#   - 監視銘柄（ティッカー）
#   - スケジュール時刻（JST）
#   - ニュース対象キーワード（企業名など）
vim config.yml  # お好きなエディタでOK

# 4) 手動で一度動作確認（即時実行）
python main.py --once

# 5) 定時実行（バックグラウンド常駐）
python main.py
```

> **注意（東証ティッカーの書き方）**: yfinanceでは **`7203.T`**（トヨタ） のように **`.T`** サフィックスが必要です。米国株はそのまま（例: `NVDA`, `TSLA`）。

## 使い方（コマンドライン）

```bash
# 1回だけ判定して終了
python main.py --once

# 対象銘柄を上書き指定する例（カンマ区切り）
python main.py --once --tickers 7203.T,6758.T,NVDA

# ニュース解析を無効化
python main.py --once --no-news
```

## 判定ロジック（概要）

スコア加点（合計スコアで判定）:
- +2: 5日線が25日線を上抜け（本日/前日でゴールデンクロス）
- +1: 5日線 > 25日線（トレンド強気）
- +1: MACD > シグナル、かつヒストグラム拡大
- +1: RSIが45〜65（過熱でも弱すぎでもない）
- +1: ADX > 20 かつ +DI > -DI（トレンドあり/強気）
- +1: 出来高が20日平均の1.3倍以上

減点/警戒:
- -1: RSI > 70（過熱）
- -1: RSI < 30（売られすぎ・短期弱気）
- -1: ATR%（ATR/終値） > 5%（ボラ高め）

**判定ルール**（初期値・自由に調整可）:
- `BUY` : スコア ≥ 3 かつ RSI ≤ 80
- `SELL`: スコア ≤ -2、または 5日線 < 25日線 かつ MACD < シグナル
- `HOLD`: 上記以外

## ファイル構成

- `config.yml` : Webhookや銘柄などの設定
- `main.py` : エントリーポイント（スケジューラ/即時実行）
- `screener.py` : データ取得と指標計算
- `signals.py` : 判定ロジック
- `notify.py` : Discord通知
- `news.py` : RSSから簡易ニュース抽出（任意）
- `requirements.txt` : 依存ライブラリ

## よくある質問

- **Q. ニュースも組み込みたい？**  
  A. `config.yml` の `news.enabled: true` とし、`news.keywords` に企業名や製品名を列挙してください。RSSはデフォルトでNikkeiやKabutanなどの一般フィードを参照し、タイトル/概要にキーワードが含まれるものを抽出します。

- **Q. LINE通知にしたい**  
  A. `notify.py` を参考に、LINE NotifyのエンドポイントにPOSTを送る関数を追加してください。

- **Q. タイムゾーン**  
  A. 既定は `Asia/Tokyo`。JST固定でスケジュールされます。

---

© 2025-10-22 – あなた専用ボット。自由に改変OK。
