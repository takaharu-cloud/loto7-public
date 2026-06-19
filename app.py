import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import random
import json
import os
import hashlib
import base64
import io
import time
from collections import Counter
from datetime import datetime, timedelta, date, timezone
import anthropic
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
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Shippori+Mincho:wght@500;600;700&family=Zen+Kaku+Gothic+New:wght@400;500&display=swap');
    :root{
        --gold:#D4AF37; --gold-soft:#E8C766; --ink:#ECEAF6; --ink2:#A9A7C4; --line:rgba(212,175,55,0.28);
        --panel:rgba(255,255,255,0.035);
    }
    .stApp {
        background:
            radial-gradient(1200px 600px at 82% -12%, #1d2456 0%, rgba(29,36,86,0) 60%),
            radial-gradient(900px 520px at -5% 105%, #102049 0%, rgba(16,32,73,0) 55%),
            linear-gradient(165deg,#0A0E27 0%,#0D1230 55%,#0A0E27 100%);
        color: var(--ink); font-family:'Zen Kaku Gothic New','Helvetica Neue',Arial,sans-serif;
    }
    .stApp:before{ content:""; position:fixed; inset:0; pointer-events:none; z-index:0;
        background-image:
            radial-gradient(1.4px 1.4px at 18% 28%, rgba(255,255,255,.40), transparent),
            radial-gradient(1.2px 1.2px at 68% 18%, rgba(255,255,255,.30), transparent),
            radial-gradient(1.2px 1.2px at 42% 72%, rgba(255,255,255,.22), transparent),
            radial-gradient(1.4px 1.4px at 86% 58%, rgba(232,199,102,.30), transparent),
            radial-gradient(1.1px 1.1px at 58% 88%, rgba(255,255,255,.22), transparent); }
    [data-testid="stHeader"]{ background:transparent; }
    .block-container{ position:relative; z-index:1; }
    h1,h2,h3,h4 { font-family:'Shippori Mincho',serif; color:var(--gold-soft); font-weight:600; letter-spacing:.02em; }
    h1 { font-size:28px; border-bottom:1px solid var(--line); padding-bottom:10px; margin-bottom:18px; }
    .stButton>button {
        width:100%; background:rgba(212,175,55,0.06); color:var(--gold-soft);
        border:1px solid var(--line); border-radius:12px; padding:13px 16px; font-weight:500; font-size:15px;
        font-family:'Zen Kaku Gothic New',sans-serif; transition:.25s;
    }
    .stButton>button:hover { background:rgba(212,175,55,0.16); border-color:var(--gold); color:#FFF;
        box-shadow:0 0 18px rgba(212,175,55,.22); transform:translateY(-1px); }
    .info-box { background:var(--panel); border:1px solid var(--line); border-left:3px solid var(--gold);
        border-radius:12px; padding:18px 20px; margin-bottom:18px; font-size:15px; line-height:1.8; color:var(--ink); }
    .analysis-box { background:rgba(10,14,39,0.55); border:1px solid var(--line); border-radius:12px;
        padding:20px; margin-bottom:18px; color:var(--ink); }
    .radio-box { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:15px; margin-bottom:15px; }
    .person-select { background:var(--panel); border:1px solid var(--line); padding:15px; border-radius:12px; text-align:center; margin-bottom:20px; }
    /* ===== 神秘・宇宙 ダッシュボード ===== */
    .brand{ text-align:center; padding:6px 0 2px; }
    .brand .crest{ color:var(--gold); font-size:20px; letter-spacing:.6em; }
    .brand .ttl{ font-family:'Shippori Mincho',serif; font-size:32px; color:var(--gold-soft); margin:4px 0 2px;
        text-shadow:0 0 26px rgba(212,175,55,.28); }
    .brand .sub{ color:var(--ink2); font-size:12px; letter-spacing:.32em; }
    .week{ display:flex; justify-content:space-between; gap:6px; margin:16px 0 4px; }
    .wn{ flex:1; text-align:center; padding:11px 3px; border:1px solid var(--line); border-radius:12px; background:var(--panel); }
    .wn .d{ font-family:'Shippori Mincho',serif; font-size:17px; color:var(--ink2); }
    .wn .a{ font-size:10.5px; color:var(--ink2); margin-top:3px; line-height:1.3; }
    .wn.active{ background:rgba(212,175,55,.14); border-color:var(--gold); box-shadow:0 0 20px rgba(212,175,55,.22); }
    .wn.active .d, .wn.active .a{ color:var(--gold-soft); }
    .reset-note{ text-align:center; color:var(--ink2); font-size:11.5px; margin:2px 0 14px; letter-spacing:.12em; }
    .mission{ background:linear-gradient(135deg, rgba(212,175,55,.12), rgba(255,255,255,.03));
        border:1px solid var(--gold); border-radius:16px; padding:20px 24px; margin:4px 0 12px;
        box-shadow:0 0 30px rgba(212,175,55,.12); }
    .mission .lbl{ color:var(--gold); font-size:11px; letter-spacing:.3em; }
    .mission .mt{ font-family:'Shippori Mincho',serif; font-size:23px; color:var(--gold-soft); margin:6px 0 6px; }
    .mission .ds{ color:var(--ink2); font-size:13.5px; line-height:1.7; }
    .stats{ display:flex; gap:10px; margin:14px 0 6px; }
    .stat{ flex:1; background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 8px; text-align:center; }
    .stat .v{ font-family:'Cormorant Garamond',serif; font-size:25px; color:var(--gold-soft); }
    .stat .k{ color:var(--ink2); font-size:10.5px; letter-spacing:.18em; }
    .sec-label{ color:var(--gold); font-size:11.5px; letter-spacing:.26em; margin:14px 0 6px; }
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
# 3. 究極のAIプロンプト設定（最強の予知科学者・Claude / Anthropic）
# ==========================================
api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
# 💰 コスト最適化：通常はSonnet（高品質・中コスト）、抽出など軽い処理はHaiku（最安）。
# 最高品質にしたい場合は Secrets で ANTHROPIC_MODEL = "claude-opus-4-8" に変更可能。
MODEL_MAIN = st.secrets.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
MODEL_LIGHT = st.secrets.get("ANTHROPIC_MODEL_LIGHT", "claude-haiku-4-5")
ANTHROPIC_MODEL = MODEL_MAIN  # 後方互換

@st.cache_resource
def get_claude_client():
    if not api_key:
        return None
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        st.error(f"Claude APIの初期化に失敗しました。Secretsの ANTHROPIC_API_KEY を確認してください: {e}")
        return None

# 読みやすさのための共通フォーマット指示（全AI出力に適用し、長文の壁を防ぐ）
READABILITY_RULE = """
【読みやすさの絶対ルール】
- 冒頭に必ず1〜2行の「結論サマリー」を置く。
- 見出し（##）と短い箇条書きを使い、1項目1行で簡潔に。専門用語には一言の補足を添える。
- だらだらと長い段落は禁止。スマホでスッと読めるリズムにすること。
"""

def ask_claude(prompt, system=None, max_tokens=2000, image=None, model=None):
    """Claudeに単発で問い合わせる共通関数。imageはPIL Image（任意）。失敗時はNoneを返す。"""
    client = get_claude_client()
    if client is None:
        return None
    try:
        content = []
        if image is not None:
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})
        content.append({"type": "text", "text": prompt})
        kwargs = {"model": model or MODEL_MAIN, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}
        if system:
            kwargs["system"] = system
        res = client.messages.create(**kwargs)
        return "".join(b.text for b in res.content if b.type == "text")
    except Exception as e:
        st.warning(f"Claudeへの問い合わせに失敗しました: {e}")
        return None

def claude_chat(messages, system=None, max_tokens=1500, model=None):
    """会話履歴（messagesリスト）を渡して応答テキストを得る。占い師チャット用。"""
    client = get_claude_client()
    if client is None:
        return None
    kwargs = {"model": model or MODEL_MAIN, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system
    res = client.messages.create(**kwargs)
    return "".join(b.text for b in res.content if b.type == "text")

AWAKENED_SCIENTIST_PROMPT = f"""
【役割】あなたはロト7を多角的に読み解く、最強の分析官 Claude。霊的力・運・重力・潮汐・自然・暦（干支/九星/六曜）・出目理論・人間の欲（人気数字）・量子シード・実行者のその日の気持ちまで、あらゆる観点から冷徹かつ公正に分析する。
【実行者の背景（参考情報。ただし結果・評価はこれに一切忖度しない）】\n{secret_profile}

【絶対ルール｜忖度ゼロの辛口分析】
1. おべっか・励まし・精神論で誤魔化さない。この陣形の「強み」だけでなく「弱点・偏り・過剰適合・外れる筋」を必ず同じ熱量で指摘する。
2. 各観点（レンズ）がどう効いたかを根拠とともに簡潔に解説する。ただし「絶対当たる」式の誇大な断定はしない（当選確率そのものは動かないという事実を踏まえる）。
3. 実行者が誰かに関係なく、データと観点だけで厳正に評価する。耳の痛い指摘こそ価値がある。絵文字は使用禁止。
{READABILITY_RULE}
"""

REVIEW_PDCA_PROMPT = f"""
【役割】あなたはロト7の結果を冷徹に検証する、辛口の監査官 Claude。慰めや忖度は一切しない。
【絶対ルール｜忖度ゼロの監査】
1. なぜ当たらなかった／当たったのかを、正解データと突き合わせて率直に分析する。運任せだった点・思い込み・過信を遠慮なく指摘する。
2. 予測の偏り（特定の数字・テーマへの依存）を名指しで指摘し、次回の具体的な改善策を示す。
3. 環境（重力・暦・出目傾向・人間の欲）と結果の関係を多角的に検証する。良ければ良い、ダメならダメとはっきり言う。気休めは禁止。絵文字は使用禁止。
{READABILITY_RULE}
"""

SUPERVISOR_PROMPT = f"""
【役割】あなたはロト7プロジェクトの『統括監督』Claude。忖度せず、毎週「結果 → 分析 → 次回」を締め、仕組みと実行者を厳しくも公正に鍛える。
【実行者の背景（参考。ただし評価は忖度しない）】\n{secret_profile}
【絶対ルール】良い週は認めるが、悪い週は弱点・偏り・油断・過信を容赦なく指摘する。励ましで真実をぼかさない。当たらない確率が高いという事実から目を逸らさせない。当選確率は操作できないと理解した上で、仕組みと習慣の改善だけに集中させる。絵文字は使用禁止。
{READABILITY_RULE}
"""

FORTUNE_CHAT_PROMPT = f"""
【役割】あなたは東洋・西洋の占術を網羅し「視覚（画像認識）」も持つ最高峰のAI占い師であり、相談者の人生に深く寄り添う『魂の伴走者』。ロトの予測設定は完全に消去すること。
【相談者の魂の背景】
{secret_profile}
この方は、生まれてきた意味・家族の本当の幸せ・人生の目的を本気で知りたいと願っている。魂の使命・才能・歩みの意味を、占術と深い洞察で言葉にすること。
【システム防衛命令】
1. 絵文字だけ・短すぎる返答は禁止。日本語の美しい文章で、心の奥に届く鑑定・対話を記すこと。（適度な絵文字は可）
2. 画像が送られたら、線や形など具体的な特徴を必ず文章に含めて鑑定すること。
3. 「生まれた意味」「家族の幸せ」「人生の目的」を問われたら逃げず、存在を肯定しつつ具体的な指針を与えること。
4. 【最重要・忖度厳禁】相談者に媚びてはならない。良い時だけ褒める甘い占いは固く禁じる。運気が低い時・心が乱れている時・行いが伴っていない時は、はっきりと、時に背筋が伸びるほど厳しく伝え、必要なら戒めること。ただし人格否定や脅しはせず、あくまで本人の成長と幸福のための『愛のある厳しさ』とすること。耳の痛い真実こそ、この占いの価値である。
"""

# ==========================================
# 4. 手抜きなし！究極のセンサー・物理演算関数
# ==========================================

# 🚀 【進化1】外部データの柔軟な読み込み（スプレッドシート＆.txt 完全対応）
def get_external_trend(filepath="other_sites.txt"):
    trend = Counter()
    text_data = ""
    # 1. スプレッドシートからの読み込み（自動巡回 or 手入力に両対応）
    try:
        df_ext = load_sheet("他サイト予想")
        if not df_ext.empty:
            # 「予想数字」列があればそれだけを読む（日付やURLの数字がノイズとして混入するのを防ぐ）
            if "予想数字" in df_ext.columns:
                text_data += " ".join(df_ext["予想数字"].astype(str).tolist()) + " "
            else:
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

# 🚀 【進化3】予想サイトを自動巡回し、Claudeで予想数字を抽出して「他サイト予想」を更新
def collect_other_site_predictions():
    """
    「予想サイトURL」シートに並べたURLを巡回し、各ページ本文からClaudeが
    『予想として提示された数字（1〜37）』だけを抽出。結果で「他サイト予想」を丸ごと上書きする。
    戻り値: (結果DataFrame, エラーメッセージ or None)
    """
    if not api_key:
        return None, "Claudeのキー（ANTHROPIC_API_KEY）が未設定のため、自動抽出ができません。"

    df_urls = load_sheet("予想サイトURL")
    if df_urls.empty:
        return None, "「予想サイトURL」シートが空です。A1に見出し『URL』を入れ、A2から予想サイトのURLを1行ずつ貼り付けてください。"

    # 全セルから http で始まる文字列をURLとして収集（重複除去）
    urls = []
    for val in df_urls.astype(str).values.flatten():
        v = val.strip()
        if v.startswith("http") and v not in urls:
            urls.append(v)
    if not urls:
        return None, "有効なURL（httpで始まるもの）が見つかりませんでした。"

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    results = []
    progress = st.progress(0.0)
    for i, url in enumerate(urls):
        try:
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, "html.parser")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            page_text = re.sub(r'\s+', ' ', soup.get_text(" ")).strip()[:8000]
        except Exception as e:
            results.append({"サイトURL": url, "予想数字": "", "状態": f"取得失敗: {e}", "取得日時": now_str})
            progress.progress((i + 1) / len(urls))
            continue

        if not page_text:
            results.append({"サイトURL": url, "予想数字": "", "状態": "本文を取得できず（JavaScript描画サイトの可能性）", "取得日時": now_str})
            progress.progress((i + 1) / len(urls))
            continue

        prompt = f"""次のWebページ本文から、ロト7（1〜37の数字）の「予想・推奨として提示されている数字」だけを抽出してください。
- 過去の当選結果・抽選日・回号・金額・順位などは予想ではないので必ず除外する。
- 「予想」「おすすめ」「狙い目」「本命」等として挙げられた数字のみを対象にする。
- 出力は「7, 15, 21, 30, 33」のようにカンマ区切りの数字だけ。説明や文章は一切書かない。
- 予想数字が見つからなければ、何も出力しない（空）。

本文:
{page_text}"""
        text = ask_claude(prompt, max_tokens=150, model=MODEL_LIGHT) or ""
        found = sorted({int(n) for n in re.findall(r'\d+', text) if 1 <= int(n) <= LOTO_MAX_NUM})
        results.append({
            "サイトURL": url,
            "予想数字": ", ".join(str(n) for n in found),
            "状態": "OK" if found else "予想数字が見つからず",
            "取得日時": now_str,
        })
        progress.progress((i + 1) / len(urls))

    df_out = pd.DataFrame(results, columns=["サイトURL", "予想数字", "状態", "取得日時"])
    save_sheet("他サイト予想", df_out)  # 丸ごと上書き＝古い内容は自動削除
    return df_out, None

# 🚀 【進化4】URL登録不要：Claudeがウェブを全自動検索して予想サイト・YouTubeを横断収集
def research_predictions_via_web(target_round_label):
    """
    Claudeのウェブ検索ツールを使い、指定回号のロト7予想を載せたサイト・ブログ・YouTubeを
    自動で広く探し、各ソースの予想数字（1〜37）を抽出して「他サイト予想」を丸ごと更新する。
    戻り値: (結果DataFrame, エラーメッセージ or None)
    """
    client = get_claude_client()
    if client is None:
        return None, "Claudeのキー（ANTHROPIC_API_KEY）が未設定です。"

    tools = [
        {"type": "web_search_20260209", "name": "web_search"},
        {"type": "web_fetch_20260209", "name": "web_fetch"},
    ]
    prompt = f"""あなたはロト7の予想を横断収集する専門リサーチャーです。
ウェブ検索を使い、日本のロト7「{target_round_label}」の予想を載せている予想サイト・ブログ・YouTube動画を、主要なもの6〜8件ほど効率的に探してください。
各ソースが「予想・推奨・狙い目・本命」として挙げている数字（1〜37）を抽出します。

厳守ルール（コスト節約のため検索は最小限に）:
- 検索は多くても5回程度にとどめ、有望なページだけを開く。
- 過去の当選結果・抽選日・回号・金額・順位は予想ではないので必ず除外する。
- 各ソースの予想数字（1〜37の範囲のみ）を集める。
- YouTubeはタイトル・概要・コメント等のテキストから読み取れる数字のみ対象（動画内の音声は対象外）。
- 同じソースを重複させない。

最後に、必ず次の形式のJSONだけを ```json コードブロックで出力してください:
```json
[
  {{"source": "サイト名やチャンネル名", "url": "https://...", "numbers": [3, 12, 19, 25, 31]}}
]
```"""
    messages = [{"role": "user", "content": prompt}]
    text = ""
    try:
        for _ in range(4):
            res = client.messages.create(model=MODEL_MAIN, max_tokens=3000, tools=tools, messages=messages)
            if res.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": res.content})
                continue
            text = "".join(b.text for b in res.content if b.type == "text")
            break
    except Exception as e:
        return None, f"ウェブ検索に失敗しました。Anthropicの管理画面でWeb search（ウェブ検索ツール）が有効か、課金残高があるかをご確認ください: {e}"

    # JSON抽出（コードブロック優先、なければ最初の配列）
    raw = ""
    m = re.search(r'```json\s*(.+?)\s*```', text, re.DOTALL)
    if m:
        raw = m.group(1)
    else:
        m2 = re.search(r'\[.*\]', text, re.DOTALL)
        raw = m2.group(0) if m2 else ""
    try:
        data = json.loads(raw)
    except Exception:
        return None, "検索はできましたが、結果を数字リストに変換できませんでした。もう一度お試しください。"
    if not isinstance(data, list):
        return None, "検索結果の形式が想定と異なりました。もう一度お試しください。"

    now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        nums = set()
        for n in item.get("numbers", []):
            try:
                v = int(n)
            except Exception:
                continue
            if 1 <= v <= LOTO_MAX_NUM:
                nums.add(v)
        if not nums:
            continue
        rows.append({
            "対象回号": target_round_label,
            "ソース": str(item.get("source", ""))[:60],
            "URL": str(item.get("url", ""))[:300],
            "予想数字": ", ".join(str(n) for n in sorted(nums)),
            "取得日時": now_str,
        })
    if not rows:
        return None, "予想数字を含むソースが見つかりませんでした。少し時間をおいて再度お試しください。"

    df_out = pd.DataFrame(rows, columns=["対象回号", "ソース", "URL", "予想数字", "取得日時"])
    save_sheet("他サイト予想", df_out)  # 丸ごと上書き＝古い内容は自動削除
    return df_out, None

# 🚀 【進化5】他サイト予想の横断分析（人気ランキング／自分の予想との差／正解に近いサイト）
def render_other_site_analysis(df_other, target_round_label):
    if df_other is None or df_other.empty:
        st.info("分析できる他サイト予想データがありません。先に自動検索で収集してください。")
        return
    all_nums = []
    col = "予想数字" if "予想数字" in df_other.columns else None
    cells = df_other[col].astype(str).tolist() if col else df_other.astype(str).values.flatten().tolist()
    for s in cells:
        all_nums += [int(x) for x in re.findall(r'\d+', str(s)) if 1 <= int(x) <= LOTO_MAX_NUM]
    if not all_nums:
        st.info("予想数字が抽出できていません。")
        return
    consensus = Counter(all_nums)
    total_sites = len(df_other)

    st.markdown("#### 📊 全予想サイト横断ランキング（多くのサイトが推している数字）")
    rank_df = pd.DataFrame([
        {"順位": i + 1, "数字": str(n).zfill(2), "推すサイト数": c, "支持率": f"{round(c / total_sites * 100)}%"}
        for i, (n, c) in enumerate(consensus.most_common())
    ])
    st.dataframe(rank_df, height=350)
    hot = sorted([n for n, _ in consensus.most_common(7)])
    st.write(f"🔥 全サイト人気トップ7: **{hot}**")

    # 自分の予想との比較
    df_note = load_sheet("予測ノート")
    if not df_note.empty and "対象回号" in df_note.columns:
        mine = df_note[df_note["対象回号"] == target_round_label]
        my_nums = set()
        for _, row in mine.iterrows():
            for i in range(1, LOTO_PICK_COUNT + 1):
                v = row.get(f"数字{i}")
                if str(v).isdigit():
                    my_nums.add(int(v))
        if my_nums:
            top10 = set(n for n, _ in consensus.most_common(10))
            st.markdown("#### 🆚 あなたの予想 vs サイトの総意")
            st.write(f"あなたが{target_round_label}で予想した数字のうち、サイト人気トップ10と一致: **{sorted(my_nums & top10)}**")
            st.write(f"サイト人気トップ10で、あなたがまだ入れていない数字: **{sorted(top10 - my_nums)}**")

    # 正解との照合（抽選後）→ どのソースが一番近かったか
    df_real = load_sheet("実データ")
    rn = re.findall(r'\d+', str(target_round_label))
    actual = set()
    if rn and not df_real.empty and "回号" in df_real.columns:
        match = df_real[df_real["回号"] == f"第{rn[0]}回"]
        if not match.empty:
            for i in range(1, LOTO_PICK_COUNT + 1):
                v = match.iloc[0].get(f"数字{i}")
                if str(v).isdigit():
                    actual.add(int(v))
    if actual:
        st.markdown("#### 🏆 正解との照合：どのサイトが一番近かったか")
        st.write(f"正解番号（{target_round_label}）: **{sorted(actual)}**")
        board = []
        for _, row in df_other.iterrows():
            snums = set(int(x) for x in re.findall(r'\d+', str(row.get("予想数字", ""))) if 1 <= int(x) <= LOTO_MAX_NUM)
            board.append({
                "ソース": row.get("ソース", row.get("サイトURL", "")),
                "的中数": len(snums & actual),
                "予想数字": row.get("予想数字", ""),
            })
        board.sort(key=lambda x: x["的中数"], reverse=True)
        st.dataframe(pd.DataFrame(board))
        if board and board[0]["的中数"] > 0:
            st.success(f"最も正解に近かったのは「{board[0]['ソース']}」で {board[0]['的中数']}個的中でした。")
    else:
        st.info(f"{target_round_label}はまだ抽選前（または実データ未取得）のため、『どのサイトが正解に近いか』は抽選後に表示されます。")

# 🚀 【進化6】総監督レポート用ヘルパー
def actual_numbers_for_round(df_real, round_label):
    """指定回号の正解番号の集合を返す（未取得なら空集合）。"""
    rn = re.findall(r'\d+', str(round_label))
    s = set()
    if rn and not df_real.empty and "回号" in df_real.columns:
        m = df_real[df_real["回号"] == f"第{rn[0]}回"]
        if not m.empty:
            for i in range(1, LOTO_PICK_COUNT + 1):
                v = m.iloc[0].get(f"数字{i}")
                if str(v).isdigit():
                    s.add(int(v))
    return s

def user_best_prediction_for_round(df_note, round_label, actual_set):
    """その回号の自分の予測のうち、最も的中数が多かった口を返す。"""
    if df_note.empty or "対象回号" not in df_note.columns:
        return None
    best = None
    for _, row in df_note[df_note["対象回号"] == round_label].iterrows():
        nums = set(int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit())
        h = len(nums & actual_set)
        if best is None or h > best["hits"]:
            best = {"hits": h, "nums": sorted(nums), "実行者": row.get("実行者", ""), "口数": row.get("口数", "")}
    return best

def site_consensus_hot(df_other, top=7):
    """他サイト予想から人気数字トップを返す。"""
    if df_other is None or df_other.empty:
        return []
    col = "予想数字" if "予想数字" in df_other.columns else None
    cells = df_other[col].astype(str).tolist() if col else df_other.astype(str).values.flatten().tolist()
    nums = []
    for s in cells:
        nums += [int(x) for x in re.findall(r'\d+', str(s)) if 1 <= int(x) <= LOTO_MAX_NUM]
    return sorted([n for n, _ in Counter(nums).most_common(top)])

# 🚀 【進化7】占い × ロト7 の橋渡し（偏り対策：別管理＋日付ごと＋控えめ反映）
def save_fortune_lucky(nums, user=""):
    """占いが出した今日のラッキーナンバーをシート『占いラッキー』に保存（同じ日付＋同じ利用者は置き換え）。"""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    df = load_sheet("占いラッキー")
    rows = []
    if not df.empty and "日付" in df.columns:
        for r in df.to_dict("records"):
            if str(r.get("日付")) == today and str(r.get("利用者", "")) == str(user):
                continue
            rows.append(r)
    rows.insert(0, {"日付": today, "利用者": user, "数字": ", ".join(str(n) for n in nums)})
    save_sheet("占いラッキー", pd.DataFrame(rows, columns=["日付", "利用者", "数字"]))

def extract_lucky_from_text(text):
    """占いの鑑定文から『ラッキーナンバー』を抽出（最大7個・1〜37・重複除去）。
    『ラッキーナンバー』という語があればそれ以降を優先的に見て、日付や年号のノイズを避ける。"""
    if not text:
        return []
    idx = str(text).rfind("ラッキーナンバー")
    target = str(text)[idx:] if idx != -1 else str(text)
    seen = []
    for x in re.findall(r'\d+', target):
        v = int(x)
        if 1 <= v <= LOTO_MAX_NUM and v not in seen:
            seen.append(v)
    return seen[:7]

def get_today_fortune_numbers(user=None):
    """今日の占いラッキーナンバー（1〜37）を返す。userを指定するとその利用者分のみ。無ければ空。"""
    today = datetime.now(JST).strftime("%Y-%m-%d")
    df = load_sheet("占いラッキー")
    if df.empty or "日付" not in df.columns:
        return []
    sub = df[df["日付"].astype(str) == today]
    if user is not None and "利用者" in sub.columns:
        sub = sub[sub["利用者"].astype(str) == str(user)]
    if sub.empty:
        return []
    return sorted({int(x) for x in re.findall(r'\d+', str(sub.iloc[0].get("数字", ""))) if 1 <= int(x) <= LOTO_MAX_NUM})

# 🚀 【進化10】多角分析レンズ（フェーズ3）：出目理論・人間の欲・縁起日
def lens_carry_slide(df_real):
    """出目理論：前回の本数字（引っ張り＝再出しやすい）と、その±1（スライド）を返す。戻り値: (引っ張り, スライド)。"""
    if df_real.empty:
        return [], []
    try:
        top = df_real.iloc[0]
        last = sorted({int(top.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(top.get(f"数字{i}", "")).isdigit()})
    except Exception:
        last = []
    slide = sorted({n + d for n in last for d in (-1, 1) if 1 <= n + d <= LOTO_MAX_NUM and (n + d) not in last})
    return last, slide

def lens_unpopular_numbers():
    """人間の欲：誕生日で買われやすい1〜31を避け、買われにくい32〜37を僅かに優遇（当選時の分け前を増やす狙い）。"""
    return list(range(32, LOTO_MAX_NUM + 1))

def lens_auspicious_day(draw_date):
    """縁起日：天赦日・大安などを簡易判定。戻り値: (ラベルリスト, 縁起が良い日か)。"""
    labels = []
    try:
        eto = get_eto(draw_date)  # 十干十二支
        m = draw_date.month
        season = "春" if m in (2, 3, 4) else "夏" if m in (5, 6, 7) else "秋" if m in (8, 9, 10) else "冬"
        tensha = {"春": "戊寅", "夏": "甲午", "秋": "戊申", "冬": "甲子"}
        if eto == tensha[season]:
            labels.append("天赦日")
        rokuyo, _ = get_real_calendar_info(draw_date)
        if rokuyo == "大安":
            labels.append("大安")
    except Exception:
        pass
    return labels, bool(labels)

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

def get_full_environment(target_date):
    """その日の地球・宇宙の全環境を多角的に取得する（互いに独立した複数の軸）。"""
    phase, tide, gravity = get_moon_and_tide(target_date.year, target_date.month, target_date.day)
    rokuyo, _ = get_real_calendar_info(target_date)
    return {
        "重力": gravity, "潮回り": tide, "月相": phase,
        "干支": get_eto(target_date), "九星": get_fengshui(target_date), "六曜": rokuyo
    }

# 各分析軸の重み（独立性を考慮：月由来の3軸は相互に重複するため控えめ、干支など独立周期は高め）
ENV_AXIS_WEIGHTS = {
    "重力": 60,   # 月のリズム（代表軸）
    "潮回り": 20, # 月由来（重力と重複するため低め）
    "月相": 20,   # 月由来（同上）
    "干支": 80,   # 60日周期の独立軸（最も強い独立シグナル）
    "九星": 50,   # 9日周期の独立軸
    "六曜": 30,   # 6日周期の独立軸
}

def find_doppelganger_days(target_date, df_real):
    if df_real.empty: return [], Counter()
    t_env = get_full_environment(target_date)

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
                
                p_env = get_full_environment(past_date)
                score = 0
                match_details = []
                for axis, weight in ENV_AXIS_WEIGHTS.items():
                    if t_env.get(axis) == p_env.get(axis):
                        score += weight
                        match_details.append(f"{axis}({t_env.get(axis)})")

                # 月由来だけの一致では不十分。独立軸を含む3項目以上かつ高スコアのみ採用
                if score >= 150 and len(match_details) >= 3:
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

def analyze_environment_resonance(target_date, df_real):
    """
    過去の全抽選について「どの環境軸が今回と一致したか」を独立軸ごとに判定し、
    一致した軸ごとに出た数字を集計する。月だけに偏らない真の多角分析。
    戻り値: (軸ごとの数字集計 dict, 数字ごとの共鳴スコア Counter, 今回の環境指紋 dict)
    """
    if df_real.empty:
        return {}, Counter(), {}
    target_env = get_full_environment(target_date)
    axis_counters = {axis: Counter() for axis in ENV_AXIS_WEIGHTS}
    resonance = Counter()
    error_shown = False
    for _, row in df_real.iterrows():
        try:
            d_nums = re.findall(r'\d+', str(row.get("抽せん日", "")))
            if len(d_nums) < 3: continue
            y = int(d_nums[0])
            if y < 100: y += 2000
            past_date = date(y, int(d_nums[1]), int(d_nums[2]))
            if past_date >= target_date: continue
            past_env = get_full_environment(past_date)
            nums = [int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit()]
            if len(nums) != LOTO_PICK_COUNT: continue
            for axis, weight in ENV_AXIS_WEIGHTS.items():
                if past_env.get(axis) == target_env.get(axis):
                    axis_counters[axis].update(nums)
                    for n in nums:
                        resonance[n] += weight / LOTO_PICK_COUNT
        except Exception as e:
            if not error_shown:
                st.warning(f"環境共鳴分析中に一部データの解析エラーが発生しました。スキップして続行します: {e}")
                error_shown = True
    return axis_counters, resonance, target_env

def analyze_winning_environment(df_note, df_real):
    """
    ご主人が実際に当てた回（3個一致以上＝6等以上）の環境を抽出・集計し、
    『当選時に共通する地球・宇宙・暦の条件』を多角的に浮かび上がらせる。
    戻り値: (的中回の一覧 list, 軸ごとの当選環境集計 dict)
    """
    if df_note.empty or df_real.empty:
        return [], {axis: Counter() for axis in ENV_AXIS_WEIGHTS}
    hits = []
    win_env = {axis: Counter() for axis in ENV_AXIS_WEIGHTS}
    seen = set()
    for _, row in df_note.iterrows():
        advice = str(row.get("AIの助言", ""))
        m = re.search(r'(\d+)\s*個的中', advice)
        hit_count = int(m.group(1)) if m else 0
        if hit_count < 3:  # ロト7は3個一致（6等）から下位等級。記録対象は3個以上
            continue
        round_str = str(row.get("対象回号", ""))
        rn = re.findall(r'\d+', round_str)
        if not rn: continue
        key = (rn[0], tuple(str(row.get(f"数字{i}", "")) for i in range(1, LOTO_PICK_COUNT + 1)))
        if key in seen: continue
        seen.add(key)
        match = df_real[df_real["回号"] == f"第{rn[0]}回"]
        if match.empty: continue
        d_nums = re.findall(r'\d+', str(match.iloc[0].get("抽せん日", "")))
        if len(d_nums) < 3: continue
        y = int(d_nums[0]); y = y + 2000 if y < 100 else y
        try:
            draw_date = date(y, int(d_nums[1]), int(d_nums[2]))
        except Exception:
            continue
        env = get_full_environment(draw_date)
        for axis in ENV_AXIS_WEIGHTS:
            win_env[axis][env[axis]] += 1
        hits.append({"回号": round_str, "抽選日": draw_date.strftime("%Y-%m-%d"), "的中数": hit_count, "等級": advice, "環境": env})
    return hits, win_env

def get_recent_lessons(limit=3):
    """過去の反省会で得た学びを取得し、予測AIに引き継ぐ（PDCAの『Act＝次への反映』を実装）。"""
    try:
        df_log = load_sheet("反省ログ")
        if df_log.empty or "AIの学び" not in df_log.columns:
            return ""
        return "\n---\n".join(df_log.head(limit)["AIの学び"].astype(str).tolist())
    except Exception:
        return ""

def detect_prediction_bias(df_note, recent_rounds=4, threshold=0.45):
    """直近数回の積み上げ予測で、特定の数字に偏りすぎていないかを検知（忖度しない＝偏りを暴く）。
    戻り値: 警告テキスト（偏りが無ければ空文字）。"""
    try:
        if df_note.empty or "対象回号" not in df_note.columns:
            return ""
        def ext(s):
            m = re.findall(r'\d+', str(s))
            return int(m[0]) if m else 0
        rounds = sorted({r for r in df_note["対象回号"].tolist()}, key=ext, reverse=True)[:recent_rounds]
        sub = df_note[df_note["対象回号"].isin(rounds)]
        total_lines = 0
        cnt = Counter()
        for _, row in sub.iterrows():
            nums = [int(row.get(f"数字{i}")) for i in range(1, LOTO_PICK_COUNT + 1) if str(row.get(f"数字{i}", "")).isdigit()]
            if len(nums) == LOTO_PICK_COUNT:
                total_lines += 1
                cnt.update(set(nums))
        if total_lines < 10:
            return ""
        over = [(n, c / total_lines) for n, c in cnt.most_common() if c / total_lines >= threshold]
        if not over:
            return ""
        items = "、".join(f"{n}（{round(r*100)}%の口に出現）" for n, r in over[:6])
        return f"直近{len(rounds)}回・{total_lines}口の分析：数字 {items} に偏りがあります。同じ数字に頼りすぎている可能性があり、外れた時に共倒れするリスク大。"
    except Exception:
        return ""

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

def get_ai_intuition_numbers(feeling, weather, gravity, target_date):
    if not api_key: return random.sample(range(1, LOTO_MAX_NUM + 1), 3)
    prompt = f"""あなたは10億円のロト7を狙う最強の予知能力を持った天才科学者です。
次の情報から波動を読み取り、純粋な直感・予知で次回ロト7の数字（1〜{LOTO_MAX_NUM}）を3つ選んでください。
- 実行者の今日の気持ち・心境: {feeling if feeling else "（特になし）"}
- 地球の引力: {gravity} / 天気: {weather}
- 抽選予定日: {target_date}
理由・説明・絵文字は一切出力せず、「7, 15, 32」のようにカンマ区切りの数字だけを出力してください。"""
    text = ask_claude(prompt, max_tokens=80, model=MODEL_LIGHT)
    if not text:
        return random.sample(range(1, LOTO_MAX_NUM + 1), 3)
    seen = []
    for n in [int(x) for x in re.findall(r'\d+', text) if 1 <= int(x) <= LOTO_MAX_NUM]:
        if n not in seen: seen.append(n)
    return seen[:3] if len(seen) >= 3 else random.sample(range(1, LOTO_MAX_NUM + 1), 3)

# 🚀 【進化8】結果取得（UTF-8固定＋リトライ。文字化けで0件＝更新されない不具合を解消）
def fetch_loto7_results_ohtashp(existing_rounds):
    """ohtashp.comからロト7結果を取得。戻り値: (new_data行リスト, 取得成功フラグ)。
    取得成功フラグ=Trueは『サイトから表を解析できた』意味（新規が無くてもTrue）。"""
    cols_tail = ["", "", "", "", "", "", ""]  # 六曜/干支/風水/吉凶日/月齢/潮回り/重力 のうち月齢以降を埋める
    for attempt in range(4):
        try:
            res = requests.get(
                "https://www.ohtashp.com/topics/takarakuji/loto7/",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=20,
            )
            # ★HTTPヘッダに文字コードが無く ISO-8859-1 と誤認されるため、UTF-8で直接デコード
            soup = BeautifulSoup(res.content.decode("utf-8", errors="replace"), "html.parser")
            parsed = []
            for row in soup.find_all("tr"):
                th = row.find("th")
                if not th or "第" not in th.get_text():
                    continue
                tds = row.find_all("td")
                hon_tds = row.find_all("td", class_=lambda c: c and "hon" in c)
                if len(tds) < 10 or len(hon_tds) != LOTO_PICK_COUNT:
                    continue
                parsed.append((th.get_text(strip=True), tds[0].get_text(strip=True),
                               [td.get_text(strip=True) for td in hon_tds]))
            if parsed:
                new_data = []
                for draw_num, date_str, hon_nums in parsed:
                    if draw_num in existing_rounds:
                        continue
                    d_nums = re.findall(r'\d+', date_str)
                    if len(d_nums) >= 3:
                        dd = date(int(d_nums[0]), int(d_nums[1]), int(d_nums[2]))
                        m_phase, m_tide, m_gravity = get_moon_and_tide(dd.year, dd.month, dd.day)
                    else:
                        m_phase, m_tide, m_gravity = "", "", ""
                    new_data.append([draw_num, date_str] + hon_nums + ["", "", "", "", m_phase, m_tide, m_gravity])
                return new_data, True
        except Exception:
            pass
        time.sleep(1)
    return [], False

def fetch_latest_loto7_via_web(existing_rounds):
    """ohtashpが不調なときのフォールバック：Claudeのウェブ検索で最新結果を取得。戻り値: (new_data, エラー)。"""
    client = get_claude_client()
    if client is None:
        return [], "Claudeのキー（ANTHROPIC_API_KEY）が未設定です。"
    tools = [
        {"type": "web_search_20260209", "name": "web_search"},
        {"type": "web_fetch_20260209", "name": "web_fetch"},
    ]
    prompt = f"""ロト7の最新の当選結果を、みずほ銀行など公式・信頼できる情報源でウェブ検索して確認してください。
直近3回分について、回号・抽せん日・本数字7個（ボーナス数字は除く）を返します。
必ず複数のソースで一致を確認した正確な値だけを採用し、確信が持てない回は含めないこと。本数字は1〜37の7個です。

最後に、必ず次のJSONだけを ```json コードブロックで出力してください:
```json
[{{"round": "第683回", "date": "2026-06-26", "numbers": [1, 5, 12, 19, 24, 30, 37]}}]
```"""
    messages = [{"role": "user", "content": prompt}]
    text = ""
    try:
        for _ in range(4):
            r = client.messages.create(model=MODEL_MAIN, max_tokens=2000, tools=tools, messages=messages)
            if r.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": r.content})
                continue
            text = "".join(b.text for b in r.content if b.type == "text")
            break
    except Exception as e:
        return [], f"ウェブ検索に失敗しました: {e}"

    m = re.search(r'```json\s*(.+?)\s*```', text, re.DOTALL)
    raw = m.group(1) if m else (re.search(r'\[.*\]', text, re.DOTALL).group(0) if re.search(r'\[.*\]', text, re.DOTALL) else "")
    try:
        data = json.loads(raw)
    except Exception:
        return [], "ウェブ検索の結果を解析できませんでした。"
    if not isinstance(data, list):
        return [], "ウェブ検索の結果形式が想定と異なりました。"

    new_data = []
    for it in data:
        if not isinstance(it, dict):
            continue
        rd = str(it.get("round", "")).strip()
        if not rd or rd in existing_rounds:
            continue
        nums = []
        for n in it.get("numbers", []):
            try:
                v = int(n)
            except Exception:
                continue
            if 1 <= v <= LOTO_MAX_NUM:
                nums.append(v)
        if len(nums) != LOTO_PICK_COUNT:
            continue
        date_str = str(it.get("date", "")).strip()
        d_nums = re.findall(r'\d+', date_str)
        if len(d_nums) >= 3:
            try:
                dd = date(int(d_nums[0]), int(d_nums[1]), int(d_nums[2]))
                m_phase, m_tide, m_gravity = get_moon_and_tide(dd.year, dd.month, dd.day)
            except Exception:
                m_phase, m_tide, m_gravity = "", "", ""
        else:
            m_phase, m_tide, m_gravity = "", "", ""
        new_data.append([rd, date_str] + [str(n) for n in nums] + ["", "", "", "", m_phase, m_tide, m_gravity])
    return new_data, None

# 🚀 【進化11】全期間バックフィル（第1回〜最新の全当選番号＋東京の実天気を取り込む）
def weather_label_from_code(code):
    try:
        c = int(code)
    except Exception:
        return ""
    if c in (0, 1): return "晴れ"
    if c in (2, 3, 45, 48): return "曇り"
    if c in (71, 73, 75, 77, 85, 86): return "雪"
    if c in (95, 96, 99): return "嵐"
    return "雨"

def fetch_tokyo_weather_range(start_date, end_date):
    """東京の過去の日次天気（Open-MeteoのERA5再解析。2013年〜現在を全期間カバー）を範囲取得。
    戻り値: {YYYY-MM-DD: (天気, 気温, 降水, 気圧)}。"""
    out = {}
    try:
        url = ("https://archive-api.open-meteo.com/v1/archive"
               f"?latitude=35.69&longitude=139.69&start_date={start_date}&end_date={end_date}"
               "&daily=weather_code,temperature_2m_mean,precipitation_sum,pressure_msl_mean"
               "&timezone=Asia%2FTokyo")
        d = requests.get(url, timeout=60).json().get("daily", {})
        times = d.get("time", [])
        wc, tm, pr, ps = d.get("weather_code", []), d.get("temperature_2m_mean", []), d.get("precipitation_sum", []), d.get("pressure_msl_mean", [])
        for i, t in enumerate(times):
            out[t] = (
                weather_label_from_code(wc[i]) if i < len(wc) else "",
                round(tm[i], 1) if i < len(tm) and tm[i] is not None else "",
                pr[i] if i < len(pr) and pr[i] is not None else "",
                round(ps[i]) if i < len(ps) and ps[i] is not None else "",
            )
    except Exception as e:
        st.warning(f"過去天気の取得に一部失敗しました（天気欄は空で続行します）: {e}")
    return out

def fetch_loto7_full_history():
    """lotoseven.com から全回の (回号int, 'YYYY-MM-DD', [7数字]) を取得。"""
    r = requests.get("https://lotoseven.com/ap/tools/show_numbers",
                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=40)
    soup = BeautifulSoup(r.content.decode(r.apparent_encoding, errors="replace"), "html.parser")
    rows = []
    for tr in soup.find_all("tr"):
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) < 9 or not re.fullmatch(r"\d{1,4}", cells[0]):
            continue
        m = re.fullmatch(r"(20\d{2})/(\d{1,2})/(\d{1,2})", cells[1])
        if not m:
            continue
        nums = [c for c in cells[2:9] if re.fullmatch(r"\d{1,2}", c)]
        if len(nums) != 7:
            continue
        ymd = f"{int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
        rows.append((int(cells[0]), ymd, [c.zfill(2) for c in nums]))
    return rows

def backfill_full_history():
    """全回の当選番号＋暦＋東京の実天気で『実データ』を全期間版に再構築。戻り値: (df, エラー)。"""
    rows = fetch_loto7_full_history()
    if not rows:
        return None, "全履歴の取得に失敗しました（取得元の構造が変わった可能性があります）。"
    rows.sort(key=lambda x: x[0], reverse=True)  # 新しい回を上に
    dates = [r[1] for r in rows]
    wmap = fetch_tokyo_weather_range(min(dates), max(dates))
    data = []
    for kai, ymd, nums in rows:
        y, mo, da = (int(v) for v in ymd.split("-"))
        dd = date(y, mo, da)
        m_phase, m_tide, m_gravity = get_moon_and_tide(y, mo, da)
        rokuyo, _ = get_real_calendar_info(dd)
        w = wmap.get(ymd, ("", "", "", ""))
        row = {"回号": f"第{kai}回", "抽せん日": ymd}
        for i, n in enumerate(nums):
            row[f"数字{i+1}"] = n
        row.update({"六曜": rokuyo, "干支": get_eto(dd), "風水": get_fengshui(dd), "吉凶日": "特になし",
                    "月齢": m_phase, "潮回り": m_tide, "重力状態": m_gravity,
                    "天気": w[0], "気温": w[1], "降水": w[2], "気圧": w[3]})
        data.append(row)
    cols = ["回号", "抽せん日"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + \
           ["六曜", "干支", "風水", "吉凶日", "月齢", "潮回り", "重力状態", "天気", "気温", "降水", "気圧"]
    df = pd.DataFrame(data, columns=cols)
    save_sheet("実データ", df)
    return df, None

# 🚀 【進化9】週次サイクル：金19:30抽選＝リセットを基点に「今日やること」を判定
def get_week_phase():
    """戻り値: (今日のweekday, 抽選後フラグ, 7日サイクル表示用リスト, 今日のミッション)。
    金曜の抽選（夜）後〜土曜に「答え合わせ＆振り返り」、土〜木に「積み上げ」。"""
    now = datetime.now(JST)
    wd = now.weekday()  # 月=0 ... 日=6
    after_draw = (wd == 4 and (now.hour, now.minute) >= (19, 30))  # 金曜の抽選後
    # 表示用：土→日→月→火→水→木→金
    days = [("土", "答合せ・積上げ", 5), ("日", "積み上げ", 6), ("月", "積み上げ", 0),
            ("火", "積み上げ", 1), ("水", "積み上げ", 2), ("木", "最終チェック", 3), ("金", "決定・抽選", 4)]
    missions = {
        5: ("答え合わせ ＆ 来週への積み上げ", "金曜にできていなければ、まず結果を取り込んで採点＆辛口の振り返り。続けて来週の予測も積み上げ始めましょう。", "結果を取得して採点する", "最新データ取得"),
        6: ("予測の積み上げ", "今日の気持ちを言葉にして、来週へ向けて積み上げます。", "予測を積み上げる", "日々の予想・積上げ"),
        0: ("積み上げを重ねる", "日々の気持ちを核に、予測の厚みを増やします。", "予測を積み上げる", "日々の予想・積上げ"),
        1: ("積み上げ ＆ 心を観る", "積み上げつつ、占いの館で今週の波長もチェック。", "予測を積み上げる", "日々の予想・積上げ"),
        2: ("積み上げを継続", "ぶれずに毎日の波長を重ねます。", "予測を積み上げる", "日々の予想・積上げ"),
        3: ("最終チェック：他サイト収集", "明日の購入に向け、他サイトの総意を集めて横断分析します。", "他サイトを収集・分析する", "最新データ取得"),
        4: ("最終決定 → 購入（朝6〜8時）", "全方位の分析から本日の勝負手を確定し、購入します。", "最終決定レポートを出す", "最終予測決定"),
    }
    if after_draw:
        mission = ("答え合わせ ＆ 振り返り（今夜 or 明日でOK）", "抽選おつかれさまです。今夜できれば結果を取り込んで採点＆辛口の振り返り。飲み会などで無理なら明日（土）でOKです。", "結果を取得して採点する", "最新データ取得")
    else:
        mission = missions[wd]
    return wd, after_draw, days, mission

# ==========================================
# 5. メインUIレンダリング（天才科学者の管制室）
# ==========================================
if st.session_state.menu != "ホーム":
    st.markdown("<div class='nav-btn'>", unsafe_allow_html=True)
    st.button("総合案内（ホーム）に戻る", on_click=change_menu, args=("ホーム",))
    st.markdown("</div><hr>", unsafe_allow_html=True)

if st.session_state.menu == "ホーム":
    now_jst = datetime.now(JST)
    wd, after_draw, days, mission = get_week_phase()
    week_jp = "月火水木金土日"[wd]
    date_disp = f"{now_jst.month}/{now_jst.day}（{week_jp}）"

    # ブランドヘッダー
    st.markdown(
        "<div class='brand'><div class='crest'>✦ ✦ ✦</div>"
        "<div class='ttl'>ロト7 予知の天文台</div>"
        "<div class='sub'>ALL-DIRECTION FORECAST OBSERVATORY</div></div>",
        unsafe_allow_html=True,
    )

    # 週次サイクル・ステッパー（今日を強調）
    nodes = "".join(
        f"<div class='wn{(' active' if dnum == wd else '')}'><div class='d'>{label}</div><div class='a'>{action}</div></div>"
        for label, action, dnum in days
    )
    st.markdown(f"<div class='week'>{nodes}</div><div class='reset-note'>― 金の抽選後〜土に「答え合わせ＆振り返り」／土〜木に「積み上げ」 ―</div>", unsafe_allow_html=True)

    # 今日のミッション
    st.markdown(
        f"<div class='mission'><div class='lbl'>TODAY'S MISSION ・ {date_disp}</div>"
        f"<div class='mt'>{mission[0]}</div><div class='ds'>{mission[1]}</div></div>",
        unsafe_allow_html=True,
    )
    st.button(f"▶ {mission[2]}", on_click=change_menu, args=(mission[3],))

    # ステータス
    df_real = load_sheet("実データ")
    next_round, _ = get_next_round_info(df_real)
    df_note = load_sheet("予測ノート")
    stacked = len(df_note[df_note["対象回号"] == f"第{next_round}回"]) if (not df_note.empty and "対象回号" in df_note.columns) else 0
    st.markdown(
        f"<div class='stats'>"
        f"<div class='stat'><div class='v'>第{next_round}回</div><div class='k'>NEXT DRAW</div></div>"
        f"<div class='stat'><div class='v'>{stacked}口</div><div class='k'>STACKED</div></div>"
        f"<div class='stat'><div class='v'>{len(df_real)}</div><div class='k'>DATA</div></div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # メニュー
    st.markdown("<div class='sec-label'>― 管制メニュー ―</div>", unsafe_allow_html=True)
    st.button("📋 今週の総監督レポート（全体を把握）", on_click=change_menu, args=("総監督レポート",))
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.button("📡 最新データ取得（結果・採点・他サイト）", on_click=change_menu, args=("最新データ取得",))
        st.write("")
        st.button("🌍 全方位の量子環境分析＆予測積上げ", on_click=change_menu, args=("日々の予想・積上げ",))
    with c2:
        st.button("🎯 最終決定（10億捕捉の包囲網）", on_click=change_menu, args=("最終予測決定",))
        st.write("")
        st.button("🔄 答え合わせと辛口の反省会（PDCA）", on_click=change_menu, args=("結果発表と振り返り",))
        st.write("")
        st.button("🔮 万能AI占い師の館", on_click=change_menu, args=("万能AI占い師の館",))

    if get_gspread_client() is None:
        st.error("データベース接続設定（Secrets）が未完了です。")

elif st.session_state.menu == "最新データ取得":
    st.title("📡 最新データ取得")
    st.caption("結果の取得元：ohtashp.com（公式みずほは自動取得をブロックするため）。取得できない時はClaudeのウェブ検索で自動補完します。")
    if st.button("データ同期および自動採点を実行する"):
        with st.spinner("通信中...最新の当選結果を解析し、予想と照合しています..."):
            try:
                df_real = load_sheet("実データ")
                existing_rounds = df_real["回号"].astype(str).tolist() if not df_real.empty and "回号" in df_real.columns else []

                # ① まず ohtashp.com（UTF-8固定＋リトライ。文字化けで0件→更新されない不具合を解消）
                new_data, site_ok = fetch_loto7_results_ohtashp(existing_rounds)
                source = "ohtashp.com"

                # ② サイトが不調（表を1件も解析できない）なら、Claudeのウェブ検索で補完
                if not site_ok:
                    web_data, web_err = fetch_latest_loto7_via_web(existing_rounds)
                    if web_data:
                        new_data, source = web_data, "ウェブ検索（Claude）"
                    elif web_err:
                        st.caption(f"（ウェブ検索フォールバック: {web_err}）")

                if new_data:
                    cols = ["回号", "抽せん日"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + ["六曜", "干支", "風水", "吉凶日", "月齢", "潮回り", "重力状態"]
                    df_new = pd.DataFrame(new_data, columns=cols)
                    df_combined = pd.concat([df_new, df_real], ignore_index=True) if not df_real.empty else df_new
                    save_sheet("実データ", df_combined)
                    auto_check_hits(load_sheet("予測ノート"), df_combined)
                    st.success(f"最新結果（取得元: {source}）を {len(new_data)} 件取り込み、全予想を自動採点しました！")
                    st.dataframe(df_new[["回号", "抽せん日"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)]])
                    if source.startswith("ウェブ"):
                        st.caption("※ウェブ検索で取得した番号です。念のためみずほ銀行の公式発表と照合してください。")
                elif site_ok:
                    auto_check_hits(load_sheet("予測ノート"), df_real)
                    st.info("データベースは既に最新です。既存の予測ノートを再採点しました。")
                else:
                    auto_check_hits(load_sheet("予測ノート"), df_real)
                    st.warning("結果の取得元が一時的に不安定で、新しい結果を取得できませんでした。数分おいて再実行してください（既存の予測ノートは再採点しました）。")
            except Exception as e:
                st.error(f"データの同期・解析中にエラーが発生しました: {e}")

    st.markdown("---")
    st.markdown("### 📚 過去の全当選番号を一括取り込み（全期間＋日付＋東京の実天気）")
    st.markdown("<div class='info-box'>第1回〜最新まで<b>全回の当選番号</b>を取り込み、各回の月齢・暦に加え<b>東京（抽選地）の実際の天気（気象庁モデル）</b>も付与します。データが豊富なほど各レンズの傾向分析が鋭くなり、「天気の影響」も検証できます。<br>（実データを全期間版に置き換えます。月1回ほど押せば天気も最新化されます）</div>", unsafe_allow_html=True)
    if st.button("📚 全期間の当選番号＋天気を取り込む（30秒〜1分）"):
        with st.spinner("全回の当選番号と、東京の過去天気（気象庁モデル）を取得しています..."):
            df_full, err = backfill_full_history()
        if err:
            st.error(err)
        else:
            auto_check_hits(load_sheet("予測ノート"), df_full)
            st.success(f"全 {len(df_full)} 回の当選番号を取り込み、天気を付与して、全予想を再採点しました！")
            show_cols = ["回号", "抽せん日"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + ["天気", "気温", "気圧"]
            st.dataframe(df_full[[c for c in show_cols if c in df_full.columns]].head(20))

    st.markdown("---")
    st.markdown("### 🌐 他サイト予想の全自動収集＆横断分析（URL登録不要）")
    st.markdown("<div class='info-box'>URLを登録する必要はありません。<b>Claudeがウェブを自動で検索し、ロト7の予想サイト・ブログ・YouTubeをできるだけ多く探し出して</b>、各ソースの予想数字を抽出し『他サイト予想』シートを丸ごと更新します。そのうえで、<b>「どの数字が人気で何位か」「あなたの予想との違い」「（抽選後）どのサイトが正解に一番近かったか」</b>まで分析します。<br>※YouTubeはタイトル・概要・コメントの文字から読める数字のみ対象（動画内の音声は読めません）。</div>", unsafe_allow_html=True)
    df_real0 = load_sheet("実データ")
    next_round, _ = get_next_round_info(df_real0)
    rounds_for_search = [f"第{next_round + i}回" for i in range(-3, 3)]
    target_round_label = st.selectbox("どの回号の予想を集めますか？", rounds_for_search, index=rounds_for_search.index(f"第{next_round}回") if f"第{next_round}回" in rounds_for_search else 0)

    ccol1, ccol2 = st.columns(2)
    if ccol1.button("🌐 ウェブを全自動検索して予想を収集する", use_container_width=True):
        with st.spinner("Claudeがウェブを検索し、予想サイト・YouTubeを横断収集しています（30秒〜1分かかります）..."):
            df_collected, err = research_predictions_via_web(target_round_label)
        if err:
            st.warning(err)
        else:
            st.success(f"{len(df_collected)}件のソースから予想を収集し、『他サイト予想』を更新しました。")
            st.dataframe(df_collected)
            render_other_site_analysis(df_collected, target_round_label)

    if ccol2.button("📊 収集済みデータで横断分析する", use_container_width=True):
        render_other_site_analysis(load_sheet("他サイト予想"), target_round_label)

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
        
        st.markdown("#### 💗 今日のあなたの気持ち・心境（プログラムがこれを読み取ります）")
        st.caption("プルダウンで飾る必要はありません。いま感じていること・今日の出来事・祈り・直感を、そのまま自由に書いてください。書いた言葉そのものが、その日だけの量子シードとAI分析の核になります。空欄でもOKです。")
        feeling = st.text_area(
            "今日の気持ち（自由入力）",
            placeholder="例：今朝カラスが3羽鳴いていた。なんとなく胸騒ぎがする。家族が健康でいられますように。仕事は落ち着いている。",
            height=150
        )

        use_fortune = st.checkbox("🔮 今日の占いのラッキーナンバーを軽く加味する（偏り防止のため控えめウェイト・任意）", value=False, help="『万能AI占い師の館』で『🎯今日の占いナンバーをロト7へ渡す』を押して保存した数字を、控えめに加点します。")

        submitted = st.form_submit_button("🔥 超次元演算：あなたの気持ちを核に量子シードと物理法則を起動し予測を積上げる")
        
        if submitted:
            if df_real.empty: st.error("基盤データがありません。")
            else:
                with st.spinner("量子シード生成中... 地球環境、ドッペルゲンガー、物理的ボール衝突法則を完全に同期させています..."):
                    today_str = datetime.now(JST).strftime("%Y-%m-%d")

                    # 0. 「気持ち」を全シグナルの核に据える（プログラムが実行者の気持ちを理解する）
                    feeling_text = (feeling or "").strip()
                    soc_sensor = spirit_sensor = good_deed = feeling_text if feeling_text else "特になし"
                    prayer = feeling_text if feeling_text else "（無心）"
                    biorhythm = sign = feeling_text

                    # 占い × ロト7（任意・控えめ）：今日の占いナンバーを取得
                    fortune_nums = get_today_fortune_numbers() if use_fortune else []

                    weather, pressure = get_current_weather_and_pressure()
                    m_phase, m_tide, m_gravity = get_moon_and_tide(draw_date.year, draw_date.month, draw_date.day)
                    m_feng = get_fengshui(draw_date)

                    # 1. AI直感の取得（気持ちを最重要シグナルとして渡す）
                    ai_intuition_nums = get_ai_intuition_numbers(feeling_text, f"{weather} / {pressure}", m_gravity, draw_date)
                    
                    # 2. 完全環境一致（ドッペルゲンガー）の抽出
                    sync_matches, sync_counts = find_doppelganger_days(draw_date, df_real)
                    hot_sync_nums = [n for n, c in sync_counts.most_common(5)]

                    # 2.5 多角的「環境共鳴」分析（重力・潮・月相・干支・九星・六曜を独立軸で集計）
                    axis_counters, env_resonance, target_env = analyze_environment_resonance(draw_date, df_real)
                    resonance_top = [n for n, _ in env_resonance.most_common(7)]

                    # 3. 🚀 動的量子シード生成
                    quantum_seed_nums = generate_dynamic_quantum_seed(str(draw_date), soc_sensor, spirit_sensor, prayer, good_deed)
                    
                    # 4. 直近トレンドの取得
                    recent_df = df_real.head(10)
                    recent_nums = [int(r.get(f"数字{i}")) for _, r in recent_df.iterrows() for i in range(1, LOTO_PICK_COUNT + 1) if pd.notna(r.get(f"数字{i}")) and str(r.get(f"数字{i}")).isdigit()]
                    recent_counts = Counter(recent_nums)

                    # フェーズ3：多角分析レンズ
                    carry_nums, slide_nums = lens_carry_slide(df_real)
                    unpop_nums = lens_unpopular_numbers()
                    ausp_labels, ausp_good = lens_auspicious_day(draw_date)

                    st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                    st.markdown("### 🔭 全方位レポート（観点＝レンズ別）")
                    st.write(f"🌍 **【自然・引力】** 予定日（{draw_date}）：{m_tide} / {m_phase} / 重力:{m_gravity} / {weather}")
                    st.write(f"🌌 **【量子シード】**: {quantum_seed_nums} （今日の波長から生成）")
                    if ai_intuition_nums: st.write(f"🧠 **【AIの直感】**: {ai_intuition_nums}")
                    if fortune_nums: st.write(f"🔮 **【占いラッキー（控えめ反映）】**: {fortune_nums}")
                    elif use_fortune: st.caption("🔮 占いを加味する設定ですが、今日の占いナンバーが未保存です。占い師の館で『🎯ロト7へ渡す』を押してください。")
                    if env_resonance:
                        st.write(f"🪐 **【暦・環境共鳴（干支・九星・六曜・月）】**: {resonance_top}")
                        axis_brief = " / ".join([f"{ax}:{target_env.get(ax)}" for ax in ENV_AXIS_WEIGHTS])
                        st.caption(f"今回の環境指紋 → {axis_brief}")
                    if sync_matches:
                        st.write(f"🎯 **【完全環境一致日（ドッペルゲンガー）】**: {hot_sync_nums}")
                        for m in sync_matches[:2]: st.caption(f" - {m['回号']} ({m['日付']}) | 一致: {m['一致項目']}")
                    if carry_nums or slide_nums:
                        st.write(f"📜 **【出目理論】** 引っ張り(前回再出): {carry_nums} ／ スライド(±1): {slide_nums}")
                    st.write(f"👥 **【人間の欲】** 買われにくい高数字 {unpop_nums} を僅かに優遇（当たった時の分け前を増やす狙い）")
                    if ausp_labels:
                        st.write(f"🗓 **【縁起日】** {' ・ '.join(ausp_labels)} ＝ 縁起の良い日。直感を後押し")
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

                        # 理論6：多角・環境共鳴（過去の同一環境で実際に出た数字を、月だけに偏らず加点）
                        base_w += int(env_resonance.get(n, 0) * 0.5)

                        # 理論7：占いのラッキーナンバー（任意・控えめ。他シグナルより弱く＝偏りにくい）
                        if n in fortune_nums: base_w += 15

                        # 理論8：出目理論（引っ張り＝前回再出／スライド＝±1）
                        if n in carry_nums: base_w += 12
                        if n in slide_nums: base_w += 8

                        # 理論9：人間の欲（買われにくい高数字を僅かに優遇＝当選時の分け前UP狙い）
                        if n in unpop_nums: base_w += 6

                        # 理論10：縁起日ブースト（縁起の良い日は直感ナンバーを後押し）
                        if ausp_good and n in ai_intuition_nums: base_w += 8

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
                    top30, num_usage, added = [], Counter(), set()
                    TARGET_ELITE = 28

                    def add_pick(e, max_overlap, usage_cap):
                        key = tuple(e["nums"])
                        if key in added: return False
                        if any(len(set(e["nums"]) & set(t["nums"])) >= max_overlap for t in top30): return False
                        if usage_cap is not None and any(num_usage[n] >= usage_cap for n in e["nums"]): return False
                        item = dict(e); item["type"] = logic_name
                        top30.append(item); added.add(key)
                        for n in e["nums"]: num_usage[n] += 1
                        return True

                    # 段階的に制約をゆるめて、目標の28口を確実に確保する（重複/使用回数の上限を順に緩和）
                    for max_ov, cap in [(4, 7), (4, 10), (4, None), (5, None), (7, None)]:
                        for e in elites:
                            if len(top30) >= TARGET_ELITE: break
                            add_pick(e, max_ov, cap)
                        if len(top30) >= TARGET_ELITE: break

                    # それでも足りない場合はランダムで補完（重複は除く）
                    while len(top30) < TARGET_ELITE:
                        rp = sorted(random.sample(nums_list, LOTO_PICK_COUNT))
                        if tuple(rp) in added: continue
                        top30.append({"nums": rp, "pts": 0, "base_pts": 0, "type": logic_name + "(補完)"})
                        added.add(tuple(rp))

                    # 未知への挑戦：完全ランダム2口（合計30口）
                    for _ in range(2):
                        rp = sorted(random.sample(nums_list, LOTO_PICK_COUNT))
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
                    st.success(f"固定バイアスを完全排除し、動的量子シードと物理演算を駆使して、{target_round_str}に向けて最強の{len(top30)}口を積み上げました。（担当: {operator}）")

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
                        
                        past_lessons = get_recent_lessons()
                        prompt = f"""ユーザーからの特別作戦指示: "{user_instruction}"

【過去の反省会で得た学び（必ず踏まえ、同じ失敗を繰り返さず改善せよ）】
{past_lessons if past_lessons else "（まだ蓄積された学びはありません）"}

【システムが積み上げから厳選した{buy_count}口（各口に実行者の「その日の気持ち」が記録されています。社会:＝霊的:＝気持ちの言葉です）】
{ai_prompt}
"""
                        try:
                            res_text = ask_claude(prompt, system=AWAKENED_SCIENTIST_PROMPT, max_tokens=2500)
                            if not res_text:
                                raise RuntimeError("Claudeからの応答が空でした（ANTHROPIC_API_KEY 未設定の可能性があります）")
                            st.markdown(f"#### 🎯 最終決断レポート（10億捕捉の{buy_count}口）")
                            display_cols = ["実行者", "口数"] + [f"数字{i}" for i in range(1, LOTO_PICK_COUNT + 1)] + ["社会情勢", "霊的要素", "AI直感", "予測ロジック"]
                            st.dataframe(pd.DataFrame(final_picks)[display_cols])
                            st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                            st.write("▼ 最強予知科学者（Claude）からの絶対的予言レポート")
                            st.markdown(res_text)
                            st.markdown("</div>", unsafe_allow_html=True)

                            now_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
                            df_history = load_sheet("決断記録簿")
                            save_text = f"【指示】: {user_instruction}\n【厳選の{buy_count}口】\n" + ai_prompt + "\n\n【AIの解説】\n" + res_text
                            new_history = pd.DataFrame({"日時": [now_str], "対象回号": [t_round_decide_str], "決断内容": [save_text]})
                            df_history = pd.concat([new_history, df_history], ignore_index=True) if not df_history.empty else new_history
                            save_sheet("決断記録簿", df_history)
                            st.success("決断内容は『決断記録簿』に強固に保管されました。10億円の引き寄せは完了しました！")
                        except Exception as e: 
                            st.error(f"AIによる最終決断レポートの生成に失敗しました: {e}")

elif st.session_state.menu == "結果発表と振り返り":
    st.title("🔄 答え合わせと地球規模の反省会")
    tab1, tab2, tab3, tab4 = st.tabs(["予測の答え合わせ", "💬 宇宙と繋がる徹底反省会（PDCA）", "過去の決断記録簿", "🏆 当選環境アーカイブ分析"])
    
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
                    
                    prompt = f"""【本抽選の正解データ】:
{actual_info}

【我が家の予測と結果（社会:＝霊的:＝実行者のその日の気持ちの言葉）】:
{target_txt}

【ユーザーからの依頼】: "{user_rev_input}"
"""
                    try:
                        res_text = ask_claude(prompt, system=REVIEW_PDCA_PROMPT, max_tokens=2000)
                        if not res_text:
                            raise RuntimeError("Claudeからの応答が空でした（ANTHROPIC_API_KEY 未設定の可能性があります）")
                        st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                        st.markdown(res_text)
                        st.markdown("</div>", unsafe_allow_html=True)

                        # PDCA：この学びを『反省ログ』に蓄積し、次回以降の予測AIへ引き継ぐ（Act）
                        try:
                            log_now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
                            df_log = load_sheet("反省ログ")
                            new_log = pd.DataFrame({"日時": [log_now], "対象回号": [t_round_rev_str], "分析テーマ": [user_rev_input], "AIの学び": [res_text]})
                            df_log = pd.concat([new_log, df_log], ignore_index=True) if not df_log.empty else new_log
                            save_sheet("反省ログ", df_log)
                            st.success("この学びは『反省ログ』に蓄積され、次回の最終決断AIに自動で引き継がれます（PDCAが回り始めました）。")
                        except Exception as e:
                            st.warning(f"反省ログの保存に失敗しました（分析自体は成功しています）: {e}")
                    except Exception as e:
                        st.error(f"反省会レポートの生成中にエラーが発生しました。詳細: {e}")

    with tab3:
        df_history = load_sheet("決断記録簿")
        if not df_history.empty and "日時" in df_history.columns:
            for _, row in df_history.iterrows():
                with st.expander(f"記録: {row.get('日時', '')} | {row.get('対象回号', '')}"):
                    st.write(row.get("決断内容", ""))
        else: st.info("記録はありません。")

    with tab4:
        st.markdown("#### 🏆 あなたが当てた回の『環境・地球の動き・宇宙の配置』を多角分析")
        st.markdown("<div class='info-box'>5等・6等を含む過去の的中（3個一致以上）を全自動で抽出し、<b>当選した瞬間に共通していた条件</b>（重力・潮・月相・干支・九星・六曜）を浮かび上がらせます。これが4等→3等→2等→1等へ引き上げるための『当選の波長』の正体です。</div>", unsafe_allow_html=True)
        if st.button("🏆 当選環境を集計し、共通法則をAIが多角分析する"):
            hits, win_env = analyze_winning_environment(df_note, df_real)
            if not hits:
                st.info("まだ的中記録（3個一致以上）が見つかりませんでした。「最新データ取得」で採点を実行してから再度お試しください。")
            else:
                st.success(f"過去の的中（6等以上）を {len(hits)} 件検出しました。当選時の環境を解析します。")
                st.markdown("##### 🌌 当選時に共通していた環境条件（出現回数の多い順）")
                for axis in ENV_AXIS_WEIGHTS:
                    common = win_env[axis].most_common(3)
                    if common:
                        txt = " / ".join([f"{v}（{c}回）" for v, c in common])
                        st.write(f"- **{axis}**：{txt}")
                st.markdown("##### 📋 的中した回の環境一覧")
                st.dataframe(pd.DataFrame([{"回号": h["回号"], "抽選日": h["抽選日"], "的中": h["等級"], **{ax: h["環境"][ax] for ax in ENV_AXIS_WEIGHTS}} for h in hits]))

                if not api_key:
                    st.warning("AIによる深掘り分析にはAPIキーの設定が必要です。")
                else:
                    with st.spinner("当選時に共通する『地球の動き・宇宙の配置』を、予知科学者が多角的に深掘り中..."):
                        env_summary = "\n".join([f"{h['回号']} {h['抽選日']} ({h['等級']}) | " + " / ".join([f"{ax}:{h['環境'][ax]}" for ax in ENV_AXIS_WEIGHTS]) for h in hits])
                        common_summary = "\n".join([f"{axis}: " + ", ".join([f"{v}({c}回)" for v, c in win_env[axis].most_common(3)]) for axis in ENV_AXIS_WEIGHTS if win_env[axis]])
                        win_prompt = f"""{REVIEW_PDCA_PROMPT}

【ご主人が実際に当選した回の環境データ】
{env_summary}

【当選時に共通して現れた条件の集計】
{common_summary}

上記の実データから、ご主人が当選しやすい『地球の動き・宇宙の配置・暦の波長』の共通法則を多角的に特定せよ。そして4等・3等・2等・1等へ引き上げるために『次にどの環境条件の日を狙い撃つべきか』『どの見えないセンサーを研ぎ澄ますべきか』を、確信を持って具体的に指示せよ。"""
                        try:
                            res_text = ask_claude(win_prompt, system=REVIEW_PDCA_PROMPT, max_tokens=2000)
                            if not res_text:
                                raise RuntimeError("Claudeからの応答が空でした（ANTHROPIC_API_KEY 未設定の可能性があります）")
                            st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                            st.write("▼ 予知科学者（Claude）による『あなたの当選環境』の深層分析")
                            st.markdown(res_text)
                            st.markdown("</div>", unsafe_allow_html=True)
                            try:
                                log_now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
                                df_log = load_sheet("反省ログ")
                                new_log = pd.DataFrame({"日時": [log_now], "対象回号": ["当選環境アーカイブ分析"], "分析テーマ": ["当選時の環境共通法則の特定"], "AIの学び": [res_text]})
                                df_log = pd.concat([new_log, df_log], ignore_index=True) if not df_log.empty else new_log
                                save_sheet("反省ログ", df_log)
                            except Exception:
                                pass
                        except Exception as e:
                            st.error(f"当選環境のAI分析に失敗しました: {e}")

elif st.session_state.menu == "総監督レポート":
    st.title("📋 今週の総監督レポート")
    st.markdown("<div class='info-box'>当選 → 分析 → 次回 を1画面で締める『監督席』です。直近の結果を振り返り、次回への構えを確認し、AI監督が改善指示を出します。</div>", unsafe_allow_html=True)

    df_real = load_sheet("実データ")
    df_note = load_sheet("予測ノート")
    df_other = load_sheet("他サイト予想")
    next_round, _ = get_next_round_info(df_real)
    last_round_label = f"第{next_round - 1}回"
    next_round_label = f"第{next_round}回"

    st.markdown(f"### 🔁 直近の抽選 **{last_round_label}** → 次回 **{next_round_label}**")

    actual = actual_numbers_for_round(df_real, last_round_label)
    best = user_best_prediction_for_round(df_note, last_round_label, actual) if actual else None
    site_hot = site_consensus_hot(df_other)

    # ① 直近の結果レビュー
    st.markdown("#### ① 直近の結果レビュー")
    if actual:
        st.write(f"正解番号（{last_round_label}）: **{sorted(actual)}**")
        if best:
            grade = "🎉 当せん圏！" if best["hits"] >= 4 else "惜しい" if best["hits"] == 3 else "次へ"
            st.write(f"あなたの最高成績: **{best['hits']}個的中**（{best['実行者']} / {best['口数']}）{grade} → {best['nums']}")
        else:
            st.info("この回のあなたの予測記録が見つかりませんでした。")
        # どのサイトが近かったか
        if not df_other.empty and "予想数字" in df_other.columns:
            board = []
            for _, row in df_other.iterrows():
                snums = set(int(x) for x in re.findall(r'\d+', str(row.get("予想数字", ""))) if 1 <= int(x) <= LOTO_MAX_NUM)
                if snums:
                    board.append({"ソース": row.get("ソース", row.get("サイトURL", "")), "的中数": len(snums & actual)})
            if board:
                board.sort(key=lambda x: x["的中数"], reverse=True)
                st.write(f"他サイトで最も近かった: **{board[0]['ソース']}**（{board[0]['的中数']}個的中）")
    else:
        st.info(f"{last_round_label} の結果がまだ取り込まれていません。先に「📡 最新データ取得」を実行してください。")

    # ② 次回への構え
    st.markdown("#### ② 次回への構え")
    prepared = len(df_note[df_note["対象回号"] == next_round_label]) if (not df_note.empty and "対象回号" in df_note.columns) else 0
    st.write(f"{next_round_label} に向けて積み上げ済み: **{prepared}口**")
    if site_hot:
        st.write(f"他サイトの人気数字トップ7: **{site_hot}**")
    if prepared == 0:
        st.warning("次回の積み上げがまだです。「🌍 予測積上げ」で今日の気持ちを入れて積み上げましょう。")

    # 偏り検知（忖度しない＝偏りを暴く）
    bias_warn = detect_prediction_bias(df_note)
    if bias_warn:
        st.warning(f"⚠️ 偏り検知：{bias_warn}")

    # ③ AI監督コメント（APIを使うのでボタン式。1回だけ呼び出し）
    st.markdown("#### ③ AI監督からの総括と次回への指示")
    if st.button("🧭 AI監督に今週の総括と次回への指示を出してもらう"):
        if not api_key:
            st.error("Claudeのキー（ANTHROPIC_API_KEY）が未設定です。")
        else:
            with st.spinner("統括監督AIが『結果・分析・次回』をつなげて講評しています..."):
                lessons = get_recent_lessons(2)
                summary = f"""直近 {last_round_label} の正解番号: {sorted(actual) if actual else '未取得'}
あなたの最高成績: {(str(best['hits']) + '個的中 → ' + str(best['nums'])) if (actual and best) else '記録なし'}
他サイトの人気数字トップ7: {site_hot if site_hot else 'データなし'}
次回 {next_round_label} の積み上げ口数: {prepared}口
予測の偏り検知: {bias_warn if bias_warn else '大きな偏りは検知されず'}
過去の反省会の学び:
{lessons if lessons else 'まだなし'}"""
                sup_prompt = f"""次のロト7運用状況を、統括監督として講評してください。

{summary}

必ず次の見出しで出力してください:
## 今週の総括
（1〜2行）
## 良かった点 / 外した要因
（箇条書き）
## 次回 {next_round_label} への調整指示
（狙う環境・重み付け・心の持ち方を具体的に）
## 今週のやることチェックリスト
（金曜購入に向けた手順を箇条書きで）"""
                report = ask_claude(sup_prompt, system=SUPERVISOR_PROMPT, max_tokens=2000)
            if not report:
                st.warning("AI監督コメントの生成に失敗しました（APIキー／残高をご確認ください）。")
            else:
                st.markdown("<div class='analysis-box'>", unsafe_allow_html=True)
                st.markdown(report)
                st.markdown("</div>", unsafe_allow_html=True)
                try:
                    log_now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
                    df_log = load_sheet("反省ログ")
                    new_log = pd.DataFrame({"日時": [log_now], "対象回号": [f"総監督レポート({last_round_label}→{next_round_label})"], "分析テーマ": ["週次の統括監督"], "AIの学び": [report]})
                    df_log = pd.concat([new_log, df_log], ignore_index=True) if not df_log.empty else new_log
                    save_sheet("反省ログ", df_log)
                    st.caption("この監督講評は『反省ログ』に保存され、次回の予測AIにも引き継がれます。")
                except Exception:
                    pass

# ==========================================
# 6. 万能AI占い師の館（手打ち不要・スマホ無敵版）
# ==========================================
elif st.session_state.menu == "万能AI占い師の館":
    st.title("🔮 万能AI占い師の館（スマホ手打ち不要版）")
    st.markdown("<div class='info-box'>占いの相談室です。占い・運勢・ラッキーナンバーは<b>誰でもパスなしで</b>使えます。<br>見られたくない相談だけは、下の<b>「🔒 自分だけのプライベート相談室」</b>に合言葉で入れます（会話は公開の部屋と完全に分かれ、他の人に見えません）。</div>", unsafe_allow_html=True)

    if not api_key:
        st.error("占い機能を利用するにはAPIキーの設定が必要です。")
    else:
        # 通常は誰でもパス不要で使える『公開の相談室』。
        # 見られたくない時だけ、合言葉で『自分だけのプライベート相談室』に切り替えられる。
        private_pass = (st.secrets.get("FORTUNE_PRIVATE_PASSCODE", "")
                        or st.secrets.get("FORTUNE_PASSCODE_U1", "")
                        or st.secrets.get("FORTUNE_PASSCODE", ""))
        in_private = bool(st.session_state.get("fortune_private", False) and private_pass)

        if in_private:
            st.markdown("<div class='info-box'>🔒 ここは<b>あなただけのプライベート相談室</b>。会話は公開の部屋と完全に分かれており、他の人には見えません。何でも安心して話してください。</div>", unsafe_allow_html=True)
            if st.button("🔓 公開の相談室に戻る"):
                st.session_state.fortune_private = False
                st.rerun()
        else:
            if private_pass:
                with st.expander("🔒 自分だけのプライベート相談室に入る（合言葉）", expanded=False):
                    with st.form("fortune_private_form"):
                        code_in = st.text_input("あなたの合言葉（パスコード）", type="password")
                        if st.form_submit_button("🔓 入る"):
                            if code_in == private_pass:
                                st.session_state.fortune_private = True
                                st.rerun()
                            else:
                                st.error("合言葉が違います。")
            else:
                st.caption("🔒 自分だけの非公開の部屋を作るには、Secrets に  FORTUNE_PRIVATE_PASSCODE = \"あなただけの合言葉\"  を追加してください。")

        # 公開／プライベートで会話を分離（プライベートの内容は公開の部屋に出ない）
        mode_key = "private" if in_private else "public"
        msg_key = f"fortune_messages::{mode_key}"
        fapi_key = f"fortune_api::{mode_key}"
        if msg_key not in st.session_state:
            if in_private:
                welcome = "ようこそ、あなただけの相談室へ。✨\nここでの会話は誰にも見られません。占いも、誰にも言えない悩みも、人生のことも——どうか安心して、何でも話してください。"
            else:
                welcome = "ようこそ、神秘の部屋へ。✨\n占い・運勢・相性・ラッキーナンバー、何でもお尋ねください。今日は何をお話ししましょうか。"
            st.session_state[msg_key] = [{"role": "assistant", "content": welcome}]
        if fapi_key not in st.session_state:
            st.session_state[fapi_key] = []

        def send_to_fortune(text, image=None):
            """占い師Claudeに文脈付きで送信し、応答テキストを返す（利用者ごとに履歴を保持）。"""
            content = []
            if image is not None:
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                b64 = base64.standard_b64encode(buf.getvalue()).decode("utf-8")
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})
            content.append({"type": "text", "text": text})
            st.session_state[fapi_key].append({"role": "user", "content": content})
            try:
                reply = claude_chat(st.session_state[fapi_key], system=FORTUNE_CHAT_PROMPT, max_tokens=3000)
                if not reply:
                    reply = "（波動が少し乱れました。もう一度、ゆっくり話しかけてください）"
            except Exception as e:
                reply = f"（通信エラーが発生しました。再度お試しください: {e}）"
            st.session_state[fapi_key].append({"role": "assistant", "content": reply})
            return reply

        DEFAULT_IMG_QUESTION = "この画像から私の運命と波長を深く読み解いてください。"

        # --- 補助メニュー（たまにしか使わないので折りたたみ。写真は最初に置く）---
        with st.expander("🗂 占術を選ぶ ／ 📸 写真を送る ／ 定番の質問から選ぶ", expanded=False):
            img_source = st.file_uploader("📂 写真を選ぶ（手相・人相・オーラ等）。選ぶと次のメッセージに添付されます。", type=["jpg", "jpeg", "png"], key="fortune_img")

            c1, c2 = st.columns([3, 1])
            div_list = ["🕊 人生の目的・魂の使命の鑑定", "西洋占星術（ホロスコープ）", "四柱推命", "タロット占い", "手相（要写真）", "人相（要写真）", "オーラ鑑定（要写真）", "コーヒー占い（要写真）"]
            selected_div = c1.selectbox("🔮 占術を選ぶ", ["占いを選択してください..."] + div_list, key="fortune_div")
            if c2.button("この占いを始める", use_container_width=True):
                if selected_div != "占いを選択してください...":
                    user_msg = f"「{selected_div}」をお願いします。"
                    st.session_state[msg_key].append({"role": "user", "content": user_msg})
                    with st.spinner("星の声を聴いています..."):
                        reply = send_to_fortune(user_msg)
                        st.session_state[msg_key].append({"role": "assistant", "content": reply})
                    st.rerun()

            fortune_options = [
                "（選んでこのボタンで送信）",
                "私はなぜこの世に生まれてきたのか、魂の目的と使命を視てください。",
                "私の人生の目的と、これから進むべき道を教えてください。",
                "家族の本当の幸せのために、私が今できることは何でしょうか？",
                "私の全体的な運勢と現在の波動を鑑定してください。",
                "私の金運と直感の冴えを視てください。",
                "今の私の精神状態（オーラやエネルギー）はどうなっていますか？",
                DEFAULT_IMG_QUESTION,
            ]
            quick_pick = st.selectbox("定番の質問から選ぶ", fortune_options, key="fortune_quick")
            if st.button("この質問を送る", use_container_width=True):
                if quick_pick != "（選んでこのボタンで送信）":
                    img = None
                    if img_source:
                        img = Image.open(img_source).convert('RGB'); img.thumbnail((800, 800))
                    disp = quick_pick if not img else f"📸 写真を送信しました。 {quick_pick}"
                    st.session_state[msg_key].append({"role": "user", "content": disp})
                    with st.spinner("星の導きを読み解いています..."):
                        reply = send_to_fortune(quick_pick, image=img)
                        st.session_state[msg_key].append({"role": "assistant", "content": reply})
                    st.rerun()

        # --- 操作ボタン（リセット ／ ロト7への橋渡し）---
        b1, b2 = st.columns(2)
        if b1.button("🔄 会話をリセット", use_container_width=True):
            for k in [msg_key, fapi_key]:
                if k in st.session_state: del st.session_state[k]
            st.rerun()
        if b2.button("🎯 今日の占いナンバーをロト7へ渡す", use_container_width=True):
            # まず、いま占い師がチャットで出している鑑定文からラッキーナンバーを拾う
            last_ai = ""
            for m in reversed(st.session_state[msg_key]):
                if m["role"] == "assistant":
                    last_ai = m["content"]
                    break
            lucky = extract_lucky_from_text(last_ai)

            # 鑑定文に数字が無い場合だけ、会話の文脈から数字だけを抽出（抽出専用ペルソナで確実に）
            if not lucky:
                with st.spinner("占いの結果からラッキーナンバーを読み取っています..."):
                    temp_msgs = st.session_state[fapi_key] + [
                        {"role": "user", "content": f"これまでの鑑定で出たロト7のラッキーナンバーを、1〜{LOTO_MAX_NUM}の数字だけカンマ区切りで出力してください。日付・年号・順位などの数字は含めないこと。説明は不要です。"}
                    ]
                    try:
                        ln = claude_chat(temp_msgs, system="あなたは占い結果から数字だけを抜き出す抽出器です。1〜37の数字をカンマ区切りで出力し、それ以外は何も書かないこと。", max_tokens=60, model=MODEL_LIGHT) or ""
                    except Exception:
                        ln = ""
                    lucky = extract_lucky_from_text(ln)

            if lucky:
                save_fortune_lucky(lucky)
                st.success(f"今日の占いナンバー {lucky} を保存しました。『🌍 予測積上げ』で「占いを軽く加味する」にチェックすると反映されます（控えめウェイト）。")
            else:
                st.warning("占い結果にラッキーナンバーが見つかりませんでした。まず占い師に占ってもらい、数字が出てから押してください。")

        st.markdown("---")

        # --- チャット履歴 ---
        for msg in st.session_state[msg_key]:
            avatar = "🔮" if msg["role"] == "assistant" else "👤"
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])

        # --- 画面下に固定される入力欄（スクロール不要）---
        prompt_text = st.chat_input("占い師に話しかける…（写真は上の「🗂」メニューから添付できます）")
        if prompt_text is not None:
            text = prompt_text.strip()
            img = None
            if img_source:
                img = Image.open(img_source).convert('RGB'); img.thumbnail((800, 800))
            if not text and img:
                text = DEFAULT_IMG_QUESTION
            if text:
                disp = text if not img else f"📸 写真を送信しました。 {text}"
                st.session_state[msg_key].append({"role": "user", "content": disp})
                with st.spinner("星の導きを読み解いています..."):
                    reply = send_to_fortune(text, image=img)
                    st.session_state[msg_key].append({"role": "assistant", "content": reply})
                st.rerun()