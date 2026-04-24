import streamlit as st
import pandas as pd
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ====== 設定 ======
FILE_PATH = "output/high_quality_dataset.csv"
SHEET_ID = "1BjiqJNwUE4ZeCxBtYRJ3qLUBym_2bAhHEZa93zWol1c"
CHECKPOINT = 10

EMOTIONS = [
    "joy", "sadness", "anger", "fear",
    "regret", "hope", "loneliness", "empathy",
    "awe", "gratitude", "inner_peace", "compassion"
]

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ====== Google Client ======
@st.cache_resource
def get_client():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    return gspread.authorize(creds)

def get_sheets():
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        stats_sheet = client.open_by_key(SHEET_ID).worksheet("user_stats")
        return sheet, stats_sheet
    except Exception as e:
        st.warning(f"⚠️ Google Sheets 連線失敗：{e}")
        return None, None

# ====== 安全寫入 ======
def safe_append(sheet, rows, retries=5):
    if sheet is None:
        return False

    for i in range(retries):
        try:
            sheet.append_rows(rows)
            return True
        except Exception as e:
            if "429" in str(e):
                time.sleep(2 ** i)
            else:
                return False
    return False

# ====== 初始化 ======
if "data" not in st.session_state:
    st.session_state.data = pd.read_csv(FILE_PATH)
    st.session_state.sample = st.session_state.data.sample(n=20).reset_index(drop=True)
    st.session_state.index = 0
    st.session_state.correct = 0   # ⭐ 保留
    st.session_state.results = []
    st.session_state.saved_index = 0

if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# ====== 登入 ======
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
current = st.session_state.index
total = len(st.session_state.sample)

if current < total:
    st.write(f"進度：{current + 1} / {total}")
else:
    st.write(f"進度：{total} / {total}")

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

        # ⭐ 後端完整記錄
        st.session_state.results.append({
            "user": st.session_state.user_name,
            "sentence": row["sentence"],
            "model_emotion": row["emotion"],
            "human_emotion": user_emotion,
            "correct": correct
        })

        # 本地備份
        pd.DataFrame(st.session_state.results).to_csv("backup.csv", index=False)

        # ====== 批次寫入 ======
        if len(st.session_state.results) % CHECKPOINT == 0:

            sheet, _ = get_sheets()

            new_rows = []
            for r in st.session_state.results[st.session_state.saved_index:]:
                new_rows.append([
                    r["user"],
                    r["sentence"],
                    r["model_emotion"],
                    r["human_emotion"],
                    r["correct"]
                ])

            success = safe_append(sheet, new_rows)

            if success:
                st.session_state.saved_index = len(st.session_state.results)

        # ❌ 不顯示正確錯誤（你要的）
        st.session_state.index += 1
        st.rerun()

# ====== 完成 ======
else:
    st.success("🎉 完成！感謝你的填答")

    total = len(st.session_state.results)
    correct = st.session_state.correct
    acc = correct / total if total > 0 else 0

    sheet, stats_sheet = get_sheets()

    # 補寫剩餘
    if st.session_state.saved_index < len(st.session_state.results):
    
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
    
        # ⭐ 關鍵修改
        success = safe_append(sheet, rows)
    
        if success:
            st.session_state.saved_index = len(st.session_state.results)

    # ⭐ 寫入統計（你後端看的）
    if stats_sheet:
        try:
            stats_sheet.append_row([
                st.session_state.user_name,
                total,
                correct,
                acc
            ])
        except:
            pass

    if st.button("重新開始"):
        st.session_state.clear()
        st.rerun()
