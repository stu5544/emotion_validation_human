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
CHECKPOINT = 10

EMOTIONS = [
    "joy", "sadness", "anger", "fear",
    "regret", "hope", "loneliness", "empathy",
    "awe", "gratitude", "inner_peace", "compassion"
]

# ====== 安全寫入（retry） ======
def safe_append(sheet, rows):
    for i in range(5):
        try:
            sheet.append_rows(rows)
            return True
        except Exception:
            time.sleep(2 ** i)
    return False

# ====== 初始化 Google Sheets（只做一次） ======
if "sheet" not in st.session_state:
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], scope
        )
        client = gspread.authorize(creds)

        spr = client.open_by_key(SHEET_ID)
        st.session_state.sheet = spr.sheet1
        st.session_state.stats_sheet = spr.worksheet("user_stats")

    except Exception as e:
        st.error(f"❌ 無法連線 Google Sheets: {e}")
        st.stop()

sheet = st.session_state.sheet
stats_sheet = st.session_state.stats_sheet

# ====== 初始化資料 ======
if "data" not in st.session_state:
    if not os.path.exists(FILE_PATH):
        st.error("找不到資料檔")
        st.stop()

    df = pd.read_csv(FILE_PATH)
    n = min(TOTAL_QUESTIONS, len(df))

    # 固定每個人題目（避免重複）
    seed = hash(st.session_state.get("user_name", "")) % 10000
    st.session_state.sample = df.sample(n=n, random_state=seed).reset_index(drop=True)

    st.session_state.index = 0
    st.session_state.correct = 0
    st.session_state.results = []
    st.session_state.saved_index = 0

# ====== 使用者登入 ======
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

if not st.session_state.user_name:
    st.title("📊 情緒分類驗證系統")
    name = st.text_input("請輸入名字")

    if st.button("開始"):
        if name.strip():
            st.session_state.user_name = name.strip()
            st.rerun()
        else:
            st.warning("請輸入名字")

    st.stop()

# ====== UI ======
st.title("📊 情緒分類驗證系統")
st.sidebar.write(f"👤 使用者：{st.session_state.user_name}")
st.sidebar.write(f"進度：{st.session_state.index + 1} / {len(st.session_state.sample)}")

# ====== 題目 ======
if st.session_state.index < len(st.session_state.sample):

    row = st.session_state.sample.iloc[st.session_state.index]

    st.subheader("句子")
    st.info(row["sentence"])

    user_emotion = st.selectbox(
        "選擇情緒",
        ["請選擇情緒"] + EMOTIONS
    )

    if st.button("提交"):

        # ❌ 防止沒選
        if user_emotion == "請選擇情緒":
            st.warning("請先選擇情緒")
        else:
            is_correct = (user_emotion == row["emotion"])

            if is_correct:
                st.session_state.correct += 1

            st.session_state.results.append({
                "user": st.session_state.user_name,
                "sentence": row["sentence"],
                "model_emotion": row["emotion"],
                "human_emotion": user_emotion,
                "correct": is_correct
            })

            # ====== checkpoint 寫入 ======
            if len(st.session_state.results) % CHECKPOINT == 0:
                new_data = st.session_state.results[st.session_state.saved_index:]

                rows = [[
                    r["user"],
                    r["sentence"],
                    r["model_emotion"],
                    r["human_emotion"],
                    r["correct"]
                ] for r in new_data]

                if safe_append(sheet, rows):
                    st.session_state.saved_index = len(st.session_state.results)
                    st.toast("已同步雲端")
                else:
                    st.warning("雲端寫入失敗，稍後補寫")

            # 本地備份（避免資料全丟）
            backup_file = f"backup_{st.session_state.user_name}.csv"
            pd.DataFrame(st.session_state.results).to_csv(backup_file, index=False)

            st.session_state.index += 1
            st.rerun()

# ====== 完成 ======
else:
    st.success("🎉 完成")

    total = len(st.session_state.results)
    correct = st.session_state.correct
    acc = correct / total if total > 0 else 0

    st.metric("準確率", f"{acc:.2%}")

    # ====== 補寫 ======
    if st.session_state.saved_index < total:
        remain = st.session_state.results[st.session_state.saved_index:]

        rows = [[
            r["user"],
            r["sentence"],
            r["model_emotion"],
            r["human_emotion"],
            r["correct"]
        ] for r in remain]

        safe_append(sheet, rows)

    # ====== 統計寫入（避免重複） ======
    existing = stats_sheet.col_values(1)

    if st.session_state.user_name not in existing:
        safe_append(stats_sheet, [[
            st.session_state.user_name,
            total,
            correct,
            acc
        ]])

    # ====== 下載 ======
    df = pd.DataFrame(st.session_state.results)
    st.download_button(
        "下載結果",
        df.to_csv(index=False),
        f"{st.session_state.user_name}_result.csv"
    )

    if st.button("重新開始"):
        st.session_state.clear()
        st.rerun()
