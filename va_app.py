import streamlit as st
import pandas as pd
import os
import time

# ====== Google Sheets ======
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ====== 設定 ======
FILE_PATH = "output/high_quality_dataset.csv"

EMOTIONS = [
    "joy", "sadness", "anger", "fear",
    "regret", "hope", "loneliness", "empathy",
    "awe", "gratitude", "inner_peace", "compassion"
]

# ====== Google Sheets 連線 ======
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = st.secrets["gcp_service_account"]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict, scope
)

client = gspread.authorize(creds)

# 🔥 改成你的 sheet_id（強烈建議）
SHEET_ID = "1BjiqJNwUE4ZeCxBtYRJ3qLUBym_2bAhHEZa93zWol1c"

sheet = client.open_by_key(SHEET_ID).sheet1
stats_sheet = client.open_by_key(SHEET_ID).worksheet("user_stats")

# ====== 初始化 Session ======
if "data" not in st.session_state:
    st.session_state.data = pd.read_csv(FILE_PATH)
    st.session_state.sample = st.session_state.data.sample(n=10).reset_index(drop=True)
    st.session_state.index = 0
    st.session_state.correct = 0
    st.session_state.results = []

# ====== 使用者名稱（只輸入一次）======
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

if not st.session_state.user_name:
    st.title("📊 情緒分類人工驗證系統")
    name_input = st.text_input("請輸入你的名字：")

    if st.button("開始測驗"):
        if name_input:
            st.session_state.user_name = name_input
            st.rerun()
        else:
            st.warning("⚠️ 請輸入名字")

    st.stop()

# ====== UI ======
st.title("📊 情緒分類人工驗證系統")

st.write(f"👤 使用者：{st.session_state.user_name}")
st.write(f"進度：{st.session_state.index + 1} / {len(st.session_state.sample)}")

# ====== 還有題目 ======
if st.session_state.index < len(st.session_state.sample):

    row = st.session_state.sample.iloc[st.session_state.index]

    st.subheader("句子：")
    st.write(row["sentence"])

    user_emotion = st.selectbox("選擇你認為的情緒：", EMOTIONS)

    if st.button("提交答案"):

        correct_answer = row["emotion"]
        is_correct = (user_emotion == correct_answer)

        if is_correct:
            st.session_state.correct += 1

        # 👉 存到 session（不立即寫入）
        st.session_state.results.append({
            "user": st.session_state.user_name,
            "sentence": row["sentence"],
            "model_emotion": correct_answer,
            "human_emotion": user_emotion,
            "correct": is_correct
        })

        st.success(f"正確答案：{correct_answer}")
        st.write("✔ 正確" if is_correct else "❌ 錯誤")

        st.session_state.index += 1
        st.rerun()

# ====== 全部完成 ======
else:
    st.success("🎉 測試完成！")

    total = len(st.session_state.sample)
    correct = st.session_state.correct
    acc = correct / total

    st.write(f"👤 使用者：{st.session_state.user_name}")
    st.write(f"總題數：{total}")
    st.write(f"正確數：{correct}")
    st.write(f"準確率：{acc:.2%}")

    # ====== 批次寫入 Google Sheets ======
    try:
        rows = []
        for r in st.session_state.results:
            rows.append([
                r["user"],
                r["sentence"],
                r["model_emotion"],
                r["human_emotion"],
                r["correct"]
            ])

        sheet.append_rows(rows)

        st.success("✅ 詳細資料已寫入 Google Sheets")

    except Exception as e:
        st.error(f"寫入詳細資料失敗：{e}")

    # ====== 寫入使用者統計 ======
    try:
        stats_sheet.append_row([
            st.session_state.user_name,
            total,
            correct,
            acc
        ])
        st.success("✅ 使用者統計已寫入")

    except Exception as e:
        st.error(f"寫入統計失敗：{e}")

    # ====== 本地儲存 ======
    result_df = pd.DataFrame(st.session_state.results)

    os.makedirs("output", exist_ok=True)
    result_df.to_csv("output/human_evaluation_result.csv", index=False)

    st.download_button(
        label="📥 下載結果 CSV",
        data=result_df.to_csv(index=False),
        file_name="human_evaluation_result.csv",
        mime="text/csv"
    )

    # ====== 重新開始 ======
    if st.button("重新開始"):
        st.session_state.clear()
        st.rerun()
