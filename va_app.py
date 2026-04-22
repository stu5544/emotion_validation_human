import streamlit as st
import pandas as pd
import os

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

# ====== Google Sheets 連線（用 secrets）======
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_dict = st.secrets["gcp_service_account"]

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    creds_dict, scope
)

client = gspread.authorize(creds)

# ⚠️ 改成你的試算表名稱
sheet = client.open_by_key("1BjiqJNwUE4ZeCxBtYRJ3qLUBym_2bAhHEZa93zWol1c").sheet1


# ====== 初始化 Session ======
if "data" not in st.session_state:
    st.session_state.data = pd.read_csv(FILE_PATH)
    st.session_state.sample = st.session_state.data.sample(n=10).reset_index(drop=True)
    st.session_state.index = 0
    st.session_state.correct = 0
    st.session_state.results = []

# ====== UI ======
st.title("📊 情緒分類人工驗證系統")

# 👉 使用者名稱
user_name = st.text_input("請輸入你的名字：")

# ====== 顯示進度 ======
st.write(f"進度：{st.session_state.index + 1} / {len(st.session_state.sample)}")

# ====== 還有題目 ======
if st.session_state.index < len(st.session_state.sample):

    row = st.session_state.sample.iloc[st.session_state.index]

    st.subheader("句子：")
    st.write(row["sentence"])

    user_emotion = st.selectbox("選擇你認為的情緒：", EMOTIONS)

    if st.button("提交答案"):

        # ====== 防呆 ======
        if not user_name:
            st.warning("⚠️ 請先輸入名字")
            st.stop()

        correct_answer = row["emotion"]
        is_correct = (user_emotion == correct_answer)

        if is_correct:
            st.session_state.correct += 1

        # ====== 寫入 Google Sheets ======
        try:
            sheet.append_row([
                user_name,
                row["sentence"],
                correct_answer,
                user_emotion,
                is_correct
            ])
        except Exception as e:
            st.error(f"寫入 Google Sheets 失敗：{e}")

        # ====== 本地紀錄 ======
        st.session_state.results.append({
            "user": user_name,
            "sentence": row["sentence"],
            "model_emotion": correct_answer,
            "human_emotion": user_emotion,
            "correct": is_correct
        })

        # ====== 顯示結果 ======
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

    st.write(f"總題數：{total}")
    st.write(f"正確數：{correct}")
    st.write(f"準確率：{acc:.2%}")

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
