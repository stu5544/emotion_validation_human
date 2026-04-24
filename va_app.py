import streamlit as st
import pandas as pd
import os
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ====== 設定 ======
FILE_PATH = "output/high_quality_dataset.csv"
SHEET_ID = "1BjiqJNwUE4ZeCxBtYRJ3qLUBym_2bAhHEZa93zWol1c"

TOTAL_QUESTIONS = 20
CHECKPOINT = 10   # 🔥 降低頻率（更穩）

EMOTIONS = [
    "joy", "sadness", "anger", "fear",
    "regret", "hope", "loneliness", "empathy",
    "awe", "gratitude", "inner_peace", "compassion"
]

# ====== 安全寫入函數（核心🔥）======
def safe_append(sheet, rows):
    for i in range(5):
        try:
            sheet.append_rows(rows)
            return True
        except Exception as e:
            time.sleep(2 ** i)
    return False

# ====== 初始化 Google Sheets（只做一次🔥）======
if "sheet" not in st.session_state:
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)

    st.session_state.sheet = client.open_by_key(SHEET_ID).sheet1
    st.session_state.stats_sheet = client.open_by_key(SHEET_ID).worksheet("user_stats")

sheet = st.session_state.sheet
stats_sheet = st.session_state.stats_sheet

# ====== 初始化資料 ======
if "data" not in st.session_state:
    df = pd.read_csv(FILE_PATH)
    n = min(TOTAL_QUESTIONS, len(df))

    st.session_state.sample = df.sample(n=n).reset_index(drop=True)
    st.session_state.index = 0
    st.session_state.correct = 0
    st.session_state.results = []
    st.session_state.saved_index = 0

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
st.write(f"👤 {st.session_state.user_name}")
st.write(f"進度：{st.session_state.index+1} / {TOTAL_QUESTIONS}")

# ====== 題目 ======
if st.session_state.index < len(st.session_state.sample):

    row = st.session_state.sample.iloc[st.session_state.index]
    st.write(row["sentence"])

    user_emotion = st.selectbox("選擇情緒", EMOTIONS)

    if st.button("提交"):

        correct = (user_emotion == row["emotion"])
        if correct:
            st.session_state.correct += 1

        st.session_state.results.append({
            "user": st.session_state.user_name,
            "sentence": row["sentence"],
            "model_emotion": row["emotion"],
            "human_emotion": user_emotion,
            "correct": correct
        })

        # ====== checkpoint寫入 ======
        if len(st.session_state.results) % CHECKPOINT == 0:

            new_data = st.session_state.results[st.session_state.saved_index:]

            rows = [[
                r["user"],
                r["sentence"],
                r["model_emotion"],
                r["human_emotion"],
                r["correct"]
            ] for r in new_data]

            success = safe_append(sheet, rows)

            if success:
                st.session_state.saved_index = len(st.session_state.results)
                st.info(f"✅ 已安全寫入 {len(rows)} 筆")
            else:
                st.warning("⚠️ 寫入失敗（已保留，稍後會補）")

        # ====== 本地備份 ======
        pd.DataFrame(st.session_state.results).to_csv("backup.csv", index=False)

        st.success("✔ 正確" if correct else "❌ 錯誤")

        st.session_state.index += 1
        st.rerun()

# ====== 完成 ======
else:
    st.success("🎉 完成")

    total = len(st.session_state.results)
    correct = st.session_state.correct
    acc = correct / total

    st.write(f"準確率：{acc:.2%}")

    # ====== 補寫剩餘 ======
    if st.session_state.saved_index < total:

        remain = st.session_state.results[st.session_state.saved_index:]

        rows = [[
            r["user"],
            r["sentence"],
            r["model_emotion"],
            r["human_emotion"],
            r["correct"]
        ] for r in remain]

        success = safe_append(sheet, rows)

        if success:
            st.success("✅ 最終補寫成功")
        else:
            st.error("❌ 最終補寫失敗（請用 backup.csv）")

    # ====== 寫統計 ======
    try:
        safe_append(stats_sheet, [[
            st.session_state.user_name,
            total,
            correct,
            acc
        ]])
    except:
        pass

    # ====== 下載 ======
    df = pd.DataFrame(st.session_state.results)
    st.download_button("下載結果", df.to_csv(index=False), "result.csv")

    if st.button("重新開始"):
        st.session_state.clear()
        st.rerun()
