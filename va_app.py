import streamlit as st
import pandas as pd
import os
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ====== 設定 ======
FILE_PATH = "output/high_quality_dataset.csv"
SHEET_ID = "1BjiqJNwUE4ZeCxBtYRJ3qLUBym_2bAhHEZa93zWol1c"
CHECKPOINT = 10   # 每10題存一次

EMOTIONS = [
    "joy", "sadness", "anger", "fear",
    "regret", "hope", "loneliness", "empathy",
    "awe", "gratitude", "inner_peace", "compassion"
]

# ====== Google Sheets ======
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    st.secrets["gcp_service_account"], scope
)
client = gspread.authorize(creds)

try:
    sheet = client.open_by_key(SHEET_ID).sheet1
    stats_sheet = client.open_by_key(SHEET_ID).worksheet("user_stats")
except Exception as e:
    st.error(f"❌ 無法連接 Google Sheets：{e}")
    st.stop()
stats_sheet = client.open_by_key(SHEET_ID).worksheet("user_stats")

# ====== 初始化 ======
if "data" not in st.session_state:
    st.session_state.data = pd.read_csv(FILE_PATH)
    st.session_state.sample = st.session_state.data.sample(n=20).reset_index(drop=True)
    st.session_state.index = 0
    st.session_state.correct = 0
    st.session_state.results = []
    st.session_state.saved_index = 0  # 已寫入到第幾筆

# ====== 使用者名稱 ======
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

if not st.session_state.user_name:
    st.title("📊 情緒分類驗證系統")
    name = st.text_input("輸入名字")

    if st.button("開始"):
        if name:
            st.session_state.user_name = name
            st.rerun()
        else:
            st.warning("請輸入名字")
    st.stop()

# ====== UI ======
st.title("📊 情緒分類驗證系統")
st.write(f"👤 使用者：{st.session_state.user_name}")
st.write(f"進度：{st.session_state.index+1} / 20")

# ====== 題目 ======
if st.session_state.index < len(st.session_state.sample):

    row = st.session_state.sample.iloc[st.session_state.index]

    st.subheader("句子")
    st.write(row["sentence"])

    user_emotion = st.selectbox("選擇情緒", EMOTIONS)

    if st.button("提交"):

        correct = (user_emotion == row["emotion"])
        if correct:
            st.session_state.correct += 1

        # 存資料
        st.session_state.results.append({
            "user": st.session_state.user_name,
            "sentence": row["sentence"],
            "model_emotion": row["emotion"],
            "human_emotion": user_emotion,
            "correct": correct
        })

        # ====== 每 CHECKPOINT 題自動存 ======
        if len(st.session_state.results) % CHECKPOINT == 0:
            try:
                new_rows = []
                for r in st.session_state.results[st.session_state.saved_index:]:
                    new_rows.append([
                        r["user"],
                        r["sentence"],
                        r["model_emotion"],
                        r["human_emotion"],
                        r["correct"]
                    ])

                sheet.append_rows(new_rows)
                st.session_state.saved_index = len(st.session_state.results)

                st.info(f"✅ 已自動儲存 {len(new_rows)} 筆")

            except Exception as e:
                st.error(f"自動儲存失敗：{e}")

        # ====== 本地備份 ======
        pd.DataFrame(st.session_state.results).to_csv("backup.csv", index=False)

        st.success("✔ 正確" if correct else "❌ 錯誤")

        st.session_state.index += 1
        st.rerun()

# ====== 完成 ======
else:
    st.success("🎉 完成！")

    total = len(st.session_state.results)
    correct = st.session_state.correct
    acc = correct / total

    st.write(f"準確率：{acc:.2%}")

    # ====== 補寫剩餘資料 ======
    if st.session_state.saved_index < len(st.session_state.results):
        try:
            remaining = st.session_state.results[st.session_state.saved_index:]
            rows = []
            for r in remaining:
                rows.append([
                    r["user"],
                    r["sentence"],
                    r["model_emotion"],
                    r["human_emotion"],
                    r["correct"]
                ])

            sheet.append_rows(rows)
            st.success("✅ 補寫完成")

        except Exception as e:
            st.error(f"補寫失敗：{e}")

    # ====== 寫統計 ======
    try:
        stats_sheet.append_row([
            st.session_state.user_name,
            total,
            correct,
            acc
        ])
    except:
        pass

    # ====== 下載 ======
    df = pd.DataFrame(st.session_state.results)
    st.download_button("下載CSV", df.to_csv(index=False), "result.csv")

    if st.button("重新開始"):
        st.session_state.clear()
        st.rerun()
