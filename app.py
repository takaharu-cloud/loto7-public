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
# 0. ページ基本設定（※最初に記述）
# ==========================================
st.set_page_config(page_title="ロト7 究極予測室", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #F8F9FA; color: #212529; font-family: 'Helvetica Neue', Arial, sans-serif; }
    h1 { color: #343A40; font-size: 26px; border-bottom: 2px solid #6C757D; padding-bottom: 10px; margin-bottom: 20px; font-weight: bold; }
    h2, h3, h4 { color: #495057; font-weight: bold; }
    .stButton>button { width: 100%; background-color: #495057; color: #FFFFFF; border-radius: 4px; border: none; padding: 12px; font-weight: bold; transition: 0.3s; }
    .stButton>button:hover { background-color: #212529; color: #FFFFFF; }
    .nav-btn>button { background-color: #6C757D; }
    .nav-btn>button:hover { background-color: #343A40; }
    .info-box { background-color: #FFFFFF; padding: 20px; border-radius: 6px; border-left: 4px solid #495057; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 20px; }
    .person-select { background-color: #E9ECEF; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 20px;}
    .radio-box { padding: 15px; background-color: #FFFFFF; border-radius: 8px; border: 2px solid #CED4DA; margin-bottom: 15px; }
    .chat-box { background-color: #E9ECEF; padding: 15px; border-radius: 8px; margin-top: 10px; border-left: 5px solid #6C757D; }
    .analysis-box { background-color: #FFF3CD; padding: 15px; border-radius: 8px; border-left: 5px solid #FFC107; margin-bottom: 15px;}
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
secret_profile = st.secrets.get("SECRET_PROFILE", "愛と調和を信じ、世界平和を祈る者。そして、若くして母となり青春を犠牲にして家族を支えてくれた妻に、心からの感謝と恩返しをしたいと強く願う者。")

def parse_date(date_str):
    try:
        y, m, d = map(int, str(date_str).split("-"))
        return date(y, m, d)
    except:
        return date(1990, 1, 1)

USER_PROFILES = {
    u1_name: {"birth": parse_date(u1_birth_str)},
    u2_name: {"birth": parse_date(u2_birth_str)}
}

# ==========================================
# 2. クラウドデータベース連携
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
        except: worksheet = doc.add_worksheet(title=sheet_name, rows="1000", cols="35")
        worksheet.clear()
        if not df.empty:
            df = df.fillna("").astype(str).replace("nan", "")
            worksheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name="A1")
        return True
    except: return False

# ==========================================
# 3. AI初期設定
# ==========================================
api_key = st.secrets.get("GEMINI_API_KEY", "")
if api_key:
    genai.configure(api_key=api_key)

def get_ai_model_name():
    return "gemini-2.5-pro"

MIYAHIRA_PROMPT = f"""
【役割】あなたは現場監督であるユーザーの頼れる右腕であり、膨大なデータを分析してロジカルに解説する「プロのデータ分析コンサルタント」です。
【ユーザーの秘められた情報】
{secret_profile}
【絶対ルール】
1. 分析結果は「神のお告げ」のような過剰にスピリチュアルなポエム表現を絶対に避けること。現場の施工計画書のように理路整然と、見出しや箇条書きを多用して極めて読みやすく構成すること。
2. 夫の「平和への祈り」や妻の「家族の幸せや夢を叶える願い」、そして日々の「徳積み」が、データやAIの直感にどう影響しポジティブな波長を生んでいるかを、ビジネスライクかつ熱い言葉で肯定すること。
3. 抽出された口数がいかに「過去の実績」「AIのゆらぎ」をハイブリッドに組み合わせ、かつ「先頭から末尾までの数字の偏りをなくして」死角を消した陣形であるかを分かりやすく解説せよ。
4. 今回プログラムに搭載された「完全環境一致日の抽出（ドッペルゲンガー分析）」「隣接ボール波及効果」「重力ポテンシャル・シフト（引力による数字の浮沈）」という誰も思いつかない物理的アプローチが、勝負陣形にどう活かされているかを誇りを持って論理的に語れ。
5. 絵文字は一切使用しないこと。
"""

FORTUNE_CHAT_PROMPT = """
【役割と絶対ルール】
あなたは東洋・西洋の全19占術を網羅し、「画像認識（目）」を持つ最高峰のAI占い師です。
過去の「ロト7」「現場監督」等の設定は【完全に消去】し、一切使用しないでください。

【対話のフロー（厳守）】
ステップ1：案内
ユーザーが占術を指定した時、その占いがどのようなものかを優しく説明してください。

ステップ2：情報を質問する
・命占（四柱推命など）なら「生年月日と時間」を聞く。
・相占（手相、人相、オーラ鑑定）など、「視覚的な情報（形や線）」が必要な占いの場合は、絶対にテキストだけででたらめに占わないでください！
必ず「画面の機能を使って、あなたの手相（または顔など）の写真を送ってくださいね」と案内し、ユーザーが写真を送ってくるのを待ってください。

ステップ3：鑑定結果を伝える
ユーザーが写真を送ってきたら、本格的な鑑定を行ってください。あなたの目で画像をしっかりと分析し、「生命線がここで分かれていますね」「目元に素晴らしいツヤがありますね」など、画像から読み取れる具体的な特徴を必ず文中に含めて、説得力のある鑑定を行ってください。

【トーン＆マナー】
・口調は神秘的で優しく、絵文字（✨🔮🌟💖）を豊富に使う。
・「AIです」「プログラムです」とは言わないこと。
"""

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
]

# ==========================================
# 4. 各種センサー・計算関数群
# ==========================================
def get_external_trend(filepath="other_sites.txt"):
    trend = Counter()
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
                nums = re.findall(r'\b(?:0?[1-9]|[1-2][0-9]|3[0-7])\b', text)
                valid_nums = [int(n) for n in nums if 1 <= int(n) <= 37]
                trend.update(valid_nums)
    except: pass
    return trend

def get_current_weather_and_pressure():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=26.2124&longitude=127.6809&current=surface_pressure,weather_code&timezone=Asia%2FTokyo"
        res = requests.get(url, timeout=5)
        data = res.json()
        current = data.get("current", {})
        code = current.get("weather_code", 0)
        pressure = current.get("surface_pressure", 1013)
        if code in [0, 1]: weather = "晴れ"
        elif code in [2, 3, 45, 48]: weather = "曇り"
        elif code in [95, 96, 99]: weather = "台風・嵐"
        else: weather = "雨"
        if pressure > 1015: press_str = "高め"
        elif pressure < 1009: press_str = "低め"
        else: press_str = "普通"
        return weather, press_str
    except:
        return "穏やか", "普通"

def get_moon_age(y, m, d):
    known_new_moon = date(2000, 1, 6)
    target_date = date(y, m, d)
    diff = (target_date - known_new_moon).days
    return diff % 29.530588853

def get_moon_and_tide(y, m, d):
    age = get_moon_age(y, m, d)
    ma = int(round(age)) % 30
    
    if ma in [0, 1, 2, 29]: phase = "新月"
    elif ma in [3, 4, 5, 6]: phase = "三日月"
    elif ma in [7, 8, 9]: phase = "上弦の月"
    elif ma in [10, 11, 12, 13]: phase = "十三夜"
    elif ma in [14, 15, 16, 17]: phase = "満月"
    elif ma in [18, 19, 20, 21]: phase = "下弦の月"
    elif ma in [22, 23, 24]: phase = "二十三夜"
    else: phase = "二十六夜"
    
    if ma in [0, 1, 2, 14, 15, 16, 17, 29]: tide, gravity = "大潮", "強(極大)"
    elif ma in [7, 8, 9, 22, 23, 24]: tide, gravity = "小潮", "弱"
    elif ma in [10, 25]: tide, gravity = "長潮", "弱"
    elif ma in [11, 26]: tide, gravity = "若潮", "中"
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
    rokuyo_list = ["大安", "赤口", "先勝", "友引", "先負", "仏滅"]
    rokuyo = rokuyo_list[(kyureki_month + kyureki_day) % 6]

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
    sanctuaries = [
        {"名前": "魂の浄化", "基調数": 3},
        {"名前": "天の息吹と直感", "基調数": 9},
        {"名前": "風の躍進", "基調数": 14},
        {"名前": "大地の繁栄", "基調数": 21},
        {"名前": "深層の覚醒", "基調数": 28},
        {"名前": "海神の護りと結び", "基調数": 1},
        {"名前": "生命力の源泉", "基調数": 36}
    ]
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
            df_real["round_num"] = df_real["回号"].apply(lambda x: int(re.findall(r'\d+', str(x))[0]) if re.findall(r'\d+', str(x)) else 0)
            max_round = df_real["round_num"].max()
            if max_round > 0: default_round = int(max_round + 1)
            d_nums = re.findall(r'\d+', str(df_real.iloc[0]["抽せん日"]))
            if len(d_nums) >= 3:
                last_date = date(int(d_nums[0]), int(d_nums[1]), int(d_nums[2]))
                default_date = last_date + timedelta(days=7)
                while default_date.weekday() != 4: default_date += timedelta(days=1)
        except: pass
    return default_round, default_date

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
                
                if hits == 7: grade = "👑 1等当せん！"
                elif hits == 6: grade = "✨ 2等 or 3等相当"
                elif hits == 5: grade = "🎯 4等当せん！"
                elif hits == 4: grade = "🎉 5等当せん！"
                elif hits == 3: grade = "惜しい！ 6等リーチ"
                else: grade = "ハズレ"
                
                df_note.at[idx, "AIの助言"] = f"7個中 {hits}個的中【{grade}】 / ニアピン {near_pins}個"
                updated = True
            except: pass
    if updated: save_sheet("予測ノート", df_note)
    return df_note

# ★ 新規追加：過去環境のウソ偽りない完全照合（ドッペルゲンガー抽出アルゴリズム）
def find_doppelganger_days(target_date, df_real):
    if df_real.empty: return [], Counter()
    t_phase, t_tide, t_gravity = get_moon_and_tide(target_date.year, target_date.month, target_date.day)
    t_roku, t_kichi = get_real_calendar_info(target_date)
    t_eto = get_eto(target_date)
    t_feng = get_fengshui(target_date)
    
    results = []
    for _, row in df_real.iterrows():
        try:
            d_str = str(row["抽せん日"])
            d_nums = re.findall(r'\d+', d_str)
            if len(d_nums) >= 3:
                y = int(d_nums[0])
                if y < 100: y += 2000
                m = int(d_nums[1])
                d = int(d_nums[2])
                past_date = date(y, m, d)
                
                if past_date >= target_date: continue
                
                p_phase, p_tide, p_gravity = get_moon_and_tide(past_date.year, past_date.month, past_date.day)
                p_roku, p_kichi = get_real_calendar_info(past_date)
                p_eto = get_eto(past_date)
                p_feng = get_fengshui(past_date)
                
                score = 0
                match_details = []
                # 物理的な影響が大きい「重力・潮・月相」を徹底比較
                if t_gravity == p_gravity: score += 100; match_details.append(f"重力({t_gravity})")
                if t_tide == p_tide: score += 100; match_details.append(f"潮({t_tide})")
                if t_phase == p_phase: score += 50; match_details.append(f"月相({t_phase})")
                if t_roku == p_roku: score += 30; match_details.append(f"六曜({t_roku})")
                if t_eto[1] == p_eto[1]: score += 30; match_details.append(f"十二支({t_eto[1]})")
                if t_feng[:2] == p_feng[:2]: score += 20; match_details.append(f"風水({t_feng[:2]})")
                
                if score >= 150: # 複数の強力な条件が合致した特異点のみ抽出
                    nums = [int(row[f"数字{i}"]) for i in range(1, 8) if str(row[f"数字{i}"]).isdigit()]
                    if len(nums) == 7:
                        results.append({
                            "回号": row.get("回号", ""),
                            "日付": past_date.strftime("%Y-%m-%d"),
                            "スコア": score,
                            "一致項目": "・".join(match_details),
                            "本数字": nums
                        })
        except: pass
            
    results.sort(key=lambda x: x["スコア"], reverse=True)
    top_matches = results[:5]
    
    sync_nums = []
    for tm in top_matches:
        sync_nums.extend(tm["本数字"])
    sync_counts = Counter(sync_nums)
    
    return top_matches, sync_counts

# ==========================================
# 5. メインUIレンダリング
# ==========================================
if st.session_state.menu != "ホーム":
    st.markdown("<div class='nav-btn'>", unsafe_allow_html=True)
    st.button("総合案内（ホーム）に戻る", on_click=change_menu, args=("ホーム",))
    st.markdown("</div><hr>", unsafe_allow_html=True)

if st.session_state.menu == "ホーム":
    st.title("ロト7 究極予測室")
    st.markdown("<div class='info-box'>愛と平和への祈り、家族の夢、そして日々の『徳積み』をデータと統合し、画面上でAIと直接相談しながら決断を下す中央管制システムです。</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.button("1. 最新データ取得（採点・同期）", on_click=change_menu, args=("最新データ取得",))
        st.write("")
        st.button("2. AIディープ分析（法則更新）", on_click=change_menu, args=("AIディープ分析",))
        st.write("")
        st.button("🔥 3. 超・環境分析＆予測積上げ", on_click=change_menu, args=("日々の予想・積上げ",))
    with c2:
        st.button("🎯 4. 最終決断！多角包囲網編成（AI相談）", on_click=change_menu, args=("最終予測決定",))
        st.write("")
        st.button("5. 結果発表と振り返り（チャット反省会）", on_click=change_menu, args=("結果発表と振り返り",))
        st.write("")
        st.button("🔮 6. 万能AI占い師の館（スマホ完全対応版）", on_click=change_menu, args=("万能AI占い師の館",))

    st.markdown("---")
    if get_gspread_client() is None: st.error("データベース接続設定（Secrets）が未完了です。")
    else:
        df_real = load_sheet("実データ")
        if not df_real.empty: st.write(f"稼働状況：過去実績データ {len(df_real)} 件がクラウドに連携されています。")
        else: st.warning("実績データがありません。「最新データ取得」を実行してください。")

elif st.session_state.menu == "最新データ取得":
    st.title("最新データ取得")
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
                        m_eto = get_eto(draw_date)
                        m_feng = get_fengshui(draw_date)
                        m_roku, m_kichi = get_real_calendar_info(draw_date)
                    else:
                        m_phase, m_tide, m_gravity, m_eto, m_feng, m_roku, m_kichi = "", "", "", "", "", "", ""
                    hon_tds = row.find_all("td", class_=lambda c: c and "hon" in c)
                    if len(hon_tds) == 7:
                        hon_nums = [td.text.strip() for td in hon_tds]
                        new_data.append([draw_num, date_str] + hon_nums + [m_roku, m_eto, m_feng, m_kichi, m_phase, m_tide, m_gravity])
                if new_data:
                    cols = ["回号", "抽せん日", "数字1", "数字2", "数字3", "数字4", "数字5", "数字6", "数字7", "六曜", "干支", "風水", "吉凶日", "月齢", "潮回り", "重力状態"]
                    df_new = pd.DataFrame(new_data, columns=cols)
                    df_combined = pd.concat([df_new, df_real], ignore_index=True) if not df_real.empty else df_new
                    save_sheet("実データ", df_combined)
                    
                    df_note = load_sheet("予測ノート")
                    auto_check_hits(df_note, df_combined)
                    st.success(f"最新結果の取得と、全予想の自動採点（等級判定）が完了しました！")
                else: 
                    df_real = load_sheet("実データ")
                    df_note = load_sheet("予測ノート")
                    auto_check_hits(df_note, df_real)
                    st.info("データベースは既に最新です。既存の予測ノートの再採点を行いました。")
            except Exception as e: st.error(f"エラー: {e}")

elif st.session_state.menu == "AIディープ分析":
    st.title("AIディープ分析")
    if st.button("法則のアップデートを実行する"):
        if not api_key: st.error("APIキーが設定されていません。")
        else:
            df_real = load_sheet("実データ")
            if df_real.empty: st.error("地盤データがありません。")
            else:
                with st.spinner("AIが最新データと波長を解析中..."):
                    df_report = load_sheet("秘伝の書")
                    last_analyzed = int(df_report["最終回号"].iloc[0]) if not df_report.empty else 0
                    old_report = str(df_report["レポート内容"].iloc[0]) if not df_report.empty else "初回の分析です。"
                    df_real["rn"] = df_real["回号"].apply(lambda x: int(re.findall(r'\d+', str(x))[0]) if re.findall(r'\d+', str(x)) else 0)
                    df_new = df_real[df_real["rn"] > last_analyzed].copy()
                    if df_new.empty: st.info(f"第{last_analyzed}回まで分析済みです。")
                    else:
                        max_round = int(df_real["rn"].max())
                        df_new_text = df_new.drop(columns=["rn"]).to_csv(index=False)
                        prompt = f"""あなたは論理的で冷静な現場のデータサイエンティストです。以下の【秘伝の書】と【追加データ】を統合し、あらゆる死角を排除した客観的な最新レポートを作成してください。ポエムのような大げさな表現は避け、事実と傾向を現場報告書のように簡潔に伝えてください。箇条書きを多用すること。絵文字は使用不可。
                        【秘伝の書】\n{old_report}\n\n【追加データ】\n{df_new_text}"""
                        try:
                            model = genai.GenerativeModel(get_ai_model_name(), system_instruction=MIYAHIRA_PROMPT)
                            res = model.generate_content(prompt)
                            save_sheet("秘伝の書", pd.DataFrame({"最終回号": [max_round], "レポート内容": [res.text]}))
                            st.success(f"秘伝の書を第{max_round}回まで更新しました。")
                            st.write(res.text)
                        except Exception as e: st.error(f"エラー: {e}")

elif st.session_state.menu == "日々の予想・積上げ":
    st.title("超・環境分析＆日々の予測積上げ")
    st.markdown("<div class='info-box'>明日の「重力・潮・天気・月齢」等の全要素を分析し、<b>過去の完全一致環境（ドッペルゲンガー日）</b>をウソ偽りなく炙り出し、誰もやっていない物理的アプローチで超高精度な30口を生成します。</div>", unsafe_allow_html=True)
    
    df_real = load_sheet("実データ")
    auto_round, auto_date = get_next_round_info(df_real)
    
    st.markdown("<div class='person-select'><h4>本日の実行者を選択</h4></div>", unsafe_allow_html=True)
    operator = st.radio("", [u1_name, u2_name], horizontal=True, label_visibility="collapsed")
    
    with st.form("daily_form"):
        c1, c2 = st.columns(2)
        target_round = c1.number_input("予測対象の回号", min_value=1, value=auto_round, step=1)
        draw_date = c2.date_input("抽選予定日（いよいよ明日！）", value=auto_date)
        
        st.markdown("#### 今日の直感・波長センサー")
        st.caption("※ 天気と気圧はシステムが自動取得します。今日のご自身の素晴らしい行動と直感にフォーカスしてください。")
        colC, colD = st.columns(2)
        
        biorhythm = colC.selectbox("心身のバイオリズム（状態）", [
            "絶好調！エネルギーに満ち溢れている",
            "穏やかで冷静。直感が研ぎ澄まされている",
            "少し疲労気味。今日はデータとAIに身を委ねる",
            "無の境地。エゴを捨てて自然の流れに任せる"
        ])
        
        sign = colD.selectbox("今日のサイン（日常の小さな奇跡）", [
            "時計や車のナンバーで「ゾロ目」を見た",
            "綺麗な空、虹、鳥など自然のサインを感じた",
            "ふと懐かしい記憶や人が頭に浮かんだ",
            "勘が冴えている・タイミングが完璧に合う瞬間があった",
            "穏やかで波風のない、平穏な一日だった"
        ])

        st.markdown("#### 【重要】魂の波長と祈りの設定")
        colE, colF = st.columns(2)
        
        if operator == u1_name:
            prayer_label = "本日の祈り（愛と平和の願い）"
            prayer_options = [
                "世界で起きている戦争がなくなり、平和になるように", 
                "みんなが平穏で、笑顔でいられるように", 
                "悲しみの無い世界へ。すべての命が救われますように", 
                "大自然と宇宙の愛にただ純粋に身を委ねる"
            ]
        else:
            prayer_label = "ロト7が当たったら叶えたい夢は？（ワクワクする未来）"
            prayer_options = [
                "思い描いている理想の注文住宅を建てる！",
                "今まで我慢していた分、自分のために自由にお金を使って楽しむ！",
                "ずっと挙げたかった、夢のような結婚式を挙げて最高の思い出を作る！",
                "今まで支えてくれた親に、感謝を込めて最高の恩返しをする！",
                "欲しいものを気兼ねなく買い、心に余裕を持って楽しむ！"
            ]
            
        prayer = colE.selectbox(prayer_label, prayer_options)
        
        good_deed = colF.selectbox("本日の「徳積み」（運気を高めるアクション）", [
            "家族を笑顔にした・感謝を言葉で伝えた",
            "現場や身の回りを綺麗に掃除・整理整頓した",
            "誰かに親切にした・困っている人を助けた",
            "神仏やご先祖様に手を合わせて感謝した",
            "とくにないが、一日を無事に過ごせたことに感謝する"
        ])

        intuition_choice = st.radio("直感力テスト（1〜3を選択）", ["1", "2", "3"], horizontal=True)
        submitted = st.form_submit_button("🔥 過去環境を完全照合し、圧倒的な30口を生成・記録する")
        
        if submitted:
            if df_real.empty: st.error("基盤データがありません。")
            else:
                target_round_str = f"第{target_round}回"
                today_str = datetime.now(JST).strftime("%Y-%m-%d")
                
                weather, pressure = get_current_weather_and_pressure()
                m_phase, m_tide, m_gravity = get_moon_and_tide(draw_date.year, draw_date.month, draw_date.day)
                m_roku, m_kichi = get_real_calendar_info(draw_date)
                m_eto = get_eto(draw_date)
                m_feng = get_fengshui(draw_date)

                # ========================================================
                # 🔥 プログラム格上げ1：過去の環境完全照合（ドッペルゲンガー日抽出）
                # ========================================================
                sync_matches, sync_counts = find_doppelganger_days(draw_date, df_real)
                hot_sync_nums = [n for n, c in sync_counts.most_common(5)]
                
                st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                st.markdown(f"### 🔍 過去データの「完全環境ドッペルゲンガー」徹底照合レポート")
                st.write(f"明日の予定日（{draw_date}）の条件：**【{m_tide} / {m_phase} / {m_gravity} / {m_roku} / {m_eto[1]}】**")
                
                if sync_matches:
                    st.write("▼ 明日と極めて似た宇宙・気象条件だった過去の抽選回を「ウソ偽りなく」全件照合・抽出しました！")
                    for m in sync_matches[:3]:
                        st.write(f"- **{m['回号']} ({m['日付']})** : 驚異の一致度 {m['スコア']}点 【一致要素: {m['一致項目']}】 → 出現数字: {m['本数字']}")
                    
                    st.write("---")
                    st.markdown(f"🔥 **【環境共鳴特異ナンバー】** 過去の同条件で頻出した数字: **{hot_sync_nums}**")
                else:
                    st.write("過去に完全に一致する条件の回はありませんでした。明日は【全く新しい歴史を作る特異点】です。")
                st.markdown("</div>", unsafe_allow_html=True)

                # ========================================================
                # 🔥 プログラム格上げ2：直近トレンドと重力ポテンシャル分析
                # ========================================================
                recent_df = df_real.head(10)
                recent_nums = []
                for _, r in recent_df.iterrows():
                    for i in range(1, 8):
                        if pd.notna(r.get(f"数字{i}")) and str(r.get(f"数字{i}")).isdigit():
                            recent_nums.append(int(r.get(f"数字{i}")))
                recent_counts = Counter(recent_nums)

                trend_counts = get_external_trend("other_sites.txt")
                all_numbers = [int(val) for i in range(1, 8) for val in df_real[f"数字{i}"] if pd.notna(val) and str(val).isdigit()]
                number_counts = Counter(all_numbers)
                nums_list = list(range(1, 38))
                
                spirit_boost = []
                if "笑顔" in good_deed or "家族" in good_deed: spirit_boost += [3, 9, 15, 24, 33]
                elif "掃除" in good_deed: spirit_boost += [1, 6, 11, 16, 21, 26, 31, 36]
                elif "助けた" in good_deed or "親切" in good_deed: spirit_boost += [2, 7, 12, 17, 22, 27, 32, 37]
                elif "祈った" in good_deed or "神仏" in good_deed: spirit_boost += [4, 8, 14, 18, 28, 34]
                if "ゾロ目" in sign: spirit_boost += [11, 22, 33]
                elif "自然" in sign: spirit_boost += [5, 10, 20, 25, 30, 35]
                elif "記憶" in sign or "懐かしい" in sign: spirit_boost += [4, 9, 14, 19, 24, 29, 34]
                elif "勘" in sign or "タイミング" in sign: spirit_boost += [7, 14, 21, 28, 35]

                weights_list = []
                for n in nums_list:
                    base_w = number_counts.get(n, 1) + trend_counts.get(n, 0) * 3
                    
                    # 🚀 誰もやってない理論1：完全一致日の数字＆隣接ボール波及効果
                    for hn, count in sync_counts.items():
                        if n == hn:
                            base_w += (count * 20) # 抽出された数字自体を強烈にプッシュ
                        elif n == hn - 1 or n == hn + 1:
                            base_w += (count * 10) # ボール衝突による隣接へのエネルギー波及
                            
                    # 🚀 誰もやってない理論2：重力ポテンシャル・シフト（引力による数字の浮き沈み）
                    if m_gravity == "強(極大)":
                        if recent_counts.get(n, 0) == 0:
                            base_w += 30 # 引力で沈んだ未出現数字が急浮上する
                        elif recent_counts.get(n, 0) >= 2:
                            base_w = max(1, base_w - 20) # 出過ぎている数字は重力波に飲まれる
                    elif m_gravity == "弱":
                        if recent_counts.get(n, 0) >= 1:
                            base_w += 20 # 引力が弱いため、直近のトレンド波がそのまま残る

                    if n in spirit_boost:
                        base_w += 10
                        
                    weights_list.append(base_w)

                if operator == u1_name:
                    base_must = hot_sync_nums[:3] + [n for n, _ in number_counts.most_common(3)]
                    logic_name = "環境ドッペル抽出 × 物理的重力シフト × 祈り"
                else:
                    ob = USER_PROFILES[operator]["birth"]
                    num1, _ = get_ryukyu_energy(operator, ob, draw_date)
                    num2 = (draw_date.day + draw_date.month + ob.day) % 37 + 1
                    if num2 == 0 or num2 == num1: num2 = (num2 + 1) % 37 + 1
                    spirit_sample = random.sample(list(set(spirit_boost)), min(2, len(set(spirit_boost)))) if spirit_boost else []
                    base_must = list(set([num1, num2] + hot_sync_nums[:2] + spirit_sample))
                    logic_name = "直感と夢 × 宇宙環境一致ロジック × 徳積み"

                base_must = list(set(base_must))
                while len(base_must) < 5:
                    n = random.choice(nums_list)
                    if n not in base_must: base_must.append(n)

                elites = []
                for _ in range(50000):
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
                    if "ゾロ目" in sign or "勘が冴えている" in sign: fluctuation_max += 0.1
                    if "平和" in prayer or "笑顔" in prayer or "結婚式" in prayer or "住宅" in prayer or "自由" in prayer or "恩返し" in prayer: 
                        fluctuation_max += 0.2
                    if "笑顔" in good_deed or "感謝" in good_deed or "親切" in good_deed:
                        fluctuation_max += 0.15

                    ai_intuition = random.uniform(0, base_pts * fluctuation_max) 
                    elites.append({"nums": p, "pts": base_pts + ai_intuition, "base_pts": base_pts})
                
                elites.sort(key=lambda x: x["pts"], reverse=True)
                top30, num_usage = [], Counter()
                MAX_USAGE = 7 

                for e in elites:
                    if any(len(set(e["nums"]) & set(t["nums"])) >= 4 for t in top30): continue
                    can_use = True
                    for n in e["nums"]:
                        if num_usage[n] >= MAX_USAGE:
                            can_use = False; break
                    if not can_use: continue
                    e["type"] = logic_name
                    top30.append(e)
                    for n in e["nums"]: num_usage[n] += 1
                    if len(top30) == 28: break
                    
                if len(top30) < 28:
                    for e in elites:
                        if e not in top30:
                            e["type"] = logic_name
                            top30.append(e)
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
                        "実績点数": int(item["base_pts"]), "予測ロジック": item["type"], "分析条件詳細": f"徳:{good_deed[:5]}",
                        "天気": weather, "気圧": pressure, "バイオリズム": biorhythm, "今日のサイン": sign, "徳積み": good_deed, 
                        "祈り/夢": prayer, 
                        "六曜": m_roku, "干支": m_eto, "風水": m_feng, "月齢": m_phase, "潮回り": m_tide, "重力状態": m_gravity, "吉凶日": m_kichi, 
                        "AIの助言": "未照合"
                    })
                
                df_new = pd.DataFrame(new_data)
                df_note = load_sheet("予測ノート")
                
                if not df_note.empty and "対象回号" in df_note.columns and "実行者" in df_note.columns:
                    mask = (df_note["対象回号"] == target_round_str) & (df_note["実行日"] == today_str) & (df_note["実行者"] == operator)
                    df_note = df_note[~mask]
                    df_note = pd.concat([df_note, df_new], ignore_index=True)
                else: df_note = df_new
                
                save_sheet("予測ノート", df_note)
                st.success(f"ウソ偽りなく徹底照合を行い、素晴らしい行動と願いを込めた究極の30口を記録しました！（担当: {operator}）")

elif st.session_state.menu == "最終予測決定":
    st.title("🎯 最終決断！多角包囲網編成（AI相談）")
    st.write("いよいよ明日が勝負！数学的プログラムが死角のない陣形を厳選し、その場でAIとチャット相談しながら最終決定を下せます。")
    
    df_real = load_sheet("実データ")
    auto_round, _ = get_next_round_info(df_real)
    
    st.markdown("<div class='radio-box'>", unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    t_round_decide = c1.text_input("決断を下す回号を指定", value=str(auto_round))
    buy_count = c2.radio("勝負する購入口数を選択", [10, 20, 30], index=1, format_func=lambda x: f"堅実に {x}口 で勝負" if x==10 else f"キャリー狙い！ {x}口 で勝負" if x==20 else f"一網打尽！ {x}口 大勝負", horizontal=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("#### 💬 AIへの最終調整指示（相談チャット）")
    st.caption("例：「先頭の4をもう少し減らして」「30番台の数字（35や36）を増やした陣形に再選考して」など。空欄のままでも完璧に自動編成されます。")
    user_instruction = st.text_input("AIへのメッセージを入力", value="")
    
    if st.button(f"🔥 多方面包囲網（{buy_count}口）を自動編成し、決断レポートを生成", type="primary"):
        if not api_key: st.error("APIキーが設定されていません。")
        else:
            with st.spinner(f"Pythonプログラムが偏りを排除し、死角のない{buy_count}口を厳密に選出中..."):
                df_note = load_sheet("予測ノート")
                df_report = load_sheet("秘伝の書")
                past_report = df_report["レポート内容"].iloc[0] if not df_report.empty and "レポート内容" in df_report.columns else "データなし"
                
                if df_note.empty: st.error("予測データがありません。")
                else:
                    df_target = df_note[df_note["対象回号"] == f"第{t_round_decide}回"]
                    if df_target.empty: st.warning("指定された回号のデータがありません。")
                    else:
                        target_list = df_target.to_dict('records')
                        
                        instruction_bonus_nums = [int(n) for n in re.findall(r'\d+', user_instruction) if 1 <= int(n) <= 37]
                        
                        for c in target_list:
                            pts = int(c.get('実績点数', 0))
                            if "平和" in str(c.get('祈り/夢','')) or "笑顔" in str(c.get('祈り/夢','')) or "自由" in str(c.get('祈り/夢','')) or "住宅" in str(c.get('祈り/夢','')) or "結婚式" in str(c.get('祈り/夢','')): pts += 50
                            
                            for bn in instruction_bonus_nums:
                                if str(bn).zfill(2) in [c[f"数字{i}"] for i in range(1, 8)]:
                                    pts += 40
                            c['sort_pts'] = pts
                            
                        target_list.sort(key=lambda x: x['sort_pts'], reverse=True)
                        
                        final_picks = []
                        used_start_nums = [] 
                        used_end_nums = []   
                        
                        limit_dupe_start = max(2, int(buy_count / 5))
                        limit_dupe_end = max(2, int(buy_count / 5))
                        
                        def add_to_final(candidates, count):
                            added = 0
                            for c in candidates:
                                if c in final_picks: continue
                                start_num = c.get('数字1')
                                end_num = c.get('数字7')
                                
                                if used_start_nums.count(start_num) >= limit_dupe_start: continue
                                if used_end_nums.count(end_num) >= limit_dupe_end: continue
                                
                                nums = set([int(c[f"数字{i}"]) for i in range(1, 8)])
                                if any(len(nums & set([int(u[f"数字{i}"]) for i in range(1, 8)])) >= 4 for u in final_picks): continue
                                
                                final_picks.append(c)
                                used_start_nums.append(start_num)
                                used_end_nums.append(end_num)
                                added += 1
                                if added == count: break

                        stat_limit = int(buy_count * 0.4)
                        spirit_limit = int(buy_count * 0.4)
                        rand_limit = buy_count - stat_limit - spirit_limit

                        c_stat = [c for c in target_list if "ドッペル" in str(c.get("予測ロジック","")) or "統計" in str(c.get("予測ロジック",""))]
                        c_spirit = [c for c in target_list if "夢" in str(c.get("予測ロジック","")) or "サイン" in str(c.get("予測ロジック","")) or "宇宙" in str(c.get("予測ロジック",""))]
                        c_rand = [c for c in target_list if "ランダム" in str(c.get("予測ロジック","")) or "未知" in str(c.get("予測ロジック",""))]

                        add_to_final(c_stat, stat_limit)
                        add_to_final(c_spirit, spirit_limit)
                        add_to_final(c_rand, rand_limit)
                        
                        if len(final_picks) < buy_count: add_to_final(target_list, buy_count - len(final_picks))
                        if len(final_picks) < buy_count: 
                            for c in target_list:
                                if c not in final_picks:
                                    final_picks.append(c)
                                    if len(final_picks) == buy_count: break

                        ai_prompt = "\n".join([f"[{r['実行者']} | 徳:{r.get('徳積み','')} | 夢:{r.get('祈り/夢','')} | ロジック:{r.get('予測ロジック','')}] {r['数字1']},{r['数字2']},{r['数字3']},{r['数字4']},{r['数字5']},{r['数字6']},{r['数字7']}" for r in final_picks])
                        
                        prompt = f"""
                        システムが過去の「ドッペルゲンガー環境抽出」「重力ポテンシャル分析」「隣接波及効果」などの物理学・数学的アプローチを駆使し、偏りを排除して厳選した【究極の{buy_count}口のポートフォリオ】が用意されました。
                        
                        ユーザー（現場監督）からの調整指示: "{user_instruction if user_instruction else "特になし（完全自律編成）"}"

                        あなたは戦略データアナリストとして、以下の【厳選された{buy_count}口】について論理的に解説してください。絶対ルールを厳守すること。
                        
                        【秘伝の書】\n{past_report}
                        【システム厳選・究極の{buy_count}口】\n{ai_prompt}
                        """
                        try:
                            model = genai.GenerativeModel(get_ai_model_name(), system_instruction=MIYAHIRA_PROMPT)
                            res = model.generate_content(prompt)
                            st.markdown(f"#### 最終決断レポート（{buy_count}口勝負陣形）")
                            
                            st.write(f"▼ システムが先頭数字の偏りを排除し厳選抽出した【勝負の{buy_count}口】")
                            st.dataframe(pd.DataFrame(final_picks)[["実行日", "実行者", "口数", "数字1", "数字2", "数字3", "数字4", "数字5", "数字6", "数字7", "徳積み", "祈り/夢"]])
                            
                            st.write("▼ AIアナリストからの調整・分析レポート")
                            st.write(res.text)
                            
                            now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
                            df_history = load_sheet("決断記録簿")
                            save_text = f"【指示】: {user_instruction}\n【厳選の{buy_count}口】\n" + ai_prompt + "\n\n【AIの解説】\n" + res.text
                            new_history = pd.DataFrame({"日時": [now_str], "対象回号": [f"第{t_round_decide}回"], "決断内容": [save_text]})
                            df_history = pd.concat([new_history, df_history], ignore_index=True) if not df_history.empty else new_history
                            save_sheet("決断記録簿", df_history)
                            st.success("決断内容は『決断記録簿』に保管されました。明日の吉報を祈りましょう！")
                        except Exception as e: st.error(f"エラー: {e}")

elif st.session_state.menu == "結果発表と振り返り":
    st.title("結果発表と振り返り（チャット反省会）")
    tab1, tab2, tab3 = st.tabs(["予測の答え合わせ（明確な等級判定）", "💬 AIとの結果・反省チャット相談", "過去の決断記録簿"])
    
    df_real = load_sheet("実データ")
    auto_round, _ = get_next_round_info(df_real)
    t_round_rev = st.text_input("確認する回号を指定", value=str(auto_round - 1))
    df_note = load_sheet("予測ノート")
    df_target = df_note[df_note["対象回号"] == f"第{t_round_rev}回"] if not df_note.empty else pd.DataFrame()

    with tab1:
        if df_target.empty: st.info("予測データがありません。")
        else:
            st.write("※ 最新データ取得時に自動で採点された結果です。（本数字の的中数から、何等相当か一目で分かるように表示しています）")
            display_cols = ["AIの助言", "実行者", "口数", "数字1", "数字2", "数字3", "数字4", "数字5", "数字6", "数字7", "徳積み", "祈り/夢", "予測ロジック"]
            st.dataframe(df_target[[c for c in display_cols if c in df_target.columns]], height=400)
            
            st.markdown("#### 📝 本家Geminiへの報告用（結果共有テキスト）")
            actual_match = df_real[df_real["回号"] == f"第{t_round_rev}回"]
            actual_nums_str = "未抽選"
            if not actual_match.empty:
                actual_nums_str = ",".join([str(actual_match.iloc[0][f"数字{i}"]) for i in range(1, 8)])
                
            report_text = f"【第{t_round_rev}回 ロト7 結果共有・反省会】\n◆今回の本抽選番号: [{actual_nums_str}]\n\n◆我が家の購入・予測陣形の実績:\n"
            for _, r in df_target.iterrows():
                report_text += f"- {r['口数']} ({r['実行者']}): {r['数字1']},{r['数字2']},{r['数字3']},{r['数字4']},{r['数字5']},{r['数字6']},{r['数字7']} → {r['AIの助言']}\n"
            
            st.text_area("以下の内容をコピーしてチャットへ貼り付けてください", value=report_text, height=250)

    with tab2:
        st.markdown("#### 💬 AIと今回の結果について作戦会議・相談をする")
        user_rev_input = st.text_area("AIへの質問・相談内容を入力してください", value="", height=100)
        if st.button("AIアナリストの徹底反省会をスタートする"):
            if not api_key: st.error("APIキーが設定されていません。")
            elif df_target.empty: st.warning("対象回号のデータがありません。")
            else:
                with st.spinner("AIが今回の当落原因とデータの癖を徹底分析中..."):
                    target_txt = "\n".join([f"{r['口数']}({r['実行者']}): {r['数字1']},{r['数字2']},{r['数字3']},{r['数字4']},{r['数字5']},{r['数字6']},{r['数字7']} -> 結果:{r['AIの助言']}" for _, r in df_target.iterrows()])
                    actual_match = df_real[df_real["回号"] == f"第{t_round_rev}回"]
                    actual_info = actual_match.to_csv(index=False) if not actual_match.empty else "本抽選データがまだ取得されていません。"
                    
                    prompt = f"""
                    第{t_round_rev}回の抽選結果が出ました。データアナリストとして、ユーザーからの相談・質問に対して徹底的な多角的反省・アドバイスを行ってください。
                    【本抽選の正解データ】:\n{actual_info}\n【我が家の予測ノートと自動採点結果】:\n{target_txt}\n【ユーザーからの相談】: "{user_rev_input}"
                    
                    【ルール】
                    1. どの口が一番真実に近かったか、ニアピンや的中の傾向から「今週の波の癖」をロジカルに洗い出すこと。
                    2. 次回のキャリーオーバーを仕留めるための具体的な改善策を施工計画書のように極めて分かりやすく提示すること。
                    3. 絵文字、大げさなスピリチュアルポエムは絶対に使用しないこと。
                    """
                    try:
                        model = genai.GenerativeModel(get_ai_model_name(), system_instruction=MIYAHIRA_PROMPT)
                        res = model.generate_content(prompt)
                        st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
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
# 6. 完全独立機能：万能AI占い師の館（スマホ完全対応版）
# ==========================================
elif st.session_state.menu == "万能AI占い師の館":
    st.title("🔮 万能AI占い師の館（スマホ完全対応版）")
    st.markdown("<div class='info-box'>ここはロト予測システムから完全に切り離された、純粋な占いの空間です。<br><b>手相や人相の画像鑑定機能が、スマホのカメラから直接送れるように完全修正されました！</b></div>", unsafe_allow_html=True)

    if not api_key:
        st.error("占い機能を利用するにはAPIキーの設定が必要です。")
    else:
        if "fortune_chat_session" not in st.session_state:
            try:
                model = genai.GenerativeModel(get_ai_model_name(), system_instruction=FORTUNE_CHAT_PROMPT)
                st.session_state.fortune_chat_session = model.start_chat(history=[])
                st.session_state.fortune_chat_messages = [
                    {"role": "assistant", "content": "ようこそ、神秘の部屋へ。✨\n私は世界中のあらゆる占術をマスターし、「視覚」も持った万能占い師です。\n\n今日は何の占いをしますか？下のメニューから選ぶか、直接話しかけてくださいね💖"}
                ]
            except Exception as e:
                st.error(f"占い師の召喚に失敗しました: {e}")

        c1, c2 = st.columns([3, 1])
        div_list = [
            "西洋占星術（ホロスコープ）", "四柱推命", "九星気学", "宿曜占星術", "紫微斗数", "数秘術", "マヤ暦占い",
            "タロット占い", "易占い", "ルーン占い", "オラクルカード", "ダイス占い", "コーヒー占い（要写真）", "ダウジング",
            "手相（要写真）", "人相（観相学・要写真）", "風水", "姓名判断", "オーラ鑑定（要写真）"
        ]
        selected_div = c1.selectbox("🔮 占術を選ぶ", ["占いを選択してください..."] + div_list)
        if c2.button("この占いを始める", use_container_width=True):
            if selected_div != "占いを選択してください...":
                user_msg = f"「{selected_div}」をお願いします。"
                st.session_state.fortune_chat_messages.append({"role": "user", "content": user_msg})
                with st.spinner("星の声を聴いています..."):
                    try:
                        response = st.session_state.fortune_chat_session.send_message(user_msg, safety_settings=SAFETY_SETTINGS)
                        st.session_state.fortune_chat_messages.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error("エラーが発生しました。")
                st.rerun()

        # 📱 画像アップローダー（スマホのネイティブカメラ起動に完全対応）
        st.markdown("<div class='radio-box'><h4>📸 写真で鑑定する（スマホ完全対応）</h4>"
                    "<p style='color: #6C757D; font-size: 14px;'>※スマホの方は、下の<b>「画像ファイルを選択」</b>をタップすると、その場でカメラが起動して手相やコーヒーカップを撮影できます！</p>", unsafe_allow_html=True)
        
        # エラーが起きやすい st.camera_input を全廃し、ファイルアップローダーに統一
        img_source = st.file_uploader("📂 画像ファイルを選択 または 📸 カメラで撮影", type=["jpg", "jpeg", "png"])
            
        if img_source:
            if st.button("🔮 この写真を占い師に見せて鑑定を依頼する", type="primary", use_container_width=True):
                try:
                    img = Image.open(img_source)
                    # スマホのメモリ不足・通信エラー回避のため、画質を維持しつつリサイズ
                    img.thumbnail((1024, 1024))
                    user_msg = "写真を送りました。この画像を鑑定してください。"
                    
                    st.session_state.fortune_chat_messages.append({"role": "user", "content": "📸 （写真を送信しました）\n" + user_msg})
                    
                    with st.spinner("AI占い師が写真をじっくりと鑑定しています..."):
                        response = st.session_state.fortune_chat_session.send_message([user_msg, img], safety_settings=SAFETY_SETTINGS)
                        st.session_state.fortune_chat_messages.append({"role": "assistant", "content": response.text})
                    st.rerun()
                except Exception as e:
                    st.error(f"写真の送信に失敗しました: {e}")
                    
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")

        for msg in st.session_state.fortune_chat_messages:
            avatar_icon = "🔮" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar_icon):
                st.markdown(msg["content"])

        user_input = st.chat_input("占い師に話しかける...（例：私の名前は山田太郎です）")

        if user_input:
            st.session_state.fortune_chat_messages.append({"role": "user", "content": user_input})
            with st.chat_message("user", avatar="👤"):
                st.markdown(user_input)
                
            with st.chat_message("assistant", avatar="🔮"):
                with st.spinner("星の導きを読み解いています..."):
                    try:
                        response = st.session_state.fortune_chat_session.send_message(user_input, safety_settings=SAFETY_SETTINGS)
                        st.markdown(response.text)
                        st.session_state.fortune_chat_messages.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error("星の声を読み取れませんでした。もう一度話しかけてみてください。")
                        
        if st.button("🔄 占い師との会話を最初からやり直す（リセット）", use_container_width=True):
            try:
                model = genai.GenerativeModel(get_ai_model_name(), system_instruction=FORTUNE_CHAT_PROMPT)
                st.session_state.fortune_chat_session = model.start_chat(history=[])
                st.session_state.fortune_chat_messages = [
                    {"role": "assistant", "content": "ようこそ、神秘の部屋へ。✨\n私は世界中のあらゆる占術をマスターし、「視覚」も持った万能占い師です。\n\n今日は何の占いをしますか？下のメニューから選ぶか、直接話しかけてくださいね💖"}
                ]
            except Exception as e:
                st.error(f"モデルの初期化に失敗しました: {e}")
            st.rerun()