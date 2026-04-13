import streamlit as st
import requests
import pandas as pd

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="Stock Judge App", layout="wide")
st.title("Stock Judge App")

tab1, tab2, tab3 = st.tabs(["個別判定", "監視銘柄", "候補一覧"])

with tab1:
    st.subheader("個別銘柄判定")
    symbol = st.text_input("銘柄コードを入力", value="7203")

    if st.button("判定する"):
        try:
            r = requests.get(f"{API_BASE}/judge/{symbol}", timeout=20)
            r.raise_for_status()
            result = r.json()

            st.markdown(f"### {result['symbol']} : **{result['judgement']}**")
            st.write(f"スコア: {result['score']}")
            st.write(f"終値: {result['close']:.2f}")

            ind = result["indicators"]
            st.write(
                f"RSI: {ind['rsi14']:.2f} / "
                f"ADX: {ind['adx14']:.2f} / "
                f"ATR%: {ind['atr_pct']:.2f} / "
                f"Vol倍率: {ind['vol_ratio']:.2f}"
            )

            st.markdown("#### 判定理由")
            reason_df = pd.DataFrame(result["reasons"])
            st.dataframe(reason_df, use_container_width=True)

        except Exception as e:
            st.error(f"取得失敗: {e}")

with tab2:
    st.subheader("監視銘柄スキャン")
    if st.button("監視銘柄を更新"):
        try:
            r = requests.get(f"{API_BASE}/watchlist", timeout=60)
            r.raise_for_status()
            items = r.json()["items"]

            rows = []
            for x in items:
                if x.get("judgement") == "ERROR":
                    rows.append({
                        "symbol": x["symbol"],
                        "judgement": "ERROR",
                        "score": None,
                        "rsi14": None,
                        "adx14": None,
                        "atr_pct": None,
                        "vol_ratio": None,
                        "candidate": False,
                    })
                else:
                    ind = x["indicators"]
                    rows.append({
                        "symbol": x["symbol"],
                        "judgement": x["judgement"],
                        "score": x["score"],
                        "rsi14": ind["rsi14"],
                        "adx14": ind["adx14"],
                        "atr_pct": ind["atr_pct"],
                        "vol_ratio": ind["vol_ratio"],
                        "candidate": x.get("candidate", False),
                    })

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error(f"取得失敗: {e}")

with tab3:
    st.subheader("STRONG BUY / BUY / CANDIDATE")
    if st.button("候補一覧を更新"):
        try:
            r = requests.get(f"{API_BASE}/candidates", timeout=60)
            r.raise_for_status()
            data = r.json()

            st.markdown("### 🔥 STRONG BUY")
            if data["strong_buy"]:
                strong_rows = []
                for x in data["strong_buy"]:
                    ind = x["indicators"]
                    strong_rows.append({
                        "symbol": x["symbol"],
                        "score": x["score"],
                        "close": x["close"],
                        "rsi14": ind["rsi14"],
                        "adx14": ind["adx14"],
                        "vol_ratio": ind["vol_ratio"],
                    })
                st.dataframe(pd.DataFrame(strong_rows), use_container_width=True)
            else:
                st.info("なし")

            st.markdown("### 📈 BUY")
            if data["buy"]:
                buy_rows = []
                for x in data["buy"]:
                    ind = x["indicators"]
                    buy_rows.append({
                        "symbol": x["symbol"],
                        "score": x["score"],
                        "close": x["close"],
                        "rsi14": ind["rsi14"],
                        "adx14": ind["adx14"],
                        "vol_ratio": ind["vol_ratio"],
                    })
                st.dataframe(pd.DataFrame(buy_rows), use_container_width=True)
            else:
                st.info("なし")

            st.markdown("### 👀 CANDIDATE")
            if data["candidate"]:
                cand_rows = []
                for x in data["candidate"]:
                    ind = x["indicators"]
                    cand_rows.append({
                        "symbol": x["symbol"],
                        "score": x["score"],
                        "close": x["close"],
                        "rsi14": ind["rsi14"],
                        "adx14": ind["adx14"],
                        "vol_ratio": ind["vol_ratio"],
                    })
                st.dataframe(pd.DataFrame(cand_rows), use_container_width=True)
            else:
                st.info("なし")

        except Exception as e:
            st.error(f"取得失敗: {e}")