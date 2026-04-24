import streamlit as st
import pandas as pd
import time
import uuid
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
    except:
        return None, None

# ====== 安全寫入（防重複 + 防429）======
def safe_append(sheet, rows, retries=5):
    if sheet is None or not rows:
        return False

    # ⭐ 去重（防 rerun / retry）
    unique_rows = []
    seen = set()

    for r in rows:
        key = tuple(r)
        if key not in seen:
            seen.add(key)
            unique_rows.append(r)

    for i in range(retries):
        try:
            sheet.append_rows(unique_rows)
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
    st.session_state.sample = (
        st.session_state.data
        .drop_duplicates(subset=["sentence"])
        .sample(n=20)
        .reset_index(drop=True)
    )
    st.session_state.index = 0
    st.session_state.correct = 0
    st.session_state.results = []
    st.session_state.saved_index = 0

# ⭐ 每個人唯一 session
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

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
total_q = len(st.session_state.sample)
current = st.session_state.index

if current < total_q:
    st.write(f"進度：{current+1} / {total_q}")
else:
    st.write(f"進度：{total_q} / {total_q}")

st.write(f"👤 使用者：{st.session_state.user_name}")

# ====== 題目 ======
if st.session_state.index < total_q:

    row = st.session_state.sample.iloc[st.session_state.index]

    st.subheader("句子")
    st.write(row["sentence"])

    user_emotion = st.selectbox("選擇情緒", EMOTIONS)

    if st.button("提交"):

        correct = (user_emotion == row["emotion"])
        if correct:
            st.session_state.correct += 1

        # ⭐ 每筆唯一
        st.session_state.results.append({
            "id": str(uuid.uuid4()),
            "session_id": st.session_state.session_id,
            "user": st.session_state.user_name,
            "sentence": row["sentence"],
            "model_emotion": row["emotion"],
            "human_emotion": user_emotion,
            "correct": correct
        })

        # 本地備份
        pd.DataFrame(st.session_state.results).to_csv("backup.csv", index=False)

        # ====== CHECKPOINT ======
        if len(st.session_state.results) % CHECKPOINT == 0:

            sheet, _ = get_sheets()

            new_rows = []
            for r in st.session_state.results[st.session_state.saved_index:]:
                new_rows.append([
                    r["id"],
                    r["session_id"],
                    r["user"],
                    r["sentence"],
                    r["model_emotion"],
                    r["human_emotion"],
                    r["correct"]
                ])

            success = safe_append(sheet, new_rows)

            if success:
                st.session_state.saved_index = len(st.session_state.results)

        st.session_state.index += 1
        st.rerun()

# ====== 完成 ======
else:
    st.success("🎉 完成！感謝你的填答")

    total = len(st.session_state.results)
    correct = st.session_state.correct
    acc = correct / total if total > 0 else 0

    sheet, stats_sheet = get_sheets()

    # ====== 補寫 ======
    if st.session_state.saved_index < len(st.session_state.results):

        remaining = st.session_state.results[st.session_state.saved_index:]
        rows = []

        for r in remaining:
            rows.append([
                r["id"],
                r["session_id"],
                r["user"],
                r["sentence"],
                r["model_emotion"],
                r["human_emotion"],
                r["correct"]
            ])

        success = safe_append(sheet, rows)
        if success:
            st.session_state.saved_index = len(st.session_state.results)

    # ====== 統計 ======
    if stats_sheet:
        try:
            stats_sheet.append_row([
                st.session_state.session_id,
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
