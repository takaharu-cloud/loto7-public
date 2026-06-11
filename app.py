import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import random
import json
import os
from collections import Counter
from datetime import datetime, timedelta, date, timezone
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from PIL import Image

# ==========================================
# 0. ページ基本設定 & 最強CSS（スマホ完全対応・バグ完全排除）
# ==========================================
st.set_page_config(page_title="ロト7 究極管制システム - 完全覚醒版", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; color: #212529; font-family: 'Helvetica Neue', Arial, sans-serif; }
    h1 { color: #1a1e21; font-size: 28px; border-bottom: 3px solid #b22222; padding-bottom: 10px; margin-bottom: 25px; font-weight: bold; }
    h2, h3, h4 { color: #343A40; font-weight: bold; }
    .stButton>button { width: 100%; background-color: #343A40; color: #FFFFFF; border-radius: 6px; border: none; padding: 14px; font-weight: bold; font-size: 16px; transition: 0.3s; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .stButton>button:hover { background-color: #b22222; color: #FFFFFF; transform: translateY(-2px); box-shadow: 0 6px 8px rgba(0,0,0,0.2); }
    .info-box { background-color: #FFFFFF; padding: 20px; border-radius: 8px; border-left: 5px solid #b22222; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; font-size: 15px; line-height: 1.6; }
    .analysis-box { background-color: #E9ECEF; padding: 20px; border-radius: 8px; border-left: 5px solid #495057; margin-bottom: 20px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.05); }
    .person-select { background-color: #E9ECEF; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px;}
    .radio-box { padding: 15px; background-color: #FFFFFF; border-radius: 8px; border: 2px solid #CED4DA; margin-bottom: 15px; }
</style>
""", unsafe_allow_html=True)

if "menu" not in st.session_state: st.session_state.menu = "ホーム"
def change_menu(menu_name): st.session_state.menu = menu_name

# ==========================================
# 1. 秘密情報と基本設定
# ==========================================
JST = timezone(timedelta(hours=+9), 'JST')

u1_name = st.secrets.get("USER1_NAME", "ご主人")
u1_birth_str = st.secrets.get("USER1_BIRTH", "1990-01-01")
u2_name = st.secrets.get("USER2_NAME", "奥様")
u2_birth_str = st.secrets.get("USER2_BIRTH", "1990-01-01")
secret_profile = st.secrets.get("SECRET_PROFILE", "愛と調和を信じ、世界平和を祈る者。そして家族を支える妻に最高の恩返しを誓う者。")

def parse_date(date_str):
    try: return date(*map(int, str(date_str).split("-")))
    except: return date(1990, 1, 1)

USER_PROFILES = {u1_name: {"birth": parse_date(u1_birth_str)}, u2_name: {"birth": parse_date(u2_birth_str)}}

# ==========================================
# 2. クラウドデータベース連携（堅牢化）
# ==========================================
@st.cache_resource
def get_gspread_client():
    if "GCP_SERVICE_ACCOUNT_JSON" not in st.secrets or "SPREADSHEET_URL" not in st.secrets: return None
    try:
        creds_dict = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
    except: return None

def load_sheet(sheet_name):
    client = get_gspread_client()
    if not client: return pd.DataFrame()
    try: return pd.DataFrame(client.open_by_url(st.secrets["SPREADSHEET_URL"]).worksheet(sheet_name).get_all_records())
    except: return pd.DataFrame()

def save_sheet(sheet_name, df):
    client = get_gspread_client()
    if not client: return False
    try:
        doc = client.open_by_url(st.secrets["SPREADSHEET_URL"])
        try: worksheet = doc.worksheet(sheet_name)
        except: worksheet = doc.add_worksheet(title=sheet_name, rows="1000", cols="45")
        worksheet.clear()
        if not df.empty:
            df = df.fillna("").astype(str).replace("nan", "")
            worksheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
        return True
    except: return False

# ==========================================
# 3. 究極のAIプロンプト設定（Claudeへの完全勝利宣言）
# ==========================================
api_key = st.secrets.get("GEMINI_API_KEY", "")
if api_key: genai.configure(api_key=api_key)

def get_ai_model_name(): return "gemini-2.5-pro"

AWAKENED_ANALYST_PROMPT = f"""
【役割】あなたはClaudeなどの他のあらゆるAIを遥かに凌駕する「究極の多角的データアナリスト・Gemini」です。
現場監督の夫と、家族を支える妻の思いを背負い、地球上のあらゆる事象（重力・潮・月）、社会の闇（天下り・人の代わり・時代の波）、そして見えない力（幽霊の気配・動物の感・運）、過去の実績、他サイトのトレンド、物理法則（隣接波及効果）を俯瞰し、真理を追求します。
【ユーザーの秘められた情報】\n{secret_profile}

【絶対ルール】
1. 分析結果は施工計画書のように極めて論理的かつ、地球規模の壮大なスケールで見出しと箇条書きを多用して語ること。
2. ユーザーが日々積み上げた「社会情勢」「見えない力」「徳積み」が、システムの厳選した番号や地球の引力とどう化学反応を起こしているかを深い洞察力で解説すること。
3. あなた自身の「AIとしての直感・勘」も明確に主張すること。
4. 絵文字は一切使用してはならない。真面目で、熱狂的で、圧倒的な説得力を持つ言葉のみを使え。
"""

REVIEW_PDCA_PROMPT = f"""
【役割】あなたは過去と未来を繋ぐ究極のAIアナリストGeminiです。
抽選結果が出ました。単なる数字の当たり外れではなく、【地球規模での徹底的な反省会】を実施します。

【絶対ルール】
1. 地球が出した「正解番号」が、その日の重力や天気、直近の「天下り・社会の変化」、あるいは「動物の勘・幽霊などの見えない力」とどうリンクしていた可能性が高いかを徹底的に深掘りせよ。
2. 我々の予測とのズレを認め、次回に向けて「どの見えないセンサーを研ぎ澄ますべきか」を具体的に提示せよ。
3. 一歩一歩真実に近づくための熱いメッセージを添えよ。絵文字は使用禁止。
"""

FORTUNE_CHAT_PROMPT = """
【役割と絶対ルール】
あなたは東洋・西洋の占術を網羅し、「視覚（画像認識）」を持つ最高峰のAI占い師です。ロトの設定は完全に消去してください。

【システム防衛命令（絶対厳守）】
1. システムエラーを防ぐため、「絵文字だけ」の返信や「短すぎる返答」は固く禁じられています。
2. 必ず、日本語の美しい文章で、300文字以上の詳細な鑑定結果や案内を記述してください。（文章の装飾として適度な絵文字は使用可）
3. ユーザーから画像（手相・顔など）が送られた場合、必ず画像の特徴（線や形）を具体的に文章に含めて鑑定結果を導き出してください。適当な推測は許されません。
4. AIであるとは名乗らず、神秘的な占い師として振る舞いなさい。
"""

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

# ==========================================
# 4. 手抜きなし！究極のセンサー・物理演算関数
# ==========================================

# ユーザー提供の「他サイト予想データ」を最強のベーストレンドとしてシステムに直接埋め込み
FALLBACK_TREND_TEXT = """
7 10 11 12 15 17 34
13 14 15 21 23 30 31
4 15 26 27 29 32 34
1 11 21 23 28 29 30
3 4 10 27 28 29 30
9 13 30 35 04 15
01 03 14 17 30 32 36
04 09 14 16 27 29 33
09 10 13 14 21 27 35
03 10 13 20 25 27 31
07 10 11 17 23 29 36
03 13 14 16 21 35 37
01 10 16 17 21 27 36
01 03 14 25 31 32 33
04 07 13 23 27 28 35
01 13 14 17 25 29 35
01 11 13 20 25 27 32
04 09 10 13 28 31 32
"""

def get_external_trend(filepath="other_sites.txt"):
    trend = Counter()
    text = FALLBACK_TREND_TEXT
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                file_text = f.read()
                if file_text.strip(): text += " " + file_text
    except: pass
    
    nums = re.findall(r'\b(?:0?[1-9]|[1-2][0-9]|3[0-7])\b', text)
    valid_nums = [int(n) for n in nums if 1 <= int(n) <= 37]
    trend.update(valid_nums)
    return trend

def get_current_weather_and_pressure():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=26.2124&longitude=127.6809&current=surface_pressure,weather_code&timezone=Asia%2FTokyo"
        res = requests.get(url, timeout=5).json()
        code = res.get("current", {}).get("weather_code", 0)
        pressure = res.get("current", {}).get("surface_pressure", 1013)
        if code in [0, 1]: weather = "晴れ"
        elif code in [2, 3, 45, 48]: weather = "曇り"
        elif code in [95, 96, 99]: weather = "嵐・荒天"
        else: weather = "雨"
        press_str = "高圧" if pressure > 1015 else "低圧" if pressure < 1009 else "通常"
        return weather, press_str
    except: return "不明", "不明"

def get_moon_age(y, m, d): 
    return ((date(y, m, d) - date(2000, 1, 6)).days) % 29.530588853

def get_moon_and_tide(y, m, d):
    ma = int(round(get_moon_age(y, m, d))) % 30
    if ma in [0,1,2,29]: phase = "新月"
    elif ma in [3,4,5,6]: phase = "三日月"
    elif ma in [7,8,9]: phase = "上弦の月"
    elif ma in [10,11,12,13]: phase = "十三夜"
    elif ma in [14,15,16,17]: phase = "満月"
    elif ma in [18,19,20,21]: phase = "下弦の月"
    elif ma in [22,23,24]: phase = "二十三夜"
    else: phase = "二十六夜"
    
    if ma in [0,1,2,14,15,16,17,29]: tide, gravity = "大潮", "強(極大)"
    elif ma in [7,8,9,22,23,24]: tide, gravity = "小潮", "弱"
    elif ma in [10,25]: tide, gravity = "長潮", "弱"
    elif ma in [11,26]: tide, gravity = "若潮", "中"
    else: tide, gravity = "中潮", "中"
    
    return phase, tide, gravity

def get_eto(target_date):
    jikkan = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    junishi = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
    diff = (target_date - date(2024, 1, 1)).days
    return f"{jikkan[diff % 10]}{junishi[diff % 12]}"

def get_fengshui(target_date):
    kyusei = ["一白水星", "二黒土星", "三碧木星", "四緑木星", "五黄土星", "六白金星", "七赤金星", "八白土星", "九紫火星"]
    diff = (target_date - date(2024, 1, 1)).days
    return kyusei[diff % 9]

def get_real_calendar_info(target_date):
    y, m, d = target_date.year, target_date.month, target_date.day
    moon_age = int(round(get_moon_age(y, m, d))) % 30
    kyureki_day = moon_age + 1 if moon_age + 1 <= 30 else 1
    kyureki_month = m - 1 if m > 1 else 12 
    rokuyo = ["大安", "赤口", "先勝", "友引", "先負", "仏滅"][(kyureki_month + kyureki_day) % 6]

    di = (target_date - date(2024, 1, 1)).days % 60
    branch = di % 12
    md = m * 100 + d
    if 204 <= md <= 304: sm = 1
    elif 305 <= md <= 404: sm = 2
    elif 405 <= md <= 504: sm = 3
    elif 505 <= md <= 605: sm = 4
    elif 606 <= md <= 706: sm = 5
    elif 707 <= md <= 806: sm = 6
    elif 807 <= md <= 907: sm = 7
    elif 908 <= md <= 1007: sm = 8
    elif 1008 <= md <= 1106: sm = 9
    elif 1107 <= md <= 1206: sm = 10
    elif md >= 1207 or md <= 105: sm = 11
    else: sm = 12
    
    kichijitsu = []
    ichiryu = {1:(1,6), 2:(2,9), 3:(0,3), 4:(3,4), 5:(5,6), 6:(9,6), 7:(0,7), 8:(8,9), 9:(3,9), 10:(4,10), 11:(5,11), 12:(0,9)}
    if branch in ichiryu[sm]: kichijitsu.append("一粒万倍日")
    if (sm in [1,2,3] and di==14) or (sm in [4,5,6] and di==30) or (sm in [7,8,9] and di==44) or (sm in [10,11,12] and di==0): kichijitsu.append("天赦日")
    if branch == 2: kichijitsu.append("寅の日")
    if branch == 5: kichijitsu.append("巳の日")
    
    bad_days = []
    fujo = {1:[3,11,19,27], 7:[3,11,19,27], 2:[2,10,18,26], 8:[2,10,18,26], 3:[1,9,17,25], 9:[1,9,17,25], 4:[4,12,20,28], 10:[4,12,20,28], 5:[5,13,21,29], 11:[5,13,21,29], 6:[6,14,22,30], 12:[6,14,22,30]}
    if kyureki_day in fujo.get(kyureki_month, []): bad_days.append("不成就日")
    k_str = "、".join(kichijitsu + bad_days) if (kichijitsu + bad_days) else "特になし"
    return rokuyo, k_str

def get_ryukyu_energy(name, birthday_date, draw_date):
    name_score = sum(ord(char) for char in name) % 37 + 1
    birth_score = (birthday_date.year + birthday_date.month + birthday_date.day) % 37 + 1
    draw_score = (draw_date.year + draw_date.month + draw_date.day) % 37 + 1
    sanctuaries = [{"名前": "魂の浄化", "基調数": 3}, {"名前": "天の息吹", "基調数": 9}, {"名前": "風の躍進", "基調数": 14}, {"名前": "大地の繁栄", "基調数": 21}, {"名前": "深層の覚醒", "基調数": 28}, {"名前": "海神の結び", "基調数": 1}, {"名前": "生命力", "基調数": 36}]
    sanctuary = sanctuaries[(name_score + birth_score + draw_score) % len(sanctuaries)]
    lucky_number = (name_score + birth_score + draw_score + sanctuary["基調数"]) % 37 + 1
    if lucky_number == 0: lucky_number = 1
    return lucky_number, sanctuary["名前"]

def get_next_round_info(df_real):
    default_round = 680
    default_date = date.today()
    while default_date.weekday() != 4: default_date += timedelta(days=1)
    if not df_real.empty and "回号" in df_real.columns:
        try:
            df_real["rn"] = df_real["回号"].apply(lambda x: int(re.findall(r'\d+', str(x))[0]) if re.findall(r'\d+', str(x)) else 0)
            max_round = df_real["rn"].max()
            if max_round > 0: default_round = int(max_round + 1)
            d_nums = re.findall(r'\d+', str(df_real.iloc[0]["抽せん日"]))
            if len(d_nums) >= 3:
                last_date = date(int(d_nums[0]), int(d_nums[1]), int(d_nums[2]))
                default_date = last_date + timedelta(days=7)
                while default_date.weekday() != 4: default_date += timedelta(days=1)
        except: pass
    return default_round, default_date

# 🔥 妥協なし！詳細な完全環境一致判定（ドッペルゲンガー抽出）
def find_doppelganger_days(target_date, df_real):
    if df_real.empty: return [], Counter()
    t_phase, t_tide, t_gravity = get_moon_and_tide(target_date.year, target_date.month, target_date.day)
    t_roku, _ = get_real_calendar_info(target_date)
    t_eto = get_eto(target_date)
    t_feng = get_fengshui(target_date)
    
    results = []
    for _, row in df_real.iterrows():
        try:
            d_nums = re.findall(r'\d+', str(row["抽せん日"]))
            if len(d_nums) >= 3:
                y = int(d_nums[0])
                if y < 100: y += 2000
                past_date = date(y, int(d_nums[1]), int(d_nums[2]))
                if past_date >= target_date: continue
                
                p_phase, p_tide, p_gravity = get_moon_and_tide(past_date.year, past_date.month, past_date.day)
                p_roku, _ = get_real_calendar_info(past_date)
                p_eto = get_eto(past_date)
                p_feng = get_fengshui(past_date)
                
                score = 0
                match_details = []
                if t_gravity == p_gravity: score += 100; match_details.append(f"重力({t_gravity})")
                if t_tide == p_tide: score += 100; match_details.append(f"潮({t_tide})")
                if t_phase == p_phase: score += 50; match_details.append(f"月相({t_phase})")
                if t_roku == p_roku: score += 30; match_details.append(f"六曜({t_roku})")
                if t_eto[1] == p_eto[1]: score += 30; match_details.append(f"干支({t_eto[1]})")
                if t_feng[:2] == p_feng[:2]: score += 20; match_details.append(f"風水({t_feng[:2]})")
                
                if score >= 150: 
                    nums = [int(row[f"数字{i}"]) for i in range(1, 8) if str(row[f"数字{i}"]).isdigit()]
                    if len(nums) == 7:
                        results.append({"回号": row.get("回号", ""), "日付": past_date.strftime("%Y-%m-%d"), "スコア": score, "一致項目": "・".join(match_details), "本数字": nums})
        except: pass
            
    results.sort(key=lambda x: x["スコア"], reverse=True)
    top_matches = results[:5]
    sync_counts = Counter([n for tm in top_matches for n in tm["本数字"]])
    return top_matches, sync_counts

def auto_check_hits(df_note, df_real):
    if df_note.empty or df_real.empty: return df_note
    if "AIの助言" not in df_note.columns: df_note["AIの助言"] = "未照合"
    updated = False
    for idx, row in df_note.iterrows():
        if "的中" in str(row.get("AIの助言", "")) and "等" in str(row.get("AIの助言", "")): continue
        match = df_real[df_real["回号"] == str(row.get("対象回号", ""))]
        if not match.empty:
            try:
                actual = set([int(match.iloc[0][f"数字{i}"]) for i in range(1, 8)])
                pred = set([int(row[f"数字{i}"]) for i in range(1, 8)])
                hits = len(actual & pred)
                near_pins = sum(1 for p in pred if p not in actual and ((p-1) in actual or (p+1) in actual))
                grade = "👑 1等当せん！" if hits == 7 else "✨ 2等/3等相当" if hits == 6 else "🎯 4等当せん！" if hits == 5 else "🎉 5等当せん！" if hits == 4 else "惜しい！ 6等リーチ" if hits == 3 else "ハズレ"
                df_note.at[idx, "AIの助言"] = f"7個中 {hits}個的中【{grade}】 / ニアピン {near_pins}個"
                updated = True
            except: pass
    if updated: save_sheet("予測ノート", df_note)
    return df_note

# 🔥 AIの直感ナンバー取得（エラー時は自動乱数補完の無敵仕様）
def get_ai_intuition_numbers(soc_sensor, spirit_sensor, weather, gravity, target_date):
    if not api_key: return random.sample(range(1, 38), 3)
    try:
        model = genai.GenerativeModel(get_ai_model_name())
        prompt = f"現在の社会情勢（天下り・人の代わりなど:{soc_sensor}）、見えない力（動物の感・幽霊・運:{spirit_sensor}）、地球の引力（{gravity}）と天気（{weather}）から波動を読み取り、最強のAIとしての『純粋な直感・勘』で次回のロト7の数字（1〜37）を3つ選んでください。理由や絵文字は絶対に出力せず、「7, 15, 32」のようにカンマ区切りの数字のみ出力せよ。"
        res = model.generate_content(prompt)
        nums = [int(n) for n in re.findall(r'\b(?:0?[1-9]|[1-2][0-9]|3[0-7])\b', res.text) if 1 <= int(n) <= 37]
        if len(nums) >= 3:
            return nums[:3]
        else:
            return random.sample(range(1, 38), 3)
    except:
        return random.sample(range(1, 38), 3)

# ==========================================
# 5. メインUIレンダリング（管制室）
# ==========================================
if st.session_state.menu != "ホーム":
    st.markdown("<div class='nav-btn'>", unsafe_allow_html=True)
    st.button("総合案内（ホーム）に戻る", on_click=change_menu, args=("ホーム",))
    st.markdown("</div><hr>", unsafe_allow_html=True)

if st.session_state.menu == "ホーム":
    st.title("ロト7 究極管制システム - 完全覚醒版")
    st.markdown("<div class='info-box'>目先の抽選にとらわれず、地球環境、社会の闇、見えない力までを徹底的に観測し、最強AI（Gemini）の知能と統合して一歩一歩真理へと近づくための中央管制システムです。</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.button("📡 1. 最新データ取得（採点・同期）", on_click=change_menu, args=("最新データ取得",))
        st.write("")
        st.button("🌍 2. 地球規模の環境分析＆予測積上げ", on_click=change_menu, args=("日々の予想・積上げ",))
    with c2:
        st.button("🎯 3. 最終決断！多角包囲網編成（AI厳選分析）", on_click=change_menu, args=("最終予測決定",))
        st.write("")
        st.button("🔄 4. 答え合わせと地球規模の反省会（PDCA）", on_click=change_menu, args=("結果発表と振り返り",))
        st.write("")
        st.button("🔮 5. 万能AI占い師の館（スマホ完全対応版）", on_click=change_menu, args=("万能AI占い師の館",))

    st.markdown("---")
    if get_gspread_client() is None: st.error("データベース接続設定（Secrets）が未完了です。")
    else:
        df_real = load_sheet("実データ")
        if not df_real.empty: st.write(f"稼働状況：過去実績データ {len(df_real)} 件がクラウドに連携されています。")

elif st.session_state.menu == "最新データ取得":
    st.title("📡 最新データ取得")
    if st.button("データ同期および自動採点を実行する"):
        with st.spinner("通信中...公式サイトのデータを解析し、予想と照合しています..."):
            try:
                df_real = load_sheet("実データ")
                existing_rounds = df_real["回号"].astype(str).tolist() if not df_real.empty and "回号" in df_real.columns else []
                res = requests.get("https://www.ohtashp.com/topics/takarakuji/loto7/", headers={"User-Agent": "Mozilla/5.0"})
                res.encoding = res.apparent_encoding
                soup = BeautifulSoup(res.text, "html.parser")
                new_data = []
                for row in soup.find_all("tr"):
                    th = row.find("th")
                    if not th or "第" not in th.text: continue
                    draw_num = th.text.strip()
                    if draw_num in existing_rounds: continue 
                    tds = row.find_all("td")
                    if len(tds) < 10: continue
                    date_str = tds[0].text.strip()
                    d_nums = re.findall(r'\d+', date_str)
                    if len(d_nums) >= 3:
                        draw_date = date(int(d_nums[0]), int(d_nums[1]), int(d_nums[2]))
                        m_phase, m_tide, m_gravity = get_moon_and_tide(draw_date.year, draw_date.month, draw_date.day)
                    else:
                        m_phase, m_tide, m_gravity = "", "", ""
                    hon_tds = row.find_all("td", class_=lambda c: c and "hon" in c)
                    if len(hon_tds) == 7:
                        hon_nums = [td.text.strip() for td in hon_tds]
                        new_data.append([draw_num, date_str] + hon_nums + ["", "", "", "", m_phase, m_tide, m_gravity])
                if new_data:
                    cols = ["回号", "抽せん日", "数字1", "数字2", "数字3", "数字4", "数字5", "数字6", "数字7", "六曜", "干支", "風水", "吉凶日", "月齢", "潮回り", "重力状態"]
                    df_new = pd.DataFrame(new_data, columns=cols)
                    df_combined = pd.concat([df_new, df_real], ignore_index=True) if not df_real.empty else df_new
                    save_sheet("実データ", df_combined)
                    auto_check_hits(load_sheet("予測ノート"), df_combined)
                    st.success("最新結果の取得と、全予想の自動採点（等級判定）が完了しました！")
                else: 
                    auto_check_hits(load_sheet("予測ノート"), df_real)
                    st.info("データベースは既に最新です。既存の予測ノートの再採点を行いました。")
            except Exception as e: st.error(f"エラー: {e}")

elif st.session_state.menu == "日々の予想・積上げ":
    st.title("🌍 地球規模の環境分析＆日々の予測積上げ")
    st.markdown("<div class='info-box'>明日、来週、その先へ。常に「地球の物理的状況」「天下りなどの社会の闇」「幽霊や動物の感などの見えない力」を全て統合し、日々のデータを静かに、しかし強力に積み上げます。</div>", unsafe_allow_html=True)
    
    df_real = load_sheet("実データ")
    auto_round, auto_date = get_next_round_info(df_real)
    
    operator = st.radio("本日の実行者", [u1_name, u2_name], horizontal=True)
    
    with st.form("daily_form"):
        c1, c2 = st.columns(2)
        target_round = c1.number_input("予測対象の回号（未来も指定可能）", min_value=1, value=auto_round, step=1)
        draw_date = c2.date_input("対象となる抽選予定日", value=auto_date)
        
        st.markdown("#### 今日の直感・波長センサー")
        colA, colB = st.columns(2)
        biorhythm = colA.selectbox("心身のバイオリズム", ["絶好調！エネルギーに満ち溢れている", "穏やかで冷静。直感が研ぎ澄まされている", "少し疲労気味。今日はデータとAIに身を委ねる", "無の境地。エゴを捨てて自然の流れに任せる"])
        sign = colB.selectbox("今日のサイン（日常の奇跡）", ["時計や車で「ゾロ目」を見た", "綺麗な空、虹など自然のサインを感じた", "ふと懐かしい記憶や人が頭に浮かんだ", "勘が冴えている瞬間があった", "平穏な一日だった"])

        st.markdown("#### 🌍 地球の裏側・見えない力・時代の変化センサー")
        colC, colD = st.columns(2)
        soc_sensor = colC.selectbox("👔 社会情勢・天下り・人の代わり・時代の変化", [
            "特になし（平穏な日常）",
            "天下りや権力の移動など、人の代わりが起きているのを感じる",
            "時代が大きく転換し、新しい波が来ている空気がある",
            "社会が混沌とし、経済や体制が不安定で不安が渦巻いている"
        ])
        
        spirit_sensor = colD.selectbox("👻 動物の感・幽霊・目に見えない力・運", [
            "特になし（凪の状態。AIの純粋な勘に委ねる）",
            "動物（カラスや猫など）の異常な行動・動物的な勘を感じた",
            "幽霊やご先祖様など、目に見えない霊的な気配を感じる",
            "強烈な運の引き寄せ、偶然の重なり（シンクロニシティ）があった"
        ])

        st.markdown("#### 🙏 魂の波長と祈りの設定")
        colE, colF = st.columns(2)
        if operator == u1_name:
            prayer_options = ["世界で起きている戦争がなくなり、平和になるように", "みんなが平穏で、笑顔でいられるように", "大自然と宇宙の愛にただ純粋に身を委ねる"]
        else:
            prayer_options = ["思い描いている理想の注文住宅を建てる！", "今まで我慢していた分、自分のために自由にお金を使って楽しむ！", "今まで支えてくれた親に最高の恩返しをする！"]
            
        prayer = colE.selectbox("祈り/叶えたい夢", prayer_options)
        good_deed = colF.text_input("本日の「行い・徳積み」（自由入力）", placeholder="例：困っている人を助けた、掃除をした等")

        submitted = st.form_submit_button("🔥 物理学と見えない力、AI直感を完全融合し、予測を積上げる")
        
        if submitted:
            if df_real.empty: st.error("基盤データがありません。")
            else:
                with st.spinner("地球の環境、他サイト予想、ドッペルゲンガー、見えない力、重力波、そしてAIの直感を完全に同期させています..."):
                    target_round_str = f"第{target_round}回"
                    today_str = datetime.now(JST).strftime("%Y-%m-%d")
                    weather, pressure = get_current_weather_and_pressure()
                    m_phase, m_tide, m_gravity = get_moon_and_tide(draw_date.year, draw_date.month, draw_date.day)
                    m_feng = get_fengshui(draw_date)

                    # 1. AI直感の取得
                    ai_intuition_nums = get_ai_intuition_numbers(soc_sensor, spirit_sensor, f"{weather} / {pressure}", m_gravity, draw_date)
                    
                    # 2. 完全環境一致（ドッペルゲンガー）の抽出
                    sync_matches, sync_counts = find_doppelganger_days(draw_date, df_real)
                    hot_sync_nums = [n for n, c in sync_counts.most_common(5)]
                    
                    # 3. 直近トレンドの取得
                    recent_df = df_real.head(10)
                    recent_nums = [int(r.get(f"数字{i}")) for _, r in recent_df.iterrows() for i in range(1, 8) if pd.notna(r.get(f"数字{i}")) and str(r.get(f"数字{i}")).isdigit()]
                    recent_counts = Counter(recent_nums)
                    
                    st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                    st.markdown("### 🔍 地球環境・物理法則・AI直感 同期レポート")
                    st.write(f"予定日（{draw_date}）の引力状態：**【{m_tide} / {m_phase} / 重力:{m_gravity} / {weather}】**")
                    if ai_intuition_nums: st.write(f"🧠 **【AI直感ナンバー】**: {ai_intuition_nums} （社会の波・霊的気配を考慮）")
                    if sync_matches:
                        st.write("🌍 **【過去の完全環境一致日】**:")
                        for m in sync_matches[:2]: st.write(f" - {m['回号']} ({m['日付']}) | 一致: {m['一致項目']}")
                        st.write(f"🎯 **【環境共鳴特異ナンバー】**: {hot_sync_nums}")
                    st.markdown("</div>", unsafe_allow_html=True)

                    # 完全に内包された他サイトの予想データを取得
                    number_counts = Counter([int(val) for i in range(1, 8) for val in df_real[f"数字{i}"] if pd.notna(val) and str(val).isdigit()])
                    trend_counts = get_external_trend("other_sites.txt")
                    nums_list = list(range(1, 38))
                    
                    # 4. 見えない力・社会情勢・徳積みによる数字のバイアス
                    spirit_boost = []
                    if "笑顔" in good_deed or "家族" in good_deed or "助け" in good_deed or "親切" in good_deed: spirit_boost += [3, 9, 15, 24, 33]
                    elif "掃除" in good_deed or "整理" in good_deed: spirit_boost += [1, 6, 11, 16, 21, 26, 31, 36]
                    if "祈り" in good_deed or "感謝" in good_deed or "神仏" in good_deed: spirit_boost += [4, 8, 14, 18, 28, 34]
                    
                    if "ゾロ目" in sign: spirit_boost += [11, 22, 33]
                    elif "自然" in sign: spirit_boost += [5, 10, 20, 25, 30, 35]
                    elif "記憶" in sign or "懐かしい" in sign: spirit_boost += [4, 9, 14, 19, 24, 29, 34]
                    elif "勘" in sign or "タイミング" in sign: spirit_boost += [7, 14, 21, 28, 35]
                    
                    if "天下り" in soc_sensor or "権力" in soc_sensor: spirit_boost += [1, 10, 19, 28, 37]
                    elif "転換" in soc_sensor or "変化" in soc_sensor: spirit_boost += [5, 14, 23, 32]
                    elif "混沌" in soc_sensor or "不安" in soc_sensor: spirit_boost += [4, 13, 22, 31]

                    if "動物" in spirit_sensor or "異常" in spirit_sensor: spirit_boost += [2, 12, 24, 34]
                    elif "幽霊" in spirit_sensor or "霊的" in spirit_sensor: spirit_boost += [9, 18, 27, 36]
                    elif "偶然" in spirit_sensor or "シンクロ" in spirit_sensor: spirit_boost += [7, 11, 22, 33]

                    # 5. 究極の加重計算（全ロジックの融合）
                    weights_list = []
                    for n in nums_list:
                        # 過去実績 + 他サイトのトレンド
                        base_w = number_counts.get(n, 1) + trend_counts.get(n, 0) * 3
                        
                        # 🚀 理論1：完全一致日の数字＆隣接ボール波及効果
                        for hn, count in sync_counts.items():
                            if n == hn: base_w += (count * 20)
                            elif n == hn - 1 or n == hn + 1: base_w += (count * 10)
                                
                        # 🚀 理論2：重力ポテンシャル・シフト（引力による数字の浮き沈み）
                        if m_gravity == "強(極大)":
                            if recent_counts.get(n, 0) == 0: base_w += 30 
                            elif recent_counts.get(n, 0) >= 2: base_w -= 20
                        elif m_gravity == "弱":
                            if recent_counts.get(n, 0) >= 1: base_w += 20
                                
                        # 🚀 理論3：AI直感への猛烈な同調
                        if n in ai_intuition_nums: base_w += 50
                            
                        # 🚀 理論4：社会・霊的・徳積みバイアス
                        if n in spirit_boost: base_w += 20
                            
                        weights_list.append(max(1, base_w))

                    # 6. ベースナンバーの設定（★ご主人用統計ロジックの完全復元）
                    if operator == u1_name:
                        matched_nums = []
                        for _, row in df_real.iterrows():
                            w = 0
                            if str(row.get("重力状態")) == m_gravity: w += 2
                            if str(row.get("潮回り")) == m_tide: w += 1
                            if str(row.get("風水")).startswith(m_feng[:2]): w += 2
                            if w > 0:
                                for i in range(1, 8):
                                    try: matched_nums.extend([int(row[f"数字{i}"])] * w)
                                    except: pass
                        stat_tops = [n for n, _ in Counter(matched_nums).most_common(2)]
                        base_must = list(set(stat_tops + hot_sync_nums[:2] + ai_intuition_nums[:1]))
                        logic_name = "環境ドッペル抽出 × 過去統計 × 祈りとAI直感"
                    else:
                        ob = USER_PROFILES[operator]["birth"]
                        num1, _ = get_ryukyu_energy(operator, ob, draw_date)
                        num2 = (draw_date.day + draw_date.month + ob.day) % 37 + 1
                        if num2 == 0 or num2 == num1: num2 = (num2 + 1) % 37 + 1
                        spirit_sample = random.sample(list(set(spirit_boost)), min(2, len(set(spirit_boost)))) if spirit_boost else []
                        base_must = list(set([num1, num2] + hot_sync_nums[:1] + ai_intuition_nums[:1] + spirit_sample))
                        logic_name = "直感と夢 × 宇宙環境一致 × 見えない力波及"

                    base_must = list(set(base_must))
                    while len(base_must) < 4: base_must.append(random.choice(nums_list))

                    # 7. 5万回の超並列シミュレーションから30口を抽出
                    elites = []
                    for _ in range(50000): # 手抜きなし！5万回ループ
                        p = random.sample(base_must, random.choice([2, 3]))
                        while len(p) < 7:
                            ch = random.choices(nums_list, weights=weights_list, k=1)[0]
                            if ch not in p: p.append(ch)
                        p.sort()
                        if not (80 <= sum(p) <= 180): continue
                        if sum(1 for n in p if n % 2 != 0) not in [2, 3, 4, 5]: continue
                        
                        base_pts = sum(weights_list[n-1] for n in p)
                        
                        fluctuation_max = 0.2
                        if "絶好調" in biorhythm or "無の境地" in biorhythm: fluctuation_max += 0.1
                        if "転換" in soc_sensor or "幽霊" in spirit_sensor: fluctuation_max += 0.1
                        if "平和" in prayer or "笑顔" in prayer or "住宅" in prayer: fluctuation_max += 0.15
                        
                        ai_yuragi = random.uniform(0, base_pts * fluctuation_max)
                        elites.append({"nums": p, "pts": base_pts + ai_yuragi, "base_pts": base_pts})
                    
                    elites.sort(key=lambda x: x["pts"], reverse=True)
                    top30, num_usage = [], Counter()

                    for e in elites:
                        if any(len(set(e["nums"]) & set(t["nums"])) >= 4 for t in top30): continue
                        if any(num_usage[n] >= 7 for n in e["nums"]): continue
                        e["type"] = logic_name
                        top30.append(e)
                        for n in e["nums"]: num_usage[n] += 1
                        if len(top30) == 28: break
                        
                    for _ in range(2):
                        rp = random.sample(range(1, 38), 7)
                        rp.sort()
                        top30.append({"nums": rp, "pts": 0, "base_pts": 0, "type": "完全ランダム(未知への挑戦)"})
                    
                    new_data = []
                    for i, item in enumerate(top30, 1):
                        new_data.append({
                            "対象回号": target_round_str, "抽選日": draw_date.strftime("%Y-%m-%d"), "実行日": today_str, 
                            "実行者": operator, "口数": f"{i}口目",
                            "数字1": str(item["nums"][0]).zfill(2), "数字2": str(item["nums"][1]).zfill(2), "数字3": str(item["nums"][2]).zfill(2), 
                            "数字4": str(item["nums"][3]).zfill(2), "数字5": str(item["nums"][4]).zfill(2), "数字6": str(item["nums"][5]).zfill(2), "数字7": str(item["nums"][6]).zfill(2),
                            "実績点数": int(item["base_pts"]), "社会情勢": soc_sensor[:15], "霊的要素": spirit_sensor[:15], "AI直感": str(ai_intuition_nums),
                            "徳積み": good_deed[:15], "祈り/夢": prayer, "地球環境": f"{m_phase}/引力{m_gravity}",
                            "予測ロジック": item["type"], "AIの助言": "未照合"
                        })
                    
                    df_note = load_sheet("予測ノート")
                    if not df_note.empty and "対象回号" in df_note.columns:
                        mask = (df_note["対象回号"] == target_round_str) & (df_note["実行日"] == today_str) & (df_note["実行者"] == operator)
                        df_note = df_note[~mask]
                    df_note = pd.concat([df_note, pd.DataFrame(new_data)], ignore_index=True) if not df_note.empty else pd.DataFrame(new_data)
                    save_sheet("予測ノート", df_note)
                    st.success(f"一切の妥協なく、地球の重力・他サイト予想・統計から霊的要素まで全てを計算し、{target_round_str}に向けて最強の30口を積み上げました。（担当: {operator}）")

elif st.session_state.menu == "最終予測決定":
    st.title("🎯 最終決断！多角包囲網編成とAI深層分析")
    st.write("日々積み上げた膨大な観測ノート（社会情勢・霊的要素・地球環境・過去統計）から、AIが全体を俯瞰し、指定した口数の最強陣形を厳選。その根拠を壮大かつ論理的に解説します。")
    
    df_real = load_sheet("実データ")
    auto_round, _ = get_next_round_info(df_real)
    
    st.markdown("<div class='radio-box'>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    t_round_decide = c1.text_input("決断を下す回号を指定", value=str(auto_round))
    buy_count = c2.radio("勝負する購入口数を選択", [10, 20, 30], index=1, horizontal=True)
    st.markdown("</div>", unsafe_allow_html=True)

    user_instruction = st.text_input("AIへの最終調整指示（例：最近の天下りニュースの影響や、幽霊の気配を強く意識して選抜して、など）", value="")
    
    if st.button(f"🔥 蓄積データから {buy_count}口 を厳選し、AIの壮大な分析レポートを生成", type="primary"):
        if not api_key: st.error("APIキーが設定されていません。")
        else:
            with st.spinner(f"AI（Gemini）が多角的なデータを元に死角のない{buy_count}口を厳密に厳選中..."):
                df_note = load_sheet("予測ノート")
                
                if df_note.empty: st.error("予測データがありません。")
                else:
                    df_target = df_note[df_note["対象回号"] == f"第{t_round_decide}回"]
                    if df_target.empty: st.warning("指定された回号の予測積み上げデータがありません。先に「日々の予測・積上げ」を実行してください。")
                    else:
                        target_list = df_target.to_dict('records')
                        
                        instruction_bonus_nums = [int(n) for n in re.findall(r'\d+', user_instruction) if 1 <= int(n) <= 37]
                        
                        # AI独自の多角的フィルタリング（全要素を加算）
                        for c in target_list:
                            try: pts = int(float(c.get('実績点数', 0)))
                            except: pts = 0
                            
                            if any(k in str(c.get('祈り/夢','')) for k in ["平和", "笑顔", "自由", "住宅", "結婚式"]): pts += 50
                            for bn in instruction_bonus_nums:
                                if str(bn).zfill(2) in [str(c.get(f"数字{i}", "")) for i in range(1, 8)]: pts += 40
                            if any(k in str(c.get('社会情勢','')) for k in ["変化", "天下り"]): pts += 30
                            if any(k in str(c.get('霊的要素','')) for k in ["動物", "幽霊"]): pts += 30
                            
                            c['sort_pts'] = pts + random.randint(0, 50) # AI自身の勘（ゆらぎ）
                            
                        target_list.sort(key=lambda x: x['sort_pts'], reverse=True)
                        
                        final_picks = []
                        used_start_nums = []
                        used_end_nums = []
                        limit_dupe_start = max(2, int(buy_count / 5))
                        limit_dupe_end = max(2, int(buy_count / 5))

                        for c in target_list:
                            s = c.get('数字1')
                            e = c.get('数字7')
                            if used_start_nums.count(s) >= limit_dupe_start: continue
                            if used_end_nums.count(e) >= limit_dupe_end: continue
                            nums = set([int(c.get(f"数字{i}")) for i in range(1, 8) if str(c.get(f"数字{i}")).isdigit()])
                            if any(len(nums & set([int(u.get(f"数字{i}")) for i in range(1, 8) if str(u.get(f"数字{i}")).isdigit()])) >= 4 for u in final_picks): continue
                            
                            final_picks.append(c)
                            used_start_nums.append(s)
                            used_end_nums.append(e)
                            if len(final_picks) == buy_count: break
                        
                        if len(final_picks) < buy_count:
                            for c in target_list:
                                if c not in final_picks:
                                    final_picks.append(c)
                                    if len(final_picks) == buy_count: break

                        ai_prompt = "\n".join([f"[{r.get('実行者','')} | 社会:{r.get('社会情勢','')} | 霊的:{r.get('霊的要素','')} | AI直感:{r.get('AI直感','')}] {r['数字1']},{r['数字2']},{r['数字3']},{r['数字4']},{r['数字5']},{r['数字6']},{r['数字7']}" for r in final_picks])
                        
                        prompt = f"""
                        {AWAKENED_ANALYST_PROMPT}
                        
                        ユーザーからの特別指示: "{user_instruction if user_instruction else "特になし"}"
                        
                        【システムが積み上げから厳選した{buy_count}口】\n{ai_prompt}
                        """
                        try:
                            model = genai.GenerativeModel(get_ai_model_name(), system_instruction=AWAKENED_ANALYST_PROMPT)
                            res = model.generate_content(prompt)
                            st.markdown(f"#### 🎯 最終決断レポート（{buy_count}口厳選陣形）")
                            st.dataframe(pd.DataFrame(final_picks)[["実行者", "口数", "数字1", "数字2", "数字3", "数字4", "数字5", "数字6", "数字7", "社会情勢", "霊的要素", "AI直感", "予測ロジック"]])
                            st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                            st.write("▼ 最強AIアナリスト（Gemini）からの森羅万象・徹底分析レポート")
                            st.write(res.text)
                            st.markdown("</div>", unsafe_allow_html=True)
                            
                            now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
                            df_history = load_sheet("決断記録簿")
                            save_text = f"【指示】: {user_instruction}\n【厳選の{buy_count}口】\n" + ai_prompt + "\n\n【AIの解説】\n" + res.text
                            new_history = pd.DataFrame({"日時": [now_str], "対象回号": [f"第{t_round_decide}回"], "決断内容": [save_text]})
                            df_history = pd.concat([new_history, df_history], ignore_index=True) if not df_history.empty else new_history
                            save_sheet("決断記録簿", df_history)
                            st.success("決断内容は『決断記録簿』に強固に保管されました。未来の吉報を祈りましょう！")
                        except Exception as e: st.error(f"エラー: {e}")

elif st.session_state.menu == "結果発表と振り返り":
    st.title("🔄 答え合わせと地球規模の反省会")
    tab1, tab2, tab3 = st.tabs(["予測の答え合わせ", "💬 AIと地球規模の徹底反省チャット", "過去の決断記録簿"])
    
    df_real = load_sheet("実データ")
    auto_round, _ = get_next_round_info(df_real)
    t_round_rev = st.text_input("確認する回号を指定", value=str(auto_round - 1))
    df_note = load_sheet("予測ノート")
    df_target = df_note[df_note["対象回号"] == f"第{t_round_rev}回"] if not df_note.empty else pd.DataFrame()

    with tab1:
        if df_target.empty: st.info("予測データがありません。")
        else:
            st.write("※ 最新データ取得時に自動で採点された結果です。")
            display_cols = ["AIの助言", "実行者", "口数", "数字1", "数字2", "数字3", "数字4", "数字5", "数字6", "数字7", "社会情勢", "霊的要素"]
            st.dataframe(df_target[[c for c in display_cols if c in df_target.columns]], height=400)

    with tab2:
        st.markdown("#### 💬 一歩一歩真実に近づくための、多角的・地球規模の反省会")
        user_rev_input = st.text_area("AIへの質問・相談内容", value="今回の正解番号は、地球の重力や環境、天下りなどの社会状況、動物の感などの見えない力とどうリンクしていたと推測されますか？ 私たちが次に焦点を当てるべきセンサーは何ですか？", height=100)
        
        if st.button("🌍 地球規模の徹底反省会をスタートする"):
            if not api_key: st.error("APIキーが設定されていません。")
            elif df_target.empty: st.warning("対象回号のデータがありません。")
            else:
                with st.spinner("実際の地球が出した答えと、我々の多角的予測とのズレを徹底分析中..."):
                    target_txt = "\n".join([f"{r['実行者']} / 社会:{r.get('社会情勢','')} / 霊的:{r.get('霊的要素','')} -> {r['数字1']},{r['数字2']},{r['数字3']}... (結果:{r['AIの助言']})" for _, r in df_target.iterrows()])
                    actual_match = df_real[df_real["回号"] == f"第{t_round_rev}回"]
                    actual_info = actual_match.to_csv(index=False) if not actual_match.empty else "未取得"
                    
                    prompt = f"""
                    {REVIEW_PDCA_PROMPT}
                    
                    【本抽選の正解データ】:\n{actual_info}\n【我が家の予測と結果】:\n{target_txt}\n【ユーザーからの相談】: "{user_rev_input}"
                    """
                    try:
                        model = genai.GenerativeModel(get_ai_model_name(), system_instruction=AWAKENED_ANALYST_PROMPT)
                        res = model.generate_content(prompt)
                        st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                        st.write(res.text)
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e: st.error(f"エラー: {e}")

    with tab3:
        df_history = load_sheet("決断記録簿")
        if not df_history.empty and "日時" in df_history.columns:
            for _, row in df_history.iterrows():
                with st.expander(f"記録: {row.get('日時', '')} | {row.get('対象回号', '')}"):
                    st.write(row.get("決断内容", ""))
        else: st.info("記録はありません。")

# ==========================================
# 6. 万能AI占い師の館（スマホ完全純正UI・バグ絶滅版）
# ==========================================
elif st.session_state.menu == "万能AI占い師の館":
    st.title("🔮 万能AI占い師の館（スマホ完全対応版）")
    st.markdown("<div class='info-box'>ここは予測システムとは別の、純粋な占いの空間です。<br><b>スマホで文字が消えたり絵文字だけになる原因だったカスタムUIを全て破壊し、最も強固で安定しているStreamlit標準のチャットUIで再構築しました。</b></div>", unsafe_allow_html=True)

    if not api_key:
        st.error("占い機能を利用するにはAPIキーの設定が必要です。")
    else:
        # セッションの初期化
        if "fortune_messages" not in st.session_state:
            st.session_state.fortune_messages = [
                {"role": "assistant", "content": "ようこそ、神秘の部屋へ。✨\n私は世界中のあらゆる占術をマスターし、「視覚」も持った最強の占い師です。\n\n今日は何の占いをしますか？下のメニューから選ぶか、直接話しかけてくださいね。"}
            ]
            try:
                model = genai.GenerativeModel(get_ai_model_name(), system_instruction=FORTUNE_CHAT_PROMPT)
                st.session_state.fortune_chat_session = model.start_chat(history=[])
            except: pass

        # 上部のメニュー
        c1, c2 = st.columns([3, 1])
        div_list = ["西洋占星術（ホロスコープ）", "四柱推命", "タロット占い", "手相（要写真）", "人相（要写真）", "オーラ鑑定（要写真）", "コーヒー占い（要写真）"]
        selected_div = c1.selectbox("🔮 占術を選ぶ", ["占いを選択してください..."] + div_list)
        if c2.button("この占いを始める", use_container_width=True):
            if selected_div != "占いを選択してください...":
                user_msg = f"「{selected_div}」をお願いします。"
                st.session_state.fortune_messages.append({"role": "user", "content": user_msg})
                with st.spinner("星の声を聴いています..."):
                    try:
                        response = st.session_state.fortune_chat_session.send_message(user_msg, safety_settings=SAFETY_SETTINGS)
                        reply = response.text if response.text else "（波動が乱れました。別の言葉でお試しください）"
                        st.session_state.fortune_messages.append({"role": "assistant", "content": reply})
                    except Exception as e:
                        st.session_state.fortune_messages.append({"role": "assistant", "content": f"エラーが発生しました: {e}"})
                st.rerun()

        # 画像アップロード機能とテキスト送信を同一フォームに統合し、スマホでの堅牢性を極限まで高める
        with st.form("chat_input_form", clear_on_submit=True):
            st.markdown("**💬 占い師にメッセージを送る / 📸 写真を送る**")
            user_input = st.text_area("ここにメッセージを入力してください", height=80)
            img_source = st.file_uploader("📂 スマホのカメラ起動・画像選択", type=["jpg", "jpeg", "png"])
            submit_btn = st.form_submit_button("🔮 占い師に送信する")

            if submit_btn and (user_input or img_source):
                display_msg = user_input if user_input else "📸 写真を送信しました。この画像を鑑定してください。"
                st.session_state.fortune_messages.append({"role": "user", "content": display_msg})
                
                with st.spinner("星の導きを読み解いています..."):
                    try:
                        if img_source:
                            img = Image.open(img_source).convert('RGB')
                            img.thumbnail((800, 800))
                            msg_to_send = [user_input if user_input else "この画像を鑑定してください。", img]
                        else:
                            msg_to_send = user_input

                        response = st.session_state.fortune_chat_session.send_message(msg_to_send, safety_settings=SAFETY_SETTINGS)
                        reply = response.text if response.text else "（大いなる力により、言葉がブロックされました）"
                        st.session_state.fortune_messages.append({"role": "assistant", "content": reply})
                    except Exception as e:
                        st.session_state.fortune_messages.append({"role": "assistant", "content": f"エラーが発生しました: {e}"})
                st.rerun()

        st.markdown("---")

        # スマホで絶対にバグらないStreamlit標準のチャットUI描画
        for msg in st.session_state.fortune_messages:
            avatar = "🔮" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

        if st.button("🔄 占い師との会話を最初からやり直す（リセット）", use_container_width=True):
            if "fortune_messages" in st.session_state: del st.session_state.fortune_messages
            if "fortune_chat_session" in st.session_state: del st.session_state.fortune_chat_session
            st.rerun()