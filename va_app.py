import streamlit as st
import pandas as pd
import random
import os

# ====== 設定 ======
FILE_PATH = "output/high_quality_dataset.csv"

EMOTIONS = [
    "joy", "sadness", "anger", "fear",
    "regret", "hope", "loneliness", "empathy",
    "awe", "gratitude", "inner_peace", "compassion"
]

# ====== 初始化 Session ======
if "data" not in st.session_state:
    st.session_state.data = pd.read_csv(FILE_PATH)
    st.session_state.sample = st.session_state.data.sample(n=10).reset_index(drop=True)
    st.session_state.index = 0
    st.session_state.correct = 0
    st.session_state.results = []

# ====== UI ======
st.title("📊 情緒分類人工驗證系統")

# ====== 顯示進度 ======
st.write(f"進度：{st.session_state.index + 1} / {len(st.session_state.sample)}")

# ====== 當還有題目 ======
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

        st.session_state.results.append({
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

    st.write(f"總題數：{total}")
    st.write(f"正確數：{correct}")
    st.write(f"準確率：{acc:.2%}")

    # ====== 儲存結果 ======
    result_df = pd.DataFrame(st.session_state.results)

    os.makedirs("output", exist_ok=True)
    result_df.to_csv("output/human_evaluation_result.csv", index=False)

    st.download_button(
        label="📥 下載結果 CSV",
        data=result_df.to_csv(index=False),
        file_name="human_evaluation_result.csv",
        mime="text/csv"
    )

    if st.button("重新開始"):
        st.session_state.clear()
        st.rerun()