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
CHECKPOINT = 10   # 每 10 題存檔一次

EMOTIONS = [
    "joy", "sadness", "anger", "fear",
    "regret", "hope", "loneliness", "empathy",
    "awe", "gratitude", "inner_peace", "compassion"
]

# ====== 安全寫入函數（加入指數退避機制） ======
def safe_append(sheet_obj, rows):
    """
    sheet_obj: gspread worksheet 對象
    rows: 二維列表，例如 [[col1, col2], [col1, col2]]
    """
    for i in range(5):
        try:
            sheet_obj.append_rows(rows)
            return True
        except Exception as e:
            time.sleep(2 ** i) # 1, 2, 4, 8, 16 秒
    return False

# ====== 初始化 Google Sheets（使用 Session State 緩存連線） ======
if "sheet" not in st.session_state:
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        # 從 st.secrets 讀取憑證
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], scope
        )
        client = gspread.authorize(creds)
        
        # 預先開啟分頁
        spr = client.open_by_key(SHEET_ID)
        st.session_state.sheet = spr.sheet1
        st.session_state.stats_sheet = spr.worksheet("user_stats")
    except Exception as e:
        st.error(f"❌ 無法連線至 Google Sheets: {e}")
        st.stop()

sheet = st.session_state.sheet
stats_sheet = st.session_state.stats_sheet

# ====== 初始化資料與狀態 ======
if "data" not in st.session_state:
    if os.path.exists(FILE_PATH):
        df = pd.read_csv(FILE_PATH)
        n = min(TOTAL_QUESTIONS, len(df))
        st.session_state.sample = df.sample(n=n).reset_index(drop=True)
    else:
        st.error(f"找不到檔案: {FILE_PATH}")
        st.stop()
        
    st.session_state.index = 0
    st.session_state.correct = 0
    st.session_state.results = []
    st.session_state.saved_index = 0

# ====== 第一步：使用者登入 ======
if "user_name" not in st.session_state or not st.session_state.user_name:
    st.title("📊 情緒分類驗證系統")
    name = st.text_input("請輸入您的姓名以開始：")
    if st.button("開始測驗"):
        if name.strip():
            st.session_state.user_name = name.strip()
            st.rerun()
        else:
            st.warning("⚠️ 請輸入名字後再繼續")
    st.stop()

# ====== 第二步：測驗 UI ======
st.title("📊 情緒分類驗證系統")
st.sidebar.write(f"👤 當前使用者：**{st.session_state.user_name}**")
st.sidebar.write(f"📈 進度：{st.session_state.index + 1} / {len(st.session_state.sample)}")

# 判斷是否還有題目
if st.session_state.index < len(st.session_state.sample):
    row = st.session_state.sample.iloc[st.session_state.index]
    
    st.subheader("待驗證句子：")
    st.info(f"「 {row['sentence']} 」")

    user_emotion = st.selectbox("您認為這句話屬於哪種情緒？", EMOTIONS, index=0)

    if st.button("提交回答", use_container_width=True):
        # 判定對錯
        is_correct = (user_emotion == row["emotion"])
        if is_correct:
            st.session_state.correct += 1

        # 存入結果清單
        st.session_state.results.append({
            "user": st.session_state.user_name,
            "sentence": row["sentence"],
            "model_emotion": row["emotion"],
            "human_emotion": user_emotion,
            "correct": is_correct
        })

        # 回饋顯示（讓使用者看到結果再跳下一題）
        if is_correct:
            st.success("✔ 正確！")
        else:
            st.error(f"❌ 錯誤。模型預測為：{row['emotion']}")

        # ====== Checkpoint 自動寫入 (每 10 題) ======
        if len(st.session_state.results) % CHECKPOINT == 0:
            new_data = st.session_state.results[st.session_state.saved_index:]
            rows = [[r["user"], r["sentence"], r["model_emotion"], r["human_emotion"], r["correct"]] for r in new_data]
            
            if safe_append(sheet, rows):
                st.session_state.saved_index = len(st.session_state.results)
                st.toast("✅ 進度已自動同步至雲端")
            else:
                st.warning("⚠️ 雲端同步失敗，系統將在測驗結束時重試")

        # 本地備份 CSV
        pd.DataFrame(st.session_state.results).to_csv("backup_results.csv", index=False)
        
        # 暫停一下再跳轉
        time.sleep(1.2)
        st.session_state.index += 1
        st.rerun()

# ====== 第三步：測驗結算 ======
else:
    st.balloons()
    st.success("🎉 恭喜！您已完成所有情緒驗證任務。")

    total = len(st.session_state.results)
    correct = st.session_state.correct
    acc = correct / total

    # 顯示統計圖表或數字
    col1, col2, col3 = st.columns(3)
    col1.metric("總題數", total)
    col2.metric("正確數", correct)
    col3.metric("準確率", f"{acc:.2%}")

    # ====== 1. 補寫剩餘資料到 Sheets ======
    if st.session_state.saved_index < total:
        remain = st.session_state.results[st.session_state.saved_index:]
        rows = [[r["user"], r["sentence"], r["model_emotion"], r["human_emotion"], r["correct"]] for r in remain]
        
        if safe_append(sheet, rows):
            st.session_state.saved_index = total
            st.write("✅ 剩餘數據已補寫成功")
        else:
            st.error("❌ 最終同步失敗，請務必下載結果 CSV 存檔")

    # ====== 2. 寫入使用者統計總結 ======
    summary_data = [[st.session_state.user_name, total, correct, f"{acc:.2%}"]]
    if safe_append(stats_sheet, summary_data):
        st.write("✅ 統計總結已寫入 user_stats 分頁")

    # ====== 3. 下載與重置 ======
    final_df = pd.DataFrame(st.session_state.results)
    st.download_button(
        label="📥 下載完整驗證結果 CSV",
        data=final_df.to_csv(index=False),
        file_name=f"result_{st.session_state.user_name}.csv",
        mime="text/csv"
    )

    if st.button("重新開始 (清空當前紀錄)"):
        st.session_state.clear()
        st.rerun()
