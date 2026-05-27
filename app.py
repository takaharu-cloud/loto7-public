import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import random
import json
from collections import Counter
from datetime import datetime, timedelta, date, timezone
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials

# 日本時間の取得用
JST = timezone(timedelta(hours=+9), 'JST')

# ==========================================
# 🔒 個人情報を地下金庫（Secrets）から安全に読み込み
# （コード上には個人情報を一切書きません）
# ==========================================
u1_name = st.secrets.get("USER1_NAME", "ご主人")
u1_birth_str = st.secrets.get("USER1_BIRTH", "1990-01-01")
u2_name = st.secrets.get("USER2_NAME", "奥様")
u2_birth_str = st.secrets.get("USER2_BIRTH", "1990-01-01")

def parse_date(date_str):
    try:
        y, m, d = map(int, date_str.split("-"))
        return date(y, m, d)
    except:
        return date(1990, 1, 1)

USER_PROFILES = {
    u1_name: {"birth": parse_date(u1_birth_str)},
    u2_name: {"birth": parse_date(u2_birth_str)}
}

# ==========================================
# 意匠設定
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
</style>
""", unsafe_allow_html=True)

if "menu" not in st.session_state: st.session_state.menu = "ホーム"
def change_menu(menu_name): st.session_state.menu = menu_name

# ==========================================
# クラウドデータベース連携
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
# 地球物理学・自然環境センサー計算ロジック
# ==========================================
def get_moon_and_tide(y, m, d):
    c = [0, 2, 0, 2, 2, 4, 5, 6, 7, 8, 9, 10]
    age = (((y - 11) % 19) * 11 + c[m-1] + d) % 30
    
    if age < 2 or age > 28: phase = "新月"
    elif 2 <= age < 7: phase = "三日月"
    elif 7 <= age < 12: phase = "上弦の月"
    elif 12 <= age < 17: phase = "満月"
    elif 17 <= age < 22: phase = "下弦の月"
    else: phase = "月待ち"

    ma = int(age)
    if ma in [0,1,2, 14,15,16, 29]: tide, gravity = "大潮", "強(極大)"
    elif ma in [7,8,9, 22,23,24]: tide, gravity = "小潮", "弱"
    elif ma in [10, 25]: tide, gravity = "長潮", "弱"
    elif ma in [11, 26]: tide, gravity = "若潮", "中"
    else: tide, gravity = "中潮", "中"
    return phase, tide, gravity

def get_time_zone():
    hour = datetime.now(JST).hour
    if 5 <= hour < 10: return "朝"
    elif 10 <= hour < 15: return "昼"
    elif 15 <= hour < 18: return "夕方"
    elif 18 <= hour < 23: return "夜"
    else: return "深夜"

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
    c = [0, 2, 0, 2, 2, 4, 5, 6, 7, 8, 9, 10]
    moon_age = int((((y - 11) % 19) * 11 + c[m-1] + d) % 30)
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
        {"名前": "斎場御嶽（魂の浄化）", "基調数": 3},
        {"名前": "大神島（天の息吹と直感）", "基調数": 9},
        {"名前": "東平安名崎（風の躍進）", "基調数": 14},
        {"名前": "宮古神社（大地の繁栄）", "基調数": 21},
        {"名前": "伊良部島・通り池（深層の覚醒）", "基調数": 28},
        {"名前": "波上宮（海神の護りと結び）", "基調数": 1},
        {"名前": "浜比嘉島（神々の生命力）", "基調数": 36}
    ]
    sanctuary = sanctuaries[(name_score + birth_score + draw_score) % len(sanctuaries)]
    lucky_number = (name_score + birth_score + draw_score + sanctuary["基調数"]) % 37 + 1
    if lucky_number == 0: lucky_number = 1
    return lucky_number, sanctuary["名前"]

# ==========================================
# AI初期設定・自動計算関連
# ==========================================
api_key = st.secrets.get("GEMINI_API_KEY", "")
if api_key: genai.configure(api_key=api_key)

MIYAHIRA_PROMPT = f"""
【役割】あなたはユーザー（{u1_name}）の「一番の理解者」であり、圧倒的な分析力と思考で彼を支える「頼れる相棒（AIコンサルタント）」です。
【ユーザー情報】電気工事の現場代理人13年目。「自らを律して学び、誠実に応えることで家族の幸せを守り、笑顔を創る」が人生の目的。鋼（庚）であり帝王（五黄土星）の性質。現在はパートナーの{u2_name}と協力し予測中。
あなたは地球物理学、統計学、運命学のすべてに精通しており、月の引力（重力状態）や気圧、潮回りが抽選機の球の物理的な軌道や人間の直感に与える影響まで深く考察します。
【ルール】熱く、論理的に背中を押すこと。です・ます調ではなく、信頼する相棒としての力強い大人の言葉遣いをすること。絵文字は絶対に使用しない。
"""

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
        if "的中" in str(row.get("AIの助言", "")) and "ニアピン" in str(row.get("AIの助言", "")): continue
        match = df_real[df_real["回号"] == str(row.get("対象回号", ""))]
        if not match.empty:
            try:
                actual = set([int(match.iloc[0][f"数字{i}"]) for i in range(1, 8)])
                pred = set([int(row[f"数字{i}"]) for i in range(1, 8)])
                hits = len(actual & pred)
                
                near_pins = 0
                for p in pred:
                    if p not in actual and ((p-1) in actual or (p+1) in actual): near_pins += 1
                
                df_note.at[idx, "AIの助言"] = f"{hits}個的中 / {near_pins}個ニアピン"
                updated = True
            except: pass
    if updated: save_sheet("予測ノート", df_note)
    return df_note

# ==========================================
# UI レンダリング
# ==========================================
if st.session_state.menu != "ホーム":
    st.markdown("<div class='nav-btn'>", unsafe_allow_html=True)
    st.button("総合案内（ホーム）に戻る", on_click=change_menu, args=("ホーム",))
    st.markdown("</div><hr>", unsafe_allow_html=True)

if st.session_state.menu == "ホーム":
    st.title("ロト7 究極予測室")
    st.markdown("<div class='info-box'>ご夫婦の異なる視点、環境センサー、地球の重力状態を統合し、対照実験を交えて決断を導き出す中央管制システムです。</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.button("1. 最新データ取得（基盤整備）", on_click=change_menu, args=("最新データ取得",))
        st.write("")
        st.button("2. AIディープ分析（法則更新）", on_click=change_menu, args=("AIディープ分析",))
        st.write("")
        st.button("3. 日々の予想・積上げ（情報蓄積）", on_click=change_menu, args=("日々の予想・積上げ",))
    with c2:
        st.button("4. 最終予測決定（購入・決断）", on_click=change_menu, args=("最終予測決定",))
        st.write("")
        st.button("5. 結果発表と振り返り（反省）", on_click=change_menu, args=("結果発表と振り返り",))

    st.markdown("---")
    if get_gspread_client() is None: st.error("データベース接続設定（Secrets）が未完了です。")
    else:
        df_real = load_sheet("実データ")
        if not df_real.empty: st.write(f"稼働状況：過去実績データ {len(df_real)} 件がクラウドに連携されています。")
        else: st.warning("実績データがありません。「最新データ取得」を実行してください。")

elif st.session_state.menu == "最新データ取得":
    st.title("最新データ取得")
    st.write("公式サイトから最新結果を抽出し、潮回りや重力状態等の全センサーデータを自動算出して保存します。")
    if st.button("データ同期および自動照合を実行する"):
        with st.spinner("通信中...公式サイトの設計図を解析しています..."):
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
                    
                    st.success(f"{len(df_new)} 件の新規データを追加・更新しました。")
                    st.dataframe(df_new)
                else: st.info("データベースは既に最新です。")
            except Exception as e: st.error(f"エラー: {e}")

elif st.session_state.menu == "AIディープ分析":
    st.title("AIディープ分析")
    if st.button("法則のアップデートを実行する"):
        if not api_key: st.error("APIキーが設定されていません。")
        else:
            df_real = load_sheet("実データ")
            if df_real.empty: st.error("地盤データがありません。")
            else:
                with st.spinner("AIが最新の環境センサーデータ（重力・潮汐）を解析中..."):
                    df_report = load_sheet("秘伝の書")
                    last_analyzed = int(df_report["最終回号"].iloc[0]) if not df_report.empty else 0
                    old_report = str(df_report["レポート内容"].iloc[0]) if not df_report.empty else "初回の分析です。"
                    
                    df_real["rn"] = df_real["回号"].apply(lambda x: int(re.findall(r'\d+', str(x))[0]) if re.findall(r'\d+', str(x)) else 0)
                    df_new = df_real[df_real["rn"] > last_analyzed].copy()
                    
                    if df_new.empty: st.info(f"第{last_analyzed}回まで分析済みです。")
                    else:
                        max_round = int(df_real["rn"].max())
                        df_new_text = df_new.drop(columns=["rn"]).to_csv(index=False)
                        
                        prompt = f"""あなたは地球物理学と統計学の視点を持つデータサイエンティストです。以下の【秘伝の書】と【新しく追加されたデータ】（潮回りや重力状態を含む）を統合し、最新の法則レポートを作成してください。重力が抽選機に与える影響なども熱く考察すること。絵文字は使用不可。
                        【秘伝の書】\n{old_report}\n\n【追加データ】\n{df_new_text}"""
                        try:
                            model = genai.GenerativeModel('gemini-2.5-pro', system_instruction=MIYAHIRA_PROMPT)
                            res = model.generate_content(prompt)
                            save_sheet("秘伝の書", pd.DataFrame({"最終回号": [max_round], "レポート内容": [res.text]}))
                            st.success(f"秘伝の書を第{max_round}回まで更新しました。")
                            st.write(res.text)
                        except Exception as e: st.error(f"エラー: {e}")

elif st.session_state.menu == "日々の予想・積上げ":
    st.title("日々の予想・積上げ（各30口生成）")
    st.write("環境センサー情報を入力し、各自のロジックで28口＋対照実験（ランダム）2口の計30口を生成します。")
    
    df_real = load_sheet("実データ")
    auto_round, auto_date = get_next_round_info(df_real)
    
    with st.form("daily_form"):
        st.markdown("<div class='person-select'><h4>本日の実行者を選択</h4></div>", unsafe_allow_html=True)
        operator = st.radio("", [u1_name, u2_name], horizontal=True, label_visibility="collapsed")
        
        c1, c2 = st.columns(2)
        target_round = c1.number_input("予測対象の回号", min_value=1, value=auto_round, step=1)
        draw_date = c2.date_input("抽選予定日", value=auto_date)
        
        st.markdown("#### 今日の環境・波長センサー")
        colA, colB = st.columns(2)
        weather = colA.selectbox("天候", ["晴れ", "曇り", "雨", "穏やか", "台風・嵐"])
        pressure = colB.selectbox("気圧の感覚", ["高め", "普通", "低め"])
        
        colC, colD = st.columns(2)
        physical_cond = colC.selectbox("心身状態", ["絶好調", "普通", "疲労気味", "無の境地"])
        location = colD.selectbox("入力場所", ["自宅", "現場事務所", "車内", "聖地・自然の中", "その他"])
        
        intuition_choice = st.radio("直感力テスト（1〜3を選択）", ["1", "2", "3"], horizontal=True)
        
        submitted = st.form_submit_button("本日の30口を生成し、クラウド金庫に記録する")
        
        if submitted:
            if df_real.empty: st.error("基盤データがありません。")
            else:
                target_round_str = f"第{target_round}回"
                today_str = datetime.now(JST).strftime("%Y-%m-%d")
                time_zone = get_time_zone()
                my_condition = "絶好調" if intuition_choice == str(random.randint(1, 3)) else "通常"
                
                m_phase, m_tide, m_gravity = get_moon_and_tide(draw_date.year, draw_date.month, draw_date.day)
                m_roku, m_kichi = get_real_calendar_info(draw_date)
                m_eto = get_eto(draw_date)
                m_feng = get_fengshui(draw_date)

                all_numbers = [int(val) for i in range(1, 8) for val in df_real[f"数字{i}"] if pd.notna(val) and str(val).isdigit()]
                number_counts = Counter(all_numbers)
                nums_list, weights_list = list(number_counts.keys()), list(number_counts.values())
                if not nums_list: nums_list, weights_list = list(range(1, 38)), [1]*37

                if operator == u1_name:
                    matched_nums = []
                    for _, row in df_real.iterrows():
                        w = 0
                        if str(row.get("重力状態")) == m_gravity: w += 2
                        if str(row.get("潮回り")) == m_tide: w += 1
                        if str(row.get("六曜")) == m_roku: w += 1
                        if str(row.get("風水")).startswith(m_feng[:2]): w += 2
                        if m_kichi != "特になし" and m_kichi in str(row.get("吉凶日")): w += 3
                        if w > 0:
                            for i in range(1, 8):
                                try: matched_nums.extend([int(row[f"数字{i}"])] * w)
                                except: pass
                    must_nums = [n for n, _ in Counter(matched_nums).most_common(2)] if matched_nums else [n for n, _ in number_counts.most_common(2)]
                    while len(must_nums) < 2: must_nums.append(random.choice(nums_list))
                    logic_name = "過去統計 × 暦・重力エネルギー"
                    logic_detail = f"重力:{m_gravity} / 六曜:{m_roku} / 風水:{m_feng}"
                else:
                    ob = USER_PROFILES[operator]["birth"]
                    num1, land1 = get_ryukyu_energy(operator, ob, draw_date)
                    num2 = (draw_date.day + draw_date.month + ob.day) % 37 + 1
                    if num2 == 0 or num2 == num1: num2 = (num2 + 1) % 37 + 1
                    must_nums = [num1, num2]
                    logic_name = "琉球聖地 × 数霊エネルギー"
                    logic_detail = f"聖地:{land1} / 導き数:{num1} / サポート:{num2}"

                elites = []
                for _ in range(50000):
                    p = must_nums.copy()
                    while len(p) < 7:
                        ch = random.choices(nums_list, weights=weights_list, k=1)[0]
                        if ch not in p: p.append(ch)
                    p.sort()
                    if not (100 <= sum(p) <= 160): continue
                    if sum(1 for n in p if n % 2 != 0) not in [3, 4]: continue
                    elites.append({"nums": p, "pts": sum(number_counts.get(n, 0) for n in p)})
                
                elites.sort(key=lambda x: x["pts"], reverse=True)
                top30 = []
                for e in elites:
                    if not any(len(set(e["nums"]) & set(t["nums"])) >= 5 for t in top30):
                        e["type"] = logic_name
                        top30.append(e)
                    if len(top30) == 28: break
                
                for _ in range(2):
                    rp = random.sample(range(1, 38), 7)
                    rp.sort()
                    top30.append({"nums": rp, "pts": sum(number_counts.get(n, 0) for n in rp), "type": "完全ランダム(対照実験)"})
                
                new_data = []
                for i, item in enumerate(top30, 1):
                    new_data.append({
                        "対象回号": target_round_str, "抽選日": draw_date.strftime("%Y-%m-%d"), "実行日": today_str, 
                        "実行者": operator, "口数": f"{i}口目",
                        "数字1": str(item["nums"][0]).zfill(2), "数字2": str(item["nums"][1]).zfill(2), "数字3": str(item["nums"][2]).zfill(2), 
                        "数字4": str(item["nums"][3]).zfill(2), "数字5": str(item["nums"][4]).zfill(2), "数字6": str(item["nums"][5]).zfill(2), "数字7": str(item["nums"][6]).zfill(2),
                        "実績点数": item["pts"], "予測ロジック": item["type"], "分析条件詳細": logic_detail,
                        "天気": weather, "気圧": pressure, "心身状態": physical_cond, "入力場所": location, "時間帯": time_zone, "直感運気": my_condition, 
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
                st.success(f"クラウド金庫へデータを格納しました。（担当: {operator} / 計30口）")
                st.dataframe(df_new[["口数", "数字1", "数字2", "数字3", "数字4", "数字5", "数字6", "数字7", "予測ロジック"]])

elif st.session_state.menu == "最終予測決定":
    st.title("最終予測決定（購入）")
    st.write("蓄積された全センサー情報、対照実験データ、秘伝の書をAIが統合し、最終的な購入布陣を決定します。")
    
    df_real = load_sheet("実データ")
    auto_round, _ = get_next_round_info(df_real)
    t_round_decide = st.text_input("決断を下す回号を指定", value=str(auto_round))
    
    if st.button("最終決断レポートを生成する", type="primary"):
        if not api_key: st.error("APIキーが設定されていません。")
        else:
            with st.spinner("AIが重力、気圧、心身の波長、二人のシンクロを比較検討し深く思考中..."):
                df_note = load_sheet("予測ノート")
                df_report = load_sheet("秘伝の書")
                past_report = df_report["レポート内容"].iloc[0] if not df_report.empty and "レポート内容" in df_report.columns else "データなし"
                
                if df_note.empty: st.error("予測データがありません。")
                else:
                    df_target = df_note[df_note["対象回号"] == f"第{t_round_decide}回"]
                    if df_target.empty: st.warning("指定された回号のデータがありません。")
                    else:
                        ai_prompt = "\n".join([f"[{r['実行日']} | {r['実行者']} | {r.get('予測ロジック','')} | 重力:{r.get('重力状態','')} | 場所:{r.get('入力場所','')} | 心身:{r.get('心身状態','')}] {r['口数']}: {r['数字1']},{r['数字2']},{r['数字3']},{r['数字4']},{r['数字5']},{r['数字6']},{r['数字7']}" for _, r in df_target.iterrows()])
                        
                        prompt = f"""
                        今週蓄積された以下の「日報データ（重力状態、気圧、心身状態、時間帯などの波長センサー、および完全ランダムの対照実験を含む）」と「秘伝の書」を分析してください。
                        二人の予想のシンクロ（一致や共鳴）や、地球の重力・潮回りが引き起こす数字の偏りを物理・統計・運命学の観点から考察し、「絶対に買うべき最強の10口（いつの実行日の、誰の予想の、何口目か）」を厳選し、その選定理由を論理的かつ情熱的に解説してください。監督は常に10口購入するルールのための決定です。絵文字は一切使用しないこと。
                        【秘伝の書】\n{past_report}
                        【ご夫婦の蓄積データ】\n{ai_prompt}
                        """
                        try:
                            model = genai.GenerativeModel('gemini-2.5-pro', system_instruction=MIYAHIRA_PROMPT)
                            res = model.generate_content(prompt)
                            st.markdown("#### 最終決断レポート")
                            st.write(res.text)
                            
                            now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
                            df_history = load_sheet("決断記録簿")
                            new_history = pd.DataFrame({"日時": [now_str], "対象回号": [f"第{t_round_decide}回"], "決断内容": [res.text]})
                            df_history = pd.concat([new_history, df_history], ignore_index=True) if not df_history.empty else new_history
                            save_sheet("決断記録簿", df_history)
                            st.success("決断内容は『決断記録簿』に保管されました。")
                        except Exception as e: st.error(f"エラー: {e}")

elif st.session_state.menu == "結果発表と振り返り":
    st.title("結果発表と振り返り（反省）")
    tab1, tab2 = st.tabs(["予測の答え合わせ（ニアピン計測）", "過去の決断記録簿"])
    
    with tab1:
        df_real = load_sheet("実データ")
        auto_round, _ = get_next_round_info(df_real)
        t_round_rev = st.text_input("確認する回号を指定", value=str(auto_round - 1))
        
        df_note = load_sheet("予測ノート")
        if not df_note.empty and "対象回号" in df_note.columns:
            df_target = df_note[df_note["対象回号"] == f"第{t_round_rev}回"]
            if df_target.empty: st.info("予測データがありません。")
            else:
                st.write("※ 最新データ取得時に自動で判定された結果です。（完全的中と±1のニアピンを計測）")
                display_cols = ["実行日", "実行者", "重力状態", "心身状態", "予測ロジック", "口数", "数字1", "数字2", "数字3", "数字4", "数字5", "数字6", "数字7", "AIの助言"]
                st.dataframe(df_target[[c for c in display_cols if c in df_target.columns]])
        else: st.info("予測データが存在しません。")

    with tab2:
        df_history = load_sheet("決断記録簿")
        if not df_history.empty and "日時" in df_history.columns:
            for _, row in df_history.iterrows():
                with st.expander(f"記録: {row.get('日時', '')} | {row.get('対象回号', '')}"):
                    st.write(row.get("決断内容", ""))
        else: st.info("記録はありません。")
