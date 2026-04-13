# bot.py — Discordで銘柄コードを受け取り、BUY/SELL/HOLDを即返信するBot
from __future__ import annotations
import re
import yaml
import discord
from discord.ext import commands
import csv
from datetime import datetime

# ---- single-instance lock on Windows ----
import os
import sys
try:
    import msvcrt
    _lock_path = os.path.join(os.path.dirname(__file__), "bot.lock")
    _lock_file = open(_lock_path, "w")
    msvcrt.locking(_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
except Exception:
    print("Another instance already running. Exiting.")
    sys.exit(0)
# -----------------------------------------

from screener import build_features
from signals import evaluate_signal

# ==============================
# 設定読み込み
# ==============================
def load_cfg(path: str = "config.yml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

cfg = load_cfg()
BOT_TOKEN = cfg.get("discord_bot_token")

if not BOT_TOKEN or "YOUR_BOT_TOKEN" in BOT_TOKEN:
    raise SystemExit("⚠️ config.yml の discord_bot_token が未設定です。")

# message_content intent を有効にする
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ==============================
# 判定処理
# ==============================
def format_result(symbol: str) -> dict:
    """
    1銘柄を判定して構造化データを返す
    """
    df = build_features(symbol)
    if len(df) < 2:
        raise ValueError(f"Not enough data for {symbol}")

    last = df.iloc[-1]
    prev = df.iloc[-2]
    return evaluate_signal(symbol, prev, last)

def append_judge_log(result: dict) -> None:
    """
    判定結果をCSVに追記する
    """
    log_path = os.path.join(os.path.dirname(__file__), "judge_log.csv")
    file_exists = os.path.exists(log_path)

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        result["symbol"],
        result["judgement"],
        result["score"],
        round(result["close"], 2),
        round(result["indicators"]["rsi14"], 2),
        round(result["indicators"]["adx14"], 2),
        round(result["indicators"]["atr_pct"], 2),
        round(result["indicators"]["vol_ratio"], 2),
    ]

    with open(log_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp",
                "symbol",
                "judgement",
                "score",
                "close",
                "rsi14",
                "adx14",
                "atr_pct",
                "vol_ratio",
            ])
        writer.writerow(row)

def format_discord_message(result: dict, detail: bool = True) -> str:
    """
    Discordに返す表示文字列を作る
    """
    indicators = result["indicators"]

    header = (
        f"`symbol | close | score | rsi | adx | atr% | vol/vol20 | judgement`\n"
        f"{result['symbol']} | "
        f"{result['close']:.2f} | "
        f"{result['score']:+d} | "
        f"{indicators['rsi14']:.1f} | "
        f"{indicators['adx14']:.1f} | "
        f"{indicators['atr_pct']:.1f}% | "
        f"{indicators['vol_ratio']:.2f}x | "
        f"**{result['judgement']}**"
    )

    if not detail:
        return header

    # 点数が動いた項目だけ表示
    reason_lines = []
    for r in result["reasons"]:
        if r["point"] != 0:
            sign = "+" if r["point"] > 0 else ""
            reason_lines.append(f"{sign}{r['point']} {r['label']}")

    if reason_lines:
        return header + "\n" + " / ".join(reason_lines)

    return header


def normalize_symbols(text: str) -> list[str]:
    """
    入力文字列から銘柄コードを抽出
    - 数字4桁 → 東証銘柄として .T を付与
    - 4桁+英字（例: 429A）→ 東証銘柄として .T を付与
    - 英字 → そのまま（米国株など）
    """
    raw = re.split(r"[,\s]+", text.strip())
    out = []

    for token in raw:
        if not token:
            continue

        # 4桁コード
        if re.fullmatch(r"\d{4}", token):
            out.append(f"{token}.T")
            continue

        # 4桁+英字（IPOなど）
        if re.fullmatch(r"\d{3,4}[A-Za-z]", token):
            out.append(f"{token.upper()}.T")
            continue

        # 米株など
        if re.fullmatch(r"[A-Za-z0-9\.\-]{1,10}", token):
            out.append(token.upper())

    exclude = set((cfg.get("exclude") or []))
    return [t for t in out if t not in exclude]


HELP_TEXT = (
    "**📘使い方**\n"
    "- `!judge 7203` → トヨタを判定\n"
    "- `!judge 7203 6758 NVDA` → 複数同時\n"
    "- `!judge 429A` → 4桁+英字にも対応\n"
    "- ただ数字だけ打ってもOK（例: `7203`）\n\n"
    "**出力形式**\n"
    "`symbol | close | score | rsi | adx | atr% | vol/vol20 | judgement`\n"
    "その下に、加点・減点の理由を表示します。"
)

# ==============================
# イベント設定
# ==============================
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


@bot.command(name="judge")
async def judge_cmd(ctx: commands.Context, *args):
    """
    !judge 7203 6758 NVDA のように使う
    """
    if not args:
        await ctx.reply(HELP_TEXT)
        return

    symbols = normalize_symbols(" ".join(args))
    if not symbols:
        await ctx.reply("⚠️ 銘柄コードを認識できません。例: `!judge 7203 6758 NVDA`")
        return

    messages = []
    for sym in symbols[:10]:
        try:
            result = format_result(sym)
            append_judge_log(result)
            messages.append(format_discord_message(result, detail=True))
        except Exception as e:
            messages.append(f"{sym} | ERROR: {e}")

    await ctx.reply("\n\n".join(messages))


@bot.event
async def on_message(message: discord.Message):
    """
    !judge なしでコードだけ送られた場合にも対応
    """
    if message.author.bot:
        return

    content = message.content.strip()

    # コマンドを先に処理
    await bot.process_commands(message)

    # ! で始まるものはコマンド扱いなのでここでは無視
    if content.startswith("!"):
        return

    symbols = normalize_symbols(content)
    if not symbols:
        return

    messages = []
    for sym in symbols[:10]:
        try:
            result = format_result(sym)
            append_judge_log(result)
            messages.append(format_discord_message(result, detail=True))
        except Exception as e:
            messages.append(f"{sym} | ERROR: {e}")

    await message.reply("\n\n".join(messages))


# ==============================
# 起動
# ==============================
if __name__ == "__main__":
    bot.run(BOT_TOKEN)