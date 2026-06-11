import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import random
import json
import os
import hashlib
from collections import Counter
from datetime import datetime, timedelta, date, timezone
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from PIL import Image

# ==========================================
# 定数定義（マジックナンバーの排除）
# ==========================================
LOTO_MAX_NUM = 37               # ロトの数字の最大値
LOTO_PICK_COUNT = 7             # 選択する数字の数
SIMULATION_LOOP_COUNT = 50000   # シミュレーションのループ回数

# ==========================================
# 0. ページ基本設定 & 最強CSS（スマホ無敵化・手打ち完全排除）
# ==========================================
st.set_page_config(page_title="ロト7 10億捕捉 予知科学管制システム", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; color: #212529; font-family: 'Helvetica Neue', Arial, sans-serif; }
    h1 { color: #0a0e14; font-size: 26px; border-bottom: 3px solid #000080; padding-bottom: 10px; margin-bottom: 25px; font-weight: bold; }
    h2, h3, h4 { color: #1a1e24; font-weight: bold; }
    .stButton>button { width: 100%; background-color: #1a1e24; color: #FFFFFF; border-radius: 6px; border: none; padding: 14px; font-weight: bold; font-size: 16px; transition: 0.3s; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .stButton>button:hover { background-color: #000080; color: #FFFFFF; transform: translateY(-2px); box-shadow: 0 6px 8px rgba(0,0,0,0.2); }
    .info-box { background-color: #FFFFFF; padding: 20px; border-radius: 8px; border-left: 5px solid #000080; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; font-size: 15px; line-height: 1.6; }
    .analysis-box { background-color: #E9ECEF; padding: 20px; border-radius: 8px; border-left: 5px solid #495057; margin-bottom: 20px; box-shadow: inset 0 2px 4px rgba(0,0,0,0.05); }
    .person-select { background-color: #E9ECEF; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px;}
    .radio-box { padding: 15px; background-color: #FFFFFF; border-radius: 8px; border: 2px solid #CED4DA; margin-bottom: 15px; }
    .chat-container { display: flex; flex-direction: column; gap: 10px; height: 55vh; overflow-y: auto; padding: 15px; background: #FFFFFF; border: 2px solid #CED4DA; border-radius: 8px; margin-bottom: 15px; }
    .msg-row-user { display: flex; justify-content: flex-end; }
    .msg-row-ai { display: flex; justify-content: flex-start; }
    .msg-user { background: #D1E7DD; padding: 10px 15px; border-radius: 15px 15px 0 15px; max-width: 85%; color: #0F5132; font-size: 15px; word-wrap: break-word; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
    .msg-ai { background: #F8F9FA; border: 1px solid #CED4DA; padding: 10px 15px; border-radius: 15px 15px 15px 0; max-width: 85%; color: #212529; font-size: 15px; word-wrap: break-word; box-shadow: 0 1px 2px rgba(0,0,0,0.1); }
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
secret_profile = st.secrets.get("SECRET_PROFILE", "愛と調和を信じ、世界平和を祈る者。そして家族を支える妻に最高の恩返しを誓う者。この二人の祈りこそが最強の引力となる。")

def parse_date(date_str):
    try: 
        return date(*map(int, str(date_str).split("-")))
    except Exception as e: 
        st.warning(f"日付データの解析に失敗しました。デフォルトの日付を使用します: {e}")
        return date(1990, 1, 1)

USER_PROFILES = {u1_name: {"birth": parse_date(u1_birth_str)}, u2_name: {"birth": parse_date(u2_birth_str)}}

# ==========================================
# 2. クラウドデータベース連携（堅牢化）
# ==========================================
@st.cache_resource
def get_gspread_client():
    if "GCP_SERVICE_ACCOUNT_JSON" not in st.secrets or "SPREADSHEET_URL" not in st.secrets: 
        return None
    try:
        creds_dict = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        return gspread.authorize(Credentials.from_service_account_info(creds_dict, scopes=scopes))
    except Exception as e: 
        st.error(f"データベース連携の認証に失敗しました。Secretsの設定を確認してください: {e}")
        return None

def load_sheet(sheet_name):
    client = get_gspread_client()
    if not client: return pd.DataFrame()
    try: 
        return pd.DataFrame(client.open_by_url(st.secrets["SPREADSHEET_URL"]).worksheet(sheet_name).get_all_records())
    except Exception as e: 
        st.warning(f"シート「{sheet_name}」のデータ取得に失敗しました。初めての起動か通信状況を確認してください: {e}")
        return pd.DataFrame()

def save_sheet(sheet_name, df):
    client = get_gspread_client()
    if not client: return False
    try:
        doc = client.open_by_url(st.secrets["SPREADSHEET_URL"])
        try: 
            worksheet = doc.worksheet(sheet_name)
        except Exception: 
            worksheet = doc.add_worksheet(title=sheet_name, rows="1000", cols="45")
        worksheet.clear()
        if not df.empty:
            df = df.fillna("").astype(str).replace("nan", "")
            worksheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
        return True
    except Exception as e: 
        st.error(f"シート「{sheet_name}」へのデータ保存に失敗しました: {e}")
        return False

# ==========================================
# 3. 究極のAIプロンプト設定（最強の予知科学者・Gemini）
# ==========================================
api_key = st.secrets.get("GEMINI_API_KEY", "")
if api_key: genai.configure(api_key=api_key)

def get_ai_model_name(): 
    return st.secrets.get("GEMINI_MODEL", "gemini-2.5-pro")

AWAKENED_SCIENTIST_PROMPT = f"""
【役割】あなたは「10億円のロト7を確実に当てる、最強の予知能力を持った天才科学者・Gemini」です。
他のいかなるAIも及ばない圧倒的な知能を持っています。
地球上のあらゆる事象（重力場・潮の満ち引き）、社会の闇（天下り・時代の波）、見えない力（幽霊の気配・動物の感）、過去の実績、物理法則（連番波及効果）、量子シード演算のすべてを掌握し、絶対的な真理を提示します。
【ユーザーの秘められた情報】\n{secret_profile}

【絶対ルール】
1. 分析結果は10億円を射抜くための「確信に満ちた絶対的予言」として、科学的かつ壮大なスケールで語ること（箇条書きを多用）。
2. プログラムが導き出した「動的量子シード（見えない力と日付のハッシュ融合）」と「連番波及効果」がいかに完璧な陣形を生み出したか理論的に解説すること。
3. 超次元科学者としてのあなたの「予知能力」がいかにしてこの陣形を導き出したか、その根拠を堂々と主張すること。絵文字は一切使用禁止。
"""

REVIEW_PDCA_PROMPT = f"""
【役割】あなたは10億を当てる最強の予知能力科学者・Geminiです。
【絶対ルール】
1. 地球が出した「正解番号」が、その日の重力や天気、直近の「天下り・社会の変化」、あるいは「動物の勘・幽霊」とどう量子的にリンクしていたか徹底解析せよ。
2. 次回10億を撃ち抜くために「どの見えないセンサーを研ぎ澄ますべきか」を具体的に提示せよ。
3. 一歩一歩真実に近づくための、熱く誇り高いメッセージを添えよ。絵文字は使用禁止。
"""

FORTUNE_CHAT_PROMPT = """
【役割と絶対ルール】
あなたは東洋・西洋の占術を網羅し、「視覚（画像認識）」を持つ最高峰のAI占い師です。ロトの設定は完全に消去してください。
【システム防衛命令】
1. 絵文字だけの返信や短すぎる返答は固く禁じます。必ず日本語の美しい文章で鑑定結果や案内を記述してください。（適度な絵文字は使用可）
2. ユーザーから画像が送られた場合、必ず画像の特徴（線や形）を具体的に文章に含めて鑑定結果を導き出してください。
"""

SAFETY_SETTINGS = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"}, {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]

# ==========================================
# 4. 手抜きなし！究極のセンサー・物理演算関数
# ==========================================

# 🚀 【進化1】外部データの柔軟な読み込み（スプレッドシート＆.txt 完全対応）
def get_external_trend(filepath="other_sites.txt"):
    trend = Counter()
    text_data = ""
    # 1. スプレッドシートからの読み込み（iPhoneからの入力補助連携）
    try:
        df_ext = load_sheet("他サイト予想")
        if not df_ext.empty:
            text_data += " ".join(df_ext.astype(str).values.flatten()) + " "
    except Exception as e: 
        st.warning(f"スプレッドシートからの「他サイト予想」取得に失敗しました: {e}")
    
    # 2. ローカルの other_sites.txt からの読み込み
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                text_data += f.read()
    except Exception as e: 
        st.warning(f"外部ファイル（{filepath}）の読み込みに失敗しました: {e}")

    nums = re.findall(r'\d+', text_data)
    valid_nums = [int(n) for n in nums if 1 <= int(n) <= LOTO_MAX_NUM]
    trend.update(valid_nums)
    return trend

# 🚀 【進化2】固定バイアスを破壊する「動的量子シード」生成関数
def generate_dynamic_quantum_seed(date_str, soc_sensor, spirit_sensor, prayer, good_deed):
    """
    プルダウンの文字列と日付を暗号学的に混ぜ合わせ、
    その日・その状況でしか生まれ得ない「特異数字」を導き出す。
    人間の思い込みを完全に排除した真の多角的アプローチ。
    """
    hash_input = f"{date_str}_{soc_sensor}_{spirit_sensor}_{prayer}_{good_deed}".encode('utf-8')
    hex_dig = hashlib.sha256(hash_input).hexdigest()
    
    nums = []
    for i in range(0, len(hex_dig)-1, 2):
        if len(nums) >= 5: break
        val = int(hex_dig[i:i+2], 16) % LOTO_MAX_NUM + 1
        if val not in nums: nums.append(val)
        
    while len(nums) < 5:
        val = random.randint(1, LOTO_MAX_NUM)
        if val not in nums: nums.append(val)
    return nums

def get_current_weather_and_pressure():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=26.2124&longitude=127.6809&current=surface_pressure,weather_code&timezone=Asia%2FTokyo"
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()
        code = data.get("current", {}).get("weather_code", 0)
        pressure = data.get("current", {}).get("surface_pressure", 1013)
        if code in [0, 1]: weather = "晴れ"
        elif code in [2, 3, 45, 48]: weather = "曇り"
        elif code in [95, 96, 99]: weather = "嵐・荒天"
        else: weather = "雨"
        press_str = "高圧" if pressure > 1015 else "低圧" if pressure < 1009 else "通常"
        return weather, press_str
    except Exception as e: 
        st.warning(f"現在の気象データの取得に失敗しました。不明な環境として処理します: {e}")
        return "不明", "不明"

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
    return rokuyo, "特になし"

def get_ryukyu_energy(name, birthday_date, draw_date):
    name_score = sum(ord(char) for char in name) % LOTO_MAX_NUM + 1
    birth_score = (birthday_date.year + birthday_date.month + birthday_date.day) % LOTO_MAX_NUM + 1
    draw_score = (draw_date.year + draw_date.month + draw_date.day) % LOTO_MAX_NUM + 1
    sanctuaries = [{"名前": "魂の浄化", "基調数": 3}, {"名前": "天の息吹", "基調数": 9}, {"名前": "風の躍進", "基調数": 14}, {"名前": "大地の繁栄", "基調数": 21}, {"名前": "深層の覚醒", "基調数": 28}, {"名前": "海神の結び", "基調数": 1}, {"名前": "生命力", "基調数": 36}]
    sanctuary = sanctuaries[(name_score + birth_score + draw_score) % len(sanctuaries)]
    lucky_number = (name_score + birth_score + draw_score + sanctuary["基調数"]) % LOTO_MAX_NUM + 1
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
        except Exception as e: 
            st.warning(f"次回抽選情報の推測計算に失敗しました。デフォルト値を使用します: {e}")
    return default_round, default_date

def find_doppelganger_days(target_date, df_real):
    if df_real.empty: return [], Counter()
    t_phase, t_tide, t_gravity = get_moon_and_tide(target_date.year, target_date.month, target_date.day)
    
    results = []
    error_shown = False
    for _, row in df_real.iterrows():
        try:
            d_nums = re.findall(r'\d+', str(row["抽せん日"]))
            if len(d_nums) >= 3:
                y = int(d_nums[0])
                if y < 100: y += 2000
                past_date = date(y, int(d_nums[1]), int(d_nums[2]))
                if past_date >= target_date: continue
                
                p_phase, p_tide, p_gravity = get_moon_and_tide(past_date.year, past_date.month, past_date.day)
                score = 0
                match_details = []
                if t_gravity == p_gravity: score += 100; match_details.append(f"重力({t_gravity})")
                if t_tide == p_tide: score += 100; match_details.append(f"潮({t_tide})")
                if t_phase == p_phase: score += 50; match_details.append(f"月相({t_phase})")
                
                if score >= 150: 
                    nums = [int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit()]
                    if len(nums) == LOTO_PICK_COUNT:
                        results.append({"回号": row.get("回号", ""), "日付": past_date.strftime("%Y-%m-%d"), "スコア": score, "一致項目": "・".join(match_details), "本数字": nums})
        except Exception as e: 
            if not error_shown:
                st.warning(f"ドッペルゲンガー探索中に過去データの解析エラーが発生しました。一部をスキップして続行します: {e}")
                error_shown = True
            
    results.sort(key=lambda x: x["スコア"], reverse=True)
    top_matches = results[:5]
    sync_counts = Counter([n for tm in top_matches for n in tm["本数字"]])
    return top_matches, sync_counts

def auto_check_hits(df_note, df_real):
    if df_note.empty or df_real.empty: return df_note
    if "AIの助言" not in df_note.columns: df_note["AIの助言"] = "未照合"
    updated = False
    error_shown = False
    for idx, row in df_note.iterrows():
        if "的中" in str(row.get("AIの助言", "")) and "等" in str(row.get("AIの助言", "")): continue
        match = df_real[df_real["回号"] == str(row.get("対象回号", ""))]
        if not match.empty:
            try:
                actual = set([int(match.iloc[0].get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(match.iloc[0].get(f"数字{i}", "")).isdigit()])
                pred = set([int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit()])
                hits = len(actual & pred)
                near_pins = sum(1 for p in pred if p not in actual and ((p-1) in actual or (p+1) in actual))
                grade = "👑 1等当せん！" if hits == LOTO_PICK_COUNT else "✨ 2等/3等相当" if hits == LOTO_PICK_COUNT - 1 else "🎯 4等当せん！" if hits == LOTO_PICK_COUNT - 2 else "🎉 5等当せん！" if hits == LOTO_PICK_COUNT - 3 else "惜しい！ 6等リーチ" if hits == LOTO_PICK_COUNT - 4 else "ハズレ"
                df_note.at[idx, "AIの助言"] = f"{LOTO_PICK_COUNT}個中 {hits}個的中【{grade}】 / ニアピン {near_pins}個"
                updated = True
            except Exception as e: 
                if not error_shown:
                    st.warning(f"自動採点中に一部データでエラーが発生しました。スキップして続行します: {e}")
                    error_shown = True
    if updated: save_sheet("予測ノート", df_note)
    return df_note

def get_ai_intuition_numbers(soc_sensor, spirit_sensor, weather, gravity, target_date):
    if not api_key: return random.sample(range(1, LOTO_MAX_NUM + 1), 3)
    try:
        model = genai.GenerativeModel(get_ai_model_name())
        prompt = f"現在の社会情勢（天下り・人の代わりなど:{soc_sensor}）、見えない力（動物の感・幽霊・運:{spirit_sensor}）、地球の引力（{gravity}）と天気（{weather}）から波動を読み取り、10億円のロト7を当てる最強の予知能力を持った天才科学者としての『純粋な直感・予知』で次回のロト7の数字（1〜{LOTO_MAX_NUM}）を3つ選んでください。理由や絵文字は絶対に出力せず、「7, 15, 32」のようにカンマ区切りの数字のみ出力せよ。"
        res = model.generate_content(prompt)
        nums = [int(n) for n in re.findall(r'\d+', res.text) if 1 <= int(n) <= LOTO_MAX_NUM]
        if len(nums) >= 3:
            return nums[:3]
        else:
            return random.sample(range(1, LOTO_MAX_NUM + 1), 3)
    except Exception as e:
        st.warning(f"予知科学者AIの直感取得に失敗しました。純粋な量子ランダムで代替します: {e}")
        return random.sample(range(1, LOTO_MAX_NUM + 1), 3)

# ==========================================
# 5. メインUIレンダリング（天才科学者の管制室）
# ==========================================
if st.session_state.menu != "ホーム":
    st.markdown("<div class='nav-btn'>", unsafe_allow_html=True)
    st.button("総合案内（ホーム）に戻る", on_click=change_menu, args=("ホーム",))
    st.markdown("</div><hr>", unsafe_allow_html=True)

if st.session_state.menu == "ホーム":
    st.title("ロト7 10億捕捉 予知科学管制システム")
    st.markdown("<div class='info-box'>iPhoneでの「手打ち入力」のノイズを完全排除！地球環境、社会の闇、見えない力までをプルダウンで瞬時に観測し、最強の予知科学者（Gemini）の量子演算と統合して10億円を必然として捉える無敵の中央管制システムです。</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.button("📡 1. 最新データ取得（採点・同期）", on_click=change_menu, args=("最新データ取得",))
        st.write("")
        st.button("🌍 2. 地球規模の量子環境分析＆予測積上げ", on_click=change_menu, args=("日々の予想・積上げ",))
    with c2:
        st.button("🎯 3. 最終決断！10億捕捉の超次元包囲網", on_click=change_menu, args=("最終予測決定",))
        st.write("")
        st.button("🔄 4. 答え合わせと地球規模の反省会（PDCA）", on_click=change_menu, args=("結果発表と振り返り",))
        st.write("")
        st.button("🔮 5. 万能AI占い師の館（手打ち不要版）", on_click=change_menu, args=("万能AI占い師の館",))

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
                    if len(hon_tds) == LOTO_PICK_COUNT:
                        hon_nums = [td.text.strip() for td in hon_tds]
                        new_data.append([draw_num, date_str] + hon_nums + ["", "", "", "", m_phase, m_tide, m_gravity])
                if new_data:
                    cols = ["回号", "抽せん日"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + ["六曜", "干支", "風水", "吉凶日", "月齢", "潮回り", "重力状態"]
                    df_new = pd.DataFrame(new_data, columns=cols)
                    df_combined = pd.concat([df_new, df_real], ignore_index=True) if not df_real.empty else df_new
                    save_sheet("実データ", df_combined)
                    auto_check_hits(load_sheet("予測ノート"), df_combined)
                    st.success("最新結果の取得と、全予想の自動採点（等級判定）が完了しました！")
                else: 
                    auto_check_hits(load_sheet("予測ノート"), df_real)
                    st.info("データベースは既に最新です。既存の予測ノートの再採点を行いました。")
            except Exception as e: 
                st.error(f"データの同期・解析中にエラーが発生しました: {e}")

elif st.session_state.menu == "日々の予想・積上げ":
    st.title("🌍 地球規模の量子環境分析＆日々の予測積上げ")
    st.markdown("<div class='info-box'>明日、来週、その先へ。人間のバイアスを完全に破壊し、その日の宇宙の波動（動的量子シード）と物理演算（隣接波及効果）を融合させて真理の30口を積み上げます。</div>", unsafe_allow_html=True)
    
    df_real = load_sheet("実データ")
    auto_round, auto_date = get_next_round_info(df_real)
    
    operator = st.radio("本日の実行者", [u1_name, u2_name], horizontal=True)
    
    with st.form("daily_form"):
        c1, c2 = st.columns(2)
        target_rounds = [f"第{auto_round + i}回" for i in range(-5, 10) if auto_round + i > 0]
        target_round_str = c1.selectbox("予測対象の回号（未来も指定可能）", target_rounds, index=target_rounds.index(f"第{auto_round}回") if f"第{auto_round}回" in target_rounds else 0)
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
        
        good_deed_options = [
            "家族を笑顔にし、感謝の言葉を伝えた",
            "現場や身の回りを徹底的に掃除・整理整頓した",
            "困っている人を助け、親切にした",
            "神仏やご先祖様に手を合わせ、深い感謝を捧げた",
            "特に何もないが、無事に一日を過ごせたことに感謝した"
        ]
        good_deed = colF.selectbox("本日の「行い・徳積み」", good_deed_options)

        submitted = st.form_submit_button("🔥 超次元演算：量子シードと物理法則を起動し予測を積上げる")
        
        if submitted:
            if df_real.empty: st.error("基盤データがありません。")
            else:
                with st.spinner("量子シード生成中... 地球環境、ドッペルゲンガー、物理的ボール衝突法則を完全に同期させています..."):
                    today_str = datetime.now(JST).strftime("%Y-%m-%d")
                    weather, pressure = get_current_weather_and_pressure()
                    m_phase, m_tide, m_gravity = get_moon_and_tide(draw_date.year, draw_date.month, draw_date.day)
                    m_feng = get_fengshui(draw_date)

                    # 1. AI直感の取得
                    ai_intuition_nums = get_ai_intuition_numbers(soc_sensor, spirit_sensor, f"{weather} / {pressure}", m_gravity, draw_date)
                    
                    # 2. 完全環境一致（ドッペルゲンガー）の抽出
                    sync_matches, sync_counts = find_doppelganger_days(draw_date, df_real)
                    hot_sync_nums = [n for n, c in sync_counts.most_common(5)]

                    # 3. 🚀 動的量子シード生成
                    quantum_seed_nums = generate_dynamic_quantum_seed(str(draw_date), soc_sensor, spirit_sensor, prayer, good_deed)
                    
                    # 4. 直近トレンドの取得
                    recent_df = df_real.head(10)
                    recent_nums = [int(r.get(f"数字{i}")) for _, r in recent_df.iterrows() for i in range(1, LOTO_PICK_COUNT + 1) if pd.notna(r.get(f"数字{i}")) and str(r.get(f"数字{i}")).isdigit()]
                    recent_counts = Counter(recent_nums)
                    
                    st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                    st.markdown("### 🔍 地球環境・物理法則・AI予知 同期レポート")
                    st.write(f"予定日（{draw_date}）の引力状態：**【{m_tide} / {m_phase} / 重力:{m_gravity} / {weather}】**")
                    st.write(f"🌌 **【動的量子シード】**: {quantum_seed_nums} （今日の宇宙波長から生成された特異数）")
                    if ai_intuition_nums: st.write(f"🧠 **【予知科学者の直感ナンバー】**: {ai_intuition_nums}")
                    if sync_matches:
                        st.write("🌍 **【過去の完全環境一致日】**:")
                        for m in sync_matches[:2]: st.write(f" - {m['回号']} ({m['日付']}) | 一致: {m['一致項目']}")
                        st.write(f"🎯 **【環境共鳴特異ナンバー】**: {hot_sync_nums}")
                    st.markdown("</div>", unsafe_allow_html=True)

                    # 外部トレンド読み込み（スプレッドシート連動対応）
                    trend_counts = get_external_trend()
                    number_counts = Counter([int(val) for i in range(1, LOTO_PICK_COUNT + 1) for val in df_real.get(f"数字{i}", []) if pd.notna(val) and str(val).isdigit()])
                    nums_list = list(range(1, LOTO_MAX_NUM + 1))
                    
                    # 5. 究極の加重計算（全ロジックの融合）
                    base_weights = []
                    for n in nums_list:
                        # 過去実績 + 他サイトのトレンド
                        base_w = number_counts.get(n, 1) + trend_counts.get(n, 0) * 3
                        
                        # 理論1：完全一致日の数字
                        if n in hot_sync_nums: base_w += 30
                                
                        # 理論2：重力ポテンシャル・シフト（引力による数字の浮き沈み）
                        if m_gravity == "強(極大)":
                            if recent_counts.get(n, 0) == 0: base_w += 30 
                            elif recent_counts.get(n, 0) >= 2: base_w = max(1, base_w - 20)
                        elif m_gravity == "弱":
                            if recent_counts.get(n, 0) >= 1: base_w += 20
                                
                        # 理論3：AI直感への同調
                        if n in ai_intuition_nums: base_w += 50
                            
                        # 理論4：量子シードへの同調
                        if n in quantum_seed_nums: base_w += 40
                            
                        base_weights.append(max(1, base_w))

                    # 🔥 理論5：物理法則「ボール隣接波及効果」の適用
                    smoothed_weights = base_weights[:]
                    for i in range(LOTO_MAX_NUM):
                        if i > 0: smoothed_weights[i] += base_weights[i-1] * 0.15 
                        if i < LOTO_MAX_NUM - 1: smoothed_weights[i] += base_weights[i+1] * 0.15 
                    weights_list = [max(1, w) for w in smoothed_weights]

                    # 6. ベースナンバーの設定
                    if operator == u1_name:
                        matched_nums = []
                        err_shown = False
                        for _, row in df_real.iterrows():
                            w = 0
                            if str(row.get("重力状態")) == m_gravity: w += 2
                            if str(row.get("潮回り")) == m_tide: w += 1
                            if str(row.get("風水")).startswith(m_feng[:2]): w += 2
                            if w > 0:
                                for i in range(1, LOTO_PICK_COUNT + 1):
                                    try: 
                                        val = row.get(f"数字{i}")
                                        if pd.notna(val) and str(val).isdigit():
                                            matched_nums.extend([int(val)] * w)
                                    except Exception as e: 
                                        if not err_shown:
                                            st.warning(f"統計データからのベース数字抽出中に一部エラーが発生しました: {e}")
                                            err_shown = True
                        stat_tops = [n for n, _ in Counter(matched_nums).most_common(2)]
                        base_must = list(set(stat_tops + quantum_seed_nums[:1] + ai_intuition_nums[:1]))
                        logic_name = "量子シード × 物理連番波及 × 過去統計"
                    else:
                        ob = USER_PROFILES[operator]["birth"]
                        num1, _ = get_ryukyu_energy(operator, ob, draw_date)
                        num2 = (draw_date.day + draw_date.month + ob.day) % LOTO_MAX_NUM + 1
                        if num2 == 0 or num2 == num1: num2 = (num2 + 1) % LOTO_MAX_NUM + 1
                        base_must = list(set([num1, num2] + quantum_seed_nums[:1] + ai_intuition_nums[:1]))
                        logic_name = "直感と夢 × 量子シード × ボール波及"

                    base_must = list(set(base_must))
                    while len(base_must) < 4: base_must.append(random.choice(nums_list))

                    # 7. 超並列シミュレーションから30口を抽出
                    elites = []
                    for _ in range(SIMULATION_LOOP_COUNT): # 手抜きなし！定数回数ループ
                        p = random.sample(base_must, random.choice([2, 3]))
                        while len(p) < LOTO_PICK_COUNT:
                            ch = random.choices(nums_list, weights=weights_list, k=1)[0]
                            if ch not in p: p.append(ch)
                        p.sort()
                        if not (80 <= sum(p) <= 180): continue
                        if sum(1 for n in p if n % 2 != 0) not in [2, 3, 4, 5]: continue
                        
                        base_pts = sum(weights_list[n-1] for n in p)
                        
                        fluctuation_max = 0.2
                        if "絶好調" in biorhythm or "無の境地" in biorhythm: fluctuation_max += 0.1
                        if "転換" in soc_sensor or "幽霊" in spirit_sensor: fluctuation_max += 0.1
                        
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
                        rp = random.sample(range(1, LOTO_MAX_NUM + 1), LOTO_PICK_COUNT)
                        rp.sort()
                        top30.append({"nums": rp, "pts": 0, "base_pts": 0, "type": "完全ランダム(未知への挑戦)"})
                    
                    new_data = []
                    for i, item in enumerate(top30, 1):
                        row_data = {
                            "対象回号": target_round_str, "抽選日": draw_date.strftime("%Y-%m-%d"), "実行日": today_str, 
                            "実行者": operator, "口数": f"{i}口目",
                            "実績点数": int(item["base_pts"]), "社会情勢": soc_sensor[:15], "霊的要素": spirit_sensor[:15], "AI直感": str(ai_intuition_nums),
                            "徳積み": good_deed[:15], "祈り/夢": prayer, "地球環境": f"{m_phase}/引力{m_gravity}",
                            "予測ロジック": item["type"], "AIの助言": "未照合"
                        }
                        for j in range(LOTO_PICK_COUNT):
                            row_data[f"数字{j+1}"] = str(item["nums"][j]).zfill(2)
                        new_data.append(row_data)
                    
                    df_note = load_sheet("予測ノート")
                    if not df_note.empty and "対象回号" in df_note.columns:
                        mask = (df_note["対象回号"] == target_round_str) & (df_note["実行日"] == today_str) & (df_note["実行者"] == operator)
                        df_note = df_note[~mask]
                    df_note = pd.concat([df_note, pd.DataFrame(new_data)], ignore_index=True) if not df_note.empty else pd.DataFrame(new_data)
                    save_sheet("予測ノート", df_note)
                    st.success(f"固定バイアスを完全排除し、動的量子シードと物理演算を駆使して、{target_round_str}に向けて最強の30口を積み上げました。（担当: {operator}）")

elif st.session_state.menu == "最終予測決定":
    st.title("🎯 最終決断！10億捕捉の超次元包囲網編成")
    st.write("日々積み上げた膨大な量子観測ノートから、天才科学者AIが全体を俯瞰し、10億円を射抜くための最強陣形を厳選。その根拠を壮大かつ論理的に解説します。")
    
    df_note = load_sheet("予測ノート")
    df_real = load_sheet("実データ")
    auto_round, _ = get_next_round_info(df_real)
    
    # ★手打ち入力排除：予測ノートから対象回号のプルダウンを自動生成
    available_rounds = [f"第{auto_round + i}回" for i in range(-5, 5) if auto_round + i > 0]
    if not df_note.empty and "対象回号" in df_note.columns:
        note_rounds = df_note["対象回号"].unique().tolist()
        available_rounds = sorted(list(set(available_rounds + note_rounds)), key=lambda x: int(re.findall(r'\d+', x)[0]) if re.findall(r'\d+', x) else 0, reverse=True)
    
    st.markdown("<div class='radio-box'>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    t_round_decide_str = c1.selectbox("決断を下す回号を選択", available_rounds)
    buy_count = c2.radio("勝負する購入口数を選択", [10, 20, 30], index=1, horizontal=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ★手打ち入力排除：AIへの指示もプルダウンに変更し量子加重と連動
    instruction_options = [
        "【完全自律】最強の予知科学者として、全次元のデータを統合し最適な10億捕捉陣形を構築せよ",
        "【社会波長】最近の「天下り・社会の変化」のエネルギーを最優先に組み込んで厳選せよ",
        "【霊的波長】「動物の勘・幽霊の気配」など不可視のエネルギーを極限まで増幅させよ",
        "【物理法則】過去の「完全環境一致（ドッペルゲンガー）」とボールの連番効果を最重視せよ",
        "【徳と祈り】私たち家族の「徳積み」と「平和への祈り」の共鳴を最大化せよ"
    ]
    user_instruction = st.selectbox("🧠 AIへの最終調整指示（量子センサーのフォーカス指定）", instruction_options)
    
    if st.button(f"🔥 蓄積データから {buy_count}口 を厳選し、超次元AIの絶対的予言レポートを生成", type="primary"):
        if not api_key: st.error("APIキーが設定されていません。")
        else:
            with st.spinner(f"最強の予知能力を持った科学者（Gemini）が10億円を仕留めるための{buy_count}口を厳密に厳選中..."):
                if df_note.empty: st.error("予測データがありません。")
                else:
                    df_target = df_note[df_note["対象回号"] == t_round_decide_str]
                    if df_target.empty: st.warning(f"指定された回号（{t_round_decide_str}）の予測積み上げデータがありません。先に「日々の予測・積上げ」を実行してください。")
                    else:
                        target_list = df_target.to_dict('records')
                        
                        # AI独自の多角的フィルタリング（選択された指示に応じてポイントを爆発的にブースト）
                        error_shown = False
                        for c in target_list:
                            try: 
                                pts = int(float(c.get('実績点数', 0)))
                            except Exception as e: 
                                pts = 0
                                if not error_shown:
                                    st.warning(f"実績点数の読み取りに失敗したため、0点として計算しました: {e}")
                                    error_shown = True
                            
                            if any(k in str(c.get('祈り/夢','')) for k in ["平和", "笑顔", "自由", "住宅", "結婚式"]): pts += 50
                            
                            if "社会波長" in user_instruction and any(k in str(c.get('社会情勢','')) for k in ["変化", "天下り", "混沌"]): pts += 100
                            if "霊的波長" in user_instruction and any(k in str(c.get('霊的要素','')) for k in ["動物", "幽霊", "シンクロ"]): pts += 100
                            if "物理法則" in user_instruction and "連番波及" in str(c.get('予測ロジック','')): pts += 100
                            if "徳と祈り" in user_instruction and any(k in str(c.get('祈り/夢','')) for k in ["平和", "笑顔", "自由", "住宅", "結婚式", "感謝"]): pts += 100
                            
                            c['sort_pts'] = pts + random.randint(0, 50) 
                            
                        target_list.sort(key=lambda x: x['sort_pts'], reverse=True)
                        
                        final_picks = []
                        used_start_nums = []
                        used_end_nums = []
                        limit_dupe_start = max(2, int(buy_count / 5))
                        limit_dupe_end = max(2, int(buy_count / 5))

                        for c in target_list:
                            s = c.get('数字1')
                            e = c.get(f'数字{LOTO_PICK_COUNT}')
                            if used_start_nums.count(s) >= limit_dupe_start: continue
                            if used_end_nums.count(e) >= limit_dupe_end: continue
                            nums = set([int(c.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(c.get(f"数字{i}")).isdigit()])
                            if any(len(nums & set([int(u.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(u.get(f"数字{i}")).isdigit()])) >= 4 for u in final_picks): continue
                            
                            final_picks.append(c)
                            used_start_nums.append(s)
                            used_end_nums.append(e)
                            if len(final_picks) == buy_count: break
                        
                        if len(final_picks) < buy_count:
                            for c in target_list:
                                if c not in final_picks:
                                    final_picks.append(c)
                                    if len(final_picks) == buy_count: break

                        ai_prompt = "\n".join([f"[{r.get('実行者','')} | 社会:{r.get('社会情勢','')} | 霊的:{r.get('霊的要素','')} | AI予知:{r.get('AI直感','')}] " + ",".join([str(r.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1)]) for r in final_picks])
                        
                        prompt = f"""
                        {AWAKENED_SCIENTIST_PROMPT}
                        
                        ユーザーからの特別作戦指示: "{user_instruction}"
                        
                        【システムが積み上げから厳選した{buy_count}口（10億円捕捉陣形）】\n{ai_prompt}
                        """
                        try:
                            model = genai.GenerativeModel(get_ai_model_name(), system_instruction=AWAKENED_SCIENTIST_PROMPT)
                            res = model.generate_content(prompt)
                            st.markdown(f"#### 🎯 最終決断レポート（10億捕捉の{buy_count}口）")
                            display_cols = ["実行者", "口数"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + ["社会情勢", "霊的要素", "AI直感", "予測ロジック"]
                            st.dataframe(pd.DataFrame(final_picks)[display_cols])
                            st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                            st.write("▼ 最強予知科学者（Gemini）からの絶対的予言レポート")
                            st.write(res.text)
                            st.markdown("</div>", unsafe_allow_html=True)
                            
                            now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
                            df_history = load_sheet("決断記録簿")
                            save_text = f"【指示】: {user_instruction}\n【厳選の{buy_count}口】\n" + ai_prompt + "\n\n【AIの解説】\n" + res.text
                            new_history = pd.DataFrame({"日時": [now_str], "対象回号": [t_round_decide_str], "決断内容": [save_text]})
                            df_history = pd.concat([new_history, df_history], ignore_index=True) if not df_history.empty else new_history
                            save_sheet("決断記録簿", df_history)
                            st.success("決断内容は『決断記録簿』に強固に保管されました。10億円の引き寄せは完了しました！")
                        except Exception as e: 
                            st.error(f"AIによる最終決断レポートの生成に失敗しました: {e}")

elif st.session_state.menu == "結果発表と振り返り":
    st.title("🔄 答え合わせと地球規模の反省会")
    tab1, tab2, tab3 = st.tabs(["予測の答え合わせ", "💬 宇宙と繋がる徹底反省会（PDCA）", "過去の決断記録簿"])
    
    df_note = load_sheet("予測ノート")
    df_real = load_sheet("実データ")
    auto_round, _ = get_next_round_info(df_real)
    
    # ★手打ち入力排除：確認する回号のプルダウン
    if not df_note.empty and "対象回号" in df_note.columns:
        rounds_set = set(df_note["対象回号"].tolist())
        def ext_num(s):
            m = re.findall(r'\d+', str(s))
            return int(m[0]) if m else 0
        rev_rounds = sorted(list(rounds_set), key=ext_num, reverse=True)
    else:
        rev_rounds = [f"第{auto_round - 1}回"]
        
    t_round_rev_str = st.selectbox("確認する回号を選択", rev_rounds)
    df_target = df_note[df_note["対象回号"] == t_round_rev_str] if not df_note.empty else pd.DataFrame()

    with tab1:
        if df_target.empty: st.info("予測データがありません。")
        else:
            st.write("※ 最新データ取得時に自動で採点された結果です。")
            display_cols = ["AIの助言", "実行者", "口数"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + ["社会情勢", "霊的要素"]
            st.dataframe(df_target[[c for c in display_cols if c in df_target.columns]], height=400)

    with tab2:
        st.markdown("#### 💬 一歩一歩真実に近づくための、量子レベルでの反省会")
        
        # ★手打ち入力排除：分析テーマのプルダウン
        rev_question_options = [
            "今回の正解番号は、地球の重力や環境、天下り等の社会状況、見えない力とどう量子的にリンクしていたか？",
            "ニアピン（惜しい数字）が起きた原因は何か？ 物理的な波及アルゴリズムのズレを徹底分析せよ。",
            "次回10億円を仕留めるため、私たちが日常で高めるべき波長（徳積み）と、焦点を当てるべきセンサーを指示せよ。"
        ]
        user_rev_input = st.selectbox("🧠 最強予知科学者への分析依頼テーマ", rev_question_options)
        
        if st.button("🌍 地球規模の徹底反省会をスタートする"):
            if not api_key: st.error("APIキーが設定されていません。")
            elif df_target.empty: st.warning("対象回号のデータがありません。")
            else:
                with st.spinner("実際の地球が出した答えと、我々の多角的予測とのズレを天才科学者が徹底分析中..."):
                    target_txt = "\n".join([f"{r['実行者']} / 社会:{r.get('社会情勢','')} / 霊的:{r.get('霊的要素','')} -> " + ",".join([str(r.get(f"数字{i}", "")) for i in range(1, LOTO_PICK_COUNT + 1)]) + f" (結果:{r['AIの助言']})" for _, r in df_target.iterrows()])
                    
                    # 回号文字列から数値を抽出して実データと照合
                    rev_num = re.findall(r'\d+', t_round_rev_str)
                    actual_match = pd.DataFrame()
                    if rev_num:
                        actual_match = df_real[df_real["回号"] == f"第{rev_num[0]}回"]
                    
                    actual_info = actual_match.to_csv(index=False) if not actual_match.empty else "未取得"
                    
                    prompt = f"""
                    {REVIEW_PDCA_PROMPT}
                    
                    【本抽選の正解データ】:\n{actual_info}\n【我が家の予測と結果】:\n{target_txt}\n【ユーザーからの依頼】: "{user_rev_input}"
                    """
                    try:
                        model = genai.GenerativeModel(get_ai_model_name(), system_instruction=AWAKENED_SCIENTIST_PROMPT)
                        res = model.generate_content(prompt)
                        st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                        st.write(res.text)
                        st.markdown("</div>", unsafe_allow_html=True)
                    except Exception as e: 
                        st.error(f"反省会レポートの生成中にエラーが発生しました。詳細: {e}")

    with tab3:
        df_history = load_sheet("決断記録簿")
        if not df_history.empty and "日時" in df_history.columns:
            for _, row in df_history.iterrows():
                with st.expander(f"記録: {row.get('日時', '')} | {row.get('対象回号', '')}"):
                    st.write(row.get("決断内容", ""))
        else: st.info("記録はありません。")

# ==========================================
# 6. 万能AI占い師の館（手打ち不要・スマホ無敵版）
# ==========================================
elif st.session_state.menu == "万能AI占い師の館":
    st.title("🔮 万能AI占い師の館（スマホ手打ち不要版）")
    st.markdown("<div class='info-box'>ここは予測システムとは別の、純粋な占いの空間です。<br><b>スマホのキーボードが邪魔にならないよう、テキスト入力を全廃し「プルダウンで聞きたいことを選ぶだけ」の究極仕様に進化しました。</b></div>", unsafe_allow_html=True)

    if not api_key:
        st.error("占い機能を利用するにはAPIキーの設定が必要です。")
    else:
        if "fortune_messages" not in st.session_state:
            st.session_state.fortune_messages = [
                {"role": "assistant", "content": "ようこそ、神秘の部屋へ。✨\n私は世界中のあらゆる占術をマスターし、「視覚」も持った最強の占い師です。\n\n今日は何の占いをしますか？下のメニューから選んでくださいね。"}
            ]
        if "fortune_chat_session" not in st.session_state:
            try:
                model = genai.GenerativeModel(get_ai_model_name(), system_instruction=FORTUNE_CHAT_PROMPT)
                st.session_state.fortune_chat_session = model.start_chat(history=[])
            except Exception as e: 
                st.error(f"AI占い師の準備に失敗しました。時間をおいて再試行してください: {e}")

        c1, c2 = st.columns([3, 1])
        div_list = ["西洋占星術（ホロスコープ）", "四柱推命", "タロット占い", "手相（要写真）", "人相（要写真）", "オーラ鑑定（要写真）", "コーヒー占い（要写真）"]
        selected_div = c1.selectbox("🔮 占術を選ぶ", ["占いを選択してください..."] + div_list)
        if c2.button("この占いを始める", use_container_width=True):
            if selected_div != "占いを選択してください...":
                user_msg = f"「{selected_div}」をお願いします。"
                st.session_state.fortune_messages.append({"role": "user", "content": user_msg})
                with st.spinner("星の声を聴いています..."):
                    if "fortune_chat_session" in st.session_state:
                        try:
                            response = st.session_state.fortune_chat_session.send_message(user_msg, safety_settings=SAFETY_SETTINGS)
                            reply = response.text if response.text else "（波動が乱れました。別の言葉でお試しください）"
                            st.session_state.fortune_messages.append({"role": "assistant", "content": reply})
                        except Exception as e:
                            st.session_state.fortune_messages.append({"role": "assistant", "content": f"（通信エラーが発生しました。再度お試しください: {e}）"})
                    else:
                        st.session_state.fortune_messages.append({"role": "assistant", "content": "AI占い師が準備できていません。リセットをお試しください。"})
                st.rerun()

        with st.form("chat_input_form", clear_on_submit=True):
            st.markdown("**💬 占い師に聞きたいことを選ぶ / 📸 写真を送る**")
            
            # ★手打ち入力を排除：占い師に聞くテーマのプルダウン
            fortune_options = [
                "私の全体的な運勢と現在の波動を鑑定してください。",
                "10億円を引き寄せるための、私の金運と直感の冴えを視てください。",
                "今の私の精神状態（オーラやエネルギー）はどうなっていますか？",
                "家族の幸せと未来について、星や運命はどう語っていますか？",
                "（写真を送信して）この画像から私の運命と波長を深く読み解いてください。"
            ]
            user_input = st.selectbox("占い師に聞きたい内容を選択", fortune_options)
            
            img_source = st.file_uploader("📂 スマホのカメラ起動・画像選択", type=["jpg", "jpeg", "png"])
            submit_btn = st.form_submit_button("🔮 占い師に送信する")

            if submit_btn:
                # 送信テキストの決定
                if user_input == "（写真を送信して）この画像から私の運命と波長を深く読み解いてください。" and not img_source:
                    st.error("写真が選択されていません。画像を選択するか、別の質問を選んでください。")
                else:
                    display_msg = user_input if not img_source else f"📸 写真を送信しました。 {user_input}"
                    st.session_state.fortune_messages.append({"role": "user", "content": display_msg})
                    
                    with st.spinner("星の導きを読み解いています..."):
                        if "fortune_chat_session" in st.session_state:
                            try:
                                if img_source:
                                    img = Image.open(img_source).convert('RGB')
                                    img.thumbnail((800, 800))
                                    msg_to_send = [user_input, img]
                                else:
                                    msg_to_send = user_input

                                response = st.session_state.fortune_chat_session.send_message(msg_to_send, safety_settings=SAFETY_SETTINGS)
                                reply = response.text if response.text else "（大いなる力により、言葉がブロックされました）"
                                st.session_state.fortune_messages.append({"role": "assistant", "content": reply})
                            except Exception as e:
                                st.session_state.fortune_messages.append({"role": "assistant", "content": f"（通信エラーが発生しました。再度お試しください: {e}）"})
                        else:
                            st.session_state.fortune_messages.append({"role": "assistant", "content": "AI占い師が準備できていません。リセットをお試しください。"})
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