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

# ====== Google Client（只初始化一次）======
@st.cache_resource
def get_client():
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    return gspread.authorize(creds)

# ====== 延遲取得 Sheet ======
def get_sheets():
    try:
        client = get_client()
        sheet = client.open_by_key(SHEET_ID).sheet1
        stats_sheet = client.open_by_key(SHEET_ID).worksheet("user_stats")
        return sheet, stats_sheet
    except Exception as e:
        st.warning(f"⚠️ Google Sheets 連線失敗，改用本地備份：{e}")
        return None, None

# ====== 安全寫入（防 429）======
def safe_append(sheet, rows, retries=5):
    if sheet is None:
        return False

    for i in range(retries):
        try:
            sheet.append_rows(rows)
            return True
        except Exception as e:
            if "429" in str(e):
                wait = 2 ** i
                st.warning(f"⚠️ API 限流，等待 {wait}s 重試...")
                time.sleep(wait)
            else:
                st.error(f"❌ 寫入錯誤：{e}")
                return False
    return False

# ====== 初始化 ======
if "data" not in st.session_state:
    st.session_state.data = pd.read_csv(FILE_PATH)
    st.session_state.sample = st.session_state.data.sample(n=20).reset_index(drop=True)
    st.session_state.index = 0
    st.session_state.results = []
    st.session_state.saved_index = 0

if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# ====== 使用者登入 ======
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

        # 只記錄，不顯示正確與否
        st.session_state.results.append({
            "user": st.session_state.user_name,
            "sentence": row["sentence"],
            "model_emotion": row["emotion"],
            "human_emotion": user_emotion
        })

        # ====== 本地備份 ======
        pd.DataFrame(st.session_state.results).to_csv("backup.csv", index=False)

        # ====== CHECKPOINT 才寫入 Google ======
        if len(st.session_state.results) % CHECKPOINT == 0:

            sheet, _ = get_sheets()

            new_rows = []
            for r in st.session_state.results[st.session_state.saved_index:]:
                new_rows.append([
                    r["user"],
                    r["sentence"],
                    r["model_emotion"],
                    r["human_emotion"]
                ])

            success = safe_append(sheet, new_rows)

            if success:
                st.session_state.saved_index = len(st.session_state.results)
                st.success(f"✅ 已同步 {len(new_rows)} 筆到 Google Sheets")
            else:
                st.warning("⚠️ 未成功寫入 Google Sheets（已保存在本地 backup.csv）")

        st.session_state.index += 1
        st.rerun()

# ====== 完成 ======
else:
    st.success("🎉 完成！感謝你的填答")

    # ====== 補寫剩餘 ======
    sheet, stats_sheet = get_sheets()

    if st.session_state.saved_index < len(st.session_state.results):

        remaining = st.session_state.results[st.session_state.saved_index:]
        rows = []

        for r in remaining:
            rows.append([
                r["user"],
                r["sentence"],
                r["model_emotion"],
                r["human_emotion"]
            ])

        safe_append(sheet, rows)

    # ====== 寫統計（只記錄作答數）======
    if stats_sheet:
        try:
            stats_sheet.append_row([
                st.session_state.user_name,
                len(st.session_state.results)
            ])
        except:
            pass

    if st.button("重新開始"):
        st.session_state.clear()
        st.rerun()
